# Rung 1 — mirror

**The same bytes, untouched, published to a routed-never-stored stream key,
with a SHA-256 digest per frame on a sibling key.** For a feed that other
participants on the goatnet should be able to see live, without anyone
committing to decode it.

## Key shapes

```
volatile/<anchor>/stream/<system>/<site>/raw/v1          the bytes
volatile/<anchor>/stream/<system>/<site>/raw-digest/v1   {"seq","cats","len","sha256"}
```

`volatile/` is excluded from router storage and the audit tail by construction,
and published with DROP congestion control, so a fast sensor never
back-pressures the tap and nothing fills a disk. `<anchor>` is your fabric
certificate's CN, so the ACL admits the write. **One key per feed.** The frame
counter rides in the digest payload, never in the key: a key per frame grows the
routing table without bound and slows the whole fabric.

## The lint, and the drop rule

Before every put the tap checks the datagram is one or more complete ASTERIX
data blocks (1-octet category, 2-octet length counting the 3-octet header, no
truncation, no trailing bytes) and, if a category list was declared, that every
block is in it. A frame that fails is **dropped and counted, never published**.
A consumer cannot tell corrupt bytes from real ones; an absent frame alarms.

The tap numbers datagrams as they arrive. A refused frame keeps its number and
gets no digest, so the digest stream shows a gap exactly where the lint fired.
The far side can tell "refused at the tap" from "lost in flight" without a
return path.

## What the demo shows

A verifier opens two subscriptions and recomputes SHA-256 over every frame it
receives. The tap lints and publishes. The synthetic sensor sends eight
datagrams, one truncated. Expected: 7 published, 1 dropped by lint, 7 received,
7 matched by digest, digest sequence gap at 5. Then a replay over the stream
key, to show nothing was retained (measured only when the credential may read
the audit tail; otherwise stated as unmeasured).

This rung needs a goatnet: pass the goat context that holds your fabric
credential.

```bash
bin/hello-feed 1-mirror --env <context>
```

## What this proves and does not

The bytes a subscriber holds are the bytes the tap published. Not that the
sensor produced them, and not that anything was delivered to anyone else.

## Consuming it into UDP-only software

`tools/asterix-relay.py --key <the raw key> --to <host>:<port>` subscribes and
re-emits every frame as a UDP datagram, unchanged, after the same lint the tap
ran. This is the shape of the first real case: a receiver (an ASTERIX server
feeding a data diode and a C2 system) that cannot speak zenoh itself. Tested
offline in `tests/test_asterix.py` (two frames forwarded byte-identical, a
truncated one refused); not yet measured against a live feed.

## Register it (optional)

If the feed should appear in the portal catalog, register the raw key with
format `asterix:034,048`. The decode-health guard reads **storage**, so a
volatile key grades `NO-SAMPLE`; the lint here and the verifier on the consumer
are the checks for this rung. Registration is for discovery, not grading.
