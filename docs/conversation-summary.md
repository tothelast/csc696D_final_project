# Conversation Summary: AI Agent Integration for Araca Insights®

**Date:** 2026-03-29 (initial), 2026-04-05 (chat-canvas split, major revision + metric fix), 2026-04-07 (anti-hallucination redesign)
**Project:** Araca Insights® — semiconductor wafer polishing analytics

---

## Project Background

Araca Insights® is a dual-interface desktop + web analytics application for semiconductor wafer polishing data. It is built with PyQt6 for the desktop shell and Dash/Plotly for the embedded web dashboard. Prior to this session the dashboard had four tabs: Analyze File, Compare Files, Key Correlations, and Predict Removal. The Predict Removal tab offered manual model selection between Ridge Regression and Random Forest.

The goal of the initial session was to replace the manual Predict Removal tab with an intelligent AI agent that automates machine learning tasks and can explain results in natural language. A follow-up session on 2026-04-05 addressed a critical prediction bug, redesigned the agent canvas with an always-visible prediction form, and overhauled the chat UX.

---

## Brainstorming Phase

### Initial Proposal

The user proposed using LangChain + Ollama to build an LLM agent that would act as a "senior ML engineer," choosing which ML model to use and what hyperparameters to set.

### Critique of the Initial Approach

A detailed engineering critique identified four core problems with this approach:

1. **LLMs are the wrong tool for model selection.** LLMs pattern-match on training text, not on actual data distributions. AutoML frameworks (TPOT, auto-sklearn, FLAML) solve model selection rigorously by actually testing pipelines with cross-validation on the data at hand.

2. **LangChain adds unnecessary complexity.** Its dependency tree is large, its prompt engineering is fragile, and behavior is non-deterministic. For a single-provider local setup it provides no meaningful benefit over the native `ollama` Python client.

3. **Local LLM constraints are severe.** 7-8B parameter models require 8-16 GB of RAM and are slow on CPU. Reasoning quality is significantly below cloud models, making them unsuitable for tasks that require genuine statistical judgment.

4. **LLM-generated explanations are misleading.** When an LLM "chooses" a model it produces authoritative-sounding reasoning that is not grounded in actual statistical analysis of the data.

### Revised Hybrid Architecture

The user agreed to a better approach that separates concerns cleanly:

- **AutoML (FLAML)** handles actual model selection -- the right tool for statistical decisions because it empirically tests pipelines with cross-validation.
- **LLM (Qwen3.5 via Ollama)** handles explanation, Q&A, report narration, and guided data exploration -- the right tool for language tasks.

---

## Key Design Decisions

| Decision | Choice | Rationale |
|---|---|---|
| AutoML framework | FLAML (Microsoft) | Lightest dependencies, designed for small datasets, cost-efficient search |
| LLM model | Qwen3.5 9B via Ollama | Supports tool calling and thinking mode; successor to Qwen3; already installed at 6.6 GB |
| Python integration | `ollama` Python client (direct) | LangChain unnecessary for a single-provider local setup |
| UI placement | New Dash tab (AI Agent) alongside existing Predict Removal | Both tabs retained; agent canvas has its own prediction form |
| Agent autonomy | Fully automatic | Agent proactively runs FLAML; users never choose models manually |
| Prediction UX | Code-driven form, not LLM-driven | Predictions run deterministically via code; LLM only pre-fills the form |
| Memory | Session-only | No cross-project persistence; avoids data governance complications |
| Deployment | Bundled installer | Ollama binary and model shipped with the app; fully offline |
| Ollama lifecycle | App-managed | The desktop app spawns and kills its own Ollama process |

---

## Research Findings

### AutoML Framework Comparison

Every major AutoML framework was evaluated. Most were eliminated:

- **auto-sklearn** -- DEAD. Last release September 2022. No Python 3.12, no Windows support. Eliminated.
- **PyCaret** -- Abandoned since April 2024. Eliminated.
- **TPOT** -- Heavy Dask dependencies; genetic programming is overkill for datasets of 15-100 rows. Eliminated.
- **H2O AutoML** -- Requires a JVM. Eliminated.
- **AutoGluon** -- Best benchmark scores but requires PyTorch (~500 MB). Eliminated.
- **LazyPredict** -- Not actually AutoML. No hyperparameter tuning. Eliminated.
- **FLAML** -- Winner. Lightest dependencies, fast, performs well on small datasets. Designed by Microsoft Research.
- **mljar-supervised** -- Strong second-place choice. Best interpretability with SHAP integration.

