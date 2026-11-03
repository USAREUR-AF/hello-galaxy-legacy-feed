#!/usr/bin/env bash
# Rung 0 — carry: the sensor's datagrams, unchanged, from one peer to another.
# Offline by default (loopback). --to <host:port> points the synthetic sensor at
# a real receiver instead; --listen <host:port> runs the receiver on a chosen
# address (for the real case run recv on the receiving peer and synth on the
# sending peer, in two terminals).
set -uo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)/lib/hello-feed.sh"
hf_parse_env "$@"; set -- "${HF_ARGS[@]}"
TO=""; COUNT=8
while [ "$#" -gt 0 ]; do case "$1" in --to) TO="$2"; shift 2;; --count) COUNT="$2"; shift 2;; *) shift;; esac; done

hf_banner "Rung 0 — carry" "ASTERIX CAT 034/048 over UDP between two peers. No fabric, no conversion, no storage."
hf_require_python || exit 1

hf_step "What the mesh does here, and what it does not"
hf_say "Two enrolled peers, one UDP flow. The mesh encrypts and routes it; nothing of ours"
hf_say "reads, converts or stores the datagrams. The receiver's onward path (a diode, a C2"
hf_say "system) is the receiver's."
hf_note "This is the right rung for a feed whose only consumer is its owner's receiver."

PORT="$(hf_free_port)"
LISTEN="127.0.0.1:$PORT"
[ -n "$TO" ] && LISTEN=""
LOG="$HF_RUN/0-recv.log"; DIG="$HF_RUN/0-digests.jsonl"; : >"$DIG"

if [ -z "$TO" ]; then
  hf_step "Start a receiver that lints the framing and logs a digest per datagram"
  hf_cmd "tools/asterix-recv.py --listen $LISTEN --count $COUNT --format asterix:034,048 --digest-log .run/0-digests.jsonl"
  hf_bg "$LOG" python3 "$HF_ROOT/tools/asterix-recv.py" --listen "$LISTEN" --count "$COUNT" --format asterix:034,048 --digest-log "$DIG" --timeout 20
  hf_wait_for "$LOG" "listening" 5 || { cat "$LOG"; exit 1; }
  TO="$LISTEN"
fi

hf_step "Run the synthetic sensor at it, with one deliberately truncated datagram"
hf_cmd "tools/asterix-synth.py --to $TO --count $COUNT --rate 4 --corrupt-every 5"
SYN="$(python3 "$HF_ROOT/tools/asterix-synth.py" --to "$TO" --count "$COUNT" --rate 4 --corrupt-every 5)"
printf '%s\n' "$SYN" | hf_show

if [ -n "$LISTEN" ]; then
  sleep 1
  hf_step "What the receiver saw"
  hf_show < "$LOG"
  hf_step "The digest log — one line per datagram, the artefact a diode's far side compares against"
  head -3 "$DIG" | hf_show; hf_note "… (.run/0-digests.jsonl)"

  hf_step "Verify"
  OUT="$(cat "$LOG")"
  hf_assert_contains "every well-formed datagram framed" "$OUT" "$((COUNT - COUNT / 5)) framed"
  hf_assert_contains "the truncated datagram was refused, by reason" "$OUT" "REFUSED: not ASTERIX block framing"
  hf_assert_contains "a CAT 034 north marker arrived" "$OUT" "cats=[34]"
  hf_assert_contains "CAT 048 plots arrived" "$OUT" "cats=[48]"
fi

hf_step "Doing this for real on a goatnet"
hf_say "1. Both peers enrolled; the sensor sends to the receiver's MESH address (100.64.x.y)."
hf_say "2. The mesh ACL admits the UDP port between the two peers' groups. Ask the declaration:"
hf_cmd "goat warrant why-blocked --scope <goatnet> --from <sensor-group> --to <receiver-group> --port <udp-port> --proto udp"
hf_say "3. Prove arrival on the receiver, not on a dashboard:"
hf_cmd "sudo tcpdump -ni any udp port <udp-port> -c 5"
hf_say "4. Optional: run tools/asterix-recv.py beside your real receiver to lint + log digests."
hf_done
