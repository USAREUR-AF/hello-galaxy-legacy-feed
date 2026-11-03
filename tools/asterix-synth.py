#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""A synthetic radar: emits ASTERIX CAT 034 north markers and CAT 048 plots
over UDP, the way a real sensor would, so every rung has a sensor to point at.

  tools/asterix-synth.py --to 127.0.0.1:30048 --count 10 --rate 2
  tools/asterix-synth.py --to 100.64.x.y:30048 --count 10 --corrupt-every 5

Every plot carries I048/020 SIM=1: the wire bytes say "simulated" and a
decoder that reads them says so too. --corrupt-every N truncates every Nth
datagram by one byte so the framing lint has something to refuse.
"""

import argparse
import os
import socket
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "lib"))
import asterix048 as ax  # noqa: E402

TRACKS = [  # track_no, rho_nm, theta_deg, mode3a, fl, address, gs_kt, heading
    # addresses sit in the ICAO 0xF0xxxx special-use block: no real airframe carries them
    (101, 12.5, 45.0, "7000", 350, 0xF00101, 420, 92.0),
    (102, 31.2, 210.5, "2345", 120, 0xF00102, 250, 15.0),
    (103, 58.9, 300.0, "1200", 60, 0xF00103, 140, 270.0),
]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--to", default="127.0.0.1:30048", help="receiver host:port")
    ap.add_argument("--count", type=int, default=10, help="datagrams to send")
    ap.add_argument("--rate", type=float, default=2.0, help="datagrams per second")
    ap.add_argument("--sac", type=int, default=7)
    ap.add_argument("--sic", type=int, default=3)
    ap.add_argument("--corrupt-every", type=int, default=0,
                    help="truncate every Nth datagram by one byte (0 = never)")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()
    host, port = a.to.rsplit(":", 1)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sent = corrupted = 0
    for i in range(a.count):
        now = time.time()
        tod = now % 86400
        recs = []
        if i % 4 == 0:
            frame = ax.block(34, [ax.encode_034_north_marker(a.sac, a.sic, tod)])
        else:
            for t, rho, theta, m3a, fl, addr, gs, hdg in TRACKS:
                theta = (theta + i * 1.5) % 360.0
                recs.append(ax.encode_048(a.sac, a.sic, tod, rho, theta, m3a, fl, addr, t, gs, hdg, simulated=True))
            frame = ax.block(48, recs)
        if a.corrupt_every and (i + 1) % a.corrupt_every == 0:
            frame = frame[:-1]
            corrupted += 1
            tag = "CORRUPT"
        else:
            tag = "ok"
        sock.sendto(frame, (host, int(port)))
        sent += 1
        if not a.quiet:
            print(f"sent #{i + 1:03d} cat={frame[0]:03d} len={len(frame):3d} {tag}", flush=True)
        if i + 1 < a.count:
            time.sleep(1.0 / a.rate)
    print(f"synth done: {sent} datagram(s) sent, {corrupted} deliberately corrupted", flush=True)


if __name__ == "__main__":
    main()
