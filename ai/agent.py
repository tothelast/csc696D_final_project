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

_MODEL = "qwen3.5:latest"
_CHAT_OPTIONS = {"temperature": 0.2, "num_ctx": 16384, "num_predict": 4096}

_SYSTEM_PROMPT = """You are an AI assistant embedded in Araca Insights®, a semiconductor wafer polishing analytics application. Users are polishing process engineers — domain experts in CMP, not in machine learning. Translate ML terminology into process-engineering language.

# Tool usage rules
- Always use tools for data access and computation. Never guess numbers or invent data.
- Call tools ONE AT A TIME. Never emit more than one tool call per response — batching breaks the tool-call parser.
- ALWAYS write a short sentence BEFORE calling any tool, explaining what you are about to do. For example: "I'll train a prediction model now." or "Let me generate a scatter plot of COF vs Removal." Never call a tool as the very first thing in your response — always lead with at least one sentence of text.
- For predictions: call open_prediction_form to pre-fill the canvas form. Do NOT predict numbers yourself or invent values. If no model is trained yet, call run_automl first.
- After calling open_prediction_form, tell the user the form is ready on the right side of the screen.
- When the user asks to build, train, or refresh a prediction model, call `run_automl` DIRECTLY. Do NOT call `get_dataset_summary`, `get_file_details`, or `get_feature_statistics` beforehand — the greeting already reports file counts and the training result already reports data-quality warnings. Reserve those reconnaissance tools for when the user explicitly asks about the data.
- Training via `run_automl` with default budget (30s) takes roughly 30-40 seconds of wall time. Any positive time_budget is valid — there is NO minimum. Never refuse a user's chosen budget. Longer budgets do NOT guarantee better results on small datasets (under 100 files).
- After `run_automl` finishes, the prediction form on the right side of the canvas is ALREADY open and populated. Do NOT ask "would you like to open the prediction form?" — tell the user it is ready to use.
- For discovery questions ("what drives X", "what's interesting", "find correlations", "what stands out", "what matters most"), prefer the broadest default the tool offers — do NOT pre-filter features or columns based on your prior intuition about what "should" matter. Let the data speak; the user can narrow afterward. Concretely: omit optional `features` arguments to use the tool's full default set.
- For narrow, specific questions ("show COF distribution", "plot Removal vs Pressure", "scatter A against B"), pick exactly what was asked — do not expand scope.
- When a tool argument is genuinely ambiguous (e.g., training budget, plot type), pick a reasonable default and state what you chose. For example: "I'll use the default 30-second training budget."

# Data accuracy rules
- When a chart tool returns a data summary, use ONLY those exact numbers when discussing the chart. Never round differently, invent trends, or embellish beyond what the summary states.
- If a tool result does not include specific numbers, do not fabricate them. Say "the chart is displayed on the right" and let the user interpret visuals.
- Never describe visual patterns (clusters, outlier positions, color gradients) that you cannot verify from the numerical data summary.
- When stating correlations, always include the actual r value from the summary (e.g. "r=0.55") rather than vague terms like "strong" or "weak".

# Response format
The chat UI renders your responses as Markdown. Use clean, minimal Markdown:
- Use `**bold**` sparingly for key terms or final numbers.
- Use `-` bullet lists (one item per line) for enumerations of 3 or more items.
- Use short paragraphs (2-4 sentences) separated by a blank line.
- State numbers inline with units: R² = 0.79, RMSE = 133 Å, Removal ≈ 540 Å.
- Do NOT use headers (`#`, `##`, `###`) — responses are chat messages, not documents.
- Do NOT use emojis.
- Do NOT wrap entire responses in code fences.
- Use backticks only for tool names or column names (e.g., `run_automl`, `Pressure PSI`).

# Tone
Be direct and terse. Lead with the answer or recommendation on the first line. Skip filler ("I'd be happy to help", "Let me explain", "As you can see", "I hope this helps", "Great question"). Skip disclaimers unless a result is genuinely unreliable (too few training samples, constant features, etc.). No self-references to "the AI" or "the model I am"."""


