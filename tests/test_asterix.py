#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Offline tests: codec round trip, lint vectors shared with goat's guard,
refusal of unimplemented items by name, GeoTrackV1 validation.

  python3 tests/test_asterix.py
"""
import importlib.util
import json
import os
import sys
from base64 import b64encode

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, os.path.join(ROOT, "lib"))
import asterix048 as ax  # noqa: E402
import asterixlint as L  # noqa: E402

spec = importlib.util.spec_from_file_location("dec", os.path.join(ROOT, "tools", "asterix-decode.py"))
dec = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dec)

fails = []


def check(label, cond, detail=""):
    print(f"  {'ok  ' if cond else 'FAIL'}  {label}{'  — ' + str(detail) if detail and not cond else ''}")
    if not cond:
        fails.append(label)


print("codec round trip")
rec = ax.encode_048(7, 3, 43200.5, 12.5, 45.0, "7000", 350, 0xF00101, 101, 420, 92.0, simulated=True)
nm = ax.encode_034_north_marker(7, 3, 43200.0)
frame = ax.block(34, [nm]) + ax.block(48, [rec, rec])
out = ax.decode_frame(frame)
check("three records decoded (1 marker, 2 plots)", len(out) == 3 and [o["cat"] for o in out] == [34, 48, 48], out)
f = out[1]["fields"]
check("SAC/SIC", (f["sac"], f["sic"]) == (7, 3))
check("time of day at 1/128 s", abs(f["tod_s"] - 43200.5) < 1 / 128)
check("polar position", abs(f["rho_nm"] - 12.5) < 1 / 256 and abs(f["theta_deg"] - 45.0) < 0.01, f)
check("Mode 3/A octal", f["mode3a"] == "7000")
check("flight level in 1/4 FL", f["fl"] == 350.0)
check("aircraft address hex", f["address"] == "F00101")
check("track number", f["track_no"] == 101)
check("velocity", abs(f["gs_kt"] - 420) < 0.2 and abs(f["heading_deg"] - 92.0) < 0.01, f)
check("SIM bit read from I048/020", f["simulated"] is True)
check("north marker recognised", out[0]["fields"]["message_type"] == "north-marker")

print("refusal by name")
bad = ax._fspec([1, 7]) + bytes([7, 3]) + b"\x00"
try:
    ax.decode_frame(ax.block(48, [bad]))
    check("I048/130 (compound) refused", False, "no exception")
except ax.NotDecoded as e:
    check("I048/130 (compound) refused, named", "I048/130" in str(e), e)
try:
    ax.decode_frame(ax.block(62, [b"\x00"]))
    check("CAT 062 refused", False, "no exception")
except ax.NotDecoded as e:
    check("CAT 062 refused, named", "62" in str(e), e)

print("lint vectors (shared with goat ops/ci/check-topic-decode-health.py)")
blk48 = ax.block(48, [rec])
blk34 = ax.block(34, [nm])
check("one block frames", L.asterix_blocks(blk48)[0] == [48])
check("two blocks frame in order", L.asterix_blocks(blk34 + blk48)[0] == [34, 48])
check("truncated refused", L.asterix_blocks(blk48[:-1])[0] is None)
check("trailing byte refused", L.asterix_blocks(blk48 + b"\x30")[0] is None)
check("LEN < 3 refused", L.asterix_blocks(bytes([48, 0, 2]) + b"xx")[0] is None)
check("declared set accepts", L.lint(blk34 + blk48, "asterix:034,048")[0])
check("stray category refused", not L.lint(blk34 + blk48, "asterix:048")[0])
check("cat-prefixed spelling", L.lint(blk48, "asterix:cat048")[0])
check("malformed declaration refused", not L.lint(blk48, "asterix:radar")[0])
check("base64 text of a frame refused", not L.lint(b64encode(blk48), "asterix")[0])
check("digest is sha256 hex", len(L.digest(blk48)) == 64)
check("split_blocks yields each block", list(L.split_blocks(blk34 + blk48)) == [blk34, blk48])

print("GeoTrackV1")
uid, track = dec.to_track(f, "0" * 32, "hello-feed", "notional", "node", 10.0, -30.0)
with open(os.path.join(ROOT, "schemas", "goat.geo.track.v1.schema.json")) as fh:
    schema = json.load(fh)
try:
    import jsonschema
    errs = list(jsonschema.Draft202012Validator(schema).iter_errors(track))
    check("record validates against the vendored schema", not errs, errs[:1])
except ImportError:
    ok, missing = dec.required_fields_present(track, schema)
    check("record carries every required field (jsonschema not installed)", ok, missing)
check("id is namespaced", track["id"] == "asterix048:7-3-101")
check("synthetic is true", track["synthetic"] is True)
check("altitude from FL", abs(track["alt_m"] - 350 * 100 * 0.3048) < 0.2)

if fails:
    print(f"\n{len(fails)} failure(s): {fails}")
    sys.exit(1)
print("\nall checks passed")


def test_relay_forwards_byte_identical_and_refuses_truncated():
    """tools/asterix-relay.py reads `goat sub` lines from stdin, forwards every
    framed datagram unchanged over UDP, and refuses a truncated one."""
    import socket
    import subprocess
    good = ax.block(48, [rec])
    key = "volatile/" + "a" * 32 + "/stream/radar-one/x/raw/v1"
    feed = f"subscribed to {key}\n{key} hex:{good.hex()}\n{key} hex:{good[:-3].hex()}\n{key} hex:{good.hex()}\n"
    r = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    r.bind(("127.0.0.1", 0))
    r.settimeout(5)
    port = r.getsockname()[1]
    p = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "asterix-relay.py"), "--anchor", "a" * 32,
                        "--system", "radar-one", "--site", "x", "--to", f"127.0.0.1:{port}",
                        "--format", "asterix:034,048", "--from-stdin", "--count", "2"],
                       input=feed, capture_output=True, text=True, timeout=20)
    assert p.returncode == 0, p.stderr
    assert "forwarded=2 refused=1" in p.stdout
    assert [r.recvfrom(4096)[0] for _ in range(2)] == [good, good]
