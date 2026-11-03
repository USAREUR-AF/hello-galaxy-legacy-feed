#!/usr/bin/env bash
# Rung 2 — decode: typed GeoTrackV1 records from the plots, validated against
# the published schema. Offline by default; --publish puts them on a STORED
# key under your anchor with --confirm and reads one back.
set -uo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)/lib/hello-feed.sh"
hf_parse_env "$@"; set -- "${HF_ARGS[@]}"
PUBLISH=0; COUNT=5; SYSTEM="hello-feed"
while [ "$#" -gt 0 ]; do case "$1" in --publish) PUBLISH=1; shift;; --count) COUNT="$2"; shift 2;; --system) SYSTEM="$2"; shift 2;; *) shift;; esac; done

hf_banner "Rung 2 — decode" "Only this rung writes to storage, so only this rung the decode-health guard can grade."
hf_require_python || exit 1
ANCHOR="$(printf '0%.0s' $(seq 1 32))"
if [ "$PUBLISH" = 1 ]; then hf_preflight_live || exit 1; ANCHOR="$(hf_anchor)"; fi
PORT="$(hf_free_port)"; LISTEN="127.0.0.1:$PORT"; LOG="$HF_RUN/2-decode.log"

hf_step "The contract: decode what the consumer reads, refuse the rest by name"
hf_say "The adapter implements I048/010,140,020,040,070,090,220,161,200 — enough for a map. A record"
hf_say "carrying any other item is refused with the item's name and carried at rung 1 only."
hf_say "Output is goat's GeoTrackV1 (schemas/goat.geo.track.v1.schema.json), validated before publishing."
hf_note "<anchor>/$SYSTEM/geo/track/asterix048/<sac>-<sic>-<track>   per-entity: right while concurrent tracks stay in the low hundreds"

hf_step "Start the adapter"
ARGS=(--listen "$LISTEN" --count "$COUNT" --system "$SYSTEM" --anchor "$ANCHOR" --timeout 60)
[ "$PUBLISH" = 1 ] && ARGS+=(--publish --env "$HF_ENV")
hf_cmd "tools/asterix-decode.py ${ARGS[*]}"
hf_bg "$LOG" python3 "$HF_ROOT/tools/asterix-decode.py" "${ARGS[@]}"
hf_wait_for "$LOG" "schema" 5 || { cat "$LOG"; exit 1; }

hf_step "Run the synthetic sensor at it"
hf_cmd "tools/asterix-synth.py --to $LISTEN --count $COUNT --rate 1"
python3 "$HF_ROOT/tools/asterix-synth.py" --to "$LISTEN" --count "$COUNT" --rate 1 --quiet | hf_show
for _ in $(seq 1 600); do grep -q "decode done" "$LOG" && break; sleep 0.2; done
hf_show < "$LOG"

hf_step "Show one record the way a map receives it"
python3 - "$HF_ROOT" <<'PY' | hf_show
import json, sys, os
sys.path.insert(0, os.path.join(sys.argv[1], "lib")); sys.path.insert(0, os.path.join(sys.argv[1], "tools"))
import asterix048 as ax
import importlib.util
spec = importlib.util.spec_from_file_location("dec", os.path.join(sys.argv[1], "tools", "asterix-decode.py")); dec = importlib.util.module_from_spec(spec); spec.loader.exec_module(dec)
rec = ax.encode_048(7, 3, 43200.0, 12.5, 45.0, "7000", 350, 0xF00101, 101, 420, 92.0)
f = ax.decode_frame(ax.block(48, [rec]))[0]["fields"]
_, t = dec.to_track(f, "0" * 32, "hello-feed", "notional", "hello-feed-adapter", 10.0, -30.0)
print(json.dumps(t, indent=1))
PY

if [ "$PUBLISH" = 1 ]; then
  hf_step "Read one back from storage"
  KEY="$ANCHOR/$SYSTEM/geo/track/asterix048/7-3-101"
  hf_cmd "goat sub $KEY --since 5m --count 1"
  BACK="$(hf_goat sub "$KEY" --since 5m --count 1 2>&1 || true)"; printf '%s\n' "$BACK" | tail -2 | hf_show
fi

hf_step "Verify"
OUT="$(cat "$LOG")"
hf_assert_contains "plots decoded and validated against GeoTrackV1" "$OUT" "plot(s) valid"
hf_assert_contains "the north marker was recognised, not forced into a track" "$OUT" "CAT034 north-marker"
hf_assert_contains "no record failed schema validation" "$OUT" "0 record(s) invalid"
if [ "$PUBLISH" = 1 ]; then
  hf_assert_contains "every published record was confirmed landed" "$OUT" "0 not confirmed"
  if printf '%s' "$BACK" | grep -q "operator-gated"; then
    printf '    SKIP a stored record reads back (reading stored history needs an operator key on this goatnet)\n'
  else
    hf_assert_contains "a stored record reads back" "$BACK" "goat.geo.track.v1"
  fi
fi
hf_done
