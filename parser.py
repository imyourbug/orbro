from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional


TIMESTAMP_FORMAT = "%Y%m%d%H%M%S.%f"  # e.g. 20240503140059.456


@dataclass(frozen=True)
class TagMessage:
    tag_id: str
    cnt: int
    timestamp: datetime


def parse_tag_line(line: str) -> TagMessage:
    """
    Parse a simulator line in the form: TAG,<tag_id>,<cnt>,<timestamp>
    - timestamp format: YYYYMMDDHHMMSS.mmm (UTC)

    Raises ValueError on invalid input.
    """
    if not isinstance(line, str):
        raise ValueError("line must be a string")

    raw = line.strip()
    if not raw:
        raise ValueError("empty line")

    parts = [p.strip() for p in raw.split(",")]
    if len(parts) != 4:
        raise ValueError(f"invalid field count: {len(parts)}")

    prefix, tag_id, cnt_str, ts_str = parts
    if prefix.upper() != "TAG":
        raise ValueError("invalid prefix; expected 'TAG'")

    if not tag_id or any(c.isspace() for c in tag_id):
        raise ValueError("invalid tag_id")

    try:
        cnt = int(cnt_str)
        if cnt < 0:
            raise ValueError
    except Exception as exc:
        raise ValueError("cnt must be a non-negative integer") from exc

    # Normalize fractional milliseconds to microseconds if only 3 digits provided
    # datetime with %f expects microseconds (6 digits). Input is mmm -> pad to 6.
    if "." in ts_str:
        date_part, frac = ts_str.split(".", 1)
        if len(frac) == 3:
            ts_norm = f"{date_part}.{frac}000"
        else:
            ts_norm = ts_str
    else:
        # assume no fractional part -> add .000000
        ts_norm = f"{ts_str}.000000"

    try:
        dt = datetime.strptime(ts_norm, TIMESTAMP_FORMAT).replace(tzinfo=timezone.utc)
    except Exception as exc:
        raise ValueError("invalid timestamp format; expected YYYYMMDDHHMMSS.mmm") from exc

    return TagMessage(tag_id=tag_id, cnt=cnt, timestamp=dt)


def format_tag_message(msg: TagMessage) -> str:
    millis = int(msg.timestamp.microsecond / 1000)
    ts = msg.timestamp.strftime("%Y%m%d%H%M%S") + f".{millis:03d}"
    return f"TAG,{msg.tag_id},{msg.cnt},{ts}"


