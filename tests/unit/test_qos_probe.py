from __future__ import annotations

import unittest
from argparse import Namespace

from src.experiments.workloads.qos_probe import validate_args


class QosProbeTests(unittest.TestCase):
    def make_args(self, rate: float = 2.0) -> Namespace:
        return Namespace(
            rate=rate,
            duration=10.0,
            timeout=1.0,
            target_port=9001,
            source_port_start=2000,
            source_port_end=10000,
            flow_idle_timeout=30.0,
        )

    def test_valid_config(self) -> None:
        validate_args(self.make_args())

    def test_zero_rate_rejected(self) -> None:
        with self.assertRaises(ValueError):
            validate_args(self.make_args(rate=0.0))


if __name__ == "__main__":
    unittest.main()
