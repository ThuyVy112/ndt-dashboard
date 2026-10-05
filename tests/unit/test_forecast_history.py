import unittest

from src.twin.forecasting.history import (
    DEFAULT_MAX_GAP_SECONDS,
    NOT_READY,
    READY,
    AppendStatus,
    HistoryNotReadyError,
    TwinHistoryBuffer,
)


def fill(buffer: TwinHistoryBuffer, controller_id: str, times: list[float]) -> list[AppendStatus]:
    return [
        buffer.append(controller_id, t, f"snap-{controller_id}-{t}", {"utilization": 0.5})
        for t in times
    ]


class ForecastHistoryTest(unittest.TestCase):
    def setUp(self) -> None:
        self.buffer = TwinHistoryBuffer(history_steps=10, safety_buffer=5)

    def test_ten_consecutive_samples_are_ready(self) -> None:
        fill(self.buffer, "c1", [float(t) for t in range(10)])
        self.assertTrue(self.buffer.ready("c1"))
        self.assertEqual(self.buffer.status("c1"), READY)
        self.assertEqual(len(self.buffer.get_history("c1")), 10)

    def test_nine_samples_are_not_ready(self) -> None:
        fill(self.buffer, "c1", [float(t) for t in range(9)])
        self.assertFalse(self.buffer.ready("c1"))
        self.assertEqual(self.buffer.status("c1"), NOT_READY)
        with self.assertRaises(HistoryNotReadyError):
            self.buffer.get_history("c1")

    def test_gap_resets_history(self) -> None:
        statuses = fill(self.buffer, "c1", [0.0, 1.0, 2.0, 8.0])  # 1s,1s,6s
        self.assertEqual(statuses[-1], AppendStatus.RESET_GAP)
        self.assertEqual(self.buffer.size("c1"), 1)  # old 3 samples dropped
        self.assertFalse(self.buffer.ready("c1"))

    def test_gap_never_stitches_two_segments(self) -> None:
        fill(self.buffer, "c1", [float(t) for t in range(10)])   # READY
        fill(self.buffer, "c1", [30.0, 31.0])                     # after a gap
        self.assertFalse(self.buffer.ready("c1"))                 # not 12 samples
        fill(self.buffer, "c1", [float(t) for t in range(32, 40)])
        history = self.buffer.get_history("c1")
        self.assertEqual(history[0].observed_at, 30.0)            # only new segment

    def test_invalid_snapshot_is_not_appended(self) -> None:
        status = self.buffer.append("c1", 0.0, "s0", {}, snapshot_valid=False)
        self.assertEqual(status, AppendStatus.REJECTED_INVALID_SNAPSHOT)
        self.assertEqual(self.buffer.size("c1"), 0)

    def test_skipped_invalid_snapshot_leaves_a_detectable_hole(self) -> None:
        # A hole longer than max_gap_seconds (3 s step > 2.5 s) must reset.
        fill(self.buffer, "c1", [0.0, 1.0])
        self.buffer.append("c1", 2.0, "bad", {}, snapshot_valid=False)
        self.buffer.append("c1", 3.0, "bad", {}, snapshot_valid=False)
        status = self.buffer.append("c1", 4.0, "s4", {})
        self.assertEqual(status, AppendStatus.RESET_GAP)
        self.assertEqual(self.buffer.size("c1"), 1)

    def test_single_missing_sample_within_max_gap_is_not_a_break(self) -> None:
        # 2 s step <= 2.5 s: same rule continuity.assign_segments applies.
        fill(self.buffer, "c1", [0.0, 1.0])
        self.assertEqual(
            self.buffer.append("c1", 3.0, "s3", {}), AppendStatus.APPENDED
        )

    def test_default_gap_matches_dataset_contract(self) -> None:
        self.assertEqual(DEFAULT_MAX_GAP_SECONDS, 2.5)
        self.assertEqual(self.buffer.max_gap_seconds, DEFAULT_MAX_GAP_SECONDS)

    def test_one_second_cadence_then_six_second_gap_resets(self) -> None:
        # Week 9 contract: 1s,1s,1s,6s -> reset / NOT_READY.
        fill(self.buffer, "c1", [0.0, 1.0, 2.0, 3.0])
        self.assertEqual(
            self.buffer.append("c1", 9.0, "s9", {}), AppendStatus.RESET_GAP
        )
        self.assertEqual(self.buffer.status("c1"), NOT_READY)

    def test_duplicate_timestamp_is_rejected(self) -> None:
        fill(self.buffer, "c1", [0.0, 1.0])
        status = self.buffer.append("c1", 1.0, "other-snapshot", {})
        self.assertEqual(status, AppendStatus.REJECTED_DUPLICATE)
        self.assertEqual(self.buffer.size("c1"), 2)

    def test_same_snapshot_read_twice_is_rejected(self) -> None:
        self.buffer.append("c1", 0.0, "snap-a", {})
        status = self.buffer.append("c1", 0.4, "snap-a", {})
        self.assertEqual(status, AppendStatus.REJECTED_DUPLICATE)

    def test_backwards_timestamp_resets(self) -> None:
        fill(self.buffer, "c1", [0.0, 1.0, 2.0])
        status = self.buffer.append("c1", 1.0 - 0.5, "late", {})
        self.assertEqual(status, AppendStatus.RESET_OUT_OF_ORDER)
        self.assertEqual(self.buffer.size("c1"), 1)

    def test_controllers_are_independent(self) -> None:
        fill(self.buffer, "c1", [float(t) for t in range(10)])
        fill(self.buffer, "c2", [float(t) for t in range(4)])
        self.assertTrue(self.buffer.ready("c1"))
        self.assertFalse(self.buffer.ready("c2"))
        fill(self.buffer, "c2", [100.0])  # gap on c2 only
        self.assertTrue(self.buffer.ready("c1"))

    def test_buffer_keeps_history_steps_plus_safety_buffer(self) -> None:
        fill(self.buffer, "c1", [float(t) for t in range(40)])
        self.assertEqual(self.buffer.size("c1"), 15)
        self.assertEqual(self.buffer.get_history("c1")[-1].observed_at, 39.0)
        self.assertEqual(len(self.buffer.get_history("c1")), 10)

    def test_clear_one_and_all(self) -> None:
        fill(self.buffer, "c1", [0.0, 1.0])
        fill(self.buffer, "c2", [0.0, 1.0])
        self.buffer.clear("c1")
        self.assertEqual(self.buffer.size("c1"), 0)
        self.assertEqual(self.buffer.size("c2"), 2)
        self.buffer.clear()
        self.assertEqual(self.buffer.size("c2"), 0)

    def test_entry_keeps_row_and_snapshot_id(self) -> None:
        self.buffer.append("c1", 0.0, "snap-x", {"utilization": 0.7})
        single = TwinHistoryBuffer(history_steps=1)
        single.append("c1", 0.0, "snap-x", {"utilization": 0.7})
        entry = single.get_history("c1")[0]
        self.assertEqual(entry.snapshot_id, "snap-x")
        self.assertEqual(entry.row["utilization"], 0.7)


