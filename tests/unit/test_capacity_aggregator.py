from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from src.experiments.capacity.aggregator import aggregate_run


class CapacityAggregatorTests(unittest.TestCase):
	def write_jsonl(
		self,
		run_dir: Path,
		name: str,
		rows: list[dict[str, object]],
	) -> None:
		(run_dir / name).write_text(
			"".join(json.dumps(row) + "\n" for row in rows),
			encoding="utf-8",
		)

	def test_aggregate_run_filters_samples_and_calculates_metrics(self) -> None:
		with tempfile.TemporaryDirectory() as temporary_dir:
			run_dir = Path(temporary_dir)
			(run_dir / "metadata.json").write_text(
				json.dumps(
					{
						"run_id": "run-1",
						"target_controller": "c1",
						"target_new_flow_rate": 20,
						"measurement_started_at": "2026-09-16T10:00:00Z",
						"measurement_ended_at": "2026-09-16T10:20:00Z",
					}
				),
				encoding="utf-8",
			)
			self.write_jsonl(
				run_dir,
				"workload.jsonl",
				[
					{
						"observed_at": "2026-09-16T10:00:00Z",
						"emitted_new_flow_rate": 10,
						"attempted_flows": 2,
						"send_errors": 1,
					},
					{
						"observed_at": "2026-09-16T10:10:00Z",
						"emitted_new_flow_rate": 20,
						"attempted_flows": 3,
						"send_errors": 0,
					},
					{
						"observed_at": "2026-09-16T10:20:00Z",
						"emitted_new_flow_rate": 999,
						"attempted_flows": 99,
						"send_errors": 99,
					},
				],
			)
			self.write_jsonl(
				run_dir,
				"controllers.jsonl",
				[
					{
						"controller_id": "c1",
						"observed_at": "2026-09-16T10:01:00Z",
						"processed_packet_in_rate": 10,
						"flow_mod_rate": 2,
						"process_cpu_percent": 30,
						"response_p95_ms": 100,
					},
					{
						"controller_id": "c1",
						"observed_at": "2026-09-16T10:02:00Z",
						"processed_packet_in_rate": 30,
						"flow_mod_rate": 4,
						"process_cpu_percent": 50,
						"response_p95_ms": 300,
					},
					{
						"controller_id": "c2",
						"observed_at": "2026-09-16T10:03:00Z",
						"processed_packet_in_rate": 999,
						"flow_mod_rate": 999,
						"process_cpu_percent": 999,
						"response_p95_ms": 999,
					},
				],
			)
			self.write_jsonl(
				run_dir,
				"switches.jsonl",
				[
					{
						"controller_id": "c1",
						"observed_at": "2026-09-16T10:04:00Z",
					},
					{
						"controller_id": "c2",
						"observed_at": "2026-09-16T10:05:00Z",
					},
				],
			)
			self.write_jsonl(
				run_dir,
				"qos.jsonl",
				[
					{
						"observed_at": "2026-09-16T10:06:00Z",
						"success": True,
						"flow_setup_latency_ms": 25,
					},
					{
						"observed_at": "2026-09-16T10:07:00Z",
						"success": False,
						"flow_setup_latency_ms": 100,
					},
				],
			)
			self.write_jsonl(
				run_dir,
				"snapshots.jsonl",
				[
					{
						"created_at": "2026-09-16T10:08:00Z",
						"quality": {"valid": True},
					},
					{
						"created_at": "2026-09-16T10:09:00Z",
						"quality": {"valid": False},
					},
				],
			)
			self.write_jsonl(
				run_dir,
				"collector_errors.jsonl",
				[
					{"observed_at": "2026-09-16T10:06:00Z", "error": "timeout"},
					{"observed_at": "2026-09-16T10:30:00Z", "error": "timeout"},
				],
			)

			summary = aggregate_run(run_dir)

		self.assertEqual(summary["measurement_samples"], {
			"workload": 2,
			"controller": 2,
			"switch": 1,
			"qos": 2,
			"snapshots": 2,
			"collector_errors": 2,
		})
		self.assertEqual(summary["emitted_new_flow_rate_mean"], 15.0)
		self.assertEqual(summary["processed_packet_in_rate_mean"], 20.0)
		self.assertEqual(summary["processed_packet_in_rate_p95"], 30.0)
		self.assertEqual(summary["processed_packet_in_rate_max"], 30.0)
		self.assertEqual(summary["flow_mod_rate_mean"], 3.0)
		self.assertEqual(summary["cpu_mean"], 40.0)
		self.assertEqual(summary["cpu_p95"], 50.0)
		self.assertEqual(summary["response_p95_ms_mean"], 200.0)
		self.assertEqual(summary["response_p95_ms_p95"], 300.0)
		self.assertEqual(summary["response_p95_ms_max"], 300.0)
		self.assertEqual(summary["qos_success_ratio"], 0.5)
		self.assertEqual(summary["flow_setup_latency_p95_ms"], 25.0)
		self.assertEqual(summary["snapshot_valid_ratio"], 0.5)
		self.assertEqual(summary["workload_attempted_flows"], 5)
		self.assertEqual(summary["workload_send_errors"], 1)

	def test_missing_optional_streams_produce_empty_metrics(self) -> None:
		with tempfile.TemporaryDirectory() as temporary_dir:
			run_dir = Path(temporary_dir)
			(run_dir / "metadata.json").write_text(
				json.dumps(
					{
						"run_id": "run-2",
						"target_controller": "c1",
						"target_new_flow_rate": 10,
						"measurement_started_at": "2026-09-16T10:00:00+00:00",
						"measurement_ended_at": "2026-09-16T10:01:00+00:00",
					}
				),
				encoding="utf-8",
			)

			summary = aggregate_run(run_dir)

		self.assertEqual(summary["measurement_samples"]["collector_errors"], 0)
		self.assertEqual(summary["processed_packet_in_rate_p95"], 0.0)
		self.assertEqual(summary["response_p95_ms_p95"], 0.0)
		self.assertEqual(summary["qos_success_ratio"], 0.0)


if __name__ == "__main__":
	unittest.main()
