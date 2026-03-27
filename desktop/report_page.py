"""Report Page — configuration UI for generating Excel and PowerPoint reports."""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QGroupBox, QCheckBox, QComboBox, QScrollArea, QGridLayout, QFrame,
    QDoubleSpinBox,
)
from PyQt6.QtCore import Qt, pyqtSignal

from desktop.theme import COLORS
from dashboard.constants import ANALYSIS_FEATURES, SELECTION_LABELS

# Mapping from UI label to RawFile property / DataFrame column
COMPARISON_TYPES = [
    ('Wafer vs Wafer', 'Wafer', 'wafer_type'),
    ('Pad vs Pad', 'Pad', 'pad_type'),
    ('Slurry vs Slurry', 'Slurry', 'slurry_type'),
    ('Conditioner vs Conditioner', 'Conditioner', 'conditioner_disk_type'),
]

ALL_CATEGORIES = ['Wafer', 'Pad', 'Slurry', 'Conditioner']

# Natural default for the x-axis dimension when comparing by a given category
SECONDARY_CATEGORY_DEFAULTS = {
    'Wafer': 'Pad',
    'Pad': 'Wafer',
    'Slurry': 'Wafer',
    'Conditioner': 'Wafer',
}

# Metrics checked by default
DEFAULT_METRICS = {'COF', 'Fz', 'Mean Temp', 'Removal', 'WIWNU', 'Removal Rate'}

# Features available for summary table columns
SUMMARY_TABLE_FEATURES = [
    'Pressure PSI', 'Mean Velocity', 'COF', 'Fy', 'Var Fy', 'Fz', 'Var Fz',
    'Directivity', 'Mean Temp', 'Init Temp', 'High Temp',
    'Mean Pressure', 'P.V', 'COF.P.V', 'Sommerfeld',
    'Removal', 'WIWNU', 'Removal Rate', 'Polish Time',
]

SUMMARY_TABLE_DEFAULTS = {
    'Pressure PSI', 'Mean Velocity', 'COF', 'Var Fy', 'Var Fz',
    'Directivity', 'Mean Temp', 'Removal Rate',
}

# Friendly names for correlation graphs (index matches PPTX_CORR_GRAPHS in pptx_builder)
PPTX_CORR_LABELS = [
    # Primary (default on)
    'COF vs V/P (Stribeck)',
    'Mean Pad Temp vs COF\u00b7P\u00b7V',
    'Var Shear Force vs P\u00b7V',
    'Var Normal Force vs P\u00b7V',
    'Removal Rate vs COF\u00b7P\u00b7V',
    'Directivity vs P\u00b7V',
    'WIWRRNU vs P\u00b7V',
    # Secondary (default off)
    'COF vs P\u00b7V',
    'Temperature vs P\u00b7V',
    'Arrhenius',
    'Preston Equation',
]

CORR_DEFAULT_ON = set(range(7))  # First 7 checked by default

# Indices with configurable Y-axis ranges and their defaults
CORR_RANGE_DEFAULTS = {
    0: (0.1, 1.0),     # COF (Stribeck)
}


