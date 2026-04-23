"""FLAML AutoML wrapper for automated model selection and prediction."""

import logging

import numpy as np
import pandas as pd
from flaml import AutoML
from sklearn.inspection import permutation_importance

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
        # Regression estimators for FLAML to search over. Tree models are
        # listed first (they typically outperform linear on tabular CMP data);
        # three linear fallbacks provide diversity: ElasticNet (L1+L2),
        # LassoLARS (pure L1 feature selection), and SGD (Huber loss for
        # outlier robustness). "catboost" would be a good addition but
        # requires a separate install. "ensemble=True" is broken in FLAML
        # 2.5.0 (StackingRegressor rejects FLAML's estimator wrappers).
        self._estimator_list = [
            "lgbm",
            "xgboost",
            "xgb_limitdepth",
            "rf",
            "extra_tree",
            "histgb",
            "enet",
            "lassolars",
            "sgd",
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
        import time as _time

        _wall_start = _time.monotonic()
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

        # Ensure each CV fold has ≥2 validation samples (avoids LOO
        # high-variance estimates on tiny datasets).
        n_cv = min(5, max(2, len(y) // 3))

        self.automl = AutoML()
        self.automl.fit(
            X,
            y,
            task="regression",
            time_budget=time_budget,
            estimator_list=self._estimator_list,
            eval_method="cv",
            n_splits=n_cv,
            metric="rmse",
            starting_points="data",
            early_stop=True,
            retrain_full=True,
            log_file_name="",
            verbose=0,
            seed=42,
        )

        best_model = self.automl.best_estimator

        # Honest held-out metrics via OOF predictions. We re-fit only the
        # *winning* estimator + config on each outer fold (max_iter=1), so
        # there is no HPO search per fold — just a single model fit taking
        # seconds, not minutes. This avoids the multiple-comparison bias of
        # self.automl.best_loss while being 10-50x faster than running full
        # AutoML in each fold.
        from sklearn.model_selection import KFold
        from sklearn.metrics import r2_score, mean_absolute_error, mean_squared_error

        kf = KFold(n_splits=n_cv, shuffle=True, random_state=42)
        oof_pred = np.empty(len(y), dtype=float)
        best_estimator_name = self.automl.best_estimator
        best_config = self.automl.best_config

        for train_idx, val_idx in kf.split(X):
            fold_ml = AutoML()
            # time_budget=-1 + max_iter=1: fit exactly one config, no time limit.
            fold_ml.fit(
                X.iloc[train_idx],
                y[train_idx],
                task="regression",
                time_budget=-1,
                max_iter=1,
                starting_points={best_estimator_name: [best_config]},
                estimator_list=[best_estimator_name],
                eval_method="holdout",
                retrain_full=True,
                log_file_name="",
                verbose=0,
                seed=42,
            )
            oof_pred[val_idx] = fold_ml.predict(X.iloc[val_idx])

        r2 = float(r2_score(y, oof_pred))
        mae = float(mean_absolute_error(y, oof_pred))
        rmse = float(np.sqrt(mean_squared_error(y, oof_pred)))
        self._oof_pred = oof_pred

        _wall_elapsed = round(_time.monotonic() - _wall_start, 1)
        _search_time = round(
            getattr(self.automl, "time_to_find_best_model", 0) or 0, 1
        )

        self.metrics = {
            "r2": r2,
            "rmse": rmse,
            "mae": mae,
            "n_train": self._n_train,
            "best_model": best_model,
            "time_budget": time_budget,
            "search_time": _search_time,
            "wall_time": _wall_elapsed,
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

    def predict(self, **kwargs) -> dict:
        """Predict removal for given conditions.

        Keys must match column names in PREDICTION_NUMERICAL_FEATURES
        and PREDICTION_CATEGORICAL_FEATURES (e.g. "Pressure PSI", "Wafer").
        """
        if self.automl is None:
            raise ValueError("No model trained. Run train() first.")

        all_features = (
            list(PREDICTION_NUMERICAL_FEATURES)
            + list(PREDICTION_CATEGORICAL_FEATURES)
        )
        missing = [f for f in all_features if f not in kwargs]
        if missing:
            raise ValueError(f"Missing features: {', '.join(missing)}")

        for feat in PREDICTION_NUMERICAL_FEATURES:
            val = kwargs[feat]
            if not isinstance(val, (int, float)) or val < 0:
                raise ValueError(
                    f"{feat} must be a non-negative number, got {val!r}"
                )

        row = {feat: kwargs[feat] for feat in all_features}
        X_new = pd.DataFrame([row])
        for col in PREDICTION_CATEGORICAL_FEATURES:
            X_new[col] = X_new[col].astype(self._cat_dtypes[col])

        prediction = float(self.automl.predict(X_new)[0])
        uncertainty = self._estimate_uncertainty(X_new)
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

        Uses cached out-of-fold predictions so residuals and predicted-vs-actual
        reflect true held-out performance rather than the optimistic training fit.
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

    def _estimate_uncertainty(self, X_new: pd.DataFrame) -> float:
        """Per-prediction uncertainty from tree ensemble variance.

        For bagging ensembles (RandomForest, ExtraTrees) each tree is an
        independent estimator, so the standard deviation of their predictions
        is a natural measure of how confident the model is for this specific
        input.  Inputs in well-covered regions of the feature space produce
        low variance; extrapolations or sparse regions produce high variance.

        For boosting models and linear models there is no meaningful per-tree
        spread, so we fall back to the global CV RMSE.
        """
        model = self.automl.model

        # Navigate to the underlying sklearn estimator.
        estimator = model
        for attr in ("estimator", "_model", "model"):
            inner = getattr(estimator, attr, None)
            if inner is not None and hasattr(inner, "predict"):
                estimator = inner
                break

        # Only bagging ensembles have independent trees whose spread is
        # meaningful (boosting trees are sequential corrections).
        if not hasattr(estimator, "estimators_"):
            return self.metrics["rmse"]

        try:
            X_trans = self.automl._transformer.transform(X_new)
            X_arr = X_trans.values if hasattr(X_trans, "values") else np.asarray(X_trans)
            tree_preds = np.array([
                t.predict(X_arr)[0] for t in estimator.estimators_
            ])
            return float(np.std(tree_preds))
        except Exception:
            return self.metrics["rmse"]

    def _extract_importances(self, feature_cols: list[str]) -> dict:
        """Model-agnostic feature importance via permutation on the training set.

        Measures the drop in R² when each column is shuffled. Works identically
        for tree, linear, and histogram-gradient-boosting estimators — unlike
        FLAML's native ``feature_importances_``, which returns None for
        ``histgb`` and inflated raw coefficients for ``enet`` / ``lassolars`` /
        ``sgd``. On the typical CMP dataset (<200 files) this costs <1 s.

        Negative values (shuffling helped — i.e. the feature is pure noise) are
        clipped to 0 so the bar chart always starts at zero.
        """
        X = self.train_df[feature_cols].copy()
        for col in PREDICTION_CATEGORICAL_FEATURES:
            if col in X.columns:
                X[col] = X[col].astype(self._cat_dtypes[col])
        y = self.train_df[PREDICTION_TARGET].values

        result = permutation_importance(
            self.automl,
            X,
            y,
            n_repeats=10,
            random_state=42,
            scoring="r2",
            n_jobs=1,
        )
        logger.info(
            "Permutation importance (%s): %s",
            self.automl.best_estimator,
            {c: round(float(v), 4)
             for c, v in zip(feature_cols, result.importances_mean)},
        )
        return {
            col: float(max(0.0, imp))
            for col, imp in zip(feature_cols, result.importances_mean)
        }

    def _build_leaderboard(self) -> list[dict]:
        """Build a sorted leaderboard from FLAML's search history."""
        results = []
        try:
            for estimator, config in self.automl.best_config_per_estimator.items():
                if config is not None:
                    loss = self.automl.best_loss_per_estimator.get(estimator)
                    if loss is not None:
                        results.append({
                            "model": estimator,
                            "rmse": float(loss),
                        })
        except AttributeError:
            logger.warning("Could not access FLAML leaderboard API.")
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
