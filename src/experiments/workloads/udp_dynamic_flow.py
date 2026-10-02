from __future__ import annotations

import argparse
import json
import math
import socket
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from src.experiments.workloads.generator import (
    JsonlWriter,
    NANOSECONDS_PER_SECOND,
    PortAllocator,
    validate_port_reuse,
)
from src.experiments.workloads.profile import WorkloadProfile
from src.experiments.workloads.stable import StableWorkload
from src.experiments.workloads.gradual import GradualWorkload
from src.experiments.workloads.burst import BurstWorkload
from src.experiments.workloads.oscillating import OscillatingWorkload


SUPPORTED_PATTERNS = (
    "stable",
    "gradual",
    "burst",
    "oscillating",
)

DEFAULT_SOURCE_PORT_START = 12000
DEFAULT_SOURCE_PORT_END = 65000
DEFAULT_SAMPLE_INTERVAL_SECONDS = 1.0
DEFAULT_FLOW_IDLE_TIMEOUT_SECONDS = 5.0
DEFAULT_PORT_REUSE_SAFETY_FACTOR = 2.0


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Dynamic UDP new-flow workload generator"
    )

    parser.add_argument("--run-id", required=True)
    parser.add_argument("--source-host", required=True)
    parser.add_argument("--source-ip", required=True)
    parser.add_argument("--target-host", required=True)
    parser.add_argument("--target-ip", required=True)
    parser.add_argument("--target-port", type=int, required=True)

    parser.add_argument(
        "--pattern",
        choices=SUPPORTED_PATTERNS,
        required=True,
    )

    parser.add_argument(
        "--rate-map",
        type=Path,
        required=True,
        help=(
            "JSON mapping from target utilization to "
            "offered new-flow rate"
        ),
    )

    parser.add_argument("--duration", type=float, required=True)

    parser.add_argument(
        "--sample-interval",
        type=float,
        default=DEFAULT_SAMPLE_INTERVAL_SECONDS,
    )

    parser.add_argument(
        "--source-port-start",
        type=int,
        default=DEFAULT_SOURCE_PORT_START,
    )

    parser.add_argument(
        "--source-port-end",
        type=int,
        default=DEFAULT_SOURCE_PORT_END,
    )

    parser.add_argument(
        "--flow-idle-timeout",
        type=float,
        default=DEFAULT_FLOW_IDLE_TIMEOUT_SECONDS,
    )

    parser.add_argument(
        "--port-reuse-safety-factor",
        type=float,
        default=DEFAULT_PORT_REUSE_SAFETY_FACTOR,
    )

    parser.add_argument("--output", type=Path, required=True)

    return parser


def build_profile(pattern: str) -> WorkloadProfile:
    if pattern == "stable":
        return StableWorkload()

    if pattern == "gradual":
        return GradualWorkload()

    if pattern == "burst":
        return BurstWorkload()

    if pattern == "oscillating":
        return OscillatingWorkload()

    raise ValueError(f"unsupported pattern: {pattern}")


def load_rate_map(path: Path) -> dict[float, float]:
    payload = json.loads(path.read_text(encoding="utf-8"))

    if not isinstance(payload, dict):
        raise ValueError("rate-map must contain a JSON object")

    result: dict[float, float] = {}

    for raw_utilization, raw_rate in payload.items():
        utilization = float(raw_utilization)
        rate = float(raw_rate)

        if not math.isfinite(utilization) or utilization < 0:
            raise ValueError(
                f"invalid utilization in rate-map: {raw_utilization}"
            )

        if not math.isfinite(rate) or rate <= 0:
            raise ValueError(
                f"invalid rate in rate-map: {raw_rate}"
            )

        result[utilization] = rate

    if not result:
        raise ValueError("rate-map must not be empty")

    return result


