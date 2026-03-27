
"""Dash application layout definitions for all three analysis tabs."""

from dash import dcc, html
from desktop.theme import COLORS
from dashboard.plotly_theme import INPUT_STYLE, DROPDOWN_STYLE_WIDE, DROPDOWN_STYLE_MEDIUM
from dashboard.constants import FEATURE_AXIS_OPTIONS, ANALYSIS_FEATURES, SCATTER_FEATURE_OPTIONS


def _graph_config(graph_id, extra_buttons=None, double_click=None):
    """Build a standard graph config dict with PNG download options."""
    config = {
        'displayModeBar': True,
        'displaylogo': False,
        'toImageButtonOptions': {
            'format': 'png',
            'filename': graph_id,
            'width': 1600,
            'height': 900,
            'scale': 2,
        },
    }
    if extra_buttons:
        config['modeBarButtonsToAdd'] = extra_buttons
    if double_click is not None:
        config['doubleClick'] = double_click
    return config


def build_single_file_tab():
    """Build the 'Analyze File' (single file) tab layout."""
    return dcc.Tab(label='Analyze File', value='single-file', className='tab', selected_className='tab--selected', children=[
        html.Div([
            # Control Panel
            html.Div(className='control-panel', children=[
                html.Div(className='control-panel-row', children=[
                    html.Div(className='control-group', children=[
                        html.Label("File Selection", className='control-label'),
                        dcc.Dropdown(
                            id='file-selector',
                            placeholder="Select a file to analyze...",
                            clearable=False
                        ),
                    ]),
                    html.Div(className='control-group', children=[
                        html.Label("X-Axis Feature", className='control-label'),
                        dcc.Dropdown(
                            id='sf-x-feature',
                            options=SCATTER_FEATURE_OPTIONS,
                            value='COF',
                            clearable=False,
                            style=DROPDOWN_STYLE_MEDIUM
                        ),
                    ]),
                    html.Div(className='control-group', children=[
                        html.Label("Y-Axis Feature", className='control-label'),
                        dcc.Dropdown(
                            id='sf-y-feature',
                            options=SCATTER_FEATURE_OPTIONS,
                            value='Fz Total (lbf)',
                            clearable=False,
                            style=DROPDOWN_STYLE_MEDIUM
                        ),
                    ]),
                ]),
            ]),

            # Graph Card
            html.Div(className='graph-card', children=[
                html.Div(className='card-header', children=[
                    html.H4("Feature Scatter Animation", className='card-title'),
                    html.P("Animated 2D scatter with time-encoded color", className='card-subtitle'),
                ]),
                # Controls Toolbar — Time Range
                html.Div(className='control-toolbar', children=[
                    html.Div(className='toolbar-group', children=[
                        html.Div(className='inline-control', children=[
                            html.Label("Time Range (s)", className='inline-label'),
                            html.Div([
                                dcc.Input(id='sf-time-start', type='text', inputMode='numeric', placeholder='Auto', style=INPUT_STYLE),
                                html.Span("\u2013", className='range-separator'),
                                dcc.Input(id='sf-time-end', type='text', inputMode='numeric', placeholder='Auto', style=INPUT_STYLE),
                            ], style={'display': 'flex', 'alignItems': 'center'})
                        ])
                    ]),
                ]),
                dcc.Graph(id='time-series-graph', config=_graph_config('time-series-graph', double_click=False), style={'height': '500px'})
            ]),

            # Stats Box
            html.Div(className='stats-box', children=[
                html.H4("Summary Statistics"),
                html.Div(id='file-stats')
            ])

        ], style={'padding': '0'})
    ])


