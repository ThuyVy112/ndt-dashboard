#!/usr/bin/env bash

set -euo pipefail


# ============================================================
# Configuration
# ============================================================

REPO_ROOT="$(git rev-parse --show-toplevel)"

cd "$REPO_ROOT"

CONTROLLERS=(
    c1
    c2
)

RATES=(
    10
    20
    50
    100
)

REPEATS=(
    1
    2
)

RUN_ROOT="data/experiment_runs"

EXPECTED_RUNS=16


# ============================================================
# Helpers
# ============================================================

cleanup_mininet() {
    echo
    echo "=== MININET CLEANUP ==="

    sudo mn -c >/dev/null 2>&1 || true
}


check_services() {
    echo
    echo "=== SERVICE PREFLIGHT ==="

    for url in \
        "http://127.0.0.1:8081/api/v1/telemetry" \
        "http://127.0.0.1:8082/api/v1/telemetry" \
        "http://127.0.0.1:9000/api/v1/state"
    do
        echo "CHECK: $url"

        if ! curl \
            -fsS \
            --max-time 3 \
            "$url" \
            >/dev/null
        then
            echo "ERROR: service unavailable:"
            echo "$url"
            exit 1
        fi
    done

    echo "SERVICE PREFLIGHT: PASS"
}


check_worktree() {
    echo
    echo "=== GIT PREFLIGHT ==="

    CURRENT_COMMIT="$(
        git rev-parse HEAD
    )"

    echo "HEAD: $CURRENT_COMMIT"

    if ! git diff --quiet; then
        echo
        echo "ERROR:"
        echo "Tracked unstaged changes exist."
        echo
        git status --short
        echo
        echo "Commit/stash them before official benchmark."
        exit 1
    fi

    if ! git diff --cached --quiet; then
        echo
        echo "ERROR:"
        echo "Staged but uncommitted changes exist."
        echo
        git status --short
        echo
        echo "Commit them before official benchmark."
        exit 1
    fi

    echo "GIT PREFLIGHT: PASS"
}


validate_existing_run() {
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


validate_new_run() {
    local run_id="$1"
    local run_dir="$2"

    echo
    echo "--- VALIDATE: $run_id ---"

    for required_file in \
        metadata.json \
        workload.jsonl \
        controllers.jsonl \
        switches.jsonl \
        snapshots.jsonl \
        qos.jsonl \
        summary.json \
        validation.json
    do
        if [ ! -f "$run_dir/$required_file" ]; then
            echo "ERROR: missing $required_file"
            return 1
        fi
    done

    if [ -f "$run_dir/failure.json" ]; then
        echo "ERROR: failure.json exists"
        cat "$run_dir/failure.json"
        return 1
    fi

    if [ -s "$run_dir/collector_errors.jsonl" ]; then
        echo "ERROR: collector errors exist"
        cat "$run_dir/collector_errors.jsonl"
        return 1
    fi

    local valid

    valid="$(
        jq -r \
            '.valid' \
            "$run_dir/validation.json"
    )"

    if [ "$valid" != "true" ]; then
        echo "ERROR: validation failed"

        jq . \
            "$run_dir/validation.json"

        return 1
    fi

    local run_commit
    local current_commit

    run_commit="$(
        jq -r \
            '.git_commit' \
            "$run_dir/metadata.json"
    )"

    current_commit="$(
        git rev-parse HEAD
    )"

    if [ "$run_commit" != "$current_commit" ]; then
        echo "ERROR: git commit mismatch"
        echo "RUN : $run_commit"
        echo "HEAD: $current_commit"
        return 1
    fi

    echo "VALIDATION: PASS"

    jq '{
        target_controller,
        target_new_flow_rate,
        measurement_samples,
        emitted_new_flow_rate_mean,
        processed_packet_in_rate_mean,
        processed_packet_in_rate_p95,
        flow_mod_rate_mean,
        cpu_p95,
        response_p95_ms_p95,
        qos_success_ratio,
        flow_setup_latency_p95_ms,
        snapshot_valid_ratio
    }' \
        "$run_dir/summary.json"
}


