---
phase: 02-console-protocol-spine
verified: 2026-10-28T18:06:01Z
status: human_needed
score: 8/8 must-haves verified
covered_files:
  - .planning/phases/02-console-protocol-spine/02-01-PLAN.md
  - .planning/phases/02-console-protocol-spine/02-01-SUMMARY.md
  - .planning/phases/02-console-protocol-spine/02-02-PLAN.md
  - .planning/phases/02-console-protocol-spine/02-02-SUMMARY.md
  - .planning/phases/02-console-protocol-spine/02-03-PLAN.md
  - .planning/phases/02-console-protocol-spine/02-03-SUMMARY.md
  - .planning/phases/02-console-protocol-spine/02-04-PLAN.md
  - .planning/phases/02-console-protocol-spine/02-04-SUMMARY.md
  - .planning/phases/02-console-protocol-spine/02-05-PLAN.md
  - .planning/phases/02-console-protocol-spine/02-05-SUMMARY.md
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
covered_digest: "v4:sha256:89ddadae51873bb425ad40ea59dd94655cb83b46b27be4dbd24cbc5602a047f2"
behavior_unverified: 0
overrides_applied: 0
re_verification:
  previous_status: gaps_found
  previous_score: 7/8
  gaps_closed:
    - "The prompt survives every operator input — including undo while the engine is dead or dies mid-repair (PROTOCOL §9.2); the console must never exit from an operator-initiated realignment"
  gaps_remaining: []
  regressions: []
deferred:
  - truth: "PROTO-07's 'RESYNC anexado ao journal e ao log' log-file half (reserved-prefix non-move line)"
    addressed_in: "Phase 3"
    evidence: "Plan 02-03 Task 1 + research Open Question #2 decision: Phase 2 journals RESYNC records; the Phase-3 LOGBOOK amendment bundle owns the '# RESYNC …' log representation that log_lint skips (skip implemented and tested in lint.py). GAP-REVIEW L-3 adds the corollary: a rendered log containing an interactive undo fails lint (double row) — same Phase-3 bundle"
  - truth: "PROTO-08's log-file half (OPP_CLOCK representation in the .log)"
    addressed_in: "Phase 3"
    evidence: "Plan 02-03 + research Open Question #1 decision: OPP_CLOCK lands in the journal with raw + parsed_ms (re-verified live this round: journal line 4 = {\"e\":\"OPP_CLOCK\",\"raw\":\"7:42\",\"parsed_ms\":462000}); the log-side representation defers to the Phase-3 amendment bundle"
  - truth: "Trailer with result, reason and BOTH final observed clocks (CLOCK-08 territory inside CR-04)"
    addressed_in: "Phase 3"
    evidence: "REQUIREMENTS.md CLOCK-08 (Phase 3): 'Resultado, motivo e ambos os relógios no instante do término são registrados'; LOG-05 (Phase 3) owns the export header/trailer. Phase-2 half of CR-04 closed: the passthrough values are now honestly labelled ('# final-clocks-note initial clock passthrough values, not observed remaining (observed clocks land in Phase 3, CLOCK-08)')"
  - truth: "# time-control carries the frozen 10 s increment (M-2): the header logs the base budget only (15+10 logs '15+0'; 1+0.1 logs '1+0')"
    addressed_in: "Phase 3"
    evidence: "Phase-3 CLOCK/LOGBOOK amendment bundle: format_time_control (main.py:182-190) derives M+S from --clock-ms but the frozen §3.1 go literal (uci.py:50: winc 10000 binc 10000) hardwires the increment. Fix = add the frozen constant to the seconds part (or import it next to GO_LITERAL); update golden fixture + e2e pins. Human-deferred per the orchestrator's disposition (frozen-contract increment handling is a Phase-3 LOGBOOK bundle item alongside CLOCK-08)"
---

# Phase 2: Console Protocol Spine — Verification Report

**Phase Goal:** A complete game can be played through the console against stock Stockfish, with every half-move logged in the Rule 9 schema and no illegal move — theirs or the engine's — ever reaching the board replica.
**Verified:** 2026-10-28T18:06:01Z
**Status:** human_needed
**Re-verification:** Yes (round 2) — after gap closure (plan 02-06, commits 5e4a7305..ea570162, merged 0f39849c)

**MVP-mode note (unchanged from the initial round):** ROADMAP marks Phase 2 `Mode: mvp`, but the phase goal is an outcome statement, not a User Story (`user-story.validate` re-run this round → invalid: no "As a…, I want…, so that…" shape). The outcome clause is verified goal-backward: complete game played ✓, every half-move logged ✓ (field defects CR-02/CR-04 now fixed), no illegal move reaching the replica ✓.

