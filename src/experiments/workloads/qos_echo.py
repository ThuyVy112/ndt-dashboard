from __future__ import annotations

import argparse
import json
import socket
import time


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="UDP QoS flow-setup echo target")
    parser.add_argument("--bind-ip", required=True)
    parser.add_argument("--port", type=int, default=9001)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        #sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((args.bind_ip, args.port))
        print(f"QOS_ECHO_READY {args.bind_ip}:{args.port}", flush=True)
        while True:
            raw, address = sock.recvfrom(
                65535
            )

            received_ns = time.monotonic_ns()

            try:
                request = json.loads(
                    raw.decode("utf-8")
                )

                response = {
                    "sequence":
                        request["sequence"],

                    "send_ns":
                        request["send_ns"],

                    "target_received_ns":
                        received_ns,

                    "target_reply_ns":
                        time.monotonic_ns(),
                }

                sock.sendto(
                    json.dumps(
                        response,
                        separators=(",", ":"),
                    ).encode("utf-8"),
                    address,
                )

            except (
                KeyError,
                TypeError,
                ValueError,
                #UnicodeDecodeError,
            ):
                continue # delete json.JSONDecodeError from except clause because it is a subclass of ValueError


if __name__ == "__main__":
    main()
