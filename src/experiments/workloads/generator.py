from __future__ import annotations

import json
import time
from pathlib import Path
from typing import TextIO


NANOSECONDS_PER_SECOND = 1_000_000_000
MILLISECONDS_PER_SECOND = 1_000.0


class PortAllocator:
    """
    Deterministic sequential UDP source-port allocator.

    Example:
        12000 -> 12001 -> 12002 -> ... -> 65000 -> 12000
    """

    def __init__(self, start: int, end: int) -> None:
        if not 1024 <= start <= 65535:
            raise ValueError(
                f"source port start must be in [1024, 65535], got {start}"
            )

        if not 1024 <= end <= 65535:
            raise ValueError(
                f"source port end must be in [1024, 65535], got {end}"
            )

        if start > end:
            raise ValueError(
                "source port start must be <= source port end"
            )

        self.start = start
        self.end = end
        self.current = start

    @property
    def size(self) -> int:
        return self.end - self.start + 1

    def next_port(self) -> int:
        port = self.current

        if self.current >= self.end:
            self.current = self.start
        else:
            self.current += 1

        return port


def validate_port_reuse(
    start: int,
    end: int,
    rate: float,
    idle_timeout_seconds: float,
    safety_factor: float = 2.0,
) -> None:
    """
    Ensure source ports are not reused while old benchmark flows
    may still exist in the OVS flow table.

    wrap_seconds =
        number_of_source_ports / target_new_flow_rate

    Required:
        wrap_seconds >= idle_timeout * safety_factor
    """

    if rate <= 0:
        raise ValueError("rate must be > 0")

    if idle_timeout_seconds <= 0:
        raise ValueError(
            "idle_timeout_seconds must be > 0"
        )

    if safety_factor < 1.0:
        raise ValueError(
            "port reuse safety factor must be >= 1.0"
        )

    allocator = PortAllocator(start, end)

    wrap_seconds = allocator.size / rate

    minimum_safe_seconds = (
        idle_timeout_seconds * safety_factor
    )

    if wrap_seconds < minimum_safe_seconds:
        raise ValueError(
            "unsafe source-port range: "
            f"pool_size={allocator.size}, "
            f"rate={rate:.3f} flows/s, "
            f"wrap_seconds={wrap_seconds:.3f}s, "
            f"required>={minimum_safe_seconds:.3f}s"
        )


class DeadlinePacer:
    """
    Monotonic deadline-based workload pacer.

    Avoids cumulative drift from:

        send()
        sleep(1 / rate)

    Instead, flow i uses:

        deadline_i = start + i / rate
    """

    def __init__(self, rate: float) -> None:
        if rate <= 0:
            raise ValueError("rate must be > 0")

        self.rate = float(rate)

        self.period_ns = max(
            1,
            int(NANOSECONDS_PER_SECOND / self.rate),
        )

    @property
    def period_ms(self) -> float:
        return (
            self.period_ns
            / 1_000_000.0
        )

    def deadline_ns(
        self,
        start_ns: int,
        sequence: int,
    ) -> int:
        return (
            start_ns
            + sequence * self.period_ns
        )

    @staticmethod
    def wait_until(deadline_ns: int) -> float:
        """
        Sleep until deadline.

        Returns:
            scheduling lag in milliseconds.
        """

        while True:
            now_ns = time.monotonic_ns()

            remaining_ns = deadline_ns - now_ns

            if remaining_ns <= 0:
                break

            time.sleep(
                remaining_ns
                / NANOSECONDS_PER_SECOND
            )

        actual_ns = time.monotonic_ns()

        lag_ns = max(
            0,
            actual_ns - deadline_ns,
        )

        return lag_ns / 1_000_000.0


class JsonlWriter:
    """
    Small JSONL writer.

    Workload Generator writes one WorkloadSample
    per sampling interval, not one JSON object per flow.
    """

    def __init__(self, path: Path) -> None:
        self.path = path

        self.path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self._stream: TextIO = self.path.open(
            "w",
            encoding="utf-8",
        )

    def write(self, payload: dict) -> None:
        self._stream.write(
            json.dumps(
                payload,
                separators=(",", ":"),
            )
            + "\n"
        )

        # Only once per workload sample (~1 second),
        # therefore this flush is cheap enough.
        self._stream.flush()

    def close(self) -> None:
        self._stream.close()

    def __enter__(self) -> "JsonlWriter":
        return self

    def __exit__(
        self,
        exc_type,
        exc_value,
        traceback,
    ) -> None:
        self.close()