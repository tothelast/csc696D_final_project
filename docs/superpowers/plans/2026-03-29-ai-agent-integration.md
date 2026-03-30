# AI Agent Integration — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Predict Removal tab with a conversational AI agent powered by FLAML (AutoML) and Qwen3 8B (Ollama) that automatically builds ML models, explains results, and generates charts — all offline.

**Architecture:** New `ai/` module with 6 files. Agent Engine runs in a background thread, communicates with bundled Ollama on port 11435. Tools are thin wrappers around existing `DataManager` + new FLAML logic. Chat UI is a Dash tab replacing Predict Removal. Existing code is modified minimally (4 files touched, 1 removed).

**Tech Stack:** FLAML (AutoML), ollama-python (LLM client), Qwen3 8B (model), Dash (chat UI), Plotly (charts)

---

## File Map

### New Files

| File | Responsibility |
|------|---------------|
| `ai/__init__.py` | Package init, exports `AgentEngine`, `OllamaManager` |
| `ai/ollama_manager.py` | Start/stop/health-check the bundled Ollama process |
| `ai/automl.py` | FLAML wrapper: train, predict, diagnostics, leaderboard |
| `ai/tools.py` | 13 tool functions (data query, ML, chart generation) for the LLM |
| `ai/agent.py` | `AgentEngine` class: conversation loop, tool dispatch, streaming |
| `ai/callbacks_agent.py` | Dash callbacks for the AI Agent tab (send, poll, tab-open) |

### Modified Files

| File | Change |
|------|--------|
| `dashboard/layouts.py` | Replace `build_prediction_tab()` with `build_agent_tab()` |
| `dashboard/callbacks.py` | Replace prediction callback import/registration with agent |
| `dashboard/styles.py` | Add CSS for chat UI components |
| `desktop/main_window.py` | Add Ollama startup in `on_advanced_analysis()`, shutdown in `closeEvent()` |
| `requirements.txt` | Add `flaml[automl]` and `ollama` |

### Removed Files

| File | Reason |
|------|--------|
| `dashboard/callbacks_prediction.py` | Replaced by `ai/automl.py` + `ai/callbacks_agent.py` |

---

## Task 1: Install Dependencies

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: Add new dependencies to requirements.txt**

Add these lines to the end of `requirements.txt`:

```
# AI Agent
flaml[automl]>=2.5.0
ollama>=0.4.0
```

- [ ] **Step 2: Install dependencies**

Run: `pip install -r requirements.txt`
Expected: All packages install successfully, including `lightgbm` and `xgboost` (pulled in by `flaml[automl]`).

- [ ] **Step 3: Verify imports work**

Run: `python -c "from flaml import AutoML; import ollama; print('OK')"`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add requirements.txt
git commit -m "Add FLAML and ollama dependencies for AI agent"
```

---

## Task 2: Ollama Process Manager

**Files:**
- Create: `ai/__init__.py`
- Create: `ai/ollama_manager.py`

- [ ] **Step 1: Create `ai/__init__.py`**

```python
"""AI agent module — LLM-powered analytics assistant."""
```

- [ ] **Step 2: Create `ai/ollama_manager.py`**

```python
"""Manage the lifecycle of a bundled Ollama process."""

import logging
import os
import platform
import subprocess
import time

import requests

logger = logging.getLogger(__name__)

# Default port avoids conflict with any user-installed Ollama on 11434
_DEFAULT_PORT = 11435
_HEALTH_TIMEOUT = 30  # seconds to wait for Ollama to become ready
_MODEL_NAME = "qwen3:8b"


class OllamaManager:
    """Start, monitor, and stop a bundled Ollama server process."""

    def __init__(self, port: int = _DEFAULT_PORT):
        self.port = port
        self.base_url = f"http://localhost:{self.port}"
        self._process: subprocess.Popen | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> bool:
        """Start Ollama and wait until it's healthy.

        Returns True if Ollama is ready and the model is available.
        Returns False on failure (caller should degrade gracefully).
        """
        if self.is_healthy():
            logger.info("Ollama already running on port %d", self.port)
            return self._model_available()

        binary = self._find_binary()
        if not binary:
            logger.error("Ollama binary not found")
            return False

        env = os.environ.copy()
        env["OLLAMA_HOST"] = f"0.0.0.0:{self.port}"

        # Point to bundled models directory if it exists
        models_dir = self._find_models_dir()
        if models_dir:
            env["OLLAMA_MODELS"] = models_dir

        try:
            self._process = subprocess.Popen(
                [binary, "serve"],
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
            )
        except OSError as exc:
            logger.error("Failed to start Ollama: %s", exc)
            return False

        if not self._wait_healthy():
            logger.error("Ollama did not become healthy within %ds", _HEALTH_TIMEOUT)
            self.stop()
            return False

        if not self._model_available():
            logger.error("Model %s is not available", _MODEL_NAME)
            self.stop()
            return False

        logger.info("Ollama ready on port %d with model %s", self.port, _MODEL_NAME)
        return True

    def stop(self):
        """Terminate the Ollama process if we own it."""
        if self._process is not None:
            self._process.terminate()
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()
            self._process = None
            logger.info("Ollama process stopped")

    def is_healthy(self) -> bool:
        """Return True if Ollama is responding on our port."""
        try:
            r = requests.get(f"{self.base_url}/api/version", timeout=2)
            return r.status_code == 200
        except requests.ConnectionError:
            return False

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _wait_healthy(self) -> bool:
        """Poll until Ollama responds or timeout expires."""
        deadline = time.time() + _HEALTH_TIMEOUT
        while time.time() < deadline:
            if self.is_healthy():
                return True
            time.sleep(0.5)
        return False

    def _model_available(self) -> bool:
        """Check if the required model is present."""
        try:
            r = requests.get(f"{self.base_url}/api/tags", timeout=5)
            if r.status_code != 200:
                return False
            models = r.json().get("models", [])
            return any(_MODEL_NAME in m.get("name", "") for m in models)
        except requests.ConnectionError:
            return False

    def _find_binary(self) -> str | None:
        """Locate the Ollama binary: bundled first, then system PATH."""
        # Check bundled location relative to project root
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        system = platform.system().lower()

        if system == "windows":
            bundled = os.path.join(project_root, "ollama", "windows", "ollama.exe")
        else:
            bundled = os.path.join(project_root, "ollama", "linux", "ollama")

        if os.path.isfile(bundled):
            return bundled

        # Fallback: system-installed ollama
        import shutil
        return shutil.which("ollama")

    def _find_models_dir(self) -> str | None:
        """Locate the bundled models directory."""
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        models_dir = os.path.join(project_root, "ollama", "models")
        if os.path.isdir(models_dir):
            return models_dir
        return None
```

- [ ] **Step 3: Verify module imports**

Run: `python -c "from ai.ollama_manager import OllamaManager; print('OK')"`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add ai/__init__.py ai/ollama_manager.py
git commit -m "Add Ollama process manager for bundled binary lifecycle"
```

---

## Task 3: FLAML AutoML Wrapper

**Files:**
- Create: `ai/automl.py`

This module wraps FLAML and preserves the data preparation logic from `callbacks_prediction.py`.

- [ ] **Step 1: Create `ai/automl.py`**

