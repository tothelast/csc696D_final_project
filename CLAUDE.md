# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Araca Insights® — a dual-interface desktop + web analytics application for semiconductor wafer polishing data. PyQt6 desktop app embeds a Dash/Plotly web dashboard via PyWebEngine.

## Commands

```bash
# Run the application
python main.py

# Install dependencies
pip install -r requirements.txt
```

No test suite, linter, or CI pipeline is configured. See "Development & Debugging" below for the ad-hoc pattern used during development, including how to load the `Sample_Full_Data/` fixture and exercise the AI agent's tools and AutoML pipeline directly from a Python shell.

## Architecture

### Four-layer structure

- **`core/`** — Data models. `RawFile` parses `.dat` measurement files and computes metrics. `Report` is a collection of `RawFile` objects, serializable to JSON.
- **`desktop/`** — PyQt6 UI. `MainWindow` uses `QStackedWidget` for page navigation (Landing → Project → Analysis). Background work runs in `QThread` workers.
- **`dashboard/`** — Dash/Plotly web app embedded in `AnalysisPage` via threaded server on port 8050. Five tabs: Analyze File, Compare Files, Key Correlations, Predict Removal, AI Agent.
- **`ai/`** — Local LLM agent (Qwen 3.5 35B via Ollama) with native JSON tool calling. Three collaborating components plus a Dash-callback layer; see "AI subsystem" below.

### AI subsystem (`ai/`)

The agent is a thin, owned ReAct loop (~300 LOC) — no LangChain/CrewAI tax. Three classes do the work:

