"""Headless REST + WebSocket service (Roadmap Phase 9).

Exposes the counting core over HTTP without the GUI — demonstrating that the
detection engine is fully decoupled from PyQt. Configure via environment:

    CVCOUNTER_SOURCE   webcam index / file path / RTSP URL   (default "0")
    CVCOUNTER_ENGINE   "mog" | "yolo"                        (default "mog")
    CVCOUNTER_MODEL    YOLO weights when engine=yolo          (default yolo11n.pt)

Run:

    pip install -r requirements-api.txt
    uvicorn api:app --host 0.0.0.0 --port 8000
    # or: python api.py

Endpoints:
    GET  /health   liveness + runner state
    GET  /counts   full snapshot (total, session, per-class, fps, alert)
    POST /reset    wipe counts and restart the tally
    WS   /ws       stream the snapshot once per second
"""
import asyncio
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from headless import HeadlessCounter

SOURCE = os.environ.get("CVCOUNTER_SOURCE", "0")
ENGINE = os.environ.get("CVCOUNTER_ENGINE", "mog")
MODEL = os.environ.get("CVCOUNTER_MODEL", "yolo11n.pt")

runner = HeadlessCounter(SOURCE, engine=ENGINE, model=MODEL)


@asynccontextmanager
async def lifespan(app: FastAPI):
    runner.start()
    try:
        yield
    finally:
        runner.stop()


app = FastAPI(title="CV Object Counter API", version="1.0", lifespan=lifespan)


@app.get("/health")
def health():
    return {"status": "ok", "state": runner.state}


@app.get("/counts")
def counts():
    return runner.snapshot()


@app.post("/reset")
def reset():
    runner.reset()
    return {"status": "reset"}


@app.websocket("/ws")
async def ws(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            await websocket.send_json(runner.snapshot())
            await asyncio.sleep(1.0)
    except WebSocketDisconnect:
        pass


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
