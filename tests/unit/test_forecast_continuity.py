import unittest

from src.twin.forecasting.continuity import assign_segments


class ForecastContinuityTests(unittest.TestCase):
    def test_continuous_sequence(self):
        self.assertEqual(
            assign_segments([1, 2, 3], 2.5),
            [0, 0, 0],
        )

    def test_gap_starts_new_segment(self):
        self.assertEqual(
            assign_segments([1, 2, 7], 2.5),
            [0, 0, 1],
        )

    def test_multiple_gaps(self):
        self.assertEqual(
            assign_segments([1, 2, 7, 8, 20], 2.5),
            [0, 0, 1, 1, 2],
        )

    def test_empty_input(self):
        self.assertEqual(assign_segments([], 2.5), [])

    def test_duplicate_timestamp_is_rejected(self):
        with self.assertRaises(ValueError):
            assign_segments([1, 2, 2], 2.5)

    def test_backwards_timestamp_is_rejected(self):
        with self.assertRaises(ValueError):
            assign_segments([1, 3, 2], 2.5)

    def test_invalid_gap_threshold(self):
        with self.assertRaises(ValueError):
            assign_segments([1, 2], 0)

    def test_iso_timestamps(self):
        timestamps = [
            "2026-01-01T00:00:00+00:00",
            "2026-01-01T00:00:01+00:00",
            "2026-01-01T00:00:05+00:00",
        ]

        self.assertEqual(
            assign_segments(timestamps, 2.5),
            [0, 0, 1],
        )


if __name__ == "__main__":
    unittest.main()
