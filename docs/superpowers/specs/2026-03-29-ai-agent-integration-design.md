# AI Agent Integration — Design Spec

**Date:** 2026-03-29
**Status:** Approved

## Overview

Integrate a local AI agent into Araca Insights® that acts as an automated ML engineer and data analyst. The agent replaces the existing Predict Removal tab with a conversational interface that automatically builds ML models using AutoML, explains results in plain English, answers questions about data, and generates ad-hoc charts — all running fully offline.

## Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| AutoML framework | **FLAML** (Microsoft) | Lightest dependencies, designed for small datasets, cost-efficient search, scikit-learn compatible. Actively maintained (v2.5.0, Jan 2026). |
| LLM | **Qwen3 8B** via Ollama | Supports both tool calling and thinking mode in Ollama. 5.2 GB model, 16 GB RAM required. 8-12 tok/s on CPU. |
| Python integration | **ollama-python** (direct) | LangChain adds unnecessary complexity for a single-provider setup. Direct library supports tools, thinking, streaming, structured output. |
| UI placement | **Dash tab** replacing Predict Removal | Stays in the web layer. Plotly charts render natively. No PyQt6 widget work needed. |
| Agent autonomy | **Fully automatic** | Agent proactively runs FLAML when data is loaded. Users don't choose models or parameters. |
| Memory | **Session-only** | Fresh context per session. No cross-project persistence. Avoids data governance issues. |
| Deployment | **Bundled installer** | Ollama binary + Qwen3 8B model shipped with the app. Fully offline. ~6 GB total. |
| Ollama lifecycle | **App-managed** | App always spawns/kills its own Ollama process on port 11435. Graceful degradation on failure. |

## Architecture

### System Overview

```
┌─────────────────────────────────────────────┐
│              Dash Dashboard                  │
│                                              │
│  ┌─────────┬─────────┬──────────┬─────────┐ │
│  │ Analyze │ Compare │ Correlat.│ AI Agent│ │
│  │  File   │  Files  │          │  (new)  │ │
│  └─────────┴─────────┴──────────┴─────────┘ │
└─────────────────────────────────────────────┘

Backend services:
┌──────────────┐  ┌──────────────┐  ┌──────────────────┐
│ Dash server  │  │   Ollama     │  │  Agent Engine     │
│ (port 8050)  │  │ (port 11435) │  │  (QThread)        │
│ existing     │  │ bundled      │  │  LLM ↔ Tools ↔ UI │
└──────────────┘  └──────────────┘  └──────────────────┘
```

### Data Access

The agent accesses data through the existing `DataManager` singleton — the same bridge pattern used by all other Dash tabs:

```
Existing code (unchanged)          Agent tools (thin wrappers)
─────────────────────────          ─────────────────────────────
DataManager.get_all_data()    ←──  get_dataset_summary()
DataManager.get_file_data()   ←──  get_file_details()
DataManager.report            ←──  accessed by all tools
_prepare_data()               ←──  run_automl() calls internally
plotly_theme.DARK_LAYOUT      ←──  chart tools reuse for styling
```

## New Module: `ai/`

```
ai/
├── __init__.py
├── ollama_manager.py    # Ollama process lifecycle (start/stop/health)
├── agent.py             # AgentEngine class — conversation loop + streaming
├── tools.py             # Data + ML tool definitions (thin wrappers)
├── charts.py            # Chart generation tools (Plotly figure builders)
├── automl.py            # FLAML wrapper (run, predict, diagnostics)
└── callbacks_agent.py   # Dash callbacks for the AI Agent tab
```

## Ollama Lifecycle

### Startup Sequence

1. `main.py` launches PyQt6 app
2. App spawns bundled Ollama binary as subprocess on port 11435
3. Sets `OLLAMA_MODELS` env var to bundled models directory
4. Polls health endpoint (`localhost:11435/api/version`), timeout 30s
5. Verifies Qwen3 8B model is available
6. App continues — Ollama ready in background

### Shutdown

App always kills the Ollama subprocess on exit.

### Graceful Degradation

