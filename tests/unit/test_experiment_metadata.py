from __future__ import annotations

import unittest
from datetime import datetime, timezone

from src.schemas.experiment import (
    ExperimentMetadata,
)


class ExperimentMetadataTests(
    unittest.TestCase
):
    def test_serialization(
        self,
    ):
        started_at = datetime(
            2026,
            9,
            12,
            0,
            0,
            tzinfo=timezone.utc,
        )

        metadata = ExperimentMetadata(
            schema_version="1.0",
            run_id="capacity-smoke-c1-10-r01",
            experiment_type="capacity-smoke",
            target_controller="c1",
            topology="smoke_2c4s",
            controller_count=2,
            switch_count=4,
            workload_pattern="stable",
            target_new_flow_rate=10.0,
            source_host="h1",
            source_ip="10.0.0.1",
            target_host="h2",
            target_ip="10.0.0.2",
            protocol="udp",
            target_port=9000,
            workload_sample_interval_seconds=1.0,
            benchmark_idle_timeout_seconds=5.0,
            telemetry_interval_seconds=1.0,
            warmup_seconds=5.0,
            measurement_seconds=20.0,
            cooldown_seconds=5.0,
            repeat_index=1,
            seed=1,
            git_commit="abc123",
            started_at=started_at,
        )

        data = metadata.to_dict()

        self.assertEqual(
            data["run_id"],
            "capacity-smoke-c1-10-r01",
        )

        self.assertEqual(
            data["started_at"],
            "2026-09-12T00:00:00+00:00",
        )

        self.assertIsNone(
            data["measurement_started_at"]
        )


if __name__ == "__main__":
    unittest.main()