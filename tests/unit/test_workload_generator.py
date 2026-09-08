from __future__ import annotations

import json
import unittest
from argparse import Namespace
from datetime import datetime, timezone
from unittest.mock import patch

from src.experiments.workloads.generator import (
    DeadlinePacer,
    PortAllocator,
    validate_port_reuse,
)
from src.experiments.workloads.udp_new_flow import (
    validate_config,
)
from src.schemas.workload import WorkloadSample


class TestPortAllocator(
    unittest.TestCase
):
    def test_port_allocator_increments_sequentially(
        self,
    ):
        allocator = PortAllocator(
            10000,
            10003,
        )

        ports = [
            allocator.next_port()
            for _ in range(4)
        ]

        self.assertEqual(
            ports,
            [
                10000,
                10001,
                10002,
                10003,
            ],
        )

    def test_port_allocator_wraps_to_start(
        self,
    ):
        allocator = PortAllocator(
            10000,
            10002,
        )

        ports = [
            allocator.next_port()
            for _ in range(5)
        ]

        self.assertEqual(
            ports,
            [
                10000,
                10001,
                10002,
                10000,
                10001,
            ],
        )

    def test_invalid_port_range_rejected(
        self,
    ):
        with self.assertRaises(
            ValueError
        ):
            PortAllocator(
                20000,
                12000,
            )


class TestPortReuseSafety(
    unittest.TestCase
):
    def test_safe_port_pool(
        self,
    ):
        validate_port_reuse(
            start=12000,
            end=65000,
            rate=100,
            idle_timeout_seconds=5,
            safety_factor=2.0,
        )

    def test_unsafe_port_pool_rejected(
        self,
    ):
        with self.assertRaises(
            ValueError
        ):
            validate_port_reuse(
                start=12000,
                end=12100,
                rate=100,
                idle_timeout_seconds=5,
                safety_factor=2.0,
            )


class TestDeadlinePacer(
    unittest.TestCase
):
    def test_deadline_sequence(
        self,
    ):
        pacer = DeadlinePacer(
            rate=100,
        )

        start_ns = 1_000_000_000

        self.assertEqual(
            pacer.period_ns,
            10_000_000,
        )

        self.assertEqual(
            pacer.deadline_ns(
                start_ns,
                0,
            ),
            1_000_000_000,
        )

        self.assertEqual(
            pacer.deadline_ns(
                start_ns,
                10,
            ),
            1_100_000_000,
        )

    def test_period_ms_matches_rate(
        self,
    ):
        cases = [
            (10, 100.0),
            (20, 50.0),
            (50, 20.0),
            (100, 10.0),
            (200, 5.0),
            (500, 2.0),
            (1000, 1.0),
        ]

        for rate, expected_ms in cases:
            pacer = DeadlinePacer(rate=rate)
            self.assertAlmostEqual(
                pacer.period_ms,
                expected_ms,
                places=6,
            )

    def test_wait_until_sleeps_remaining_time(
        self,
    ):
        deadline_ns = (
            2_000_000_000
        )

        with patch(
            "src.experiments.workloads."
            "generator.time.monotonic_ns",
            side_effect=[
                500_000_000,
                2_000_000_000,
                2_000_000_000,
            ],
        ), patch(
            "src.experiments.workloads."
            "generator.time.sleep"
        ) as sleep_mock:
            lag_ms = (
                DeadlinePacer.wait_until(
                    deadline_ns
                )
            )

        sleep_mock.assert_called_once_with(
            1.5
        )

        self.assertEqual(
            lag_ms,
            0.0,
        )


class TestGeneratorValidation(
    unittest.TestCase
):
    @staticmethod
    def make_config(
        rate: float = 10.0,
    ) -> Namespace:
        return Namespace(
            run_id="test-run",

            source_host="h1",
            source_ip="10.0.0.1",

            target_host="h2",
            target_ip="10.0.0.2",
            target_port=9000,

            pattern="stable",

            rate=rate,
            duration=20.0,
            sample_interval=1.0,

            source_port_start=12000,
            source_port_end=65000,

            flow_idle_timeout=5.0,
            port_reuse_safety_factor=2.0,
        )

    def test_rate_zero_is_rejected(
        self,
    ):
        with self.assertRaises(
            ValueError
        ):
            validate_config(
                self.make_config(
                    rate=0
                )
            )

    def test_negative_rate_is_rejected(
        self,
    ):
        with self.assertRaises(
            ValueError
        ):
            validate_config(
                self.make_config(
                    rate=-1
                )
            )

    def test_invalid_sample_interval_rejected(
        self,
    ):
        config = self.make_config()
        config.sample_interval = 0

        with self.assertRaises(
            ValueError
        ):
            validate_config(config)

    def test_valid_smoke_config(
        self,
    ):
        validate_config(
            self.make_config(
                rate=100
            )
        )


class TestWorkloadSample(
    unittest.TestCase
):
    def test_workload_sample_serializes(
        self,
    ):
        sample = WorkloadSample(
            run_id="test-run",

            observed_at=datetime(
                2026,
                9,
                8,
                0,
                0,
                0,
                tzinfo=timezone.utc,
            ),

            source_host="h1",
            source_ip="10.0.0.1",

            target_host="h2",
            target_ip="10.0.0.2",
            target_port=9000,

            protocol="udp",
            pattern="stable",

            target_new_flow_rate=100.0,
            emitted_new_flow_rate=99.5,

            interval_seconds=1.0,

            attempted_flows=100,
            emitted_flows=99,
            send_errors=1,

            late_events=0,
            max_schedule_lag_ms=0.5,

            cumulative_attempted_flows=100,
            cumulative_emitted_flows=99,
            cumulative_send_errors=1,

            first_source_port=12000,
            last_source_port=12099,
        )

        data = sample.to_dict()

        serialized = json.dumps(data)
        decoded = json.loads(
            serialized
        )

        self.assertEqual(
            decoded["run_id"],
            "test-run",
        )

        self.assertEqual(
            decoded["protocol"],
            "udp",
        )

        self.assertEqual(
            decoded["pattern"],
            "stable",
        )

        self.assertEqual(
            decoded["target_host"],
            "h2",
        )

        self.assertEqual(
            decoded["target_ip"],
            "10.0.0.2",
        )


if __name__ == "__main__":
    unittest.main()