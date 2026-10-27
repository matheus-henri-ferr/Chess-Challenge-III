---
phase: 02-console-protocol-spine
verified: 2026-10-27T23:19:44Z
status: gaps_found
score: 5/8 must-haves verified
covered_files:
  - .planning/phases/02-console-protocol-spine/02-01-PLAN.md
  - .planning/phases/02-console-protocol-spine/02-01-SUMMARY.md
  - .planning/phases/02-console-protocol-spine/02-02-PLAN.md
  - .planning/phases/02-console-protocol-spine/02-02-SUMMARY.md
  - .planning/phases/02-console-protocol-spine/02-03-PLAN.md
  - .planning/phases/02-console-protocol-spine/02-03-SUMMARY.md
  - console/src/console/__init__.py
  - console/src/console/engine/session.py
  - console/src/console/game/board.py
  - console/src/console/game/journal.py
  - console/src/console/game/moves.py
  - console/src/console/log/lint.py
  - console/src/console/log/movelog.py
  - console/src/console/main.py
  - console/src/console/transport/parser.py
  - console/src/console/transport/uci.py
  - console/src/console/ui/loop.py
  - console/tests/fixtures/golden-game.log
  - console/tests/test_board.py
  - console/tests/test_e2e_fullgame.py
  - console/tests/test_journal.py
  - console/tests/test_movelog.py
  - console/tests/test_moves.py
  - console/tests/test_ponder_discard.py
  - console/tests/test_session.py
  - console/tests/test_transport.py
  - evidence/02-wire-spike.log
  - tools/mock_none_engine.py
  - tools/tests/test_contract.py
covered_digest: "v4:sha256:1289aa09cdbb6e60b6cd1bb191d14dd09c94c75ab63b55bb1d0ea9d12f0daab1"
behavior_unverified: 0
overrides_applied: 0
gaps:
  - truth: "The operator can realign the replica with `u` (undo) mid-game without the console dying — Rule 10 realignment must be possible without restart, and the prompt must never die under the operator"
    status: failed
    reason: "CR-01 (critical, reproduced live by this verification): undo during OUR_SEARCH leaves the interrupted search's go outstanding; the next corrected opp-move re-entry calls _start_search() which raises RuntimeError (§1.3), uncaught by handle_line/run — the console exits mid-game. `u` also emits no journal record (journal replay diverges from the live move list) and can leave last_announced pointing at a removed move."
    artifacts:
      - path: console/src/console/ui/loop.py
        issue: "lines 119-125: `u` calls session.board.pop() directly — no FSM repair, no transport interaction, no sink record"
      - path: console/src/console/engine/session.py
        issue: "no session-owned undo path; on_operator_move → _start_search() raises when transport.outstanding is set"
    missing:
      - "Session.undo_last_ply(): pop, then if transport.outstanding is not None send stop + mark_discarding + consume the owed bestmove; reset last_announced/discarding; re-derive state from board.expected_mover(); emit a RESYNC/undo journal record"
      - "Route the loop's `u` through that method; add a regression test for undo-during-search"
  - truth: "score_white is a correct White-POV normalisation of the STM-POV score (LOGBOOK §2.1)"
    status: failed
    reason: "CR-02 (high, reproduced live): score_white_of('cp -30', side='w') returns 'cp 30' — a white-mover negative score is already White-POV-negative and must stay -30. Every 'we are worse' white row in the graded artefact carries a sign-flipped score_white; log_lint never checks the value, so nothing downstream catches it. test_movelog only exercises side=None and side='b', masking the live path."
    artifacts:
      - path: console/src/console/log/movelog.py
        issue: "lines 70-73: `elif value < 0: value = -value` branch inverts the sign for white-mover rows"
    missing:
      - "Negate only when side == 'b'; delete the `elif value < 0` branch"
      - "Regression tests: white row cp -30 → cp -30; black row cp -30 → cp 30"
  - truth: "A valid log from a game where we play black (our-color b, white moves first) passes log_lint — the fail-closed linter must not fail a correct log"
    status: failed
    reason: "CR-03 (high, reproduced live): lint_log seeds side alternation from header our-color, but our-color is the console's colour, not the game's first mover (always white). A black-side log's first row is side=w and fails alternation, cascading to every odd row. ~50% of real games produce logs that fail the linter. Both e2e tests run our-color=w only, so the suite cannot see it."
    artifacts:
      - path: console/src/console/log/lint.py
        issue: "lines 85-86: first_mover = header.get('our-color', 'w') conflates console colour with first mover"
    missing:
      - "Seed expect_side = 'w' unconditionally (chess: white always moves first, LOGBOOK §1.4)"
      - "An e2e or lint test with '# our-color b' and a white-first row"
  - truth: "The .log header/trailer tell the truth about the run that produced them"
    status: failed
    reason: "CR-04 (high): GameTracer._write_log — the only Phase 2 log producer — hardcodes '# time-control 15+10' regardless of --clock-ms (the e2e itself runs w=60000,b=60000 and logs 15+10), writes the INITIAL passthrough clocks as '# final-clocks' (never observed remaining time), and emits a 12-char net-sha256 prefix with prose, inconsistent with the §5.1 sha256 contract. The committed golden fixture carries all three falsifications."
    artifacts:
      - path: console/src/console/main.py
        issue: "lines 570, 574-575, 586-587: hardcoded time-control, initial clocks as final, abbreviated net hash; bypasses MoveLog.write_header/write_trailer"
    missing:
      - "Record the actual time-control from --clock-ms; either track observed end-of-game clocks or label the passthrough honestly (full observed clocks are CLOCK-08/Phase 3)"
      - "Use MoveLog.write_header/write_trailer (or match their parameter contract) and decide the net-sha256 format (full hash, or a dated LOGBOOK revision blessing the prefix form)"
