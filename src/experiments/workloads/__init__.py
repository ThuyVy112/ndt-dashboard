self.benchmark_enabled = (
    os.getenv(
        "NDT_BENCHMARK_ENABLED",
        "0",
    )
    == "1"
)

self.benchmark_udp_port = int(
    os.getenv(
        "NDT_BENCHMARK_UDP_PORT",
        "9000",
    )
)

self.benchmark_idle_timeout = int(
    os.getenv(
        "NDT_BENCHMARK_FLOW_IDLE_TIMEOUT",
        "5",
    )
)