### LLM Model Comparison

The Qwen3 model family was identified as uniquely suitable because it is the only family with both stable tool calling and a thinking mode available in Ollama.

- **DeepSeek-R1** -- Tool calling broken or unstable in Ollama. Eliminated.
- **Llama 3.x** -- Good tool calling but no native thinking mode.
- **Qwen3.5 9B** -- Initially reported as broken for tool calling, but tested and confirmed working on Ollama v0.18.3. Already installed. Selected.

---

## Implementation

### Architecture Overview

```
Dash Dashboard -- 5 tabs
  Analyze File | Compare Files | Key Correlations | Predict Removal | AI Agent

AI Agent tab layout (40/60 split):
  Left 40%: Chat column (messages, suggestions, input)
  Right 60%: Canvas column (50/50 side-by-side)
    Left half: Prediction form (dropdowns + numeric inputs + result)
    Right half: Charts carousel (prev/next navigation)

Backend services:
  Dash server (port 8050) | Ollama (port 11434/11435) | Agent Engine (background thread)
```

### New Module: `ai/` (5 files)

| File | Class | Responsibility |
|---|---|---|
| `ai/__init__.py` | -- | Package exports |
| `ai/automl.py` | `AutoMLManager` | FLAML wrapper: train models, generate predictions, compute diagnostics. Stores training CategoricalDtype for correct predict-time encoding. |
| `ai/tools.py` | `AgentTools` | 13 tool functions callable by the LLM agent, with input validation and category resolution |
| `ai/agent.py` | `AgentEngine` | Conversation loop, tool dispatch, streaming response assembly, prefill routing |
| `ai/callbacks_agent.py` | -- | Dash callbacks: send message, poll response, tab activation, canvas chart navigation/rendering, canvas prediction form, tool indicators |

### The 13 Agent Tools

**Data tools (4)**
- `get_dataset_summary` -- High-level overview of loaded data
- `get_file_details` -- Metadata and stats for a single `.dat` file
- `get_feature_statistics` -- Descriptive statistics for selected features, optionally grouped by categorical
- `detect_outliers` -- IQR-based outlier detection across the dataset

**ML tools (3)**
- `run_automl` -- Trigger FLAML to search and select the best regression pipeline (default 30s budget)
- `open_prediction_form` -- Pre-fill the canvas prediction form with resolved category values; does NOT compute predictions itself
- `get_model_diagnostics` -- Return cross-validation scores, feature importances, and residuals

**Chart tools (6)**
- `generate_scatter` -- Scatter plot of two features with optional color-by and filter (validates filter values)
- `generate_distribution` -- Histogram or box plot for a feature
- `generate_bar_chart` -- Grouped bar chart with error bars
- `generate_correlation_heatmap` -- Pearson correlation matrix heatmap (defaults to all 16 numerical features)
- `generate_time_series` -- Time-series plot for a single file
- `generate_model_plots` -- Predicted-vs-actual, feature importance, residuals, and residual distribution (4 charts)

### Modified Existing Files

- **`dashboard/layouts.py`** -- Added `build_prediction_form(id_prefix)` reusable helper; refactored Predict Removal tab to use it; redesigned AI Agent tab with side-by-side canvas (form left, charts right); added `agent-automl-trained` and `agent-pred-prefill` stores
- **`dashboard/callbacks.py`** -- Agent callback registration alongside existing prediction callbacks
- **`dashboard/callbacks_prediction.py`** -- Retained for the manual Predict Removal tab (Ridge/RF); uses sklearn Pipeline with OneHotEncoder
- **`dashboard/styles.py`** -- Added CSS for chat bubbles, tool indicators (running/done/failed with pulse animation), markdown content styling, canvas form/charts split sections
- **`dashboard/constants.py`** -- `PREDICTION_CATEGORICAL_FEATURES`, `PREDICTION_NUMERICAL_FEATURES`, `PREDICTION_TARGET` used across both manual and agent prediction paths
- **`desktop/main_window.py`** -- Ollama lifecycle management (start on app open, stop on app close)
- **`requirements.txt`** -- Added `flaml[automl]>=2.5.0` and `ollama>=0.4.0`

---

## Session 2 (2026-04-05): Critical Bug Fix + Canvas Redesign

### Critical Bug: Wrong Prediction (104 A vs 606 A)