```python
"""FLAML AutoML wrapper for automated model selection and prediction."""

import logging
import pickle
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

    # ------------------------------------------------------------------
    # Data preparation (adapted from callbacks_prediction._prepare_data)
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Training
    # ------------------------------------------------------------------

    def train(self, time_budget: int = 60) -> dict:
        """Run FLAML AutoML and return a results summary.

        Returns dict with keys: best_model, leaderboard, metrics,
        feature_importances, n_train, warnings.
        """
        df = self.prepare_data()
        self.train_df = df
        self._n_train = len(df)

        feature_cols = list(PREDICTION_NUMERICAL_FEATURES) + list(
            PREDICTION_CATEGORICAL_FEATURES
        )
        X = df[feature_cols].copy()
        y = df[PREDICTION_TARGET].values

        # Convert categoricals to pandas category dtype for FLAML
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

        # Extract results
        best_model = self.automl.best_estimator
        best_loss = self.automl.best_loss  # RMSE (lower is better)

        # Compute R² and MAE via cross-validation on best config
        from sklearn.model_selection import cross_val_score, KFold

        cv = KFold(n_splits=min(5, len(y)), shuffle=True, random_state=42)
        best_pipeline = self.automl.model
        r2_scores = cross_val_score(best_pipeline, X, y, cv=cv, scoring="r2")
        mae_scores = cross_val_score(
            best_pipeline, X, y, cv=cv, scoring="neg_mean_absolute_error"
        )

        self.metrics = {
            "r2": float(np.mean(r2_scores)),
            "rmse": float(best_loss),
            "mae": float(-np.mean(mae_scores)),
            "n_train": self._n_train,
            "best_model": best_model,
            "time_budget": time_budget,
        }

        # Feature importances from the best model
        self.feature_importances = self._extract_importances(feature_cols)

        # Build leaderboard from FLAML's search history
        self.leaderboard = self._build_leaderboard()

        # Data quality warnings
        warnings = self._build_warnings(df)

        return {
            "best_model": best_model,
            "leaderboard": self.leaderboard,
            "metrics": self.metrics,
            "feature_importances": self.feature_importances,
            "n_train": self._n_train,
            "warnings": warnings,
        }

    # ------------------------------------------------------------------
    # Prediction
    # ------------------------------------------------------------------

    def predict(
        self,
        pressure_psi: float,
        polish_time: float,
        wafer: str,
        pad: str,
        slurry: str,
        conditioner: str,
    ) -> dict:
        """Predict removal for given conditions.

        Returns dict with keys: prediction, uncertainty, model_info.
        Raises ValueError if no model is trained.
        """
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

        # Uncertainty: use RMSE from cross-validation
        uncertainty = self.metrics["rmse"]

        # Clamp negative predictions
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

    # ------------------------------------------------------------------
    # Diagnostics
    # ------------------------------------------------------------------

    def get_diagnostics(self) -> dict:
        """Return model diagnostics for the current trained model.

        Returns dict with residual stats, CV fold scores, warnings,
        and hyperparameters.
        """
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

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _extract_importances(self, feature_cols: list[str]) -> dict:
        """Extract feature importances from the best FLAML model."""
        model = self.automl.model
        if hasattr(model, "feature_importances_"):
            importances = model.feature_importances_
        elif hasattr(model, "coef_"):
            importances = np.abs(model.coef_)
        else:
            # Try to get from the estimator inside a pipeline
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
```

- [ ] **Step 2: Verify imports**

Run: `python -c "from ai.automl import AutoMLManager; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add ai/automl.py
git commit -m "Add FLAML AutoML wrapper for automated model training"
```

---

## Task 4: Tool Definitions

**Files:**
- Create: `ai/tools.py`

These are the 13 functions the LLM can call. Each has type-annotated arguments and a docstring (Ollama auto-generates schemas from these).

- [ ] **Step 1: Create `ai/tools.py`**

