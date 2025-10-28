from __future__ import annotations

import argparse
import socket
import time
from datetime import datetime, timezone
from typing import List


def now_ts() -> str:
    dt = datetime.now(tz=timezone.utc)
    millis = int(dt.microsecond / 1000)
    return dt.strftime("%Y%m%d%H%M%S") + f".{millis:03d}"


def run(ids: List[str], host: str, port: int, interval: float) -> None:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    cnts = {i: 0 for i in ids}
    try:
        while True:
            for tag_id in ids:
                cnts[tag_id] += 1
                line = f"TAG,{tag_id},{cnts[tag_id]},{now_ts()}"
                sock.sendto(line.encode("utf-8"), (host, port))
            time.sleep(interval)
    finally:
        sock.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Simple UDP Tag simulator")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9999)
    parser.add_argument("--interval", type=float, default=1.0, help="seconds between bursts")
    parser.add_argument(
        "--ids",
        nargs="+",
        default=["fa451f0755d8", "b1c2d3e4f5a6", "112233aabbcc"],
        help="List of tag IDs",
    )
    args = parser.parse_args()
    run(args.ids, args.host, args.port, args.interval)


