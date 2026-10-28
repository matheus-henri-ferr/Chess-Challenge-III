# Phase 2 Gap-Closure — Plan Checker Report

**Phase:** 02-console-protocol-spine (gap-closure round)
**Checked:** 2026-10-28
**Plans checked:** 2 (02-04 wave 1, 02-05 wave 2)
**Mode:** gap_closure (verify-gate round 2 of /gsd-plan-phase --gaps)

## Overall Verdict: WAIT — one-line revisions to 02-05, then execute

- **02-04: PASS** — no issues found.
- **02-05: WAIT** — 0 blockers, 2 warnings (both one-line mechanical fixes), 2 advisories. No re-verification loop required; the planner applies the fixes directly and execution proceeds.

Deterministic checks already run upstream (not re-run here, accepted as input): verify-command-paths → not_applicable (0 blockers), verify-failure-directions → ok (15 checks, 0 blockers/warnings), verify.plan-structure + frontmatter.validate → valid.

---

## 1. Gap coverage — all 4 failed truths mapped, zero silent drops

| # | Failed gap truth (02-VERIFICATION.md `gaps:`) | Plan | must_haves.truths (quoted) | Task(s) |
|---|---|---|---|---|
| 1 | "The operator can realign the replica with `u` (undo) mid-game without the console dying — Rule 10 realignment must be possible without restart, and the prompt must never die under the operator" | 02-04 | identical string (truth 1) | Task 1 (undo_last_ply + §1.3 repair + RESYNC record + loop routing + regression suite), Task 2 (drain fault discipline keeps the prompt alive) |
| 2 | "score_white is a correct White-POV normalisation of the STM-POV score (LOGBOOK §2.1)" | 02-05 | identical string (truth 1) | Task 1 (sign rule + ScoreWhiteSignTests matrix), Task 3 (black-side e2e), plan-level sign probe |
| 3 | "A valid log from a game where we play black (our-color b, white moves first) passes log_lint — the fail-closed linter must not fail a correct log" | 02-05 | identical string (truth 2) | Task 1 (expect_side="w" seed + AlternationSeedTests), Task 3 (BlackSideFullGameTests) |
| 4 | "The .log header/trailer tell the truth about the run that produced them" | 02-05 | identical string (truth 3) | Task 2 (MoveLog writer routing, real time-control, honest clock label, full net sha256), Task 3 (golden regeneration + time-control pin) |

Every truth is quoted verbatim in a plan's must_haves; every must_have traces to tasks with grep-able source assertions, behavior assertions, and runnable test commands.

## 2. Deferred items — none planned

- **PROTO-07 log-file `# RESYNC …` representation:** not implemented. 02-04 only journals the RESYNC record (Phase-2 scope, replay contract already in journal.py:107-109). 02-05's objective names the deferral explicitly.
- **PROTO-08 OPP_CLOCK log representation:** not implemented; nothing in either plan renders OPP_CLOCK into the .log.
- **Observed final clocks (CLOCK-08/LOG-05):** not implemented. 02-05 Task 2 keeps the passthrough values and adds the honest `final-clocks-note` label — this is exactly the "label the passthrough honestly" option the verifier's own `missing:` item prescribes ("either track observed end-of-game clocks or label the passthrough honestly (full observed clocks are CLOCK-08/Phase 3)"). Not scope reduction: the Phase-2 truth never included observed clocks. Both deferrals are re-named in 02-05's success criteria.

Extra-scope check: the folded CR-06/CR-10/CR-11/CR-12 work stays inside the touched files and the fail-silent-pipeline rationale in the objective; CR-05/07/08/09/13/14 remain open in the ledger and are explicitly not attempted (02-05 Task 1: "do not attempt CR-13/CR-14"). No ledger re-open, no scope creep.

## 3. Task concreteness

