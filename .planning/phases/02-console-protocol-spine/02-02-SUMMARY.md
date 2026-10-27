---
plan: 02-02
phase: 02-console-protocol-spine
title: console interactive spine — typed reject, replica, Session FSM, operator loop
status: complete
completed: 2026-10-27
requirements-completed: [PROTO-01, PROTO-02, PROTO-03, PROTO-05, PROTO-06, PROTO-07, PROTO-04]
requirements-pending: []
# Shared-ID gate note (matches 02-01-SUMMARY's #2388 disposition): PROTO-04 was
# left Pending by 02-01 because 02-02 also declares it. 02-02's SUMMARY landing
# is what flips it — hence PROTO-04 appears in requirements-completed here.
estimate:
  tokens: 120000
  actual_tokens: 498500  # chars/4 over the realized diff (13 files, 1994 insertions)
  raw_tokens: 60000
  tasks: 3
  confidence: low
  duration_s: 740  # PLAN_START 1793130174 → SUMMARY write, single session
plan_head_before: 620411819aa4fa7a2ecb05c5fbf3d8327c256c51
plan_head_after: b86ad530
commits:
  - 2c157b2f feat(02-02): typed-reject parse layer, board replica, CF-7 ponder-discard suite (test-first)
  - 3421e8aa feat(02-02): Session FSM with side guard, bestmove validation, game-start trigger, ponder discard
  - b86ad530 feat(02-02): OperatorLoop select-on-stdin + game-mode wiring in main (piped smoke green)
---

## What shipped

The interactive spine: every operator keystroke and every engine answer now
flows through validated, journaled, state-machine-guarded paths.

- `console/src/console/game/moves.py` — PROTO-01 typed-reject layer:
  `normalize_token` (strip → squeeze → lowercase), `RejectKind`
  (MALFORMED/NULL/ILLEGAL), `Reject` (kind + raw + reason), `operator_move`
  (0000 guard BEFORE `parse_uci` — the library accepts `0000` silently;
  promotion-ambiguity re-prompt naming the four suffixes, verified:
  `parse_uci('a7a8')` itself raises IllegalMoveError so the gate must run
  pre-parse), `announce_form` (E2-E4, E7-E8=Q). SAN never reaches
  `parse_san` — length-4/5 gate rejects it as MALFORMED.
- `console/src/console/game/board.py` — `BoardState` replica:
  `push_validated` captures move_no/side BEFORE the push (Pitfall 6),
  `try_push_token` → `(move, meta) | (None, Reject)`, `position_line()` is
  the ONLY producer of `position startpos moves …` (Pitfall 3), `outcome()`
  detects terminal state without self-adjudicating, `expected_mover()` is
  the guard substrate, `pop()` realigns without restart (Rule 10).
- `console/src/console/engine/session.py` — `Session` FSM, RESEARCH
  Pattern 2 implemented literally: states IDLE/OUR_SEARCH/ANNOUNCE_PENDING/
  AWAIT_OPP_CONFIRM/OPP_TURN/PONDERING + internal DISCARDING. Side-to-move
  guard reads `board.turn` only; wrong-side input is a typed reject naming
  the expected side (PROTO-05, both directions tested). `start_game()` is
  the B1 fix: our colour to move → position+go fires automatically
  (IDLE → OUR_SEARCH); opp first → sends nothing. bestmove path: stale →
  STALE_BESTMOVE sink only (CF-7); `(none)` → GAME_END + IDLE (§7.2);
  current → validated against the replica BEFORE display, illegal → FAULT
  record + loud message, never announced, never pushed (T-02-07); legal →
  pushed + announced + MOVE_LOGGED(src=search) with captured
  depth/nodes/score/engine_ms/pv. Resync = replay-last-N through the legal
  gate on a FRESH BoardState + explicit `y` confirmation (PROTO-07,
  T-02-10 — no free-FEN path exists). §2.3 option set queued, flushed once
  at IDLE. Ponder machinery table-visible: `enter_pondering` (go ponder §3.5),
  miss → stop + mark_discarding → owed bestmove consumed + sunk → real
  position+go; `ponderhit` path raises NotImplementedError (Phase 5).