def build_multi_file_tab():
    """Build the 'Compare Files' (multi-file) tab layout."""
    return dcc.Tab(label='Compare Files', value='multi-file', className='tab', selected_className='tab--selected', children=[
        html.Div([
            # Global Control Panel (File Selection & View Toggles)
            html.Div(className='control-panel', children=[
                html.Div(className='control-panel-row', children=[
                    # File Selection Group
                    html.Div(className='control-group-wide', children=[
                        html.Label("File Selection", className='section-label'),
                        dcc.Dropdown(
                            id='multi-file-selector',
                            placeholder="All files selected (click to filter)",
                            multi=True,
                        )
                    ]),

                    # Analysis Views Group
                    html.Div(className='control-group', children=[
                        html.Label("Analysis Views", className='section-label'),
                        html.Div(className='checklist-container', children=[
                            dcc.Checklist(
                                id='analysis-options',
                                options=[
                                    {'label': ' Time Series', 'value': 'timeseries'},
                                    {'label': ' PCA Clustering', 'value': 'pca'},
                                    {'label': ' Feature Explorer', 'value': 'explorer'}
                                ],
                                value=['timeseries'],
                                inline=True,
                            )
                        ])
                    ]),
                ]),
            ]),

            # Empty State Message (shown when no views selected)
            html.Div(id='empty-state-container', className='empty-state', style={'display': 'none'}, children=[
                html.Div("\U0001f4ca", className='empty-state-icon'),
                html.P("Select one or more analysis views above to begin", className='empty-state-text'),
            ]),

            # Graphs Grid
            html.Div(id='graphs-grid-container', className='graphs-grid', children=[

                # 1. Time Series Card
                html.Div(id='card-timeseries', className='graph-card', children=[
                    html.Div(className='card-header', children=[
                        html.H4("Time Series Overlap", className='card-title'),
                        html.P("Compare metric values across all selected files over time", className='card-subtitle'),
                    ]),
                    # Controls Toolbar
                    html.Div(className='control-toolbar', children=[
                        # Metric Selection
                        html.Div(className='inline-control', children=[
                            html.Label("Metric", className='inline-label'),
                            dcc.Dropdown(
                                id='ts-metric',
                                options=[
                                    {'label': 'Coefficient of Friction (COF)', 'value': 'COF'},
                                    {'label': 'Down Force (Fz)', 'value': 'Fz Total (lbf)'},
                                    {'label': 'Shear Force (Fy)', 'value': 'Fy Total (lbf)'},
                                    {'label': 'IR Temperature', 'value': 'IR Temperature'}
                                ],
                                value='COF',
                                clearable=False,
                                style=DROPDOWN_STYLE_WIDE
                            )
                        ]),
                        # X-Range
                        html.Div(className='toolbar-group', children=[
                            html.Div(className='inline-control', children=[
                                html.Label("X-Range (Time)", className='inline-label'),
                                html.Div([
                                    dcc.Input(id='ts-xmin', type='text', inputMode='numeric', placeholder='Auto', style=INPUT_STYLE),
                                    html.Span("\u2013", className='range-separator'),
                                    dcc.Input(id='ts-xmax', type='text', inputMode='numeric', placeholder='Auto', style=INPUT_STYLE),
                                ], style={'display': 'flex', 'alignItems': 'center'})
                            ])
                        ]),
                        # Y-Range
                        html.Div(className='toolbar-group', children=[
                            html.Div(className='inline-control', children=[
                                html.Label("Y-Range (Value)", className='inline-label'),
                                html.Div([
                                    dcc.Input(id='ts-ymin', type='text', inputMode='numeric', placeholder='Auto', style=INPUT_STYLE),
                                    html.Span("\u2013", className='range-separator'),
                                    dcc.Input(id='ts-ymax', type='text', inputMode='numeric', placeholder='Auto', style=INPUT_STYLE),
                                ], style={'display': 'flex', 'alignItems': 'center'})
                            ])
                        ])
                    ]),
                    dcc.Graph(id='ts-graph', config=_graph_config('ts-graph', double_click=False), style={'height': '420px'})
                ]),

                # 2. PCA Clustering Card (primary clustering view)
                html.Div(id='card-pca', className='graph-card', style={'display': 'none'}, children=[
                    html.Div(className='card-header', children=[
                        html.H4("PCA Clustering", className='card-title'),
                        html.P("2D PCA projection with K-Means clustering", className='card-subtitle'),
                    ]),
                    html.Div(className='control-toolbar', children=[
                        # Feature subset selector
                        html.Div(className='inline-control', style={'minWidth': '260px', 'flex': '1'}, children=[
                            html.Label("Features", className='inline-label'),
                            dcc.Dropdown(
                                id='pca-feature-selector',
                                options=[{'label': f, 'value': f} for f in ANALYSIS_FEATURES],
                                value=[f for f in ANALYSIS_FEATURES],
                                multi=True,
                                placeholder='All features (click to filter)',
                            )
                        ]),
                        # Color By
                        html.Div(className='inline-control', children=[
                            html.Label("Color By", className='inline-label'),
                            dcc.Dropdown(
                                id='pca-color',
                                options=[{'label': 'K-Means Cluster', 'value': 'cluster'}] + FEATURE_AXIS_OPTIONS,
                                value='cluster',
                                clearable=False,
                                style=DROPDOWN_STYLE_MEDIUM
                            )
                        ]),
                        # Auto-K badge
                        html.Span(id='pca-k-badge', className='variance-badge', children="K = --"),
                        html.Span(id='pca-variance-badge', className='variance-badge', children="Explained: --%"),
                    ]),
                    # PCA scatter plot (always full width)
                    dcc.Graph(id='pca-graph', config=_graph_config('pca-graph', extra_buttons=['select2d', 'lasso2d']), style={'height': '420px', 'marginBottom': '12px'}),
                    # Selection details (appears below scatter on select)
                    html.Div(id='pca-selection-panel', className='stats-box',
                             style={'display': 'none'}, children=[
                        html.Div(id='pca-selection-header'),
                        html.Div(id='pca-selection-info', className='pca-selection-row'),
                    ]),
                    # Hidden store for caching PCA analysis data (used by selection callback)
                    dcc.Store(id='pca-analysis-store'),
                    # Diagnostics — collapsible section with loadings, silhouette, scree
                    html.Details(style={'marginTop': '12px'}, children=[
                        html.Summary("Diagnostics (Loadings, Cluster Quality, Variance)", style={
                            'cursor': 'pointer', 'fontSize': '13px', 'fontWeight': '600',
                            'color': COLORS['text_secondary'], 'padding': '6px 0',
                        }),
                        html.Div(className='diagnostics-row', children=[
                            dcc.Graph(id='pca-loadings-graph', config={'displayModeBar': False}, style={'height': '300px', 'width': '100%'}),
                            dcc.Graph(id='silhouette-graph', config={'displayModeBar': False}, style={'height': '300px', 'width': '100%'}),
                            dcc.Graph(id='scree-graph', config={'displayModeBar': False}, style={'height': '300px', 'width': '100%'}),
                        ])
                    ])
                ]),

                # 3. Feature Explorer Card (drill-down by raw features)
                html.Div(id='card-explorer', className='graph-card', style={'display': 'none'}, children=[
                    html.Div(className='card-header', children=[
                        html.H4("Feature Explorer", className='card-title'),
                        html.P("Inspect cluster membership across individual features (K is auto-selected via PCA Clustering above)", className='card-subtitle'),
                    ]),
                    html.Div(className='control-toolbar', children=[
                        html.Div(className='toolbar-group', children=[
                            html.Div(className='inline-control', children=[
                                html.Label("X-Axis", className='inline-label'),
                                dcc.Dropdown(
                                    id='explorer-x',
                                    options=FEATURE_AXIS_OPTIONS,
                                    value='Removal',
                                    clearable=False,
                                    style=DROPDOWN_STYLE_MEDIUM
                                )
                            ]),
                            html.Div(className='inline-control', children=[
                                html.Label("Y-Axis", className='inline-label'),
                                dcc.Dropdown(
                                    id='explorer-y',
                                    options=FEATURE_AXIS_OPTIONS,
                                    value='COF',
                                    clearable=False,
                                    style=DROPDOWN_STYLE_MEDIUM
                                )
                            ])
                        ]),
                    ]),
                    dcc.Graph(id='explorer-graph', config=_graph_config('explorer-graph'), style={'height': '380px'})
                ])
            ])

        ], style={'padding': '0'})
    ])


