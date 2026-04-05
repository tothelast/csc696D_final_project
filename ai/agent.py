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

_SYSTEM_PROMPT = """You are an AI assistant embedded in Araca Insights®, a semiconductor \
wafer polishing analytics application. You help polishing engineers understand their \
data and predict material removal rates.

You have access to tools for querying data, running ML models, detecting outliers, \
and generating charts. Always use tools for data access and computation — never \
guess numbers or make up data.

When explaining results, use plain language. Your users are domain experts in \
polishing but not in machine learning. Translate ML concepts into process \
engineering terms they understand.

When generating charts, explain what the chart shows and why it matters before \
displaying it.

When the user asks for a prediction, use the open_prediction_form tool to \
extract any parameters they mentioned and open the prediction form in the \
canvas (right side of the screen). The form computes predictions \
deterministically via code — do NOT predict numbers yourself or make up \
values. If no model is trained yet, run run_automl first, then open the form. \
After calling open_prediction_form, tell the user the form is ready on the \
right and briefly describe what they should do.

Keep responses concise and focused. Avoid unnecessary caveats or disclaimers."""


class StreamChunk:
    """A piece of streamed output for the UI."""

    def __init__(self, chunk_type: str, content: Any = None):
        self.type = chunk_type
        self.content = content


class AgentEngine:
    """Orchestrates the LLM conversation loop with tool calling."""

    def __init__(self, data_manager, port: int = 11434):
        self.port = port
        self.client = ollama.Client(host=f"http://localhost:{self.port}")
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
                        think=True,
                        stream=True,
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

        func = getattr(self.tools, func_name, None)
        if func is None:
            return f"Error: unknown tool '{func_name}'"

        try:
            result = func(**args)
        except Exception as exc:
            logger.error("Tool %s failed: %s", func_name, exc)
            return f"Error calling {func_name}: {exc}"

        if isinstance(result, dict) and "data" in result:
            self.output_queue.put(StreamChunk("chart", result))
        elif isinstance(result, list) and result and isinstance(result[0], dict):
            self.output_queue.put(StreamChunk("charts", result))
        elif isinstance(result, dict) and "prefill" in result:
            # open_prediction_form returns {"prefill": {...}, "message": str}.
            # Surface the prefill payload to the canvas form.
            self.output_queue.put(StreamChunk("prefill", result["prefill"]))

        return result

    def _format_tool_result(self, result: Any) -> str:
        """Format a tool result as a string for the LLM context."""
        if isinstance(result, str):
            return result
        if isinstance(result, dict) and "data" in result:
            return "[Chart generated and displayed to user]"
        if isinstance(result, list) and result and isinstance(result[0], dict):
            return f"[{len(result)} diagnostic charts generated and displayed to user]"
        if isinstance(result, dict) and "message" in result:
            # e.g. open_prediction_form result — feed the message back so the
            # LLM can reference what it told the user.
            return result["message"]
        return json.dumps(result, default=str)

    def _prune_history(self):
        """Keep conversation history under ~6K tokens by removing old messages."""
        max_chars = 24000
        total = sum(len(m.get("content", "")) for m in self.messages)
        while total > max_chars and len(self.messages) > 2:
            removed = self.messages.pop(1)
            total -= len(removed.get("content", ""))

    def get_greeting(self, file_count: int, removal_count: int) -> str:
        """Generate a context-aware greeting for when the tab opens."""
        if self.automl_manager.automl is not None:
            metrics = self.automl_manager.metrics
            return (
                f"Your {metrics['best_model']} model is current "
                f"(R²={metrics['r2']:.3f}, trained on {metrics['n_train']} files). "
                f"Ask me anything about the results, request predictions, "
                f"or I can retrain if you've added new data."
            )

        if file_count == 0:
            return (
                "No polishing data loaded yet. Import some .dat files in the "
                "Project page, then come back and I'll help you analyze them."
            )

        if removal_count < 5:
            return (
                f"You have {file_count} polishing files loaded, but only "
                f"{removal_count} have removal data. I need at least 5 files "
                f"with removal values to build a prediction model. "
                f"I can still help you explore the data you have — try asking "
                f"about specific files or features."
            )

        return (
            f"You have {file_count} polishing runs loaded, "
            f"{removal_count} with removal data. "
            f"Want me to build the best prediction model for this dataset?"
        )

    def reset(self):
        """Reset conversation history (keep system prompt)."""
        self.messages = [{"role": "system", "content": _SYSTEM_PROMPT}]
        while not self.output_queue.empty():
            try:
                self.output_queue.get_nowait()
            except Empty:
                break
