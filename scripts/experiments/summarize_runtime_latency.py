from __future__ import annotations

import argparse
import csv
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from statistics import fmean
from typing import Any, Iterable


def read_records(path: Path) -> list[dict[str, Any]]:
	paths = sorted(path.rglob("*") if path.is_dir() else [path])
	records: list[dict[str, Any]] = []

	for input_path in paths:
		if not input_path.is_file():
			continue
		if input_path.suffix == ".jsonl":
			with input_path.open(encoding="utf-8") as handle:
				for line_number, line in enumerate(handle, start=1):
					if not line.strip():
						continue
					value = json.loads(line)
					if not isinstance(value, dict):
						raise ValueError(
							f"{input_path}:{line_number} must contain a JSON object"
						)
					records.append(value)
		elif input_path.suffix == ".json":
			value = json.loads(input_path.read_text(encoding="utf-8"))
			if isinstance(value, list):
				records.extend(item for item in value if isinstance(item, dict))
			elif isinstance(value, dict):
				records.append(value)
			else:
				raise ValueError(f"{input_path} must contain a JSON object or list")
		elif input_path.suffix == ".csv":
			with input_path.open(newline="", encoding="utf-8") as handle:
				records.extend(dict(row) for row in csv.DictReader(handle))

	return records


def _number(value: Any, field: str) -> float:
	try:
		result = float(value)
	except (TypeError, ValueError) as exc:
		raise ValueError(f"{field} must be numeric") from exc
	if not math.isfinite(result) or result < 0:
		raise ValueError(f"{field} must be finite and non-negative")
	return result


def collection_latency_values(records: Iterable[dict[str, Any]]) -> list[float]:
	values: list[float] = []
	for record in records:
		if "collection_latency_ms" in record:
			values.append(_number(record["collection_latency_ms"], "collection_latency_ms"))
		for controller in record.get("controllers", []):
			if isinstance(controller, dict) and "collection_latency_ms" in controller:
				values.append(
					_number(controller["collection_latency_ms"], "collection_latency_ms")
				)
	return values


def _parse_timestamp(value: Any, field: str) -> datetime:
	if not isinstance(value, str):
		raise ValueError(f"{field} must be an ISO 8601 timestamp")
	parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
	if parsed.tzinfo is None:
		parsed = parsed.replace(tzinfo=timezone.utc)
	return parsed


def migration_latency_values(records: Iterable[dict[str, Any]]) -> list[float]:
	values: list[float] = []
	for record in records:
		if str(record.get("state", "")).upper() != "COMMITTED":
			continue
		if record.get("started_at") is None or record.get("finished_at") is None:
			raise ValueError("COMMITTED migration is missing started_at or finished_at")
		duration_ms = (
			_parse_timestamp(record["finished_at"], "finished_at")
			- _parse_timestamp(record["started_at"], "started_at")
		).total_seconds() * 1000.0
		if duration_ms < 0:
			raise ValueError("migration finished_at must not precede started_at")
		values.append(duration_ms)
	return values


def summarize(values: list[float]) -> dict[str, float]:
	if not values:
		raise ValueError("no latency observations found")
	ordered = sorted(values)

	def percentile(fraction: float) -> float:
		index = min(len(ordered) - 1, math.ceil(fraction * len(ordered)) - 1)
		return float(ordered[index])

	return {
		"count": len(values),
		"mean": float(fmean(values)),
		"p50": percentile(0.50),
		"p95": percentile(0.95),
		"max": float(max(values)),
	}


def write_json(path: Path, value: dict[str, Any]) -> None:
	path.parent.mkdir(parents=True, exist_ok=True)
	path.write_text(
		json.dumps(value, indent=2) + "\n",
		encoding="utf-8",
	)


def build_artifacts(
	collection_records: Iterable[dict[str, Any]],
	migration_records: Iterable[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any]]:
	collection_summary = summarize(collection_latency_values(collection_records))
	migration_summary = summarize(migration_latency_values(migration_records))
	runtime_summary = {
		"schema_version": "1.0",
		"collection_latency_ms": collection_summary,
		"migration_latency_ms": migration_summary,
	}
	horizon_inputs = {
		"schema_version": "1.0",
		"collection_p95_ms": collection_summary["p95"],
		"migration_p95_ms": migration_summary["p95"],
		"decision_p95_ms": None,
		"final_horizon_ready": False,
	}
	return runtime_summary, horizon_inputs


def main() -> None:
	parser = argparse.ArgumentParser(description="Summarize runtime latency measurements")
	parser.add_argument("--collection-input", type=Path, required=True)
	parser.add_argument("--migration-input", type=Path, required=True)
	parser.add_argument(
		"--output-dir",
		type=Path,
		default=Path("data/benchmarks/runtime"),
	)
	args = parser.parse_args()

	runtime_summary, horizon_inputs = build_artifacts(
		read_records(args.collection_input),
		read_records(args.migration_input),
	)
	write_json(args.output_dir / "runtime_latency_summary.json", runtime_summary)
	write_json(args.output_dir / "forecast_horizon_inputs.json", horizon_inputs)


if __name__ == "__main__":
	main()
