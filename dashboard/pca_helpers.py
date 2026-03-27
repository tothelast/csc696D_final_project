"""PCA diagnostic chart builders and auto-K selection for Compare Files tab."""

import numpy as np
import plotly.graph_objects as go
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score

from desktop.theme import COLORS
from dashboard.plotly_theme import DARK_LAYOUT, CLUSTER_COLORS


def compute_best_k(X_scaled, k_range=range(2, 9)):
    """Find optimal K via silhouette score across a range of cluster counts.

    Returns (best_k, silhouette_scores, inertias, valid_ks).
    Guards against too-few samples.
    """
    n_samples = len(X_scaled)
    if n_samples < 3:
        return 2, [], [], []

    valid_range = [k for k in k_range if k < n_samples]
    if not valid_range:
        return 2, [], [], []

    silhouette_scores = []
    inertias = []
    for k in valid_range:
        km = KMeans(n_clusters=k, random_state=42, n_init=10)
        labels = km.fit_predict(X_scaled)
        inertias.append(km.inertia_)
        silhouette_scores.append(silhouette_score(X_scaled, labels))

    best_idx = int(np.argmax(silhouette_scores))
    best_k = valid_range[best_idx]
    return best_k, silhouette_scores, inertias, valid_range


def build_loadings_figure(pca_model, feature_names, explained_var):
    """Create a grouped horizontal bar chart showing PCA component loadings."""
    loadings = pca_model.components_.T  # shape: (n_features, 2)
    fig = go.Figure()
    for pc_idx, pc_label in enumerate(['PC1', 'PC2']):
        fig.add_trace(go.Bar(
            y=feature_names,
            x=loadings[:, pc_idx],
            name=f'{pc_label} ({explained_var[pc_idx]*100:.0f}%)',
            orientation='h',
            marker_color=CLUSTER_COLORS[pc_idx],
            opacity=0.85
        ))
    fig.update_layout(**DARK_LAYOUT)
    fig.update_layout(
        barmode='group',
        margin=dict(l=90, r=20, t=10, b=30),
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='left', x=0, font=dict(size=11)),
        xaxis_title='Loading',
        yaxis=dict(autorange='reversed'),
        height=300
    )
    return fig


def build_silhouette_figure(k_range, silhouette_scores, best_k):
    """Line+marker chart of silhouette score vs K with star on best K."""
    fig = go.Figure()
    ks = list(k_range)

    fig.add_trace(go.Scatter(
        x=ks, y=silhouette_scores,
        mode='lines+markers',
        marker=dict(size=8, color=COLORS['accent']),
        line=dict(color=COLORS['accent'], width=2),
        hovertemplate='K=%{x}<br>Silhouette=%{y:.3f}<extra></extra>',
    ))

    # Star marker on best K
    best_idx = ks.index(best_k)
    fig.add_trace(go.Scatter(
        x=[best_k], y=[silhouette_scores[best_idx]],
        mode='markers',
        marker=dict(size=16, color='#f59e0b', symbol='star'),
        showlegend=False,
        hovertemplate=f'Best K={best_k}<br>Silhouette={silhouette_scores[best_idx]:.3f}<extra></extra>',
    ))

    # Score annotation with pixel offset above the star
    fig.add_annotation(
        x=best_k, y=silhouette_scores[best_idx],
        text=f'{silhouette_scores[best_idx]:.3f}',
        showarrow=False,
        yshift=18,
        font=dict(size=11, color='#f59e0b'),
    )

    fig.update_layout(**DARK_LAYOUT)
    fig.update_layout(
        xaxis_title='Number of Clusters (K)',
        yaxis_title='Silhouette Score',
        margin=dict(l=50, r=20, t=30, b=40),
        height=300,
        showlegend=False,
        xaxis=dict(dtick=1),
    )
    return fig


def build_scree_figure(explained_var_full):
    """Bar chart of per-component variance + cumulative line."""
    n = len(explained_var_full)
    pc_labels = [f'PC{i+1}' for i in range(n)]
    var_pct = explained_var_full * 100
    cumulative = np.cumsum(var_pct)

    bar_colors = [COLORS['accent'] if i < 2 else '#707070' for i in range(n)]

    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=pc_labels, y=var_pct,
        marker_color=bar_colors,
        name='Individual',
        hovertemplate='%{x}: %{y:.1f}%<extra></extra>',
    ))

    fig.add_trace(go.Scatter(
        x=pc_labels, y=cumulative,
        mode='lines+markers',
        marker=dict(size=6, color='#22c55e'),
        line=dict(color='#22c55e', width=2),
        name='Cumulative',
        hovertemplate='%{x}: %{y:.1f}% cumulative<extra></extra>',
    ))

    for threshold in [80, 90]:
        fig.add_hline(
            y=threshold,
            line_dash='dash',
            line_color=COLORS['text_secondary'],
            opacity=0.4,
            annotation_text=f'{threshold}%',
            annotation_position='right',
            annotation_font_color=COLORS['text_secondary'],
            annotation_font_size=10,
        )

    fig.update_layout(**DARK_LAYOUT)
    fig.update_layout(
        xaxis_title='Principal Component',
        yaxis_title='Explained Variance (%)',
        margin=dict(l=50, r=40, t=30, b=40),
        height=300,
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='left', x=0, font=dict(size=10)),
        barmode='overlay',
    )
    return fig