If Ollama fails to start or model is unavailable:
- AI Agent tab displays: "AI assistant unavailable. Check that your system has at least 16 GB RAM."
- Other three tabs (Analyze File, Compare Files, Key Correlations) work normally
- If inference hangs (>120s), timeout with error, user can retry

## Agent Conversation Loop

```python
class AgentEngine:
    def __init__(self, data_manager, port=11435):
        self.client = ollama.Client(host=f"localhost:{port}")
        self.messages = []          # Conversation history
        self.tools = [...]          # All 13 tool functions
        self.model_state = None     # FLAML results once trained
        self.buffer = Queue()       # Streaming output to UI

    def process_message(self, user_text):
        self.messages.append({"role": "user", "content": user_text})

        while True:
            response = self.client.chat(
                model="qwen3:8b",
                messages=self.messages,
                tools=self.tools,
                think=True,
                stream=True,
            )
            full_response = self._stream_to_buffer(response)
            self.messages.append(full_response.message)

            if full_response.message.tool_calls:
                for tc in full_response.message.tool_calls:
                    result = self._execute_tool(tc)
                    self.messages.append({
                        "role": "tool",
                        "content": str(result)
                    })
                # Loop — LLM sees results, may call more tools or respond
            else:
                break  # Final answer delivered
```

### System Prompt

```
You are an AI assistant embedded in Araca Insights®, a semiconductor
wafer polishing analytics application. You help polishing engineers
understand their data and predict material removal rates.

You have access to tools for querying data, running ML models,
detecting outliers, and generating charts. Always use tools for
data access and computation — never guess numbers.

When explaining results, use plain language. Your users are domain
experts in polishing but not in machine learning. Translate ML
concepts into process engineering terms.

When generating charts, explain what the chart shows and why it
matters before displaying it.
```

### Context Management

- System prompt + tool definitions: ~2K tokens
- Conversation history kept in memory (session-only)
- Prune oldest non-system messages beyond ~6K tokens
- Tools return summarized stats, not raw DataFrames

### Thinking Mode

- `think=True` for analytical questions ("why is this an outlier?")
- `think=False` for simple requests ("predict removal for...")
- Heuristic in `process_message` classifies intent

## Proactive Agent Behavior

### On Tab Open (data loaded, no model):
> "You have 23 polishing runs loaded. I see 3 wafer types, 2 pad types, and 2 slurry types. Removal data is available for 19 of 23 files. Want me to build the best prediction model for this dataset?"

### On Tab Open (model trained):
> "Your LightGBM model is current (R²=0.91, trained on 19 files). Ask me anything about the results, request predictions, or I can retrain if you've added new data."

### On Data Change (files added after training):
> "I notice 3 new files were added since the model was trained. The model may be stale. Want me to retrain?"

### Automatic FLAML Flow:
1. Agent calls `run_automl()` — FLAML searches for ~60 seconds
2. Receives leaderboard, best model, metrics, feature importances
3. Explains results conversationally with inline charts

## Tool Definitions (13 total)

### Data Tools (4) — wrappers around DataManager

| Tool | Args | Returns |
|------|------|---------|
| `get_dataset_summary()` | none | File count, removal availability, feature ranges, categorical counts |
| `get_file_details(filename)` | filename: str | Summary metrics, categorical attributes for one file |
| `get_feature_statistics(feature, group_by?)` | feature: str, group_by: str (optional) | Mean, std, min, max, median — optionally per group |
| `detect_outliers(feature)` | feature: str | Outlier files with values and IQR deviation |

### ML Tools (3) — wrappers around `ai/automl.py`

| Tool | Args | Returns |
|------|------|---------|
| `run_automl(time_budget?)` | time_budget: int (default 60) | Best model, top-5 leaderboard, CV metrics, feature importances |
| `predict_removal(pressure_psi, polish_time, wafer, pad, slurry, conditioner)` | 6 required args | Prediction (Å), uncertainty, model info |
| `get_model_diagnostics()` | none | Residual stats, fold scores, data quality warnings, hyperparams |

### Chart Tools (6) — Plotly figure builders using DataManager data

