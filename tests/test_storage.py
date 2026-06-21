"""Unit tests for HourlyStorage per-class aggregation and clearing."""
import os
import tempfile

import pytest

from storage import HourlyStorage


@pytest.fixture
def store():
    path = os.path.join(tempfile.mkdtemp(), "t.db")
    yield HourlyStorage(path)


def test_increment_and_total(store):
    store.increment_many(["bottle", "bottle", "cup"])
    assert store.get_total() == 3
    assert dict(store.get_class_breakdown()) == {"bottle": 2, "cup": 1}


def test_current_hour_breakdown(store):
    store.increment("box")
    assert dict(store.get_current_hour_class_breakdown()) == {"box": 1}


def test_reset_is_destructive(store):
    store.increment_many(["a", "b"])
    store.reset()
    assert store.get_total() == 0
    assert store.get_class_breakdown() == []


def test_clear_range_removes_only_matching(store):
    # write directly into two different days
    with store._connect() as c:
        c.execute("INSERT INTO hourly_counts VALUES ('2026-01-01 10:00', 5)")
        c.execute("INSERT INTO hourly_counts VALUES ('2026-02-01 10:00', 7)")
        c.execute("INSERT INTO class_hourly VALUES ('2026-01-01 10:00', 'x', 5)")
    removed = store.clear_range("2026-01-01", "2026-01-31")
    assert removed == 5
    assert store.get_total() == 7  # February survives


def test_exports_write_files(store):
    store.increment_many(["bottle", "cup"])
    base = tempfile.mkdtemp()
    xlsx, csv_p, json_p = (os.path.join(base, f"r.{ext}")
                           for ext in ("xlsx", "csv", "json"))
    store.export_excel(xlsx)
    store.export_csv(csv_p)
    store.export_json(json_p)
    assert all(os.path.getsize(p) > 0 for p in (xlsx, csv_p, json_p))


def test_json_export_structure(store):
    import json
    store.increment_many(["bottle", "bottle"])
    path = os.path.join(tempfile.mkdtemp(), "r.json")
    store.export_json(path)
    with open(path) as f:
        report = json.load(f)
    assert report["total"] == 2
    assert {"class": "bottle", "count": 2} in report["class_totals"]
