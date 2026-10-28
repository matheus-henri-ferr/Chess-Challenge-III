---
phase: 02-console-protocol-spine
plan: 04
subsystem: console
tags: [undo, resync, fsync, journal, fail-closed, uci, error-handling]

# Dependency graph
requires:
  - phase: 02-console-protocol-spine (02-02, 02-03)
    provides: Session FSM + OperatorLoop + transport primitives (_consume_owed_bestmove), append-only JSONL journal, MoveLog projection + log_lint
provides:
  - Session.undo_last_ply — session-owned undo with §1.3 transport repair (stop + discard + consume owed bestmove before any next go) and a replay()-honoured RESYNC record
  - Fail-closed event/journal pipeline: CR-06 clamp+journaled timing anomaly, CR-10 guarded drain (ENGINE_FAULT + traceback, drain continues), CR-11 short-write loop + JournalCorruptionError (path+line), CR-12 session half (no placeholder SyzygyPath)
  - Piped-input line-loss fix (_read_line past-newline buffer) with regression test
affects: [02-05, phase-3-clock, verify-work]

# Actuals (#2632) — pairs with the plan's `estimate` to calibrate future estimates.
actuals:
  tokens: 135000
  tasks: 3
  commits: 8

# Tech tracking
tech-stack:
  added: []   # stdlib only (queue, traceback, memoryview)
  patterns: [fail-journal-not-crash, session-owned-realignment, short-write-completion-loop]

key-files:
  created: [.planning/phases/02-console-protocol-spine/02-04-SUMMARY.md]
  modified: [console/src/console/engine/session.py, console/src/console/ui/loop.py, console/src/console/game/journal.py, console/tests/test_session.py, console/tests/test_journal.py]

key-decisions:
  - "Undo during an outstanding search repairs the transport (stop → mark_discarding → consume owed bestmove) before any next start_search — the CR-01 crash sequence is now a regression test"
  - "A lying engine_ms clamps the row (floor-of-1 kept) and journals ENGINE_FAULT — a MOVE_LOGGED row is never silently lost"
  - "drain_events catches queue.Empty separately; handler exceptions journal ENGINE_FAULT with traceback and the drain continues — the prompt never dies"
  - "append_event loops os.write until the memoryview is exhausted, fsync exactly once — a short write can never durably commit a torn line"
  - "JournalCorruptionError names path + 1-based line + decode error on torn lines; replay() inherits it"
  - "('SyzygyPath', '<empty>') removed from startup options — 02-05 adds the validated --syzygy-path flag"

patterns-established:
  - "Fail-journal-not-crash: every anomaly in the event/journal pipeline lands an ENGINE_FAULT record with evidence, never an assert or a silent swallow"
  - "Session-owned realignment: the loop never mutates board/transport directly; undo goes through Session.undo_last_ply"

requirements-completed: [PROTO-06, PROTO-07, LOG-01]

