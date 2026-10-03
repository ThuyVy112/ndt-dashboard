#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.twin.forecasting.raw_validator import validate_raw_samples


REQUIRED_FIELDS = {
    "run_id",
    "controller_id",
    "observed_at",
    "workload_type",
    "workload_phase",
    "processed_packet_in_rate",
    "flow_mod_rate",
    "process_cpu_percent",
    "process_memory_rss_mb",
    "response_p95_ms",
    "managed_switch_count",
    "safe_capacity_pps",
    "utilization",
    "max_switch_control_load_share",
    "age_of_twin_ms",
    "twinning_rate",
    "completeness_ratio",
    "synchronization_jitter_ms",
    "snapshot_valid",
    "snapshot_id",
}


@dataclass(frozen=True)
class CollectionIssue:
    code: str
    message: str
    controller_id: str | None = None


@dataclass(frozen=True)
class CollectionValidationResult:
    valid: bool
    run_id: str
    total_samples: int
    samples_per_controller: dict[str, int]
    coverage_per_controller: dict[str, float]
    issues: tuple[CollectionIssue, ...]


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"required file not found: {path}")

    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"required file not found: {path}")

    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue

            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"{path}:{line_number}: invalid JSON"
                ) from exc

            if not isinstance(value, dict):
                raise ValueError(
                    f"{path}:{line_number}: row must be a JSON object"
                )

            rows.append(value)

    return rows


