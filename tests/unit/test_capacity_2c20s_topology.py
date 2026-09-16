from __future__ import annotations

import unittest

from src.experiments.topologies.capacity_2c20s import (
    Capacity2C20STopo,
)


class Capacity2C20STopologyTests(
    unittest.TestCase
):
    def test_topology_shape(self) -> None:
        topo = Capacity2C20STopo()

        switches = sorted(
            topo.switches()
        )

        hosts = sorted(
            topo.hosts()
        )

        self.assertEqual(
            len(switches),
            20,
        )

        self.assertEqual(
            len(hosts),
            20,
        )

        for index in range(1, 21):
            self.assertIn(
                f"s{index}",
                switches,
            )

            self.assertIn(
                f"h{index}",
                hosts,
            )

    def test_each_host_connected_to_matching_switch(
        self,
    ) -> None:
        topo = Capacity2C20STopo()

        links = {
            frozenset(link)
            for link in topo.links()
        }

        for index in range(1, 21):
            self.assertIn(
                frozenset(
                    (
                        f"h{index}",
                        f"s{index}",
                    )
                ),
                links,
            )

    def test_switches_form_chain(
        self,
    ) -> None:
        topo = Capacity2C20STopo()

        links = {
            frozenset(link)
            for link in topo.links()
        }

        for index in range(1, 20):
            self.assertIn(
                frozenset(
                    (
                        f"s{index}",
                        f"s{index + 1}",
                    )
                ),
                links,
            )


if __name__ == "__main__":
    unittest.main()
