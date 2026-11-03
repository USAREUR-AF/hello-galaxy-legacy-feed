#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Rung 0 receiver: listen for ASTERIX datagrams, lint the framing, write a
digest log. This is what a partner's receiver COULD do beside its real job;
nothing here touches the fabric.

  tools/asterix-recv.py --listen 0.0.0.0:30048 --count 10 --format asterix:034,048 \
      --digest-log .run/recv-digests.jsonl

The digest log is one JSON object per datagram: seq, category list, length,
sha256, lint verdict. Two receivers on opposite sides of a data diode each
write one; comparing the two logs offline is the integrity check across the
diode, because the diode has no return path for anything else.
"""

import argparse
import json
import os
import socket
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
import asterixlint as L  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--listen", default="0.0.0.0:30048")
    ap.add_argument("--count", type=int, default=10, help="datagrams to accept before exiting")
    ap.add_argument("--format", default="asterix", help="asterix | asterix:048 | asterix:034,048")
    ap.add_argument("--digest-log", default="", help="JSONL path; omit to print only")
    ap.add_argument("--timeout", type=float, default=30.0)
    a = ap.parse_args()
    host, port = a.listen.rsplit(":", 1)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((host, int(port)))
    sock.settimeout(a.timeout)
    log = open(a.digest_log, "a") if a.digest_log else None
    ok = bad = 0
    print(f"listening on {a.listen} for {a.count} datagram(s), lint format {a.format}", flush=True)
    for seq in range(1, a.count + 1):
        try:
            data, peer = sock.recvfrom(65535)
        except socket.timeout:
            print(f"timeout after {a.timeout}s with {seq - 1} received", flush=True)
            break
        good, detail, cats = L.lint(data, a.format)
        row = {"seq": seq, "from": peer[0], "len": len(data), "cats": cats,
               "sha256": L.digest(data), "ok": good, "detail": detail,
               "received_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
        if log:
            log.write(json.dumps(row) + "\n")
            log.flush()
        if good:
            ok += 1
            print(f"recv #{seq:03d} from {peer[0]} cats={cats} len={len(data)} sha256={row['sha256'][:16]}… ok", flush=True)
        else:
            bad += 1
            print(f"recv #{seq:03d} from {peer[0]} len={len(data)} REFUSED: {detail}", flush=True)
    print(f"recv done: {ok} framed, {bad} refused", flush=True)
    sys.exit(0 if bad == 0 else 3)


if __name__ == "__main__":
    main()
