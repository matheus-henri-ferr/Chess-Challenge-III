# LOGBOOK — Rule 9 Game Log Specification (ChessChallendIII)

> Normative specification of the graded game log. Rule 9 (transcribed in
> `docs/competition-rules.md`): *"É obrigatório, porém, registrar log em .txt
> ou .log contendo, para cada lance: número do lance, cor, lance escolhido em
> notação UCI, profundidade atingida, nós avaliados, avaliação da posição,
> variante principal (PV) e tempo gasto. O log será entregue à banca ao final
> de cada partida."* Tests cite sections as `LOGBOOK §N`.
>
> Frozen: 2026-10-26

License: GPL-3.0-or-later. See Copying.txt and NOTICE.

## 1. Mandate

1.1. One `.log` file per game, named `game-<id>.log`, written by the console.

1.2. The file is **append-only** during the game and **never edited** after
     it. The delivered artefact is the file as it was when the game ended.

1.3. The log is delivered to the panel at the end of every game. A missing
     mandatory field is a compliance failure, not a formatting bug — `log_lint`
     (§6) fails closed.

1.4. Every half-move of BOTH colours is logged: ours and the opponent's.

## 2. The eight mandatory fields

| # | Rule 9 field (PT) | log key | Type | Unit | Source | Empty allowed? |
|---|---|---|---|---|---|---|
| 1 | número do lance | `move_no` | int | full-move number | `board.fullmove_number` | no |
| 2 | cor | `side` | `w`\|`b` | — | side that made the move | no |
| 3 | lance escolhido em notação UCI | `uci` | string | — | `bestmove` / parsed operator input / book entry | no (`(none)` on a terminal move) |
| 4 | profundidade atingida | `depth` | int | plies | last completed `info depth` | no (0 for book/tb/opp) |
| 5 | nós avaliados | `nodes` | int | nodes | `info nodes` | no (0 for book/tb/opp) |
| 6 | avaliação da posição | `score` | string | cp or `mate N` | `info score` **verbatim**, incl. bound flag | no (`-` when absent) |
| 7 | variante principal (PV) | `pv` | space-separated UCI | — | `info pv` | no (the move itself for book/tb) |
| 8 | tempo gasto | `engine_ms` + `wall_ms` | int | ms | `info time` (wire ms, PROTOCOL §5.2); `monotonic_ns()` delta | no (0 for book; `wall_ms` always measured) |

2.1. `score` records the side-to-move POV value verbatim, including any
     `lowerbound`/`upperbound` flag, **and** additionally a White-POV
     normalisation in the `score_white` key (`-` when absent).

2.2. The time pair is two keys: `engine_ms` (the engine's reported `time`,
     which arrives in milliseconds on the wire) and `wall_ms` (the console's
     monotonic wall-clock delta). `wall_ms ≥ engine_ms` always.

## 3. Line format

3.1. One line per half-move. `key=value` pairs separated by single spaces, in
     a stable key order:

```
src=<src> move_no=<int> side=<w|b> uci=<uci> depth=<int> nodes=<int> score=<score> score_white=<score|-> engine_ms=<int> wall_ms=<int> pv=<moves>
```

3.2. No spaces inside values. The PV is space-separated *by definition*, so
     **`pv` goes last on the line, unquoted** — frozen choice, no alternatives.

3.3. Unknown keys MUST NOT be invented per line; new keys require a new dated
     revision of this document (§7).

## 4. Variants (`src=` values)

4.1. `src=search` (default) — an engine search produced the move; all eight
     fields from `info`.

4.2. `src=book` — an opening-book move: `depth=0 nodes=0 score=book
     pv=<the move itself> engine_ms=0`, `wall_ms` measured.

4.3. `src=tb` — a tablebase-guided move: `depth=0 nodes=0
     score=tb win|draw|loss pv=<the move itself> engine_ms=0`.

4.4. `src=ponder` — a discarded search (ponder miss or stale `bestmove`,
     PROTOCOL §7.3): logged for the record, never announced to the operator.

4.5. `src=opp` — the opponent's half-move as entered by the operator:
     `depth=0 nodes=0 score=- engine_ms=0`, `wall_ms` measured, `uci` = the
     parsed input.

4.6. `src=none` — a terminal move: `uci=(none) depth=0 nodes=0`, non-empty
     `score` (e.g. `mate 0`).

## 5. Header and trailer

5.1. The first lines (header) record: game id, date, our colour, time control,
     engine binary sha256, net sha256, the full `setoption` set, the effective
     `SyzygyProbeLimit`, the TB inventory hash, the book hash + max ply, and
     `network=off`.

5.2. The last lines (trailer) record: result, reason, both final clocks as
     observed, and the log's own sha256.

## 6. The `log_lint` contract

6.1. A linter (`log_lint`, implemented in Phase 2) MUST fail closed — every
     check below is a failure, never a warning:

- every one of the eight keys (plus `src`, `score_white`) present per line;
- `move_no` monotonically non-decreasing; `side` alternates `w`,`b`;
- `uci` legal in the replayed position (or `(none)` for `src=none`);
- `pv` non-empty (the move itself counts for book/tb);
- `wall_ms ≥ engine_ms`;
- no `src=` value outside the §4 set;
- header and trailer present and complete (§5).

6.2. A log that passes `log_lint` is the deliverable; a log that fails is a
     game incident, handled per the event runbook.

## 7. Versioning and change control

7.1. This document froze on 2026-10-26 together with `docs/PROTOCOL.md` in a
     docs-only commit; `tools/check_contract_order.py` proves the freeze
     predates implementation.

7.2. A change requires a new dated revision header, a note in
     `PROVENANCE.md`, and re-running `tools/tests/test_contract.py`.
