# Which rung?

Pick the lowest rung that serves the consumer. Each step up costs effort and
adds maintenance that attaches only to feeds somebody reads.

| If… | then | because |
|---|---|---|
| the only consumer is your own receiver, the sensor is yours, and nobody else on the goatnet should see the feed | **rung 0, carry** | the mesh already moves any IP traffic between two enrolled peers; nothing else is needed and nothing else is added. Nothing enters the fabric, so this is a private cable, not participation |
| you must **receive** a feed that is already on the fabric into software that only speaks UDP (an ASTERIX server, a diode, a C2 gateway) | **rung 1, consumer side** | `goat sub` on the registered key plus `tools/asterix-relay.py` hands the frames to your receiver untouched; the lint refuses a corrupt frame before it reaches you |
| other participants should be able to **see** the feed live, nobody has committed to decoding it | **rung 1, mirror** | bytes stay bytes; discovery, live inspection and a frame-level integrity record come for the price of a tap |
| a map, a fusion tool or another system must **read** the content | **rung 2, decode** | only typed records on a stored key can be retrieved, graded for readability and drawn |

Three rules hold at every rung:

1. **Checks live at the ends.** There is no broker to validate in. The
   publisher lints before it puts, the subscriber verifies what it holds, the
   guard grades what storage holds.
2. **One stable key per feed.** Varying things (frame number, time, track id)
   ride in the payload. A key per message grows the routing table without bound.
3. **Decode what you need, refuse what you do not implement.** Never guess at an
   item; carry it untouched at rung 1 instead.

A typical case is a consumer at rung 1: a radar already publishes ASTERIX
CAT 034/048 to a goatnet, and a partner's receiver must take that feed off the fabric
and forward it through a data diode into a C2 system. It needs a fabric
credential and the relay; it needs no conversion. Rung 0 would have been wrong
there: a sensor-to-receiver cable over the mesh puts nothing on the backbone,
and the point of the connection is that the backbone carries the feed.
