"""
ui/timeline_widget.py
Custom timeline scrubber with in-point / out-point markers,
playhead, and thumbnail strip.
"""

from PyQt6.QtWidgets import QWidget, QSizePolicy, QToolTip
from PyQt6.QtCore import Qt, pyqtSignal, QRect, QPoint, QPointF
from PyQt6.QtGui import (
    QPainter, QColor, QPen, QBrush, QLinearGradient,
    QFont, QFontMetrics, QPainterPath, QCursor
)


class TimelineWidget(QWidget):
    """
    A fully custom-drawn timeline widget.

    Features:
    - Click/drag to seek
    - Draggable in-point (I) and out-point (O) markers
    - Highlighted in/out range
    - Timecode ticks
    - Keyboard shortcuts: I = set in, O = set out
    """

    seek_requested = pyqtSignal(float)       # seconds
    in_point_changed = pyqtSignal(float)     # seconds
    out_point_changed = pyqtSignal(float)    # seconds

    _HANDLE_W = 10
    _TRACK_H = 24
    _TICK_AREA_H = 20

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(72)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self._duration = 0.0
        self._position = 0.0
        self._in_point = 0.0
        self._out_point = 0.0

        self._dragging = None   # "playhead" | "in" | "out" | None
        self._hover_x = -1

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_duration(self, seconds: float):
        self._duration = max(seconds, 0.001)
        if self._out_point == 0.0:
            self._out_point = self._duration
        self.update()

    def set_position(self, seconds: float):
        self._position = max(0.0, min(seconds, self._duration))
        self.update()

    def set_in_point(self, seconds: float):
        self._in_point = max(0.0, min(seconds, self._out_point - 0.1))
        self.in_point_changed.emit(self._in_point)
        self.update()

    def set_out_point(self, seconds: float):
        self._out_point = max(self._in_point + 0.1, min(seconds, self._duration))
        self.out_point_changed.emit(self._out_point)
        self.update()

    def get_in_point(self) -> float:
        return self._in_point

    def get_out_point(self) -> float:
        return self._out_point

    def reset_points(self):
        self._in_point = 0.0
        self._out_point = self._duration
        self.in_point_changed.emit(self._in_point)
        self.out_point_changed.emit(self._out_point)
        self.update()

    # ------------------------------------------------------------------
    # Geometry helpers
    # ------------------------------------------------------------------

    def _track_rect(self) -> QRect:
        m = 16   # horizontal margin
        y = self._TICK_AREA_H
        h = self._TRACK_H
        return QRect(m, y, self.width() - m * 2, h)

    def _sec_to_x(self, sec: float) -> int:
        r = self._track_rect()
        if self._duration <= 0:
            return r.left()
        return r.left() + int((sec / self._duration) * r.width())

    def _x_to_sec(self, x: int) -> float:
        r = self._track_rect()
        if r.width() <= 0:
            return 0.0
        ratio = (x - r.left()) / r.width()
        return max(0.0, min(1.0, ratio)) * self._duration

    def _hit_handle(self, x: int, target_sec: float, tolerance: int = 8) -> bool:
        tx = self._sec_to_x(target_sec)
        return abs(x - tx) <= tolerance

    # ------------------------------------------------------------------
    # Paint
    # ------------------------------------------------------------------

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        r = self._track_rect()
        w = self.width()

        # Background
        p.fillRect(self.rect(), QColor("#1a1a2e"))

        # Tick marks
        self._draw_ticks(p, r)

        # Full track background
        track_bg = QColor("#2a2a3e")
        p.fillRect(r, track_bg)

        # In/Out range highlight
        if self._duration > 0:
            in_x = self._sec_to_x(self._in_point)
            out_x = self._sec_to_x(self._out_point)
            range_rect = QRect(in_x, r.top(), out_x - in_x, r.height())
            grad = QLinearGradient(QPointF(range_rect.topLeft()), QPointF(range_rect.bottomLeft()))
            grad.setColorAt(0, QColor("#3d5a80"))
            grad.setColorAt(1, QColor("#2d4a70"))
            p.fillRect(range_rect, QBrush(grad))

            # Track border
            p.setPen(QPen(QColor("#4a4a6a"), 1))
            p.drawRect(r)

            # In-point handle
            self._draw_handle(p, in_x, r, QColor("#00d4aa"), "◀", "I")
            # Out-point handle
            self._draw_handle(p, out_x, r, QColor("#ff6b6b"), "▶", "O")

            # Playhead
            px = self._sec_to_x(self._position)
            ph_pen = QPen(QColor("#ffffff"), 2)
            p.setPen(ph_pen)
            p.drawLine(px, r.top() - 2, px, r.bottom() + 2)
            # Playhead diamond
            diamond = QPainterPath()
            diamond.moveTo(px, r.top() - 6)
            diamond.lineTo(px + 5, r.top())
            diamond.lineTo(px, r.top() + 6)
            diamond.lineTo(px - 5, r.top())
            diamond.closeSubpath()
            p.fillPath(diamond, QColor("#ffffff"))

        # Hover tooltip line
        if self._hover_x > 0 and self._duration > 0:
            p.setPen(QPen(QColor(255, 255, 255, 60), 1, Qt.PenStyle.DotLine))
            p.drawLine(self._hover_x, r.top(), self._hover_x, r.bottom())

        p.end()

    def _draw_ticks(self, p: QPainter, r: QRect):
        if self._duration <= 0:
            return

        p.setPen(QPen(QColor("#4a4a6a"), 1))
        font = QFont("Courier New", 8)
        p.setFont(font)
        fm = QFontMetrics(font)

        # Determine tick interval
        intervals = [0.5, 1, 2, 5, 10, 15, 30, 60, 120, 300]
        pixels_per_sec = r.width() / self._duration
        min_label_px = 60
        interval = 1.0
        for iv in intervals:
            if pixels_per_sec * iv >= min_label_px:
                interval = iv
                break

        t = 0.0
        while t <= self._duration:
            x = self._sec_to_x(t)
            p.drawLine(x, r.top() - 4, x, r.top() - 1)
            label = self._format_tc_short(t)
            text_w = fm.horizontalAdvance(label)
            p.setPen(QColor("#7a7a9a"))
            p.drawText(x - text_w // 2, r.top() - 6, label)
            p.setPen(QPen(QColor("#4a4a6a"), 1))
            t += interval

    def _draw_handle(self, p: QPainter, x: int, r: QRect, color: QColor, arrow: str, label: str):
        hw = self._HANDLE_W
        # Vertical line
        p.setPen(QPen(color, 2))
        p.drawLine(x, r.top(), x, r.bottom())

        # Flag
        flag = QPainterPath()
        if arrow == "◀":   # in-point: flag extends right
            flag.moveTo(x, r.top())
            flag.lineTo(x + hw * 2, r.top())
            flag.lineTo(x + hw * 2, r.top() + hw)
            flag.lineTo(x, r.top() + hw)
            flag.closeSubpath()
        else:              # out-point: flag extends left
            flag.moveTo(x, r.top())
            flag.lineTo(x - hw * 2, r.top())
            flag.lineTo(x - hw * 2, r.top() + hw)
            flag.lineTo(x, r.top() + hw)
            flag.closeSubpath()

        p.fillPath(flag, color)
        p.setPen(QColor("#000000"))
        p.setFont(QFont("Arial", 7, QFont.Weight.Bold))
        if arrow == "◀":
            p.drawText(x + 3, r.top() + hw - 3, label)
        else:
            p.drawText(x - hw * 2 + 3, r.top() + hw - 3, label)

    # ------------------------------------------------------------------
    # Mouse Events
    # ------------------------------------------------------------------

    def mousePressEvent(self, event):
        if self._duration <= 0:
            return
        x = event.position().x()

        if self._hit_handle(int(x), self._in_point):
            self._dragging = "in"
        elif self._hit_handle(int(x), self._out_point):
            self._dragging = "out"
        else:
            self._dragging = "playhead"
            sec = self._x_to_sec(int(x))
            self.seek_requested.emit(sec)

    def mouseMoveEvent(self, event):
        if self._duration <= 0:
            return
        x = int(event.position().x())
        self._hover_x = x
        sec = self._x_to_sec(x)

        if self._dragging == "playhead":
            self.seek_requested.emit(sec)
        elif self._dragging == "in":
            self.set_in_point(sec)
        elif self._dragging == "out":
            self.set_out_point(sec)
        else:
            # Cursor hint
            if self._hit_handle(x, self._in_point) or self._hit_handle(x, self._out_point):
                self.setCursor(Qt.CursorShape.SizeHorCursor)
            else:
                self.setCursor(Qt.CursorShape.CrossCursor)

            # Tooltip
            QToolTip.showText(QCursor.pos(), self._format_tc(sec), self)

        self.update()

    def mouseReleaseEvent(self, event):
        self._dragging = None

    def leaveEvent(self, event):
        self._hover_x = -1
        self.update()

    # ------------------------------------------------------------------
    # Keyboard
    # ------------------------------------------------------------------

    def keyPressEvent(self, event):
        key = event.key()
        if key == Qt.Key.Key_I:
            self.set_in_point(self._position)
        elif key == Qt.Key.Key_O:
            self.set_out_point(self._position)
        else:
            super().keyPressEvent(event)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _format_tc(seconds: float) -> str:
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        ms = int((seconds * 1000) % 1000)
        return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"

    @staticmethod
    def _format_tc_short(seconds: float) -> str:
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        if h > 0:
            return f"{h}:{m:02d}:{s:02d}"
        return f"{m}:{s:02d}"
