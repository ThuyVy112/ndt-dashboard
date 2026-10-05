"""Per-controller history buffer for the runtime forecaster.

The buffer only ever holds ONE contiguous run of samples. A gap, a backwards
timestamp or a stale duplicate never gets stitched into the history: a gap
clears the buffer so the forecaster reports NOT_READY until enough fresh,
consecutive samples have arrived again.
"""
from __future__ import annotations

import threading
from collections import deque
from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping

from src.twin.forecasting.continuity import Timestamp, timestamp_to_seconds

READY = "READY"
NOT_READY = "NOT_READY"

# Same limit as the dataset (configs: validation.max_gap_seconds) and as
# continuity.assign_segments in the training pipeline. Using one value keeps
# runtime history identical to what the model saw while training.
DEFAULT_MAX_GAP_SECONDS = 2.5

# Same tolerance as continuity.assign_segments.
_EPSILON = 1e-9


class AppendStatus(str, Enum):
    APPENDED = "APPENDED"
    REJECTED_INVALID_SNAPSHOT = "REJECTED_INVALID_SNAPSHOT"
    REJECTED_DUPLICATE = "REJECTED_DUPLICATE"
    RESET_GAP = "RESET_GAP"
    RESET_OUT_OF_ORDER = "RESET_OUT_OF_ORDER"


class HistoryNotReadyError(RuntimeError):
    pass


@dataclass(frozen=True)
class HistoryEntry:
    controller_id: str
    observed_at: float  # epoch seconds
    snapshot_id: str
    row: Mapping[str, Any]  # TwinState controller row (frozen week-6 contract)


class TwinHistoryBuffer:
    def __init__(
        self,
        history_steps: int = 10,
        safety_buffer: int = 5,
        max_gap_seconds: float = DEFAULT_MAX_GAP_SECONDS,
    ) -> None:
        if history_steps <= 0 or safety_buffer < 0:
            raise ValueError("invalid history_steps / safety_buffer")
        if max_gap_seconds <= 0:
            raise ValueError("max_gap_seconds must be > 0")
        self.history_steps = history_steps
        self.safety_buffer = safety_buffer
        self.max_gap_seconds = max_gap_seconds
        self._buffers: dict[str, deque[HistoryEntry]] = {}
        self._lock = threading.Lock()  # orchestrator polls from a thread

    def append(
        self,
        controller_id: str,
        observed_at: Timestamp,
        snapshot_id: str,
        row: Mapping[str, Any],
        *,
        snapshot_valid: bool = True,
    ) -> AppendStatus:
        """Add one TwinState row. Returns what happened to the buffer."""
        # Invalid snapshots are never stored. A hole longer than max_gap_seconds
        # is caught by the gap check on the next valid sample, so history
        # cannot silently bridge it.
        if not snapshot_valid:
            return AppendStatus.REJECTED_INVALID_SNAPSHOT

        timestamp = timestamp_to_seconds(observed_at)
        entry = HistoryEntry(controller_id, timestamp, snapshot_id, row)

        with self._lock:
            buffer = self._buffers.setdefault(
                controller_id,
                deque(maxlen=self.history_steps + self.safety_buffer),
            )
            if buffer:
                last = buffer[-1]
                delta = timestamp - last.observed_at
                # Same timestamp or same snapshot read twice: stale duplicate.
                if abs(delta) <= _EPSILON or snapshot_id == last.snapshot_id:
                    return AppendStatus.REJECTED_DUPLICATE
                if delta < 0:
                    buffer.clear()
                    buffer.append(entry)
                    return AppendStatus.RESET_OUT_OF_ORDER
                if delta > self.max_gap_seconds + _EPSILON:
                    buffer.clear()
                    buffer.append(entry)
                    return AppendStatus.RESET_GAP
            buffer.append(entry)
            return AppendStatus.APPENDED

    def append_twin_state(
        self,
        twin_state: Mapping[str, Any],
    ) -> dict[str, AppendStatus]:
        """Append every controller row of one TwinState (GET /api/v1/twin/state).

        The snapshot time (created_at) is the sample time, so reading the same
        snapshot twice is rejected instead of looking like a new observation.
        quality.valid decides whether the whole snapshot may be stored.
        """
        controllers = twin_state.get("controllers")
        if not isinstance(controllers, list):
            # e.g. {"status": "NOT_READY"} before the first snapshot exists.
            return {}

        created_at = twin_state.get("created_at")
        snapshot_id = str(twin_state.get("snapshot_id", ""))
        if created_at is None or not snapshot_id:
            raise ValueError("twin_state needs created_at and snapshot_id")

        quality = twin_state.get("quality")
        snapshot_valid = (
            isinstance(quality, Mapping) and quality.get("valid") is True
        )

        return {
            str(row["controller_id"]): self.append(
                str(row["controller_id"]),
                created_at,
                snapshot_id,
                row,
                snapshot_valid=snapshot_valid,
            )
            for row in controllers
        }

    def size(self, controller_id: str) -> int:
        with self._lock:
            return len(self._buffers.get(controller_id, ()))

    def ready(self, controller_id: str) -> bool:
        return self.size(controller_id) >= self.history_steps

    def status(self, controller_id: str) -> str:
        return READY if self.ready(controller_id) else NOT_READY

    def get_history(self, controller_id: str) -> list[HistoryEntry]:
        """Latest ``history_steps`` consecutive entries, oldest first."""
        with self._lock:
            buffer = self._buffers.get(controller_id, deque())
            if len(buffer) < self.history_steps:
                raise HistoryNotReadyError(
                    f"{controller_id}: {len(buffer)}/{self.history_steps} "
                    "consecutive samples"
                )
            return list(buffer)[-self.history_steps:]

    def clear(self, controller_id: str | None = None) -> None:
        """Clear one controller, or all when no id is given."""
        with self._lock:
            if controller_id is None:
                self._buffers.clear()
            else:
                self._buffers.pop(controller_id, None)
