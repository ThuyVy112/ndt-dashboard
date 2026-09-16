from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from urllib.request import Request, urlopen

from mininet.link import TCLink
from mininet.log import setLogLevel
from mininet.net import Mininet
from mininet.node import OVSSwitch, RemoteController

from src.experiments.capacity.capacity_runner import run_capacity_experiment
from src.experiments.common.config import load_yaml, validate_capacity_config
from src.experiments.topologies.smoke_2c4s import Smoke2C4STopo


def post_json(url: str) -> dict:
    request = Request(url, data=b"", method="POST")
    with urlopen(request, timeout=10) as response:
        payload = json.load(response)
    if not isinstance(payload, dict):
        raise RuntimeError(f"expected JSON object from {url}")
    return payload


def get_json(url: str) -> dict:
    with urlopen(url, timeout=3) as response:
        payload = json.load(response)
    if not isinstance(payload, dict):
        raise RuntimeError(f"expected JSON object from {url}")
    return payload


def wait_for_controller_connections(
    config: dict,
    expected_switch_count: int = 4,
    timeout_seconds: float = 15.0,
) -> None:
    deadline = time.monotonic() + timeout_seconds
    urls = config["runtime"]["controller_urls"]

    while time.monotonic() < deadline:
        ready = True
        for base_url in urls.values():
            try:
                state = get_json(
                    str(base_url).rstrip("/") + "/api/v1/state"
                )
                switches = state.get("switches", [])
                if len(switches) < expected_switch_count:
                    ready = False
                    break
            except Exception:
                ready = False
                break

        if ready:
            return
        time.sleep(0.5)

    raise RuntimeError("controllers did not see all switches before timeout")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the 2C4S capacity smoke matrix")
    parser.add_argument("--config", default="configs/experiments/capacity_smoke_2c4s.yaml")
    parser.add_argument("--controller", choices=("c1", "c2", "all"), default="all")
    parser.add_argument("--rate", type=float)
    parser.add_argument("--repeat", type=int)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    repo_root = Path.cwd()
    config = load_yaml(repo_root / args.config)
    validate_capacity_config(config)
    setLogLevel("info")
    net = Mininet(
        topo=Smoke2C4STopo(),
        controller=None,
        switch=OVSSwitch,
        link=TCLink,
        build=False,
    )
    net.addController("c1", controller=RemoteController, ip="127.0.0.1", port=6653)
    net.addController("c2", controller=RemoteController, ip="127.0.0.1", port=6654)

    try:
        net.build()
        net.start()
        wait_for_controller_connections(
            config,
            expected_switch_count=4,
        )
        orchestrator_url = str(config["runtime"]["orchestrator_url"]).rstrip("/")
        roles = post_json(f"{orchestrator_url}/api/v1/init-roles")
        print("INIT_ROLES:", roles.get("ownership"), flush=True)
        controllers = ["c1", "c2"] if args.controller == "all" else [args.controller]
        rates = [args.rate] if args.rate is not None else config["workload"]["rates_fps"]
        repeats = [args.repeat] if args.repeat is not None else range(1, int(config["repeats"]) + 1)
        for controller_id in controllers:
            for rate in rates:
                for repeat_index in repeats:
                    run_dir = run_capacity_experiment(
                        net=net,
                        config=config,
                        controller_id=controller_id,
                        rate=float(rate),
                        repeat_index=int(repeat_index),
                        repo_root=repo_root,
                    )
                    print("PASS:", run_dir, flush=True)
    finally:
        net.stop()


if __name__ == "__main__":
    main()
