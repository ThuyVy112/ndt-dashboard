import unittest
from datetime import datetime, timedelta, timezone

from src.schemas.snapshot import (
	NetworkSnapshot,
	OwnershipState,
	SnapshotQuality,
)
from src.schemas.telemetry import (
	ControllerTelemetry,
	SwitchTelemetry,
)
from src.twin.state.quality import TwinQualityAssessor


class TwinQualityAssessorTests(unittest.TestCase):
	def setUp(self) -> None:
		self.created_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
		self.switch_ids = [f"s{index}" for index in range(1, 21)]

	def controller(self, controller_id, observed_at):
		return ControllerTelemetry(
			controller_id=controller_id,
			observed_at=observed_at,
			ingested_at=observed_at,
			packet_in_total=0,
			packet_in_rate=0.0,
			processed_packet_in_total=0,
			processed_packet_in_rate=0.0,
			flow_mod_total=0,
			flow_mod_rate=0.0,
			process_cpu_percent=0.0,
			process_memory_rss_mb=0.0,
			response_mean_ms=0.0,
			response_p95_ms=0.0,
			managed_switch_count=0,
		)

	def switch(self, switch_id, controller_id="c1"):
		return SwitchTelemetry(
			switch_id=switch_id,
			controller_id=controller_id,
			observed_at=self.created_at,
			packet_in_total=0,
			packet_in_rate=0.0,
			processed_packet_in_total=0,
			processed_packet_in_rate=0.0,
			flow_mod_total=0,
			flow_mod_rate=0.0,
			control_load_share=0.0,
		)

	def snapshot(
		self,
		controllers=None,
		switch_ids=None,
		consistent=True,
	):
		switch_ids = self.switch_ids if switch_ids is None else switch_ids
		controllers = (
			[
				self.controller("c1", self.created_at),
				self.controller("c2", self.created_at),
			]
			if controllers is None
			else controllers
		)
		return NetworkSnapshot(
			snapshot_id="snapshot-1",
			created_at=self.created_at,
			topology_version=1,
			ownership_version=1,
			controllers=controllers,
			switches=[self.switch(switch_id) for switch_id in switch_ids],
			ownership=[
				OwnershipState(
					switch_id,
					"c1",
					"MASTER",
					"MASTER",
					1,
					1,
				)
				for switch_id in self.switch_ids
			],
			quality=SnapshotQuality(
				fresh=True,
				complete=True,
				consistent=consistent,
				valid=True,
			),
		)

	def assessor(self, twinning_rate):
		return TwinQualityAssessor(
			expected_controller_ids={"c1", "c2"},
			expected_switch_ids=set(self.switch_ids),
			max_age_ms=2500,
			min_completeness_ratio=1.0,
			min_twinning_rate=0.95,
			twinning_rate_provider=lambda: twinning_rate,
		)

	def test_complete_snapshot_has_completeness_one(self):
		quality = self.assessor(1.0).assess(self.snapshot())

		self.assertEqual(quality.completeness_ratio, 1.0)
		self.assertTrue(quality.valid)

	def test_missing_controller_has_incomplete_invalid_quality(self):
		snapshot = self.snapshot(
			controllers=[self.controller("c1", self.created_at)],
		)

		quality = self.assessor(1.0).assess(snapshot)

		self.assertLess(quality.completeness_ratio, 1.0)
		self.assertFalse(quality.valid)

	def test_missing_switch_telemetry_has_incomplete_quality(self):
		quality = self.assessor(1.0).assess(
			self.snapshot(switch_ids=self.switch_ids[:-1]),
		)

		self.assertLess(quality.completeness_ratio, 1.0)

	def test_stale_controller_is_invalid(self):
		stale = self.created_at - timedelta(milliseconds=2501)
		snapshot = self.snapshot(
			controllers=[
				self.controller("c1", stale),
				self.controller("c2", self.created_at),
			],
		)

		quality = self.assessor(1.0).assess(snapshot)

		self.assertGreater(quality.age_of_twin_ms, 2500)
		self.assertFalse(quality.valid)

	def test_controllers_observed_at_same_time_have_zero_jitter(self):
		quality = self.assessor(1.0).assess(self.snapshot())

		self.assertEqual(quality.synchronization_jitter_ms, 0.0)

	def test_controller_timestamps_one_hundred_ms_apart_have_matching_jitter(self):
		quality = self.assessor(1.0).assess(
			self.snapshot(
				controllers=[
					self.controller("c1", self.created_at),
					self.controller(
						"c2",
						self.created_at + timedelta(milliseconds=100),
					),
				],
			),
		)

		self.assertEqual(quality.synchronization_jitter_ms, 100.0)

	def test_twinning_rate_one_is_valid_when_other_conditions_pass(self):
		quality = self.assessor(1.0).assess(self.snapshot())

		self.assertEqual(quality.twinning_rate, 1.0)
		self.assertTrue(quality.valid)

	def test_twinning_rate_below_point_nine_five_is_invalid(self):
		quality = self.assessor(0.9).assess(self.snapshot())

		self.assertEqual(quality.twinning_rate, 0.9)
		self.assertFalse(quality.valid)

	def test_ownership_conflict_is_reported_as_inconsistent(self):
		quality = self.assessor(1.0).assess(
			self.snapshot(consistent=False),
		)

		self.assertFalse(quality.consistent)


if __name__ == "__main__":
	unittest.main()
