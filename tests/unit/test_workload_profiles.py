import math
import unittest

from src.experiments.workloads.profile import WorkloadPoint


class WorkloadPointTests(unittest.TestCase):
	def test_hot_switch_fields_are_optional_together(self):
		point = WorkloadPoint(
			elapsed_seconds=1.0,
			target_utilization=0.8,
			phase="hot-switch",
		)

		self.assertIsNone(point.hot_switch_id)
		self.assertIsNone(point.hot_switch_share)

	def test_hot_switch_fields_accept_valid_values(self):
		point = WorkloadPoint(
			elapsed_seconds=1.0,
			target_utilization=0.8,
			phase="hot-switch",
			hot_switch_id="s1",
			hot_switch_share=1.0,
		)

		self.assertEqual(point.hot_switch_id, "s1")
		self.assertEqual(point.hot_switch_share, 1.0)

	def test_hot_switch_fields_must_be_provided_together(self):
		for hot_switch_id, hot_switch_share in (
			("s1", None),
			(None, 0.5),
		):
			with self.subTest(
				hot_switch_id=hot_switch_id,
				hot_switch_share=hot_switch_share,
			):
				with self.assertRaisesRegex(
					ValueError,
					"must be provided together",
				):
					WorkloadPoint(
						elapsed_seconds=1.0,
						target_utilization=0.8,
						phase="hot-switch",
						hot_switch_id=hot_switch_id,
						hot_switch_share=hot_switch_share,
					)

	def test_hot_switch_id_must_not_be_empty(self):
		with self.assertRaisesRegex(ValueError, "hot_switch_id must not be empty"):
			WorkloadPoint(
				elapsed_seconds=1.0,
				target_utilization=0.8,
				phase="hot-switch",
				hot_switch_id=" ",
				hot_switch_share=0.5,
			)

	def test_hot_switch_share_must_be_finite(self):
		for hot_switch_share in (math.nan, math.inf, -math.inf):
			with self.subTest(hot_switch_share=hot_switch_share):
				with self.assertRaisesRegex(
					ValueError,
					"hot_switch_share must be finite",
				):
					WorkloadPoint(
						elapsed_seconds=1.0,
						target_utilization=0.8,
						phase="hot-switch",
						hot_switch_id="s1",
						hot_switch_share=hot_switch_share,
					)

	def test_hot_switch_share_must_be_between_zero_and_one(self):
		for hot_switch_share in (-0.1, 1.1):
			with self.subTest(hot_switch_share=hot_switch_share):
				with self.assertRaisesRegex(
					ValueError,
					r"hot_switch_share must be in \[0, 1\]",
				):
					WorkloadPoint(
						elapsed_seconds=1.0,
						target_utilization=0.8,
						phase="hot-switch",
						hot_switch_id="s1",
						hot_switch_share=hot_switch_share,
					)


if __name__ == "__main__":
	unittest.main()
