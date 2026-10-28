# CHECKER-02-06 — Gap-Closure Round-2 Plan Verification

**Phase:** 02-console-protocol-spine
**Plan under review:** .planning/phases/02-console-protocol-spine/02-06-PLAN.md (wave 1, gap_closure: true, 2 tasks, depends_on: [])
**Date:** 2026-10-28
**Method:** Goal-backward verification of the single residual gap (GAP-REVIEW H-1, high, reproduced live by 02-VERIFICATION.md) against the plan file, the verification report, GAP-REVIEW.md, the live source (session.py, loop.py, uci.py, test_session.py), and the structure/estimate validators.

## Inputs consumed

- 02-06-PLAN.md in full (frontmatter, objective, both tasks, threat model, verification, success criteria).
- 02-VERIFICATION.md: frontmatter `gaps:` block (the failed truth, the `missing:` fix directive) and the Behavioral Spot-Checks H-1 row.
- GAP-REVIEW.md § H-1 (reproduction and sketched fix) and § L-1 (the folded low finding).
- Live source reads: session.py (undo_last_ply ~357-470, _consume_owed_bestmove, _on_fault, _start_search), loop.py (drain_events, `u` branch at 136-142, _quit), uci.py (send raise at 192-193, outstanding/discarding discipline), test_session.py (FakeTransport, make_session, pump, UndoRealignmentTests).
- Validators: `verify.plan-structure` → **valid** (2 tasks, all required elements present); `estimate-check --calibrated` → 55,000 tokens vs 100,000 budget, ratio 0.55, **not over budget** (confidence low, 0 calibration samples — see Advisories).
- Repo checks: all three files in `files_modified` are git-tracked (verified with `git ls-files --error-unmatch`); `git diff HEAD -- docs/PROTOCOL.md docs/LOGBOOK.md` is currently empty and no task touches docs/; the test count the plan cites ("existing 27+ tests") was measured live at 27 existing `def test_` cases.

## Check 1 — The failed truth maps to must_haves.truths (required)

The 02-VERIFICATION.md gap truth reads, verbatim:

> "The prompt survives every operator input — including undo while the engine is dead or dies mid-repair (PROTOCOL §9.2); the console must never exit from an operator-initiated realignment"

02-06's frontmatter `must_haves.truths` contains exactly this string, character for character, and the objective quotes it again as the gap truth. The artifacts and key_links beneath it map one-to-one onto the failure evidence: session.py (repair catches + outstanding clearance + ENGINE_FAULT per mode + RESYNC always), loop.py (last-resort `u` guard), test_session.py (the new survival test classes). **Check 1: PASS.**

## Check 2 — Tests cover both missing repro paths plus loop-level survival (required)

The verification's `missing:` list demands: "undo with a transport whose send raises RuntimeError; undo with a queue yielding eof — neither exists". The plan delivers both, plus the surrounding layers:

- **(a) send-raises path:** `UndoPromptSurvivalTests.test_stop_send_raises_engine_dead_prompt_survives` — a `DyingEngineTransport` whose `send` raises `RuntimeError("engine exited rc=-9")`, modelling uci.py:192-193 exactly. Asserts no escape, ENGINE_FAULT, `t.outstanding is None`, RESYNC(applied, plies=1, via=undo) present, correct post-state, and session usability after recovery. This is path 1 of the live H-1 reproduction.
- **(b) eof path:** `UndoPromptSurvivalTests.test_eof_before_owed_bestmove_journaled_and_survives` — stages `{"type": "eof"}` in the queue before the undo, matching the real reader-thread delivery, and asserts the evidence record the plan adds inside `_consume_owed_bestmove`, no phantom MOVE_LOGGED, both discarding mirrors clear. This is path 2 of the live reproduction.
- **(c) re-fire path:** `test_refire_send_raises_lands_idle_with_resync` — the third death shape (dead at `_start_search` after the pop), landing IDLE per the `_on_fault` precedent. Not required by the `missing:` list; correct to include since the plan's own step 2 opens this path.
- **(d) loop-level survival:** Task 2's `LoopUndoSurvivalTests.test_loop_u_survives_session_crash_and_stays_functional` drives `handle_line("u")` with a session whose `undo_last_ply` raises — pinning the last-resort layer against any residual exception the hardened session misses, and proving the loop stays functional afterwards.

The verification's secondary damage items are also pinned: the eof event journaled as evidence (T-02-27) and RESYNC emitted on every post-pop path so the journal never diverges from the live board at death. I confirmed the asserted line numbers against the tree: the eof raise is at session.py:466, the send raise at uci.py:192-193, the `u` branch at loop.py:136. **Check 2: PASS.**

## Check 3 — Task concreteness (required)

