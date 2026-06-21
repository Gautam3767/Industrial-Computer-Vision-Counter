from datetime import datetime
from time import time

import cv2
from PyQt5.QtCore import QDate, Qt, QTimer
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QSpinBox,
    QStackedWidget,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from alerts import ThroughputMonitor
from config import load_config, save_config
from detector import ObjectCounter
from history_view import HistoryView
from live_chart import LiveThroughputChart
from storage import HourlyStorage
from video_view import VideoView
from video_worker import VideoWorker
from yolo_detector import YoloCounter


def list_cameras(max_test=3):
    found = []
    for i in range(max_test):
        cap = cv2.VideoCapture(i)
        if cap is not None and cap.isOpened():
            found.append(i)
            cap.release()
    return found


ENGINE_MOG = "Motion (MOG2)"
ENGINE_YOLO = "YOLO11 + ByteTrack"

SOURCE_WEBCAM = "Webcam"
SOURCE_FILE = "Video file"
SOURCE_URL = "RTSP / URL"


STYLE = """
QMainWindow, QWidget#central { background: #f4f5f7; }
QLabel { color: #1c1e21; font-size: 13px; }

QTabWidget::pane { border: none; }
QTabBar::tab {
    background: transparent;
    color: #57606a;
    padding: 8px 18px;
    font-size: 13px;
    font-weight: 600;
    border-bottom: 2px solid transparent;
}
QTabBar::tab:selected { color: #1958c9; border-bottom: 2px solid #2b7fff; }

QGroupBox {
    background: white;
    border: 1px solid #e1e4e8;
    border-radius: 10px;
    margin-top: 18px;
    padding: 14px 12px 12px 12px;
    font-weight: 600;
    font-size: 13px;
    color: #1c1e21;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 12px;
    padding: 0 6px;
    color: #57606a;
    font-size: 10px;
    letter-spacing: 1.5px;
}

QPushButton {
    background: white;
    border: 1px solid #d0d7de;
    border-radius: 7px;
    padding: 8px 14px;
    font-size: 13px;
    color: #1c1e21;
}
QPushButton:hover { background: #f6f8fa; border-color: #afb8c1; }
QPushButton:pressed { background: #eaeef2; }
QPushButton:disabled { color: #8c959f; background: #f6f8fa; }
QPushButton:checked { background: #e8f0fe; border-color: #2b7fff; color: #1958c9; }
QPushButton#primaryBtn {
    background: #2b7fff;
    color: white;
    border: none;
    font-weight: 600;
}
QPushButton#primaryBtn:hover { background: #1f6feb; }
QPushButton#primaryBtn:pressed { background: #1958c9; }
QPushButton#primaryBtn:disabled { background: #9ac0ff; color: white; }
QPushButton#dangerBtn { color: #cf222e; }
QPushButton#dangerBtn:hover { background: #fbecec; border-color: #f6b5bb; }

QComboBox, QSpinBox, QLineEdit, QDateEdit {
    background: white;
    border: 1px solid #d0d7de;
    border-radius: 6px;
    padding: 6px 10px;
    font-size: 13px;
    min-height: 22px;
    selection-background-color: #cfe5ff;
}
QComboBox::drop-down { border: none; width: 22px; }
QComboBox QAbstractItemView {
    background: white;
    border: 1px solid #d0d7de;
    selection-background-color: #e8f0fe;
    selection-color: #1c1e21;
    outline: none;
}

QSlider::groove:horizontal {
    height: 4px;
    background: #d0d7de;
    border-radius: 2px;
}
QSlider::sub-page:horizontal {
    background: #2b7fff;
    border-radius: 2px;
}
QSlider::handle:horizontal {
    background: white;
    border: 2px solid #2b7fff;
    width: 14px;
    height: 14px;
    margin: -6px 0;
    border-radius: 9px;
}

QFrame#videoContainer {
    background: white;
    border: 1px solid #e1e4e8;
    border-radius: 12px;
}
QFrame#counterFrame {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #2b7fff, stop:1 #1958c9);
    border-radius: 12px;
}
QLabel#counterLabel {
    color: rgba(255,255,255,0.75);
    font-size: 10px;
    letter-spacing: 2px;
    font-weight: 600;
}
QLabel#counterValue {
    color: white;
    font-size: 64px;
    font-weight: 700;
}
QLabel#subLabel {
    color: rgba(255,255,255,0.7);
    font-size: 9px;
    letter-spacing: 1.5px;
    font-weight: 600;
}
QLabel#subValue {
    color: white;
    font-size: 22px;
    font-weight: 600;
}
QLabel#statusDot { color: #999; font-size: 12px; }
QLabel#appTitle { font-size: 18px; font-weight: 700; color: #1c1e21; }
QLabel#appSubtitle { font-size: 12px; color: #57606a; }
QLabel#engineHint { color: #57606a; font-size: 11px; }
QLabel#classPanel { color: #1c1e21; font-size: 13px; }
QLabel#alertBanner {
    color: white;
    font-size: 13px;
    font-weight: 600;
    border-radius: 8px;
    padding: 8px 12px;
}
"""


