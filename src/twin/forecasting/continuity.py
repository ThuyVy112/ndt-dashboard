from __future__ import annotations

from datetime import datetime
from typing import Iterable


def _timestamp_seconds(value: float | int | str | datetime) -> float:
    if isinstance(value, datetime):
        return value.timestamp()

    if isinstance(value, (int, float)):
        return float(value)

    if isinstance(value, str):
        try:
            return datetime.fromisoformat(
                value.replace("Z", "+00:00")
            ).timestamp()
        except ValueError as exc:
            raise ValueError(
                f"invalid timestamp: {value!r}"
            ) from exc

    raise TypeError(
        f"unsupported timestamp type: {type(value).__name__}"
    )


def assign_segments(
    timestamps: Iterable[float | int | str | datetime],
    max_gap_seconds: float,
) -> list[int]:
    """
    Assign a continuity segment ID to ordered timestamps.

    A positive gap greater than max_gap_seconds starts a new segment.
    Duplicate or backwards timestamps are rejected rather than bridged.
    """
    if max_gap_seconds <= 0:
        raise ValueError("max_gap_seconds must be positive")

    values = [_timestamp_seconds(value) for value in timestamps]

    if not values:
        return []

    segments = [0]
    segment_id = 0
    previous = values[0]

    for current in values[1:]:
        delta = current - previous

        if delta <= 0:
            raise ValueError(
                "timestamps must be strictly increasing; "
                "duplicate or backwards timestamp detected"
            )

        if delta > max_gap_seconds:
            segment_id += 1

        segments.append(segment_id)
        previous = current

    return segments
