"""
Orchestrator: This module runs a forecast data collection pipeline:
config --> profile.target_at(t) --> target utilization --> CapacityWorkloadMapper --> offered flows/s --> workload generator --> GET TwinState every 1 s --> ForecastRawSample --> forecast_samples.jsonl
"""
from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from src.experiments.workloads.profile import WorkloadPoint
from src.schemas.forecasting import ForecastRawSample
from src.twin.forecasting.raw_validator import validate_raw_samples


@dataclass(frozen=True)
class ForecastRunConfig:
    workload_type: str
    duration_seconds: float
    sampling_interval_seconds: float
    controller_ids: tuple[str, ...]
    output_dir: Path
    run_id: str | None = None


class ForecastDataRunner:
    def __init__(
        self,
        config: ForecastRunConfig,
        twin_state_provider: Callable[[], dict[str, Any]],
        workload_step: Callable[[float], WorkloadPoint],
    ) -> None:
        self.config = config
        self.twin_state_provider = twin_state_provider
        self.workload_step = workload_step

    def run(self) -> Path:
        run_id = self.config.run_id or (
            f"{self.config.workload_type}-"
            f"{uuid.uuid4().hex[:8]}"
        )

        run_dir = self.config.output_dir / run_id
        if self.config.run_id is None:
            run_dir.mkdir(parents=True, exist_ok=False)
        else:
            run_dir.mkdir(parents=True, exist_ok=True)

        samples: list[ForecastRawSample] = []

        self._write_metadata(
            run_dir,
            run_id,
        )

        start_monotonic = time.monotonic()
        next_sample_at = start_monotonic

        while True:
            now = time.monotonic()
            elapsed = now - start_monotonic

            if elapsed >= self.config.duration_seconds:
                break

            if now < next_sample_at:
                time.sleep(
                    min(
                        next_sample_at - now,
                        0.05,
                    )
                )
                continue

            workload_point = self.workload_step(elapsed)

            twin_state = self.twin_state_provider()

            observed_at = datetime.now(timezone.utc)

            current_samples = self._samples_from_twin_state(
                run_id=run_id,
                observed_at=observed_at,
                twin_state=twin_state,
                workload_point=workload_point,
            )

            samples.extend(current_samples)

            for sample in current_samples:
                self._append_jsonl(
                    run_dir / "forecast_samples.jsonl",
                    sample.to_dict(),
                )

            next_sample_at += (
                self.config.sampling_interval_seconds
            )

        self._finalize(
            run_dir=run_dir,
            samples=samples,
        )

        return run_dir

    def _samples_from_twin_state(
        self,
        *,
        run_id: str,
        observed_at: datetime,
        twin_state: dict[str, Any],
        workload_point: WorkloadPoint,
    ) -> list[ForecastRawSample]:
        samples: list[ForecastRawSample] = []

        snapshot_id = str(twin_state.get("snapshot_id", ""))
        quality = twin_state.get("quality", {})
        controllers = twin_state.get("controllers", [])
        switches = twin_state.get("switches", [])
        ownership = twin_state.get("ownership", [])

        owner_by_switch = {
            str(item["switch_id"]): str(item["owner_controller_id"])
            for item in ownership
        }

        for controller in controllers:
            controller_id = str(controller["controller_id"])
            if controller_id not in self.config.controller_ids:
                continue
            owned_switch_load_shares = [
                float(switch.get("control_load_share", 0.0))
                for switch in switches
                if str(switch.get("controller_id", "")) == controller_id
                and owner_by_switch.get(
                    str(switch.get("switch_id", ""))
                ) == controller_id
            ]

            max_switch_control_load_share = max(
                owned_switch_load_shares,
                default=0.0,
            )

            samples.append(
                ForecastRawSample(
                    run_id=run_id,
                    controller_id=controller_id,
                    observed_at=observed_at,
                    workload_type=self.config.workload_type,
                    workload_phase=workload_point.phase,
                    processed_packet_in_rate=float(
                        controller["processed_packet_in_rate"]
                    ),
                    flow_mod_rate=float(controller.get("flow_mod_rate", 0.0)),
                    process_cpu_percent=float(
                        controller.get("process_cpu_percent", 0.0)
                    ),
                    process_memory_rss_mb=float(
                        controller.get("process_memory_rss_mb", 0.0)
                    ),
                    response_p95_ms=float(
                        controller.get("response_p95_ms", 0.0)
                    ),
                    managed_switch_count=int(
                        controller.get("managed_switch_count", 0)
                    ),
                    safe_capacity_pps=float(controller["safe_capacity_pps"]),
                    utilization=float(controller["utilization"]),
                    max_switch_control_load_share=float(
                        max_switch_control_load_share
                    ),
                    age_of_twin_ms=float(quality.get("age_of_twin_ms", 0.0)),
                    twinning_rate=float(quality.get("twinning_rate", 0.0)),
                    completeness_ratio=float(
                        quality.get("completeness_ratio", 0.0)
                    ),
                    synchronization_jitter_ms=float(
                        quality.get("synchronization_jitter_ms", 0.0)
                    ),
                    snapshot_valid=bool(quality.get("valid", False)),
                    snapshot_id=snapshot_id,
                )
            )

        return samples

    @staticmethod
    def _append_jsonl(
        path: Path,
        value: dict[str, Any],
    ) -> None:
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(value) + "\n")

    def _write_metadata(
        self,
        run_dir: Path,
        run_id: str,
    ) -> None:
        metadata = {
            "schema_version": "1.0",
            "run_id": run_id,
            "workload_type": self.config.workload_type,
            "duration_seconds": self.config.duration_seconds,
            "sampling_interval_seconds": self.config.sampling_interval_seconds,
            "controllers": list(self.config.controller_ids),
            "migration_enabled": False,
        }
        (run_dir / "metadata.json").write_text(
            json.dumps(metadata, indent=2) + "\n",
            encoding="utf-8",
        )

    def _finalize(
        self,
        *,
        run_dir: Path,
        samples: list[ForecastRawSample],
    ) -> None:
        validation = validate_raw_samples(
            samples,
            expected_sampling_interval_seconds=(
                self.config.sampling_interval_seconds
            ),
        )

        validation_payload = {
            "valid": validation.valid,
            "total_samples": validation.total_samples,
            "invalid_snapshot_count": validation.invalid_snapshot_count,
            "duplicate_count": validation.duplicate_count,
            "sampling_gap_count": validation.sampling_gap_count,
            "issues": [
                {
                    "code": issue.code,
                    "message": issue.message,
                    "controller_id": issue.controller_id,
                    "snapshot_id": issue.snapshot_id,
                }
                for issue in validation.issues
            ],
        }
        (run_dir / "validation.json").write_text(
            json.dumps(validation_payload, indent=2) + "\n",
            encoding="utf-8",
        )

        controller_counts: dict[str, int] = {}
        for sample in samples:
            controller_counts[sample.controller_id] = (
                controller_counts.get(sample.controller_id, 0) + 1
            )

        summary = {
            "total_samples": len(samples),
            "samples_per_controller": controller_counts,
            "validation_passed": validation.valid,
        }
        (run_dir / "summary.json").write_text(
            json.dumps(summary, indent=2) + "\n",
            encoding="utf-8",
        )
