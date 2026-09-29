from __future__ import annotations

import math
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class WorkloadPoint:
    elapsed_seconds: float
    target_utilization: float
    phase: str
    hot_switch_id: str | None = None
    hot_switch_share: float | None = None # as hot_switch needs more information, we can add more fields to this class in the future
    # if only target_utilization,  runner does not know which switch is hot, so we need to add hot_switch_id and hot_switch_share to this class
    def __post_init__(self) -> None:
        if not math.isfinite(self.elapsed_seconds):
            raise ValueError("elapsed_seconds must be finite")

        if self.elapsed_seconds < 0:
            raise ValueError(
                "elapsed_seconds must be non-negative"
            )

        if not math.isfinite(self.target_utilization):
            raise ValueError(
                "target_utilization must be finite"
            )

        if self.target_utilization < 0:
            raise ValueError(
                "target_utilization must be non-negative"
            )

        if not self.phase.strip():
            raise ValueError("phase must not be empty")

        if (self.hot_switch_id is None) != (self.hot_switch_share is None):
            raise ValueError(
                "hot_switch_id and hot_switch_share must be provided together"
            )

        if self.hot_switch_id is not None:
            if not self.hot_switch_id.strip():
                raise ValueError("hot_switch_id must not be empty")

        if self.hot_switch_share is not None:
            if not math.isfinite(self.hot_switch_share):
                raise ValueError("hot_switch_share must be finite")
            if not 0.0 <= self.hot_switch_share <= 1.0:
                raise ValueError("hot_switch_share must be in [0, 1]")


class WorkloadProfile(ABC):
    @abstractmethod
    def target_at(
        self,
        elapsed_seconds: float,
    ) -> WorkloadPoint:
        """Return target workload at elapsed_seconds."""
        raise NotImplementedError