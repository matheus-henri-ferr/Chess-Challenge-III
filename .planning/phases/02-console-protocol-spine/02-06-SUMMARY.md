---
phase: 02-console-protocol-spine
plan: 06
subsystem: console
tags: [undo, error-handling, uci, journal, fail-journal-not-crash, h-1, gap-closure]

# Dependency graph
requires:
  - phase: 02-console-protocol-spine (02-04)
    provides: Session.undo_last_ply with the §1.5 repair (stop → mark_discarding → _consume_owed_bestmove), RESYNC journal record, FakeTransport test idioms
provides:
  - Engine-death-proof undo repair: every death shape (dead at stop-send; EOF before the owed bestmove; dead at re-fire _start_search) completes the operator realignment with zero escaping exceptions
  - Per-failure-mode ENGINE_FAULT evidence: stop-send failure, repair abort (eof), re-fire failure each journal a distinct record; the consumed eof event is journalled as evidence, never dropped
  - RESYNC(applied, plies=1, via=undo) emitted on every post-pop path — the journal never diverges from the live board at engine death
  - L-1 fold: queue.Empty timeout path clears transport.outstanding AND transport.discarding; corrected opp-move re-entry lands OUR_SEARCH
  - Last-resort loop guard: the `u` branch journals ENGINE_FAULT with traceback and keeps the prompt alive even for unanticipated session crashes
affects: [phase-3-clock-logbook, verify-work]

# Actuals (#2632) — pairs with the plan's `estimate` to calibrate future estimates.
actuals:
  tokens: 44000
  tasks: 2
  commits: 4

plan_head_before: bc72782c891d2ee6568a20ab94fb2793bc660bfd
plan_head_after: ea570162

# Tech tracking
tech-stack:
  added: []   # stdlib only (queue, traceback already in use)
  patterns: [fail-journal-not-crash, last-resort-guard, transport-mirror-clearance]

key-files:
  created: [.planning/phases/02-console-protocol-spine/02-06-SUMMARY.md, .planning/phases/02-console-protocol-spine/evidence/02-06-red-evidence.json]
  modified: [console/src/console/engine/session.py, console/src/console/ui/loop.py, console/tests/test_session.py]

key-decisions:
  - "Every undo-repair failure mode (stop-send RuntimeError/OSError, queue.Empty timeout, eof RuntimeError, re-fire failure) journals its own ENGINE_FAULT record and never propagates — the operator prompt survives all three engine-death shapes (H-1 closed)"
  - "_consume_owed_bestmove journals the consumed eof event as ENGINE_FAULT evidence before raising — a dropped event used to lose the death record exactly when it matters (T-02-27)"
  - "RESYNC(applied, plies=1, via=undo) moved outside the guarded sections — emitted on every post-pop path so Journal.replay() matches the live board even when the repair failed (T-02-27)"
  - "Re-fire failure lands IDLE (the _on_fault precedent); §9.2 restart machinery stays out of scope per the plan's explicit assumptions"
  - "Loop `u` guard uses the exact drain_events CR-10 discipline (guarded-getattr sink + display_cb + stdout fault line); success-path echo byte-identical"

patterns-established:
  - "Fail-journal-not-crash at every layer: session repair → per-mode ENGINE_FAULT; loop `u` → last-resort ENGINE_FAULT with traceback"
  - "Transport-mirror clearance: on every undo-repair exit path, transport.outstanding is None and transport.discarding is False, so the corrected re-entry cannot trip §1.3"

requirements-completed: [PROTO-06]

