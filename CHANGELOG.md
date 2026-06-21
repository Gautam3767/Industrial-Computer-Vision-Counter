# Changelog

All notable changes to this project are documented here. The format loosely
follows [Keep a Changelog](https://keepachangelog.com/); the project is
pre-1.0, so the API is not yet considered stable.

## [Unreleased]

### Added
- **Repository foundations** (Roadmap Phase 0): `.gitignore`, MIT `LICENSE`,
  this changelog, pinned `requirements.txt` + a `requirements-dev.txt`, and a
  proper `README` with the engine trade-off table and architecture notes.
- **Threaded architecture** (Phase 1): a `VideoWorker(QThread)` now owns the
  camera and runs detection/inference off the GUI thread. The UI only paints
  frames and updates counters, so it stays responsive even with the Medium YOLO
  model. Engine swaps are mutex-guarded; the worker shuts down cleanly.
- **Performance instrumentation** (Phase 2): on-frame overlay showing inference
  FPS, ms/frame, device (CPU/MPS/CUDA) and the active engine, plus a
  "Performance vs Accuracy" slider that runs detection every Nth frame and
  coasts the preview in between.
- **Interactive counting line** (Phase 3): draw an arbitrary-angle line directly
  on the video by click-dragging. Crossings are detected with a cross-product
  side test, so diagonal lines count correctly in the chosen direction. The
  drawn geometry persists across runs in `config.json`.
- **Per-class analytics** (Phase 4): the counter records each crossing object's
  class. A live per-class breakdown panel shows the tally; the SQLite schema and
  Excel/CSV exports now include a per-class breakdown.
- **Live charts & History tab** (Phase 5): a real-time counts-per-minute
  throughput chart (pyqtgraph) and an in-app History/Analytics tab with an
  hourly chart and hourly/daily/per-class tables. Added JSON export and a
  non-destructive date-range clear (alongside the existing wipe-all reset).
- **Real input sources** (Phase 6): unified source picker for webcam, video file
  (with play/pause and a scrub bar), and RTSP/HTTP streams.
- **Alerts & robustness** (Phase 7): belt-jam and spike anomaly alerts with an
  on-screen banner and optional beep; automatic reconnect for dropped
  webcams/streams.
- **Engineering rigor** (Phase 8): `pytest` unit tests for the pure logic
  (`LineCrossingCounter`, `CentroidTracker`, `ThroughputMonitor`, storage),
  `ruff`/`black` config, a GitHub Actions CI workflow, and a PyInstaller spec.
- **Headless service** (Phase 9): a Qt-free `HeadlessCounter` plus a FastAPI
  REST + WebSocket service (`api.py`) and a Dockerfile, demonstrating the core
  is decoupled from the UI. Added a custom-model writeup (`docs/custom-model.md`).
