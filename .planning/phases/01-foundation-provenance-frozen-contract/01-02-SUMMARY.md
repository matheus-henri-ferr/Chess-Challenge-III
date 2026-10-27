---
phase: 01-foundation-provenance-frozen-contract
plan: 02
subsystem: contract-console
tags: [protocol, logbook, uci, mock, freeze, contract, rule-9]

# Dependency graph
requires:
  - phase: none (01-01 not a hard dep: mocks are stdlib; test_contract reuses tools/tests/__init__.py created by 01-01 — present)
provides:
  - docs/PROTOCOL.md (frozen console↔engine contract: §3.1 go literal, §6 tm= grammar + closed reason set, §7 bestmove/search_id, §11 change control)
  - docs/LOGBOOK.md (frozen Rule 9 log spec: 8 mandatory fields + score_white, src= variants, pv-last-unquoted, fail-closed log_lint, header/trailer)
  - tools/mock_engine.py (contract-speaking UCI mock + 10 misbehaviour flags + --record/--tm-trace)
  - tools/mock_gui.py (driver emitting ONLY the frozen go literal; CSV_COLUMNS = LOGBOOK keys; wall_ms ≥ engine_ms invariant)
  - tools/check_contract_order.py (freeze-predates-implementation proof, repo-root argv)
  - tools/tests/test_contract.py (12 doc↔mock↔driver agreement + ordering tests)
  - evidence/01-contract-transcript.log (Task 1 exchange + Task 2 2-game session, 17 bestmove)
