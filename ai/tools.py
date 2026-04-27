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
        """List the loaded CMP dataset's shape: file count, exact filenames, summary-metric columns with value ranges, time-series columns, and categorical breakdowns (Wafer/Pad/Slurry/Conditioner).

        Single source of truth for column names and categorical values. Every
        other tool (get_file_details, get_feature_statistics, find_files_by_config,
        generate_*, run_automl) consumes names that appear here verbatim. Call
        this first whenever the schema is not already in context, then resolve
        user words ("force", "temperature") to the exact column names listed.

        Takes no arguments.

        Returns:
            Plain text (no chart) with sections in this order: Dataset (counts),
            categorical breakdowns with per-value file counts, Summary metrics
            (per-file aggregates with min/max/mean), Time-series columns
            (per-frame), and Files (exact filenames). Cite values from this
            text directly; do not paraphrase.
        """
        df = self.dm.get_all_data()
        if df.empty:
            return "No data loaded."

        n_files = len(df)
        has_removal = int((df.get("Removal", pd.Series(dtype=float)) > 0).sum())

        lines = [
            f"Dataset: {n_files} polishing files, {has_removal} with removal data."
        ]

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
                top = ", ".join(f"{v} ({c})" for v, c in counts.items())
                lines.append(f"  {cat}: {len(counts)} types — {top}")

        # Summary-metric columns: per-file aggregates. Used by get_file_details,
        # get_feature_statistics, detect_outliers, generate_scatter,
        # generate_distribution, generate_bar_chart, run_automl.
        housekeeping = {"Date", "File Name", "file_id", "Notes", "Wafer #"}
        summary_cols = [
            c
            for c in df.columns
            if c not in housekeeping
            and c not in CATEGORICAL_FEATURES
            and pd.api.types.is_numeric_dtype(df[c])
        ]
        if summary_cols:
            lines.append(
                "Summary metrics (per-file aggregates — use these names with get_file_details, get_feature_statistics, detect_outliers, generate_scatter, generate_distribution, generate_bar_chart, run_automl):"
            )
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
            lines.append(
                "Time-series columns (per-frame — use ONLY these names with generate_time_series; they differ from the summary-metric names above):"
            )
            for c in ts_cols:
                if c == "time (s)":
                    lines.append(
                        f"  - {c}    [x-axis — used automatically; do NOT pass as a feature]"
                    )
                else:
                    lines.append(f"  - {c}")

        if "File Name" in df.columns:
            lines.append(
                "Files (use these exact names — do not invent or abbreviate; "
                "to map a user-described run to a filename, call "
                "find_files_by_config instead of pattern-matching this list):"
            )
            for name in df["File Name"]:
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
        """Inspect every recorded summary metric and categorical setting for a single polishing run.

        Use when the user asks about one specific .dat file (e.g. "what are the
        details for run_023.dat", "show me file X"). For configuration-based
        lookups ("the run with tantalum at 2 psi"), call `find_files_by_config`
        instead.

        Args:
            filename: Exact .dat filename as listed in `get_dataset_summary`'s
                Files: section. Must be a literal match — never invent,
                abbreviate, complete, or guess. If the user gave a partial name
                that does not appear in the Files: list, ask which they meant
                rather than calling this tool.

        Returns:
            Plain text (no chart): COF, Fz, Var Fz, Mean/Init/High Temp,
            Removal (Å), WIWNU, Pressure (PSI), Polish Time (min), Mean
            Pressure, Mean Velocity, P.V, Removal Rate, plus Wafer/Pad/Slurry/
            Conditioner. Cite values from this text directly.
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
            "COF",
            "Fz",
            "Var Fz",
            "Mean Temp",
            "Init Temp",
            "High Temp",
            "Removal",
            "WIWNU",
            "Pressure PSI",
            "Polish Time",
            "Mean Pressure",
            "Mean Velocity",
            "P.V",
            "Removal Rate",
        ]
        for col in metric_cols:
            if col in row.index and pd.notna(row[col]):
                lines.append(f"  {col}: {row[col]:.4g}")

        for cat in CATEGORICAL_FEATURES:
            if cat in row.index:
                lines.append(f"  {cat}: {row[cat] or 'Not set'}")

        return "\n".join(lines)

    def find_files_by_config(
        self,
        wafer: str = None,
        pad: str = None,
        slurry: str = None,
        conditioner: str = None,
        pressure_psi: float = None,
        polish_time: float = None,
    ) -> str:
        """Look up filenames matching a process-configuration filter (wafer, pad, slurry, conditioner, pressure, polish time).

        Use whenever the user describes a run by its setup instead of by its
        filename (e.g. "the run with tantalum at 2 psi", "the IC1010 run").
        Pass only the fields the user explicitly named; omit the rest.

        CATEGORICAL ARGUMENTS MUST BE EXACT MATCHES of values listed in
        `get_dataset_summary`'s Categorical breakdown — case, hyphens, suffixes
        and all. Do not call this tool with a partial, paraphrased, or
        "close-enough" categorical value; if the user's term does not appear
        verbatim in the breakdown, ask the user to confirm which exact value
        they meant. Numerical arguments (pressure_psi, polish_time) match
        within ±0.01 in their native units (PSI, minutes).

        Args:
            wafer: Exact Wafer value from the Categorical breakdown (e.g.
                'Cu', 'Ta', 'TEOS'). Optional.
            pad: Exact Pad value from the Categorical breakdown (e.g.
                'IC1010', 'D100'). Optional.
            slurry: Exact Slurry value from the Categorical breakdown (e.g.
                'CU4545F-300'). Optional.
            conditioner: Exact Conditioner value from the Categorical
                breakdown. Optional.
            pressure_psi: Down-force pressure in PSI. Optional.
            polish_time: Polish duration in minutes. Optional.

        Returns:
            Plain text (no chart):
            - Exactly 1 match: the filename, ready to pass to `get_file_details`,
              `generate_time_series`, etc.
            - Multiple matches: up to 50 filenames with the fields that differ
              between them, so the agent can ask the user to disambiguate.
            - 0 matches: which filter caused the empty result. Do NOT retry
              with guessed values; ask the user which filter to relax.
        """
        df = self.dm.get_all_data()
        if df.empty:
            return "No data loaded."

        filters = {
            "Wafer": wafer,
            "Pad": pad,
            "Slurry": slurry,
            "Conditioner": conditioner,
            "Pressure PSI": pressure_psi,
            "Polish Time": polish_time,
        }
        applied = {k: v for k, v in filters.items() if v is not None}
        if not applied:
            return (
                "No filter provided. Pass at least one of: wafer, pad, "
                "slurry, conditioner, pressure_psi, polish_time."
            )

        missing = [k for k in applied if k not in df.columns]
        if missing:
            return f"Column(s) not present in the loaded data: {missing}."

        mask = pd.Series(True, index=df.index)
        for col, val in applied.items():
            if col in PREDICTION_NUMERICAL_FEATURES:
                mask &= (df[col] - val).abs() < 0.01
            else:
                mask &= df[col] == val

        matched = df.loc[mask]
        n = len(matched)
        applied_str = ", ".join(f"{k}={v}" for k, v in applied.items())

        if n == 0:
            return (
                f"No files match {applied_str}. Do not retry with guessed "
                f"values — ask the user which filter to relax."
            )
        if n == 1:
            return f"1 file matches {applied_str}:\n  - {matched['File Name'].iloc[0]}"

        differing = [
            c
            for c in CATEGORICAL_FEATURES + PREDICTION_NUMERICAL_FEATURES
            if c in matched.columns and matched[c].nunique(dropna=False) > 1
        ]
        cap = 50
        head = matched.head(cap)
        lines = [f"{n} files match {applied_str}."]
        if differing:
            lines.append(f"They differ on: {', '.join(differing)}.")
        lines.append("Files:")
        for _, row in head.iterrows():
            extras = []
            for c in differing:
                val = row[c]
                if pd.isna(val) or (isinstance(val, str) and val == ""):
                    rendered = "Not set"
                elif c in PREDICTION_NUMERICAL_FEATURES:
                    rendered = f"{val:.4g}"
                else:
                    rendered = str(val)
                extras.append(f"{c}: {rendered}")
            suffix = f"  [{', '.join(extras)}]" if extras else ""
            lines.append(f"  - {row['File Name']}{suffix}")
        if n > cap:
            lines.append(f"  ... and {n - cap} more — narrow the filter.")
        return "\n".join(lines)

    def get_feature_statistics(self, feature: str, group_by: str = None) -> str:
        """Compute descriptive statistics (mean, std, min, max, median, n) for one summary metric across the dataset, optionally split by a categorical.

        Use for direct distribution questions ("what is the average COF",
        "how does Removal vary by Pad"). Do NOT call before `run_automl` —
        AutoML reports its own data-quality summary.

        Args:
            feature: Exact summary-metric column name from `get_dataset_summary`'s
                Summary metrics section (e.g. 'COF', 'Removal', 'Mean Temp',
                'Pressure PSI', 'Polish Time'). Must be a literal match.
            group_by: Optional categorical column to split by — must be one of
                'Wafer', 'Pad', 'Slurry', 'Conditioner'. Omit to get whole-dataset
                statistics.

        Returns:
            Plain text (no chart): mean, std, min, max, median, n. If
            group_by is given, one line per group. Cite values directly.
        """
        df = self.dm.get_all_data()
        if df.empty:
            return "No data loaded."

        if feature not in df.columns:
            available = [c for c in df.columns if c not in ("file_id",)]
            return (
                f"Feature '{feature}' not found. Available: {', '.join(available[:15])}"
            )

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
        """Identify polishing runs whose value for one summary metric falls outside Tukey IQR fences (Q1 − 1.5·IQR, Q3 + 1.5·IQR).

        Use when the user asks for outliers, anomalies, or files that "stand
        out" on a specific metric. Returns the offending filenames so the
        agent can quote them.

        Args:
            feature: Exact summary-metric column name from `get_dataset_summary`
                (e.g. 'Removal', 'COF', 'Mean Temp', 'WIWNU'). Must be a
                literal match.

        Returns:
            Plain text (no chart): IQR bounds plus, for each outlier,
            filename, value, direction (above/below), and absolute deviation
            from the nearest fence. If the feature is constant or has no
            outliers, that is stated explicitly.
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
        """Build the best removal prediction model for the loaded dataset by running FLAML AutoML across nine regressors with 5-fold cross-validation.

        Call this DIRECTLY whenever the user asks to train, build, refresh,
        or rebuild a prediction model. Do NOT call `get_dataset_summary`,
        `get_feature_statistics`, or `detect_outliers` first — this tool
        already surfaces data-quality warnings.

        Side effect: when training succeeds, the prediction form on the right
        side of the canvas is populated with the trained categorical options
        and made visible. Tell the user it is ready; do NOT ask whether to
        open it.

        Args:
            time_budget: Search budget in seconds. Default 30. ANY positive
                integer is valid — there is NO minimum (1, 5, 15, 30, 60, 120
                are all accepted). Wall-clock time ≈ time_budget plus a few
                seconds for out-of-fold metric evaluation. Longer budgets do
                NOT guarantee better results on small datasets (under 100
                files); they can overfit by selecting overly complex models.
                Practical defaults: <100 files → 30s; 100–500 files → 60s;
                500+ files → 120s.

        Returns:
            Plain text (no chart): best model name, held-out 5-fold CV
            metrics (R², CV RMSE in Å, CV MAE in Å), training timing,
            top-5 model leaderboard with per-model RMSE, permutation
            feature importances (R² drop), and data-quality warnings.
            All removal numbers are in Ångström. Cite the exact R² and
            RMSE values from this output — never invent them.
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
        prefix = [
            k for k in known if k.lower().startswith(vl) or vl.startswith(k.lower())
        ]
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
        """Open and pre-fill the canvas prediction form so the user can run the trained model on a new process configuration.

        Requires that `run_automl` has already produced a model. The prediction
        itself is computed deterministically when the user clicks Predict in
        the form — never produce a removal number yourself.

        Pass only the values the user explicitly named; leave the rest as None.
        Categorical arguments must be exact trained-category values (the same
        values listed in `get_dataset_summary`'s Categorical breakdown). The
        tool will fuzzy-resolve a partial value (e.g. 'CU4545F' →
        'CU4545F-300') when there is exactly one candidate, but on any
        ambiguity returns an "Unknown {column}" message — at that point ask
        the user, do NOT guess.

        Units are fixed: PSI for pressure, minutes for polish time. Do not
        accept or pass kPa, bar, seconds, or other units.

        Args:
            pressure_psi: Down-force pressure in PSI. Optional.
            polish_time: Polish duration in minutes. Optional.
            wafer: Exact Wafer category from training (e.g. 'Cu', 'Ta'). Optional.
            pad: Exact Pad category from training (e.g. 'IC1010'). Optional.
            slurry: Exact Slurry category from training (e.g. 'CU4545F-300'). Optional.
            conditioner: Exact Conditioner category from training. Optional.

        Returns:
            Dict consumed by the canvas. The agent receives only the text
            `message` field — confirming the form is open with which values
            pre-filled and listing the available trained-category options for
            each dropdown. The Plotly figure side of the canvas is unchanged.
            No prediction number is produced here.
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
            "Wafer": wafer,
            "Pad": pad,
            "Slurry": slurry,
            "Conditioner": conditioner,
        }
        prefill = {}
        try:
            for col, val in provided.items():
                if val is not None and str(val).strip():
                    prefill[col] = self._resolve_category(str(val), col)
        except ValueError as exc:
            return {"message": f"Cannot open form: {exc}"}

        if pressure_psi is not None:
            prefill["Pressure PSI"] = float(pressure_psi)
        if polish_time is not None:
            prefill["Polish Time"] = float(polish_time)

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

    def analyze_sensitivity(
        self,
        feature: str,
        pressure_psi: float = None,
        polish_time: float = None,
        wafer: str = None,
        pad: str = None,
        slurry: str = None,
        conditioner: str = None,
        n_points: int = 11,
    ) -> dict:
        """Sweep one recipe knob across its trained range while holding the other inputs at a baseline, and predict Removal at each step (One-Factor-At-A-Time sensitivity on the trained model).

        Use for trade-off / trend questions: "how does Pressure affect
        Removal", "sensitivity of Removal to Polish Time", "compare predicted
        Removal across pads". Requires a model trained by `run_automl`.

        Baseline defaults: median for unspecified numerical features
        (Pressure PSI, Polish Time), mode for unspecified categoricals
        (Wafer, Pad, Slurry, Conditioner). User-supplied baseline arguments
        override defaults; the swept feature's own argument is ignored. Grid
        is clamped to the training envelope (min..max for numerics, every
        trained category for categoricals) so the model never extrapolates.

        Args:
            feature: Exact knob to sweep. One of 'Pressure PSI',
                'Polish Time', 'Wafer', 'Pad', 'Slurry', 'Conditioner'.
            pressure_psi: Optional baseline pressure (PSI).
            polish_time: Optional baseline polish time (minutes).
            wafer: Optional baseline Wafer category (exact trained value).
            pad: Optional baseline Pad category.
            slurry: Optional baseline Slurry category.
            conditioner: Optional baseline Conditioner category.
            n_points: Numeric grid density (3..25, default 11). Ignored for
                categoricals.

        Returns:
            Dict with two keys:
            - 'figure' — Plotly line+ribbon (numeric) or bar+error
              (categorical) of Predicted Removal Å vs the swept knob, with
              ±1σ uncertainty.
            - 'summary' — text the agent receives: feature swept, baseline
              values held fixed, every (knob → predicted Å ± σ) grid point,
              predicted-removal range, endpoint slope (numeric), and a
              monotonicity flag. Cite values verbatim; do NOT interpolate
              between grid points.
        """
        if self.ml.automl is None:
            return {
                "figure": self._empty_fig("No model trained."),
                "summary": (
                    "No model trained yet. Call run_automl first, then "
                    "re-run analyze_sensitivity."
                ),
            }

        valid = list(PREDICTION_NUMERICAL_FEATURES) + list(
            PREDICTION_CATEGORICAL_FEATURES
        )
        if feature not in valid:
            return {
                "figure": self._empty_fig(f"Unknown feature: {feature}"),
                "summary": (
                    f"Unknown feature '{feature}'. Valid options: {', '.join(valid)}."
                ),
            }

        df = self.ml.train_df
        is_numeric = feature in PREDICTION_NUMERICAL_FEATURES

        baseline = {}
        for col in PREDICTION_NUMERICAL_FEATURES:
            baseline[col] = float(df[col].median())
        for col in PREDICTION_CATEGORICAL_FEATURES:
            baseline[col] = str(df[col].mode().iloc[0])

        overrides = {
            "Pressure PSI": pressure_psi,
            "Polish Time": polish_time,
            "Wafer": wafer,
            "Pad": pad,
            "Slurry": slurry,
            "Conditioner": conditioner,
        }
        try:
            for col, val in overrides.items():
                if val is None or col == feature:
                    continue
                if col in PREDICTION_NUMERICAL_FEATURES:
                    fv = float(val)
                    if fv < 0:
                        raise ValueError(f"{col} must be non-negative, got {fv}.")
                    baseline[col] = fv
                else:
                    baseline[col] = self._resolve_category(str(val), col)
        except ValueError as exc:
            return {
                "figure": self._empty_fig(f"Bad baseline: {exc}"),
                "summary": f"Cannot run sensitivity: {exc}",
            }

        if is_numeric:
            col_min = float(df[feature].min())
            col_max = float(df[feature].max())
            if col_max <= col_min:
                return {
                    "figure": self._empty_fig(
                        f"{feature} is constant in training data."
                    ),
                    "summary": (
                        f"Cannot sweep {feature}: it is constant "
                        f"({col_min}) in the training data so the model "
                        f"learned no effect."
                    ),
                }
            n = int(max(3, min(25, n_points)))
            grid = np.linspace(col_min, col_max, n).tolist()
            x_labels = [round(v, 4) for v in grid]
        else:
            cats = self.ml.get_category_options().get(feature, [])
            if len(cats) < 2:
                return {
                    "figure": self._empty_fig(
                        f"{feature} has fewer than 2 trained categories."
                    ),
                    "summary": (
                        f"Cannot sweep {feature}: only {len(cats)} trained "
                        f"category — need at least 2 to compare."
                    ),
                }
            grid = list(cats)
            x_labels = list(cats)

        predictions = []
        sigmas = []
        for g in grid:
            kw = dict(baseline)
            kw[feature] = g
            try:
                res = self.ml.predict(**kw)
            except Exception as exc:
                return {
                    "figure": self._empty_fig(f"Predict failed: {exc}"),
                    "summary": f"Sensitivity sweep failed: {exc}",
                }
            predictions.append(float(res["prediction"]))
            sigmas.append(float(res["uncertainty"]))

        fig = self._sensitivity_figure(
            feature, x_labels, predictions, sigmas, is_numeric
        )
        summary = self._sensitivity_summary(
            feature, baseline, grid, predictions, sigmas, is_numeric
        )
        return {"figure": fig, "summary": summary}

    def get_model_diagnostics(self) -> str:
        """Report detailed diagnostics for the currently trained removal-rate model — out-of-fold residual stats, held-out 5-fold CV metrics, data-quality warnings, and best-config hyperparameters.

        Use to confirm a model has been trained and to inspect its residual
        behavior. Returns an error string if no model is trained — that
        error is the canonical signal that the user has not yet run
        `run_automl`.

        Takes no arguments.

        Returns:
            Plain text (no chart): best-model name, held-out CV (R², RMSE in
            Å, MAE in Å), training file count, out-of-fold residual mean/std/
            range, best hyperparameter config, and any data-quality warnings.
            Removal units are Å. Cite values directly.
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
        """Plot one summary metric against another across all polishing runs as a scatter (one point per file), optionally colored by a categorical and filtered to a subset.

        Use for relationship questions ("plot Removal vs Pressure", "scatter
        COF against Mean Temp", "Removal vs Pressure colored by Pad").

        Args:
            x_feature: Exact summary-metric column for the x-axis. Valid
                names: COF, Fy, Var Fy, Fz, Var Fz, Mean Temp, Init Temp,
                High Temp, Removal, WIWNU, Mean Pressure, Mean Velocity, P.V,
                COF.P.V, Sommerfeld, Removal Rate, Pressure PSI, Polish Time.
            y_feature: Exact summary-metric column for the y-axis (same
                valid names as x_feature).
            color_by: Optional categorical for per-group coloring. Must be
                exactly one of: Wafer, Pad, Slurry, Conditioner.
            filter_column: Optional column name to subset rows on. Pair with
                filter_value.
            filter_value: Exact value to match in filter_column — must be a
                value present in the dataset. Inexact / paraphrased values
                return an error rather than silently producing an empty plot.

        Returns:
            Dict with two keys:
            - 'figure' — Plotly scatter rendered in the canvas to the user
              (you cannot see it).
            - 'summary' — text the agent receives: point count, Pearson r
              with sign, x range, y range, and the color-by group count when
              applicable. Cite r and the ranges from this string verbatim;
              do NOT invent clusters, bands, or outliers not present here.
        """
        df = self.dm.get_all_data()
        if df.empty:
            return {
                "figure": self._empty_fig("No data loaded."),
                "summary": "No data loaded.",
            }

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
            valid = sorted(
                str(v) for v in df[filter_column].dropna().unique() if str(v)
            )
            if str(filter_value) not in valid:
                return (
                    f"Filter value '{filter_value}' not found in column "
                    f"'{filter_column}'. Valid values: {', '.join(valid)}"
                )
            df = df[df[filter_column] == filter_value]

        fig = go.Figure()
        if color_by and color_by in df.columns:
            for i, (group, group_df) in enumerate(df.groupby(color_by)):
                fig.add_trace(
                    go.Scatter(
                        x=group_df.get(x_feature),
                        y=group_df.get(y_feature),
                        mode="markers",
                        name=str(group),
                        marker=dict(
                            size=9, color=CLUSTER_COLORS[i % len(CLUSTER_COLORS)]
                        ),
                        text=group_df.get("File Name"),
                        hovertemplate=f"<b>%{{text}}</b><br>{x_feature}: %{{x:.4g}}<br>{y_feature}: %{{y:.4g}}<extra>{group}</extra>",
                    )
                )
        else:
            fig.add_trace(
                go.Scatter(
                    x=df.get(x_feature),
                    y=df.get(y_feature),
                    mode="markers",
                    marker=dict(size=9, color=COLORS["accent"]),
                    text=df.get("File Name"),
                    hovertemplate=f"<b>%{{text}}</b><br>{x_feature}: %{{x:.4g}}<br>{y_feature}: %{{y:.4g}}<extra></extra>",
                )
            )

        # Build a text summary for the LLM.
        common = df[[x_feature, y_feature]].dropna()
        n = len(common)
        summary_lines = [f"Scatter: {y_feature} vs {x_feature}, n={n} points"]
        if n >= 3:
            r_val = float(np.corrcoef(common[x_feature], common[y_feature])[0, 1])
            if r_val > 0:
                direction = f"positive: {x_feature} up \u2192 {y_feature} up"
            elif r_val < 0:
                direction = f"negative: {x_feature} up \u2192 {y_feature} down"
            else:
                direction = "zero: no linear trend"
            summary_lines.append(f"  Pearson r={r_val:.3f} ({direction})")
        summary_lines.append(
            f"  x range: {common[x_feature].min():.4g} to {common[x_feature].max():.4g}"
        )
        summary_lines.append(
            f"  y range: {common[y_feature].min():.4g} to {common[y_feature].max():.4g}"
        )
        if color_by and color_by in df.columns:
            summary_lines.append(
                f"  Colored by {color_by} ({df[color_by].nunique()} groups)"
            )

        fig.update_layout(**DARK_LAYOUT)
        fig.update_layout(
            title=f"{y_feature} vs {x_feature}",
            xaxis_title=x_feature,
            yaxis_title=y_feature,
        )
        return {"figure": fig.to_plotly_json(), "summary": "\n".join(summary_lines)}

    def generate_distribution(self, feature: str, group_by: str = None) -> dict:
        """Plot the cross-run distribution of one summary metric — a histogram by default, or a per-category box plot when group_by is given.

        Use for "show the distribution of …", "histogram of Removal", "how is
        COF spread across pads".

        Args:
            feature: Exact summary-metric column to plot. Valid names: COF,
                Fy, Var Fy, Fz, Var Fz, Mean Temp, Init Temp, High Temp,
                Removal, WIWNU, Mean Pressure, Mean Velocity, P.V, COF.P.V,
                Sommerfeld, Removal Rate, Pressure PSI, Polish Time.
            group_by: Optional categorical for a grouped box plot. Must be
                exactly one of: Wafer, Pad, Slurry, Conditioner. Omit for a
                single histogram across all runs.

        Returns:
            Dict with two keys:
            - 'figure' — Plotly histogram or box plot rendered to the user.
            - 'summary' — text the agent receives. For histogram: n, mean,
              std, min, max, skewness with direction. For grouped box: per-
              group mean / median / n plus the highest- and lowest-mean
              groups. Cite values directly; do not infer modes, gaps, or
              outliers not present in the summary.
        """
        df = self.dm.get_all_data()
        if df.empty:
            return {
                "figure": self._empty_fig("No data loaded."),
                "summary": "No data loaded.",
            }

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
                fig.add_trace(
                    go.Box(
                        y=group_df.get(feature),
                        name=str(group),
                        marker_color=CLUSTER_COLORS[i % len(CLUSTER_COLORS)],
                    )
                )
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
                summary_lines.append(
                    f"  Highest mean: {group_means.idxmax()} ({group_means.max():.4g})"
                )
                summary_lines.append(
                    f"  Lowest mean: {group_means.idxmin()} ({group_means.min():.4g})"
                )
        else:
            fig.add_trace(
                go.Histogram(
                    x=df.get(feature),
                    marker_color=COLORS["accent"],
                    marker_line=dict(color=COLORS["border_light"], width=1),
                    opacity=0.85,
                )
            )
            fig.update_layout(title=f"Distribution of {feature}")
            # Summary for histogram.
            valid = df[feature].dropna()
            summary_lines.append(f"Distribution of {feature} (n={len(valid)})")
            summary_lines.append(f"  mean={valid.mean():.4g}, std={valid.std():.4g}")
            summary_lines.append(f"  min={valid.min():.4g}, max={valid.max():.4g}")
            skew_val = float(valid.skew())
            skew_dir = (
                "right-skewed"
                if skew_val > 0.5
                else ("left-skewed" if skew_val < -0.5 else "roughly symmetric")
            )
            summary_lines.append(f"  skewness={skew_val:.2f} ({skew_dir})")

        fig.update_layout(**DARK_LAYOUT)
        fig.update_layout(yaxis_title="Count" if not group_by else feature)
        return {"figure": fig.to_plotly_json(), "summary": "\n".join(summary_lines)}

    def generate_bar_chart(self, feature: str, group_by: str) -> dict:
        """Compare the mean of one summary metric across the levels of a categorical, with one bar per level and standard-deviation error bars.

        Use for "compare Removal across Pads", "average COF by Slurry",
        "which Conditioner gives the highest removal rate".

        Args:
            feature: Exact summary-metric column for the y-axis. Valid names:
                COF, Fy, Var Fy, Fz, Var Fz, Mean Temp, Init Temp, High Temp,
                Removal, WIWNU, Mean Pressure, Mean Velocity, P.V, COF.P.V,
                Sommerfeld, Removal Rate, Pressure PSI, Polish Time.
            group_by: Categorical for the x-axis. Required. Must be exactly
                one of: Wafer, Pad, Slurry, Conditioner.

        Returns:
            Dict with two keys:
            - 'figure' — Plotly bar chart with error bars rendered to the user.
            - 'summary' — text the agent receives: per-group mean and std,
              plus highest-mean and lowest-mean groups. Cite values directly.
        """
        df = self.dm.get_all_data()
        if df.empty:
            return {
                "figure": self._empty_fig("No data loaded."),
                "summary": "No data loaded.",
            }

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
        fig.add_trace(
            go.Bar(
                x=means.index.astype(str),
                y=means.values,
                error_y=dict(type="data", array=stds.values, visible=True),
                marker_color=COLORS["accent"],
            )
        )

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
        """Compute and visualize the Pearson correlation matrix among numerical summary metrics — answers "what drives removal", "what correlates with what", "find the strongest relationships".

        The default feature set covers every measured output plus the two
        controllable process parameters (Pressure PSI, Polish Time) — these
        matter physically via Preston's equation and engineers almost always
        want them in the matrix. Constant columns (σ = 0) are dropped
        automatically because their correlations are mathematically undefined;
        their names appear in the summary so the agent can explain the
        omission.

        Args:
            features: Optional list of exact summary-metric column names.
                Omit or pass an empty list to use the default set. Explicit
                lists are filtered the same way (constants always dropped).
                For discovery questions, prefer omitting this argument.

        Returns:
            Dict with two keys:
            - 'figure' — Plotly heatmap with annotated r values, rendered
              to the user.
            - 'summary' — text the agent receives: any constant features
              excluded, the full list of correlations with Removal sorted
              by |r|, and the top-5 strongest pairwise correlations. Cite
              the exact r values from this string (e.g. 'r=0.55'); never
              describe color patterns or "blocks" in the heatmap that the
              summary does not enumerate.
        """
        df = self.dm.get_all_data()
        if df.empty:
            return {
                "figure": self._empty_fig("No data loaded."),
                "summary": "No data loaded.",
            }

        if not features:  # None or empty list → use all defaults
            features = [f for f in CORRELATION_FEATURES if f in df.columns]
        else:
            features = [f for f in features if f in df.columns]

        numeric_df = (
            df[features].select_dtypes(include=[np.number]).dropna(axis=1, how="all")
        )

        # Drop constant columns — correlation is undefined when σ = 0.
        constant_cols = [
            c for c in numeric_df.columns if numeric_df[c].nunique(dropna=True) <= 1
        ]
        if constant_cols:
            numeric_df = numeric_df.drop(columns=constant_cols)

        if numeric_df.shape[1] < 2:
            return {
                "figure": self._empty_fig(
                    "Not enough varying numerical features to correlate."
                ),
                "summary": (
                    "Correlation heatmap could not be built: fewer than two "
                    "varying features remained after dropping constants "
                    f"({', '.join(constant_cols) or 'none'})."
                ),
            }

        corr = numeric_df.corr()

        fig = go.Figure(
            data=go.Heatmap(
                z=corr.values,
                x=corr.columns.tolist(),
                y=corr.index.tolist(),
                colorscale="RdBu_r",
                zmid=0,
                text=np.round(corr.values, 2),
                texttemplate="%{text}",
                textfont={"size": 10},
            )
        )

        summary_lines = []
        if constant_cols:
            summary_lines.append(
                f"Excluded (constant in this dataset): {', '.join(constant_cols)}"
            )

        if "Removal" in corr.columns:
            removal_corr = (
                corr["Removal"].drop("Removal").sort_values(key=abs, ascending=False)
            )
            summary_lines.append("Correlations with Removal:")
            for feat, val in removal_corr.items():
                if val > 0:
                    arrow = f"Removal up \u2192 {feat} up"
                elif val < 0:
                    arrow = f"Removal up \u2192 {feat} down"
                else:
                    arrow = "no linear trend"
                summary_lines.append(f"  {feat}: r={val:.2f} ({arrow})")

        pairs = [
            (a, b, corr.loc[a, b]) for a, b in itertools.combinations(corr.columns, 2)
        ]
        pairs.sort(key=lambda x: abs(x[2]), reverse=True)
        summary_lines.append("Strongest overall correlations:")
        for a, b, r in pairs[:5]:
            if r > 0:
                arrow = f"{a} up \u2192 {b} up"
            elif r < 0:
                arrow = f"{a} up \u2192 {b} down"
            else:
                arrow = "no linear trend"
            summary_lines.append(f"  {a} vs {b}: r={r:.2f} ({arrow})")

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
        """Plot per-frame time-series traces (force, torque, temperature, COF, etc.) for ONE polishing run vs time in seconds.

        Use to inspect within-run behavior of a specific .dat file. The
        per-frame schema is DIFFERENT from the per-file summary metrics —
        e.g. summary `Fz` corresponds to time-series `Fz Total (lbf)`,
        summary `Mean Temp` corresponds to time-series `IR Temperature`.
        Always resolve user words against `get_dataset_summary`'s
        "Time-series columns" section, not the Summary metrics section.

        Args:
            filename: Exact filename from the Files: section of
                `get_dataset_summary`'s output. Do not invent or abbreviate.
            features: List of exact time-series column names (NOT summary
                metric names). Unknown names return a clarification error
                rather than an empty chart. All features share one y-axis;
                if their magnitudes differ greatly (e.g. COF 0–1 vs Force
                0–300 lbf), call this tool separately per feature for
                readable scaling. Do NOT pass `'time (s)'` — it is the x-axis.
            y_min: Lower y-axis bound. Pass ONLY when the user stated a
                numeric lower bound (e.g. "plot COF from 0 to 2"). MUST be
                paired with y_max — passing only one is ambiguous and
                returns a clarification request. Never invent bounds.
            y_max: Upper y-axis bound. Same rule as y_min. Units match the
                plotted feature (lbf for force, °C for IR Temperature, etc.).
            x_min: Lower x-axis bound in SECONDS. Pass ONLY for an explicit
                user-stated time window (e.g. "first 30 seconds" → x_min=0,
                x_max=30). MUST be paired with x_max. Auto-ranges over the
                full file when both are unset.
            x_max: Upper x-axis bound in SECONDS. Same rule as x_min.

        Default y-axis behavior when no range is passed:
            - features == ['COF']: y pinned to [0, 1] (CMP convention).
            - anything else: auto-range from data.

        Returns:
            Dict with two keys:
            - 'figure' — Plotly multi-trace line plot rendered to the user.
            - 'summary' — text the agent receives: per-feature min, max,
              mean, and start-vs-end trend ("increasing" / "decreasing" /
              "stable") clipped to the steady polish interval (transients
              excluded). On invalid input the summary starts with
              "Ambiguous input:" or "Unknown time-series feature(s):" —
              treat that as a clarification signal, not a result.
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
            return {
                "figure": self._empty_fig(f"File '{filename}' not found."),
                "summary": f"File '{filename}' not found.",
            }

        unknown = [f for f in features if f not in ts_data.columns]
        if unknown:
            features_only = [c for c in ts_data.columns if c != "time (s)"]
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

        x_values = ts_data["time (s)"] if "time (s)" in ts_data.columns else None
        x_title = "Time (s)" if x_values is not None else "Sample"

        # Clip stats to the steady polish interval so transients (startup/
        # shutdown spikes when forces approach zero) don't dominate the summary
        # the agent reports back to the user. The chart still plots the full
        # time series — only the summary stats are clipped.
        interval = self.dm.get_file_interval(filename)
        stats_data = ts_data
        interval_note = None
        if interval and len(interval) == 2 and "time (s)" in ts_data.columns:
            start_s, end_s = interval
            mask = (ts_data["time (s)"] >= start_s) & (ts_data["time (s)"] <= end_s)
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
                trace_kwargs["x"] = x_values
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
        elif features == ["COF"]:
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
        """Render the four standard diagnostic charts for the currently trained removal-rate model — predicted vs actual, permutation feature importance, residuals vs predicted, and residual distribution.

        Requires that `run_automl` has produced a model. Use whenever the
        user asks "how is the model doing", "show diagnostics", "show
        residuals", "what's most important". Returns a no-model placeholder
        if nothing is trained.

        Takes no arguments.

        Returns:
            Dict with two keys:
            - 'figures' — list of 4 Plotly figures rendered side-by-side to
              the user (predicted vs actual with |error| color, permutation
              importance bars, residuals vs predicted, residual histogram).
              All removal axes are in Å.
            - 'summary' — text the agent receives: best-model name, R²,
              RMSE in Å, MAE in Å, residual mean/std/range, top-5 features
              by importance, and the three runs with the largest absolute
              error (filename, actual, predicted, residual). Cite values
              directly; never describe the shape of the residual histogram
              beyond what the summary states.
        """
        try:
            diag = self.ml.get_diagnostics()
        except ValueError:
            empty = self._empty_fig("No model trained.")
            return {
                "figures": [empty, empty, empty, empty],
                "summary": "No model trained yet.",
            }

        y_true = np.array(diag["y_true"])
        y_pred = np.array(diag["y_pred"])
        file_names = diag["file_names"]
        importances = diag["feature_importances"]
        residuals = y_true - y_pred

        # 1. Predicted vs Actual
        fig1 = go.Figure()
        abs_err = np.abs(y_pred - y_true)
        fig1.add_trace(
            go.Scatter(
                x=y_true,
                y=y_pred,
                mode="markers",
                marker=dict(
                    size=9,
                    color=abs_err,
                    colorscale="Bluered",
                    showscale=True,
                    colorbar=dict(title="|Error|"),
                ),
                text=file_names,
                hovertemplate="<b>%{text}</b><br>Actual: %{x:.0f}Å<br>Predicted: %{y:.0f}Å<extra></extra>",
            )
        )
        all_vals = np.concatenate([y_true, y_pred])
        lo, hi = float(np.min(all_vals)), float(np.max(all_vals))
        margin = (hi - lo) * 0.05
        fig1.add_trace(
            go.Scatter(
                x=[lo - margin, hi + margin],
                y=[lo - margin, hi + margin],
                mode="lines",
                line=dict(dash="dash", color=COLORS["text_secondary"]),
                showlegend=False,
                hoverinfo="skip",
            )
        )
        fig1.update_layout(**DARK_LAYOUT)
        fig1.update_layout(
            title="Predicted vs Actual",
            xaxis_title="Actual Removal (Å)",
            yaxis_title="Predicted Removal (Å)",
            showlegend=False,
        )

        # 2. Feature Importance
        fig2 = go.Figure()
        sorted_imp = sorted(importances.items(), key=lambda x: x[1])
        fig2.add_trace(
            go.Bar(
                x=[v for _, v in sorted_imp],
                y=[k for k, _ in sorted_imp],
                orientation="h",
                marker_color=COLORS["accent"],
            )
        )
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
        fig3.add_trace(
            go.Scatter(
                x=y_pred,
                y=residuals,
                mode="markers",
                marker=dict(size=9, color=COLORS["accent"]),
                text=file_names,
                hovertemplate="<b>%{text}</b><br>Predicted: %{x:.0f}Å<br>Residual: %{y:.0f}Å<extra></extra>",
            )
        )
        fig3.add_hline(y=0, line_dash="dash", line_color=COLORS["text_secondary"])
        fig3.update_layout(**DARK_LAYOUT)
        fig3.update_layout(
            title="Residuals vs Predicted",
            xaxis_title="Predicted Removal (Å)",
            yaxis_title="Residual (Å)",
            showlegend=False,
        )

        # 4. Residual Distribution
        fig4 = go.Figure()
        fig4.add_trace(
            go.Histogram(
                x=residuals,
                nbinsx=max(8, len(residuals) // 4),
                marker_color=COLORS["accent"],
                opacity=0.85,
            )
        )
        fig4.add_annotation(
            text=f"Mean: {np.mean(residuals):.0f}  Std: {np.std(residuals):.0f}",
            xref="paper",
            yref="paper",
            x=0.02,
            y=1.0,
            xanchor="left",
            yanchor="top",
            showarrow=False,
            font=dict(size=11, color=COLORS["text_secondary"]),
        )
        fig4.update_layout(**DARK_LAYOUT)
        fig4.update_layout(
            title="Residual Distribution",
            xaxis_title="Residual (Å)",
            yaxis_title="Count",
            showlegend=False,
        )

        # Build a text summary of model diagnostics for the LLM.
        sorted_imp_desc = sorted(importances.items(), key=lambda x: x[1], reverse=True)
        summary_lines = [
            f"Model diagnostics ({diag['metrics']['best_model']}):",
            f"  R²={diag['metrics']['r2']:.3f}, RMSE={diag['metrics']['rmse']:.0f}Å, MAE={diag['metrics']['mae']:.0f}Å",
            f"  Residuals: mean={np.mean(residuals):.1f}, std={np.std(residuals):.1f}, "
            f"range=[{np.min(residuals):.1f}, {np.max(residuals):.1f}]",
            "  Top features: "
            + ", ".join(f"{k}={v:.3f}" for k, v in sorted_imp_desc[:5]),
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
            "figures": [
                fig1.to_plotly_json(),
                fig2.to_plotly_json(),
                fig3.to_plotly_json(),
                fig4.to_plotly_json(),
            ],
            "summary": "\n".join(summary_lines),
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _sensitivity_figure(
        self,
        feature: str,
        x_labels: list,
        predictions: list,
        sigmas: list,
        is_numeric: bool,
    ) -> dict:
        """Plot a sensitivity sweep — line+ribbon for numerics, bars+error for categoricals."""
        fig = go.Figure()
        upper = [p + s for p, s in zip(predictions, sigmas)]
        lower = [p - s for p, s in zip(predictions, sigmas)]

        if is_numeric:
            fig.add_trace(
                go.Scatter(
                    x=x_labels + x_labels[::-1],
                    y=upper + lower[::-1],
                    fill="toself",
                    fillcolor="rgba(99, 179, 237, 0.20)",
                    line=dict(width=0),
                    hoverinfo="skip",
                    showlegend=False,
                )
            )
            fig.add_trace(
                go.Scatter(
                    x=x_labels,
                    y=predictions,
                    mode="lines+markers",
                    line=dict(color=COLORS["accent"], width=2),
                    marker=dict(size=8, color=COLORS["accent"]),
                    hovertemplate=(
                        f"{feature}: %{{x}}<br>"
                        "Predicted Removal: %{y:.0f}\u00c5<extra></extra>"
                    ),
                    showlegend=False,
                )
            )
            x_title = feature + (
                " (PSI)"
                if feature == "Pressure PSI"
                else " (min)"
                if feature == "Polish Time"
                else ""
            )
        else:
            fig.add_trace(
                go.Bar(
                    x=x_labels,
                    y=predictions,
                    error_y=dict(type="data", array=sigmas, visible=True),
                    marker_color=COLORS["accent"],
                    hovertemplate=(
                        f"{feature}: %{{x}}<br>"
                        "Predicted Removal: %{y:.0f}\u00c5<extra></extra>"
                    ),
                )
            )
            x_title = feature

        fig.update_layout(**DARK_LAYOUT)
        fig.update_layout(
            title=f"Sensitivity: Predicted Removal vs {feature}",
            xaxis_title=x_title,
            yaxis_title="Predicted Removal (\u00c5)",
            showlegend=False,
        )
        return fig.to_plotly_json()

    def _sensitivity_summary(
        self,
        feature: str,
        baseline: dict,
        grid: list,
        predictions: list,
        sigmas: list,
        is_numeric: bool,
    ) -> str:
        """Build the deterministic summary string for analyze_sensitivity."""
        lines = [f"Sensitivity sweep of {feature} (n={len(grid)} points)."]
        held = []
        for k, v in baseline.items():
            if k == feature:
                continue
            held.append(f"{k}={v:.3f}" if isinstance(v, float) else f"{k}={v}")
        lines.append("Baseline (held fixed): " + ", ".join(held))
        lines.append("Per-point predictions (Predicted Removal \u00c5 \u00b1 1\u03c3):")
        for g, p, s in zip(grid, predictions, sigmas):
            gv = f"{g:.3f}" if isinstance(g, float) else str(g)
            lines.append(f"  {feature}={gv} -> {p:.0f}\u00c5 \u00b1 {s:.0f}")

        p_min, p_max = min(predictions), max(predictions)
        lines.append(
            f"Predicted Removal range: {p_min:.0f}\u00c5 .. {p_max:.0f}\u00c5 "
            f"(span {p_max - p_min:.0f}\u00c5)."
        )

        if is_numeric and len(grid) >= 2:
            delta_x = grid[-1] - grid[0]
            delta_y = predictions[-1] - predictions[0]
            slope = delta_y / delta_x if delta_x != 0 else 0.0
            unit_label = (
                "\u00c5/PSI"
                if feature == "Pressure PSI"
                else "\u00c5/min"
                if feature == "Polish Time"
                else f"\u00c5/{feature}-unit"
            )
            lines.append(
                f"Endpoint slope: {slope:+.0f} {unit_label} "
                f"(from {feature}={grid[0]:.3f} to {grid[-1]:.3f})."
            )
            diffs = [
                predictions[i + 1] - predictions[i] for i in range(len(predictions) - 1)
            ]
            if all(d >= 0 for d in diffs):
                mono = "monotonically increasing"
            elif all(d <= 0 for d in diffs):
                mono = "monotonically decreasing"
            else:
                mono = "non-monotonic"
            lines.append(f"Monotonicity: {mono}.")
        else:
            i_max = predictions.index(p_max)
            i_min = predictions.index(p_min)
            lines.append(
                f"Highest: {feature}={grid[i_max]} -> {p_max:.0f}\u00c5. "
                f"Lowest: {feature}={grid[i_min]} -> {p_min:.0f}\u00c5."
            )

        lines.append(
            "Cite per-point \u00c5 values verbatim. Do NOT interpolate "
            "between grid points or invent values not in this list."
        )
        return "\n".join(lines)

    def _empty_fig(self, message: str) -> dict:
        """Create an empty Plotly figure with a centered message."""
        fig = go.Figure()
        fig.update_layout(**DARK_LAYOUT)
        fig.add_annotation(
            text=message,
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.5,
            showarrow=False,
            font=dict(size=14, color=COLORS["text_secondary"]),
        )
        return fig.to_plotly_json()

    def get_all_tools(self) -> list:
        """Return list of all tool functions for Ollama registration."""
        return [
            self.get_dataset_summary,
            self.get_file_details,
            self.find_files_by_config,
            self.get_feature_statistics,
            self.detect_outliers,
            self.run_automl,
            self.open_prediction_form,
            self.analyze_sensitivity,
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
            entries.append(
                {
                    "name": fn.__name__,
                    "category": "other",
                    "title": fn.__name__.replace("_", " ").capitalize(),
                    "long": (fn.__doc__ or "").strip(),
                    "examples": [],
                }
            )
    entries.sort(key=lambda e: order.get(e["category"], 99))
    return entries
