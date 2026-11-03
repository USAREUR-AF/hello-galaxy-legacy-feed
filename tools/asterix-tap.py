#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Rung 1 tap: receive ASTERIX datagrams, lint, publish the UNTOUCHED bytes
to a routed-never-stored stream key, and publish a per-frame digest beside
them on a sibling key.

  tools/asterix-tap.py --listen 0.0.0.0:30048 --count 10 --env <context> \
      --system hello-feed --site notional --format asterix:034,048

Keys (anchor read from the goat context's certificate CN):
  volatile/<anchor>/stream/<system>/<site>/raw/v1          the bytes
  volatile/<anchor>/stream/<system>/<site>/raw-digest/v1   {"seq","cats","len","sha256"}

A frame that fails the lint is DROPPED and counted, never published: a
consumer cannot tell corrupt bytes from real ones, an absent frame alarms.

Demo simplification, stated: each frame is one `goat pub` process, so this
tap tops out around one frame a second. A production tap holds one zenoh
session with one declared publisher per key and puts the digest in the
sample ATTACHMENT; the goat CLI has no attachment flag, hence the sibling
key here. The key shape and the lint are the part to copy.
"""

import argparse
import json
import os
import socket
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
import asterixlint as L  # noqa: E402


def anchor_for(env):
    cert = os.path.expanduser(f"~/.goat/contexts/{env}/mtls.cert.pem")
    out = subprocess.run(["openssl", "x509", "-in", cert, "-noout", "-subject"],
                         capture_output=True, text=True, check=True).stdout
    for part in out.replace("subject=", "").split(","):
        k, _, v = part.strip().partition("=")
        if k.strip() == "CN":
            return v.strip()
    raise SystemExit(f"no CN in {cert}")


def goat_pub(env, key, payload, encoding=None):
    cmd = ["goat", "--context", env, "pub", key, "--volatile-stream", "--payload-file", "/dev/stdin"]
    if encoding:
        cmd += ["--encoding", encoding]
    r = subprocess.run(cmd, input=payload, capture_output=True)
    return r.returncode == 0, r.stderr.decode(errors="replace").strip().splitlines()[-1:] or [""]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--listen", default="0.0.0.0:30048")
    ap.add_argument("--count", type=int, default=10)
    ap.add_argument("--env", default=os.environ.get("HF_ENV", ""), help="goat context holding your fabric credential")
    ap.add_argument("--system", default="hello-feed")
    ap.add_argument("--site", default="notional")
    ap.add_argument("--format", default="asterix:034,048")
    ap.add_argument("--timeout", type=float, default=60.0)
    ap.add_argument("--anchor", default="", help="override the anchor (tests)")
    a = ap.parse_args()
    if not a.env:
        ap.error("--env <goat context> is required: this step talks to a goatnet (see: goat context ls)")
    anchor = a.anchor or anchor_for(a.env)
    raw_key = f"volatile/{anchor}/stream/{a.system}/{a.site}/raw/v1"
    dig_key = f"volatile/{anchor}/stream/{a.system}/{a.site}/raw-digest/v1"
    print(f"anchor {anchor}\nraw    {raw_key}\ndigest {dig_key}", flush=True)
    host, port = a.listen.rsplit(":", 1)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((host, int(port)))
    sock.settimeout(a.timeout)
    published = dropped = failed = 0
    for seq in range(1, a.count + 1):
        try:
            data, _ = sock.recvfrom(65535)
        except socket.timeout:
            print(f"timeout after {a.timeout}s with {seq - 1} received", flush=True)
            break
        good, detail, cats = L.lint(data, a.format)
        if not good:
            dropped += 1
            print(f"tap #{seq:03d} len={len(data)} DROPPED, not published: {detail}", flush=True)
            continue
        sha = L.digest(data)
        ok1, err1 = goat_pub(a.env, raw_key, data)
        digest = json.dumps({"seq": seq, "cats": cats, "len": len(data), "sha256": sha},
                            separators=(",", ":")).encode()
        ok2, err2 = goat_pub(a.env, dig_key, digest, encoding="json")
        if ok1 and ok2:
            published += 1
            print(f"tap #{seq:03d} cats={cats} len={len(data)} sha256={sha[:16]}… published bytes + digest", flush=True)
        else:
            failed += 1
            print(f"tap #{seq:03d} publish FAILED raw={ok1} digest={ok2} {err1} {err2}", flush=True)
    print(f"tap done: {published} published, {dropped} dropped by lint, {failed} publish failures", flush=True)
    sys.exit(0 if failed == 0 else 4)


if __name__ == "__main__":
    main()
