# CV Object Counter — Improvement Roadmap

Goal: take the current working app (PyQt5 + MOG2/YOLO11 conveyor counter) from a
solid prototype to a standout portfolio project that demonstrates **CV/ML depth,
software-engineering rigor, a polished demo, and real usability** — all at once.

Phases are ordered so each one builds on the last. You can stop after any phase
and still have a coherent, shippable improvement.

---

## Phase 0 — Make it a real repository (foundations) ~½ day

These cost almost nothing and change how the project is *perceived* immediately.

- [ ] `git init` + first commit of the current working state, then commit per phase.
- [ ] `.gitignore` — exclude `venv/`, `__pycache__/`, `counts.db`, `*.pt` model
      weights, exported `.xlsx` reports.
- [ ] Stop committing 5.6 MB+ of model weights. Keep `download_models.py` as the
      acquisition path; document it. (Optionally Git LFS for `best-5.pt` if it's
      a custom-trained model worth showcasing.)
- [ ] `README.md`: one-line pitch, animated GIF demo, feature list, the engine
      trade-off table (reuse the in-app hint copy), install + run, architecture
      diagram, roadmap link.
- [ ] `LICENSE` (MIT) + `CHANGELOG.md`.
- [ ] Pin dependency versions in `requirements.txt` and add a `requirements-dev.txt`
      (pytest, ruff, pyinstaller).

**Acceptance:** repo clones clean, `pip install -r requirements.txt && python main.py`
works from scratch, README renders with a demo GIF.

---

## Phase 1 — Threaded architecture (the #1 fix) ~1 day

**Problem:** `MainWindow._update_frame` (app.py:584) runs capture **and** YOLO
inference on the GUI thread via a 30 ms `QTimer`. Heavier models freeze the UI.

**Plan:**
- [ ] New `VideoWorker(QThread)`: owns the `cv2.VideoCapture`, reads frames in a
      loop, runs `counter.process()`, emits `frame_ready(np.ndarray, dict)` and
      `stats_ready(fps, latency_ms)` via Qt signals.
- [ ] UI thread only paints the pixmap and updates counters — never touches the
      camera or the model.
- [ ] Thread-safe engine swap: pause worker, swap counter, resume. Guard shared
      state with a `QMutex` or a command queue.
- [ ] Clean shutdown in `closeEvent` (stop loop, `wait()`, release capture).
- [ ] Decouple capture FPS from render FPS; drop stale frames instead of queueing.

**Acceptance:** UI stays fully responsive (drag window, move sliders) while
Medium YOLO runs. No frame-read on the GUI thread.

---

## Phase 2 — Performance instrumentation & smoothness ~½ day

- [ ] On-frame overlay: inference FPS, ms/frame, device (CPU/MPS/CUDA), active
      engine + model. You already resolve device in `best_device()`.
- [ ] Async/skip inference: run detection every Nth frame, coast tracks between
      frames so preview stays smooth on CPU. Expose N as a "Performance" slider.
- [ ] Optional: half-precision already on for GPU (yolo_detector.py:148) — surface
      it as a visible toggle so reviewers see the optimization.

**Acceptance:** FPS overlay visible; a "Performance vs Accuracy" control measurably
changes FPS.

---

## Phase 3 — Interactive ROI / counting line ~1 day  *(demo "wow")*

**Problem:** the line is slider-only (horizontal/vertical at a %). Limiting and
not impressive on camera.

**Plan:**
- [ ] Mouse-draw the counting line directly on the video (click-drag endpoints).
- [ ] Support an **arbitrary-angle** line, not just H/V — generalize
      `LineCrossingCounter` to test which side of a line segment a centroid is on
      (sign of cross product) instead of comparing a single axis.
- [ ] Optional: multiple lines and/or a polygon ROI (only count inside region).
- [ ] Persist the drawn geometry in config.

**Acceptance:** user drags a diagonal line on the feed; crossings count correctly
in the chosen direction.

---