deferred:
  - truth: "PROTO-07's 'RESYNC anexado ao journal e ao log' log-file half (reserved-prefix non-move line)"
    addressed_in: "Phase 3"
    evidence: "Plan 02-03 Task 1 + research Open Question #2 decision: Phase 2 journals RESYNC records; the Phase-3 LOGBOOK amendment bundle owns the '# RESYNC …' log representation that log_lint skips (skip already implemented and tested in lint.py)"
  - truth: "PROTO-08's log-file half (OPP_CLOCK representation in the .log)"
    addressed_in: "Phase 3"
    evidence: "Plan 02-03 + research Open Question #1 decision: OPP_CLOCK lands in the journal with raw + parsed_ms (verified); the log-side representation defers to the Phase-3 amendment bundle"
  - truth: "Trailer with result, reason and BOTH final observed clocks (CLOCK-08 territory inside CR-04)"
    addressed_in: "Phase 3"
    evidence: "REQUIREMENTS.md CLOCK-08 (Phase 3): 'Resultado, motivo e ambos os relógios no instante do término são registrados'; LOG-05 (Phase 3) owns the export header/trailer. The Phase-2 half of CR-04 (stop writing initial values as final; stop hardcoding time-control) stays a gap above"
---

# Phase 2: Console Protocol Spine — Verification Report

**Phase Goal:** A complete game can be played through the console against stock Stockfish, with every half-move logged in the Rule 9 schema and no illegal move — theirs or the engine's — ever reaching the board replica.
**Verified:** 2026-10-27T23:19:44Z
**Status:** gaps_found
**Re-verification:** No — initial verification

**MVP-mode note:** ROADMAP marks Phase 2 `Mode: mvp`, but the phase goal is an outcome statement, not a User Story (`user-story.validate` → invalid: no "As a…, I want…, so that…" shape). Per the plans' own user stories (console / operator / team), the outcome clause was verified goal-backward: complete game played ✓, every half-move logged ✓ (with CR-02/CR-04 field defects), no illegal move reaching the replica ✓. If the milestone wants the formal MVP User Flow Coverage format, run `/gsd-mvp-phase 2` to set a User Story goal and re-verify.

## Goal Achievement

### Observable Truths