- **read_first includes every modified file:** 02-04 T1 (session.py, loop.py, test_session.py + journal replay contract + PROTOCOL §1.3/§1.5), T2 (session.py, loop.py, test_session.py), T3 (journal.py, test_journal.py). 02-05 T1 (movelog.py, lint.py, test_movelog.py + LOGBOOK §1.4/§2.1), T2 (main.py, movelog.py contract, test_movelog.py + 02-03-SUMMARY Deviation #3), T3 (test_e2e_fullgame.py, golden fixture). Verified against the live tree — all referenced symbols exist (`_start_search` §1.3 raise at session.py:149/uci.py:262-264, `_consume_owed_bestmove` at session.py:396, `confirm_resync` RESYNC shape at session.py:347, loop `u` branch at loop.py:119-125, `elif value < 0` at movelog.py:70-73, `first_mover = header.get("our-color", "w")` at lint.py:85-86, tracer falsifications at main.py:570/574-575/586-587, golden fixture carries all three).
- **Acceptance criteria are source/behavior/test assertions:** every criterion is grep-able source ("contains no `elif value < 0` branch", "no direct `session.board.pop()` call in the `u` branch", "defines `net_sha256` and `format_time_control`"), a pinned behavior ("score_white_of('cp -30','w') == 'cp -30'", "the CR-01 sequence … ends in OUR_SEARCH with zero exceptions"), or a test command with exit-0. No subjective criteria.
- **Actions carry concrete identifiers without full code blocks:** exact function names (`undo_last_ply`, `mark_discarding`, `_consume_owed_bestmove`, `JournalCorruptionError`, `format_time_control`, `net_sha256`), exact record shapes (`{"e": "RESYNC", "phase": "applied", "plies": 1, "via": "undo", "fen": …}`), exact test matrices (8 sign cases incl. bound-flag and None paths), exact CLI semantics (`expanduser().resolve()`, SystemExit on non-existing absolute dir). The REVIEW's fix sketch is referenced, not pasted; the plan states the deltas beyond it (queue.Empty catch, display fallback, RESYNC emission) precisely.

## 4. fails_when coverage

All six runnable `<automated>` verify blocks (3 per plan) carry a `<fails_when>` sibling naming the failure output (non-zero exit, FAILED/ERROR line, `Ran 0 tests`, missing `OK fullgame`/`OK LOG_LINT`, grep count 0). Plan-level `<verification>` chains state "fail-closed, run at plan end, each command exits 0". Consistent with the upstream failing-directions result (15 checks, 0 issues). Note: Task 2 of 02-05's `grep -c "net-sha256"` gate is sound — baseline count 1 is cited and true in the current fixture (verified), and the gate holds both before and after Task 3's regeneration.

## 5. Frontmatter

| Field | 02-04 | 02-05 |
|---|---|---|
| gap_closure | true | true |
| wave / depends_on | 1 / [] | 2 / ["02-04"] — wave = max(deps)+1 ✓, sequential as required |
| requirements | [PROTO-06, PROTO-07, LOG-01] | [LOG-02, LOG-03, LOG-04, PROTO-06] — matches the approved gap-closure citation set |
| files_modified vs task files | exact union of the 3 tasks' `<files>` (session, loop, journal, test_session, test_journal) | exact union of the 3 tasks' `<files>` (movelog, lint, main, test_movelog, test_e2e_fullgame, golden-game.log) — see W-2 for Task 2's internal gap |
| tracked paths | all 5 git-tracked (verified) | all 6 git-tracked (verified); the untracked 94 MB net file correctly excluded from files_modified with the runtime-hash + PROVENANCE-fallback design (full hash present in PROVENANCE.md §1) |

Acyclic graph, no forward references, no same-wave pairs (waves 1 and 2 differ), no cross-plan data-contract conflicts (session.options placeholder removal in 02-04 strictly precedes the flag re-entry in 02-05; golden-game.log written only by 02-05).

## 6. Risk analysis

**Golden regeneration ordering — correct.** The regenerated fixture's `# setoption` header must reflect the effective option set *after* 02-04 removed `("SyzygyPath", "<empty>")`; 02-05 Task 2 builds that line from `session.options`. Inverted order would re-bake the placeholder into the committed fixture. `depends_on: ["02-04"]` enforces the right order, and 02-05 Task 2 explicitly frames its SyzygyPath append as "02-04 removed the placeholder tuple; this is the only way SyzygyPath re-enters the set". The e2e and golden runs also exercise the repaired drain/clamp paths. Ordering is sound.

**CR-01 regression fidelity — verified against source.** Task 1a stages the stop-answer into `t.events` exactly as the real reader delivers it after `stop`, calls `undo_last_ply()` with `FakeTransport.outstanding` set, asserts stop-sent / discarding-armed / STALE_BESTMOVE sunk / RESYNC(applied, plies=1) / state AWAIT_OPP_CONFIRM, then simulates the reader's `outstanding = None` side-effect (the real transport clears outstanding at uci.py:180-181 when the matching bestmove is enqueued — FakeTransport's raw event queue does not, so the explicit simulation is the honest modeling) and replays the corrected opp move. Pre-fix, this sequence raises `RuntimeError("start_search with a go outstanding")` from FakeTransport.start_search (test_session.py:56) — the same uncaught exception the verifier reproduced live. The test genuinely reproduces the crash and would be RED before the fix. Case (b) (ANNOUNCE_PENDING undo → no stop → re-search) and case (c) (empty-board no-op, no record) match the FSM and replay contracts. The queue.Empty catch (engine never answers the stop) keeps the prompt alive per gap truth #1's second clause.

