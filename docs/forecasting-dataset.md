# Forecasting Dataset

This document describes the first raw-data contract for the Future Load
Predictor. It covers collection and validation only; feature engineering,
model training, and a standalone collection CLI are not implemented yet.

## Configuration

The forecast configuration is in `configs/forecasting/forecast.yaml`:

- sampling interval: 1 second;
- history window: 10 seconds;
- horizon method: measured runtime p95;
- raw features include utilization, processed Packet-In rate, Flow-Mod rate,
  process CPU and memory, response p95, managed switch count, and maximum
  switch control load share.

The experiment matrix is in
`configs/experiments/forecast_dataset_2c20s.yaml`. It defines the 2-controller,
20-switch workload set and smoke/full durations.

## Twin State Input

`ForecastDataRunner._samples_from_twin_state()` consumes the JSON returned by
`GET /api/v1/twin/state`. The key names are derived from
`src/schemas/twin.py`, not from a separate forecast-specific payload.

Top-level keys:

- `snapshot_id`
- `controllers`
- `quality`

Controller keys used by the converter:

- `controller_id`
- `processed_packet_in_rate`
- `safe_capacity_pps`
- `utilization`
- `flow_mod_rate`
- `process_cpu_percent`
- `process_memory_rss_mb`
- `response_p95_ms`
- `managed_switch_count`

Quality keys used by the converter:

- `age_of_twin_ms`
- `twinning_rate`
- `completeness_ratio`
- `synchronization_jitter_ms`
- `valid`

Controllers not listed in `ForecastRunConfig.controller_ids` are ignored.
`collection_latency_ms` is available in the Twin State controller object but is
not currently part of `ForecastRawSample`.

## Run Output

The runner writes one directory per run below its configured output directory:

- `metadata.json`: schema version, run id, workload, duration, sampling
  interval, configured controllers, and migration status;
- `workload.jsonl`: one `WorkloadPoint` record per sampling tick, including
  elapsed time, phase, target utilization, and optional hot-switch fields;
- `forecast_samples.jsonl`: one serialized `ForecastRawSample` per controller
  and observation;
- `validation.json`: validity, sample counts, issue counters, and structured
  validation issues;
- `summary.json`: total samples, samples per controller, and validation status.

The runner currently exposes a Python API through
`src/experiments/runners/forecast_data_runner.py`; no standalone CLI launcher
has been added.

## Validation

`validate_raw_samples()` validates samples per `(controller_id, observed_at)`
stream. It checks:

- non-empty controller and snapshot identifiers;
- finite positive safe capacity;
- finite non-negative utilization;
- valid and monotonic timestamps;
- duplicate timestamps;
- expected sampling intervals and longer sampling gaps.

A sample with `snapshot_valid: false` is not discarded. It remains in the raw
JSONL audit trail, while `invalid_snapshot_count` is incremented and a
`snapshot_invalid` issue is recorded.

## Horizon

`estimate_horizon()` sums collection, decision, and migration p95 runtime
latencies, converts the result to seconds, and rounds up to the configured
sample step:

```text
required_lead_time_seconds = (collection_p95_ms + decision_p95_ms + migration_p95_ms) / 1000
horizon_steps = ceil(required_lead_time_seconds / step_seconds)
effective_horizon_seconds = horizon_steps * step_seconds
```

A decision latency is required before a final horizon can be estimated.