coverage:
  - id: D1
    description: "Undo with a dead engine at stop-send completes: ENGINE_FAULT(stop send failed) journaled, transport.outstanding cleared, RESYNC(applied, plies=1, via=undo) present, state AWAIT_OPP_CONFIRM, session usable after recovery (on_operator_move e7e6 → OUR_SEARCH)"
    requirement: PROTO-06
    verification:
      - kind: unit
        ref: "console/tests/test_session.py#UndoPromptSurvivalTests.test_stop_send_raises_engine_dead_prompt_survives"
        status: pass
  - id: D2
    description: "Undo with engine EOF before the owed bestmove completes: the eof event journalled as ENGINE_FAULT evidence + repair-abort record, outstanding cleared, RESYNC present, no phantom MOVE_LOGGED, both discarding mirrors clear"
    requirement: PROTO-06
    verification:
      - kind: unit
        ref: "console/tests/test_session.py#UndoPromptSurvivalTests.test_eof_before_owed_bestmove_journaled_and_survives"
        status: pass
  - id: D3
    description: "Undo with a dead engine at the re-fire search lands IDLE with an ENGINE_FAULT(re-fire failed) record and the RESYNC record still journaled — no exception escapes"
    requirement: PROTO-06
    verification:
      - kind: unit
        ref: "console/tests/test_session.py#UndoPromptSurvivalTests.test_refire_send_raises_lands_idle_with_resync"
        status: pass
  - id: D4
    description: "L-1 folded: the queue.Empty timeout path leaves t.discarding False and t.outstanding None; the corrected opp-move re-entry (e7e6) lands OUR_SEARCH"
    requirement: PROTO-06
    verification:
      - kind: unit
        ref: "console/tests/test_session.py#UndoRealignmentTests.test_a_undo_no_answer_to_stop_prompt_survives"
        status: pass
  - id: D5
    description: "Last-resort loop guard: a residual RuntimeError from undo_last_ply journals ENGINE_FAULT with traceback, surfaces on stdout, and the loop stays functional (still routes `u` after `q`)"
    requirement: PROTO-06
    verification:
      - kind: unit
        ref: "console/tests/test_session.py#LoopUndoSurvivalTests.test_loop_u_survives_session_crash_and_stays_functional"
        status: pass
  - id: D6
    description: "Full console suite green (110 tests incl. real-SF e2e) and the piped undo smoke exits 0 with the `undone: e2e4` echo and zero tracebacks — no regression outside the undo path"
    requirement: PROTO-06
    verification:
      - kind: integration
        ref: "command: PYTHONPATH=vendor:console/src python3 -m unittest discover -s console/tests -t . → Ran 110 tests, OK"
        status: pass
      - kind: e2e
        ref: "command: printf 'e2e4\\nt 7:42\\nu\\nu\\nq\\n' | PYTHONPATH=vendor:console/src python3 -m console.main --engine tools/mock_engine.py --our-color b --clock-ms w=600000,b=600000 → SMOKE_RC=0, 'undone: e2e4' echoed, 0 tracebacks"
        status: pass

# Metrics
duration: 9min
completed: 2026-10-28
status: complete
---

# Phase 2 Plan 06: H-1 Undo Prompt-Survival Gap Closure Summary

**Every engine-death shape during an operator undo (dead at stop-send, EOF before the owed bestmove, dead at re-fire) now completes the realignment with zero escaping exceptions, per-mode ENGINE_FAULT evidence, and the RESYNC record always journaled — plus a last-resort loop guard so even an unanticipated undo crash cannot kill the prompt.**

## Performance

- **Duration:** 9 min
- **Started:** 2026-10-28T17:38:21Z
- **Completed:** 2026-10-28T17:47:00Z
- **Tasks:** 2 (both TDD RED→GREEN)
- **Files modified:** 3 (+1 evidence file)

## Accomplishments
- H-1 closed: all three engine-death shapes in `undo_last_ply` complete without any exception reaching the loop — the console never exits from an operator-initiated realignment (PROTOCOL §9.2 / Rule 10)
- Evidence-preserving `_consume_owed_bestmove`: the consumed `eof` event is journalled as an `ENGINE_FAULT` record before the raise (previously consumed and dropped)
- RESYNC(applied, plies=1, via=undo) emitted on every post-pop path — journal and live board agree at the moment of death (T-02-27)
- L-1 folded: the queue.Empty timeout path clears `transport.outstanding` + `transport.discarding`; the corrected re-entry after a silent engine lands OUR_SEARCH
- Last-resort loop `u` guard: residual exception → ENGINE_FAULT with traceback through the session sink + display line + stdout fault line; success-path echo byte-identical

