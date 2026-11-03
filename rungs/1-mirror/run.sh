#!/usr/bin/env bash
# Rung 1 — mirror: the same bytes, untouched, on a routed-never-stored stream
# key, with a per-frame SHA-256 digest beside them. LIVE against a fabric.
set -uo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)/lib/hello-feed.sh"
hf_parse_env "$@"; set -- "${HF_ARGS[@]}"
COUNT=8; SYSTEM="hello-feed"; SITE="notional"
while [ "$#" -gt 0 ]; do case "$1" in --count) COUNT="$2"; shift 2;; --system) SYSTEM="$2"; shift 2;; --site) SITE="$2"; shift 2;; *) shift;; esac; done

hf_banner "Rung 1 — mirror" "Bytes stay bytes. volatile/ class, your own anchor, one stable key per feed, digest on a sibling key."
hf_preflight_live || exit 1
ANCHOR="$(hf_anchor)"
RAW="volatile/$ANCHOR/stream/$SYSTEM/$SITE/raw/v1"
DIGK="volatile/$ANCHOR/stream/$SYSTEM/$SITE/raw-digest/v1"
PORT="$(hf_free_port)"; LISTEN="127.0.0.1:$PORT"
TAPLOG="$HF_RUN/1-tap.log"; VERLOG="$HF_RUN/1-verify.log"; READY="$HF_RUN/1-verify.ready"; rm -f "$READY"

hf_step "The key shapes"
hf_note "$RAW"
hf_note "$DIGK"
hf_say "volatile/ = routed live, never retained (DROP congestion control). <anchor> = your cert CN, so"
hf_say "the ACL admits the write. ONE key per feed: the frame counter rides in the digest, never the key."

hf_step "Start the verifier: two subscriptions, recompute SHA-256 over every frame"
PUBLISHED=$((COUNT - COUNT / 5))
hf_cmd "tools/asterix-verify.py --env $HF_ENV --anchor $ANCHOR --system $SYSTEM --site $SITE --expect $PUBLISHED"
hf_bg "$VERLOG" python3 "$HF_ROOT/tools/asterix-verify.py" --env "$HF_ENV" --anchor "$ANCHOR" --system "$SYSTEM" --site "$SITE" --expect "$PUBLISHED" --timeout 150 --ready-file "$READY"
i=0; while [ ! -f "$READY" ] && [ $i -lt 300 ]; do sleep 0.1; i=$((i+1)); done
[ -f "$READY" ] || { hf_say "verifier did not open both subscriptions in 30s:"; hf_show < "$VERLOG"; exit 1; }
hf_note "both subscriptions open"

hf_step "Start the tap: lint, publish the bytes, publish the digest"
hf_cmd "tools/asterix-tap.py --listen $LISTEN --count $COUNT --env $HF_ENV --system $SYSTEM --site $SITE --format asterix:034,048"
hf_bg "$TAPLOG" python3 "$HF_ROOT/tools/asterix-tap.py" --listen "$LISTEN" --count "$COUNT" --env "$HF_ENV" --system "$SYSTEM" --site "$SITE" --format asterix:034,048 --timeout 60
hf_wait_for "$TAPLOG" "digest volatile" 5 || { cat "$TAPLOG"; exit 1; }

hf_step "Run the synthetic sensor at the tap, one datagram truncated on purpose"
hf_cmd "tools/asterix-synth.py --to $LISTEN --count $COUNT --rate 0.5 --corrupt-every 5"
hf_note "slow on purpose: this demo tap spawns one goat pub per frame (see README for the production shape)"
python3 "$HF_ROOT/tools/asterix-synth.py" --to "$LISTEN" --count "$COUNT" --rate 0.5 --corrupt-every 5 --quiet | hf_show

hf_say "The tap numbers datagrams as they ARRIVE. A refused frame keeps its number and gets no"
hf_say "digest, so the digest stream shows a gap exactly where the lint fired — the far side can"
hf_say "tell 'refused at the tap' from 'lost in flight' without a return path."

hf_step "Wait for the tap and the verifier to finish"
for _ in $(seq 1 600); do grep -q "tap done" "$TAPLOG" && grep -q "^verify: .*matched" "$VERLOG" && break; sleep 0.2; done
hf_say "tap:";    hf_show < "$TAPLOG"
hf_say "verify:"; grep -E '^verify' "$VERLOG" | hf_show

hf_step "Try to retrieve the stream afterwards — expect nothing"
hf_cmd "goat replay $RAW --since 10m"
HIST="$(hf_goat replay "$RAW" --since 10m 2>&1 || true)"
REPLAY_MEASURED=1
if printf '%s' "$HIST" | grep -q "operator-gated"; then
  REPLAY_MEASURED=0
  hf_note "not measured from this credential: the audit-tail read needs an operator key."
  hf_note "volatile/ is excluded from router storage and the audit tail by construction (goat zenoh-volatile-class.md §3)."
elif [ -z "$(printf '%s' "$HIST" | tr -d '[:space:]')" ]; then hf_note "(empty — volatile/ is excluded from storage and audit by design)"
else printf '%s\n' "$HIST" | grep -v WARN | hf_show; fi

hf_step "Verify"
TAP="$(cat "$TAPLOG")"; VER="$(grep -E '^verify:' "$VERLOG" | tail -1)"
hf_assert_contains "the truncated frame was dropped by the lint, not published" "$TAP" "DROPPED, not published"
hf_assert_contains "every well-formed frame was published with its digest"  "$TAP" "$PUBLISHED published"
hf_assert_contains "no publish failed"                                      "$TAP" "0 publish failures"
hf_assert_contains "every frame the subscriber holds has a matching digest" "$VER" "0 without a digest"
hf_assert_contains "the only digest-sequence gap is the frame the lint refused (seq 5)" "$VER" "gaps [5]"
if [ "$REPLAY_MEASURED" = 1 ]; then hf_assert_lacks "nothing was retained for replay" "$HIST" "$RAW"; fi
hf_done
