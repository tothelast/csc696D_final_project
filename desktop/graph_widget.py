"""Graph Widget - Matplotlib-based interactive graphs."""

import os
import numpy as np
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QMessageBox, QSizePolicy
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from desktop.theme import COLORS, ToastNotification

# Dark theme colors for matplotlib
PLOT_BG_COLOR = COLORS['bg_secondary']  # Plot area background
PLOT_TEXT_COLOR = COLORS['text_primary']  # Labels and titles
PLOT_GRID_COLOR = COLORS['border_light']  # Grid lines


class GraphWidget(QWidget):
    """Widget for displaying interactive matplotlib graphs."""

    def __init__(self, project_dir=None):
        super().__init__()
        self.project_dir = project_dir
        self.current_raw_file = None
        self.current_graph_type = 0
        self.current_interval = [7, 57]
        self.ax = None
        self.last_stats = {}  # Store statistics from last plot
        self.setup_ui()

    def apply_dark_theme(self, ax):
        """Apply dark theme styling to matplotlib axes."""
        # Set axes background
        ax.set_facecolor(PLOT_BG_COLOR)

        # Set text colors for labels and title
        ax.xaxis.label.set_color(PLOT_TEXT_COLOR)
        ax.yaxis.label.set_color(PLOT_TEXT_COLOR)
        ax.title.set_color(PLOT_TEXT_COLOR)

        # Set tick label colors
        ax.tick_params(axis='x', colors=PLOT_TEXT_COLOR)
        ax.tick_params(axis='y', colors=PLOT_TEXT_COLOR)

        # Set spine colors
        for spine in ax.spines.values():
            spine.set_color(PLOT_GRID_COLOR)

    def setup_ui(self):
        """Initialize the UI components."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Create matplotlib figure with better sizing
        self.figure = Figure(dpi=100)
        self.figure.set_facecolor(COLORS['bg_primary'])
        self.canvas = FigureCanvas(self.figure)

        # Make canvas expand to fill available space
        self.canvas.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )

        layout.addWidget(self.canvas)

    def _safe_tight_layout(self):
        """Call tight_layout only when the canvas is large enough to avoid singular matrix errors."""
        w, h = self.canvas.get_width_height()
        if h < 50 or w < 50:
            return
        try:
            self.figure.tight_layout(pad=0.5)
        except Exception:
            pass

    def set_project_dir(self, project_dir):
        """Set the project directory for saving graphs."""
        self.project_dir = project_dir

    def save_graph(self):
        """Save the current graph to the project directory."""
        if not self.current_raw_file:
            QMessageBox.warning(self, "Warning", "No graph to save.")
            return

        if not self.project_dir:
            QMessageBox.warning(self, "Warning", "No project directory set.")
            return

        # Generate filename from file name and graph type
        file_basename = os.path.splitext(self.current_raw_file.file_basename)[0]
        graph_names = ["COF", "Forces", "Temperature"]
        graph_name = (
            graph_names[self.current_graph_type]
            if self.current_graph_type < len(graph_names)
            else "Graph"
        )

        filename = f"{file_basename}_{graph_name}.png"
        file_path = os.path.join(self.project_dir, filename)

        try:
            self.figure.savefig(file_path, dpi=150, bbox_inches='tight', facecolor=COLORS['bg_primary'])
            ToastNotification(f"Saved: {filename}", self)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save graph:\n{str(e)}")

    def apply_axis_scale(self, x_min, x_max, y_min, y_max):
        """Apply custom axis scaling to the current graph."""
        if self.ax is None:
            return

        self.ax.set_xlim(x_min, x_max)
        self.ax.set_ylim(y_min, y_max)
        self.canvas.draw()

    def get_axis_limits(self):
        """Get current axis limits."""
        if self.ax is None:
            return (0, 60, 0, 1)

        x_lim = self.ax.get_xlim()
        y_lim = self.ax.get_ylim()
        return (x_lim[0], x_lim[1], y_lim[0], y_lim[1])

    def plot(self, raw_file, graph_type, interval):
        """Plot the specified graph type.

        Args:
            raw_file: RawFile instance
            graph_type: 0=COF, 1=Forces, 2=Temperature
            interval: [start, end] time interval in seconds

        Returns:
            Tuple of (x_min, x_max, y_min, y_max) axis limits
        """
        # Store current state
        self.current_raw_file = raw_file
        self.current_graph_type = graph_type
        self.current_interval = interval

        self.figure.clear()
        self.ax = None

        if graph_type == 0:
            self.plot_cof(raw_file, interval)
        elif graph_type == 1:
            self.plot_forces(raw_file, interval)
        elif graph_type == 2:
            self.plot_temperature(raw_file, interval)

        self.canvas.draw()

        # Return axis limits for external controls
        return self.get_axis_limits()

    def _plot_traces(self, traces, interval, xlabel, ylabel, title):
        """Plot one or more traces with interval shading, dark theme, legend, and grid.

        Args:
            traces: list of (time_array, data_array, color, label) tuples
            interval: [start, end] time interval in seconds
            xlabel, ylabel, title: axis labels and title
        """
        self.ax = self.figure.add_subplot(111)

        for time_data, y_data, color, label in traces:
            self.ax.plot(time_data, y_data, color=color, linewidth=1, label=label)

        # Highlight interval region
        self.ax.axvspan(interval[0], interval[1], alpha=0.2, color=COLORS['success'], label='Analysis Interval')
        self.ax.axvline(x=interval[0], color=COLORS['success'], linestyle='--', linewidth=1)
        self.ax.axvline(x=interval[1], color=COLORS['success'], linestyle='--', linewidth=1)

        self.ax.set_xlabel(xlabel, fontsize=10)
        self.ax.set_ylabel(ylabel, fontsize=10)
        self.ax.set_title(title, fontsize=12, fontweight='bold')

        self.apply_dark_theme(self.ax)

        legend = self.ax.legend(loc='upper left', bbox_to_anchor=(1.02, 1),
                                facecolor=COLORS['bg_secondary'], edgecolor='none',
                                framealpha=0.9)
        for text in legend.get_texts():
            text.set_color(PLOT_TEXT_COLOR)

        self.ax.grid(True, alpha=0.3, color=PLOT_GRID_COLOR)

        self._safe_tight_layout()
        self.figure.subplots_adjust(right=0.82)

    def plot_cof(self, raw_file, interval):
        """Plot COF vs time."""
        time = raw_file.total_per_frame["time (s)"]
        cof = raw_file.total_per_frame["COF"]

        mask = (time >= interval[0]) & (time <= interval[1])
        time_filtered = time[mask]
        cof_filtered = cof[mask]

        if len(cof_filtered) > 0:
            self.last_stats = {
                "cof_mean": float(np.mean(cof_filtered)),
                "cof_variance": float(np.var(cof_filtered)),
            }
        else:
            self.last_stats = {"cof_mean": 0.0, "cof_variance": 0.0}

        self._plot_traces(
            [(time_filtered, cof_filtered, COLORS['accent'], 'COF')],
            interval, 'Time (s)', 'COF', 'Coefficient of Friction vs Time'
        )

    def plot_forces(self, raw_file, interval):
        """Plot Fy and Fz forces vs time."""
        time = raw_file.total_per_frame["time (s)"]
        fy = raw_file.total_per_frame["Fy Total (lbf)"]
        fz = raw_file.total_per_frame["Fz Total (lbf)"]

        mask = (time >= interval[0]) & (time <= interval[1])
        time_filtered = time[mask]
        fy_filtered = fy[mask]
        fz_filtered = fz[mask]

        if len(fy_filtered) > 0 and len(fz_filtered) > 0:
            self.last_stats = {
                "fy_mean": float(np.mean(fy_filtered)),
                "fy_variance": float(np.var(fy_filtered)),
                "fz_mean": float(np.mean(fz_filtered)),
                "fz_variance": float(np.var(fz_filtered)),
            }
        else:
            self.last_stats = {
                "fy_mean": 0.0,
                "fy_variance": 0.0,
                "fz_mean": 0.0,
                "fz_variance": 0.0,
            }

        self._plot_traces(
            [
                (time_filtered, fy_filtered, COLORS['accent'], 'Fy Total (lbf)'),
                (time_filtered, fz_filtered, COLORS['danger'], 'Fz Total (lbf)'),
            ],
            interval, 'Time (s)', 'Force (lbf)', 'Forces vs Time'
        )

    def plot_temperature(self, raw_file, interval):
        """Plot IR Temperature vs time."""
        hz = raw_file.hz
        num_rows = len(raw_file.raw_data)
        time = np.array([i / hz for i in range(num_rows)])
        temp = raw_file.raw_data["IR Temperature"].values

        mask = (time >= interval[0]) & (time <= interval[1])
        time_filtered = time[mask]
        temp_filtered = temp[mask]

        if len(temp_filtered) > 0:
            self.last_stats = {
                "temp_mean": float(np.mean(temp_filtered)),
                "temp_initial": (
                    float(temp_filtered[0]) if len(temp_filtered) > 0 else 0.0
                ),
                "temp_high": float(np.max(temp_filtered)),
            }
        else:
            self.last_stats = {"temp_mean": 0.0, "temp_initial": 0.0, "temp_high": 0.0}

        self._plot_traces(
            [(time_filtered, temp_filtered, COLORS['warning'], 'IR Temperature')],
            interval, 'Time (s)', 'Temperature (°C)', 'IR Temperature vs Time'
        )

    def get_stats(self):
        """Return the statistics from the last plotted graph."""
        return self.last_stats

    def showEvent(self, event):
        """Handle show events to reapply tight_layout when widget becomes visible."""
        super().showEvent(event)
        if self.ax is not None:
            self._safe_tight_layout()
            self.canvas.draw_idle()

    def resizeEvent(self, event):
        """Handle resize events to reapply tight_layout."""
        super().resizeEvent(event)
        if self.ax is None:
            return
        w, h = self.canvas.get_width_height()
        if h < 50 or w < 50:
            return
        self._safe_tight_layout()
        self.figure.subplots_adjust(right=0.82)  # Keep room for legend
        self.canvas.draw_idle()
