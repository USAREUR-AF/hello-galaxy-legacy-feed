# Rung 0 — carry

**The sensor's datagrams, unchanged, from one enrolled peer to another. No
fabric, no conversion, no storage.** This is the right rung for a feed whose
only consumer is its owner's own receiver.

## What the mesh does, and does not

Two peers, one UDP flow. The mesh encrypts and routes it. Nothing of ours reads,
converts or stores the datagrams. The receiver's onward path (a diode, a C2
system) is the receiver's.

## What can stop it

1. **Enrollment.** Both the sensor (or the device it sits behind) and the
   receiver are enrolled peers, and the sensor sends to the receiver's **mesh**
   address (`100.64.x.y`), not a LAN address.
2. **The mesh ACL.** The two peers' groups must have a rule admitting the UDP
   port. Ask the declaration before asking a person:
   `goat warrant why-blocked --scope <goatnet> --from <sensor-group> --to <receiver-group> --port <udp-port> --proto udp`
3. **The site network.** Peers that can only reach out on TCP 443 connect through
   relays rather than directly. It works; it is slower.

## Prove arrival

On the receiver, not on a dashboard:

```bash
sudo tcpdump -ni any udp port <udp-port> -c 5
```

## What the demo shows

A receiver on loopback lints every datagram's framing and writes a digest log
(one JSON line per datagram: seq, categories, length, SHA-256, verdict). The
synthetic sensor sends eight datagrams with one truncated on purpose; the
receiver frames seven and refuses one, by reason. The digest log is the
artefact two receivers on opposite sides of a data diode compare offline
([`docs/digest-across-a-diode.md`](../../docs/digest-across-a-diode.md)).

```bash
bin/hello-feed 0-carry                              # loopback
tools/asterix-recv.py --listen 0.0.0.0:30048 --count 100 --digest-log recv.jsonl   # on the receiving peer
tools/asterix-synth.py --to 100.64.x.y:30048 --count 100                           # on the sending peer
```
