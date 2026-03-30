"""Dash callbacks for the AI Agent tab.

Handles: sending messages, polling streamed responses, tab activation,
suggestion chips, and rendering charts inline.
"""

import json
import logging
from queue import Empty

import plotly
from dash import Input, Output, State, callback_context, html, dcc, no_update

from ai.agent import AgentEngine, StreamChunk

logger = logging.getLogger(__name__)

# Module-level reference set during registration
_engine: AgentEngine | None = None


def register_agent_callbacks(app, data_manager, agent_engine: AgentEngine):
    """Register all callbacks for the AI Agent tab."""
    global _engine
    _engine = agent_engine

    # == Callback 1: Send message (from input or suggestion chips) ==========
    @app.callback(
        [Output('agent-pending-message', 'data'),
         Output('agent-input', 'value'),
         Output('agent-poll-interval', 'disabled'),
         Output('agent-processing', 'data')],
        [Input('agent-send-btn', 'n_clicks'),
         Input('agent-input', 'n_submit'),
         Input('agent-suggest-0', 'n_clicks'),
         Input('agent-suggest-1', 'n_clicks'),
         Input('agent-suggest-2', 'n_clicks'),
         Input('agent-suggest-3', 'n_clicks')],
        [State('agent-input', 'value'),
         State('agent-processing', 'data')],
        prevent_initial_call=True,
    )
    def send_message(send_clicks, submit, s0, s1, s2, s3, input_value, is_processing):
        if is_processing:
            return no_update, no_update, no_update, no_update

        ctx = callback_context
        if not ctx.triggered:
            return no_update, no_update, no_update, no_update

        trigger_id = ctx.triggered[0]['prop_id'].split('.')[0]

        suggestions = {
            'agent-suggest-0': "Build a prediction model",
            'agent-suggest-1': "Summarize my dataset",
            'agent-suggest-2': "Which files are outliers?",
            'agent-suggest-3': "Predict removal for new conditions",
        }

        if trigger_id in suggestions:
            message = suggestions[trigger_id]
        elif trigger_id in ('agent-send-btn', 'agent-input'):
            message = (input_value or "").strip()
        else:
            return no_update, no_update, no_update, no_update

        if not message:
            return no_update, no_update, no_update, no_update

        # Start processing
        _engine.process_message(message)

        return message, "", False, True  # pending_message, clear input, enable poll, processing

    # == Callback 2: Poll streamed response ==================================
    @app.callback(
        [Output('agent-chat-area', 'children'),
         Output('agent-poll-interval', 'disabled', allow_duplicate=True),
         Output('agent-processing', 'data', allow_duplicate=True),
         Output('agent-model-badge', 'children'),
         Output('agent-model-badge', 'className'),
         Output('agent-suggestions', 'style')],
        [Input('agent-poll-interval', 'n_intervals')],
        [State('agent-chat-area', 'children'),
         State('agent-pending-message', 'data'),
         State('agent-processing', 'data')],
        prevent_initial_call=True,
    )
    def poll_response(n_intervals, current_children, pending_msg, is_processing):
        if not is_processing:
            return no_update, True, no_update, no_update, no_update, no_update

        children = list(current_children) if current_children else []

        # If this is the first poll after a new message, add the user message
        if pending_msg and not any(
            _is_user_message(c, pending_msg) for c in children
        ):
            children.append(
                html.Div(pending_msg, className='agent-message user')
            )

        # Drain the output queue
        text_buffer = ""
        thinking_buffer = ""
        charts = []
        is_done = False
        error_msg = None

        while True:
            try:
                chunk = _engine.output_queue.get_nowait()
            except Empty:
                break

            if chunk.type == "text":
                text_buffer += chunk.content
            elif chunk.type == "thinking":
                thinking_buffer += chunk.content
            elif chunk.type == "chart":
                charts.append(chunk.content)
            elif chunk.type == "charts":
                charts.extend(chunk.content)
            elif chunk.type == "done":
                is_done = True
            elif chunk.type == "error":
                error_msg = chunk.content

        # Accumulate thinking into a single collapsible element
        if thinking_buffer:
            existing_thinking = _find_thinking_element(children)
            if existing_thinking is not None:
                # Append to existing thinking element
                idx, prev_thinking = existing_thinking
                children[idx] = html.Details(
                    className='agent-thinking',
                    children=[
                        html.Summary("Reasoning..."),
                        html.P(prev_thinking + thinking_buffer),
                    ],
                    **{'data-thinking': 'true'},
                )
            else:
                children.append(
                    html.Details(
                        className='agent-thinking',
                        children=[
                            html.Summary("Reasoning..."),
                            html.P(thinking_buffer),
                        ],
                        **{'data-thinking': 'true'},
                    )
                )

        # Show a loading indicator while processing and no text yet
        if not text_buffer and not is_done and not charts and not error_msg:
            # If there's no streaming assistant message yet, add a loading one
            if not children or not _is_assistant_streaming(children[-1]):
                if not any(_is_loading(c) for c in children):
                    children.append(
                        html.Div(
                            "Thinking...",
                            className='agent-message assistant',
                            **{'data-loading': 'true'},
                        )
                    )

        # Add text response
        if text_buffer:
            # Remove loading indicator if present
            children = [c for c in children if not _is_loading(c)]

            # Check if last child is an in-progress assistant message
            if children and _is_assistant_streaming(children[-1]):
                # Append to existing message
                prev_text = _extract_text(children[-1])
                children[-1] = html.Div(
                    prev_text + text_buffer,
                    className='agent-message assistant',
                    **{'data-streaming': 'true'},
                )
            else:
                children.append(
                    html.Div(
                        text_buffer,
                        className='agent-message assistant',
                        **{'data-streaming': 'true'},
                    )
                )

        # Add charts inline
        for chart_data in charts:
            children.append(
                html.Div(className='agent-chart-container', children=[
                    dcc.Graph(
                        figure=chart_data,
                        config={'displayModeBar': True, 'displaylogo': False},
                        style={'height': '380px'},
                    ),
                ])
            )

        # Handle errors
        if error_msg:
            children.append(
                html.Div(
                    f"Error: {error_msg}",
                    className='agent-message system',
                )
            )

        # Finalize
        if is_done:
            # Remove loading indicator and thinking elements
            children = [c for c in children if not _is_loading(c)]

            # Mark last assistant message as done (remove streaming flag)
            if children and _is_assistant_streaming(children[-1]):
                text = _extract_text(children[-1])
                children[-1] = html.Div(text, className='agent-message assistant')

            # Update model badge
            model_text = "No model"
            model_class = "agent-status-badge"
            if _engine.automl_manager.metrics:
                m = _engine.automl_manager.metrics
                model_text = f"{m['best_model']} (R²={m['r2']:.3f})"
                model_class = "agent-status-badge active"

            return (
                children,
                True,     # disable poll
                False,    # not processing
                model_text,
                model_class,
                {'display': 'none'},  # hide suggestions after first message
            )

        return children, no_update, no_update, no_update, no_update, no_update

    # == Callback 3: Tab activation — greeting ==============================
    @app.callback(
        [Output('agent-chat-area', 'children', allow_duplicate=True),
         Output('agent-data-badge', 'children'),
         Output('agent-ollama-badge', 'children'),
         Output('agent-ollama-badge', 'className')],
        Input('analysis-tabs', 'value'),
        State('agent-chat-area', 'children'),
        prevent_initial_call=True,
    )
    def on_tab_activate(tab_value, current_children):
        if tab_value != 'agent':
            return no_update, no_update, no_update, no_update

        # Only greet once (when chat is empty)
        if current_children:
            return no_update, no_update, no_update, no_update

        df = data_manager.get_all_data()
        file_count = len(df)
        removal_count = int((df.get('Removal', 0) > 0).sum()) if not df.empty else 0

        greeting = _engine.get_greeting(file_count, removal_count)
        children = [html.Div(greeting, className='agent-message assistant')]

        data_badge = f"{file_count} files"

        # Check Ollama health on the engine's port
        try:
            import requests
            r = requests.get(f"http://localhost:{_engine.port}/api/version", timeout=2)
            healthy = r.status_code == 200
        except Exception:
            healthy = False

        if healthy:
            ollama_text = "Connected"
            ollama_class = "agent-status-badge active"
        else:
            ollama_text = "Unavailable"
            ollama_class = "agent-status-badge"

        return children, data_badge, ollama_text, ollama_class