## TDD Evidence

### Task 1 — RED (commit 5e4a7305)
Command: `PYTHONPATH=vendor:console/src python3 -m unittest console.tests.test_session -v` → `Ran 30 tests ... FAILED (failures=1, errors=3)`. Full transcript persisted at `.planning/phases/02-console-protocol-spine/evidence/02-06-red-evidence.json`. Semantic assessment: valid RED — each target test executed and failed on the planned behavioral assertion:
- `test_stop_send_raises_engine_dead_prompt_survives` → ERROR: `RuntimeError: engine exited rc=-9` escaping `session.py:385` (`self.transport.send("stop")`)
- `test_eof_before_owed_bestmove_journaled_and_survives` → ERROR: `RuntimeError: engine EOF before the owed bestmove` escaping `_consume_owed_bestmove` (session.py:466), uncaught by `except queue.Empty`
- `test_refire_send_raises_lands_idle_with_resync` → ERROR: `RuntimeError: engine exited rc=-9` escaping via `_start_search` (session.py:402 → 153)
- `test_a_undo_no_answer_to_stop_prompt_survives` (extended) → FAIL: `AssertionError: True is not false : transport discarding cleared, not only the mirror` (L-1)

### Task 1 — GREEN (commit 8b2d6776)
Hardened `undo_last_ply`: stop-send wrapped in `try/except (RuntimeError, OSError)` (journal + clear outstanding + skip discard/consume); `_consume_owed_bestmove` handlers widened (queue.Empty now also clears transport mirrors — L-1; RuntimeError/OSError journals the abort; `finally` clears both discarding mirrors); re-derivation/re-fire wrapped the same way (failure → IDLE per `_on_fault`); RESYNC emit moved after all guarded sections; `_consume_owed_bestmove` eof branch journals evidence before raising. Post: `Ran 30 tests ... OK`.

### Task 2 — RED (commit adcf45af)
`LoopUndoSurvivalTests.test_loop_u_survives_session_crash_and_stays_functional` → ERROR: `RuntimeError: boom` propagated out of `handle_line("u")` (loop.py:137) — the exact propagation chain GAP-REVIEW H-1 documented.

### Task 2 — GREEN (commit ea570162)
`u` branch wrapped in `try/except Exception` with the CR-10 discipline (guarded-getattr sink journal with `traceback` field, display_cb line, one stdout fault notice, return). Post: `Ran 31 tests ... OK`.

## TDD Gate Compliance
- RED → GREEN order per task: test(02-06) 5e4a7305 < feat(02-06) 8b2d6776; test(02-06) adcf45af < feat(02-06) ea570162 ✓
- RED failed for the right reason (planned behavioral assertion, zero-test-discovery absent) ✓
- GREEN minimal: only the catch structure + evidence records + mirror clearance; no scope creep ✓
- REFACTOR: not needed — no cleanup beyond what GREEN carried ✓
- Note: `gsd_run check tdd-red-evidence` was unavailable in this runtime (`gsd_run: command not found`); the RED record was persisted as a structured JSON evidence file with the required fields (command, exitCode, output summary, targetTest, expected/actual, semanticAssessment) and reviewed semantically before GREEN.

## Task Commits

1. **Task 1 RED: failing engine-death undo tests** - `5e4a7305` (test)
2. **Task 1 GREEN: hardened undo repair + eof evidence** - `8b2d6776` (feat)
3. **Task 2 RED: failing loop-u survival test** - `adcf45af` (test)
4. **Task 2 GREEN: last-resort loop guard** - `ea570162` (feat)

