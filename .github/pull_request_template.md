## Summary

Adds the 2C4S capacity smoke benchmark flow with telemetry collection, aggregation,
validation, QoS probing, and run cleanup.

## Changes

- Add capacity experiment configuration, runner, collector, aggregator, and validator.
- Aggregate workload, controller, switch, QoS, snapshot, and collector-error data within the measurement window.
- Add p95 controller metrics and enforce switch presence, collector-error absence, and 80% sample coverage.
- Build metadata from the complete runtime ownership state so a 2C4S run records four switches.
- Wait for both controllers to see all four switches before initializing roles.
- Clear reactive, verification, and benchmark cookies without removing table-miss flows.
- Verify benchmark flows expire after cooldown and fail early when the QoS process exits during warm-up.
- Add unit tests for the capacity aggregator, capacity validator, and QoS argument validation.

## Compatibility and Runtime Impact

- This changes the capacity experiment runtime and metadata/summary output.
- Existing controller, verification, and table-miss flows are preserved; only experiment cookies `0x10`, `0x20`, and `0x30` are cleared.
- Requires the 2C4S self-hosted SDN integration environment for end-to-end execution.

## Verification

- [x] `python -m py_compile` passes for the changed capacity and topology modules.
- [x] `python -m unittest tests.unit.test_capacity_aggregator -v` passes.
- [x] `python -m unittest tests.unit.test_capacity_validator -v` passes.
- [x] Cookie cleanup and flow-count helper smoke checks pass with mocked `ovs-ofctl` output.
- [ ] `python -m unittest discover -s tests/unit -v` passes.
- [ ] `ruff check ...` passes.
- [ ] `mypy ...` passes for MVP data/state modules.
- [ ] 2C4S self-hosted SDN integration test passes.

## Evidence

Targeted unit tests passed. Full unit, lint, type-check, and live SDN integration runs
remain to be executed in an environment with the required tooling and Mininet/OVS services.
