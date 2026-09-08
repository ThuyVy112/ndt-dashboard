from __future__ import annotations

import argparse
import json
import socket
import time
from datetime import datetime, timezone
from pathlib import Path

from src.experiments.workloads.generator import (
    DeadlinePacer,
    JsonlWriter,
    NANOSECONDS_PER_SECOND,
    PortAllocator,
    validate_port_reuse,
)
from src.schemas.workload import WorkloadSample
from ipaddress import ip_address

DEFAULT_SOURCE_PORT_START = 12000
DEFAULT_SOURCE_PORT_END = 65000

DEFAULT_SAMPLE_INTERVAL_SECONDS = 1.0
DEFAULT_FLOW_IDLE_TIMEOUT_SECONDS = 5.0
DEFAULT_PORT_REUSE_SAFETY_FACTOR = 2.0

DEFAULT_PATTERN = "stable"
PROTOCOL = "udp"
SUPPORTED_PATTERNS = [
    "stable",
    "gradual",
    "burst",
    "oscillating",
    "hot_switch",
]


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Controlled UDP new-flow workload generator "
            "for SDN controller experiments"
        )
    )

    parser.add_argument(
        "--run-id",
        required=True,
        help="Unique experiment run identifier",
    )

    parser.add_argument(
        "--source-host",
        required=True,
        help="Mininet source host name, e.g. h1",
    )

    parser.add_argument(
        "--source-ip",
        required=True,
        help="Source IPv4 address, e.g. 10.0.0.1",
    )

    parser.add_argument(
        "--target-host",
        required=True,
        help="Mininet destination host name, e.g. h2",
    )

    parser.add_argument(
        "--target-ip",
        required=True,
        help="Destination IPv4 address, e.g. 10.0.0.2",
    )

    parser.add_argument(
        "--target-port",
        type=int,
        required=True,
        help="Destination UDP port, normally 9000",
    )

    parser.add_argument(
        "--pattern",
        choices=sorted(SUPPORTED_PATTERNS),
        default=DEFAULT_PATTERN,
        help="Workload pattern, default: stable",
    )

    parser.add_argument(
        "--rate",
        type=float,
        required=True,
        help="Target new-flow rate in flows/s",
    )

    parser.add_argument(
        "--duration",
        type=float,
        required=True,
        help="Workload duration in seconds",
    )

    parser.add_argument(
        "--sample-interval",
        type=float,
        default=DEFAULT_SAMPLE_INTERVAL_SECONDS,
        help=(
            "Workload JSONL sampling interval "
            "in seconds, default: 1.0"
        ),
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
        help=(
            "Benchmark OpenFlow idle timeout used "
            "for source-port reuse safety validation"
        ),
    )

    parser.add_argument(
        "--port-reuse-safety-factor",
        type=float,
        default=DEFAULT_PORT_REUSE_SAFETY_FACTOR,
        help=(
            "Required safety factor between source-port "
            "wrap time and OpenFlow idle timeout"
        ),
    )

    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Output workload JSONL file",
    )

    return parser


def validate_config(
    args: argparse.Namespace,
) -> None:
    source_ip = ip_address(args.source_ip)
    target_ip = ip_address(args.target_ip)

    #validate that source and target IPs are not the same
    if source_ip.version != 4:
        raise ValueError(
            f"source-ip must be IPv4, got: {args.source_ip}"
        )

    if target_ip.version != 4:
        raise ValueError(
            f"target-ip must be IPv4, got: {args.target_ip}"
        )
    if source_ip == target_ip:
        raise ValueError(
            "source-ip and target-ip must be different"
        )
    if not args.run_id.strip():
        raise ValueError(
            "run-id must not be empty"
        )

    if not args.source_host.strip():
        raise ValueError(
            "source-host must not be empty"
        )

    if not args.target_host.strip():
        raise ValueError(
            "target-host must not be empty"
        )

    if args.rate <= 0:
        raise ValueError(
            "rate must be > 0"
        )

    if args.duration <= 0:
        raise ValueError(
            "duration must be > 0"
        )

    if args.sample_interval <= 0:
        raise ValueError(
            "sample-interval must be > 0"
        )

    if args.flow_idle_timeout <= 0:
        raise ValueError(
            "flow-idle-timeout must be > 0"
        )

    if args.port_reuse_safety_factor < 1.0:
        raise ValueError(
            "port-reuse-safety-factor must be >= 1.0"
        )

    if not 1 <= args.target_port <= 65535:
        raise ValueError(
            f"invalid target port: {args.target_port}"
        )

    if not 1024 <= args.source_port_start <= 65535:
        raise ValueError(
            "source-port-start must be "
            "in [1024, 65535]"
        )

    if not 1024 <= args.source_port_end <= 65535:
        raise ValueError(
            "source-port-end must be "
            "in [1024, 65535]"
        )

    if (
        args.source_port_start
        > args.source_port_end
    ):
        raise ValueError(
            "source-port-start must be "
            "<= source-port-end"
        )

    validate_port_reuse(
        start=args.source_port_start,
        end=args.source_port_end,
        rate=args.rate,
        idle_timeout_seconds=(
            args.flow_idle_timeout
        ),
        safety_factor=(
            args.port_reuse_safety_factor
        ),
    )


