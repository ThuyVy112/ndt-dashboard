import unittest

from src.twin.capacity.model import (
    CapacityModel,
)


class CapacityModelTests(
    unittest.TestCase
):
    def setUp(self) -> None:
        self.model = CapacityModel(
            {
                "c1": 1000.0,
                "c2": 800.0,
            }
        )

    def test_zero_load(self) -> None:
        self.assertEqual(
            self.model.utilization(
                "c1",
                0.0,
            ),
            0.0,
        )

    def test_half_utilization(
        self,
    ) -> None:
        self.assertAlmostEqual(
            self.model.utilization(
                "c1",
                500.0,
            ),
            0.5,
        )

    def test_overload_not_clamped(
        self,
    ) -> None:
        self.assertAlmostEqual(
            self.model.utilization(
                "c1",
                1200.0,
            ),
            1.2,
        )

    def test_negative_load_rejected(
        self,
    ) -> None:
        with self.assertRaises(
            ValueError
        ):
            self.model.utilization(
                "c1",
                -1.0,
            )

    def test_unknown_controller(
        self,
    ) -> None:
        with self.assertRaises(
            KeyError
        ):
            self.model.utilization(
                "c3",
                100.0,
            )

    def test_invalid_capacity(
        self,
    ) -> None:
        with self.assertRaises(
            ValueError
        ):
            CapacityModel(
                {
                    "c1": 0.0,
                }
            )


if __name__ == "__main__":
    unittest.main()
