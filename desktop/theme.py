"""
Centralized Theme Configuration for Wafer Polishing Data Manager.

This module provides a single source of truth for all colors and styling
used across both PyQt6 and Dash components of the application.
"""

from PyQt6.QtWidgets import QLabel, QGraphicsOpacityEffect
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QFont

# =============================================================================
# Color Palette - Dark Theme with Light Grey Text
# =============================================================================
# Reference: Dark theme with readable light text

COLORS = {
    # Backgrounds
    'bg_primary': '#1f1f1f',      # Main background
    'bg_secondary': '#2a2a2a',    # Card/panel background
    'bg_tertiary': '#353535',     # Toolbar/control background
    'bg_hover': '#383838',        # Hover state background
    'bg_disabled': '#404040',     # Disabled state background

    # Borders
    'border': '#3d3d3d',          # Primary border
    'border_light': '#4a4a4a',    # Secondary/lighter border
    'border_focus': '#3b82f6',    # Focus state border (accent color)

    # Text - Light grey palette for better readability on dark background
    'text_primary': '#e0e0e0',    # Primary text (bright for readability)
    'text_secondary': '#a0a0a0',  # Secondary/muted text
    'text_muted': '#707070',      # Disabled/placeholder text
    'text_on_accent': '#ffffff',  # White text for buttons with colored backgrounds

    # Accent colors (Tailwind blue palette)
    'accent': '#3b82f6',          # Primary blue (Tailwind blue-500)
    'accent_hover': '#2563eb',    # Hover blue (Tailwind blue-600)
    'accent_pressed': '#1d4ed8',  # Pressed blue (Tailwind blue-700)

    # Selection
    'selection_bg': '#3d5a80',    # Selection background
    'selection_text': '#7cb3f0',  # Selection text

    # Status colors
    'success': '#22c55e',         # Green for success/positive
    'warning': '#f59e0b',         # Orange for warnings
    'danger': '#ef4444',          # Red for danger/errors
    'danger_hover': '#dc2626',    # Hover state for danger

    # Scrollbar
    'scrollbar_bg': '#2a2a2a',    # Scrollbar track background
    'scrollbar_handle': '#4a4a4a', # Scrollbar handle
    'scrollbar_hover': '#5a5a5a', # Scrollbar handle hover
}