def rate_for_utilization(
    rate_map: dict[float, float],
    target_utilization: float,
) -> float:
    for utilization, rate in rate_map.items():
        if math.isclose(
            utilization,
            target_utilization,
            rel_tol=0.0,
            abs_tol=1e-9,
        ):
            return rate

    points = sorted(rate_map.items())

    if target_utilization < points[0][0]:
        raise ValueError(
            "target utilization is below rate-map range: "
            f"{target_utilization}"
        )

    if target_utilization > points[-1][0]:
        raise ValueError(
            "target utilization is above rate-map range: "
            f"{target_utilization}"
        )

    for index in range(1, len(points)):
        left_u, left_rate = points[index - 1]
        right_u, right_rate = points[index]

        if left_u <= target_utilization <= right_u:
            fraction = (
                (target_utilization - left_u)
                / (right_u - left_u)
            )

            return (
                left_rate
                + fraction * (right_rate - left_rate)
            )

    raise RuntimeError(
        f"unable to map utilization: {target_utilization}"
    )


def send_udp_flow(
    source_ip: str,
    source_port: int,
    target_ip: str,
    target_port: int,
) -> None:
    with socket.socket(
        socket.AF_INET,
        socket.SOCK_DGRAM,
    ) as sock:
        sock.bind((source_ip, source_port))
        sock.sendto(b"x", (target_ip, target_port))


def validate_args(
    args: argparse.Namespace,
    rate_map: dict[float, float],
) -> None:
    if args.duration <= 0:
        raise ValueError("duration must be > 0")

    if args.sample_interval <= 0:
        raise ValueError("sample-interval must be > 0")

    if args.flow_idle_timeout <= 0:
        raise ValueError("flow-idle-timeout must be > 0")

    if args.port_reuse_safety_factor < 1.0:
        raise ValueError(
            "port-reuse-safety-factor must be >= 1.0"
        )

    if not 1 <= args.target_port <= 65535:
        raise ValueError("invalid target port")

    max_rate = max(rate_map.values())

    validate_port_reuse(
        start=args.source_port_start,
        end=args.source_port_end,
        rate=max_rate,
        idle_timeout_seconds=args.flow_idle_timeout,
        safety_factor=args.port_reuse_safety_factor,
    )


