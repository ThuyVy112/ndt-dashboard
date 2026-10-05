import unittest
from pathlib import Path

from scripts.experiments.forecast_collection_plan import (
    build_plan,
    load_config,
)


CONFIG_PATH = Path(
    "configs/experiments/forecast_dataset_2c20s.yaml"
)


class ForecastCollectionPlanTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = load_config(CONFIG_PATH)

    def test_official_config_contract(self) -> None:
        self.assertEqual(
            self.config["schema_version"],
            "1.0",
        )
        self.assertEqual(
            self.config["experiment"]["type"],
            "forecast-dataset-2c20s",
        )
        self.assertEqual(
            self.config["experiment"]["topology"],
            "capacity_2c20s",
        )
        self.assertEqual(
            self.config["controllers"],
            ["c1", "c2"],
        )
        self.assertFalse(
            self.config["migration"]["enabled"]
        )

    def test_official_plan_contains_25_runs(self) -> None:
        runs = build_plan(self.config)

        self.assertEqual(len(runs), 25)
        self.assertEqual(
            len({run.run_id for run in runs}),
            25,
        )

    def test_first_and_last_run(self) -> None:
        runs = build_plan(self.config)

        self.assertEqual(
            runs[0].run_id,
            "stable-r01-s101",
        )
        self.assertEqual(
            runs[0].workload,
            "stable",
        )
        self.assertEqual(
            runs[0].repeat_index,
            1,
        )
        self.assertEqual(
            runs[0].seed,
            101,
        )

        self.assertEqual(
            runs[-1].run_id,
            "hot-switch-r05-s105",
        )
        self.assertEqual(
            runs[-1].workload,
            "hot-switch",
        )
        self.assertEqual(
            runs[-1].repeat_index,
            5,
        )
        self.assertEqual(
            runs[-1].seed,
            105,
        )

    def test_seed_maps_to_repeat(self) -> None:
        runs = build_plan(self.config)

        for run in runs:
            self.assertEqual(
                run.seed,
                100 + run.repeat_index,
            )

    def test_invalid_seed_count_is_rejected(self) -> None:
        config = dict(self.config)
        config["seeds"] = [101]

        with self.assertRaises(ValueError):
            build_plan(config)


if __name__ == "__main__":
    unittest.main()
