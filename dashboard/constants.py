"""Shared constants for the Dash analysis application."""

from dash import html

# Features used for K-Means clustering and PCA analysis.
# Excludes non-meaningful columns: 'File Name' (string), 'Wafer #' (identifier),
# 'Notes' (string), 'file_id' (Python object ID — meaningless for analysis).
ANALYSIS_FEATURES = [
    'COF', 'Fy', 'Var Fy', 'Fz', 'Var Fz',
    'Mean Temp', 'Init Temp', 'High Temp',
    'Removal', 'WIWNU',
    'Mean Pressure', 'Mean Velocity', 'P.V', 'COF.P.V', 'Sommerfeld', 'Removal Rate'
]

# Features for correlation analysis. Extends ANALYSIS_FEATURES with the
# controllable process parameters (pressure, polish time) because Preston's
# equation (MRR ∝ P·V·t) makes them the correlations engineers care about
# most. Kept separate from ANALYSIS_FEATURES so PCA / K-Means (which cannot
# tolerate zero-variance columns through StandardScaler) stay safe.
CORRELATION_FEATURES = ANALYSIS_FEATURES + ['Pressure PSI', 'Polish Time']

# Feature explorer axis options with full labels
FEATURE_AXIS_OPTIONS = [
    {'label': 'Coefficient of Friction', 'value': 'COF'},
    {'label': 'Shear Force (Fy)', 'value': 'Fy'},
    {'label': 'Var Fy', 'value': 'Var Fy'},
    {'label': 'Down Force (Fz)', 'value': 'Fz'},
    {'label': 'Var Fz', 'value': 'Var Fz'},
    {'label': 'Mean Temperature', 'value': 'Mean Temp'},
    {'label': 'Init Temperature', 'value': 'Init Temp'},
    {'label': 'High Temperature', 'value': 'High Temp'},
    {'label': 'Removal (\u00c5)', 'value': 'Removal'},
    {'label': 'WIWNU (%)', 'value': 'WIWNU'},
    {'label': 'Mean Pressure (Pa)', 'value': 'Mean Pressure'},
    {'label': 'Mean Velocity (m/s)', 'value': 'Mean Velocity'},
    {'label': 'P\u00b7V (Pa\u00b7m/s)', 'value': 'P.V'},
    {'label': 'COF\u00b7P\u00b7V (Pa\u00b7m/s)', 'value': 'COF.P.V'},
    {'label': 'Sommerfeld #', 'value': 'Sommerfeld'},
    {'label': 'Removal Rate (\u00c5/min)', 'value': 'Removal Rate'},
]

# Scatter plot feature options — maps to total_per_frame column names
# Excludes 'time (s)' (animation axis) and '1 pound force = N' (constant)
SCATTER_FEATURE_OPTIONS = [
    {'label': 'COF', 'value': 'COF'},
    {'label': 'Down Force - Fz (lbf)', 'value': 'Fz Total (lbf)'},
    {'label': 'Shear Force - Fy (lbf)', 'value': 'Fy Total (lbf)'},
    {'label': 'Down Force - Fz (N)', 'value': 'Fz Total (N)'},
    {'label': 'Shear Force - Fy (N)', 'value': 'Fy Total (N)'},
    {'label': 'IR Temperature', 'value': 'IR Temperature'},
    {'label': 'Pressure (Pa)', 'value': 'Pressure (Pa)'},
    {'label': 'Pad Rotation Rate (Rad/s)', 'value': 'Pad Rotation Rate (Rad/s)'},
    {'label': 'Sliding Velocity (m/s)', 'value': 'Average Nominal Wafer Sliding Velocity (m/s)'},
    {'label': 'Sommerfeld - v/P (m/Pa·s)', 'value': 'v / P (m/Pas.s)'},
    {'label': 'P·V (m·Pa/s)', 'value': 'P.V (m.Pa/s)'},
    {'label': 'COF·P·V (Pa·m/s)', 'value': 'COF.P.V (m.Pa/s)'},
]

# Correlation graph IDs and definitions
CORR_GRAPH_IDS = ['corr-stribeck', 'corr-cof-pv', 'corr-temp-pv', 'corr-arrhenius', 'corr-preston', 'corr-wiwnu-pv', 'corr-power-density']

# Graph definitions: (id, x_col, y_col, x_label, y_label, transform_x, transform_y)
CORR_GRAPHS = [
    ('corr-stribeck',  'Sommerfeld', 'COF',           'Pseudo-Sommerfeld Number', 'Mean COF',                'log_axis', 'log_axis'),
    ('corr-cof-pv',    'P.V',       'COF',           'P\u00b7V (Pa\u00b7m/s)',               'Mean COF',                    None, None),
    ('corr-temp-pv',   'P.V',       'Mean Temp',     'P\u00b7V (Pa\u00b7m/s)',               'Mean Pad Temp (C)',           None, None),
    ('corr-arrhenius', 'Mean Temp', 'Removal Rate',  '1/T (1/K)',                            'ln(RR)',                      'inv_kelvin', 'ln'),
    ('corr-preston',   'P.V',       'Removal Rate',  'P\u00b7V (Pa\u00b7m/s)',               'Mean Removal Rate (A/min)',   None, None),
    ('corr-wiwnu-pv',  'P.V',       'WIWNU',       'P\u00b7V (Pa\u00b7m/s)',               'WIWNU (%)',                   None, None),
]

# Display labels with units for the z-score selection chart
SELECTION_LABELS = {
    'COF': 'COF',
    'Fy': 'Fy (lbf)',
    'Var Fy': 'Var Fy (lbf\u00b2)',
    'Fz': 'Fz (lbf)',
    'Var Fz': 'Var Fz (lbf\u00b2)',
    'Mean Temp': 'Mean Temp (\u00b0C)',
    'Init Temp': 'Init Temp (\u00b0C)',
    'High Temp': 'High Temp (\u00b0C)',
    'Removal': 'Removal (\u00c5)',
    'WIWNU': 'WIWNU (%)',
    'Mean Pressure': 'Mean Pressure (Pa)',
    'Mean Velocity': 'Mean Velocity (m/s)',
    'P.V': 'P\u00b7V (Pa\u00b7m/s)',
    'COF.P.V': 'COF\u00b7P\u00b7V (Pa\u00b7m/s)',
    'Sommerfeld': 'Sommerfeld #',
    'Removal Rate': 'Removal Rate (\u00c5/min)',
    'Pressure PSI': 'Pressure (PSI)',
    'Polish Time': 'Polish Time (min)',
    'Directivity': 'Directivity',
}

# Categorical features available for breakdown in PCA selection
CATEGORICAL_FEATURES = ['Wafer', 'Pad', 'Slurry', 'Conditioner']

# Prediction tab constants
PREDICTION_CATEGORICAL_FEATURES = ['Wafer', 'Pad', 'Slurry', 'Conditioner']
PREDICTION_NUMERICAL_FEATURES = ['Pressure PSI', 'Polish Time']
PREDICTION_TARGET = 'Removal'
CATEGORICAL_LABELS = {
    'Wafer': 'Wafer',
    'Pad': 'Pad',
    'Slurry': 'Slurry',
    'Conditioner': 'Conditioner',
}

# Placeholder for variance display
VARIANCE_PLACEHOLDER = [html.Span("Explained Variance: "), html.Strong("--")]