def send_udp_flow(
    source_ip: str,
    source_port: int,
    target_ip: str,
    target_port: int,
) -> None:
    """
    Send exactly one UDP packet using a unique source port.

    A new source port changes the UDP 5-tuple and therefore
    creates a distinct benchmark flow.
    """

    with socket.socket(
        socket.AF_INET,
        socket.SOCK_DGRAM,
    ) as sock:
        sock.bind(
            (
                source_ip,
                source_port,
            )
        )

        sock.sendto(
            b"x",
            (
                target_ip,
                target_port,
            ),
        )

        # --report-every 5 --> log received_packets, receive_rate
        sock.setsockopt(
            socket.SOL_SOCKET,
            socket.SO_RCVBUF,
            4 * 1024 * 1024
        )



def create_workload_sample(
    args: argparse.Namespace,
    interval_started_ns: int,
    interval_finished_ns: int,
    interval_attempted_flows: int,
    interval_emitted_flows: int,
    interval_send_errors: int,
    interval_late_events: int,
    interval_max_schedule_lag_ms: float,
    cumulative_attempted_flows: int,
    cumulative_emitted_flows: int,
    cumulative_send_errors: int,
    first_source_port: int | None,
    last_source_port: int | None,
) -> WorkloadSample:
    interval_seconds = max(
        (
            interval_finished_ns
            - interval_started_ns
        )
        / NANOSECONDS_PER_SECOND,
        1e-9,
    )

    emitted_new_flow_rate = (
        interval_emitted_flows
        / interval_seconds
    )

    return WorkloadSample(
        run_id=args.run_id,
        observed_at=datetime.now(
            timezone.utc
        ),

        source_host=args.source_host,
        source_ip=args.source_ip,

        target_host=args.target_host,
        target_ip=args.target_ip,
        target_port=args.target_port,

        protocol=PROTOCOL,
        pattern=args.pattern,

        target_new_flow_rate=args.rate,
        emitted_new_flow_rate=(
            emitted_new_flow_rate
        ),

        interval_seconds=interval_seconds,

        attempted_flows=(
            interval_attempted_flows
        ),
        emitted_flows=(
            interval_emitted_flows
        ),
        send_errors=(
            interval_send_errors
        ),

        late_events=(
            interval_late_events
        ),
        max_schedule_lag_ms=(
            interval_max_schedule_lag_ms
        ),

        cumulative_attempted_flows=(
            cumulative_attempted_flows
        ),
        cumulative_emitted_flows=(
            cumulative_emitted_flows
        ),
        cumulative_send_errors=(
            cumulative_send_errors
        ),

        first_source_port=first_source_port,
        last_source_port=last_source_port,
    )


