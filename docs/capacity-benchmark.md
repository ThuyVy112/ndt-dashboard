# Capacity Benchmark

This document describes the 2-controller, 4-switch capacity smoke benchmark.
The benchmark measures controller load while a stable UDP new-flow workload runs
through the 2C4S Mininet topology.

## Prerequisites

The benchmark requires a Linux host with:

- Open vSwitch and Mininet;
- passwordless sudo for Mininet and OVS commands;
- Ryu installed in `~/ryu-venv`;
- the orchestrator dependencies installed in `~/ndt-venv`;
- ports `6653`, `6654`, `8081`, `8082`, and `9000` available.

The controller and orchestrator processes must be started before the topology:

```bash
./scripts/cleanup.sh
./scripts/start_c1.sh
./scripts/start_c2.sh
RUN_ID=capacity ./scripts/start_orchestrator.sh
```

Run the commands above from separate terminals. The controller scripts use the
Ryu virtual environment and the orchestrator script uses the NDT virtual
environment.

## Manual preflight and one-packet gate

For a manual run, keep the services and topology in separate `tmux` windows:
`c1`, `c2`, `orch`, `mn`, and `monitor`.

Start the controllers and orchestrator:

```bash
tmux send-keys -t ndt:c1 'cd ~/ndt-safe-load-balancing && ./scripts/start_c1.sh' C-m
tmux send-keys -t ndt:c2 'cd ~/ndt-safe-load-balancing && ./scripts/start_c2.sh' C-m
tmux send-keys -t ndt:orch 'cd ~/ndt-safe-load-balancing && RUN_ID="${RUN_ID}" ./scripts/start_orchestrator.sh' C-m
```

Confirm that the controller OpenFlow/API ports and the orchestrator API are
listening:

```bash
sleep 3
ss -ltn | grep -E ':(6653|6654|8081|8082|9000)\b'
```

Start the 2C4S Mininet topology in the `mn` window:

```bash
tmux send-keys -t ndt:mn 'cd ~/ndt-safe-load-balancing && sudo -E env PYTHONPATH="$PWD" python3 src/experiments/topologies/smoke_2c4s.py' C-m
```

Initialize roles only after the topology is connected. Save the response as
evidence and verify both controllers see all four switches:

```bash
EVIDENCE="$PWD/data/evidence/manual-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$EVIDENCE"

curl -s -X POST http://127.0.0.1:9000/api/v1/init-roles \
  | tee "$EVIDENCE/init-roles.json" \
  | jq '.ownership'

curl -s http://127.0.0.1:8081/api/v1/state \
  | jq '.switches[] | {switch_id, role}'
curl -s http://127.0.0.1:8082/api/v1/state \
  | jq '.switches[] | {switch_id, role}'

curl -s http://127.0.0.1:8081/api/v1/telemetry \
  | jq '.controller.managed_switch_count'
curl -s http://127.0.0.1:8082/api/v1/telemetry \
  | jq '.controller.managed_switch_count'
```

This role assignment freezes the expected topology ownership for the run. If
either controller restarts after this point, initialize roles again before
continuing.

Warm up each host pair without using `pingall`; the purpose is to let Ryu learn
the `mac_to_port` paths rather than to measure latency:

```text
mininet> h1 ping -c 2 h2
mininet> h2 ping -c 2 h1
mininet> h3 ping -c 2 h4
mininet> h4 ping -c 2 h3
```

Before starting the workload, remove stale experiment flows. Do not remove the
table-miss flow:

```bash
for sw in s1 s2 s3 s4; do
  sudo ovs-ofctl -O OpenFlow13 del-flows "$sw" 'cookie=0x10/0xffffffffffffffff'
  sudo ovs-ofctl -O OpenFlow13 del-flows "$sw" 'cookie=0x20/0xffffffffffffffff'
  sudo ovs-ofctl -O OpenFlow13 del-flows "$sw" 'cookie=0x30/0xffffffffffffffff'
done
```

Inspect the remaining flows if troubleshooting:

```bash
for sw in s1 s2 s3 s4; do
  echo "===== $sw ====="
  sudo ovs-ofctl -O OpenFlow13 dump-flows "$sw"
done
```

Start the UDP sinks on `h2` and `h4`:

