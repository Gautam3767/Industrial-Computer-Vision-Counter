"""Unit tests for ThroughputMonitor jam/spike detection."""
from alerts import ThroughputMonitor


def test_no_alert_when_inactive():
    m = ThroughputMonitor(jam_seconds=5)
    assert m.evaluate(now=100.0, active=False) == "ok"


def test_jam_after_idle_period():
    m = ThroughputMonitor(jam_seconds=5)
    m.start(0.0)
    m.record(1.0)               # produced a count early on
    assert m.evaluate(3.0, active=True) == "ok"     # still within grace
    assert m.evaluate(7.0, active=True) == "jam"     # idle >= 5s while running


def test_jam_clears_after_new_count():
    m = ThroughputMonitor(jam_seconds=5)
    m.start(0.0)
    m.record(1.0)
    assert m.evaluate(7.0, active=True) == "jam"
    m.record(7.5)
    assert m.evaluate(8.0, active=True) == "ok"


def test_no_jam_before_running_long_enough():
    m = ThroughputMonitor(jam_seconds=5)
    m.start(100.0)              # just started, no counts yet
    assert m.evaluate(103.0, active=True) == "ok"


def test_spike_detection():
    m = ThroughputMonitor(spike_per_min=10)
    m.start(0.0)
    for i in range(11):        # 11 counts within the last 60s
        m.record(0.5 + i * 0.1)
    assert m.evaluate(5.0, active=True) == "spike"


def test_per_minute_buckets():
    m = ThroughputMonitor()
    now = 600.0
    m.record(now - 5)          # current minute
    m.record(now - 65)         # one minute ago
    m.record(now - 70)         # one minute ago
    pm = m.per_minute(now, minutes=3)
    # last element is the current minute (offset 0)
    assert pm[-1] == (0, 1)
    assert pm[-2] == (-1, 2)


def test_reset_clears_events():
    m = ThroughputMonitor()
    m.start(0.0)
    m.record(1.0)
    m.reset()
    assert list(m.events) == []
    assert m.last_count_at is None
    assert m.evaluate(100.0, active=True) == "ok"