class ResetDialog(QDialog):
    """Choose between wiping all history or clearing a date range (Phase 5)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Clear counts")
        v = QVBoxLayout(self)
        v.setSpacing(10)

        self.range_radio = QRadioButton("Clear a date range only (recommended)")
        self.range_radio.setChecked(True)
        v.addWidget(self.range_radio)

        row = QHBoxLayout()
        row.addWidget(QLabel("From"))
        self.from_date = QDateEdit(QDate.currentDate())
        self.from_date.setCalendarPopup(True)
        self.from_date.setDisplayFormat("yyyy-MM-dd")
        row.addWidget(self.from_date)
        row.addWidget(QLabel("To"))
        self.to_date = QDateEdit(QDate.currentDate())
        self.to_date.setCalendarPopup(True)
        self.to_date.setDisplayFormat("yyyy-MM-dd")
        row.addWidget(self.to_date)
        v.addLayout(row)

        self.all_radio = QRadioButton("Clear ALL history (destructive)")
        v.addWidget(self.all_radio)

        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        v.addWidget(bb)

    def result_spec(self):
        if self.all_radio.isChecked():
            return ("all",)
        return ("range",
                self.from_date.date().toString("yyyy-MM-dd"),
                self.to_date.date().toString("yyyy-MM-dd"))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("CV Object Counter")
        self.resize(1420, 860)

        self.cfg = load_config()
        self.storage = HourlyStorage()
        self.counter = ObjectCounter()
        self.monitor = ThroughputMonitor()

        self.worker = None
        self.running = False
        self.paused = False
        self.session_count = 0
        self._busy = False
        self._scrubbing = False
        self._alert_state = "ok"
        # Mouse-drawn line as ((nx1, ny1), (nx2, ny2)) or None (= use slider).
        self._custom_line = None

        self._build_ui()
        self.setStyleSheet(STYLE)
        self._apply_config()
        self._sync_counter_settings()
        self.counter.custom_line = self._custom_line
        self._refresh_counter_displays()
        self._refresh_class_panel()
        self._apply_engine_visibility()
        self._on_source_type_change(self.source_type_combo.currentText())

        # 1 Hz tick: anomaly evaluation + live chart refresh.
        self._tick = QTimer(self)
        self._tick.timeout.connect(self._on_tick)
        self._tick.start(1000)

    # ---------- UI construction ----------

    def _build_ui(self):
        self.tabs = QTabWidget()
        self.tabs.setObjectName("central")
        self.setCentralWidget(self.tabs)

        live = QWidget()
        root = QHBoxLayout(live)
        root.setContentsMargins(18, 12, 18, 18)
        root.setSpacing(16)
        root.addWidget(self._build_video_panel(), 3)
        root.addWidget(self._build_controls_panel(), 0)
        self.tabs.addTab(live, "Live")

        self.history_view = HistoryView(self.storage)
        self.tabs.addTab(self.history_view, "History")
        self.tabs.currentChanged.connect(self._on_tab_change)

    def _build_video_panel(self):
        container = QFrame()
        container.setObjectName("videoContainer")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        header = QHBoxLayout()
        title = QLabel("CV Object Counter")
        title.setObjectName("appTitle")
        subtitle = QLabel("Conveyor belt counter")
        subtitle.setObjectName("appSubtitle")

        title_col = QVBoxLayout()
        title_col.setSpacing(0)
        title_col.addWidget(title)
        title_col.addWidget(subtitle)
        header.addLayout(title_col)
        header.addStretch()

        self.status_label = QLabel("● Idle")
        self.status_label.setObjectName("statusDot")
        header.addWidget(self.status_label)
        layout.addLayout(header)

        self.alert_banner = QLabel("")
        self.alert_banner.setObjectName("alertBanner")
        self.alert_banner.setVisible(False)
        layout.addWidget(self.alert_banner)

        self.video_label = VideoView("Select a source and press Start")
        self.video_label.setAlignment(Qt.AlignCenter)
        self.video_label.setMinimumSize(720, 500)
        self.video_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.video_label.setStyleSheet(
            "background: #0a0a0a; color: #777; border-radius: 10px; font-size: 13px;"
        )
        self.video_label.line_drawn.connect(self._on_line_drawn)
        layout.addWidget(self.video_label, 1)

        layout.addWidget(self._build_playback_bar())
        layout.addWidget(self._build_live_chart())
        return container

    def _build_playback_bar(self):
        self.playback_widget = QWidget()
        row = QHBoxLayout(self.playback_widget)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)

        self.play_btn = QPushButton("⏸ Pause")
        self.play_btn.setFixedWidth(96)
        self.play_btn.clicked.connect(self._toggle_pause)
        row.addWidget(self.play_btn)

        self.seek_slider = QSlider(Qt.Horizontal)
        self.seek_slider.setRange(0, 0)
        self.seek_slider.sliderPressed.connect(lambda: setattr(self, "_scrubbing", True))
        self.seek_slider.sliderReleased.connect(self._on_seek_released)
        row.addWidget(self.seek_slider, 1)

        self.time_label = QLabel("0 / 0")
        self.time_label.setObjectName("engineHint")
        row.addWidget(self.time_label)

        self.playback_widget.setVisible(False)
        return self.playback_widget

    def _build_live_chart(self):
        box = QGroupBox("LIVE THROUGHPUT (counts / min, last 15 min)")
        v = QVBoxLayout(box)
        v.setContentsMargins(10, 8, 10, 8)
        self.live_chart = LiveThroughputChart(minutes=15)
        self.live_chart.setMinimumHeight(140)
        self.live_chart.setMaximumHeight(170)
        v.addWidget(self.live_chart)
        return box

    def _build_controls_panel(self):
        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.setSpacing(14)
        layout.setContentsMargins(0, 0, 10, 0)  # room for scrollbar

        layout.addWidget(self._build_counter_display())
        layout.addWidget(self._build_class_group())
        layout.addWidget(self._build_source_group())
        layout.addWidget(self._build_engine_group())
        layout.addWidget(self._build_yolo_group())
        layout.addWidget(self._build_perf_group())
        layout.addWidget(self._build_alerts_group())
        layout.addWidget(self._build_line_group())
        layout.addLayout(self._build_action_buttons())
        layout.addStretch()

        scroll = QScrollArea()
        scroll.setWidget(inner)
        scroll.setWidgetResizable(True)
        scroll.setFixedWidth(380)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { background: transparent; }")
        return scroll

    def _build_counter_display(self):
        frame = QFrame()
        frame.setObjectName("counterFrame")
        v = QVBoxLayout(frame)
        v.setContentsMargins(20, 18, 20, 18)
        v.setSpacing(4)

        top = QLabel("TOTAL COUNT")
        top.setObjectName("counterLabel")
        v.addWidget(top)

        self.total_display = QLabel("0")
        self.total_display.setObjectName("counterValue")
        self.total_display.setAlignment(Qt.AlignCenter)
        v.addWidget(self.total_display)

        sub = QHBoxLayout()
        sub.setSpacing(12)
        for label_text, attr in [("THIS HOUR", "hour_display"),
                                 ("SESSION", "session_display")]:
            col = QVBoxLayout()
            col.setSpacing(2)
            lbl = QLabel(label_text)
            lbl.setObjectName("subLabel")
            val = QLabel("0")
            val.setObjectName("subValue")
            col.addWidget(lbl)
            col.addWidget(val)
            sub.addLayout(col)
            setattr(self, attr, val)

        v.addLayout(sub)
        return frame

    def _build_class_group(self):
        group = QGroupBox("PER-CLASS BREAKDOWN")
        v = QVBoxLayout(group)
        v.setSpacing(6)
        self.class_panel = QLabel("No counts yet.")
        self.class_panel.setObjectName("classPanel")
        self.class_panel.setWordWrap(True)
        v.addWidget(self.class_panel)
        return group

    def _build_source_group(self):
        group = QGroupBox("SOURCE")
        v = QVBoxLayout(group)
        v.setSpacing(8)

        self.source_type_combo = QComboBox()
        self.source_type_combo.addItems([SOURCE_WEBCAM, SOURCE_FILE, SOURCE_URL])
        self.source_type_combo.currentTextChanged.connect(self._on_source_type_change)
        v.addWidget(self.source_type_combo)

        self.source_stack = QStackedWidget()

        # Webcam page
        webcam_page = QWidget()
        wrow = QHBoxLayout(webcam_page)
        wrow.setContentsMargins(0, 0, 0, 0)
        self.cam_combo = QComboBox()
        self.refresh_btn = QPushButton("⟳")
        self.refresh_btn.setFixedWidth(36)
        self.refresh_btn.setToolTip("Rescan cameras")
        self.refresh_btn.clicked.connect(self._populate_cameras)
        wrow.addWidget(self.cam_combo, 1)
        wrow.addWidget(self.refresh_btn)
        self.source_stack.addWidget(webcam_page)

        # File page
        file_page = QWidget()
        frow = QHBoxLayout(file_page)
        frow.setContentsMargins(0, 0, 0, 0)
        self.file_edit = QLineEdit()
        self.file_edit.setPlaceholderText("Path to a video file…")
        browse = QPushButton("Browse")
        browse.clicked.connect(self._browse_file)
        frow.addWidget(self.file_edit, 1)
        frow.addWidget(browse)
        self.source_stack.addWidget(file_page)

        # URL page
        url_page = QWidget()
        urow = QHBoxLayout(url_page)
        urow.setContentsMargins(0, 0, 0, 0)
        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("rtsp://… or http://…")
        urow.addWidget(self.url_edit, 1)
        self.source_stack.addWidget(url_page)

        v.addWidget(self.source_stack)

        self.start_btn = QPushButton("Start")
        self.start_btn.setObjectName("primaryBtn")
        self.start_btn.clicked.connect(self._toggle_capture)
        v.addWidget(self.start_btn)

        self._populate_cameras()
        return group

    def _build_engine_group(self):
        group = QGroupBox("DETECTION ENGINE")
        v = QVBoxLayout(group)
        v.setSpacing(8)

        self.engine_combo = QComboBox()
        self.engine_combo.addItems([ENGINE_MOG, ENGINE_YOLO])
        self.engine_combo.currentTextChanged.connect(self._on_engine_change)
        v.addWidget(self.engine_combo)

        self.engine_hint = QLabel(
            "Motion: fast, class-agnostic, needs steady lighting."
        )
        self.engine_hint.setObjectName("engineHint")
        self.engine_hint.setWordWrap(True)
        v.addWidget(self.engine_hint)

        return group

    def _build_yolo_group(self):
        self.yolo_group = QGroupBox("YOLO11 SETTINGS")
        v = QVBoxLayout(self.yolo_group)
        v.setSpacing(10)

        row = QHBoxLayout()
        row.addWidget(QLabel("Model"))
        self.yolo_model_combo = QComboBox()
        self.yolo_model_combo.addItems(list(YoloCounter.MODEL_SIZES.keys()))
        row.addWidget(self.yolo_model_combo, 1)
        v.addLayout(row)

        size_row = QHBoxLayout()
        size_row.addWidget(QLabel("Input size"))
        self.yolo_imgsz_combo = QComboBox()
        self.yolo_imgsz_combo.addItem("Fast (480)", 480)
        self.yolo_imgsz_combo.addItem("Balanced (640)", 640)
        self.yolo_imgsz_combo.addItem("Detail (960)", 960)
        self.yolo_imgsz_combo.addItem("High detail (1280)", 1280)
        self.yolo_imgsz_combo.setCurrentIndex(1)
        self.yolo_imgsz_combo.currentIndexChanged.connect(self._update_imgsz)
        size_row.addWidget(self.yolo_imgsz_combo, 1)
        v.addLayout(size_row)

        self.yolo_conf_label = QLabel("Confidence: 0.35")
        v.addWidget(self.yolo_conf_label)
        self.yolo_conf_slider = QSlider(Qt.Horizontal)
        self.yolo_conf_slider.setRange(10, 90)
        self.yolo_conf_slider.setValue(35)
        self.yolo_conf_slider.valueChanged.connect(self._update_conf)
        v.addWidget(self.yolo_conf_slider)

        self.yolo_enhance_chk = QCheckBox("Low-light boost (CLAHE)")
        self.yolo_enhance_chk.setToolTip(
            "Recommended for dark objects on dark conveyor belts. "
            "Boosts local contrast so YOLO can see darker items."
        )
        self.yolo_enhance_chk.toggled.connect(self._update_enhance)
        v.addWidget(self.yolo_enhance_chk)

        v.addWidget(QLabel("Classes (comma-separated, empty = all)"))
        self.yolo_classes_edit = QLineEdit()
        self.yolo_classes_edit.setPlaceholderText("e.g. bottle, cup, box")
        self.yolo_classes_edit.editingFinished.connect(self._apply_classes)
        v.addWidget(self.yolo_classes_edit)

        self.yolo_device_label = QLabel("Device: —")
        self.yolo_device_label.setObjectName("engineHint")
        v.addWidget(self.yolo_device_label)

        self.yolo_load_btn = QPushButton("Load / Reload Model")
        self.yolo_load_btn.setObjectName("primaryBtn")
        self.yolo_load_btn.clicked.connect(self._load_yolo)
        v.addWidget(self.yolo_load_btn)

        return self.yolo_group

    def _build_perf_group(self):
        group = QGroupBox("PERFORMANCE")
        v = QVBoxLayout(group)
        v.setSpacing(8)

        self.perf_label = QLabel("Inference: every frame (most accurate)")
        v.addWidget(self.perf_label)
        self.perf_slider = QSlider(Qt.Horizontal)
        self.perf_slider.setRange(1, 5)
        self.perf_slider.setValue(1)
        self.perf_slider.setToolTip(
            "Run detection every Nth frame and coast the preview between — "
            "trades accuracy for a smoother, faster feed."
        )
        self.perf_slider.valueChanged.connect(self._update_perf)
        v.addWidget(self.perf_slider)

        self.stats_label = QLabel("— FPS")
        self.stats_label.setObjectName("engineHint")
        v.addWidget(self.stats_label)
        return group

    def _build_alerts_group(self):
        group = QGroupBox("ALERTS")
        v = QVBoxLayout(group)
        v.setSpacing(8)

        jam_row = QHBoxLayout()
        jam_row.addWidget(QLabel("Jam if idle for (s)"))
        self.jam_spin = QSpinBox()
        self.jam_spin.setRange(3, 120)
        self.jam_spin.setValue(int(self.monitor.jam_seconds))
        self.jam_spin.valueChanged.connect(
            lambda v: setattr(self.monitor, "jam_seconds", float(v))
        )
        jam_row.addWidget(self.jam_spin)
        v.addLayout(jam_row)

        spike_row = QHBoxLayout()
        spike_row.addWidget(QLabel("Spike if > (per min)"))
        self.spike_spin = QSpinBox()
        self.spike_spin.setRange(10, 5000)
        self.spike_spin.setSingleStep(10)
        self.spike_spin.setValue(self.monitor.spike_per_min)
        self.spike_spin.valueChanged.connect(
            lambda v: setattr(self.monitor, "spike_per_min", int(v))
        )
        spike_row.addWidget(self.spike_spin)
        v.addLayout(spike_row)

        self.sound_chk = QCheckBox("Beep on alert")
        self.sound_chk.setChecked(True)
        v.addWidget(self.sound_chk)
        return group

    def _build_line_group(self):
        group = QGroupBox("COUNTING LINE")
        v = QVBoxLayout(group)
        v.setSpacing(10)

        draw_row = QHBoxLayout()
        self.draw_line_btn = QPushButton("✏ Draw line")
        self.draw_line_btn.setCheckable(True)
        self.draw_line_btn.setToolTip("Click-drag an arbitrary-angle line on the video.")
        self.draw_line_btn.toggled.connect(self._toggle_draw)
        draw_row.addWidget(self.draw_line_btn, 1)
        self.clear_line_btn = QPushButton("Clear")
        self.clear_line_btn.setToolTip("Revert to the orientation/position slider line.")
        self.clear_line_btn.clicked.connect(self._clear_line)
        draw_row.addWidget(self.clear_line_btn)
        v.addLayout(draw_row)

        self.line_status = QLabel("Using orientation / position slider.")
        self.line_status.setObjectName("engineHint")
        self.line_status.setWordWrap(True)
        v.addWidget(self.line_status)

        orient_row = QHBoxLayout()
        orient_row.addWidget(QLabel("Orientation"))
        self.orient_combo = QComboBox()
        self.orient_combo.addItems(["Horizontal", "Vertical"])
        self.orient_combo.currentTextChanged.connect(self._update_orientation)
        orient_row.addWidget(self.orient_combo, 1)
        v.addLayout(orient_row)

        self.pos_label = QLabel("Line position: 50%")
        v.addWidget(self.pos_label)
        self.pos_slider = QSlider(Qt.Horizontal)
        self.pos_slider.setRange(5, 95)
        self.pos_slider.setValue(50)
        self.pos_slider.valueChanged.connect(self._update_line_position)
        v.addWidget(self.pos_slider)

        dir_row = QHBoxLayout()
        dir_row.addWidget(QLabel("Count direction"))
        self.dir_combo = QComboBox()
        self.dir_combo.addItems(["Both", "Forward", "Backward"])
        self.dir_combo.currentTextChanged.connect(self._update_direction)
        dir_row.addWidget(self.dir_combo, 1)
        v.addLayout(dir_row)

        self.min_row_widget = QWidget()
        min_row = QHBoxLayout(self.min_row_widget)
        min_row.setContentsMargins(0, 0, 0, 0)
        min_row.addWidget(QLabel("Min object size (px²)"))
        self.min_spin = QSpinBox()
        self.min_spin.setRange(200, 100000)
        self.min_spin.setSingleStep(100)
        self.min_spin.setValue(1500)
        self.min_spin.valueChanged.connect(self._update_min_area)
        min_row.addWidget(self.min_spin)
        v.addWidget(self.min_row_widget)

        return group

    def _build_action_buttons(self):
        row = QHBoxLayout()
        row.setSpacing(8)

        self.reset_btn = QPushButton("Clear…")
        self.reset_btn.setObjectName("dangerBtn")
        self.reset_btn.clicked.connect(self._reset)
        row.addWidget(self.reset_btn)

        self.export_btn = QPushButton("Export")
        self.export_btn.setObjectName("primaryBtn")
        self.export_btn.clicked.connect(self._export)
        row.addWidget(self.export_btn)
        return row

    # ---------- Config persistence ----------

    def _apply_config(self):
        cfg = self.cfg
        orient = cfg.get("orientation")
        if orient in ("Horizontal", "Vertical"):
            self.orient_combo.setCurrentText(orient)
        if isinstance(cfg.get("line_position"), int):
            self.pos_slider.setValue(cfg["line_position"])
        direction = cfg.get("direction")
        if direction in ("Both", "Forward", "Backward"):
            self.dir_combo.setCurrentText(direction)
        if isinstance(cfg.get("infer_every"), int):
            self.perf_slider.setValue(max(1, min(5, cfg["infer_every"])))
        line = cfg.get("custom_line")
        if line and len(line) == 2:
            (x1, y1), (x2, y2) = line
            self._custom_line = ((float(x1), float(y1)), (float(x2), float(y2)))
            self.line_status.setText("Custom drawn line (restored).")

    def _save_config(self):
        save_config({
            "orientation": self.orient_combo.currentText(),
            "line_position": self.pos_slider.value(),
            "direction": self.dir_combo.currentText(),
            "infer_every": self.perf_slider.value(),
            "custom_line": self._custom_line,
        })

    # ---------- Engine swap ----------

    def _activate_counter(self, counter):
        """Make `counter` the live engine, carrying over current settings."""
        self.counter = counter
        self.counter.on_count = None
        self._sync_counter_settings()
        self.counter.custom_line = self._custom_line
        if self.worker is not None:
            self.worker.set_counter(self.counter)

    def _on_engine_change(self, engine):
        self._apply_engine_visibility()
        if engine == ENGINE_MOG:
            self._activate_counter(ObjectCounter())
            self.engine_hint.setText(
                "Motion: fast, class-agnostic, needs steady lighting."
            )
            self.status_label.setText("● Engine: MOG2")
        else:
            self.engine_hint.setText(
                "YOLO11: class-aware, robust to occlusion. Click 'Load' to initialize."
            )
            self.status_label.setText("● YOLO not loaded — click Load")

    def _apply_engine_visibility(self):
        is_yolo = self.engine_combo.currentText() == ENGINE_YOLO
        self.yolo_group.setVisible(is_yolo)
        self.min_row_widget.setVisible(not is_yolo)

    def _load_yolo(self):
        if self._busy:
            return
        self._busy = True
        self.yolo_load_btn.setEnabled(False)
        self.status_label.setText("● Loading YOLO model…")
        QApplication.processEvents()

        model_label = self.yolo_model_combo.currentText()
        model_file = YoloCounter.MODEL_SIZES[model_label]

        try:
            new_counter = YoloCounter(model_file=model_file)
        except ImportError:
            self._busy = False
            self.yolo_load_btn.setEnabled(True)
            QMessageBox.critical(
                self, "ultralytics not installed",
                "Install it with:\n\n  pip install ultralytics\n\n"
                "Then click Load again.",
            )
            self.status_label.setText("● ultralytics missing")
            return
        except Exception as e:
            self._busy = False
            self.yolo_load_btn.setEnabled(True)
            QMessageBox.critical(self, "Model load failed", str(e))
            self.status_label.setText("● Model load failed")
            return

        self._activate_counter(new_counter)
        self._apply_classes()
        self.yolo_device_label.setText(f"Device: {new_counter.device}")

        self._busy = False
        self.yolo_load_btn.setEnabled(True)
        self.status_label.setText(f"● YOLO loaded: {model_label}")

    def _sync_counter_settings(self):
        """Push current line/direction/orientation settings to the active counter."""
        self.counter.line_position = self.pos_slider.value() / 100.0
        self.counter.orientation = self.orient_combo.currentText().lower()
        self.counter.direction = self.dir_combo.currentText().lower()
        if isinstance(self.counter, ObjectCounter):
            self.counter.min_area = self.min_spin.value()
        else:
            self.counter.conf_threshold = self.yolo_conf_slider.value() / 100.0
            self.counter.imgsz = self.yolo_imgsz_combo.currentData()
            self.counter.enhance_low_light = self.yolo_enhance_chk.isChecked()
            self.yolo_device_label.setText(f"Device: {self.counter.device}")

    def _apply_classes(self):
        if not isinstance(self.counter, YoloCounter):
            return
        indices, unknown = self.counter.resolve_class_filter(
            self.yolo_classes_edit.text()
        )
        if unknown:
            QMessageBox.warning(
                self, "Unknown classes",
                "These names/indices are not in the model:\n  "
                + ", ".join(unknown)
                + "\n\nThey were ignored.",
            )

    # ---------- Source selection ----------

    def _on_source_type_change(self, text):
        index = {SOURCE_WEBCAM: 0, SOURCE_FILE: 1, SOURCE_URL: 2}.get(text, 0)
        self.source_stack.setCurrentIndex(index)

    def _browse_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Choose a video file", "",
            "Video files (*.mp4 *.mov *.avi *.mkv *.m4v);;All files (*)",
        )
        if path:
            self.file_edit.setText(path)

    def _resolve_source(self):
        kind = self.source_type_combo.currentText()
        if kind == SOURCE_WEBCAM:
            idx = self.cam_combo.currentData()
            if idx is None or idx < 0:
                return None, "Select a valid camera first."
            return idx, None
        if kind == SOURCE_FILE:
            path = self.file_edit.text().strip()
            if not path:
                return None, "Choose a video file first."
            return path, None
        url = self.url_edit.text().strip()
        if not url:
            return None, "Enter an RTSP/HTTP URL first."
        return url, None

    def _populate_cameras(self):
        self.cam_combo.clear()
        self.status_label.setText("● Scanning…")
        cams = list_cameras()
        if not cams:
            self.cam_combo.addItem("No cameras found", -1)
            self.status_label.setText("● No cameras")
        else:
            for c in cams:
                self.cam_combo.addItem(f"Camera {c}", c)
            self.status_label.setText(f"● {len(cams)} camera(s) available")

    # ---------- Capture lifecycle ----------

    def _toggle_capture(self):
        if self.running:
            self._stop()
        else:
            self._start()

    def _start(self):
        source, err = self._resolve_source()
        if err:
            QMessageBox.warning(self, "No source", err)
            return

        self.worker = VideoWorker(source, self.counter)
        self.worker.set_infer_every(self.perf_slider.value())
        self.worker.frame_ready.connect(self._on_frame)
        self.worker.stats_ready.connect(self._on_stats)
        self.worker.counted.connect(self._on_counted)
        self.worker.error.connect(self._on_worker_error)
        self.worker.progress.connect(self._on_progress)
        self.worker.state_changed.connect(self._on_worker_state)
        self.worker.start()

        self.running = True
        self.paused = False
        self.monitor.reset()
        self.monitor.start(time())
        self.start_btn.setText("Stop")
        self.play_btn.setText("⏸ Pause")
        is_file = self.worker.kind == "file"
        self.playback_widget.setVisible(is_file)
        self.status_label.setText("● Live")
        self.status_label.setStyleSheet("color: #28a745; font-size: 12px;")

    def _stop(self):
        if self.worker is not None:
            self.worker.stop()
            self.worker = None
        self.running = False
        self.paused = False
        self.monitor.stop()
        self._clear_alert()
        self.start_btn.setText("Start")
        self.playback_widget.setVisible(False)
        self.status_label.setStyleSheet("color: #999; font-size: 12px;")
        self.status_label.setText("● Idle")

    def _toggle_pause(self):
        if self.worker is None:
            return
        self.paused = self.worker.toggle_paused()
        self.play_btn.setText("▶ Play" if self.paused else "⏸ Pause")

    def _on_seek_released(self):
        self._scrubbing = False
        if self.worker is not None:
            self.worker.seek(self.seek_slider.value())

    def _on_frame(self, frame):
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        img = QImage(rgb.data, w, h, ch * w, QImage.Format_RGB888)
        pix = QPixmap.fromImage(img).scaled(
            self.video_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        self.video_label.setPixmap(pix)

    def _on_stats(self, fps, ms, label):
        self.stats_label.setText(f"{fps:.1f} FPS · {ms:.0f} ms · {label}")

    def _on_progress(self, cur, total):
        if self._scrubbing:
            return
        self.seek_slider.setRange(0, max(0, total))
        self.seek_slider.setValue(cur)
        self.time_label.setText(f"{cur} / {total}")

    def _on_worker_state(self, state):
        if state == "reconnecting":
            self.status_label.setText("● Reconnecting…")
            self.status_label.setStyleSheet("color: #d29922; font-size: 12px;")
        elif state == "live":
            self.status_label.setText("● Live")
            self.status_label.setStyleSheet("color: #28a745; font-size: 12px;")
        elif state == "paused":
            self.status_label.setText("● Paused")
            self.status_label.setStyleSheet("color: #999; font-size: 12px;")
        elif state == "ended":
            self.status_label.setText("● Video ended")
            self._stop()

    def _on_worker_error(self, msg):
        self.status_label.setText(f"● {msg}")
        self.status_label.setStyleSheet("color: #cf222e; font-size: 12px;")
        self._stop()

    # ---------- Counter state ----------

    def _on_counted(self, classes):
        self.session_count += len(classes)
        self.storage.increment_many(classes)
        self.monitor.record(time(), len(classes))
        self._refresh_counter_displays()
        self._refresh_class_panel()

    def _refresh_counter_displays(self):
        self.total_display.setText(str(self.storage.get_total()))
        self.hour_display.setText(str(self.storage.get_current_hour_count()))
        self.session_display.setText(str(self.session_count))

    def _refresh_class_panel(self):
        breakdown = self.storage.get_class_breakdown()
        if not breakdown:
            self.class_panel.setText("No counts yet.")
            return
        self.class_panel.setText(
            "\n".join(f"{cls}:  {count}" for cls, count in breakdown)
        )

    # ---------- Periodic tick: alerts + live chart ----------

    def _on_tick(self):
        now = time()
        self.live_chart.update_data(self.monitor.per_minute(now))
        active = self.running and not self.paused
        state = self.monitor.evaluate(now, active)
        if state != self._alert_state:
            self._alert_state = state
            self._apply_alert(state)

    def _apply_alert(self, state):
        if state == "ok":
            self._clear_alert()
            return
        if state == "jam":
            self.alert_banner.setText(
                f"⚠ JAM: no objects counted for {int(self.monitor.jam_seconds)}s — belt stalled?"
            )
            self.alert_banner.setStyleSheet("background: #cf222e;")
        else:  # spike
            self.alert_banner.setText(
                f"⚠ SPIKE: throughput above {self.monitor.spike_per_min}/min — possible double-count or pile-up."
            )
            self.alert_banner.setStyleSheet("background: #bc4c00;")
        self.alert_banner.setVisible(True)
        if self.sound_chk.isChecked():
            QApplication.beep()

    def _clear_alert(self):
        self._alert_state = "ok"
        self.alert_banner.setVisible(False)

    # ---------- Counting-line handlers ----------

    def _on_line_drawn(self, x1, y1, x2, y2):
        self._custom_line = ((x1, y1), (x2, y2))
        self.counter.custom_line = self._custom_line
        self.draw_line_btn.setChecked(False)
        self.video_label.set_draw_mode(False)
        self.line_status.setText("Custom drawn line active (arbitrary angle).")
        self._save_config()

    def _toggle_draw(self, checked):
        self.video_label.set_draw_mode(checked)
        if checked:
            self.line_status.setText("Click-drag on the video to draw the line.")

    def _clear_line(self):
        self._custom_line = None
        self.counter.custom_line = None
        self.draw_line_btn.setChecked(False)
        self.video_label.set_draw_mode(False)
        self.line_status.setText("Using orientation / position slider.")
        self._save_config()

    # ---------- Setting handlers ----------

    def _update_line_position(self, v):
        self.counter.line_position = v / 100.0
        self.pos_label.setText(f"Line position: {v}%")

    def _update_orientation(self, text):
        self.counter.orientation = text.lower()

    def _update_direction(self, text):
        self.counter.direction = text.lower()

    def _update_min_area(self, v):
        if isinstance(self.counter, ObjectCounter):
            self.counter.min_area = v

    def _update_conf(self, v):
        conf = v / 100.0
        self.yolo_conf_label.setText(f"Confidence: {conf:.2f}")
        if isinstance(self.counter, YoloCounter):
            self.counter.conf_threshold = conf

    def _update_imgsz(self, _index):
        if isinstance(self.counter, YoloCounter):
            self.counter.imgsz = self.yolo_imgsz_combo.currentData()

    def _update_enhance(self, checked):
        if isinstance(self.counter, YoloCounter):
            self.counter.enhance_low_light = checked

    def _update_perf(self, n):
        self.perf_label.setText(
            "Inference: every frame (most accurate)" if n == 1
            else f"Inference: every {n} frames (smoother / faster)"
        )
        if self.worker is not None:
            self.worker.set_infer_every(n)

    # ---------- Tabs ----------

    def _on_tab_change(self, index):
        if self.tabs.widget(index) is self.history_view:
            self.history_view.refresh()

    # ---------- Actions ----------

    def _reset(self):
        dlg = ResetDialog(self)
        if dlg.exec_() != QDialog.Accepted:
            return
        spec = dlg.result_spec()
        if spec[0] == "all":
            self.counter.reset()
            self.storage.reset()
            self.session_count = 0
            self.monitor.reset()
        else:
            _, start, end = spec
            if start > end:
                start, end = end, start
            removed = self.storage.clear_range(start, end)
            QMessageBox.information(
                self, "Cleared",
                f"Removed {removed} counts between {start} and {end}.",
            )
        self._refresh_counter_displays()
        self._refresh_class_panel()
        self.history_view.refresh()

    def _export(self):
        default = f"count_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        path, selected = QFileDialog.getSaveFileName(
            self, "Save report", default,
            "Excel files (*.xlsx);;CSV files (*.csv);;JSON files (*.json)",
        )
        if not path:
            return
        lower = path.lower()
        if not lower.endswith((".xlsx", ".csv", ".json")):
            if "csv" in selected.lower():
                path += ".csv"
            elif "json" in selected.lower():
                path += ".json"
            else:
                path += ".xlsx"
            lower = path.lower()
        try:
            if lower.endswith(".csv"):
                self.storage.export_csv(path)
            elif lower.endswith(".json"):
                self.storage.export_json(path)
            else:
                self.storage.export_excel(path)
            QMessageBox.information(self, "Exported", f"Report saved to:\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Export failed", str(e))

    # ---------- Lifecycle ----------

    def closeEvent(self, event):
        self._save_config()
        self._stop()
        event.accept()
