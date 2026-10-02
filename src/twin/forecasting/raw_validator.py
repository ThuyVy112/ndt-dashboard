from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from src.schemas.forecasting import ForecastRawSample


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    message: str
    controller_id: str | None = None
    snapshot_id: str | None = None


@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    total_samples: int
    invalid_snapshot_count: int
    duplicate_count: int
    sampling_gap_count: int
    issues: tuple[ValidationIssue, ...]


def validate_raw_samples(
    samples: Iterable[ForecastRawSample | Mapping[str, Any]],
    expected_sampling_interval_seconds: float = 1.0,
) -> ValidationResult:
    """Validate raw forecast samples without dropping invalid samples."""
    try:
        expected_interval = float(expected_sampling_interval_seconds)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            "expected_sampling_interval_seconds must be positive"
        ) from exc

    if not math.isfinite(expected_interval) or expected_interval <= 0:
        raise ValueError(
            "expected_sampling_interval_seconds must be positive"
        )

    issues: list[ValidationIssue] = []
    grouped_samples: dict[str, list[tuple[int, Any, str | None]]] = defaultdict(list)
    total_samples = 0
    invalid_snapshot_count = 0
    duplicate_count = 0
    sampling_gap_count = 0

    for index, sample in enumerate(samples):
        total_samples += 1
        controller_id = _text_value(sample, "controller_id")
        snapshot_id = _text_value(sample, "snapshot_id")
        observed_at = _value(sample, "observed_at")

        if not controller_id:
            issues.append(
                ValidationIssue(
                    code="controller_id_empty",
                    message="controller_id must not be empty",
                    snapshot_id=snapshot_id,
                )
            )

        if not snapshot_id:
            issues.append(
                ValidationIssue(
                    code="snapshot_id_empty",
                    message="snapshot_id must not be empty",
                    controller_id=controller_id or None,
                )
            )

        safe_capacity = _number_value(sample, "safe_capacity_pps")
        if safe_capacity is None or not math.isfinite(safe_capacity) or safe_capacity <= 0:
            issues.append(
                ValidationIssue(
                    code="safe_capacity_invalid",
                    message="safe_capacity_pps must be finite and positive",
                    controller_id=controller_id or None,
                    snapshot_id=snapshot_id or None,
                )
            )

        utilization = _number_value(sample, "utilization")
        if utilization is None or not math.isfinite(utilization) or utilization < 0:
            issues.append(
                ValidationIssue(
                    code="utilization_invalid",
                    message="utilization must be finite and non-negative",
                    controller_id=controller_id or None,
                    snapshot_id=snapshot_id or None,
                )
            )

        if _value(sample, "snapshot_valid") is False:
            invalid_snapshot_count += 1
            issues.append(
                ValidationIssue(
                    code="snapshot_invalid",
                    message="snapshot_valid is false",
                    controller_id=controller_id or None,
                    snapshot_id=snapshot_id or None,
                )
            )

        if controller_id and observed_at is not None:
            grouped_samples[controller_id].append(
                (index, observed_at, snapshot_id or None)
            )

    for controller_id, controller_samples in grouped_samples.items():
        previous_timestamp: datetime | None = None
        for _, observed_at, sample_snapshot_id in controller_samples:
            timestamp = _parse_timestamp(observed_at)
            if timestamp is None:
                issues.append(
                    ValidationIssue(
                        code="timestamp_invalid",
                        message="observed_at must be a valid timestamp",
                        controller_id=controller_id,
                        snapshot_id=sample_snapshot_id,
                    )
                )
                continue

            if previous_timestamp is not None:
                interval = (timestamp - previous_timestamp).total_seconds()
                if interval <= 0:
                    duplicate = interval == 0
                    if duplicate:
                        duplicate_count += 1
                    issues.append(
                        ValidationIssue(
                            code="duplicate" if duplicate else "timestamp_not_monotonic",
                            message=(
                                "duplicate timestamp for controller"
                                if duplicate
                                else "timestamps must be strictly increasing"
                            ),
                            controller_id=controller_id,
                            snapshot_id=sample_snapshot_id,
                        )
                    )
                else:
                    interval_tolerance = expected_interval * 0.10
                    lower_bound = expected_interval - interval_tolerance
                    upper_bound = expected_interval + interval_tolerance
                    gap_threshold = expected_interval * 1.50

                    if interval > gap_threshold:
                        sampling_gap_count += 1
                        issues.append(
                            ValidationIssue(
                                code="sampling_gap",
                                message=(
                                    f"sampling gap is {interval:g}s; "
                                    f"threshold is {gap_threshold:g}s"
                                ),
                                controller_id=controller_id,
                                snapshot_id=sample_snapshot_id,
                            )
                        )
                    elif interval < lower_bound or interval > upper_bound:
                        issues.append(
                            ValidationIssue(
                                code="sampling_interval",
                                message=(
                                    f"expected sampling interval "
                                    f"{expected_interval:g}s +/-10%, "
                                    f"got {interval:g}s"
                                ),
                                controller_id=controller_id,
                                snapshot_id=sample_snapshot_id,
                            )
                        )

            previous_timestamp = timestamp

    return ValidationResult(
        valid=not issues,
        total_samples=total_samples,
        invalid_snapshot_count=invalid_snapshot_count,
        duplicate_count=duplicate_count,
        sampling_gap_count=sampling_gap_count,
        issues=tuple(issues),
    )


def _value(sample: ForecastRawSample | Mapping[str, Any], name: str) -> Any:
    if isinstance(sample, Mapping):
        return sample.get(name)
    return getattr(sample, name, None)


def _text_value(
    sample: ForecastRawSample | Mapping[str, Any],
    name: str,
) -> str:
    value = _value(sample, name)
    return value.strip() if isinstance(value, str) else ""


def _number_value(
    sample: ForecastRawSample | Mapping[str, Any],
    name: str,
) -> float | None:
    value = _value(sample, name)
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_timestamp(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None