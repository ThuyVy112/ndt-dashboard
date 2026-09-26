import unittest
from datetime import datetime, timezone

from src.twin.state.twinning_rate import TwinningRateTracker


class TwinningRateTrackerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.now = datetime(2026, 1, 1, tzinfo=timezone.utc)

    def test_ten_successes_have_rate_one(self):
        tracker = TwinningRateTracker(window_seconds=60)
        for _ in range(10):
            tracker.record(True, self.now)

        self.assertEqual(tracker.rate(self.now), 1.0)

    def test_nine_successes_and_one_failure_have_rate_point_nine(self):
        tracker = TwinningRateTracker(window_seconds=60)
        for _ in range(9):
            tracker.record(True, self.now)
        tracker.record(False, self.now)

        self.assertEqual(tracker.rate(self.now), 0.9)

    def test_empty_tracker_has_zero_rate(self):
        tracker = TwinningRateTracker(window_seconds=60)

        self.assertEqual(tracker.rate(self.now), 0.0)


if __name__ == "__main__":
    unittest.main()
