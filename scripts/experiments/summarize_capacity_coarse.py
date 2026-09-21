from __future__ import annotations

import csv
import statistics
from collections import defaultdict
from pathlib import Path


INPUT_PATH = Path(
    "data/benchmarks/capacity_runs.csv"
)

OUTPUT_PATH = Path(
    "data/benchmarks/reports/"
    "capacity_coarse_summary.csv"
)

COARSE_RUN_PREFIX = (
    "capacity-2c20s-coarse-"
)


def mean(
    rows: list[dict[str, str]],
    field: str,
) -> float:
    return statistics.mean(
        float(row[field])
        for row in rows
    )


def main() -> None:
    if not INPUT_PATH.exists():
        raise SystemExit(
            "capacity_runs.csv does not exist"
        )

    with INPUT_PATH.open(
        newline="",
        encoding="utf-8",
    ) as handle:
        all_rows = list(
            csv.DictReader(handle)
        )

    rows = [
       row
       for row in all_rows
       if row.get(
           "run_id",
           "",
       ).startswith(
           COARSE_RUN_PREFIX
       )
    ]

    if not rows:
        raise SystemExit(
            "no coarse capacity runs found in "
            "capacity_runs.csv"
        ) 

    groups: dict[
        tuple[str, float],
        list[dict[str, str]],
    ] = defaultdict(list)


    for row in rows:
        groups[
            (
                row["controller"],
                float(
                    row[
                        "target_new_flow_rate"
                    ]
                ),
            )
        ].append(row)


    summary_rows = []

    for (
        controller,
        rate,
    ), group in groups.items():

        emitted = mean(
            group,
            "emitted_new_flow_rate_mean",
        )

        processed = mean(
            group,
            "processed_packet_in_rate_mean",
        )

        summary_rows.append({
            "controller":
                controller,

            "target_rate":
                rate,

            "repeats":
                len(group),

            "emitted_mean":
                emitted,

            "processed_mean":
                processed,

            "packet_in_per_flow":
                (
                    processed / emitted
                    if emitted > 0
                    else 0.0
                ),

            "processed_p95_mean":
                mean(
                    group,
                    "processed_packet_in_rate_p95",
                ),

            "flow_mod_mean":
                mean(
                    group,
                    "flow_mod_rate_mean",
                ),

            "cpu_p95_mean":
                mean(
                    group,
                    "cpu_p95",
                ),

            "response_p95_mean":
                mean(
                    group,
                    "response_p95_ms_p95",
                ),

            "setup_p95_mean":
                mean(
                    group,
                    "flow_setup_latency_p95_ms",
                ),

            "qos_success_mean":
                mean(
                    group,
                    "qos_success_ratio",
                ),

            "snapshot_valid_mean":
                mean(
                    group,
                    "snapshot_valid_ratio",
                ),
        })


    summary_rows.sort(
        key=lambda row: (
            row["controller"],
            row["target_rate"],
        )
    )


    OUTPUT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    fieldnames = list(
        summary_rows[0].keys()
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
            summary_rows
        )


    print(
        f"{'CTRL':<5}"
        f"{'RATE':>8}"
        f"{'N':>4}"
        f"{'EMIT':>10}"
        f"{'PIN':>12}"
        f"{'PIN/FLOW':>11}"
        f"{'CPU95':>9}"
        f"{'RESP95':>10}"
        f"{'SETUP95':>10}"
        f"{'QOS':>8}"
    )


    for row in summary_rows:
        print(
            f"{row['controller']:<5}"
            f"{row['target_rate']:>8.0f}"
            f"{row['repeats']:>4}"
            f"{row['emitted_mean']:>10.2f}"
            f"{row['processed_mean']:>12.2f}"
            f"{row['packet_in_per_flow']:>11.3f}"
            f"{row['cpu_p95_mean']:>9.2f}"
            f"{row['response_p95_mean']:>10.3f}"
            f"{row['setup_p95_mean']:>10.3f}"
            f"{row['qos_success_mean']:>8.3f}"
        )


if __name__ == "__main__":
    main()
