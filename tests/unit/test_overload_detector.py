import unittest

from src.twin.decision.overload_detector import OverloadDetector, assess_overload


class OverloadDetectorTest(unittest.TestCase):
    def test_safe_prediction(self) -> None:
        result = assess_overload(0.80, 0.05)
        self.assertAlmostEqual(result.upper_bound, 0.85)
        self.assertFalse(result.risk)

    def test_upper_bound_crosses_one(self) -> None:
        result = assess_overload(0.96, 0.06)
        self.assertAlmostEqual(result.upper_bound, 1.02)
        self.assertTrue(result.risk)

    def test_prediction_above_one_is_not_clamped(self) -> None:
        result = assess_overload(1.05, 0.04)
        self.assertTrue(result.risk)
        self.assertAlmostEqual(result.upper_bound, 1.09)

    def test_boundary_equal_to_one_is_risk(self) -> None:
        result = assess_overload(0.95, 0.05)
        self.assertAlmostEqual(result.upper_bound, 1.00)
        self.assertTrue(result.risk)

    def test_just_below_boundary_is_not_risk(self) -> None:
        self.assertFalse(assess_overload(0.94, 0.05).risk)

    def test_detector_carries_controller_id_and_threshold(self) -> None:
        detector = OverloadDetector(threshold=0.9)
        result = detector.assess("c1", 0.80, 0.05)
        self.assertEqual(result.controller_id, "c1")
        self.assertFalse(result.risk)
        self.assertTrue(detector.assess("c2", 0.86, 0.05).risk)

    def test_invalid_inputs(self) -> None:
        with self.assertRaises(ValueError):
            assess_overload(-0.1, 0.05)
        with self.assertRaises(ValueError):
            assess_overload(0.5, -0.01)
        with self.assertRaises(ValueError):
            assess_overload(float("nan"), 0.05)
        with self.assertRaises(ValueError):
            OverloadDetector(threshold=0)


    def test_assess_many_with_shared_margin(self) -> None:
        result = OverloadDetector().assess_many({"c1": 0.96, "c2": 0.60}, 0.06)

        self.assertTrue(result["c1"].risk)
        self.assertFalse(result["c2"].risk)

    def test_assess_many_with_per_controller_margin(self) -> None:
        result = OverloadDetector().assess_many(
            {"c1": 0.80, "c2": 0.80},
            {"c1": 0.05, "c2": 0.25},
        )

        self.assertFalse(result["c1"].risk)
        self.assertTrue(result["c2"].risk)

    def test_assess_many_missing_margin_raises(self) -> None:
        with self.assertRaises(KeyError):
            OverloadDetector().assess_many({"c1": 0.5}, {"c2": 0.1})


if __name__ == "__main__":
    unittest.main()
