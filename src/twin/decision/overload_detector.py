"""Early overload-risk rule used before any migration is considered.

upper_bound = predicted_utilization + error_margin
risk        = upper_bound >= threshold            (threshold = 1.0 by default)

error_margin is the forecaster's measured error (e.g. P95 absolute error), so
the controller is flagged even when the forecast itself is still below 1.0.
Utilization is never clamped: predicted values above 1.0 are valid inputs.
"""
from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import asdict, dataclass

# Absorbs float error so 0.95 + 0.05 is treated as exactly 1.0.
_EPSILON = 1e-9


@dataclass(frozen=True)
class OverloadAssessment:
    controller_id: str
    predicted_utilization: float
    error_margin: float
    upper_bound: float
    threshold: float
    risk: bool

    def to_dict(self) -> dict[str, float | str | bool]:
        return asdict(self)


def assess_overload(
    predicted_utilization: float,
    error_margin: float,
    threshold: float = 1.0,
    controller_id: str = "",
) -> OverloadAssessment:
    if not (math.isfinite(predicted_utilization) and math.isfinite(error_margin)):
        raise ValueError("predicted_utilization and error_margin must be finite")
    if predicted_utilization < 0:
        raise ValueError("predicted_utilization must be >= 0")
    if error_margin < 0:
        raise ValueError("error_margin must be >= 0")
    if threshold <= 0:
        raise ValueError("threshold must be > 0")

    upper_bound = predicted_utilization + error_margin
    return OverloadAssessment(
        controller_id=controller_id,
        predicted_utilization=predicted_utilization,
        error_margin=error_margin,
        upper_bound=upper_bound,
        threshold=threshold,
        risk=upper_bound >= threshold - _EPSILON,
    )


class OverloadDetector:
    def __init__(self, threshold: float = 1.0) -> None:
        if threshold <= 0:
            raise ValueError("threshold must be > 0")
        self.threshold = threshold

    def assess(
        self,
        controller_id: str,
        predicted_utilization: float,
        error_margin: float,
    ) -> OverloadAssessment:
        return assess_overload(
            predicted_utilization,
            error_margin,
            threshold=self.threshold,
            controller_id=controller_id,
        )

    def assess_many(
        self,
        predicted_utilization: Mapping[str, float],
        error_margin: float | Mapping[str, float],
    ) -> dict[str, OverloadAssessment]:
        """Assess every controller; margin may be one value or one per controller."""
        results: dict[str, OverloadAssessment] = {}

        for controller_id, predicted in predicted_utilization.items():
            if isinstance(error_margin, Mapping):
                margin = error_margin[controller_id]
            else:
                margin = error_margin
            results[controller_id] = self.assess(controller_id, predicted, margin)

        return results
