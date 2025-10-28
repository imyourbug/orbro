from __future__ import annotations

import asyncio
import logging
import socket
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Optional
import os

from parser import parse_tag_line, TagMessage
from db import init_db, update_from_message


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("tag-listener")


@dataclass
class TagState:
    id: str
    description: str = ""
    last_cnt: int = 1
    last_seen: Optional[datetime] = None


class TagStore:
    def __init__(self) -> None:
        self._tags: Dict[str, TagState] = {}

    def register(self, tag_id: str, description: str = "") -> TagState:
        state = self._tags.get(tag_id)
        if state is None:
            state = TagState(id=tag_id, description=description)
            self._tags[tag_id] = state
        else:
            if description:
                state.description = description
        return state

    def get(self, tag_id: str) -> Optional[TagState]:
        return self._tags.get(tag_id)

    def list(self) -> Dict[str, TagState]:
        return dict(self._tags)

    def update_from_message(self, msg: TagMessage) -> TagState:
        state = self._tags.get(msg.tag_id)
        if state is None:
            # Allow in-memory tracking only for pre-registered in this process
            return None  # type: ignore[return-value]

        changed = state.last_cnt != msg.cnt
        if changed:
            logger.info(
                "CNT changed for %s: %s -> %s at %s",
                msg.tag_id,
                state.last_cnt,
                msg.cnt,
                msg.timestamp.isoformat(),
            )
            state.last_cnt = msg.cnt
        state.last_seen = msg.timestamp
        return state


store = TagStore()


async def udp_server(host: str = "127.0.0.1", port: int = 9999) -> None:
    loop = asyncio.get_running_loop()
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((host, port))
    sock.setblocking(False)
    logger.info("UDP server listening on %s:%d", host, port)
    auto_inc = os.getenv("AUTO_INCREMENT_CNT", "0") in ("1", "true", "TRUE", "yes", "YES")

    try:
        while True:
            data, _addr = await loop.sock_recvfrom(sock, 8192)
            try:
                line = data.decode("utf-8", errors="ignore").strip()
                msg = parse_tag_line(line)

                # Update DB first (if registered) and log on change
                updated = update_from_message(
                    tag_id=msg.tag_id,
                    cnt=msg.cnt,
                    timestamp_iso=msg.timestamp.isoformat(),
                    auto_increment=auto_inc,
                )
                if updated is not None and updated.get("changed"):
                    logger.info(
                        "CNT changed for %s -> %s at %s (DB)",
                        msg.tag_id,
                        updated.get("last_cnt"),
                        msg.timestamp.isoformat(),
                    )

                # Also keep in-memory state for those registered in-process
                if updated is not None:
                    # reflect DB value if auto-increment is on
                    msg = TagMessage(tag_id=msg.tag_id, cnt=int(updated["last_cnt"]), timestamp=msg.timestamp)
                store.update_from_message(msg)
            except Exception as exc:
                logger.warning("failed to process line: %s", exc)
    finally:
        sock.close()


def run_udp_server_blocking(host: str = "127.0.0.1", port: int = 9999) -> None:
    asyncio.run(udp_server(host, port))


if __name__ == "__main__":
    init_db()
    # Example pre-registrations for quick manual tests
    store.register("fa451f0755d8", "Helmet Tag for worker A")
    store.register("b1c2d3e4f5a6", "Helmet Tag for worker B")
    store.register("112233aabbcc", "Vehicle Tag for forklift")
    run_udp_server_blocking()


