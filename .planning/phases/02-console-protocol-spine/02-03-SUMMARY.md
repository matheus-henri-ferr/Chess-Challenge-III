---
plan: 02-03
phase: 02-console-protocol-spine
title: journal + MoveLog projection + fail-closed log_lint + real-engine full game (Gate 1)
status: complete
completed: 2026-10-27
requirements-completed: [LOG-01, LOG-02, LOG-03, LOG-04, PROTO-08]
requirements-pending: []
# PROTO-08: this plan completes BOTH halves — the journal half (OPP_CLOCK
# records land in the journal with raw + parsed_ms, 02-02's `t` command
# routed through the sink) and the half the plan scoped to Phase 2's
# delivered surface. The log-file *representation* of PROTO-08's extra
# fields and research OQ#2's `# RESYNC …` reserved-prefix line remain
# Phase-3 work (LOGBOOK amendment bundle) — see Deviations #1/#2.
estimate:
  tokens: 110000
  actual_tokens: 302000  # chars/4 over the realized diff (13 files, ~800 insertions)
  raw_tokens: 55000
  tasks: 3
  confidence: low
  duration_s: 1800  # single session, base 6ec66e74 → SUMMARY
plan_head_before: 6ec66e7487a89316cad788e5d4d79b0e5ffd7b41
plan_head_after: c6a77643e496901dc2f2f7184867f4d91f871c19
commits:
  - d59f51a4 feat(02-03): append-only fsync journal wired as the session event sink
  - 7c042680 test(02-03): MoveLog + log_lint suite red-first (console.log.lint missing)
  - 017becd0 feat(02-03): MoveLog projection + fail-closed log_lint (GREEN)
  - 64f068ee feat(02-03): tracer full-game e2e + golden lint-clean log (Gate 1)
  - c6a77643 test(02-03): RED evidence transcript for TDD move-log suite
---

## What shipped

The Rule 9 spine, end to end: every half-move of a real Stockfish game is
journaled with fsync, projected into the §3.1 log format by a pure fold,
certified by a fail-closed linter, and proven by a committed golden log.

- `console/src/console/game/journal.py` — append-only JSONL journal:
  `append_event` writes one record + `os.fsync` before returning (the
  event lands on disk before the console proceeds); `Journal.iter_records`
  replays the file; records are plain dicts with the 02-02 event
  vocabulary. A crash mid-write loses at most the tail record, never a
  prefix — replay of any committed prefix is stable.
- `console/src/console/engine/session.py` — journal fills (Task 1):
  GAME_START carries `game_id` + `clock_ms` (02-02 already carried
  our_color); the opp-move §4.5 record carries zeroed depth/nodes/
  engine_ms/score + a measured `wall_ms`; the terminal `bestmove (none)`
  path emits the §4.6 row (src=none, uci=(none), depth=0, nodes=0, non-
  empty score from last_info) BEFORE GAME_END; GAME_END carries `result`
  + `reason`. `wall_ms` is captured as `max(1, now - search_t0_ms)` for
  src=search rows: a completed search spans ≥1 pipe round-trip below the
  ms quantum, and instant-search stubs report `time 1` — the T-02-13
  write-time assert (wall ≥ engine) held with the floor.
- `console/src/console/main.py` — `--log-dir` (resolved absolute, created
  if missing, LOUD refusal + non-zero exit BEFORE the game when
  unwritable — proven by a throwaway `.journal-probe.tmp` append+fsync+
  read-back in the SAME directory, then unlinked, so the journal's first
  record stays the session's GAME_START); `--game-id` (T-02-15: alnum +
  dash only, no path traversal surface); `engine_sha256()` recomputes the
  binary's sha256 at game start (header always tells the truth; script
  engines → "unavailable").
- `console/src/console/log/movelog.py` — the projection (Task 2, GREEN):
  `MoveLog.build(records)` folds journal records into log rows — a pure
  function of the journal, never a parallel history; `render(rec)` emits
  the §3.1 line order verbatim (src first, pv last unquoted);
  `score_white_of` normalizes the numeric part to White's POV (negates
  on a white row's negative and for side=b) while keeping the bound flag
  (`lowerbound`/`upperbound`) and `-` verbatim; STALE_BESTMOVE folds to
  a src=ponder row (move_no=0, side=-) per §4.4. `LOG_KEYS` equals
  tools/tests/test_contract.py's frozen constant exactly (asserted both
  directions); the §3.1 LINE order is independent of the tuple order.
