"""Dash callbacks for the Predict Removal tab.

Provides two ML models — Ridge Regression and Random Forest — trained on
categorical (Wafer, Pad, Slurry, Conditioner) and numerical (Pressure PSI,
Polish Time) features to predict wafer removal in Angstroms.
"""

import base64
import pickle

import dash
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from dash import Input, Output, State, html
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import RidgeCV
from sklearn.model_selection import KFold, cross_val_predict, cross_val_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from dashboard.constants import (
    PREDICTION_CATEGORICAL_FEATURES,
    PREDICTION_NUMERICAL_FEATURES,
    PREDICTION_TARGET,
)
from dashboard.plotly_theme import CLUSTER_COLORS, DARK_LAYOUT, create_empty_figure
from desktop.theme import COLORS

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_MIN_SAMPLES = 5  # absolute minimum to attempt training


def _prepare_data(data_manager):
    """Return (df, cat_options) for rows with valid Removal > 0.

    Raises ValueError when insufficient data is available.
    """
    df = data_manager.get_all_data()
    if df.empty:
        raise ValueError("No data loaded.")

    required = PREDICTION_CATEGORICAL_FEATURES + PREDICTION_NUMERICAL_FEATURES + [PREDICTION_TARGET, 'File Name']
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Missing columns: {', '.join(missing)}")

    df = df[required].copy()
    df = df[df[PREDICTION_TARGET] > 0].reset_index(drop=True)

    if len(df) < _MIN_SAMPLES:
        raise ValueError(
            f"Only {len(df)} file(s) have Removal data. "
            f"Need at least {_MIN_SAMPLES}."
        )

    # Fill empty categorical strings with 'Unknown'
    for col in PREDICTION_CATEGORICAL_FEATURES:
        df[col] = df[col].fillna('Unknown').replace('', 'Unknown')

    cat_options = {}
    for col in PREDICTION_CATEGORICAL_FEATURES:
        vals = sorted(df[col].unique())
        cat_options[col] = [{'label': v, 'value': v} for v in vals]

    return df, cat_options


def _build_pipeline(model_type, add_interaction=False):
    """Build an unfitted sklearn Pipeline for the given model type."""
    num_cols = list(PREDICTION_NUMERICAL_FEATURES)
    if add_interaction:
        num_cols = num_cols + ['P_x_T']

    preprocessor = ColumnTransformer(
        transformers=[
            ('num', StandardScaler(), num_cols),
            ('cat', OneHotEncoder(handle_unknown='ignore', sparse_output=False),
             PREDICTION_CATEGORICAL_FEATURES),
        ],
        remainder='drop',
    )

    if model_type == 'ridge':
        estimator = RidgeCV(alphas=np.logspace(-3, 3, 50))
    else:
        estimator = RandomForestRegressor(
            n_estimators=100,
            min_samples_leaf=3,
            random_state=42,
            oob_score=True,
        )

    return Pipeline([
        ('preprocessor', preprocessor),
        ('model', estimator),
    ])


def _add_interaction(df):
    """Add P_x_T = Pressure PSI * Polish Time interaction column."""
    df = df.copy()
    df['P_x_T'] = df['Pressure PSI'] * df['Polish Time']
    return df


def _cross_validate(pipeline, X, y):
    """Run 5-fold cross-validation, return (y_pred_cv, r2, rmse, mae)."""
    cv = KFold(n_splits=min(5, len(y)), shuffle=True, random_state=42)
    y_pred_cv = cross_val_predict(pipeline, X, y, cv=cv)
    r2_scores = cross_val_score(pipeline, X, y, cv=cv, scoring='r2')
    neg_mse = cross_val_score(pipeline, X, y, cv=cv, scoring='neg_mean_squared_error')
    neg_mae = cross_val_score(pipeline, X, y, cv=cv, scoring='neg_mean_absolute_error')
    r2 = float(np.mean(r2_scores))
    rmse = float(np.sqrt(-np.mean(neg_mse)))
    mae = float(-np.mean(neg_mae))
    return y_pred_cv, r2, rmse, mae