```python
"""Tool functions for the AI agent.

Each function is a thin wrapper around DataManager or AutoMLManager.
The ollama-python library auto-generates JSON schemas from the type
annotations and docstrings.
"""

import json
import logging

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from dashboard.constants import (
    ANALYSIS_FEATURES,
    CATEGORICAL_FEATURES,
    PREDICTION_CATEGORICAL_FEATURES,
    PREDICTION_NUMERICAL_FEATURES,
)
from dashboard.plotly_theme import DARK_LAYOUT, CLUSTER_COLORS
from desktop.theme import COLORS

logger = logging.getLogger(__name__)


class AgentTools:
    """Container for all agent tool functions.

    Instantiated with references to DataManager and AutoMLManager so that
    tool functions can access app state.
    """

    def __init__(self, data_manager, automl_manager):
        self.dm = data_manager
        self.ml = automl_manager

    # ------------------------------------------------------------------
    # Data Tools
    # ------------------------------------------------------------------

    def get_dataset_summary(self) -> str:
        """Get an overview of all loaded polishing data including file count, feature ranges, and categorical value counts.

        Returns:
            Summary of loaded dataset as formatted text.
        """
        df = self.dm.get_all_data()
        if df.empty:
            return "No data loaded."

        n_files = len(df)
        has_removal = int((df.get("Removal", pd.Series(dtype=float)) > 0).sum())

        lines = [f"Dataset: {n_files} polishing files, {has_removal} with removal data."]

        # Numerical ranges
        for feat in PREDICTION_NUMERICAL_FEATURES:
            if feat in df.columns:
                lines.append(
                    f"  {feat}: {df[feat].min():.2f} – {df[feat].max():.2f} "
                    f"(mean {df[feat].mean():.2f})"
                )

        if "Removal" in df.columns:
            valid = df[df["Removal"] > 0]["Removal"]
            if not valid.empty:
                lines.append(
                    f"  Removal: {valid.min():.0f} – {valid.max():.0f} Å "
                    f"(mean {valid.mean():.0f} Å)"
                )

        # Categorical counts
        for cat in CATEGORICAL_FEATURES:
            if cat in df.columns:
                vals = df[cat].replace("", "Unknown").fillna("Unknown")
                counts = vals.value_counts()
                top = ", ".join(f"{v} ({c})" for v, c in counts.head(5).items())
                lines.append(f"  {cat}: {len(counts)} types — {top}")

        return "\n".join(lines)

    def get_file_details(self, filename: str) -> str:
        """Get detailed metrics for a specific polishing run file.

        Args:
            filename: The .dat filename (e.g. 'run_023.dat').

        Returns:
            Summary metrics and categorical attributes for the file.
        """
        df = self.dm.get_all_data()
        if df.empty:
            return "No data loaded."

        row = df[df["File Name"] == filename]
        if row.empty:
            available = ", ".join(df["File Name"].tolist()[:10])
            return f"File '{filename}' not found. Available: {available}"

        row = row.iloc[0]
        lines = [f"File: {filename}"]

        # Key metrics
        metric_cols = [
            "COF", "Fz", "Var Fz", "Mean Temp", "Init Temp", "High Temp",
            "Removal", "WIWNU", "Pressure PSI", "Polish Time",
            "Mean Pressure", "Mean Velocity", "P.V", "Removal Rate",
        ]
        for col in metric_cols:
            if col in row.index and pd.notna(row[col]):
                lines.append(f"  {col}: {row[col]:.4g}")

        # Categoricals
        for cat in CATEGORICAL_FEATURES:
            if cat in row.index:
                lines.append(f"  {cat}: {row[cat] or 'Not set'}")

        return "\n".join(lines)

    def get_feature_statistics(self, feature: str, group_by: str = None) -> str:
        """Get descriptive statistics for a feature, optionally grouped by a categorical.

        Args:
            feature: Column name (e.g. 'COF', 'Removal', 'Mean Temp').
            group_by: Optional categorical to group by ('Wafer', 'Pad', 'Slurry', or 'Conditioner').

        Returns:
            Mean, std, min, max, median, optionally broken down by group.
        """
        df = self.dm.get_all_data()
        if df.empty:
            return "No data loaded."

        if feature not in df.columns:
            available = [c for c in df.columns if c not in ("file_id",)]
            return f"Feature '{feature}' not found. Available: {', '.join(available[:15])}"

        if group_by and group_by in df.columns:
            grouped = df.groupby(group_by)[feature]
            lines = [f"Statistics for {feature} grouped by {group_by}:"]
            for name, group in grouped:
                valid = group.dropna()
                if not valid.empty:
                    lines.append(
                        f"  {name}: mean={valid.mean():.4g}, std={valid.std():.4g}, "
                        f"min={valid.min():.4g}, max={valid.max():.4g}, "
                        f"median={valid.median():.4g}, n={len(valid)}"
                    )
            return "\n".join(lines)

        valid = df[feature].dropna()
        return (
            f"Statistics for {feature} (n={len(valid)}):\n"
            f"  mean={valid.mean():.4g}, std={valid.std():.4g}\n"
            f"  min={valid.min():.4g}, max={valid.max():.4g}\n"
            f"  median={valid.median():.4g}"
        )

    def detect_outliers(self, feature: str) -> str:
        """Find outlier files for a given feature using the IQR method.

        Args:
            feature: Column name to check for outliers (e.g. 'Removal', 'COF').

        Returns:
            List of outlier files with their values and how far they deviate.
        """
        df = self.dm.get_all_data()
        if df.empty:
            return "No data loaded."

        if feature not in df.columns:
            return f"Feature '{feature}' not found."

        valid = df[[feature, "File Name"]].dropna(subset=[feature])
        q1 = valid[feature].quantile(0.25)
        q3 = valid[feature].quantile(0.75)
        iqr = q3 - q1

        if iqr == 0:
            return f"No variation in {feature} — all values are equal."

        lower = q1 - 1.5 * iqr
        upper = q3 + 1.5 * iqr
        outliers = valid[(valid[feature] < lower) | (valid[feature] > upper)]

        if outliers.empty:
            return f"No outliers found for {feature} (IQR method, Q1={q1:.4g}, Q3={q3:.4g})."

        lines = [
            f"Outliers for {feature} (IQR: {iqr:.4g}, bounds: [{lower:.4g}, {upper:.4g}]):"
        ]
        for _, row in outliers.iterrows():
            val = row[feature]
            direction = "above" if val > upper else "below"
            deviation = abs(val - upper) if val > upper else abs(val - lower)
            lines.append(
                f"  {row['File Name']}: {val:.4g} ({direction} by {deviation:.4g})"
            )
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # ML Tools
    # ------------------------------------------------------------------

    def run_automl(self, time_budget: int = 60) -> str:
        """Train and evaluate multiple ML pipelines using AutoML to find the best model.

        Args:
            time_budget: Maximum seconds to search for the best model. Default 60.

        Returns:
            Best model name, top-5 leaderboard, cross-validation metrics, and feature importances.
        """
        try:
            results = self.ml.train(time_budget=time_budget)
        except ValueError as exc:
            return f"Cannot train: {exc}"

        lines = [f"AutoML complete. Best model: {results['best_model']}"]
        lines.append(
            f"Metrics: R²={results['metrics']['r2']:.3f}, "
            f"RMSE={results['metrics']['rmse']:.0f}Å, "
            f"MAE={results['metrics']['mae']:.0f}Å, "
            f"trained on {results['n_train']} files."
        )

        if results["leaderboard"]:
            lines.append("\nLeaderboard:")
            for i, entry in enumerate(results["leaderboard"], 1):
                lines.append(f"  {i}. {entry['model']} — RMSE={entry['rmse']:.0f}Å")

        if results["feature_importances"]:
            sorted_imp = sorted(
                results["feature_importances"].items(), key=lambda x: x[1], reverse=True
            )
            lines.append("\nFeature importances:")
            for name, imp in sorted_imp:
                lines.append(f"  {name}: {imp:.4f}")

        if results["warnings"]:
            lines.append("\nWarnings:")
            for w in results["warnings"]:
                lines.append(f"  - {w}")

        return "\n".join(lines)

    def predict_removal(
        self,
        pressure_psi: float,
        polish_time: float,
        wafer: str,
        pad: str,
        slurry: str,
        conditioner: str,
    ) -> str:
        """Predict material removal for given polishing conditions.

        Args:
            pressure_psi: Down force pressure in PSI.
            polish_time: Polish duration in minutes.
            wafer: Wafer type identifier.
            pad: Pad type identifier.
            slurry: Slurry type identifier.
            conditioner: Conditioner disk type identifier.

        Returns:
            Predicted removal in Angstroms with uncertainty estimate and model info.
        """
        try:
            result = self.ml.predict(
                pressure_psi=pressure_psi,
                polish_time=polish_time,
                wafer=wafer,
                pad=pad,
                slurry=slurry,
                conditioner=conditioner,
            )
        except ValueError as exc:
            return f"Cannot predict: {exc}"

        lines = [
            f"Predicted Removal: {result['prediction']:.0f} Å",
            f"Uncertainty: ±{result['uncertainty']:.0f} Å",
            f"Model: {result['model']} (R²={result['r2']:.3f}, trained on {result['n_train']} files)",
        ]
        if result["clamped"]:
            lines.append("Note: prediction was negative and clamped to 0.")
        return "\n".join(lines)

    def get_model_diagnostics(self) -> str:
        """Get detailed diagnostics for the currently trained model.

        Returns:
            Residual statistics, cross-validation metrics, data quality warnings, and model hyperparameters.
        """
        try:
            diag = self.ml.get_diagnostics()
        except ValueError as exc:
            return f"Cannot get diagnostics: {exc}"

        lines = [
            f"Model: {diag['metrics']['best_model']}",
            f"R²={diag['metrics']['r2']:.3f}, RMSE={diag['metrics']['rmse']:.0f}Å, MAE={diag['metrics']['mae']:.0f}Å",
            f"Trained on {diag['metrics']['n_train']} files.",
            f"\nResiduals: mean={diag['residual_mean']:.1f}, std={diag['residual_std']:.1f}, "
            f"range=[{diag['residual_min']:.1f}, {diag['residual_max']:.1f}]",
            f"\nBest config: {diag['best_config']}",
        ]
        if diag["warnings"]:
            lines.append("\nWarnings:")
            for w in diag["warnings"]:
                lines.append(f"  - {w}")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Chart Tools
    # ------------------------------------------------------------------

    def generate_scatter(
        self,
        x_feature: str,
        y_feature: str,
        color_by: str = None,
        filter_column: str = None,
        filter_value: str = None,
    ) -> dict:
        """Generate a scatter plot of two features from the dataset.

        Args:
            x_feature: Feature name for the x-axis.
            y_feature: Feature name for the y-axis.
            color_by: Optional categorical feature for color coding points.
            filter_column: Optional column name to filter data on.
            filter_value: Optional value to filter for in filter_column.

        Returns:
            Plotly figure as a JSON-serializable dictionary.
        """
        df = self.dm.get_all_data()
        if df.empty:
            return self._empty_fig("No data loaded.")

        if filter_column and filter_value and filter_column in df.columns:
            df = df[df[filter_column] == filter_value]

        fig = go.Figure()
        if color_by and color_by in df.columns:
            for i, (group, group_df) in enumerate(df.groupby(color_by)):
                fig.add_trace(go.Scatter(
                    x=group_df.get(x_feature),
                    y=group_df.get(y_feature),
                    mode="markers",
                    name=str(group),
                    marker=dict(size=9, color=CLUSTER_COLORS[i % len(CLUSTER_COLORS)]),
                    text=group_df.get("File Name"),
                    hovertemplate=f"<b>%{{text}}</b><br>{x_feature}: %{{x:.4g}}<br>{y_feature}: %{{y:.4g}}<extra>{group}</extra>",
                ))
        else:
            fig.add_trace(go.Scatter(
                x=df.get(x_feature),
                y=df.get(y_feature),
                mode="markers",
                marker=dict(size=9, color=COLORS["accent"]),
                text=df.get("File Name"),
                hovertemplate=f"<b>%{{text}}</b><br>{x_feature}: %{{x:.4g}}<br>{y_feature}: %{{y:.4g}}<extra></extra>",
            ))

        fig.update_layout(**DARK_LAYOUT)
        fig.update_layout(
            title=f"{y_feature} vs {x_feature}",
            xaxis_title=x_feature,
            yaxis_title=y_feature,
        )
        return fig.to_plotly_json()

    def generate_distribution(self, feature: str, group_by: str = None) -> dict:
        """Generate a histogram or box plot for a feature.

        Args:
            feature: Feature name to plot.
            group_by: Optional categorical feature for grouped box plot.

        Returns:
            Plotly figure as a JSON-serializable dictionary.
        """
        df = self.dm.get_all_data()
        if df.empty:
            return self._empty_fig("No data loaded.")

        fig = go.Figure()
        if group_by and group_by in df.columns:
            for i, (group, group_df) in enumerate(df.groupby(group_by)):
                fig.add_trace(go.Box(
                    y=group_df.get(feature),
                    name=str(group),
                    marker_color=CLUSTER_COLORS[i % len(CLUSTER_COLORS)],
                ))
            fig.update_layout(title=f"{feature} by {group_by}")
        else:
            fig.add_trace(go.Histogram(
                x=df.get(feature),
                marker_color=COLORS["accent"],
                marker_line=dict(color=COLORS["border_light"], width=1),
                opacity=0.85,
            ))
            fig.update_layout(title=f"Distribution of {feature}")

        fig.update_layout(**DARK_LAYOUT)
        fig.update_layout(yaxis_title="Count" if not group_by else feature)
        return fig.to_plotly_json()

    def generate_bar_chart(self, feature: str, group_by: str) -> dict:
        """Generate a grouped bar chart showing means with error bars.

        Args:
            feature: Numerical feature for the y-axis values.
            group_by: Categorical feature for grouping bars.

        Returns:
            Plotly figure as a JSON-serializable dictionary.
        """
        df = self.dm.get_all_data()
        if df.empty:
            return self._empty_fig("No data loaded.")

        grouped = df.groupby(group_by)[feature]
        means = grouped.mean()
        stds = grouped.std().fillna(0)

        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=means.index.astype(str),
            y=means.values,
            error_y=dict(type="data", array=stds.values, visible=True),
            marker_color=COLORS["accent"],
        ))

        fig.update_layout(**DARK_LAYOUT)
        fig.update_layout(
            title=f"Mean {feature} by {group_by}",
            xaxis_title=group_by,
            yaxis_title=feature,
        )
        return fig.to_plotly_json()

    def generate_correlation_heatmap(self, features: list[str] = None) -> dict:
        """Generate a correlation matrix heatmap for numerical features.

        Args:
            features: Optional list of feature names. Defaults to all numerical analysis features.

        Returns:
            Plotly figure as a JSON-serializable dictionary.
        """
        df = self.dm.get_all_data()
        if df.empty:
            return self._empty_fig("No data loaded.")

        if features is None:
            features = [f for f in ANALYSIS_FEATURES if f in df.columns]

        numeric_df = df[features].select_dtypes(include=[np.number]).dropna(axis=1, how="all")
        corr = numeric_df.corr()

        fig = go.Figure(data=go.Heatmap(
            z=corr.values,
            x=corr.columns.tolist(),
            y=corr.index.tolist(),
            colorscale="RdBu_r",
            zmid=0,
            text=np.round(corr.values, 2),
            texttemplate="%{text}",
            textfont={"size": 10},
        ))

        fig.update_layout(**DARK_LAYOUT)
        fig.update_layout(
            title="Feature Correlation Matrix",
            width=700,
            height=600,
        )
        return fig.to_plotly_json()

    def generate_time_series(self, filename: str, features: list[str]) -> dict:
        """Generate a time-series plot for a specific polishing run file.

        Args:
            filename: The .dat filename.
            features: List of feature names to plot over time (e.g. ['COF', 'IR Temperature']).

        Returns:
            Plotly figure as a JSON-serializable dictionary.
        """
        ts_data = self.dm.get_file_data(filename)
        if ts_data is None:
            return self._empty_fig(f"File '{filename}' not found.")

        fig = go.Figure()
        for i, feat in enumerate(features):
            if feat in ts_data.columns:
                fig.add_trace(go.Scatter(
                    y=ts_data[feat],
                    mode="lines",
                    name=feat,
                    line=dict(color=CLUSTER_COLORS[i % len(CLUSTER_COLORS)]),
                ))

        fig.update_layout(**DARK_LAYOUT)
        fig.update_layout(
            title=f"Time Series: {filename}",
            xaxis_title="Sample",
            yaxis_title="Value",
        )
        return fig.to_plotly_json()

    def generate_model_plots(self) -> list[dict]:
        """Generate all diagnostic plots for the currently trained model.

        Returns:
            List of 4 Plotly figures: predicted vs actual, feature importance,
            residuals vs predicted, and residual distribution.
        """
        try:
            diag = self.ml.get_diagnostics()
        except ValueError:
            empty = self._empty_fig("No model trained.")
            return [empty, empty, empty, empty]

        y_true = np.array(diag["y_true"])
        y_pred = np.array(diag["y_pred"])
        file_names = diag["file_names"]
        importances = diag["feature_importances"]
        residuals = y_true - y_pred

        # 1. Predicted vs Actual
        fig1 = go.Figure()
        abs_err = np.abs(y_pred - y_true)
        fig1.add_trace(go.Scatter(
            x=y_true, y=y_pred, mode="markers",
            marker=dict(size=9, color=abs_err, colorscale="Bluered", showscale=True,
                        colorbar=dict(title="|Error|")),
            text=file_names,
            hovertemplate="<b>%{text}</b><br>Actual: %{x:.0f}Å<br>Predicted: %{y:.0f}Å<extra></extra>",
        ))
        all_vals = np.concatenate([y_true, y_pred])
        lo, hi = float(np.min(all_vals)), float(np.max(all_vals))
        margin = (hi - lo) * 0.05
        fig1.add_trace(go.Scatter(
            x=[lo - margin, hi + margin], y=[lo - margin, hi + margin],
            mode="lines", line=dict(dash="dash", color=COLORS["text_secondary"]),
            showlegend=False, hoverinfo="skip",
        ))
        fig1.update_layout(**DARK_LAYOUT, title="Predicted vs Actual",
                           xaxis_title="Actual Removal (Å)", yaxis_title="Predicted Removal (Å)",
                           showlegend=False)

        # 2. Feature Importance
        fig2 = go.Figure()
        sorted_imp = sorted(importances.items(), key=lambda x: x[1])
        fig2.add_trace(go.Bar(
            x=[v for _, v in sorted_imp],
            y=[k for k, _ in sorted_imp],
            orientation="h",
            marker_color=COLORS["accent"],
        ))
        fig2.update_layout(**DARK_LAYOUT, title="Feature Importance",
                           xaxis_title="Importance",
                           margin=dict(l=140, r=30, t=50, b=50))

        # 3. Residuals vs Predicted
        fig3 = go.Figure()
        fig3.add_trace(go.Scatter(
            x=y_pred, y=residuals, mode="markers",
            marker=dict(size=9, color=COLORS["accent"]),
            text=file_names,
            hovertemplate="<b>%{text}</b><br>Predicted: %{x:.0f}Å<br>Residual: %{y:.0f}Å<extra></extra>",
        ))
        fig3.add_hline(y=0, line_dash="dash", line_color=COLORS["text_secondary"])
        fig3.update_layout(**DARK_LAYOUT, title="Residuals vs Predicted",
                           xaxis_title="Predicted Removal (Å)", yaxis_title="Residual (Å)",
                           showlegend=False)

        # 4. Residual Distribution
        fig4 = go.Figure()
        fig4.add_trace(go.Histogram(
            x=residuals, nbinsx=max(8, len(residuals) // 4),
            marker_color=COLORS["accent"], opacity=0.85,
        ))
        fig4.add_annotation(
            text=f"Mean: {np.mean(residuals):.0f}  Std: {np.std(residuals):.0f}",
            xref="paper", yref="paper", x=0.02, y=1.0,
            xanchor="left", yanchor="top", showarrow=False,
            font=dict(size=11, color=COLORS["text_secondary"]),
        )
        fig4.update_layout(**DARK_LAYOUT, title="Residual Distribution",
                           xaxis_title="Residual (Å)", yaxis_title="Count",
                           showlegend=False)

        return [fig1.to_plotly_json(), fig2.to_plotly_json(),
                fig3.to_plotly_json(), fig4.to_plotly_json()]

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _empty_fig(self, message: str) -> dict:
        """Create an empty Plotly figure with a centered message."""
        fig = go.Figure()
        fig.update_layout(**DARK_LAYOUT)
        fig.add_annotation(
            text=message, xref="paper", yref="paper", x=0.5, y=0.5,
            showarrow=False, font=dict(size=14, color=COLORS["text_secondary"]),
        )
        return fig.to_plotly_json()

    def get_all_tools(self) -> list:
        """Return list of all tool functions for Ollama registration."""
        return [
            self.get_dataset_summary,
            self.get_file_details,
            self.get_feature_statistics,
            self.detect_outliers,
            self.run_automl,
            self.predict_removal,
            self.get_model_diagnostics,
            self.generate_scatter,
            self.generate_distribution,
            self.generate_bar_chart,
            self.generate_correlation_heatmap,
            self.generate_time_series,
            self.generate_model_plots,
        ]
```

