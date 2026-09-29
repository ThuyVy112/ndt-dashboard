from __future__ import annotations

from dataclasses import dataclass
from abc import ABC, abstractmethod


@dataclass(frozen=True)
class WorkloadPoint:
    elapsed_seconds: float
    target_utilization: float
    phase: str


class WorkloadProfile(ABC):
    @abstractmethod
    def target_at(self, elapsed_seconds: float) -> WorkloadPoint:
        """Return the target workload state at the given elapsed time."""
        raise NotImplementedError