| Tool | Args | Returns |
|------|------|---------|
| `generate_scatter(x, y, color_by?, filter_column?, filter_value?)` | 2 required, 3 optional | Plotly figure JSON |
| `generate_distribution(feature, group_by?)` | 1 required, 1 optional | Plotly figure JSON |
| `generate_bar_chart(feature, group_by)` | 2 required | Plotly figure JSON |
| `generate_correlation_heatmap(features?)` | optional list | Plotly figure JSON |
| `generate_time_series(filename, features)` | 2 required | Plotly figure JSON |
| `generate_model_plots()` | none | List of 4 Plotly figures |

All 13 tools compute deterministically. The LLM decides when and with what arguments to call them, then explains the results.

## AI Agent Tab UI

### Layout

```
┌────────────────────────────────────────────┐
│  Status bar                                │
│  [Model: LightGBM R²=0.91] [19 files] [●] │
├────────────────────────────────────────────┤
│  Chat area (scrollable)                    │
│                                            │
│  Agent: "Trained 23 pipelines in 47s..."   │
│                                            │
│  User: "Why is wafer 3 an outlier?"        │
│                                            │
│  Agent: "Wafer 3 has removal 2847Å..."     │
│         [interactive Plotly chart]          │
│                                            │
├────────────────────────────────────────────┤
│  [Text input________________________] [>>] │
│                                            │
│  Suggested: [Build model] [Summarize data] │
│             [Find outliers] [Predict]      │
└────────────────────────────────────────────┘
```

### Rendering

- Messages: styled Dash HTML components (markdown rendered)
- Charts: `dcc.Graph` components inline — fully interactive (zoom, hover, pan)
- Metric cards: styled badges for R², RMSE, etc.
- Thinking: collapsible "reasoning" section
- Auto-scroll to bottom on new messages

### Streaming Pattern (Dash callback-driven)

1. User sends message → callback writes to message queue
2. Agent thread processes message, streams tokens to shared buffer
3. `dcc.Interval` (200ms) polls buffer, updates chat display
4. Interval stops when agent finishes

### Empty State

Suggested prompt chips when chat is empty:
- "Build a prediction model"
- "Summarize my dataset"
- "Which files are outliers?"
- "Predict removal for new conditions"

## Files Modified in Existing Codebase

| File | Change |
|------|--------|
| `dashboard/layouts.py` | Add AI Agent tab, remove Predict Removal tab |
| `dashboard/callbacks.py` | Register agent callbacks, remove prediction callback registration |
| `desktop/main_window.py` | Add Ollama startup/shutdown to app lifecycle |
| `requirements.txt` | Add `flaml[automl]`, `ollama` |

## Files Removed

| File | Reason |
|------|--------|
| `dashboard/callbacks_prediction.py` | Replaced by `ai/automl.py` + `ai/callbacks_agent.py` |

## Files Untouched

- `core/` — no changes
- `dashboard/callbacks_single.py`, `callbacks_compare.py`, `callbacks_correlations.py` — no changes
- `dashboard/dash_bridge.py` — no changes (agent reads from DataManager like other tabs)
- `dashboard/constants.py` — no changes (agent tools reference existing constants)
- `desktop/project_page.py`, `analysis_page.py`, `file_details_panel.py` — no changes

## Installer & Bundling

### Bundle Structure

```
araca-insights-installer/
├── install.sh / install.bat
├── app/
│   ├── main.py
│   ├── core/
│   ├── desktop/
│   ├── dashboard/
│   ├── ai/
│   └── requirements.txt
├── ollama/
│   ├── linux/ollama              # ~150 MB
│   └── windows/ollama.exe
└── models/
    └── qwen3-8b-q4_K_M.gguf     # ~5.2 GB
```

### Install Process

1. Copy app files to target directory
2. Copy Ollama binary to `app/ollama/`
3. Import model into Ollama's local storage
4. Install Python dependencies (`pip install -r requirements.txt`)
5. Create desktop shortcut / launcher

### Runtime

- `ollama_manager.py` sets `OLLAMA_MODELS` to bundled models directory
- Ollama runs on port 11435 (avoids conflict with user-installed Ollama)
- Total bundle size: ~6 GB

## Dependencies Added

```
flaml[automl]    # FLAML + lightgbm + xgboost
ollama           # Python client for Ollama API
```

Optional: `catboost` for additional model coverage in FLAML.
