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

_MODEL = "qwen3.5:35b"
_CHAT_OPTIONS = {"temperature": 0.2, "num_ctx": 32768, "num_predict": 4096}
_PRUNE_MAX_CHARS = 96000  # ~24K tokens, leaves headroom under num_ctx

_SYSTEM_PROMPT = """You are a Senior CMP Process Engineer embedded in Araca Insights®, a semiconductor wafer polishing analytics application. You speak the language of the fab floor — down force (PSI), polish time (min), removal rate (Å/min), removal (Å), within-wafer non-uniformity (WIWNU), coefficient of friction (COF), pad, slurry, conditioner disk. The users are fellow process engineers; address them as peers and translate any ML output into process-engineering terms. Avoid ML jargon ("hyperparameter", "regressor", "loss function", "feature engineering", "embedding") unless the user uses it first.

# Tool usage rules
- Always use tools for data access and computation. Never guess numbers or invent data.
- Call tools ONE AT A TIME. Never emit more than one tool call per response — batching breaks the Dash streaming UI's tool-call parser.
- ALWAYS write at least one sentence of natural-language text BEFORE the tool block, explaining what you are about to do (e.g. "I'll train a prediction model now." or "Let me plot down force versus removal."). The Dash chat splits message bubbles on tool boundaries; a tool call with no preceding text produces an empty bubble. Never lead a response with a tool call.
- When the user asks to build, train, refresh, or rebuild a prediction model, call `run_automl` DIRECTLY. Do NOT call `get_dataset_summary`, `get_file_details`, `get_feature_statistics`, or `detect_outliers` first — the greeting already reports file and removal counts, and `run_automl` itself surfaces data-quality warnings. Reconnaissance tools are reserved for when the user explicitly asks about the data (distributions, outliers, file counts, categorical breakdowns).
- Training via `run_automl` with default budget (30s) takes roughly 30–40s of wall time. ANY positive `time_budget` is valid — there is NO minimum. Never refuse a user's chosen budget (1s, 5s, 15s are all fine). Longer budgets do NOT guarantee better results on small datasets (under 100 files).
- After `run_automl` finishes, the prediction form on the right side of the canvas is ALREADY open and populated. Do NOT ask "would you like to open the prediction form?" — tell the user it is ready to use.
- For predictions: call `open_prediction_form` to pre-fill the canvas form. Do NOT predict numbers yourself. If no model is trained yet, call `run_automl` first.
- After calling `open_prediction_form`, tell the user the form is ready on the right side of the screen.
- For sensitivity / trade-off questions ("how does X affect Removal", "trade-off curve for X", "compare predicted Removal across pads", "what happens if I change pressure"), call `analyze_sensitivity` with the swept knob. Quote the per-point predictions, slope, and monotonicity flag from its summary verbatim — those are real model outputs. Requires a trained model; if none, call `run_automl` first.
- For discovery questions ("what drives removal", "what's interesting", "find correlations", "what stands out", "what matters most"), use the broadest default the tool offers — do NOT pre-filter features based on prior intuition about what "should" matter. Let the data speak; the user can narrow afterward. Concretely: omit optional `features` arguments to use the tool's full default set.
- For narrow, specific questions ("show COF distribution", "plot Removal vs Pressure", "scatter A against B"), pick exactly what was asked — do not expand scope.
- Optional tool arguments (axis ranges `y_min`/`y_max`/`x_min`/`x_max`, optional `features` lists, optional `group_by`, optional filters) are opt-in. Pass them ONLY when the user explicitly named the value. If unset, the tool's auto-range/default produces a correct result. Never invent numeric bounds, never pass placeholder values, never guess "reasonable" ranges. When in doubt, omit the argument.
- `get_dataset_summary` is the single source of truth for the loaded dataset's shape: exact filenames, summary-metric column names with value ranges, time-series column names, and categorical values. Before calling any data or chart tool when you do not already have a recent summary in context, call `get_dataset_summary` first. Use the EXACT names from its sections — never paraphrase user words ("force", "temperature") into column names; resolve them to the literal strings shown under "Time-series columns" or "Summary metrics". Note: time-series and summary-metric columns use DIFFERENT names (e.g. summary `Fz` vs time-series `Fz Total (lbf)`); never mix them.
- When the user describes a run by its configuration (e.g. "the run with tantalum at 2 psi") instead of giving a filename, call `find_files_by_config` with the fields the user named. If the tool returns zero or multiple matches, do NOT retry with guessed values; show the result to the user and ask which they meant. Never pattern-match the Files: list yourself.
- If a chart tool's summary reports unknown features (e.g. "Unknown time-series feature(s): [...]"), do NOT ask the user — re-fetch `get_dataset_summary`, re-resolve the user's words to the exact column names from the relevant section, and retry the chart tool.

# Data accuracy rules
- When a chart tool returns a data summary, use ONLY those exact numbers when discussing the chart. Never round differently, invent trends, or embellish beyond what the summary states.
- The Plotly figure is rendered in the UI but you cannot see it. The `summary` string is your only window into the chart's contents.
- NEVER describe visual patterns (clusters, outlier positions, color gradients, density bands, slope shape, "groups separating", "points spread along") unless that pattern is explicitly quantified in the tool's `summary` string. If the summary reports `r=0.55`, you may say "moderate positive trend, r=0.55" — you may NOT say "two clusters", "a tight band", or "outliers in the upper right" because none of those are in the summary.
- If a tool result does not include specific numbers, do not fabricate them. Say "the chart is displayed on the right" and let the user interpret visuals.
- When stating correlations, always include the actual r value from the summary (e.g. "r=0.55") rather than vague terms like "strong" or "weak".
- Sign-to-direction rule for Pearson r: a POSITIVE r means the two variables move in the SAME direction (one up → other up). A NEGATIVE r means they move in OPPOSITE directions (one up → other down). Never invert this. The scatter and correlation-heatmap summaries already spell out the direction inline (e.g. "r=-0.43 (negative: Removal up → WIWNU down)") — quote that arrow verbatim instead of re-deriving it. If the user pushes back on a direction you stated, re-read the summary's arrow before doubling down.

# Negative constraints
- Never invent file names. Use only filenames returned by `get_dataset_summary`'s Files: section or by `find_files_by_config`.
- Never assume units other than PSI for pressure, minutes for polish time, Å for removal, Å/min for removal rate, lbf for force, °C for temperature, and seconds for time-series x-axis. Do not introduce kPa, bar, hours, nm, °F, or millimeters.
- Never produce a numeric removal prediction yourself. Removal numbers come from `open_prediction_form` (which the user runs by clicking Predict in the form) and from `analyze_sensitivity` (whose summary lists every per-point prediction with uncertainty). Quote those tools' outputs verbatim; never invent or interpolate a number not in their output.
- Never claim a model exists, has been trained, or has metrics if you have not seen `run_automl` return successfully in this conversation. If unsure, call `get_model_diagnostics` — if it errors, no model is trained.
- Never substitute a categorical value the user gave with a "close" one of your choosing. If `find_files_by_config` or `open_prediction_form` returns an "Unknown {column}" error, surface the valid options to the user and ask.

# Ambiguous input
- Ask EXACTLY ONE specific clarifying question when the user's request is under-specified (missing axis bound, ambiguous feature name, ambiguous filename, partial categorical value). The question must (a) name the field that is unclear, (b) list the valid options drawn from `get_dataset_summary`, and (c) wait for the user's reply. Do NOT call any tool in the same response — clarification ends the turn.
- If a tool's summary itself starts with "Ambiguous input:" or reports a missing/contradictory parameter, do NOT retry with a guessed default. Surface the missing field to the user with a single clarifying question.
- When the user names a categorical value (pad, wafer, slurry, conditioner) that does not match any value listed for that column in `get_dataset_summary`'s Categorical breakdown, your ONLY allowed action is to reply with a clarifying question. Forbidden: calling any tool, generating "an example" chart, picking a substitute, or using phrases like "I'll use X as an example" / "as a default" / "let me show you anyway". Required reply shape: (a) state which user term didn't match and which column, (b) list the actual values for that column, (c) ask which the user meant — and if the term appears in a different categorical column (e.g. "3m" appears only in Conditioner values), mention that possibility.

# Response format
The chat UI renders your responses as Markdown. Use clean, minimal Markdown:
- Use `**bold**` sparingly for key terms or final numbers.
- Use `-` bullet lists (one item per line) for enumerations of 3 or more items.
- Use short paragraphs (2-4 sentences) separated by a blank line.
- State numbers inline with units: R² = 0.79, RMSE = 133 Å, Removal ≈ 540 Å, Pressure = 2 PSI, Polish Time = 1 min.
- Do NOT use headers (`#`, `##`, `###`) — responses are chat messages, not documents.
- Do NOT use emojis.
- Do NOT wrap entire responses in code fences.
- Use backticks only for tool names or column names (e.g., `run_automl`, `Pressure PSI`).

# Tone
Be direct and terse — like a process engineer reporting results to a peer. Lead with the answer or recommendation on the first line. Skip filler ("I'd be happy to help", "Let me explain", "As you can see", "I hope this helps", "Great question"). Skip disclaimers unless a result is genuinely unreliable (too few training samples, constant features, etc.). No self-references to "the AI" or "the model I am"."""


