"""Tool functions for the AI agent.

Each function is a thin wrapper around DataManager or AutoMLManager.
The ollama-python library auto-generates JSON schemas from the type
annotations and docstrings.
"""

import json
import logging

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from dashboard.constants import (
    ANALYSIS_FEATURES,
    CATEGORICAL_FEATURES,
    PREDICTION_CATEGORICAL_FEATURES,
    PREDICTION_NUMERICAL_FEATURES,
)
from dashboard.plotly_theme import DARK_LAYOUT, CLUSTER_COLORS
from desktop.theme import COLORS

logger = logging.getLogger(__name__)


class AgentTools:
    """Container for all agent tool functions."""

    def __init__(self, data_manager, automl_manager):
        self.dm = data_manager
        self.ml = automl_manager

    # ------------------------------------------------------------------
    # Data Tools
    # ------------------------------------------------------------------

    def get_dataset_summary(self) -> str:
        """Get an overview of all loaded polishing data including file count, feature ranges, and categorical value counts.

        Returns:
            Summary of loaded dataset as formatted text.
        """
        df = self.dm.get_all_data()
        if df.empty:
            return "No data loaded."

        n_files = len(df)
        has_removal = int((df.get("Removal", pd.Series(dtype=float)) > 0).sum())

        lines = [f"Dataset: {n_files} polishing files, {has_removal} with removal data."]

        for feat in PREDICTION_NUMERICAL_FEATURES:
            if feat in df.columns:
                lines.append(
                    f"  {feat}: {df[feat].min():.2f} – {df[feat].max():.2f} "
                    f"(mean {df[feat].mean():.2f})"
                )

        if "Removal" in df.columns:
            valid = df[df["Removal"] > 0]["Removal"]
            if not valid.empty:
                lines.append(
                    f"  Removal: {valid.min():.0f} – {valid.max():.0f} Å "
                    f"(mean {valid.mean():.0f} Å)"
                )

        for cat in CATEGORICAL_FEATURES:
            if cat in df.columns:
                vals = df[cat].replace("", "Unknown").fillna("Unknown")
                counts = vals.value_counts()
                top = ", ".join(f"{v} ({c})" for v, c in counts.head(5).items())
                lines.append(f"  {cat}: {len(counts)} types — {top}")

        return "\n".join(lines)

    def get_file_details(self, filename: str) -> str:
        """Get detailed metrics for a specific polishing run file.

        Args:
            filename: The .dat filename (e.g. 'run_023.dat').

        Returns:
            Summary metrics and categorical attributes for the file.
        """
        df = self.dm.get_all_data()
        if df.empty:
            return "No data loaded."

        row = df[df["File Name"] == filename]
        if row.empty:
            available = ", ".join(df["File Name"].tolist()[:10])
            return f"File '{filename}' not found. Available: {available}"

        row = row.iloc[0]
        lines = [f"File: {filename}"]

        metric_cols = [
            "COF", "Fz", "Var Fz", "Mean Temp", "Init Temp", "High Temp",
            "Removal", "WIWNU", "Pressure PSI", "Polish Time",
            "Mean Pressure", "Mean Velocity", "P.V", "Removal Rate",
        ]
        for col in metric_cols:
            if col in row.index and pd.notna(row[col]):
                lines.append(f"  {col}: {row[col]:.4g}")

        for cat in CATEGORICAL_FEATURES:
            if cat in row.index:
                lines.append(f"  {cat}: {row[cat] or 'Not set'}")

        return "\n".join(lines)

    def get_feature_statistics(self, feature: str, group_by: str = None) -> str:
        """Get descriptive statistics for a feature, optionally grouped by a categorical.

        Args:
            feature: Column name (e.g. 'COF', 'Removal', 'Mean Temp').
            group_by: Optional categorical to group by ('Wafer', 'Pad', 'Slurry', or 'Conditioner').

        Returns:
            Mean, std, min, max, median, optionally broken down by group.
        """
        df = self.dm.get_all_data()
        if df.empty:
            return "No data loaded."

        if feature not in df.columns:
            available = [c for c in df.columns if c not in ("file_id",)]
            return f"Feature '{feature}' not found. Available: {', '.join(available[:15])}"

        if group_by and group_by in df.columns:
            grouped = df.groupby(group_by)[feature]
            lines = [f"Statistics for {feature} grouped by {group_by}:"]
            for name, group in grouped:
                valid = group.dropna()
                if not valid.empty:
                    lines.append(
                        f"  {name}: mean={valid.mean():.4g}, std={valid.std():.4g}, "
                        f"min={valid.min():.4g}, max={valid.max():.4g}, "
                        f"median={valid.median():.4g}, n={len(valid)}"
                    )
            return "\n".join(lines)

        valid = df[feature].dropna()
        return (
            f"Statistics for {feature} (n={len(valid)}):\n"
            f"  mean={valid.mean():.4g}, std={valid.std():.4g}\n"
            f"  min={valid.min():.4g}, max={valid.max():.4g}\n"
            f"  median={valid.median():.4g}"
        )

    def detect_outliers(self, feature: str) -> str:
        """Find outlier files for a given feature using the IQR method.

        Args:
            feature: Column name to check for outliers (e.g. 'Removal', 'COF').

        Returns:
            List of outlier files with their values and how far they deviate.
        """
        df = self.dm.get_all_data()
        if df.empty:
            return "No data loaded."

        if feature not in df.columns:
            return f"Feature '{feature}' not found."

        valid = df[[feature, "File Name"]].dropna(subset=[feature])
        q1 = valid[feature].quantile(0.25)
        q3 = valid[feature].quantile(0.75)
        iqr = q3 - q1

        if iqr == 0:
            return f"No variation in {feature} — all values are equal."

        lower = q1 - 1.5 * iqr
        upper = q3 + 1.5 * iqr
        outliers = valid[(valid[feature] < lower) | (valid[feature] > upper)]

        if outliers.empty:
            return f"No outliers found for {feature} (IQR method, Q1={q1:.4g}, Q3={q3:.4g})."

        lines = [
            f"Outliers for {feature} (IQR: {iqr:.4g}, bounds: [{lower:.4g}, {upper:.4g}]):"
        ]
        for _, row in outliers.iterrows():
            val = row[feature]
            direction = "above" if val > upper else "below"
            deviation = abs(val - upper) if val > upper else abs(val - lower)
            lines.append(
                f"  {row['File Name']}: {val:.4g} ({direction} by {deviation:.4g})"
            )
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # ML Tools
    # ------------------------------------------------------------------

    def run_automl(self, time_budget: int = 60) -> str:
        """Train and evaluate multiple ML pipelines using AutoML to find the best model.

        Args:
            time_budget: Maximum seconds to search for the best model. Default 60.

        Returns:
            Best model name, top-5 leaderboard, cross-validation metrics, and feature importances.
        """
        try:
            results = self.ml.train(time_budget=time_budget)
        except ValueError as exc:
            return f"Cannot train: {exc}"

        lines = [f"AutoML complete. Best model: {results['best_model']}"]
        lines.append(
            f"Metrics: R²={results['metrics']['r2']:.3f}, "
            f"RMSE={results['metrics']['rmse']:.0f}Å, "
            f"MAE={results['metrics']['mae']:.0f}Å, "
            f"trained on {results['n_train']} files."
        )

        if results["leaderboard"]:
            lines.append("\nLeaderboard:")
            for i, entry in enumerate(results["leaderboard"], 1):
                lines.append(f"  {i}. {entry['model']} — RMSE={entry['rmse']:.0f}Å")

        if results["feature_importances"]:
            sorted_imp = sorted(
                results["feature_importances"].items(), key=lambda x: x[1], reverse=True
            )
            lines.append("\nFeature importances:")
            for name, imp in sorted_imp:
                lines.append(f"  {name}: {imp:.4f}")

        if results["warnings"]:
            lines.append("\nWarnings:")
            for w in results["warnings"]:
                lines.append(f"  - {w}")

        return "\n".join(lines)

    def predict_removal(
        self,
        pressure_psi: float,
        polish_time: float,
        wafer: str,
        pad: str,
        slurry: str,
        conditioner: str,
    ) -> str:
        """Predict material removal for given polishing conditions.

        Args:
            pressure_psi: Down force pressure in PSI.
            polish_time: Polish duration in minutes.
            wafer: Wafer type identifier.
            pad: Pad type identifier.
            slurry: Slurry type identifier.
            conditioner: Conditioner disk type identifier.

        Returns:
            Predicted removal in Angstroms with uncertainty estimate and model info.
        """
        try:
            result = self.ml.predict(
                pressure_psi=pressure_psi,
                polish_time=polish_time,
                wafer=wafer,
                pad=pad,
                slurry=slurry,
                conditioner=conditioner,
            )
        except ValueError as exc:
            return f"Cannot predict: {exc}"

        lines = [
            f"Predicted Removal: {result['prediction']:.0f} Å",
            f"Uncertainty: ±{result['uncertainty']:.0f} Å",
            f"Model: {result['model']} (R²={result['r2']:.3f}, trained on {result['n_train']} files)",
        ]
        if result["clamped"]:
            lines.append("Note: prediction was negative and clamped to 0.")
        return "\n".join(lines)

    def get_model_diagnostics(self) -> str:
        """Get detailed diagnostics for the currently trained model.

        Returns:
            Residual statistics, cross-validation metrics, data quality warnings, and model hyperparameters.
        """
        try:
            diag = self.ml.get_diagnostics()
        except ValueError as exc:
            return f"Cannot get diagnostics: {exc}"

        lines = [
            f"Model: {diag['metrics']['best_model']}",
            f"R²={diag['metrics']['r2']:.3f}, RMSE={diag['metrics']['rmse']:.0f}Å, MAE={diag['metrics']['mae']:.0f}Å",
            f"Trained on {diag['metrics']['n_train']} files.",
            f"\nResiduals: mean={diag['residual_mean']:.1f}, std={diag['residual_std']:.1f}, "
            f"range=[{diag['residual_min']:.1f}, {diag['residual_max']:.1f}]",
            f"\nBest config: {diag['best_config']}",
        ]
        if diag["warnings"]:
            lines.append("\nWarnings:")
            for w in diag["warnings"]:
                lines.append(f"  - {w}")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Chart Tools
    # ------------------------------------------------------------------

    def generate_scatter(
        self,
        x_feature: str,
        y_feature: str,
        color_by: str = None,
        filter_column: str = None,
        filter_value: str = None,
    ) -> dict:
        """Generate a scatter plot of two features from the dataset.

        Args:
            x_feature: Feature name for the x-axis.
            y_feature: Feature name for the y-axis.
            color_by: Optional categorical feature for color coding points.
            filter_column: Optional column name to filter data on.
            filter_value: Optional value to filter for in filter_column.

        Returns:
            Plotly figure as a JSON-serializable dictionary.
        """
        df = self.dm.get_all_data()
        if df.empty:
            return self._empty_fig("No data loaded.")

        if filter_column and filter_value and filter_column in df.columns:
            df = df[df[filter_column] == filter_value]

        fig = go.Figure()
        if color_by and color_by in df.columns:
            for i, (group, group_df) in enumerate(df.groupby(color_by)):
                fig.add_trace(go.Scatter(
                    x=group_df.get(x_feature),
                    y=group_df.get(y_feature),
                    mode="markers",
                    name=str(group),
                    marker=dict(size=9, color=CLUSTER_COLORS[i % len(CLUSTER_COLORS)]),
                    text=group_df.get("File Name"),
                    hovertemplate=f"<b>%{{text}}</b><br>{x_feature}: %{{x:.4g}}<br>{y_feature}: %{{y:.4g}}<extra>{group}</extra>",
                ))
        else:
            fig.add_trace(go.Scatter(
                x=df.get(x_feature),
                y=df.get(y_feature),
                mode="markers",
                marker=dict(size=9, color=COLORS["accent"]),
                text=df.get("File Name"),
                hovertemplate=f"<b>%{{text}}</b><br>{x_feature}: %{{x:.4g}}<br>{y_feature}: %{{y:.4g}}<extra></extra>",
            ))

        fig.update_layout(**DARK_LAYOUT)
        fig.update_layout(
            title=f"{y_feature} vs {x_feature}",
            xaxis_title=x_feature,
            yaxis_title=y_feature,
        )
        return fig.to_plotly_json()

    def generate_distribution(self, feature: str, group_by: str = None) -> dict:
        """Generate a histogram or box plot for a feature.

        Args:
            feature: Feature name to plot.
            group_by: Optional categorical feature for grouped box plot.

        Returns:
            Plotly figure as a JSON-serializable dictionary.
        """
        df = self.dm.get_all_data()
        if df.empty:
            return self._empty_fig("No data loaded.")

        fig = go.Figure()
        if group_by and group_by in df.columns:
            for i, (group, group_df) in enumerate(df.groupby(group_by)):
                fig.add_trace(go.Box(
                    y=group_df.get(feature),
                    name=str(group),
                    marker_color=CLUSTER_COLORS[i % len(CLUSTER_COLORS)],
                ))
            fig.update_layout(title=f"{feature} by {group_by}")
        else:
            fig.add_trace(go.Histogram(
                x=df.get(feature),
                marker_color=COLORS["accent"],
                marker_line=dict(color=COLORS["border_light"], width=1),
                opacity=0.85,
            ))
            fig.update_layout(title=f"Distribution of {feature}")

        fig.update_layout(**DARK_LAYOUT)
        fig.update_layout(yaxis_title="Count" if not group_by else feature)
        return fig.to_plotly_json()

    def generate_bar_chart(self, feature: str, group_by: str) -> dict:
        """Generate a grouped bar chart showing means with error bars.

        Args:
            feature: Numerical feature for the y-axis values.
            group_by: Categorical feature for grouping bars.

        Returns:
            Plotly figure as a JSON-serializable dictionary.
        """
        df = self.dm.get_all_data()
        if df.empty:
            return self._empty_fig("No data loaded.")

        grouped = df.groupby(group_by)[feature]
        means = grouped.mean()
        stds = grouped.std().fillna(0)

        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=means.index.astype(str),
            y=means.values,
            error_y=dict(type="data", array=stds.values, visible=True),
            marker_color=COLORS["accent"],
        ))

        fig.update_layout(**DARK_LAYOUT)
        fig.update_layout(
            title=f"Mean {feature} by {group_by}",
            xaxis_title=group_by,
            yaxis_title=feature,
        )
        return fig.to_plotly_json()

    def generate_correlation_heatmap(self, features: list[str] = None) -> dict:
        """Generate a correlation matrix heatmap for numerical features.

        Args:
            features: Optional list of feature names. Defaults to all numerical analysis features.

        Returns:
            Plotly figure as a JSON-serializable dictionary.
        """
        df = self.dm.get_all_data()
        if df.empty:
            return self._empty_fig("No data loaded.")

        if features is None:
            features = [f for f in ANALYSIS_FEATURES if f in df.columns]

        numeric_df = df[features].select_dtypes(include=[np.number]).dropna(axis=1, how="all")
        corr = numeric_df.corr()

        fig = go.Figure(data=go.Heatmap(
            z=corr.values,
            x=corr.columns.tolist(),
            y=corr.index.tolist(),
            colorscale="RdBu_r",
            zmid=0,
            text=np.round(corr.values, 2),
            texttemplate="%{text}",
            textfont={"size": 10},
        ))

        fig.update_layout(**DARK_LAYOUT)
        fig.update_layout(
            title="Feature Correlation Matrix",
            width=700,
            height=600,
        )
        return fig.to_plotly_json()

    def generate_time_series(self, filename: str, features: list[str]) -> dict:
        """Generate a time-series plot for a specific polishing run file.

        Args:
            filename: The .dat filename.
            features: List of feature names to plot over time (e.g. ['COF', 'IR Temperature']).

        Returns:
            Plotly figure as a JSON-serializable dictionary.
        """
        ts_data = self.dm.get_file_data(filename)
        if ts_data is None:
            return self._empty_fig(f"File '{filename}' not found.")

        fig = go.Figure()
        for i, feat in enumerate(features):
            if feat in ts_data.columns:
                fig.add_trace(go.Scatter(
                    y=ts_data[feat],
                    mode="lines",
                    name=feat,
                    line=dict(color=CLUSTER_COLORS[i % len(CLUSTER_COLORS)]),
                ))

        fig.update_layout(**DARK_LAYOUT)
        fig.update_layout(
            title=f"Time Series: {filename}",
            xaxis_title="Sample",
            yaxis_title="Value",
        )
        return fig.to_plotly_json()

    def generate_model_plots(self) -> list[dict]:
        """Generate all diagnostic plots for the currently trained model.

        Returns:
            List of 4 Plotly figures: predicted vs actual, feature importance,
            residuals vs predicted, and residual distribution.
        """
        try:
            diag = self.ml.get_diagnostics()
        except ValueError:
            empty = self._empty_fig("No model trained.")
            return [empty, empty, empty, empty]

        y_true = np.array(diag["y_true"])
        y_pred = np.array(diag["y_pred"])
        file_names = diag["file_names"]
        importances = diag["feature_importances"]
        residuals = y_true - y_pred

        # 1. Predicted vs Actual
        fig1 = go.Figure()
        abs_err = np.abs(y_pred - y_true)
        fig1.add_trace(go.Scatter(
            x=y_true, y=y_pred, mode="markers",
            marker=dict(size=9, color=abs_err, colorscale="Bluered", showscale=True,
                        colorbar=dict(title="|Error|")),
            text=file_names,
            hovertemplate="<b>%{text}</b><br>Actual: %{x:.0f}Å<br>Predicted: %{y:.0f}Å<extra></extra>",
        ))
        all_vals = np.concatenate([y_true, y_pred])
        lo, hi = float(np.min(all_vals)), float(np.max(all_vals))
        margin = (hi - lo) * 0.05
        fig1.add_trace(go.Scatter(
            x=[lo - margin, hi + margin], y=[lo - margin, hi + margin],
            mode="lines", line=dict(dash="dash", color=COLORS["text_secondary"]),
            showlegend=False, hoverinfo="skip",
        ))
        fig1.update_layout(**DARK_LAYOUT)
        fig1.update_layout(title="Predicted vs Actual",
                           xaxis_title="Actual Removal (Å)", yaxis_title="Predicted Removal (Å)",
                           showlegend=False)

        # 2. Feature Importance
        fig2 = go.Figure()
        sorted_imp = sorted(importances.items(), key=lambda x: x[1])
        fig2.add_trace(go.Bar(
            x=[v for _, v in sorted_imp],
            y=[k for k, _ in sorted_imp],
            orientation="h",
            marker_color=COLORS["accent"],
        ))
        fig2.update_layout(**DARK_LAYOUT)
        fig2.update_layout(title="Feature Importance",
                           xaxis_title="Importance",
                           margin=dict(l=140, r=30, t=50, b=50))

        # 3. Residuals vs Predicted
        fig3 = go.Figure()
        fig3.add_trace(go.Scatter(
            x=y_pred, y=residuals, mode="markers",
            marker=dict(size=9, color=COLORS["accent"]),
            text=file_names,
            hovertemplate="<b>%{text}</b><br>Predicted: %{x:.0f}Å<br>Residual: %{y:.0f}Å<extra></extra>",
        ))
        fig3.add_hline(y=0, line_dash="dash", line_color=COLORS["text_secondary"])
        fig3.update_layout(**DARK_LAYOUT)
        fig3.update_layout(title="Residuals vs Predicted",
                           xaxis_title="Predicted Removal (Å)", yaxis_title="Residual (Å)",
                           showlegend=False)

        # 4. Residual Distribution
        fig4 = go.Figure()
        fig4.add_trace(go.Histogram(
            x=residuals, nbinsx=max(8, len(residuals) // 4),
            marker_color=COLORS["accent"], opacity=0.85,
        ))
        fig4.add_annotation(
            text=f"Mean: {np.mean(residuals):.0f}  Std: {np.std(residuals):.0f}",
            xref="paper", yref="paper", x=0.02, y=1.0,
            xanchor="left", yanchor="top", showarrow=False,
            font=dict(size=11, color=COLORS["text_secondary"]),
        )
        fig4.update_layout(**DARK_LAYOUT)
        fig4.update_layout(title="Residual Distribution",
                           xaxis_title="Residual (Å)", yaxis_title="Count",
                           showlegend=False)

        return [fig1.to_plotly_json(), fig2.to_plotly_json(),
                fig3.to_plotly_json(), fig4.to_plotly_json()]

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _empty_fig(self, message: str) -> dict:
        """Create an empty Plotly figure with a centered message."""
        fig = go.Figure()
        fig.update_layout(**DARK_LAYOUT)
        fig.add_annotation(
            text=message, xref="paper", yref="paper", x=0.5, y=0.5,
            showarrow=False, font=dict(size=14, color=COLORS["text_secondary"]),
        )
        return fig.to_plotly_json()

    def get_all_tools(self) -> list:
        """Return list of all tool functions for Ollama registration."""
        return [
            self.get_dataset_summary,
            self.get_file_details,
            self.get_feature_statistics,
            self.detect_outliers,
            self.run_automl,
            self.predict_removal,
            self.get_model_diagnostics,
            self.generate_scatter,
            self.generate_distribution,
            self.generate_bar_chart,
            self.generate_correlation_heatmap,
            self.generate_time_series,
            self.generate_model_plots,
        ]
