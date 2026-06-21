"""Live counts-per-minute throughput chart (Roadmap Phase 5).

Thin wrapper over pyqtgraph so the rest of the app doesn't depend on it
directly. If pyqtgraph isn't installed the widget degrades to a short message
instead of crashing the app.
"""
from PyQt5.QtWidgets import QLabel, QVBoxLayout, QWidget

try:
    import pyqtgraph as pg
    HAVE_PYQTGRAPH = True
except Exception:  # pragma: no cover - optional dependency
    HAVE_PYQTGRAPH = False


class LiveThroughputChart(QWidget):
    """Bar chart of counts-per-minute over the last N minutes."""

    def __init__(self, minutes=15, parent=None):
        super().__init__(parent)
        self.minutes = minutes
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        if not HAVE_PYQTGRAPH:
            msg = QLabel("Install pyqtgraph to see the live throughput chart\n"
                         "(pip install pyqtgraph).")
            msg.setWordWrap(True)
            layout.addWidget(msg)
            self._bars = None
            return

        pg.setConfigOptions(antialias=True, background="w", foreground="#57606a")
        self.plot = pg.PlotWidget()
        self.plot.setMenuEnabled(False)
        self.plot.setMouseEnabled(x=False, y=False)
        self.plot.hideButtons()
        self.plot.setLabel("left", "counts / min")
        self.plot.setLabel("bottom", "minutes ago")
        self.plot.showGrid(x=False, y=True, alpha=0.2)
        self._bars = pg.BarGraphItem(x=[0], height=[0], width=0.8, brush="#2b7fff")
        self.plot.addItem(self._bars)
        layout.addWidget(self.plot)

    def update_data(self, per_minute):
        """per_minute: list of (minute_offset, count) from ThroughputMonitor."""
        if self._bars is None:
            return
        xs = [o for o, _ in per_minute]
        ys = [c for _, c in per_minute]
        self._bars.setOpts(x=xs, height=ys, width=0.8)
        top = max(ys) if ys else 0
        self.plot.setYRange(0, max(5, top + 1))