## Goal Achievement

### Observable Truths

| #   | Truth   | Status     | Evidence       |
| --- | ------- | ---------- | -------------- |
| 1   | SC1 — `Nf3`/`0000`/malformed tokens: typed error, prompt alive, reason echoed, REJECT evidence record, clock untouched | ✓ VERIFIED | Regression: full console suite re-run by this re-verification — `Ran 106 tests … OK` (128.8 s, incl. real-SF games); piped smoke re-run live (`e2e4 / t 7:42 / u / d2d4 / q`) → FEN echo + opp-clock + undone echo + corrected-move echo, rc=0; REJECT records in journal |
| 2   | SC2 — legal move advances replica, FEN echo matches, half-move in the log with all fields | ✓ VERIFIED | Piped smoke re-run live: `E2-E4  FEN: rnbq…` then `D2-D4  FEN: …3P4/…` after undo; golden log 18 rows × 11 keys; test_board replay agreement |
| 3   | SC3 — ANNOUNCE blank until bestmove, uppercase hyphenated, PV never leaks into it | ✓ VERIFIED (regression) | PvNeverAnnounceTests + announce_form tests green in the 106-test run; unchanged code path (no diff to announce logic this round) |
| 4   | SC4 — ponder miss: no board advance, no state change, STALE_BESTMOVE journal record, test written BEFORE the handler | ✓ VERIFIED (regression) | test_ponder_discard 7/7 green in the suite run; commit order previously verified via git (test 2c157b2f < handler 3421e8aa) |
| 5   | SC5 — full game vs stock Stockfish → log_lint zero missing fields, incl. opponent half-moves and terminal moves — for BOTH colours now | ✓ VERIFIED | e2e re-run by this re-verification: `Ran 5 tests … OK` (124 s) incl. `BlackSideFullGameTests.test_full_game_black_side_lint_clean_log` (real SF, our-color b, 12 rows, lint clean) and the white-side real-SF game; golden lint CLI re-run → `OK LOG_LINT` rc=0; live tracer run this round (`--auto-opp … --log-dir /tmp/opencode/xlog`) → `OK fullgame: 4 half-moves, lint clean`, rc=0 |
| 6   | Operator realignment `u` mid-game without the console dying (Rule 10) — CR-01 closure + H-1 engine-death edge (02-06) | ✓ VERIFIED | Happy path: in-process repro (round 1) + regression-pinned `UndoRealignmentTests` (5 tests). **H-1 edge re-verified LIVE this round with the real binary (`./src/stockfish`), all three death shapes:** (1) engine SIGKILLed mid-search, operator types `u` → stop-send RuntimeError caught → `ENGINE_FAULT: undo repair: stop send failed (RuntimeError('engine exited rc=-9'))`, undo returns `e2e4`, RESYNC(applied, plies=1, via=undo) journaled, replay FEN == live FEN, outstanding cleared, AWAIT_OPP_CONFIRM; (2) engine killed between stop and the owed bestmove → eof event journalled as evidence + `undo repair aborted` fault, both discarding mirrors clear; (3) dead at re-fire → `engine re-fire failed` fault, state IDLE. Zero exceptions escaped in all three; regression-pinned by `UndoPromptSurvivalTests` (3) + `LoopUndoSurvivalTests` (1) + the L-1-extended no-answer test, all green in the 31-test session suite and the 110-test full suite |
| 7   | score_white is a correct White-POV normalisation (LOGBOOK §2.1) — CR-02 closure | ✓ VERIFIED | Live probe re-run independently: `score_white_of('cp -30','w') → 'cp -30'`, `('cp -30','b') → 'cp 30'`, `('cp 30','b') → 'cp -30'`, mate + bound-flag + `-` cases all correct; build-path pin re-run live (`MoveLog.build` white row `score=cp -30 → score_white=cp -30`); `elif value < 0` branch gone (source read); `ScoreWhiteSignTests` (7) green |
| 8   | log_lint certifies any valid log (both colours) and the header/trailer tell the truth — CR-03/CR-04 closure, **minus two residual header falsehoods** | ✓ VERIFIED with residuals (M-2 deferred; H-1 is truth #6's edge) | CR-03: black-side lint probe re-run live (`# our-color b`, white-first row) → zero failures; control probe: black-first row STILL fails (`side b breaks w/b alternation`) — enforcement not weakened; BlackSideFullGameTests green. CR-04: golden fixture `# time-control 1+0` (matches its w=60000 run), full 64-hex `# net-sha256` (recomputed hash of the net file = the fixture value), honest `# final-clocks-note`, and `# log-sha256` independently recomputed = sha256 of the bytes preceding the line (MATCH). Live tracer run: `# setoption` shows the effective set incl. a validated `--syzygy-path`, `# time-control 10+0` from w=600000. **Residual M-2:** the frozen 10 s increment is omitted (`15+10` logs `15+0`) — deferred to Phase 3 per disposition, see deferred list |

**Score:** 8/8 truths verified (0 present, behavior-unverified)

**Score note (round 2):** the residual H-1 gap truth is closed — all three engine-death shapes on the undo path were re-verified LIVE this round against the real `./src/stockfish` binary through the real `EngineTransport`, each surviving with zero escaping exceptions, per-mode ENGINE_FAULT evidence, and the always-journalled RESYNC record. The gap is marked `resolved` in the frontmatter. Status moves to `human_needed` (not `passed`) solely for the operator-ergonomics items in Human Verification Required — interactive feel is not grep-able; no code defect remains.

### Gaps Closed This Round (was: initial-round gaps #6–#8)

| Gap | Fix | Independent evidence this round |
| --- | --- | ------------------------------- |
| CR-01 undo crash | `Session.undo_last_ply` (session.py:358) — pop → §1.3 repair (stop + mark_discarding + `_consume_owed_bestmove`, queue.Empty → ENGINE_FAULT) → state re-derivation → RESYNC(applied, plies=1, via=undo); loop `u` routed through it (loop.py:136-142, no `board.pop` left in loop.py) | In-process repro live: crash sequence now zero-exception; piped smoke `e2e4/t 7:42/u/d2d4/q` rc=0; `UndoRealignmentTests` 5/5; journal replay FEN == live FEN after undo |
| CR-02 score_white sign | Negate only `side == "b"`; `elif value < 0` deleted | Probe matrix live (w/b × cp ±30 × mate × bound flag × `-`); build-path pin live; 7 ScoreWhiteSignTests green |
| CR-03 lint alternation seed | `expect_side = "w"` unconditional (lint.py:91) | Black-side log lints clean (live); black-first still fails (live); `AlternationSeedTests` 2/2 + BlackSideFullGameTests (real SF, b) green |
| CR-04 header/trailer truth | Tracer routed through `MoveLog.write_header/write_trailer`; `format_time_control` from `--clock-ms`; honest final-clocks note; full 64-hex `net_sha256()` (recomputed = fixture value) | Golden fixture lint OK + digest independently recomputed MATCH; live tracer run shows effective option set, real time-control, note line; `TracerHeaderTruthTests` green; frozen docs diff `90368f13..HEAD -- docs/` EMPTY (freeze commit bd349ec3 untouched) |
| **H-1 undo prompt death on engine death (round-2 gap)** | `undo_last_ply` hardened (02-06): stop-send wrapped `except (RuntimeError, OSError)` (journal + clear outstanding + skip discard/consume); `_consume_owed_bestmove` handlers widened (queue.Empty clears both mirrors — L-1; RuntimeError/OSError journals the abort; eof evidence emitted before the raise; `finally` clears both discarding mirrors); re-fire `_start_search` guarded → IDLE; RESYNC moved after all guarded sections; loop `u` last-resort `try/except Exception` (journal + display + stdout fault line) | **LIVE this round, real binary, all three shapes:** (1) SIGKILL mid-search + `u` → fault `stop send failed (RuntimeError('engine exited rc=-9'))`, undo returns `e2e4`, RESYNC(applied) journaled, replay FEN == live FEN, AWAIT_OPP_CONFIRM; (2) kill between stop and owed bestmove → eof journalled as evidence + `undo repair aborted`, mirrors clear; (3) dead at re-fire → `engine re-fire failed`, IDLE. Regression-pinned: `UndoPromptSurvivalTests` 3/3, `LoopUndoSurvivalTests` 1/1, L-1 assertions in `test_a_undo_no_answer_to_stop_prompt_survives` — session suite 31/31, full suite 110/110 |

### Deferred Items

| # | Item | Addressed In | Evidence |
|---|------|-------------|----------|
| 1 | PROTO-07 log-file `# RESYNC …` representation (+ L-3: interactive-undo logs fail lint until the projection folds RESYNC) | Phase 3 | Plan 02-03 OQ#2 disposition; lint reserved-prefix skip implemented + tested; L-3 confirmed this round (replay board aligned, move_rows keep the phantom row) |
| 2 | PROTO-08 log-file OPP_CLOCK representation | Phase 3 | Plan 02-03 OQ#1 disposition; journal half re-verified live this round |
| 3 | Observed final clocks in the trailer | Phase 3 | CLOCK-08 + LOG-05; passthrough now honestly labelled (note line in fixture + live run) |
| 4 | `# time-control` increment (M-2): frozen winc/binc 10000 not reflected in the header | Phase 3 | GAP-REVIEW M-2 confirmed live: `format_time_control(900000,900000) → '15+0'`; the orchestrator's disposition files it with the Phase-3 LOGBOOK amendment bundle alongside CLOCK-08; honest-labelling mitigates (the go literal is printed and contract-pinned three ways) |

### Advisory (New Scope, Unevidenced)

Not applicable — re-verification round; all new-scope findings carry deterministic evidence (GAP-REVIEW findings, each re-verified live below).

### Required Artifacts

| Artifact | Expected    | Status | Details |
| -------- | ----------- | ------ | ------- |
| `console/src/console/engine/session.py` | Session FSM + `undo_last_ply` (§1.3 repair + RESYNC record) | ✓ VERIFIED | Round-2 diff: repair catches `(RuntimeError, OSError)` around the stop send (session.py:400), around `_consume_owed_bestmove` (422), and around the re-derivation/`_start_search` block (440); `queue.Empty` handler clears `transport.outstanding` + `transport.discarding` (L-1); `_consume_owed_bestmove` eof branch emits ENGINE_FAULT evidence before raising (513-518); RESYNC emit after all guarded sections (449-450) — reachable on every post-pop path. Confirmed by source read + live repro |
| `console/src/console/ui/loop.py` | `u` → session; drain_events guarded; piped `_read_line` buffer | ✓ VERIFIED | `u` branch now wrapped in `try/except Exception` with the CR-10 discipline — guarded-getattr sink journal with `traceback` field (loop.py:139-154), display_cb line, stdout fault notice; success-path echo byte-identical (`test_d_loop_routes_u_through_session` green); no `board.pop` in loop.py (grep rc=1); piped multiline regression green |
| `console/tests/test_session.py` | + `UndoPromptSurvivalTests`, `LoopUndoSurvivalTests`, L-1 fold | ✓ VERIFIED | 31 tests OK (re-run this round, 1.3 s); RED→GREEN commit order verified in git (test 5e4a7305 < feat 8b2d6776; test adcf45af < feat ea570162) |
| `console/src/console/game/journal.py` | Short-write loop + `JournalCorruptionError` | ✓ VERIFIED | memoryview completion loop before single fsync; corruption tests (short-write, torn line, replay propagation) green in the 110-run |
| `console/src/console/log/movelog.py` | score_white_of sign rule; write_trailer flush-before-digest | ✓ VERIFIED | Sign rule live-probed (`w,cp-30→cp -30`; `b,cp-30→cp 30`; `b,cp+30→cp -30`); `fh.flush()` before read-back — golden fixture digest recomputed MATCH |
| `console/src/console/log/lint.py` | Unconditional `"w"` alternation seed | ✓ VERIFIED | lint.py:91 (source re-read); black-side clean + black-first fails (both live probes re-run this round); L-4 dead code (`_parse_header` + `header` assignment) noted, cosmetic |
| `console/src/console/main.py` | `net_sha256`, `format_time_control`, `validate_syzygy_path`, writers routing | ✓ VERIFIED with notes | Writers routing live (tracer run emits `# log-sha256` matching); `--syzygy-path` validated or SystemExit (live: bad dir → `SystemExit: bad --syzygy-path '/nonexistent': no such directory`); **notes:** M-2 increment omission (deferred); L-2 control-char path accepted when the dir exists (live-confirmed, self-inflicted single-user context); smoke path bypasses the flag by design (validated only on run_game) |
| `console/tests/fixtures/golden-game.log` | Regenerated, zero falsifications | ✓ VERIFIED | `# time-control 1+0`, 64-hex net-sha256 (recomputed), final-clocks-note, `# log-sha256` recomputed MATCH; lint CLI OK rc=0 (re-run this round); 12 src= rows |
| `console/tests/*` (10 modules) | Regression coverage incl. black-side e2e | ✓ VERIFIED | Full discover: `Ran 110 tests … OK` (134.3 s, re-run this round — up from 106 with the 4 new survival tests + L-1 extensions); e2e alone previously 5/5 OK |
| `tools/tests/test_contract.py` | 19 tests incl. three-way go agreement | ✓ VERIFIED | Re-run this round: `Ran 19 tests … OK`; `check_contract_order.py` → `OK CONTRACT ORDER` |
| `evidence/02-wire-spike.log`, `evidence/02-04-*, 02-05-*, 02-06-*` | RED-first + smoke transcripts | ✓ VERIFIED | RED transcripts show the pre-fix failures verbatim; `02-06-red-evidence.json` present with all three death shapes' uncaught-RuntimeError transcripts; paced smoke shows deterministic undone echo |

### Key Link Verification

| From | To  | Via | Status | Details |
| ---- | --- | --- | ------ | ------- |
| ui/loop.py `u` branch | engine/session.py `undo_last_ply` | handle_line dispatch | WIRED | loop.py:136-154 (`try/except Exception` last-resort guard added by 02-06); test_d pins single call + echo; no direct board.pop remains |
| undo_last_ply | transport (stop/mark_discarding/consume) | §1.3/§1.5 repair | WIRED | Live repro: stop sent, discard armed, owed bestmove consumed before re-entry — **and on engine death: the failed send is caught, outstanding cleared, no propagation (live, all 3 shapes)** |
| undo_last_ply | journal RESYNC record | `_emit({"e":"RESYNC","phase":"applied","plies":1,"via":"undo","fen":…})` | WIRED | Record live in journal on the happy path AND on all three engine-death paths (live repro); `replay()` pops 1 ply — replay FEN == live FEN verified |
| `_consume_owed_bestmove` eof branch | journal ENGINE_FAULT evidence | `_emit({"e":"ENGINE_FAULT","reason":"engine EOF before the owed bestmove…"})` before the raise | WIRED | Live shape-2 repro: fault record present + `undo repair aborted` record; never a dropped event |
| loop `u` guard | journal + display + stdout | guarded-getattr sink with `traceback` field | WIRED | loop.py:143-153; `LoopUndoSurvivalTests` green (fault record with traceback + loop stays functional) |
| score_white_of | MoveLog.build | build passes `event.get("side")` | WIRED | Live build-path probe: white negative row stays negative; regression matrix green |
| lint_log | chess first-mover invariant | `expect_side = "w"` unconditional | WIRED | lint.py:91; both live probes (accept black-side, reject black-first) re-run this round |
| GameTracer._write_log | MoveLog.write_header/write_trailer | single-writer discipline | WIRED | No hand-rolled `#` lines in the tracer (source read); live run header matches writer contract; digest flush fix proven by recomputation |
| --syzygy-path | Session.options → header/wire | validate → append → flush | WIRED | Live run: `# setoption … SyzygyPath=/tmp/opencode` appears; bad path → loud SystemExit before the game |
| transport GO_LITERAL | docs/PROTOCOL.md §3.1 + mock_engine | test_contract three-way agreement | WIRED | 19/19 green this round; freeze order re-checked |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
| -------- | ------------- | ------ | ------------------ | ------ |
| golden log search rows | depth/nodes/score/pv | live `info` lines from real SF19 | Yes | ✓ FLOWING |
| golden log opp rows | uci/wall_ms | feeder through the legality gate + monotonic delta | Yes | ✓ FLOWING |
| journal | every event | session sink, fsynced JSONL (short-write-safe) | Yes | ✓ FLOWING |
| log header `# time-control` | clock values | derived from `--clock-ms` (real), minus the frozen increment | Yes, partial | ✓ FLOWING (M-2 increment omission deferred) |
| log header `# net-sha256` | net file bytes | hashed from `src/nn-1a298aa575a0.nnue` at game start | Yes | ✓ FLOWING (recomputed MATCH) |
| log `# final-clocks` | clock values | initial passthrough, honestly labelled by the note | Labelled | ✓ HONEST-LABEL (observed clocks are CLOCK-08/Phase 3) |
| log `score_white` | score + side | computed by the corrected rule | Yes | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| -------- | ------- | ------ | ------ |
| Session suite (incl. 4 new survival tests) | `PYTHONPATH=vendor:console/src python3 -m unittest console.tests.test_session` | `Ran 31 tests in 1.334s … OK` | ✓ PASS |
| Full console suite | `PYTHONPATH=vendor:console/src python3 -m unittest discover -s console/tests -t .` | `Ran 110 tests in 134.259s … OK` (re-run this round, incl. real-SF e2e) | ✓ PASS |
| Contract suite + freeze order | `python3 -m unittest tools.tests.test_contract` / `python3 tools/check_contract_order.py` | `Ran 19 tests … OK` / `OK CONTRACT ORDER` | ✓ PASS |
| Golden log lint | `PYTHONPATH=vendor:console/src python3 -m console.log.lint console/tests/fixtures/golden-game.log` | `OK LOG_LINT` rc=0 (re-run) | ✓ PASS |
| CR-02 sign probe (re-run) | `score_white_of('cp -30','w')` / `('cp -30','b')` / `('cp 30','b')` | `cp -30` / `cp 30` / `cp -30` | ✓ PASS |
| CR-03 black-side lint probe (re-run) | lint a valid `# our-color b` white-first log (full header/trailer) | zero failures; black-first control still fails (`side b breaks w/b alternation`) | ✓ PASS |
| CR-01 in-process repro (corrected token d2d4) | opp e2e4 → go outstanding → undo → corrected d2d4 | no exception; RESYNC journaled; replay FEN == live FEN | ✓ PASS |
| Piped smoke with double undo | `printf 'e2e4\nt 7:42\nu\nu\nq\n' \| … console.main --engine tools/mock_engine.py --our-color b --clock-ms w=600000,b=600000` | rc=0, `undone: e2e4` echoed; no Traceback lines (re-run this round) | ✓ PASS |
| **H-1 LIVE shape 1: dead at stop-send** | real `./src/stockfish` via `EngineTransport`, opp e2e4 → OUR_SEARCH → `popen.kill()` → `undo_last_ply()` | `ENGINE FAULT: undo repair: stop send failed (RuntimeError('engine exited rc=-9'))`; undo returns `e2e4`; RESYNC(applied, plies=1, via=undo) journaled; replay FEN == live FEN; AWAIT_OPP_CONFIRM; outstanding None; mirrors clear; **zero exceptions** | ✓ PASS (gap resolved) |
| **H-1 LIVE shape 2: dies between stop and owed bestmove** | same transport; `send` monkeypatched to `kill()` right after `stop` passes through → `_consume_owed_bestmove` drains the eof | fault 1 `engine EOF before the owed bestmove (consumed event preserved as evidence)` + fault 2 `undo repair aborted: RuntimeError(...)`; undo returns `e2e4`; RESYNC journaled; mirrors clear; **zero exceptions** | ✓ PASS (gap resolved) |
| **H-1 LIVE shape 3: dead at re-fire** | real engine answers bestmove (ANNOUNCE_PENDING) → `popen.kill()` → `undo_last_ply()` | fault `undo repair: engine re-fire failed (RuntimeError('engine exited rc=-9'))`; undo returns the announced move; RESYNC journaled; state IDLE; **zero exceptions** | ✓ PASS (gap resolved) |
| M-1 undo-race probe | real SF, answer dispatched before undo, then drain | FAULT "illegal move" on the rewound board (side-to-move gate) — never played/announced; 2 live runs | ✓ PASS (not playable; state lands IDLE — noisy but safe) |
| M-2 increment probe | `format_time_control(900000,900000)` | `15+0` (truth: 15+10) | ⚠️ DEFERRED (Phase 3) |
| Frozen docs | `git diff HEAD -- docs/PROTOCOL.md docs/LOGBOOK.md` and `git diff 783639d8..HEAD -- docs/` | empty (both re-run) | ✓ PASS |

### Probe Execution

No `scripts/*/tests/probe-*.sh` probes declared for this phase; the behavioral spot-checks above cover the runnable verification surface (transport smoke on the competition binary re-run this round → `OK transport smoke: 5 wire facts confirmed`, rc=0).

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
| ----------- | ---------- | ----------- | ------ | -------- |
| PROTO-01 | 02-02 | Strict UCI parser, typed rejects, rejected tokens logged | ✓ SATISFIED | test_moves matrix green in 110-run; REJECT records in live smoke journal |
| PROTO-02 | 02-02 | Board replica, validated-only advance, both sides | ✓ SATISFIED | Replay agreement; position_line sole producer; undo pop realignment proven live (incl. engine-death shapes this round) |
| PROTO-03 | 02-02 | Illegal announced move never advances state; illegal bestmove never displayed | ✓ SATISFIED | FAULT path re-exercised live in the M-1 probes (engine's stale answer rejected, never played); IllegalBestmoveFaultTests green |
| PROTO-04 | 02-01, 02-02 | ANNOUNCE exclusively from bestmove; wire discipline | ✓ SATISFIED | PvNeverAnnounceTests green; contract 19/19; M-1 probes confirm no announce from a stale answer |
| PROTO-05 | 02-02 | Explicit FSM + side-to-move guard | ✓ SATISFIED | TransitionTableTests green; undo re-derivation live (AWAIT_OPP_CONFIRM / OUR_SEARCH / IDLE correct in all three death shapes this round) |
| PROTO-06 | 02-02, 02-04, 02-05, **02-06** | Keyboard-only, paste-tolerant, instant echo, reject cue | ✓ SATISFIED (prompt-survival half now complete) | Piped smoke green incl. double undo; **H-1 closed: all three engine-death shapes survive an operator undo, live-verified against the real binary this round**; `UndoPromptSurvivalTests` + `LoopUndoSurvivalTests` green |
| PROTO-07 | 02-02, 02-04 | Resync by replay-last-N with confirmation; journal record | ✓ SATISFIED (Phase-2 scope) | RESYNC(applied, via=undo) journaled + replay-pops (live, incl. death shapes); request/confirm_resync tests green. Log half deferred Phase 3 |
| PROTO-08 | 02-03 | Opponent clock via `t`, alternate formats, stored in journal | ✓ SATISFIED (Phase-2 scope) | Live journal line: `{"e":"OPP_CLOCK","raw":"7:42","parsed_ms":462000}`. Log half deferred Phase 3 |
| LOG-01 | 02-03, 02-04 | One .log per game, all fields per half-move; fail-silent pipeline repairs | ✓ SATISFIED | Golden + live logs: 11 keys/row; short-write + corruption tests green; drain faults journaled |
| LOG-02 | 02-03, 02-05 | Eight fields, score verbatim incl. mate N and bound flags; score_white correct | ✓ SATISFIED | CR-02 fixed + probed (re-run this round); verbatim/bound round-trips green |
| LOG-03 | 02-03, 02-05 | engine_ms AND wall_ms, wall ≥ engine | ✓ SATISFIED | CR-06 clamp+journal green; lint re-check green |
| LOG-04 | 02-03, 02-05 | Book rows src=book d=0 n=0; terminal rows non-empty | ✓ SATISFIED (Phase-2 scope) | Terminal src=none row lint-clean (suite); book placeholder honest (`book-hash none` pre-Phase-3) |

All 12 requirement IDs (PROTO-01…08, LOG-01…04) map to Phase 2 in REQUIREMENTS.md traceability and are claimed across the six plans (02-01: PROTO-04; 02-02: PROTO-01..07; 02-03: PROTO-08, LOG-01..04; 02-04: PROTO-06/07, LOG-01; 02-05: LOG-02..04, PROTO-06; 02-06: PROTO-06). No orphaned Phase-2 requirements.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| ---- | ---- | ------- | -------- | ------ |
| console/src/console/main.py | 182-190 | `format_time_control` omits the frozen 10 s increment | ⚠️ Warning (deferred Phase 3) | Header logs 15+0 for a 15+10 run (M-2, live-confirmed) |
| console/src/console/main.py | 98-111 | `validate_syzygy_path` accepts control chars if the dir exists; dead `is_absolute` branch | ℹ️ Info | L-2 live-confirmed; self-inflicted single-user context |
| console/src/console/engine/session.py | 385-398 | M-1 race: answered-but-undrained bestmove drains AFTER undo → FAULT + state IDLE (not played — side-to-move gate holds) | ℹ️ Info | Noisy-but-safe; GAP-REVIEW's "played on rewound board" case is structurally blocked by the side-to-move legality gate (proven by 2 live runs + analysis) |
| console/src/console/log/movelog.py + lint.py | 89-117 / 95-165 | L-3: undo journals keep MOVE_LOGGED rows; projection ignores RESYNC → an undo-containing rendered log fails lint | ℹ️ Info | Documented Phase-3 deferral (OQ#2); no Phase-2 artefact path renders an interactive-undo log |
| console/src/console/log/lint.py | 76, 51-61 | L-4: dead `header` assignment + `_parse_header` | ℹ️ Info | Cosmetic dead code |

Round-1 blocker (H-1: uncaught RuntimeError in the undo repair) is **resolved** — see Gaps Closed. The prior H-1 anti-pattern row is removed; L-1 (transport.discarding armed on queue.Empty) is **resolved** by 02-06's fold (both mirrors cleared, pinned by the extended no-answer test). Debt-marker scan on the three files modified this round (session.py, loop.py, test_session.py): zero TBD/FIXME/XXX markers (grep rc=1). The two "placeholder" grep hits in session.py are historical comments naming *removed* placeholder patterns (research A2 reference, CR-12 comment) — not live stubs.

Open ledgers: original REVIEW CR-05/07/08/09/13/14 + IN-01..08 remain open per 02-REVIEW-DISPOSITION (not re-reviewed, unchanged code). M-2/L-2/L-3/L-4 as tabled above; M-1 live-probed safe (open ledger, out of 02-06 scope by explicit fence).

### Human Verification Required

Automated evidence covers the goal's happy path end-to-end, both colours, real binary — and, after 02-06, the engine-death edge of the undo path (all three shapes live-verified this round). No code defect remains. Status is `human_needed` solely for operator-ergonomics items only a human at the terminal can confirm:

1. **Interactive feel of the spine** — run a live session against `./src/stockfish`: wrong-side move typing, ANNOUNCE appearing while idle, `>> ANNOUNCE:` visual distinctness, reject-cue visibility under time pressure.
   - Why human: rendering prominence and operator ergonomics are not grep-able.
2. **H-1 operator experience (the fixed path, as a live drill)** — start a game, kill the engine mid-search (`kill -9` on the stockfish PID), type `u`, observe: a one-line `ENGINE FAULT: undo repair: …` notice, the `undone: <move>` echo (or fault line), and the `move>` prompt still accepting input. Then type a corrected opponent move — the console must continue (shape-dependent: AWAIT_OPP_CONFIRM or IDLE, both functional).
   - Expected after 02-06 (verified programmatically this round through the real transport): fault journaled, RESYNC applied, prompt alive, no traceback, no exit.
   - Why human: confirms the prompt-survival invariant the way the operator will actually hit it (tty, mid-game pressure), including that the fault lines are readable and not lost in scrollback.

### Gaps Summary

Round 2 (this verification): the single residual gap **H-1 is RESOLVED**. Plan 02-06 (commits 5e4a7305 test-RED → 8b2d6776 feat-GREEN → adcf45af test-RED → ea570162 feat-GREEN, merged 0f39849c) hardened the undo path exactly as the gap's `missing:` items directed:

1. **Catch widened** — the repair block in `undo_last_ply` now wraps the stop send, `_consume_owed_bestmove`, and the re-fire `_start_search` each in `except (RuntimeError, OSError)`; the existing `queue.Empty` handler was extended to clear `transport.outstanding` and `transport.discarding` (folding L-1). Verified by source read (session.py:397-451) and by all three live death shapes.
2. **transport.outstanding cleared on every failure mode** — confirmed in the live repros (`outstanding=None` after undo in shapes 1-3 and the timeout path).
3. **ENGINE_FAULT journaled per failure mode** — distinct records: `undo repair: stop send failed (…)`, `engine EOF before the owed bestmove (consumed event preserved as evidence)`, `undo repair aborted: (…)`, `undo repair: engine re-fire failed (…)`, and the loop's last-resort `undo failed: (…)` with a `traceback` field.
4. **Consumed eof event journalled as evidence inside `_consume_owed_bestmove`** — before the raise (session.py:509-518); live shape-2 repro shows both records.
5. **RESYNC(applied, plies=1, via=undo) on every post-pop path** — emit moved after all guarded sections (session.py:449-450); live repros confirm the journal FEN equals the live board FEN at the moment of death in every shape.
6. **Loop last-resort guard** — the `u` branch journals + displays + prints a fault notice and returns; success-path echo byte-identical (`test_d_loop_routes_u_through_session` green).

The original live repro (engine killed mid-search, operator types `u` → uncaught `RuntimeError('engine exited rc=-9')` → console exits) no longer reproduces: the same sequence now completes with a fault record, the RESYNC entry, and a live prompt. All four round-1 gaps (CR-01..CR-04) re-spot-checked and remain RESOLVED (score_white probes, black-side lint accept / black-first reject, golden fixture digest + lint CLI, frozen docs diffs empty). Full console suite 110/110 OK, session suite 31/31, contract 19/19 + freeze order, piped smoke rc 0 with the undone echo.

Residual known issues scored as non-blocking (per the round's disposition): M-1 (undo race — live-probed safe, open ledger, explicitly fenced out of 02-06), M-2 (time-control increment — deferred to Phase 3 with CLOCK-08), L-2/L-3/L-4 (cosmetic/open ledger). L-1 is resolved (folded into 02-06, regression-pinned).

No `gaps:` remain in the frontmatter. Status is `human_needed` only because two operator-ergonomics items require a human at the terminal (interactive feel + the death-drill as the operator experiences it); every grep-able and runnable check passes.

---

_Verified: 2026-10-28T18:06:01Z_
_Verifier: the agent (gsd-verifier)_