def twin_state(index: int, *, valid: bool = True) -> dict[str, object]:
    """Minimal TwinState dict shaped like GET /api/v1/twin/state."""
    return {
        "snapshot_id": f"snap-{index}",
        "created_at": f"2026-10-05T00:00:{index:02d}+00:00",
        "controllers": [
            {"controller_id": "c1", "utilization": 0.4 + index / 100},
            {"controller_id": "c2", "utilization": 0.3},
        ],
        "quality": {"valid": valid, "consistent": valid},
    }


class TwinStateAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.buffer = TwinHistoryBuffer(history_steps=10, safety_buffer=5)

    def test_ten_consecutive_twin_states_are_ready_for_both_controllers(self) -> None:
        for index in range(10):
            result = self.buffer.append_twin_state(twin_state(index))
            self.assertEqual(
                set(result.values()), {AppendStatus.APPENDED}
            )

        self.assertEqual(self.buffer.status("c1"), READY)
        self.assertEqual(self.buffer.status("c2"), READY)
        history = self.buffer.get_history("c1")
        self.assertEqual(history[0].snapshot_id, "snap-0")
        self.assertEqual(history[-1].row["utilization"], 0.49)

    def test_nine_twin_states_are_not_ready(self) -> None:
        for index in range(9):
            self.buffer.append_twin_state(twin_state(index))

        self.assertEqual(self.buffer.status("c1"), NOT_READY)

    def test_invalid_twin_state_is_not_stored(self) -> None:
        result = self.buffer.append_twin_state(twin_state(0, valid=False))

        self.assertEqual(
            result,
            {
                "c1": AppendStatus.REJECTED_INVALID_SNAPSHOT,
                "c2": AppendStatus.REJECTED_INVALID_SNAPSHOT,
            },
        )
        self.assertEqual(self.buffer.size("c1"), 0)

    def test_same_snapshot_twice_is_rejected(self) -> None:
        self.buffer.append_twin_state(twin_state(0))
        result = self.buffer.append_twin_state(twin_state(0))

        self.assertEqual(set(result.values()), {AppendStatus.REJECTED_DUPLICATE})
        self.assertEqual(self.buffer.size("c1"), 1)

    def test_gap_in_snapshot_time_resets_history(self) -> None:
        for index in range(5):
            self.buffer.append_twin_state(twin_state(index))
        result = self.buffer.append_twin_state(twin_state(11))  # 7 s later

        self.assertEqual(set(result.values()), {AppendStatus.RESET_GAP})
        self.assertEqual(self.buffer.size("c1"), 1)

    def test_not_ready_api_response_is_ignored(self) -> None:
        self.assertEqual(self.buffer.append_twin_state({"status": "NOT_READY"}), {})

    def test_twin_state_without_time_or_id_is_rejected(self) -> None:
        broken = twin_state(0)
        del broken["created_at"]

        with self.assertRaises(ValueError):
            self.buffer.append_twin_state(broken)


if __name__ == "__main__":
    unittest.main()
