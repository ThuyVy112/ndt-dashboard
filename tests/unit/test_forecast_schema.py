# create valid sample, serialization datetime, immutable, reject identifiers, and reject invalid numeric values
import math
import unittest
from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timezone
from typing import Any

from src.schemas.forecasting import ForecastRawSample


class ForecastRawSampleTests(unittest.TestCase):
    def make_sample(
        self,
        **overrides: Any,
    ) -> ForecastRawSample:
        sample = ForecastRawSample(
            run_id="forecast-stable-r01",
            controller_id="c1",
            observed_at=datetime(
                2026,
                1,
                1,
                0,
                0,
                0,
                tzinfo=timezone.utc,
            ),
            workload_type="stable",
            workload_phase="steady",
            processed_packet_in_rate=500.0,
            flow_mod_rate=20.0,
            process_cpu_percent=35.0,
            process_memory_rss_mb=100.0,
            response_p95_ms=10.0,
            managed_switch_count=10,
            safe_capacity_pps=830.0,
            utilization=0.60,
            max_switch_control_load_share=0.20,
            age_of_twin_ms=100.0,
            twinning_rate=1.0,
            completeness_ratio=1.0,
            synchronization_jitter_ms=5.0,
            snapshot_valid=True,
            snapshot_id="snapshot-001",
        )

        if not overrides:
            return sample

        return replace(sample, **overrides)

    def test_create_valid_sample(self):
        sample = self.make_sample()

        self.assertEqual(sample.run_id, "forecast-stable-r01")
        self.assertEqual(sample.controller_id, "c1")
        self.assertEqual(sample.workload_type, "stable")
        self.assertEqual(sample.workload_phase, "steady")
        self.assertEqual(sample.safe_capacity_pps, 830.0)
        self.assertEqual(sample.utilization, 0.60)
        self.assertTrue(sample.snapshot_valid)

    def test_to_dict_serializes_datetime_as_iso8601(self):
        sample = self.make_sample()

        data = sample.to_dict()

        self.assertIsInstance(data, dict)
        self.assertEqual(
            data["observed_at"],
            "2026-01-01T00:00:00+00:00",
        )
        self.assertEqual(data["run_id"], "forecast-stable-r01")
        self.assertEqual(data["controller_id"], "c1")
        self.assertEqual(data["snapshot_id"], "snapshot-001")

    def test_sample_is_immutable(self):
        sample = self.make_sample()

        with self.assertRaises(FrozenInstanceError):
            sample.utilization = 0.90 # type: ignore[misc]

    def test_rejects_empty_workload_metadata(self):
        for field_name in (
            "workload_type",
            "workload_phase",
        ):
            with self.subTest(field_name=field_name):
                with self.assertRaises(ValueError):
                    self.make_sample(
                        **{field_name: " "}
                    )

    def test_rejects_empty_identifiers(self):
        for field_name in (
            "run_id",
            "controller_id",
            "snapshot_id",
        ):
            with self.subTest(field_name=field_name):
                with self.assertRaises(ValueError):
                    self.make_sample(
                        **{field_name: " "}
                    )

    def test_rejects_negative_managed_switch_count(self):
        with self.assertRaisesRegex(
            ValueError,
            "managed_switch_count must be non-negative",
        ):
            self.make_sample(
                managed_switch_count=-1,
            )

    def test_rejects_invalid_safe_capacity(self):
        for value in (
            0.0,
            -1.0,
            math.nan,
            math.inf,
            -math.inf,
        ):
            with self.subTest(value=value):
                with self.assertRaisesRegex(
                    ValueError,
                    "safe_capacity_pps must be finite and positive",
                ):
                    self.make_sample(
                        safe_capacity_pps=value,
                    )

    def test_rejects_non_finite_safe_capacity(self):
        for value in (
            math.nan,
            math.inf,
            -math.inf,
        ):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    self.make_sample(
                        safe_capacity_pps=value,
                    )

    def test_rejects_negative_numeric_metrics(self):
        fields = (
            "processed_packet_in_rate",
            "flow_mod_rate",
            "process_cpu_percent",
            "process_memory_rss_mb",
            "response_p95_ms",
            "utilization",
            "max_switch_control_load_share",
            "age_of_twin_ms",
            "twinning_rate",
            "completeness_ratio",
            "synchronization_jitter_ms",
        )

        for field_name in fields:
            with self.subTest(field_name=field_name):
                with self.assertRaises(ValueError):
                    self.make_sample(
                        **{field_name: -1.0}
                    )

    def test_rejects_non_finite_numeric_metrics(self):
        fields = (
            "processed_packet_in_rate",
            "flow_mod_rate",
            "process_cpu_percent",
            "process_memory_rss_mb",
            "response_p95_ms",
            "utilization",
            "max_switch_control_load_share",
            "age_of_twin_ms",
            "twinning_rate",
            "completeness_ratio",
            "synchronization_jitter_ms",
        )

        for field_name in fields:
            for value in (
                math.nan,
                math.inf,
                -math.inf,
            ):
                with self.subTest(
                    field_name=field_name,
                    value=value,
                ):
                    with self.assertRaises(ValueError):
                        self.make_sample(
                            **{field_name: value}
                        )

    def test_allows_utilization_above_one_for_overload(self):
        sample = self.make_sample(
            utilization=1.10,
        )

        self.assertEqual(
            sample.utilization,
            1.10,
        )


if __name__ == "__main__":
    unittest.main() 