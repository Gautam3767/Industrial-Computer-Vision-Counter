class LineCrossingCounter:
    """Counts tracked objects that cross or touch a virtual line.

    Takes a {track_id: (cx, cy)} mapping each tick and tallies any ID whose
    centroid crossed `line_coord` along `axis_index` (0 = x for vertical lines,
    1 = y for horizontal lines). If optional box spans are supplied, an object
    can also count as soon as its box overlaps the line. Each ID is counted at
    most once.
    """

    def __init__(self):
        self.previous = {}
        self.counted = set()
        self.total = 0

    def reset(self):
        self.previous = {}
        self.counted = set()
        self.total = 0

    @staticmethod
    def _direction_matches(direction, delta, allow_unknown=False):
        if direction == "both":
            return True
        if delta is None:
            return allow_unknown
        if delta == 0:
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

    def update(self, tracked, line_coord, axis_index, direction, on_count=None,
               spans=None):
        counted_now = 0
        spans = spans or {}
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
                self.total += 1
                counted_now += 1
                self.counted.add(obj_id)
                if on_count:
                    on_count()

        self.previous = {k: tuple(v) for k, v in tracked.items()}
        return counted_now
