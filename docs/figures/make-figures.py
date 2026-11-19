#!/usr/bin/env python3
"""Draw this repository's figures.

    python3 -I docs/figures/make-figures.py           # write docs/figures/*.svg
    python3 -I docs/figures/make-figures.py --check   # exit 1 if a committed figure is out of date

Each figure is written twice, `<name>-light.svg` and `<name>-dark.svg`, for a
`<picture>` element. Every name in a figure is the repository's own: its
README, its rung READMEs and its tools. Standard library only.
"""
# --- Hello Galaxy figure kit: identical in every hello-galaxy-* repo's make-figures.py ---------------
# Standard library only. Text is measured with Helvetica's advance widths (Arial and Liberation Sans
# share them), so every label is placed, wrapped and checked before it is written. The colours are the
# series' tokens; a figure uses classes only, so its light and dark files differ only in the tokens.
import os
import sys
from xml.sax.saxutils import escape

W = 880  # canvas width; text is never under 13 units on it
FONT = "'Helvetica Neue', Helvetica, Arial, 'Liberation Sans', sans-serif"
MONO = "Menlo, Consolas, 'Liberation Mono', 'Courier New', monospace"
TOKENS = {
    "light": dict(ink="#191c22", quiet="#555c68", rule="#dde1e6", line="#878f9c", paper="#ffffff",
                  panel="#f5f6f8", accent="#0b5a72", accent_soft="#e2f0f4", on_accent="#ffffff",
                  good="#2a6a35", good_bg="#e4f3e6", warn="#875200", warn_bg="#fcf0d7",
                  info="#285d9e", info_bg="#e6eff9", crit="#b0261d", crit_bg="#fbeae8"),
    "dark": dict(ink="#e7e9ec", quiet="#a5acb7", rule="#30363e", line="#7b8592", paper="#121417",
                 panel="#1a1d21", accent="#6cc3da", accent_soft="#14303a", on_accent="#121417",
                 good="#6fc480", good_bg="#1b2e20", warn="#e2b04e", warn_bg="#32291a",
                 info="#86b3ea", info_bg="#1a2636", crit="#f08b80", crit_bg="#3a1f1f"),
}
CSS = """
.t{fill:var(--ink)} .tq{fill:var(--quiet)} .ta{fill:var(--accent)} .tg{fill:var(--good)}
.tw{fill:var(--warn)} .ti{fill:var(--info)} .tc{fill:var(--crit)} .ton{fill:var(--on-accent)}
.bx{fill:var(--panel);stroke:var(--line);stroke-width:1.25} .bxa{fill:var(--accent-soft);stroke:var(--accent);stroke-width:1.5}
.bxg{fill:var(--good-bg);stroke:var(--good);stroke-width:1.25} .bxc{fill:var(--crit-bg);stroke:var(--crit);stroke-width:1.25}
.bxw{fill:var(--warn-bg);stroke:var(--warn);stroke-width:1.25} .bxi{fill:var(--info-bg);stroke:var(--info);stroke-width:1.25}
.zone{fill:none;stroke:var(--line);stroke-width:1.25;stroke-dasharray:6 5}
.ln{stroke:var(--line);stroke-width:1.5;fill:none} .lna{stroke:var(--accent);stroke-width:2.25;fill:none}
.lng{stroke:var(--good);stroke-width:2;fill:none} .lnc{stroke:var(--crit);stroke-width:2;fill:none;stroke-dasharray:4 4}
.lni{stroke:var(--info);stroke-width:2;fill:none} .lnr{stroke:var(--rule);stroke-width:1;fill:none}
.fa{fill:var(--accent)} .fl{fill:var(--line)} .fg{fill:var(--good)} .fc{fill:var(--crit)} .fi{fill:var(--info)}
.halo{paint-order:stroke fill;stroke:var(--paper);stroke-width:5px;stroke-linejoin:round}
"""
_REG = [278, 278, 426, 556, 556, 1000, 667, 278, 333, 333, 389, 600, 278, 389, 278, 333, 556, 556, 556, 556,
        556, 556, 556, 556, 556, 556, 278, 278, 600, 600, 600, 556, 1015, 667, 685, 722, 722, 667, 611, 778,
        722, 278, 519, 667, 556, 871, 722, 778, 667, 778, 722, 667, 611, 722, 667, 944, 667, 667, 611, 278,
        333, 278, 600, 556, 333, 556, 593, 537, 593, 556, 296, 574, 556, 222, 222, 519, 222, 853, 556, 574,
        593, 593, 333, 500, 315, 556, 500, 758, 518, 500, 500, 334, 260, 334, 600]
