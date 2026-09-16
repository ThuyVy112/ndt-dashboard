from __future__ import annotations

import json
import math
import statistics
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def parse_dt(value: str) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"{path}:{line_number} must be a JSON object")
            rows.append(value)
    return rows


def percentile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, math.ceil(fraction * len(ordered)) - 1))
    return float(ordered[index])


def in_window(row: dict[str, Any], field: str, start: datetime, end: datetime) -> bool:
    value = row.get(field)
    if value is None:
        return False
    try:
        observed = parse_dt(str(value))
    except (TypeError, ValueError):
        return False
    return start <= observed < end


def _mean(values: list[float]) -> float:
    return float(statistics.mean(values)) if values else 0.0


def aggregate_run(run_dir: Path) -> dict[str, Any]:
    metadata_path = run_dir / "metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    start = parse_dt(metadata["measurement_started_at"])
    end = parse_dt(metadata["measurement_ended_at"])
    target_controller = str(metadata["target_controller"])

    workload = [
        row for row in read_jsonl(run_dir / "workload.jsonl")
        if in_window(row, "observed_at", start, end)
    ]
    controllers = [
        row for row in read_jsonl(run_dir / "controllers.jsonl")
        if row.get("controller_id") == target_controller
        and in_window(row, "observed_at", start, end)
    ]
    switches = [
        row for row in read_jsonl(run_dir / "switches.jsonl")
        if row.get("controller_id") == target_controller
        and in_window(row, "observed_at", start, end)
    ]
    qos = [
        row for row in read_jsonl(run_dir / "qos.jsonl")
        if in_window(row, "observed_at", start, end)
    ]
    snapshots = [
        row for row in read_jsonl(run_dir / "snapshots.jsonl")
        if in_window(row, "created_at", start, end)
    ]
    collector_errors = read_jsonl(run_dir / "collector_errors.jsonl")

    emitted = [float(row["emitted_new_flow_rate"]) for row in workload]
    processed = [float(row["processed_packet_in_rate"]) for row in controllers]
    flow_mod = [float(row["flow_mod_rate"]) for row in controllers]
    cpu = [float(row["process_cpu_percent"]) for row in controllers]
    response_p95 = [float(row["response_p95_ms"]) for row in controllers]
    successful_qos = [row for row in qos if row.get("success") is True]
    setup_latency = [
        float(row["flow_setup_latency_ms"])
        for row in successful_qos
        if row.get("flow_setup_latency_ms") is not None
    ]
    snapshot_valid = [row.get("quality", {}).get("valid") is True for row in snapshots]

    return {
        "run_id": metadata["run_id"],
        "target_controller": target_controller,
        "target_new_flow_rate": float(metadata["target_new_flow_rate"]),
        "measurement_samples": {
            "workload": len(workload),
            "controller": len(controllers),
            "switch": len(switches),
            "qos": len(qos),
            "snapshots": len(snapshots),
            "collector_errors": len(collector_errors),
        },
        "emitted_new_flow_rate_mean": _mean(emitted),
        "processed_packet_in_rate_mean": _mean(processed),
        "processed_packet_in_rate_p95": percentile(processed, 0.95),
        "processed_packet_in_rate_max": max(processed, default=0.0),
        "flow_mod_rate_mean": _mean(flow_mod),
        "flow_mod_rate_max": max(flow_mod, default=0.0),
        "cpu_mean": _mean(cpu),
        "cpu_p95": percentile(cpu, 0.95),
        "response_p95_ms_mean": _mean(response_p95),
        "response_p95_ms_p95": percentile(response_p95, 0.95),
        "response_p95_ms_max": max(response_p95, default=0.0),
        "qos_success_ratio": len(successful_qos) / len(qos) if qos else 0.0,
        "flow_setup_latency_p95_ms": percentile(setup_latency, 0.95),
        "snapshot_valid_ratio": sum(snapshot_valid) / len(snapshot_valid) if snapshot_valid else 0.0,
        "workload_attempted_flows": sum(int(row.get("attempted_flows", 0)) for row in workload),
        "workload_send_errors": sum(int(row.get("send_errors", 0)) for row in workload),
    }