**Symptom:** The AI agent predicted 104 A for Ox/FjH800/CU4545F-300/3MA82AF-3lbf/1.5 PSI/1 min. The manual Random Forest tab predicted 606 A for the same configuration. The true expert value is ~606 A (training data replicates: 389, 457, 604, 688 A; mean 534.5 A).

**Root cause:** In `ai/automl.py`, the `predict()` method created a fresh single-row DataFrame and called `.astype("category")`, which generated NEW category codes starting at 0. Training used alphabetical codes: `Wafer {Cu:0, Ox:1, TaN:2}`, `Pad {CH052:0, CH059:1, FjH800:2}`. So "Ox" (training code 1) arrived as code 0, and "FjH800" (training code 2) arrived as code 0 -- FLAML's XGBoost interpreted the row as Cu/CH052, whose training prediction is exactly 104.3 A.

**Fix:** Store training `CategoricalDtype` per column in `self._cat_dtypes` during `train()`. Apply the stored dtypes in `predict()` so category codes are consistent.

**Verification:** Prediction jumped from 104.3 A to 539.9 A (matches training mean of 534.5 A).

### Inline Chart Fix: Chat-Canvas Split

**Symptom:** When the AI agent generated a chart, it rendered inline inside the chat bubble area. Charts frequently shrank to unreadable sizes or failed to appear at all.

**Root cause:** Charts were appended directly into the chat message list as `dcc.Graph` components with a hardcoded `height: 380px`. The chat container is a vertical flex column sized for text bubbles (`.agent-message { max-width: 85% }`). Plotly's default margins (~130 px horizontal, ~100 px vertical) consumed a large fraction of the constrained 380 px, leaving very little actual plotting area. When multiple charts or long conversations pushed content out of the scroll viewport, freshly appended charts were rendered offscreen entirely.

**Fix:** Split the AI Agent tab into a two-pane layout:
- **Left column (40%):** Chat messages, suggestion chips, and input — unchanged except `.agent-message` max-width widened to 95% for the narrower column.
- **Right column (60%):** Dedicated canvas with a full-height `dcc.Graph` (`responsive: True`), a `"0 / 0"` counter, and prev/next navigation buttons. An empty-state placeholder shown before any charts are generated.

Charts are no longer rendered in chat. Instead:
1. `poll_response` appends each chart to a `dcc.Store('agent-chart-history')` list and sets `dcc.Store('agent-chart-index')` to the newest entry.
2. A `[Chart N generated →]` system message is inserted into the chat as a contextual reference.
3. A new `render_canvas` callback reads history + index and renders the active chart at full canvas size, updates the counter, and toggles prev/next button states.
4. A new `navigate_canvas` callback handles prev/next clicks with bounds clamping.

Multi-chart tools (`generate_model_plots` returns 4 figures via `StreamChunk("charts", ...)`) append each figure as a separate history entry.

**Files modified:**
- `dashboard/layouts.py` — `build_agent_tab()` restructured into `.agent-split` > `.agent-chat-column` + `.agent-canvas-column` with canvas header/body/footer and two new stores (`agent-chart-history`, `agent-chart-index`).
- `dashboard/styles.py` — Added `.agent-split`, `.agent-chat-column`, `.agent-canvas-column`, `.agent-canvas-header/body/empty/footer`, `.agent-canvas-nav-btn` CSS rules.
- `ai/callbacks_agent.py` — `poll_response` routes charts to history store instead of inline `dcc.Graph`; added `navigate_canvas` and `render_canvas` callbacks; removed unused `dcc` import.

This initial canvas implementation (100% chart carousel) was later enhanced in the Canvas Redesign below to include the always-visible prediction form alongside the charts.

### Canvas Redesign: Always-Visible Prediction Form

**Problem:** Predictions through the LLM were non-deterministic, slow, and could silently pass wrong category strings (e.g., the LLM abbreviated "CU4545F-300" to "CU4545F").

**Design decision:** Predictions are computed by code, not by the LLM. Form dropdowns bound to training categories eliminate the abbreviated-value failure mode by construction.

**Implementation:**
- Canvas column (right 60% of agent tab) split side-by-side: prediction form (left 50%) and charts (right 50%)
- `build_prediction_form(id_prefix)` helper generates form from `PREDICTION_CATEGORICAL_FEATURES` and `PREDICTION_NUMERICAL_FEATURES` -- adding a new column only requires updating `dashboard/constants.py`
- `predict_removal` tool replaced with `open_prediction_form` -- LLM extracts user's values, resolves abbreviated categories via fuzzy matching (exact -> prefix -> substring), and pre-fills the form via `agent-pred-prefill` store
- Actual prediction runs in `canvas_predict` callback, calling `AutoMLManager.predict()` directly
- Agent is NOT notified of form-submitted predictions; user can discuss results by referencing values in chat

