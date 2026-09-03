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


def ordered_ulids(count: int, now_ms: int | None = None) -> list[str]:
    """`count` ULIDs that sort in the order they were asked for.

    `new_ulid` draws fresh randomness every call, so two identifiers minted in
    the same millisecond sort at random. Every `ORDER BY <ts>, id` in the
    repository is a stable tiebreak only across milliseconds, which is fine
    where the rows are seconds apart and wrong where a loop writes several at
    once.

    That was found on the morning surface: the interviewer raises its questions
    in one turn, in the order it judged most useful to ask them, and two
    questions written in the same millisecond arrived in the briefing in
    whichever order their random bits fell. On a list that is untidy; on a
    screen that shows one question at a time it discards the interviewer's
    judgment about which one matters, because the first is the one a person
    with thirty seconds answers.

    Implemented as the ULID specification's monotonic rule — one random draw,
    then increment — so the sequence is unguessable at its start and ordered
    within itself. It is deliberately *not* what `new_ulid` does: making every
    identifier in the process monotonic would put shared mutable state under
    every table's primary key, and only the callers that hold ordering
    information need this.
    """
    if count < 0:
        raise ValueError("count must not be negative")
    ts = now_ms if now_ms is not None else int(time.time() * 1000)
    randomness = int.from_bytes(os.urandom(10), "big")
    # Leave headroom so the increments below cannot carry into the timestamp.
    # A batch large enough to exhaust it would need 2**80 identifiers.
    randomness = min(randomness, (1 << 80) - 1 - count)
    return [_encode(ts, 10) + _encode(randomness + i, 16) for i in range(count)]
