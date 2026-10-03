import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.experiments.runners.forecast_data_runner import (
    ForecastDataRunner,
    ForecastRunConfig,
)


class ForecastRunMetadataTests(unittest.TestCase):
    def test_official_provenance_is_serialized(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_id = "forecast-stable-2c20s-r01"

            config = ForecastRunConfig(
                workload_type="stable",
                duration_seconds=180.0,
                sampling_interval_seconds=1.0,
                controller_ids=("c1", "c2"),
                output_dir=Path(tmp),
                run_id=run_id,
                experiment_type="forecast-dataset-2c20s",
                topology="capacity_2c20s",
                repeat_index=1,
                seed=101,
                capacity_artifact=(
                    "data/benchmarks/controller_capacity.json"
                ),
                git_commit="abc123",
            )

            def twin_state_provider() -> dict[str, Any]:
                return {}

            def unused_workload_step(_: float) -> Any:
                raise AssertionError(
                    "workload_step must not be called by metadata test"
                )

            runner = ForecastDataRunner(
                config=config,
                twin_state_provider=twin_state_provider,
                workload_step=unused_workload_step,
            )

            run_dir = Path(tmp) / run_id
            run_dir.mkdir()

            started_at = datetime(
                2026,
                10,
                3,
                1,
                2,
                3,
                tzinfo=timezone.utc,
            )

            runner._write_metadata(
                run_dir,
                run_id,
                started_at=started_at,
            )

            metadata = json.loads(
                (run_dir / "metadata.json").read_text(
                    encoding="utf-8"
                )
            )

            self.assertEqual(
                metadata["schema_version"],
                "1.0",
            )
            self.assertEqual(
                metadata["run_id"],
                run_id,
            )
            self.assertEqual(
                metadata["experiment_type"],
                "forecast-dataset-2c20s",
            )
            self.assertEqual(
                metadata["topology"],
                "capacity_2c20s",
            )
            self.assertEqual(
                metadata["workload_type"],
                "stable",
            )
            self.assertEqual(
                metadata["repeat_index"],
                1,
            )
            self.assertEqual(
                metadata["seed"],
                101,
            )
            self.assertEqual(
                metadata["duration_seconds"],
                180.0,
            )
            self.assertEqual(
                metadata["sampling_interval_seconds"],
                1.0,
            )
            self.assertEqual(
                metadata["controllers"],
                ["c1", "c2"],
            )
            self.assertFalse(
                metadata["migration_enabled"]
            )
            self.assertEqual(
                metadata["git_commit"],
                "abc123",
            )
            self.assertEqual(
                metadata["capacity_artifact"],
                "data/benchmarks/controller_capacity.json",
            )

            self.assertEqual(
                metadata["started_at"],
                started_at.isoformat(),
            )
            self.assertIsNone(
                metadata["ended_at"]
            )

            ended_at = datetime(
                2026,
                10,
                3,
                1,
                5,
                4,
                tzinfo=timezone.utc,
            )

            runner._complete_metadata(
                run_dir=run_dir,
                ended_at=ended_at,
            )

            completed_metadata = json.loads(
                (run_dir / "metadata.json").read_text(
                    encoding="utf-8"
                )
            )

            self.assertEqual(
                completed_metadata["started_at"],
                started_at.isoformat(),
            )
            self.assertEqual(
                completed_metadata["ended_at"],
                ended_at.isoformat(),
            )


if __name__ == "__main__":
    unittest.main()
