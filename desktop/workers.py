"""Background workers for file loading and importing."""

import os
import shutil
from PyQt6.QtCore import QThread, pyqtSignal
from core.raw_file import RawFile
from core.report import Report


class FileLoadWorker(QThread):
    """Worker thread for loading an existing project's files."""

    progress = pyqtSignal(int, int, str)  # (current, total, filename)
    finished = pyqtSignal(object)         # loaded Report
    error = pyqtSignal(str)

    def __init__(self, data, project_dir):
        super().__init__()
        self._data = data
        self._project_dir = project_dir

    def run(self):
        try:
            files_data = self._data.get('report', {}).get('files', [])
            total = len(files_data)
            report = Report()

            for i, file_data in enumerate(files_data):
                try:
                    raw_file = RawFile.from_dict(file_data, self._project_dir)
                    report.add_file(raw_file)
                except Exception as e:
                    print(f"Error loading file {file_data.get('file_name', 'unknown')}: {e}")
                self.progress.emit(i + 1, total, file_data.get('file_name', 'unknown'))

            self.finished.emit(report)
        except Exception as e:
            self.error.emit(str(e))


class FileImportWorker(QThread):
    """Worker thread for importing new .dat files into a project."""

    progress = pyqtSignal(int, int, str)  # (current, total, filename)
    finished = pyqtSignal(list)           # list of new RawFile objects
    error = pyqtSignal(str)

    def __init__(self, file_paths, data_dir):
        super().__init__()
        self._file_paths = file_paths
        self._data_dir = data_dir

    def run(self):
        try:
            total = len(self._file_paths)
            new_files = []

            for i, file_path in enumerate(self._file_paths):
                try:
                    dest_path = self._copy_with_dedup(file_path)
                    raw_file = RawFile(dest_path, wafer_num=1)
                    new_files.append(raw_file)
                except Exception as e:
                    print(f"Error importing {os.path.basename(file_path)}: {e}")
                self.progress.emit(i + 1, total, os.path.basename(file_path))

            self.finished.emit(new_files)
        except Exception as e:
            self.error.emit(str(e))

    def _copy_with_dedup(self, file_path):
        """Copy file to data_dir, handling duplicate filenames."""
        file_basename = os.path.basename(file_path)
        dest_path = os.path.join(self._data_dir, file_basename)

        if os.path.exists(dest_path):
            base, ext = os.path.splitext(file_basename)
            counter = 1
            while os.path.exists(dest_path):
                dest_path = os.path.join(self._data_dir, f"{base}_{counter}{ext}")
                counter += 1

        shutil.copy2(file_path, dest_path)
        return dest_path


class ReportGenerationWorker(QThread):
    """Worker thread for generating Excel and PowerPoint reports."""

    progress = pyqtSignal(int, int, str)  # (current, total, step_label)
    finished = pyqtSignal(list)           # list of generated file paths
    error = pyqtSignal(str)

    def __init__(self, report, project_dir, config):
        super().__init__()
        self._report = report
        self._project_dir = project_dir
        self._config = config

    def _count_steps(self):
        steps = 0
        if self._config['include_summary_excel']:
            steps += 1
        if self._config['include_detailed_excel']:
            steps += len(self._report.files) + 1  # per-file + finalize flush
        if self._config['include_pptx']:
            from desktop.pptx_builder import PptxBuilder
            steps += PptxBuilder.count_slides(self._report, self._config)
        return max(steps, 1)

    def run(self):
        from desktop.report_dialog import create_detailed_excel, create_summary_excel

        try:
            project_name = os.path.basename(self._project_dir)
            total = self._count_steps()
            current = 0
            paths = []

            # Phase 1: Excel files
            if self._config['include_summary_excel']:
                self.progress.emit(current, total, "Creating summary Excel...")
                summary_path = os.path.join(self._project_dir, f"{project_name}_report.xlsx")
                create_summary_excel(self._report, summary_path)
                paths.append(summary_path)
                current += 1

            if self._config['include_detailed_excel']:
                self.progress.emit(current, total, "Creating detailed Excel...")
                detailed_path = os.path.join(self._project_dir, f"{project_name}_detailed.xlsx")

                def detail_progress(file_num, file_total):
                    nonlocal current
                    current += 1
                    self.progress.emit(current, total, f"Writing file {file_num} of {file_total}...")

                def save_progress():
                    nonlocal current
                    current += 1
                    self.progress.emit(current, total, "Saving Excel file...")

                create_detailed_excel(self._report, detailed_path,
                                      progress_callback=detail_progress,
                                      save_callback=save_progress)
                paths.append(detailed_path)

            # Phase 2: PowerPoint
            if self._config['include_pptx']:
                from desktop.pptx_builder import PptxBuilder

                def pptx_progress(label):
                    nonlocal current
                    current += 1
                    self.progress.emit(current, total, label)

                pptx_path = PptxBuilder.build(
                    self._report, self._config, self._project_dir, pptx_progress
                )
                paths.append(pptx_path)

            self.finished.emit(paths)
        except Exception as e:
            self.error.emit(str(e))
