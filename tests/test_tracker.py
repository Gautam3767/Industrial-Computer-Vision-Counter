"""Unit tests for CentroidTracker register/match/deregister behaviour."""
from detector import CentroidTracker


def test_register_assigns_sequential_ids():
    t = CentroidTracker()
    objs = t.update([(10, 10), (50, 50)])
    assert set(objs.keys()) == {0, 1}
    assert objs[0] == (10, 10)
    assert objs[1] == (50, 50)


def test_matches_nearest_keeps_id():
    t = CentroidTracker()
    t.update([(10, 10)])
    objs = t.update([(13, 12)])  # small move — same object
    assert list(objs.keys()) == [0]
    assert objs[0] == (13, 12)


def test_far_jump_registers_new_id():
    t = CentroidTracker(max_distance=20)
    t.update([(10, 10)])
    objs = t.update([(200, 200)])  # beyond max_distance -> new object
    assert 1 in objs  # a new id was created


def test_deregister_after_max_disappeared():
    t = CentroidTracker(max_disappeared=2)
    t.update([(10, 10)])
    for _ in range(3):       # exceed max_disappeared empty frames
        t.update([])
    assert t.objects == {}


def test_reappear_before_timeout_survives():
    t = CentroidTracker(max_disappeared=5)
    t.update([(10, 10)])
    t.update([])             # one missed frame
    objs = t.update([(11, 11)])
    assert list(objs.keys()) == [0]


def test_two_objects_keep_distinct_ids():
    t = CentroidTracker()
    t.update([(10, 10), (100, 100)])
    objs = t.update([(12, 11), (98, 101)])
    assert objs[0] == (12, 11)
    assert objs[1] == (98, 101)