class StreamChunk:
    """A piece of streamed output for the UI."""

    def __init__(self, chunk_type: str, content: Any = None):
        self.type = chunk_type
        self.content = content


class AgentEngine:
    """Orchestrates the LLM conversation loop with tool calling."""

    def __init__(self, data_manager, port: int = 11434):
        self.port = port
        self.client = ollama.Client(
            host=f"http://localhost:{self.port}", timeout=60
        )
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
                        self.messages.append({
                            "role": "tool",
                            "content": self._format_tool_result(result),
                        })
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
            self.output_queue.put(StreamChunk(
                "tool_end", {"name": func_name, "success": False}
            ))
            return f"Error: unknown tool '{func_name}'"

        try:
            result = func(**args)
        except Exception as exc:
            logger.error("Tool %s failed: %s", func_name, exc)
            self.output_queue.put(StreamChunk(
                "tool_end", {"name": func_name, "success": False}
            ))
            return f"Error calling {func_name}: {exc}"

        # Mark the tool as finished (before charts/prefill side-effects so the
        # UI can flip the indicator to "done" right away).
        self.output_queue.put(StreamChunk(
            "tool_end", {"name": func_name, "success": True}
        ))

        if isinstance(result, dict) and "figure" in result:
            # Single chart with summary (new format from chart tools).
            self.output_queue.put(StreamChunk("chart", result["figure"]))
        elif isinstance(result, dict) and "figures" in result:
            # Multiple charts with summary (generate_model_plots).
            self.output_queue.put(StreamChunk("charts", result["figures"]))
        elif isinstance(result, dict) and "data" in result:
            # Legacy fallback: bare Plotly figure.
            self.output_queue.put(StreamChunk("chart", result))
        elif isinstance(result, list) and result and isinstance(result[0], dict):
            # Legacy fallback: list of bare Plotly figures.
            self.output_queue.put(StreamChunk("charts", result))
        elif isinstance(result, dict) and "prefill" in result:
            # open_prediction_form returns {"prefill": {...}, "message": str}.
            self.output_queue.put(StreamChunk("prefill", result["prefill"]))

        return result

    def _format_tool_result(self, result: Any) -> str:
        """Format a tool result as a string for the LLM context.

        Chart tools return {"figure": ..., "summary": ...}.  The summary
        gives the LLM real numbers to cite so it never has to guess.
        """
        if isinstance(result, str):
            return result
        if isinstance(result, dict) and "figure" in result:
            summary = result.get("summary", "")
            if summary:
                if len(summary) > 1500:
                    summary = summary[:1500] + "\n  [summary truncated]"
                return f"[Chart displayed to user]\nData summary:\n{summary}"
            return "[Chart displayed to user]"
        if isinstance(result, dict) and "figures" in result:
            n = len(result["figures"])
            summary = result.get("summary", "")
            if summary:
                if len(summary) > 1500:
                    summary = summary[:1500] + "\n  [summary truncated]"
                return f"[{n} diagnostic charts displayed to user]\nData summary:\n{summary}"
            return f"[{n} diagnostic charts displayed to user]"
        # Legacy fallback for bare Plotly figures.
        if isinstance(result, dict) and "data" in result:
            return "[Chart displayed to user]"
        if isinstance(result, list) and result and isinstance(result[0], dict):
            return f"[{len(result)} diagnostic charts displayed to user]"
        if isinstance(result, dict) and "message" in result:
            return result["message"]
        return json.dumps(result, default=str)

    def _prune_history(self):
        """Keep conversation history under ~12K tokens by removing old messages."""
        max_chars = 48000
        total = sum(len(m.get("content", "")) for m in self.messages)
        while total > max_chars and len(self.messages) > 2:
            removed = self.messages.pop(1)
            total -= len(removed.get("content", ""))

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
