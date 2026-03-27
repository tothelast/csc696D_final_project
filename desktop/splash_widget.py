"""Circular progress splash widget shown during file loading/importing."""

import os
from PyQt6.QtWidgets import QWidget, QGraphicsOpacityEffect
from PyQt6.QtCore import (
    Qt, pyqtSignal, pyqtProperty, QPropertyAnimation, QEasingCurve,
    QRectF, QTimer
)
from PyQt6.QtGui import QPainter, QPen, QFont, QColor, QPixmap

from desktop.landing_page import invert_dark_pixels
from desktop.theme import COLORS

CIRCLE_DIAMETER = 280
LOGO_HEIGHT = 100
ARC_WIDTH = 5


class CircularSplashWidget(QWidget):
    """Full-page widget with a circular progress indicator, logo, and status text."""

    finished = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._progress = 0.0
        self._status_text = ""
        self._progress_anim = None
        self._fade_anim = None
        self._finishing = False

        # Load and process logo
        self._logo_pixmap = None
        logo_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logo.png")
        if os.path.exists(logo_path):
            pixmap = QPixmap(logo_path)
            scaled = pixmap.scaledToHeight(LOGO_HEIGHT, Qt.TransformationMode.SmoothTransformation)
            self._logo_pixmap = invert_dark_pixels(scaled)

    # -- Qt property for animation --
    def _get_progress(self):
        return self._progress

    def _set_progress_value(self, value):
        self._progress = value
        self.update()

    progress = pyqtProperty(float, _get_progress, _set_progress_value)

    # -- Public API --
    def set_progress(self, value, status_text=None):
        """Animate progress to `value` (0-100) and optionally update status text."""
        if status_text is not None:
            self._status_text = status_text

        # Stop any running animation
        if self._progress_anim is not None:
            self._progress_anim.stop()

        anim = QPropertyAnimation(self, b"progress")
        anim.setDuration(300)
        anim.setStartValue(self._progress)
        anim.setEndValue(float(value))
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._progress_anim = anim  # prevent GC

        if value >= 100 and not self._finishing:
            anim.finished.connect(self._on_complete)

        anim.start()

    def reset(self):
        """Reset widget state for reuse."""
        self._progress = 0.0
        self._status_text = ""
        self._finishing = False
        # Clear any opacity effect from previous fade-out
        self.setGraphicsEffect(None)
        self.update()

    # -- Internal --
    def _on_complete(self):
        if self._finishing:
            return
        self._finishing = True
        QTimer.singleShot(400, self._fade_out)

    def _fade_out(self):
        effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(effect)
        anim = QPropertyAnimation(effect, b"opacity")
        anim.setDuration(500)
        anim.setStartValue(1.0)
        anim.setEndValue(0.0)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.finished.connect(self.finished.emit)
        self._fade_anim = anim  # prevent GC
        anim.start()

    # -- Painting --
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 1. Background
        painter.fillRect(self.rect(), QColor(COLORS['bg_primary']))

        # Geometry
        w, h = self.width(), self.height()
        status_font = QFont("sans-serif", 12)
        status_height = 30
        total_height = CIRCLE_DIAMETER + 16 + status_height
        top_y = (h - total_height) / 2
        cx = w / 2
        circle_rect = QRectF(
            cx - CIRCLE_DIAMETER / 2,
            top_y,
            CIRCLE_DIAMETER,
            CIRCLE_DIAMETER,
        )

        # 2. Track ring (full circle)
        track_pen = QPen(QColor(COLORS['border']), ARC_WIDTH)
        track_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(track_pen)
        painter.drawEllipse(circle_rect)

        # 3. Progress arc
        if self._progress > 0:
            arc_pen = QPen(QColor(COLORS['accent']), ARC_WIDTH)
            arc_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(arc_pen)
            # Qt angles: 0° = 3 o'clock, positive = counter-clockwise
            # We want start at 12 o'clock (90°) sweeping clockwise (negative)
            start_angle = 90 * 16  # 12 o'clock in 1/16 degree units
            span_angle = -int((self._progress / 100.0) * 360 * 16)
            painter.drawArc(circle_rect, start_angle, span_angle)

        # Interior region for logo + percentage
        inset = ARC_WIDTH + 10
        interior_top = circle_rect.top() + inset
        interior_bottom = circle_rect.bottom() - inset
        interior_height = interior_bottom - interior_top
        interior_mid = interior_top + interior_height / 2

        # 4. Logo (upper half of interior)
        if self._logo_pixmap is not None:
            lw = self._logo_pixmap.width()
            lh = self._logo_pixmap.height()
            logo_x = cx - lw / 2
            # Center logo in upper half
            upper_half_center = interior_top + (interior_mid - interior_top) / 2
            logo_y = upper_half_center - lh / 2
            painter.drawPixmap(int(logo_x), int(logo_y), self._logo_pixmap)

        # 5. Percentage text (lower half of interior)
        pct_font = QFont("sans-serif", 32, QFont.Weight.Bold)
        painter.setFont(pct_font)
        painter.setPen(QColor(COLORS['text_primary']))
        lower_rect = QRectF(
            circle_rect.left(), interior_mid,
            circle_rect.width(), interior_bottom - interior_mid
        )
        painter.drawText(lower_rect, Qt.AlignmentFlag.AlignCenter, f"{int(self._progress)}%")

        # 6. Status text below circle
        if self._status_text:
            painter.setFont(status_font)
            painter.setPen(QColor(COLORS['text_secondary']))
            status_rect = QRectF(
                0, circle_rect.bottom() + 16,
                w, status_height
            )
            painter.drawText(status_rect, Qt.AlignmentFlag.AlignCenter, self._status_text)

        painter.end()
