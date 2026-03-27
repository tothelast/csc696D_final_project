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

No test suite, linter, or CI pipeline is configured.

## Architecture

### Three-layer structure

- **`core/`** — Data models. `RawFile` parses `.dat` measurement files and computes metrics. `Report` is a collection of `RawFile` objects, serializable to JSON.
- **`desktop/`** — PyQt6 UI. `MainWindow` uses `QStackedWidget` for page navigation (Landing → Project → Analysis). Background work runs in `QThread` workers.
- **`dashboard/`** — Dash/Plotly web app embedded in `AnalysisPage` via threaded server on port 8050. Four tabs: Analyze File, Compare Files, Key Correlations, Predict Removal.

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
- Feature lists are defined in `dashboard/constants.py` (`ANALYSIS_FEATURES`, `FEATURE_AXIS_OPTIONS`, `SCATTER_FEATURE_OPTIONS`)

### Callback organization
Dash callbacks are split by tab: `callbacks.py` (registration entry point), `callbacks_single.py`, `callbacks_compare.py`, `callbacks_correlations.py`, `callbacks_prediction.py`.

### Theming
Colors are centralized in `desktop/theme.py` (`COLORS` dict). The Dash side has its own `dashboard/styles.py` and `dashboard/plotly_theme.py`. Both use a dark theme.

### Project portability
`RawFile.to_dict(project_dir)` saves paths relative to the project directory; `from_dict(data, project_dir)` restores them. This lets users move project folders.

### ML models (Predict Removal tab)
- **Ridge Regression**: Adds interaction term `Pressure × Polish Time`, uses `RidgeCV` with LOO cross-validation
- **Random Forest**: 100 trees, `min_samples_leaf=3`, OOB scoring, uncertainty = std dev across trees
- Both use `Pipeline` + `ColumnTransformer` (OneHotEncoder for categoricals, StandardScaler for numericals)
