"""Analyze File (single file) tab callbacks — animated feature scatter plot."""

import numpy as np
from dash import html, Input, Output
import plotly.graph_objects as go

from desktop.theme import COLORS
from dashboard.plotly_theme import DARK_LAYOUT, create_empty_figure

MAX_FRAMES = 60
MAX_DATA_POINTS = 1500
MARKER_OPACITY = 0.8


def _to_num(val):
    """Convert a text input value to float, or None if empty/invalid."""
    if val is None or val == '':
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def register_single_file_callbacks(app, data_manager):
    """Register the Analyze File tab callbacks."""

    @app.callback(
        [Output('time-series-graph', 'figure'),
         Output('file-stats', 'children')],
        [Input('file-selector', 'value'),
         Input('sf-x-feature', 'value'),
         Input('sf-y-feature', 'value'),
         Input('sf-time-start', 'value'),
         Input('sf-time-end', 'value'),
         Input('analysis-tabs', 'value')]
    )
    def update_scatter_animation(file_basename, x_feature, y_feature,
                                  time_start, time_end, tab):
        """Build animated scatter plot with time-encoded color."""
        empty_stats = html.Div([
            html.P("No file selected",
                   style={'color': COLORS['text_secondary'], 'fontStyle': 'italic'})
        ])

        if tab != 'single-file' or not file_basename:
            return create_empty_figure("Select a file above to view its data."), empty_stats

        df = data_manager.get_file_data(file_basename)
        if df is None or df.empty:
            return create_empty_figure("Error loading file data."), html.Div([
                html.P("Error loading data", style={'color': COLORS['danger']})
            ])

        # Validate selected features exist in this file's data
        for feat in (x_feature, y_feature):
            if feat not in df.columns:
                return (
                    create_empty_figure(f"Column '{feat}' is not available for this file."),
                    html.Div([html.P(f"'{feat}' not found in data",
                                     style={'color': COLORS['text_secondary']})])
                )

        # Apply time filter
        t_start = _to_num(time_start)
        t_end = _to_num(time_end)
        df_filtered = df
        if t_start is not None:
            df_filtered = df_filtered[df_filtered['time (s)'] >= t_start]
        if t_end is not None:
            df_filtered = df_filtered[df_filtered['time (s)'] <= t_end]

        if df_filtered.empty:
            return (
                create_empty_figure("No data points in the specified time range."),
                html.Div([html.P("No data in range",
                                 style={'color': COLORS['text_secondary']})])
            )

        # Performance: subsample if too many points
        if len(df_filtered) > MAX_DATA_POINTS:
            indices = np.round(np.linspace(0, len(df_filtered) - 1, MAX_DATA_POINTS)).astype(int)
            df_filtered = df_filtered.iloc[indices].reset_index(drop=True)

        time_col = df_filtered['time (s)'].values
        x_col = df_filtered[x_feature].values
        y_col = df_filtered[y_feature].values
        n_points = len(df_filtered)
        t_min, t_max = float(time_col[0]), float(time_col[-1])

        # Build frame boundary indices
        if n_points <= MAX_FRAMES:
            frame_ends = list(range(1, n_points + 1))
        else:
            frame_ends = np.round(np.linspace(1, n_points, MAX_FRAMES)).astype(int).tolist()
            frame_ends[-1] = n_points

        # Initial opacity: first batch visible, rest hidden
        initial_end = frame_ends[0]
        opacity_init = np.zeros(n_points)
        opacity_init[:initial_end] = MARKER_OPACITY

        # All points in the initial trace — animation toggles opacity only
        fig = go.Figure(
            data=[go.Scatter(
                x=x_col,
                y=y_col,
                mode='markers',
                marker=dict(
                    color=time_col,
                    colorscale='Plasma',
                    cmin=t_min,
                    cmax=t_max,
                    size=6,
                    opacity=opacity_init,
                    colorbar=dict(
                        title=dict(text='Time (s)',
                                   font=dict(color=COLORS['text_secondary'], size=12)),
                        tickfont=dict(color=COLORS['text_secondary'], size=10),
                        bgcolor=COLORS['bg_secondary'],
                        bordercolor=COLORS['border_light'],
                        borderwidth=1,
                        thickness=15,
                        len=0.8,
                    ),
                ),
                hovertemplate=(
                    f'{x_feature}: %{{x:.4f}}<br>'
                    f'{y_feature}: %{{y:.4f}}<br>'
                    'Time: %{marker.color:.2f}s<extra></extra>'
                ),
            )],
        )

        # Frames only update marker.opacity (same trace length, no redraw needed)
        frames = []
        for k, end_i in enumerate(frame_ends):
            opacity = np.zeros(n_points)
            opacity[:end_i] = MARKER_OPACITY
            frames.append(go.Frame(
                data=[dict(marker=dict(opacity=opacity))],
                name=str(k),
                traces=[0],
            ))
        fig.frames = frames

        # Slider steps
        slider_steps = []
        for k, end_i in enumerate(frame_ends):
            slider_steps.append(dict(
                args=[[str(k)], dict(
                    frame=dict(duration=0, redraw=False),
                    mode='immediate',
                    transition=dict(duration=0),
                )],
                label=f'{time_col[end_i - 1]:.1f}',
                method='animate',
            ))

        # Apply dark theme + layout
        fig.update_layout(**DARK_LAYOUT)
        fig.update_layout(
            xaxis_title=x_feature,
            yaxis_title=y_feature,
            margin=dict(l=50, r=30, t=40, b=100),
            hovermode='closest',
            showlegend=False,
            updatemenus=[dict(
                buttons=[
                    dict(
                        args=[None, dict(
                            frame=dict(duration=80, redraw=False),
                            fromcurrent=True,
                            transition=dict(duration=0),
                        )],
                        label='\u25b6 Play',
                        method='animate',
                    ),
                    dict(
                        args=[[None], dict(
                            frame=dict(duration=0, redraw=False),
                            mode='immediate',
                            transition=dict(duration=0),
                        )],
                        label='\u25a0 Pause',
                        method='animate',
                    ),
                ],
                direction='left',
                pad=dict(r=10, t=70),
                showactive=False,
                type='buttons',
                x=0.1,
                xanchor='right',
                y=0,
                yanchor='top',
                font=dict(color=COLORS['text_primary'], size=11),
                bgcolor=COLORS['bg_tertiary'],
                bordercolor=COLORS['border_light'],
            )],
            sliders=[dict(
                active=0,
                yanchor='top',
                xanchor='left',
                currentvalue=dict(
                    prefix='Time: ',
                    suffix='s',
                    visible=True,
                    xanchor='right',
                    font=dict(color=COLORS['text_secondary'], size=11),
                ),
                transition=dict(duration=0),
                pad=dict(b=10, t=50),
                len=0.9,
                x=0.1,
                y=0,
                steps=slider_steps,
                font=dict(color=COLORS['text_secondary']),
                tickcolor=COLORS['border_light'],
                bordercolor=COLORS['border_light'],
                bgcolor=COLORS['bg_tertiary'],
                activebgcolor=COLORS['accent'],
            )],
        )

        # Build stats for both features
        stats_content = []
        for label, feature in [('X-Axis', x_feature), ('Y-Axis', y_feature)]:
            vals = df_filtered[feature]
            stats_content.append(html.Div(className='stat-item', children=[
                html.Span(f"{label}: {feature}", className='stat-label'),
                html.Span(
                    f"Mean: {vals.mean():.4f}  |  Std: {vals.std():.4f}  |  "
                    f"Range: {vals.min():.4f} \u2013 {vals.max():.4f}",
                    className='stat-value'
                ),
            ]))

        return fig, html.Div(stats_content)