affects: [Phase 2 console (parses exactly §5/§7), Phase 4 TM (fills §6 values, tm=custom-vMAJOR.MINOR), Phase 6 SPRT/logs, 01-03's first impl commit must postdate freeze 2fd4bf4f]

# Actuals (#2632) — pairs with the plan's `estimate` to calibrate future estimates.
actuals:
  tokens: 44000
  tasks: 3
  commits: 3

# Tech tracking
tech-stack:
  added: []
  patterns: [frozen-literal-as-constant (GO_LITERAL identical in doc/mock/driver, asserted both directions), docs-only freeze commit proven by diff-tree, synthetic-repo testing of git-history tooling, wall>=engine invariant asserted at write time]

key-files:
  created:
    - docs/PROTOCOL.md
    - docs/LOGBOOK.md
    - tools/mock_engine.py
    - tools/mock_gui.py
    - tools/check_contract_order.py
    - tools/tests/test_contract.py
    - evidence/01-contract-transcript.log
  modified: []

key-decisions:
  - "Freeze landed as ONE docs-only commit 2fd4bf4f containing exactly PROTOCOL.md + LOGBOOK.md (Task 1 committed PROTOCOL alone, Task 2's LOGBOOK was amended in — end state satisfies the Task 3 gate verbatim)"
  - "CSV columns renamed to LOGBOOK §2 keys: move_no (not ply), engine_ms+wall_ms pair (not time_ms); mock_gui asserts wall_ms ≥ engine_ms per row (LOGBOOK §2.2)"
  - "mock_engine caps reported `time` under --delay-ms so the wall_ms ≥ engine_ms invariant is physically satisfiable in the demo run"
  - "check_contract_order.py scopes history to project commits (rev-list HEAD ^sf_19) — rev-list --all walks upstream sf_19 and false-fails; synthetic repos without sf_19 fall back to HEAD"
  - "check_contract_order.py passes --root to every diff-tree — a root commit's diff is EMPTY without it, which made an impl-first synthetic repo read as vacuously OK (caught by test)"
  - "Freeze detection: exactly one commit whose changed-file set == {PROTOCOL, LOGBOOK}; ambiguous (0 or >1) is FAIL, not a guess"
  - "Comment-only provenance rule mirrors 01-01's actual src/ edits: ^Modified by ChessChallendIII on <date>: (// prefix tolerated, same regex as check_license.sh) plus blank lines"

# Deviations from the plan (Rules 1–3 auto-fixes, none needed Rule 4 STOP)
deviations:
  - "Plan's verify greps r['tm_trace'], r['depth'], r['pv'] on CSV — done, plus wall_ms ≥ engine_ms added (LOGBOOK §2.2 is a frozen invariant; asserting it is in the spirit of 'driver invariants self-asserting')"
  - "check_contract_order.py takes optional repo-root argv (plan said work on the repo; synthetic tests need isolation — pattern-matched on check_provenance.py's path argv)"

must_be_informed:
  - "Freeze commit is 2fd4bf4f — 01-03's src/engine.cpp patch MUST postdate it (check_contract_order.py will then flip from vacuous OK to a real ancestry OK; if it FAILs, the src patch landed on the wrong side)"
  - "LOGBOOK §2.2 wall_ms ≥ engine_ms is asserted by mock_gui now; the Phase 2 console must inherit this invariant in its own logger"
  - "Ponder grammar frozen (§3.5) but Ponder=false until TM-13 (Phase 5)"
---

# Plan 01-02 — Contract Freeze & Mocks: SUMMARY

## What was built

- **docs/PROTOCOL.md** — eleven numbered sections. Load-bearing literals:
  §3.1 `go wtime <int_ms> btime <int_ms> winc 10000 binc 10000` (worked
  example at §3.4 with 798000/851000), §3.2 forbids
  movetime/movestogo/depth/nodes/infinite/searchmoves, §6.1 tm= grammar with
  closed reason set {reserve, bank_positive, low_clock, instant, book_exit,
  scramble} + §6.3 tm=upstream ablation shape, §7.3 stale-bestmove discard by
  search_id, §9.1 CRITICAL ERROR is fatal, §11 change control.
- **docs/LOGBOOK.md** — Rule 9 quoted verbatim; eight mandatory fields table
  (move_no, side, uci, depth, nodes, score, pv, engine_ms+wall_ms) with
  type/unit/source/empty-allowed per field; score_white normalisation (§2.1);
  line format with pv last, unquoted (§3.2); src= variants
  search/book/tb/ponder/opp/none (§4); header/trailer (§5); fail-closed
  log_lint contract (§6).
- **tools/mock_engine.py** — stdlib UCI mock; `GO_LITERAL` constant mirrors
  §3.1; scenario flags (--delay-ms, --crash-after, --stale-bestmove,
  --silent-hang, --illegal-bestmove, --none-bestmove, --crash-on-option,
  --garbage, --slow-ready, --tm-trace, --record); `info string tm=…` exactly
  per §6.1; EOF == quit like uci.cpp's read-loop.
- **tools/mock_gui.py** — driver that sends ONLY the frozen go literal, one
  outstanding go, `position startpos moves …` always; stale-slot discard
  (§7.3); `CSV_COLUMNS = [move_no, side, uci, depth, nodes, score, engine_ms,
  wall_ms, pv, tm_trace]`; asserts tm_trace non-empty (with --require-tm) and
  wall_ms ≥ engine_ms on every row.
- **tools/check_contract_order.py** — proves the docs freeze predates
  implementation: freeze = the unique commit whose changed-file set is exactly
  the two docs; walks project commits touching src/ console/ pipeline/
  (tools/ and scripts/ deliberately excluded); ignores comment-only
  provenance edits; `merge-base --is-ancestor` verdict; `OK CONTRACT ORDER`
  / named FAIL + nonzero.
- **tools/tests/test_contract.py** — 12 unittest cases in 5 groups: go-literal
  doc↔mock↔gui agreement (both directions), forbidden tokens only inside
  prohibition text (never in grammar blocks), tm reason-token set equality,
  LOGBOOK keys ⊆ CSV_COLUMNS, and four synthetic-repo ordering scenarios.
- **evidence/01-contract-transcript.log** — Task 1 single exchange + Task 2
  2-game --require-tm session, rendered both directions from --record JSONL;
  17 `bestmove` lines.

## Verification evidence

| Gate | Result |
|---|---|
| `python3 tools/check_contract_order.py` | `OK CONTRACT ORDER` (vacuous — no impl commit yet; 01-03 flips it to real) |
| `python3 -m unittest tools.tests.test_contract -v` | 12/12 pass |
| `python3 -m unittest discover -s tools/tests -t .` | 17/17 pass (incl. 01-01's 5) |
| freeze-commit gate (diff-tree == exactly 2 docs, `--diff-filter=A` count 1) | `FREEZE-GATE-OK` |
| `PYTHONPATH=vendor python3 tools/mock_gui.py --games 2 --require-tm --engine-arg=--delay-ms=2800 --record … --csv …` | `OK mock_gui: 16 searches`; all rows: tm_trace ✓, depth 16 ✓, pv first token ∈ opening set ✓, wall_ms ≥ engine_ms ✓ |
| `grep -c bestmove evidence/01-contract-transcript.log` | 17 (≥ 2 required) |

## Requirements coverage

| Req | Evidence |
|---|---|
| FOUND-05 (docs frozen in docs-only commit) | freeze `2fd4bf4f`, gate above |
| FOUND-05 (mocks complete a real search speaking the frozen literal) | 16-search session + committed transcript |
| FOUND-05 (freeze provably predates implementation) | `check_contract_order.py` + 4 synthetic-repo tests |

## Commits

- `2fd4bf4f` docs(01-02): freeze docs/PROTOCOL.md + docs/LOGBOOK.md (FOUND-05)
- `17d52a4f` feat(01-02): contract mocks end-to-end (mock_engine + mock_gui)
- `eb86704a` feat(01-02): ordering proof + contract regression tests

## Leftovers for later plans/phases

- 01-03: first real impl commit (src/engine.cpp TB clamp) — MUST postdate
  `2fd4bf4f`; checker flips from vacuous to real ancestry proof then.
- Phase 2 console implements `log_lint` (LOGBOOK §6) and the §7.3
  search_id discard; mocks already speak both sides.
- Phase 4 TM fills §6 values and bumps `tm=custom-v1.0` → real version.
- `--start-fen` is accepted-but-unimplemented in mock_gui (mock plays the
  scripted opening regardless); harmless, documented in --help.
