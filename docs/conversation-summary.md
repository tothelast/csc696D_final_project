# Conversation Summary: AI Agent Integration for Araca Insights®

**Date:** 2026-03-29
**Project:** Araca Insights® — semiconductor wafer polishing analytics

---

## Project Background

Araca Insights® is a dual-interface desktop + web analytics application for semiconductor wafer polishing data. It is built with PyQt6 for the desktop shell and Dash/Plotly for the embedded web dashboard. Prior to this session the dashboard had four tabs: Analyze File, Compare Files, Key Correlations, and Predict Removal. The Predict Removal tab offered manual model selection between Ridge Regression and Random Forest.

The goal of this session was to replace the manual Predict Removal tab with an intelligent AI agent that automates machine learning tasks and can explain results in natural language.

---

## Brainstorming Phase

### Initial Proposal

The user proposed using LangChain + Ollama to build an LLM agent that would act as a "senior ML engineer," choosing which ML model to use and what hyperparameters to set.

### Critique of the Initial Approach

A detailed engineering critique identified four core problems with this approach:

1. **LLMs are the wrong tool for model selection.** LLMs pattern-match on training text, not on actual data distributions. AutoML frameworks (TPOT, auto-sklearn, FLAML) solve model selection rigorously by actually testing pipelines with cross-validation on the data at hand.

2. **LangChain adds unnecessary complexity.** Its dependency tree is large, its prompt engineering is fragile, and behavior is non-deterministic. For a single-provider local setup it provides no meaningful benefit over the native `ollama` Python client.

3. **Local LLM constraints are severe.** 7–8B parameter models require 8–16 GB of RAM and are slow on CPU. Reasoning quality is significantly below cloud models, making them unsuitable for tasks that require genuine statistical judgment.

4. **LLM-generated explanations are misleading.** When an LLM "chooses" a model it produces authoritative-sounding reasoning that is not grounded in actual statistical analysis of the data.

### Revised Hybrid Architecture

The user agreed to a better approach that separates concerns cleanly:

- **AutoML (FLAML)** handles actual model selection — the right tool for statistical decisions because it empirically tests pipelines with cross-validation.
- **LLM (Qwen3.5 via Ollama)** handles explanation, Q&A, report narration, and guided data exploration — the right tool for language tasks.

---

## Key Design Decisions

| Decision | Choice | Rationale |
|---|---|---|
| AutoML framework | FLAML (Microsoft) | Lightest dependencies, designed for small datasets, cost-efficient search |
| LLM model | Qwen3.5 9B via Ollama | Supports tool calling and thinking mode; successor to Qwen3; already installed at 6.6 GB |
| Python integration | `ollama` Python client (direct) | LangChain unnecessary for a single-provider local setup |
| UI placement | New Dash tab replacing Predict Removal | Stays in the web layer; Plotly charts are native |
| Agent autonomy | Fully automatic | Agent proactively runs FLAML; users never choose models manually |
| Memory | Session-only | No cross-project persistence; avoids data governance complications |
| Deployment | Bundled installer | Ollama binary and model shipped with the app; fully offline |
| Ollama lifecycle | App-managed | The desktop app spawns and kills its own Ollama process |

---

## Research Findings

### AutoML Framework Comparison

Every major AutoML framework was evaluated. Most were eliminated:

- **auto-sklearn** — DEAD. Last release September 2022. No Python 3.12, no Windows support. Eliminated.
- **PyCaret** — Abandoned since April 2024. Eliminated.
- **TPOT** — Heavy Dask dependencies; genetic programming is overkill for datasets of 15–100 rows. Eliminated.
- **H2O AutoML** — Requires a JVM. Eliminated.
- **AutoGluon** — Best benchmark scores but requires PyTorch (~500 MB). Eliminated.
- **LazyPredict** — Not actually AutoML. No hyperparameter tuning. Eliminated.
- **FLAML** — Winner. Lightest dependencies, fast, performs well on small datasets. Designed by Microsoft Research.
- **mljar-supervised** — Strong second-place choice. Best interpretability with SHAP integration.

### LLM Model Comparison

The Qwen3 model family was identified as uniquely suitable because it is the only family with both stable tool calling and a thinking mode available in Ollama.

- **DeepSeek-R1** — Tool calling broken or unstable in Ollama. Eliminated.
- **Llama 3.x** — Good tool calling but no native thinking mode.
- **Qwen3.5 9B** — Initially reported as broken for tool calling, but tested and confirmed working on Ollama v0.18.3. Already installed. Selected.

---

## Implementation

### Architecture Overview

```
Dash Dashboard — 4 tabs
  Analyze File | Compare Files | Key Correlations | AI Agent (new, replaces Predict Removal)

Backend services
  Dash server (port 8050) | Ollama (port 11434/11435) | Agent Engine (background thread)
```

### New Module: `ai/` (6 files)

| File | Class | Responsibility |
|---|---|---|
| `ai/__init__.py` | — | Package exports |
| `ai/ollama_manager.py` | `OllamaManager` | Start, stop, and health-check the Ollama process |
| `ai/automl.py` | `AutoMLManager` | FLAML wrapper: train models, generate predictions, compute diagnostics |
| `ai/tools.py` | `AgentTools` | 13 tool functions callable by the LLM agent |
| `ai/agent.py` | `AgentEngine` | Conversation loop, tool dispatch, streaming response assembly |
| `ai/callbacks_agent.py` | — | Dash callbacks: send message, poll response, tab activation greeting |

