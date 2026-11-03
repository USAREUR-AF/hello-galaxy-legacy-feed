# Rung 2 — decode

**Typed records produced from the bytes, published to a stored key.** For a
feed a map or a fusion tool must read. Only this rung writes to storage, so
only this rung the decode-health guard can grade.

## The contract

Decode what the consumer reads. Refuse the rest **by name**. The adapter here
implements I048/010, 140, 020, 040, 070, 090, 220, 161 and 200, which is enough
for a map: sensor id, time, report descriptor (including the SIM bit), polar
position, Mode 3/A, flight level, aircraft address, track number, velocity. A
record carrying any other item raises `NotDecoded("I048/130 present: …")` and
is counted; nothing is guessed. CAT 034 north markers are recognised and not
forced into tracks.

Output is goat's `GeoTrackV1` (`schemas/goat.geo.track.v1.schema.json`,
vendored from goat), the shape goat's map draws without
further lookup. Every record is validated against the schema before it is
published. `synthetic` is `true` unconditionally here: this adapter has no
registry to read it from, and in goat the flag comes from the producer org's
registry row, never from the payload.

## Key shape

```
<anchor>/<system>/geo/track/asterix048/<sac>-<sic>-<track_no>
```

Per-entity keys are right while concurrent tracks stay in the low hundreds. A
radar whose track numbers churn publishes one key per stream with the track set
in the payload instead.

## What the demo shows

Offline: five datagrams decoded, every plot validated, the north marker
recognised, one record printed the way a map receives it. With `--publish`:
each record is put with `--confirm` (read back from storage) and one is read
back with `goat sub --since`.

```bash
bin/hello-feed 2-decode                       # offline
bin/hello-feed 2-decode --publish --env <context>  # needs a goatnet; stored under your anchor
```

Register the key with format `json` (or upload a schema) so the hourly
decode-health guard grades it `OK` / `UNDECODABLE` / `STALE` from then on.