def run_generator(
    args: argparse.Namespace,
) -> WorkloadSample:
    """
    Run controlled UDP new-flow workload.

    Design:
    - Each UDP source port represents one new 5-tuple flow.
    - Workload samples use fixed time windows.
    - A flow whose deadline is exactly on a sample boundary
      belongs to the NEW window, not the previous one.
    - Individual flow records are not written to JSONL.
    """

    validate_config(args)

    allocator = PortAllocator(
        start=args.source_port_start,
        end=args.source_port_end,
    )

    pacer = DeadlinePacer(
        rate=args.rate,
    )

    start_ns = time.monotonic_ns()

    end_ns = (
        start_ns
        + int(
            args.duration
            * NANOSECONDS_PER_SECOND
        )
    )

    sample_interval_ns = int(
        args.sample_interval
        * NANOSECONDS_PER_SECOND
    )

    next_sample_ns = (
        start_ns
        + sample_interval_ns
    )

    interval_started_ns = start_ns

    sequence = 0

    # =========================================================
    # Run-level counters
    # =========================================================

    cumulative_attempted_flows = 0
    cumulative_emitted_flows = 0
    cumulative_send_errors = 0

    # if the generator is too late to send a flow (overload), it counts as a late event
    cumulative_late_events = 0
    run_max_schedule_lag_ms = 0.0

    run_first_source_port = None
    run_last_source_port = None

    # =========================================================
    # Current sample-window counters
    # =========================================================

    interval_attempted_flows = 0
    interval_emitted_flows = 0
    interval_send_errors = 0

    interval_late_events = 0
    interval_max_schedule_lag_ms = 0.0

    interval_first_source_port = None
    interval_last_source_port = None

    last_sample: WorkloadSample | None = None

    with JsonlWriter(args.output) as writer:

        # =====================================================
        # Helper: flush exactly one sampling window
        # =====================================================

        def flush_interval(
            interval_finished_ns: int,
        ) -> WorkloadSample:
            nonlocal interval_started_ns

            nonlocal interval_attempted_flows
            nonlocal interval_emitted_flows
            nonlocal interval_send_errors

            nonlocal interval_late_events
            nonlocal interval_max_schedule_lag_ms

            nonlocal interval_first_source_port
            nonlocal interval_last_source_port

            sample = create_workload_sample(
                args=args,

                interval_started_ns=(
                    interval_started_ns
                ),

                interval_finished_ns=(
                    interval_finished_ns
                ),

                interval_attempted_flows=(
                    interval_attempted_flows
                ),

                interval_emitted_flows=(
                    interval_emitted_flows
                ),

                interval_send_errors=(
                    interval_send_errors
                ),

                interval_late_events=(
                    interval_late_events
                ),

                interval_max_schedule_lag_ms=(
                    interval_max_schedule_lag_ms
                ),

                cumulative_attempted_flows=(
                    cumulative_attempted_flows
                ),

                cumulative_emitted_flows=(
                    cumulative_emitted_flows
                ),

                cumulative_send_errors=(
                    cumulative_send_errors
                ),

                first_source_port=(
                    interval_first_source_port
                ),

                last_source_port=(
                    interval_last_source_port
                ),
            )

            writer.write(
                sample.to_dict()
            )

            # ---------------------------------------------
            # Reset ONLY current-window counters
            # ---------------------------------------------

            interval_attempted_flows = 0
            interval_emitted_flows = 0
            interval_send_errors = 0

            interval_late_events = 0
            interval_max_schedule_lag_ms = 0.0

            interval_first_source_port = None
            interval_last_source_port = None

            interval_started_ns = (
                interval_finished_ns
            )

            return sample

        # =====================================================
        # Main workload loop
        # =====================================================

        while True:

            deadline_ns = pacer.deadline_ns(
                start_ns=start_ns,
                sequence=sequence,
            )

            # Experiment workload window is [start, end).
            if deadline_ns >= end_ns:
                break

            # =================================================
            # IMPORTANT FIX:
            #
            # Flush all expired sampling windows BEFORE
            # generating the event.
            #
            # Example:
            # next_sample = 1.0s
            # flow deadline = 1.0s
            #
            # Flush [0,1) first.
            # Then flow at 1.0s belongs to [1,2).
            # =================================================

            while deadline_ns >= next_sample_ns:

                last_sample = flush_interval(
                    next_sample_ns
                )

                next_sample_ns += (
                    sample_interval_ns
                )

            # =================================================
            # Wait until scheduled flow deadline
            # =================================================

            schedule_lag_ms = (
                pacer.wait_until(
                    deadline_ns
                )
            )

            now_ns = time.monotonic_ns()

            # Generator is too late and experiment window
            # has already finished.
            if now_ns >= end_ns:
                break

            # =================================================
            # Allocate one unique UDP source port
            # =================================================

            source_port = (
                allocator.next_port()
            )

            if run_first_source_port is None:
                run_first_source_port = (
                    source_port
                )

            run_last_source_port = (
                source_port
            )

            if (
                interval_first_source_port
                is None
            ):
                interval_first_source_port = (
                    source_port
                )

            interval_last_source_port = (
                source_port
            )

            # =================================================
            # Update attempted counters
            # =================================================

            sequence += 1

            cumulative_attempted_flows += 1
            interval_attempted_flows += 1

            # =================================================
            # Scheduling quality
            #
            # Event is considered late if generator misses
            # at least one full intended inter-flow period.
            # =================================================

            if (
                schedule_lag_ms
                > pacer.period_ms / 1_000_000.0
            ):
                interval_late_events += 1
                cumulative_late_events += 1

            interval_max_schedule_lag_ms = max(
                interval_max_schedule_lag_ms,
                schedule_lag_ms,
            )

            run_max_schedule_lag_ms = max(
                run_max_schedule_lag_ms,
                schedule_lag_ms,
            )

            # =================================================
            # Emit one new UDP flow
            # =================================================

            try:
                send_udp_flow(
                    source_ip=args.source_ip,
                    source_port=source_port,
                    target_ip=args.target_ip,
                    target_port=args.target_port,
                )

                cumulative_emitted_flows += 1
                interval_emitted_flows += 1

            except OSError:
                cumulative_send_errors += 1
                interval_send_errors += 1

        # =====================================================
        # Keep the experiment aligned with requested duration.
        #
        # Example:
        # 10 flows/s, 20s:
        # last flow deadline = 19.9s
        #
        # Still wait until exactly 20s before closing
        # the final sampling window.
        # =====================================================

        now_ns = time.monotonic_ns()

        if now_ns < end_ns:
            DeadlinePacer.wait_until(
                end_ns
            )

        # =====================================================
        # Flush every full remaining sampling window.
        #
        # For duration=20s, sample=1s:
        # exactly 20 samples are produced.
        # =====================================================

        while next_sample_ns <= end_ns:

            last_sample = flush_interval(
                next_sample_ns
            )

            next_sample_ns += (
                sample_interval_ns
            )

        # =====================================================
        # Handle final partial window.
        #
        # Example:
        # duration=20.5s, sample_interval=1s
        #
        # Full samples:
        # [0,1), ..., [19,20)
        #
        # Partial:
        # [20,20.5)
        # =====================================================

        if interval_started_ns < end_ns:

            last_sample = flush_interval(
                end_ns
            )

    # =========================================================
    # Final run-level summary
    #
    # This is printed to stdout only.
    # It is NOT written into workload.jsonl.
    # =========================================================

    elapsed_seconds = max(
        (
            end_ns
            - start_ns
        )
        / NANOSECONDS_PER_SECOND,
        1e-9,
    )

    return WorkloadSample(
        run_id=args.run_id,

        observed_at=datetime.now(
            timezone.utc
        ),

        source_host=args.source_host,
        source_ip=args.source_ip,

        target_host=args.target_host,
        target_ip=args.target_ip,
        target_port=args.target_port,

        protocol=PROTOCOL,
        pattern=args.pattern,

        target_new_flow_rate=(
            args.rate
        ),

        emitted_new_flow_rate=(
            cumulative_emitted_flows
            / elapsed_seconds
        ),

        interval_seconds=(
            elapsed_seconds
        ),

        attempted_flows=(
            cumulative_attempted_flows
        ),

        emitted_flows=(
            cumulative_emitted_flows
        ),

        send_errors=(
            cumulative_send_errors
        ),

        # stdout: 
        # {
        #     "status": "WORKLOAD_DONE",
        #     "target_new_flow_rate": 100,
        #     "emitted_new_flow_rate": 99.5,
        #     "late_events": 2,
        #     "maxx_schedule_lag_ms": 0.5
        # }

        late_events=(
            cumulative_late_events
        ),

        max_schedule_lag_ms=(
            run_max_schedule_lag_ms
        ),

        cumulative_attempted_flows=(
            cumulative_attempted_flows
        ),

        cumulative_emitted_flows=(
            cumulative_emitted_flows
        ),

        cumulative_send_errors=(
            cumulative_send_errors
        ),

        first_source_port=(
            run_first_source_port
        ),

        last_source_port=(
            run_last_source_port
        ),
    )


def main() -> None:
    args = (
        build_arg_parser()
        .parse_args()
    )

    try:
        summary = run_generator(
            args
        )

        print(
            json.dumps(
                {
                    "status": "WORKLOAD_DONE",
                    **summary.to_dict(),
                }
            )
        )

    except (
        OSError,
        ValueError,
    ) as exc:
        raise SystemExit(
            f"UDP new-flow generator failed: {exc}"
        ) from exc


if __name__ == "__main__":
    main()