# Coverage metadata (#1602) — one entry per shipped deliverable.
coverage:
  - id: D1
    description: "Session-owned undo_last_ply: the CR-01 sequence (opp move accepted → go outstanding → undo → corrected opp move e7e6) completes with zero exceptions, stop sent, discard armed, owed bestmove sunk, RESYNC(applied, plies=1, via=undo) journaled, state OUR_SEARCH"
    requirement: PROTO-07
    verification:
      - kind: unit
        ref: "console/tests/test_session.py#UndoRealignmentTests.test_a_undo_during_our_search_repair_and_reentry"
        status: pass
      - kind: unit
        ref: "console/tests/test_session.py#UndoRealignmentTests.test_b_undo_without_outstanding_go_refires_search"
        status: pass
      - kind: unit
        ref: "console/tests/test_session.py#UndoRealignmentTests.test_c_undo_empty_board_returns_none"
        status: pass
      - kind: e2e
        ref: "piped survival smoke — .planning/phases/02-console-protocol-spine/evidence/02-04-paced-smoke.txt (rc 0, undone: echoed)"
        status: pass
    human_judgment: false
  - id: D2
    description: "Loop routes `u` through session.undo_last_ply; no direct board.pop in the u branch; prompt survives undo during search (incl. stop-then-silence)"
    requirement: PROTO-06
    verification:
      - kind: unit
        ref: "console/tests/test_session.py#UndoRealignmentTests.test_d_loop_routes_u_through_session"
        status: pass
      - kind: unit
        ref: "console/tests/test_session.py#UndoRealignmentTests.test_a_undo_no_answer_to_stop_prompt_survives"
        status: pass
      - kind: unit
        ref: "console/tests/test_session.py#LoopTests.test_piped_multiline_stdin_reaches_handle_line"
        status: pass
    human_judgment: false
  - id: D3
    description: "Fail-silent repairs: wall_ms<engine_ms journals ENGINE_FAULT and clamps (no bare assert); handler exception journals ENGINE_FAULT with traceback and drain continues; no '<empty>' placeholder in options"
    requirement: LOG-01
    verification:
      - kind: unit
        ref: "console/tests/test_session.py#TimingAnomalyTests.test_stale_engine_ms_is_clamped_and_journaled"
        status: pass
      - kind: unit
        ref: "console/tests/test_session.py#DrainFaultTests.test_handler_exception_journals_fault_and_keeps_draining"
        status: pass
      - kind: unit
        ref: "console/tests/test_session.py#DrainFaultTests.test_options_carry_no_placeholder_paths"
        status: pass
    human_judgment: false
  - id: D4
    description: "Journal durability: short-write recovery loop before fsync; torn/garbage line raises JournalCorruptionError with path+line on iter_records and replay"
    requirement: LOG-01
    verification:
      - kind: unit
        ref: "console/tests/test_journal.py#CorruptionDurabilityTests.test_short_write_recovery_loop"
        status: pass
      - kind: unit
        ref: "console/tests/test_journal.py#CorruptionDurabilityTests.test_torn_line_raises_corruption_error_with_path_and_lineno"
        status: pass
      - kind: unit
        ref: "console/tests/test_journal.py#CorruptionDurabilityTests.test_replay_propagates_corruption_error_not_jsondecode"
        status: pass
    human_judgment: false

# Metrics
duration: 90min
completed: 2026-10-28
status: complete
---

# Plan 02-04: Gap closure — CR-01 undo crash + fail-silent paths Summary

**The operator's `u` now realigns the board mid-search without killing the console, and every fail-silent path in the event/journal pipeline fails loudly with journaled evidence.**

## Performance

- **Duration:** ~90 min (2 sessions; context reset between Task-1 GREEN and Task-2 RED)
- **Tasks:** 3 completed (+1 Rule-3 auto-fix)
- **Files modified:** 5 (+3 evidence/summary artifacts)

## Accomplishments
- CR-01 closed: undo during an outstanding search repairs the transport per §1.3 and re-derives state from the replica — the verifier's reproduced crash sequence is now a green regression test.
- CR-06/CR-10/CR-11/CR-12(session) closed: clamp+journal instead of assert, guarded drain with traceback, short-write loop + named corruption error, no bogus SyzygyPath on the wire.
- Piped-input line-loss (Rule 3) fixed: `_read_line` buffers past-newline bytes; piped smoke deterministic.

## Task Commits

Each task was committed atomically:

1. **Task 1: session-owned undo_last_ply (CR-01 vertical slice)** — `1d0bdebe` (test RED) → `4438e78b` (feat GREEN)
2. **Task 2: fail-silent repairs (CR-06/CR-10/CR-12)** — `75902a8c` (test RED) → `7d119ca4` (feat GREEN)
3. **Task 3: journal durability (CR-11)** — `b1c87188` (feat)

Supporting commits: `d76bffa0` (fix: `_read_line` piped-buffer, Rule 3), `d63a7177` (evidence transcripts), `d36c3e55` (plan summary).