- [ ] **Step 2: Verify imports**

Run: `python -c "from ai.tools import AgentTools; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add ai/tools.py
git commit -m "Add 13 agent tool definitions wrapping DataManager and FLAML"
```

---

## Task 5: Agent Engine

**Files:**
- Create: `ai/agent.py`

The conversation loop: manages Ollama chat, dispatches tool calls, streams responses.

- [ ] **Step 1: Create `ai/agent.py`**

```python
"""Agent engine — manages LLM conversation, tool dispatch, and streaming."""

import json
import logging
import threading
from queue import Queue, Empty
from typing import Any

import ollama

from ai.automl import AutoMLManager
from ai.tools import AgentTools

logger = logging.getLogger(__name__)

_MODEL = "qwen3:8b"

_SYSTEM_PROMPT = """You are an AI assistant embedded in Araca Insights®, a semiconductor \
wafer polishing analytics application. You help polishing engineers understand their \
data and predict material removal rates.

You have access to tools for querying data, running ML models, detecting outliers, \
and generating charts. Always use tools for data access and computation — never \
guess numbers or make up data.

When explaining results, use plain language. Your users are domain experts in \
polishing but not in machine learning. Translate ML concepts into process \
engineering terms they understand.

When generating charts, explain what the chart shows and why it matters before \
displaying it.

When the user asks for a prediction, use the predict_removal tool. If no model \
is trained yet, use run_automl first to train one.

Keep responses concise and focused. Avoid unnecessary caveats or disclaimers."""


class StreamChunk:
    """A piece of streamed output for the UI."""

    def __init__(self, chunk_type: str, content: Any = None):
        self.type = chunk_type  # "text", "thinking", "chart", "charts", "done", "error"
        self.content = content


class AgentEngine:
    """Orchestrates the LLM conversation loop with tool calling."""

    def __init__(self, data_manager, port: int = 11435):
        self.port = port
        self.client = ollama.Client(host=f"http://localhost:{self.port}")
        self.automl_manager = AutoMLManager(data_manager)
        self.tools = AgentTools(data_manager, self.automl_manager)
        self.messages: list[dict] = [
            {"role": "system", "content": _SYSTEM_PROMPT}
        ]
        self.output_queue: Queue[StreamChunk] = Queue()
        self._lock = threading.Lock()
        self._processing = False

    @property
    def is_processing(self) -> bool:
        return self._processing

    def process_message(self, user_text: str):
        """Process a user message in a background thread.

        Streams output chunks to self.output_queue for the UI to poll.
        """
        thread = threading.Thread(
            target=self._process_message_sync,
            args=(user_text,),
            daemon=True,
        )
        thread.start()

    def _process_message_sync(self, user_text: str):
        """Synchronous message processing with tool loop."""
        with self._lock:
            self._processing = True

        try:
            self.messages.append({"role": "user", "content": user_text})
            self._prune_history()

            tool_funcs = self.tools.get_all_tools()
            max_rounds = 8  # Safety limit on tool-calling rounds

            for _ in range(max_rounds):
                try:
                    response = self.client.chat(
                        model=_MODEL,
                        messages=self.messages,
                        tools=tool_funcs,
                        think=True,
                        stream=True,
                    )
                except Exception as exc:
                    logger.error("Ollama chat error: %s", exc)
                    self.output_queue.put(StreamChunk("error", str(exc)))
                    self.output_queue.put(StreamChunk("done"))
                    return

                full_message = self._stream_response(response)
                self.messages.append(
                    {"role": "assistant", "content": full_message.get("content", "")}
                )

                # Handle tool calls
                tool_calls = full_message.get("tool_calls")
                if tool_calls:
                    # Add the assistant message with tool calls
                    self.messages[-1]["tool_calls"] = tool_calls

                    for tc in tool_calls:
                        result = self._execute_tool(tc)
                        self.messages.append({
                            "role": "tool",
                            "content": self._format_tool_result(result),
                        })
                else:
                    # No more tool calls — final answer delivered
                    break

            self.output_queue.put(StreamChunk("done"))

        except Exception as exc:
            logger.error("Agent error: %s", exc)
            self.output_queue.put(StreamChunk("error", str(exc)))
            self.output_queue.put(StreamChunk("done"))
        finally:
            self._processing = False

    def _stream_response(self, stream) -> dict:
        """Consume streamed response, emitting chunks to the UI queue.

        Returns the fully assembled message dict.
        """
        full_content = ""
        full_thinking = ""
        tool_calls = None

        for chunk in stream:
            msg = chunk.get("message", {})

            # Thinking tokens
            thinking = msg.get("thinking", "")
            if thinking:
                full_thinking += thinking
                self.output_queue.put(StreamChunk("thinking", thinking))

            # Content tokens
            content = msg.get("content", "")
            if content:
                full_content += content
                self.output_queue.put(StreamChunk("text", content))

            # Tool calls come in the final chunk
            if msg.get("tool_calls"):
                tool_calls = msg["tool_calls"]

        result = {"content": full_content}
        if tool_calls:
            result["tool_calls"] = tool_calls
        return result

    def _execute_tool(self, tool_call: dict) -> Any:
        """Execute a tool call and return the result."""
        func_name = tool_call["function"]["name"]
        args = tool_call["function"].get("arguments", {})

        logger.info("Calling tool: %s(%s)", func_name, args)

        # Find the tool method on AgentTools
        func = getattr(self.tools, func_name, None)
        if func is None:
            return f"Error: unknown tool '{func_name}'"

        try:
            result = func(**args)
        except Exception as exc:
            logger.error("Tool %s failed: %s", func_name, exc)
            return f"Error calling {func_name}: {exc}"

        # If result is a chart (dict with "data" key) or list of charts, emit to UI
        if isinstance(result, dict) and "data" in result:
            self.output_queue.put(StreamChunk("chart", result))
        elif isinstance(result, list) and result and isinstance(result[0], dict):
            self.output_queue.put(StreamChunk("charts", result))

        return result

    def _format_tool_result(self, result: Any) -> str:
        """Format a tool result as a string for the LLM context."""
        if isinstance(result, str):
            return result
        if isinstance(result, dict) and "data" in result:
            return "[Chart generated and displayed to user]"
        if isinstance(result, list) and result and isinstance(result[0], dict):
            return f"[{len(result)} diagnostic charts generated and displayed to user]"
        return json.dumps(result, default=str)

    def _prune_history(self):
        """Keep conversation history under ~6K tokens by removing old messages."""
        # Rough estimate: 4 chars ≈ 1 token
        max_chars = 24000  # ~6K tokens
        total = sum(len(m.get("content", "")) for m in self.messages)
        while total > max_chars and len(self.messages) > 2:
            # Remove oldest non-system message
            removed = self.messages.pop(1)
            total -= len(removed.get("content", ""))

    def get_greeting(self, file_count: int, removal_count: int) -> str:
        """Generate a context-aware greeting for when the tab opens."""
        if self.automl_manager.automl is not None:
            metrics = self.automl_manager.metrics
            return (
                f"Your {metrics['best_model']} model is current "
                f"(R²={metrics['r2']:.3f}, trained on {metrics['n_train']} files). "
                f"Ask me anything about the results, request predictions, "
                f"or I can retrain if you've added new data."
            )

        if file_count == 0:
            return (
                "No polishing data loaded yet. Import some .dat files in the "
                "Project page, then come back and I'll help you analyze them."
            )

        if removal_count < 5:
            return (
                f"You have {file_count} polishing files loaded, but only "
                f"{removal_count} have removal data. I need at least 5 files "
                f"with removal values to build a prediction model. "
                f"I can still help you explore the data you have — try asking "
                f"about specific files or features."
            )

        return (
            f"You have {file_count} polishing runs loaded, "
            f"{removal_count} with removal data. "
            f"Want me to build the best prediction model for this dataset?"
        )

    def reset(self):
        """Reset conversation history (keep system prompt)."""
        self.messages = [{"role": "system", "content": _SYSTEM_PROMPT}]
        while not self.output_queue.empty():
            try:
                self.output_queue.get_nowait()
            except Empty:
                break
```

