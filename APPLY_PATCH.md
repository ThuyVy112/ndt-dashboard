# Apply and verify the capacity benchmark

This repository already contains the capacity benchmark implementation. This
file is a verification runbook, not an overlay patch. Do not unzip or rsync a
separate telemetry bundle on top of the repository.

## 1. Check the working tree

Run these commands before editing or applying additional changes:

```bash
git status
git log --oneline -5
```

Keep unrelated local changes intact. Review the current diff before committing:

```bash
git diff --stat
git diff
```

## 2. Prepare Python environments

The Ryu controllers and orchestrator use separate virtual environments:

```bash
python3 -m venv ~/ndt-venv
source ~/ndt-venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements-orchestrator.txt
pip install -r requirements-dev.txt
deactivate

source ~/ryu-venv/bin/activate
pip install -r requirements-controller-extra.txt
deactivate
```

The SDN host must also provide Mininet, Open vSwitch, `curl`, `jq`, `tmux`, and
passwordless sudo for the required OVS/Mininet commands.

## 3. Run local verification

From the repository root:

```bash
python3 -m compileall -q src tests
python3 -m unittest discover -s tests/unit -v
```

The unit suite covers the capacity aggregator, capacity validator, workload
generation, schemas, telemetry, and QoS argument validation. CI additionally
runs Ruff and Mypy over `src/experiments` and the existing application modules.

## 4. Run the existing SDN integration smoke test

On a prepared self-hosted Linux SDN runner:

```bash
./scripts/cleanup.sh
./scripts/smoke_test.sh
```

The integration smoke test starts C1, C2, and the orchestrator, creates the
2C4S topology, and verifies role initialization, telemetry, bidirectional
migration, snapshots, and rollback. The GitHub workflow is
`.github/workflows/integration.yml`.

## 5. Run the capacity benchmark

In separate terminals, start C1, C2, and the orchestrator, then run a focused
case from a fourth terminal:

```bash
./scripts/start_c1.sh
```

```bash
./scripts/start_c2.sh
```

```bash
RUN_ID=capacity ./scripts/start_orchestrator.sh
```

From the repository root, after the services are ready:

```bash
sudo -E env PYTHONPATH="$PWD" python3 \
	src/experiments/topologies/capacity_smoke_2c4s.py \
	--controller c1 \
	--rate 10 \
	--repeat 1
```

Run the complete configured matrix only after the focused case passes:

```bash
sudo -E env PYTHONPATH="$PWD" python3 \
	src/experiments/topologies/capacity_smoke_2c4s.py \
	--controller all
```

The topology waits for both controllers to report all four switches before
calling `/api/v1/init-roles`. The runner records workload, controller, switch,
QoS, snapshot, and collector-error streams, then aggregates and validates the
measurement window.

For the manual tmux preflight, one-packet gate, output schema, validation
thresholds, and cookie lifecycle, follow:

```text
docs/capacity-benchmark.md
```

## 6. Review outputs and cleanup

Completed runs are written to `data/experiment_runs/`. Review at least:

- `metadata.json` for topology counts and measurement timestamps;
- `summary.json` for means, maxima, p95 values, and sample counts;
- `validation.json` for validation errors and warnings;
- `collector_errors.jsonl` for collector failures.

Validation requires at least 80% workload/controller sample coverage, switch and
snapshot samples, valid snapshots, non-zero controller rates, no collector
errors, and the configured QoS success ratio.

After a failed or interrupted SDN run:

```bash
./scripts/cleanup.sh
```

The capacity runner clears only experiment cookies `0x10`, `0x20`, and `0x30`;
it preserves the table-miss cookie and verifies that benchmark flows expire
after cooldown.

## 7. Commit and pull request

Use a focused commit message for the completed feature:

```text
feat(capacity): add safe 2C4S capacity benchmark
```

Before opening the pull request, run the local verification commands, review
the diff, and update `.github/pull_request_template.md` with the actual checks
that passed. Target the integration branch according to the repository's branch
policy; do not force-push a branch shared with another developer.