```text
mininet> h2 pkill -f src.experiments.workloads.udp_sink || true
mininet> h4 pkill -f src.experiments.workloads.udp_sink || true
mininet> h2 python3 -m src.experiments.workloads.udp_sink --bind-ip 10.0.0.2 --port 9000 --report-every 5 > /tmp/udp-sink-h2.log 2>&1 &
mininet> h4 python3 -m src.experiments.workloads.udp_sink --bind-ip 10.0.0.4 --port 9000 --report-every 5 > /tmp/udp-sink-h4.log 2>&1 &
mininet> h2 pgrep -a python3
mininet> h4 pgrep -a python3
```

Run the one-packet gate separately for each controller path. Immediately after
sending the packet, every switch on that path must contain a benchmark flow
with cookie `0x30`:

```text
# C1 path: h1 -> h2, through s1 and s2
mininet> h1 python3 -c "import socket; s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM); s.bind(('10.0.0.1',12000)); s.sendto(b'x',('10.0.0.2',9000)); s.close()"
```

```bash
sudo ovs-ofctl -O OpenFlow13 dump-flows s1 | grep 'cookie=0x30'
sudo ovs-ofctl -O OpenFlow13 dump-flows s2 | grep 'cookie=0x30'
```

```text
# C2 path: h3 -> h4, through s3 and s4
mininet> h3 python3 -c "import socket; s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM); s.bind(('10.0.0.3',12000)); s.sendto(b'x',('10.0.0.4',9000)); s.close()"
```

```bash
sudo ovs-ofctl -O OpenFlow13 dump-flows s3 | grep 'cookie=0x30'
sudo ovs-ofctl -O OpenFlow13 dump-flows s4 | grep 'cookie=0x30'
```

The gate passes only when all four expected path switches create a `0x30`
flow. Do not restart either controller after this gate; a restart can change
role state and invalidate the evidence.

## Run the benchmark

From the repository root, run one controller, rate, and repeat first:

```bash
sudo -E env PYTHONPATH="$PWD" python3 \
  src/experiments/topologies/capacity_smoke_2c4s.py \
  --controller c1 \
  --rate 10 \
  --repeat 1
```

The topology waits until both controllers report all four switches before it
initializes roles. The runner then:

1. starts the workload, QoS probe, and telemetry collector;
2. records a warm-up, measurement, and cooldown period;
3. aggregates samples from the measurement window;
4. validates sample coverage, controller/switch telemetry, snapshots, QoS, and
   collector errors;
5. verifies that benchmark flows expire after cooldown.

To run the configured matrix for both controllers:

```bash
sudo -E env PYTHONPATH="$PWD" python3 \
  src/experiments/topologies/capacity_smoke_2c4s.py \
  --controller all
```

Use `--rate` and `--repeat` to run a focused case without the complete matrix.
The default configuration is `configs/experiments/capacity_smoke_2c4s.yaml`.

## Outputs

Runs are written below `data/experiment_runs/` using one directory per run.
A completed run contains:

- `metadata.json`: experiment parameters and measurement timestamps;
- `workload.jsonl`: generated-flow samples;
- `controllers.jsonl`: target-controller telemetry;
- `switches.jsonl`: target-controller switch telemetry;
- `qos.jsonl`: QoS probe results;
- `snapshots.jsonl`: snapshot samples;
- `collector_errors.jsonl`: collector failures, if any;
- `summary.json`: aggregated means, maxima, p95 values, and sample counts;
- `validation.json`: validation result and error codes.

The summary counts collector errors across the run. Any collector error makes
validation fail, even when other telemetry samples are present.

## Validation rules

For the default 20-second measurement and 1-second sample intervals, workload
and controller streams must each contain at least 16 samples. Validation also
requires:

- at least one workload, controller, switch, and snapshot sample;
- a valid snapshot for every snapshot sample;
- non-zero processed Packet-In and Flow-Mod rates;
- no collector errors;
- QoS success ratio of at least 95% when the QoS probe is enabled;
- workload send errors within the configured limit.

The summary includes `processed_packet_in_rate_p95` and
`response_p95_ms_p95` for later capacity and knee analysis.

## Flow cleanup

Before each run, the runner clears only experiment cookies:

- `0x10`: reactive flows;
- `0x20`: verification flows;
- `0x30`: benchmark flows.

The table-miss cookie `0x0` is not cleared. After cooldown, the runner waits
for all `0x30` benchmark flows to disappear before writing the final metadata.

If a run fails, clean the SDN state before retrying:

```bash
./scripts/cleanup.sh
```

## Verification

Fast local checks do not require Mininet:

```bash
python -m compileall -q src tests
python -m unittest discover -s tests/unit -v
```

The capacity benchmark itself requires the self-hosted Linux SDN environment
and is not run by the GitHub-hosted unit-test job.
