# Future Work — Araca Insights AI Agent

Recommendations for evolving the AI Agent tab, written from a senior agentic-AI + CMP chemical-engineering perspective. Constraints: **offline-first** (target users may run on locked-down workstations) and **the current system works well** — adopt change only for genuinely new capability, not modernisation.

A companion landscape reference for general agentic-LLM design lives at `~/.claude/docs/agentic-llm-2026-cheatsheet.md`.

## Where the current agent stands

The implementation in `ai/` makes correct choices on most agentic-AI axes:

| Axis | Choice | Verdict |
|---|---|---|
| Loop paradigm | ReAct (max 8 turns, history pruned at 48 K chars) | Right call for open-ended analyst questions |
| Action format | JSON tool-calling via Ollama native function calling | Correct for 13 tools and a 7B–14B-class model |
| Tool result design | `{figure, summary}` dual channel | Better than most reference implementations |
| Runtime | Local Ollama with bundled fallback binary | Best fit for offline desktop |
| Memory | Sliding window | Acceptable for single-session use |
| Multi-agent | Single agent | Correct for one domain and 13 tools |
| Tabular ML | FLAML over 9 estimators + permutation importance + per-prediction uncertainty | Best-in-class; no HF equivalent |
| Framework | Roll-your-own ~300 LOC | Defensible — abstraction tax avoided |

The agentic-AI side is solid. The interesting gaps are domain-specific: a CMP engineer would want capabilities the agent simply doesn't have today.

---

## Tier 1 — high leverage, ship first

### 1. Preston-equation fit tool
The agent currently reasons about removal rate purely correlationally via FLAML feature importance. Every CMP engineer reaches first for *MRR = K · P · V* (Preston, 1927). Add:

```
fit_preston_coefficient(filter: dict | None) -> {
    K_preston, K_ci_95, n_wafers,
    residual_rms, fit_quality_label,
    deviation_from_preston: list[{wafer, observed, predicted, residual_pct}]
}
```

Restrict to a subset where slurry, pad, and conditioner are held constant. The `Sample_Full_Data/` set already has `Slurry='CU4545F-300'` constant, so this is straightforward.

**Why it matters**: lets the agent answer *"is this process Preston-linear?"* — the question a real CMP engineer asks first. FLAML stays as a screening tool; Preston gives the interpretable physics-grounded baseline that feature importance can't match.

**Files**: new `ai/preston.py`; register in `ai/tools.py:865`; system-prompt hint in `ai/agent.py:19-50`.

### 2. Local RAG over CMP literature + vendor docs
Embed Preston / Luo-Dornfeld / chemical-mechanical interaction papers, slurry vendor datasheets (CU4545F-300 has published spec sheets), pad and conditioner manuals, internal SOPs. `BAAI/bge-small-en-v1.5` (~80 MB, offline) into FAISS. Expose as a `query_knowledge_base` tool the agent calls when a question is knowledge-domain rather than data-domain.

**Why it matters**: the single biggest *new capability* — agent can cite written physics and chemistry instead of pattern-matching from training data. Converts answers like "high COF correlates with low removal" into "high COF correlates with low removal, consistent with Luo-Dornfeld's mixed-mode lubrication regime (cite)."

**Files**: new `ai/rag.py` (embedding + index); new `knowledge/` corpus dir; tool registration in `ai/tools.py:865`.

### 3. Process-engineering safety bounds on prediction outputs
Today `open_prediction_form` and the FLAML model can recommend any pressure / time the optimiser lands on, including values outside the safe operating envelope (over-polish, pattern collapse, sub-pad damage). Add hard configurable bounds (e.g. `P_max = 6 psi`, `t_max = 180 s`, plus minimum bounds) and have the prediction tool refuse-with-explanation when its recommendation falls outside them.

**Why it matters**: the kind of guardrail a senior process engineer puts in *before* the tool is used in anger. Prevents an agent recommendation from being a liability.

**Files**: `dashboard/callbacks_prediction.py`, `ai/automl.py` (predict path), config in project settings.

### 4. Configurable model name
Hardcoded `qwen3.5:latest` lives in `ai/agent.py:16` and `ai/ollama_manager.py:17`. Move to a settings entry (`~/.araca/config.yaml` or co-located with existing project settings). Document a curated list of tested alternatives Ollama can pull (Qwen 3.6 family, Gemma 4, gpt-oss-20b, Qwen 3 Coder).

