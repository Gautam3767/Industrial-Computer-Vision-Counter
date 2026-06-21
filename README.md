# CV Object Counter

[![CI](https://github.com/Gautam3767/Industrial-Computer-Vision-Couter/actions/workflows/ci.yml/badge.svg)](https://github.com/Gautam3767/Industrial-Computer-Vision-Couter/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/)

> Real-time conveyor-belt object counter — a PyQt5 desktop app with two
> interchangeable detection engines (motion-based MOG2 and YOLO11 + ByteTrack),
> an interactive counting line, per-class analytics, live charts, alerts, and a
> headless REST/WebSocket service.

![Demo](docs/demo.gif)

<!-- Record a ~10s screen capture of the app counting objects crossing the line
     and save it to docs/demo.gif. (e.g. macOS: QuickTime screen recording →
     convert with `ffmpeg -i demo.mov -vf "fps=12,scale=900:-1" docs/demo.gif`) -->

## Features

- **Two detection engines, swappable at runtime**
  - *Motion (MOG2)* — fast, dependency-light, class-agnostic background
    subtraction with centroid tracking.
  - *YOLO11 + ByteTrack* — class-aware detection with persistent track IDs,
    robust to occlusion and crossings.
- **Threaded architecture** — capture and inference run on a background
  `QThread`, so the UI never freezes (Phase 1).
- **Performance instrumentation** — on-frame FPS / ms-per-frame / device
  overlay and a *Performance vs Accuracy* slider that skips inference on
  intermediate frames and coasts the preview (Phase 2).
- **Interactive counting line** — drag an **arbitrary-angle** line directly on
  the video; crossings are detected with a cross-product side test and counted
  in a chosen direction. Geometry persists in `config.json` (Phase 3).
- **Per-class analytics** — live per-class breakdown panel, per-class SQLite
  history, and per-class breakdown in exports (Phase 4).
- **Live charts & History tab** — real-time counts-per-minute throughput chart
  (pyqtgraph) and an in-app History/Analytics tab (hourly chart + hourly/daily/
  per-class tables) sourced from SQLite. Export to Excel, CSV **or JSON**;
  non-destructive date-range clearing (Phase 5).
- **Real input sources** — webcam, **video file** (with play/pause + scrub bar),
  or **RTSP/HTTP stream** (auto-reconnect on drop) via a unified source picker
  (Phase 6).
- **Alerts & robustness** — belt-**jam** alert (throughput → 0) and **spike**
  alert, with an on-screen banner and optional beep; webcam/stream reconnect
  (Phase 7).
- **Engineering rigor** — pure-logic unit tests (`pytest`), `ruff` linting,
  GitHub Actions CI, and a PyInstaller spec for a double-clickable binary
  (Phase 8).
- **Headless service** — run the counter without the GUI and expose live counts
  over REST + WebSocket (FastAPI), with a Dockerfile (Phase 9).

## Engine trade-offs

| | Motion (MOG2) | YOLO11 + ByteTrack |
|---|---|---|
| Speed | Very fast (CPU) | Depends on model/device |
| Dependencies | OpenCV only | `ultralytics` + torch |
| Class-aware | No (single "object" class) | Yes (per-class tally) |
| Robust to occlusion / crossings | No | Yes |
| Best for | Steady lighting, distinct objects | Mixed objects, harder scenes |
| Lighting sensitivity | Needs steady lighting | CLAHE low-light boost available |

### YOLO11 model sizes (rough guide)

Indicative trade-offs across the bundled model sizes; measure on your hardware
with the on-screen FPS overlay (device-dependent — CPU vs MPS vs CUDA).

| Model | Params | Relative speed | Relative accuracy | Use when |
|---|---|---|---|---|
| `yolo11n` (Nano) | ~2.6 M | ★★★★★ | ★★ | CPU / real-time preview |
| `yolo11s` (Small) | ~9.4 M | ★★★★ | ★★★ | balanced |
| `yolo11m` (Medium) | ~20 M | ★★ | ★★★★ | GPU / accuracy-critical |
| `best-5` (Custom) | depends | — | domain-tuned | your trained line |

See [docs/custom-model.md](docs/custom-model.md) for training and deploying the
custom model.

## Install & run

Requires **Python 3.9+**.

```bash
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Optional: pre-download YOLO weights into ./models so the app never
# re-downloads at runtime (needs the optional `ultralytics` dependency).
python download_models.py

python main.py
```

The MOG2 engine works with just the core requirements; the YOLO engine needs
`ultralytics` (already in `requirements.txt`). Model weights (`*.pt`) are **not**
committed — `download_models.py` is the acquisition path.

## Usage

1. Pick a **Source** (webcam / video file / RTSP URL) and press **Start**.
2. Choose a detection engine. For YOLO, pick a model size and press
   **Load / Reload Model**.
3. Set the counting line — use the **Orientation / position** controls, or click
   **Draw line** and drag an arbitrary-angle segment on the video.
4. Counts accumulate live. The per-class panel and live throughput chart update
   in real time; the **History** tab shows hourly/daily/per-class analytics.
5. **Export** writes an Excel / CSV / JSON report. **Clear…** lets you wipe a
   date range (non-destructive) or all history.

## Headless API (no GUI)

```bash
pip install -r requirements-api.txt
CVCOUNTER_SOURCE=0 CVCOUNTER_ENGINE=mog uvicorn api:app --port 8000
# or one-shot from a video file:
python headless.py --source clip.mp4 --engine yolo --model yolo11n.pt
```

| Endpoint | Description |
|---|---|
| `GET /health` | liveness + runner state |
| `GET /counts` | full snapshot (total, session, per-class, fps, alert) |
| `POST /reset` | wipe counts and restart the tally |
| `WS /ws` | stream the snapshot once per second |

### Docker

```bash
docker build -t cv-counter-api .
docker run -p 8000:8000 -e CVCOUNTER_SOURCE="rtsp://cam/stream" cv-counter-api
```

## Development

```bash
pip install -r requirements-dev.txt
pytest          # unit tests for the pure logic (counting, tracking, alerts)
ruff check .    # lint
pyinstaller CVObjectCounter.spec   # build a double-clickable binary
```

## Architecture

```
main.py ── QApplication entry point
  └─ app.py ── MainWindow (UI only: Live tab + History tab)
       ├─ video_worker.py ── VideoWorker(QThread): owns the source (webcam/file/
       │                       stream), runs the active counter off the GUI
       │                       thread, pause/seek/reconnect, emits frames+stats
       ├─ video_view.py ──── VideoView(QLabel): displays frames, mouse-drawn line
       ├─ live_chart.py ──── LiveThroughputChart (pyqtgraph)
       ├─ history_view.py ── HistoryView: SQLite-backed analytics tab
       ├─ detector.py ────── ObjectCounter (MOG2) + CentroidTracker
       ├─ yolo_detector.py ─ YoloCounter (YOLO11 + ByteTrack)
       ├─ counting_line.py ─ LineCrossingCounter (axis + arbitrary-segment,
       │                       per-class tally) — pure, dependency-free logic
       ├─ alerts.py ──────── ThroughputMonitor (jam/spike, per-minute) — pure
       ├─ storage.py ─────── HourlyStorage (SQLite + Excel/CSV/JSON export)
       └─ config.py ──────── load/save config.json (drawn line, last options)

headless.py ── HeadlessCounter: Qt-free runner (same engines, plain thread)
  └─ api.py ── FastAPI REST + WebSocket service  ── Dockerfile
```

The detection engines share a small interface (`process(frame, run_inference)`
returning an annotated frame plus the list of classes counted this tick), which
is what makes them hot-swappable behind both the GUI worker and the headless
runner.

## Roadmap

See [ROADMAP.md](ROADMAP.md) for the full plan. Phases 0–9 are implemented.

## License

[MIT](LICENSE).
