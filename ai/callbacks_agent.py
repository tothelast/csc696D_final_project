"""Dash callbacks for the AI Agent tab.

Handles: sending messages, polling streamed responses, tab activation,
suggestion chips, and rendering charts inline.
"""

import logging
from queue import Empty

import json

from dash import ALL, Input, Output, State, callback_context, dcc, html, no_update

from ai.agent import AgentEngine
from dashboard.constants import (
    PREDICTION_CATEGORICAL_FEATURES,
    PREDICTION_NUMERICAL_FEATURES,
)


def _feature_id(feature: str) -> str:
    """Mirror of dashboard.layouts._feature_id_suffix for agent-pred-* IDs."""
    return 'agent-pred-' + feature.replace(' PSI', '').lower().replace(' ', '-')


def _props(c) -> dict:
    """Return the props dict whether ``c`` is a Dash component or a serialized
    dict from callback State. Within one callback invocation, `children` is a
    mix of both: existing entries arrived as dicts via State, freshly appended
    entries are still Dash component objects until Dash serializes them on
    return. Checkers that do `isinstance(c, dict)` and skip otherwise will
    miss the fresh ones (causes e.g. the tool-indicator 'running' pill not to
    flip to 'done' when tool_start and tool_end land on the same poll tick).
    """
    if hasattr(c, 'to_plotly_json'):
        return c.to_plotly_json().get('props', {}) or {}
    if isinstance(c, dict):
        return c.get('props', {}) or {}
    return {}


def _extract_chart_title(fig_json: dict) -> str:
    """Extract a human-readable title from a Plotly figure JSON."""
    title = fig_json.get('layout', {}).get('title', '')
    if isinstance(title, dict):
        return title.get('text', '') or ''
    return str(title) if title else ''


_TOOL_LABELS = {
    'run_automl': 'Training prediction model',
    'get_dataset_summary': 'Reading dataset summary',
    'get_file_details': 'Loading file details',
    'get_feature_statistics': 'Computing statistics',
    'detect_outliers': 'Detecting outliers',
    'open_prediction_form': 'Opening prediction form',
    'get_model_diagnostics': 'Loading model diagnostics',
    'generate_scatter': 'Generating scatter plot',
    'generate_distribution': 'Generating distribution plot',
    'generate_bar_chart': 'Generating bar chart',
    'generate_correlation_heatmap': 'Generating correlation heatmap',
    'generate_time_series': 'Generating time series',
    'generate_model_plots': 'Generating diagnostic plots',
}


def _tool_indicator(tool_name: str, status: str):
    """Build a chat indicator for a tool call.

    status: 'running' | 'done' | 'failed'
    """
    label = _TOOL_LABELS.get(tool_name, tool_name.replace('_', ' ').capitalize())
    dot = {'running': '\u25cb', 'done': '\u2713', 'failed': '\u2717'}[status]
    text = f"{dot} {label}" + ('\u2026' if status == 'running' else '')
    return html.Div(
        text,
        className=f'agent-tool-indicator {status}',
        **{'data-tool': tool_name},
    )


def _find_running_tool_indicator(children, tool_name: str):
    """Find the index of the most recent running indicator for tool_name."""
    for i in range(len(children) - 1, -1, -1):
        props = _props(children[i])
        class_name = props.get('className', '') or ''
        parts = class_name.split()
        if 'agent-tool-indicator' in parts and 'running' in parts:
            if props.get('data-tool') == tool_name:
                return i
    return None


