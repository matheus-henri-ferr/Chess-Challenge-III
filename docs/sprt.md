# SPRT recipe — ChessChallendIII (PIPE-01)

Normative. This is the single copy of the SPRT command; Phase 6 reuses it
unedited. `tools/sprt.sh` wraps it with an audit trail (invocation, date,
commit, both binaries' sha256, book sha256 → `results/sprt-<timestamp>.log`).

## The command

```sh
tools/fastchess-linux-x86-64/fastchess \
  -engine name=base cmd=<path-to-base-binary> \
  -engine name=custom cmd=<path-to-candidate-binary> \
  -each proto=uci tc=10+0.1 "option.Move Overhead=100" \
  -openings file=tools/books/UHO_Lichess_4852_v1.epd format=epd order=random \
  -rounds <n> -repeat -concurrency <n> \
  -sprt elo0=0 elo1=5 alpha=0.05 beta=0.05 model=normalized \
  -report penta=true -recover \
  -pgnout file=results/out.pgn notation=uci
```

Parameters: `elo0=0 elo1=5` Elo bounds, `alpha=beta=0.05` error rates,
`tc=10+0.1`, `-repeat` (each opening twice, colours swapped — pair statistics
require it), pentanomial reporting.

## The three corrections (verified against fastchess 1.8.2-alpha)

| # | Correction | Why |
|---|---|---|
| 1 | The Move Overhead option token uses a **space** between `Move` and `Overhead`, quoted: `"option.Move Overhead=100"` — on both engines | fastchess matches the literal UCI option name; the underscored variant is rejected with a warning and silently does nothing. (REQUIREMENTS.md records the underscored form; this space form is the verified-correct one — RESEARCH Q8/OQ-8.) |
| 2 | `-openings` is required for a **verdict** (though not merely to start a run) | Without openings the first plies repeat, draw rates explode and the pentanomial model degrades; SPRT bounds assume opening variety. |
| 3 | Output shape is an `LLR:` line plus `Ptnml(0-2)` counts, e.g. `LLR: -0.02 (-0.7%) (-2.94, 2.94) [0.00, 5.00]` | LLR outside (-2.94, 2.94) decides H0/H1; the penta counts show the pair distribution the LLR was computed from. |

## Time controls

- **`10+0.1` is the only verdict time control.** Accept/reject decisions are
  never drawn at the competition TC (`15+10`, ~5 min/game → hundreds of games
  take days) and never at `1+0.01` (draw-rate and TM distortion; smoke tests
  only).
- After any accept/reject at `10+0.1`, verify the TM at `60+1` and `15+10`
  with a handful of games before shipping.

## Book

`tools/books/UHO_Lichess_4852_v1.epd` — official-stockfish/books, CC0-1.0,
2,632,036 lines, 16 plies. Hash pinned in `tools/books/SHA256SUMS`. Downloaded
from the repo's zip (`UHO_Lichess_4852_v1.epd.zip`); the raw-`.epd` URL does
not exist in that repository.

## Provenance note

`REQUIREMENTS.md` PIPE-01 records the option token with an underscore; the
space form above is the verified-correct one (RESEARCH Q8, open question
OQ-8, resolved by running fastchess). This note is the audit trail for the
discrepancy.
