# Capacity benchmark implementation notes

This repository now includes a safe 2-controller, 4-switch capacity smoke
benchmark. These notes describe the implementation already present in the
repository; they are not instructions for applying an external overlay.

## Runtime components

- `src/experiments/capacity/collector.py` polls both controllers and the
	orchestrator during a run and writes raw JSONL streams.
- `src/experiments/capacity/aggregator.py` filters measurements by the metadata
	window and aggregates workload, controller, switch, QoS, snapshot, and
	collector-error data.
- `src/experiments/capacity/validator.py` rejects incomplete or unsafe runs.
- `src/experiments/capacity/capacity_runner.py` owns warm-up, measurement,
	cooldown, process cleanup, flow cleanup, and result validation.
- `src/experiments/topologies/capacity_smoke_2c4s.py` waits for both controllers
	to see all four switches before initializing roles.
- `src/experiments/workloads/qos_probe.py` and `qos_echo.py` provide the QoS
	flow setup measurement path.

The default experiment configuration is:

```text
configs/experiments/capacity_smoke_2c4s.yaml
```

It uses a 20-second measurement window, 1-second workload and telemetry sample
intervals, and a 5-second cooldown.

## Aggregation and validation contract

Each run writes these primary files under `data/experiment_runs/<run-id>/`:

- `metadata.json`
- `workload.jsonl`
- `controllers.jsonl`
- `switches.jsonl`
- `qos.jsonl`
- `snapshots.jsonl`
- `collector_errors.jsonl`
- `summary.json`
- `validation.json`

The summary includes means, maxima, p95 values, sample counts, QoS success
ratio, workload flow totals, and collector-error count. In particular, it
includes:

- `processed_packet_in_rate_p95`
- `response_p95_ms_p95`
- `measurement_samples.collector_errors`

Validation requires:

- workload and controller coverage of at least 80% of expected samples;
- at least one workload, controller, switch, and snapshot sample;
- no collector errors;
- valid snapshots throughout the measurement window;
- non-zero processed Packet-In and Flow-Mod rates;
- configured QoS success ratio when QoS probing is enabled;
- workload send errors within the configured limit.

For the default 20-second/1-second configuration, the coverage threshold is
16 samples for both workload and controller streams.

## Flow safety

The runner clears only experiment cookies before a run:

- `0x10`: reactive flows;
- `0x20`: verification flows;
- `0x30`: benchmark flows.

The table-miss cookie `0x0` is preserved. After cooldown, the runner checks
that all benchmark `0x30` flows have expired. A QoS process that exits during
warm-up also fails the run before measurement begins.

## Verification

Local verification:

```bash
python3 -m compileall -q src tests
python3 -m unittest discover -s tests/unit -v
```

CI additionally runs Ruff and Mypy over the experiment modules. The role,
telemetry, migration, snapshot, and rollback integration smoke test runs on a
self-hosted Linux/Mininet/OVS runner through `scripts/smoke_test.sh`.

Manual capacity preflight, tmux setup, the one-packet `0x30` gate, and the
focused/full benchmark commands are documented in:

```text
docs/capacity-benchmark.md
```
