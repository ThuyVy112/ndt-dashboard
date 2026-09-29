import math
import unittest
from datetime import datetime, timezone

from src.schemas.forecasting import ForecastRawSample
from src.twin.forecasting.raw_validator import (
    validate_raw_samples,
)


class ForecastRawValidatorTests(unittest.TestCase):
    def make_sample(
        self,
        *,
        controller_id: str = "c1",
        snapshot_id: str = "s1",
        observed_at: str | datetime = "2026-01-01T00:00:00+00:00",
        safe_capacity_pps: float = 100.0,
        utilization: float = 0.5,
        snapshot_valid: bool = True,
    ) -> dict[str, object]:
        return {
            "controller_id": controller_id,
            "snapshot_id": snapshot_id,
            "observed_at": observed_at,
            "safe_capacity_pps": safe_capacity_pps,
            "utilization": utilization,
            "snapshot_valid": snapshot_valid,
        }

    # check that the validator correctly identifies valid and invalid samples, including empty input, valid samples, invalid identifiers, invalid numeric values, non-finite numeric values, invalid timestamps, duplicate timestamps, sampling intervals, and custom sampling intervals.
    def test_empty_input_is_valid(self):
        result = validate_raw_samples([])

        self.assertTrue(result.valid)
        self.assertEqual(result.total_samples, 0)
        self.assertEqual(result.invalid_snapshot_count, 0)
        self.assertEqual(result.duplicate_count, 0)
        self.assertEqual(result.sampling_gap_count, 0)
        self.assertEqual(result.issues, ())

    # check that the validator correctly identifies valid samples and groups them by controller, including multiple samples for the same controller and different controllers.
    def test_valid_samples_are_valid_and_grouped_by_controller(
        self,
    ):
        samples = [
            self.make_sample(
                controller_id="c1",
                snapshot_id="s1",
            ),
            self.make_sample(
                controller_id="c1",
                snapshot_id="s2",
                observed_at=(
                    "2026-01-01T00:00:01+00:00"
                ),
            ),
            self.make_sample(
                controller_id="c2",
                snapshot_id="s3",
            ),
            self.make_sample(
                controller_id="c2",
                snapshot_id="s4",
                observed_at=(
                    "2026-01-01T00:00:01+00:00"
                ),
            ),
        ]

        result = validate_raw_samples(samples)

        self.assertTrue(result.valid)
        self.assertEqual(result.total_samples, 4)
        self.assertEqual(result.invalid_snapshot_count, 0)
        self.assertEqual(result.duplicate_count, 0)
        self.assertEqual(result.sampling_gap_count, 0)
        self.assertEqual(result.issues, ())

    def test_accepts_forecast_raw_sample_instances(self):
        sample = ForecastRawSample(
            run_id="run-1",
            controller_id="c1",
            observed_at=datetime(
                2026,
                1,
                1,
                tzinfo=timezone.utc,
            ),
            workload_type="stable",
            workload_phase="steady",
            processed_packet_in_rate=10.0,
            flow_mod_rate=2.0,
            process_cpu_percent=20.0,
            process_memory_rss_mb=50.0,
            response_p95_ms=5.0,
            managed_switch_count=2,
            safe_capacity_pps=100.0,
            utilization=0.5,
            max_switch_control_load_share=0.2,
            age_of_twin_ms=10.0,
            twinning_rate=1.0,
            completeness_ratio=1.0,
            synchronization_jitter_ms=1.0,
            snapshot_valid=True,
            snapshot_id="s1",
        )

        result = validate_raw_samples([sample])

        self.assertTrue(result.valid)
        self.assertEqual(result.total_samples, 1)

    def test_allows_overload_utilization(self):
        result = validate_raw_samples(
            [
                self.make_sample(
                    utilization=1.10,
                )
            ]
        )

        self.assertTrue(result.valid)

    def test_snapshot_invalid_is_counted_without_dropping_sample(
        self,
    ):
        result = validate_raw_samples(
            [
                self.make_sample(
                    snapshot_id="s1",
                    snapshot_valid=False,
                ),
                self.make_sample(
                    snapshot_id="s2",
                    observed_at=(
                        "2026-01-01T00:00:01+00:00"
                    ),
                ),
            ]
        )

        self.assertFalse(result.valid)
        self.assertEqual(result.total_samples, 2)
        self.assertEqual(result.invalid_snapshot_count, 1)
        self.assertEqual(
            [issue.code for issue in result.issues],
            ["snapshot_invalid"],
        )

    def test_empty_identifiers_create_issues(self):
        result = validate_raw_samples(
            [
                self.make_sample(
                    controller_id=" ",
                    snapshot_id="",
                )
            ]
        )

        self.assertFalse(result.valid)

        self.assertEqual(
            {issue.code for issue in result.issues},
            {
                "controller_id_empty",
                "snapshot_id_empty",
            },
        )

    def test_invalid_numeric_values_create_issues(self):
        result = validate_raw_samples(
            [
                self.make_sample(
                    safe_capacity_pps=0.0,
                    utilization=-1.0,
                )
            ]
        )

        self.assertFalse(result.valid)

        self.assertEqual(
            {issue.code for issue in result.issues},
            {
                "safe_capacity_invalid",
                "utilization_invalid",
            },
        )

    def test_non_finite_numeric_values_are_invalid(self):
        cases = (
            ("safe_capacity_pps", math.nan),
            ("safe_capacity_pps", math.inf),
            ("safe_capacity_pps", -math.inf),
            ("utilization", math.nan),
            ("utilization", math.inf),
            ("utilization", -math.inf),
        )

        for field_name, value in cases:
            with self.subTest(
                field_name=field_name,
                value=value,
            ):
                result = validate_raw_samples(
                    [
                        self.make_sample(
                            **{field_name: value}
                        )
                    ]
                )

                self.assertFalse(result.valid)

                expected_code = (
                    "safe_capacity_invalid"
                    if field_name == "safe_capacity_pps"
                    else "utilization_invalid"
                )

                self.assertIn(
                    expected_code,
                    {
                        issue.code
                        for issue in result.issues
                    },
                )

    def test_invalid_timestamp_is_reported(self):
        result = validate_raw_samples(
            [
                self.make_sample(
                    observed_at="not-a-timestamp",
                )
            ]
        )

        self.assertFalse(result.valid)
        self.assertEqual(
            [issue.code for issue in result.issues],
            ["timestamp_invalid"],
        )

    def test_duplicate_timestamp_is_counted(self):
        result = validate_raw_samples(
            [
                self.make_sample(snapshot_id="s1"),
                self.make_sample(snapshot_id="s2"),
            ]
        )

        self.assertFalse(result.valid)
        self.assertEqual(result.duplicate_count, 1)
        self.assertEqual(
            [issue.code for issue in result.issues],
            ["duplicate"],
        )

    def test_same_timestamp_on_different_controllers_is_not_duplicate(
        self,
    ):
        result = validate_raw_samples(
            [
                self.make_sample(
                    controller_id="c1",
                    snapshot_id="s1",
                ),
                self.make_sample(
                    controller_id="c2",
                    snapshot_id="s2",
                ),
            ]
        )

        self.assertTrue(result.valid)
        self.assertEqual(result.duplicate_count, 0)

    def test_timestamp_must_be_monotonic_per_controller(self):
        result = validate_raw_samples(
            [
                self.make_sample(
                    snapshot_id="s1",
                    observed_at=(
                        "2026-01-01T00:00:01+00:00"
                    ),
                ),
                self.make_sample(
                    snapshot_id="s2",
                    observed_at=(
                        "2026-01-01T00:00:00+00:00"
                    ),
                ),
            ]
        )

        self.assertFalse(result.valid)
        self.assertEqual(result.duplicate_count, 0)
        self.assertEqual(
            [issue.code for issue in result.issues],
            ["timestamp_not_monotonic"],
        )

    def test_short_sampling_interval_is_reported_without_gap(
        self,
    ):
        result = validate_raw_samples(
            [
                self.make_sample(snapshot_id="s1"),
                self.make_sample(
                    snapshot_id="s2",
                    observed_at=datetime(
                        2026,
                        1,
                        1,
                        microsecond=500_000,
                        tzinfo=timezone.utc,
                    ),
                ),
            ]
        )

        self.assertFalse(result.valid)
        self.assertEqual(result.sampling_gap_count, 0)
        self.assertEqual(
            [issue.code for issue in result.issues],
            ["sampling_interval"],
        )

    def test_long_sampling_interval_is_reported_as_gap(self):
        result = validate_raw_samples(
            [
                self.make_sample(snapshot_id="s1"),
                self.make_sample(
                    snapshot_id="s2",
                    observed_at=(
                        "2026-01-01T00:00:03+00:00"
                    ),
                ),
            ]
        )

        self.assertFalse(result.valid)
        self.assertEqual(result.sampling_gap_count, 1)
        self.assertEqual(
            [issue.code for issue in result.issues],
            [
                "sampling_interval",
                "sampling_gap",
            ],
        )

    def test_custom_sampling_interval_is_supported(self):
        result = validate_raw_samples(
            [
                self.make_sample(snapshot_id="s1"),
                self.make_sample(
                    snapshot_id="s2",
                    observed_at=(
                        "2026-01-01T00:00:02+00:00"
                    ),
                ),
            ],
            expected_sampling_interval_seconds=2.0,
        )

        self.assertTrue(result.valid)
        self.assertEqual(result.sampling_gap_count, 0)

    def test_expected_sampling_interval_must_be_positive_and_finite(
        self,
    ):
        invalid_values = (
            0.0,
            -1.0,
            math.inf,
            -math.inf,
            math.nan,
            "invalid",
        )

        for expected_interval in invalid_values:
            with self.subTest(
                expected_interval=expected_interval,
            ):
                with self.assertRaisesRegex(
                    ValueError,
                    "expected_sampling_interval_seconds "
                    "must be positive",
                ):
                    validate_raw_samples(
                        [],
                        expected_sampling_interval_seconds=(
                            expected_interval
                        ),
                    )


if __name__ == "__main__":
    unittest.main()