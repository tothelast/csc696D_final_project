"""Dash callbacks for the AI Agent tab.

Handles: sending messages, polling streamed responses, tab activation,
suggestion chips, and rendering charts inline.
"""

import json
import logging
from queue import Empty

import plotly
from dash import ALL, Input, Output, State, callback_context, html, no_update

from ai.agent import AgentEngine, StreamChunk
from dashboard.constants import (
    PREDICTION_CATEGORICAL_FEATURES,
    PREDICTION_NUMERICAL_FEATURES,
)


def _feature_id(feature: str) -> str:
    """Mirror of dashboard.layouts._feature_id_suffix for agent-pred-* IDs."""
    return 'agent-pred-' + feature.replace(' PSI', '').lower().replace(' ', '-')

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
         Output('agent-suggestions', 'style'),
         Output('agent-chart-history', 'data', allow_duplicate=True),
         Output('agent-chart-index', 'data', allow_duplicate=True),
         Output('agent-automl-trained', 'data', allow_duplicate=True),
         Output('agent-pred-prefill', 'data', allow_duplicate=True)],
        [Input('agent-poll-interval', 'n_intervals')],
        [State('agent-chat-area', 'children'),
         State('agent-pending-message', 'data'),
         State('agent-processing', 'data'),
         State('agent-chart-history', 'data'),
         State('agent-chart-index', 'data')],
        prevent_initial_call=True,
    )
    def poll_response(n_intervals, current_children, pending_msg, is_processing,
                       chart_history, chart_index):
        if not is_processing:
            return (no_update, True, no_update, no_update, no_update, no_update,
                    no_update, no_update, no_update, no_update)

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
        prefill_payload = None
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
            elif chunk.type == "prefill":
                prefill_payload = chunk.content
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

        # Route charts to the canvas history store; reference them in chat
        history_out = no_update
        index_out = no_update
        if charts:
            history = list(chart_history) if chart_history else []
            for chart_data in charts:
                history.append(chart_data)
                children.append(
                    html.Div(
                        f"[Chart {len(history)} generated \u2192]",
                        className='agent-message system',
                    )
                )
            history_out = history
            index_out = len(history) - 1  # jump to newest

        # Handle errors
        if error_msg:
            children.append(
                html.Div(
                    f"Error: {error_msg}",
                    className='agent-message system',
                )
            )

        # Flip the trained flag whenever AutoMLManager has a fitted model; the
        # form-reveal callback watches this store.
        trained_out = bool(_engine.automl_manager.automl is not None)
        prefill_out = prefill_payload if prefill_payload is not None else no_update

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
                history_out,
                index_out,
                trained_out,
                prefill_out,
            )

        return (children, no_update, no_update, no_update, no_update, no_update,
                history_out, index_out, trained_out, prefill_out)

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

    # == Callback 4: Canvas navigation (prev / next) ========================
    @app.callback(
        Output('agent-chart-index', 'data', allow_duplicate=True),
        [Input('agent-canvas-prev', 'n_clicks'),
         Input('agent-canvas-next', 'n_clicks')],
        [State('agent-chart-index', 'data'),
         State('agent-chart-history', 'data')],
        prevent_initial_call=True,
    )
    def navigate_canvas(prev_clicks, next_clicks, index, history):
        ctx = callback_context
        if not ctx.triggered or not history:
            return no_update

        trigger_id = ctx.triggered[0]['prop_id'].split('.')[0]
        idx = index if index is not None else -1

        if trigger_id == 'agent-canvas-prev':
            return max(0, idx - 1)
        if trigger_id == 'agent-canvas-next':
            return min(len(history) - 1, idx + 1)
        return no_update

    # == Callback 5: Canvas render ==========================================
    @app.callback(
        [Output('agent-canvas-graph', 'figure'),
         Output('agent-canvas-graph', 'style'),
         Output('agent-canvas-empty', 'style'),
         Output('agent-canvas-counter', 'children'),
         Output('agent-canvas-prev', 'disabled'),
         Output('agent-canvas-next', 'disabled')],
        [Input('agent-chart-history', 'data'),
         Input('agent-chart-index', 'data')],
        prevent_initial_call=False,
    )
    def render_canvas(history, index):
        history = history or []
        total = len(history)

        graph_visible = {'height': '100%', 'width': '100%', 'display': 'block'}
        graph_hidden = {'height': '100%', 'width': '100%', 'display': 'none'}
        empty_visible = {}  # use CSS defaults
        empty_hidden = {'display': 'none'}

        if total == 0:
            return (
                {'data': [], 'layout': {}},
                graph_hidden,
                empty_visible,
                "0 / 0",
                True,
                True,
            )

        idx = index if index is not None else -1
        if idx < 0 or idx >= total:
            idx = total - 1

        return (
            history[idx],
            graph_visible,
            empty_hidden,
            f"{idx + 1} / {total}",
            idx == 0,
            idx == total - 1,
        )

    # == Callback 6: Reveal prediction form + populate options on train =====
    _cat_option_outputs = [
        Output(_feature_id(f), 'options') for f in PREDICTION_CATEGORICAL_FEATURES
    ]

    @app.callback(
        [Output('agent-pred-form', 'style'),
         Output('agent-pred-empty', 'style'),
         *_cat_option_outputs],
        Input('agent-automl-trained', 'data'),
        prevent_initial_call=False,
    )
    def reveal_prediction_form(trained):
        """Show the form and populate each dropdown from training categories
        when the agent finishes training a model. Generalised: iterates
        PREDICTION_CATEGORICAL_FEATURES so adding a column only requires
        updating dashboard/constants.py."""
        if not trained or _engine.automl_manager.automl is None:
            hidden_form = {'display': 'none'}
            shown_empty = {}
            empty_opts = [[] for _ in PREDICTION_CATEGORICAL_FEATURES]
            return (hidden_form, shown_empty, *empty_opts)

        cat_opts = _engine.automl_manager.get_category_options()
        options_per_feature = []
        for feat in PREDICTION_CATEGORICAL_FEATURES:
            vals = cat_opts.get(feat, [])
            options_per_feature.append([{'label': v, 'value': v} for v in vals])

        shown_form = {'display': 'flex', 'flexDirection': 'column', 'gap': '8px',
                      'paddingTop': '8px'}
        hidden_empty = {'display': 'none'}
        return (shown_form, hidden_empty, *options_per_feature)

    # == Callback 7: Apply agent-supplied prefill to form fields ============
    _all_value_outputs = (
        [Output(_feature_id(f), 'value', allow_duplicate=True)
         for f in PREDICTION_CATEGORICAL_FEATURES] +
        [Output(_feature_id(f), 'value', allow_duplicate=True)
         for f in PREDICTION_NUMERICAL_FEATURES]
    )

    @app.callback(
        _all_value_outputs,
        Input('agent-pred-prefill', 'data'),
        prevent_initial_call=True,
    )
    def apply_prefill(prefill):
        """When the LLM's open_prediction_form tool emits a prefill payload,
        drop each provided value into the corresponding form field; leave
        unprovided fields untouched."""
        if not prefill:
            return [no_update] * (
                len(PREDICTION_CATEGORICAL_FEATURES) + len(PREDICTION_NUMERICAL_FEATURES)
            )
        values = []
        for feat in PREDICTION_CATEGORICAL_FEATURES + PREDICTION_NUMERICAL_FEATURES:
            if feat in prefill and prefill[feat] is not None:
                values.append(prefill[feat])
            else:
                values.append(no_update)
        return values

    # == Callback 8: Compute prediction when user clicks the canvas Predict =
    _all_value_states = (
        [State(_feature_id(f), 'value') for f in PREDICTION_CATEGORICAL_FEATURES] +
        [State(_feature_id(f), 'value') for f in PREDICTION_NUMERICAL_FEATURES]
    )

    @app.callback(
        Output('agent-pred-result', 'children'),
        Input('agent-pred-predict-btn', 'n_clicks'),
        _all_value_states,
        prevent_initial_call=True,
    )
    def canvas_predict(n_clicks, *values):
        """Validate form inputs and call AutoMLManager.predict() directly.

        Predictions are deterministic code-paths — the LLM is not involved,
        and dropdown bindings guarantee each categorical value matches a
        trained category (so the category-dtype bug cannot recur here)."""
        if not n_clicks:
            return no_update
        if _engine.automl_manager.automl is None:
            return html.P("Train a model first.",
                           style={'color': '#707070', 'fontSize': '13px'})

        n_cat = len(PREDICTION_CATEGORICAL_FEATURES)
        cat_values = values[:n_cat]
        num_values_raw = values[n_cat:]

        # Validate
        missing = []
        for feat, val in zip(PREDICTION_CATEGORICAL_FEATURES, cat_values):
            if not val:
                missing.append(feat)
        num_values = []
        for feat, raw in zip(PREDICTION_NUMERICAL_FEATURES, num_values_raw):
            try:
                num_values.append(float(raw))
            except (TypeError, ValueError):
                missing.append(feat)
                num_values.append(None)
        if missing:
            return html.P(
                f"Please fill in: {', '.join(missing)}",
                style={'color': '#ef4444', 'fontSize': '13px'},
            )

        # AutoMLManager.predict() currently expects fixed kwargs. If the
        # feature list grows, extend predict() alongside this dict.
        kwargs = dict(zip(
            PREDICTION_CATEGORICAL_FEATURES,
            [v.strip() if isinstance(v, str) else v for v in cat_values],
        ))
        kwargs['pressure_psi'] = num_values[
            PREDICTION_NUMERICAL_FEATURES.index('Pressure PSI')
        ]
        kwargs['polish_time'] = num_values[
            PREDICTION_NUMERICAL_FEATURES.index('Polish Time')
        ]
        # Normalize categorical kwargs to predict()'s parameter names.
        cat_rename = {'Wafer': 'wafer', 'Pad': 'pad', 'Slurry': 'slurry',
                      'Conditioner': 'conditioner'}
        kwargs = {cat_rename.get(k, k): v for k, v in kwargs.items()}

        try:
            result = _engine.automl_manager.predict(**kwargs)
        except Exception as exc:
            return html.P(f"Prediction failed: {exc}",
                           style={'color': '#ef4444', 'fontSize': '13px'})

        m = _engine.automl_manager.metrics or {}
        children = [
            html.Span(f"Predicted Removal: {result['prediction']:,.0f} \u00c5",
                      style={'fontSize': '18px', 'fontWeight': '600',
                              'color': '#e0e0e0'}),
            html.Br(),
            html.Span(f"Uncertainty: \u00b1 {result['uncertainty']:,.0f} \u00c5",
                      style={'fontSize': '12px', 'color': '#a0a0a0'}),
            html.Br(),
            html.Span(
                f"{result['model']} \u2022 R\u00b2 = {m.get('r2', 0):.3f} "
                f"\u2022 trained on {result['n_train']} files",
                style={'fontSize': '11px', 'color': '#707070'},
            ),
        ]
        if result.get('clamped'):
            children.append(
                html.P("Note: model predicted negative removal \u2014 clamped to 0.",
                        style={'color': '#f59e0b', 'fontSize': '11px',
                               'marginTop': '6px'})
            )
        return html.Div(children)


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