- [ ] **Step 2: Verify imports**

Run: `python -c "from ai.agent import AgentEngine; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add ai/agent.py
git commit -m "Add AgentEngine with conversation loop, tool dispatch, and streaming"
```

---

## Task 6: Chat UI Styles

**Files:**
- Modify: `dashboard/styles.py`

Add CSS classes for the chat interface. Append to the existing CSS inside `INDEX_STRING`.

- [ ] **Step 1: Read the end of styles.py to find the insertion point**

The CSS block ends with a closing `</style>` tag inside `INDEX_STRING`. Add new styles just before that closing tag.

- [ ] **Step 2: Add chat CSS to `dashboard/styles.py`**

Find the closing `</style>` in `INDEX_STRING` and insert these styles before it:

```css
/* ── AI Agent Chat ─────────────────────────────────────────── */
.agent-status-bar {
    display: flex;
    gap: 12px;
    align-items: center;
    padding: 8px 16px;
    background: #2a2a2a;
    border-bottom: 1px solid #404040;
    font-size: 12px;
}
.agent-status-badge {
    padding: 3px 10px;
    border-radius: 12px;
    background: #353535;
    color: #888888;
    font-size: 11px;
}
.agent-status-badge.active {
    background: #1a3a1a;
    color: #22c55e;
}
.agent-chat-area {
    flex: 1;
    overflow-y: auto;
    padding: 16px;
    display: flex;
    flex-direction: column;
    gap: 12px;
}
.agent-message {
    max-width: 85%;
    padding: 10px 14px;
    border-radius: 12px;
    font-size: 13px;
    line-height: 1.5;
    word-wrap: break-word;
}
.agent-message.assistant {
    align-self: flex-start;
    background: #353535;
    color: #e0e0e0;
    border-bottom-left-radius: 4px;
}
.agent-message.user {
    align-self: flex-end;
    background: #1e3a5f;
    color: #e0e0e0;
    border-bottom-right-radius: 4px;
}
.agent-message.system {
    align-self: center;
    background: transparent;
    color: #888888;
    font-style: italic;
    text-align: center;
    font-size: 12px;
}
.agent-thinking {
    font-size: 11px;
    color: #666666;
    padding: 4px 10px;
    border-left: 2px solid #404040;
    margin: 4px 0;
    cursor: pointer;
}
.agent-thinking summary {
    color: #888888;
}
.agent-input-area {
    display: flex;
    gap: 8px;
    padding: 12px 16px;
    background: #2a2a2a;
    border-top: 1px solid #404040;
}
.agent-input-area input {
    flex: 1;
    background: #353535;
    border: 1px solid #404040;
    border-radius: 8px;
    color: #e0e0e0;
    padding: 10px 14px;
    font-size: 13px;
    outline: none;
}
.agent-input-area input:focus {
    border-color: #3b82f6;
}
.agent-send-btn {
    background: #3b82f6;
    color: white;
    border: none;
    border-radius: 8px;
    padding: 10px 20px;
    font-size: 13px;
    font-weight: 600;
    cursor: pointer;
}
.agent-send-btn:hover {
    background: #2563eb;
}
.agent-send-btn:disabled {
    background: #404040;
    color: #666666;
    cursor: not-allowed;
}
.agent-suggestions {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    justify-content: center;
    padding: 8px 16px;
}
.agent-suggestion-chip {
    background: #353535;
    border: 1px solid #404040;
    border-radius: 16px;
    color: #888888;
    padding: 6px 14px;
    font-size: 12px;
    cursor: pointer;
}
.agent-suggestion-chip:hover {
    border-color: #3b82f6;
    color: #e0e0e0;
}
.agent-chart-container {
    width: 100%;
    margin: 8px 0;
    border-radius: 8px;
    overflow: hidden;
}
```

