from __future__ import annotations

from collections import deque
from datetime import (
    datetime,
    timedelta,
    timezone,
)


class TwinningRateTracker:
    def __init__(
        self,
        window_seconds: float,
    ) -> None:

        if window_seconds <= 0:
            raise ValueError(
                "window_seconds must be > 0"
            )

        self.window_seconds = float(
            window_seconds
        )

        self._attempts: deque[tuple[datetime, bool]] = deque()

    def record(
        self,
        success: bool,
        observed_at: datetime | None = None,
    ) -> None:

        now = (
            observed_at
            or datetime.now(timezone.utc)
        )

        self._attempts.append(
            (
                now,
                bool(success),
            )
        )

        self._prune(now)

    def _prune(
        self,
        now: datetime,
    ) -> None:

        threshold = (
            now
            - timedelta(
                seconds=self.window_seconds
            )
        )

        while (
            self._attempts
            and self._attempts[0][0]
            < threshold
        ):
            self._attempts.popleft()

    def rate(
        self,
        now: datetime | None = None,
    ) -> float:

        current = (
            now
            or datetime.now(timezone.utc)
        )

        self._prune(current)

        if not self._attempts:
            return 0.0

        # Count the number of successes in the current window
        successes = sum(
            1
            for _, success
            in self._attempts
            if success
        )

        return (
            successes
            / len(self._attempts)
        )