**read_first coverage:** Task 1 reads session.py (~357-470, naming the exact blocks: the `except queue.Empty` at ~390-398, the eof raise at ~465-466, `_on_fault`, `_emit`), uci.py (send, mark_discarding, _dispatch_bestmove, start_search's §1.3 guard), test_session.py (FakeTransport fields, make_session, pump, UndoRealignmentTests idioms), plus the VERIFICATION gaps block, GAP-REVIEW § H-1/§ L-1, and frozen PROTOCOL §9.2. Task 2 reads loop.py (~98-142, the `drain_events` CR-10 idiom the guard mirrors, the `u` branch at 136-142) and the loop-routing test idiom at test_session.py ~625-648. Together the two tasks cover session.py / loop.py / test_session.py as required.

**Concrete identifiers:** Both actions name exception types (`RuntimeError`, `OSError`, `queue.Empty`), journal record names (`ENGINE_FAULT` with per-mode reasons, `RESYNC` with phase=applied / plies=1 / via=undo), transport fields (`outstanding`, `discarding`, both session and transport mirrors), test class and method names, the exact display line the smoke greps (`undone: e2e4`), and grep-able source assertions in the acceptance criteria. No full code pastes — structure is described at contract level, consistent with the fix shape GAP-REVIEW sketched. **Check 3: PASS.**

## Check 4 — RED/GREEN ordering (required)

Both tasks are `type="auto" tdd="true"`. Task 1's action opens "**RED first** — add the following to test_session.py, run … and record the failing state … in the SUMMARY **before touching session.py**", then "**Then green** — implement in session.py". Task 2 mirrors the order ("record the red state in the SUMMARY" before the loop.py change). The output contract requires the uncaught-RuntimeError transcripts in 02-06-SUMMARY.md, so the red evidence is auditable after execution. **Check 4: PASS.**

## Check 5 — files_modified, tracking, frozen docs (required)

- Frontmatter `files_modified` = {console/src/console/engine/session.py, console/src/console/ui/loop.py, console/tests/test_session.py}; Task 1 files = {session.py, test_session.py}, Task 2 files = {loop.py, test_session.py}. Union equals the frontmatter exactly; nothing outside it is modified.
- All three paths verified git-tracked.
- No task edits docs/; the plan's own verification chain step 4 enforces `git diff HEAD -- docs/PROTOCOL.md docs/LOGBOOK.md` → empty, and the GPLv3 header preservation is an explicit action step. **Check 5: PASS.**

## Check 6 — Scope fence (required)

- **M-2 (time-control increment):** explicitly deferred to the Phase 3 LOGBOOK bundle; no task touches main.py or format_time_control.
- **PROTO-07/08 log-file halves:** deferred Phase 3; the plan only touches the Phase-2 journal-side RESYNC record, which is in scope.
- **CLOCK-08/LOG-05 observed final clocks:** untouched.
- **M-1:** not folded — live-probed safe per the re-verification, and the action explicitly forbids adding the M-1 discriminator ("Do NOT add the M-1 discriminator"). Folding was optional; declining it is compliant.
- **L-2/L-3/L-4:** not planned.
- **L-1:** folded, which the checker input marks in-scope-optional, with a correct justification (the fix lands in the same repair block the plan restructures) and its own test (d) + threat row T-02-28.
- **requirements: [PROTO-06]** — correct: the gap truth is the prompt-survival half of PROTO-06, and no other requirement's half-moved scope is claimed. **Check 6: PASS.**

## Additional dimensions

- **Structure:** `verify.plan-structure` → valid, exit 0; both tasks carry name/files/read_first/action/verify(+fails_when)/done/acceptance_criteria.
- **Dependencies:** single plan, `depends_on: []`, wave 1 — valid; plans 02-01..02-05 are all executed (SUMMARYs present), so no undeclared same-wave coupling exists in this round.
- **Verify-command sanity:** both <verify> blocks are runnable unittest invocations with no swallowed errors (`2>/dev/null || echo` absent, no anchored package-manager greps, no hard-coded counts — the only count reference, "27+", is a floor and matches the measured 27). Task 2's `A && B; echo SMOKE_RC=$?` shape is fail-closed: if A fails, B never runs and SMOKE_RC carries A's non-zero rc, which `fails_when` rejects. The piped smoke exercises both undo paths deterministically (mock engine; if it answers before the first `u`, the first undo takes the no-outstanding path and the second the re-fire path — both assert-free of exceptions either way).
- **must_haves derivation:** the single truth is user-observable and testable; artifacts map to it; key_links wire undo_last_ply → transport, → journal, and loop `u` → session rather than merely listing files.
- **Threat model:** T-02-26/27/28/SC continue the ledger correctly (02-05's highest is T-02-25, verified by grep).
- **AGENTS.md compliance:** stdlib-only (no pip), unittest (project standard), GSD workflow respected, GPLv3 headers explicitly preserved.

## Advisories (info — no revision required)

1. **[task_completeness] Cross-reference lettering slip in Task 1 read_first.** The read_first bullet says the existing-test extension is "Task 1c", but the action labels that extension (d); (c) is the re-fire test. An executor following the read_first pointer literally would look for the wrong letter. The action text itself is unambiguous, so this cannot misdirect execution in practice.
2. **[scope_sanity] Estimate confidence is low (0 calibration samples)** — the 55,000-token figure is uncalibrated, though it sits at 0.55 of budget with a comfortable margin. Weighted against the plan's small file/task footprint, this is informational only.
3. **[verification_derivation] The plan calls its smoke pipe "the proven command, reuse verbatim"** while the pipe differs slightly from the one the verification ran (adds a second `u`, drops `d2d4`). The modified pipe is still deterministic and arguably broader; the "verbatim" phrasing is the only inaccuracy.

## Conclusion

The plan is a faithful, tightly scoped closure of the phase's single residual gap: the failed truth is quoted verbatim into must_haves, both missing reproduction paths from the verification's `missing:` list get named regression tests plus loop-level survival coverage, both tasks are TDD-ordered with concrete, grep-able acceptance criteria, files and tracking are clean, frozen docs are guarded by the plan's own verification chain, and every deferred item stays out of scope while the optionally-foldable L-1 is folded with justification. The three advisories above are cosmetic and carry no required revisions.

**VERDICT: PASS** — 02-06-PLAN.md may proceed to execution as written; no required revisions.
