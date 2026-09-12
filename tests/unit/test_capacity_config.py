from __future__ import annotations

import unittest
from pathlib import Path

from src.experiments.common.config import (
    load_yaml,
    validate_capacity_config,
)


class CapacityConfigTests(
    unittest.TestCase
):
    def test_smoke_config_is_valid(
        self,
    ):
        config = load_yaml(
            Path(
                "configs/experiments/"
                "capacity_smoke_2c4s.yaml"
            )
        )

        validate_capacity_config(
            config
        )

        self.assertFalse(
            config["migration"]["enabled"]
        )

        self.assertEqual(
            config["workload"]["rates_fps"],
            [
                10,
                20,
                50,
                100,
            ],
        )


if __name__ == "__main__":
    unittest.main()