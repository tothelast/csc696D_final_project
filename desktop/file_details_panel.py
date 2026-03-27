"""File Details Panel - Shows file attributes and data visualization."""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel,
    QDoubleSpinBox, QSpinBox, QTextEdit, QTabWidget, QSplitter,
    QTableView, QComboBox, QGroupBox, QPushButton, QScrollArea,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QStandardItemModel, QStandardItem

from desktop.graph_widget import GraphWidget
from desktop.theme import ToastNotification
from desktop.material_categories import (
    rebuild_global_sets, create_autocomplete_combo, populate_all_combos,
    combo_value, set_combo_value, block_signals,
)
from desktop.stats_panel import StatsPanel


class FileDetailsPanel(QWidget):
    """Panel showing file details, attributes, and data visualization."""

    def __init__(self, project_dir=None):
        super().__init__()
        self.raw_file = None
        self.report = None
        self.project_dir = project_dir
        self._previous_graph_type = 0  # Track previous graph type for saving settings
        self._first_show = True  # Flag for initial splitter sizing
        self.setup_ui()

    def set_report(self, report):
        """Store a reference to the Report so we can rebuild category sets from all files."""
        self.report = report

    def setup_ui(self):
        """Initialize the UI components."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 0, 0, 0)

        # Vertical splitter for top (40%) and bottom (60%)
        self.splitter = QSplitter(Qt.Orientation.Vertical)
        layout.addWidget(self.splitter)

        # Top section - File Attributes (40%)
        self.attributes_widget = self.create_attributes_section()
        self.splitter.addWidget(self.attributes_widget)

        # Bottom section - Data Visualization (60%)
        self.data_widget = self.create_data_section()
        self.splitter.addWidget(self.data_widget)

        self.attributes_widget.setMinimumHeight(80)
        self.data_widget.setMinimumHeight(1)

        # Stretch factors: top stays at preferred size, bottom absorbs extra space
        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setCollapsible(0, False)
        self.splitter.setCollapsible(1, False)

    def showEvent(self, event):
        """On first show, size the splitter so the attributes panel fits without scrolling."""
        super().showEvent(event)
        if self._first_show:
            self._first_show = False
            # Content height + apply button + QGroupBox chrome
            content_h = self._attr_inner_widget.sizeHint().height()
            apply_h = self.apply_btn.sizeHint().height() + 16  # 8px top + 8px bottom margin
            group_layout = self.attributes_widget.layout()
            margins = group_layout.contentsMargins()
            chrome = margins.top() + margins.bottom() + 40  # group box title + combo extra
            ideal = content_h + apply_h + chrome
            remaining = max(self.height() - ideal, 100)
            self.splitter.setSizes([ideal, remaining])

    def create_attributes_section(self):
        """Create the file attributes section."""
        widget = QGroupBox("File Attributes")
        layout = QVBoxLayout(widget)

        # Scroll area so fields scroll instead of overlapping when splitter is dragged
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        inner_widget = QWidget()
        inner_layout = QVBoxLayout(inner_widget)
        inner_layout.setContentsMargins(0, 0, 0, 0)
        self._attr_inner_widget = inner_widget
        scroll_area.setWidget(inner_widget)
        layout.addWidget(scroll_area)

        form_layout = QFormLayout()
        form_layout.setSpacing(12)

        # Wafer #
        self.wafer_num_input = QSpinBox()
        self.wafer_num_input.setRange(1, 10000)
        self.wafer_num_input.setMinimumWidth(150)
        self.wafer_num_input.setReadOnly(False)
        self.wafer_num_input.setButtonSymbols(QSpinBox.ButtonSymbols.UpDownArrows)
        form_layout.addRow("Wafer #:", self.wafer_num_input)

        # Removal
        self.removal_input = QDoubleSpinBox()
        self.removal_input.setRange(0, 100000)
        self.removal_input.setDecimals(2)
        self.removal_input.setMinimumWidth(150)
        self.removal_input.setReadOnly(False)
        self.removal_input.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.UpDownArrows)
        form_layout.addRow("Removal (Å):", self.removal_input)

        # WIWNU
        self.nu_input = QDoubleSpinBox()
        self.nu_input.setRange(0, 1000)
        self.nu_input.setDecimals(2)
        self.nu_input.setMinimumWidth(150)
        self.nu_input.setReadOnly(False)
        self.nu_input.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.UpDownArrows)
        form_layout.addRow("WIWNU (%):", self.nu_input)

        # Notes
        self.notes_input = QTextEdit()
        self.notes_input.setMinimumHeight(60)
        self.notes_input.setMaximumHeight(100)
        self.notes_input.setReadOnly(False)
        self.notes_input.setPlaceholderText("Enter notes here...")
        form_layout.addRow("Notes:", self.notes_input)

        # Right column: analysis interval + material type dropdowns
        right_form = QFormLayout()
        right_form.setSpacing(12)

        # Analysis Interval (first row — most impactful setting)
        interval_layout = QHBoxLayout()
        interval_layout.setSpacing(6)
        self.interval_start = QDoubleSpinBox()
        self.interval_start.setRange(-1000, 10000)
        self.interval_start.setValue(7)
        self.interval_start.setSuffix(" s")
        self.interval_start.setDecimals(1)
        self.interval_start.setMinimumWidth(70)
        self.interval_start.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.UpDownArrows)
        interval_layout.addWidget(self.interval_start)
        interval_layout.addWidget(QLabel("to"))
        self.interval_end = QDoubleSpinBox()
        self.interval_end.setRange(-1000, 10000)
        self.interval_end.setValue(57)
        self.interval_end.setSuffix(" s")
        self.interval_end.setDecimals(1)
        self.interval_end.setMinimumWidth(70)
        self.interval_end.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.UpDownArrows)
        interval_layout.addWidget(self.interval_end)
        right_form.addRow("Analysis Interval:", interval_layout)

        self.wafer_type_combo = create_autocomplete_combo()
        right_form.addRow("Wafer:", self.wafer_type_combo)

        self.pad_type_combo = create_autocomplete_combo()
        right_form.addRow("Pad:", self.pad_type_combo)

        self.slurry_type_combo = create_autocomplete_combo()
        right_form.addRow("Slurry:", self.slurry_type_combo)

        self.conditioner_disk_type_combo = create_autocomplete_combo()
        right_form.addRow("Conditioner:", self.conditioner_disk_type_combo)

        # Set Points
        self.pressure_psi_input = QDoubleSpinBox()
        self.pressure_psi_input.setRange(0, 100)
        self.pressure_psi_input.setDecimals(1)
        self.pressure_psi_input.setMinimumWidth(150)
        self.pressure_psi_input.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.UpDownArrows)
        right_form.addRow("Pressure (PSI):", self.pressure_psi_input)

        self.polish_time_input = QDoubleSpinBox()
        self.polish_time_input.setRange(0, 1000)
        self.polish_time_input.setDecimals(1)
        self.polish_time_input.setMinimumWidth(150)
        self.polish_time_input.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.UpDownArrows)
        right_form.addRow("Polish Time (min):", self.polish_time_input)

        # Two-column layout with equal stretch so both columns resize proportionally.
        # Each form is placed inside a QWidget so its size policy prevents it from
        # stretching vertically beyond its natural height.
        left_widget = QWidget()
        left_widget.setLayout(right_form)

        right_widget = QWidget()
        right_widget.setLayout(form_layout)

        columns_layout = QHBoxLayout()
        columns_layout.addWidget(left_widget, 1, Qt.AlignmentFlag.AlignTop)
        columns_layout.addSpacing(24)
        columns_layout.addWidget(right_widget, 1, Qt.AlignmentFlag.AlignTop)
        inner_layout.addLayout(columns_layout)

        # Apply button — fixed below the scroll area (not inside it)
        apply_layout = QHBoxLayout()
        apply_layout.addStretch()
        self.apply_btn = QPushButton("Apply")
        self.apply_btn.setFixedWidth(100)
        self.apply_btn.clicked.connect(self.on_apply_clicked)
        apply_layout.addWidget(self.apply_btn)
        apply_layout.setContentsMargins(0, 8, 12, 8)
        layout.addLayout(apply_layout)

        return widget

    def create_data_section(self):
        """Create the data visualization section."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)

        self.data_tabs = QTabWidget()
        layout.addWidget(self.data_tabs)

        # Tab 1: Raw Processed Data
        self.raw_data_table = QTableView()
        self.raw_data_model = QStandardItemModel()
        self.raw_data_table.setModel(self.raw_data_model)
        self.data_tabs.addTab(self.raw_data_table, "Raw Processed Data")

        # Tab 2: Total Per Frame
        self.total_per_frame_table = QTableView()
        self.total_per_frame_model = QStandardItemModel()
        self.total_per_frame_table.setModel(self.total_per_frame_model)
        self.data_tabs.addTab(self.total_per_frame_table, "Total Per Frame")

        # Tab 3: Graphs
        graphs_widget = QWidget()
        graphs_layout = QVBoxLayout(graphs_widget)
        graphs_layout.setSpacing(8)

        # Top controls row: Graph selector + Y-Axis
        controls_layout = QHBoxLayout()

        # Graph selector
        controls_layout.addWidget(QLabel("Graph Type:"))
        self.graph_selector = QComboBox()
        self.graph_selector.addItems(["COF Graph", "Forces Graph", "Temperature Graph"])
        self.graph_selector.currentIndexChanged.connect(self.on_graph_type_changed)
        controls_layout.addWidget(self.graph_selector)

        controls_layout.addSpacing(20)

        # Y-Axis range controls
        controls_layout.addWidget(QLabel("Y-Axis:"))
        self.y_min = QDoubleSpinBox()
        self.y_min.setRange(-100000, 100000)
        self.y_min.setValue(0)
        self.y_min.setDecimals(2)
        self.y_min.setMinimumWidth(70)
        self.y_min.setReadOnly(False)
        self.y_min.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.UpDownArrows)
        self.y_min.valueChanged.connect(self.on_y_axis_changed)
        controls_layout.addWidget(self.y_min)

        controls_layout.addWidget(QLabel("to"))

        self.y_max = QDoubleSpinBox()
        self.y_max.setRange(-100000, 100000)
        self.y_max.setValue(1)
        self.y_max.setDecimals(2)
        self.y_max.setMinimumWidth(70)
        self.y_max.setReadOnly(False)
        self.y_max.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.UpDownArrows)
        self.y_max.valueChanged.connect(self.on_y_axis_changed)
        controls_layout.addWidget(self.y_max)

        controls_layout.addStretch()

        # Save button (consistent with app styling)
        self.save_graph_btn = QPushButton("Save Graph")
        self.save_graph_btn.clicked.connect(self.on_save_graph)
        controls_layout.addWidget(self.save_graph_btn)

        graphs_layout.addLayout(controls_layout)

        # Statistics panel above the graph
        self.stats_panel = StatsPanel()
        graphs_layout.addWidget(self.stats_panel)

        # Graph widget
        self.graph_widget = GraphWidget(project_dir=self.project_dir)
        graphs_layout.addWidget(self.graph_widget, 1)  # stretch factor 1 to take remaining space

        self.data_tabs.addTab(graphs_widget, "Graphs")

        return widget

    def update_stats_panel(self):
        """Update the statistics panel based on the current graph type."""
        if not self.graph_widget:
            return
        graph_type = self.graph_selector.currentIndex()
        self.stats_panel.update_stats(graph_type, self.graph_widget.get_stats())

    def set_file(self, raw_file):
        """Set the current file to display."""
        self.raw_file = raw_file

        # Rebuild category sets from ALL files in the report and refresh combos
        rebuild_global_sets(self.report)
        populate_all_combos(self)

        with block_signals(
            self.interval_start, self.interval_end,
            self.wafer_num_input, self.removal_input,
            self.nu_input, self.notes_input,
            self.pressure_psi_input, self.polish_time_input
        ):
            self.interval_start.setValue(raw_file.interval[0])
            self.interval_end.setValue(raw_file.interval[1])
            self.wafer_num_input.setValue(raw_file.wafer_num)
            self.removal_input.setValue(raw_file.removal)
            self.nu_input.setValue(raw_file.nu)
            self.notes_input.setPlainText(raw_file.notes)
            set_combo_value(self.slurry_type_combo, raw_file.slurry_type)
            set_combo_value(self.wafer_type_combo, raw_file.wafer_type)
            set_combo_value(self.pad_type_combo, raw_file.pad_type)
            set_combo_value(self.conditioner_disk_type_combo, raw_file.conditioner_disk_type)
            self.pressure_psi_input.setValue(raw_file.pressure_psi)
            self.polish_time_input.setValue(raw_file.polish_time)

        # Update tables
        self.update_raw_data_table()
        self.update_total_per_frame_table()

        # Plot graph and restore per-graph Y-axis settings
        graph_type = self.graph_selector.currentIndex()
        self._previous_graph_type = graph_type  # Reset tracker for new file
        self._load_and_apply_graph_settings(graph_type, raw_file)

    def update_raw_data_table(self):
        """Update the raw data table view."""
        if not self.raw_file:
            return
        self.populate_table_model(self.raw_data_model, self.raw_file.raw_data)
        self.raw_data_table.resizeColumnsToContents()

    def update_total_per_frame_table(self):
        """Update the total per frame table view."""
        if not self.raw_file:
            return
        self.populate_table_model(self.total_per_frame_model, self.raw_file.total_per_frame)
        self.total_per_frame_table.resizeColumnsToContents()

    def populate_table_model(self, model, df):
        """Populate a QStandardItemModel from a pandas DataFrame."""
        model.clear()
        model.setHorizontalHeaderLabels(df.columns.tolist())

        # Limit rows for performance (show first 1000 rows)
        display_df = df.head(1000)
        for row_idx in range(len(display_df)):
            row_items = []
            for col_idx in range(len(display_df.columns)):
                value = display_df.iloc[row_idx, col_idx]
                if isinstance(value, float):
                    text = f"{value:.6f}"
                else:
                    text = str(value)
                item = QStandardItem(text)
                item.setEditable(False)
                row_items.append(item)
            model.appendRow(row_items)

    def update_graph(self):
        """Update the graph based on current selection."""
        if not self.raw_file:
            return
        graph_type = self.graph_selector.currentIndex()
        interval = [self.interval_start.value(), self.interval_end.value()]
        self.graph_widget.plot(self.raw_file, graph_type, interval)

        # Apply current Y-axis limits after redraw (keep user's Y-axis settings)
        y_min = self.y_min.value()
        y_max = self.y_max.value()
        if y_min < y_max and self.graph_widget.ax:
            self.graph_widget.ax.set_ylim(y_min, y_max)
            self.graph_widget.canvas.draw()

        # Update the statistics panel
        self.update_stats_panel()

    def _save_current_graph_settings(self):
        """Save current Y-axis settings for the current graph type."""
        if not self.raw_file:
            return
        graph_type = self.graph_selector.currentIndex()
        graph_key = str(graph_type)
        self.raw_file.graph_settings[graph_key] = {
            'y_min': self.y_min.value(),
            'y_max': self.y_max.value()
        }

    def _load_and_apply_graph_settings(self, graph_type, raw_file=None):
        """Load and apply saved Y-axis settings for a graph type, or use auto-detected range."""
        if raw_file is None:
            raw_file = self.raw_file
        if not raw_file:
            return

        graph_key = str(graph_type)
        settings = raw_file.graph_settings.get(graph_key)

        # Always use the canonical interval from raw_file
        interval = raw_file.interval

        with block_signals(self.y_min, self.y_max):
            # Plot the graph
            axis_limits = self.graph_widget.plot(raw_file, graph_type, interval)

            if settings and 'y_min' in settings and 'y_max' in settings:
                # Restore saved Y-axis settings
                self.y_min.setValue(settings['y_min'])
                self.y_max.setValue(settings['y_max'])
                # Apply the saved Y-axis limits to the graph
                if settings['y_min'] < settings['y_max'] and self.graph_widget.ax:
                    self.graph_widget.ax.set_ylim(settings['y_min'], settings['y_max'])
                    self.graph_widget.canvas.draw()
            elif axis_limits:
                # First time viewing this graph type - use defaults per graph type
                if graph_type == 0:  # COF: fixed 0-1 range
                    y_min_val, y_max_val = 0.0, 1.0
                else:  # Forces, Temperature: full range of plotted points
                    y_min_val, y_max_val = axis_limits[2], axis_limits[3]
                self.y_min.setValue(y_min_val)
                self.y_max.setValue(y_max_val)
                if y_min_val < y_max_val and self.graph_widget.ax:
                    self.graph_widget.ax.set_ylim(y_min_val, y_max_val)
                    self.graph_widget.canvas.draw()
                # Save the initial Y-axis values
                raw_file.graph_settings[graph_key] = {
                    'y_min': y_min_val,
                    'y_max': y_max_val
                }

        # Update the statistics panel
        self.update_stats_panel()

    def on_y_axis_changed(self):
        """Handle Y-axis scale change in real-time."""
        if not self.raw_file or not self.graph_widget or not self.graph_widget.ax:
            return

        y_min = self.y_min.value()
        y_max = self.y_max.value()

        # Save Y-axis values for the current graph type
        self._save_current_graph_settings()

        # Only update if min < max
        if y_min < y_max:
            self.graph_widget.ax.set_ylim(y_min, y_max)
            self.graph_widget.canvas.draw()

    def on_save_graph(self):
        """Handle save graph button click."""
        if self.graph_widget:
            self.graph_widget.save_graph()

    def set_project_dir(self, project_dir):
        """Set the project directory for saving graphs."""
        self.project_dir = project_dir
        if self.graph_widget:
            self.graph_widget.set_project_dir(project_dir)

    def on_apply_clicked(self):
        """Apply all current widget values to the current file."""
        if not self.raw_file:
            return

        # Read all values from widgets
        start = self.interval_start.value()
        end = self.interval_end.value()
        if start < end:
            self.raw_file.interval = [start, end]

        self.raw_file.wafer_num = self.wafer_num_input.value()
        self.raw_file.removal = self.removal_input.value()
        self.raw_file.nu = self.nu_input.value()
        self.raw_file.notes = self.notes_input.toPlainText()

        self.raw_file.wafer_type = combo_value(self.wafer_type_combo)
        self.raw_file.pad_type = combo_value(self.pad_type_combo)
        self.raw_file.slurry_type = combo_value(self.slurry_type_combo)
        self.raw_file.conditioner_disk_type = combo_value(self.conditioner_disk_type_combo)

        self.raw_file.pressure_psi = self.pressure_psi_input.value()
        self.raw_file.polish_time = self.polish_time_input.value()

        # Rebuild category sets from all files (reflects additions and removals)
        rebuild_global_sets(self.report)
        populate_all_combos(self)

        # Recalculate graph and statistics
        self.update_graph()

        # Toast notification
        ToastNotification("Changes applied successfully", self)

    def on_graph_type_changed(self, index):
        """Handle graph type selection change."""
        if not self.raw_file:
            return

        # Save Y-axis settings for the previous graph type before switching
        prev_key = str(self._previous_graph_type)
        self.raw_file.graph_settings[prev_key] = {
            'y_min': self.y_min.value(),
            'y_max': self.y_max.value()
        }

        # Load and apply settings for the new graph type
        self._load_and_apply_graph_settings(index)

        # Update the previous graph type tracker
        self._previous_graph_type = index

    def get_tab_index(self):
        """Get current tab index."""
        return self.data_tabs.currentIndex()

    def set_tab_index(self, index):
        """Set current tab index."""
        if 0 <= index < self.data_tabs.count():
            self.data_tabs.setCurrentIndex(index)

    def get_graph_index(self):
        """Get current graph type index."""
        return self.graph_selector.currentIndex()

    def set_graph_index(self, index):
        """Set current graph type index."""
        if 0 <= index < self.graph_selector.count():
            self.graph_selector.setCurrentIndex(index)

