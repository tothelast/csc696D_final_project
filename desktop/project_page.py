"""Project Page - Main workspace with file list and data visualization."""

import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QListWidget, QListWidgetItem, QSplitter, QFileDialog, QMessageBox,
    QStackedWidget, QFrame, QAbstractItemView, QLineEdit
)
from PyQt6.QtCore import pyqtSignal, Qt, QTimer
from PyQt6.QtGui import QPixmap

from desktop.file_details_panel import FileDetailsPanel
from desktop.bulk_edit_panel import BulkEditPanel
from desktop.landing_page import invert_dark_pixels
from desktop.theme import COLORS


class ProjectPage(QWidget):
    """Main project page with file list and details panel."""

    generate_report_clicked = pyqtSignal()
    advanced_analysis_clicked = pyqtSignal()
    import_files_requested = pyqtSignal(list)  # list of file path strings

    def __init__(self):
        super().__init__()
        self.report = None
        self.project_dir = None
        self.setup_ui()

    def setup_ui(self):
        """Initialize the UI components."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Header with title and generate report button
        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)

        title_label = QLabel("Project Files")
        title_label.setObjectName("headerLabel")
        header_layout.addWidget(title_label)

        header_layout.addStretch()

        self.generate_report_btn = QPushButton("Generate Report")
        self.generate_report_btn.clicked.connect(self.generate_report_clicked.emit)
        header_layout.addWidget(self.generate_report_btn)

        self.advanced_analysis_btn = QPushButton("Advanced Analysis")
        self.advanced_analysis_btn.setObjectName("secondaryButton")
        self.advanced_analysis_btn.clicked.connect(self.advanced_analysis_clicked.emit)
        header_layout.addWidget(self.advanced_analysis_btn)

        layout.addWidget(header)

        # Main splitter
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(self.splitter, 1)

        # Left panel (30%)
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 8, 0)

        # Buttons
        btn_layout = QHBoxLayout()
        self.add_files_btn = QPushButton("Add Raw File(s)")
        self.add_files_btn.clicked.connect(self.on_add_files)
        btn_layout.addWidget(self.add_files_btn)

        self.remove_file_btn = QPushButton("Remove File")
        self.remove_file_btn.setObjectName("dangerButton")
        self.remove_file_btn.clicked.connect(self.on_remove_file)
        btn_layout.addWidget(self.remove_file_btn)
        left_layout.addLayout(btn_layout)

        # Search bar
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Search files...")
        self.search_bar.setClearButtonEnabled(True)
        self.search_bar.textChanged.connect(self.filter_file_list)
        left_layout.addWidget(self.search_bar)

        # File list (ExtendedSelection enables Shift+click, Ctrl+click, and drag)
        self.file_list = QListWidget()
        self.file_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self._selection_timer = QTimer()
        self._selection_timer.setSingleShot(True)
        self._selection_timer.setInterval(50)
        self._selection_timer.timeout.connect(self.on_selection_changed)
        self.file_list.itemSelectionChanged.connect(self._selection_timer.start)
        left_layout.addWidget(self.file_list)

        self.splitter.addWidget(left_panel)

        # Right panel (70%) - Stacked widget for placeholder and details
        self.right_stack = QStackedWidget()

        # Placeholder widget for empty state
        self.placeholder_widget = self.create_placeholder_widget()
        self.right_stack.addWidget(self.placeholder_widget)

        # Details panel for when a single file is selected
        self.details_panel = FileDetailsPanel()
        self.right_stack.addWidget(self.details_panel)

        # Bulk edit panel for when multiple files are selected
        self.bulk_edit_panel = BulkEditPanel()
        self.right_stack.addWidget(self.bulk_edit_panel)

        # Start with placeholder visible
        self.right_stack.setCurrentWidget(self.placeholder_widget)

        self.splitter.addWidget(self.right_stack)

        # Set splitter sizes (30% / 70%)
        self.splitter.setSizes([300, 700])

    def create_placeholder_widget(self):
        """Create a placeholder widget shown when no file is selected."""
        widget = QFrame()
        widget.setObjectName("placeholderFrame")
        widget.setStyleSheet(f"""
            #placeholderFrame {{
                background-color: {COLORS['bg_primary']};
                border: none;
            }}
        """)

        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)

        layout.addStretch(1)

        # Logo + text grouped tightly in a centered column
        center_widget = QWidget()
        center_widget.setStyleSheet("background: transparent;")
        center_layout = QVBoxLayout(center_widget)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(20)
        center_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Company logo — reduced opacity feel via muted tint
        logo_label = QLabel()
        logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logo.png")
        if os.path.exists(logo_path):
            pixmap = QPixmap(logo_path)
            scaled_pixmap = pixmap.scaledToHeight(130, Qt.TransformationMode.SmoothTransformation)
            inverted_pixmap = invert_dark_pixels(scaled_pixmap)
            logo_label.setPixmap(inverted_pixmap)
        else:
            logo_label.setText("ARACA")
            logo_label.setStyleSheet(f"font-size: 28px; font-weight: bold; color: {COLORS['text_muted']};")
        center_layout.addWidget(logo_label)

        # Message directly beneath logo
        message_label = QLabel("Select or add files to begin")
        message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        message_label.setStyleSheet(f"""
            font-size: 16px;
            color: {COLORS['text_muted']};
        """)
        center_layout.addWidget(message_label)

        layout.addWidget(center_widget)

        layout.addStretch(1)

        return widget

    def set_project(self, report, project_dir, ui_state=None):
        """Set the current project."""
        self.report = report
        self.project_dir = project_dir

        # Pass report reference to panels so they can rebuild category sets
        self.details_panel.set_report(report)
        self.bulk_edit_panel.set_report(report)

        # Pass project directory to details panel for graph saving
        self.details_panel.set_project_dir(project_dir)

        self.refresh_file_list()

        # Always start with no file selected and placeholder visible
        self.file_list.clearSelection()
        self.file_list.setCurrentRow(-1)
        self.right_stack.setCurrentWidget(self.placeholder_widget)

    def get_ui_state(self):
        """Get current UI state for saving."""
        return {
            'selected_file_index': self.file_list.currentRow(),
            'tab_index': self.details_panel.get_tab_index(),
            'graph_index': self.details_panel.get_graph_index()
        }

    def filter_file_list(self, text):
        """Hide file list items that don't match the search text."""
        for i in range(self.file_list.count()):
            item = self.file_list.item(i)
            item.setHidden(bool(text) and text not in item.text())

    def refresh_file_list(self):
        """Refresh the file list widget."""
        self.search_bar.clear()
        self.file_list.blockSignals(True)
        self.file_list.clear()
        if self.report:
            # Sort files by basename for consistent display
            sorted_files = sorted(self.report.files, key=lambda f: f.file_basename.lower())
            for raw_file in sorted_files:
                item = QListWidgetItem(raw_file.file_basename)
                item.setToolTip(raw_file.file_name)
                # Store reference to the actual file object
                item.setData(Qt.ItemDataRole.UserRole, raw_file)
                self.file_list.addItem(item)
        self.file_list.blockSignals(False)

    def on_add_files(self):
        """Handle add files button click."""
        files, _ = QFileDialog.getOpenFileNames(
            self, "Select Raw Data Files", "",
            "DAT Files (*.dat);;All Files (*)"
        )
        if files:
            self.import_files_requested.emit(files)

    def on_remove_file(self):
        """Handle remove file button click — removes all selected files."""
        selected_items = self.file_list.selectedItems()
        if not selected_items:
            return

        count = len(selected_items)
        message = (
            "Are you sure you want to remove this file?"
            if count == 1
            else f"Are you sure you want to remove {count} files?"
        )
        reply = QMessageBox.question(
            self, "Remove File",
            message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            for item in selected_items:
                raw_file = item.data(Qt.ItemDataRole.UserRole)
                if raw_file:
                    self.report.remove_file(raw_file)
            self.refresh_file_list()
            if self.file_list.count() == 0:
                self.right_stack.setCurrentWidget(self.placeholder_widget)

    def on_selection_changed(self):
        """Handle file selection change — single file, multi-file, or none."""
        if not self.report:
            self.right_stack.setCurrentWidget(self.placeholder_widget)
            return

        selected_items = self.file_list.selectedItems()

        if len(selected_items) == 0:
            self.right_stack.setCurrentWidget(self.placeholder_widget)
        elif len(selected_items) == 1:
            raw_file = selected_items[0].data(Qt.ItemDataRole.UserRole)
            if raw_file:
                self.details_panel.set_file(raw_file)
                self.right_stack.setCurrentWidget(self.details_panel)
            else:
                self.right_stack.setCurrentWidget(self.placeholder_widget)
        else:
            # Multiple files selected — show bulk edit panel
            raw_files = []
            for item in selected_items:
                raw_file = item.data(Qt.ItemDataRole.UserRole)
                if raw_file:
                    raw_files.append(raw_file)
            if raw_files:
                self.bulk_edit_panel.set_files(raw_files)
                self.right_stack.setCurrentWidget(self.bulk_edit_panel)
            else:
                self.right_stack.setCurrentWidget(self.placeholder_widget)