def validate_collection(
    *,
    metadata: dict[str, Any],
    samples: list[dict[str, Any]],
    min_coverage: float = 0.95,
    utilization_tolerance: float = 0.02,
    max_gap_seconds: float = 2.5,
) -> CollectionValidationResult:
    issues: list[CollectionIssue] = []

    run_id = str(metadata.get("run_id", "")).strip()
    workload_type = str(metadata.get("workload_type", "")).strip()

    try:
        duration_seconds = float(metadata["duration_seconds"])
        sampling_interval_seconds = float(
            metadata["sampling_interval_seconds"]
        )
    except (KeyError, TypeError, ValueError):
        duration_seconds = 0.0
        sampling_interval_seconds = 0.0
        issues.append(
            CollectionIssue(
                code="metadata_invalid",
                message=(
                    "duration_seconds and sampling_interval_seconds "
                    "must be present and positive"
                ),
            )
        )

    if duration_seconds <= 0 or sampling_interval_seconds <= 0:
        if not any(issue.code == "metadata_invalid" for issue in issues):
            issues.append(
                CollectionIssue(
                    code="metadata_invalid",
                    message=(
                        "duration_seconds and sampling_interval_seconds "
                        "must be positive"
                    ),
                )
            )

    controllers_raw = metadata.get("controllers", [])
    if not isinstance(controllers_raw, list):
        controllers_raw = []

    expected_controllers = tuple(
        str(value).strip()
        for value in controllers_raw
        if str(value).strip()
    )

    if not run_id:
        issues.append(
            CollectionIssue(
                code="run_id_missing",
                message="metadata.run_id must not be empty",
            )
        )

    if not workload_type:
        issues.append(
            CollectionIssue(
                code="workload_type_missing",
                message="metadata.workload_type must not be empty",
            )
        )

    if not expected_controllers:
        issues.append(
            CollectionIssue(
                code="controllers_missing",
                message="metadata.controllers must not be empty",
            )
        )

    if metadata.get("migration_enabled") is not False:
        issues.append(
            CollectionIssue(
                code="migration_enabled",
                message="official forecast collection requires migration_enabled=false",
            )
        )

    if not samples:
        issues.append(
            CollectionIssue(
                code="samples_empty",
                message="forecast_samples.jsonl contains no samples",
            )
        )

    counts: Counter[str] = Counter()
    capacities: dict[str, list[float]] = defaultdict(list)

    for index, sample in enumerate(samples):
        missing = sorted(REQUIRED_FIELDS - sample.keys())
        if missing:
            issues.append(
                CollectionIssue(
                    code="missing_fields",
                    message=(
                        f"sample {index} missing fields: "
                        + ", ".join(missing)
                    ),
                    controller_id=str(
                        sample.get("controller_id", "")
                    ).strip()
                    or None,
                )
            )

        sample_run_id = str(sample.get("run_id", "")).strip()
        controller_id = str(sample.get("controller_id", "")).strip()
        sample_workload = str(
            sample.get("workload_type", "")
        ).strip()
        workload_phase = str(
            sample.get("workload_phase", "")
        ).strip()

        if sample_run_id != run_id:
            issues.append(
                CollectionIssue(
                    code="run_id_mismatch",
                    message=(
                        f"sample {index} run_id={sample_run_id!r} "
                        f"does not match metadata run_id={run_id!r}"
                    ),
                    controller_id=controller_id or None,
                )
            )

        if controller_id not in expected_controllers:
            issues.append(
                CollectionIssue(
                    code="controller_unexpected",
                    message=(
                        f"sample {index} controller_id={controller_id!r} "
                        "is not listed in metadata.controllers"
                    ),
                    controller_id=controller_id or None,
                )
            )

        if controller_id:
            counts[controller_id] += 1

        if sample_workload != workload_type:
            issues.append(
                CollectionIssue(
                    code="workload_type_mismatch",
                    message=(
                        f"sample {index} workload_type={sample_workload!r} "
                        f"does not match metadata workload_type="
                        f"{workload_type!r}"
                    ),
                    controller_id=controller_id or None,
                )
            )

        if not workload_phase:
            issues.append(
                CollectionIssue(
                    code="workload_phase_missing",
                    message=f"sample {index} workload_phase is empty",
                    controller_id=controller_id or None,
                )
            )

        try:
            safe_capacity = float(sample["safe_capacity_pps"])
            processed_rate = float(sample["processed_packet_in_rate"])
            utilization = float(sample["utilization"])
        except (KeyError, TypeError, ValueError):
            continue

        if controller_id and math.isfinite(safe_capacity):
            capacities[controller_id].append(safe_capacity)

        if (
            math.isfinite(safe_capacity)
            and safe_capacity > 0
            and math.isfinite(processed_rate)
            and math.isfinite(utilization)
        ):
            expected_utilization = processed_rate / safe_capacity
            if not math.isclose(
                utilization,
                expected_utilization,
                rel_tol=utilization_tolerance,
                abs_tol=utilization_tolerance,
            ):
                issues.append(
                    CollectionIssue(
                        code="utilization_mismatch",
                        message=(
                            f"sample {index}: utilization={utilization:g}, "
                            f"processed/safe={expected_utilization:g}"
                        ),
                        controller_id=controller_id or None,
                    )
                )

    for controller_id, values in capacities.items():
        if not values:
            continue

        reference = values[0]
        for value in values[1:]:
            if not math.isclose(
                value,
                reference,
                rel_tol=1e-9,
                abs_tol=1e-9,
            ):
                issues.append(
                    CollectionIssue(
                        code="safe_capacity_inconsistent",
                        message=(
                            f"safe_capacity_pps changes within run for "
                            f"{controller_id}"
                        ),
                        controller_id=controller_id,
                    )
                )
                break

    expected_per_controller = 0
    if duration_seconds > 0 and sampling_interval_seconds > 0:
        expected_per_controller = int(
            round(duration_seconds / sampling_interval_seconds)
        )

    coverage: dict[str, float] = {}

    for controller_id in expected_controllers:
        count = counts.get(controller_id, 0)

        if expected_per_controller > 0:
            controller_coverage = count / expected_per_controller
        else:
            controller_coverage = 0.0

        coverage[controller_id] = controller_coverage

        if controller_coverage < min_coverage:
            issues.append(
                CollectionIssue(
                    code="coverage_below_threshold",
                    message=(
                        f"{controller_id}: {count}/"
                        f"{expected_per_controller} samples "
                        f"({controller_coverage:.3f}) < "
                        f"{min_coverage:.3f}"
                    ),
                    controller_id=controller_id,
                )
            )

    # Week 8 official continuity contract.
    #
    # Raw validation intentionally keeps the stricter Week 7 cadence
    # diagnostics. Official collection acceptance instead allows gaps
    # up to max_gap_seconds and handles them here.
    from datetime import datetime

    timestamps_by_controller: dict[str, list[datetime]] = defaultdict(list)

    for sample in samples:
        controller_id = str(
            sample.get("controller_id", "")
        ).strip()
        observed_at = sample.get("observed_at")

        if not controller_id or not isinstance(observed_at, str):
            continue

        try:
            timestamp = datetime.fromisoformat(
                observed_at.replace("Z", "+00:00")
            )
        except ValueError:
            continue

        timestamps_by_controller[controller_id].append(timestamp)

    for controller_id, timestamps in timestamps_by_controller.items():
        for previous, current in zip(
            timestamps,
            timestamps[1:],
        ):
            gap_seconds = (
                current - previous
            ).total_seconds()

            if gap_seconds > max_gap_seconds:
                issues.append(
                    CollectionIssue(
                        code="max_gap_exceeded",
                        message=(
                            f"{controller_id}: sampling gap "
                            f"{gap_seconds:.3f}s > "
                            f"{max_gap_seconds:.3f}s"
                        ),
                        controller_id=controller_id,
                    )
                )

    raw_result = validate_raw_samples(
        samples,
        expected_sampling_interval_seconds=(
            sampling_interval_seconds
            if sampling_interval_seconds > 0
            else 1.0
        ),
    )

    for issue in raw_result.issues:
        if issue.code in {
            "sampling_gap",
            "sampling_interval",
        }:
            continue
        issues.append(
            CollectionIssue(
                code=f"raw_{issue.code}",
                message=issue.message,
                controller_id=issue.controller_id,
            )
        )

    return CollectionValidationResult(
        valid=not issues,
        run_id=run_id,
        total_samples=len(samples),
        samples_per_controller=dict(counts),
        coverage_per_controller=coverage,
        issues=tuple(issues),
    )


def validate_run_directory(
    run_dir: Path,
    *,
    min_coverage: float = 0.95,
    max_gap_seconds: float = 2.5,
) -> CollectionValidationResult:
    metadata = _load_json(run_dir / "metadata.json")
    samples = _load_jsonl(run_dir / "forecast_samples.jsonl")

    return validate_collection(
        metadata=metadata,
        samples=samples,
        min_coverage=min_coverage,
        max_gap_seconds=max_gap_seconds,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate one Week 8 forecast collection run."
    )
    parser.add_argument("run_dir", type=Path)
    parser.add_argument(
        "--min-coverage",
        type=float,
        default=0.95,
    )

    parser.add_argument(
        "--max-gap-seconds",
        type=float,
        default=2.5,
        help="Maximum allowed per-controller sampling gap in seconds.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
    )
    args = parser.parse_args()

    result = validate_run_directory(
        args.run_dir,
        min_coverage=args.min_coverage,
        max_gap_seconds=args.max_gap_seconds,
    )

    payload = {
        **asdict(result),
        "issues": [asdict(issue) for issue in result.issues],
    }

    print(json.dumps(payload, indent=2))

    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(payload, indent=2) + "\n",
            encoding="utf-8",
        )

    return 0 if result.valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
