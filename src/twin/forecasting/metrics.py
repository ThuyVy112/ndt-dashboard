"""Forecast error metrics (pure Python, no model or dataset required)."""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Sequence


@dataclass(frozen=True)
class ForecastMetrics:
    sample_count: int
    mae: float
    rmse: float
    mape_percent: float
    r2: float
    p95_abs_error: float

    def to_dict(self) -> dict[str, float | int]:
        return asdict(self)


def _validate(y_true: Sequence[float], y_pred: Sequence[float]) -> None:
    if len(y_true) != len(y_pred):
        raise ValueError("y_true and y_pred must have the same length")
    if len(y_true) == 0:
        raise ValueError("inputs must not be empty")
    if not all(math.isfinite(v) for v in (*y_true, *y_pred)):
        raise ValueError("inputs must be finite numbers")


def abs_errors(y_true: Sequence[float], y_pred: Sequence[float]) -> list[float]:
    _validate(y_true, y_pred)
    return [abs(t - p) for t, p in zip(y_true, y_pred)]


def mae(y_true: Sequence[float], y_pred: Sequence[float]) -> float:
    errors = abs_errors(y_true, y_pred)
    return math.fsum(errors) / len(errors)


def rmse(y_true: Sequence[float], y_pred: Sequence[float]) -> float:
    errors = abs_errors(y_true, y_pred)
    return math.sqrt(math.fsum(e * e for e in errors) / len(errors))


def mape_percent(
    y_true: Sequence[float],
    y_pred: Sequence[float],
    epsilon: float = 1e-6,
) -> float:
    """Mean absolute percentage error in percent.

    Points with |y_true| < epsilon are skipped: an idle controller (U ~ 0)
    would otherwise divide by zero and dominate the average.
    """
    _validate(y_true, y_pred)
    ratios = [
        abs(t - p) / abs(t) for t, p in zip(y_true, y_pred) if abs(t) >= epsilon
    ]
    if not ratios:
        raise ValueError("all y_true values are ~0; MAPE is undefined")
    return 100.0 * math.fsum(ratios) / len(ratios)


def r2_score(y_true: Sequence[float], y_pred: Sequence[float]) -> float:
    _validate(y_true, y_pred)
    mean_true = math.fsum(y_true) / len(y_true)
    ss_res = math.fsum((t - p) ** 2 for t, p in zip(y_true, y_pred))
    ss_tot = math.fsum((t - mean_true) ** 2 for t in y_true)
    if ss_tot == 0.0:
        # Constant target: R2 is only meaningful for a perfect prediction.
        return 1.0 if ss_res == 0.0 else float("nan")
    return 1.0 - ss_res / ss_tot


def percentile(values: Sequence[float], q: float) -> float:
    """Percentile with linear interpolation (same rule as numpy default)."""
    if not values:
        raise ValueError("values must not be empty")
    if not 0.0 <= q <= 100.0:
        raise ValueError("q must be in [0, 100]")
    ordered = sorted(values)
    position = (len(ordered) - 1) * q / 100.0
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def p95_abs_error(y_true: Sequence[float], y_pred: Sequence[float]) -> float:
    """95% of predictions are off by at most this much (feeds error_margin)."""
    return percentile(abs_errors(y_true, y_pred), 95.0)


def compute_metrics(
    y_true: Sequence[float],
    y_pred: Sequence[float],
) -> ForecastMetrics:
    return ForecastMetrics(
        sample_count=len(y_true),
        mae=mae(y_true, y_pred),
        rmse=rmse(y_true, y_pred),
        mape_percent=mape_percent(y_true, y_pred),
        r2=r2_score(y_true, y_pred),
        p95_abs_error=p95_abs_error(y_true, y_pred),
    )