| #   | Truth   | Status     | Evidence       |
| --- | ------- | ---------- | -------------- |
| 1   | SC1 — `Nf3`/`0000`/malformed tokens: typed error, prompt alive, reason echoed, REJECT evidence record, clock untouched | ✓ VERIFIED | test_moves 8 tests + test_session LoopTests; piped smoke run by this verification: `e2e4 / t 7:42 / q` → FEN echo + OPP_CLOCK, rc=0; rejects never touch clock state (session code path: reject → emit + display, return before any send) |
| 2   | SC2 — legal move advances replica, FEN echo matches, half-move in the log with all fields | ✓ VERIFIED | piped smoke `E2-E4  FEN: rnbq…` (run live); golden log: 18 rows, 11 keys each; test_board replay-agreement + mock_gui formula cross-check |
| 3   | SC3 — ANNOUNCE blank until bestmove, uppercase hyphenated, PV never leaks into it | ✓ VERIFIED | Live probe this verification: mock game → exactly `E2-E4` on bestmove, PV events flowed without writing ANNOUNCE; PvNeverAnnounceTests + announce_form tests |
| 4   | SC4 — ponder miss: no board advance, no state change, STALE_BESTMOVE journal record, test written BEFORE the handler | ✓ VERIFIED | test_ponder_discard 7/7 (three orderings, transport + session levels); commit order verified via git: test in 2c157b2f, handler in 3421e8aa |
| 5   | SC5 — full game vs stock Stockfish → log_lint zero missing fields, incl. opponent half-moves and terminal moves | ✓ VERIFIED (our-color=w games) | Full console suite run by this verification: 83/83 OK incl. real-SF e2e (12 plies) and mock terminal-row game; golden log lint CLI → `OK LOG_LINT`; `src=opp` rows present. Caveat: CR-03 means black-side games fail lint — scored as truth #8 |
| 6   | Operator realignment `u` mid-game without the console dying (Rule 10) | ✗ FAILED | CR-01 reproduced live in-process: undo with a go outstanding → next `on_operator_move` raises uncaught RuntimeError → console exits mid-game |
| 7   | score_white is a correct White-POV normalisation (LOGBOOK §2.1) | ✗ FAILED | Live probe: `score_white_of('cp -30', 'w') → 'cp 30'` (must stay −30) |
| 8   | log_lint certifies any valid log (both colours) and the header/trailer tell the truth | ✗ FAILED | Live probe: black-side log (`# our-color b`, white-first rows) → `FAIL line 1: side w breaks w/b alternation`, rc=1; CR-04 hardcoded time-control/initial-clocks falsifications confirmed by source read of main.py:570/586-587 |

**Score:** 5/8 truths verified (0 present, behavior-unverified)

### Deferred Items

| # | Item | Addressed In | Evidence |
|---|------|-------------|----------|
| 1 | PROTO-07 log-file `# RESYNC …` representation | Phase 3 | Plan 02-03 OQ#2 disposition; lint reserved-prefix skip already implemented + tested |
| 2 | PROTO-08 log-file OPP_CLOCK representation | Phase 3 | Plan 02-03 OQ#1 disposition; journal half verified |
| 3 | Observed final clocks in the trailer | Phase 3 | CLOCK-08 + LOG-05 own end-of-game clocks and export trailer |

### Advisory (New Scope, Unevidenced)

Not applicable — initial verification, no re-verification round.

### Required Artifacts

