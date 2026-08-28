"""ULIDs drawn from a seeded generator.

`db.ids.new_ulid` takes its randomness from `os.urandom`, which is right for
real work and fatal here: an identifier that changes between two runs of the
same seed makes the night unreproducible, and reproducibility is the whole
value of a seed — a demo that can be rehearsed, a test that can name a row.

The layout is the one the schema already expects — 48 bits of timestamp then 80
bits of randomness in Crockford base32 — so `db.ids.timestamp_ms` reads these
back and `ORDER BY created_at_ms, id` sorts a generated night by the same clock
it sorts a real one by.
"""

from __future__ import annotations

import random

_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"  # Crockford base32, no I/L/O/U
_TIME_CHARS = 10
_RANDOM_CHARS = 16
_BITS_PER_CHAR = 5


def _encode(value: int, length: int) -> str:
    chars = []
    for _ in range(length):
        chars.append(_ALPHABET[value & 0x1F])
        value >>= _BITS_PER_CHAR
    return "".join(reversed(chars))


class Mint:
    """A ULID source bound to one seeded generator."""

    def __init__(self, rng: random.Random) -> None:
        self._rng = rng

    def __call__(self, ts_ms: int) -> str:
        """A ULID carrying `ts_ms`, unique within this generator's stream.

        `Repository.insert_entry` rejects a client-supplied identifier whose
        embedded instant disagrees with `created_at_ms`, so the timestamp half
        is the caller's instant rather than anything this class chooses.
        """
        return _encode(ts_ms, _TIME_CHARS) + _encode(
            self._rng.getrandbits(_RANDOM_CHARS * _BITS_PER_CHAR), _RANDOM_CHARS
        )
