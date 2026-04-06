"""FLAML AutoML wrapper for automated model selection and prediction."""

import logging

import numpy as np
import pandas as pd
from flaml import AutoML

from dashboard.constants import (
    PREDICTION_CATEGORICAL_FEATURES,
    PREDICTION_NUMERICAL_FEATURES,
    PREDICTION_TARGET,
)

logger = logging.getLogger(__name__)

_MIN_SAMPLES = 5


class AutoMLManager:
    """Manages FLAML model training, prediction, and diagnostics."""

    def __init__(self, data_manager):
        self.data_manager = data_manager
        self.automl: AutoML | None = None
        self.train_df: pd.DataFrame | None = None
        self.metrics: dict | None = None
        self.leaderboard: list[dict] | None = None
        self.feature_importances: dict | None = None
        self._n_train: int = 0
        self._oof_pred: np.ndarray | None = None
        # CategoricalDtype snapshot taken during training. Predict-time rows
        # must be cast with these exact dtypes so category→integer codes stay
        # aligned with the trained model; a fresh .astype("category") on a
        # single-row frame would reassign codes starting at 0 and silently
        # produce wrong predictions.
        self._cat_dtypes: dict | None = None
        # Regression estimators for FLAML to search over. Weighted toward tree
        # models since they outperform linear on this wafer-polishing dataset;
        # "enet" (ElasticNet) is included as the Ridge-equivalent linear
        # fallback. Used by both the outer fit and the nested-CV metric loop.
        # Note: "lrl2" is LogisticRegression (classification-only); "enet"
        # is the regression-capable L2-regularized linear model in FLAML.
        # "catboost" would be a good addition but requires a separate install.
        self._estimator_list = [
            "lgbm",
            "xgboost",
            "xgb_limitdepth",
            "rf",
            "extra_tree",
            "histgb",
            "enet",
        ]

    def prepare_data(self) -> pd.DataFrame:
        """Return cleaned DataFrame with rows having valid Removal > 0.
        Raises ValueError when insufficient data is available.
        """
        df = self.data_manager.get_all_data()
        if df.empty:
            raise ValueError("No data loaded.")

        required = (
            PREDICTION_CATEGORICAL_FEATURES
            + PREDICTION_NUMERICAL_FEATURES
            + [PREDICTION_TARGET, "File Name"]
        )
        missing = [c for c in required if c not in df.columns]
        if missing:
            raise ValueError(f"Missing columns: {', '.join(missing)}")

        df = df[required].copy()
        df = df[df[PREDICTION_TARGET] > 0].reset_index(drop=True)

        if len(df) < _MIN_SAMPLES:
            raise ValueError(
                f"Only {len(df)} file(s) have Removal data. "
                f"Need at least {_MIN_SAMPLES}."
            )

        for col in PREDICTION_CATEGORICAL_FEATURES:
            df[col] = df[col].fillna("Unknown").replace("", "Unknown")

        return df

    def train(self, time_budget: int = 60) -> dict:
        """Run FLAML AutoML and return a results summary."""
        df = self.prepare_data()
        self.train_df = df
        self._n_train = len(df)

        feature_cols = list(PREDICTION_NUMERICAL_FEATURES) + list(
            PREDICTION_CATEGORICAL_FEATURES
        )
        X = df[feature_cols].copy()
        y = df[PREDICTION_TARGET].values

        for col in PREDICTION_CATEGORICAL_FEATURES:
            X[col] = X[col].astype("category")

        # Snapshot the training CategoricalDtype per column so predict() can
        # apply the identical category→code mapping to incoming rows.
        self._cat_dtypes = {
            col: X[col].dtype for col in PREDICTION_CATEGORICAL_FEATURES
        }

        self.automl = AutoML()
        self.automl.fit(
            X,
            y,
            task="regression",
            time_budget=time_budget,
            estimator_list=self._estimator_list,
            eval_method="cv",
            n_splits=min(5, len(y)),
            metric="rmse",
            verbose=0,
            seed=42,
        )

        best_model = self.automl.best_estimator

        # Honest held-out metrics via nested CV. We do NOT use self.automl.best_loss
        # because it is multiple-comparison biased (best-of-many-searches), and we
        # do NOT use self.automl.predict(X) because that evaluates on training data.
        # Instead, re-run FLAML on each outer fold and collect out-of-fold predictions.
        from sklearn.model_selection import KFold
        from sklearn.metrics import r2_score, mean_absolute_error, mean_squared_error

        outer_k = min(5, len(y))
        kf = KFold(n_splits=outer_k, shuffle=True, random_state=42)
        oof_pred = np.empty(len(y), dtype=float)
        inner_budget = max(10, time_budget // outer_k)

        for train_idx, val_idx in kf.split(X):
            fold_automl = AutoML()
            fold_automl.fit(
                X.iloc[train_idx],
                y[train_idx],
                task="regression",
                time_budget=inner_budget,
                estimator_list=self._estimator_list,
                eval_method="cv",
                n_splits=min(5, len(train_idx)),
                metric="rmse",
                verbose=0,
                seed=42,
            )
            oof_pred[val_idx] = fold_automl.predict(X.iloc[val_idx])

        r2 = float(r2_score(y, oof_pred))
        mae = float(mean_absolute_error(y, oof_pred))
        rmse = float(np.sqrt(mean_squared_error(y, oof_pred)))
        self._oof_pred = oof_pred

        self.metrics = {
            "r2": r2,
            "rmse": rmse,
            "mae": mae,
            "n_train": self._n_train,
            "best_model": best_model,
            "time_budget": time_budget,
        }

        self.feature_importances = self._extract_importances(feature_cols)
        self.leaderboard = self._build_leaderboard()
        warnings = self._build_warnings(df)

        return {
            "best_model": best_model,
            "leaderboard": self.leaderboard,
            "metrics": self.metrics,
            "feature_importances": self.feature_importances,
            "n_train": self._n_train,
            "warnings": warnings,
        }

    def predict(
        self,
        pressure_psi: float,
        polish_time: float,
        wafer: str,
        pad: str,
        slurry: str,
        conditioner: str,
    ) -> dict:
        """Predict removal for given conditions."""
        if self.automl is None:
            raise ValueError("No model trained. Run train() first.")

        row = {
            "Pressure PSI": pressure_psi,
            "Polish Time": polish_time,
            "Wafer": wafer,
            "Pad": pad,
            "Slurry": slurry,
            "Conditioner": conditioner,
        }
        X_new = pd.DataFrame([row])
        for col in PREDICTION_CATEGORICAL_FEATURES:
            X_new[col] = X_new[col].astype(self._cat_dtypes[col])

        prediction = float(self.automl.predict(X_new)[0])
        uncertainty = self.metrics["rmse"]
        clamped = prediction < 0
        prediction = max(0.0, prediction)

        return {
            "prediction": prediction,
            "uncertainty": uncertainty,
            "clamped": clamped,
            "model": self.metrics["best_model"],
            "r2": self.metrics["r2"],
            "n_train": self._n_train,
        }

    def get_category_options(self) -> dict:
        """Return sorted training values per categorical column.

        Used by the UI to populate dropdown options after training, and by
        the agent's tool to validate/resolve user-supplied category strings.
        Returns an empty dict until train() has been called.
        """
        if self._cat_dtypes is None:
            return {}
        return {
            col: [str(v) for v in dtype.categories]
            for col, dtype in self._cat_dtypes.items()
        }

    def get_diagnostics(self) -> dict:
        """Return model diagnostics for the current trained model.

        Uses cached out-of-fold predictions from nested CV so residuals and
        predicted-vs-actual reflect true held-out performance rather than
        the optimistic training fit.
        """
        if self.automl is None or self._oof_pred is None:
            raise ValueError("No model trained.")

        df = self.train_df
        y = df[PREDICTION_TARGET].values
        y_pred = self._oof_pred
        residuals = y - y_pred

        return {
            "residual_mean": float(np.mean(residuals)),
            "residual_std": float(np.std(residuals)),
            "residual_min": float(np.min(residuals)),
            "residual_max": float(np.max(residuals)),
            "metrics": self.metrics,
            "feature_importances": self.feature_importances,
            "best_config": str(self.automl.best_config),
            "warnings": self._build_warnings(df),
            "y_true": y.tolist(),
            "y_pred": y_pred.tolist(),
            "file_names": df["File Name"].tolist(),
        }

    def _extract_importances(self, feature_cols: list[str]) -> dict:
        """Extract feature importances from the best FLAML model.

        FLAML's DataTransformer may drop constant columns (e.g. Polish Time
        or Slurry when they have a single unique value), so the model may see
        fewer features than ``feature_cols``. When that happens, we read the
        actual post-transform column names from the transformer rather than
        falling back to generic ``feature_0`` labels.
        """
        model = self.automl.model
        importances = None
        if hasattr(model, "feature_importances_") and model.feature_importances_ is not None:
            importances = model.feature_importances_
        elif hasattr(model, "coef_") and model.coef_ is not None:
            importances = np.abs(model.coef_)
        else:
            estimator = model
            if hasattr(model, "named_steps"):
                estimator = model.named_steps.get(
                    "model", model.named_steps.get("estimator", model)
                )
            if hasattr(estimator, "feature_importances_") and estimator.feature_importances_ is not None:
                importances = estimator.feature_importances_
            elif hasattr(estimator, "coef_") and estimator.coef_ is not None:
                importances = np.abs(estimator.coef_)

        if importances is None:
            return {col: 0.0 for col in feature_cols}

        # Determine the correct column names for the importance vector.
        names = feature_cols
        if len(importances) != len(feature_cols):
            # The transformer dropped constant columns — get the actual names
            # from a single-row transform so labels stay meaningful.
            try:
                X_sample = self.train_df[feature_cols].head(1).copy()
                for col in PREDICTION_CATEGORICAL_FEATURES:
                    if col in X_sample.columns:
                        X_sample[col] = X_sample[col].astype(
                            self._cat_dtypes[col]
                        )
                X_trans = self.automl._transformer.transform(X_sample)
                if hasattr(X_trans, "columns") and len(X_trans.columns) == len(
                    importances
                ):
                    names = list(X_trans.columns)
            except Exception:
                pass  # fall through to best-effort below

        if len(importances) == len(names):
            return {col: float(imp) for col, imp in zip(names, importances)}
        # Last resort — still use indexed names but shouldn't happen now
        return {f"feature_{i}": float(v) for i, v in enumerate(importances)}

    def _build_leaderboard(self) -> list[dict]:
        """Build a sorted leaderboard from FLAML's search history."""
        results = []
        if hasattr(self.automl, "best_config_per_estimator"):
            for estimator, config in self.automl.best_config_per_estimator.items():
                if config is not None:
                    loss = self.automl.best_loss_per_estimator.get(estimator)
                    if loss is not None:
                        results.append({
                            "model": estimator,
                            "rmse": float(loss),
                        })
        results.sort(key=lambda x: x["rmse"])
        return results[:5]

    def _build_warnings(self, df: pd.DataFrame) -> list[str]:
        """Build data quality warnings."""
        warnings = []
        n = len(df)
        if n < 20:
            warnings.append(
                f"Only {n} files have Removal data. Model accuracy may be limited."
            )
        for col in PREDICTION_CATEGORICAL_FEATURES:
            counts = df[col].value_counts()
            singles = counts[counts == 1].index.tolist()
            if singles:
                warnings.append(
                    f"{col} has single-sample categories: "
                    f"{', '.join(str(s) for s in singles)}."
                )
        for col in PREDICTION_NUMERICAL_FEATURES:
            if df[col].nunique() <= 1:
                warnings.append(
                    f"{col} is constant — model cannot learn its effect."
                )
        return warnings
