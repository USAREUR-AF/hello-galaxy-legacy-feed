# ASTERIX framing, and what the lint checks

An ASTERIX **data block** is:

```
octet 0      CAT    category (34 = radar service messages, 48 = monoradar target reports, 62 = system tracks …)
octets 1-2   LEN    big-endian, the whole block INCLUDING these three header octets
octets 3..   one or more records, each starting with an FSPEC
```

A UDP datagram carries one or more blocks laid end to end.

## The lint (lib/asterixlint.py; the same walk as goat's guard)

Walk from offset 0: read CAT and LEN, require LEN ≥ 3 and `offset + LEN ≤ total`,
advance by LEN. At the end require offset == total. Optionally require every CAT
to be in a declared set.

| Payload | Verdict | Why |
|---|---|---|
| complete blocks | ok | framing holds |
| last block cut short | refused | LEN promises bytes that are not there |
| extra bytes after the last block | refused | a partial header follows a complete block |
| LEN < 3 | refused | a block cannot be shorter than its own header |
| a block of a category the feed did not declare | refused | the feed said `asterix:034,048` |
| base64 **text** of a valid frame | refused | text is not framing; goat's guard then reports DOUBLE-ENCODED |
| JSON text | refused | same |

## What the lint does not check

Anything inside a record. A block whose FSPEC or items are nonsense still
frames. That is deliberate: the lint runs per frame at wire rate with no spec
knowledge, in any language, in three lines. Item-level decoding is rung 2's job
and refuses what it does not implement.

## The format string goat accepts

| Format | Accepts |
|---|---|
| `asterix` | any complete blocks |
| `asterix:048` | complete blocks, all CAT 048 |
| `asterix:034,048` | complete blocks, each in the set (`cat048` also reads as 48) |

Registered on a **stored** topic, `ops/ci/check-topic-decode-health.py` grades
it `OK`, `UNDECODABLE`, `DOUBLE-ENCODED`, `STALE` or `NO-SAMPLE`. On a
`volatile/` key there is no storage to read, so the guard reports `NO-SAMPLE`
and the lint at the tap is the check.