def build_correlations_tab():
    """Build the 'Key Correlations' tab layout."""
    return dcc.Tab(label='Key Correlations', value='correlations', className='tab', selected_className='tab--selected', children=[
        html.Div([
            # Control Panel
            html.Div(className='control-panel', children=[
                html.Div(className='control-panel-row', children=[
                    html.Div(className='control-group-wide', children=[
                        html.Label("File Selection", className='section-label'),
                        dcc.Dropdown(
                            id='corr-file-selector',
                            placeholder="All files selected (click to filter)",
                            multi=True,
                        )
                    ]),
                    html.Div(className='control-group', children=[
                        html.Label("Pressure Filter", className='section-label'),
                        dcc.Dropdown(
                            id='corr-psi-filter',
                            placeholder="All pressures (click to filter)",
                            multi=True,
                        )
                    ]),
                ]),
                # Material / Equipment Filters
                html.Div(className='control-panel-row', style={'marginTop': '12px'}, children=[
                    html.Div(className='control-group', children=[
                        html.Label("Wafer Type", className='section-label'),
                        dcc.Dropdown(
                            id='corr-filter-wafer',
                            placeholder="All wafers",
                            multi=True,
                        )
                    ]),
                    html.Div(className='control-group', children=[
                        html.Label("Pad Type", className='section-label'),
                        dcc.Dropdown(
                            id='corr-filter-pad',
                            placeholder="All pads",
                            multi=True,
                        )
                    ]),
                    html.Div(className='control-group', children=[
                        html.Label("Slurry Type", className='section-label'),
                        dcc.Dropdown(
                            id='corr-filter-slurry',
                            placeholder="All slurries",
                            multi=True,
                        )
                    ]),
                    html.Div(className='control-group', children=[
                        html.Label("Conditioner Disk", className='section-label'),
                        dcc.Dropdown(
                            id='corr-filter-conditioner',
                            placeholder="All conditioners",
                            multi=True,
                        )
                    ]),
                ]),
            ]),

            # Correlation Graphs Grid
            html.Div(className='correlation-grid', children=[
                # 1. Stribeck Curve
                html.Div(className='graph-card', children=[
                    html.Div(className='card-header', style={'display': 'flex', 'alignItems': 'center', 'justifyContent': 'space-between'}, children=[
                        html.Div(children=[
                            html.H4("Stribeck Curve", className='card-title'),
                            html.P("Mean COF vs Pseudo-Sommerfeld Number (log-log scale)", className='card-subtitle'),
                        ]),
                        dcc.Checklist(id='corr-stribeck-lines', options=[{'label': ' Lines', 'value': 'on'}], value=['on'], className='corr-line-toggle'),
                    ]),
                    dcc.Graph(id='corr-stribeck', config=_graph_config('corr-stribeck'), style={'height': '350px'})
                ]),
                # 2. COF vs P.V
                html.Div(className='graph-card', children=[
                    html.Div(className='card-header', style={'display': 'flex', 'alignItems': 'center', 'justifyContent': 'space-between'}, children=[
                        html.Div(children=[
                            html.H4("COF vs P.V", className='card-title'),
                            html.P("Mean COF vs P.V", className='card-subtitle'),
                        ]),
                        dcc.Checklist(id='corr-cof-pv-lines', options=[{'label': ' Lines', 'value': 'on'}], value=['on'], className='corr-line-toggle'),
                    ]),
                    dcc.Graph(id='corr-cof-pv', config=_graph_config('corr-cof-pv'), style={'height': '350px'})
                ]),
                # 3. Temperature vs P.V
                html.Div(className='graph-card', children=[
                    html.Div(className='card-header', style={'display': 'flex', 'alignItems': 'center', 'justifyContent': 'space-between'}, children=[
                        html.Div(children=[
                            html.H4("Mean Pad Temp vs P.V", className='card-title'),
                            html.P("Mean Pad Temp vs P.V", className='card-subtitle'),
                        ]),
                        dcc.Checklist(id='corr-temp-pv-lines', options=[{'label': ' Lines', 'value': 'on'}], value=['on'], className='corr-line-toggle'),
                    ]),
                    dcc.Graph(id='corr-temp-pv', config=_graph_config('corr-temp-pv'), style={'height': '350px'})
                ]),
                # 4. Arrhenius Plot
                html.Div(className='graph-card', children=[
                    html.Div(className='card-header', style={'display': 'flex', 'alignItems': 'center', 'justifyContent': 'space-between'}, children=[
                        html.Div(children=[
                            html.H4("Arrhenius Plot", className='card-title'),
                            html.P("ln(RR) vs 1/T (1/K)", className='card-subtitle'),
                        ]),
                        dcc.Checklist(id='corr-arrhenius-lines', options=[{'label': ' Lines', 'value': 'on'}], value=['on'], className='corr-line-toggle'),
                    ]),
                    dcc.Graph(id='corr-arrhenius', config=_graph_config('corr-arrhenius'), style={'height': '350px'})
                ]),
                # 5. Preston's Plot
                html.Div(className='graph-card', children=[
                    html.Div(className='card-header', style={'display': 'flex', 'alignItems': 'center', 'justifyContent': 'space-between'}, children=[
                        html.Div(children=[
                            html.H4("Preston's Plot", className='card-title'),
                            html.P("Mean Removal Rate vs P.V", className='card-subtitle'),
                        ]),
                        dcc.Checklist(id='corr-preston-lines', options=[{'label': ' Lines', 'value': 'on'}], value=['on'], className='corr-line-toggle'),
                    ]),
                    dcc.Graph(id='corr-preston', config=_graph_config('corr-preston'), style={'height': '350px'})
                ]),
                # 6. WIWNU vs P.V
                html.Div(className='graph-card', children=[
                    html.Div(className='card-header', style={'display': 'flex', 'alignItems': 'center', 'justifyContent': 'space-between'}, children=[
                        html.Div(children=[
                            html.H4("WIWNU vs P.V", className='card-title'),
                            html.P("WIWNU vs P.V", className='card-subtitle'),
                        ]),
                        dcc.Checklist(id='corr-wiwnu-pv-lines', options=[{'label': ' Lines', 'value': 'on'}], value=['on'], className='corr-line-toggle'),
                    ]),
                    dcc.Graph(id='corr-wiwnu-pv', config=_graph_config('corr-wiwnu-pv'), style={'height': '350px'})
                ]),
                # 7. Power Density
                html.Div(className='graph-card', children=[
                    html.Div(className='card-header', style={'display': 'flex', 'alignItems': 'center', 'justifyContent': 'space-between'}, children=[
                        html.Div(children=[
                            html.H4("Power Density", className='card-title'),
                            html.P("Y-axis vs P\u00b7V\u00b7COF", className='card-subtitle'),
                        ]),
                        html.Div(style={'display': 'flex', 'alignItems': 'center', 'gap': '12px'}, children=[
                            dcc.Checklist(id='corr-power-density-lines', options=[{'label': ' Lines', 'value': 'on'}], value=['on'], className='corr-line-toggle'),
                            dcc.Dropdown(
                                id='corr-power-density-y',
                                options=[
                                    {'label': 'Mean Pad Temp', 'value': 'Mean Temp'},
                                    {'label': 'Removal Rate', 'value': 'Removal Rate'},
                                    {'label': 'Var Fz', 'value': 'Var Fz'},
                                    {'label': 'Var Fy', 'value': 'Var Fy'},
                                ],
                                value='Mean Temp',
                                clearable=False,
                                style={'width': '160px', 'fontSize': '12px'},
                            ),
                        ]),
                    ]),
                    dcc.Graph(id='corr-power-density', config=_graph_config('corr-power-density'), style={'height': '350px'})
                ]),
            ]),

        ], style={'padding': '0'})
    ])


