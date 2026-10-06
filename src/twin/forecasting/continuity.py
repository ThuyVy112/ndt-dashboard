from __future__ import annotations

import math
from collections import Counter
from datetime import datetime
from typing import Iterable, Sequence, Union


# Accepted timestamp inputs (epoch seconds, ISO-8601 text, datetime).
Timestamp = Union[float, int, str, datetime]


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
    # NaN would compare False against every threshold and silently bridge a gap.
    if not math.isfinite(max_gap_seconds) or max_gap_seconds <= 0:
        raise ValueError("max_gap_seconds must be positive")

    values = [_timestamp_seconds(value) for value in timestamps]

    if not all(math.isfinite(value) for value in values):
        raise ValueError("timestamps must be finite")

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


def segment_lengths(segment_ids: Sequence[int]) -> dict[int, int]:
    """Number of observations in each continuity segment."""
    return dict(Counter(segment_ids))


def count_windows(segment_ids: Sequence[int], window_size: int) -> int:
    """Count sliding windows that stay inside one segment.

    A window never crosses a gap, so t=1,2,3,8,9 with window_size=3 yields
    one window (1,2,3), not three windows over five "consecutive" points.
    """
    if window_size <= 0:
        raise ValueError("window_size must be positive")

    return sum(
        max(0, length - window_size + 1)
        for length in segment_lengths(segment_ids).values()
    )


def timestamp_to_seconds(value: Timestamp) -> float:
    """Public conversion to epoch seconds (shared with history.py)."""
    return _timestamp_seconds(value)
