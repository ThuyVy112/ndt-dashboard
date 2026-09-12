from __future__ import annotations
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Optional


@dataclass(frozen=True)
class ExperimentMetadata:
    schema_version: str

    run_id: str
    experiment_type: str

    controller_count: int
    switch_count: int

    topology: str
    workload_pattern: str
    protocol: str

    target_controller: str
    target_port: int

    source_host: str
    target_host: str
    source_ip: str
    target_ip: str

    target_new_flow_rate: float

    duration_seconds: float
    sample_interval_seconds: float

    benchmark_idle_timeout_seconds: float
    telemetry_interval_seconds: float

    warmup_seconds: float
    measurement_seconds: float
    cooldown_seconds: float

    repeat_index: int

    seed: int
    git_commit: str

    started_at: datetime
    measurement_started_at: Optional[datetime] = None
    measurement_ended_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)

        for key in ["started_at", "measurement_started_at", "measurement_ended_at", "ended_at"]:
            value = payload.get(key)
            if value is not None:
                payload[key] = value.isoformat()
        return payload