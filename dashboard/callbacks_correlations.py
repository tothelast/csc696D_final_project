"""Correlations tab callbacks — Stribeck, Preston, Arrhenius, and other
correlation graphs with material/equipment filtering."""

import dash
from dash import Input, Output
import plotly.graph_objects as go
import pandas as pd
import numpy as np

from desktop.theme import COLORS
from dashboard.plotly_theme import DARK_LAYOUT, create_empty_figure, CLUSTER_COLORS
from dashboard.constants import CORR_GRAPH_IDS, CORR_GRAPHS


def register_correlation_callbacks(app, data_manager):
    """Register all Correlations tab callbacks."""

    # =====================================================================
    # Correlation helpers
    # =====================================================================

    def _get_group_column(df):
        """Return a Series grouping files by Pressure PSI setpoint."""
        if 'Pressure PSI' in df.columns:
            return df['Pressure PSI'].fillna(0).astype(str) + ' PSI'
        return pd.Series(['Unknown'] * len(df), index=df.index)

    def _apply_material_filters(df, wafer_vals, pad_vals, slurry_vals, conditioner_vals):
        """Filter DataFrame by material/equipment selections.

        Each parameter is a list of selected values (from a multi-select
        dropdown).  ``None`` means "no filter" for that category; an empty
        list ``[]`` means the user explicitly deselected everything, so no
        rows should match.  Within a single category the logic is OR (any
        match); across categories the logic is AND (all must match).
        """
        for col, vals in [('Wafer', wafer_vals), ('Pad', pad_vals),
                          ('Slurry', slurry_vals), ('Conditioner', conditioner_vals)]:
            if vals is not None and len(vals) == 0:
                return df.iloc[0:0]  # empty DataFrame, preserves columns
            if vals and len(vals) > 0 and col in df.columns:
                df = df[df[col].isin(vals)]
        return df

    def _build_corr_figure(df, x_col, y_col, x_label, y_label, transform_x, transform_y, show_lines=True):
        """Build a single correlation figure with grouped scatter + lines."""
        if x_col not in df.columns or y_col not in df.columns:
            return create_empty_figure(f"Missing column: {x_col} or {y_col}")

        work = df.copy()

        # Apply transforms
        if transform_x == 'inv_kelvin':
            # Convert °C to K, then take 1/T
            temp_k = work[x_col] + 273.15
            temp_k = temp_k.replace(0, np.nan)
            work['_x'] = 1.0 / temp_k
        elif transform_x == 'ln':
            vals = work[x_col].replace(0, np.nan)
            work['_x'] = np.log(vals)
        else:
            work['_x'] = work[x_col]

        if transform_y == 'ln':
            vals = work[y_col].replace(0, np.nan)
            work['_y'] = np.log(vals)
        else:
            work['_y'] = work[y_col]

        # Filter out non-positive values when using log axes (log(0) is undefined)
        if transform_x == 'log_axis':
            work = work[work['_x'] > 0]
        if transform_y == 'log_axis':
            work = work[work['_y'] > 0]

        # Drop NaN/inf
        work = work.replace([np.inf, -np.inf], np.nan).dropna(subset=['_x', '_y'])
        if work.empty:
            return create_empty_figure("Insufficient data for this plot")

        fig = go.Figure()
        groups = sorted(work['_group'].unique())

        for i, group in enumerate(groups):
            gdf = work[work['_group'] == group].sort_values('_x')
            color = CLUSTER_COLORS[i % len(CLUSTER_COLORS)]

            opacity = 1.0

            # Truncate long file names for hover readability
            short_names = gdf['File Name'].apply(lambda n: (n[:30] + '\u2026') if len(str(n)) > 30 else n)

            hover_template = (
                '<b>%{customdata[0]}</b><br>'
                f'{x_label}: ' + '%{x:.4f}<br>'
                f'{y_label}: ' + '%{y:.4f}<br>'
                'Wafer: %{customdata[1]}<br>'
                'Pad: %{customdata[2]}<br>'
                'Slurry: %{customdata[3]}<br>'
                'Conditioner: %{customdata[4]}'
                '<extra></extra>'
            )

            customdata = np.column_stack([
                short_names.values,
                gdf['Wafer'].fillna('').values,
                gdf['Pad'].fillna('').values,
                gdf['Slurry'].fillna('').values,
                gdf['Conditioner'].fillna('').values,
            ])

            trace_mode = 'lines+markers' if show_lines else 'markers'

            fig.add_trace(go.Scatter(
                x=gdf['_x'], y=gdf['_y'],
                mode=trace_mode,
                name=str(group),
                marker=dict(size=8, color=color, line=dict(width=1, color=COLORS['bg_tertiary'])),
                line=dict(color=color, width=2),
                opacity=opacity,
                customdata=customdata,
                hovertemplate=hover_template,
            ))

        fig.update_layout(**DARK_LAYOUT)
        fig.update_layout(
            xaxis_title=x_label,
            yaxis_title=y_label,
            margin=dict(l=60, r=20, t=65, b=50),
            legend=dict(
                orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0,
                font=dict(size=11),
            ),
            hovermode='closest',
            hoverlabel=dict(
                bgcolor=COLORS['bg_tertiary'],
                bordercolor=COLORS['border_light'],
                font=dict(size=12, color=COLORS['text_primary']),
                namelength=-1,
            ),
        )

        if transform_x == 'log_axis':
            fig.update_xaxes(type='log', exponentformat='e')
        if transform_y == 'log_axis':
            fig.update_yaxes(type='log', exponentformat='e')

        return fig

    # =====================================================================
    # Correlation Explorer callback
    # =====================================================================

    @app.callback(
        [Output(gid, 'figure') for gid in CORR_GRAPH_IDS],
        [Input('corr-file-selector', 'value'),
         Input('analysis-tabs', 'value'),
         Input('corr-power-density-y', 'value'),
         Input('corr-psi-filter', 'value'),
         Input('corr-filter-wafer', 'value'),
         Input('corr-filter-pad', 'value'),
         Input('corr-filter-slurry', 'value'),
         Input('corr-filter-conditioner', 'value'),
         # Per-graph line toggle inputs (checklist value lists)
         Input('corr-stribeck-lines', 'value'),
         Input('corr-cof-pv-lines', 'value'),
         Input('corr-temp-pv-lines', 'value'),
         Input('corr-arrhenius-lines', 'value'),
         Input('corr-preston-lines', 'value'),
         Input('corr-wiwnu-pv-lines', 'value'),
         Input('corr-power-density-lines', 'value')]
    )
    def update_correlations(selected_files, tab, power_density_y, selected_psi,
                            filter_wafer, filter_pad, filter_slurry, filter_conditioner,
                            lines_stribeck, lines_cof_pv, lines_temp_pv,
                            lines_arrhenius, lines_preston, lines_wiwnu_pv,
                            lines_power_density):
        """Update all 7 correlation graphs."""
        n_graphs = len(CORR_GRAPH_IDS)

        if tab != 'correlations':
            return [dash.no_update] * n_graphs

        df = data_manager.get_all_data()
        if df.empty:
            return [create_empty_figure("No data loaded. Add files in the Project page first.")] * n_graphs

        if selected_files is not None and len(selected_files) == 0:
            return [create_empty_figure("No files selected.")] * n_graphs

        if selected_files:
            df = df[df['File Name'].isin(selected_files)]

        if df.empty:
            return [create_empty_figure("No matching files found.")] * n_graphs

        # Filter by selected PSI values
        if selected_psi is not None and len(selected_psi) == 0:
            return [create_empty_figure("No pressures selected.")] * n_graphs
        if selected_psi:
            if 'Pressure PSI' in df.columns:
                df = df[df['Pressure PSI'].isin(selected_psi)]
            if df.empty:
                return [create_empty_figure("No files match selected pressures.")] * n_graphs

        # Apply material / equipment filters
        df = _apply_material_filters(df, filter_wafer, filter_pad, filter_slurry, filter_conditioner)
        if df.empty:
            return [create_empty_figure("No files match the selected filters.")] * n_graphs

        # Build group column (always by Pressure PSI)
        df = df.copy()
        df['_group'] = _get_group_column(df)

        # Use stored COF·P·V (Power Density) column
        if 'COF.P.V' in df.columns:
            df['Power Density'] = df['COF.P.V']
        else:
            df['Power Density'] = np.nan

        # Per-graph line toggle states (checklist returns ['on'] or [])
        line_toggles = [lines_stribeck, lines_cof_pv, lines_temp_pv,
                        lines_arrhenius, lines_preston, lines_wiwnu_pv]

        figures = []
        for i, (_, x_col, y_col, x_label, y_label, tx, ty) in enumerate(CORR_GRAPHS):
            show_lines = bool(line_toggles[i] and 'on' in line_toggles[i])
            fig = _build_corr_figure(df, x_col, y_col, x_label, y_label, tx, ty, show_lines)
            figures.append(fig)

        # Power Density graph
        y_labels = {'Mean Temp': 'Mean Pad Temp (\u00b0C)', 'Removal Rate': 'Removal Rate (\u00c5/min)',
                    'Var Fz': 'Var Fz', 'Var Fy': 'Var Fy'}
        pd_y_col = power_density_y or 'Mean Temp'
        pd_y_label = y_labels.get(pd_y_col, pd_y_col)
        pd_show_lines = bool(lines_power_density and 'on' in lines_power_density)
        pd_fig = _build_corr_figure(df, 'Power Density', pd_y_col, 'P\u00b7V\u00b7COF (Pa\u00b7m/s)', pd_y_label, None, None, pd_show_lines)
        figures.append(pd_fig)

        return figures
