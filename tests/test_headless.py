"""Unit tests for the Qt-free HeadlessCounter (always uses a temp DB)."""
from headless import HeadlessCounter, parse_source


def test_parse_source():
    assert parse_source("0") == 0
    assert parse_source(3) == 3
    assert parse_source("clip.mp4") == "clip.mp4"
    assert parse_source("rtsp://cam/stream") == "rtsp://cam/stream"


def test_snapshot_shape(tmp_path):
    r = HeadlessCounter(source="/tmp/does_not_exist_zzz.mp4", engine="mog",
                        db_path=str(tmp_path / "h.db"))
    snap = r.snapshot()
    assert snap["total"] == 0
    assert snap["engine"] == "mog"
    assert snap["alert"] == "ok"
    assert "class_breakdown" in snap


def test_reset(tmp_path):
    r = HeadlessCounter(source=0, engine="mog", db_path=str(tmp_path / "h.db"))
    r.storage.increment_many(["bottle", "cup"])
    assert r.snapshot()["total"] == 2
    r.reset()
    assert r.snapshot()["total"] == 0
    assert r.session_count == 0
