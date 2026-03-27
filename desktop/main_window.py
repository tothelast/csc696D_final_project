"""Main Window - handles navigation between landing page and project page."""

import json
import os
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QStackedWidget,
    QFileDialog, QMessageBox
)

from desktop.landing_page import LandingPage
from desktop.project_page import ProjectPage
from desktop.analysis_page import AnalysisPage
from desktop.splash_widget import CircularSplashWidget
from desktop.report_page import ReportPage
from desktop.workers import FileLoadWorker, FileImportWorker, ReportGenerationWorker
from desktop.theme import ToastNotification
from dashboard.dash_bridge import DataManager
from core.report import Report


class MainWindow(QMainWindow):
    """Main application window with page navigation."""

    PROJECT_FILE_NAME = "project.json"

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Araca Insights® Wafer Polishing Data Manager")
        self.setMinimumSize(1200, 800)

        # Start maximized (full screen)
        self.showMaximized()

        # Project state
        self.project_dir = None
        self.report = Report()
        self.ui_state = {}

        # Worker references (prevent GC)
        self._load_worker = None
        self._import_worker = None
        self._report_worker = None

        # Setup UI
        self.setup_ui()

    def setup_ui(self):
        """Initialize the UI components."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(0, 0, 0, 0)

        # Stacked widget for page navigation
        self.stack = QStackedWidget()
        layout.addWidget(self.stack)

        # Splash widget (added first, but navigated to by reference)
        self.splash_widget = CircularSplashWidget()
        self.stack.addWidget(self.splash_widget)

        # Create pages
        self.landing_page = LandingPage()
        self.landing_page.create_project_clicked.connect(self.on_create_project)
        self.landing_page.load_project_clicked.connect(self.on_load_project)
        self.stack.addWidget(self.landing_page)

        self.project_page = ProjectPage()
        self.project_page.generate_report_clicked.connect(self.on_generate_report)
        self.project_page.advanced_analysis_clicked.connect(self.on_advanced_analysis)
        self.project_page.import_files_requested.connect(self._on_import_requested)
        self.stack.addWidget(self.project_page)

        self.analysis_page = AnalysisPage()
        self.analysis_page.back_clicked.connect(self.on_analysis_back)
        self.stack.addWidget(self.analysis_page)

        self.report_page = ReportPage()
        self.report_page.back_clicked.connect(self.on_report_back)
        self.report_page.generate_requested.connect(self.on_start_generation)
        self.stack.addWidget(self.report_page)

        # Start on landing page
        self.stack.setCurrentWidget(self.landing_page)

    def on_create_project(self):
        """Handle create new project action."""
        directory = QFileDialog.getExistingDirectory(
            self, "Select Project Directory", "",
            QFileDialog.Option.ShowDirsOnly
        )
        if directory:
            self.project_dir = directory
            self.report = Report()
            self.ui_state = {}
            self.project_page.set_project(self.report, self.project_dir, self.ui_state)
            self.stack.setCurrentWidget(self.project_page)
            self.setWindowTitle(f"Araca Insights® Wafer Polishing Data Manager - {os.path.basename(directory)}")

    def on_load_project(self):
        """Handle load existing project action."""
        directory = QFileDialog.getExistingDirectory(
            self, "Select Project Folder", "",
            QFileDialog.Option.ShowDirsOnly
        )
        if directory:
            # Check if project.json exists in the selected folder
            project_file = os.path.join(directory, self.PROJECT_FILE_NAME)
            if not os.path.exists(project_file):
                QMessageBox.warning(self, "Invalid Project Folder",
                    "Invalid project folder.\n\nThe selected folder does not contain a valid project file.")
                return

            try:
                self.load_project(project_file)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to load project:\n{str(e)}")

    def load_project(self, file_path):
        """Load project from file using a background worker."""
        with open(file_path, 'r') as f:
            data = json.load(f)

        self.project_dir = os.path.dirname(file_path)
        self.ui_state = data.get('ui_state', {})
        self.setWindowTitle(f"Araca Insights® Wafer Polishing Data Manager - {os.path.basename(self.project_dir)}")

        # Show splash and start worker
        self.splash_widget.reset()
        self.stack.setCurrentWidget(self.splash_widget)
        self.splash_widget.set_progress(0, "Loading project...")

        self._load_worker = FileLoadWorker(data, self.project_dir)
        self._load_worker.progress.connect(self._on_load_progress)
        self._load_worker.finished.connect(self._on_load_finished)
        self._load_worker.error.connect(self._on_load_error)
        self._load_worker.start()

    def _on_load_progress(self, current, total, _filename):
        pct = (current / (total + 1)) * 100
        self.splash_widget.set_progress(pct, f"Loading file {current} of {total}")

    def _on_load_finished(self, report):
        self.report = report
        self.project_page.set_project(self.report, self.project_dir, self.ui_state)
        # Connect before setting 100% to avoid race with splash fade-out
        self.splash_widget.finished.connect(self._switch_to_project_page)
        self.splash_widget.set_progress(100, "Ready!")

    def _on_load_error(self, error_msg):
        self.stack.setCurrentWidget(self.landing_page)
        QMessageBox.critical(self, "Error", f"Failed to load project:\n{error_msg}")

    def _switch_to_project_page(self):
        # Disconnect so it doesn't fire again on next use
        try:
            self.splash_widget.finished.disconnect(self._switch_to_project_page)
        except TypeError:
            pass
        self.stack.setCurrentWidget(self.project_page)

    # -- File import orchestration --
    def _on_import_requested(self, file_paths):
        """Handle import request from ProjectPage."""
        data_dir = os.path.join(self.project_dir, 'data')
        os.makedirs(data_dir, exist_ok=True)

        self.splash_widget.reset()
        self.stack.setCurrentWidget(self.splash_widget)
        self.splash_widget.set_progress(0, "Importing files...")

        self._import_worker = FileImportWorker(file_paths, data_dir)
        self._import_worker.progress.connect(self._on_import_progress)
        self._import_worker.finished.connect(self._on_import_finished)
        self._import_worker.error.connect(self._on_import_error)
        self._import_worker.start()

    def _on_import_progress(self, current, total, _filename):
        pct = (current / (total + 1)) * 100
        self.splash_widget.set_progress(pct, f"Importing file {current} of {total}")

    def _on_import_finished(self, new_files):
        for raw_file in new_files:
            self.report.add_file(raw_file)

        # Reassign wafer numbers based on alphabetical order
        sorted_files = sorted(self.report.files, key=lambda f: f.file_basename.lower())
        for idx, raw_file in enumerate(sorted_files, start=1):
            raw_file.wafer_num = idx

        self.project_page.refresh_file_list()
        self.splash_widget.finished.connect(self._switch_to_project_page)
        self.splash_widget.set_progress(100, "Ready!")

    def _on_import_error(self, error_msg):
        self.stack.setCurrentWidget(self.project_page)
        QMessageBox.warning(self, "Import Error", f"Failed to import files:\n{error_msg}")

    def save_project(self):
        """Save project to file."""
        if not self.project_dir:
            return

        # Get current UI state from project page
        self.ui_state = self.project_page.get_ui_state()

        data = {
            # Pass project_dir to save relative paths
            'report': self.report.to_dict(self.project_dir),
            'ui_state': self.ui_state
        }

        file_path = os.path.join(self.project_dir, self.PROJECT_FILE_NAME)
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=2)

    def on_generate_report(self):
        """Navigate to the report configuration page."""
        if not self.report or not self.report.files:
            QMessageBox.information(self, "No Data", "Please add files before generating a report.")
            return
        self.report_page.set_report(self.report, self.project_dir)
        self.stack.setCurrentWidget(self.report_page)

    def on_report_back(self):
        """Return to project page from report page."""
        self.stack.setCurrentWidget(self.project_page)

    def on_start_generation(self, config):
        """Start report generation with splash widget progress."""
        self.splash_widget.reset()
        self.stack.setCurrentWidget(self.splash_widget)
        self.splash_widget.set_progress(0, "Generating reports...")

        self._report_worker = ReportGenerationWorker(self.report, self.project_dir, config)
        self._report_worker.progress.connect(self._on_report_progress)
        self._report_worker.finished.connect(self._on_report_finished)
        self._report_worker.error.connect(self._on_report_error)
        self._report_worker.start()

    def _on_report_progress(self, current, total, label):
        pct = (current / (total + 1)) * 100
        self.splash_widget.set_progress(pct, label)

    def _on_report_finished(self, _paths):
        self.splash_widget.finished.connect(self._on_report_splash_done)
        self.splash_widget.set_progress(100, "Done!")

    def _on_report_splash_done(self):
        try:
            self.splash_widget.finished.disconnect(self._on_report_splash_done)
        except TypeError:
            pass
        self.stack.setCurrentWidget(self.project_page)
        ToastNotification("Reports saved to project folder", self.project_page)

    def _on_report_error(self, error_msg):
        self.stack.setCurrentWidget(self.project_page)
        QMessageBox.critical(self, "Error", f"Failed to generate report:\n{error_msg}")

    def on_advanced_analysis(self):
        """Switch to advanced analysis page."""
        if not self.report or not self.report.files:
            QMessageBox.information(self, "No Data", "Please load raw files before starting analysis.")
            return

        # Update data manager
        data_manager = DataManager()
        data_manager.update_report(self.report)

        # Pass project directory for PNG saving
        self.analysis_page.set_project_dir(self.project_dir)

        # Start server if needed and switch page
        already_running = self.analysis_page.start_server()
        if already_running:
            self.analysis_page.reload_view()
        self.stack.setCurrentWidget(self.analysis_page)

    def on_analysis_back(self):
        """Return to project page from analysis."""
        self.stack.setCurrentWidget(self.project_page)

    def closeEvent(self, event):
        """Save project on close."""
        if self.project_dir and self.report.files:
            reply = QMessageBox.question(
                self, "Save Project",
                "Do you want to save the project before closing?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No |
                QMessageBox.StandardButton.Cancel
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.save_project()
                event.accept()
            elif reply == QMessageBox.StandardButton.No:
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()