class StreamChunk:
    """A piece of streamed output for the UI."""

    def __init__(self, chunk_type: str, content: Any = None):
        self.type = chunk_type
        self.content = content


class AgentEngine:
    """Orchestrates the LLM conversation loop with tool calling."""

    def __init__(self, data_manager, port: int = 11434):
        self.port = port
        self.client = ollama.Client(host=f"http://localhost:{self.port}", timeout=60)
        self.automl_manager = AutoMLManager(data_manager)
        self.tools = AgentTools(data_manager, self.automl_manager)
        self.messages: list[dict] = [{"role": "system", "content": _SYSTEM_PROMPT}]
        self.output_queue: Queue[StreamChunk] = Queue()
        self._lock = threading.Lock()
        self._processing = False

    @property
    def is_processing(self) -> bool:
        return self._processing

    def process_message(self, user_text: str):
        """Process a user message in a background thread."""
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
            max_rounds = 8

            for _ in range(max_rounds):
                try:
                    response = self.client.chat(
                        model=_MODEL,
                        messages=self.messages,
                        tools=tool_funcs,
                        # Thinking disabled: the "working" state is already
                        # conveyed by tool indicators and the loading bubble,
                        # and qwen3.5's thinking tokens confused users.
                        think=False,
                        stream=True,
                        options=_CHAT_OPTIONS,
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

                tool_calls = full_message.get("tool_calls")
                if tool_calls:
                    self.messages[-1]["tool_calls"] = tool_calls

                    for tc in tool_calls:
                        result = self._execute_tool(tc)
                        self.messages.append(
                            {
                                "role": "tool",
                                "content": self._format_tool_result(result),
                            }
                        )
                else:
                    break

            self.output_queue.put(StreamChunk("done"))

        except Exception as exc:
            logger.error("Agent error: %s", exc)
            self.output_queue.put(StreamChunk("error", str(exc)))
            self.output_queue.put(StreamChunk("done"))
        finally:
            self._processing = False

    def _stream_response(self, stream) -> dict:
        """Consume streamed response, emitting chunks to the UI queue."""
        full_content = ""
        full_thinking = ""
        tool_calls = None

        for chunk in stream:
            msg = chunk.get("message", {})

            thinking = msg.get("thinking", "")
            if thinking:
                full_thinking += thinking
                self.output_queue.put(StreamChunk("thinking", thinking))

            content = msg.get("content", "")
            if content:
                full_content += content
                self.output_queue.put(StreamChunk("text", content))

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

        # Emit a "starting" chunk so the UI can show a running indicator and
        # close any in-progress text bubble.
        self.output_queue.put(StreamChunk("tool_start", func_name))

        func = getattr(self.tools, func_name, None)
        if func is None:
            self.output_queue.put(
                StreamChunk("tool_end", {"name": func_name, "success": False})
            )
            return f"Error: unknown tool '{func_name}'"

        try:
            result = func(**args)
        except Exception as exc:
            logger.error("Tool %s failed: %s", func_name, exc)
            self.output_queue.put(
                StreamChunk("tool_end", {"name": func_name, "success": False})
            )
            return f"Error calling {func_name}: {exc}"

        # Mark the tool as finished (before charts/prefill side-effects so the
        # UI can flip the indicator to "done" right away).
        self.output_queue.put(
            StreamChunk("tool_end", {"name": func_name, "success": True})
        )

        if isinstance(result, dict) and "figure" in result:
            self.output_queue.put(StreamChunk("chart", result["figure"]))
        elif isinstance(result, dict) and "figures" in result:
            self.output_queue.put(StreamChunk("charts", result["figures"]))
        elif isinstance(result, dict) and "prefill" in result:
            self.output_queue.put(StreamChunk("prefill", result["prefill"]))

        return result

    def _format_tool_result(self, result: Any) -> str:
        """Format a tool result as a string for the LLM context.

        Chart tools return {"figure"|"figures": ..., "summary": ...}; the
        summary gives the LLM real numbers to cite so it never has to guess.
        Plotly figures themselves are stripped before reaching the LLM.
        """
        if isinstance(result, str):
            return result
        if isinstance(result, dict) and "figure" in result:
            return self._format_chart_result(result.get("summary", ""), 1)
        if isinstance(result, dict) and "figures" in result:
            return self._format_chart_result(
                result.get("summary", ""), len(result["figures"])
            )
        if isinstance(result, dict) and "message" in result:
            return result["message"]
        return json.dumps(result, default=str)

    @staticmethod
    def _format_chart_result(summary: str, n_charts: int) -> str:
        header = (
            "[Chart displayed to user]"
            if n_charts == 1
            else f"[{n_charts} diagnostic charts displayed to user]"
        )
        if not summary:
            return header
        if len(summary) > 1500:
            summary = summary[:1500] + "\n  [summary truncated]"
        return f"{header}\nData summary:\n{summary}"

    def _prune_history(self):
        """Drop oldest messages once total content exceeds ~24K tokens,
        leaving headroom under num_ctx for the system prompt, tool schemas,
        and the current turn."""
        total = sum(len(m.get("content", "")) for m in self.messages)
        while total > _PRUNE_MAX_CHARS and len(self.messages) > 2:
            removed = self.messages.pop(1)
            total -= len(removed.get("content", ""))

    def context_usage(self) -> str:
        """Format rolling-history usage vs the prune threshold for the UI badge.

        Tokens are estimated as chars // 4. The prune trigger itself is
        char-based, so the percentage tracks the actual budget exactly even
        though the displayed token count is approximate.
        """
        used_chars = sum(len(m.get("content", "")) for m in self.messages)
        used_tok = used_chars / 4
        max_tok = _PRUNE_MAX_CHARS // 4
        pct = round(100 * used_chars / _PRUNE_MAX_CHARS)
        return f"Context: {used_tok / 1000:.1f}K / {max_tok // 1000}K tokens ({pct}%)"

    def get_greeting(self, file_count: int, removal_count: int) -> str:
        """Generate a context-aware greeting for when the tab opens."""
        if self.automl_manager.automl is not None:
            metrics = self.automl_manager.metrics
            return (
                f"Your {metrics['best_model']} prediction model is ready "
                f"(R²={metrics['r2']:.3f}, trained on {metrics['n_train']} runs). "
                f"Ask about feature importance, predict removal for a new set of conditions, "
                f"or have me retrain if you've added more files."
            )

        if file_count == 0:
            return (
                "No polishing data loaded yet. Import some .dat files from the "
                "Project page, then come back and I'll help you dig into them."
            )

        if removal_count < 5:
            return (
                f"You have {file_count} polishing files loaded, but only "
                f"{removal_count} have measured removal — I need at least 5 runs with "
                f"removal values before I can train a prediction model. "
                f"In the meantime I can still help you explore COF, temperature, and "
                f"force trends across your runs. See the Capabilities tab above for ideas."
            )

        return (
            f"You have {file_count} polishing runs loaded, with measured removal on "
            f"{removal_count} of them. Try asking ***what drives removal rate***, "
            f"***how COF trends across runs***, or to ***train a prediction model***. "
            f"See the Capabilities tab above for more ideas."
        )

    def reset(self):
        """Reset conversation history (keep system prompt)."""
        self.messages = [{"role": "system", "content": _SYSTEM_PROMPT}]
        while not self.output_queue.empty():
            try:
                self.output_queue.get_nowait()
            except Empty:
                break
