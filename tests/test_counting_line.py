"""Unit tests for LineCrossingCounter — pure, dependency-free logic."""
from counting_line import LineCrossingCounter


def _step(lc, prev, curr, **kw):
    """Helper: prime previous position, then update with current position."""
    lc.previous = {1: prev}
    return lc.update({1: curr}, **kw)


# ---------- axis-aligned crossing ----------

def test_axis_horizontal_crossing_counts_once():
    lc = LineCrossingCounter()
    counted = _step(lc, (50, 40), (50, 60), line_coord=50, axis_index=1,
                    direction="both")
    assert counted == ["object"]
    assert lc.total == 1
    # crossing again with the same id does not recount
    again = lc.update({1: (50, 80)}, 50, 1, "both")
    assert again == []
    assert lc.total == 1


def test_axis_no_crossing_when_same_side():
    lc = LineCrossingCounter()
    counted = _step(lc, (50, 10), (50, 40), line_coord=50, axis_index=1,
                    direction="both")
    assert counted == []
    assert lc.total == 0


def test_axis_direction_filter_blocks_wrong_way():
    lc = LineCrossingCounter()
    # moving downward (delta>0 = forward); ask for backward only
    counted = _step(lc, (50, 40), (50, 60), line_coord=50, axis_index=1,
                    direction="backward")
    assert counted == []
    # forward is accepted
    lc2 = LineCrossingCounter()
    ok = _step(lc2, (50, 40), (50, 60), line_coord=50, axis_index=1,
               direction="forward")
    assert ok == ["object"]


def test_axis_span_touch_counts_short_sighting():
    lc = LineCrossingCounter()
    # no previous position, but the box span straddles the line
    counted = lc.update({1: (50, 50)}, 50, 1, "both",
                        spans={1: (40, 60)})
    assert counted == ["object"]


def test_per_class_tally():
    lc = LineCrossingCounter()
    lc.previous = {1: (50, 40), 2: (50, 40)}
    counted = lc.update(
        {1: (50, 60), 2: (50, 60)}, 50, 1, "both",
        classes={1: "bottle", 2: "cup"},
    )
    assert sorted(counted) == ["bottle", "cup"]
    assert lc.class_counts == {"bottle": 1, "cup": 1}


def test_reset_clears_state():
    lc = LineCrossingCounter()
    _step(lc, (50, 40), (50, 60), line_coord=50, axis_index=1, direction="both")
    lc.reset()
    assert lc.total == 0
    assert lc.counted == set()
    assert lc.class_counts == {}
    assert lc.previous == {}


# ---------- arbitrary-angle segment crossing ----------

def test_segment_diagonal_crossing():
    lc = LineCrossingCounter()
    p1, p2 = (0, 0), (100, 100)  # line y = x
    lc.previous = {1: (60, 40)}  # below-right of the line
    counted = lc.update_segment({1: (40, 60)}, p1, p2, "both",
                                classes={1: "box"})
    assert counted == ["box"]
    assert lc.total == 1


def test_segment_outside_extent_does_not_count():
    lc = LineCrossingCounter()
    p1, p2 = (0, 0), (100, 100)
    # crosses the infinite line far beyond the drawn segment
    lc.previous = {1: (260, 240)}
    counted = lc.update_segment({1: (240, 260)}, p1, p2, "both")
    assert counted == []
    assert lc.total == 0


def test_segment_direction_filter():
    lc = LineCrossingCounter()
    p1, p2 = (0, 0), (100, 100)
    lc.previous = {1: (60, 40)}
    counted = lc.update_segment({1: (40, 60)}, p1, p2, "backward")
    assert counted == []


def test_segment_needs_two_frames():
    lc = LineCrossingCounter()
    p1, p2 = (0, 0), (100, 100)
    # first sighting (no previous) never counts in segment mode
    counted = lc.update_segment({1: (40, 60)}, p1, p2, "both")
    assert counted == []


def test_side_sign():
    # point above the y=x line should be on the opposite side of one below it
    s_above = LineCrossingCounter._side((0, 0), (100, 100), (40, 60))
    s_below = LineCrossingCounter._side((0, 0), (100, 100), (60, 40))
    assert (s_above > 0) != (s_below > 0)
