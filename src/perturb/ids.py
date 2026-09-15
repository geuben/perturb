import os
import time

_CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def new_ulid() -> str:
    ms = int(time.time() * 1000)
    rand = int.from_bytes(os.urandom(10), "big") & ((1 << 80) - 1)
    value = (ms << 80) | rand
    chars = []
    for _ in range(26):
        chars.append(_CROCKFORD[value & 0x1F])
        value >>= 5
    return "".join(reversed(chars))