## Files Created/Modified
- `console/src/console/engine/session.py` — `undo_last_ply` (§1.3 repair + RESYNC record); `_on_bestmove` clamp+ENGINE_FAULT (CR-06); options placeholder removed (CR-12)
- `console/src/console/ui/loop.py` — `u` routed through session; `drain_events` guarded (CR-10); `_read_line` past-newline buffer
- `console/src/console/game/journal.py` — short-write completion loop; `JournalCorruptionError` (CR-11)
- `console/tests/test_session.py` — UndoRealignmentTests (5), TimingAnomalyTests, DrainFaultTests, piped-buffer regression
- `console/tests/test_journal.py` — CorruptionDurabilityTests (3); pre-existing 11 intact

## Decisions Made
- Floor-of-1 wall_ms kept (sub-quantum searches stay writable); anomaly path clamps to engine_ms and journals — never crashes, never drops the row.
- RESYNC record reuses the exact shape `Journal.replay()` already honours (`phase=applied, plies=1`) — no replay-side change needed.
- Ponder machinery and `request_resync`/`confirm_resync` untouched (plan constraint; CR-07/08/09 stay open).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Correctness] `_read_line` discarded piped/typed-ahead lines**
- **Found during:** Task 1 verification (piped smoke raced/lost lines)
- **Issue:** bytes after the first `\n` in a single `os.read` were dropped, making verify-chain #4 non-deterministic
- **Fix:** `self._stdin_buf` holds past-newline bytes; `_read_line` returns buffered lines first
- **Files modified:** `console/src/console/ui/loop.py`, `console/tests/test_session.py`
- **Verification:** `test_piped_multiline_stdin_reaches_handle_line` green; full suite green
- **Committed in:** `d76bffa0`

**Total deviations:** 1 auto-fixed (Rule 3)
**Impact on plan:** Necessary for the plan's own verification step; in plan files; no scope creep.

## Issues Encountered
- Raw 4-line piped smoke races the mock's <1 ms answer ("nothing to undo", rc 0); plan accepts any prompt-surviving rc-0 run. Paced feeder transcript proves the `undone:` echo deterministically; both transcripts committed.
- TDD classifier requires FULL `-v` unittest output (headers + `Ran N` + outcome); abridged captures return `invalid_record`. Task-2 record rebuilt with full output → RED_EVIDENCE_OK.
- `gsd_run` CLI not on PATH in this worktree — ledger file created manually; TDD classifier + requirements marking via the GSD MCP hub.

## User Setup Required
None - no external service configuration required.

## Verification (plan-level verify chain, fail-closed, all exit 0)

1. `PYTHONPATH=vendor:console/src python3 -m unittest console.tests.test_session console.tests.test_journal -v` → `Ran 41 tests … OK`
2. `PYTHONPATH=vendor:console/src python3 -m unittest discover -s console/tests -t .` → `Ran 95 tests … OK` (incl. real-SF e2e, 66 s)
3. `python3 -m unittest tools.tests.test_contract` → `Ran 19 tests … OK`
4. Piped survival smoke → rc 0, `undone: e2e4` echoed, corrected `d7d5` accepted (paced transcript in evidence)

Acceptance greps: no `session.board.pop` in the `u` branch; no `assert wall_ms` in session.py; no `"<empty>"` in options; `except queue.Empty` in drain_events; `JournalCorruptionError` defined+raised; `undo_last_ply` + `"via": "undo"` present.

## Next Phase Readiness
- `Session.options` carries no SyzygyPath — 02-05's validated `--syzygy-path` flag may re-add it from operator config.
- PROTO-06 marking is gated on 02-05 (shared-ID rule #2388): this plan reinforced it; the ready-ids gate kept it Pending until 02-05's SUMMARY exists.
- Log-side RESYNC/OPP_CLOCK representation remains Phase-3's amendment bundle (unchanged from 02-03).

---
*Phase: 02-console-protocol-spine*
*Completed: 2026-10-28*