## Files Created/Modified
- `console/src/console/engine/session.py` — hardened `undo_last_ply` repair contract (three catch layers + always-journalled RESYNC), evidence-preserving `_consume_owed_bestmove` eof branch, widened docstring
- `console/src/console/ui/loop.py` — `u` branch last-resort `try/except Exception` guard (journal + display + stdout, prompt alive)
- `console/tests/test_session.py` — `UndoPromptSurvivalTests` (3 tests), `LoopUndoSurvivalTests` (1 test), L-1/outstanding-clearance assertions in `test_a_undo_no_answer_to_stop_prompt_survives`
- `.planning/phases/02-console-protocol-spine/evidence/02-06-red-evidence.json` — structured RED transcript

## Decisions Made
- Test (a)/(c) model the dead engine with `FakeTransport` subclasses whose `send` raises `RuntimeError("engine exited rc=-9")` when a `dead` flag is set — mirroring the real transport's dead-poll at uci.py:192-193 (the plan's spec)
- Test (b) asserts 2 ENGINE_FAULT records (eof-evidence + repair-abort) — the plan's design journals the eof event inside `_consume_owed_bestmove` AND the repair-abort; both records are distinct evidence
- Test (c) asserts `removed == "g1f3"` (the staged bestmove was already pushed to the replica in ANNOUNCE_PENDING; the pop removes it) — the plan's `e7e5` example described the undo target loosely; the assertion verifies the same invariant (the pop's ply is journalled via RESYNC)
- Re-fire failure lands IDLE per `_on_fault` — restart machinery is §9.2's documented policy, explicitly out of scope

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Existing 02-04 test assertion updated to post-repair discarding semantics**
- **Found during:** Task 1 GREEN (`test_a_undo_during_our_search_repair_and_reentry`)
- **Issue:** `assertTrue(t.discarding, "owed bestmove marked stale")` encoded the pre-L-1 behaviour; the plan's green step (step 1, `finally` clears BOTH discarding mirrors) supersedes it — the real transport's `_dispatch_bestmove` clears the flag when the owed bestmove is consumed (uci.py:183), so post-repair the flag is clear
- **Fix:** assertion changed to `assertFalse(t.discarding, "discard flag clear post-repair")` with a comment; the test's other assertions untouched
- **Files modified:** console/tests/test_session.py
- **Verification:** suite green; the L-1 semantics are pinned by the plan-mandated assertions in `test_a_undo_no_answer_to_stop_prompt_survives`
- **Committed in:** 8b2d6776 (Task 1 commit)

**2. [Rule 3 - Blocking] Worktree lacked the gitignored `src/stockfish` binary — real-SF e2e failed with FileNotFoundError (pre-existing at the wave base, not a regression)**
- **Found during:** plan-level verification step 2 (`unittest discover`, 110 tests)
- **Issue:** the e2e spawns `./src/stockfish` relative to REPO_ROOT; the 99 MB binary is gitignored in the main checkout and absent in this worktree. Reproduced identically at the wave base commit via `git archive` — pre-existing environment gap, zero relation to this plan's diff
- **Fix:** symlinked the main checkout's binary into the worktree (`src/stockfish -> ../../../../src/stockfish`); no tracked file changed
- **Files modified:** none tracked (untracked symlink, gitignored by `src/stockfish` rule)
- **Verification:** `test_e2e_fullgame` → `Ran 5 tests ... OK` (126.6 s); full suite → `Ran 110 tests ... OK`
- **Committed in:** n/a (environment fix, nothing to commit)

---

**Total deviations:** 2 auto-fixed (1 bug, 1 blocking environment)
**Impact on plan:** both fixes necessary; no scope creep. The 02-04 assertion update is the exact semantics change the plan's L-1 fold prescribes.

## Issues Encountered
None beyond the deviations above.