**Why it matters**: hygiene fix that lets users trial stronger models as they appear, and enables A/B testing the same prompts against different backends.

**Files**: `ai/agent.py:16`, `ai/ollama_manager.py:17`, new local config reader.

---

## Tier 2 — worth experimenting with

### 5. Within-wafer non-uniformity (NU) as a first-class output
The codebase has `nu` and `Var Fz` already. NU is *the* second-order CMP metric — uniformity is what determines yield. Add `analyze_uniformity(filter)` returning within-wafer NU statistics, edge-vs-centre distinctions, and correlations of NU with controllable parameters.

**Why it matters**: today the agent has to compose NU analysis from generic stats tools; promoting it to a first-class tool surfaces the metric the user actually cares about for yield.

**Files**: new tool in `ai/tools.py`; consider whether `dashboard/callbacks_compare.py` should expose the same logic in the UI.

### 6. Run-to-run drift / temporal awareness
CMP has pad-wear drift, slurry-lot effects, conditioner aging. Treating wafers as i.i.d. is a real source of misleading conclusions. Add `temporal_drift_check(feature)` that fits a trend over wafer order and reports slope plus significance. Update the system prompt so the agent knows to call this before interpreting any correlation as causal.

**Why it matters**: an agent that ignores temporal confounding will confidently mis-attribute drift to controllable parameters. This is the kind of mistake that erodes trust with experienced process engineers.

**Files**: new tool in `ai/tools.py`; system-prompt addition in `ai/agent.py:19-50`.

### 7. `smolagents.CodeAgent` mode behind a toggle, paired with a coder-tuned local model
When an analyst asks "show me how COF correlates with downforce gradient over time within each conditioner generation," that needs a 3+ tool dance today. A code agent with `pandas` + `plotly` + the existing tools as a Python-callable module could handle it in one turn.

**Caveat**: Qwen 3.5 is not a coder model. Only enable code mode with a coder-tuned local backend (e.g. Qwen 3 Coder 7B via Ollama). Sandbox via `smolagents.LocalPythonExecutor` with import allow-list (`pandas`, `numpy`, `plotly`, `tools.*`). Default to "standard" so nothing regresses.

**Validation**: fixed basket of 5–10 representative questions; record step count, total tokens, final-output correctness, latency. Promote to default only if code mode wins on step count *and* ties-or-better on correctness.

**Files**: alternate loop in `ai/agent.py`; new `smolagents` dependency; toggle in `ai/callbacks_agent.py`.

### 8. Structured output for prediction recommendations
When the agent recommends a process condition, return:

```
{
  recommended_pressure_psi, recommended_polish_time_s,
  expected_removal, uncertainty_pct,
  basis_in_text, within_safety_bounds: bool,
  confidence_label: "high" | "medium" | "low"
}
```

instead of free-text Markdown. Easy via function-calling coercion (`tool_choice: required` on a single fake tool); no runtime change needed. If the project ever migrates to vLLM/SGLang, switch to grammar-constrained `guided_json` for 100 % schema conformance.

**Why it matters**: makes recommendations loggable, A/B-testable, and consumable by downstream tools (e.g. an export-to-recipe-file feature).

**Files**: `ai/agent.py` (response shaping), new schema in `ai/tools.py`.

---

## Tier 3 — nice-to-have

### 9. Conversation persistence across sessions
Single line of advice for an analyst tool used over weeks. Pickle conversation history to disk per project, or use Mem0 for cross-session preference recall. Lets users ask "remind me what we concluded last Tuesday."

**Files**: extend `core/report.py` save/load to include agent transcripts, or sidecar JSON.

### 10. Eval harness with golden trajectories
Fixed basket of ~20 representative questions with expected behaviour. Replay on every model swap or prompt change. Without this, you can't tell when "small tweak" regresses anything.

**Files**: new `tests/agent_evals/` with replay runner; document golden questions in markdown.

### 11. Outlier explanations, not just detection
Today `detect_outliers` flags statistical outliers. A CMP engineer wants to know *why*: slurry-batch boundary, conditioner replacement, pad break-in period. Cross-reference outliers against temporal markers and cohort variables in the dataset.

**Files**: extend `detect_outliers` in `ai/tools.py`.

