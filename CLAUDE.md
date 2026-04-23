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

No test suite, linter, or CI pipeline is configured. See "Testing and debugging with real CMP data" below for the ad-hoc pattern used during development.

## Architecture

### Four-layer structure

- **`core/`** — Data models. `RawFile` parses `.dat` measurement files and computes metrics. `Report` is a collection of `RawFile` objects, serializable to JSON.
- **`desktop/`** — PyQt6 UI. `MainWindow` uses `QStackedWidget` for page navigation (Landing → Project → Analysis). Background work runs in `QThread` workers.
- **`dashboard/`** — Dash/Plotly web app embedded in `AnalysisPage` via threaded server on port 8050. Five tabs: Analyze File, Compare Files, Key Correlations, Predict Removal, AI Agent.
- **`ai/`** — Local LLM agent (qwen3.5 via Ollama) with tool calling. `agent.py` drives the conversation loop; `tools.py` defines the ~13 tools (data queries, chart generators, AutoML trainer); `automl.py` wraps FLAML for the prediction model; `callbacks_agent.py` registers the chat/canvas Dash callbacks.

### Data flow

1. User imports `.dat` files → `FileImportWorker` copies to `project/data/`
2. `RawFile.__init__()` parses CSV, calculates metrics (COF, temperature, removal rate, etc.)
3. `Report` holds all `RawFile` objects; saved/loaded as `project.json` with relative paths
4. On "Advanced Analysis", `DataManager` singleton receives the `Report` reference
5. Dash callbacks read from `DataManager.get_all_data()` (summary DataFrame) or `DataManager.get_file_data(basename)` (time-series DataFrame)

### Key bridge pattern

`DataManager` (`dashboard/dash_bridge.py`) is a singleton that bridges PyQt6 and Dash. The desktop side sets the report; the dashboard side reads it. This is the only shared state between the two interfaces.

## Important Conventions

### RawFile property setters
All mutable properties (`removal`, `nu`, `pressure_psi`, `polish_time`, `wafer_num`, etc.) use `@property`/`@setter` decorators that trigger `final_row` recalculation. Always use setters, never modify `_final_row` directly.

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

## Testing and debugging with real CMP data

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
