"""Background capture + inference thread (Roadmap Phases 1, 6, 7).

`VideoWorker` owns the `cv2.VideoCapture` and runs the active counter's
`process()` off the GUI thread, so heavy inference (e.g. Medium YOLO) never
freezes the UI. It supports three source kinds — webcam index, video file, and
RTSP/HTTP stream — with pause/seek for files and automatic reconnect-on-drop for
webcams and streams. The UI thread only paints the frames it emits.
"""
from time import perf_counter

import cv2
import numpy as np
from PyQt5.QtCore import QMutex, QMutexLocker, QThread, pyqtSignal

_STREAM_PREFIXES = ("rtsp://", "rtmp://", "http://", "https://")


class VideoWorker(QThread):
    # Annotated BGR frame ready to display.
    frame_ready = pyqtSignal(np.ndarray)
    # inference FPS, ms/frame, overlay label (e.g. "yolo11n · MPS").
    stats_ready = pyqtSignal(float, float, str)
    # Class names counted since the last emit (drives storage + per-class panel).
    counted = pyqtSignal(list)
    # Fatal error message; the loop has stopped.
    error = pyqtSignal(str)
    # current_frame, total_frames — for the file scrub bar (0, 0 if not a file).
    progress = pyqtSignal(int, int)
    # "live" | "reconnecting" | "paused" | "ended"
    state_changed = pyqtSignal(str)

    def __init__(self, source, counter, parent=None, max_reconnect=5):
        super().__init__(parent)
        self._source = source
        self._kind = self._classify(source)
        self._counter = counter
        self._mutex = QMutex()
        self._running = False
        self._paused = False
        self._loop = True            # loop video files at EOF
        self._seek_to = None         # pending seek (frame index) for files
        self._max_reconnect = max_reconnect
        self._cap = None
        # Phase 2: run detection every Nth frame, coast the preview between.
        self.infer_every = 1
        self._frame_idx = 0
        # Exponential moving average of FPS for a steady on-screen number.
        self._ema_fps = None

    @property
    def kind(self):
        return self._kind

    @staticmethod
    def _classify(source):
        if isinstance(source, int):
            return "webcam"
        if str(source).lower().startswith(_STREAM_PREFIXES):
            return "stream"
        return "file"

    # ---------- controls (called from the GUI thread) ----------

    def set_counter(self, counter):
        """Hot-swap the detection engine without stopping capture (thread-safe)."""
        with QMutexLocker(self._mutex):
            self._counter = counter
            self._frame_idx = 0

    def set_infer_every(self, n):
        with QMutexLocker(self._mutex):
            self.infer_every = max(1, int(n))

    def set_paused(self, paused):
        with QMutexLocker(self._mutex):
            self._paused = bool(paused)

    def toggle_paused(self):
        with QMutexLocker(self._mutex):
            self._paused = not self._paused
            return self._paused

    def seek(self, frame_index):
        with QMutexLocker(self._mutex):
            self._seek_to = max(0, int(frame_index))

    # ---------- capture loop ----------

    def _open(self):
        cap = cv2.VideoCapture(self._source)
        if self._kind == "webcam":
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        if self._kind != "file":
            # Keep the grab buffer shallow so we process the freshest frame.
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        return cap

    def run(self):
        self._cap = self._open()
        if not self._cap.isOpened():
            self.error.emit(f"Could not open source: {self._source}")
            return

        total = int(self._cap.get(cv2.CAP_PROP_FRAME_COUNT)) if self._kind == "file" else 0
        self._running = True
        self.state_changed.emit("live")
        was_paused = False

        while self._running:
            with QMutexLocker(self._mutex):
                paused = self._paused
                seek_to = self._seek_to
                self._seek_to = None

            if seek_to is not None and self._kind == "file":
                self._cap.set(cv2.CAP_PROP_POS_FRAMES, seek_to)

            if paused:
                if not was_paused:
                    self.state_changed.emit("paused")
                    was_paused = True
                self.msleep(30)
                continue
            if was_paused:
                self.state_changed.emit("live")
                was_paused = False

            ok, frame = self._cap.read()
            if not ok:
                if self._kind == "file":
                    if self._loop and total > 0:
                        self._cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                        continue
                    self.state_changed.emit("ended")
                    break
                # webcam / stream dropped — try to recover instead of dying.
                if not self._reconnect():
                    break
                continue

            with QMutexLocker(self._mutex):
                counter = self._counter
                infer_every = self.infer_every
                run_inference = (self._frame_idx % infer_every == 0)
                self._frame_idx += 1

            t0 = perf_counter()
            try:
                processed, counted = counter.process(frame, run_inference)
            except Exception as e:  # never let a bad frame kill the thread
                self.error.emit(str(e))
                break
            dt = perf_counter() - t0

            fps = 1.0 / dt if dt > 0 else 0.0
            self._ema_fps = fps if self._ema_fps is None else (
                0.85 * self._ema_fps + 0.15 * fps
            )

            self._draw_overlay(processed, self._ema_fps, dt * 1000.0,
                               counter.overlay_label, run_inference)

            self.frame_ready.emit(processed)
            self.stats_ready.emit(self._ema_fps, dt * 1000.0, counter.overlay_label)
            if counted:
                self.counted.emit(list(counted))
            if self._kind == "file" and total > 0:
                cur = int(self._cap.get(cv2.CAP_PROP_POS_FRAMES))
                self.progress.emit(cur, total)

        if self._cap is not None:
            self._cap.release()

    def _reconnect(self):
        """Try to reopen a dropped webcam/stream with linear backoff."""
        self.state_changed.emit("reconnecting")
        if self._cap is not None:
            self._cap.release()
        for _ in range(self._max_reconnect):
            if not self._running:
                return False
            self.msleep(800)
            cap = self._open()
            if cap.isOpened():
                ok, _ = cap.read()
                if ok:
                    self._cap = cap
                    self.state_changed.emit("live")
                    return True
            cap.release()
        self.error.emit(
            f"Lost source and could not reconnect after {self._max_reconnect} attempts."
        )
        return False

    @staticmethod
    def _draw_overlay(img, fps, ms, label, run_inference):
        h, w = img.shape[:2]
        tag = "" if run_inference else "  (coast)"
        lines = [f"{fps:4.1f} FPS   {ms:5.1f} ms{tag}", label]
        font = cv2.FONT_HERSHEY_SIMPLEX
        y = 24
        for text in lines:
            (tw, th), _ = cv2.getTextSize(text, font, 0.55, 1)
            x = w - tw - 16
            cv2.rectangle(img, (x - 6, y - th - 4), (x + tw + 6, y + 6),
                          (0, 0, 0), -1)
            cv2.putText(img, text, (x, y), font, 0.55, (0, 255, 180), 1,
                        cv2.LINE_AA)
            y += th + 12

    def stop(self):
        self._running = False
        self.wait()
