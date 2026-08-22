import numpy as np

from traffic_monitoring.pipeline import IoUTracker, Track, _crossed_line, _traffic_condition


def test_tracker_preserves_id_for_matching_vehicle():
    tracker = IoUTracker()
    first = tracker.update([("car", np.array([10, 10, 50, 50]))])
    second = tracker.update([("car", np.array([14, 10, 54, 50]))])
    assert first[0].id == second[0].id


def test_line_crossing_detects_side_change():
    track = Track(1, "car", np.array([0, 0, 10, 10]), center=(20, 50), previous_center=(20, 10))
    assert _crossed_line(track, (0, 30, 100, 30))


def test_traffic_condition_uses_occupancy():
    assert _traffic_condition(total=1, occupancy_percent=70, duration_seconds=180) == "padat"
