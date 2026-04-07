# AutoML Refinement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Harden and refine the FLAML AutoML wrapper (`ai/automl.py`) for maximum prediction reliability, remove dead code across the `ai/` module, and ensure consistency with the rest of the project.

**Architecture:** Incremental improvements to the existing `AutoMLManager` class — no structural changes. Add two estimators to broaden the search, make implicit defaults explicit, simplify feature importance extraction, improve inner-fold training, and clean dead imports across all `ai/*.py` files.

**Tech Stack:** FLAML 2.5.0, scikit-learn, pandas, numpy

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `ai/automl.py` | Modify | AutoML wrapper — estimator list, fit params, feature importance, leaderboard |
| `ai/callbacks_agent.py` | Modify | Dead import cleanup only |
| `ai/tools.py` | Modify | Dead import cleanup only |
| `ai/agent.py` | No change | Already clean |
| `ai/ollama_manager.py` | No change | Already clean |
| `ai/__init__.py` | No change | Already clean |

---

### Task 1: Add `lassolars` and `sgd` to estimator list

**Files:**
- Modify: `ai/automl.py:45-53`

These two estimators are built into FLAML 2.5.0 for regression and tested to work with mixed categorical/numerical data:
- `lassolars` — Lasso via LARS, complements `enet` with automatic L1 feature selection (useful when some categoricals are noise)
- `sgd` — SGD regressor with diverse loss functions including Huber (robust to outliers in removal measurements)