def _assistant_msg(text: str, *, streaming: bool = False, loading: bool = False):
    """Build an assistant chat message as rendered Markdown.

    State is encoded in className (dcc.Markdown doesn't support arbitrary
    data-* attributes). Helpers like _is_assistant_streaming / _is_loading
    read these classes back from the component dict.
    """
    classes = ['agent-message', 'assistant']
    if streaming:
        classes.append('streaming')
    if loading:
        classes.append('loading')
    return dcc.Markdown(
        text or '',
        className=' '.join(classes),
        link_target='_blank',
        dangerously_allow_html=False,
    )

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
         Output('agent-open-tabs', 'data', allow_duplicate=True),
         Output('agent-active-tab', 'data', allow_duplicate=True),
         Output('agent-automl-trained', 'data', allow_duplicate=True),
         Output('agent-pred-prefill', 'data', allow_duplicate=True)],
        [Input('agent-poll-interval', 'n_intervals')],
        [State('agent-chat-area', 'children'),
         State('agent-pending-message', 'data'),
         State('agent-processing', 'data'),
         State('agent-chart-history', 'data'),
         State('agent-open-tabs', 'data')],
        prevent_initial_call=True,
    )
    def poll_response(n_intervals, current_children, pending_msg, is_processing,
                       chart_history, open_tabs):
        if not is_processing:
            return (no_update, True, no_update, no_update, no_update, no_update,
                    no_update, no_update, no_update, no_update, no_update)

        children = list(current_children) if current_children else []

        # If this is the first poll after a new message, add the user message
        if pending_msg and not any(
            _is_user_message(c, pending_msg) for c in children
        ):
            children.append(
                html.Div(pending_msg, className='agent-message user')
            )

        # Drain the output queue. We preserve the relative order of text and
        # tool events by applying tool events to `children` immediately (they
        # partition the stream into turn-segments), while text is accumulated
        # into a buffer that gets appended to the trailing streaming bubble.
        text_buffer = ""
        thinking_buffer = ""
        charts = []
        prefill_payload = None
        is_done = False
        error_msg = None

        def _flush_text(buf):
            """Append buffered text to the trailing streaming bubble, or open
            a new one if the last element is a tool indicator / chart / etc."""
            if not buf:
                return
            nonlocal children
            children = [c for c in children if not _is_loading(c)]
            if children and _is_assistant_streaming(children[-1]):
                prev = _extract_text(children[-1])
                children[-1] = _assistant_msg(prev + buf, streaming=True)
            else:
                children.append(_assistant_msg(buf, streaming=True))

        def _close_streaming():
            """Finalize any streaming assistant bubble so the next text run
            opens a fresh bubble."""
            nonlocal children
            children = [c for c in children if not _is_loading(c)]
            if children and _is_assistant_streaming(children[-1]):
                text = _extract_text(children[-1])
                children[-1] = _assistant_msg(text)

        while True:
            try:
                chunk = _engine.output_queue.get_nowait()
            except Empty:
                break

            if chunk.type == "text":
                text_buffer += chunk.content
            elif chunk.type == "thinking":
                thinking_buffer += chunk.content
            elif chunk.type == "tool_start":
                # Flush any pending text, close the current assistant bubble,
                # then append a running tool indicator.
                _flush_text(text_buffer); text_buffer = ""
                _close_streaming()
                children.append(_tool_indicator(chunk.content, 'running'))
            elif chunk.type == "tool_end":
                info = chunk.content if isinstance(chunk.content, dict) else {'name': str(chunk.content), 'success': True}
                idx = _find_running_tool_indicator(children, info['name'])
                if idx is not None:
                    children[idx] = _tool_indicator(
                        info['name'], 'done' if info.get('success') else 'failed'
                    )
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

        # Flush any text that arrived after the last tool event (or all of it
        # if no tool events fired this tick).
        _flush_text(text_buffer)

        # Show a loading indicator while processing and no text yet. Skip if
        # there's a running tool indicator — that already signals "working".
        def _is_running_indicator(c):
            parts = (_props(c).get('className', '') or '').split()
            return 'agent-tool-indicator' in parts and 'running' in parts
        has_running_tool = any(_is_running_indicator(c) for c in children)
        if (not text_buffer and not is_done and not charts and not error_msg
                and not has_running_tool):
            # If there's no streaming assistant message yet, add a loading one
            if not children or not _is_assistant_streaming(children[-1]):
                if not any(_is_loading(c) for c in children):
                    children.append(_assistant_msg("Thinking...", loading=True))

        # Route charts to the canvas history store; reference them in chat
        history_out = no_update
        tabs_out = no_update
        active_out = no_update
        if charts:
            history = list(chart_history) if chart_history else []
            tabs = list(open_tabs) if open_tabs else []
            for chart_data in charts:
                history.append(chart_data)
                chart_idx = len(history) - 1
                title = _extract_chart_title(chart_data)
                label = title if title else f"Chart {len(history)}"
                tabs.append({'chart_idx': chart_idx, 'label': label})
                children.append(
                    html.Div(
                        f"[{label} \u2192]",
                        className='agent-message system',
                    )
                )
            history_out = history
            tabs_out = tabs
            active_out = f"chart-{len(history) - 1}"  # jump to newest

        # Handle errors
        if error_msg:
            children.append(
                html.Div(
                    f"Error: {error_msg}",
                    className='agent-message system',
                )
            )

        # Flip the trained flag only once training has FINISHED — not just when
        # AutoML() is instantiated. train() sets self.automl before fit() runs
        # and populates self.metrics at the very end, so use metrics as the
        # "ready to predict" signal to avoid a race where the form opens while
        # FLAML is still fitting.
        trained_out = bool(
            _engine.automl_manager.automl is not None
            and _engine.automl_manager.metrics is not None
        )
        prefill_out = prefill_payload if prefill_payload is not None else no_update

        # Finalize
        if is_done:
            # Remove loading indicator and thinking elements
            children = [c for c in children if not _is_loading(c)]

            # Mark last assistant message as done (remove streaming flag)
            if children and _is_assistant_streaming(children[-1]):
                text = _extract_text(children[-1])
                children[-1] = _assistant_msg(text)

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
                tabs_out,
                active_out,
                trained_out,
                prefill_out,
            )

        return (children, no_update, no_update, no_update, no_update, no_update,
                history_out, tabs_out, active_out, trained_out, prefill_out)

    # == Callback 3: Tab activation — greeting ==============================
    @app.callback(
        [Output('agent-chat-area', 'children', allow_duplicate=True),
         Output('agent-data-badge', 'children'),
         Output('agent-ollama-badge', 'children'),
         Output('agent-ollama-badge', 'className'),
         Output('agent-model-badge', 'children', allow_duplicate=True),
         Output('agent-model-badge', 'className', allow_duplicate=True)],
        Input('analysis-tabs', 'value'),
        State('agent-chat-area', 'children'),
        prevent_initial_call=True,
    )
    def on_tab_activate(tab_value, current_children):
        if tab_value != 'agent':
            return no_update, no_update, no_update, no_update, no_update, no_update

        df = data_manager.get_all_data()
        file_count = len(df)
        removal_count = int((df.get('Removal', 0) > 0).sum()) if not df.empty else 0

        greeting = _engine.get_greeting(file_count, removal_count)

        # Restore model badge from server-side state (survives page reloads)
        if _engine and _engine.automl_manager.metrics:
            m = _engine.automl_manager.metrics
            model_text = f"{m['best_model']} (R²={m['r2']:.3f})"
            model_class = "agent-status-badge active"
        else:
            model_text = no_update
            model_class = no_update

        # Dedup guard: if the greeting (or any assistant message containing
        # that exact text) is already in the chat, don't re-append it. This
        # protects against double-renders if the callback ever re-fires on
        # the same tab activation.
        if current_children:
            for c in current_children:
                if _extract_text(c) == greeting:
                    return no_update, no_update, no_update, no_update, model_text, model_class
            # Chat is non-empty but doesn't contain the greeting — still skip,
            # matching prior "only greet once" behaviour.
            return no_update, no_update, no_update, no_update, model_text, model_class

        children = [_assistant_msg(greeting)]

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

        return children, data_badge, ollama_text, ollama_class, model_text, model_class

    # == Callback 4: Render tab bar ==========================================
    @app.callback(
        Output('agent-tab-bar', 'children'),
        [Input('agent-open-tabs', 'data'),
         Input('agent-active-tab', 'data')],
        prevent_initial_call=False,
    )
    def render_tab_bar(open_tabs, active_tab):
        active = active_tab or 'predict'
        tabs = [
            html.Div(
                "Predict Removal",
                id='agent-tab-predict',
                className='agent-tab active' if active == 'predict' else 'agent-tab',
                n_clicks=0,
            ),
        ]
        for tab_info in (open_tabs or []):
            chart_idx = tab_info['chart_idx']
            tab_id = f'chart-{chart_idx}'
            is_active = active == tab_id
            tabs.append(
                html.Div(className='agent-tab-wrapper', children=[
                    html.Div(
                        tab_info['label'],
                        id={'type': 'agent-chart-tab', 'index': chart_idx},
                        className='agent-tab active' if is_active else 'agent-tab',
                        n_clicks=0,
                    ),
                    html.Button(
                        '\u00d7',
                        id={'type': 'agent-chart-tab-close', 'index': chart_idx},
                        className='agent-tab-close',
                        n_clicks=0,
                    ),
                ])
            )
        return tabs

    # == Callback 5: Render tab content =====================================
    @app.callback(
        [Output('agent-pred-panel', 'style'),
         Output('agent-chart-panel', 'style'),
         Output('agent-canvas-graph', 'figure')],
        [Input('agent-active-tab', 'data')],
        [State('agent-chart-history', 'data')],
        prevent_initial_call=False,
    )
    def render_tab_content(active_tab, chart_history):
        if active_tab == 'predict' or not active_tab:
            return {}, {'display': 'none'}, no_update

        try:
            chart_idx = int(active_tab.split('-', 1)[1])
        except (ValueError, IndexError):
            return {}, {'display': 'none'}, no_update

        history = chart_history or []
        if chart_idx < 0 or chart_idx >= len(history):
            return {}, {'display': 'none'}, no_update

        # Patch the figure to autosize into its container instead of
        # using a fixed pixel width/height baked into the JSON.
        fig = dict(history[chart_idx])
        layout = dict(fig.get('layout', {}))
        layout['autosize'] = True
        layout.pop('width', None)
        layout.pop('height', None)
        fig['layout'] = layout

        return (
            {'display': 'none'},
            {},  # use CSS defaults (flex column, fills container)
            fig,
        )

    # == Callback 5a: Switch to Predict tab =================================
    @app.callback(
        Output('agent-active-tab', 'data', allow_duplicate=True),
        Input('agent-tab-predict', 'n_clicks'),
        prevent_initial_call=True,
    )
    def switch_to_predict(n):
        if not n:
            return no_update
        return 'predict'

    # == Callback 5b: Switch to a chart tab =================================
    @app.callback(
        Output('agent-active-tab', 'data', allow_duplicate=True),
        Input({'type': 'agent-chart-tab', 'index': ALL}, 'n_clicks'),
        prevent_initial_call=True,
    )
    def switch_to_chart(n_clicks_list):
        ctx = callback_context
        if not ctx.triggered or not n_clicks_list or not any(n_clicks_list):
            return no_update
        triggered = ctx.triggered[0]
        idx_dict = json.loads(triggered['prop_id'].split('.')[0])
        return f"chart-{idx_dict['index']}"

    # == Callback 5c: Close a chart tab =====================================
    @app.callback(
        [Output('agent-open-tabs', 'data', allow_duplicate=True),
         Output('agent-active-tab', 'data', allow_duplicate=True)],
        Input({'type': 'agent-chart-tab-close', 'index': ALL}, 'n_clicks'),
        [State('agent-open-tabs', 'data'),
         State('agent-active-tab', 'data')],
        prevent_initial_call=True,
    )
    def close_chart_tab(n_clicks_list, open_tabs, active_tab):
        ctx = callback_context
        if not ctx.triggered or not n_clicks_list or not any(n_clicks_list):
            return no_update, no_update

        idx_dict = json.loads(ctx.triggered[0]['prop_id'].split('.')[0])
        closing_idx = idx_dict['index']
        closing_tab_id = f"chart-{closing_idx}"

        new_tabs = [t for t in (open_tabs or []) if t['chart_idx'] != closing_idx]

        new_active = active_tab
        if active_tab == closing_tab_id:
            if new_tabs:
                old_pos = next(
                    (i for i, t in enumerate(open_tabs or [])
                     if t['chart_idx'] == closing_idx), 0
                )
                pick = min(old_pos, len(new_tabs) - 1)
                new_active = f"chart-{new_tabs[pick]['chart_idx']}"
            else:
                new_active = 'predict'

        return new_tabs, new_active

    # == Sync trained flag on tab activation ================================
    # When the Dash page reloads (e.g. user leaves to the Landing/Project
    # page and comes back), the agent-automl-trained store resets to its
    # default (False) and the form would stay hidden until the next
    # interaction. This callback reconciles the client-side store with the
    # engine's actual trained state every time the Agent tab becomes active,
    # including the initial page load.
    @app.callback(
        Output('agent-automl-trained', 'data', allow_duplicate=True),
        Input('analysis-tabs', 'value'),
        prevent_initial_call='initial_duplicate',
    )
    def sync_trained_on_tab(tab_value):
        if tab_value != 'agent':
            return no_update
        if _engine and _engine.automl_manager.metrics is not None:
            return True
        return no_update

    # == Callback 6: Populate prediction form options on train ================
    _cat_option_outputs = [
        Output(_feature_id(f), 'options') for f in PREDICTION_CATEGORICAL_FEATURES
    ]

    @app.callback(
        [Output('agent-pred-form', 'style'),
         Output('agent-pred-empty', 'style'),
         *_cat_option_outputs],
        [Input('agent-automl-trained', 'data'),
         Input('analysis-tabs', 'value')],
        prevent_initial_call=False,
    )
    def populate_prediction_options(trained, tab_value):
        """Toggle form visibility and populate dropdowns.

        Before training: show the empty-state message, hide the form.
        After training: show the form with training categories."""
        if trained and _engine.automl_manager.automl is not None:
            cat_opts = _engine.automl_manager.get_category_options()
            options = [
                [{'label': v, 'value': v} for v in cat_opts.get(feat, [])]
                for feat in PREDICTION_CATEGORICAL_FEATURES
            ]
            return ({'display': 'flex', 'flexDirection': 'column', 'gap': '8px'},
                    {'display': 'none'}, *options)

        # Not trained — hide the form, show the empty-state message
        return ({'display': 'none'}, {}, *[[] for _ in PREDICTION_CATEGORICAL_FEATURES])

    # == Callback 7: Apply agent-supplied prefill to form fields ============
    _all_value_outputs = (
        [Output(_feature_id(f), 'value', allow_duplicate=True)
         for f in PREDICTION_CATEGORICAL_FEATURES] +
        [Output(_feature_id(f), 'value', allow_duplicate=True)
         for f in PREDICTION_NUMERICAL_FEATURES]
    )

    @app.callback(
        [*_all_value_outputs,
         Output('agent-active-tab', 'data', allow_duplicate=True)],
        Input('agent-pred-prefill', 'data'),
        prevent_initial_call=True,
    )
    def apply_prefill(prefill):
        """When the LLM's open_prediction_form tool emits a prefill payload,
        drop each provided value into the corresponding form field and switch
        to the Predict tab so the user sees it."""
        n_fields = len(PREDICTION_CATEGORICAL_FEATURES) + len(PREDICTION_NUMERICAL_FEATURES)
        if not prefill:
            return [no_update] * n_fields + [no_update]
        values = []
        for feat in PREDICTION_CATEGORICAL_FEATURES + PREDICTION_NUMERICAL_FEATURES:
            if feat in prefill and prefill[feat] is not None:
                values.append(prefill[feat])
            else:
                values.append(no_update)
        return values + ['predict']

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
            return html.P("Ask the agent to build the model first.",
                           style={'color': '#707070', 'fontSize': '13px'})
        if _engine.automl_manager.metrics is None:
            # AutoML() instantiated but fit() / nested-CV still running.
            return html.P(
                "Training in progress \u2014 please wait a few seconds and try again.",
                style={'color': '#f59e0b', 'fontSize': '13px'},
            )

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

        # Build kwargs using column names directly — predict() now accepts
        # **kwargs keyed by the constant column names, so adding new features
        # only requires updating constants.py.
        kwargs = dict(zip(
            PREDICTION_CATEGORICAL_FEATURES,
            [v.strip() if isinstance(v, str) else v for v in cat_values],
        ))
        for feat, val in zip(PREDICTION_NUMERICAL_FEATURES, num_values):
            kwargs[feat] = val

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
    props = _props(component)
    return (props.get('className') == 'agent-message user'
            and props.get('children') == text)


def _is_assistant_streaming(component):
    """Check if a component is a streaming assistant message."""
    class_name = _props(component).get('className', '') or ''
    parts = class_name.split()
    return 'assistant' in parts and 'streaming' in parts


def _extract_text(component):
    """Extract the Markdown source (or plain text) from a chat message."""
    children = _props(component).get('children', '')
    return children if isinstance(children, str) else ''


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
    class_name = _props(component).get('className', '') or ''
    return 'loading' in class_name.split()
