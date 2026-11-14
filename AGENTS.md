# AGENTS.md

Instructions for AI coding agents, and a short version for anyone working here. [CONTRIBUTING.md](CONTRIBUTING.md) is the full process.

## What this repository is

hello-galaxy-legacy-feed shows three ways to carry a sensor feed in a legacy wire format (here ASTERIX CAT 034/048) on a goatnet: carry the bytes, mirror them, or decode them. The sensor is synthetic.

It is one of the Hello Galaxy demonstrations: small, runnable examples, each showing one part of [goat](https://github.com/USAREUR-AF/goatcore). It holds no goat source code.

## Layout

| Path | What |
|---|---|
| `rungs/` | one directory per rung: `README.md` and `run.sh` |
| `bin/hello-feed` | the runner |
| `lib/` | the ASTERIX codec, the lint, shared shell functions |
| `tools/` | synthetic sensor, relay, receiver, decoder and verifier scripts |
| `schemas/` | the JSON schema of the decoded track |
| `tests/test_asterix.py` | offline tests of the codec, lint vectors and schema |

## Before you push

CI (`.github/workflows/ci.yml`) runs these; none needs a goatnet:

```bash
shellcheck -e SC1090,SC1091,SC2034 lib/hello-feed.sh rungs/*/run.sh bin/hello-feed
python3 -m pip install -r requirements.txt
python3 tests/test_asterix.py
NO_COLOR=1 bin/hello-feed 0-carry
NO_COLOR=1 bin/hello-feed 2-decode
```

Every directory under `rungs/` holds a `README.md` and an executable `run.sh`, and every file in `tools/` is executable; CI checks both.

## Rules

1. **Nothing from a real deployment.** No hostname, domain, address, key or person of a real goatnet goes into a file or a commit message. Use made-up names, documentation addresses (RFC 5737) and `example.org` mail.
2. **Commits.** Conventional Commits subject of 100 characters or fewer, with a scope (`fix(<component>): …`). Every commit is signed off (`git commit -s`, the DCO) and signed with a key GitHub verifies. The organization's required check `verified-commits` refuses a pull request that holds an unverified commit.
3. **One logical change per pull request.**
4. **Vulnerabilities** go through [SECURITY.md](SECURITY.md), never a public issue.

The contribution guide for goat as a whole is [goatcore CONTRIBUTING.md](https://github.com/USAREUR-AF/goatcore/blob/main/CONTRIBUTING.md).