Both are fast (relative cost ~160x LightGBM in FLAML's cost model, but training time is negligible on small data), so they add diversity without meaningful budget impact.

- [ ] **Step 1: Update the estimator list**

In `ai/automl.py`, replace lines 45-53:

```python
        self._estimator_list = [
            "lgbm",
            "xgboost",
            "xgb_limitdepth",
            "rf",
            "extra_tree",
            "histgb",
            "enet",
        ]
```

with:

```python
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
```

- [ ] **Step 2: Update the comment above the list**

Replace the comment block at lines 39-44:

```python
        # Regression estimators for FLAML to search over. Weighted toward tree
        # models since they outperform linear on this wafer-polishing dataset;
        # "enet" (ElasticNet) is included as the Ridge-equivalent linear
        # fallback. Used by both the main fit and the OOF metric evaluation.
        # Note: "lrl2" is LogisticRegression (classification-only); "enet"
        # is the regression-capable L2-regularized linear model in FLAML.
        # "catboost" would be a good addition but requires a separate install.
```

with:

```python
        # Regression estimators for FLAML to search over. Tree models are
        # listed first (they typically outperform linear on tabular CMP data);
        # three linear fallbacks provide diversity: ElasticNet (L1+L2),
        # LassoLARS (pure L1 feature selection), and SGD (Huber loss for
        # outlier robustness). "catboost" would be a good addition but
        # requires a separate install. "ensemble=True" is broken in FLAML
        # 2.5.0 (StackingRegressor rejects FLAML's estimator wrappers).
```

- [ ] **Step 3: Verify the app starts and training works**

Run:
```bash
.venv/bin/python -c "
from ai.automl import AutoMLManager
print('Estimator list:', AutoMLManager(None)._estimator_list)
assert 'lassolars' in AutoMLManager(None)._estimator_list
assert 'sgd' in AutoMLManager(None)._estimator_list
print('OK')
"
```

Expected: prints the 9-element list and `OK`.

---

### Task 2: Make `retrain_full=True` explicit in both fit calls

**Files:**
- Modify: `ai/automl.py:115-129` (outer fit)
- Modify: `ai/automl.py:148-161` (inner fold fit)

FLAML defaults `retrain_full=True`, but this is not documented as a stable guarantee. Making it explicit:
1. Protects against future FLAML version changes
2. Makes the intent clear — the outer model MUST be trained on all data for best predictions
3. The inner fold models MUST also retrain on their full fold data (not just the holdout-training split) so OOF predictions reflect a model trained on as much data as possible

- [ ] **Step 1: Add `retrain_full=True` to the outer fit**

In `ai/automl.py`, the `self.automl.fit(...)` call starting at line 115. Add `retrain_full=True` after `early_stop=True`:

```python
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
```

- [ ] **Step 2: Add `retrain_full=True` to the inner fold fit**

In `ai/automl.py`, the `fold_ml.fit(...)` call starting at line 149. Add `retrain_full=True` after `eval_method="holdout"`:

```python
            fold_ml = AutoML()
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
```

- [ ] **Step 3: Verify no regression**

Run:
```bash
.venv/bin/python -c "
from flaml import AutoML
from sklearn.datasets import make_regression
X, y = make_regression(n_samples=30, n_features=4, noise=10, random_state=42)
ml = AutoML()
ml.fit(X, y, task='regression', time_budget=5, eval_method='cv', n_splits=3,
       metric='rmse', retrain_full=True, verbose=0, seed=42)
print(f'best={ml.best_estimator}, loss={ml.best_loss:.2f}')
print('retrain_full explicit: OK')
"
```

Expected: prints best estimator and `OK`.

---

### Task 3: Simplify `_extract_importances()` using FLAML's built-in property

**Files:**
- Modify: `ai/automl.py:320-371`

FLAML v2.5.0 provides `automl.feature_importances_` which handles pipeline unwrapping, `coef_` fallback, and `feature_importances_` extraction. The current method reimplements this with extra fallback paths. Simplify to use the built-in as the primary source, keeping only the DataTransformer column-name recovery logic (which FLAML doesn't provide).

- [ ] **Step 1: Replace `_extract_importances` method**

Replace the entire `_extract_importances` method (lines 320-371) with:

```python
    def _extract_importances(self, feature_cols: list[str]) -> dict:
        """Extract feature importances from the best FLAML model.

        Uses FLAML's built-in ``feature_importances_`` property as the
        primary source. When the DataTransformer drops constant columns,
        the importance vector is shorter than ``feature_cols``; in that
        case we recover the actual post-transform column names from the
        transformer so labels stay meaningful.
        """
        importances = self.automl.feature_importances_
        if importances is None:
            return {col: 0.0 for col in feature_cols}

        importances = np.abs(importances)

        # When all features survive the transformer, names align directly.
        if len(importances) == len(feature_cols):
            return {col: float(imp) for col, imp in zip(feature_cols, importances)}

        # The transformer dropped constant columns — recover actual names.
        try:
            X_sample = self.train_df[feature_cols].head(1).copy()
            for col in PREDICTION_CATEGORICAL_FEATURES:
                if col in X_sample.columns:
                    X_sample[col] = X_sample[col].astype(self._cat_dtypes[col])
            X_trans = self.automl._transformer.transform(X_sample)
            if hasattr(X_trans, "columns") and len(X_trans.columns) == len(importances):
                return {
                    col: float(imp)
                    for col, imp in zip(X_trans.columns, importances)
                }
        except Exception:
            pass

        # Last resort — indexed names (should not happen).
        return {f"feature_{i}": float(v) for i, v in enumerate(importances)}
```

- [ ] **Step 2: Verify feature importances still work**

Run:
```bash
.venv/bin/python -c "
from flaml import AutoML
import pandas as pd, numpy as np
np.random.seed(42)
n = 30
X = pd.DataFrame({
    'Pressure PSI': np.random.uniform(1, 10, n),
    'Polish Time': np.random.uniform(0.5, 60, n),
    'Wafer': pd.Categorical(np.random.choice(['W1','W2','W3'], n)),
    'Pad': pd.Categorical(np.random.choice(['P1','P2'], n)),
})
y = X['Pressure PSI'] * 100 + np.random.normal(0, 50, n)
ml = AutoML()
ml.fit(X, y, task='regression', time_budget=5, eval_method='cv', n_splits=3,
       metric='rmse', verbose=0, seed=42)
imp = ml.feature_importances_
print(f'importances type: {type(imp)}, len: {len(imp) if imp is not None else None}')
print(f'feature_importances_: {imp}')
print('OK')
"
```

Expected: prints array of importances matching feature count, and `OK`.

---

### Task 4: Remove dead imports across `ai/` module

**Files:**
- Modify: `ai/callbacks_agent.py:7,11,12,14`
- Modify: `ai/tools.py:8`

Dead imports found:
- `callbacks_agent.py`: `import json` (unused), `import plotly` (unused), `StreamChunk` (imported but never referenced), `ALL` from dash (unused)
- `tools.py`: `import json` (unused)

- [ ] **Step 1: Clean `ai/callbacks_agent.py` imports**

Replace line 7:
```python
import json
```
with nothing (delete the line).

Replace line 11:
```python
import plotly
```
with nothing (delete the line).

Replace line 12:
```python
from dash import ALL, Input, Output, State, callback_context, dcc, html, no_update
```
with:
```python
from dash import Input, Output, State, callback_context, dcc, html, no_update
```

Replace line 14:
```python
from ai.agent import AgentEngine, StreamChunk
```
with:
```python
from ai.agent import AgentEngine
```

- [ ] **Step 2: Clean `ai/tools.py` imports**

Replace line 8:
```python
import json
```
with nothing (delete the line).

- [ ] **Step 3: Verify imports don't break anything**

Run:
```bash
.venv/bin/python -c "
from ai.callbacks_agent import register_agent_callbacks
from ai.tools import AgentTools
print('All imports OK')
"
```

Expected: `All imports OK`.

---

### Task 5: Annotate leaderboard as search-phase estimates

**Files:**
- Modify: `ai/tools.py:243-246` (in `run_automl`)

The leaderboard in `_build_leaderboard()` uses `best_loss_per_estimator` from FLAML's internal search. These are optimistically biased (best-of-many selection per estimator). The held-out CV metrics only cover the winning model. The LLM should communicate this distinction to users.

- [ ] **Step 1: Add annotation to leaderboard output in `run_automl`**

In `ai/tools.py`, replace the leaderboard section (lines 243-246):

```python
        if results["leaderboard"]:
            lines.append("\nLeaderboard:")
            for i, entry in enumerate(results["leaderboard"], 1):
                lines.append(f"  {i}. {entry['model']} — RMSE={entry['rmse']:.0f}Å")
```

with:

```python
        if results["leaderboard"]:
            lines.append("\nLeaderboard (search-phase estimates, not held-out):")
            for i, entry in enumerate(results["leaderboard"], 1):
                lines.append(f"  {i}. {entry['model']} — RMSE={entry['rmse']:.0f}Å")
```

---

## Summary of Changes

| Change | Why |
|--------|-----|
| Add `lassolars`, `sgd` estimators | Broader search — L1 selection and Huber outlier robustness |
| Explicit `retrain_full=True` | Defensive against FLAML default changes; both outer and inner fits |
| Simplify `_extract_importances()` | Use FLAML's built-in, keep only the column-name recovery fallback |
| Remove dead imports | `json`, `plotly`, `ALL`, `StreamChunk` unused across 2 files |
| Annotate leaderboard | User-facing honesty — search-phase estimates vs held-out metrics |

## What Was NOT Changed (and why)

| Skipped | Reason |
|---------|--------|
| `ensemble=True` | Crashes on FLAML 2.5.0 — StackingRegressor rejects FLAML's estimator wrappers |
| `eval_method="cv"` in inner folds | With `max_iter=1` + `retrain_full=True`, holdout is fine — the model retrains on full fold data regardless |
| Log file | Disabled intentionally (`""`) — no test suite to consume logs, and verbose logging would clutter the user's project directory |
| `kneighbor` / `svc` estimators | High cost-relative-to-lgbm (KNN is O(n) at predict time, SVC scales poorly), marginal benefit on tabular CMP data |