def run_generator(
    args: argparse.Namespace,
    *,
    send_flow: Callable[
        [str, int, str, int],
        None,
    ] = send_udp_flow,
) -> None:
    rate_map = load_rate_map(args.rate_map)
    validate_args(args, rate_map)

    profile = build_profile(args.pattern)

    allocator = PortAllocator(
        args.source_port_start,
        args.source_port_end,
    )

    start_ns = time.monotonic_ns()
    end_ns = start_ns + int(
        args.duration * NANOSECONDS_PER_SECOND
    )

    sample_interval_ns = int(
        args.sample_interval * NANOSECONDS_PER_SECOND
    )

    next_sample_ns = start_ns + sample_interval_ns

    interval_start_ns = start_ns
    interval_attempted = 0
    interval_emitted = 0
    interval_errors = 0
    interval_late = 0
    interval_max_lag_ms = 0.0

    cumulative_attempted = 0
    cumulative_emitted = 0
    cumulative_errors = 0

    first_source_port: int | None = None
    last_source_port: int | None = None

    next_flow_ns = start_ns

    def write_sample(
        writer: JsonlWriter,
        finished_ns: int,
    ) -> None:
        nonlocal interval_start_ns
        nonlocal interval_attempted
        nonlocal interval_emitted
        nonlocal interval_errors
        nonlocal interval_late
        nonlocal interval_max_lag_ms

        interval_elapsed_seconds = max(
            0.0,
            (interval_start_ns - start_ns)
            / NANOSECONDS_PER_SECOND,
        )

        point = profile.target_at(
            min(
                interval_elapsed_seconds,
                args.duration,
            )
        )

        target_rate = rate_for_utilization(
            rate_map,
            point.target_utilization,
        )

        interval_seconds = max(
            (finished_ns - interval_start_ns)
            / NANOSECONDS_PER_SECOND,
            1e-9,
        )

        emitted_rate = (
            interval_emitted / interval_seconds
        )

        writer.write(
            {
                "run_id": args.run_id,
                "observed_at": datetime.now(
                    timezone.utc
                ).isoformat(),
                "source_host": args.source_host,
                "source_ip": args.source_ip,
                "target_host": args.target_host,
                "target_ip": args.target_ip,
                "target_port": args.target_port,
                "protocol": "udp",
                "pattern": args.pattern,
                "phase": point.phase,
                "target_utilization": (
                    point.target_utilization
                ),
                "target_new_flow_rate": target_rate,
                "emitted_new_flow_rate": emitted_rate,
                "interval_seconds": interval_seconds,
                "attempted_flows": interval_attempted,
                "emitted_flows": interval_emitted,
                "send_errors": interval_errors,
                "late_events": interval_late,
                "max_schedule_lag_ms": (
                    interval_max_lag_ms
                ),
                "cumulative_attempted_flows": (
                    cumulative_attempted
                ),
                "cumulative_emitted_flows": (
                    cumulative_emitted
                ),
                "cumulative_send_errors": (
                    cumulative_errors
                ),
                "first_source_port": first_source_port,
                "last_source_port": last_source_port,
            }
        )

        interval_start_ns = finished_ns
        interval_attempted = 0
        interval_emitted = 0
        interval_errors = 0
        interval_late = 0
        interval_max_lag_ms = 0.0

    with JsonlWriter(args.output) as writer:
        while True:
            now_ns = time.monotonic_ns()

            while (
                now_ns >= next_sample_ns
                and next_sample_ns <= end_ns
            ):
                write_sample(writer, next_sample_ns)
                next_sample_ns += sample_interval_ns

            if now_ns >= end_ns:
                break

            elapsed_seconds = (
                now_ns - start_ns
            ) / NANOSECONDS_PER_SECOND

            point = profile.target_at(elapsed_seconds)

            target_rate = rate_for_utilization(
                rate_map,
                point.target_utilization,
            )

            period_ns = max(
                1,
                int(
                    NANOSECONDS_PER_SECOND
                    / target_rate
                ),
            )

            if now_ns < next_flow_ns:
                sleep_seconds = (
                    next_flow_ns - now_ns
                ) / NANOSECONDS_PER_SECOND

                time.sleep(
                    min(sleep_seconds, 0.01)
                )

                continue

            lag_ms = max(
                0.0,
                (now_ns - next_flow_ns) / 1_000_000.0,
            )

            if lag_ms > 1.0:
                interval_late += 1

            interval_max_lag_ms = max(
                interval_max_lag_ms,
                lag_ms,
            )

            source_port = allocator.next_port()

            if first_source_port is None:
                first_source_port = source_port

            last_source_port = source_port

            interval_attempted += 1
            cumulative_attempted += 1

            try:
                send_flow(
                    args.source_ip,
                    source_port,
                    args.target_ip,
                    args.target_port,
                )
                interval_emitted += 1
                cumulative_emitted += 1

            except OSError:
                interval_errors += 1
                cumulative_errors += 1

            # The next deadline is based on the current target
            # rate. This allows the workload profile to change
            # dynamically without restarting the generator.
            next_flow_ns += period_ns

        while next_sample_ns <= end_ns:
            write_sample(writer, next_sample_ns)
            next_sample_ns += sample_interval_ns

    summary = {
        "status": "WORKLOAD_DONE",
        "run_id": args.run_id,
        "pattern": args.pattern,
        "duration_seconds": args.duration,
        "cumulative_attempted_flows": cumulative_attempted,
        "cumulative_emitted_flows": cumulative_emitted,
        "cumulative_send_errors": cumulative_errors,
        "first_source_port": first_source_port,
        "last_source_port": last_source_port,
    }

    print(
        json.dumps(summary, separators=(",", ":")),
        flush=True,
    )


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()

    run_generator(args)


if __name__ == "__main__":
    main()
