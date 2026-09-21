from __future__ import annotations

import csv
import statistics
from collections import defaultdict
from pathlib import Path


INPUT_PATH = Path(
    "data/benchmarks/capacity_runs.csv"
)

OUTPUT_PATH = Path(
    "data/benchmarks/"
    "capacity_fine_summary.csv"
)

FINE_RUN_PREFIX = (
    "capacity-2c20s-fine-"
)

EXPECTED_REPEATS = 5


def values(
    rows: list[dict[str, str]],
    field: str,
) -> list[float]:
    return [
        float(row[field])
        for row in rows
    ]


def mean(
    rows: list[dict[str, str]],
    field: str,
) -> float:
    return statistics.mean(
        values(rows, field)
    )


def sample_std(
    rows: list[dict[str, str]],
    field: str,
) -> float:
    data = values(
        rows,
        field,
    )

    if len(data) < 2:
        return 0.0

    return statistics.stdev(
        data
    )


def valid_setup_values(
    rows: list[dict[str, str]],
) -> list[float]:
    """
    flow_setup_latency_p95_ms == 0 can mean that
    no QoS probe succeeded in that run.

    Do not treat that value as an actual 0 ms
    setup latency.
    """

    result: list[float] = []

    for row in rows:
        qos_success = float(
            row["qos_success_ratio"]
        )

        if qos_success <= 0.0:
            continue

        result.append(
            float(
                row[
                    "flow_setup_latency_p95_ms"
                ]
            )
        )

    return result


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

    # Only use Day 6 fine runs.
    rows = [
        row
        for row in all_rows
        if row.get(
            "run_id",
            "",
        ).startswith(
            FINE_RUN_PREFIX
        )
    ]

    if not rows:
        raise SystemExit(
            "no fine capacity runs found in "
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

    summary_rows: list[
        dict[str, object]
    ] = []

    incomplete_groups: list[
        tuple[str, float, int]
    ] = []

    for (
        controller,
        rate,
    ), group in groups.items():

        if len(group) != EXPECTED_REPEATS:
            incomplete_groups.append(
                (
                    controller,
                    rate,
                    len(group),
                )
            )

        emitted = mean(
            group,
            "emitted_new_flow_rate_mean",
        )

        processed = mean(
            group,
            "processed_packet_in_rate_mean",
        )

        processed_std = sample_std(
            group,
            "processed_packet_in_rate_mean",
        )

        qos_values = values(
            group,
            "qos_success_ratio",
        )

        setup_values = (
            valid_setup_values(
                group
            )
        )

        setup_mean: float | None

        if setup_values:
            setup_mean = (
                statistics.mean(
                    setup_values
                )
            )
        else:
            setup_mean = None

        summary_rows.append(
            {
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

                "processed_std":
                    processed_std,

                "packet_in_per_flow":
                    (
                        processed
                        / emitted
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
                    (
                        setup_mean
                        if setup_mean
                        is not None
                        else ""
                    ),

                "qos_success_mean":
                    statistics.mean(
                        qos_values
                    ),

                "qos_success_min":
                    min(
                        qos_values
                    ),

                "snapshot_valid_mean":
                    mean(
                        group,
                        "snapshot_valid_ratio",
                    ),
            }
        )

    summary_rows.sort(
        key=lambda row: (
            str(
                row["controller"]
            ),
            float(
                row["target_rate"]
            ),
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
        f"{'RATE':>7}"
        f"{'N':>4}"
        f"{'EMIT':>9}"
        f"{'PIN_MEAN':>11}"
        f"{'PIN_STD':>10}"
        f"{'CPU95':>9}"
        f"{'RESP95':>10}"
        f"{'SETUP95':>10}"
        f"{'QOS':>8}"
        f"{'QOS_MIN':>10}"
    )

    for row in summary_rows:

        setup_value = (
            row["setup_p95_mean"]
        )

        if setup_value == "":
            setup_text = "N/A"
        else:
            setup_text = (
                f"{float(setup_value):.3f}"
            )

        print(
            f"{str(row['controller']):<5}"
            f"{float(row['target_rate']):>7.0f}"
            f"{int(row['repeats']):>4}"
            f"{float(row['emitted_mean']):>9.2f}"
            f"{float(row['processed_mean']):>11.2f}"
            f"{float(row['processed_std']):>10.2f}"
            f"{float(row['cpu_p95_mean']):>9.2f}"
            f"{float(row['response_p95_mean']):>10.3f}"
            f"{setup_text:>10}"
            f"{float(row['qos_success_mean']):>8.3f}"
            f"{float(row['qos_success_min']):>10.3f}"
        )

    print()
    print(
        f"wrote {len(summary_rows)} groups "
        f"to {OUTPUT_PATH}"
    )

    if incomplete_groups:
        print()
        print(
            "WARNING: fine groups without "
            f"{EXPECTED_REPEATS} repeats:"
        )

        for (
            controller,
            rate,
            count,
        ) in incomplete_groups:
            print(
                "  "
                f"{controller} "
                f"rate={rate:g}: "
                f"{count}/"
                f"{EXPECTED_REPEATS}"
            )


if __name__ == "__main__":
    main()