- **`AgentEngine`** (`ai/agent.py`) — owns the conversation. Holds the `messages` list (system prompt + user/assistant/tool turns), a streaming `Queue[StreamChunk]` for the Dash UI, and a daemon worker thread per user message. Each turn calls `ollama.Client.chat(model=_MODEL, tools=…, stream=True)` against a local Ollama daemon (default port 11434), consumes streamed `tool_calls`, dispatches them through `AgentTools`, appends the result as a `role=tool` message, and re-enters the loop. Hard caps: 8 tool rounds per user turn, history pruned at 48 K chars (`_prune_history`), `think=False` (Qwen's thinking tokens confused users in practice). The system prompt at lines 19–50 is the Senior CMP Process Engineer persona — keep that voice when adding new tool guidance.
- **`AgentTools`** (`ai/tools.py`) — registers **15** bound methods via `get_all_tools()` (line ~1745). Ollama auto-generates JSON schemas from type annotations + docstrings, so docstring wording is part of the tool API: it directly steers when and how the LLM calls each tool. Categories: data queries (`get_dataset_summary`, `get_file_details`, `find_files_by_config`, `get_feature_statistics`, `detect_outliers`), modelling (`run_automl`, `open_prediction_form`, `analyze_sensitivity`, `get_model_diagnostics`), and chart generators (`generate_scatter`, `generate_distribution`, `generate_bar_chart`, `generate_correlation_heatmap`, `generate_time_series`, `generate_model_plots`). Every chart tool returns the dual-channel `{"figure": <plotly-json>, "summary": <text>}` shape — the LLM only sees `summary`, the user sees `figure` rendered on the canvas.
- **`AutoMLManager`** (`ai/automl.py`) — FLAML wrapper for the agent's prediction tools. Searches over nine regression estimators (`lgbm`, `xgboost`, `xgb_limitdepth`, `rf`, `extra_tree`, `histgb`, `enet`, `lassolars`, `sgd`) with `eval_method="cv"`, `metric="rmse"`, `n_splits=min(5, max(2, n//3))`, `seed=42`. After FLAML returns a winner, a **second nested-CV pass** re-fits only the winning `(estimator, config)` once per outer fold (`time_budget=-1, max_iter=1, starting_points={best: [config]}`) to produce honest out-of-fold predictions in `_oof_pred` — this avoids the multiple-comparison bias of `automl.best_loss` while staying 10–50× faster than running full AutoML per fold. Per-prediction uncertainty: tree-ensemble spread for bagging models (`RandomForest`, `ExtraTrees`), CV RMSE fallback for boosting/linear. Feature importance: `sklearn.inspection.permutation_importance` (R² drop, `n_repeats=10`) — used uniformly because FLAML's native `feature_importances_` returns `None` for `histgb` and inflated raw coefficients for linear models.
- **`callbacks_agent.py`** — Dash callbacks that wire the chat input, streamed bubbles, tool indicators, and right-side canvas (chart + prediction form) to the `AgentEngine` queue. The prediction form is auto-opened and pre-populated when `run_automl` succeeds.

### Data flow

1. User imports `.dat` files → `FileImportWorker` copies to `project/data/`.
2. `RawFile.__init__()` parses the CSV, computes per-frame time-series and the `final_row` summary (COF, mean temp, var Fz, removal rate, …).
3. `Report` aggregates all `RawFile` objects; saved/loaded as `project.json` with paths relative to the project directory (`to_dict`/`from_dict`).
4. When the user clicks "Advanced Analysis", the desktop side calls `DataManager.update_report(report)` — the singleton at `dashboard/dash_bridge.py` is the **sole bridge** between the PyQt6 process and the Dash app threaded onto port 8050.
5. Every Dash callback, every AI tool, and every AutoML training run reads through that same singleton: `DataManager.get_all_data()` returns the per-file summary DataFrame; `DataManager.get_file_data(basename)` returns the per-frame time-series DataFrame for a single run. Because `AgentEngine`, `AgentTools`, and `AutoMLManager` are all constructed with the same `DataManager` reference, any data loaded in the desktop UI is immediately visible to the agent and to an external browser session pointed at `http://127.0.0.1:8050/`.

## Important Conventions

### RawFile property setters
All mutable properties on `RawFile` (`removal`, `nu`, `pressure_psi`, `polish_time`, `wafer_num`, `pad`, `slurry`, `conditioner`, …) are wrapped in `@property` / `@<name>.setter` decorators whose setters re-run the `final_row` computation. **Always assign through the setter** (`raw_file.removal = 1234`); never mutate `_final_row` directly and never bypass the setter via `__dict__` or `object.__setattr__`. The summary DataFrame returned by `DataManager.get_all_data()` is built from `final_row`, so a stale `_final_row` silently propagates into every chart, correlation, prediction, and AutoML training run downstream.

### DataFrame column names
- **Time-series** (per-frame): `'Fz Total (lbf)'`, `'Fy Total (lbf)'`, `'IR Temperature'`, etc.
- **Summary** (final_row): `'COF'`, `'Fz'`, `'Var Fz'`, `'Mean Temp'`, `'Removal'`, `'Pressure PSI'`, etc.
- **Categorical**: `'Wafer'`, `'Pad'`, `'Slurry'`, `'Conditioner'`
- Feature lists are defined in `dashboard/constants.py`:
  - `ANALYSIS_FEATURES` — measured outputs only (safe for PCA/K-Means, which cannot tolerate zero-variance columns through `StandardScaler`)
  - `CORRELATION_FEATURES` — `ANALYSIS_FEATURES` + controllable parameters (`Pressure PSI`, `Polish Time`); used by the AI agent's correlation heatmap, which defensively drops constant columns at call time
  - `FEATURE_AXIS_OPTIONS`, `SCATTER_FEATURE_OPTIONS` — UI dropdown labels for the Compare Files tab

### Callback organization
Dash callbacks are split by tab: `dashboard/callbacks.py` (registration entry point), `callbacks_single.py`, `callbacks_compare.py`, `callbacks_correlations.py`, `callbacks_prediction.py`, and `ai/callbacks_agent.py` for the AI Agent tab.

### Theming
Colors are centralized in `desktop/theme.py` (`COLORS` dict). The Dash side has its own `dashboard/styles.py` and `dashboard/plotly_theme.py`. Both use a dark theme.

### Project portability
`RawFile.to_dict(project_dir)` saves paths relative to the project directory; `from_dict(data, project_dir)` restores them. This lets users move project folders.

### ML models
There are two independent prediction pipelines — they do not share state.

**Predict Removal tab** (`dashboard/callbacks_prediction.py`):
- **Ridge Regression**: Adds interaction term `Pressure × Polish Time`, uses `RidgeCV` with LOO cross-validation
- **Random Forest**: 100 trees, `min_samples_leaf=3`, OOB scoring, uncertainty = std dev across trees
- Both use `Pipeline` + `ColumnTransformer` (OneHotEncoder for categoricals, StandardScaler for numericals)

**AI Agent's `run_automl` tool** (`ai/automl.py`):
- **FLAML AutoML** over nine regression estimators (lgbm, xgboost, xgb_limitdepth, rf, extra_tree, histgb, enet, lassolars, sgd); metric = RMSE; 5-fold CV; honest held-out OOF predictions via a second single-config refit per fold
- Categorical features use pandas `CategoricalDtype` snapshots taken at train time so predict-time rows keep the same category→code mapping
- Feature importance is computed via `sklearn.inspection.permutation_importance` (R² drop, n_repeats=10) — FLAML's native `feature_importances_` returns None for `histgb` and inflated raw coefficients for linear models, so permutation is used uniformly for comparable, model-agnostic values

### ML model consistency (`_cat_dtypes`)
FLAML's gradient-boosted and tree estimators consume categorical columns by their integer codes, not their string labels. `AutoMLManager.train()` therefore takes a snapshot of every training-time `CategoricalDtype` into `self._cat_dtypes` (a `dict[col, CategoricalDtype]`, see `ai/automl.py:109–111`) immediately after `X[col].astype("category")`. Any predict-time row **must** be cast back through that exact dtype before being passed to `self.automl.predict(...)`:

```python
for col in PREDICTION_CATEGORICAL_FEATURES:
    X_new[col] = X_new[col].astype(self._cat_dtypes[col])
```

The naive alternative — calling `astype("category")` on the single-row predict frame — re-derives the categories from whatever happens to be in that row, reassigns codes starting at `0`, and silently produces wrong predictions (Pad "IC1000" gets code `0` instead of, say, `3`). The same `_cat_dtypes` dict also drives `get_category_options()`, which is what the prediction form's dropdowns and the agent's `open_prediction_form` tool use to validate user-supplied category strings against the trained model's known levels. **Never rebuild categoricals from a fresh frame at predict time, and never reassign `_cat_dtypes` outside of `train()`.**

## Development & Debugging

The `Sample_Full_Data/` directory is the canonical fixture for manual tests and debugging. It holds `project.json` plus 94 `.dat` files; 76 of them have valid `Removal > 0`. Known quirks worth exercising: `Polish Time` is constant across the whole set (`nunique=1`), `Slurry` is single-valued (`CU4545F-300`), and `Conditioner` has only two levels — these are useful for checking constant-column and low-cardinality guards.

### Load the fixture in a shell

```python
import sys, json; sys.path.insert(0, '.')
from core.report import Report
from dashboard.dash_bridge import DataManager

with open('Sample_Full_Data/project.json') as f:
    data = json.load(f)
dm = DataManager()
dm.update_report(Report.from_dict(data['report'], project_dir='Sample_Full_Data'))
# dm is the same singleton the dashboard uses, so every downstream tool sees the same data.
```

Note the nesting — `project.json` has a top-level `"report"` key; pass `data['report']` to `Report.from_dict`, not `data`.

### Exercise the AI agent tools directly

```python
from ai.tools import AgentTools
from ai.automl import AutoMLManager

tools = AgentTools(dm, AutoMLManager(dm))
# Fast, data-only tools need no training:
print(tools.get_dataset_summary())
heatmap = tools.generate_correlation_heatmap()   # uses CORRELATION_FEATURES, drops constants
# Tools that need a trained model (run_automl takes ~30 s):
tools.run_automl(time_budget=20)
tools.get_model_diagnostics()
tools.generate_model_plots()
```

Every chart tool returns `{"figure": <plotly-json>, "summary": <text>}` — inspect `summary` for values, `figure['data'][0]` for the raw Plotly trace.

### Exercise the live UI (server must be running)

Start the app with `python main.py` (Dash serves at `http://127.0.0.1:8050/`). You can drive the AI Agent tab from an external browser or from Playwright MCP tools against the same URL — the `DataManager` singleton is shared, so data loaded in the PyQt window is visible to the browser session.

Useful snippet for inspecting a rendered chart's actual Plotly data via Playwright:

```js
() => {
  const plots = document.querySelectorAll('.js-plotly-plot');
  return Array.from(plots).map(p => ({
    title: p.layout?.title?.text || p.layout?.title || '',
    x: p._fullData?.[0]?.x,
    y: p._fullData?.[0]?.y,
    xaxis_range: p._fullLayout?.xaxis?.range,
  }));
}
```

This is how the blank Feature-Importance bug was originally identified — the trace showed `x=[0,0,0,0,0,0]` with `xaxis_range=[-1, 1]` despite the chart "looking right" to the LLM.

### Quick log-level observability

`ai/automl.py` and `ai/tools.py` use the `logging` module. To see every tool call, AutoML estimator selection, and permutation-importance output while iterating:

```bash
PYTHONUNBUFFERED=1 python main.py 2>&1 | tee /tmp/araca.log
```

Then `grep -E 'Permutation importance|Calling tool' /tmp/araca.log` to trace agent behavior without reading the full Ollama stream.