- `console/src/console/ui/loop.py` — `OperatorLoop`: select-on-stdin
  (0.05 s tick) + non-blocking queue drain; ANNOUNCE appears while the
  operator sits at the prompt. Echo contract (PROTO-06): `E7-E5  FEN: …`
  instantly on accept, `REJECTED <kind>: <reason>` instantly on reject,
  `>> ANNOUNCE:` only from bestmove (PV renders via the `  PV:` callback,
  never the announce buffer — Pitfall 5). Paste tolerance: one line,
  stripped, whitespace-collapsed, 32-char bound. Commands: `t <time>`
  (M:SS/H:MM:SS/M.SS; bare digits echo the seconds interpretation and
  journal raw+parsed_ms as OPP_CLOCK — never silent guessing),
  `r <N>`/`resync <N>` + `y`, `u` undo, `q`/EOF clean shutdown
  (stop-if-searching then close, §1.5 order).
- `console/src/console/main.py` — game mode wired: `--engine`,
  `--engine-arg`, `--our-color` (default w), `--clock-ms` (repeatable
  `w=600000,b=600000` verbatim passthrough; Phase 3 ClockModel replaces),
  `--transport-smoke` retained. Startup order: handshake → §2.3 flush at
  IDLE → `session.start_game()` → `OperatorLoop.run()`.
- `console/src/console/transport/uci.py` — one added kwarg: optional
  `cwd` for the engine Popen (Python mock scripts resolve repo-relative
  paths from any caller cwd). Transport discipline untouched.

## Requirements coverage

| Requirement | Evidence | Status |
|---|---|---|
| PROTO-01 strict parser | `game/moves.py` (RejectKind/operator_move/announce_form); six verified tokens in test_moves (`0000`, `E2E4`, `Nf3`, `O-O`, `e2-e4`, `e2e5`) + spaces + promotion ambiguity; every reject carries raw+kind (REJECT records) | Complete |
| PROTO-02 replica + position lines | `game/board.py`; replay agreement with independent `chess.Board`; position_line round-trips through mock_engine (engine survives, ply-parity answer matches); move_no/side vs mock_gui formula `(len(moves)+2)//2` | Complete |
| PROTO-03 announce from bestmove only | `session._on_bestmove` sole ANNOUNCE writer; PV-never-ANNOUNCE test (info event with pv → announce list stays empty); announce_form uppercase hyphenated | Complete |
| PROTO-04 stale bestmove discarded | CF-7: test_ponder_discard.py committed in Task 1 (2c157b2f) BEFORE the handler (3421e8aa) — git-history order proves test-first; three orderings (late / post-stop / unconsumed) green at transport + session levels; mock --stale-bestmove → FAULT-not-announced | Complete |
| PROTO-05 side-to-move guard | `on_operator_move` guard on `board.turn`; both directions tested; two consecutive opp moves structurally impossible (second is wrong-side) | Complete |
| PROTO-06 operator loop | `ui/loop.py` select-based (no blocking input()); piped smoke: `printf 'e2e4\nt 7:42\nq\n' \| … --our-color b` → FEN echo, LOOP_OK, exits 0 well under 60 s; typed rejects instant; ANNOUNCE-while-idle liveness test | Complete |
| PROTO-07 resync by replay | `request_resync`/`confirm_resync`: fresh BoardState, legal-gate re-entry, explicit confirmation gate (unconfirmed/wrong-N applies nothing), RESYNC records; no FEN-edit command exists | Complete |

human_judgment items: none declared by the plan's frontmatter (all
deliverables above have automated evidence).

## Red-state evidence (CF-7, Task 1)

`console/tests/test_ponder_discard.py` was written and run BEFORE any
session handler existed:

```
ERROR: test_ponder_discard (unittest.loader._FailedTest.test_ponder_discard)
ImportError: Failed to import test module: test_ponder_discard
ModuleNotFoundError: No module named 'console.game'
Ran 1 test in 0.000s
FAILED (errors=1)   # rc=1
```

Commit order in git history: test file in Task 1's commit (2c157b2f),
session handler in Task 2's (3421e8aa). Three session-level cases were
skip-guarded during Task 1 (`skipUnless(Session is not None …)`), unskipped
automatically when Task 2 landed the handler — documented interpretation of
the plan's Task-1-verify-vs-session-level-cases wrinkle (verify greps for
`stale` ≥ 3 and runs the suite; the suite passes with 3 skips at Task 1,
7/7 at Task 2).

## Verification (plan-level, all green)

- `PYTHONPATH=vendor:console/src python3 -m unittest discover -s console/tests -t .` → `Ran 52 tests … OK`
- `python3 -m unittest tools.tests.test_contract -v` → `Ran 19 tests … OK`
- Piped smoke: `printf 'e2e4\nt 7:42\nq\n' | PYTHONPATH=vendor:console/src
  python3 -m console.main --engine tools/mock_engine.py --our-color b
  --clock-ms w=600000,b=600000 | grep -q 'FEN:' && echo LOOP_OK` →
  `LOOP_OK`, rc=0 (well under the 60 s cap).
