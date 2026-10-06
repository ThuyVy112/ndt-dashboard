import json
import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from unittest.mock import patch

from scripts.experiments.validate_forecast_collection import (
    validate_run_directory,
)
from src.experiments.runners.forecast_data_runner import (
    ForecastDataRunner,
    ForecastRunConfig,
)
from src.experiments.workloads.profile import WorkloadPoint

RUN_ID = "stable-r01-s101"
CAPACITY = {"c1": 830.912131857993, "c2": 832.9337985006983}
CONTRACT_FIELDS = (
    "run_id",
    "workload_type",
    "repeat",
    "seed",
    "duration_seconds",
    "sampling_interval_seconds",
    "controller_ids",
    "migration_enabled",
    "git_commit",
    "git_tag",
    "safe_capacity_c1",
    "safe_capacity_c2",
    "started_at",
    "finished_at",
    "topology",
)


def write_capacity_artifact(directory: Path) -> Path:
    path = directory / "controller_capacity.json"
    path.write_text(
        json.dumps(
            {"controllers": {cid: {"c_safe_pps": value} for cid, value in CAPACITY.items()}}
        ),
        encoding="utf-8",
    )
    return path


def make_runner(
    directory: Path,
    artifact: Path | None,
    *,
    duration: float = 3.0,
    git_tag: str | None = None,
    twin_state_provider: Any = None,
) -> ForecastDataRunner:
    config = ForecastRunConfig(
        workload_type="stable",
        duration_seconds=duration,
        sampling_interval_seconds=1.0,
        controller_ids=("c1", "c2"),
        output_dir=directory,
        run_id=RUN_ID,
        experiment_type="forecast-dataset-2c20s",
        topology="capacity_2c20s",
        repeat_index=1,
        seed=101,
        capacity_artifact=str(artifact) if artifact else None,
        git_commit="abc1234",
        git_tag=git_tag,
    )
    return ForecastDataRunner(
        config=config,
        twin_state_provider=twin_state_provider or (lambda: {}),
        workload_step=lambda elapsed: WorkloadPoint(elapsed, 0.5, "steady"),
    )


def fake_twin_state() -> dict[str, Any]:
    controllers = [
        {
            "controller_id": cid,
            "processed_packet_in_rate": 100.0,
            "safe_capacity_pps": CAPACITY[cid],
            "utilization": 100.0 / CAPACITY[cid],
            "managed_switch_count": 10,
        }
        for cid in ("c1", "c2")
    ]
    return {
        "snapshot_id": f"snap-{datetime.now(timezone.utc).timestamp()}",
        "controllers": controllers,
        "quality": {
            "age_of_twin_ms": 100.0,
            "twinning_rate": 1.0,
            "completeness_ratio": 1.0,
            "synchronization_jitter_ms": 1.0,
            "valid": True,
        },
    }


class ForecastRunMetadataProvenanceTests(unittest.TestCase):
    def test_metadata_records_tag_and_safe_capacity(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            runner = make_runner(
                directory,
                write_capacity_artifact(directory),
                git_tag="forecast-dataset-v1",
            )
            run_dir = directory / RUN_ID
            run_dir.mkdir()
            runner._write_metadata(run_dir, RUN_ID)

            metadata = json.loads((run_dir / "metadata.json").read_text())

        self.assertEqual(metadata["git_tag"], "forecast-dataset-v1")
        self.assertEqual(metadata["safe_capacity_c1"], CAPACITY["c1"])
        self.assertEqual(metadata["safe_capacity_c2"], CAPACITY["c2"])

    def test_tag_comes_from_environment_when_not_configured(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(
            os.environ, {"FORECAST_GIT_TAG": "from-env"}
        ):
            directory = Path(tmp)
            runner = make_runner(directory, write_capacity_artifact(directory))
            run_dir = directory / RUN_ID
            run_dir.mkdir()
            runner._write_metadata(run_dir, RUN_ID)

            metadata = json.loads((run_dir / "metadata.json").read_text())

        self.assertEqual(metadata["git_tag"], "from-env")

    def test_missing_artifact_omits_capacity_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            runner = make_runner(directory, None)
            run_dir = directory / RUN_ID
            run_dir.mkdir()
            runner._write_metadata(run_dir, RUN_ID)

            metadata = json.loads((run_dir / "metadata.json").read_text())

        self.assertNotIn("safe_capacity_c1", metadata)

    def test_real_runner_output_satisfies_the_metadata_contract(self) -> None:
        # End to end: ForecastDataRunner writes a short run, the validator
        # checks it against the official metadata contract.
        with tempfile.TemporaryDirectory() as tmp, patch.dict(
            os.environ, {"FORECAST_GIT_TAG": "forecast-dataset-v1"}
        ):
            directory = Path(tmp)
            runner = make_runner(
                directory,
                write_capacity_artifact(directory),
                twin_state_provider=fake_twin_state,
            )
            run_dir = runner.run()

            result = validate_run_directory(
                run_dir,
                min_coverage=0.5,
                metadata_required_fields=CONTRACT_FIELDS,
            )

        codes = {issue.code for issue in result.issues}
        self.assertNotIn("metadata_field_missing", codes)
        self.assertNotIn("safe_capacity_metadata_mismatch", codes)
        self.assertNotIn("run_id_format_invalid", codes)


if __name__ == "__main__":
    unittest.main()
