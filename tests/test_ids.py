import time

from perturb.ids import new_ulid

CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def test_new_ulid_encodes_current_time_in_crockford_base32():
    before_ms = int(time.time() * 1000)
    result = new_ulid()
    after_ms = int(time.time() * 1000)

    assert len(result) == 26
    assert all(c in CROCKFORD for c in result)

    # Decode the first 10 chars as a 50-bit Crockford base32 number (timestamp in ms).
    ts_chars = result[:10]
    decoded = 0
    for c in ts_chars:
        decoded = decoded * 32 + CROCKFORD.index(c)

    assert before_ms - 5000 <= decoded <= after_ms + 5000