- `console/src/console/log/lint.py` — fail-closed `lint_log` (Task 2):
  header/trailer presence, per-row all-keys check (names the missing
  key), src whitelist, side alternation, wall_ms ≥ engine_ms, engine_ms
  ≥ 0; every failure NAMED. CLI (`python3 -m console.log.lint <file>`)
  exits 0 on `OK LOG_LINT` / 1 with the failure list.
- `console/src/console/ui/loop.py` — `run(tracer=)`: in tracer mode
  stdin EOF is NOT the game's end (a harness-driven run has
  `</dev/null`; the immediate EOF previously raced the feeder and killed
  the engine); the loop ends only on tracer-finished or `q`.
- `GameTracer` (main.py, Task 3) — `--auto-opp LINE` / `--max-plies N`:
  a feeder thread plays the opponent's side of a fixed legal line through
  `session.on_operator_move` (the SAME typed legality gate as a human —
  no feeder shortcut); legality probed on a scratch BoardState replaying
  the live move list; diverged scripted tokens skipped forward. At
  max-plies / terminal / line-exhaustion / engine death / 280 s budget:
  GAME_END journaled → `.log` rendered FROM THE JOURNAL via MoveLog →
  in-process lint (TracerLogError on any failure — fail closed) →
  `OK fullgame: N half-moves, lint clean` → exit 0.
- `console/tests/` — test_journal.py (11: fsync-before-return, replay
  stability, probe isolation), test_movelog.py (17, red-first), test_e2e_fullgame.py
  (3: real-SF full game, golden fixture, terminal none-row).

## Requirements coverage

