"""Tiny JSON-backed settings store.

Remembers the last-used options (engine, counting-line geometry, direction,
performance level) across runs. Best-effort: any read/write error is swallowed
so a missing or corrupt file never blocks the app.
"""
import json
from pathlib import Path

CONFIG_PATH = Path(__file__).parent / "config.json"


def load_config():
    try:
        return json.loads(CONFIG_PATH.read_text())
    except Exception:
        return {}


def save_config(data):
    try:
        CONFIG_PATH.write_text(json.dumps(data, indent=2))
    except Exception:
        pass
