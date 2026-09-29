from __future__ import annotations

from .profile import WorkloadPoint, WorkloadProfile


class StableWorkload(WorkloadProfile):
    def __init__(
        self,
        target_utilization: float = 0.60, # default to 60% utilization for stable workload, can override with other values
    ) -> None:
        self.target_utilization = target_utilization

    def target_at(
        self,
        elapsed_seconds: float,
    ) -> WorkloadPoint:
        return WorkloadPoint(
            elapsed_seconds=elapsed_seconds,
            target_utilization=self.target_utilization,
            phase="stable",
        )