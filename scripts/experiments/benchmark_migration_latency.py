#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from mininet.link import TCLink
from mininet.log import setLogLevel
from mininet.net import Mininet
from mininet.node import OVSSwitch, RemoteController

from src.experiments.topologies.capacity_2c20s import (
    Capacity2C20STopo,
)


ORCH = "http://127.0.0.1:9000"


def request_json(
    method: str,
    url: str,
    payload: dict[str, Any] | None = None,
    timeout: float = 20,
) -> dict[str, Any]:
    data = (
        json.dumps(payload).encode()
        if payload is not None
        else None
    )

    request = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Content-Type": "application/json",
        },
    )

    try:
        with urllib.request.urlopen(
            request,
            timeout=timeout,
        ) as response:
            value = json.loads(
                response.read().decode()
            )
    except urllib.error.HTTPError as exc:
        body = exc.read().decode(
            "utf-8",
            errors="replace",
        )
        raise RuntimeError(
            f"HTTP {exc.code} {method} {url}: "
            f"{body}"
        ) from exc

    if not isinstance(value, dict):
        raise RuntimeError(
            "API response must be an object"
        )

    return value


def force_packet_in(
    net: Mininet,
    sequence: int,
) -> None:
    """Generate a fresh flow through s1.

    A changing UDP destination port prevents repeated
    verification attempts from reusing the same learned
    OpenFlow entry.
    """
    s1 = net.get("s1")
    h1 = net.get("h1")
    h20 = net.get("h20")

    # Remove only reactive forwarding rules while keeping
    # the table-miss rule that sends unknown traffic to the
    # controller.
    s1.cmd(
        "ovs-ofctl -O OpenFlow13 "
        "del-flows s1 'priority=10'"
    )

    dst_port = 20000 + (sequence % 30000)

    h1.cmd(
        "python3 -c "
        "\"import socket; "
        "s=socket.socket(socket.AF_INET,"
        "socket.SOCK_DGRAM); "
        f"s.sendto(b'x',('{h20.IP()}',"
        f"{dst_port})); "
        "s.close()\" "
        ">/dev/null 2>&1 &"
    )


def migrate_with_traffic(
    net: Mininet,
    target: str,
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    error: dict[str, Exception] = {}

    def invoke() -> None:
        try:
            result.update(
                request_json(
                    "POST",
                    f"{ORCH}/api/v1/migrations",
                    {
                        "switch_id": "s1",
                        "target_controller": target,
                        "simulate_failure": "none",
                    },
                    timeout=20,
                )
            )
        except Exception as exc:
            error["value"] = exc

    thread = threading.Thread(
        target=invoke,
        daemon=True,
    )
    thread.start()

    packet_sequence = time.monotonic_ns()

    for index in range(40):
        time.sleep(0.10)

        force_packet_in(
            net,
            packet_sequence + index,
        )

        if not thread.is_alive():
            break

    thread.join(timeout=20)

    if thread.is_alive():
        raise RuntimeError(
            "migration request did not finish"
        )

    if error:
        raise error["value"]

    return result



def append_jsonl(
    path: Path,
    record: dict[str, Any],
) -> None:
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    with path.open(
        "a",
        encoding="utf-8",
    ) as handle:
        handle.write(
            json.dumps(record) + "\n"
        )


def main() -> None:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--count",
        type=int,
        default=20,
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            "data/benchmarks/runtime/"
            "migration_latency.jsonl"
        ),
    )

    args = parser.parse_args()

    excluded_path = (
        args.output.parent
        / "migration_latency_excluded.jsonl"
    )

    args.output.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    # Each invocation starts a fresh benchmark.
    args.output.unlink(missing_ok=True)
    excluded_path.unlink(missing_ok=True)

    if args.count < 2:
        raise ValueError(
            "--count must be >= 2"
        )

    setLogLevel("warning")

    net = Mininet(
        topo=Capacity2C20STopo(),
        controller=None,
        switch=OVSSwitch,
        link=TCLink,
        build=False,
    )

    net.addController(
        "c1",
        controller=RemoteController,
        ip="127.0.0.1",
        port=6653,
    )
    net.addController(
        "c2",
        controller=RemoteController,
        ip="127.0.0.1",
        port=6654,
    )

    net.build()
    net.start()

    records: list[dict[str, Any]] = []

    try:
        time.sleep(2)

        init = request_json(
            "POST",
            f"{ORCH}/api/v1/init-roles",
        )

        if init.get("status") != "INITIALIZED":
            raise RuntimeError(
                f"init roles failed: {init}"
            )

        force_packet_in(
            net,
            time.monotonic_ns(),
        )

        owner = "c1"

        attempts = 0
        max_attempts = args.count * 3
        failed_records: list[dict[str, Any]] = []

        while len(records) < args.count:
            attempts += 1

            if attempts > max_attempts:
                raise RuntimeError(
                    "could not collect enough COMMITTED "
                    f"migrations: committed={len(records)}, "
                    f"attempts={attempts - 1}"
                )

            target = (
                "c2"
                if owner == "c1"
                else "c1"
            )

            response = migrate_with_traffic(
                net,
                target,
            )

            status = str(
                response.get("status", "")
            ).upper()

            tx = response.get("transaction")

            if not isinstance(tx, dict):
                raise RuntimeError(
                    "migration response missing "
                    "transaction"
                )

            if status == "COMMITTED":
                records.append(tx)
                append_jsonl(
                    args.output,
                    tx,
                )

                print(
                    f"COMMITTED "
                    f"{len(records):02d}/{args.count} "
                    f"(attempt {attempts:02d}): "
                    f"{owner} -> {target}"
                )

                # Ownership changes only after a
                # successful migration.
                owner = target

            else:
                failed_records.append(tx)
                append_jsonl(
                    excluded_path,
                    tx,
                )

                print(
                    f"EXCLUDED attempt {attempts:02d}: "
                    f"{owner} -> {target} "
                    f"state={status} "
                    f"reason={tx.get('failure_reason')}"
                )

            time.sleep(0.75)

    finally:
        net.stop()

    print(
        f"MIGRATION_BENCHMARK_PASS: "
        f"{len(records)} COMMITTED"
    )
    print(f"OUTPUT: {args.output}")


if __name__ == "__main__":
    main()
