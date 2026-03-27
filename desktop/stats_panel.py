"""Stats Panel - Displays statistics for the current graph type.

A self-contained QFrame widget that shows COF, Forces, or Temperature
statistics using a QStackedWidget to switch between the three views.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QFrame, QStackedWidget,
)

from desktop.theme import COLORS


class StatsPanel(QFrame):
    """Statistics display panel that sits above the graph widget.

    Shows different stats depending on the active graph type:
      - Index 0 (COF): Mean, Variance
      - Index 1 (Forces): Fy mean/var, Fz mean/var
      - Index 2 (Temperature): Mean, Initial, High
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("statsPanel")
        self.setStyleSheet("""
            #statsPanel {
                background-color: transparent;
                border: none;
                padding: 8px;
            }
        """)
        self.setFixedHeight(80)

        container_layout = QVBoxLayout(self)
        container_layout.setContentsMargins(12, 8, 12, 8)
        container_layout.setSpacing(4)

        self._stats_stack = QStackedWidget()
        container_layout.addWidget(self._stats_stack)

        # COF Stats (index 0)
        cof_stats = QWidget()
        cof_layout = QHBoxLayout(cof_stats)
        cof_layout.setContentsMargins(0, 0, 0, 0)
        cof_layout.setSpacing(40)
        cof_mean_layout, self._cof_mean_value = self._make_stat_item("Mean")
        cof_var_layout, self._cof_var_value = self._make_stat_item("Variance")
        cof_layout.addLayout(cof_mean_layout)
        cof_layout.addLayout(cof_var_layout)
        cof_layout.addStretch()
        self._stats_stack.addWidget(cof_stats)

        # Forces Stats (index 1)
        forces_stats = QWidget()
        forces_layout = QHBoxLayout(forces_stats)
        forces_layout.setContentsMargins(0, 0, 0, 0)
        forces_layout.setSpacing(40)
        fy_group, self._fy_mean_value, self._fy_var_value = self._make_force_group(
            "Shear Force (Fy)", COLORS['accent']
        )
        fz_group, self._fz_mean_value, self._fz_var_value = self._make_force_group(
            "Down Force (Fz)", COLORS['danger']
        )
        forces_layout.addLayout(fy_group)
        forces_layout.addLayout(fz_group)
        forces_layout.addStretch()
        self._stats_stack.addWidget(forces_stats)

        # Temperature Stats (index 2)
        temp_stats = QWidget()
        temp_layout = QHBoxLayout(temp_stats)
        temp_layout.setContentsMargins(0, 0, 0, 0)
        temp_layout.setSpacing(40)
        temp_mean_layout, self._temp_mean_value = self._make_stat_item("Mean")
        temp_initial_layout, self._temp_initial_value = self._make_stat_item("Initial")
        temp_high_layout, self._temp_high_value = self._make_stat_item("High")
        temp_layout.addLayout(temp_mean_layout)
        temp_layout.addLayout(temp_initial_layout)
        temp_layout.addLayout(temp_high_layout)
        temp_layout.addStretch()
        self._stats_stack.addWidget(temp_stats)

    def update_stats(self, graph_type, stats):
        """Update displayed statistics for the given graph type.

        Args:
            graph_type: 0 = COF, 1 = Forces, 2 = Temperature
            stats: dict from GraphWidget.get_stats()
        """
        self._stats_stack.setCurrentIndex(graph_type)

        if graph_type == 0:  # COF
            self._cof_mean_value.setText(f"{stats.get('cof_mean', 0):.6f}")
            self._cof_var_value.setText(f"{stats.get('cof_variance', 0):.8f}")
        elif graph_type == 1:  # Forces
            self._fy_mean_value.setText(f"{stats.get('fy_mean', 0):.4f} lbf")
            self._fy_var_value.setText(f"{stats.get('fy_variance', 0):.6f}")
            self._fz_mean_value.setText(f"{stats.get('fz_mean', 0):.4f} lbf")
            self._fz_var_value.setText(f"{stats.get('fz_variance', 0):.6f}")
        elif graph_type == 2:  # Temperature
            self._temp_mean_value.setText(f"{stats.get('temp_mean', 0):.2f} °C")
            self._temp_initial_value.setText(f"{stats.get('temp_initial', 0):.2f} °C")
            self._temp_high_value.setText(f"{stats.get('temp_high', 0):.2f} °C")

    @staticmethod
    def _make_stat_item(label_text, font_size_label=11, font_size_value=16):
        """Create a label + value pair for the stats panel.

        Returns:
            (container_layout, value_label) tuple
        """
        container = QVBoxLayout()
        container.setSpacing(2)
        label = QLabel(label_text)
        label.setStyleSheet(f"font-size: {font_size_label}px; color: {COLORS['text_secondary']}; font-weight: bold;")
        value = QLabel("--")
        value.setStyleSheet(f"font-size: {font_size_value}px; color: {COLORS['text_primary']}; font-weight: bold;")
        container.addWidget(label)
        container.addWidget(value)
        return container, value

    def _make_force_group(self, header_text, header_color):
        """Create a force stats group (header + mean/variance row).

        Returns:
            (group_layout, mean_value_label, var_value_label) tuple
        """
        group = QVBoxLayout()
        group.setSpacing(2)
        header = QLabel(header_text)
        header.setStyleSheet(f"font-size: 12px; color: {header_color}; font-weight: bold;")
        group.addWidget(header)

        stats_row = QHBoxLayout()
        stats_row.setSpacing(20)

        mean_layout, mean_value = self._make_stat_item("Mean", font_size_label=10, font_size_value=14)
        var_layout, var_value = self._make_stat_item("Variance", font_size_label=10, font_size_value=14)
        stats_row.addLayout(mean_layout)
        stats_row.addLayout(var_layout)

        group.addLayout(stats_row)
        return group, mean_value, var_value