# ---------------------------------------------------------------------------
# Helpers for inspecting Dash component trees
# ---------------------------------------------------------------------------

def _is_user_message(component, text):
    """Check if a Dash component is a user message with the given text."""
    if not isinstance(component, dict):
        return False
    props = component.get('props', {})
    return props.get('className') == 'agent-message user' and props.get('children') == text


def _is_assistant_streaming(component):
    """Check if a component is a streaming assistant message."""
    if not isinstance(component, dict):
        return False
    props = component.get('props', {})
    return (props.get('className') == 'agent-message assistant'
            and props.get('data-streaming') == 'true')


def _extract_text(component):
    """Extract text content from a Dash HTML component."""
    if isinstance(component, dict):
        return component.get('props', {}).get('children', '')
    return ''


def _find_thinking_element(children):
    """Find the last thinking element and return (index, accumulated_text)."""
    for i in range(len(children) - 1, -1, -1):
        c = children[i]
        if isinstance(c, dict):
            props = c.get('props', {})
            if props.get('data-thinking') == 'true':
                # Extract the text from the P child
                inner = props.get('children', [])
                if isinstance(inner, list) and len(inner) >= 2:
                    p_el = inner[1]
                    if isinstance(p_el, dict):
                        text = p_el.get('props', {}).get('children', '')
                        return (i, text)
                return (i, '')
    return None


def _is_loading(component):
    """Check if a component is a loading indicator."""
    if not isinstance(component, dict):
        return False
    props = component.get('props', {})
    return props.get('data-loading') == 'true'