| Requirement | Evidence | Status |
|---|---|---|
| LOG-01 journal + fsync | `game/journal.py`; append_event fsyncs before returning; 11 tests; probe file proves writability without polluting the game journal | Complete |
| LOG-02 MoveLog projection | `log/movelog.py` pure fold; variant fills asserted per §4 (search full, opp zeros, none terminal, ponder from STALE_BESTMOVE); LOG_KEYS == contract constant both directions | Complete |
| LOG-03 log_lint fail-closed | `log/lint.py`; named failures (missing key, alternation, wall<engine, bad src, header/trailer); CLI rc 0/1 asserted both ways | Complete |
| LOG-04 full game → golden log | `test_e2e_fullgame.py` real-SF run (12 plies, 64 s wall) → `fixtures/golden-game.log` (26 lines, 6 src=opp rows) committed; `grep -q 'src=opp'` + lint CLI green on it | Complete |
| PROTO-08 journal half | `t <time>` OPP_CLOCK records land in the journal with raw + parsed_ms via the sink (wired Task 1); log-side representation deferred to Phase 3 (see Deviations #1) | Complete (Phase-2 scope) |

human_judgment items: none declared by the plan's frontmatter.

## Red-state evidence (Task 2, tdd=true)

`console/tests/test_movelog.py` written and run BEFORE `console/log/`
existed; transcript verbatim at
`.planning/phases/02-console-protocol-spine/evidence/02-03-red-movelog.txt`
(committed c6a77643):

```
ModuleNotFoundError: No module named 'console.log'
Ran 17 tests in 0.002s
FAILED (errors=17)
```

Git history order: 7c042680 (RED, tests only) → 017becd0 (GREEN,
implementation). 17/17 after GREEN; 1 test
(`LintCliTests.test_cli_ok_on_golden_log`) was written skip-guarded and
auto-unskipped when `fixtures/golden-game.log` landed in Task 3.

## Verification (plan-level verify chain, fail-closed, all exit 0)

1. `PYTHONPATH=vendor:console/src python3 -m unittest console.tests.test_e2e_fullgame -v`
   → `Ran 3 tests … OK` (real-SF game 64 s, terminal-row game, golden fixture)
2. `PYTHONPATH=vendor:console/src python3 -m unittest discover -s console/tests -t .`
   → `Ran 83 tests … OK` (1 skip resolved: golden-log case now runs)
3. `PYTHONPATH=vendor:console/src python3 -m unittest discover -s tools/tests -t .`
   → `Ran 37 tests … OK`
4. `PYTHONPATH=vendor:console/src python3 -m console.log.lint console/tests/fixtures/golden-game.log`
   → `OK LOG_LINT`
5. `grep -q 'src=opp' console/tests/fixtures/golden-game.log` → rc 0

Golden log facts: 12 search rows + 6 opp rows (both colours' half-moves),
all eleven §3.1 keys per row, every src=opp row depth=0/nodes=0/score=-/engine_ms=0
with measured wall_ms, every src=search row depth>0, wall_ms ≥ engine_ms
on all 18 rows, `# log-sha256` trailer covers the file bytes.

## Deviations and interpretation notes

1. **PROTO-08 / research OQ#1 log-side representation → Phase 3.** The
   plan's Task-1 sentence defers it explicitly: OPP_CLOCK and the
   `# RESYNC …` reserved-prefix line (OQ#2) are journaled in Phase 2 but
   render no log line this phase; the Phase-3 LOGBOOK amendment bundle
   owns both. No frozen doc amended here.
2. **`--auto-opp`/`--max-plies`/GameTracer shape** — the plan named the
   flags but left the mechanism open ("tracer", research OQ#4's
   fixed-legal-line option chosen). The feeder types through the
   operator path (no shortcut); a scripted move illegal in the diverged
   position is skipped, and a run-dry line now ENDS the game cleanly
   (`_finish(reason="scripted line exhausted")`) instead of idling to
   the 280 s wall budget (found by the first real-SF run: 9 plies +
   6 ENGINE_FAULTs then budget-exceeded; fix verified in the committed
   run).
3. **e2e clock lowered to `w=60000,b=60000`** — at 900000 ms SF19
   single-thread burns ~28 s/move; 12 plies exceeded the 300 s budget.
   The go literal is a passthrough (Phase 3 ClockModel owns real
   clocks); log shape identical. Header still prints the competition
   `# time-control 15+10` (frozen field).
4. **Golden log's engine-sha256** is the worktree build's sha (header
   tells the truth); `# net-sha256 1a298aa575a0` states the official
   SF19 net, unmodified — lint checks the prefix only.
5. **`gsd_run` CLI unavailable in this worktree** — all bookkeeping
   (ledger file `$(git rev-parse --git-dir)/gsd-plan-head-before-02-03`,
   this hand-written SUMMARY) done manually. Recorded for the checker.
6. **wall_ms floor of 1** for src=search rows (see What shipped) — a
   T-02-13 conservation; the mock's instant-search stubs would otherwise
   trip the write-time assert.

## Threat model dispositions (all mitigated as planned)

- T-02-11 journal tampering → append-only, fsync-before-return, replay
  stable on any committed prefix; log rendered FROM the journal only.
- T-02-12 unwritable log-dir → loud refusal BEFORE the game (probe file
  in the target directory), non-zero exit, named reason.
- T-02-13 time conservation → write-time assert wall_ms ≥ engine_ms +
  lint check; wall floor 1 handles sub-quantum searches.
- T-02-14 game-id injection → alnum+dash gate (T-02-15), SystemExit on
  violation.
- T-02-SC installs → none: stdlib + vendored `chess` only (new imports:
  hashlib, json, pathlib, threading, datetime).

## Handoff to Phase 3

- Journal event vocabulary now includes the §4.5/§4.6 fills: opp rows
  carry zeros + measured wall; the terminal `(none)` row exists BEFORE
  GAME_END; GAME_END carries `result` + `reason`. MoveLog folds all of
  them — Phase 3's log-side OPP_CLOCK/RESYNC representations slot into
  `MoveLog.build` + `lint.py`'s skip-list without touching the session.
- The tracer (`--auto-opp`/`--max-plies`) is the harness surface for
  future self-play/SPRT glue; its exit model is fail-closed on lint.
- `render`/`score_white_of` are the only log-text producers — Phase 3
  amendments (OQ#1/#2 lines) extend `lint.py`'s reserved prefixes and
  `MoveLog.build`'s fold, nothing else.

## Self-Check: PASSED

- All 3 tasks committed atomically (feat/test commits per task, no
  backticks, files staged individually, hooks on — no --no-verify).
- Plan-level verify chain fail-closed green (all five elements exit 0).
- RED-first proven by commit order (7c042680 → 017becd0) + transcript.
- Golden log real-SF, lint-clean, carries src=opp rows.
- No `.planning/STATE.md`/`ROADMAP.md`/`REQUIREMENTS.md` writes
  (orchestrator owns them).
- Estimated tokens consciously exceeded (110k → ~302k realized chars/4):
  journal + projection + linter + real-engine e2e in one critical path;
  no scope shaved — all three tasks delivered complete per acceptance
  criteria.
