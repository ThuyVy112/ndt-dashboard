#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

CONFIG="configs/experiments/forecast_dataset_2c20s.yaml"

CAPACITY_RUNS="data/benchmarks/capacity_runs.csv"
CONTROLLER_CAPACITY="data/benchmarks/controller_capacity.json"
ORCHESTRATOR_URL="http://127.0.0.1:9000"

DRY_RUN=0
MODE=""
WORKLOAD=""
REPEAT=""
SKIP_EXISTING=0

usage() {
    cat <<'EOF'
Usage:
  collect_forecast_data.sh --dry-run
  collect_forecast_data.sh --dry-run --single WORKLOAD REPEAT
  collect_forecast_data.sh --single WORKLOAD REPEAT
  collect_forecast_data.sh --all
  collect_forecast_data.sh --all --skip-existing

Examples:
  collect_forecast_data.sh --dry-run
  collect_forecast_data.sh --dry-run --single stable 1
  collect_forecast_data.sh --single stable 1
  collect_forecast_data.sh --all
EOF
}

while (($#)); do
    case "$1" in
        --dry-run)
            DRY_RUN=1
            shift
            ;;

        --single)
            [[ $# -ge 3 ]] || {
                echo "--single requires WORKLOAD REPEAT" >&2
                exit 2
            }

            MODE="single"
            WORKLOAD="$2"
            REPEAT="$3"
            shift 3
            ;;

        --all)
            MODE="all"
            shift
            ;;

        --skip-existing)
            SKIP_EXISTING=1
            shift
            ;;

        -h|--help)
            usage
            exit 0
            ;;

        *)
            echo "Unknown argument: $1" >&2
            usage
            exit 2
            ;;
    esac
done

# --dry-run alone means show the entire official plan.
if [[ -z "$MODE" ]]; then
    if [[ "$DRY_RUN" -eq 1 ]]; then
        MODE="all"
    else
        usage
        exit 2
    fi
fi

# ----------------------------------------------------------
# Load official experiment contract from YAML.
# ----------------------------------------------------------

eval "$(
python3 - "$CONFIG" <<'PY'
import shlex
import sys
from pathlib import Path

import yaml

config = yaml.safe_load(
    Path(sys.argv[1]).read_text(encoding="utf-8")
)

experiment = config["experiment"]
timing = config["timing"]
validation = config["validation"]

values = {
    "EXPERIMENT_TYPE": experiment["type"],
    "TOPOLOGY_NAME": experiment["topology"],
    "OUTPUT_ROOT": experiment["output_root"],
    "DURATION": timing["duration_seconds"],
    "SAMPLE_INTERVAL": config["sampling_interval_seconds"],
    "MIN_COVERAGE": validation["min_sample_coverage_ratio"],
    "MAX_GAP": validation["max_gap_seconds"],
    "MAX_SEND_ERROR": validation["max_send_error_ratio"],
}

for key, value in values.items():
    print(f"{key}={shlex.quote(str(value))}")
PY
)"

# ----------------------------------------------------------
# Preflight static artifacts.
# ----------------------------------------------------------

for path in \
    "$CONFIG" \
    "$CAPACITY_RUNS" \
    "$CONTROLLER_CAPACITY" \
    "configs/controllers_2c20s.yaml"
do
    if [[ ! -f "$path" ]]; then
        echo "Missing required artifact: $path" >&2
        exit 1
    fi
done

GIT_COMMIT="$(git rev-parse HEAD)"

# ----------------------------------------------------------
# Official deterministic plan.
# ----------------------------------------------------------

mapfile -t PLAN < <(
python3 - "$CONFIG" <<'PY'
import sys
from pathlib import Path

import yaml

from scripts.experiments.forecast_collection_plan import (
    build_plan,
)

config = yaml.safe_load(
    Path(sys.argv[1]).read_text(encoding="utf-8")
)

for run in build_plan(config):
    print(
        f"{run.workload}|"
        f"{run.repeat_index}|"
        f"{run.seed}|"
        f"{run.run_id}"
    )
PY
)

run_one() {
    local workload="$1"
    local repeat="$2"
    local seed="$3"
    local run_id="$4"

    local run_dir="${OUTPUT_ROOT}/${run_id}"

    if [[ -e "$run_dir" ]]; then
        if [[ "$SKIP_EXISTING" -eq 1 ]]; then
            echo "[SKIP] existing run: $run_id"
            return 0
        fi

        echo "ERROR: official run directory already exists:" >&2
        echo "  $run_dir" >&2
        echo "Refusing to overwrite or append official data." >&2
        exit 1
    fi

    local workload_flag

    case "$workload" in
        stable)
            workload_flag="--forecast-stable"
            ;;
        gradual)
            workload_flag="--forecast-gradual"
            ;;
        burst)
            workload_flag="--forecast-burst"
            ;;
        oscillating)
            workload_flag="--forecast-oscillating"
            ;;
        hot-switch)
            workload_flag="--forecast-hot-switch"
            ;;
        *)
            echo "Unsupported workload: $workload" >&2
            exit 1
            ;;
    esac

    local -a cmd=(
        sudo -E env
        "PYTHONPATH=$ROOT"
        "$(which python3)"
        src/experiments/topologies/runtime_2c20s.py

        "$workload_flag"

        --capacity-runs
        "$CAPACITY_RUNS"

        --controller-capacity
        "$CONTROLLER_CAPACITY"

        --output-dir
        "$OUTPUT_ROOT"

        --duration
        "$DURATION"

        --sample-interval
        "$SAMPLE_INTERVAL"

        --run-id
        "$run_id"

        --experiment-type
        "$EXPERIMENT_TYPE"

        --topology-name
        "$TOPOLOGY_NAME"

        --repeat-index
        "$repeat"

        --seed
        "$seed"

        --capacity-artifact
        "$CONTROLLER_CAPACITY"

        --git-commit
        "$GIT_COMMIT"

        --orchestrator-url
        "$ORCHESTRATOR_URL"
    )

    echo
    echo "============================================================"
    echo "RUN_ID=$run_id"
    echo "WORKLOAD=$workload"
    echo "REPEAT=$repeat"
    echo "SEED=$seed"
    echo "OUTPUT=$run_dir"
    echo "CAPACITY_RUNS=$CAPACITY_RUNS"
    echo "CONTROLLER_CAPACITY=$CONTROLLER_CAPACITY"
    echo "GIT_COMMIT=$GIT_COMMIT"
    echo "============================================================"

    if [[ "$DRY_RUN" -eq 1 ]]; then
        printf 'COMMAND='
        printf ' %q' "${cmd[@]}"
        printf '\n'
        return 0
    fi

    "${cmd[@]}"
}

matched=0

for row in "${PLAN[@]}"; do
    IFS='|' read -r workload repeat seed run_id <<< "$row"

    if [[ "$MODE" == "single" ]]; then
        if [[ "$workload" != "$WORKLOAD" ||
              "$repeat" != "$REPEAT" ]]; then
            continue
        fi
    fi

    matched=$((matched + 1))
    run_one "$workload" "$repeat" "$seed" "$run_id"
done

if [[ "$matched" -eq 0 ]]; then
    echo "No official run matched request." >&2
    exit 1
fi

echo
echo "SELECTED_RUNS=$matched"

if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "DRY_RUN: PASS"
fi