### The 13 Agent Tools

**Data tools (4)**
- `get_dataset_summary` — High-level overview of loaded data
- `get_file_details` — Metadata and stats for a single `.dat` file
- `get_feature_statistics` — Descriptive statistics for selected features
- `detect_outliers` — IQR-based outlier detection across the dataset

**ML tools (3)**
- `run_automl` — Trigger FLAML to search and select the best regression pipeline
- `predict_removal` — Run inference with the trained model on specified inputs
- `get_model_diagnostics` — Return cross-validation scores, feature importances, and residuals

**Chart tools (6)**
- `generate_scatter` — Scatter plot of two features
- `generate_distribution` — Histogram / KDE for a feature
- `generate_bar_chart` — Bar chart (e.g., removal by wafer or pad)
- `generate_correlation_heatmap` — Pearson correlation matrix heatmap
- `generate_time_series` — Time-series plot for a single file
- `generate_model_plots` — Actual vs. predicted and residual plots for the trained model

### Modified Existing Files

- **`dashboard/layouts.py`** — Predict Removal tab replaced with AI Agent tab (chat interface + chart panel)
- **`dashboard/callbacks.py`** — Prediction callback registration replaced with agent callback registration
- **`dashboard/styles.py`** — Added CSS for chat bubbles, thinking collapsibles, and the two-panel agent layout
- **`desktop/main_window.py`** — Added Ollama lifecycle management (start on app open, stop on app close)
- **`requirements.txt`** — Added `flaml[automl]>=2.5.0` and `ollama>=0.4.0`

### Removed Files

- **`dashboard/callbacks_prediction.py`** — Functionality replaced by `ai/automl.py` and `ai/callbacks_agent.py`

---

## Bugs Found and Fixed During Testing

Six bugs were identified and resolved during the testing phase.

### Bug 1 — XGBRegressor `classes_` AttributeError

**Symptom:** FLAML selected XGBoost as the best model, but metric calculation crashed with an `AttributeError` on `classes_`.

**Root cause:** FLAML's XGBoost wrapper does not expose the `classes_` attribute that scikit-learn's `cross_val_score` expects.

**Fix:** Replaced `cross_val_score` with direct `model.predict()` followed by manual `r2_score` and `mean_absolute_error` calculations.

### Bug 2 — No loading indicator

**Symptom:** The UI appeared frozen while the LLM was processing. Users saw nothing.

**Fix:** A "Thinking..." placeholder message is inserted immediately when a request is submitted, then replaced when the actual response arrives.

### Bug 3 — Wrong predictions and NaN metrics

**Symptom:** Model predictions were nonsensical and metric values showed as NaN.

**Root cause:** This was a downstream effect of Bug 1. The XGBoost CV failure produced NaN scores that propagated into prediction and display.

**Fix:** Resolved by the same fix as Bug 1.

### Bug 4 — Charts not generating

**Symptom:** Agent-generated charts returned errors instead of figures.

**Root cause:** `fig.update_layout(**DARK_LAYOUT, title="...")` passed the `title` key twice because `DARK_LAYOUT` already contains a `title` key. Plotly raised a `TypeError` for the duplicate keyword argument.

**Fix:** Split into two separate `update_layout()` calls — one to apply `DARK_LAYOUT`, one to set the title.

### Bug 5 — Thinking fragments rendering as multiple collapsibles

**Symptom:** Each 200ms poll that found thinking-mode chunks created a new `<details>` collapsible element, flooding the UI.

**Fix:** All thinking chunks are now accumulated server-side and flushed as a single collapsible `<details>` block only when the full thinking sequence is complete.

### Bug 6 — OllamaManager port mismatch

**Symptom:** The app failed to connect to Ollama even though Ollama was running correctly.

**Root cause:** The `OllamaManager` attempted to connect on port 11435 (the bundled-install port), but the system-wide Ollama instance runs on port 11434.

**Fix:** `OllamaManager` now checks port 11434 first. If a healthy Ollama instance is found there it uses that; otherwise it falls back to launching its own instance on port 11435.

### Bug 7 — OllamaManager constructor signature mismatch

**Symptom:** `on_tab_activate` callback crashed when passed `port=` as a keyword argument.

**Root cause:** The constructor signature had been changed but a call site in `desktop/main_window.py` was not updated.

**Fix:** The call site was updated to use a direct HTTP health check instead of passing the port through the constructor.

---

## Dependencies Added

| Package | Version constraint | Purpose |
|---|---|---|
| `flaml[automl]` | `>=2.5.0` | AutoML framework (pulls in LightGBM, XGBoost) |
| `ollama` | `>=0.4.0` | Ollama Python client for LLM communication |

---

## Final State

All implementation is complete. Six bugs discovered during testing were diagnosed and fixed. The Predict Removal tab has been fully replaced by the AI Agent tab. The agent:

- Automatically runs FLAML to select and train the best regression model without user involvement
- Exposes 13 tools covering data exploration, ML training, prediction, and chart generation
- Uses Qwen3.5 9B's thinking mode for complex reasoning and tool calling for structured actions
- Streams responses with a visual "Thinking..." indicator while the LLM processes
- Manages its own Ollama process lifecycle, including graceful detection of an already-running system Ollama instance
- Keeps all conversation state in memory for the duration of the session only