class ReportPage(QWidget):
    """Full-page UI for configuring and triggering report generation."""

    back_clicked = pyqtSignal()
    generate_requested = pyqtSignal(dict)

    def __init__(self):
        super().__init__()
        self._report = None
        self._project_dir = None
        self._metric_checkboxes = []
        self._corr_checkboxes = []
        self._corr_range_widgets = []  # list of None or (min_spin, max_spin) per graph
        self._summary_table_checkboxes = []
        self._summary_table_widgets = []  # sub-widgets to enable/disable with summary tables toggle
        self._pptx_widgets = []  # widgets to enable/disable with master checkbox
        self.setup_ui()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_report(self, report, project_dir):
        """Called by MainWindow before navigating to this page."""
        self._report = report
        self._project_dir = project_dir
        self._update_group_preview()

    # ------------------------------------------------------------------
    # UI Setup
    # ------------------------------------------------------------------

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # --- Header (matches AnalysisPage) ---
        header = QWidget()
        header.setStyleSheet(
            f"background-color: {COLORS['bg_secondary']}; "
            f"border-bottom: 1px solid {COLORS['border']};"
        )
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(16, 8, 16, 8)

        back_btn = QPushButton("\u2190 Back to Project")
        back_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {COLORS['accent']};
                font-weight: 600;
                font-size: 14px;
                border: none;
                text-align: left;
            }}
            QPushButton:hover {{
                text-decoration: underline;
            }}
        """)
        back_btn.clicked.connect(self.back_clicked.emit)
        header_layout.addWidget(back_btn)

        title = QLabel("Generate Reports")
        title.setStyleSheet(
            f"font-size: 16px; font-weight: bold; color: {COLORS['text_primary']};"
        )
        header_layout.addWidget(title)
        header_layout.addStretch()
        header.setFixedHeight(50)
        layout.addWidget(header)

        # --- Scrollable body ---
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; }")

        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(32, 24, 32, 24)
        body_layout.setSpacing(20)

        # Center content with max width
        content = QWidget()
        content.setMaximumWidth(800)
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(20)

        # --- Excel Reports Section ---
        excel_group = QGroupBox("Excel Reports")
        excel_group.setStyleSheet("QGroupBox { padding-top: 8px; }")
        excel_layout = QVBoxLayout(excel_group)
        excel_layout.setSpacing(4)

        self.summary_checkbox = QCheckBox("Summary Report")
        self.summary_checkbox.setChecked(True)
        self.summary_checkbox.stateChanged.connect(self._update_generate_btn)
        excel_layout.addWidget(self.summary_checkbox)

        summary_desc = QLabel(
            "One-row-per-file table of key metrics \u2014 COF, forces, "
            "temperature, removal rate, and more."
        )
        summary_desc.setStyleSheet(
            f"font-size: 12px; color: {COLORS['text_secondary']}; padding-left: 24px;"
        )
        summary_desc.setWordWrap(True)
        excel_layout.addWidget(summary_desc)
        excel_layout.addSpacing(8)

        self.detailed_checkbox = QCheckBox("Detailed Data File")
        self.detailed_checkbox.setChecked(False)
        self.detailed_checkbox.stateChanged.connect(self._update_generate_btn)
        excel_layout.addWidget(self.detailed_checkbox)

        detailed_desc = QLabel(
            "Complete raw time-series measurements and per-frame "
            "calculations, one sheet per file."
        )
        detailed_desc.setStyleSheet(
            f"font-size: 12px; color: {COLORS['text_secondary']}; padding-left: 24px;"
        )
        detailed_desc.setWordWrap(True)
        excel_layout.addWidget(detailed_desc)

        detailed_warn = QLabel(
            "\u26a0 Large projects may take several minutes to generate "
            "depending on the number of files and system resources."
        )
        detailed_warn.setStyleSheet(
            f"font-size: 12px; color: {COLORS['warning']}; padding-left: 24px;"
        )
        detailed_warn.setWordWrap(True)
        excel_layout.addWidget(detailed_warn)

        content_layout.addWidget(excel_group)

        # --- PowerPoint Section ---
        pptx_group = QGroupBox("PowerPoint Report")
        pptx_group.setStyleSheet("QGroupBox { padding-top: 8px; }")
        pptx_layout = QVBoxLayout(pptx_group)
        pptx_layout.setSpacing(8)

        self.pptx_checkbox = QCheckBox("Generate PowerPoint Report")
        self.pptx_checkbox.setChecked(False)
        self.pptx_checkbox.stateChanged.connect(self._on_pptx_toggled)
        pptx_layout.addWidget(self.pptx_checkbox)

        pptx_desc = QLabel(
            "Presentation with comparison charts, correlation graphs, and "
            "summary tables grouped by category. All charts are natively "
            "editable in PowerPoint."
        )
        pptx_desc.setStyleSheet(
            f"font-size: 12px; color: {COLORS['text_secondary']}; padding-left: 24px;"
        )
        pptx_desc.setWordWrap(True)
        pptx_layout.addWidget(pptx_desc)
        self._pptx_widgets.append(pptx_desc)

        # Comparison type
        type_row = QHBoxLayout()
        type_label = QLabel("Comparison Type:")
        type_label.setFixedWidth(140)
        type_row.addWidget(type_label)
        self.type_combo = QComboBox()
        for label, _col, _prop in COMPARISON_TYPES:
            self.type_combo.addItem(label)
        self.type_combo.currentIndexChanged.connect(self._update_group_preview)
        self.type_combo.currentIndexChanged.connect(self._update_secondary_combo)
        self.type_combo.setMinimumWidth(220)
        type_row.addWidget(self.type_combo)
        type_row.addStretch()
        pptx_layout.addLayout(type_row)
        self._pptx_widgets.extend([type_label, self.type_combo])

        # Group preview (between comparison type and compare across)
        self.preview_label = QLabel("")
        self.preview_label.setWordWrap(True)
        self.preview_label.setStyleSheet(f"color: {COLORS['text_secondary']}; padding: 4px 0;")
        pptx_layout.addWidget(self.preview_label)
        self._pptx_widgets.append(self.preview_label)

        # Compare across (secondary category for bar chart x-axis)
        secondary_row = QHBoxLayout()
        secondary_label = QLabel("Compare Across:")
        secondary_label.setFixedWidth(140)
        secondary_row.addWidget(secondary_label)
        self.secondary_combo = QComboBox()
        self.secondary_combo.setMinimumWidth(220)
        secondary_row.addWidget(self.secondary_combo)
        secondary_row.addStretch()
        pptx_layout.addLayout(secondary_row)
        self._pptx_widgets.extend([secondary_label, self.secondary_combo])
        self._update_secondary_combo()

        # Metrics to compare
        metrics_header = QHBoxLayout()
        metrics_label = QLabel("Metrics to Compare:")
        metrics_label.setStyleSheet("font-weight: 600;")
        metrics_header.addWidget(metrics_label)
        metrics_header.addStretch()

        select_all_btn = QPushButton("Select All")
        select_all_btn.setObjectName("secondaryButton")
        select_all_btn.setFixedHeight(28)
        select_all_btn.clicked.connect(lambda: self._set_all_metrics(True))
        metrics_header.addWidget(select_all_btn)

        deselect_all_btn = QPushButton("Deselect All")
        deselect_all_btn.setObjectName("secondaryButton")
        deselect_all_btn.setFixedHeight(28)
        deselect_all_btn.clicked.connect(lambda: self._set_all_metrics(False))
        metrics_header.addWidget(deselect_all_btn)

        pptx_layout.addLayout(metrics_header)
        self._pptx_widgets.extend([metrics_label, select_all_btn, deselect_all_btn])

        # Metrics grid
        metrics_frame = QFrame()
        metrics_frame.setStyleSheet(
            f"QFrame {{ background-color: {COLORS['bg_secondary']}; "
            f"border: 1px solid {COLORS['border']}; border-radius: 6px; padding: 8px; }}"
        )
        metrics_grid = QGridLayout(metrics_frame)
        metrics_grid.setSpacing(8)

        for i, feature in enumerate(ANALYSIS_FEATURES):
            label = SELECTION_LABELS.get(feature, feature)
            cb = QCheckBox(label)
            cb.setProperty('feature_key', feature)
            cb.setChecked(feature in DEFAULT_METRICS)
            self._metric_checkboxes.append(cb)
            self._pptx_widgets.append(cb)
            row, col = divmod(i, 4)
            metrics_grid.addWidget(cb, row, col)

        pptx_layout.addWidget(metrics_frame)

        # Correlation graphs
        corr_label = QLabel("Correlation Graphs:")
        corr_label.setStyleSheet("font-weight: 600;")
        pptx_layout.addWidget(corr_label)
        self._pptx_widgets.append(corr_label)

        corr_frame = QFrame()
        corr_frame.setStyleSheet(
            f"QFrame {{ background-color: {COLORS['bg_secondary']}; "
            f"border: 1px solid {COLORS['border']}; border-radius: 6px; padding: 8px; }}"
        )
        corr_grid = QGridLayout(corr_frame)
        corr_grid.setSpacing(8)

        for i, label in enumerate(PPTX_CORR_LABELS):
            cb = QCheckBox(label)
            cb.setChecked(i in CORR_DEFAULT_ON)
            self._corr_checkboxes.append(cb)
            self._pptx_widgets.append(cb)

            corr_grid.addWidget(cb, i, 0)

            if i in CORR_RANGE_DEFAULTS:
                default_min, default_max = CORR_RANGE_DEFAULTS[i]
                min_spin = QDoubleSpinBox()
                min_spin.setPrefix("Y min: ")
                min_spin.setDecimals(2)
                min_spin.setRange(0, 100000)
                min_spin.setValue(default_min)
                spin_style = "QDoubleSpinBox { padding: 0px 2px; }"
                min_spin.setFixedWidth(110)
                min_spin.setFixedHeight(cb.sizeHint().height())
                min_spin.setStyleSheet(spin_style)
                min_spin.setSpecialValueText("")
                max_spin = QDoubleSpinBox()
                max_spin.setPrefix("Y max: ")
                max_spin.setDecimals(2)
                max_spin.setRange(0, 100000)
                max_spin.setValue(default_max)
                max_spin.setFixedWidth(110)
                max_spin.setFixedHeight(cb.sizeHint().height())
                max_spin.setStyleSheet(spin_style)
                max_spin.setSpecialValueText("")
                corr_grid.addWidget(min_spin, i, 1)
                corr_grid.addWidget(max_spin, i, 2)
                self._pptx_widgets.extend([min_spin, max_spin])
                self._corr_range_widgets.append((min_spin, max_spin))
                cb.stateChanged.connect(
                    lambda state, mn=min_spin, mx=max_spin:
                        (mn.setEnabled(state == Qt.CheckState.Checked.value),
                         mx.setEnabled(state == Qt.CheckState.Checked.value))
                )
            else:
                self._corr_range_widgets.append(None)

        pptx_layout.addWidget(corr_frame)

        # Summary tables
        self.summary_tables_checkbox = QCheckBox("Include summary tables")
        self.summary_tables_checkbox.setChecked(False)
        self.summary_tables_checkbox.stateChanged.connect(self._on_summary_tables_toggled)
        pptx_layout.addWidget(self.summary_tables_checkbox)
        self._pptx_widgets.append(self.summary_tables_checkbox)

        summary_desc = QLabel(
            "One table per combination of comparison type and compare-across "
            "category, showing selected metrics for each polishing run."
        )
        summary_desc.setStyleSheet(
            f"font-size: 12px; color: {COLORS['text_secondary']}; padding-left: 24px;"
        )
        summary_desc.setWordWrap(True)
        pptx_layout.addWidget(summary_desc)
        self._pptx_widgets.append(summary_desc)
        self._summary_table_widgets.append(summary_desc)

        # Summary table feature selection
        st_header = QHBoxLayout()
        st_label = QLabel("Table Columns:")
        st_label.setStyleSheet("font-weight: 600; padding-left: 24px;")
        st_header.addWidget(st_label)
        st_header.addStretch()

        st_select_all = QPushButton("Select All")
        st_select_all.setObjectName("secondaryButton")
        st_select_all.setFixedHeight(28)
        st_select_all.clicked.connect(lambda: self._set_all_summary_features(True))
        st_header.addWidget(st_select_all)

        st_deselect_all = QPushButton("Deselect All")
        st_deselect_all.setObjectName("secondaryButton")
        st_deselect_all.setFixedHeight(28)
        st_deselect_all.clicked.connect(lambda: self._set_all_summary_features(False))
        st_header.addWidget(st_deselect_all)

        pptx_layout.addLayout(st_header)
        self._pptx_widgets.extend([st_label, st_select_all, st_deselect_all])
        self._summary_table_widgets.extend([st_label, st_select_all, st_deselect_all])

        st_frame = QFrame()
        st_frame.setStyleSheet(
            f"QFrame {{ background-color: {COLORS['bg_secondary']}; "
            f"border: 1px solid {COLORS['border']}; border-radius: 6px; padding: 8px; }}"
        )
        st_grid = QGridLayout(st_frame)
        st_grid.setSpacing(8)

        for i, feature in enumerate(SUMMARY_TABLE_FEATURES):
            label = SELECTION_LABELS.get(feature, feature)
            cb = QCheckBox(label)
            cb.setProperty('feature_key', feature)
            cb.setChecked(feature in SUMMARY_TABLE_DEFAULTS)
            self._summary_table_checkboxes.append(cb)
            self._pptx_widgets.append(cb)
            self._summary_table_widgets.append(cb)
            row, col = divmod(i, 4)
            st_grid.addWidget(cb, row, col)

        pptx_layout.addWidget(st_frame)
        self._summary_table_widgets.append(st_frame)

        # Time traces
        self.time_traces_checkbox = QCheckBox(
            "Include time-trace appendix (one slide per file)"
        )
        self.time_traces_checkbox.setChecked(True)
        self.time_traces_checkbox.stateChanged.connect(self._on_time_traces_toggled)
        pptx_layout.addWidget(self.time_traces_checkbox)
        self._pptx_widgets.append(self.time_traces_checkbox)

        # COF Y-axis range for appendix time-trace charts
        tt_range_row = QHBoxLayout()
        tt_range_row.setContentsMargins(24, 0, 0, 0)
        tt_range_label = QLabel("COF Y-axis range:")
        tt_range_row.addWidget(tt_range_label)

        spin_style = "QDoubleSpinBox { padding: 0px 2px; }"
        self.tt_cof_min = QDoubleSpinBox()
        self.tt_cof_min.setPrefix("Min: ")
        self.tt_cof_min.setDecimals(2)
        self.tt_cof_min.setRange(0, 100000)
        self.tt_cof_min.setValue(0.10)
        self.tt_cof_min.setFixedWidth(110)
        self.tt_cof_min.setFixedHeight(self.time_traces_checkbox.sizeHint().height())
        self.tt_cof_min.setStyleSheet(spin_style)
        tt_range_row.addWidget(self.tt_cof_min)

        self.tt_cof_max = QDoubleSpinBox()
        self.tt_cof_max.setPrefix("Max: ")
        self.tt_cof_max.setDecimals(2)
        self.tt_cof_max.setRange(0, 100000)
        self.tt_cof_max.setValue(1.00)
        self.tt_cof_max.setFixedWidth(110)
        self.tt_cof_max.setFixedHeight(self.time_traces_checkbox.sizeHint().height())
        self.tt_cof_max.setStyleSheet(spin_style)
        tt_range_row.addWidget(self.tt_cof_max)
        tt_range_row.addStretch()

        pptx_layout.addLayout(tt_range_row)
        self._tt_range_widgets = [tt_range_label, self.tt_cof_min, self.tt_cof_max]
        self._pptx_widgets.extend(self._tt_range_widgets)

        content_layout.addWidget(pptx_group)

        # --- Generate button ---
        self.generate_btn = QPushButton("Generate Reports")
        self.generate_btn.setFixedHeight(44)
        self.generate_btn.setStyleSheet(f"""
            QPushButton {{
                font-size: 15px;
                font-weight: 700;
                padding: 10px 32px;
            }}
        """)
        self.generate_btn.clicked.connect(self._on_generate_clicked)
        content_layout.addWidget(self.generate_btn)

        content_layout.addStretch()

        # Center content widget
        center_layout = QHBoxLayout()
        center_layout.addStretch()
        center_layout.addWidget(content)
        center_layout.addStretch()
        body_layout.addLayout(center_layout)

        scroll.setWidget(body)
        layout.addWidget(scroll)

        # Initial state: pptx section disabled, summary table sub-widgets disabled
        self._set_pptx_section_enabled(False)
        for w in self._summary_table_widgets:
            w.setEnabled(False)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _on_pptx_toggled(self, state):
        enabled = state == Qt.CheckState.Checked.value
        self._set_pptx_section_enabled(enabled)
        self._update_generate_btn()

    def _set_pptx_section_enabled(self, enabled):
        for w in self._pptx_widgets:
            w.setEnabled(enabled)

    def _set_all_metrics(self, checked):
        for cb in self._metric_checkboxes:
            cb.setChecked(checked)

    def _on_summary_tables_toggled(self, state):
        enabled = state == Qt.CheckState.Checked.value
        for w in self._summary_table_widgets:
            w.setEnabled(enabled)

    def _on_time_traces_toggled(self, state):
        enabled = state == Qt.CheckState.Checked.value
        for w in self._tt_range_widgets:
            w.setEnabled(enabled)

    def _set_all_summary_features(self, checked):
        for cb in self._summary_table_checkboxes:
            cb.setChecked(checked)

    def _update_secondary_combo(self):
        """Repopulate the 'Compare Across' combo when comparison type changes."""
        idx = self.type_combo.currentIndex()
        if idx < 0:
            return
        _, primary_col, _ = COMPARISON_TYPES[idx]
        default = SECONDARY_CATEGORY_DEFAULTS.get(primary_col, 'Wafer')

        self.secondary_combo.blockSignals(True)
        self.secondary_combo.clear()
        for cat in ALL_CATEGORIES:
            if cat != primary_col:
                self.secondary_combo.addItem(cat)
        # Select the default
        default_idx = self.secondary_combo.findText(default)
        if default_idx >= 0:
            self.secondary_combo.setCurrentIndex(default_idx)
        self.secondary_combo.blockSignals(False)

    def _update_generate_btn(self):
        any_selected = (
            self.summary_checkbox.isChecked()
            or self.detailed_checkbox.isChecked()
            or self.pptx_checkbox.isChecked()
        )
        self.generate_btn.setEnabled(any_selected)

    def _update_group_preview(self):
        if not self._report or not self._report.files:
            self.preview_label.setText("No files loaded.")
            return

        idx = self.type_combo.currentIndex()
        if idx < 0:
            return
        _label, _col, prop = COMPARISON_TYPES[idx]

        # Count files per group
        groups = {}
        unassigned = 0
        for f in self._report.files:
            val = getattr(f, prop, None)
            if val and str(val).strip():
                groups.setdefault(str(val).strip(), 0)
                groups[str(val).strip()] += 1
            else:
                unassigned += 1

        if not groups:
            category_name = COMPARISON_TYPES[idx][0].split(' vs ')[0].lower()
            self.preview_label.setText(
                f"No {category_name} types assigned. "
                f"Please assign them on the Project page first."
            )
            self.preview_label.setStyleSheet(
                f"color: {COLORS['warning']}; padding: 4px 0;"
            )
            return

        parts = [f"{name} ({count} files)" for name, count in sorted(groups.items())]
        text = f"Found {len(groups)} groups: " + ", ".join(parts)
        if unassigned:
            text += f"  ({unassigned} unassigned files excluded)"
        self.preview_label.setText(text)
        self.preview_label.setStyleSheet(
            f"color: {COLORS['text_secondary']}; padding: 4px 0;"
        )

    def _build_config(self):
        """Collect all UI selections into a config dict."""
        idx = self.type_combo.currentIndex()
        _, col, _ = COMPARISON_TYPES[idx]

        selected_metrics = [
            cb.property('feature_key')
            for cb in self._metric_checkboxes
            if cb.isChecked()
        ]

        selected_correlations = []
        for i, cb in enumerate(self._corr_checkboxes):
            if cb.isChecked():
                entry = {'index': i, 'y_min': None, 'y_max': None}
                rw = self._corr_range_widgets[i]
                if rw:
                    min_spin, max_spin = rw
                    if min_spin.value() > 0:
                        entry['y_min'] = min_spin.value()
                    if max_spin.value() > 0:
                        entry['y_max'] = max_spin.value()
                selected_correlations.append(entry)

        summary_table_features = [
            cb.property('feature_key')
            for cb in self._summary_table_checkboxes
            if cb.isChecked()
        ]

        return {
            'include_summary_excel': self.summary_checkbox.isChecked(),
            'include_detailed_excel': self.detailed_checkbox.isChecked(),
            'include_pptx': self.pptx_checkbox.isChecked(),
            'comparison_category': col,
            'secondary_category': self.secondary_combo.currentText(),
            'selected_metrics': selected_metrics,
            'selected_correlations': selected_correlations,
            'include_summary_tables': self.summary_tables_checkbox.isChecked(),
            'summary_table_features': summary_table_features,
            'include_time_traces': self.time_traces_checkbox.isChecked(),
            'tt_cof_y_min': self.tt_cof_min.value(),
            'tt_cof_y_max': self.tt_cof_max.value() if self.tt_cof_max.value() > 0 else None,
        }

    def _on_generate_clicked(self):
        config = self._build_config()
        self.generate_requested.emit(config)
