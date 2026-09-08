from datetime import datetime, timezone
import unittest

from src.schemas.workload import WorkloadSample


class WorkloadSchemaTests(unittest.TestCase):
    def test_serialization(self):
        sample = WorkloadSample(
            run_id="workload-smoke-c1-10-r01",
            observed_at=datetime.now(timezone.utc),
            source_host="h1",
            source_ip="10.0.0.1",
            target_host="h2",
            target_ip="10.0.0.2",
            target_port=9000,
            protocol="udp",
            pattern="stable",
            target_new_flow_rate=10.0,
            emitted_new_flow_rate=9.9,
            interval_seconds=1.0,
            attempted_flows=10,
            emitted_flows=10,
            send_errors=0,
            late_events=0,
            max_schedule_lag_ms=0.2,
            cumulative_attempted_flows=10,
            cumulative_emitted_flows=10,
            cumulative_send_errors=0,
            first_source_port=12000,
            last_source_port=12009,
        )

        payload = sample.to_dict()

        self.assertEqual(
            payload["target_new_flow_rate"],
            10.0,
        )

        self.assertEqual(
            payload["emitted_new_flow_rate"],
            9.9,
        )

        self.assertEqual(
            payload["source_host"],
            "h1",
        )

        self.assertEqual(
            payload["target_host"],
            "h2",
        )

        # add assertions for protocol and pattern fields
        # CLI: --protocol udp --pattern stable
        # h1 python3 -m src.experiments.workloads.udp_new_flow \
        #     --run-id workload-c1-10-r01 \
        #     --source-host h1 \
        #     --source-ip 10.0.0.1 \
        #     --target-host h2 \
        #     --target-ip 10.0.0.2 \
        #     --target-port 9000 \
        #     --pattern stable \
        #     --rate 10 \
        #     --duration 20 \
        #     --sample-interval 1 \
        #     --source-port-start 12000 \
        #     --source-port-end 65000 \
        #     --flow-idle-timeout 5 \
        #     --port-reuse-safety-factor 2 \
        #     --output /tmp/workload-c1-10-r01.jsonl

        self.assertEqual(
            payload["protocol"],
            "udp",
        )

        self.assertEqual(
            payload["pattern"],
            "stable",
        )


if __name__ == "__main__":
    unittest.main()