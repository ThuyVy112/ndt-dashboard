from __future__ import annotations

from typing import Any


def validate_summary(summary: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    validation = config["validation"]
    samples = summary["measurement_samples"]
    target = float(summary["target_new_flow_rate"])
    actual = float(summary["emitted_new_flow_rate_mean"])

    if actual <= 0:
        errors.append("emitted_rate_zero")
    elif abs(actual - target) / target > float(validation["emitted_rate_tolerance_ratio"]):
        errors.append("emitted_rate_out_of_tolerance")

    attempted = int(summary["workload_attempted_flows"])
    send_errors = int(summary["workload_send_errors"])
    if attempted and send_errors / attempted > float(validation["max_send_error_ratio"]):
        errors.append("send_error_ratio_too_high")
    if samples["workload"] <= 0:
        errors.append("workload_samples_missing")
    if samples["controller"] <= 0:
        errors.append("controller_samples_missing")
    if samples["switch"] <= 0:
        errors.append("switch_samples_missing")
    if samples.get("collector_errors", 0) > 0:
        errors.append("collector_errors_present")

    measurement_seconds = float(config["timing"]["measurement_seconds"])
    workload_interval = float(config["workload"]["sample_interval_seconds"])
    telemetry_interval = float(config["telemetry"]["interval_seconds"])
    expected_workload_samples = measurement_seconds / workload_interval
    expected_controller_samples = measurement_seconds / telemetry_interval
    minimum_coverage_ratio = 0.80

    if samples["workload"] < expected_workload_samples * minimum_coverage_ratio:
        errors.append("insufficient_workload_samples")
    if samples["controller"] < expected_controller_samples * minimum_coverage_ratio:
        errors.append("insufficient_controller_samples")

    if samples["snapshots"] <= 0:
        errors.append("snapshot_samples_missing")
    if summary["snapshot_valid_ratio"] < 1.0:
        errors.append("snapshot_invalid_in_measurement")
    if summary["processed_packet_in_rate_max"] <= 0:
        errors.append("processed_packet_in_rate_zero")
    if summary["flow_mod_rate_max"] <= 0:
        errors.append("flow_mod_rate_zero")

    if config["qos_probe"].get("enabled", False):
        if samples["qos"] <= 0:
            errors.append("qos_samples_missing")
        elif summary["qos_success_ratio"] < float(validation["min_qos_success_ratio"]):
            if validation.get("smoke_mode", False):
                errors.append("qos_success_ratio_too_low")
            else:
                warnings.append("qos_degradation_detected")

    return {"valid": not errors, "errors": errors, "warnings": warnings}
