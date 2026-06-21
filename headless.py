"""Qt-free counting runner (Roadmap Phase 9).

Runs the exact same detection engines as the GUI, but in a plain background
thread with no PyQt dependency — proof that the core is cleanly separated from
the UI. Used by the FastAPI service (`api.py`) and runnable on its own:

    python headless.py --source 0 --engine mog
    python headless.py --source video.mp4 --engine yolo --model yolo11n.pt
"""
import argparse
import threading
import time

import cv2

from alerts import ThroughputMonitor
from detector import ObjectCounter
from storage import HourlyStorage


def parse_source(s):
    """Accept an int-like webcam index, a file path, or an RTSP/HTTP URL."""
    if isinstance(s, int):
        return s
    text = str(s)
    return int(text) if text.isdigit() else text


class HeadlessCounter:
    def __init__(self, source=0, engine="mog", model="yolo11n.pt", storage=None,
                 db_path="counts.db"):
        self.source = parse_source(source)
        self.storage = storage or HourlyStorage(db_path)
        self.monitor = ThroughputMonitor()
        self.engine_name = engine
        self.counter = self._make_counter(engine, model)

        self._thread = None
        self._running = False
        self._lock = threading.Lock()
        self.session_count = 0
        self.fps = 0.0
        self.latency_ms = 0.0
        self.state = "idle"

    @staticmethod
    def _make_counter(engine, model):
        if engine == "yolo":
            from yolo_detector import YoloCounter  # deferred (heavy import)
            return YoloCounter(model_file=model)
        return ObjectCounter()

    # ---------- lifecycle ----------

    def start(self):
        if self._running:
            return
        self._running = True
        self.monitor.reset()
        self.monitor.start(time.time())
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=2)
        self.state = "stopped"

    def reset(self):
        with self._lock:
            self.storage.reset()
            self.counter.reset()
            self.session_count = 0
            self.monitor.reset()
            if self._running:
                self.monitor.start(time.time())

    def _loop(self):
        cap = cv2.VideoCapture(self.source)
        if not cap.isOpened():
            self.state = "error: cannot open source"
            self._running = False
            return
        self.state = "running"
        misses = 0
        while self._running:
            ok, frame = cap.read()
            if not ok:
                misses += 1
                if misses > 10:
                    self.state = "ended"
                    break
                time.sleep(0.3)
                cap.release()
                cap = cv2.VideoCapture(self.source)
                continue
            misses = 0

            t0 = time.time()
            try:
                _, counted = self.counter.process(frame, True)
            except Exception as e:
                self.state = f"error: {e}"
                break
            dt = time.time() - t0

            with self._lock:
                self.fps = 1.0 / dt if dt > 0 else 0.0
                self.latency_ms = dt * 1000.0
                if counted:
                    self.session_count += len(counted)
                    self.storage.increment_many(counted)
                    self.monitor.record(time.time(), len(counted))
        cap.release()
        if self.state == "running":
            self.state = "stopped"

    # ---------- read-only view ----------

    def snapshot(self):
        with self._lock:
            now = time.time()
            return {
                "state": self.state,
                "engine": self.engine_name,
                "total": self.storage.get_total(),
                "session": self.session_count,
                "current_hour": self.storage.get_current_hour_count(),
                "fps": round(self.fps, 1),
                "latency_ms": round(self.latency_ms, 1),
                "rate_per_min": self.monitor.rate_per_min(now),
                "alert": self.monitor.evaluate(now, self._running),
                "class_breakdown": dict(self.storage.get_class_breakdown()),
            }


def main():
    ap = argparse.ArgumentParser(description="Headless CV object counter")
    ap.add_argument("--source", default="0", help="webcam index, file path, or URL")
    ap.add_argument("--engine", choices=["mog", "yolo"], default="mog")
    ap.add_argument("--model", default="yolo11n.pt", help="YOLO weights (engine=yolo)")
    ap.add_argument("--interval", type=float, default=2.0, help="status print interval (s)")
    args = ap.parse_args()

    runner = HeadlessCounter(args.source, engine=args.engine, model=args.model)
    runner.start()
    print(f"Counting from {args.source!r} with engine={args.engine}. Ctrl-C to stop.")
    try:
        while True:
            time.sleep(args.interval)
            s = runner.snapshot()
            print(f"[{s['state']}] total={s['total']} session={s['session']} "
                  f"fps={s['fps']} rate/min={s['rate_per_min']:.0f} alert={s['alert']}")
    except KeyboardInterrupt:
        pass
    finally:
        runner.stop()


if __name__ == "__main__":
    main()
