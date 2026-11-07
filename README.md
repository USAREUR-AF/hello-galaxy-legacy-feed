# hello-galaxy: legacy feed carriage

**A sensor that speaks a legacy wire format (here ASTERIX CAT 034/048) arrives on
a goatnet. What do you need to do with it? Three rungs, each one runnable, each
with the integrity check that belongs to it, shown against the real `goat` CLI.**

This is a repo in the **Hello Galaxy** series: small, self-contained, runnable
examples of best practice in one dimension. Like the rest of the series, it is
a short runbook per rung plus one driver script that narrates what happens.
The sensor is synthetic (every plot carries the ASTERIX SIM bit); everything
else runs for real. Where something is a deployment property rather than a
publisher's choice, the docs say so.

---

## The question this repo answers

A radar on a goatnet emits ASTERIX over UDP. A partner's receiver must take that
feed and forward it through a data diode into a C2 system. The partner holds a
fabric credential and asks: **do we need any of this?**

Yes. The feed is on the data fabric so that every authorized participant can
receive it; the partner is one of those participants, and `goat sub` plus the
relay in this repo is how a UDP-only receiver gets the bytes. The three rungs
are the three things a feed can be on a goatnet: carried between two peers and
seen by nobody else, mirrored untouched so others can receive it, or decoded so
a map can draw it.

Read [`docs/00-which-rung.md`](docs/00-which-rung.md) first. It is the whole
decision in one page.

## The three rungs

| Rung | What moves | Runs | Checks demonstrated |
|---|---|---|---|
| [**0 carry**](rungs/0-carry/) | the sensor's datagrams, unchanged, peer to peer | offline (loopback) or two real peers | framing lint + digest log beside the receiver; ACL question; packet capture |
| [**1 mirror**](rungs/1-mirror/) | the same bytes, untouched, on a `volatile/` stream key; a SHA-256 digest per frame on a sibling key | **live** against a fabric, under your own anchor | lint before every put (refused frames dropped, never published); subscriber recomputes digests; gap = refused frame |
| [**2 decode**](rungs/2-decode/) | typed `GeoTrackV1` records on a stored key | offline, or `--publish` live | decode what the consumer needs, refuse the rest by name; JSON-schema validation; `--confirm` read-back |

## Run it

```bash
# prerequisites: python3 (jsonschema optional but used when present)
pip install -r requirements.txt

bin/hello-feed 0-carry                  # offline, ~5 s
bin/hello-feed 2-decode                 # offline, ~10 s
```

Rungs 0 and 2 run on a laptop with no goatnet; CI runs exactly these. Rung 1 and
`2-decode --publish` need a goatnet: the `goat` CLI (built from
[`usareur-af/goatcore`](https://github.com/usareur-af/goatcore)) with a fabric
credential collected into a context (`goat context ls`). Any appropriate goatnet you
have access to works:
EFDI, the shared sandbox goatnet that partners are onboarded to (if you are onboarded to it); <!-- oss-allow: operator-approved public example goatnet -->
a goatlite you stand up yourself on one box (goatcore's quickstart
[`docs/tutorials/00-goatlite.md`](https://github.com/usareur-af/goatcore/blob/main/docs/tutorials/00-goatlite.md)); or another
goatnet you have access to.

```bash
bin/hello-feed 1-mirror --env <context>             # live, ~2 min (one goat pub per frame, on purpose slow)
bin/hello-feed 2-decode --publish --env <context>
```

Every live write lands under **your** anchor (`volatile/<anchor>/stream/**`,
`<anchor>/**`), which the slot ACL admits and nobody else's keys share.

## What is deliberately simplified, and what to copy

The demo tap spawns one `goat pub` per frame, so it tops out near one frame a
second. A production tap keeps one zenoh session with one declared publisher per
key and puts the digest in the sample **attachment**; the goat CLI has no
attachment flag, so here the digest rides a sibling key. **Copy the key shapes,
the lint, the drop-on-refuse rule and the digest; replace the per-frame process
with a native publisher.**

The CAT 048 decoder implements nine items (I048/010, 140, 020, 040, 070, 090,
220, 161, 200). A record carrying any other item is refused with the item's
name. That is the pattern, not a gap: an adapter decodes what its consumer
reads and carries everything else untouched at rung 1.

## Repo layout

```
bin/hello-feed            dispatcher
lib/hello-feed.sh         shared narration / assertion / process library
lib/asterixlint.py        block-framing lint + SHA-256 digest — the same walk goat's decode-health guard runs
lib/asterix048.py         small CAT 034/048 encoder + decoder; refuses unimplemented items by name
tools/asterix-synth.py    synthetic radar: CAT 034 north markers + CAT 048 plots over UDP (SIM=1 set)
tools/asterix-recv.py     rung 0 receiver: lint + digest log (JSONL)
tools/asterix-tap.py      rung 1: lint, publish bytes untouched, publish digest
tools/asterix-verify.py   rung 1: two subscriptions, recompute SHA-256, match, report gaps
tools/asterix-relay.py    rung 1 consumer: goat sub → lint → UDP to a receiver that only speaks UDP
tools/asterix-decode.py   rung 2: decode → GeoTrackV1 → validate → (publish --confirm)
schemas/                  goat.geo.track.v1.schema.json, the GeoTrackV1 display schema, vendored from goat
rungs/                    0-carry, 1-mirror, 2-decode: README + run.sh each
docs/                     00-which-rung, asterix-framing, digest-across-a-diode, do-it-for-real
tests/test_asterix.py     offline: codec round trip, lint vectors shared with goat's guard, refusal by name
FINDINGS.md               goat CLI behaviours a script driving it has to know
```

## How this maps to goat

Paths are in [`usareur-af/goatcore`](https://github.com/usareur-af/goatcore).

| Here | In goat |
|---|---|
| `lib/asterixlint.py` | `asterix_blocks` / `asterix_declared_cats` in `ops/ci/check-topic-decode-health.py` (the `asterix[:<cat>,…]` format grade) |
| rung 1 key shapes | `docs/design/zenoh-volatile-class.md`, `docs/design/pubsub-best-practices.md` §1b |
| rung 2 output | the GeoTrackV1 display schema (`schemas/` here), drawn by goat's map |
| why checks sit at the ends | `docs/design/zenoh-brokerless-consequences.md`: the fabric has no broker, and a denied publish is silent, so nothing in the middle can validate |

Part of the hello-galaxy family of runnable goat demos.

## Licence

`hello-galaxy-legacy-feed` was written by U.S. Federal government employees. In the U.S. it is not subject to copyright and is in the public domain; in countries where copyright is recognized, it is released under the [Apache License 2.0](LICENSE). See [INTENT.md](INTENT.md).
