#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Rung 1 relay: subscribe to a feed's raw stream key on the fabric and
re-emit every frame as a UDP datagram to a local ASTERIX receiver.

  tools/asterix-relay.py --env <context> --key <topic key from goat topic ls> \
      --to 127.0.0.1:30048 [--format asterix:034,048] [--count N]
  tools/asterix-relay.py --env <context> --anchor <32hex> --system radar-one --site <site> --to ...

This is the consumer half of rung 1 for a receiver that only speaks UDP
(an off-the-shelf ASTERIX server, a data diode, a C2 gateway). The tap on
the publishing side put the sensor's datagrams on the fabric untouched; this
relay hands them to the receiver untouched. Nothing is converted.

Each frame is linted with the same block-framing walk the tap uses; a frame
that fails is counted and NOT forwarded, so a corrupt frame cannot reach the
receiver looking like a real one.

Uses `goat sub --follow --uuid`: goat prints a binary sample as
`<key> hex:<bytes>`, and its "listening on" line (older builds: "subscribed to") arrives on stderr (merged).
Demo simplification: one subprocess, line-oriented; a production relay holds
one zenoh session with a declared subscriber. The lint and the drop rule are
the part to copy.
"""

import argparse
import os
import socket
import subprocess
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
import asterixlint as L  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--env", default=os.environ.get("HF_ENV", ""), help="goat context holding your fabric credential")
    ap.add_argument("--key", default="", help="the feed's key as `goat topic ls` shows it; overrides --anchor/--system/--site")
    ap.add_argument("--anchor", default="", help="publisher's anchor (fabric cert CN, 32 hex) for the rung 1 key shape")
    ap.add_argument("--system", default="hello-feed")
    ap.add_argument("--site", default="notional")
    ap.add_argument("--to", default="127.0.0.1:30048", help="host:port of the UDP receiver")
    ap.add_argument("--format", default="asterix", help="asterix or asterix:<cat>,<cat>")
    ap.add_argument("--count", type=int, default=0, help="stop after N forwarded frames (0 = run until killed)")
    ap.add_argument("--timeout", type=float, default=0, help="stop after this many seconds (0 = none)")
    ap.add_argument("--ready-file", default="", help="touch this path once the subscription is open")
    ap.add_argument("--from-stdin", action="store_true", help="read `goat sub` output from stdin (offline test)")
    a = ap.parse_args()
    if not a.from_stdin and not a.env:
        ap.error("--env <goat context> is required: this step talks to a goatnet (see: goat context ls)")

    host, _, port = a.to.rpartition(":")
    dst = (host or "127.0.0.1", int(port))
    if a.key:
        key = a.key
    elif a.anchor:
        key = f"volatile/{a.anchor}/stream/{a.system}/{a.site}/raw/v1"
    else:
        ap.error("give --key, or --anchor with --system/--site")
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    if a.from_stdin:
        lines = sys.stdin
        proc = None
    else:
        proc = subprocess.Popen(["goat", "--context", a.env, "sub", key, "--follow", "--uuid"],
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        lines = proc.stdout

    fwd = refused = 0
    t0 = time.monotonic()
    try:
        for line in lines:
            line = line.rstrip("\n")
            if line.startswith(("subscribed to", "listening on")):
                print(f"relay: {line}", file=sys.stderr)
                if a.ready_file:
                    open(a.ready_file, "w").close()
                continue
            if " hex:" not in line:
                continue
            try:
                frame = bytes.fromhex(line.rsplit(" hex:", 1)[1].strip())
            except ValueError:
                continue
            ok, detail, cats = L.lint(frame, a.format)
            if not ok:
                refused += 1
                print(f"relay: refused frame ({detail}); not forwarded", file=sys.stderr)
                continue
            sock.sendto(frame, dst)
            fwd += 1
            print(f"relay: forwarded cats={cats} len={len(frame)} -> {a.to}", file=sys.stderr)
            if a.count and fwd >= a.count:
                break
            if a.timeout and time.monotonic() - t0 > a.timeout:
                break
    finally:
        if proc:
            proc.terminate()
    print(f"relay: forwarded={fwd} refused={refused}")
    return 0 if fwd or not a.count else 1


if __name__ == "__main__":
    sys.exit(main())
