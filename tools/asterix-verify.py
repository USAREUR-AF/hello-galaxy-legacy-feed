#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Rung 1 verify: subscribe to the bytes key and the digest key, recompute
SHA-256 over every frame received, and report whether each frame has a
matching digest and whether the digest sequence has gaps.

  tools/asterix-verify.py --env <context> --anchor <32hex> --system hello-feed --site notional \
      --expect 8 --timeout 90

Uses two `goat sub --follow --uuid` processes (--uuid so the printed key is
the canonical anchor form, not the display alias). `goat sub` prints a
binary sample as `<key> hex:<bytes>` and a JSON sample as `<key> <text>`;
both are parsed here; its "listening on" line (older builds: "subscribed to") arrives on stderr, merged.
Frames are matched to digests by SHA-256, not by arrival order, because the
two keys are independent DROP streams.

What this proves: the bytes a subscriber holds are the bytes the tap
published. What it does not prove: that the sensor produced them, or that
anything was delivered to anyone else.
"""

import argparse
import hashlib
import json
import os
import subprocess
import sys
import threading
import time


def tail(cmd, sink, stop):
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        for line in p.stdout:
            if stop.is_set():
                break
            sink(line.rstrip("\n"))
    finally:
        p.terminate()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--env", default=os.environ.get("HF_ENV", ""), help="goat context holding your fabric credential")
    ap.add_argument("--anchor", required=True)
    ap.add_argument("--system", default="hello-feed")
    ap.add_argument("--site", default="notional")
    ap.add_argument("--expect", type=int, default=8, help="frames expected; exits when seen")
    ap.add_argument("--timeout", type=float, default=90.0)
    ap.add_argument("--ready-file", default="", help="touch this path once both subscriptions are open")
    a = ap.parse_args()
    if not a.env:
        ap.error("--env <goat context> is required: this step talks to a goatnet (see: goat context ls)")
    raw_key = f"volatile/{a.anchor}/stream/{a.system}/{a.site}/raw/v1"
    dig_key = f"volatile/{a.anchor}/stream/{a.system}/{a.site}/raw-digest/v1"
    frames, digests, lock, stop = [], {}, threading.Lock(), threading.Event()
    opened = {"raw": False, "dig": False}

    def on_raw(line):
        if line.startswith(("subscribed to", "listening on")):
            opened["raw"] = True
            return
        if " hex:" in line:
            hx = line.rsplit(" hex:", 1)[1].strip()
            try:
                b = bytes.fromhex(hx)
            except ValueError:
                return
            with lock:
                frames.append(hashlib.sha256(b).hexdigest())

    def on_dig(line):
        if line.startswith(("subscribed to", "listening on")):
            opened["dig"] = True
            return
        if line.startswith(dig_key + " "):
            body = line[len(dig_key) + 1:].strip()
            try:
                d = json.loads(body)
            except ValueError:
                return
            with lock:
                digests[d["sha256"]] = d

    threads = [
        threading.Thread(target=tail, args=(["goat", "--context", a.env, "sub", raw_key, "--follow", "--uuid"], on_raw, stop), daemon=True),
        threading.Thread(target=tail, args=(["goat", "--context", a.env, "sub", dig_key, "--follow", "--uuid"], on_dig, stop), daemon=True),
    ]
    for t in threads:
        t.start()
    t0 = time.time()
    ready_written = False
    while time.time() - t0 < a.timeout:
        if not ready_written and opened["raw"] and opened["dig"]:
            print("verify: both subscriptions open", flush=True)
            if a.ready_file:
                open(a.ready_file, "w").close()
            ready_written = True
        with lock:
            if len(frames) >= a.expect and len(digests) >= a.expect:
                break
        time.sleep(0.5)
    stop.set()
    with lock:
        matched = sum(1 for s in frames if s in digests)
        unmatched = len(frames) - matched
        seqs = sorted(d["seq"] for d in digests.values())
    gaps = [s for s in range(seqs[0], seqs[-1] + 1) if s not in seqs] if seqs else []
    print(f"verify: {len(frames)} frame(s) received, {len(digests)} digest(s) received, "
          f"{matched} matched by sha256, {unmatched} without a digest, digest seq gaps {gaps or 'none'}", flush=True)
    sys.exit(0 if (len(frames) >= a.expect and unmatched == 0) else 5)


if __name__ == "__main__":
    main()