### Race Condition Fix: Form Appeared Before Model Trained

**Symptom:** The prediction form appeared mid-training (while FLAML was still fitting), and clicking Predict produced `'NoneType' object is not subscriptable`.

**Root cause:** `self.automl = AutoML()` is set before `fit()` completes, so `automl is not None` became True immediately. But `self.metrics` was still None.

**Fix:** Changed trained flag to check both `automl is not None AND metrics is not None`. Added a "Training in progress" guard message in `canvas_predict`.

### Stale Store Fix: Form Hidden After Navigation

**Symptom:** When the user left the dashboard and returned, the `agent-automl-trained` store reset to False, hiding the form until the next interaction.

**Fix:** Added `sync_trained_on_tab` callback that fires on tab activation (including initial page load via `prevent_initial_call='initial_duplicate'`), reads engine state, and updates the store.

---

## Session 2: Chat UX Overhaul

### Markdown Rendering

**Problem:** The LLM output markdown syntax (`**bold**`, `- lists`, ``` `code` ```) that showed as literal noise in plain-text `html.Div` chat bubbles.

**Fix:** Replaced `html.Div` with `dcc.Markdown` for assistant messages. Updated system prompt to use clean, minimal Markdown (bold for key terms, dashes for lists, no headers, no emojis). Added CSS for `p`, `ul`, `li`, `code`, `strong`, `a` inside `.agent-message.assistant`.

### Tool Execution Indicators

**Problem:** No visible indication when a tool was running. Users couldn't tell if the agent was working or finished.

**Fix:**
- `_execute_tool` in `agent.py` now emits `StreamChunk("tool_start", func_name)` before execution and `StreamChunk("tool_end", {name, success})` after
- Chat shows styled pill indicators: `○ Training prediction model…` (blue pulsing while running), `✓ Training prediction model` (green when done), `✗ ...` (red on failure)
- 13 tool-to-friendly-label mappings in `_TOOL_LABELS`

### Split Message Bubbles Across Tool Calls

**Problem:** Pre-tool text ("I'll train a model") and post-tool text ("Training complete") were concatenated into one giant bubble.

**Fix:** `tool_start` chunk handler closes any in-progress streaming bubble. Text arriving after a tool call opens a fresh bubble.

### Tool Indicator Stuck in "Running" State

**Problem:** Fast tools like `get_dataset_summary` (completing in milliseconds) had their indicator stuck in blue/running forever, even though the tool had completed.

**Root cause:** Within one `poll_response` callback tick, `children` is a mixed list: existing entries arrive as dicts (from Dash State), freshly appended entries are Dash component objects. All checker functions (`_find_running_tool_indicator`, `_is_assistant_streaming`, `_is_loading`, etc.) used `isinstance(c, dict)` and skipped Dash component objects. When `tool_start` and `tool_end` landed in the same tick, the finder couldn't locate the fresh indicator.

**Fix:** Added `_props(c)` helper that normalizes both dicts and Dash components via `to_plotly_json()`. Rewrote all checker functions to use it. Verified with 16 unit tests covering both dict and component forms.

### Thinking Mode Disabled

**Problem:** Qwen3.5's `think=True` mode produced "Reasoning..." collapsible panels that confused users ("What is this? Is the agent still working?").

**Fix:** Set `think=False`. Tool indicators and loading bubble already convey working state clearly.

---

## Session 2: Defensive Tool Improvements

### Correlation Heatmap Empty List Bug

**Problem:** When the LLM passed `features=[]` (empty list), the heatmap was empty. The code only checked `if features is None:` for the default fallback.

**Fix:** Changed to `if not features:` so both None and empty list trigger the default (all 16 ANALYSIS_FEATURES).

### Scatter Plot Invalid Filter Values