def get_pyqt_stylesheet():
    """
    Return the complete PyQt6 stylesheet for dark theme.

    Uses colors from the centralized COLORS dictionary to ensure consistency
    across the entire application.
    """
    return f"""
        QMainWindow, QWidget {{
            background-color: {COLORS['bg_primary']};
            color: {COLORS['text_primary']};
            font-size: 13px;
        }}

        QLabel {{
            color: {COLORS['text_primary']};
        }}

        QPushButton {{
            background-color: {COLORS['accent']};
            color: {COLORS['text_on_accent']};
            border: none;
            padding: 8px 16px;
            border-radius: 6px;
            font-weight: 600;
        }}

        QPushButton:hover {{
            background-color: {COLORS['accent_hover']};
        }}

        QPushButton:pressed {{
            background-color: {COLORS['accent_pressed']};
        }}

        QPushButton:disabled {{
            background-color: {COLORS['bg_disabled']};
            color: {COLORS['text_secondary']};
        }}

        QPushButton#secondaryButton {{
            background-color: {COLORS['bg_disabled']};
            color: {COLORS['text_primary']};
        }}

        QPushButton#secondaryButton:hover {{
            background-color: {COLORS['border_light']};
        }}

        QPushButton#dangerButton {{
            background-color: {COLORS['danger']};
            color: {COLORS['text_on_accent']};
        }}

        QPushButton#dangerButton:hover {{
            background-color: {COLORS['danger_hover']};
        }}

        QListWidget {{
            background-color: {COLORS['bg_secondary']};
            color: {COLORS['text_primary']};
            border: 1px solid {COLORS['border']};
            border-radius: 6px;
            padding: 4px;
        }}

        QListWidget::item {{
            color: {COLORS['text_primary']};
            padding: 8px;
            border-radius: 4px;
        }}

        QListWidget::item:selected {{
            background-color: {COLORS['selection_bg']};
            color: {COLORS['selection_text']};
        }}

        QListWidget::item:hover:!selected {{
            background-color: {COLORS['bg_hover']};
            color: {COLORS['text_primary']};
        }}

        QLineEdit, QSpinBox, QDoubleSpinBox {{
            background-color: {COLORS['bg_secondary']};
            color: {COLORS['text_primary']};
            border: 1px solid {COLORS['border']};
            border-radius: 6px;
            padding: 6px;
            min-height: 20px;
        }}

        QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
            border: 2px solid {COLORS['accent']};
        }}

        QSpinBox::up-button, QDoubleSpinBox::up-button,
        QSpinBox::down-button, QDoubleSpinBox::down-button {{
            width: 20px;
            border: none;
            background-color: {COLORS['bg_tertiary']};
        }}

        QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
        QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {{
            background-color: {COLORS['border_light']};
        }}

        QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {{
            border-left: 5px solid transparent;
            border-right: 5px solid transparent;
            border-bottom: 5px solid {COLORS['text_primary']};
            width: 0;
            height: 0;
        }}

        QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {{
            border-left: 5px solid transparent;
            border-right: 5px solid transparent;
            border-top: 5px solid {COLORS['text_primary']};
            width: 0;
            height: 0;
        }}

        QTextEdit {{
            background-color: {COLORS['bg_secondary']};
            color: {COLORS['text_primary']};
            border: 1px solid {COLORS['border']};
            border-radius: 6px;
            padding: 6px;
        }}

        QTextEdit:focus {{
            border: 2px solid {COLORS['accent']};
        }}

        QTabWidget::pane {{
            border: 1px solid {COLORS['border']};
            background-color: {COLORS['bg_secondary']};
            border-radius: 6px;
        }}

        QTabBar::tab {{
            background-color: {COLORS['bg_tertiary']};
            color: {COLORS['text_secondary']};
            padding: 8px 16px;
            margin-right: 2px;
            border-top-left-radius: 6px;
            border-top-right-radius: 6px;
        }}

        QTabBar::tab:selected {{
            background-color: {COLORS['bg_secondary']};
            color: {COLORS['accent']};
            border-bottom: 2px solid {COLORS['accent']};
        }}

        QTableView {{
            background-color: {COLORS['bg_secondary']};
            color: {COLORS['text_primary']};
            border: 1px solid {COLORS['border']};
            border-radius: 6px;
            gridline-color: {COLORS['border']};
            selection-background-color: {COLORS['selection_bg']};
            selection-color: {COLORS['selection_text']};
        }}

        QTableView::item {{
            color: {COLORS['text_primary']};
            padding: 4px;
        }}

        QHeaderView::section {{
            background-color: {COLORS['bg_tertiary']};
            color: {COLORS['text_primary']};
            padding: 8px;
            border: none;
            border-bottom: 1px solid {COLORS['border']};
            border-right: 1px solid {COLORS['border']};
            font-weight: 600;
        }}

        QSplitter::handle {{
            background-color: {COLORS['border']};
        }}

        QLabel#headerLabel {{
            font-size: 18px;
            font-weight: 600;
            color: {COLORS['text_primary']};
        }}

        QGroupBox {{
            font-weight: 600;
            color: {COLORS['text_primary']};
            border: 1px solid {COLORS['border']};
            border-radius: 6px;
            margin-top: 16px;
            padding-top: 16px;
        }}

        QGroupBox::title {{
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 5px;
            color: {COLORS['text_primary']};
        }}

        QComboBox {{
            background-color: {COLORS['bg_secondary']};
            color: {COLORS['text_primary']};
            border: 1px solid {COLORS['border']};
            border-radius: 6px;
            padding: 6px;
            min-height: 20px;
        }}

        QComboBox:focus {{
            border: 2px solid {COLORS['accent']};
        }}

        QComboBox::drop-down {{
            border: none;
            width: 24px;
        }}

        QComboBox QAbstractItemView {{
            background-color: {COLORS['bg_secondary']};
            color: {COLORS['text_primary']};
            selection-background-color: {COLORS['selection_bg']};
            selection-color: {COLORS['selection_text']};
        }}

        QScrollBar:vertical {{
            background-color: {COLORS['scrollbar_bg']};
            width: 12px;
            border-radius: 6px;
        }}

        QScrollBar::handle:vertical {{
            background-color: {COLORS['scrollbar_handle']};
            border-radius: 6px;
            min-height: 20px;
        }}

        QScrollBar::handle:vertical:hover {{
            background-color: {COLORS['scrollbar_hover']};
        }}

        QScrollBar:horizontal {{
            background-color: {COLORS['scrollbar_bg']};
            height: 12px;
            border-radius: 6px;
        }}

        QScrollBar::handle:horizontal {{
            background-color: {COLORS['scrollbar_handle']};
            border-radius: 6px;
            min-width: 20px;
        }}

        QScrollBar::handle:horizontal:hover {{
            background-color: {COLORS['scrollbar_hover']};
        }}

        QScrollBar::add-line, QScrollBar::sub-line {{
            width: 0px;
            height: 0px;
        }}

        QMessageBox {{
            background-color: {COLORS['bg_secondary']};
            border: none;
        }}

        QMessageBox QLabel {{
            color: {COLORS['text_primary']};
            background-color: transparent;
        }}

        QMessageBox QPushButton {{
            background-color: {COLORS['accent']};
            color: {COLORS['text_primary']};
            border: none;
            border-radius: 4px;
            padding: 6px 16px;
            min-width: 60px;
        }}

        QMessageBox QPushButton:hover {{
            background-color: {COLORS['accent_hover']};
        }}

        QDialog {{
            background-color: {COLORS['bg_secondary']};
            border: none;
        }}

        QFileDialog {{
            background-color: {COLORS['bg_secondary']};
        }}

        QCheckBox {{
            color: {COLORS['text_primary']};
            spacing: 8px;
        }}

        QCheckBox::indicator {{
            width: 18px;
            height: 18px;
            border: 2px solid {COLORS['border_light']};
            border-radius: 4px;
            background-color: {COLORS['bg_secondary']};
        }}

        QCheckBox::indicator:checked {{
            background-color: {COLORS['accent']};
            border-color: {COLORS['accent']};
        }}

        QCheckBox::indicator:disabled {{
            background-color: {COLORS['bg_disabled']};
            border-color: {COLORS['border']};
        }}
    """


class ToastNotification(QLabel):
    """A small auto-hiding notification that appears at the top-right of the window."""

    def __init__(self, message, parent, duration=3000):
        super().__init__(message, parent)
        self.setFont(QFont("sans-serif", 11))
        self.setStyleSheet(f"""
            background-color: {COLORS['bg_tertiary']};
            color: {COLORS['text_primary']};
            border: 1px solid {COLORS['success']};
            border-left: 3px solid {COLORS['success']};
            border-radius: 6px;
            padding: 10px 16px;
        """)
        self.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.adjustSize()
        self.setMinimumWidth(220)
        self.adjustSize()

        # Position at top-right of the parent window
        top_widget = parent.window()
        self.setParent(top_widget)
        x = (top_widget.width() - self.width()) // 2
        self.move(x, 16)
        self.raise_()
        self.show()

        # Fade out and destroy after duration
        QTimer.singleShot(duration, self._fade_out)

    def _fade_out(self):
        effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(effect)
        self.anim = QPropertyAnimation(effect, b"opacity")
        self.anim.setDuration(400)
        self.anim.setStartValue(1.0)
        self.anim.setEndValue(0.0)
        self.anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.anim.finished.connect(self.deleteLater)
        self.anim.start()

