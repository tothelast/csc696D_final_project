#!/usr/bin/env python3
"""
Wafer Polishing Data Manager - Main Entry Point
A PyQt6 desktop application for managing and analyzing wafer polishing data.
"""

import sys
import subprocess
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from desktop.main_window import MainWindow
from desktop.theme import get_pyqt_stylesheet

# Prevent console window flashes from any subprocess calls when running as
# a frozen (PyInstaller) windowed app on Windows.
if sys.platform == 'win32' and (getattr(sys, 'frozen', False) or "__compiled__" in globals()):
    _original_popen_init = subprocess.Popen.__init__

    def _no_window_popen_init(self, *args, **kwargs):
        CREATE_NO_WINDOW = 0x08000000
        kwargs.setdefault('creationflags', 0)
        kwargs['creationflags'] |= CREATE_NO_WINDOW
        _original_popen_init(self, *args, **kwargs)

    subprocess.Popen.__init__ = _no_window_popen_init


def main():
    # Enable high DPI scaling
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("Wafer Polishing Data Manager")
    app.setOrganizationName("Araca")

    # Apply modern dark theme stylesheet from centralized theme
    app.setStyleSheet(get_pyqt_stylesheet())

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()

