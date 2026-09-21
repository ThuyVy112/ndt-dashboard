# Data Layout

## experiment_runs/

Raw, immutable experiment outputs.

Each run contains:

- metadata.json
- workload.jsonl
- controllers.jsonl
- switches.jsonl
- snapshots.jsonl
- qos.jsonl
- summary.json
- validation.json
- logs/

`_archive/` contains previous smoke/debug runs and must not be used
automatically as official training data.

## raw/

Legacy Week 4 telemetry output.

Do not use directly for ML training.

## snapshots/

Legacy Week 4 network snapshots.

Do not use directly for ML training.

## benchmarks/

Derived controller-capacity artifacts:

- capacity_runs.csv
- capacity_breakpoints.json
- controller_capacity.json

## forecasting/

Datasets for Future Load Predictor.

- raw/: aligned raw time series
- processed/: feature-engineered dataset
- splits/: train/validation/test
- reports/: dataset quality/statistics

## outcome/

Datasets for the Post-Migration Outcome Model.
