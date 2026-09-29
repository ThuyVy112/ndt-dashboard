import math
import unittest

from src.twin.forecasting.horizon import (
    ForecastHorizon,
    RuntimeLatency,
    estimate_horizon,
)


class ForecastHorizonTests(unittest.TestCase):
    def test_runtime_latency_to_dict(self):
        latency = RuntimeLatency(
            collection_p95_ms=120.0,
            decision_p95_ms=80.0,
            migration_p95_ms=300.0,
        )

        self.assertEqual(
            latency.to_dict(),
            {
                "collection_p95_ms": 120.0,
                "decision_p95_ms": 80.0,
                "migration_p95_ms": 300.0,
            },
        )

    def test_forecast_horizon_to_dict(self):
        horizon = ForecastHorizon(
            required_lead_time_seconds=0.5,
            horizon_steps=2,
            effective_horizon_seconds=0.6,
        )

        self.assertEqual(
            horizon.to_dict(),
            {
                "required_lead_time_seconds": 0.5,
                "horizon_steps": 2,
                "effective_horizon_seconds": 0.6,
            },
        )

    def test_estimate_horizon_rounds_up_to_next_step(self):
        horizon = estimate_horizon(
            RuntimeLatency(
                collection_p95_ms=100.0,
                decision_p95_ms=150.0,
                migration_p95_ms=250.0,
            ),
            step_seconds=0.4,
        )

        self.assertAlmostEqual(
            horizon.required_lead_time_seconds,
            0.5,
        )
        self.assertEqual(
            horizon.horizon_steps,
            2,
        )
        self.assertAlmostEqual(
            horizon.effective_horizon_seconds,
            0.8,
        )

    def test_week7_reference_horizon(self):
        horizon = estimate_horizon(
            RuntimeLatency(
                collection_p95_ms=800.0,
                decision_p95_ms=300.0,
                migration_p95_ms=2000.0,
            ),
            step_seconds=1.0,
        )

        self.assertAlmostEqual(
            horizon.required_lead_time_seconds,
            3.1,
        )
        self.assertEqual(
            horizon.horizon_steps,
            4,
        )
        self.assertAlmostEqual(
            horizon.effective_horizon_seconds,
            4.0,
        )

    def test_estimate_horizon_exact_step_count(self):
        horizon = estimate_horizon(
            RuntimeLatency(
                collection_p95_ms=100.0,
                decision_p95_ms=200.0,
                migration_p95_ms=700.0,
            ),
            step_seconds=1.0,
        )
        # sampling 1 second steps, the required lead time is 1.0 seconds, which is exactly 1 step, so the effective horizon is also 1.0 seconds
        self.assertAlmostEqual(
            horizon.required_lead_time_seconds,
            1.0,
        )
        self.assertEqual(
            horizon.horizon_steps,
            1,
        )
        self.assertAlmostEqual(
            horizon.effective_horizon_seconds,
            1.0,
        )

    def test_estimate_horizon_requires_decision_latency(self):
        with self.assertRaisesRegex(
            ValueError,
            "decision_p95_ms is required",
        ):
            estimate_horizon(
                RuntimeLatency(
                    collection_p95_ms=100.0,
                    decision_p95_ms=None,
                    migration_p95_ms=200.0,
                ),
                step_seconds=1.0,
            )

    def test_estimate_horizon_rejects_invalid_step_seconds(self):
        invalid_values = (
            0.0,
            -1.0,
            math.inf,
            -math.inf,
            math.nan,
        )

        for step_seconds in invalid_values:
            with self.subTest(
                step_seconds=step_seconds,
            ):
                with self.assertRaisesRegex(
                    ValueError,
                    "step_seconds must be a positive finite number",
                ):
                    estimate_horizon(
                        RuntimeLatency(
                            collection_p95_ms=100.0,
                            decision_p95_ms=100.0,
                            migration_p95_ms=100.0,
                        ),
                        step_seconds=step_seconds,
                    )

    def test_estimate_horizon_rejects_invalid_runtime_latency(
        self,
    ):
        invalid_values = (
            -1.0,
            math.inf,
            -math.inf,
            math.nan,
        )

        for field_name in (
            "collection_p95_ms",
            "decision_p95_ms",
            "migration_p95_ms",
        ):
            for value in invalid_values:
                with self.subTest(
                    field_name=field_name,
                    value=value,
                ):
                    values = {
                        "collection_p95_ms": 100.0,
                        "decision_p95_ms": 100.0,
                        "migration_p95_ms": 100.0,
                    }

                    values[field_name] = value

                    with self.assertRaisesRegex(
                        ValueError,
                        "runtime latency values must be "
                        "finite and non-negative",
                    ):
                        estimate_horizon(
                            RuntimeLatency(**values),
                            step_seconds=1.0,
                        )


if __name__ == "__main__":
    unittest.main()