_BOLD = [278, 333, 474, 556, 556, 1000, 722, 278, 333, 333, 407, 600, 278, 407, 278, 371, 556, 556, 556, 556,
         556, 556, 556, 556, 556, 556, 333, 333, 600, 600, 600, 611, 975, 722, 722, 741, 741, 667, 611, 778,
         741, 295, 556, 722, 611, 907, 741, 778, 667, 778, 722, 667, 611, 741, 667, 944, 667, 667, 648, 333,
         371, 333, 600, 556, 333, 574, 611, 574, 611, 574, 333, 611, 611, 278, 278, 574, 278, 906, 611, 611,
         611, 611, 389, 556, 352, 611, 556, 814, 556, 556, 519, 389, 280, 389, 600]
_WIDE = {"→": 1000, "—": 1000, "–": 556, "’": 278, "·": 278, "✓": 800, "✕": 800}


def tw(s, size, bold=False, mono=False):
    """Advance width of s at size, with a 4 % margin for hinting differences."""
    if mono:
        return len(s) * size * 0.602 * 1.02
    table = _BOLD if bold else _REG
    u = sum(table[ord(c) - 32] if 32 <= ord(c) < 127 else _WIDE.get(c, 1000) for c in s)
    return u * size / 1000 * 1.04


def wrap(s, width, size, bold=False, mono=False):
    out, line = [], ""
    for word in s.split(" "):
        t = word if not line else line + " " + word
        if not line or tw(t, size, bold, mono) <= width:
            line = t
        else:
            out.append(line)
            line = word
    out.append(line)
    for ln in out:
        if tw(ln, size, bold, mono) > width:
            raise SystemExit("label does not fit %d units: %r" % (width, ln))
    return out


def _n(v):
    return ("%.1f" % v).rstrip("0").rstrip(".")


