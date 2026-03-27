"""Landing Page - Initial page with create/load project options."""

import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QSpacerItem, QSizePolicy
)
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QPixmap, QImage

from desktop.theme import COLORS


def invert_dark_pixels(pixmap):
    """
    Invert dark pixels in a pixmap to make them light.
    Preserves the red color and makes black/dark grey text white.
    """
    image = pixmap.toImage()
    image = image.convertToFormat(QImage.Format.Format_ARGB32)

    for y in range(image.height()):
        for x in range(image.width()):
            pixel = image.pixelColor(x, y)
            r, g, b, a = pixel.red(), pixel.green(), pixel.blue(), pixel.alpha()

            # Skip transparent pixels
            if a < 10:
                continue

            # Check if pixel is dark (grey/black) - not red
            # Red pixels have high R and low G, B
            is_red = r > 150 and g < 100 and b < 100

            if not is_red:
                # Invert dark pixels to light
                # If the pixel is dark (low brightness), make it light
                brightness = (r + g + b) / 3
                if brightness < 128:
                    # Invert to light grey/white
                    new_val = 255 - int(brightness)
                    pixel.setRed(new_val)
                    pixel.setGreen(new_val)
                    pixel.setBlue(new_val)
                    image.setPixelColor(x, y, pixel)

    return QPixmap.fromImage(image)


class LandingPage(QWidget):
    """Landing page with create new project and load existing project buttons."""

    create_project_clicked = pyqtSignal()
    load_project_clicked = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setup_ui()

    def setup_ui(self):
        """Initialize the UI components."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(50, 50, 50, 50)

        # Add vertical spacer
        layout.addSpacerItem(QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding))

        # Company Logo
        logo_label = QLabel()
        logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logo.png")
        if os.path.exists(logo_path):
            pixmap = QPixmap(logo_path)
            # Scale logo to reasonable size while maintaining aspect ratio
            scaled_pixmap = pixmap.scaledToHeight(250, Qt.TransformationMode.SmoothTransformation)
            # Invert dark pixels to light for dark theme visibility
            inverted_pixmap = invert_dark_pixels(scaled_pixmap)
            logo_label.setPixmap(inverted_pixmap)
        else:
            logo_label.setText("ARACA Incorporated")
            logo_label.setStyleSheet(f"font-size: 28px; font-weight: bold; color: {COLORS['text_primary']};")
        layout.addWidget(logo_label)

        # Add spacing after logo
        layout.addSpacerItem(QSpacerItem(20, 30, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed))

        # Title - Rich text for professional branding (2 lines)
        title_label = QLabel()
        title_label.setTextFormat(Qt.TextFormat.RichText)
        title_label.setText(
            f'<span style="font-size: 38px; font-weight: 700; color: {COLORS["accent"]};">'
            f'Araca Insights<sup>®</sup></span>'
            f'<span style="font-size: 38px; font-weight: 300; color: {COLORS["text_primary"]};">'
            f' Wafer Polishing Data Manager</span>'
        )
        title_label.setObjectName("headerLabel")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet("margin-bottom: 10px;")
        layout.addWidget(title_label)

        # Subtitle
        subtitle_label = QLabel("Analyze and manage your wafer polishing data with ease")
        subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle_label.setStyleSheet(f"font-size: 16px; color: {COLORS['text_secondary']}; margin-bottom: 40px;")
        layout.addWidget(subtitle_label)

        # Buttons container
        button_container = QWidget()
        button_layout = QHBoxLayout(button_container)
        button_layout.setSpacing(20)

        # Add horizontal spacer
        button_layout.addSpacerItem(QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum))

        # Create New Project button
        self.create_btn = QPushButton("Create New Project")
        self.create_btn.setMinimumSize(200, 50)
        self.create_btn.setStyleSheet("""
            QPushButton {
                font-size: 15px;
                font-weight: 600;
            }
        """)
        self.create_btn.clicked.connect(self.create_project_clicked.emit)
        button_layout.addWidget(self.create_btn)

        # Load Existing Project button
        self.load_btn = QPushButton("Load Existing Project")
        self.load_btn.setObjectName("secondaryButton")
        self.load_btn.setMinimumSize(200, 50)
        self.load_btn.setStyleSheet("""
            QPushButton {
                font-size: 15px;
                font-weight: 600;
            }
        """)
        self.load_btn.clicked.connect(self.load_project_clicked.emit)
        button_layout.addWidget(self.load_btn)

        # Add horizontal spacer
        button_layout.addSpacerItem(QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum))

        layout.addWidget(button_container)

        # Add vertical spacer
        layout.addSpacerItem(QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding))

        # Footer
        footer_label = QLabel("© 2026 Araca Incorporated")
        footer_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        footer_label.setStyleSheet(f"font-size: 12px; color: {COLORS['text_secondary']};")
        layout.addWidget(footer_label)