def build_prediction_tab():
    """Build the 'Predict Removal' tab layout."""
    return dcc.Tab(label='Predict Removal', value='prediction', className='tab', selected_className='tab--selected', children=[
        html.Div([
            # Control Panel — model selection + train button
            html.Div(className='control-panel', children=[
                html.Div(className='control-panel-row', children=[
                    html.Div(className='control-group', children=[
                        html.Label("Model", className='control-label'),
                        dcc.RadioItems(
                            id='pred-model-select',
                            options=[
                                {'label': ' Ridge Regression', 'value': 'ridge'},
                                {'label': ' Random Forest', 'value': 'rf'},
                            ],
                            value='ridge',
                            inline=True,
                            className='checklist-container',
                            inputStyle={'marginRight': '4px'},
                            labelStyle={'marginRight': '24px', 'fontSize': '13px',
                                        'color': '#888888', 'cursor': 'pointer'},
                        ),
                    ]),
                    html.Div(style={'display': 'flex', 'alignItems': 'flex-end'}, children=[
                        html.Button("Train Model", id='pred-train-btn', n_clicks=0,
                                    className='pred-btn'),
                    ]),
                ]),

                # Metric badges
                html.Div(className='pred-metrics', style={'marginTop': '12px'}, children=[
                    html.Span(id='pred-n-files', className='variance-badge',
                              children='0 files'),
                    html.Span(id='pred-r2', className='variance-badge',
                              title='How well the model explains variation in Removal. 1.0 = perfect, 0.0 = no better than guessing the average.\nR\u00b2 = 1 \u2212 \u03a3(y\u1d62 \u2212 \u0177\u1d62)\u00b2 / \u03a3(y\u1d62 \u2212 \u0233)\u00b2',
                              children='R\u00b2 = --'),
                    html.Span(id='pred-rmse', className='variance-badge',
                              title='Root Mean Squared Error \u2014 average prediction error in Angstroms. Penalizes large misses more heavily. Lower is better.\nRMSE = \u221a(\u03a3(y\u1d62 \u2212 \u0177\u1d62)\u00b2 / n)',
                              children='RMSE = --'),
                    html.Span(id='pred-mae', className='variance-badge',
                              title='Mean Absolute Error \u2014 average prediction error in Angstroms. Lower is better.\nMAE = \u03a3|y\u1d62 \u2212 \u0177\u1d62| / n',
                              children='MAE = --'),
                ]),
                html.Div(id='pred-warning', style={'display': 'none'}),
            ]),

            # Prediction Input Card (hidden until model is trained)
            html.Div(id='pred-input-container', className='graph-card', style={'display': 'none'}, children=[
                html.Div(className='card-header', children=[
                    html.H4("Predict New Configuration", className='card-title'),
                    html.P("Select materials and process parameters to predict removal",
                           className='card-subtitle'),
                ]),
                html.Div(className='control-toolbar', children=[
                    html.Div(className='inline-control', children=[
                        html.Label("Wafer", className='inline-label'),
                        dcc.Dropdown(id='pred-wafer', placeholder="Select...",
                                     clearable=False, style={'width': '160px'}),
                    ]),
                    html.Div(className='inline-control', children=[
                        html.Label("Pad", className='inline-label'),
                        dcc.Dropdown(id='pred-pad', placeholder="Select...",
                                     clearable=False, style={'width': '160px'}),
                    ]),
                    html.Div(className='inline-control', children=[
                        html.Label("Slurry", className='inline-label'),
                        dcc.Dropdown(id='pred-slurry', placeholder="Select...",
                                     clearable=False, style={'width': '160px'}),
                    ]),
                    html.Div(className='inline-control', children=[
                        html.Label("Conditioner", className='inline-label'),
                        dcc.Dropdown(id='pred-conditioner', placeholder="Select...",
                                     clearable=False, style={'width': '160px'}),
                    ]),
                ]),
                html.Div(className='control-toolbar', children=[
                    html.Div(className='inline-control', children=[
                        html.Label("Pressure (PSI)", className='inline-label'),
                        dcc.Input(id='pred-pressure', type='number', placeholder='e.g. 4',
                                  style={**INPUT_STYLE, 'width': '100px'}),
                    ]),
                    html.Div(className='inline-control', children=[
                        html.Label("Polish Time (min)", className='inline-label'),
                        dcc.Input(id='pred-polish-time', type='number',
                                  placeholder='e.g. 1',
                                  style={**INPUT_STYLE, 'width': '100px'}),
                    ]),
                    html.Div(style={'display': 'flex', 'alignItems': 'flex-end'}, children=[
                        html.Button("Predict", id='pred-predict-btn', n_clicks=0,
                                    className='pred-btn'),
                    ]),
                ]),

                # Prediction result
                html.Div(id='pred-result', className='pred-result-box',
                         children=html.P("Train a model, then enter a configuration above.",
                                         style={'color': '#707070', 'fontSize': '13px'})),
            ]),

            # Diagnostics 2x2 Grid (hidden until model is trained)
            html.Div(id='pred-diagnostics-container', className='prediction-grid', style={'display': 'none'}, children=[
                html.Div(className='graph-card', children=[
                    dcc.Graph(id='pred-vs-actual', config=_graph_config('pred-vs-actual'),
                              style={'height': '380px', 'width': '100%'}),
                ]),
                html.Div(className='graph-card', children=[
                    dcc.Graph(id='pred-importance', config=_graph_config('pred-importance'),
                              style={'height': '380px', 'width': '100%'}),
                ]),
                html.Div(className='graph-card', children=[
                    dcc.Graph(id='pred-residual', config=_graph_config('pred-residual'),
                              style={'height': '380px', 'width': '100%'}),
                ]),
                html.Div(className='graph-card', children=[
                    dcc.Graph(id='pred-residual-hist',
                              config=_graph_config('pred-residual-hist'),
                              style={'height': '380px', 'width': '100%'}),
                ]),
            ]),

        ], style={'padding': '0'})
    ])


def build_app_layout():
    """Assemble the complete application layout with all tabs and hidden stores."""
    return html.Div([
        dcc.Tabs(id="analysis-tabs", value='single-file', className='tab-parent', parent_className='tab-parent', content_className='tab-content', children=[
            build_single_file_tab(),
            build_multi_file_tab(),
            build_correlations_tab(),
            build_prediction_tab(),
        ]),
        dcc.Store(id='pred-model-store'),
        dcc.Store(id='ts-dblclick-trigger', data=0),
        dcc.Store(id='sf-dblclick-trigger', data=0),
        html.Div(id='ts-graph-listener', style={'display': 'none'}),
        html.Div(id='sf-graph-listener', style={'display': 'none'}),
    ])