class Fig:
    def __init__(self, title, alt, subtitle=None):
        self.title, self.alt, self.items, self.boxes = title, alt, [], []
        self.texts, self._owner = [], None
        self.text(24, 38, title, 20, "t", bold=True, note=True)
        self.y = 50
        if subtitle:
            for i, ln in enumerate(wrap(subtitle, W - 48, 15)):
                self.text(24, 66 + i * 21, ln, 15, "tq", note=True)
                self.y = 72 + i * 21

    # primitives ---------------------------------------------------------------------------------------
    def add(self, s):
        self.items.append(s)

    def text(self, x, y, s, size=14, cls="t", anchor="start", bold=False, mono=False, halo=False, note=False):
        if size < 13:
            raise SystemExit("text under 13 units: %r" % s)
        w = tw(s, size, bold, mono)
        x0 = x - (w if anchor == "end" else w / 2 if anchor == "middle" else 0)
        if x0 < 4 or x0 + w > W - 4:
            raise SystemExit("text off the canvas: %r (%.0f..%.0f)" % (s, x0, x0 + w))
        self.texts.append((x0, y - size * 0.75, x0 + w, y + size * 0.22, self._owner, s))
        a = ' text-anchor="%s"' % anchor if anchor != "start" else ""
        b = ' font-weight="700"' if bold else ""
        m = ' font-family="%s"' % MONO if mono else ""
        c = cls + (" halo" if halo else "")
        r = ' data-role="note"' if note else ""  # a sentence, not a label
        self.add('<text x="%s" y="%s" class="%s" font-size="%s"%s%s%s%s>%s</text>'
                 % (_n(x), _n(y), c, _n(size), a, b, m, r, escape(s)))
        return w

    def rect(self, x, y, w, h, cls="bx", rx=8):
        self.add('<rect x="%s" y="%s" width="%s" height="%s" rx="%s" class="%s"/>'
                 % (_n(x), _n(y), _n(w), _n(h), _n(rx), cls))

    def zone(self, x, y, w, h, label=None, cls="tq"):
        self.rect(x, y, w, h, "zone", 12)
        if label:
            self.text(x + 14, y + 22, label, 14, cls, bold=True)

    def arrow(self, pts, cls="ln", head=True, both=False):
        d = "M" + "L".join("%s %s" % (_n(a), _n(b)) for a, b in pts)
        self.add('<path d="%s" class="%s"/>' % (d, cls))
        fill = {"ln": "fl", "lna": "fa", "lng": "fg", "lnc": "fc", "lni": "fi"}.get(cls, "fl")
        ends = ([(pts[-2], pts[-1])] if head else []) + ([(pts[1], pts[0])] if both else [])
        for (x1, y1), (x2, y2) in ends:
            dx, dy = x2 - x1, y2 - y1
            ln = (dx * dx + dy * dy) ** 0.5
            ux, uy = dx / ln, dy / ln
            bx, by = x2 - ux * 10, y2 - uy * 10
            self.add('<path d="M%s %sL%s %sL%s %sz" class="%s"/>'
                     % (_n(x2), _n(y2), _n(bx - uy * 5), _n(by + ux * 5), _n(bx + uy * 5), _n(by - ux * 5), fill))

    def badge(self, x, y, label):
        """A step number: the series' signature. x, y = centre."""
        w = max(30, tw(label, 13, True) + 16)
        self.rect(x - w / 2, y - 15, w, 30, "fa", 15)
        keep, self._owner = self._owner, -1  # a badge may sit on a box's corner
        self.text(x, y + 4.6, label, 13, "ton", "middle", bold=True)
        self._owner = keep
        return w

    def badge_line(self, x, y, label, s, size=14, cls="t"):
        """A badge followed by one line of text; y = the badge's centre."""
        w = self.badge(x + max(30, tw(label, 13, True) + 16) / 2, y, label)
        self.text(x + w + 10, y + 5, s, size, cls, note=len(s.split()) > 10)
        return x + w + 10

    def chip(self, x, y, s, cls="bx", tcls="t", mono=False, size=13, bold=False):
        w = tw(s, size, bold, mono) + 16
        self.rect(x, y, w, 30, cls, 6)
        self.boxes.append((x, y, w, 30))
        self._owner = len(self.boxes) - 1
        self.text(x + 8, y + 19.5, s, size, tcls, mono=mono, bold=bold)
        self._owner = None
        return w

    def chips(self, x, y, right, items, gap=8):
        """Flow (text, box class, text class) chips from x to right; returns the y below the last row."""
        cx = x
        for s, cls, tcls in items:
            w = tw(s, 13) + 16
            if cx + w > right:
                cx, y = x, y + 38
            cx += self.chip(cx, y, s, cls, tcls) + gap
        return y + 30

    def card(self, x, y, w, title, lines=(), cls="bx", tcls="t", mono_lines=False, size=14, pad=12,
             measure=False, min_h=0, badge=None):
        """A box with a bold title and wrapped lines, the title led by an optional step badge.
        Returns its height (only that, with measure=True)."""
        bw = max(30, tw(badge, 13, True) + 16) + 8 if badge else 0
        rows = [(ln, size + 1, True, False, tcls, 0, bw) for ln in wrap(title, w - 2 * pad - bw, size + 1, bold=True)]
        for k, item in enumerate(lines):
            mono = mono_lines or (isinstance(item, tuple) and item[1] == "mono")
            s = item[0] if isinstance(item, tuple) else item
            sz = size if not mono else 13
            for i, ln in enumerate(l for part in s.split("\n") for l in wrap(part, w - 2 * pad, sz, mono=mono)):
                rows.append((ln, sz, False, mono, "tq", 5 if i == 0 and k > 0 else 0, 0))
        if badge:
            rows[0] = rows[0][:5] + (7, bw)  # room for the badge's height, above and below the title
            if len(rows) > 1:
                rows[1] = rows[1][:5] + (rows[1][5] + 7, rows[1][6])
        h = pad + sum(r[1] * 1.38 + r[5] for r in rows) + pad - 4
        if measure:
            return h
        h = max(h, min_h)
        self.rect(x, y, w, h, cls)
        self.boxes.append((x, y, w, h))
        me = len(self.boxes) - 1
        cy = y + pad
        for n, (s, sz, b, m, c, gap, off) in enumerate(rows):
            cy += sz * 1.38 + gap
            if n == 0 and badge:
                self._owner = -1
                self.badge(x + pad + (bw - 8) / 2, cy - sz * 0.38 - sz * 0.36, badge)
            self._owner = me
            self.text(x + pad + off, cy - sz * 0.38, s, sz, c, bold=b, mono=m)
        self._owner = None
        return h

    # output -------------------------------------------------------------------------------------------
    def lint(self, height):
        """Refuse a label that runs into another label or into a box it is not part of."""
        bad = []
        for i, (a0, b0, a1, b1, own, s) in enumerate(self.texts):
            if b1 > height - 2:
                bad.append("below the canvas: %r" % s)
            for j, (x, y, w, h) in enumerate(self.boxes):
                if own != j and a0 < x + w and a1 > x and b0 < y + h and b1 > y and own != -1:
                    bad.append("text %r runs into box %d" % (s, j))
            for (c0, d0, c1, d1, _, t) in self.texts[i + 1:]:
                if a0 < c1 and a1 > c0 and b0 < d1 and b1 > d0:
                    bad.append("text %r overlaps %r" % (s, t))
        if bad:
            raise SystemExit("figure %r:\n  " % self.title + "\n  ".join(bad))

    def svg(self, theme, height):
        self.lint(height)
        t = TOKENS[theme]
        var = " ".join("--%s:%s;" % (k.replace("_", "-"), v) for k, v in t.items())
        return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %d %s" width="%d" height="%s" role="img" '
                'aria-label="%s"><title>%s</title><style>svg{%s font-family:%s}%s</style>\n%s\n</svg>\n'
                % (W, _n(height), W, _n(height), escape(self.alt, {'"': "&quot;"}), escape(self.title),
                   var, FONT, CSS.strip(), "\n".join(self.items)))