**Problem:** The LLM hallucinated filter values (e.g., `filter_value='SAE SOL'` for a pad that doesn't exist). The scatter tool silently produced an empty plot.

**Fix:** Added validation: check `filter_value` against actual unique values in the data. Return an error string listing valid options if no match, so the LLM can self-correct.

### Feature Importance Generic Names

**Problem:** Feature importance plots showed `feature_0, feature_1, feature_2, feature_3` instead of actual names like Pad, Wafer, Pressure PSI, Conditioner.

**Root cause:** FLAML's DataTransformer drops constant columns (Polish Time, Slurry), so the model sees 4 features while `feature_cols` has 6 entries. Length mismatch triggered a fallback to generic names. Additionally, some estimators had `feature_importances_` set to `None` rather than absent.

**Fix:** When lengths don't match, read actual post-transform column names from FLAML's `_transformer.transform()`. Added None guards for `feature_importances_` and `coef_`.

### Redundant Dataset Summary Before Training

**Problem:** The greeting already shows "76 polishing runs loaded, 76 with removal data." When the user said "Build a prediction model", the agent called `get_dataset_summary` first and repeated the same information.

**Fix:** System prompt now instructs: "When the user asks to train a model, call `run_automl` DIRECTLY. Reserve reconnaissance tools for when the user explicitly asks about the data."

### Time Budget and Form Auto-Open

**Problem 1:** Agent told users training takes "60 seconds" but actual wall time was ~2 minutes (nested CV). **Fix:** Updated `run_automl` docstring to explain 2x factor and set default to 30s.

**Problem 2:** Agent asked "Would you like to open the prediction form?" but the form auto-opens after training. **Fix:** `run_automl` tool output now includes "Prediction form status: READY" and system prompt says "Do NOT ask if they want to open the form."

**Problem 3:** Agent refused to accept `time_budget=30`, hallucinating a minimum of 60s. **Fix:** Docstring now explicitly states "Any positive integer is valid -- there is NO minimum."

### System Prompt Best Practices

The system prompt was rewritten following Qwen3.5/Ollama best practices:

- Structured sections: `# Tool usage rules`, `# Response format`, `# Tone`
- Markdown rendering enabled: allows `**bold**`, `- lists`, backtick `code` (rendered via `dcc.Markdown`)
- Forbids headers (`#`), emojis, code fences around entire responses
- Tool pre-announcement rule: "ALWAYS write a short sentence BEFORE calling any tool"
- One tool per response rule: prevents XML parser failures from batched tool calls
- Direct reconnaissance ban for training requests
- Explicit time budget guidance and form auto-open awareness

---

## Bugs Found and Fixed (Session 1)

Six bugs were identified and resolved during the initial testing phase.

### Bug 1 -- XGBRegressor `classes_` AttributeError

**Symptom:** FLAML selected XGBoost as the best model, but metric calculation crashed with an `AttributeError` on `classes_`.

**Root cause:** FLAML's XGBoost wrapper does not expose the `classes_` attribute that scikit-learn's `cross_val_score` expects.

**Fix:** Replaced `cross_val_score` with direct `model.predict()` followed by manual `r2_score` and `mean_absolute_error` calculations.

### Bug 2 -- No loading indicator

**Symptom:** The UI appeared frozen while the LLM was processing.

**Fix:** A "Thinking..." placeholder message is inserted immediately when a request is submitted, then replaced when the actual response arrives.

### Bug 3 -- Wrong predictions and NaN metrics

**Symptom:** Model predictions were nonsensical and metric values showed as NaN.

**Root cause:** Downstream effect of Bug 1. The XGBoost CV failure produced NaN scores.

**Fix:** Resolved by the same fix as Bug 1.

### Bug 4 -- Charts not generating

**Symptom:** Agent-generated charts returned errors instead of figures.

**Root cause:** `fig.update_layout(**DARK_LAYOUT, title="...")` passed the `title` key twice.

**Fix:** Split into two separate `update_layout()` calls.

### Bug 5 -- Thinking fragments rendering as multiple collapsibles

**Symptom:** Each 200ms poll that found thinking-mode chunks created a new `<details>` element.

**Fix:** All thinking chunks accumulated server-side and flushed as a single block.

### Bug 6 -- OllamaManager port mismatch

**Symptom:** App failed to connect to Ollama even though it was running.

**Fix:** `OllamaManager` now checks port 11434 first; falls back to 11435.

### Bug 7 -- OllamaManager constructor signature mismatch

**Symptom:** `on_tab_activate` callback crashed when passed `port=` keyword.

**Fix:** Call site updated to use direct HTTP health check.

---

## Session 3 (2026-04-05): AutoML Metric Inflation Fix + Manual Tab Restoration

### Critical Bug: AutoML R² Inflated by Training-Set Evaluation

**Symptom:** The AI Agent's AutoML (FLAML) consistently reported higher R² than the manual Ridge/Random Forest models in the Predict Removal tab, yet produced worse actual predictions on new data.

**Root cause investigation:** A systematic comparison of the two pipelines (AutoML in `ai/automl.py` vs manual in `araca/dashboard/callbacks_prediction.py`) revealed three compounding issues:

1. **Training-set R² and MAE (primary cause).** `ai/automl.py:96-101` computed metrics by calling `self.automl.predict(X)` on the same data the model was trained on. After FLAML's `fit()`, the best model is refit on all data, so `predict(X)` evaluates on training data -- yielding optimistically high R² (e.g., 0.996 vs honest 0.879 on test data). The manual pipeline used `cross_val_score` on a fresh unfitted pipeline per fold, giving honest held-out metrics.

2. **Multiple-comparison bias in `best_loss`.** FLAML searches across many estimator × hyperparameter configs and reports the best CV RMSE found. "Best over many searches" is a biased-low estimate of true generalization error (winner's curse).

3. **No linear model in estimator list.** The list was `["lgbm", "xgboost", "rf", "extra_tree"]` -- all tree-based. On small wafer-polishing datasets (5-30 files), Ridge Regression often generalizes better. FLAML had no chance to pick a linear model.

**Fixes applied:**

| Fix | File | Description |
|---|---|---|
| Nested CV metrics | `ai/automl.py` | Replaced training-set R²/MAE/RMSE with nested 5-fold CV. Each outer fold runs a fresh FLAML search on the training portion and predicts on the held-out portion. Out-of-fold predictions give honest generalization metrics matching the manual pipeline's methodology. |
| OOF diagnostics | `ai/automl.py` | `get_diagnostics()` now uses cached out-of-fold predictions (`self._oof_pred`) instead of `self.automl.predict(X)`. All diagnostic plots (Predicted vs Actual, Residuals, Residual Distribution) now reflect held-out performance. |
| Expanded estimator list | `ai/automl.py` | Changed to `["lgbm", "xgboost", "xgb_limitdepth", "rf", "extra_tree", "histgb", "enet"]`. Added `xgb_limitdepth` (regularized XGBoost for small data), `histgb` (sklearn HistGradientBoosting), and `enet` (ElasticNet -- Ridge-equivalent regression linear model). |
| Metric labels | `ai/tools.py` | Docstrings and output strings updated to say "held-out 5-fold CV metrics", "CV RMSE", "CV MAE" to accurately reflect the methodology. |

**Failed approach:** Initially tried adding `"lrl2"` (L2-regularized Logistic Regression) to FLAML's estimator list. Discovered at runtime that `lrl2` is classification-only (`AssertionError: LogisticRegression for classification task only`). Replaced with `"enet"` (ElasticNet), which is the correct regression-capable L2-regularized linear model in FLAML.

**Verified:** End-to-end test on synthetic 30-row dataset confirmed:
- Training R² = 0.996 vs honest OOF R² = 0.879 (gap of 0.117)
- Training MAE = 56 vs OOF MAE = 305 (old reporting was 5.4× too optimistic)
- All 7 estimators in the new list train successfully for `task="regression"`
- `enet` won 4/5 inner folds on linear-relationship data, confirming the linear model is reachable

### Manual Predict Removal Tab Restored

The manual Predict Removal tab (Ridge Regression / Random Forest with sklearn Pipeline + OneHotEncoder + StandardScaler) was restored from the araca project to give users both manual and automated prediction workflows side by side.

**Files added/modified:**
- `dashboard/callbacks_prediction.py` -- Copied from `araca/dashboard/callbacks_prediction.py` (584 lines). Provides `RidgeCV` and `RandomForestRegressor` training with honest 5-fold CV metrics via `cross_val_predict` / `cross_val_score`, prediction form, and 2×2 diagnostics grid.
- `dashboard/layouts.py` -- Added `build_prediction_tab()` function (125 lines) and inserted it into `build_app_layout()` with `dcc.Store(id='pred-model-store')`.
- `dashboard/callbacks.py` -- Imported and registered `register_prediction_callbacks`.

**No other changes needed:** CSS classes (`.prediction-grid`, `.pred-btn`, `.pred-metrics`, `.pred-result-box`) already existed in `dashboard/styles.py`. Constants (`PREDICTION_CATEGORICAL_FEATURES`, `PREDICTION_NUMERICAL_FEATURES`, `PREDICTION_TARGET`) already existed in `dashboard/constants.py`.

**Tab order:** Analyze File → Compare Files → Key Correlations → **Predict Removal** → AI Agent.

### Polish Time Unit Consistency

Verified that Polish Time is consistently stored, trained on, and predicted in **minutes** across every surface in the project: `core/raw_file.py` (storage), `desktop/file_details_panel.py` (desktop form), `dashboard/layouts.py` (Predict Removal form label: "Polish Time (min)"), `ai/tools.py` (agent tool docstring: "Polish duration in minutes"), and `ai/automl.py` (prediction pass-through). Both the manual tab and the AI agent expect minutes; no unit mismatch exists.

---

## Dependencies Added

| Package | Version constraint | Purpose |
|---|---|---|
| `flaml[automl]` | `>=2.5.0` | AutoML framework (pulls in LightGBM, XGBoost) |
| `ollama` | `>=0.4.0` | Ollama Python client for LLM communication |

---

## Final State

All implementation is complete across three sessions. The dashboard has five tabs:

**Predict Removal tab** (manual models):
- **Ridge Regression** with `RidgeCV(alphas=logspace(-3,3,50))` and `P_x_T` interaction term
- **Random Forest** with `n_estimators=100, min_samples_leaf=3, oob_score=True`
- Honest 5-fold CV metrics via `cross_val_predict` / `cross_val_score`
- sklearn Pipeline with `OneHotEncoder` + `StandardScaler`
- 2×2 diagnostic plots: Predicted vs Actual, Feature Importance, Residuals, Residual Distribution

**AI Agent tab** (automated models + natural language):
- **AutoML training** via FLAML with 7 estimators: `lgbm`, `xgboost`, `xgb_limitdepth`, `rf`, `extra_tree`, `histgb`, `enet`
- **Honest nested-CV metrics** -- out-of-fold predictions from 5-fold nested CV eliminate training-set inflation and multiple-comparison bias
- **13 tools** covering data exploration, ML training, prediction, and chart generation
- **Canvas prediction form** (always visible after training) with dropdowns populated from training categories -- deterministic, code-driven predictions
- **Category resolution** for LLM-abbreviated values (fuzzy matching: exact -> prefix -> substring)
- **Tool execution indicators** with running/done/failed states and pulse animation
- **Markdown rendering** in chat bubbles via `dcc.Markdown`
- **Split message bubbles** across tool calls for clean conversation flow
- **Defensive tool validation** -- invalid filter values, empty feature lists, and None importances all handled gracefully with informative error messages
- **Proper CategoricalDtype preservation** at predict time -- eliminates the silent category-code mismatch bug
- **Ollama lifecycle management** including graceful detection of system-wide instances
- **Session-only memory** with no cross-project persistence

Both prediction interfaces use the same feature set (`Pressure PSI`, `Polish Time` in minutes, `Wafer`, `Pad`, `Slurry`, `Conditioner`) and target (`Removal` in Angstroms), enabling direct comparison of manual vs automated model selection.

---

## Session 4 (2026-04-07): Anti-Hallucination Redesign & LLM Parameter Optimization

### Critical Problem: Agent Hallucinating Chart Interpretations

**Symptom:** When the agent generated charts (especially the correlation heatmap), it fabricated interpretations of data it couldn't see. Example: the heatmap showed COF has a **0.55 positive** correlation with Removal, but the agent claimed "a **strong negative** correlation" -- completely wrong. This created mistrust because the user could see the chart contradicting the agent's claims.

**Root cause:** `_format_tool_result()` in `agent.py` stripped all chart data, returning only `[Chart generated and displayed to user]` to the LLM. The LLM had zero information about the chart's contents but was not instructed to admit ignorance, so it confabulated plausible-sounding (but incorrect) interpretations.

**Design decision:** Rather than making the agent say "I can't see the chart," feed the actual data back. This makes the agent genuinely knowledgeable about what it shows.

### Fix 1: Chart Summary Extraction (ai/tools.py)

All 6 chart tools changed return format from bare Plotly JSON (`fig.to_plotly_json()`) to `{"figure": <plotly_json>, "summary": "<text digest>"}`. The summary gives the LLM real numbers to cite:

| Tool | Summary contents |
|------|-----------------|
| `generate_correlation_heatmap` | All correlations with Removal sorted by \|r\|, top 5 strongest feature pairs overall |
| `generate_scatter` | Pearson r, trend direction, axis ranges, group count if colored |
| `generate_distribution` | mean, std, min, max, skewness direction (histogram) or per-group mean/median with highest/lowest (box plot) |
| `generate_bar_chart` | Per-group mean and std, highest and lowest group |
| `generate_time_series` | Per-feature min, max, mean, trend direction (increasing/decreasing/stable) |
| `generate_model_plots` | R², residual stats, top 5 feature importances, 3 largest prediction errors with file names |

Empty-data returns also wrapped in the new format: `{"figure": self._empty_fig(...), "summary": "No data loaded."}`.

### Fix 2: Agent Engine Routing & Formatting (ai/agent.py)

**`_execute_tool` result routing** updated to detect the new format:
1. `{"figure": ...}` → extract `result["figure"]` for UI StreamChunk (bare Plotly JSON, backwards-compatible)
2. `{"figures": [...]}` → extract `result["figures"]` for UI StreamChunk
3. Legacy `{"data": ...}` and `list[dict]` fallbacks retained for safety

**`_format_tool_result` redesign** -- feeds summaries to the LLM:
- `{"figure": ..., "summary": ...}` → `"[Chart displayed to user]\nData summary:\n{summary}"`
- `{"figures": ..., "summary": ...}` → `"[N diagnostic charts displayed to user]\nData summary:\n{summary}"`
- Summary truncated to 1500 chars max to prevent context bloat
- Legacy formats fall back to `"[Chart displayed to user]"` (no summary)

### Fix 3: Anti-Hallucination System Prompt Rules

Added two new sections to the system prompt:

**Data accuracy rules:**
- Use ONLY exact numbers from the data summary when discussing charts
- Never round differently, invent trends, or embellish beyond what the summary states
- Never describe visual patterns that cannot be verified from the numerical summary
- Always include the actual r value when stating correlations (e.g., "r=0.55") rather than vague terms

**Smart defaults guidance:**
- When the user's request is ambiguous, pick reasonable defaults and state what was chosen
- Example: "I'll use all numerical features for the heatmap"

### Fix 4: Ollama Parameter Optimization

Added explicit LLM parameters (previously all unset, using Ollama defaults):

```python
_CHAT_OPTIONS = {"temperature": 0.2, "num_ctx": 16384, "num_predict": 4096}
```

| Parameter | Previous | New | Rationale |
|-----------|----------|-----|-----------|
| `temperature` | ~0.7-0.8 (default) | 0.2 | Reduces creativity/randomness; makes the model stick to provided data rather than embellishing. Key factor in reducing hallucination. |
| `num_ctx` | unset (model default) | 16384 | Explicitly sets context window. Qwen3.5 supports 256K but 16K balances memory usage with practical needs. |
| `num_predict` | unset | 4096 | Prevents runaway generation. Agent responses rarely exceed 1-2K tokens. |

### Fix 5: Conversation History Limit Increased

Changed `max_chars` in `_prune_history()` from 24,000 to 48,000. The old limit (~6K tokens) was overly conservative and could prune important tool results from recent turns. The new limit (~12K tokens) fits comfortably within the 16K context window while preserving more conversation history, especially important now that chart summaries add ~300-800 chars per tool result.

### Files Modified

| File | Changes |
|------|---------|
| `ai/tools.py` | Added `import itertools`. All 6 chart methods return `{"figure": ..., "summary": ...}` instead of bare Plotly JSON. Added summary extraction logic (~80 new lines). Updated empty-data returns. |
| `ai/agent.py` | Added `_CHAT_OPTIONS` constant. Updated `client.chat()` to pass `options=_CHAT_OPTIONS`. Added "Data accuracy rules" and smart-defaults guidance to system prompt (~10 lines). Redesigned `_execute_tool` detection (~8 lines) and `_format_tool_result` (~15 lines) for new format with legacy fallbacks. Increased `max_chars` from 24,000 to 48,000. |

**No changes to:** `ai/callbacks_agent.py`, `ai/automl.py`, `ai/ollama_manager.py`. The UI pipeline is unaffected because `_execute_tool` extracts `result["figure"]` before pushing to the StreamChunk queue -- callbacks receive the same bare Plotly JSON as before.

### Design Decisions Discussed But Not Implemented

- **Context window sizing for RTX 5070 Ti (16 GB VRAM):** Analysis showed 32K tokens would be comfortably handled by the hardware. Currently set to 16K which is sufficient for the agent's conversation patterns (typical 5-turn chat uses ~2,200 tokens, heavy 10-turn session ~5,300 tokens). Can be bumped to 32K if users report the agent "forgetting" earlier conversation.
- **Coupling pruning limit to num_ctx:** The `max_chars` and `num_ctx` are currently independent constants. If `num_ctx` changes, `max_chars` should be updated proportionally. A derived formula was discussed but not yet implemented.
