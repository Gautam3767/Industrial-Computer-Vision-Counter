"""Video display widget with a mouse-drawn counting line (Roadmap Phase 3).

A `QLabel` that shows the (already aspect-scaled, letterboxed) frame pixmap and,
in draw mode, lets the user click-drag an arbitrary-angle line. It emits the
endpoints normalized to the displayed image (0-1), so the geometry is
resolution-independent and survives camera/frame-size changes.
"""
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor, QPainter, QPen
from PyQt5.QtWidgets import QLabel


class VideoView(QLabel):
    # Normalized endpoints: x1, y1, x2, y2 in [0, 1] relative to the image.
    line_drawn = pyqtSignal(float, float, float, float)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._draw_mode = False
        self._drawing = False
        self._start = None  # widget coords
        self._end = None
        self._pix_w = 0
        self._pix_h = 0

    def set_draw_mode(self, on):
        self._draw_mode = on
        self.setCursor(Qt.CrossCursor if on else Qt.ArrowCursor)

    def setPixmap(self, pix):
        self._pix_w = pix.width()
        self._pix_h = pix.height()
        super().setPixmap(pix)

    # ---------- coordinate mapping (account for letterboxing) ----------

    def _pix_offset(self):
        return ((self.width() - self._pix_w) // 2,
                (self.height() - self._pix_h) // 2)

    def _to_norm(self, pos):
        if self._pix_w <= 0 or self._pix_h <= 0:
            return None
        ox, oy = self._pix_offset()
        nx = (pos.x() - ox) / self._pix_w
        ny = (pos.y() - oy) / self._pix_h
        return max(0.0, min(1.0, nx)), max(0.0, min(1.0, ny))

    # ---------- mouse handling ----------

    def mousePressEvent(self, e):
        if self._draw_mode and e.button() == Qt.LeftButton:
            self._drawing = True
            self._start = e.pos()
            self._end = e.pos()
            self.update()
        else:
            super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        if self._drawing:
            self._end = e.pos()
            self.update()
        else:
            super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e):
        if self._drawing and e.button() == Qt.LeftButton:
            self._drawing = False
            self._end = e.pos()
            n1 = self._to_norm(self._start)
            n2 = self._to_norm(self._end)
            self.update()
            # Ignore stray clicks that didn't actually drag a line.
            if n1 and n2 and (abs(n1[0] - n2[0]) > 0.02
                              or abs(n1[1] - n2[1]) > 0.02):
                self.line_drawn.emit(n1[0], n1[1], n2[0], n2[1])
            self._start = self._end = None
        else:
            super().mouseReleaseEvent(e)

    # ---------- rubber-band preview while dragging ----------

    def paintEvent(self, e):
        super().paintEvent(e)
        if self._drawing and self._start and self._end:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setPen(QPen(QColor(255, 210, 0), 2))
            painter.drawLine(self._start, self._end)
            painter.setBrush(QColor(255, 210, 0))
            for p in (self._start, self._end):
                painter.drawEllipse(p, 4, 4)
            painter.end()
