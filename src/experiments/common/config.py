# config loader

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import yaml


def load_yaml(
    path: Path,
) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(
            f"config not found: {path}"
        )

    with path.open(
        encoding="utf-8",
    ) as stream:
        data = yaml.safe_load(stream)

    if not isinstance(data, dict):
        raise ValueError(
            "experiment config must be a mapping"
        )

    return data

# validate config for capacity benchmark
def validate_capacity_config(
    config: Dict[str, Any],
) -> None:
    required_sections = (
        "experiment",
        "scenarios",
        "workload",
        "timing",
        "qos_probe",
        "telemetry",
        "migration",
    )

    for section in required_sections:
        if section not in config:
            raise ValueError(
                f"missing config section: {section}"
            )

    experiment = config["experiment"]

    if not experiment.get("topology"):
        raise ValueError(
            "experiment.topology is required"
        )

    workload = config["workload"]

    rates = workload.get(
        "rates_fps",
        [],
    )

    if not rates:
        raise ValueError(
            "workload.rates_fps must not be empty"
        )

    for rate in rates:
        if float(rate) <= 0:
            raise ValueError(
                "all workload rates must be > 0"
            )

    timing = config["timing"]

    for field in (
        "warmup_seconds",
        "measurement_seconds",
        "cooldown_seconds",
    ):
        if float(timing[field]) <= 0:
            raise ValueError(
                f"{field} must be > 0"
            )

    if config["migration"].get(
        "enabled",
        True,
    ):
        raise ValueError(
            "migration must be disabled "
            "during capacity benchmark"
        )

    for controller_id in (
        "c1",
        "c2",
    ):
        if controller_id not in config["scenarios"]:
            raise ValueError(
                f"missing scenario: {controller_id}"
            )