- [ ] **Step 3: Commit**

```bash
git add dashboard/styles.py
git commit -m "Add CSS styles for AI agent chat interface"
```

---

## Task 7: AI Agent Tab Layout

**Files:**
- Modify: `dashboard/layouts.py`

Replace `build_prediction_tab()` with `build_agent_tab()`.

- [ ] **Step 1: Replace the prediction tab function**

In `dashboard/layouts.py`, replace the entire `build_prediction_tab()` function (lines 450–571) with:

```python
def build_agent_tab():
    """Build the 'AI Agent' tab layout with chat interface."""
    return dcc.Tab(label='AI Agent', value='agent', className='tab', selected_className='tab--selected', children=[
        html.Div(style={
            'display': 'flex', 'flexDirection': 'column',
            'height': 'calc(100vh - 120px)', 'padding': '0',
        }, children=[

            # Status bar
            html.Div(className='agent-status-bar', children=[
                html.Span(id='agent-model-badge', className='agent-status-badge',
                           children='No model'),
                html.Span(id='agent-data-badge', className='agent-status-badge',
                           children='0 files'),
                html.Span(id='agent-ollama-badge', className='agent-status-badge',
                           children='Connecting...'),
            ]),

            # Chat message area
            html.Div(id='agent-chat-area', className='agent-chat-area', children=[]),

            # Suggested prompts (shown when chat is empty)
            html.Div(id='agent-suggestions', className='agent-suggestions', children=[
                html.Button("Build a prediction model", id='agent-suggest-0',
                            className='agent-suggestion-chip', n_clicks=0),
                html.Button("Summarize my dataset", id='agent-suggest-1',
                            className='agent-suggestion-chip', n_clicks=0),
                html.Button("Which files are outliers?", id='agent-suggest-2',
                            className='agent-suggestion-chip', n_clicks=0),
                html.Button("Predict removal for new conditions", id='agent-suggest-3',
                            className='agent-suggestion-chip', n_clicks=0),
            ]),

            # Input area
            html.Div(className='agent-input-area', children=[
                dcc.Input(
                    id='agent-input',
                    type='text',
                    placeholder='Ask about your polishing data...',
                    debounce=False,
                    n_submit=0,
                ),
                html.Button("Send", id='agent-send-btn',
                            className='agent-send-btn', n_clicks=0),
            ]),

            # Hidden stores for agent state
            dcc.Store(id='agent-messages-store', data=[]),
            dcc.Store(id='agent-pending-message', data=None),
            dcc.Store(id='agent-processing', data=False),
            dcc.Interval(id='agent-poll-interval', interval=200, disabled=True),
        ])
    ])
```

