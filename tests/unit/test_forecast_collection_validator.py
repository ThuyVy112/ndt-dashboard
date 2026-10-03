import unittest

from scripts.experiments.validate_forecast_collection import (
    validate_collection,
)


class ForecastCollectionValidatorTests(unittest.TestCase):
    def metadata(self):
        return {
            "run_id": "stable-r01-s101",
            "workload_type": "stable",
            "duration_seconds": 2,
            "sampling_interval_seconds": 1,
            "controllers": ["c1", "c2"],
            "migration_enabled": False,
        }

    def sample(
        self,
        *,
        controller_id="c1",
        observed_at="2026-01-01T00:00:00+00:00",
        snapshot_id="snap-1",
        workload_phase="steady",
        safe_capacity_pps=100.0,
        processed_packet_in_rate=50.0,
        utilization=0.5,
        snapshot_valid=True,
    ):
        return {
            "run_id": "stable-r01-s101",
            "controller_id": controller_id,
            "observed_at": observed_at,
            "workload_type": "stable",
            "workload_phase": workload_phase,
            "processed_packet_in_rate": processed_packet_in_rate,
            "flow_mod_rate": 1.0,
            "process_cpu_percent": 10.0,
            "process_memory_rss_mb": 50.0,
            "response_p95_ms": 2.0,
            "managed_switch_count": 10,
            "safe_capacity_pps": safe_capacity_pps,
            "utilization": utilization,
            "max_switch_control_load_share": 0.1,
            "age_of_twin_ms": 100.0,
            "twinning_rate": 1.0,
            "completeness_ratio": 1.0,
            "synchronization_jitter_ms": 1.0,
            "snapshot_valid": snapshot_valid,
            "snapshot_id": snapshot_id,
        }

    def valid_samples(self):
        return [
            self.sample(
                controller_id="c1",
                snapshot_id="s1",
            ),
            self.sample(
                controller_id="c1",
                observed_at="2026-01-01T00:00:01+00:00",
                snapshot_id="s2",
            ),
            self.sample(
                controller_id="c2",
                snapshot_id="s1",
            ),
            self.sample(
                controller_id="c2",
                observed_at="2026-01-01T00:00:01+00:00",
                snapshot_id="s2",
            ),
        ]

    def codes(self, result):
        return {issue.code for issue in result.issues}

    def test_valid_collection(self):
        result = validate_collection(
            metadata=self.metadata(),
            samples=self.valid_samples(),
        )

        self.assertTrue(result.valid)
        self.assertEqual(result.total_samples, 4)
        self.assertEqual(result.samples_per_controller["c1"], 2)
        self.assertEqual(result.samples_per_controller["c2"], 2)
        self.assertEqual(result.coverage_per_controller["c1"], 1.0)
        self.assertEqual(result.coverage_per_controller["c2"], 1.0)

    def test_duplicate_timestamp(self):
        samples = self.valid_samples()
        samples[1]["observed_at"] = samples[0]["observed_at"]

        result = validate_collection(
            metadata=self.metadata(),
            samples=samples,
        )

        self.assertFalse(result.valid)
        self.assertIn("raw_duplicate", self.codes(result))

    def test_out_of_order_timestamp(self):
        samples = self.valid_samples()
        samples[1]["observed_at"] = "2025-12-31T23:59:59+00:00"

        result = validate_collection(
            metadata=self.metadata(),
            samples=samples,
        )

        self.assertFalse(result.valid)
        self.assertIn(
            "raw_timestamp_not_monotonic",
            self.codes(result),
        )

    def test_gap_within_week8_limit_is_allowed(self):
        metadata = self.metadata()
        metadata["duration_seconds"] = 3

        samples = self.valid_samples()
        samples[1]["observed_at"] = "2026-01-01T00:00:02+00:00"
        samples[3]["observed_at"] = "2026-01-01T00:00:02+00:00"

        result = validate_collection(
            metadata=metadata,
            samples=samples,
            min_coverage=0.4,
            max_gap_seconds=2.5,
        )

        self.assertTrue(result.valid)

    def test_gap_above_week8_limit_is_rejected(self):
        metadata = self.metadata()
        metadata["duration_seconds"] = 4

        samples = self.valid_samples()
        samples[1]["observed_at"] = "2026-01-01T00:00:03+00:00"
        samples[3]["observed_at"] = "2026-01-01T00:00:03+00:00"

        result = validate_collection(
            metadata=metadata,
            samples=samples,
            min_coverage=0.4,
            max_gap_seconds=2.5,
        )

        self.assertFalse(result.valid)
        self.assertIn("max_gap_exceeded", self.codes(result))

    def test_missing_required_field(self):
        samples = self.valid_samples()
        del samples[0]["workload_phase"]

        result = validate_collection(
            metadata=self.metadata(),
            samples=samples,
        )

        self.assertFalse(result.valid)
        self.assertIn("missing_fields", self.codes(result))
        self.assertIn("workload_phase_missing", self.codes(result))

    def test_invalid_snapshot(self):
        samples = self.valid_samples()
        samples[0]["snapshot_valid"] = False

        result = validate_collection(
            metadata=self.metadata(),
            samples=samples,
        )

        self.assertFalse(result.valid)
        self.assertIn("raw_snapshot_invalid", self.codes(result))

    def test_wrong_controller(self):
        samples = self.valid_samples()
        samples[0]["controller_id"] = "c3"

        result = validate_collection(
            metadata=self.metadata(),
            samples=samples,
        )

        self.assertFalse(result.valid)
        self.assertIn("controller_unexpected", self.codes(result))

    def test_safe_capacity_non_positive(self):
        samples = self.valid_samples()
        samples[0]["safe_capacity_pps"] = 0.0

        result = validate_collection(
            metadata=self.metadata(),
            samples=samples,
        )

        self.assertFalse(result.valid)
        self.assertIn(
            "raw_safe_capacity_invalid",
            self.codes(result),
        )

    def test_utilization_mismatch(self):
        samples = self.valid_samples()
        samples[0]["utilization"] = 0.8

        result = validate_collection(
            metadata=self.metadata(),
            samples=samples,
        )

        self.assertFalse(result.valid)
        self.assertIn("utilization_mismatch", self.codes(result))

    def test_missing_workload_phase(self):
        samples = self.valid_samples()
        samples[0]["workload_phase"] = ""

        result = validate_collection(
            metadata=self.metadata(),
            samples=samples,
        )

        self.assertFalse(result.valid)
        self.assertIn("workload_phase_missing", self.codes(result))

    def test_run_id_mismatch(self):
        samples = self.valid_samples()
        samples[0]["run_id"] = "other-run"

        result = validate_collection(
            metadata=self.metadata(),
            samples=samples,
        )

        self.assertFalse(result.valid)
        self.assertIn("run_id_mismatch", self.codes(result))

    def test_migration_must_be_disabled(self):
        metadata = self.metadata()
        metadata["migration_enabled"] = True

        result = validate_collection(
            metadata=metadata,
            samples=self.valid_samples(),
        )

        self.assertFalse(result.valid)
        self.assertIn("migration_enabled", self.codes(result))

    def test_coverage_below_threshold(self):
        samples = self.valid_samples()
        samples.pop()

        result = validate_collection(
            metadata=self.metadata(),
            samples=samples,
        )

        self.assertFalse(result.valid)
        self.assertIn(
            "coverage_below_threshold",
            self.codes(result),
        )

    def test_safe_capacity_must_remain_constant(self):
        samples = self.valid_samples()
        samples[1]["safe_capacity_pps"] = 101.0
        samples[1]["processed_packet_in_rate"] = 50.5
        samples[1]["utilization"] = 0.5

        result = validate_collection(
            metadata=self.metadata(),
            samples=samples,
        )

        self.assertFalse(result.valid)
        self.assertIn(
            "safe_capacity_inconsistent",
            self.codes(result),
        )


if __name__ == "__main__":
    unittest.main()
