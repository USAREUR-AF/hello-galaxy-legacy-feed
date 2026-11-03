#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""A deliberately small ASTERIX CAT 034 / CAT 048 encoder and decoder.

It implements the items a position consumer needs and REFUSES the rest by
name. That refusal is the design, not a shortcut: a rung-2 adapter decodes
what its consumer reads and carries everything else untouched at rung 1.
Guessing at an unimplemented item would publish a typed record nobody can
trust.

Encodings follow the EUROCONTROL CAT 048 and CAT 034 specifications as
commonly fielded (CAT 048 ed. 1.2x UAP; CAT 034 ed. 1.2x UAP). Field
units are stated at each item so a reader can check them against the spec.
"""

import math
import struct

# ---------------------------------------------------------------------------
# User Application Profiles: FRN -> (item, kind, fixed-length-or-None)
# kind: F fixed, X extensible (octets until FX bit 0), C compound, R repetitive
# ---------------------------------------------------------------------------
UAP_048 = {
    1: ("I048/010", "F", 2), 2: ("I048/140", "F", 3), 3: ("I048/020", "X", None),
    4: ("I048/040", "F", 4), 5: ("I048/070", "F", 2), 6: ("I048/090", "F", 2),
    7: ("I048/130", "C", None),
    8: ("I048/220", "F", 3), 9: ("I048/240", "F", 6), 10: ("I048/250", "R", 8),
    11: ("I048/161", "F", 2), 12: ("I048/042", "F", 4), 13: ("I048/200", "F", 4),
    14: ("I048/170", "X", None),
    15: ("I048/210", "F", 4), 16: ("I048/030", "X", None), 17: ("I048/080", "F", 2),
    18: ("I048/100", "F", 4), 19: ("I048/110", "F", 2), 20: ("I048/120", "C", None),
    21: ("I048/230", "F", 2),
    22: ("I048/260", "F", 7), 23: ("I048/055", "F", 1), 24: ("I048/050", "F", 2),
    25: ("I048/065", "F", 1), 26: ("I048/060", "F", 2), 27: ("SP", "C", None),
    28: ("RE", "C", None),
}
UAP_034 = {
    1: ("I034/010", "F", 2), 2: ("I034/000", "F", 1), 3: ("I034/030", "F", 3),
    4: ("I034/020", "F", 1), 5: ("I034/041", "F", 2), 6: ("I034/050", "C", None),
    7: ("I034/060", "C", None),
}

# Items this module decodes into fields. Everything else present in a record
# makes decode() raise NotDecoded naming the item.
DECODED_048 = {"I048/010", "I048/140", "I048/020", "I048/040", "I048/070",
               "I048/090", "I048/220", "I048/161", "I048/200"}
DECODED_034 = {"I034/010", "I034/000", "I034/030"}


class NotDecoded(Exception):
    """The record carries an item this adapter does not implement."""


def _fspec(frns):
    """FSPEC octets for a set of FRNs: 7 bits per octet MSB-first, FX in LSB."""
    top = max(frns)
    n_oct = (top + 6) // 7
    out = bytearray(n_oct)
    for frn in frns:
        o, b = (frn - 1) // 7, (frn - 1) % 7
        out[o] |= 0x80 >> b
    for o in range(n_oct - 1):
        out[o] |= 0x01
    return bytes(out)


def _parse_fspec(buf, off):
    frns, frn_base = [], 0
    while True:
        octet = buf[off]
        off += 1
        for b in range(7):
            if octet & (0x80 >> b):
                frns.append(frn_base + b + 1)
        frn_base += 7
        if not octet & 0x01:
            break
    return frns, off


def block(cat, records):
    body = b"".join(records)
    ln = 3 + len(body)
    return bytes([cat]) + ln.to_bytes(2, "big") + body


# ---------------------------------------------------------------------------
# CAT 048 — monoradar target reports
# ---------------------------------------------------------------------------
def encode_048(sac, sic, tod_s, rho_nm, theta_deg, mode3a_octal, fl, address,
               track_no, gs_kt, heading_deg, simulated=True):
    """One CAT 048 record carrying I048/010,140,020,040,070,090,220,161,200.

    tod_s: seconds since midnight UTC. rho_nm/theta_deg: polar position from
    the sensor. fl: flight level (hundreds of feet). address: 24-bit ICAO.
    gs_kt/heading_deg: calculated track velocity.
    """
    frns = [1, 2, 3, 4, 5, 6, 8, 11, 13]
    i010 = bytes([sac & 0xFF, sic & 0xFF])
    i140 = (int(round(tod_s * 128)) & 0xFFFFFF).to_bytes(3, "big")
    # I048/020 first octet: TYP(3) SIM RDP SPI RAB FX. TYP 011 = SSR + PSR.
    typ = 0b011
    i020 = bytes([(typ << 5) | (0x10 if simulated else 0)])
    rho = int(round(rho_nm * 256)) & 0xFFFF
    theta = int(round((theta_deg % 360.0) / 360.0 * 65536)) & 0xFFFF
    i040 = struct.pack(">HH", rho, theta)
    code = int(str(mode3a_octal), 8) & 0x0FFF           # V=0 G=0 L=0
    i070 = struct.pack(">H", code)
    i090 = struct.pack(">H", (int(round(fl * 4)) & 0x3FFF))  # V=0 G=0, 1/4 FL
    i220 = (address & 0xFFFFFF).to_bytes(3, "big")
    i161 = struct.pack(">H", track_no & 0x0FFF)
    gs = int(round(gs_kt / 3600.0 * 16384)) & 0xFFFF      # 2^-14 NM/s
    hdg = int(round((heading_deg % 360.0) / 360.0 * 65536)) & 0xFFFF
    i200 = struct.pack(">HH", gs, hdg)
    return _fspec(frns) + i010 + i140 + i020 + i040 + i070 + i090 + i220 + i161 + i200


def _extensible(buf, off):
    start = off
    while True:
        octet = buf[off]
        off += 1
        if not octet & 0x01:
            return buf[start:off], off


def _consume(buf, off, item, kind, fixed):
    if kind == "F":
        return buf[off:off + fixed], off + fixed
    if kind == "X":
        return _extensible(buf, off)
    if kind == "R":
        rep = buf[off]
        return buf[off:off + 1 + rep * fixed], off + 1 + rep * fixed
    raise NotDecoded(f"{item} present: compound item not implemented by this adapter")


def decode_048_record(buf, off):
    """Decode one CAT 048 record starting at off. Returns (fields, new_off)."""
    frns, off = _parse_fspec(buf, off)
    f = {}
    for frn in frns:
        if frn not in UAP_048:
            raise NotDecoded(f"FRN {frn} outside the CAT 048 UAP")
        item, kind, fixed = UAP_048[frn]
        raw, off = _consume(buf, off, item, kind, fixed)
        if item not in DECODED_048:
            raise NotDecoded(f"{item} present: not implemented by this adapter")
        if item == "I048/010":
            f["sac"], f["sic"] = raw[0], raw[1]
        elif item == "I048/140":
            f["tod_s"] = int.from_bytes(raw, "big") / 128.0
        elif item == "I048/020":
            f["typ"] = raw[0] >> 5
            f["simulated"] = bool(raw[0] & 0x10)
            f["test_target"] = bool(raw[0] & 0x08)
            f["spi"] = bool(raw[0] & 0x04)
        elif item == "I048/040":
            rho, theta = struct.unpack(">HH", raw)
            f["rho_nm"] = rho / 256.0
            f["theta_deg"] = theta * 360.0 / 65536
        elif item == "I048/070":
            (v,) = struct.unpack(">H", raw)
            f["mode3a_valid"] = not bool(v & 0x8000)
            f["mode3a"] = format(v & 0x0FFF, "04o")
        elif item == "I048/090":
            (v,) = struct.unpack(">H", raw)
            fl = v & 0x3FFF
            if fl & 0x2000:
                fl -= 0x4000
            f["fl_valid"] = not bool(v & 0x8000)
            f["fl"] = fl / 4.0
        elif item == "I048/220":
            f["address"] = format(int.from_bytes(raw, "big"), "06X")
        elif item == "I048/161":
            f["track_no"] = struct.unpack(">H", raw)[0] & 0x0FFF
        elif item == "I048/200":
            gs, hdg = struct.unpack(">HH", raw)
            f["gs_kt"] = gs / 16384.0 * 3600.0
            f["heading_deg"] = hdg * 360.0 / 65536
    return f, off


# ---------------------------------------------------------------------------
# CAT 034 — radar service messages (north marker / sector crossing)
# ---------------------------------------------------------------------------
def encode_034_north_marker(sac, sic, tod_s):
    i010 = bytes([sac & 0xFF, sic & 0xFF])
    i000 = bytes([1])                                # 1 = North marker
    i030 = (int(round(tod_s * 128)) & 0xFFFFFF).to_bytes(3, "big")
    return _fspec([1, 2, 3]) + i010 + i000 + i030


def decode_034_record(buf, off):
    frns, off = _parse_fspec(buf, off)
    f = {}
    for frn in frns:
        if frn not in UAP_034:
            raise NotDecoded(f"FRN {frn} outside the CAT 034 UAP")
        item, kind, fixed = UAP_034[frn]
        raw, off = _consume(buf, off, item, kind, fixed)
        if item not in DECODED_034:
            raise NotDecoded(f"{item} present: not implemented by this adapter")
        if item == "I034/010":
            f["sac"], f["sic"] = raw[0], raw[1]
        elif item == "I034/000":
            f["message_type"] = {1: "north-marker", 2: "sector-crossing"}.get(raw[0], str(raw[0]))
        elif item == "I034/030":
            f["tod_s"] = int.from_bytes(raw, "big") / 128.0
    return f, off


# ---------------------------------------------------------------------------
# Whole frames
# ---------------------------------------------------------------------------
def decode_frame(payload):
    """Decode every record in every block. Returns a list of
    {"cat": n, "fields": {...}}. Raises NotDecoded on an unimplemented item;
    the caller then carries the frame untouched instead of guessing."""
    out, off, n = [], 0, len(payload)
    while off < n:
        cat = payload[off]
        ln = int.from_bytes(payload[off + 1:off + 3], "big")
        end = off + ln
        p = off + 3
        while p < end:
            if cat == 48:
                fields, p = decode_048_record(payload, p)
            elif cat == 34:
                fields, p = decode_034_record(payload, p)
            else:
                raise NotDecoded(f"category {cat}: not implemented by this adapter")
            out.append({"cat": cat, "fields": fields})
        off = end
    return out


def polar_to_latlon(lat0_deg, lon0_deg, rho_nm, theta_deg):
    """Flat-earth projection of a polar plot around the sensor. Good to a
    few metres at radar ranges; not for anything that needs geodesy."""
    d_m = rho_nm * 1852.0
    th = math.radians(theta_deg)
    dn, de = d_m * math.cos(th), d_m * math.sin(th)
    lat = lat0_deg + math.degrees(dn / 6371000.0)
    lon = lon0_deg + math.degrees(de / (6371000.0 * math.cos(math.radians(lat0_deg))))
    return lat, lon
