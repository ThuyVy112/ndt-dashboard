import csv
import json
import math
import tempfile
import unittest
from pathlib import Path

from src.experiments.workloads.capacity_mapper import CapacityWorkloadMapper


class CapacityWorkloadMapperTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        self.capacity_path = root / "capacity.json"
        self.benchmark_path = root / "benchmarks.csv"

        self.capacity_path.write_text(
            json.dumps({"controllers": {"c1": {"c_safe_pps": 100.0}}}),
            encoding="utf-8",
        )

        with self.benchmark_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=[
                    "controller",
                    "target_new_flow_rate",
                    "processed_packet_in_rate_mean",
                    "valid",
                ],
            )
            writer.writeheader()
            writer.writerows(
                [
                    {"controller": "c1", "target_new_flow_rate": 0.0, "processed_packet_in_rate_mean": 0.0, "valid": "true"},
                    {"controller": "c1", "target_new_flow_rate": 10.0, "processed_packet_in_rate_mean": 60.0, "valid": "true"},
                    {"controller": "c1", "target_new_flow_rate": 20.0, "processed_packet_in_rate_mean": 95.0, "valid": "true"},
                    {"controller": "c1", "target_new_flow_rate": 30.0, "processed_packet_in_rate_mean": 105.0, "valid": "true"},
                    {"controller": "c1", "target_new_flow_rate": 40.0, "processed_packet_in_rate_mean": 100.0, "valid": "true"},
                ]
            )

        self.mapper = CapacityWorkloadMapper(
            self.benchmark_path,
            self.capacity_path,
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_positive_utilization_is_accepted(self) -> None:
        rate = self.mapper.offered_rate_for_utilization("c1", 0.60)

        self.assertGreater(rate, 0.0)
        self.assertEqual(rate, 10.0)

    def test_overload_utilization_is_accepted(self) -> None:
        self.assertEqual(
            self.mapper.offered_rate_for_utilization("c1", 1.05),
            30.0,
        )

    def test_negative_or_non_finite_utilization_is_rejected(self) -> None:
        for utilization in (-0.1, math.nan, math.inf, -math.inf):
            with self.subTest(utilization=utilization):
                with self.assertRaisesRegex(
                    ValueError,
                    "target_utilization must be a finite non-negative number",
                ):
                    self.mapper.offered_rate_for_utilization("c1", utilization)

    def test_saturated_observations_are_excluded_from_interpolation(self) -> None:
        with self.assertWarns(RuntimeWarning):
            mapper = CapacityWorkloadMapper(
                self.benchmark_path,
                self.capacity_path,
            )

        with self.assertRaisesRegex(ValueError, "outside observed benchmark range"):
            mapper.offered_rate_for_utilization("c1", 1.10)


if __name__ == "__main__":
    unittest.main()