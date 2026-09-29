from __future__ import annotations

from .profile import WorkloadPoint, WorkloadProfile


class BurstWorkload(WorkloadProfile):
    def target_at(
        self,
        elapsed_seconds: float,
    ) -> WorkloadPoint:

        if elapsed_seconds < 15:
            utilization = 0.50
            phase = "baseline_1"

        elif elapsed_seconds < 25:
            utilization = 1.10
            phase = "burst_1"

        elif elapsed_seconds < 45:
            utilization = 0.50
            phase = "recovery"

        elif elapsed_seconds < 55:
            utilization = 1.05
            phase = "burst_2"

        else:
            utilization = 0.50
            phase = "baseline_2"

        return WorkloadPoint(
            elapsed_seconds=elapsed_seconds,
            target_utilization=utilization,
            phase=phase,
        )