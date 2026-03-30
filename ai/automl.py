"""FLAML AutoML wrapper for automated model selection and prediction."""

import logging
from typing import Any

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

        self.automl = AutoML()
        self.automl.fit(
            X,
            y,
            task="regression",
            time_budget=time_budget,
            estimator_list=["lgbm", "xgboost", "rf", "extra_tree"],
            eval_method="cv",
            n_splits=min(5, len(y)),
            metric="rmse",
            verbose=0,
            seed=42,
        )

        best_model = self.automl.best_estimator
        best_loss = self.automl.best_loss

        # Compute R² and MAE from training predictions
        # (avoid cross_val_score which breaks with FLAML's XGBoost wrapper)
        y_pred = self.automl.predict(X)
        from sklearn.metrics import r2_score, mean_absolute_error
        r2 = r2_score(y, y_pred)
        mae = mean_absolute_error(y, y_pred)

        self.metrics = {
            "r2": float(r2),
            "rmse": float(best_loss),
            "mae": float(mae),
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
            X_new[col] = X_new[col].astype("category")

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

    def get_diagnostics(self) -> dict:
        """Return model diagnostics for the current trained model."""
        if self.automl is None:
            raise ValueError("No model trained.")

        df = self.train_df
        feature_cols = list(PREDICTION_NUMERICAL_FEATURES) + list(
            PREDICTION_CATEGORICAL_FEATURES
        )
        X = df[feature_cols].copy()
        for col in PREDICTION_CATEGORICAL_FEATURES:
            X[col] = X[col].astype("category")
        y = df[PREDICTION_TARGET].values

        y_pred = self.automl.predict(X)
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
        """Extract feature importances from the best FLAML model."""
        model = self.automl.model
        if hasattr(model, "feature_importances_"):
            importances = model.feature_importances_
        elif hasattr(model, "coef_"):
            importances = np.abs(model.coef_)
        else:
            estimator = model
            if hasattr(model, "named_steps"):
                estimator = model.named_steps.get(
                    "model", model.named_steps.get("estimator", model)
                )
            if hasattr(estimator, "feature_importances_"):
                importances = estimator.feature_importances_
            elif hasattr(estimator, "coef_"):
                importances = np.abs(estimator.coef_)
            else:
                return {col: 0.0 for col in feature_cols}

        if len(importances) != len(feature_cols):
            return {f"feature_{i}": float(v) for i, v in enumerate(importances)}

        return {col: float(imp) for col, imp in zip(feature_cols, importances)}

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
