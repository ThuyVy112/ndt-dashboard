# loading and validating experiment configurations for the load balancing system
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import yaml

# loads experiment configuration from a YAML file and validates it
def load_yaml(
    path: Path,
) -> Dict[str, Any]:
    """
    Load a YAML experiment configuration.

    Raises:
        FileNotFoundError:
            When the configuration file does not exist.

        ValueError:
            When the YAML root is not a mapping.
    """

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


def validate_capacity_config(
    config: Dict[str, Any],
) -> None:
    """
    Validate configuration for a controller capacity experiment.

    This validator checks configuration correctness only.

    It must NOT decide whether a controller is overloaded or safe.
    Those decisions are made later from experiment results.
    """

    # =========================================================
    # 1. Required top-level sections
    # =========================================================

    required_sections = (
        "experiment",
        "runtime",
        "scenarios",
        "workload",
        "timing",
        "qos_probe",
        "telemetry",
        "migration",
        "validation",
    )

    for section in required_sections:
        if section not in config:
            raise ValueError(
                f"missing config section: {section}"
            )

    # =========================================================
    # 2. Experiment
    # =========================================================

    experiment = config["experiment"]

    if not isinstance(
        experiment,
        dict,
    ):
        raise ValueError(
            "experiment must be a mapping"
        )

    if not experiment.get("type"):
        raise ValueError(
            "experiment.type is required"
        )

    if not experiment.get("topology"):
        raise ValueError(
            "experiment.topology is required"
        )

    if not experiment.get("output_root"):
        raise ValueError(
            "experiment.output_root is required"
        )

    # =========================================================
    # 3. Runtime endpoints
    # =========================================================

    runtime = config["runtime"]

    if not isinstance(
        runtime,
        dict,
    ):
        raise ValueError(
            "runtime must be a mapping"
        )

    if not runtime.get(
        "orchestrator_url"
    ):
        raise ValueError(
            "runtime.orchestrator_url is required"
        )

    controller_urls = runtime.get(
        "controller_urls"
    )

    if not isinstance(
        controller_urls,
        dict,
    ):
        raise ValueError(
            "runtime.controller_urls "
            "must be a mapping"
        )

    for controller_id in (
        "c1",
        "c2",
    ):
        if not controller_urls.get(
            controller_id
        ):
            raise ValueError(
                "missing controller URL: "
                f"{controller_id}"
            )

    # =========================================================
    # 4. Scenarios
    # =========================================================

    scenarios = config["scenarios"]

    if not isinstance(
        scenarios,
        dict,
    ):
        raise ValueError(
            "scenarios must be a mapping"
        )

    required_scenario_fields = (
        "target_controller",
        "source_host",
        "source_ip",
        "target_host",
        "target_ip",
        "path_switches",
    )

    for controller_id in (
        "c1",
        "c2",
    ):
        if controller_id not in scenarios:
            raise ValueError(
                f"missing scenario: {controller_id}"
            )

        scenario = scenarios[
            controller_id
        ]

        if not isinstance(
            scenario,
            dict,
        ):
            raise ValueError(
                f"scenario {controller_id} "
                "must be a mapping"
            )

        for field in (
            required_scenario_fields
        ):
            if field not in scenario:
                raise ValueError(
                    f"missing scenarios."
                    f"{controller_id}.{field}"
                )

        if (
            scenario[
                "target_controller"
            ]
            != controller_id
        ):
            raise ValueError(
                f"scenarios.{controller_id}."
                "target_controller "
                f"must be {controller_id}"
            )

        path_switches = scenario[
            "path_switches"
        ]

        if (
            not isinstance(
                path_switches,
                list,
            )
            or not path_switches
        ):
            raise ValueError(
                f"scenarios.{controller_id}."
                "path_switches "
                "must be a non-empty list"
            )

    # =========================================================
    # 5. Workload
    # =========================================================

    workload = config["workload"]

    if not isinstance(
        workload,
        dict,
    ):
        raise ValueError(
            "workload must be a mapping"
        )

    protocol = str(
        workload.get(
            "protocol",
            "",
        )
    ).lower()

    if protocol != "udp":
        raise ValueError(
            "workload.protocol must be udp"
        )

    pattern = workload.get(
        "pattern"
    )

    if not pattern:
        raise ValueError(
            "workload.pattern is required"
        )

    target_port = int(
        workload.get(
            "target_port",
            0,
        )
    )

    if not 1 <= target_port <= 65535:
        raise ValueError(
            "workload.target_port "
            "must be in [1, 65535]"
        )

    rates = workload.get(
        "rates_fps",
        [],
    )

    if (
        not isinstance(
            rates,
            list,
        )
        or not rates
    ):
        raise ValueError(
            "workload.rates_fps "
            "must be a non-empty list"
        )

    for rate in rates:
        if float(rate) <= 0:
            raise ValueError(
                "all workload rates "
                "must be > 0"
            )

    # IMPORTANT:
    # This must be OUTSIDE the rate loop.
    sample_interval = float(
        workload.get(
            "sample_interval_seconds",
            0,
        )
    )

    if sample_interval <= 0:
        raise ValueError(
            "workload.sample_interval_seconds "
            "must be > 0"
        )

    source_port_start = int(
        workload.get(
            "source_port_start",
            0,
        )
    )

    source_port_end = int(
        workload.get(
            "source_port_end",
            0,
        )
    )

    if not (
        1024
        <= source_port_start
        <= 65535
    ):
        raise ValueError(
            "workload.source_port_start "
            "must be in [1024, 65535]"
        )

    if not (
        1024
        <= source_port_end
        <= 65535
    ):
        raise ValueError(
            "workload.source_port_end "
            "must be in [1024, 65535]"
        )

    if (
        source_port_start
        > source_port_end
    ):
        raise ValueError(
            "workload.source_port_start "
            "must be <= source_port_end"
        )

    flow_idle_timeout = float(
        workload.get(
            "flow_idle_timeout_seconds",
            0,
        )
    )

    if flow_idle_timeout <= 0:
        raise ValueError(
            "workload.flow_idle_timeout_seconds "
            "must be > 0"
        )

    port_reuse_safety_factor = float(
        workload.get(
            "port_reuse_safety_factor",
            0,
        )
    )

    if (
        port_reuse_safety_factor
        < 1.0
    ):
        raise ValueError(
            "workload."
            "port_reuse_safety_factor "
            "must be >= 1.0"
        )

    # =========================================================
    # 6. Timing
    # =========================================================

    timing = config["timing"]

    if not isinstance(
        timing,
        dict,
    ):
        raise ValueError(
            "timing must be a mapping"
        )

    warmup_seconds = float(
        timing.get(
            "warmup_seconds",
            -1,
        )
    )

    measurement_seconds = float(
        timing.get(
            "measurement_seconds",
            0,
        )
    )

    cooldown_seconds = float(
        timing.get(
            "cooldown_seconds",
            -1,
        )
    )

    # Warm-up may legally be zero.
    if warmup_seconds < 0:
        raise ValueError(
            "warmup_seconds must be >= 0"
        )

    # Measurement must contain actual samples.
    if measurement_seconds <= 0:
        raise ValueError(
            "measurement_seconds must be > 0"
        )

    # Cooldown may legally be zero.
    if cooldown_seconds < 0:
        raise ValueError(
            "cooldown_seconds must be >= 0"
        )

    # =========================================================
    # 7. Repeats
    # =========================================================

    repeats = int(
        config.get(
            "repeats",
            0,
        )
    )

    if repeats <= 0:
        raise ValueError(
            "repeats must be > 0"
        )

    # =========================================================
    # 8. QoS probe
    # =========================================================

    qos_probe = config["qos_probe"]

    if not isinstance(
        qos_probe,
        dict,
    ):
        raise ValueError(
            "qos_probe must be a mapping"
        )

    qos_enabled = bool(
        qos_probe.get(
            "enabled",
            False,
        )
    )

    if qos_enabled:
        qos_target_port = int(
            qos_probe.get(
                "target_port",
                0,
            )
        )

        if not (
            1
            <= qos_target_port
            <= 65535
        ):
            raise ValueError(
                "qos_probe.target_port "
                "must be in [1, 65535]"
            )

        if (
            qos_target_port
            == target_port
        ):
            raise ValueError(
                "qos_probe.target_port "
                "must differ from "
                "workload.target_port"
            )

        qos_rate = float(
            qos_probe.get(
                "rate_per_second",
                0,
            )
        )

        if qos_rate <= 0:
            raise ValueError(
                "qos_probe.rate_per_second "
                "must be > 0"
            )

        qos_timeout = float(
            qos_probe.get(
                "response_timeout_seconds",
                0,
            )
        )

        if qos_timeout <= 0:
            raise ValueError(
                "qos_probe."
                "response_timeout_seconds "
                "must be > 0"
            )

        qos_port_start = int(
            qos_probe.get(
                "source_port_start",
                0,
            )
        )

        qos_port_end = int(
            qos_probe.get(
                "source_port_end",
                0,
            )
        )

        if not (
            1024
            <= qos_port_start
            <= 65535
        ):
            raise ValueError(
                "qos_probe.source_port_start "
                "must be in [1024, 65535]"
            )

        if not (
            1024
            <= qos_port_end
            <= 65535
        ):
            raise ValueError(
                "qos_probe.source_port_end "
                "must be in [1024, 65535]"
            )

        if qos_port_start > qos_port_end:
            raise ValueError(
                "qos_probe.source_port_start "
                "must be <= "
                "qos_probe.source_port_end"
            )

        qos_idle_timeout = float(
            qos_probe.get(
                "flow_idle_timeout_seconds",
                0,
            )
        )

        if qos_idle_timeout <= 0:
            raise ValueError(
                "qos_probe."
                "flow_idle_timeout_seconds "
                "must be > 0"
            )

    # =========================================================
    # 9. Telemetry
    # =========================================================

    telemetry = config[
        "telemetry"
    ]

    if not isinstance(
        telemetry,
        dict,
    ):
        raise ValueError(
            "telemetry must be a mapping"
        )

    telemetry_interval = float(
        telemetry.get(
            "interval_seconds",
            0,
        )
    )

    if telemetry_interval <= 0:
        raise ValueError(
            "telemetry.interval_seconds "
            "must be > 0"
        )

    # =========================================================
    # 10. Migration safety
    # =========================================================

    migration = config[
        "migration"
    ]

    if not isinstance(
        migration,
        dict,
    ):
        raise ValueError(
            "migration must be a mapping"
        )

    if migration.get(
        "enabled",
        True,
    ):
        raise ValueError(
            "migration must be disabled "
            "during capacity benchmark"
        )

    # =========================================================
    # 11. Validation configuration
    # =========================================================

    validation = config[
        "validation"
    ]

    if not isinstance(
        validation,
        dict,
    ):
        raise ValueError(
            "validation must be a mapping"
        )

    emitted_tolerance = float(
        validation.get(
            "emitted_rate_tolerance_ratio",
            -1,
        )
    )

    if not (
        0.0
        <= emitted_tolerance
        <= 1.0
    ):
        raise ValueError(
            "validation."
            "emitted_rate_tolerance_ratio "
            "must be in [0, 1]"
        )

    max_send_error_ratio = float(
        validation.get(
            "max_send_error_ratio",
            -1,
        )
    )

    if not (
        0.0
        <= max_send_error_ratio
        <= 1.0
    ):
        raise ValueError(
            "validation."
            "max_send_error_ratio "
            "must be in [0, 1]"
        )

    min_qos_success_ratio = float(
        validation.get(
            "min_qos_success_ratio",
            -1,
        )
    )

    if not (
        0.0
        <= min_qos_success_ratio
        <= 1.0
    ):
        raise ValueError(
            "validation."
            "min_qos_success_ratio "
            "must be in [0, 1]"
        )