## Phase 4 — Multi-class analytics ~1 day  *(CV depth, low cost)*

**Problem:** YOLO already knows each object's class (yolo_detector.py:182) but
everything collapses into one total.

**Plan:**
- [ ] `LineCrossingCounter` records the class of each counted ID.
- [ ] Live per-class breakdown panel ("bottle: 12, cup: 4").
- [ ] Storage schema gains a `class` column; hourly aggregation per class.
- [ ] Excel/CSV export includes the per-class breakdown.

**Acceptance:** counting mixed objects shows a correct live per-class tally that
also appears in exports.

---

## Phase 5 — Live dashboard & charts ~1 day  *(demo "wow")*

- [ ] Embed a real-time throughput chart (pyqtgraph) — counts-per-minute, last N
      minutes, optionally stacked by class.
- [ ] In-app History/Analytics tab: hourly + daily view sourced from SQLite, with
      the chart and a table.
- [ ] Export options beyond Excel: CSV and JSON.
- [ ] Make Reset non-destructive: date-range clear instead of wiping all history
      (app.py:650 currently deletes everything).

**Acceptance:** chart updates live as objects cross; History tab reflects DB.

---

## Phase 6 — Real input sources ~1 day  *(usability)*

- [ ] Video **file** input with a scrub/seek bar and play/pause (great for repeatable
      demos without hardware).
- [ ] **RTSP / IP camera** URL input (with reconnect-on-drop).
- [ ] Source picker unifies: webcam index / file / RTSP.

**Acceptance:** can count from a recorded `.mp4` and from an RTSP stream; stream
auto-reconnects after a drop.

---

## Phase 7 — Alerts & robustness ~½ day  *(usability / "smart" feel)*

- [ ] Throughput anomaly alerts: flag belt **jam** (throughput → 0 for X seconds)
      or unusual spikes, using existing hourly/event data.
- [ ] Optional desktop notification / sound on threshold breach.
- [ ] Graceful handling of camera disconnect mid-run (already partially handled at
      app.py:588 — make it recover, not just stop).

**Acceptance:** simulate a stall → app raises a visible jam alert.

---

## Phase 8 — Engineering rigor / CI ~1 day  *(SWE credibility)*

- [ ] Unit tests for the pure logic — `LineCrossingCounter` (crossing, direction,
      span-touch, count-once) and `CentroidTracker` (register/match/deregister).
      Both are dependency-free and ideal to test.
- [ ] `ruff` + `black` config; type hints across modules (you're ~80% there).
- [ ] GitHub Actions: lint + test on push; status badge in README.
- [ ] PyInstaller spec → double-clickable `.app`/`.exe` artifact; document the build.

**Acceptance:** `pytest` green locally and in CI; a built binary launches.

---

## Phase 9 — Stretch / differentiators (pick 1–2)

- [ ] **Headless mode + REST/WebSocket API** (FastAPI): run the counter without the
      GUI and expose live counts — shows you can separate core from UI.
- [ ] **Model evaluation harness**: run a labeled clip, report counting accuracy
      (precision/recall vs ground truth) — strong CV-engineer signal.
- [ ] **Custom model story**: document how `best-5.pt` was trained (dataset, classes,
      mAP) — turns "I used YOLO" into "I trained and deployed a model."
- [ ] **Dockerfile** for the headless service.
- [ ] **Speed/size benchmark table** across nano/small/medium × imgsz in the README.

---

## Suggested order if doing it all

`Phase 0 → 1 → 8 (tests early) → 4 → 3 → 5 → 2 → 6 → 7 → 9`

Rationale: foundations and the threading fix unblock everything; tests early keep
the refactors safe; multi-class + ROI + dashboard are the highest visible payoff
per hour; input sources / alerts / stretch round it out.

---

## Quick wins worth doing regardless (each < 30 min)

- Settings persistence (config.json) so the app remembers your last setup.
- FPS overlay (subset of Phase 2).
- `.gitignore` + README + git history (Phase 0).
- One screen-recorded GIF for the README.
