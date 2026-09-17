from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any


RUN_ROOT = Path(
    "data/experiment_runs"
)

OUTPUT_PATH = Path(
    "data/benchmarks/capacity_runs.csv"
)

PATTERN = (
    "capacity-2c20s-coarse-*/summary.json"
)


def load_json(
    path: Path,
) -> dict[str, Any]:
    return json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )


def main() -> None:
    rows: list[dict[str, Any]] = []

    for summary_path in sorted(
        RUN_ROOT.glob(PATTERN)
    ):
        run_dir = (
            summary_path.parent
        )

        metadata_path = (
            run_dir / "metadata.json"
        )

        validation_path = (
            run_dir / "validation.json"
        )

        if (
            not metadata_path.exists()
            or not validation_path.exists()
        ):
            continue

        metadata = load_json(
            metadata_path
        )

        summary = load_json(
            summary_path
        )

        validation = load_json(
            validation_path
        )

        samples = summary.get(
            "measurement_samples",
            {},
        )

        rows.append({
            "run_id":
                summary["run_id"],

            "git_commit":
                metadata["git_commit"],

            "controller":
                summary[
                    "target_controller"
                ],

            "repeat_index":
                metadata["repeat_index"],

            "target_new_flow_rate":
                summary[
                    "target_new_flow_rate"
                ],

            "emitted_new_flow_rate_mean":
                summary[
                    "emitted_new_flow_rate_mean"
                ],

            "processed_packet_in_rate_mean":
                summary[
                    "processed_packet_in_rate_mean"
                ],

            "processed_packet_in_rate_p95":
                summary[
                    "processed_packet_in_rate_p95"
                ],

            "processed_packet_in_rate_max":
                summary[
                    "processed_packet_in_rate_max"
                ],

            "flow_mod_rate_mean":
                summary[
                    "flow_mod_rate_mean"
                ],

            "flow_mod_rate_max":
                summary[
                    "flow_mod_rate_max"
                ],

            "cpu_mean":
                summary[
                    "cpu_mean"
                ],

            "cpu_p95":
                summary[
                    "cpu_p95"
                ],

            "response_p95_ms_mean":
                summary[
                    "response_p95_ms_mean"
                ],

            "response_p95_ms_p95":
                summary[
                    "response_p95_ms_p95"
                ],

            "response_p95_ms_max":
                summary[
                    "response_p95_ms_max"
                ],

            "qos_success_ratio":
                summary[
                    "qos_success_ratio"
                ],

            "flow_setup_latency_p95_ms":
                summary[
                    "flow_setup_latency_p95_ms"
                ],

            "snapshot_valid_ratio":
                summary[
                    "snapshot_valid_ratio"
                ],

            "workload_samples":
                samples.get(
                    "workload",
                    0,
                ),

            "controller_samples":
                samples.get(
                    "controller",
                    0,
                ),

            "switch_samples":
                samples.get(
                    "switch",
                    0,
                ),

            "qos_samples":
                samples.get(
                    "qos",
                    0,
                ),

            "snapshot_samples":
                samples.get(
                    "snapshots",
                    0,
                ),

            "collector_errors":
                samples.get(
                    "collector_errors",
                    0,
                ),

            "valid":
                validation.get(
                    "valid",
                    False,
                ),

            "errors":
                "|".join(
                    validation.get(
                        "errors",
                        [],
                    )
                ),

            "warnings":
                "|".join(
                    validation.get(
                        "warnings",
                        [],
                    )
                ),
        })


    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    if not rows:
        print(
            "No coarse capacity runs found."
        )
        return


    fieldnames = list(
        rows[0].keys()
    )

    with OUTPUT_PATH.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as handle:

        writer = csv.DictWriter(
            handle,
            fieldnames=fieldnames,
        )

        writer.writeheader()

        writer.writerows(
            rows
        )


    print(
        f"wrote {len(rows)} runs "
        f"to {OUTPUT_PATH}"
    )


if __name__ == "__main__":
    main()
