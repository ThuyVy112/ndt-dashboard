import unittest
from datetime import (
    datetime,
    timedelta,
    timezone,
)

from src.schemas.telemetry import (
    ControllerTelemetry,
)
from src.schemas.snapshot import (
    NetworkSnapshot,
    SnapshotQuality,
)
from src.schemas.twin import (
    TwinQuality,
)
from src.twin.capacity.model import (
    CapacityModel,
)
from src.twin.state.builder import (
    TwinStateBuilder,
)


class TwinStateBuilderTests(
    unittest.TestCase
):
    def setUp(self) -> None:
        self.capacity = CapacityModel(
            {
                "c1": 1000.0,
                "c2": 800.0,
            }
        )

    def quality(self, _snapshot):
        return TwinQuality(
            age_of_twin_ms=100.0,
            twinning_rate=1.0,
            completeness_ratio=1.0,
            synchronization_jitter_ms=5.0,
            consistent=True,
            valid=True,
        )

    def controller(
        self,
        controller_id="c1",
        processed_packet_in_rate=0.0,
        collection_latency_ms=250.0,
    ):
        observed_at = datetime(
            2026,
            1,
            1,
            tzinfo=timezone.utc,
        )
        ingested_at = observed_at + timedelta(
            milliseconds=collection_latency_ms,
        )
        return ControllerTelemetry(
            controller_id=controller_id,
            observed_at=observed_at,
            ingested_at=ingested_at,
            packet_in_total=0,
            packet_in_rate=0.0,
            processed_packet_in_total=0,
            processed_packet_in_rate=processed_packet_in_rate,
            flow_mod_total=0,
            flow_mod_rate=0.0,
            process_cpu_percent=0.0,
            process_memory_rss_mb=0.0,
            response_mean_ms=0.0,
            response_p95_ms=0.0,
            managed_switch_count=0,
        )

    def snapshot(self, controller):
        return NetworkSnapshot(
            snapshot_id="snapshot-1",
            created_at=datetime(
                2026,
                1,
                1,
                tzinfo=timezone.utc,
            ),
            topology_version=1,
            ownership_version=1,
            controllers=[controller],
            switches=[],
            ownership=[],
            quality=SnapshotQuality(
                fresh=True,
                complete=True,
                consistent=True,
                valid=True,
            ),
        )

    def build(self, controller):
        builder = TwinStateBuilder(
            self.capacity,
            self.quality,
        )
        return builder.build(self.snapshot(controller))

    def test_load_zero_has_zero_utilization(self):
        state = self.build(
            self.controller(processed_packet_in_rate=0.0),
        )

        self.assertEqual(state.controllers[0].utilization, 0.0)

    def test_load_500_has_half_utilization(self):
        state = self.build(
            self.controller(processed_packet_in_rate=500.0),
        )

        self.assertEqual(state.controllers[0].utilization, 0.5)

    def test_load_at_safe_capacity_has_one_utilization(self):
        state = self.build(
            self.controller(processed_packet_in_rate=1000.0),
        )

        self.assertEqual(state.controllers[0].utilization, 1.0)

    def test_load_above_safe_capacity_has_utilization_above_one(self):
        state = self.build(
            self.controller(processed_packet_in_rate=1200.0),
        )

        self.assertGreater(state.controllers[0].utilization, 1.0)

    def test_collection_latency_is_preserved_in_milliseconds(self):
        state = self.build(
            self.controller(collection_latency_ms=250.0),
        )

        self.assertEqual(
            state.controllers[0].collection_latency_ms,
            250.0,
        )

    def test_unknown_controller_fails(self):
        with self.assertRaisesRegex(KeyError, "unknown controller: c3"):
            self.build(
                self.controller(controller_id="c3"),
            )