# ---------------------------------------------------------------------------
# Figure builders
# ---------------------------------------------------------------------------

def _fig_pred_vs_actual(y_true, y_pred, file_names, model_label=''):
    """Scatter of predicted vs actual with 45-degree line."""
    fig = go.Figure()
    residuals = y_pred - y_true
    abs_res = np.abs(residuals)

    fig.add_trace(go.Scatter(
        x=y_true, y=y_pred,
        mode='markers',
        marker=dict(
            size=9,
            color=abs_res,
            colorscale='Bluered',
            showscale=True,
            colorbar=dict(title='|Error|', tickfont=dict(color=COLORS['text_secondary'])),
            line=dict(width=1, color=COLORS['border_light']),
        ),
        text=file_names,
        customdata=np.column_stack([residuals]),
        hovertemplate=(
            '<b>%{text}</b><br>'
            'Actual: %{x:,.0f} \u00c5<br>'
            'Predicted: %{y:,.0f} \u00c5<br>'
            'Error: %{customdata[0]:,.0f} \u00c5<extra></extra>'
        ),
        name=model_label or 'Predictions',
    ))

    # 45-degree reference line
    all_vals = np.concatenate([y_true, y_pred])
    lo, hi = float(np.min(all_vals)), float(np.max(all_vals))
    margin = (hi - lo) * 0.05
    fig.add_trace(go.Scatter(
        x=[lo - margin, hi + margin],
        y=[lo - margin, hi + margin],
        mode='lines',
        line=dict(dash='dash', color=COLORS['text_secondary'], width=1),
        showlegend=False,
        hoverinfo='skip',
    ))

    fig.update_layout(**DARK_LAYOUT)
    fig.update_layout(
        title='Predicted vs Actual',
        xaxis_title='Actual Removal (\u00c5)',
        yaxis_title='Predicted Removal (\u00c5)',
        showlegend=False,
    )
    return fig


def _fig_importance(pipeline, feature_names, model_type):
    """Horizontal bar chart of feature importance / coefficients."""
    fig = go.Figure()

    if model_type == 'ridge':
        coefs = pipeline.named_steps['model'].coef_
        importance = coefs
        labels = feature_names
        # Sort by absolute value
        order = np.argsort(np.abs(importance))
        importance = importance[order]
        labels = [labels[i] for i in order]
        colors = [COLORS['accent'] if v >= 0 else '#ef4444' for v in importance]
        fig.add_trace(go.Bar(
            x=importance, y=labels, orientation='h',
            marker_color=colors,
            hovertemplate='%{y}: %{x:.3f}<extra></extra>',
        ))
        fig.update_layout(title='Ridge Coefficients')
    else:
        importance = pipeline.named_steps['model'].feature_importances_
        labels = feature_names
        order = np.argsort(importance)
        importance = importance[order]
        labels = [labels[i] for i in order]
        fig.add_trace(go.Bar(
            x=importance, y=labels, orientation='h',
            marker_color=COLORS['accent'],
            hovertemplate='%{y}: %{x:.4f}<extra></extra>',
        ))
        fig.update_layout(title='Feature Importance')

    fig.update_layout(**DARK_LAYOUT)
    fig.update_layout(
        xaxis_title='Importance' if model_type != 'ridge' else 'Coefficient',
        margin=dict(l=140, r=30, t=50, b=50),
    )
    return fig


def _fig_residuals(y_true, y_pred, file_names):
    """Residuals vs predicted scatter with zero line."""
    residuals = y_true - y_pred
    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=y_pred, y=residuals,
        mode='markers',
        marker=dict(size=9, color=COLORS['accent'],
                    line=dict(width=1, color=COLORS['border_light'])),
        text=file_names,
        hovertemplate=(
            '<b>%{text}</b><br>'
            'Predicted: %{x:,.0f} \u00c5<br>'
            'Residual: %{y:,.0f} \u00c5<extra></extra>'
        ),
    ))

    # Zero line
    fig.add_hline(y=0, line_dash='dash', line_color=COLORS['text_secondary'], line_width=1)

    fig.update_layout(**DARK_LAYOUT)
    fig.update_layout(
        title='Residuals vs Predicted',
        xaxis_title='Predicted Removal (\u00c5)',
        yaxis_title='Residual (\u00c5)',
        showlegend=False,
    )
    return fig


