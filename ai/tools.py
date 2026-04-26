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
    CORRELATION_FEATURES,
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
        """Single source of truth for the loaded dataset's shape: file count, file names, summary-metric columns with value ranges, time-series columns, and categorical breakdowns.

        Other tools (get_file_details, get_feature_statistics, generate_*, run_automl)
        consume names/values that appear in this tool's output. Always call this
        first when you don't have the schema in context, and resolve user words
        ("force", "temperature") to the exact column names listed here before
        passing them to other tools.

        Returns:
            Summary of loaded dataset as formatted text with sections:
            Dataset / Categorical breakdown / Summary metrics / Time-series
            columns / Files.
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

        # Summary-metric columns: per-file aggregates. Used by get_file_details,
        # get_feature_statistics, detect_outliers, generate_scatter,
        # generate_distribution, generate_bar_chart, run_automl.
        housekeeping = {"Date", "File Name", "file_id", "Notes", "Wafer #"}
        summary_cols = [
            c for c in df.columns
            if c not in housekeeping
            and c not in CATEGORICAL_FEATURES
            and pd.api.types.is_numeric_dtype(df[c])
        ]
        if summary_cols:
            lines.append("Summary metrics (per-file aggregates — use these names with get_file_details, get_feature_statistics, detect_outliers, generate_scatter, generate_distribution, generate_bar_chart, run_automl):")
            for c in summary_cols:
                col = df[c].dropna()
                if not col.empty:
                    lines.append(
                        f"  - {c}: {col.min():.4g} – {col.max():.4g} "
                        f"(mean {col.mean():.4g})"
                    )
                else:
                    lines.append(f"  - {c}: (no data)")

        # Time-series columns: per-frame, sampled at the file's hz. Different
        # schema from summary metrics. Used ONLY by generate_time_series.
        ts_cols = self._sample_time_series_columns()
        if ts_cols:
            lines.append("Time-series columns (per-frame — use ONLY these names with generate_time_series; they differ from the summary-metric names above):")
            for c in ts_cols:
                if c == 'time (s)':
                    lines.append(f"  - {c}    [x-axis — used automatically; do NOT pass as a feature]")
                else:
                    lines.append(f"  - {c}")

        if "File Name" in df.columns:
            names = df["File Name"].tolist()
            lines.append("Files (use these exact names — do not invent or abbreviate):")
            for name in names:
                lines.append(f"  - {name}")

        return "\n".join(lines)

    def _sample_time_series_columns(self) -> list[str]:
        """Return the per-frame time-series column names from the first loaded
        file. These are file-level constants set in RawFile.populate_total_per_frame,
        so the first file is representative."""
        df = self.dm.get_all_data()
        if df.empty or "File Name" not in df.columns:
            return []
        first_name = df["File Name"].iloc[0]
        ts = self.dm.get_file_data(first_name)
        return list(ts.columns) if ts is not None else []

    def get_file_details(self, filename: str) -> str:
        """Get detailed metrics for a specific polishing run file.

        Args:
            filename: The exact .dat filename as listed by get_dataset_summary.
                Do NOT invent or abbreviate names — use the literal string from
                the Files: section of get_dataset_summary's output.

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
            x_feature: Feature name for the x-axis. Must be one of:
                COF, Fy, Var Fy, Fz, Var Fz, Mean Temp, Init Temp, High Temp,
                Removal, WIWNU, Mean Pressure, Mean Velocity, P.V, COF.P.V,
                Sommerfeld, Removal Rate, Pressure PSI, Polish Time.
            y_feature: Feature name for the y-axis (same valid values as
                x_feature).
            color_by: Optional categorical feature for color coding points.
                Must be one of: Wafer, Pad, Slurry, Conditioner.
            filter_column: Optional column name to filter data on.
            filter_value: Value to match in filter_column. Must be an exact
                value present in the data. If unsure, call get_dataset_summary
                first to see available values.

        Returns:
            Plotly figure as a JSON-serializable dictionary, or an error
            string if any input is invalid.
        """
        df = self.dm.get_all_data()
        if df.empty:
            return {"figure": self._empty_fig("No data loaded."), "summary": "No data loaded."}

        if x_feature not in CORRELATION_FEATURES:
            return (
                f"x_feature '{x_feature}' not valid. Valid features: "
                f"{', '.join(CORRELATION_FEATURES)}"
            )
        if y_feature not in CORRELATION_FEATURES:
            return (
                f"y_feature '{y_feature}' not valid. Valid features: "
                f"{', '.join(CORRELATION_FEATURES)}"
            )
        if color_by is not None and color_by not in CATEGORICAL_FEATURES:
            return (
                f"color_by '{color_by}' not valid. Valid options: "
                f"{', '.join(CATEGORICAL_FEATURES)}"
            )

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
            feature: Feature name to plot. Must be one of:
                COF, Fy, Var Fy, Fz, Var Fz, Mean Temp, Init Temp, High Temp,
                Removal, WIWNU, Mean Pressure, Mean Velocity, P.V, COF.P.V,
                Sommerfeld, Removal Rate, Pressure PSI, Polish Time.
            group_by: Optional categorical feature for grouped box plot.
                Must be one of: Wafer, Pad, Slurry, Conditioner.

        Returns:
            Plotly figure as a JSON-serializable dictionary, or an error
            string if any input is invalid.
        """
        df = self.dm.get_all_data()
        if df.empty:
            return {"figure": self._empty_fig("No data loaded."), "summary": "No data loaded."}

        if feature not in CORRELATION_FEATURES:
            return (
                f"feature '{feature}' not valid. Valid features: "
                f"{', '.join(CORRELATION_FEATURES)}"
            )
        if group_by is not None and group_by not in CATEGORICAL_FEATURES:
            return (
                f"group_by '{group_by}' not valid. Valid options: "
                f"{', '.join(CATEGORICAL_FEATURES)}"
            )

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
            feature: Numerical feature for the y-axis values. Must be one of:
                COF, Fy, Var Fy, Fz, Var Fz, Mean Temp, Init Temp, High Temp,
                Removal, WIWNU, Mean Pressure, Mean Velocity, P.V, COF.P.V,
                Sommerfeld, Removal Rate, Pressure PSI, Polish Time.
            group_by: Categorical feature for grouping bars. Must be one of:
                Wafer, Pad, Slurry, Conditioner.

        Returns:
            Plotly figure as a JSON-serializable dictionary, or an error
            string if any input is invalid.
        """
        df = self.dm.get_all_data()
        if df.empty:
            return {"figure": self._empty_fig("No data loaded."), "summary": "No data loaded."}

        if feature not in CORRELATION_FEATURES:
            return (
                f"feature '{feature}' not valid. Valid features: "
                f"{', '.join(CORRELATION_FEATURES)}"
            )
        if group_by not in CATEGORICAL_FEATURES:
            return (
                f"group_by '{group_by}' not valid. Valid options: "
                f"{', '.join(CATEGORICAL_FEATURES)}"
            )

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
        """Generate a Pearson correlation matrix heatmap for numerical features.

        The default feature set covers every measured output PLUS the two
        controllable process parameters (Pressure PSI, Polish Time) — these
        matter physically via Preston's equation and engineers almost always
        want to see them in the matrix.

        Any column that is constant across the dataset is dropped automatically
        (its correlation is mathematically undefined). The dropped names are
        reported in the data summary so you can tell the user why they are
        missing.

        Args:
            features: Optional list of feature names. Omit (or pass an empty
                list) to use the default set. Explicit lists are filtered the
                same way — constant columns are always dropped.

        Returns:
            Plotly figure as a JSON-serializable dictionary, plus a text
            summary listing the strongest correlations with Removal, the top
            pairwise correlations, and any excluded constant features.
        """
        df = self.dm.get_all_data()
        if df.empty:
            return {"figure": self._empty_fig("No data loaded."), "summary": "No data loaded."}

        if not features:  # None or empty list → use all defaults
            features = [f for f in CORRELATION_FEATURES if f in df.columns]
        else:
            features = [f for f in features if f in df.columns]

        numeric_df = df[features].select_dtypes(include=[np.number]).dropna(axis=1, how="all")

        # Drop constant columns — correlation is undefined when σ = 0.
        constant_cols = [c for c in numeric_df.columns
                         if numeric_df[c].nunique(dropna=True) <= 1]
        if constant_cols:
            numeric_df = numeric_df.drop(columns=constant_cols)

        if numeric_df.shape[1] < 2:
            return {
                "figure": self._empty_fig("Not enough varying numerical features to correlate."),
                "summary": (
                    "Correlation heatmap could not be built: fewer than two "
                    "varying features remained after dropping constants "
                    f"({', '.join(constant_cols) or 'none'})."
                ),
            }

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

        summary_lines = []
        if constant_cols:
            summary_lines.append(
                f"Excluded (constant in this dataset): {', '.join(constant_cols)}"
            )

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

    def generate_time_series(
        self,
        filename: str,
        features: list[str],
        y_min: float = None,
        y_max: float = None,
        x_min: float = None,
        x_max: float = None,
    ) -> dict:
        """Generate a time-series plot for a specific polishing run file.

        Args:
            filename: Exact filename from the Files: section of
                get_dataset_summary's output. Do not invent or abbreviate.
            features: List of column names from the Time-series columns section
                of get_dataset_summary's output. These DIFFER from the summary
                metrics — e.g. user says "Fz" → pass 'Fz Total (lbf)'; user
                says "temperature" → pass 'IR Temperature'. Unknown names
                return a clarification error rather than an empty chart.
                All features share one y-axis. If they have very different
                magnitudes (e.g., COF at 0-1 vs Force at 0-300 lbf), call this
                tool separately for each so the user gets a readable chart per
                scale.
            y_min: Optional lower bound for the y-axis. Pass when the user names
                an explicit range (e.g. "plot COF from 0 to 2"). Must be paired
                with y_max — passing only one is ambiguous and returns a
                clarification request instead of a chart.
            y_max: Optional upper bound for the y-axis. See y_min.
            x_min: Optional lower bound for the x-axis (time in seconds). Pass
                when the user names an explicit time window (e.g. "show the first
                30 seconds" → x_min=0, x_max=30). Must be paired with x_max —
                passing only one is ambiguous and returns a clarification request.
            x_max: Optional upper bound for the x-axis (seconds). See x_min.

        Default y-axis behavior when no range is passed:
            - features == ['COF']: y pinned to [0, 1] (CMP convention).
            - anything else: auto-range from data.

        Default x-axis behavior: auto-range over the file's full time span when
        no x_min/x_max is passed.

        Returns:
            Plotly figure as a JSON-serializable dictionary, plus a text summary.
        """
        # Half-bound input is ambiguous — surface back to the agent for clarification.
        if (y_min is None) != (y_max is None):
            return {
                "figure": self._empty_fig("Ambiguous y-axis range"),
                "summary": (
                    f"Ambiguous input: y_min={y_min}, y_max={y_max}. "
                    f"Ask the user for the missing bound before re-running."
                ),
            }
        if (x_min is None) != (x_max is None):
            return {
                "figure": self._empty_fig("Ambiguous x-axis range"),
                "summary": (
                    f"Ambiguous input: x_min={x_min}, x_max={x_max}. "
                    f"Ask the user for the missing bound before re-running."
                ),
            }

        ts_data = self.dm.get_file_data(filename)
        if ts_data is None:
            return {"figure": self._empty_fig(f"File '{filename}' not found."),
                    "summary": f"File '{filename}' not found."}

        unknown = [f for f in features if f not in ts_data.columns]
        if unknown:
            features_only = [c for c in ts_data.columns if c != 'time (s)']
            return {
                "figure": self._empty_fig("Unknown time-series features"),
                "summary": (
                    f"Unknown time-series feature(s): {unknown}. These names are "
                    f"not in the per-frame schema. Re-resolve user words to the "
                    f"exact names listed in get_dataset_summary's 'Time-series "
                    f"columns' section. Note: 'time (s)' is the x-axis and is "
                    f"used automatically — do NOT pass it as a feature. "
                    f"Valid feature columns for this file: {features_only}."
                ),
            }

        x_values = ts_data['time (s)'] if 'time (s)' in ts_data.columns else None
        x_title = "Time (s)" if x_values is not None else "Sample"

        # Clip stats to the steady polish interval so transients (startup/
        # shutdown spikes when forces approach zero) don't dominate the summary
        # the agent reports back to the user. The chart still plots the full
        # time series — only the summary stats are clipped.
        interval = self.dm.get_file_interval(filename)
        stats_data = ts_data
        interval_note = None
        if interval and len(interval) == 2 and 'time (s)' in ts_data.columns:
            start_s, end_s = interval
            mask = (ts_data['time (s)'] >= start_s) & (ts_data['time (s)'] <= end_s)
            if mask.any():
                stats_data = ts_data[mask]
                interval_note = (
                    f"  (stats below are over the steady polish interval "
                    f"[{start_s:g}s–{end_s:g}s]; startup/shutdown transients excluded)"
                )

        fig = go.Figure()
        summary_lines = [f"Time series for {filename}:"]
        if interval_note:
            summary_lines.append(interval_note)
        for i, feat in enumerate(features):
            trace_kwargs = dict(
                y=ts_data[feat],
                mode="lines",
                name=feat,
                line=dict(color=CLUSTER_COLORS[i % len(CLUSTER_COLORS)]),
            )
            if x_values is not None:
                trace_kwargs['x'] = x_values
            fig.add_trace(go.Scatter(**trace_kwargs))
            series = stats_data[feat].dropna()
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
            xaxis_title=x_title,
            yaxis_title="Value",
        )

        if y_min is not None and y_max is not None:
            fig.update_yaxes(range=[y_min, y_max], autorange=False)
            summary_lines.append(f"  y-axis: [{y_min}, {y_max}] (user-specified)")
        elif features == ['COF']:
            fig.update_yaxes(range=[0, 1], autorange=False)
            summary_lines.append("  y-axis: [0, 1] (default for COF)")
        else:
            fig.update_yaxes(autorange=True)
            summary_lines.append("  y-axis: auto-range (spans all plotted features)")

        if x_min is not None and x_max is not None:
            fig.update_xaxes(range=[x_min, x_max], autorange=False)
            summary_lines.append(f"  x-axis: [{x_min}, {x_max}] s (user-specified)")
        else:
            fig.update_xaxes(autorange=True)
            summary_lines.append("  x-axis: auto-range (full file time span)")

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


def build_tool_catalog() -> list[dict]:
    """UI-ready entries for every registered capability, in display order.

    Joins the live registration list from ``AgentTools.get_all_tools`` with
    user-facing copy from ``ai.tool_ui.TOOL_UI``. Capabilities without a
    ``TOOL_UI`` entry fall through to the ``other`` category with a
    humanized name and no example prompts — graceful, never broken.
    """
    from ai.tool_ui import TOOL_UI, CATEGORY_ORDER

    # AgentTools(None, None) is safe: get_all_tools only returns bound method
    # references; it never touches self.dm or self.ml. If that changes, swap
    # to iterating TOOL_UI.keys() and pulling docstrings via getattr(AgentTools).
    registered = AgentTools(None, None).get_all_tools()
    order = {c: i for i, c in enumerate(CATEGORY_ORDER)}
    entries = []
    for fn in registered:
        ui = TOOL_UI.get(fn.__name__)
        if ui:
            entries.append({"name": fn.__name__, **ui})
        else:
            entries.append({
                "name": fn.__name__,
                "category": "other",
                "title": fn.__name__.replace("_", " ").capitalize(),
                "long": (fn.__doc__ or "").strip(),
                "examples": [],
            })
    entries.sort(key=lambda e: order.get(e["category"], 99))
    return entries
