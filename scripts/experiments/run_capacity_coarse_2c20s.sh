#!/usr/bin/env bash

set -euo pipefail


REPO_ROOT="$(git rev-parse --show-toplevel)"

cd "$REPO_ROOT"


CONFIG="configs/experiments/capacity_coarse_2c20s.yaml"

RUN_ROOT="data/experiment_runs"

ALL_RATES=(
    25
    50
    100
    200
    400
    800
    1600
)

CONTROLLERS=(
    c1
    c2
)

REPEATS=(
    1
    2
)


# ------------------------------------------------------------
# Optional argument:
#
#   ./run_capacity_coarse_2c20s.sh 25
#
# runs only one offered rate.
#
# Without argument:
#
#   ./run_capacity_coarse_2c20s.sh
#
# runs the whole coarse matrix.
# ------------------------------------------------------------

if [ "$#" -eq 0 ]; then
    RATES=(
        "${ALL_RATES[@]}"
    )
elif [ "$#" -eq 1 ]; then
    REQUESTED_RATE="$1"

    valid_rate=false

    for candidate in "${ALL_RATES[@]}"; do
        if [ "$candidate" = "$REQUESTED_RATE" ]; then
            valid_rate=true
            break
        fi
    done

    if [ "$valid_rate" != "true" ]; then
        echo "Unsupported coarse rate:"
        echo "$REQUESTED_RATE"
        exit 1
    fi

    RATES=(
        "$REQUESTED_RATE"
    )
else
    echo "Usage:"
    echo "$0 [rate]"
    exit 1
fi


check_git() {
    echo
    echo "=== GIT PREFLIGHT ==="

    echo "HEAD:"
    git rev-parse HEAD

    if ! git diff --quiet; then
        echo "ERROR: unstaged tracked changes"
        git status --short
        exit 1
    fi

    if ! git diff --cached --quiet; then
        echo "ERROR: staged uncommitted changes"
        git status --short
        exit 1
    fi

    echo "GIT PREFLIGHT: PASS"
}


check_runtime() {
    echo
    echo "=== RUNTIME PREFLIGHT ==="

    for port in \
        6653 \
        6654 \
        8081 \
        8082 \
        9000
    do
        if ! timeout 2 bash -c \
            "</dev/tcp/127.0.0.1/$port" \
            2>/dev/null
        then
            echo "ERROR: port $port unavailable"
            exit 1
        fi

        echo "PASS: port $port"
    done

    ownership_count="$(
        curl -fsS \
        http://127.0.0.1:9000/api/v1/state \
        | jq '.ownership | length'
    )"

    if [ "$ownership_count" -ne 20 ]; then
        echo "ERROR:"
        echo "orchestrator does not use 2C20S config"
        echo "ownership entries: $ownership_count"
        exit 1
    fi

    echo "PASS: orchestrator ownership = 20"
}


check_existing_run() {
    local run_dir="$1"

    if [ ! -f "$run_dir/validation.json" ]; then
        return 1
    fi

    local valid

    valid="$(
        jq -r \
        '.valid // false' \
        "$run_dir/validation.json"
    )"

    [ "$valid" = "true" ]
}


check_git
check_runtime

sudo mn -c >/dev/null 2>&1 || true


for rate in "${RATES[@]}"; do

    echo
    echo "############################################"
    echo "COARSE RATE: $rate flows/s"
    echo "############################################"

    for controller in "${CONTROLLERS[@]}"; do

        for repeat in "${REPEATS[@]}"; do

            repeat_text="$(
                printf '%02d' "$repeat"
            )"

            run_id="$(
                printf \
                'capacity-2c20s-coarse-%s-%s-r%s' \
                "$controller" \
                "$rate" \
                "$repeat_text"
            )"

            run_dir="${RUN_ROOT}/${run_id}"

            echo
            echo "============================================"
            echo "RUN: $run_id"
            echo "============================================"

            if [ -d "$run_dir" ]; then

                if check_existing_run "$run_dir"; then
                    echo "SKIP valid existing run:"
                    echo "$run_id"
                    continue
                fi

                echo
                echo "ERROR:"
                echo "Existing run is incomplete or invalid:"
                echo "$run_dir"
                echo
                echo "Move it to _failed before rerunning."

                exit 1
            fi


            sudo -E env \
                PYTHONPATH="$REPO_ROOT" \
                python3 -m \
                src.experiments.topologies.capacity_smoke_2c20s \
                --config "$CONFIG" \
                --controller "$controller" \
                --rate "$rate" \
                --repeat "$repeat"


            if [ ! -f "$run_dir/validation.json" ]; then
                echo "ERROR: validation.json missing"
                exit 1
            fi


            valid="$(
                jq -r \
                    '.valid' \
                    "$run_dir/validation.json"
            )"

            if [ "$valid" != "true" ]; then
                echo "ERROR: invalid capacity run"

                jq . \
                    "$run_dir/validation.json"

                exit 1
            fi


            echo
            echo "SUMMARY:"

            jq '{
                target_controller,
                target_new_flow_rate,
                emitted_new_flow_rate_mean,
                processed_packet_in_rate_mean,
                processed_packet_in_rate_p95,
                processed_packet_in_rate_max,
                flow_mod_rate_mean,
                cpu_p95,
                response_p95_ms_p95,
                qos_success_ratio,
                flow_setup_latency_p95_ms,
                snapshot_valid_ratio,
                measurement_samples
            }' \
                "$run_dir/summary.json"


            echo
            echo "PASS: $run_id"

        done
    done
done


echo
echo "============================================"
echo "REQUESTED COARSE SWEEP COMPLETE"
echo "============================================"
