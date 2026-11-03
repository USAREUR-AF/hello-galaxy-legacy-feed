# Doing it for real on a goatnet

Every step on this page needs a goatnet and enrolled peers on it.

## Rung 0

1. Enroll both the sensor's peer and the receiver. The sensor sends to the
   receiver's mesh address (`100.64.x.y`).
2. Check the ACL from the goatnet's declaration, no credentials needed:
   `goat warrant why-blocked --scope <goatnet> --from <sensor-group> --to <receiver-group> --port <udp-port> --proto udp`.
   If it is a gap, the command prints the smallest port-set and the PR diff.
3. Prove arrival on the receiver: `sudo tcpdump -ni any udp port <udp-port> -c 5`.
4. Optional: run `tools/asterix-recv.py` beside the real receiver for a lint +
   digest log.

## Rung 1, receiving a feed that is already on the fabric

1. Collect your fabric credential from the console (shown once); `goat context ls`
   shows the context it landed in. `goat pub` and `goat sub` once, on a key under
   your own anchor, to prove the credential works.
2. Find the feed: `goat topic ls` (or the portal catalog). Note its key and its
   declared format (`asterix:034,048`).
3. Watch it: `goat sub <key> --follow --uuid`. Frames print as `<key> hex:<bytes>`.
4. Hand it to your receiver: `tools/asterix-relay.py --env <goatnet> --key <key>
   --to <receiver-ip>:<udp-port> --format asterix:034,048`. Run it on the peer
   that can reach the receiver. Prove arrival with
   `sudo tcpdump -ni any udp port <udp-port> -c 5` on the receiver.
5. Your receiver, the diode and the C2 system see the sensor's bytes unchanged.

## Rung 1, publishing a feed

1. Collect your fabric credential from the console (shown once); `goat context ls`
   shows the context it landed in.
2. Choose `<system>` and `<site>` labels. Run the tap on the peer that receives
   the sensor's datagrams (or on the receiver itself, forwarding a copy).
3. Replace the demo tap with a native publisher for a real feed: one zenoh
   session, one declared publisher per key, digest in the attachment, the same
   lint before every put, the same drop-on-refuse rule.
4. Register the raw key with format `asterix:<cats>` if it should appear in the
   portal catalog. Registration is discovery, not grading, for a volatile key.

## Rung 2

1. Decide the items your consumer reads. Implement those; refuse the rest by name.
2. Publish `GeoTrackV1` (or another published schema) to a stored key under your
   anchor; `goat pub --confirm` reads it back.
3. Register the key with its format (`json`, or upload the schema). The hourly
   decode-health guard then grades it.
4. Keep the per-entity key count bounded; a churning radar goes to one key per
   stream with the track set in the payload.

## Who to ask

Your goatnet's operators. Send the two mesh addresses, the UDP port and the
goatnet; the ACL question is answered from the declaration.