def _fig_residual_hist(y_true, y_pred):
    """Histogram of residuals."""
    residuals = y_true - y_pred
    fig = go.Figure()

    fig.add_trace(go.Histogram(
        x=residuals,
        nbinsx=max(8, len(residuals) // 4),
        marker_color=COLORS['accent'],
        marker_line=dict(color=COLORS['border_light'], width=1),
        opacity=0.85,
        hovertemplate='Range: %{x}<br>Count: %{y}<extra></extra>',
    ))

    mean_r = float(np.mean(residuals))
    std_r = float(np.std(residuals))

    fig.add_annotation(
        text=f"Mean: {mean_r:,.0f}  Std: {std_r:,.0f}",
        xref="paper", yref="paper", x=0.02, y=1.0,
        xanchor='left', yanchor='top',
        showarrow=False,
        font=dict(size=11, color=COLORS['text_secondary']),
        bgcolor=COLORS['bg_secondary'],
        bordercolor=COLORS['border_light'],
        borderwidth=1, borderpad=4,
    )

    fig.update_layout(**DARK_LAYOUT)
    fig.update_layout(
        title='Residual Distribution',
        xaxis_title='Residual (\u00c5)',
        yaxis_title='Count',
        showlegend=False,
    )
    return fig


def _get_feature_names(pipeline):
    """Extract feature names from a fitted ColumnTransformer."""
    ct = pipeline.named_steps['preprocessor']
    names = []
    for name, transformer, columns in ct.transformers_:
        if name == 'remainder':
            continue
        if hasattr(transformer, 'get_feature_names_out'):
            names.extend(transformer.get_feature_names_out())
        else:
            names.extend(columns)
    return [str(n) for n in names]


def _serialize_pipeline(pipeline):
    """Pickle + base64-encode a fitted pipeline for dcc.Store."""
    return base64.b64encode(pickle.dumps(pipeline)).decode('utf-8')


def _deserialize_pipeline(b64_str):
    """Decode a base64 pipeline string back to a fitted pipeline."""
    return pickle.loads(base64.b64decode(b64_str))


def _build_warning(df):
    """Build a data quality warning message (or empty string)."""
    warnings = []
    n = len(df)
    if n < 20:
        warnings.append(
            f"Only {n} files have Removal data. Model accuracy may be limited."
        )
    for col in PREDICTION_CATEGORICAL_FEATURES:
        counts = df[col].value_counts()
        singles = counts[counts == 1].index.tolist()
        if singles:
            warnings.append(
                f"{col} has single-sample categories: {', '.join(str(s) for s in singles)}."
            )
    for col in PREDICTION_NUMERICAL_FEATURES:
        if df[col].nunique() <= 1:
            warnings.append(
                f"{col} is constant across all files — model cannot learn its effect."
            )
    return '  '.join(warnings)


# ---------------------------------------------------------------------------
# Callback registration
# ---------------------------------------------------------------------------

def register_prediction_callbacks(app, data_manager):
    """Register all callbacks for the Predict Removal tab."""

    # == Callback 1: Train model ============================================
    @app.callback(
        [Output('pred-vs-actual', 'figure'),
         Output('pred-importance', 'figure'),
         Output('pred-residual', 'figure'),
         Output('pred-residual-hist', 'figure'),
         Output('pred-n-files', 'children'),
         Output('pred-r2', 'children'),
         Output('pred-rmse', 'children'),
         Output('pred-mae', 'children'),
         Output('pred-warning', 'children'),
         Output('pred-warning', 'style'),
         Output('pred-model-store', 'data'),
         Output('pred-wafer', 'options'),
         Output('pred-pad', 'options'),
         Output('pred-slurry', 'options'),
         Output('pred-conditioner', 'options'),
         Output('pred-input-container', 'style'),
         Output('pred-diagnostics-container', 'style'),
         Output('pred-result', 'children', allow_duplicate=True)],
        Input('pred-train-btn', 'n_clicks'),
        State('pred-model-select', 'value'),
        prevent_initial_call=True,
    )
    def train_model(_n_clicks, model_type):
        n_outputs = 18
        empty = create_empty_figure
        no_opts = []
        hide = {'display': 'none'}
        warn_hide = {'display': 'none'}

        try:
            df, cat_options = _prepare_data(data_manager)
        except ValueError as exc:
            msg = str(exc)
            return (
                empty(msg), empty(msg), empty(msg), empty(msg),
                '0 files', 'R\u00b2 = --', 'RMSE = --', 'MAE = --',
                msg,
                {'display': 'block', 'color': '#f59e0b', 'fontSize': '12px',
                 'padding': '8px 0'},
                None,
                no_opts, no_opts, no_opts, no_opts,
                hide, hide,
                html.P(msg, style={'color': '#ef4444', 'fontSize': '13px'}),
            )

        model_type = model_type or 'ridge'
        is_ridge = model_type == 'ridge'
        use_interaction = is_ridge

        train_df = _add_interaction(df) if use_interaction else df.copy()
        feature_cols = list(PREDICTION_NUMERICAL_FEATURES) + (
            ['P_x_T'] if use_interaction else []
        ) + list(PREDICTION_CATEGORICAL_FEATURES)
        X = train_df[feature_cols]
        y = train_df[PREDICTION_TARGET].values

        pipeline = _build_pipeline(model_type, add_interaction=use_interaction)
        pipeline.fit(X, y)

        y_pred_cv, r2, rmse, mae = _cross_validate(
            _build_pipeline(model_type, add_interaction=use_interaction), X, y
        )

        file_names = df['File Name'].values

        fig_pva = _fig_pred_vs_actual(y, y_pred_cv, file_names)
        feat_names = _get_feature_names(pipeline)
        fig_imp = _fig_importance(pipeline, feat_names, model_type)
        fig_res = _fig_residuals(y, y_pred_cv, file_names)
        fig_hist = _fig_residual_hist(y, y_pred_cv)

        warning_text = _build_warning(df)
        warn_style = (
            {'display': 'block', 'color': '#f59e0b', 'fontSize': '12px',
             'padding': '8px 0'}
            if warning_text else warn_hide
        )

        store = {
            'model_bytes': _serialize_pipeline(pipeline),
            'model_type': model_type,
            'metrics': {'r2': r2, 'rmse': rmse, 'mae': mae, 'n_train': len(y)},
        }

        model_label = 'Ridge Regression' if is_ridge else 'Random Forest'
        ready_msg = html.P(
            f"Model trained. Select a configuration above and click Predict.",
            style={'color': COLORS['text_secondary'], 'fontSize': '13px'},
        )

        show = {'display': 'block'}
        show_grid = {'display': 'grid', 'gridTemplateColumns': '1fr 1fr',
                     'gap': '16px', 'marginTop': '16px'}

        return (
            fig_pva, fig_imp, fig_res, fig_hist,
            f"{len(y)} files",
            f"R\u00b2 = {r2:.3f}",
            f"RMSE = {rmse:,.0f} \u00c5",
            f"MAE = {mae:,.0f} \u00c5",
            warning_text, warn_style,
            store,
            cat_options.get('Wafer', []),
            cat_options.get('Pad', []),
            cat_options.get('Slurry', []),
            cat_options.get('Conditioner', []),
            show, show_grid,
            ready_msg,
        )

    # == Callback 2: Predict removal ========================================
    @app.callback(
        Output('pred-result', 'children'),
        Input('pred-predict-btn', 'n_clicks'),
        [State('pred-model-store', 'data'),
         State('pred-wafer', 'value'),
         State('pred-pad', 'value'),
         State('pred-slurry', 'value'),
         State('pred-conditioner', 'value'),
         State('pred-pressure', 'value'),
         State('pred-polish-time', 'value')],
        prevent_initial_call=True,
    )
    def predict_removal(_n, model_data, wafer, pad, slurry, conditioner,
                        pressure, polish_time):
        if model_data is None:
            return html.P("Train a model first.",
                          style={'color': COLORS['text_secondary']})

        # Validate inputs
        missing = []
        if not wafer:
            missing.append('Wafer')
        if not pad:
            missing.append('Pad')
        if not slurry:
            missing.append('Slurry')
        if not conditioner:
            missing.append('Conditioner')
        try:
            pressure = float(pressure)
        except (TypeError, ValueError):
            missing.append('Pressure PSI')
        try:
            polish_time = float(polish_time)
        except (TypeError, ValueError):
            missing.append('Polish Time')

        if missing:
            return html.P(
                f"Please fill in: {', '.join(missing)}",
                style={'color': '#ef4444', 'fontSize': '13px'},
            )

        pipeline = _deserialize_pipeline(model_data['model_bytes'])
        model_type = model_data['model_type']
        metrics = model_data['metrics']

        row = {
            'Pressure PSI': pressure,
            'Polish Time': polish_time,
            'Wafer': wafer,
            'Pad': pad,
            'Slurry': slurry,
            'Conditioner': conditioner,
        }
        if model_type == 'ridge':
            row['P_x_T'] = pressure * polish_time

        X_new = pd.DataFrame([row])

        prediction = float(pipeline.predict(X_new)[0])

        # Uncertainty estimate
        if model_type == 'rf':
            tree_preds = np.array([
                t.predict(pipeline.named_steps['preprocessor'].transform(X_new))
                for t in pipeline.named_steps['model'].estimators_
            ])
            uncertainty = float(np.std(tree_preds))
        else:
            uncertainty = metrics.get('rmse', 0)

        # Clamp negative predictions
        clamped = prediction < 0
        prediction = max(0, prediction)

        # Tooltip text varies by model type
        if model_type == 'rf':
            uncertainty_tip = (
                'Spread (standard deviation) of predictions across individual '
                'trees in the forest. Wider spread means less agreement among trees.\n'
                '\u03c3 = \u221a(\u03a3(\u0177\u209c \u2212 \u0233_pred)\u00b2 / T)\n'
                '\u0177\u209c = prediction from tree t, \u0233_pred = mean prediction, T = number of trees'
            )
            model_tip = (
                'Ensemble of decision trees \u2014 each tree votes on the prediction. '
                'Captures non-linear relationships. Less interpretable but often '
                'more accurate on complex data.'
            )
        else:
            uncertainty_tip = (
                'Based on RMSE (Root Mean Squared Error) from cross-validation. '
                'Represents the model\u2019s average prediction error on held-out data.\n'
                'RMSE = \u221a(\u03a3(y\u1d62 \u2212 \u0177\u1d62)\u00b2 / n)\n'
                'y\u1d62 = actual, \u0177\u1d62 = predicted, n = number of samples'
            )
            model_tip = (
                'Linear regression with L2 regularization \u2014 fits a straight-line '
                'relationship with a penalty to prevent overfitting. Interpretable '
                'and stable, best when relationships are roughly linear.'
            )

        result_children = [
            html.Span(
                f"Predicted Removal: {prediction:,.0f} \u00c5",
                style={'fontSize': '18px', 'fontWeight': '600',
                       'color': COLORS['text_primary']},
            ),
            html.Br(),
            html.Span(
                f"Uncertainty: \u00b1 {uncertainty:,.0f} \u00c5",
                title=uncertainty_tip,
                style={'fontSize': '13px', 'color': COLORS['text_secondary']},
            ),
            html.Br(),
            html.Span(
                f"{'Ridge Regression' if model_type == 'ridge' else 'Random Forest'}"
                f" \u2022 R\u00b2 = {metrics['r2']:.3f}"
                f" \u2022 trained on {metrics['n_train']} files",
                title=model_tip,
                style={'fontSize': '11px', 'color': COLORS['text_secondary']},
            ),
        ]
        if clamped:
            result_children.append(html.P(
                "Note: model predicted negative removal — clamped to 0.",
                style={'color': '#f59e0b', 'fontSize': '11px', 'marginTop': '6px'},
            ))

        return html.Div(result_children)
