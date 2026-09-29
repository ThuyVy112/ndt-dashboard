from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class RuntimeLatency:
    collection_p95_ms: float
    decision_p95_ms: float | None
    migration_p95_ms: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ForecastHorizon:
    required_lead_time_seconds: float
    horizon_steps: int
    effective_horizon_seconds: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def estimate_horizon(
    runtime_latency: RuntimeLatency,
    step_seconds: float,
) -> ForecastHorizon:
    if runtime_latency.decision_p95_ms is None:
        raise ValueError(
            "decision_p95_ms is required before the final "
            "forecast horizon can be estimated"
        )

    if (
        not math.isfinite(step_seconds)
        or step_seconds <= 0
    ):
        raise ValueError(
            "step_seconds must be a positive finite number"
        )

    components = (
        runtime_latency.collection_p95_ms,
        runtime_latency.decision_p95_ms,
        runtime_latency.migration_p95_ms,
    )

    if any(
        not math.isfinite(value) or value < 0
        for value in components
    ):
        raise ValueError(
            "runtime latency values must be finite "
            "and non-negative"
        )

    required_lead_time_seconds = (
        sum(components) / 1000.0
    )

    horizon_steps = math.ceil(
        required_lead_time_seconds / step_seconds
    )

    effective_horizon_seconds = (
        horizon_steps * step_seconds
    )

    return ForecastHorizon(
        required_lead_time_seconds=(
            required_lead_time_seconds
        ),
        horizon_steps=horizon_steps,
        effective_horizon_seconds=(
            effective_horizon_seconds
        ),
    )