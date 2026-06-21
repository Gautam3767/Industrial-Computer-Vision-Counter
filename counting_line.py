class LineCrossingCounter:
    """Counts tracked objects that cross (or touch) a virtual line.

    Takes a ``{track_id: (cx, cy)}`` mapping each tick and tallies any ID whose
    centroid crossed the line. Two line representations are supported:

    * **Axis-aligned** (``update``): a horizontal/vertical line at ``line_coord``
      along ``axis_index`` (0 = x for vertical lines, 1 = y for horizontal).
      Optional box spans let an object count as soon as its box overlaps the
      line, so brief sightings still register.
    * **Arbitrary segment** (``update_segment``): a line from ``p1`` to ``p2`` at
      any angle. The side of the segment a centroid is on is the sign of the
      cross product; a crossing is a sign change while the foot of the
      perpendicular falls within the segment.

    Each ID is counted at most once. When a per-ID ``classes`` mapping is given,
    a per-class tally is kept in :attr:`class_counts` and each ``update`` call
    returns the list of class names counted on that tick.
    """

    def __init__(self):
        self.previous = {}
        self.counted = set()
        self.total = 0
        self.class_counts = {}

    def reset(self):
        self.previous = {}
        self.counted = set()
        self.total = 0
        self.class_counts = {}

    # ---------- shared bookkeeping ----------

    def _record(self, obj_id, cls, on_count):
        cls = cls or "object"
        self.total += 1
        self.counted.add(obj_id)
        self.class_counts[cls] = self.class_counts.get(cls, 0) + 1
        if on_count:
            on_count(cls)
        return cls

    @staticmethod
    def _direction_matches(direction, delta, allow_unknown=False):
        if direction == "both":
            return True
        if delta is None or delta == 0:
            return allow_unknown
        forward = delta > 0
        return ((direction == "forward" and forward)
                or (direction == "backward" and not forward))

    @staticmethod
    def _span_touches_line(span, line_coord):
        if span is None:
            return False
        a, b = span
        lo, hi = sorted((a, b))
        return lo <= line_coord <= hi

    # ---------- axis-aligned (horizontal / vertical) ----------

    def update(self, tracked, line_coord, axis_index, direction, on_count=None,
               spans=None, classes=None):
        counted = []
        spans = spans or {}
        classes = classes or {}
        for obj_id, centroid in tracked.items():
            if obj_id in self.counted:
                continue
            prev = self.previous.get(obj_id)
            b = centroid[axis_index]
            delta = None
            crossed = False
            if prev is not None:
                a = prev[axis_index]
                delta = b - a
                crossed = (a < line_coord <= b) or (a > line_coord >= b)

            touched = self._span_touches_line(spans.get(obj_id), line_coord)
            if not crossed and not touched:
                continue

            # With a one-frame or already-on-line detection, movement direction
            # cannot be inferred yet. Trust the line touch so short sightings
            # still count.
            allow_unknown = touched
            if self._direction_matches(direction, delta, allow_unknown):
                counted.append(self._record(obj_id, classes.get(obj_id), on_count))

        self.previous = {k: tuple(v) for k, v in tracked.items()}
        return counted

    # ---------- arbitrary-angle segment ----------

    @staticmethod
    def _side(p1, p2, pt):
        """Signed area / cross product: >0, <0, or 0 for which side of p1->p2."""
        return ((p2[0] - p1[0]) * (pt[1] - p1[1])
                - (p2[1] - p1[1]) * (pt[0] - p1[0]))

    @staticmethod
    def _within_segment(p1, p2, pt, margin=0.05):
        """True if pt projects onto the p1->p2 segment (with a small margin)."""
        ax, ay = p1
        bx, by = p2
        dx, dy = bx - ax, by - ay
        denom = dx * dx + dy * dy
        if denom == 0:
            return False
        t = ((pt[0] - ax) * dx + (pt[1] - ay) * dy) / denom
        return -margin <= t <= 1 + margin

    def update_segment(self, tracked, p1, p2, direction, on_count=None,
                       classes=None):
        counted = []
        classes = classes or {}
        for obj_id, centroid in tracked.items():
            if obj_id in self.counted:
                continue
            prev = self.previous.get(obj_id)
            if prev is None:
                continue

            s_prev = self._side(p1, p2, prev)
            s_curr = self._side(p1, p2, centroid)
            # Sign change = crossed the infinite line.
            crossed = (s_prev < 0 <= s_curr) or (s_prev > 0 >= s_curr)
            if s_prev == 0 or s_curr == 0:
                crossed = s_prev != s_curr
            if not crossed:
                continue
            # Restrict to the drawn segment, not its infinite extension.
            if not self._within_segment(p1, p2, centroid):
                continue

            # "forward" = moving toward the positive side of p1->p2.
            delta = 1 if s_curr > s_prev else -1
            if self._direction_matches(direction, delta):
                counted.append(self._record(obj_id, classes.get(obj_id), on_count))

        self.previous = {k: tuple(v) for k, v in tracked.items()}
        return counted
