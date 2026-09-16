from __future__ import annotations

import unittest
from typing import Any

from src.experiments.capacity.validator import validate_summary


class CapacityValidatorTests(unittest.TestCase):
	def make_config(self, qos_enabled: bool = False, smoke_mode: bool = True) -> dict[str, Any]:
		return {
			"timing": {"measurement_seconds": 20},
			"workload": {"sample_interval_seconds": 1},
			"telemetry": {"interval_seconds": 1},
			"validation": {
				"emitted_rate_tolerance_ratio": 0.10,
				"max_send_error_ratio": 0.01,
				"min_qos_success_ratio": 0.95,
				"smoke_mode": smoke_mode,
			},
			"qos_probe": {"enabled": qos_enabled},
		}

	def make_summary(self) -> dict[str, Any]:
		return {
			"target_new_flow_rate": 20,
			"emitted_new_flow_rate_mean": 20,
			"workload_attempted_flows": 100,
			"workload_send_errors": 0,
			"measurement_samples": {
				"workload": 16,
				"controller": 16,
				"switch": 1,
				"qos": 1,
				"snapshots": 1,
				"collector_errors": 0,
			},
			"snapshot_valid_ratio": 1.0,
			"processed_packet_in_rate_max": 10,
			"flow_mod_rate_max": 10,
			"qos_success_ratio": 1.0,
		}

	def test_valid_summary_at_minimum_coverage(self) -> None:
		result = validate_summary(self.make_summary(), self.make_config())

		self.assertTrue(result["valid"])
		self.assertEqual(result["errors"], [])
		self.assertEqual(result["warnings"], [])

	def test_missing_switches_and_collector_errors_are_errors(self) -> None:
		summary = self.make_summary()
		summary["measurement_samples"]["switch"] = 0
		summary["measurement_samples"]["collector_errors"] = 2

		result = validate_summary(summary, self.make_config())

		self.assertFalse(result["valid"])
		self.assertIn("switch_samples_missing", result["errors"])
		self.assertIn("collector_errors_present", result["errors"])

	def test_coverage_below_eighty_percent_is_an_error(self) -> None:
		summary = self.make_summary()
		summary["measurement_samples"]["workload"] = 15
		summary["measurement_samples"]["controller"] = 15

		result = validate_summary(summary, self.make_config())

		self.assertFalse(result["valid"])
		self.assertIn("insufficient_workload_samples", result["errors"])
		self.assertIn("insufficient_controller_samples", result["errors"])

	def test_qos_failure_is_error_in_smoke_mode(self) -> None:
		summary = self.make_summary()
		summary["qos_success_ratio"] = 0.90

		result = validate_summary(
			summary,
			self.make_config(qos_enabled=True, smoke_mode=True),
		)

		self.assertFalse(result["valid"])
		self.assertIn("qos_success_ratio_too_low", result["errors"])
		self.assertEqual(result["warnings"], [])

	def test_qos_failure_is_warning_outside_smoke_mode(self) -> None:
		summary = self.make_summary()
		summary["qos_success_ratio"] = 0.90

		result = validate_summary(
			summary,
			self.make_config(qos_enabled=True, smoke_mode=False),
		)

		self.assertTrue(result["valid"])
		self.assertEqual(result["errors"], [])
		self.assertIn("qos_degradation_detected", result["warnings"])


if __name__ == "__main__":
	unittest.main()
