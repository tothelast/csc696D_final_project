"""Dash application entry point. Assembles layout and registers callbacks."""

import dash
import sys
import os

# Add parent directory to path to allow importing from analysis package if running directly
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from dashboard.dash_bridge import DataManager
except ImportError:
    # Fallback if running as a package
    from .dash_bridge import DataManager

from dashboard.styles import INDEX_STRING
from dashboard.layouts import build_app_layout
from dashboard.callbacks import register_callbacks

data_manager = DataManager()

app = dash.Dash(__name__, external_stylesheets=[])
server = app.server

app.index_string = INDEX_STRING
app.layout = build_app_layout()
register_callbacks(app, data_manager)

if __name__ == '__main__':
    app.run(debug=True)
