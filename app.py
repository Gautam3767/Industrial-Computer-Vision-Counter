from datetime import datetime

import cv2
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QFileDialog, QFrame, QGroupBox,
    QHBoxLayout, QLabel, QLineEdit, QMainWindow, QMessageBox, QPushButton,
    QScrollArea, QSizePolicy, QSlider, QSpinBox, QVBoxLayout, QWidget,
)

from detector import ObjectCounter
from storage import HourlyStorage
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


STYLE = """
QMainWindow, QWidget#central { background: #f4f5f7; }
QLabel { color: #1c1e21; font-size: 13px; }

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

QComboBox, QSpinBox, QLineEdit {
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
"""


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("CV Object Counter")
        self.resize(1380, 820)

        self.storage = HourlyStorage()
        self.counter = ObjectCounter()
        self.counter.on_count = self._on_count

        self.cap = None
        self.running = False
        self.session_count = 0
        self._busy = False

        self.timer = QTimer()
        self.timer.timeout.connect(self._update_frame)

        self._build_ui()
        self.setStyleSheet(STYLE)
        self._refresh_counter_displays()
        self._apply_engine_visibility()

    # ---------- UI construction ----------

    def _build_ui(self):
        central = QWidget()
        central.setObjectName("central")
        self.setCentralWidget(central)

        root = QHBoxLayout(central)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(16)

        root.addWidget(self._build_video_panel(), 3)
        root.addWidget(self._build_controls_panel(), 0)

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

        self.video_label = QLabel("Select a camera and press Start")
        self.video_label.setAlignment(Qt.AlignCenter)
        self.video_label.setMinimumSize(720, 540)
        self.video_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.video_label.setStyleSheet(
            "background: #0a0a0a; color: #777; border-radius: 10px; font-size: 13px;"
        )
        layout.addWidget(self.video_label, 1)

        return container

    def _build_controls_panel(self):
        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.setSpacing(14)
        layout.setContentsMargins(0, 0, 10, 0)  # room for scrollbar

        layout.addWidget(self._build_counter_display())
        layout.addWidget(self._build_camera_group())
        layout.addWidget(self._build_engine_group())
        layout.addWidget(self._build_yolo_group())
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

    def _build_camera_group(self):
        group = QGroupBox("CAMERA")
        v = QVBoxLayout(group)
        v.setSpacing(8)

        row = QHBoxLayout()
        self.cam_combo = QComboBox()
        self.refresh_btn = QPushButton("⟳")
        self.refresh_btn.setFixedWidth(36)
        self.refresh_btn.setToolTip("Rescan cameras")
        self.refresh_btn.clicked.connect(self._populate_cameras)
        row.addWidget(self.cam_combo, 1)
        row.addWidget(self.refresh_btn)
        v.addLayout(row)

        self.start_btn = QPushButton("Start Camera")
        self.start_btn.setObjectName("primaryBtn")
        self.start_btn.clicked.connect(self._toggle_camera)
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

    def _build_line_group(self):
        group = QGroupBox("COUNTING LINE")
        v = QVBoxLayout(group)
        v.setSpacing(10)

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

        self.reset_btn = QPushButton("Reset")
        self.reset_btn.setObjectName("dangerBtn")
        self.reset_btn.clicked.connect(self._reset)
        row.addWidget(self.reset_btn)

        self.export_btn = QPushButton("Export Excel")
        self.export_btn.setObjectName("primaryBtn")
        self.export_btn.clicked.connect(self._export)
        row.addWidget(self.export_btn)
        return row

    # ---------- Engine swap ----------

    def _on_engine_change(self, engine):
        self._apply_engine_visibility()
        if engine == ENGINE_MOG:
            self._stop()
            self.counter = ObjectCounter()
            self.counter.on_count = self._on_count
            self._sync_counter_settings()
            self.engine_hint.setText(
                "Motion: fast, class-agnostic, needs steady lighting."
            )
            self.status_label.setText("● Engine: MOG2")
        else:
            self.engine_hint.setText(
                "YOLO11: class-aware, robust to occlusion. Click 'Load' to initialize."
            )
            self.status_label.setText("● YOLO not loaded — click Load")
            # Keep existing MOG2 counter until user loads YOLO
            self._stop()
            self.start_btn.setEnabled(False)

    def _apply_engine_visibility(self):
        is_yolo = self.engine_combo.currentText() == ENGINE_YOLO
        self.yolo_group.setVisible(is_yolo)
        self.min_row_widget.setVisible(not is_yolo)

    def _load_yolo(self):
        if self._busy:
            return
        self._busy = True
        self.yolo_load_btn.setEnabled(False)
        self.start_btn.setEnabled(False)
        self.status_label.setText("● Loading YOLO model…")
        QApplication.processEvents()

        model_label = self.yolo_model_combo.currentText()
        model_file = YoloCounter.MODEL_SIZES[model_label]

        self._stop()
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

        self.counter = new_counter
        self.counter.on_count = self._on_count
        self._sync_counter_settings()
        self._apply_classes()

        self._busy = False
        self.yolo_load_btn.setEnabled(True)
        self.start_btn.setEnabled(True)
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

    # ---------- Camera / frame loop ----------

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

    def _toggle_camera(self):
        if self.running:
            self._stop()
        else:
            self._start()

    def _start(self):
        idx = self.cam_combo.currentData()
        if idx is None or idx < 0:
            QMessageBox.warning(self, "No camera", "Select a valid camera first.")
            return
        self.cap = cv2.VideoCapture(idx)
        if not self.cap.isOpened():
            QMessageBox.critical(self, "Error", f"Could not open camera {idx}.")
            self.cap = None
            return
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

        self.running = True
        self.start_btn.setText("Stop Camera")
        self.status_label.setText(f"● Live — Camera {idx}")
        self.status_label.setStyleSheet("color: #28a745; font-size: 12px;")
        self.timer.start(30)

    def _stop(self):
        self.timer.stop()
        if self.cap is not None:
            self.cap.release()
            self.cap = None
        self.running = False
        self.start_btn.setText("Start Camera")
        self.status_label.setStyleSheet("color: #999; font-size: 12px;")

    def _update_frame(self):
        if self.cap is None:
            return
        ok, frame = self.cap.read()
        if not ok:
            self.status_label.setText("● Frame read failed")
            return
        try:
            processed, _ = self.counter.process(frame)
        except Exception as e:
            self.status_label.setText(f"● Error: {e}")
            self._stop()
            return

        rgb = cv2.cvtColor(processed, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        img = QImage(rgb.data, w, h, ch * w, QImage.Format_RGB888)
        pix = QPixmap.fromImage(img).scaled(
            self.video_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        self.video_label.setPixmap(pix)

    # ---------- Counter state ----------

    def _on_count(self):
        self.session_count += 1
        self.storage.increment(1)
        self._refresh_counter_displays()

    def _refresh_counter_displays(self):
        self.total_display.setText(str(self.storage.get_total()))
        self.hour_display.setText(str(self.storage.get_current_hour_count()))
        self.session_display.setText(str(self.session_count))

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

    # ---------- Actions ----------

    def _reset(self):
        reply = QMessageBox.question(
            self, "Reset counts",
            "Clear the session counter and all hourly history?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        self.counter.reset()
        self.storage.reset()
        self.session_count = 0
        self._refresh_counter_displays()

    def _export(self):
        default = f"count_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Excel report", default, "Excel files (*.xlsx)"
        )
        if not path:
            return
        if not path.lower().endswith(".xlsx"):
            path += ".xlsx"
        try:
            self.storage.export_excel(path)
            QMessageBox.information(
                self, "Exported", f"Hourly report saved to:\n{path}"
            )
        except Exception as e:
            QMessageBox.critical(self, "Export failed", str(e))

    # ---------- Lifecycle ----------

    def closeEvent(self, event):
        self._stop()
        event.accept()