### 12. Cohort variance decomposition (slurry-batch, conditioner-generation)
ANOVA-style tool to estimate variance contribution from `Conditioner` and any other categorical cohort variables. Helps separate process noise from cohort effects. Two `Conditioner` levels in `Sample_Full_Data/` is enough to demonstrate the pattern.

**Files**: new tool in `ai/tools.py`.

---

## Tier 4 — would not do

- **Multi-agent (managed agents, orchestrator-workers).** No payoff at 13 tools, one domain, one user. Re-evaluate at 25+ heterogeneous tools.
- **Migrate to LangGraph / CrewAI / AutoGen / OpenAI Agents SDK.** Pure abstraction tax for this scope; you already own the agent loop in ~300 LOC.
- **HF Inference Providers as primary path.** Disqualified by offline constraint.
- **Vision models for wafer images.** Solving a problem you don't have. Revisit if SEM / AFM / optical-scan inputs become a real workflow.
- **`transformers` runtime.** Strictly worse than Ollama for desktop deployment.
- **Replace FLAML.** Strict regression on tabular CMP data.
- **MCP server adoption today.** Worth watching; only adopt if a CMP vendor publishes an MCP server (instrument metrology APIs, LIMS systems) or if you want Claude Desktop / ChatGPT to consume Araca's tools externally.

---

## What to ship first

If a single PR: **Preston-fit tool (Tier 1.1) + local RAG over CMP literature (Tier 1.2)**. Together they convert the agent from *"describes what's in your data"* to *"explains your data through CMP physics with cited references."* That's the qualitative jump an experienced CMP engineer notices immediately. The other items are improvements; those two are a capability-ceiling raise.

Tier 1.3 (safety bounds) and 1.4 (configurable model) are small enough to bundle with whichever Tier 1 PR ships first.

---

## Verification plan

Each item below is independent. Run after implementation; confirm before promoting.

### Tier 1.1 — Preston tool
- Load `Sample_Full_Data/` (per `CLAUDE.md` snippet); call `fit_preston_coefficient()` with no filter.
- Verify K is in physically plausible range for Cu CMP (~ 10⁻¹⁴–10⁻¹³ m²/N order of magnitude in SI; convert to dataset units).
- Verify the tool refuses gracefully when the filter selects too few wafers.
- Ask the agent "is this process Preston-linear?" and confirm it calls the tool and interprets the residuals.

### Tier 1.2 — Local RAG
- Index a 5–10-document fixture corpus at app start.
- Ask a question whose answer is *only* in the corpus; verify the response cites the retrieved chunk.
- Remove the corpus; verify graceful degradation (tool returns "no corpus available", agent falls back).
- Smoke-test the rest of the dashboard with `Sample_Full_Data/`.

### Tier 1.3 — Safety bounds
- Configure aggressive bounds (e.g. `P_max = 4 psi`); ask the agent to recommend a process; confirm it refuses recommendations outside bounds with a clear explanation.
- Restore default bounds; confirm normal recommendations work.

### Tier 1.4 — Configurable model
- Run with default Qwen 3.5; confirm no behaviour change.
- Edit config to another Ollama-resident model; restart; confirm load and response.
- Check `/tmp/araca.log` for `Calling tool` traces (per `CLAUDE.md`'s log observability pattern) to confirm tool calls still parse.

### Tier 2.7 — CodeAgent toggle (when attempted)
- Verify `LocalPythonExecutor` blocks shell-out, file writes outside tmp, and network calls.
- Run the fixed basket of 5–10 questions in both modes; tabulate step count and correctness.
- Promote only on a majority win.

---

## Critical files reference

| Concern | File(s) |
|---|---|
| Agent loop / model name / system prompt | `ai/agent.py` (model at line 16, system prompt 19-50, loop ~103, history pruning ~262) |
| Tool definitions and registration | `ai/tools.py` (registration at `get_all_tools()` ~line 865) |
| AutoML pipeline | `ai/automl.py` |
| Ollama lifecycle / model name | `ai/ollama_manager.py` (line 17) |
| Dash UI integration | `ai/callbacks_agent.py` |
| Prediction tab | `dashboard/callbacks_prediction.py` |
| Feature lists (analysis vs correlation) | `dashboard/constants.py` |
| Theming | `desktop/theme.py`, `dashboard/styles.py`, `dashboard/plotly_theme.py` |
| DataManager singleton bridge | `dashboard/dash_bridge.py` |
| Test fixture | `Sample_Full_Data/` |