- Per-task suites: test_moves + test_board 18/18; test_session 18/18;
  test_ponder_discard 7/7 (orderings late/post-stop/unconsumed all named
  and passing).

## Deviations and interpretation notes

1. **Session-level ponder tests skip-guarded in Task 1, unskipped in
   Task 2** (plan wrinkle: Task 1's verify demands the ponder suite green
   while two of its cases need `Session`). Documented above; the red-first
   gate itself was satisfied by the import error, no test was weakened.
2. **Bestmove pushes the replica immediately** (plan text said "never
   pushed" for the illegal case only). Interpretation: a legal current
   bestmove is validated, pushed, announced, and logged at once — the
   operator then plays it physically and confirms (`y` →
   AWAIT_OPP_CONFIRM). This keeps `board.turn` truthful for the guard and
   keeps the replica the single authority (§1.6); the alternative
   (announce-without-push) would let the next typed move hit a stale
   guard.
3. **`main.py` --ply-limit flag from the plan's artifact list was not
   added**: it belongs to 02-03's e2e (`--max-plies` there); adding an
   unused flag now would be dead surface. Recorded for the checker.
4. **`EngineTransport` gained an optional `cwd` kwarg** (backwards-
   compatible): the mock engine is a Python script needing repo-relative
   resolution from any caller cwd. No behaviour change for existing
   callers.
5. **`--transport-smoke` retains its real-binary probes unchanged** — the
   worktree has no `src/stockfish` binary, so the smoke was exercised on
   the mock up to the illegal-position probe (which by design hardcodes
   `./src/stockfish`). The piped interactive smoke (this plan's Task 3
   gate) runs fully on the mock and is green.

## Threat model dispositions (all mitigated as planned)

- T-02-05 paste/SAN execution → single-line reads, 32-char bound,
  whitespace collapse, SAN → MALFORMED (never parse_san).
- T-02-06 stale ponder bestmove → test-first suite + search_id/discard
  machinery (transport, 02-01) + session sink; all three orderings green.
- T-02-07 illegal bestmove → validated against the replica BEFORE display;
  FAULT record, never announced, never pushed; second independent check is
  the legality gate before every position send (position_line is the only
  producer).
- T-02-08 silent rejects → every reject emits a REJECT sink record with
  raw + kind (02-03 journals them).
- T-02-09 info flood → reader thread → queue → select-poll loop; prompt
  latency independent of nps (liveness test green).
- T-02-10 free-FEN resync → replay-last-N through the legal gate +
  explicit confirmation; no FEN edit path exists in the command set.
- T-02-SC installs → none: stdlib + vendored `chess` only (imports in new
  files: enum, re, select, sys, time, os, json, queue, pathlib, unittest,
  chess).

## Handoff to 02-03

- Event vocabulary frozen as implemented: `GAME_START, MOVE_LOGGED,
  REJECT, STALE_BESTMOVE, OPP_CLOCK, RESYNC, ENGINE_FAULT, FAULT,
  GAME_END` (FAULT = illegal engine bestmove; ENGINE_FAULT = engine
  eof/timeout/garbage — 02-03 journals both, Phase 3 may merge).
- Sink interface: `Session(sink=callable(dict))` — pass `journal.append`.
- MOVE_LOGGED carries: `src` (opp|search), `move_no`, `side`, `uci` (+ for
  src=search: `depth`, `nodes`, `score`, `engine_ms`, `pv`).
- OPP_CLOCK carries `raw` + `parsed_ms`. RESYNC carries `phase`
  (requested|applied) + FENs. GAME_END carries `reason`.
- `main.py` wiring point for `--log-dir`: construct the Journal in
  `run_game` and pass `journal.append` as `sink` (currently a no-op
  lambda).
- Loop's `t` command already routes to `session.on_opp_clock` — the
  journal half of PROTO-08 is a sink wiring away.

## Self-Check: PASSED

- All 3 tasks committed atomically (feat(02-02) × 3, no backticks, files
  staged individually).
- Plan-level verification commands all green (52 + 19 tests, LOOP_OK).
- CF-7 test-first proven by commit order + red-state transcript above.
- `--our-color b` piped smoke green (iteration 3 fix honored: with w the
  B1 trigger would auto-fire search #1 and reject the typed e2e4).
- No `.planning/STATE.md`/`ROADMAP.md` writes (orchestrator owns them).
- Estimated tokens consciously exceeded (120k → ~499k realized chars/4):
  FSM + loop + test-first suite in one critical path; no scope shaved —
  all three tasks delivered complete per acceptance criteria.
