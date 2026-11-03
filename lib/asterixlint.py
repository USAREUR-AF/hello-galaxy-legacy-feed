#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""ASTERIX block-framing lint — the same walk the goat decode-health guard runs.

An ASTERIX data block is: one octet CATEGORY, two octets LENGTH (big-endian,
counting the whole block including this 3-octet header), then records. A
UDP datagram carries one or more blocks laid end to end.

This checks the ENVELOPE only. A block whose records are nonsense still
frames. Per-item decoding is asterix048.py's job, at rung 2.

Kept byte-for-byte in step with `asterix_blocks` / `asterix_declared_cats`
in goat's ops/ci/check-topic-decode-health.py; tests/test_asterix.py pins
the shared vectors so the two cannot drift apart silently.
"""

import hashlib


def asterix_blocks(payload):
    """Returns (cats, reason): the category of every block in order, or
    (None, why) when the framing cannot be true."""
    n, off, cats = len(payload), 0, []
    if n < 3:
        return None, f"{n} byte(s) is shorter than one 3-octet block header"
    while off < n:
        if n - off < 3:
            return None, f"{n - off} trailing byte(s) after the last complete block"
        cat = payload[off]
        ln = int.from_bytes(payload[off + 1:off + 3], "big")
        if ln < 3:
            return None, f"block at offset {off} declares LEN {ln}, below the 3-octet header"
        if off + ln > n:
            return None, (f"block at offset {off} declares LEN {ln} but only "
                          f"{n - off} byte(s) remain")
        cats.append(cat)
        off += ln
    return cats, ""


def asterix_declared_cats(fmt):
    """'asterix:034,048' -> {34, 48}; 'asterix' -> set(). Raises on junk."""
    if ":" not in fmt:
        return set()
    out = set()
    for part in fmt.split(":", 1)[1].split(","):
        part = part.strip().lower().removeprefix("cat")
        if not part.isdigit():
            raise ValueError(f"'{part}' is not an ASTERIX category number")
        out.add(int(part))
    return out


def lint(payload, fmt="asterix"):
    """(ok, detail, cats). ok is False when the frame must not be published."""
    try:
        declared = asterix_declared_cats(fmt)
    except ValueError as ex:
        return False, f"format '{fmt}' is malformed: {ex}", None
    cats, reason = asterix_blocks(payload)
    if cats is None:
        return False, f"not ASTERIX block framing: {reason}", None
    if declared:
        stray = sorted(set(cats) - declared)
        if stray:
            return False, f"block category {stray[0]} present but feed declares {fmt}", cats
    return True, "", cats


def digest(payload):
    """The per-frame digest published beside the bytes: SHA-256, hex."""
    return hashlib.sha256(payload).hexdigest()


def split_blocks(payload):
    """Yield each complete block as bytes. Caller lints first."""
    off = 0
    while off < len(payload):
        ln = int.from_bytes(payload[off + 1:off + 3], "big")
        yield payload[off:off + ln]
        off += ln
