"""User-facing copy for the 'How can I help?' panel on the AI Agent tab.

This is the ONLY place UI copy for the capabilities panel lives. It is
independent of the technical docstrings in ai/tools.py (which Ollama reads
to build the LLM tool schema). End users never see those docstrings; they
see what's below — written in process-engineering language.

Adding a new capability:
  1. Add the method to AgentTools in ai/tools.py and register it in
     AgentTools.get_all_tools().
  2. Add a TOOL_UI entry here with the four keys below.

Missing entries fall through to a 'More' category with the function name
humanized and the docstring as the long description — the app never
breaks, but the copy reads like a function name until an entry is added.
"""

CATEGORY_TITLES = {
    "explore": "Explore your data",
    "predict": "Build & use prediction models",
    "visualize": "Visualize your data",
    "other": "More",
}

CATEGORY_ORDER = ("explore", "predict", "visualize", "other")

TOOL_UI = {
    # ── Explore your data ─────────────────────────────────────────────
    "get_dataset_summary": {
        "category": "explore",
        "title": "Summarize my dataset",
        "long": "Reports how many files are loaded, the range of key "
        "measurements (pressure, removal), and breaks down "
        "categorical values like wafer, pad, slurry, and conditioner.",
        "examples": ["Summarize my dataset."],
    },
    "get_file_details": {
        "category": "explore",
        "title": "Look up a specific file",
        "long": "Pulls every recorded metric for a single file — COF, "
        "forces, temperature, removal, wafer, pad, slurry, and "
        "conditioner — so you can inspect one run in detail.",
        "examples": ["What are the details for run_023.dat?"],
    },
    "find_files_by_config": {
        "category": "explore",
        "title": "Find files by configuration",
        "long": "Returns the files that match a configuration filter — "
        "wafer, pad, slurry, conditioner, pressure, or polish time. "
        "Use when you want to identify a run by its setup instead "
        "of by file name.",
        "examples": ["Find files with tantalum wafer at 2 psi."],
    },
    "get_feature_statistics": {
        "category": "explore",
        "title": "Statistics for a measurement",
        "long": "Computes mean, standard deviation, min, max, and median "
        "for any measurement. Optionally broken down by wafer, "
        "pad, slurry, or conditioner so you can compare groups.",
        "examples": [
            "What's the average COF across pads?",
            "How does removal vary by slurry?",
        ],
    },
    "detect_outliers": {
        "category": "explore",
        "title": "Find unusual files",
        "long": "Uses an IQR (inter-quartile range) check to flag files "
        "whose values for a given measurement are far above or "
        "below the rest — handy for spotting bad runs.",
        "examples": ["Which files are outliers for removal?"],
    },
    # ── Build & use prediction models ────────────────────────────────
    "run_automl": {
        "category": "predict",
        "title": "Build a prediction model",
        "long": "Automatically tries several model types and picks the best "
        "one at predicting removal from your process settings "
        "(pressure, polish time, pad, wafer, slurry, conditioner). "
        "Training takes about 30 seconds.",
        "examples": ["Build a prediction model."],
    },
    "open_prediction_form": {
        "category": "predict",
        "title": "Predict removal for new conditions",
        "long": "Opens the prediction form on the right side of the screen, "
        "pre-filled with any process conditions you mention, so you "
        "can see the predicted removal for that setup.",
        "examples": ["Predict removal at 5 psi on pad A."],
    },
    "analyze_sensitivity": {
        "category": "predict",
        "title": "Sensitivity sweep",
        "long": "Sweeps one recipe knob (pressure, polish time, pad, "
        "wafer, slurry, or conditioner) across its trained range "
        "while holding the others fixed, and plots how predicted "
        "removal responds. Use to see trade-off curves and how "
        "sensitive the process is to a single setting.",
        "examples": [
            "How does removal change with pressure?",
            "Sensitivity of removal to polish time.",
            "Compare predicted removal across pads.",
        ],
    },
    "get_model_diagnostics": {
        "category": "predict",
        "title": "Check how good the model is",
        "long": "Reports how accurately the current prediction model fits "
        "the data (R², RMSE) and which process settings drive "
        "the predictions most.",
        "examples": ["How accurate is the model?"],
    },
    "generate_model_plots": {
        "category": "predict",
        "title": "Show prediction model charts",
        "long": "Shows the diagnostic charts for the current model: "
        "predicted vs. actual removal, residuals, and a ranking "
        "of which inputs matter most.",
        "examples": ["Show me the model's diagnostic charts."],
    },
    # ── Visualize your data ──────────────────────────────────────────
    "generate_scatter": {
        "category": "visualize",
        "title": "Compare two measurements",
        "long": "Plots one measurement against another as a scatter plot, "
        "optionally coloring points by wafer, pad, slurry, or "
        "conditioner so you can see group-level patterns.",
        "examples": ["Plot COF against removal, colored by pad."],
    },
    "generate_distribution": {
        "category": "visualize",
        "title": "Distribution of a measurement",
        "long": "Plots a histogram (or box plot, if grouped) showing how "
        "the values of one measurement are distributed across all "
        "your files.",
        "examples": ["Show the distribution of COF."],
    },
    "generate_bar_chart": {
        "category": "visualize",
        "title": "Compare by category",
        "long": "Bar chart showing the average of a measurement across "
        "categories (wafer, pad, slurry, conditioner) with error "
        "bars so you can see where the real differences are.",
        "examples": ["Compare removal across pads."],
    },
    "generate_correlation_heatmap": {
        "category": "visualize",
        "title": "Which measurements move together",
        "long": "Heatmap showing how strongly every pair of measurements "
        "moves together — useful for finding which process "
        "settings drive outcomes like removal.",
        "examples": ["Which measurements correlate with removal?"],
    },
    "generate_time_series": {
        "category": "visualize",
        "title": "Plot a run over time",
        "long": "Plots selected measurements over the course of a single "
        "polishing run so you can see how temperature, force, or "
        "COF changed during the process.",
        "examples": [
            "Plot temperature over time for the run on pad <pad> at "
            "<pressure> psi.\n"
            "Configurations you can specify: wafer · pad · slurry · conditioner · pressure · polish time"
        ],
    },
}
