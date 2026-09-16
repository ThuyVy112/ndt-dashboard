#!/usr/bin/env python3

from __future__ import annotations

from mininet.topo import Topo


class Capacity2C20STopo(Topo):
    """
    Capacity benchmark topology:

        h1--s1--s2--...--s10--s11--...--s20--h20

    Each switch has one directly attached host:

        h1  <-> s1
        h2  <-> s2
        ...
        h20 <-> s20

    Initial ownership:

        s1..s10  -> c1
        s11..s20 -> c2
    """

    def build(self) -> None:
        switches: list[str] = []

        for index in range(1, 21):
            switch = self.addSwitch(
                f"s{index}",
                dpid=f"{index:016x}",
                protocols="OpenFlow13",
            )

            host = self.addHost(
                f"h{index}",
                ip=f"10.0.0.{index}/24",
                mac=f"00:00:00:00:00:{index:02x}",
            )

            self.addLink(
                host,
                switch,
            )

            switches.append(
                switch
            )

        for index in range(
            len(switches) - 1
        ):
            self.addLink(
                switches[index],
                switches[index + 1],
            )
