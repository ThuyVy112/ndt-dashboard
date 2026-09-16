from __future__ import annotations

import argparse
import json
import socket
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.experiments.workloads.generator import DeadlinePacer, JsonlWriter, PortAllocator, validate_port_reuse


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="UDP first-flow QoS probe")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--source-host", required=True)
    parser.add_argument("--source-ip", required=True)
    parser.add_argument("--target-host", required=True)
    parser.add_argument("--target-ip", required=True)
    parser.add_argument("--target-port", type=int, default=9001)
    parser.add_argument("--rate", type=float, default=2.0)
    parser.add_argument("--duration", type=float, required=True)
    parser.add_argument("--timeout", type=float, default=1.0)
    parser.add_argument("--source-port-start", type=int, default=2000)
    parser.add_argument("--source-port-end", type=int, default=10000)
    parser.add_argument("--flow-idle-timeout", type=float, default=30.0)
    parser.add_argument("--flow-idle-timeout", type=float, default=30.0)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def validate_args(args: argparse.Namespace) -> None:
    if args.rate <= 0:
        raise ValueError("rate must be > 0")
    if args.duration <= 0:
        raise ValueError("duration must be > 0")
    if args.timeout <= 0:
        raise ValueError("timeout must be > 0")
    if not 1 <= args.target_port <= 65535:
        raise ValueError("target-port must be in [1, 65535]")
    validate_port_reuse(
        start=args.source_port_start,
        end=args.source_port_end,
        rate=args.rate,
        idle_timeout_seconds=args.flow_idle_timeout,
        safety_factor=2.0,
    )


def run_probe(args: argparse.Namespace) -> dict[str, Any]:
    validate_args(args)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    allocator = PortAllocator(args.source_port_start, args.source_port_end)
    pacer = DeadlinePacer(args.rate)
    total_probes = max(1, int(args.rate * args.duration))
    start_ns = time.monotonic_ns()
    attempted = 0
    succeeded = 0

    with JsonlWriter(args.output) as writer:
        for sequence in range(total_probes):
            schedule_lag_ms = pacer.wait_until(pacer.deadline_ns(start_ns, sequence))
            source_port = allocator.next_port()
            send_ns = time.monotonic_ns()
            row: dict[str, Any] = {
                "run_id": args.run_id,
                "observed_at": datetime.now(timezone.utc).isoformat(),
                "sequence": sequence,
                "source_host": args.source_host,
                "source_ip": args.source_ip,
                "source_port": source_port,
                "target_host": args.target_host,
                "target_ip": args.target_ip,
                "target_port": args.target_port,
                "success": False,
                "schedule_lag_ms": schedule_lag_ms,
                "flow_setup_latency_ms": None,
                "rtt_ms": None,
                "error": None,
                "clock_basis": "shared-kernel-monotonic",
            }
            attempted += 1
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                    sock.bind((args.source_ip, source_port))
                    sock.settimeout(args.timeout)
                    payload = {"sequence": sequence, "send_ns": send_ns}
                    sock.sendto(
                        json.dumps(payload, separators=(",", ":")).encode("utf-8"),
                        (args.target_ip, args.target_port),
                    )
                    response_raw, _ = sock.recvfrom(65535)
                    ack_ns = time.monotonic_ns()
                response = json.loads(response_raw.decode("utf-8"))

                if int(
                    response["sequence"]
                ) != sequence:
                    raise ValueError(
                        "QoS response sequence mismatch"
                    )

                if int(
                    response["send_ns"]
                ) != send_ns:
                    raise ValueError(
                        "QoS response send_ns mismatch"
                    )
                
                target_received_ns = int(response["target_received_ns"])
                row["flow_setup_latency_ms"] = max(0.0, (target_received_ns - send_ns) / 1_000_000.0)
                row["rtt_ms"] = max(0.0, (ack_ns - send_ns) / 1_000_000.0)
                row["success"] = True
                succeeded += 1
            except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
                row["error"] = str(exc)
            writer.write(row)

    return {
        "status": "QOS_PROBE_DONE",
        "run_id": args.run_id,
        "attempted": attempted,
        "succeeded": succeeded,
        "failed": attempted - succeeded,
        "success_ratio": succeeded / attempted if attempted else 0.0,
    }


def main() -> None:
    args = build_parser().parse_args()
    try:
        print(json.dumps(run_probe(args), separators=(",", ":")))
    except ValueError as exc:
        raise SystemExit(f"QoS probe failed: {exc}") from exc


if __name__ == "__main__":
    main()
