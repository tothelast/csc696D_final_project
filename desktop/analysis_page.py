import os
import threading
import socket
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QHBoxLayout, QLabel
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEngineProfile
from PyQt6.QtCore import QUrl, pyqtSignal, QTimer

# Import centralized theme
from desktop.theme import COLORS, ToastNotification

# Import Dash app and server
try:
    from dashboard.app import app
except ImportError:
    # Fallback if running as script
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from dashboard.app import app

class AnalysisPage(QWidget):
    """
    Page for displaying the embedded Plotly Dash application.
    """
    back_clicked = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.server_thread = None
        self.port = 8050
        self.server_started = False
        self.project_dir = None
        self.setup_ui()
        self._connect_download_handler()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Header with Back button
        header = QWidget()
        header.setStyleSheet(f"background-color: {COLORS['bg_secondary']}; border-bottom: 1px solid {COLORS['border']};")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(16, 8, 16, 8)

        self.back_btn = QPushButton("← Back to Project")
        self.back_btn.setStyleSheet(f"""
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
        self.back_btn.clicked.connect(self.back_clicked.emit)
        header_layout.addWidget(self.back_btn)

        title = QLabel("Advanced Analysis")
        title.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {COLORS['text_primary']};")
        header_layout.addWidget(title)

        header.setFixedHeight(50)

        header_layout.addStretch()
        layout.addWidget(header, 0)

        # Web Engine View
        self.web_view = QWebEngineView()
        self.web_view.setZoomFactor(1.25)
        layout.addWidget(self.web_view, 1)

    def _connect_download_handler(self):
        """Connect QWebEngine's download signal to save PNGs to project_dir."""
        profile = QWebEngineProfile.defaultProfile()
        profile.downloadRequested.connect(self._handle_download)

    def set_project_dir(self, project_dir):
        """Set the project directory for saving downloaded plots."""
        self.project_dir = project_dir

    def _handle_download(self, download):
        """Intercept browser downloads and redirect PNGs to project_dir."""
        if not self.project_dir:
            download.cancel()
            return

        download.setDownloadDirectory(self.project_dir)
        download.accept()

        filename = download.downloadFileName()
        download.isFinishedChanged.connect(
            lambda: self._on_download_finished(download, filename)
        )

    def _on_download_finished(self, download, filename):
        """Show toast notification when download completes."""
        from PyQt6.QtWebEngineCore import QWebEngineDownloadRequest
        if download.state() == QWebEngineDownloadRequest.DownloadState.DownloadCompleted:
            ToastNotification(f"Saved: {filename}", self)

    def find_free_port(self):
        """Find a free port to run the Dash server."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('', 0))
            return s.getsockname()[1]

    def start_server(self) -> bool:
        """Start the Dash server in a background thread.

        Returns True if the server was already running (caller should
        reload the view manually). Returns False when a fresh server is
        being started (the poller will load the page when ready).
        """
        if self.server_started:
            return True

        # Try default port, if taken find another
        try:
            test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            test_socket.bind(('127.0.0.1', 8050))
            test_socket.close()
            self.port = 8050
        except OSError:
            self.port = self.find_free_port()

        def run():
            # Suppress Dash startup messages
            import logging
            log = logging.getLogger('werkzeug')
            log.setLevel(logging.ERROR)
            app.run(port=self.port, debug=False, use_reloader=False)

        self.server_thread = threading.Thread(target=run, daemon=True)
        self.server_thread.start()
        self.server_started = True

        # Poll until the server is actually accepting connections before loading
        self._poll_count = 0
        self._poll_server()
        return False

    def _poll_server(self):
        """Check if the Dash server is ready before loading the page."""
        try:
            test = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            test.settimeout(0.1)
            test.connect(('127.0.0.1', self.port))
            test.close()
            self.web_view.setUrl(QUrl(f"http://127.0.0.1:{self.port}"))
        except (ConnectionRefusedError, OSError):
            self._poll_count += 1
            if self._poll_count < 50:  # give up after ~5 seconds
                QTimer.singleShot(100, self._poll_server)

    def reload_view(self):
        """Reload the web view."""
        if self.server_started:
             self.web_view.setUrl(QUrl(f"http://127.0.0.1:{self.port}"))
