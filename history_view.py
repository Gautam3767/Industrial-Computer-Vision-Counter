"""In-app History / Analytics tab (Roadmap Phase 5).

Sourced entirely from SQLite via HourlyStorage: an hourly bar chart plus an
hourly table, a daily summary table, and a per-class breakdown table. A Refresh
button reloads from the database on demand.
"""
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

try:
    import pyqtgraph as pg
    HAVE_PYQTGRAPH = True
except Exception:  # pragma: no cover - optional dependency
    HAVE_PYQTGRAPH = False


def _table(headers):
    t = QTableWidget(0, len(headers))
    t.setHorizontalHeaderLabels(headers)
    t.verticalHeader().setVisible(False)
    t.setEditTriggers(QTableWidget.NoEditTriggers)
    t.setSelectionMode(QTableWidget.NoSelection)
    t.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
    return t


def _fill(table, rows):
    table.setRowCount(len(rows))
    for r, row in enumerate(rows):
        for c, value in enumerate(row):
            item = QTableWidgetItem(str(value))
            if c > 0:
                item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            table.setItem(r, c, item)


class HistoryView(QWidget):
    def __init__(self, storage, parent=None):
        super().__init__(parent)
        self.storage = storage

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(14)

        header = QHBoxLayout()
        title = QLabel("History & Analytics")
        title.setObjectName("appTitle")
        header.addWidget(title)
        header.addStretch()
        self.refresh_btn = QPushButton("⟳ Refresh")
        self.refresh_btn.clicked.connect(self.refresh)
        header.addWidget(self.refresh_btn)
        root.addLayout(header)

        # Hourly chart
        chart_box = QGroupBox("HOURLY THROUGHPUT")
        chart_layout = QVBoxLayout(chart_box)
        if HAVE_PYQTGRAPH:
            pg.setConfigOptions(antialias=True, background="w", foreground="#57606a")
            self.plot = pg.PlotWidget()
            self.plot.setMenuEnabled(False)
            self.plot.setMouseEnabled(x=True, y=False)
            self.plot.setLabel("left", "count")
            self.plot.setLabel("bottom", "hour bucket (index)")
            self.plot.showGrid(x=False, y=True, alpha=0.2)
            self._bars = pg.BarGraphItem(x=[0], height=[0], width=0.8, brush="#2b7fff")
            self.plot.addItem(self._bars)
            self.plot.setMinimumHeight(220)
            chart_layout.addWidget(self.plot)
        else:
            self._bars = None
            chart_layout.addWidget(
                QLabel("Install pyqtgraph for the hourly chart (pip install pyqtgraph).")
            )
        root.addWidget(chart_box)

        # Tables row
        tables = QHBoxLayout()
        tables.setSpacing(14)

        hourly_box = QGroupBox("HOURLY")
        hb = QVBoxLayout(hourly_box)
        self.hourly_table = _table(["Date", "Hour", "Count"])
        hb.addWidget(self.hourly_table)
        tables.addWidget(hourly_box, 2)

        daily_box = QGroupBox("DAILY")
        db = QVBoxLayout(daily_box)
        self.daily_table = _table(["Date", "Count"])
        db.addWidget(self.daily_table)
        tables.addWidget(daily_box, 1)

        class_box = QGroupBox("PER-CLASS")
        cb = QVBoxLayout(class_box)
        self.class_table = _table(["Class", "Count"])
        cb.addWidget(self.class_table)
        tables.addWidget(class_box, 1)

        root.addLayout(tables, 1)

    def refresh(self):
        hourly = self.storage.get_all_hourly()
        daily = self.storage.get_daily()
        classes = self.storage.get_class_breakdown()

        if self._bars is not None:
            xs = list(range(len(hourly)))
            ys = [c for _, c in hourly]
            self._bars.setOpts(x=xs or [0], height=ys or [0], width=0.8)
            self.plot.setYRange(0, max(5, (max(ys) + 1) if ys else 5))

        _fill(self.hourly_table,
              [(b.split(" ")[0], b.split(" ")[1], c) for b, c in hourly])
        _fill(self.daily_table, daily)
        _fill(self.class_table, classes)
