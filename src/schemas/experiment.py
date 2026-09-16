from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Dict, Optional


@dataclass
class ExperimentMetadata:
    """
    Metadata describing one reproducible experiment run.

    Timing model:

        started_at
            |
            | warmup
            v
        measurement_started_at
            |
            | measurement
            v
        measurement_ended_at
            |
            | cooldown
            v
        ended_at

    Only samples inside the measurement window should be used
    for experiment aggregation and capacity evaluation.
    """

    # =========================================================
    # Schema / run identity
    # =========================================================

    schema_version: str

    run_id: str
    experiment_type: str

    # =========================================================
    # Experiment target
    # =========================================================

    target_controller: str
    topology: str

    controller_count: int
    switch_count: int

    # =========================================================
    # Workload configuration
    # =========================================================

    workload_pattern: str
    target_new_flow_rate: float

    source_host: str
    source_ip: str

    target_host: str
    target_ip: str

    protocol: str
    target_port: int

    workload_sample_interval_seconds: float
    benchmark_idle_timeout_seconds: float

    # =========================================================
    # Telemetry configuration
    # =========================================================

    telemetry_interval_seconds: float

    # =========================================================
    # Experiment timing
    # =========================================================

    warmup_seconds: float
    measurement_seconds: float
    cooldown_seconds: float

    # =========================================================
    # Reproducibility
    # =========================================================

    repeat_index: int
    seed: int

    git_commit: str

    # =========================================================
    # Runtime timestamps
    # =========================================================

    started_at: datetime

    measurement_started_at: Optional[datetime] = None
    measurement_ended_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None

    def __post_init__(self) -> None:
        """
        Validate static experiment metadata.

        Runtime timestamp ordering is validated only when the
        corresponding timestamp has already been assigned.
        """

        if not self.schema_version.strip():
            raise ValueError(
                "schema_version must not be empty"
            )

        if not self.run_id.strip():
            raise ValueError(
                "run_id must not be empty"
            )

        if not self.experiment_type.strip():
            raise ValueError(
                "experiment_type must not be empty"
            )

        if not self.target_controller.strip():
            raise ValueError(
                "target_controller must not be empty"
            )

        if not self.topology.strip():
            raise ValueError(
                "topology must not be empty"
            )

        if not self.workload_pattern.strip():
            raise ValueError(
                "workload_pattern must not be empty"
            )

        if not self.source_ip.strip():
            raise ValueError(
                "source_ip must not be empty"
            )

        if not self.target_ip.strip():
            raise ValueError(
                "target_ip must not be empty"
            )

        if not self.git_commit.strip():
            raise ValueError(
                "git_commit must not be empty"
            )

        if self.controller_count <= 0:
            raise ValueError(
                "controller_count must be > 0"
            )

        if self.switch_count <= 0:
            raise ValueError(
                "switch_count must be > 0"
            )

        if self.target_new_flow_rate <= 0:
            raise ValueError(
                "target_new_flow_rate must be > 0"
            )

        if not self.source_host.strip():
            raise ValueError(
                "source_host must not be empty"
            )

        if not self.target_host.strip():
            raise ValueError(
                "target_host must not be empty"
            )

        if not self.protocol.strip():
            raise ValueError(
                "protocol must not be empty"
            )

        if not 1 <= self.target_port <= 65535:
            raise ValueError(
                "target_port must be in [1, 65535]"
            )

        if (
            self.workload_sample_interval_seconds
            <= 0
        ):
            raise ValueError(
                "workload_sample_interval_seconds "
                "must be > 0"
            )

        if (
            self.benchmark_idle_timeout_seconds
            <= 0
        ):
            raise ValueError(
                "benchmark_idle_timeout_seconds "
                "must be > 0"
            )

        if self.telemetry_interval_seconds <= 0:
            raise ValueError(
                "telemetry_interval_seconds "
                "must be > 0"
            )

        if self.warmup_seconds < 0:
            raise ValueError(
                "warmup_seconds must be >= 0"
            )

        if self.measurement_seconds <= 0:
            raise ValueError(
                "measurement_seconds must be > 0"
            )

        if self.cooldown_seconds < 0:
            raise ValueError(
                "cooldown_seconds must be >= 0"
            )

        if self.repeat_index <= 0:
            raise ValueError(
                "repeat_index must be > 0"
            )

        if self.seed < 0:
            raise ValueError(
                "seed must be >= 0"
            )

        self._validate_runtime_timestamps()

    def _validate_runtime_timestamps(
        self,
    ) -> None:
        """
        Validate timestamps that are already available.

        Metadata is intentionally mutable because the runner
        progressively fills measurement_started_at,
        measurement_ended_at and ended_at.
        """

        if (
            self.measurement_started_at is not None
            and self.measurement_started_at
            < self.started_at
        ):
            raise ValueError(
                "measurement_started_at "
                "must be >= started_at"
            )

        if (
            self.measurement_started_at is not None
            and self.measurement_ended_at is not None
            and self.measurement_ended_at
            < self.measurement_started_at
        ):
            raise ValueError(
                "measurement_ended_at must be >= "
                "measurement_started_at"
            )

        if (
            self.measurement_ended_at is not None
            and self.ended_at is not None
            and self.ended_at
            < self.measurement_ended_at
        ):
            raise ValueError(
                "ended_at must be >= "
                "measurement_ended_at"
            )

        if (
            self.ended_at is not None
            and self.ended_at < self.started_at
        ):
            raise ValueError(
                "ended_at must be >= started_at"
            )

    @property
    def workload_duration_seconds(
        self,
    ) -> float:
        """
        Workload is generated during warmup + measurement.

        Cooldown happens after workload generation stops.
        """

        return (
            self.warmup_seconds
            + self.measurement_seconds
        )

    @property
    def total_run_duration_seconds(
        self,
    ) -> float:
        return (
            self.warmup_seconds
            + self.measurement_seconds
            + self.cooldown_seconds
        )

    def to_dict(self) -> Dict[str, Any]:
        self._validate_runtime_timestamps()

        payload = asdict(self)

        for key in (
            "started_at",
            "measurement_started_at",
            "measurement_ended_at",
            "ended_at",
        ):
            value = payload[key]

            if value is not None:
                payload[key] = value.isoformat()

        # Derived values are stored for easier inspection,
        # but they are not independent configuration fields.
        payload[
            "workload_duration_seconds"
        ] = self.workload_duration_seconds

        payload[
            "total_run_duration_seconds"
        ] = self.total_run_duration_seconds

        return payload