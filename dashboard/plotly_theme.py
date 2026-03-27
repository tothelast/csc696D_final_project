"""Plotly dark theme configuration and shared figure helpers."""

import plotly.graph_objects as go
from desktop.theme import COLORS

# Plotly dark template matching PyQt6 design
DARK_LAYOUT = {
    'paper_bgcolor': COLORS['bg_secondary'],
    'plot_bgcolor': COLORS['bg_secondary'],
    'font': {'color': COLORS['text_primary'], 'size': 12, 'family': '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif'},
    'title': {'font': {'color': COLORS['text_primary'], 'size': 14}},
    'xaxis': {
        'gridcolor': COLORS['border'],
        'linecolor': COLORS['border_light'],
        'tickfont': {'color': COLORS['text_secondary']},
        'title': {'font': {'color': COLORS['text_secondary']}},
        'zerolinecolor': COLORS['border_light'],
    },
    'yaxis': {
        'gridcolor': COLORS['border'],
        'linecolor': COLORS['border_light'],
        'tickfont': {'color': COLORS['text_secondary']},
        'title': {'font': {'color': COLORS['text_secondary']}},
        'zerolinecolor': COLORS['border_light'],
    },
    'legend': {
        'bgcolor': 'rgba(0, 0, 0, 0)',
        'bordercolor': 'rgba(0, 0, 0, 0)',
        'borderwidth': 0,
        'font': {'color': COLORS['text_primary'], 'size': 11},
    },
    'colorway': ['#3b82f6', '#ef4444', '#22c55e', '#f59e0b', '#8b5cf6', '#ec4899', '#14b8a6', '#f97316'],
    'margin': {'l': 50, 'r': 30, 't': 50, 'b': 50},
}


def create_empty_figure(message="No data available"):
    """Create an empty figure with a styled message for dark theme."""
    fig = go.Figure()
    fig.add_annotation(
        text=message,
        xref="paper", yref="paper",
        x=0.5, y=0.5,
        showarrow=False,
        font=dict(size=14, color=COLORS['text_secondary']),
    )
    fig.update_layout(**DARK_LAYOUT)
    fig.update_layout(
        xaxis=dict(showgrid=False, showticklabels=False, zeroline=False),
        yaxis=dict(showgrid=False, showticklabels=False, zeroline=False),
    )
    return fig


# Common input styles for dark theme
INPUT_STYLE = {
    'width': '70px',
    'minWidth': '70px',
    'backgroundColor': COLORS['bg_secondary'],
    'border': f"1px solid {COLORS['border_light']}",
    'borderRadius': '4px',
    'color': COLORS['text_primary'],
    'padding': '8px 10px',
    'fontSize': '12px',
}

DROPDOWN_STYLE_WIDE = {'width': '280px'}
DROPDOWN_STYLE_MEDIUM = {'width': '160px'}

# Shared cluster color palette
CLUSTER_COLORS = ['#3b82f6', '#ef4444', '#22c55e', '#f59e0b', '#8b5cf6', '#ec4899', '#14b8a6', '#f97316']
