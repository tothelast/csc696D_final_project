"""Compare Files tab callbacks — time series overlay, PCA clustering,
feature explorer, and PCA selection details."""

import dash
from dash import dcc, html, Input, Output
import plotly.graph_objects as go
from sklearn.decomposition import PCA
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
import pandas as pd
from desktop.theme import COLORS
from dashboard.plotly_theme import DARK_LAYOUT, create_empty_figure, CLUSTER_COLORS
from dashboard.pca_helpers import compute_best_k, build_loadings_figure, build_silhouette_figure, build_scree_figure
from dashboard.constants import (
    ANALYSIS_FEATURES, SELECTION_LABELS,
    CATEGORICAL_FEATURES,
)


def _to_num(val):
    """Convert a text input value to float, or None if empty/invalid."""
    if val is None or val == '':
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def register_compare_callbacks(app, data_manager):
    """Register all Compare Files tab callbacks."""

    # =====================================================================
    # Multi-file Time Series
    # =====================================================================

    @app.callback(
        Output('ts-graph', 'figure'),
        [Input('ts-metric', 'value'),
         Input('ts-xmin', 'value'),
         Input('ts-xmax', 'value'),
         Input('ts-ymin', 'value'),
         Input('ts-ymax', 'value'),
         Input('multi-file-selector', 'value'),
         Input('analysis-tabs', 'value'),
         Input('ts-dblclick-trigger', 'data')]
    )
    def update_timeseries(metric, x_min, x_max, y_min, y_max, selected_files, tab, _trigger):
        """Update multi-file time series comparison chart."""
        if tab != 'multi-file':
            return dash.no_update

        df = data_manager.get_all_data()
        if df.empty:
            return create_empty_figure("No data loaded. Add files in the Project page first.")

        # Handle file selection: empty list means no files selected
        if selected_files is not None and len(selected_files) == 0:
            return create_empty_figure("No files selected. Use the dropdown above to select files.")

        if selected_files:
            df = df[df['File Name'].isin(selected_files)]

        if df.empty:
            return create_empty_figure("No matching files found.")

        fig = go.Figure()
        files_to_plot = df['File Name'].tolist()[:20]

        for fname in files_to_plot:
            file_df = data_manager.get_file_data(fname)
            if file_df is not None and metric in file_df.columns:
                if 'time (s)' in file_df.columns:
                    fig.add_trace(go.Scatter(
                        x=file_df['time (s)'],
                        y=file_df[metric],
                        mode='lines',
                        name=fname,
                        opacity=0.8,
                        hovertemplate='%{y:.4f}<extra>%{fullData.name}</extra>'
                    ))

        if len(fig.data) == 0:
            return create_empty_figure(f"Metric '{metric}' not available in selected files.")

        # Apply dark theme layout
        fig.update_layout(**DARK_LAYOUT)

        # Parse text inputs to numbers (inputs are type='text' to avoid
        # browser NaN issues when clearing number inputs via callbacks)
        nx_min, nx_max = _to_num(x_min), _to_num(x_max)
        ny_min, ny_max = _to_num(y_min), _to_num(y_max)

        if nx_min is not None and nx_max is not None:
            fig.update_xaxes(range=[nx_min, nx_max], autorange=False)
        if ny_min is not None and ny_max is not None:
            fig.update_yaxes(range=[ny_min, ny_max], autorange=False)

        # Additional layout options - legend below graph to avoid modebar overlap
        fig.update_layout(
            xaxis_title="Time (s)",
            yaxis_title=metric,
            margin=dict(l=50, r=20, t=10, b=140),
            legend=dict(
                orientation="h",
                yanchor="top",
                y=-0.22,
                xanchor="left",
                x=0,
                font=dict(size=10),
                bgcolor='rgba(42, 42, 42, 0.95)',
                bordercolor=COLORS['border_light'],
                borderwidth=1
            ),
            hovermode='x unified'
        )
        return fig

    # =====================================================================
    # PCA / Clustering helpers
    # =====================================================================

    def _prepare_cluster_pca_data(selected_files, k, selected_features=None):
        """Shared data preparation for PCA Clustering and Feature Explorer.

        Uses the explicit ANALYSIS_FEATURES list (or a user-selected subset)
        to ensure only meaningful features are included.

        Returns (df, pca_df, explained_var_full, pca_model, feature_names,
                 scaler, X_scaled).
        Raises ValueError with a user-friendly message on insufficient data.
        """
        df = data_manager.get_all_data()
        if df.empty:
            raise ValueError("No data loaded. Add files in the Project page first.")

        if selected_files is not None and len(selected_files) == 0:
            raise ValueError("No files selected. Use the dropdown above to select files.")

        if selected_files:
            df = df[df['File Name'].isin(selected_files)]

        if len(df) < 3:
            raise ValueError("Need at least 3 files for PCA clustering.")

        # Use selected features or fall back to all analysis features
        base_features = selected_features if selected_features else ANALYSIS_FEATURES
        available = [f for f in base_features if f in df.columns]
        X = df[available].dropna(axis=1)
        feature_names = X.columns.tolist()
        if len(feature_names) < 2:
            raise ValueError("Insufficient numeric features for analysis (need at least 2).")

        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)

        # K-Means
        n_clusters = min(k, len(df))
        kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
        df = df.copy()
        df['Cluster'] = kmeans.fit_predict(X_scaled).astype(str)

        # PCA — fit on all components for scree plot, use first 2 for scatter
        n_components = min(len(feature_names), len(df))
        pca = PCA(n_components=n_components)
        all_components = pca.fit_transform(X_scaled)
        explained_var_full = pca.explained_variance_ratio_

        pca_df = pd.DataFrame({'PC1': all_components[:, 0], 'PC2': all_components[:, 1] if n_components >= 2 else 0.0})
        pca_df['File Name'] = df['File Name'].values
        pca_df['Cluster'] = df['Cluster'].values

        return df, pca_df, explained_var_full, pca, feature_names, scaler, X_scaled

    # =====================================================================
    # PCA Clustering callback
    # =====================================================================

    @app.callback(
        [Output('pca-graph', 'figure'),
         Output('pca-analysis-store', 'data'),
         Output('pca-loadings-graph', 'figure'),
         Output('silhouette-graph', 'figure'),
         Output('scree-graph', 'figure'),
         Output('pca-k-badge', 'children'),
         Output('pca-variance-badge', 'children')],
        [Input('pca-feature-selector', 'value'),
         Input('pca-color', 'value'),
         Input('multi-file-selector', 'value'),
         Input('analysis-tabs', 'value')]
    )
    def update_pca_clustering(sel_features, color_by, selected_files, tab):
        """Update PCA projection colored by auto-K-Means clusters or a continuous metric.

        Also outputs:
          - pca-analysis-store: cached DataFrame (JSON) for the selection callback
          - pca-loadings-graph: horizontal bar chart of PCA component loadings
          - silhouette-graph: silhouette score vs K
          - scree-graph: explained variance per component
          - pca-k-badge: auto-selected K value
        """
        n_out = 7
        empty_loadings = create_empty_figure("No data for loadings")
        empty_diag = create_empty_figure("Insufficient data")
        if tab != 'multi-file':
            return [dash.no_update] * n_out

        # Validate feature selection
        features = sel_features if sel_features else None
        if sel_features is not None and len(sel_features) == 0:
            msg = "Select at least 1 feature"
            empty = create_empty_figure(msg)
            return empty, None, empty_loadings, empty_diag, empty_diag, "K = --", "Explained: --%"

        if features and len(features) == 1:
            # Single feature: can't do 2-component PCA
            msg = "Select at least 2 features for PCA"
            empty = create_empty_figure(msg)
            return empty, None, empty_loadings, empty_diag, empty_diag, "K = --", "Explained: --%"

        # Step 1: Prepare data with a placeholder k=2 to get X_scaled
        try:
            df, pca_df, explained_var_full, pca_model, feature_names, scaler, X_scaled = (
                _prepare_cluster_pca_data(selected_files, k=2, selected_features=features)
            )
        except ValueError as e:
            empty = create_empty_figure(str(e))
            return empty, None, empty_loadings, empty_diag, empty_diag, "K = --", "Explained: --%"
        except Exception as e:
            empty = create_empty_figure(f"Error: {e}")
            return empty, None, empty_loadings, empty_diag, empty_diag, "K = --", "Explained: --%"

        # Step 2: Auto-K via silhouette score
        k_range = range(2, 9)
        best_k, sil_scores, inertias, valid_ks = compute_best_k(X_scaled, k_range)

        # Step 3: Refit with best_k
        n_clusters = min(best_k, len(df))
        kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
        df = df.copy()
        df['Cluster'] = kmeans.fit_predict(X_scaled).astype(str)
        pca_df['Cluster'] = df['Cluster'].values

        # --- Build store data ---
        store_df = df.copy()
        store_df['PC1'] = pca_df['PC1'].values
        store_df['PC2'] = pca_df['PC2'].values
        store_cols = ['File Name', 'Cluster', 'PC1', 'PC2']
        store_cols += [c for c in ANALYSIS_FEATURES if c in store_df.columns]
        store_cols += [c for c in CATEGORICAL_FEATURES if c in store_df.columns]
        store_records = store_df[store_cols].to_dict('records')
        store_data = {
            'rows': store_records,
            'scaler_mean': dict(zip(feature_names, scaler.mean_.tolist())),
            'scaler_std': dict(zip(feature_names, scaler.scale_.tolist())),
        }

        # --- Build rich hover data ---
        HOVER_COLS = ['File Name', 'Cluster', 'COF', 'Fy', 'Fz', 'Mean Temp', 'Removal', 'WIWNU']
        hover_template = (
            '<b>%{customdata[0]}</b><br>'
            'Cluster: %{customdata[1]}<br>'
            'PC1: %{x:.3f} | PC2: %{y:.3f}<br>'
            '<br>'
            'COF: %{customdata[2]:.4f}<br>'
            'Fy: %{customdata[3]:.4f} lbf<br>'
            'Fz: %{customdata[4]:.4f} lbf<br>'
            'Mean Temp: %{customdata[5]:.2f}\u00b0C<br>'
            'Removal (\u00c5): %{customdata[6]:.1f}<br>'
            'WIWNU: %{customdata[7]:.2f}%'
            '<extra></extra>'
        )
        for col in HOVER_COLS:
            if col not in pca_df.columns and col in df.columns:
                pca_df[col] = df[col].values

        # --- Build PCA scatter figure ---
        fig = go.Figure()
        explained_var_2d = explained_var_full[:2]

        if color_by and color_by != 'cluster' and color_by in df.columns:
            pca_df[color_by] = df[color_by].values
            fig.add_trace(go.Scatter(
                x=pca_df['PC1'], y=pca_df['PC2'],
                mode='markers',
                marker=dict(
                    size=10,
                    color=pca_df[color_by],
                    colorscale='Viridis',
                    showscale=True,
                    colorbar=dict(
                        title=dict(text=SELECTION_LABELS.get(color_by, color_by), font=dict(color=COLORS['text_primary'])),
                        tickfont=dict(color=COLORS['text_secondary']),
                        bgcolor=COLORS['bg_secondary'],
                        bordercolor=COLORS['border']
                    ),
                    line=dict(width=1, color=COLORS['bg_tertiary'])
                ),
                text=pca_df['File Name'],
                customdata=pca_df[HOVER_COLS].values,
                hovertemplate=hover_template
            ))
        else:
            for i, cluster in enumerate(sorted(pca_df['Cluster'].unique())):
                cluster_df = pca_df[pca_df['Cluster'] == cluster]
                fig.add_trace(go.Scatter(
                    x=cluster_df['PC1'], y=cluster_df['PC2'],
                    mode='markers',
                    name=f'Cluster {cluster}',
                    marker=dict(
                        size=10,
                        color=CLUSTER_COLORS[i % len(CLUSTER_COLORS)],
                        line=dict(width=1, color=COLORS['bg_tertiary'])
                    ),
                    text=cluster_df['File Name'],
                    customdata=cluster_df[HOVER_COLS].values,
                    hovertemplate=hover_template
                ))

        fig.update_layout(**DARK_LAYOUT)
        fig.update_layout(
            xaxis_title=f"PC1 ({explained_var_2d[0]*100:.1f}%)",
            yaxis_title=f"PC2 ({explained_var_2d[1]*100:.1f}%)" if len(explained_var_2d) > 1 else "PC2",
            margin=dict(l=50, r=20, t=50, b=50),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0, font=dict(size=11)),
            dragmode='select'
        )

        # --- Build diagnostic figures ---
        loadings_fig = build_loadings_figure(pca_model, feature_names, explained_var_2d)

        if sil_scores:
            sil_fig = build_silhouette_figure(valid_ks, sil_scores, best_k)
        else:
            sil_fig = create_empty_figure("Need 3+ files for silhouette analysis")

        scree_fig = build_scree_figure(explained_var_full)

        k_badge = f"K = {best_k}"
        total_var = sum(explained_var_2d) * 100
        variance_badge = f"Explained: {total_var:.1f}%"

        return fig, store_data, loadings_fig, sil_fig, scree_fig, k_badge, variance_badge


    # =====================================================================
    # Feature Explorer
    # =====================================================================

    @app.callback(
        Output('explorer-graph', 'figure'),
        [Input('pca-feature-selector', 'value'),
         Input('explorer-x', 'value'),
         Input('explorer-y', 'value'),
         Input('multi-file-selector', 'value'),
         Input('analysis-tabs', 'value')]
    )
    def update_feature_explorer(sel_features, x_axis, y_axis, selected_files, tab):
        """Scatter plot of raw features colored by auto-K cluster assignment."""
        if tab != 'multi-file':
            return dash.no_update

        features = sel_features if sel_features else None

        try:
            df, _, _, _, _, _, X_scaled = _prepare_cluster_pca_data(selected_files, k=2, selected_features=features)
        except ValueError as e:
            return create_empty_figure(str(e))
        except Exception as e:
            return create_empty_figure(f"Error: {e}")

        # Auto-K for cluster coloring
        best_k, _, _, _ = compute_best_k(X_scaled)
        n_clusters = min(best_k, len(df))
        kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
        df = df.copy()
        df['Cluster'] = kmeans.fit_predict(X_scaled).astype(str)

        if x_axis not in df.columns or y_axis not in df.columns:
            return create_empty_figure(f"Column '{x_axis}' or '{y_axis}' not found in data.")

        fig = go.Figure()
        for i, cluster in enumerate(sorted(df['Cluster'].unique())):
            cluster_df = df[df['Cluster'] == cluster]
            fig.add_trace(go.Scatter(
                x=cluster_df[x_axis], y=cluster_df[y_axis],
                mode='markers',
                name=f'Cluster {cluster}',
                marker=dict(
                    size=10,
                    color=CLUSTER_COLORS[i % len(CLUSTER_COLORS)],
                    line=dict(width=1, color=COLORS['bg_tertiary'])
                ),
                text=cluster_df['File Name'],
                hovertemplate='<b>%{text}</b><br>' + f'{SELECTION_LABELS.get(x_axis, x_axis)}: ' + '%{x:.4f}<br>' + f'{SELECTION_LABELS.get(y_axis, y_axis)}: ' + '%{y:.4f}<extra></extra>'
            ))

        fig.update_layout(**DARK_LAYOUT)
        fig.update_layout(
            xaxis_title=SELECTION_LABELS.get(x_axis, x_axis),
            yaxis_title=SELECTION_LABELS.get(y_axis, y_axis),
            margin=dict(l=50, r=20, t=50, b=50),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0, font=dict(size=11))
        )
        return fig

    # =====================================================================
    # PCA Selection Details (lasso / box select)
    # =====================================================================

    @app.callback(
        [Output('pca-selection-panel', 'style'),
         Output('pca-selection-header', 'children'),
         Output('pca-selection-info', 'children')],
        [Input('pca-graph', 'selectedData'),
         Input('pca-analysis-store', 'data')]
    )
    def update_pca_selection(selected_data, store_data):
        """Display z-scored feature bar chart and categorical breakdown for selected files."""
        panel_hidden = {'display': 'none'}

        if not selected_data or not store_data:
            return panel_hidden, [], []

        store_rows = store_data.get('rows', [])
        scaler_mean = store_data.get('scaler_mean', {})
        scaler_std = store_data.get('scaler_std', {})

        # Collect file names from selected points via customdata
        selected_names = set()
        for pt in selected_data.get('points', []):
            name = pt.get('customdata')
            if name:
                if isinstance(name, list):
                    name = name[0]
                selected_names.add(name)

        if not selected_names:
            return panel_hidden, [], []

        rows = [r for r in store_rows if r.get('File Name') in selected_names]
        if not rows:
            return panel_hidden, [], []

        sel_df = pd.DataFrame(rows)
        n = len(sel_df)

        # --- Z-Score bar chart — show all features used in PCA (from scaler) ---
        available = [f for f in scaler_mean if f in sel_df.columns]
        raw_means = sel_df[available].apply(pd.to_numeric, errors='coerce').mean()
        z_scores = pd.Series(
            [(raw_means[f] - scaler_mean[f]) / scaler_std[f] if scaler_std.get(f, 0) > 0 else 0.0
             for f in available],
            index=available
        )

        bar_colors = [COLORS['accent'] if v >= 0 else '#ef4444' for v in z_scores.values]
        display_labels = [SELECTION_LABELS.get(f, f) for f in available]

        zscore_height = max(36 * len(available), 200)

        fig = go.Figure(go.Bar(
            x=z_scores.values,
            y=display_labels,
            orientation='h',
            marker_color=bar_colors,
            text=[f'{v:+.2f}\u03c3' for v in z_scores.values],
            textposition='outside',
            textfont=dict(size=11, color=COLORS['text_secondary']),
            hovertemplate='%{y}<br>Z-score: %{x:+.3f}<br>Raw mean: %{customdata:.4f}<extra></extra>',
            customdata=raw_means[available].values,
        ))
        fig.update_layout(**DARK_LAYOUT)

        # --- Categorical breakdown stacked bar chart ---
        cat_cols = [c for c in CATEGORICAL_FEATURES if c in sel_df.columns]
        active_cats = [c for c in cat_cols if sel_df[c].fillna('').ne('').any()]

        # Compute matched height so both charts align
        cat_height = (max(50 * len(active_cats), 80) + 120) if active_cats else 0
        matched_height = max(zscore_height, cat_height, 280)

        fig.update_layout(
            title='Z-Scores vs Dataset Mean',
            margin=dict(l=10, r=60, t=40, b=30),
            height=matched_height,
            xaxis_title='Z-Score (\u03c3 from dataset mean)',
            yaxis=dict(autorange='reversed', automargin=True, tickfont=dict(size=11)),
            xaxis=dict(tickfont=dict(size=10), zeroline=True, zerolinecolor=COLORS['border_light'], zerolinewidth=1.5),
            showlegend=False,
            bargap=0.3,
        )

        # Determine z-score flex basis based on whether categories exist
        zscore_flex = '1 1 55%' if active_cats else '1 1 100%'
        chart_children = [
            html.Div(style={'flex': zscore_flex, 'minWidth': '0'}, children=[
                dcc.Graph(figure=fig, config={'displayModeBar': False}),
            ]),
        ]

        if active_cats:
            sel_df = sel_df.copy()
            for cat in active_cats:
                sel_df[cat] = sel_df[cat].fillna('').apply(lambda v: 'Unset' if v == '' else v)

            cat_fig = go.Figure()

            for cat in active_cats:
                unique_vals = sorted(sel_df[cat].unique())
                for i, val in enumerate(unique_vals):
                    count = (sel_df[cat] == val).sum()
                    pct = count / n * 100 if n > 0 else 0
                    cat_fig.add_trace(go.Bar(
                        y=[cat],
                        x=[count],
                        name=val,
                        orientation='h',
                        marker_color=CLUSTER_COLORS[i % len(CLUSTER_COLORS)],
                        legendgroup=cat,
                        legendgrouptitle_text=cat,
                        text=[f'{count}'] if count > 0 else [''],
                        textposition='inside',
                        textfont=dict(size=11, color='white'),
                        hovertemplate=f'{cat}<br>{val}: {count} ({pct:.0f}%)<extra></extra>',
                    ))

            cat_fig.update_layout(**DARK_LAYOUT)
            cat_fig.update_layout(
                title='Category Breakdown',
                barmode='stack',
                margin=dict(l=10, r=20, t=40, b=80),
                height=matched_height,
                xaxis=dict(
                    title='Count',
                    tickfont=dict(size=10),
                    dtick=max(1, n // 5),
                ),
                yaxis=dict(autorange='reversed', automargin=True, tickfont=dict(size=11)),
                legend=dict(
                    orientation='h', yanchor='top', y=-0.3, xanchor='left', x=0,
                    font=dict(size=11),
                    groupclick='toggleitem',
                    tracegroupgap=20,
                ),
                bargap=0.35,
            )

            chart_children.append(
                html.Div(style={'flex': '1 1 45%', 'minWidth': '0'}, children=[
                    dcc.Graph(figure=cat_fig, config={'displayModeBar': False}),
                ]),
            )

        panel_visible = {'display': 'block'}
        header = html.P(
            f"{n} file{'s' if n != 1 else ''} selected",
            style={'marginBottom': '8px', 'color': COLORS['text_secondary']},
        )
        return panel_visible, header, chart_children