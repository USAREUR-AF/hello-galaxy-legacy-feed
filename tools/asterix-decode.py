#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Rung 2 adapter: receive ASTERIX datagrams, decode the CAT 048 items a map
needs, emit one GeoTrackV1 record per plot, validate it against the published
schema, and (optionally) publish it to a STORED key.

  tools/asterix-decode.py --listen 0.0.0.0:30048 --count 6 --sensor-at 10.0,-30.0 --print
  tools/asterix-decode.py ... --publish --env <context> --system hello-feed

Keys (per-entity, the shape goat-map draws):
  <anchor>/<system>/geo/track/asterix048/<sac>-<sic>-<track_no>

A record with an item this adapter does not implement is REFUSED by name and
counted; nothing is guessed. The GeoTrackV1 schema is vendored from goat at
schemas/goat.geo.track.v1.schema.json. `synthetic` is set TRUE
unconditionally here because this adapter has no registry to read it from;
in goat the flag comes from the producer org's registry row, never from the
payload.
"""

import argparse
import json
import os
import socket
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "lib"))
import asterix048 as ax  # noqa: E402
import asterixlint as L  # noqa: E402

SCHEMA = os.path.join(HERE, "..", "schemas", "goat.geo.track.v1.schema.json")


def validator():
    try:
        import jsonschema
    except ImportError:
        return None
    with open(SCHEMA) as f:
        return jsonschema.Draft202012Validator(json.load(f))


def required_fields_present(rec, schema):
    missing = [k for k in schema["required"] if k not in rec]
    return (not missing), missing


def to_track(f, anchor, system, site, node, lat0, lon0):
    lat, lon = ax.polar_to_latlon(lat0, lon0, f["rho_nm"], f["theta_deg"])
    uid = f"{f['sac']}-{f['sic']}-{f['track_no']}"
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    day = time.strftime("%Y-%m-%d", time.gmtime())
    tod = f.get("tod_s")
    reported = None
    if tod is not None:
        h, rem = divmod(int(tod), 3600)
        m, s = divmod(rem, 60)
        reported = f"{day}T{h:02d}:{m:02d}:{s:02d}Z"
    rec = {
        "schema": "goat.geo.track.v1",
        "id": f"asterix048:{uid}",
        "label": str(f["track_no"]),
        "kind": "track",
        "source": {"sensor": "asterix-cat048", "site": site, "node": node},
        "lat": round(lat, 6), "lon": round(lon, 6),
        "alt_m": round(f["fl"] * 100 * 0.3048, 1) if f.get("fl_valid") else None,
        "course_deg": round(f["heading_deg"], 2) if "heading_deg" in f else None,
        "speed_mps": round(f["gs_kt"] * 0.514444, 2) if "gs_kt" in f else None,
        "affiliation": "unknown",
        "dimension": "air",
        "descriptor": f"mode3a={f.get('mode3a')} addr={f.get('address')} sim={f.get('simulated')}",
        "reported_at": reported,
        "observed_at": now,
        "synthetic": True,
        "producer_anchor": anchor,
        "org": None,
    }
    return uid, rec


def anchor_for(env):
    cert = os.path.expanduser(f"~/.goat/contexts/{env}/mtls.cert.pem")
    out = subprocess.run(["openssl", "x509", "-in", cert, "-noout", "-subject"],
                         capture_output=True, text=True, check=True).stdout
    for part in out.replace("subject=", "").split(","):
        k, _, v = part.strip().partition("=")
        if k.strip() == "CN":
            return v.strip()
    raise SystemExit(f"no CN in {cert}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--listen", default="0.0.0.0:30048")
    ap.add_argument("--count", type=int, default=6, help="datagrams to consume")
    ap.add_argument("--sensor-at", default="10.0,-30.0", help="sensor lat,lon (notional default, open Atlantic)")
    ap.add_argument("--system", default="hello-feed")
    ap.add_argument("--site", default="notional")
    ap.add_argument("--node", default="hello-feed-adapter")
    ap.add_argument("--env", default=os.environ.get("HF_ENV", ""), help="goat context holding your fabric credential")
    ap.add_argument("--anchor", default="", help="override (offline runs use 32 zeros)")
    ap.add_argument("--publish", action="store_true", help="goat pub each record with --confirm")
    ap.add_argument("--print", action="store_true", help="print each record")
    ap.add_argument("--timeout", type=float, default=30.0)
    a = ap.parse_args()
    if a.publish and not a.env:
        ap.error("--env <goat context> is required: this step talks to a goatnet (see: goat context ls)")
    lat0, lon0 = (float(x) for x in a.sensor_at.split(","))
    anchor = a.anchor or (anchor_for(a.env) if a.publish else "0" * 32)
    with open(SCHEMA) as fh:
        schema = json.load(fh)
    v = validator()
    print(f"schema {schema['$id']} ({'jsonschema' if v else 'required-fields-only'} validation)", flush=True)
    host, port = a.listen.rsplit(":", 1)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((host, int(port)))
    sock.settimeout(a.timeout)
    plots = markers = refused = invalid = published = confirmed_fail = 0
    for seq in range(1, a.count + 1):
        try:
            data, _ = sock.recvfrom(65535)
        except socket.timeout:
            print(f"timeout after {a.timeout}s with {seq - 1} received", flush=True)
            break
        good, detail, _ = L.lint(data, "asterix:034,048")
        if not good:
            refused += 1
            print(f"decode #{seq:03d} REFUSED at framing: {detail}", flush=True)
            continue
        try:
            records = ax.decode_frame(data)
        except ax.NotDecoded as ex:
            refused += 1
            print(f"decode #{seq:03d} REFUSED, carried raw only: {ex}", flush=True)
            continue
        for r in records:
            if r["cat"] == 34:
                markers += 1
                print(f"decode #{seq:03d} CAT034 {r['fields']['message_type']} tod={r['fields']['tod_s']:.3f}s", flush=True)
                continue
            uid, rec = to_track(r["fields"], anchor, a.system, a.site, a.node, lat0, lon0)
            if v:
                errs = sorted(v.iter_errors(rec), key=lambda e: e.path)
                ok = not errs
                why = errs[0].message if errs else ""
            else:
                ok, missing = required_fields_present(rec, schema)
                why = f"missing {missing}" if missing else ""
            if not ok:
                invalid += 1
                print(f"decode #{seq:03d} track {uid} INVALID against schema: {why}", flush=True)
                continue
            plots += 1
            key = f"{anchor}/{a.system}/geo/track/asterix048/{uid}"
            if a.print:
                print(json.dumps(rec, separators=(",", ":")), flush=True)
            else:
                print(f"decode #{seq:03d} track {uid} lat={rec['lat']} lon={rec['lon']} alt_m={rec['alt_m']} valid", flush=True)
            if a.publish:
                payload = json.dumps(rec, separators=(",", ":")).encode()
                cmd = ["goat", "--context", a.env, "pub", key, "--encoding", "json", "--confirm",
                       "--payload-file", "/dev/stdin"]
                res = subprocess.run(cmd, input=payload, capture_output=True)
                if res.returncode == 0:
                    published += 1
                    print(f"        published + confirmed {key}", flush=True)
                else:
                    confirmed_fail += 1
                    print(f"        publish NOT confirmed {key}: {res.stderr.decode(errors='replace').strip().splitlines()[-1:]}", flush=True)
    print(f"decode done: {plots} plot(s) valid, {markers} north marker(s), {refused} frame(s) refused, "
          f"{invalid} record(s) invalid, {published} published, {confirmed_fail} not confirmed", flush=True)
    sys.exit(0 if (invalid == 0 and confirmed_fail == 0) else 6)


if __name__ == "__main__":
    main()
