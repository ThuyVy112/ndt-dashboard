from __future__ import annotations

from .profile import WorkloadPoint, WorkloadProfile


class HotSwitchWorkload(WorkloadProfile):
    def __init__(
        self,
        target_utilization: float = 0.80,
        hot_switch_id: str = "s1",
        hot_switch_share: float = 0.55, # just generation target, not actual hot switch share, because actual hot switch share is determined by the controller and may be different from the target
        # acceptance criteria: maxSwitchShare_hot > maxSwitchShare_stable,
    ) -> None:
        self.target_utilization = target_utilization
        self.hot_switch_id = hot_switch_id
        self.hot_switch_share = hot_switch_share

    def target_at(
        self,
        elapsed_seconds: float,
    ) -> WorkloadPoint:
        return WorkloadPoint(
            elapsed_seconds=elapsed_seconds,
            target_utilization=self.target_utilization,
            phase="hot_switch",
            hot_switch_id=self.hot_switch_id,
            hot_switch_share=self.hot_switch_share,
        )