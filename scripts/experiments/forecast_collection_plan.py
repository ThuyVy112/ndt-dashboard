#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import yaml


DEFAULT_CONFIG = Path(
    "configs/experiments/forecast_dataset_2c20s.yaml"
)


@dataclass(frozen=True)
class ForecastCollectionRun:
    workload: str
    repeat_index: int
    seed: int
    run_id: str


def load_config(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = yaml.safe_load(handle)

    if not isinstance(value, dict):
        raise ValueError("forecast dataset config must be a mapping")

    return value


def build_plan(config: dict[str, Any]) -> list[ForecastCollectionRun]:
    workloads = config["workloads"]
    repeats = int(config["repeats"])
    seeds = config["seeds"]

    if not isinstance(workloads, list) or not workloads:
        raise ValueError("workloads must be a non-empty list")

    if not isinstance(seeds, list):
        raise ValueError("seeds must be a list")

    if repeats <= 0:
        raise ValueError("repeats must be positive")

    if len(seeds) != repeats:
        raise ValueError(
            "number of seeds must equal repeats"
        )

    if len(set(seeds)) != len(seeds):
        raise ValueError("seeds must be unique")

    runs: list[ForecastCollectionRun] = []

    for workload in workloads:
        workload_name = str(workload)

        for index in range(repeats):
            repeat_index = index + 1
            seed = int(seeds[index])

            # Deterministic run id: {workload}-r{NN}-s{seed},
            # e.g. stable-r01-s101 / hot-switch-r05-s105.
            # src.twin.forecasting.splitter.parse_run_id reads this format.
            run_id = (
                f"{workload_name}-r{repeat_index:02d}-s{seed}"
            )

            runs.append(
                ForecastCollectionRun(
                    workload=workload_name,
                    repeat_index=repeat_index,
                    seed=seed,
                    run_id=run_id,
                )
            )

    run_ids = [run.run_id for run in runs]

    if len(run_ids) != len(set(run_ids)):
        raise ValueError("generated run IDs are not unique")

    return runs


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG,
    )
    parser.add_argument(
        "--json",
        action="store_true",
    )
    args = parser.parse_args()

    config = load_config(args.config)
    runs = build_plan(config)

    if args.json:
        print(
            json.dumps(
                [asdict(run) for run in runs],
                indent=2,
            )
        )
    else:
        for run in runs:
            print(
                f"{run.run_id}\t"
                f"{run.workload}\t"
                f"repeat={run.repeat_index}\t"
                f"seed={run.seed}"
            )

        print(f"TOTAL={len(runs)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
