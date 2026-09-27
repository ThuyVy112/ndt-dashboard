#!/usr/bin/env python3

from mininet.cli import CLI
from mininet.link import TCLink
from mininet.log import setLogLevel
from mininet.net import Mininet
from mininet.node import OVSSwitch, RemoteController

from src.experiments.topologies.capacity_2c20s import (
    Capacity2C20STopo,
)


def main() -> None:
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

        CLI(net)

    finally:
        print("*** Stopping network")
        net.stop()


if __name__ == "__main__":
    main()