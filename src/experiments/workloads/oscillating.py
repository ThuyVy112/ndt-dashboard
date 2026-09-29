from __future__ import annotations

import math

from .profile import WorkloadPoint, WorkloadProfile


class OscillatingWorkload(WorkloadProfile):
    def __init__(
        self,
        baseline: float = 0.70,
        amplitude: float = 0.20,
        period_seconds: float = 20.0,
    ) -> None:
        if period_seconds <= 0:
            raise ValueError(
                "period_seconds must be positive"
            )

        self.baseline = baseline
        self.amplitude = amplitude
        self.period_seconds = period_seconds

    def target_at(
        self,
        elapsed_seconds: float,
    ) -> WorkloadPoint:

        utilization = (
            self.baseline
            + self.amplitude
            * math.sin(
                2.0
                * math.pi
                * elapsed_seconds
                / self.period_seconds
            )
        )

        return WorkloadPoint(
            elapsed_seconds=elapsed_seconds,
            target_utilization=utilization,
            phase="oscillating",
        )