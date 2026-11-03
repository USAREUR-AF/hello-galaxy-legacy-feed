# A digest across a data diode

A data diode passes bytes one way and nothing back. No acknowledgement, no
retransmit request, no "did you get frame 5". The only integrity check that
works across it is one both sides can compute independently and compare later.

## The record each side keeps

One line per datagram, written by `tools/asterix-recv.py` (rung 0) or published
by `tools/asterix-tap.py` (rung 1):

```json
{"seq": 5, "cats": [48], "len": 78, "sha256": "…", "ok": true, "detail": "", "received_at": "2026-01-01T00:00:05Z"}
```

`seq` counts datagrams as they **arrive** at that side. A frame the lint refuses
keeps its number and is marked `ok: false`; at rung 1 it is dropped before
publishing, so the digest stream shows a gap there.

## Comparing

Export the near-side and far-side logs, join on `sha256`:

- a digest on both sides: carried intact;
- a near-side digest with no far-side match: lost or altered in the diode's
  path (compare `len` to tell which);
- a far-side digest with no near-side match: the far side received something the
  near side never sent, or the near-side log is incomplete.

Sequence gaps on the near side that are marked refused are the sensor's
problem, not the path's.

## What this proves and does not

That the bytes the far side holds are the bytes the near side logged. Not that
the sensor produced them, not that they were delivered to anyone else, and not
anything about timing. The comparison is offline and after the fact, because
the diode allows nothing else.