**Other live-source cross-checks that passed:** the mock engine answers `go` inline, so the 02-04 piped smoke reaches `undone:` echoed + rc 0 under both event-drain interleavings (the plan's "may FAULT … irrelevant" hedge covers the residual); removing the SyzygyPath tuple does not break OptionFlushTests (it asserts five specific setoption lines, none SyzygyPath); the extra `# final-clocks-note` trailer line cannot fail lint (only required-field prefixes are checked; `_parse_header` ingesting it as a header key is the known open CR-14, untouched); the plan's numeric baselines are accurate against the tree (83 console tests, 17 movelog tests, 11 journal tests, golden grep count 1).

---

## Issues

### Warnings (fix before execution; one-line each, no re-verification round needed)

**W-1. [verification_derivation] The black-side e2e's row-count expectation must be reachable by the scripted line it specifies**
- Plan: 02-05, Task 3
- Evidence: the example scripted white line `e2e4 g1f3 b1c3 d2d4 c2c4 g1f3 c2c3 e2e4` yields only 5 usable white moves: the second `g1f3` and second `e2e4` are skipped by the `played` set (main.py `_next_opp_token`), and `c2c3` is illegal after `c2c4`. Five white moves + five engine replies = at most 10 rows; the game ends via "scripted line exhausted" before `max_plies=12` can fire. The action's parenthetical "assert only ≥12 rows and lint-clean" is therefore unreachable as written; an executor mirroring the white-side test's `assertGreaterEqual(len, 12)` produces a deterministically failing test (the primary assertions — rc 0, `OK fullgame`, log exists, `lint_log == []` — remain achievable).
- Example fix (non-binding): either extend the scripted line with further distinct legal white moves (e.g. `f1d3 g2g3 a2a3 f1e2`-shaped continuations), or set `max_plies=10` / assert ≥10 rows — any mechanism that makes the row-count expectation consistent with the line.

**W-2. [task_completeness] Task 2's preferred implementation route must stay inside Task 2's declared `<files>`**
- Plan: 02-05, Task 2
- Evidence: the action "prefer extending write_trailer so the note rides the writer" modifies `console/src/console/log/movelog.py`, but Task 2's `<files>` lists only `main.py` and `test_movelog.py`. The plan-level `files_modified` already covers movelog.py (via Task 1), so the manifest stays consistent, but an executor following the stated preference makes an edit outside the task's declared file set.
- Example fix (non-binding): add `console/src/console/log/movelog.py` to Task 2's `<files>`, or drop the extend-write_trailer option in favour of the main.py-manual-line route.

### Advisories (info)

**I-1. [scope_sanity] 02-05's estimate sits at 95% of the smart-zone budget**
- Plan: 02-05
- Evidence: estimate-check --calibrated → 95,000 tokens vs 100,000 budget, `over_budget: false`, ratio 0.95, `confidence: low` (no completed-phase actuals recorded yet — the figure is not calibration-backed). Within budget, but the tightest slice in the phase.
- Example fix (non-binding): none required; if execution feels tight, the CLI-side `--syzygy-path` assertion can ride the piped smoke instead of a dedicated test (the plan already permits either).

**I-2. [research_resolution] RESEARCH.md's Open Questions are substantively resolved but the section heading lacks the (RESOLVED) marker**
- File: 02-RESEARCH.md
- Evidence: all four questions carry recorded dispositions (02-03-SUMMARY Deviations #1–#4: OQ#1/#2 → Phase 3 LOGBOOK amendment bundle, OQ#3 → implemented as recommended, OQ#4 → scripted feeder + real engine, which 02-05 Task 3 follows). Neither gap-closure plan reopens any of them. Marker-only staleness.
- Example fix (non-binding): retitle to `## Open Questions (RESOLVED)` with one-line dispositions pointing at the 02-03 SUMMARY.

---

## Coverage and scope summary

| Plan | Tasks | Files | Wave | Estimate (calibrated) | Verdict |
|---|---|---|---|---|---|
| 02-04 | 3 | 5 | 1 | 80,000 / 100,000 (80%, low confidence) | PASS |
| 02-05 | 3 | 6 | 2 | 95,000 / 100,000 (95%, low confidence) | WAIT (W-1, W-2) |

Requirement citations match the approved gap-closure set (02-04: PROTO-06, PROTO-07, LOG-01; 02-05: LOG-02, LOG-03, LOG-04, PROTO-06); the remaining phase IDs belong to already-verified plans or Phase 3 and are correctly not claimed. Architectural Responsibility Map: every task sits in the Console-process tier; no engine-tier work. AGENTS.md: offline/stdlib-only honored (both plans declare zero package installs), GPLv3 header preservation explicit in both plans, GSD workflow context intact.

**Recommendation:** 0 blockers, 2 warnings. Returning to the planner for the two one-line fixes to 02-05 (W-1 scripted line / row-count consistency, W-2 Task 2 file declaration); 02-04 executes as written. After the fixes, no re-verification round is required — proceed to /gsd-execute-phase 2.
