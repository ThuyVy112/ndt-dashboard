from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from urllib.request import Request, urlopen

from mininet.link import TCLink
from mininet.log import setLogLevel
from mininet.net import Mininet
from mininet.node import (
    OVSSwitch,
    RemoteController,
)

from src.experiments.capacity.capacity_runner import (
    run_capacity_experiment,
)
from src.experiments.common.config import (
    load_yaml,
    validate_capacity_config,
)
from src.experiments.topologies.capacity_2c20s import (
    Capacity2C20STopo,
)


def get_json(
    url: str,
    timeout_seconds: float = 3.0,
) -> dict:
    with urlopen(
        url,
        timeout=timeout_seconds,
    ) as response:
        payload = json.load(response)

    if not isinstance(
        payload,
        dict,
    ):
        raise RuntimeError(
            f"expected JSON object from {url}"
        )

    return payload


def post_json(
    url: str,
) -> dict:
    request = Request(
        url,
        data=b"",
        method="POST",
    )

    with urlopen(
        request,
        timeout=30,
    ) as response:
        payload = json.load(response)

    if not isinstance(
        payload,
        dict,
    ):
        raise RuntimeError(
            f"expected JSON object from {url}"
        )

    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run the 2C20S capacity experiment"
        )
    )

    parser.add_argument(
        "--config",
        default=(
            "configs/experiments/"
            "capacity_smoke_2c20s.yaml"
        ),
    )

    parser.add_argument(
        "--controller",
        choices=("c1", "c2", "all"),
        default="all",
    )

    parser.add_argument(
        "--rate",
        type=float,
    )

    parser.add_argument(
        "--repeat",
        type=int,
    )

    return parser


def wait_for_controller_connections(
    controller_urls: dict[str, str],
    expected_switch_count: int = 20,
    timeout_seconds: float = 45.0,
) -> None:
    deadline = (
        time.monotonic()
        + timeout_seconds
    )

    last_error = (
        "controller connection state "
        "not available"
    )

    while time.monotonic() < deadline:
        try:
            all_ready = True

            for (
                controller_id,
                base_url,
            ) in controller_urls.items():
                state = get_json(
                    f"{str(base_url).rstrip('/')}"
                    "/api/v1/state"
                )

                switches = state.get(
                    "switches"
                )

                if not isinstance(
                    switches,
                    list,
                ):
                    all_ready = False
                    last_error = (
                        f"{controller_id}: "
                        "switch list missing"
                    )
                    break

                connected = [
                    item
                    for item in switches
                    if (
                        isinstance(item, dict)
                        and item.get(
                            "connected"
                        )
                        is True
                    )
                ]

                if len(
                    connected
                ) < expected_switch_count:
                    all_ready = False

                    last_error = (
                        f"{controller_id}: "
                        f"{len(connected)}/"
                        f"{expected_switch_count} "
                        "switches connected"
                    )

                    break

            if all_ready:
                print(
                    "CONTROLLER_CONNECTIONS: "
                    "PASS",
                    flush=True,
                )
                return

        except Exception as exc:
            last_error = str(exc)

        time.sleep(0.5)

    raise RuntimeError(
        "controllers did not see all "
        "switches before timeout: "
        f"{last_error}"
    )


def validate_initialized_ownership(
    ownership: object,
) -> None:
    if not isinstance(
        ownership,
        dict,
    ):
        raise RuntimeError(
            "init-roles response missing "
            "ownership"
        )

    if len(ownership) != 20:
        raise RuntimeError(
            "expected 20 ownership entries, "
            f"got {len(ownership)}"
        )

    for index in range(1, 11):
        switch_id = f"s{index}"

        if ownership.get(
            switch_id
        ) != "c1":
            raise RuntimeError(
                f"{switch_id} expected c1, "
                f"got {ownership.get(switch_id)}"
            )

    for index in range(11, 21):
        switch_id = f"s{index}"

        if ownership.get(
            switch_id
        ) != "c2":
            raise RuntimeError(
                f"{switch_id} expected c2, "
                f"got {ownership.get(switch_id)}"
            )


def main() -> None:
    args = (
        build_parser()
        .parse_args()
    )

    repo_root = Path.cwd()

    config = load_yaml(
        repo_root / args.config
    )

    validate_capacity_config(
        config
    )

    setLogLevel(
        "info"
    )

    net = Mininet(
        topo=Capacity2C20STopo(),
        controller=None,
        switch=OVSSwitch,
        link=TCLink,
        build=False,
    )

    net.addController(
        "c1",
        controller=RemoteController,
        ip="127.0.0.1",
        port=6653,
    )

    net.addController(
        "c2",
        controller=RemoteController,
        ip="127.0.0.1",
        port=6654,
    )

    try:
        net.build()
        net.start()

        runtime = config[
            "runtime"
        ]

        wait_for_controller_connections(
            controller_urls=runtime[
                "controller_urls"
            ],
            expected_switch_count=20,
        )

        orchestrator_url = str(
            runtime[
                "orchestrator_url"
            ]
        ).rstrip("/")

        roles = post_json(
            f"{orchestrator_url}"
            "/api/v1/init-roles"
        )

        validate_initialized_ownership(
            roles.get(
                "ownership"
            )
        )

        print(
            "INIT_ROLES:",
            roles.get("ownership"),
            flush=True,
        )

        controllers = (
            ["c1", "c2"]
            if args.controller == "all"
            else [args.controller]
        )

        rates = (
            [args.rate]
            if args.rate is not None
            else config[
                "workload"
            ][
                "rates_fps"
            ]
        )

        repeats = (
            [args.repeat]
            if args.repeat is not None
            else range(
                1,
                int(
                    config[
                        "repeats"
                    ]
                )
                + 1,
            )
        )

        for controller_id in controllers:
            for rate in rates:
                for repeat_index in repeats:
                    run_dir = (
                        run_capacity_experiment(
                            net=net,
                            config=config,
                            controller_id=controller_id,
                            rate=float(rate),
                            repeat_index=int(
                                repeat_index
                            ),
                            repo_root=repo_root,
                        )
                    )

                    print(
                        "PASS:",
                        run_dir,
                        flush=True,
                    )

    finally:
        net.stop()


if __name__ == "__main__":
    main()
