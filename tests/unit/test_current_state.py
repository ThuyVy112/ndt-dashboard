import unittest
from datetime import datetime, timezone

from src.orchestrator.current_state import CurrentStateStore
from src.schemas.twin import TwinQuality, TwinState


class CurrentStateStoreTests(unittest.TestCase):
    def test_twin_state_is_not_ready_until_set(self):
        store = CurrentStateStore()

        self.assertIsNone(store.twin_state_dict())

    def test_twin_state_dict_uses_state_serialization(self):
        store = CurrentStateStore()
        state = TwinState(
            snapshot_id="snapshot-1",
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            topology_version=1,
            ownership_version=1,
            controllers=[],
            switches=[],
            ownership=[],
            quality=TwinQuality(
                age_of_twin_ms=100.0,
                twinning_rate=1.0,
                completeness_ratio=1.0,
                synchronization_jitter_ms=0.0,
                consistent=True,
                valid=True,
            ),
        )

        store.set_twin_state(state)

        self.assertEqual(store.twin_state_dict(), state.to_dict())


if __name__ == "__main__":
    unittest.main()