- [ ] **Step 2: Update `build_app_layout()` to use the new tab**

In `build_app_layout()` (line 581), replace `build_prediction_tab()` with `build_agent_tab()`:

```python
def build_app_layout():
    """Assemble the complete application layout with all tabs and hidden stores."""
    return html.Div([
        dcc.Tabs(id="analysis-tabs", value='single-file', className='tab-parent', parent_className='tab-parent', content_className='tab-content', children=[
            build_single_file_tab(),
            build_multi_file_tab(),
            build_correlations_tab(),
            build_agent_tab(),
        ]),
        dcc.Store(id='ts-dblclick-trigger', data=0),
        dcc.Store(id='sf-dblclick-trigger', data=0),
        html.Div(id='ts-graph-listener', style={'display': 'none'}),
        html.Div(id='sf-graph-listener', style={'display': 'none'}),
    ])
```

Note: The `pred-model-store` `dcc.Store` is removed since the agent manages model state internally.

- [ ] **Step 3: Commit**

```bash
git add dashboard/layouts.py
git commit -m "Replace Predict Removal tab with AI Agent chat tab"
```

---

## Task 8: Agent Dash Callbacks

**Files:**
- Create: `ai/callbacks_agent.py`

These callbacks wire the Dash UI to the AgentEngine.

- [ ] **Step 1: Create `ai/callbacks_agent.py`**

```python
"""Dash callbacks for the AI Agent tab.

Handles: sending messages, polling streamed responses, tab activation,
suggestion chips, and rendering charts inline.
"""

import json
import logging
from queue import Empty

import plotly
from dash import Input, Output, State, callback_context, html, dcc, no_update

from ai.agent import AgentEngine, StreamChunk

logger = logging.getLogger(__name__)

# Module-level reference set during registration
_engine: AgentEngine | None = None


def register_agent_callbacks(app, data_manager, agent_engine: AgentEngine):
    """Register all callbacks for the AI Agent tab."""
    global _engine
    _engine = agent_engine

    # == Callback 1: Send message (from input or suggestion chips) ==========
    @app.callback(
        [Output('agent-pending-message', 'data'),
         Output('agent-input', 'value'),
         Output('agent-poll-interval', 'disabled'),
         Output('agent-processing', 'data')],
        [Input('agent-send-btn', 'n_clicks'),
         Input('agent-input', 'n_submit'),
         Input('agent-suggest-0', 'n_clicks'),
         Input('agent-suggest-1', 'n_clicks'),
         Input('agent-suggest-2', 'n_clicks'),
         Input('agent-suggest-3', 'n_clicks')],
        [State('agent-input', 'value'),
         State('agent-processing', 'data')],
        prevent_initial_call=True,
    )
    def send_message(send_clicks, submit, s0, s1, s2, s3, input_value, is_processing):
        if is_processing:
            return no_update, no_update, no_update, no_update

        ctx = callback_context
        if not ctx.triggered:
            return no_update, no_update, no_update, no_update

        trigger_id = ctx.triggered[0]['prop_id'].split('.')[0]

        suggestions = {
            'agent-suggest-0': "Build a prediction model",
            'agent-suggest-1': "Summarize my dataset",
            'agent-suggest-2': "Which files are outliers?",
            'agent-suggest-3': "Predict removal for new conditions",
        }

        if trigger_id in suggestions:
            message = suggestions[trigger_id]
        elif trigger_id in ('agent-send-btn', 'agent-input'):
            message = (input_value or "").strip()
        else:
            return no_update, no_update, no_update, no_update

        if not message:
            return no_update, no_update, no_update, no_update

        # Start processing
        _engine.process_message(message)

        return message, "", False, True  # pending_message, clear input, enable poll, processing

    # == Callback 2: Poll streamed response ==================================
    @app.callback(
        [Output('agent-chat-area', 'children'),
         Output('agent-poll-interval', 'disabled', allow_duplicate=True),
         Output('agent-processing', 'data', allow_duplicate=True),
         Output('agent-model-badge', 'children'),
         Output('agent-model-badge', 'className'),
         Output('agent-suggestions', 'style')],
        [Input('agent-poll-interval', 'n_intervals')],
        [State('agent-chat-area', 'children'),
         State('agent-pending-message', 'data'),
         State('agent-processing', 'data')],
        prevent_initial_call=True,
    )
    def poll_response(n_intervals, current_children, pending_msg, is_processing):
        if not is_processing:
            return no_update, True, no_update, no_update, no_update, no_update

        children = list(current_children) if current_children else []

        # If this is the first poll after a new message, add the user message
        if pending_msg and not any(
            _is_user_message(c, pending_msg) for c in children
        ):
            children.append(
                html.Div(pending_msg, className='agent-message user')
            )

        # Drain the output queue
        text_buffer = ""
        thinking_buffer = ""
        charts = []
        is_done = False
        error_msg = None

        while True:
            try:
                chunk = _engine.output_queue.get_nowait()
            except Empty:
                break

            if chunk.type == "text":
                text_buffer += chunk.content
            elif chunk.type == "thinking":
                thinking_buffer += chunk.content
            elif chunk.type == "chart":
                charts.append(chunk.content)
            elif chunk.type == "charts":
                charts.extend(chunk.content)
            elif chunk.type == "done":
                is_done = True
            elif chunk.type == "error":
                error_msg = chunk.content

        # Add thinking as collapsible
        if thinking_buffer:
            children.append(
                html.Details(
                    className='agent-thinking',
                    children=[
                        html.Summary("Reasoning..."),
                        html.P(thinking_buffer),
                    ],
                )
            )

        # Add text response
        if text_buffer:
            # Check if last child is an in-progress assistant message
            if children and _is_assistant_streaming(children[-1]):
                # Append to existing message
                prev_text = _extract_text(children[-1])
                children[-1] = html.Div(
                    prev_text + text_buffer,
                    className='agent-message assistant',
                    **{'data-streaming': 'true'},
                )
            else:
                children.append(
                    html.Div(
                        text_buffer,
                        className='agent-message assistant',
                        **{'data-streaming': 'true'},
                    )
                )

        # Add charts inline
        for chart_data in charts:
            children.append(
                html.Div(className='agent-chart-container', children=[
                    dcc.Graph(
                        figure=chart_data,
                        config={'displayModeBar': True, 'displaylogo': False},
                        style={'height': '380px'},
                    ),
                ])
            )

        # Handle errors
        if error_msg:
            children.append(
                html.Div(
                    f"Error: {error_msg}",
                    className='agent-message system',
                )
            )

        # Finalize
        if is_done:
            # Mark last assistant message as done (remove streaming flag)
            if children and _is_assistant_streaming(children[-1]):
                text = _extract_text(children[-1])
                children[-1] = html.Div(text, className='agent-message assistant')

            # Update model badge
            model_text = "No model"
            model_class = "agent-status-badge"
            if _engine.automl_manager.metrics:
                m = _engine.automl_manager.metrics
                model_text = f"{m['best_model']} (R²={m['r2']:.3f})"
                model_class = "agent-status-badge active"

            return (
                children,
                True,     # disable poll
                False,    # not processing
                model_text,
                model_class,
                {'display': 'none'},  # hide suggestions after first message
            )

        return children, no_update, no_update, no_update, no_update, no_update

    # == Callback 3: Tab activation — greeting ==============================
    @app.callback(
        [Output('agent-chat-area', 'children', allow_duplicate=True),
         Output('agent-data-badge', 'children'),
         Output('agent-ollama-badge', 'children'),
         Output('agent-ollama-badge', 'className')],
        Input('analysis-tabs', 'value'),
        State('agent-chat-area', 'children'),
        prevent_initial_call=True,
    )
    def on_tab_activate(tab_value, current_children):
        if tab_value != 'agent':
            return no_update, no_update, no_update, no_update

        # Only greet once (when chat is empty)
        if current_children:
            return no_update, no_update, no_update, no_update

        df = data_manager.get_all_data()
        file_count = len(df)
        removal_count = int((df.get('Removal', 0) > 0).sum()) if not df.empty else 0

        greeting = _engine.get_greeting(file_count, removal_count)
        children = [html.Div(greeting, className='agent-message assistant')]

        data_badge = f"{file_count} files"

        # Check Ollama health
        from ai.ollama_manager import OllamaManager
        mgr = OllamaManager(port=_engine.port)
        if mgr.is_healthy():
            ollama_text = "Connected"
            ollama_class = "agent-status-badge active"
        else:
            ollama_text = "Unavailable"
            ollama_class = "agent-status-badge"

        return children, data_badge, ollama_text, ollama_class


# ---------------------------------------------------------------------------
# Helpers for inspecting Dash component trees
# ---------------------------------------------------------------------------

def _is_user_message(component, text):
    """Check if a Dash component is a user message with the given text."""
    if not isinstance(component, dict):
        return False
    props = component.get('props', {})
    return props.get('className') == 'agent-message user' and props.get('children') == text


def _is_assistant_streaming(component):
    """Check if a component is a streaming assistant message."""
    if not isinstance(component, dict):
        return False
    props = component.get('props', {})
    return (props.get('className') == 'agent-message assistant'
            and props.get('data-streaming') == 'true')


def _extract_text(component):
    """Extract text content from a Dash HTML component."""
    if isinstance(component, dict):
        return component.get('props', {}).get('children', '')
    return ''
```