## Known Stubs
None — no placeholder values, no unwired data paths, no skipped tests.

## Threat Model Dispositions (T-02-26/27/28 — mitigated)
- T-02-26 (prompt death): repair catches (queue.Empty, RuntimeError, OSError) per step, clears transport.outstanding, journals per mode; re-fire lands IDLE; loop `u` last-resort guarded; regression tests pin all three shapes — VERIFIED (Tasks 1+2)
- T-02-27 (repudiation): eof event journalled as evidence; RESYNC on every post-pop path — VERIFIED (tests b, c + acceptance greps)
- T-02-28 (stale discard flag): both transport mirrors cleared on the timeout path; corrected re-entry proven — VERIFIED (test d)
- T-02-SC (tampering): zero new dependencies, no package installs — n/a

## User Setup Required
None - no external service configuration required.

## Verification Results (plan-level chain)
1. `PYTHONPATH=vendor:console/src python3 -m unittest console.tests.test_session -v` → `Ran 31 tests ... OK` rc 0 ✓
2. `PYTHONPATH=vendor:console/src python3 -m unittest discover -s console/tests -t .` → `Ran 110 tests ... OK` (133.9 s, incl. real-SF e2e) ✓
3. Piped smoke: `printf 'e2e4\nt 7:42\nu\nu\nq\n' | ... --our-color b ...` → `SMOKE_RC=0`, `undone: e2e4` echoed, 0 `Traceback` lines ✓
4. `git diff HEAD -- docs/PROTOCOL.md docs/LOGBOOK.md` → empty (frozen contracts untouched) ✓

## Acceptance Criteria Verification (both tasks, all PASS)
- `except (RuntimeError, OSError)` present around stop send (session.py:400), around `_consume_owed_bestmove` (422), and around the re-derivation/`_start_search` block (440); `queue.Empty` handler clears `transport.outstanding` + `transport.discarding` ✓
- `_consume_owed_bestmove` eof branch emits ENGINE_FAULT before raising (session.py:513-518) ✓
- RESYNC emit is after all guarded sections — reachable on all three failure paths ✓
- Tests (a), (b), (c) pass — no `RuntimeError` escapes `undo_last_ply`; RESYNC on the sink in every case ✓
- Test (d) passes — `t.discarding is False`, `t.outstanding is None`, corrected re-entry lands OUR_SEARCH ✓
- Loop `u` branch grep-able `try/except Exception` with `traceback` field (loop.py:139-147) ✓
- `test_d_loop_routes_u_through_session` green unchanged (success echo byte-identical) ✓
- Combined Task 2 verify exits 0 with `undone: e2e4` + `SMOKE_RC=0` ✓

## Self-Check: PASSED
- [ -f ] all key files exist on disk (session.py, loop.py, test_session.py, SUMMARY, evidence JSON) ✓
- Commits 5e4a7305, 8b2d6776, adcf45af, ea570162 all ancestors of HEAD ✓
- `git rev-list --count bc72782c..HEAD` = 4 (matches actuals.commits) ✓
- No unexpected file deletions in any commit ✓

## Next Phase Readiness
- H-1 (the re-verification's single residual gap) is closed with regression pins on all three death shapes; PROTO-06's prompt-survival half is complete
- Deferred per the plan's explicit assumptions: M-1 (undo race, live-probed safe, open ledger), M-2 (`# time-control` increment → Phase 3 LOGBOOK bundle with CLOCK-08), L-2/L-3/L-4 (cosmetic/open ledger), PROTO-07/08 log-file halves + full §9.2 restart machinery (Phase 3)
- `gsd_run windows append` unavailable in this runtime and `.planning/WINDOWS.md` absent — the one deviation (02-04 assertion update, intentional semantics change) is recorded here and in the broken-windows sense is a closed item, not a defect

---
*Phase: 02-console-protocol-spine*
*Completed: 2026-10-28*
