"""Dash callback registrations for all analysis tabs.

This module serves as the orchestrator that delegates callback registration
to tab-specific modules while keeping shared callbacks (clientside listeners,
visibility, file selectors, range defaults) here.
"""

import dash
from dash import Input, Output, State

from dashboard.callbacks_compare import register_compare_callbacks
from dashboard.callbacks_single import register_single_file_callbacks
from dashboard.callbacks_correlations import register_correlation_callbacks
from dashboard.callbacks_prediction import register_prediction_callbacks
from ai.callbacks_agent import register_agent_callbacks


def register_callbacks(app, data_manager, agent_engine=None):
    """Register all Dash callbacks on the given app instance."""

    # =========================================================================
    # Clientside callbacks: attach plotly_doubleclick listeners that fire the
    # trigger stores, causing the range-default callbacks to reset the inputs.
    # Native double-click is disabled via doubleClick:false in the graph config
    # (layouts.py) to prevent Plotly's axis toggle from desynchronising Dash
    # component state.
    # =========================================================================

    app.clientside_callback(
        """
        function(figure) {
            var container = document.getElementById('ts-graph');
            if (!container) return window.dash_clientside.no_update;
            var el = (typeof container.on === 'function')
                ? container
                : container.querySelector('.js-plotly-plot');
            if (!el) return window.dash_clientside.no_update;
            if (!el._tsListened) {
                el._tsListened = true;
                el.on('plotly_doubleclick', function() {
                    dash_clientside.set_props('ts-dblclick-trigger', {data: Date.now()});
                });
            }
            return window.dash_clientside.no_update;
        }
        """,
        Output('ts-graph-listener', 'children'),
        Input('ts-graph', 'figure'),
        prevent_initial_call=True
    )

    app.clientside_callback(
        """
        function(figure) {
            var container = document.getElementById('time-series-graph');
            if (!container) return window.dash_clientside.no_update;
            var el = (typeof container.on === 'function')
                ? container
                : container.querySelector('.js-plotly-plot');
            if (!el) return window.dash_clientside.no_update;
            if (!el._sfListened) {
                el._sfListened = true;
                el.on('plotly_doubleclick', function() {
                    dash_clientside.set_props('sf-dblclick-trigger', {data: Date.now()});
                });
            }
            return window.dash_clientside.no_update;
        }
        """,
        Output('sf-graph-listener', 'children'),
        Input('time-series-graph', 'figure'),
        prevent_initial_call=True
    )

    # =========================================================================
    # Visibility callback - controls card display and empty state
    # =========================================================================

    @app.callback(
        [Output('card-timeseries', 'style'),
         Output('card-pca', 'style'),
         Output('card-explorer', 'style'),
         Output('empty-state-container', 'style'),
         Output('graphs-grid-container', 'style')],
        [Input('analysis-options', 'value')]
    )
    def update_visibility(options):
        """Show/hide graph cards based on selected analysis options."""
        if not options:
            return (
                {'display': 'none'},
                {'display': 'none'},
                {'display': 'none'},
                {'display': 'flex'},
                {'display': 'none'}
            )

        show_ts = {} if 'timeseries' in options else {'display': 'none'}
        show_pca = {} if 'pca' in options else {'display': 'none'}
        show_explorer = {} if 'explorer' in options else {'display': 'none'}

        return show_ts, show_pca, show_explorer, {'display': 'none'}, {}

    # =========================================================================
    # Range input defaults
    # =========================================================================

    @app.callback(
        [Output('sf-time-start', 'value'),
         Output('sf-time-end', 'value')],
        [Input('file-selector', 'value'),
         Input('sf-dblclick-trigger', 'data')]
    )
    def update_single_file_time_defaults(file_basename, _trigger):
        """Set default time range from the file's interval."""
        if file_basename:
            interval = data_manager.get_file_interval(file_basename)
            if interval and len(interval) == 2:
                return interval[0], interval[1]
        return '', ''

    @app.callback(
        [Output('ts-xmin', 'value'),
         Output('ts-xmax', 'value'),
         Output('ts-ymin', 'value'),
         Output('ts-ymax', 'value')],
        [Input('ts-metric', 'value'),
         Input('ts-dblclick-trigger', 'data')]
    )
    def update_compare_range_defaults(metric, _trigger):
        """Set default range values for the Compare Files tab.

        Uses '' instead of None for dcc.Input type='text' values because
        browsers reject null (NaN) on number inputs, causing a state desync
        between the DOM (keeps old value) and Dash (thinks it's None).
        """
        y_min, y_max = (0, 1) if metric == 'COF' else ('', '')
        return '', '', y_min, y_max

    # =========================================================================
    # File selector callback
    # =========================================================================

    @app.callback(
        [Output('file-selector', 'options'),
         Output('file-selector', 'value'),
         Output('multi-file-selector', 'options'),
         Output('multi-file-selector', 'value'),
         Output('corr-file-selector', 'options'),
         Output('corr-file-selector', 'value'),
         Output('corr-psi-filter', 'options'),
         Output('corr-psi-filter', 'value'),
         # Material / equipment filter options & values
         Output('corr-filter-wafer', 'options'),
         Output('corr-filter-wafer', 'value'),
         Output('corr-filter-pad', 'options'),
         Output('corr-filter-pad', 'value'),
         Output('corr-filter-slurry', 'options'),
         Output('corr-filter-slurry', 'value'),
         Output('corr-filter-conditioner', 'options'),
         Output('corr-filter-conditioner', 'value')],
        Input('analysis-tabs', 'value'),
        [State('corr-file-selector', 'value'),
         State('corr-psi-filter', 'value'),
         State('corr-filter-wafer', 'value'),
         State('corr-filter-pad', 'value'),
         State('corr-filter-slurry', 'value'),
         State('corr-filter-conditioner', 'value')]
    )
    def update_file_selector(_tab, curr_corr_files, curr_psi,
                             curr_wafer, curr_pad, curr_slurry, curr_conditioner):
        """Update file selector dropdowns with available files.

        Correlation filter values are only set on first load (when None).
        On subsequent tab switches the values are preserved via no_update.
        """
        files = data_manager.get_file_names()
        options = [{'label': f, 'value': f} for f in files]
        # Pre-select first file for single-file tab, all files for multi/corr tabs
        first_file = files[0] if files else None

        # Build PSI filter options from loaded data
        df = data_manager.get_all_data()
        if not df.empty and 'Pressure PSI' in df.columns:
            psi_values = sorted(df['Pressure PSI'].dropna().unique())
            psi_options = [{'label': f'{p} PSI', 'value': p} for p in psi_values]
        else:
            psi_options = []

        # Build material / equipment filter options
        material_options = {}
        for col in ['Wafer', 'Pad', 'Slurry', 'Conditioner']:
            if not df.empty and col in df.columns:
                unique_vals = sorted([v for v in df[col].dropna().unique() if v != ''])
                material_options[col] = [{'label': v, 'value': v} for v in unique_vals]
            else:
                material_options[col] = []

        # Correlation filter values: only initialise on first load (None),
        # preserve user selections on subsequent tab switches.
        if curr_corr_files is None:
            corr_files_val = files
        else:
            corr_files_val = dash.no_update

        if curr_psi is None:
            psi_val = [p['value'] for p in psi_options]
        else:
            psi_val = dash.no_update

        # Material filters: default to all values selected
        mat_vals = {}
        for col in ['Wafer', 'Pad', 'Slurry', 'Conditioner']:
            curr = {'Wafer': curr_wafer, 'Pad': curr_pad,
                    'Slurry': curr_slurry, 'Conditioner': curr_conditioner}[col]
            if curr is None:
                mat_vals[col] = [o['value'] for o in material_options[col]]
            else:
                mat_vals[col] = dash.no_update

        return (
            options, first_file, options, files,
            options, corr_files_val,
            psi_options, psi_val,
            material_options['Wafer'], mat_vals['Wafer'],
            material_options['Pad'], mat_vals['Pad'],
            material_options['Slurry'], mat_vals['Slurry'],
            material_options['Conditioner'], mat_vals['Conditioner'],
        )

    # =========================================================================
    # Delegate tab-specific callbacks to sub-modules
    # =========================================================================

    register_compare_callbacks(app, data_manager)
    register_single_file_callbacks(app, data_manager)
    register_correlation_callbacks(app, data_manager)
    register_prediction_callbacks(app, data_manager)
    if agent_engine is not None:
        register_agent_callbacks(app, data_manager, agent_engine)