def write_all(figs, here):
    """figs: {name: (Fig, height)}. Writes <name>-light.svg and <name>-dark.svg; --check compares."""
    check = "--check" in sys.argv[1:]
    stale = []
    for name, (fig, height) in figs.items():
        for theme in ("light", "dark"):
            path = os.path.join(here, "%s-%s.svg" % (name, theme))
            body = fig.svg(theme, height)
            if check:
                try:
                    with open(path, encoding="utf-8") as fh:
                        if fh.read() != body:
                            stale.append(path)
                except FileNotFoundError:
                    stale.append(path)
            else:
                with open(path, "w", encoding="utf-8") as fh:
                    fh.write(body)
                print("wrote", os.path.relpath(path, os.path.join(here, "..", "..")))
    if stale:
        print("out of date, run python3 -I docs/figures/make-figures.py:\n  " + "\n  ".join(stale))
        sys.exit(1)
# --- end of the Hello Galaxy figure kit -------------------------------------------------------------------


# Figure for hello-galaxy-legacy-feed. Facts: README.md "The three rungs", rungs/*/README.md.
def figures():
    f = Fig("One radar feed, three ways onto a goatnet", "", subtitle=
            "A synthetic radar sends ASTERIX CAT 034/048 over UDP. Each rung moves the feed further and "
            "carries the check that belongs to it.")
    f.alt = ("A synthetic radar's ASTERIX CAT 034/048 feed goes onto a goatnet three ways: rung 0 carries the "
             "datagrams unchanged to one peer with a framing lint and digest log; rung 1 mirrors the same bytes "
             "on a volatile stream key with a SHA-256 digest per frame, so any authorized subscriber or a UDP "
             "relay can take them; rung 2 decodes them into GeoTrackV1 records on a stored key for goat's map, "
             "refusing items it does not implement by name.")
    lanes = [
        ("0", "carry", "Datagrams, unchanged, peer to peer",
         ["offline on loopback, or between two real peers"],
         "One receiver", ["no one else on the goatnet sees the feed"],
         "framing lint and a digest log beside the receiver"),
        ("1", "mirror", "Same bytes, untouched, on a stream key",
         [("volatile/<anchor>/stream/.../raw/v1", "mono"), "a SHA-256 digest per frame on a sibling key"],
         "Any authorized subscriber", ["a relay feeds UDP to a receiver behind a data diode"],
         "lint before every put; a refused frame is dropped, never published, and leaves a gap"),
        ("2", "decode", "GeoTrackV1 records on a stored key",
         [("<anchor>/<system>/geo/track/...", "mono"), "nine items decoded, others refused by name"],
         "goat's map draws them", ["the record validates against the GeoTrackV1 schema"],
         "JSON-schema validation, and a read-back with --confirm"),
    ]
    x1, w1, x2, w2 = 244, 346, 622, 234
    y = f.y + 26
    mids = []
    for num, name, what, lines, who, wlines, check in lanes:
        f.badge(x1 + 13, y + 2, num)
        f.text(x1 + 34, y + 7, "Rung %s, %s" % (num, name), 15, "t", bold=True)
        top = y + 22
        h1 = f.card(x1, top, w1, what, lines, "bxa")
        h2 = f.card(x2, top, w2, who, wlines)
        h = max(h1, h2)
        f.arrow([(x1 + w1 + 2, top + 26), (x2 - 2, top + 26)], "lna")
        f.text(x1 + 2, top + h + 22, "✓ Check: " + check, 14, "tg", note=True)
        mids.append(top + 26)
        y = top + h + 52
    height = y - 14
    # the source, fanned to the three rungs
    sy = (mids[0] + mids[-1]) / 2
    src = ("Synthetic radar", ["ASTERIX CAT 034/048", "over UDP", "SIM bit on every plot"])
    sh = f.card(24, 0, 184, *src, measure=True)
    f.card(24, sy - sh / 2, 184, *src)
    trunk = 222
    f.arrow([(208, sy), (trunk, sy)], "ln", head=False)
    f.arrow([(trunk, mids[0]), (trunk, mids[-1])], "ln", head=False)
    for m in mids:
        f.arrow([(trunk, m), (x1 - 2, m)], "ln")
    return {"three-rungs": (f, height)}


if __name__ == "__main__":
    write_all(figures(), os.path.dirname(os.path.abspath(__file__)))
