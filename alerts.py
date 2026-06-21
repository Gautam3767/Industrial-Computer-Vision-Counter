"""Throughput monitoring and anomaly detection (Roadmap Phase 7).

Pure, dependency-free logic so it is trivially unit-testable. The caller feeds
in count events with timestamps and periodically asks ``evaluate(now, active)``
for the current alert state. Also doubles as the data source for the live
counts-per-minute chart (Phase 5) via :meth:`per_minute`.
"""
import math
from collections import deque


class ThroughputMonitor:
    """Tracks recent count events and flags belt jams or unusual spikes.

    * **Jam** — the line was running and producing counts, then throughput drops
      to zero for ``jam_seconds`` while still active (a stall / blockage).
    * **Spike** — counts in the last 60 s exceed ``spike_per_min`` (a burst that
      may indicate double-counting or a pile-up).
    """

    def __init__(self, jam_seconds=10.0, spike_per_min=120, window_seconds=900):
        self.jam_seconds = jam_seconds
        self.spike_per_min = spike_per_min
        self.window_seconds = window_seconds
        self.events = deque()           # timestamps (float seconds)
        self.last_count_at = None
        self.active_since = None
        self._state = "ok"              # "ok" | "jam" | "spike"

    def reset(self):
        self.events.clear()
        self.last_count_at = None
        self.active_since = None
        self._state = "ok"

    def start(self, now):
        """Mark the line as active (capture started/resumed)."""
        self.active_since = now

    def stop(self):
        self.active_since = None
        self._state = "ok"

    def record(self, now, n=1):
        for _ in range(n):
            self.events.append(now)
        self.last_count_at = now
        self._prune(now)

    def _prune(self, now):
        cutoff = now - self.window_seconds
        while self.events and self.events[0] < cutoff:
            self.events.popleft()

    def counts_in_window(self, now, window):
        cutoff = now - window
        return sum(1 for t in self.events if t >= cutoff)

    def per_minute(self, now, minutes=15):
        """Counts-per-minute for the last ``minutes`` whole minutes.

        Returns a list of (minute_offset, count) where minute_offset is the
        number of minutes ago (0 = current minute, negative going back), so it
        plots left-to-right as time advances.
        """
        buckets = [0] * minutes
        for t in self.events:
            ago = now - t
            idx = int(ago // 60)
            if 0 <= idx < minutes:
                buckets[idx] += 1
        # Reverse so index 0 is the oldest minute on the left of the chart.
        offsets = list(range(-(minutes - 1), 1))
        return list(zip(offsets, list(reversed(buckets))))

    def evaluate(self, now, active):
        """Return the current alert state: "ok", "jam", or "spike".

        ``active`` is whether capture is currently running (and not paused).
        """
        if not active:
            self._state = "ok"
            return self._state

        # Spike takes priority — it's an immediate, current-window signal.
        if self.spike_per_min and self.counts_in_window(now, 60) > self.spike_per_min:
            self._state = "spike"
            return self._state

        # Jam: we were producing counts, but nothing for jam_seconds.
        if self.last_count_at is not None:
            idle = now - self.last_count_at
            running_for = (now - self.active_since
                           if self.active_since is not None else 0.0)
            if idle >= self.jam_seconds and running_for >= self.jam_seconds:
                self._state = "jam"
                return self._state

        self._state = "ok"
        return self._state

    @property
    def state(self):
        return self._state

    def rate_per_min(self, now):
        """Smoothed instantaneous throughput (counts/min) over the last 60 s."""
        c = self.counts_in_window(now, 60)
        return float(c) if not math.isnan(c) else 0.0