# ============================================================
# Start
# ============================================================

echo "============================================="
echo "2C4S CAPACITY SMOKE MATRIX"
echo "============================================="

echo "Repository:"
echo "$REPO_ROOT"

echo
echo "Expected runs:"
echo "$EXPECTED_RUNS"


# ============================================================
# Preflight
# ============================================================

check_worktree

check_services

cleanup_mininet


# ============================================================
# Run matrix
# ============================================================

for controller in "${CONTROLLERS[@]}"
do
    for rate in "${RATES[@]}"
    do
        for repeat in "${REPEATS[@]}"
        do
            repeat_text="$(
                printf '%02d' "$repeat"
            )"

            run_id="capacity-smoke-${controller}-${rate}-r${repeat_text}"

            run_dir="${RUN_ROOT}/${run_id}"

            echo
            echo "============================================="
            echo "RUN: $run_id"
            echo "============================================="

            if [ -d "$run_dir" ]; then

                if validate_existing_run "$run_dir"; then
                    echo "SKIP VALID EXISTING RUN:"
                    echo "$run_id"
                    continue
                fi

                echo
                echo "ERROR:"
                echo "Run directory exists but is incomplete/invalid:"
                echo "$run_dir"
                echo
                echo "Move it to _failed or remove it,"
                echo "then rerun the script."

                exit 1
            fi

            sudo -E env \
                PYTHONPATH="$REPO_ROOT" \
                python3 -m \
                src.experiments.topologies.capacity_smoke_2c4s \
                --controller "$controller" \
                --rate "$rate" \
                --repeat "$repeat"

            validate_new_run \
                "$run_id" \
                "$run_dir"

            echo
            echo "PASS: $run_id"

        done
    done
done


# ============================================================
# Final audit
# ============================================================

echo
echo "============================================="
echo "FINAL AUDIT"
echo "============================================="

RUN_COUNT="$(
    find "$RUN_ROOT" \
        -maxdepth 1 \
        -type d \
        -name 'capacity-smoke-*' \
        | wc -l
)"

VALIDATION_COUNT="$(
    find "$RUN_ROOT" \
        -maxdepth 2 \
        -type f \
        -path '*/capacity-smoke-*/validation.json' \
        | wc -l
)"

VALID_COUNT=0
INVALID_COUNT=0

for file in \
    "$RUN_ROOT"/capacity-smoke-*/validation.json
do
    if [ ! -f "$file" ]; then
        continue
    fi

    valid="$(
        jq -r '.valid' "$file"
    )"

    if [ "$valid" = "true" ]; then
        VALID_COUNT=$((VALID_COUNT + 1))
    else
        INVALID_COUNT=$((INVALID_COUNT + 1))

        echo
        echo "INVALID:"
        echo "$file"

        jq . "$file"
    fi
done


echo
echo "Run directories    : $RUN_COUNT"
echo "Validation files   : $VALIDATION_COUNT"
echo "Valid runs         : $VALID_COUNT"
echo "Invalid runs       : $INVALID_COUNT"


if [ "$RUN_COUNT" -ne "$EXPECTED_RUNS" ]; then
    echo
    echo "ERROR:"
    echo "Expected $EXPECTED_RUNS run directories."
    exit 1
fi


if [ "$VALIDATION_COUNT" -ne "$EXPECTED_RUNS" ]; then
    echo
    echo "ERROR:"
    echo "Expected $EXPECTED_RUNS validation files."
    exit 1
fi


if [ "$VALID_COUNT" -ne "$EXPECTED_RUNS" ]; then
    echo
    echo "ERROR:"
    echo "Not all runs are valid."
    exit 1
fi


echo
echo "============================================="
echo "2C4S CAPACITY SMOKE: PASS"
echo "============================================="

cleanup_mininet
