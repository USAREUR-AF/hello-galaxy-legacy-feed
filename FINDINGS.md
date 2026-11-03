# Findings — goat CLI behaviours this demo works around

Each one shaped a script here; each is worth knowing before you script `goat`
yourself.

| # | What | How the demo handles it |
|---|---|---|
| 1 | `goat sub` prints the **display alias** of an anchor by default (`volatile/maintainer/…`), so a tool matching on the canonical key must pass `--uuid`. Documented in the CLI help, easy to miss when scripting. | the verifier and relay run `goat sub --uuid` |
| 2 | `goat sub`'s "subscribed to" line is on **stderr**, samples on **stdout**. A verifier that wants a ready signal has to merge them. | the verifier and relay merge the two streams |
| 3 | `goat pub` has no attachment flag, so a per-frame digest has to ride a sibling key. A native publisher puts it in the sample attachment. | the digest rides `…/raw-digest/v1` beside `…/raw/v1` |
| 4 | `goat replay` / `goat sub --since` read the audit tail, which needs an **operator** key; a plain fabric credential is refused. An "empty replay" assertion made from a non-operator credential passes for the wrong reason. | rung 1 reports the replay as not measured when the credential is refused |
| 5 | The portal topic `format` is free text validated only for `protobuf:` and `xml:`; `asterix:048` is accepted and graded by the decode-health guard, but the portal inspector has no decoded pane for it. | registration is described as discovery, not grading |
