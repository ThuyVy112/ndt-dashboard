from __future__ import annotations

import json
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict
from urllib.request import urlopen

from src.experiments.common.run_io import append_jsonl


class RunCollector:
    """Poll controller telemetry and orchestrator snapshots for one run."""

    def __init__(
        self,
        controller_urls: Dict[str, str],
        orchestrator_url: str,
        run_dir: Path,
        poll_interval_seconds: float,
    ) -> None:
        if poll_interval_seconds <= 0:
            raise ValueError("poll_interval_seconds must be > 0")
        self.controller_urls = {
            key: str(value).rstrip("/")
            for key, value in controller_urls.items()
        }
        self.orchestrator_url = orchestrator_url.rstrip("/")
        self.run_dir = run_dir
        self.poll_interval_seconds = float(poll_interval_seconds)
        self.stop_event = threading.Event()
        self.thread: threading.Thread | None = None
        self.last_snapshot_id: str | None = None

    @staticmethod
    def _get_json(url: str) -> dict[str, Any]:
        with urlopen(url, timeout=2.0) as response:
            payload = json.load(response)
        if not isinstance(payload, dict):
            raise ValueError(f"expected JSON object from {url}")
        return payload

    def _collect_once(self) -> None:
        ingested_at = datetime.now(timezone.utc).isoformat()
        for controller_id, base_url in self.controller_urls.items():
            payload = self._get_json(f"{base_url}/api/v1/telemetry")
            controller = payload.get("controller")
            if not isinstance(controller, dict):
                raise ValueError(f"controller:{controller_id}:telemetry_missing")
            controller_row = dict(controller)
            controller_row["controller_id"] = controller_id
            controller_row["ingested_at"] = ingested_at
            append_jsonl(self.run_dir / "controllers.jsonl", controller_row)
            for switch in payload.get("switches", []):
                if not isinstance(switch,dict,):
                    raise ValueError(
                        "switch telemetry" "must_be_json_object"
                    )
                switch_row = dict(switch)
                switch_row["controller_id"] = controller_id
                switch_row["ingested_at"] = ingested_at
                append_jsonl(self.run_dir / "switches.jsonl", switch_row)

        state = self._get_json(f"{self.orchestrator_url}/api/v1/state")
        snapshot = state.get("latest_snapshot")
        if isinstance(snapshot, dict):
            snapshot_id = snapshot.get("snapshot_id")
            if snapshot_id != self.last_snapshot_id:
                append_jsonl(self.run_dir / "snapshots.jsonl", snapshot)
                self.last_snapshot_id = snapshot_id

    def _loop(self) -> None:
        while not self.stop_event.is_set():
            started = time.monotonic()
            try:
                self._collect_once()
            except Exception as exc:
                append_jsonl(
                    self.run_dir / "collector_errors.jsonl",
                    {
                        "observed_at": datetime.now(timezone.utc).isoformat(),
                        "error": str(exc),
                    },
                )
            wait_seconds = max(0.0, self.poll_interval_seconds - (time.monotonic() - started))
            self.stop_event.wait(wait_seconds)

    def start(self) -> None:
        if self.thread is not None:
            raise RuntimeError("collector already started")
        self.stop_event.clear()
        self.thread = threading.Thread(
            target=self._loop,
            daemon=True,
            name="capacity-run-collector",
        )
        self.thread.start()

    def stop(self) -> None:
        self.stop_event.set()
        if self.thread is not None:
            self.thread.join(timeout=5.0)
            self.thread = None