| Artifact | Expected    | Status | Details |
| -------- | ----------- | ------ | ------- |
| `console/src/console/transport/uci.py` | EngineTransport: framing, reader thread, search_id, discarding, option queue, stderr drain, frozen go builders | ✓ VERIFIED | 344 lines; §1.3 raise, §1.4 IDLE-only flush, §2.1 handshake deadline all present; tested by test_transport 9 tests; contract-tested 3-way go agreement |
| `console/src/console/transport/parser.py` | Whitelisted line→event parser, bestmove_of | ✓ VERIFIED | Token-walk, no whole-line regex; `time` stays wire ms; garbage inert; wired into reader loop |
| `console/src/console/game/moves.py` | Typed-reject layer (RejectKind/operator_move/announce_form) | ✓ VERIFIED | 0000 guard before parse_uci; promotion ambiguity re-prompt; SAN never routed to parse_san |
| `console/src/console/game/board.py` | BoardState replica, position_line sole producer | ✓ VERIFIED | move_no/side captured before push; pop() realignment; wired into session + tracer |
| `console/src/console/engine/session.py` | Session FSM (6 states + DISCARDING), side guard, bestmove validation, start_game trigger, ponder machinery | ✓ VERIFIED | All states grep-verified; FAULT path tested; resync replay+confirmation tested; wired as main.py's game core |
| `console/src/console/ui/loop.py` | OperatorLoop: select-on-stdin + queue poll, echo contract, commands | ✓ VERIFIED | select + 0.05 tick; 32-char paste bound; t/r/u/q dispatch; **but `u` path carries CR-01** (scored as truth #6) |
| `console/src/console/game/journal.py` | Append-only fsync journal + replay | ✓ VERIFIED | O_APPEND+fsync per record; byte-prefix stability + kill-safety tests; replay reproduces FEN/moves incl. applied RESYNC |
| `console/src/console/log/movelog.py` | MoveLog projection, §3.1 order, SRC_SET, score_white | ✓ VERIFIED with defect | Pure fold from journal; key order contract-tested both directions; **score_white sign defect (CR-02)** scored as truth #7 |
| `console/src/console/log/lint.py` | Fail-closed log_lint + CLI | ✓ VERIFIED with defect | All checks named failures, no WARN tier, exit codes both ways tested; **alternation seed defect (CR-03)** scored as truth #8 |
| `console/src/console/main.py` | CLI wiring: game mode, --transport-smoke, --log-dir, tracer | ✓ VERIFIED with defect | Smoke rc=0 on real binary (re-run by this verification); journal writability probe; **tracer header/trailer falsifications (CR-04)** scored as truth #8 |
| `console/tests/*` (9 modules) | 83 tests: transport, moves, board, session, ponder-discard, journal, movelog, e2e | ✓ VERIFIED | Full discover run by this verification: `Ran 83 tests … OK` (67.8 s, incl. real-SF game) |
| `console/tests/fixtures/golden-game.log` | Committed real-SF log, lint-clean | ✓ VERIFIED | 26 lines, 12 search + 6 opp rows, header/trailer; lint OK. Carries CR-04's falsified header fields |
| `evidence/02-wire-spike.log` | Five wire facts on the competition binary | ✓ VERIFIED | Greps re-run: `bestmove (none)`, `CRITICAL ERROR`, frozen go literal — all present; smoke re-run rc=0 this session |
| `tools/tests/test_contract.py` | 19 tests incl. console↔doc↔mock go agreement + console source walk | ✓ VERIFIED | Re-run: `Ran 19 tests … OK`; `OK CONTRACT ORDER` re-run: freeze bd349ec3 ancestor of first implementation commit |

### Key Link Verification

| From | To  | Via | Status | Details |
| ---- | --- | --- | ------ | ------- |
| ui/loop.py | engine/session.py | on_engine_event / on_operator_move dispatch | WIRED | drain_events → session; handle_line → session paths |
| engine/session.py | transport/uci.py | start_search/send/mark_discarding/events | WIRED | start_game → position+go verified via mock --record transcript in GameStartTriggerTests |
| engine/session.py | game/journal.py | sink=journal.append in main.py run_game | WIRED | GAME_START/GAME_END in e2e journal assertions; test_journal replay-of-live-session-flow |
| game/board.py | engine position send | position_line() sole producer | WIRED | Session `_start_search` sends `self.board.position_line()`; no other position-line producer in console/src (grep) |
| log/movelog.py | game/journal.py | MoveLog.build folds journal records | WIRED | Tracer `_write_log` renders from `self._records()` (journal read-back) |
| log/lint.py | log file | lint_log replay through fresh chess.Board | WIRED | Golden log + failure fixtures; CLI tested both ways |
| main.py GameTracer | ui/loop.py | loop.run(tracer=) exit path | WIRED | tracer.finished checked in run(); stop() joins |
| transport GO_LITERAL | docs/PROTOCOL.md §3.1 + mock_engine | test_contract three-way agreement | WIRED | 19/19 contract tests green this verification |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
| -------- | ------------- | ------ | ------------------ | ------ |
| golden log search rows | depth/nodes/score/pv | live `info` lines from real SF19 (wire ms kept) | Yes (e2e real-engine run) | ✓ FLOWING |
| golden log opp rows | uci/wall_ms | feeder through the operator legality gate + monotonic delta | Yes | ✓ FLOWING |
| journal | every event | session sink, fsynced JSONL | Yes | ✓ FLOWING |
| log header `# time-control` / `# final-clocks` | clock values | hardcoded `15+10` / initial passthrough | No | ⚠️ STATIC (CR-04) |
| log `score_white` | score + side | computed, but sign rule wrong for white-negative rows | Partially | ⚠️ (CR-02) |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| -------- | ------- | ------ | ------ |
| Full console suite (incl. real-SF full game, 300 s budget) | `PYTHONPATH=vendor:console/src python3 -m unittest discover -s console/tests -t .` | `Ran 83 tests in 67.831s … OK` | ✓ PASS |
| Contract suite + freeze-order | `python3 -m unittest tools.tests.test_contract` / `python3 tools/check_contract_order.py` | 19 OK / `OK CONTRACT ORDER` | ✓ PASS |
| Golden log lint + opp rows | `python3 -m console.log.lint console/tests/fixtures/golden-game.log`; `grep -q 'src=opp' …` | `OK LOG_LINT` rc=0 / match | ✓ PASS |
| Transport smoke on real binary | `python3 -m console.main --transport-smoke --engine ./src/stockfish --record …` | `OK transport smoke: 5 wire facts confirmed`, rc=0 | ✓ PASS |
| Piped interactive smoke | `printf 'e2e4\nt 7:42\nq\n' \| … console.main --engine tools/mock_engine.py --our-color b …` | rc=0, `E2-E4  FEN: rnbq…` echo, OPP_CLOCK | ✓ PASS |
| CR-02 sign probe | `score_white_of('cp -30', 'w')` | `cp 30` (must be `cp -30`) | ✗ FAIL |
| CR-03 black-side lint probe | lint a valid `# our-color b` white-first log | `FAIL … side w breaks w/b alternation`, rc=1 | ✗ FAIL |
| CR-01 undo-during-search repro | in-process: opp move pushed, go outstanding, `board.pop()`, corrected `on_operator_move` | `RuntimeError: start_search with a go outstanding (PROTOCOL §1.3)` uncaught | ✗ FAIL |

### Probe Execution

No `scripts/*/tests/probe-*.sh` probes declared for this phase; the behavioral spot-checks above cover the runnable verification surface (transport smoke = the phase's own probe command, re-run independently by this verifier).

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
| ----------- | ---------- | ----------- | ------ | -------- |
| PROTO-01 | 02-02 | Strict UCI parser, typed rejects, rejected tokens logged | ✓ SATISFIED | moves.py; test_moves matrix (0000/E2E4/Nf3/O-O/e2-e4/e2e5 + spaces + promo ambiguity); REJECT sink records |
| PROTO-02 | 02-02 | Board replica, validated-only advance, both sides | ✓ SATISFIED | board.py; replay agreement; position_line sole producer; guard substrate |
| PROTO-03 | 02-02 | Illegal announced move never advances state; illegal bestmove never displayed | ✓ SATISFIED | FAULT path + IllegalBestmoveFaultTests (e2e5 → FAULT, no announce, no push); legality gate both directions |
| PROTO-04 | 02-01, 02-02 | ANNOUNCE exclusively from bestmove (REQUIREMENTS wording); plan 02-01 additionally mapped wire-discipline (frozen go, stale discard, IDLE-only options) here | ✓ SATISFIED | ANNOUNCE: sole writer `_on_bestmove`, PvNeverAnnounceTests, live probe. Wire discipline: test_transport 9 + contract 19 |
| PROTO-05 | 02-02 | Explicit FSM + side-to-move guard | ✓ SATISFIED | All 6 states + DISCARDING present; TransitionTableTests data-driven rows; guard both directions |
| PROTO-06 | 02-02 | Keyboard-only, paste-tolerant, instant echo, reject cue | ✓ SATISFIED | select-based loop, 32-char bound, instant FEN echo, REJECTED lines; piped smoke green. Caveat: CR-01 kills the console on the `u`-during-search path (scored as truth #6) |
| PROTO-07 | 02-02, 02-03 | Resync by replay-last-N with confirmation; journal record | ✓ SATISFIED (Phase-2 scope) | request/confirm_resync tested incl. gate + range; RESYNC journaled; replay honours applied RESYNC. Log half deferred Phase 3 |
| PROTO-08 | 02-03 | Opponent clock via `t`, alternate formats, stored in journal | ✓ SATISFIED (Phase-2 scope) | parse_clock_token M:SS/H:MM:SS/M.SS/bare; OPP_CLOCK with raw+parsed_ms in journal (piped smoke + test). Log half deferred Phase 3 |
| LOG-01 | 02-03 | One .log per game, all fields per half-move incl. opponent | ✓ SATISFIED | Golden log + e2e: 11 keys per row, 6 src=opp rows, fsync journal is the single source |
| LOG-02 | 02-03 | Eight fields, score verbatim incl. mate N and bound flags | ⚠️ PARTIAL | score verbatim ✓ (bound flags round-trip tested); **score_white sign wrong for white-negative rows (CR-02 — gap #2)** |
| LOG-03 | 02-03 | engine_ms (wire) AND wall_ms (monotonic), wall ≥ engine | ✓ SATISFIED | Write-time floor+assert; lint re-check; e2e asserts per row |
| LOG-04 | 02-03 | Book rows src=book d=0 n=0; terminal rows non-empty | ✓ SATISFIED (Phase-2 scope) | Terminal: mock --none-bestmove game → src=none row, lint-clean (test green in suite). Book moves do not occur in Phase 2 (book-hash none placeholder; SRC_SET carries book for Phase 3) |

All 12 requirement IDs declared across the three plans (02-01: PROTO-04; 02-02: PROTO-01..07; 02-03: PROTO-08, LOG-01..04) map to Phase 2 in REQUIREMENTS.md traceability. No orphaned Phase-2 requirements. Note: the per-ID content mapping in the plan summaries is shifted one slot for PROTO-03/PROTO-04 relative to REQUIREMENTS.md wording (PROTO-03 row describes announce-only-from-bestmove; PROTO-04 row describes stale-bestmove discard). Both underlying behaviours — illegal bestmove never displayed, and ANNOUNCE exclusively from bestmove — are implemented and tested, so both requirements are met regardless of which summary row carries the label.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| ---- | ---- | ------- | -------- | ------ |
| (none) | — | No TBD/FIXME/XXX/HACK/PLACEHOLDER markers in console/src or touched tooling (grep rc=1) | — | — |

Open code-review ledger (02-REVIEW-DISPOSITION.md, all `open`): 1 critical + 3 high are scored above as gaps (CR-01..04). The remaining 10 medium (CR-05..CR-14) and 8 low (IN-01..08) findings do not block the five roadmap success criteria on the paths they exercise — notable ones for Phase 3 planning: CR-06 (swallowed assert can silently drop a journal row when a lying peer reports engine_ms > wall_ms), CR-10 (bare `except Exception` in drain_events), CR-11 (short-write torn JSON line in the journal), CR-12 (`SyzygyPath <empty>` placeholder sent every game), CR-13 (lint never cross-checks `side` against the replayed board's turn — a fabricated-but-alternating side column passes). None of these is exercised by a passing Phase 2 game, but CR-06/CR-10/CR-11 are fail-silent paths in the graded-artefact pipeline and should be folded into the Phase 3 plan rather than forgotten.

### Human Verification Required

Automated evidence covers all five roadmap success criteria for our-color=w games. Residual items that only a human at the terminal can confirm (do not block — the phase already carries blocking gaps):

1. **Interactive feel of the spine** — run a live session against `./src/stockfish`: type a wrong-side move, watch ANNOUNCE appear while idle at the prompt, confirm `>> ANNOUNCE:` reads as visually distinct from `  PV:` lines, and confirm the reject cue is noticeable under time pressure.
   - Why human: rendering prominence and operator ergonomics are not grep-able.

### Gaps Summary

The spine is real and largely proven: all five roadmap success criteria pass for white-side games on the exact frozen contract — 83/83 console tests green including a real-SF 12-ply game whose log lints clean, the five wire facts re-confirmed on the competition binary this session, the CF-7 test-first gate honoured (commit order verified), and the journal/projection/linter architecture is genuinely fail-closed in structure.

Four defects block the goal as stated:

1. **CR-01 (critical)** — `u` during an active search crashes the console (reproduced live). The goal's "no illegal move ever reaching the replica" survives, but "a complete game can be played" does not: a single operator undo mid-search ends the game. This is the primary operator realignment path Rule 10 mandates.
2. **CR-02 (high)** — `score_white` sign inverted for white-mover negative scores in the graded artefact; deterministic, lint-blind (reproduced live).
3. **CR-03 (high)** — every black-side game's valid log fails the fail-closed linter (reproduced live); both e2e tests run white only, which is exactly why the suite is green.
4. **CR-04 (high)** — the only Phase 2 log producer hardcodes the time-control and writes initial clocks as final clocks; the committed golden fixture carries these falsifications (Phase 3's CLOCK-08/LOG-05 own the full observed-clock treatment, but the Phase 2 artefact must at minimum stop lying about the current run).

Grouped root cause: CR-02/CR-03/CR-04 are all "the log is produced and checked, but its field semantics were only ever exercised through one colour/one shape" — a single focused gap-closure plan (fix score_white_of sign rule, lint alternation seed, tracer header/trailer truthfulness, plus black-side e2e coverage) closes three of the four. CR-01 needs a session-owned undo with §1.3 repair and a journal record, plus a regression test.

All four are structured in the frontmatter `gaps:` block for `/gsd-plan-phase --gaps`.

---

_Verified: 2026-10-27T23:19:44Z_
_Verifier: the agent (gsd-verifier)_
