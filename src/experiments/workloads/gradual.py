from __future__ import annotations

from .profile import WorkloadPoint, WorkloadProfile


class GradualWorkload(WorkloadProfile):
    def target_at(
        self,
        elapsed_seconds: float,
    ) -> WorkloadPoint:

        if elapsed_seconds < 10:
            utilization = 0.40
            phase = "u40"
        elif elapsed_seconds < 20:
            utilization = 0.50
            phase = "u50"
        elif elapsed_seconds < 30:
            utilization = 0.60
            phase = "u60"
        elif elapsed_seconds < 40:
            utilization = 0.70
            phase = "u70"
        elif elapsed_seconds < 50:
            utilization = 0.80
            phase = "u80"
        else:
            utilization = 0.95
            phase = "u95"

        return WorkloadPoint(
            elapsed_seconds=elapsed_seconds,
            target_utilization=utilization,
            phase=phase,
        )