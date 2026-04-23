"""Tool functions for the AI agent.

Each function is a thin wrapper around DataManager or AutoMLManager.
The ollama-python library auto-generates JSON schemas from the type
annotations and docstrings.
"""

import itertools
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

    def run_automl(self, time_budget: int = 30) -> str:
        """Train and evaluate multiple ML pipelines using AutoML to find the best model.

        Any positive integer is valid for time_budget — there is NO minimum.
        Wall-clock time is approximately equal to time_budget plus a few
        seconds for out-of-fold metric evaluation.

        Practical guidance by dataset size:
        - Under 100 files: 30s (default) is sufficient
        - 100-500 files: 60s gives a more thorough search
        - 500+ files: 120s may help find better configurations
        Longer budgets do NOT guarantee better results. On small datasets,
        longer searches can overfit by selecting overly complex models.

        Args:
            time_budget: Search budget in seconds. Default 30. Any positive
                value is accepted.

        Returns:
            Best model name, top-5 leaderboard, held-out 5-fold CV metrics,
            feature importances, and data-quality warnings. After this tool
            returns successfully, the prediction form on the right side of
            the canvas is already populated and ready to use; the user does
            NOT need to do anything to open it.
        """
        try:
            results = self.ml.train(time_budget=time_budget)
        except ValueError as exc:
            return f"Cannot train: {exc}"

        m = results["metrics"]
        lines = [f"AutoML complete. Best model: {results['best_model']}"]
        lines.append(
            f"Held-out CV metrics: R²={m['r2']:.3f}, "
            f"CV RMSE={m['rmse']:.0f}Å, "
            f"CV MAE={m['mae']:.0f}Å, "
            f"trained on {results['n_train']} files."
        )
        lines.append(
            f"Timing: best model found in {m['search_time']}s, "
            f"total wall time {m['wall_time']}s "
            f"(budget: {m['time_budget']}s)."
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

        lines.append(
            "\nPrediction form status: READY — dropdowns are populated from "
            "training categories and the form is already visible on the "
            "right side of the canvas. Tell the user the form is ready and "
            "they can enter values to make predictions. Do NOT ask the user "
            "if they want to open the form — it is already open."
        )

        return "\n".join(lines)

    def _resolve_category(self, value: str, column: str) -> str:
        """Map a user-supplied string to an exact training category value.

        Tries exact match → prefix match → substring match (all case-insensitive
        after exact). Raises ValueError listing valid options if the value is
        unknown or ambiguous.
        """
        known = self.ml.get_category_options().get(column, [])
        if not known:
            raise ValueError(
                f"No trained categories for {column}. Train a model first."
            )
        if value in known:
            return value
        vl = value.lower().strip()
        # prefix match either direction
        prefix = [k for k in known
                  if k.lower().startswith(vl) or vl.startswith(k.lower())]
        if len(prefix) == 1:
            return prefix[0]
        # substring match either direction
        sub = [k for k in known if vl in k.lower() or k.lower() in vl]
        if len(sub) == 1:
            return sub[0]
        raise ValueError(
            f"Unknown {column} value '{value}'. Valid options: {', '.join(known)}"
        )

    def open_prediction_form(
        self,
        pressure_psi: float = None,
        polish_time: float = None,
        wafer: str = None,
        pad: str = None,
        slurry: str = None,
        conditioner: str = None,
    ) -> dict:
        """Open the prediction form in the canvas, pre-filled with any values the user mentioned.

        The prediction itself is computed deterministically when the user
        clicks Predict in the form — do NOT try to predict numbers yourself.
        Any categorical values you pass here are resolved to the exact trained
        category names (e.g. 'CU4545F' -> 'CU4545F-300'). Pass only what the
        user mentioned; leave the rest as None.

        Args:
            pressure_psi: Down force pressure in PSI (optional).
            polish_time: Polish duration in minutes (optional).
            wafer: Wafer type (optional).
            pad: Pad type (optional).
            slurry: Slurry type (optional).
            conditioner: Conditioner disk type (optional).

        Returns:
            Dict with 'prefill' payload and a short text message.
        """
        if self.ml.automl is None:
            return {
                "message": (
                    "No model trained yet. Run AutoML first, then I'll open "
                    "the prediction form for you."
                )
            }

        # Resolve each provided categorical value; raise with a helpful error
        # if the match is ambiguous or unknown.
        provided = {
            'Wafer': wafer, 'Pad': pad, 'Slurry': slurry, 'Conditioner': conditioner,
        }
        prefill = {}
        try:
            for col, val in provided.items():
                if val is not None and str(val).strip():
                    prefill[col] = self._resolve_category(str(val), col)
        except ValueError as exc:
            return {"message": f"Cannot open form: {exc}"}

        if pressure_psi is not None:
            prefill['Pressure PSI'] = float(pressure_psi)
        if polish_time is not None:
            prefill['Polish Time'] = float(polish_time)

        cat_opts = self.ml.get_category_options()
        options_summary = " | ".join(
            f"{col}: {', '.join(vals)}" for col, vals in cat_opts.items() if vals
        )

        if prefill:
            filled = ", ".join(f"{k}={v}" for k, v in prefill.items())
            msg = (
                f"Prediction form opened in the canvas with these values "
                f"pre-filled: {filled}. Review them and click **Predict**. "
                f"Available options \u2014 {options_summary}."
            )
        else:
            msg = (
                "Prediction form is available in the canvas. Pick the Wafer, "
                "Pad, Slurry, Conditioner from the dropdowns, type Pressure "
                "(PSI) and Polish Time (min), then click **Predict**. "
                f"Available options \u2014 {options_summary}."
            )

        return {"prefill": prefill, "message": msg}

    def get_model_diagnostics(self) -> str:
        """Get detailed diagnostics for the currently trained model.

        Returns:
            Residual statistics, held-out 5-fold CV metrics, data quality warnings, and model hyperparameters.
        """
        try:
            diag = self.ml.get_diagnostics()
        except ValueError as exc:
            return f"Cannot get diagnostics: {exc}"

        lines = [
            f"Model: {diag['metrics']['best_model']}",
            f"Held-out CV: R²={diag['metrics']['r2']:.3f}, RMSE={diag['metrics']['rmse']:.0f}Å, MAE={diag['metrics']['mae']:.0f}Å",
            f"Trained on {diag['metrics']['n_train']} files.",
            f"\nOOF residuals: mean={diag['residual_mean']:.1f}, std={diag['residual_std']:.1f}, "
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
            color_by: Optional categorical feature for color coding points
                (e.g. 'Wafer', 'Pad', 'Slurry', 'Conditioner').
            filter_column: Optional column name to filter data on.
            filter_value: Value to match in filter_column. Must be an exact
                value present in the data. If unsure, call get_dataset_summary
                first to see available values.

        Returns:
            Plotly figure as a JSON-serializable dictionary, or an error
            string if the filter_value is not found.
        """
        df = self.dm.get_all_data()
        if df.empty:
            return {"figure": self._empty_fig("No data loaded."), "summary": "No data loaded."}

        if filter_column and filter_value and filter_column in df.columns:
            # Validate filter_value — return a helpful error rather than
            # silently producing an empty plot.
            valid = sorted(str(v) for v in df[filter_column].dropna().unique() if str(v))
            if str(filter_value) not in valid:
                return (
                    f"Filter value '{filter_value}' not found in column "
                    f"'{filter_column}'. Valid values: {', '.join(valid)}"
                )
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

        # Build a text summary for the LLM.
        common = df[[x_feature, y_feature]].dropna()
        n = len(common)
        summary_lines = [f"Scatter: {y_feature} vs {x_feature}, n={n} points"]
        if n >= 3:
            r_val = float(np.corrcoef(common[x_feature], common[y_feature])[0, 1])
            trend = "positive" if r_val > 0 else "negative"
            summary_lines.append(f"  Pearson r={r_val:.3f} ({trend} trend)")
        summary_lines.append(
            f"  x range: {common[x_feature].min():.4g} to {common[x_feature].max():.4g}"
        )
        summary_lines.append(
            f"  y range: {common[y_feature].min():.4g} to {common[y_feature].max():.4g}"
        )
        if color_by and color_by in df.columns:
            summary_lines.append(f"  Colored by {color_by} ({df[color_by].nunique()} groups)")

        fig.update_layout(**DARK_LAYOUT)
        fig.update_layout(
            title=f"{y_feature} vs {x_feature}",
            xaxis_title=x_feature,
            yaxis_title=y_feature,
        )
        return {"figure": fig.to_plotly_json(), "summary": "\n".join(summary_lines)}

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
            return {"figure": self._empty_fig("No data loaded."), "summary": "No data loaded."}

        fig = go.Figure()
        summary_lines = []

        if group_by and group_by in df.columns:
            for i, (group, group_df) in enumerate(df.groupby(group_by)):
                fig.add_trace(go.Box(
                    y=group_df.get(feature),
                    name=str(group),
                    marker_color=CLUSTER_COLORS[i % len(CLUSTER_COLORS)],
                ))
            fig.update_layout(title=f"{feature} by {group_by}")
            # Summary for grouped box plot.
            summary_lines.append(f"{feature} by {group_by}:")
            group_means = df.groupby(group_by)[feature].mean().dropna()
            for name, group in df.groupby(group_by):
                valid = group[feature].dropna()
                if not valid.empty:
                    summary_lines.append(
                        f"  {name}: mean={valid.mean():.4g}, median={valid.median():.4g}, n={len(valid)}"
                    )
            if not group_means.empty:
                summary_lines.append(f"  Highest mean: {group_means.idxmax()} ({group_means.max():.4g})")
                summary_lines.append(f"  Lowest mean: {group_means.idxmin()} ({group_means.min():.4g})")
        else:
            fig.add_trace(go.Histogram(
                x=df.get(feature),
                marker_color=COLORS["accent"],
                marker_line=dict(color=COLORS["border_light"], width=1),
                opacity=0.85,
            ))
            fig.update_layout(title=f"Distribution of {feature}")
            # Summary for histogram.
            valid = df[feature].dropna()
            summary_lines.append(f"Distribution of {feature} (n={len(valid)})")
            summary_lines.append(f"  mean={valid.mean():.4g}, std={valid.std():.4g}")
            summary_lines.append(f"  min={valid.min():.4g}, max={valid.max():.4g}")
            skew_val = float(valid.skew())
            skew_dir = ("right-skewed" if skew_val > 0.5
                        else ("left-skewed" if skew_val < -0.5 else "roughly symmetric"))
            summary_lines.append(f"  skewness={skew_val:.2f} ({skew_dir})")

        fig.update_layout(**DARK_LAYOUT)
        fig.update_layout(yaxis_title="Count" if not group_by else feature)
        return {"figure": fig.to_plotly_json(), "summary": "\n".join(summary_lines)}

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
            return {"figure": self._empty_fig("No data loaded."), "summary": "No data loaded."}

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

        # Summary for the LLM.
        summary_lines = [f"Mean {feature} by {group_by}:"]
        for name in means.index:
            summary_lines.append(
                f"  {name}: mean={means[name]:.4g} (std={stds[name]:.4g})"
            )
        summary_lines.append(f"  Highest: {means.idxmax()} ({means.max():.4g})")
        summary_lines.append(f"  Lowest: {means.idxmin()} ({means.min():.4g})")

        fig.update_layout(**DARK_LAYOUT)
        fig.update_layout(
            title=f"Mean {feature} by {group_by}",
            xaxis_title=group_by,
            yaxis_title=feature,
        )
        return {"figure": fig.to_plotly_json(), "summary": "\n".join(summary_lines)}

    def generate_correlation_heatmap(self, features: list[str] = None) -> dict:
        """Generate a correlation matrix heatmap for numerical features.

        IMPORTANT: omit the `features` parameter entirely to include ALL
        numerical features (COF, Fz, Var Fz, Mean Temp, Init Temp, High Temp,
        Removal, WIWNU, Mean Pressure, Mean Velocity, P.V, COF.P.V,
        Sommerfeld, Pressure PSI, Polish Time, Removal Rate). Passing an
        empty list or a partial list will limit the heatmap to only those
        columns — this is almost never what the user wants.

        Args:
            features: Optional list of feature names. Defaults to ALL numerical
                analysis features when omitted or empty.

        Returns:
            Plotly figure as a JSON-serializable dictionary.
        """
        df = self.dm.get_all_data()
        if df.empty:
            return {"figure": self._empty_fig("No data loaded."), "summary": "No data loaded."}

        if not features:  # None or empty list → use all defaults
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

        # Build a text summary of key correlations for the LLM.
        summary_lines = []
        if "Removal" in corr.columns:
            removal_corr = corr["Removal"].drop("Removal").sort_values(
                key=abs, ascending=False
            )
            summary_lines.append("Correlations with Removal:")
            for feat, val in removal_corr.items():
                summary_lines.append(f"  {feat}: r={val:.2f}")

        pairs = [
            (a, b, corr.loc[a, b])
            for a, b in itertools.combinations(corr.columns, 2)
        ]
        pairs.sort(key=lambda x: abs(x[2]), reverse=True)
        summary_lines.append("Strongest overall correlations:")
        for a, b, r in pairs[:5]:
            summary_lines.append(f"  {a} vs {b}: r={r:.2f}")

        fig.update_layout(**DARK_LAYOUT)
        fig.update_layout(
            title="Feature Correlation Matrix",
            width=700,
            height=600,
        )
        return {"figure": fig.to_plotly_json(), "summary": "\n".join(summary_lines)}

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
            return {"figure": self._empty_fig(f"File '{filename}' not found."),
                    "summary": f"File '{filename}' not found."}

        fig = go.Figure()
        summary_lines = [f"Time series for {filename}:"]
        for i, feat in enumerate(features):
            if feat in ts_data.columns:
                fig.add_trace(go.Scatter(
                    y=ts_data[feat],
                    mode="lines",
                    name=feat,
                    line=dict(color=CLUSTER_COLORS[i % len(CLUSTER_COLORS)]),
                ))
                series = ts_data[feat].dropna()
                if not series.empty:
                    start_avg = series.iloc[:5].mean()
                    end_avg = series.iloc[-5:].mean()
                    if end_avg > start_avg * 1.05:
                        trend = "increasing"
                    elif end_avg < start_avg * 0.95:
                        trend = "decreasing"
                    else:
                        trend = "stable"
                    summary_lines.append(
                        f"  {feat}: min={series.min():.4g}, max={series.max():.4g}, "
                        f"mean={series.mean():.4g}, trend={trend}"
                    )

        fig.update_layout(**DARK_LAYOUT)
        fig.update_layout(
            title=f"Time Series: {filename}",
            xaxis_title="Sample",
            yaxis_title="Value",
        )
        return {"figure": fig.to_plotly_json(), "summary": "\n".join(summary_lines)}

    def generate_model_plots(self) -> dict:
        """Generate all diagnostic plots for the currently trained model.

        Returns:
            Dict with 'figures' (list of 4 Plotly figures) and 'summary' text:
            predicted vs actual, feature importance, residuals vs predicted,
            and residual distribution.
        """
        try:
            diag = self.ml.get_diagnostics()
        except ValueError:
            empty = self._empty_fig("No model trained.")
            return {"figures": [empty, empty, empty, empty],
                    "summary": "No model trained yet."}

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
        max_imp = max((v for _, v in sorted_imp), default=0.0)
        fig2.update_layout(**DARK_LAYOUT)
        fig2.update_layout(
            title="Feature Importance",
            xaxis_title="Permutation Importance (R² drop)",
            xaxis_range=[0, max_imp * 1.1 if max_imp > 0 else 1],
            margin=dict(l=140, r=30, t=50, b=50),
        )

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

        # Build a text summary of model diagnostics for the LLM.
        sorted_imp_desc = sorted(importances.items(), key=lambda x: x[1], reverse=True)
        summary_lines = [
            f"Model diagnostics ({diag['metrics']['best_model']}):",
            f"  R²={diag['metrics']['r2']:.3f}, RMSE={diag['metrics']['rmse']:.0f}Å, MAE={diag['metrics']['mae']:.0f}Å",
            f"  Residuals: mean={np.mean(residuals):.1f}, std={np.std(residuals):.1f}, "
            f"range=[{np.min(residuals):.1f}, {np.max(residuals):.1f}]",
            "  Top features: " + ", ".join(f"{k}={v:.3f}" for k, v in sorted_imp_desc[:5]),
        ]
        abs_errors = np.abs(residuals)
        worst_idx = np.argsort(abs_errors)[-3:][::-1]
        summary_lines.append("  Largest errors:")
        for idx in worst_idx:
            summary_lines.append(
                f"    {file_names[idx]}: actual={y_true[idx]:.0f}, "
                f"pred={y_pred[idx]:.0f}, error={residuals[idx]:.0f}"
            )

        return {
            "figures": [fig1.to_plotly_json(), fig2.to_plotly_json(),
                        fig3.to_plotly_json(), fig4.to_plotly_json()],
            "summary": "\n".join(summary_lines),
        }

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
            self.open_prediction_form,
            self.get_model_diagnostics,
            self.generate_scatter,
            self.generate_distribution,
            self.generate_bar_chart,
            self.generate_correlation_heatmap,
            self.generate_time_series,
            self.generate_model_plots,
        ]
