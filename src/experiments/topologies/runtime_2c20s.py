#!/usr/bin/env python3

import argparse
from pathlib import Path

from mininet.cli import CLI
from mininet.link import TCLink
from mininet.log import setLogLevel
from mininet.net import Mininet
from mininet.node import OVSSwitch, RemoteController

from src.experiments.topologies.capacity_2c20s import (
    Capacity2C20STopo,
)
from scripts.experiments.run_forecast_stable_2c20s import (
    run_forecast_stable,
)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--forecast-stable",
        action="store_true",
        help="run the stable forecast smoke instead of opening the Mininet CLI",
    )
    parser.add_argument(
        "--capacity-runs",
        type=Path,
        help="benchmark CSV required by --forecast-stable",
    )
    parser.add_argument(
        "--controller-capacity",
        type=Path,
        default=Path("data/benchmarks/controller_capacity.json"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/experiment_runs/forecasting"),
    )
    parser.add_argument("--duration", type=float, default=60.0)
    parser.add_argument("--sample-interval", type=float, default=1.0)
    parser.add_argument("--target-utilization", type=float, default=0.60)
    parser.add_argument(
        "--orchestrator-url",
        default="http://127.0.0.1:9000",
    )
    return parser


def main() -> None:
    args = build_arg_parser().parse_args()
    if args.forecast_stable and args.capacity_runs is None:
        raise SystemExit("--capacity-runs is required with --forecast-stable")

    setLogLevel("info")

    net = Mininet(
        topo=Capacity2C20STopo(),
        controller=None,
        switch=OVSSwitch,
        link=TCLink,
        build=False,
    )

    # External Ryu controllers.
    net.addController(
        "c1",
        controller=RemoteController,
        ip="127.0.0.1",
        port=6653,
    )

    net.addController(
        "c2",
        controller=RemoteController,
        ip="127.0.0.1",
        port=6654,
    )

    try:
        print("*** Building 2C20S topology")
        net.build()

        print("*** Starting network")
        net.start()

        print()
        print("*** 2C20S runtime topology READY")
        print("*** Controllers:")
        print("***   C1 -> 127.0.0.1:6653")
        print("***   C2 -> 127.0.0.1:6654")
        print()
        print("*** DO NOT generate traffic yet.")
        print(
            "*** Init roles from another terminal:"
        )
        print(
            "*** curl -s -X POST "
            "http://127.0.0.1:9000/api/v1/init-roles | jq"
        )
        print()

        if args.forecast_stable:
            run_forecast_stable(
                net,
                capacity_runs_path=args.capacity_runs,
                controller_capacity_path=args.controller_capacity,
                output_dir=args.output_dir,
                duration_seconds=args.duration,
                sampling_interval_seconds=args.sample_interval,
                target_utilization=args.target_utilization,
                orchestrator_url=args.orchestrator_url,
            )
        else:
            CLI(net)

    finally:
        print("*** Stopping network")
        net.stop()


if __name__ == "__main__":
    main()