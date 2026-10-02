#!/usr/bin/env python3
from __future__ import annotations

from src.experiments.topologies.capacity_2c20s import (
    Capacity2C20STopo,
)


class ForecastHotSwitch2C20STopo(
    Capacity2C20STopo
):
    """
    2C20S forecasting topology with one additional
    local sink attached to every switch.

    Base topology:
        hi --- si

    Hot-switch extension:
        hi --- si --- hsi

    Local source-to-sink traffic avoids traversing
    the inter-switch chain, allowing spatially
    concentrated Packet-In load.
    """

    def build(self) -> None:
        super().build()

        for index in range(1, 21):
            sink = self.addHost(
                f"hs{index}",
                ip=f"10.0.0.{100 + index}/24",
                mac=(
                    "00:00:00:01:"
                    f"{index // 256:02x}:"
                    f"{index % 256:02x}"
                ),
            )

            self.addLink(
                sink,
                f"s{index}",
            )
