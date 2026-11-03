# shellcheck shell=bash
# hello-feed.sh — shared library for "Hello Galaxy: legacy feed carriage".
#
# Sourced by every rung driver. Environment resolution (which goat context a
# live rung runs against), the anchor derivation, narration, assertions and
# background-process bookkeeping. Adapted from hello-galaxy-zenoh-patterns'
# lib so the series reads the same way.
#
# Execution model:
#   rung 0 and rung 2 (offline mode) run on a laptop with no fabric at all.
#   rung 1 and rung 2 --publish run LIVE against a real goatnet (the goat
#   context passed with --env) under YOUR OWN anchor: volatile/<anchor>/stream/** and
#   <anchor>/**. Nothing touches anyone else's keys and nothing is faked.

set -o pipefail

HF_LIB="${BASH_SOURCE[0]}"
HF_ROOT="$(cd "$(dirname "$HF_LIB")/.." && pwd)"
export HF_ROOT
HF_RUN="$HF_ROOT/.run"
mkdir -p "$HF_RUN"

HF_ENV="${HF_ENV:-}"
hf_parse_env() {
  HF_ARGS=()
  while [ "$#" -gt 0 ]; do
    case "$1" in
      --env) HF_ENV="$2"; shift 2 ;;
      --env=*) HF_ENV="${1#--env=}"; shift ;;
      *) HF_ARGS+=("$1"); shift ;;
    esac
  done
  export HF_ENV
}

hf_goat() { goat --context "$HF_ENV" "$@"; }
hf_cert_path() { echo "$HOME/.goat/contexts/$HF_ENV/mtls.cert.pem"; }
hf_anchor() {
  local cert cn
  cert="$(hf_cert_path)"
  [ -f "$cert" ] || { echo ""; return 1; }
  cn="$(openssl x509 -in "$cert" -noout -subject 2>/dev/null \
        | sed -n 's/.*CN *= *\([^,/]*\).*/\1/p' | tr -d '[:space:]')"
  echo "$cn"
}

# A free loopback UDP port so parallel runs and CI do not collide.
hf_free_port() { python3 -c 'import socket;s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);s.bind(("127.0.0.1",0));print(s.getsockname()[1])'; }

# --- presentation -----------------------------------------------------------
if [ -t 1 ] && [ "${NO_COLOR:-}" = "" ]; then
  C_RESET=$'\033[0m'; C_BOLD=$'\033[1m'; C_DIM=$'\033[2m'
  C_GREEN=$'\033[32m'; C_RED=$'\033[31m'; C_CYAN=$'\033[36m'; C_BLUE=$'\033[34m'
else
  C_RESET=""; C_BOLD=""; C_DIM=""; C_GREEN=""; C_RED=""; C_CYAN=""; C_BLUE=""
fi
HF_STEP=0
hf_banner() {
  printf '\n%s%s== %s ==%s\n' "$C_BOLD" "$C_BLUE" "$1" "$C_RESET"
  [ -n "${2:-}" ] && printf '%s%s%s\n' "$C_DIM" "$2" "$C_RESET"
}
hf_step() { HF_STEP=$((HF_STEP + 1)); printf '\n%s%s[%d] %s%s\n' "$C_BOLD" "$C_CYAN" "$HF_STEP" "$1" "$C_RESET"; }
hf_say()  { printf '    %s\n' "$1"; }
hf_note() { printf '    %s%s%s\n' "$C_DIM" "$1" "$C_RESET"; }
hf_cmd()  { printf '    %s$ %s%s\n' "$C_GREEN" "$1" "$C_RESET"; }
hf_show() { sed 's/^/    │ /'; }

# --- preflight --------------------------------------------------------------
hf_require_python() {
  command -v python3 >/dev/null 2>&1 || { printf '%spython3 is required.%s\n' "$C_RED" "$C_RESET" >&2; return 1; }
}
hf_preflight_live() {
  hf_require_python || return 1
  if [ -z "$HF_ENV" ]; then
    printf '%sThis rung needs a goatnet.%s Pass --env <context> (see: goat context ls).\n' "$C_RED" "$C_RESET" >&2
    return 1
  fi
  if ! command -v goat >/dev/null 2>&1; then
    printf '%sgoat is not on your PATH.%s See README → Prerequisites.\n' "$C_RED" "$C_RESET" >&2
    return 1
  fi
  local anchor; anchor="$(hf_anchor || true)"
  if [ -z "$anchor" ]; then
    printf '%sNo fabric certificate for context "%s".%s Collect your fabric credential, then run: goat context use %s\n' \
      "$C_RED" "$HF_ENV" "$C_RESET" "$HF_ENV" >&2
    return 1
  fi
  printf '%senv: %s · anchor: %s%s\n' "$C_DIM" "$HF_ENV" "$anchor" "$C_RESET"
}

# --- background processes ---------------------------------------------------
HF_PIDS=()
hf_bg() {  # hf_bg <logfile> <cmd...>
  local log="$1"; shift
  "$@" >"$log" 2>&1 &
  HF_PIDS+=("$!")
}
hf_wait_for() {  # hf_wait_for <file> <pattern> <seconds>
  local f="$1" pat="$2" secs="${3:-10}" i=0
  while [ "$i" -lt $((secs * 10)) ]; do
    grep -q -- "$pat" "$f" 2>/dev/null && return 0
    sleep 0.1; i=$((i + 1))
  done
  return 1
}
hf_cleanup() { for p in ${HF_PIDS[@]+"${HF_PIDS[@]}"}; do kill "$p" 2>/dev/null || true; done; }
trap hf_cleanup EXIT

# --- assertions -------------------------------------------------------------
HF_FAILS=0
hf_assert_contains() {
  local what="$1" hay="$2" needle="$3"
  if printf '%s' "$hay" | grep -qF -- "$needle"; then printf '    %s✓%s %s\n' "$C_GREEN" "$C_RESET" "$what"
  else printf '    %s✗%s %s (expected: %s)\n' "$C_RED" "$C_RESET" "$what" "$needle" >&2; HF_FAILS=$((HF_FAILS + 1)); fi
}
hf_assert_lacks() {
  local what="$1" hay="$2" needle="$3"
  if printf '%s' "$hay" | grep -qF -- "$needle"; then printf '    %s✗%s %s (did NOT expect: %s)\n' "$C_RED" "$C_RESET" "$what" "$needle" >&2; HF_FAILS=$((HF_FAILS + 1))
  else printf '    %s✓%s %s\n' "$C_GREEN" "$C_RESET" "$what"; fi
}
hf_done() {
  if [ "$HF_FAILS" -eq 0 ]; then printf '\n%s%s✓ rung complete — every assertion held.%s\n' "$C_BOLD" "$C_GREEN" "$C_RESET"; return 0; fi
  printf '\n%s%s✗ %d assertion(s) failed.%s\n' "$C_BOLD" "$C_RED" "$HF_FAILS" "$C_RESET" >&2; return 1
}