- [ ] **Step 2: Verify imports**

Run: `python -c "from ai.callbacks_agent import register_agent_callbacks; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add ai/callbacks_agent.py
git commit -m "Add Dash callbacks for AI Agent tab (send, poll, greeting)"
```

---

## Task 9: Wire Everything Together

**Files:**
- Modify: `dashboard/callbacks.py`
- Modify: `dashboard/app.py`
- Modify: `desktop/main_window.py`

- [ ] **Step 1: Update `dashboard/callbacks.py`**

Replace the prediction import and registration with the agent:

At the top of the file, replace line 14:
```python
from dashboard.callbacks_prediction import register_prediction_callbacks
```
with:
```python
from ai.callbacks_agent import register_agent_callbacks
```

At the bottom of the file (line 237), replace:
```python
    register_prediction_callbacks(app, data_manager)
```
with:
```python
    register_agent_callbacks(app, data_manager, agent_engine)
```

Update the function signature on line 17 from:
```python
def register_callbacks(app, data_manager):
```
to:
```python
def register_callbacks(app, data_manager, agent_engine=None):
```

- [ ] **Step 2: Update `dashboard/app.py`**

The app module needs to create the `AgentEngine` and pass it to callback registration.

Replace the contents of `dashboard/app.py` with:

```python
"""Dash application entry point."""

import dash
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from dashboard.dash_bridge import DataManager
except ImportError:
    from .dash_bridge import DataManager

from dashboard.styles import INDEX_STRING
from dashboard.layouts import build_app_layout
from dashboard.callbacks import register_callbacks

data_manager = DataManager()

# Create agent engine (Ollama must be started separately before use)
try:
    from ai.agent import AgentEngine
    agent_engine = AgentEngine(data_manager)
except ImportError:
    agent_engine = None

app = dash.Dash(__name__, external_stylesheets=[])
server = app.server

app.index_string = INDEX_STRING
app.layout = build_app_layout()
register_callbacks(app, data_manager, agent_engine)

if __name__ == '__main__':
    app.run(debug=True)
```

- [ ] **Step 3: Update `desktop/main_window.py`**

Add Ollama lifecycle management. Near the top imports, add:

```python
from ai.ollama_manager import OllamaManager
```

Add an instance variable in `__init__()`:

```python
self.ollama_manager = OllamaManager()
```

In `on_advanced_analysis()` (after `data_manager.update_report(self.report)` on line 269), add Ollama startup:

```python
        # Start Ollama if not already running
        if not self.ollama_manager.is_healthy():
            self.ollama_manager.start()
```

In `closeEvent()`, add Ollama shutdown before `event.accept()`. Add this at the beginning of the method:

```python
        # Stop Ollama process
        self.ollama_manager.stop()
```

- [ ] **Step 4: Verify the app starts without errors**

Run: `python -c "from dashboard.app import app; print('App created OK')"`
Expected: `App created OK`

- [ ] **Step 5: Commit**

```bash
git add dashboard/callbacks.py dashboard/app.py desktop/main_window.py
git commit -m "Wire agent engine into Dash callbacks and Ollama into app lifecycle"
```

---

## Task 10: Remove Old Prediction Module

**Files:**
- Delete: `dashboard/callbacks_prediction.py`

- [ ] **Step 1: Verify no remaining imports**

Run: `grep -r "callbacks_prediction" --include="*.py" .`
Expected: No results (all references were updated in Task 9).

- [ ] **Step 2: Delete the file**

```bash
rm dashboard/callbacks_prediction.py
```

- [ ] **Step 3: Verify app still imports cleanly**

Run: `python -c "from dashboard.app import app; print('OK')"`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add -u dashboard/callbacks_prediction.py
git commit -m "Remove old Predict Removal callbacks (replaced by AI agent)"
```

---

## Task 11: Update `ai/__init__.py` Exports

**Files:**
- Modify: `ai/__init__.py`

- [ ] **Step 1: Update package exports**

```python
"""AI agent module — LLM-powered analytics assistant."""

from ai.agent import AgentEngine
from ai.ollama_manager import OllamaManager
from ai.automl import AutoMLManager

__all__ = ["AgentEngine", "OllamaManager", "AutoMLManager"]
```

- [ ] **Step 2: Commit**

```bash
git add ai/__init__.py
git commit -m "Export public classes from ai package"
```

---

## Task 12: Integration Test — Full Stack

**Files:** None (manual verification)

- [ ] **Step 1: Ensure Ollama is installed and Qwen3 8B is available**

Run: `ollama list`
If qwen3:8b is not listed, run: `ollama pull qwen3:8b`

- [ ] **Step 2: Start the application**

Run: `python main.py`
Expected: App launches, no errors in console.

- [ ] **Step 3: Navigate to Advanced Analysis**

1. Create or load a project with at least 5 .dat files that have removal data
2. Click "Advanced Analysis"
Expected: Dashboard loads with 4 tabs: Analyze File, Compare Files, Key Correlations, AI Agent

- [ ] **Step 4: Test AI Agent tab**

1. Click "AI Agent" tab
2. Verify greeting message appears with data summary
3. Verify status badges show file count and Ollama connection
4. Click "Build a prediction model" suggestion chip
5. Wait for FLAML to train (~60 seconds) and agent to explain results
6. Verify model diagnostic charts appear inline
7. Type "Why is [filename] an outlier?" and verify response
8. Type "Show me removal vs pressure by pad type" and verify chart appears
9. Type "Predict removal for Pad-IC at 4 PSI for 1 minute" and verify prediction

- [ ] **Step 5: Test graceful degradation**

1. Stop Ollama: `pkill ollama`
2. Reload AI Agent tab
3. Verify "Unavailable" badge appears
4. Verify other 3 tabs still work normally

- [ ] **Step 6: Final commit**

```bash
git add -A
git commit -m "AI Agent integration: FLAML AutoML + Qwen3 8B conversational assistant"
```
