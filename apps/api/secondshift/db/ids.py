"""ULID generation.

Sortable by creation time, generated without coordination. The database uses
these for every primary key except `events.id`, which is a dense integer so
timeline playback can cursor by a monotonic key.
"""

from __future__ import annotations

import os
import time

_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"  # Crockford base32, no I/L/O/U
_ENCODED_LEN = 26


def _encode(value: int, length: int) -> str:
    chars = []
    for _ in range(length):
        chars.append(_ALPHABET[value & 0x1F])
        value >>= 5
    return "".join(reversed(chars))


def new_ulid(now_ms: int | None = None) -> str:
    """Return a 26-character ULID: 48 bits of timestamp, 80 bits of randomness."""
    ts = now_ms if now_ms is not None else int(time.time() * 1000)
    randomness = int.from_bytes(os.urandom(10), "big")
    return _encode(ts, 10) + _encode(randomness, 16)


def timestamp_ms(ulid: str) -> int:
    """Recover the millisecond timestamp a ULID was generated at."""
    if len(ulid) != _ENCODED_LEN:
        raise ValueError(f"not a ULID: {ulid!r}")
    value = 0
    for char in ulid[:10]:
        value = (value << 5) | _ALPHABET.index(char)
    return value
