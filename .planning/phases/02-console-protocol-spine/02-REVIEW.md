---
phase: 02-console-protocol-spine
reviewed: 2026-10-27
depth: deep
files_reviewed: 20
files_reviewed_list:
  - console/src/console/transport/uci.py
  - console/src/console/transport/parser.py
  - console/src/console/game/moves.py
  - console/src/console/game/board.py
  - console/src/console/game/journal.py
  - console/src/console/engine/session.py
  - console/src/console/ui/loop.py
  - console/src/console/log/movelog.py
  - console/src/console/log/lint.py
  - console/src/console/main.py
  - console/tests/test_transport.py
  - console/tests/test_session.py
  - console/tests/test_board.py
  - console/tests/test_moves.py
  - console/tests/test_journal.py
  - console/tests/test_movelog.py
  - console/tests/test_ponder_discard.py
  - console/tests/test_e2e_fullgame.py
  - tools/mock_none_engine.py
  - tools/tests/test_contract.py
findings:
  critical: 1
  high: 3
  medium: 10
  low: 8
  total: 22
status: issues_found
---

# Phase 2: Code Review Report

**Reviewed:** 2026-10-27
**Depth:** deep
**Files Reviewed:** 20
**Status:** issues_found

## Summary

Deep review of the Phase 2 console spine: transport framing/reader thread, whitelisted parser, Session FSM, operator loop, fsync journal, MoveLog projection, fail-closed lint, and tracer e2e — traced end-to-end against the frozen PROTOCOL.md/LOGBOOK.md.

The core discipline is real: binary unbuffered pipes, selector framing, search_id pairing, typed rejects, append-only fsync journal, and a genuinely fail-closed lint are all correctly built and well tested. But the review found one critical crash in the primary operator path (`u` during an active search makes the next legal opp-move re-entry raise out of the loop and kill the console), three high-severity graded-log defects (the `score_white` sign rule is inverted for white-mover negative scores; log_lint seeds side alternation from `our-color`, so every black-side game log fails lint; the tracer — the only log producer — hardcodes time-control and writes initial clocks as final clocks), and a series of medium/low robustness gaps concentrated in non-live paths (ponder machinery) and failure-swallowing. Both e2e tests run our-color=w only, which masks two of the high findings.

## Critical Issues

### CR-01: `u` (undo) during OUR_SEARCH makes the next opp-move re-entry crash the console — uncaught `RuntimeError` from `start_search`

**File:** `console/src/console/ui/loop.py:119-125` with `console/src/console/engine/session.py:143-154,157-196` and `console/src/console/transport/uci.py:259-264`
**Issue:** The loop handles `u` with `self.session.board.pop()` only — no FSM repair, no transport interaction, no journal record. Verified crash trace: opponent announces a move; operator types it (accepted, pushed, `_start_search()` fires → state=OUR_SEARCH, `outstanding` set); the operator then notices the physical move was different and types `u` to realign (Rule 10). `pop()` removes the opp ply; `expected_mover()` flips back to the opponent. Operator types the corrected move: `on_operator_move` accepts it (mover ≠ our colour), pushes it, then calls `_start_search()` — which raises `RuntimeError("start_search with a go outstanding (PROTOCOL §1.3)")` because the interrupted search's go is still outstanding and its bestmove never consumed. `handle_line` and `run()` have no try/except on this path, so the exception propagates out of `run()` through `run_game`'s finally → the console **exits mid-game**. Even without the crash, `u` emits no RESYNC/undo journal record, so `Journal.replay()` reproduces a different move list than the live session (the T-02-11 replay substrate silently diverges), and popping during ANNOUNCE_PENDING leaves `last_announced` pointing at a move no longer on the replica.
**Fix:** Route `u` through the session with state + §1.3 repair:
```python
# engine/session.py
def undo_last_ply(self):
    removed = self.board.pop()
    if removed is None:
        return None
    if self.transport.outstanding is not None:
        self.transport.send("stop")            # §1.5: stop first…
        self.transport.mark_discarding()       # …owed bestmove is stale
        self._consume_owed_bestmove()
    self.discarding = False
    self.last_announced = None
    self.state = (self.IDLE if self.board.expected_mover() == self.our_color
                  else self.AWAIT_OPP_CONFIRM)
    self._emit({"e": "RESYNC", "phase": "applied", "plies": 1})
    return removed
```
and have the loop call `self.session.undo_last_ply()` instead of `board.pop()` directly.

## High Issues

### CR-02: `score_white_of` inverts the White-POV sign for white-mover negative scores — deterministic graded-log field error, lint cannot catch it

**File:** `console/src/console/log/movelog.py:48-77` (specifically the `elif value < 0` branch at lines 70-73)
**Issue:** LOGBOOK §2.1: `score_white` is a White-POV normalisation of the STM-POV score. UCI `score` is side-to-move POV, so a **white-mover row with `cp -30` is already White-POV −30** (white is worse). The code's `elif value < 0: value = -value` branch flips it to `cp 30` — the sign is wrong on every "we are worse" white row, the most common losing-game log line. Verified cases: side="w", cp -30 → code emits `cp 30` (wrong, must stay −30); side="b", cp -30 → `cp 30` (correct); side="b", cp 30 → `cp 30`→`-30` (correct). The test suite (`test_movelog.py:190-204`) only exercises side=None and side="b" rows — the live white-negative case is untested, and `MoveLog.build` always passes a real `side`, so the None path in the test does not cover production behaviour. `log_lint` checks only `score_white` presence, never its value, so nothing downstream catches this. Deterministic, every affected game, graded artefact.
**Fix:** Delete the `elif value < 0` branch entirely; negate only when `side == "b"`:
```python
value = int(tokens[1])
if side == "b":
    value = -value   # STM black → negate; side "w"/None is already White-POV
out = f"{tokens[0]} {value}"
```
Add regression tests: white row `cp -30` → `cp -30`; black row `cp -30` → `cp 30`.

### CR-03: log_lint seeds side alternation from `our-color` — every black-side game log fails lint (and e2e never tests black)

**File:** `console/src/console/log/lint.py:85-86`
**Issue:**
```python
first_mover = header.get("our-color", "w")
expect_side = first_mover if first_mover in ("w", "b") else "w"
```
`our-color` is the console's colour, not the game's first mover — the first mover of a chess game is always white. When we play black (`--our-color b`), LOGBOOK §1.4 requires logging both colours from ply 1, so the first row is `side=w` (the opponent's move) — but the linter expects `side=b` and fails it ("side w breaks w/b alternation"), then fails every subsequent odd row as the seed never recovers in step. Result: **50% of real games produce logs that fail the fail-closed linter** — a "game incident" per LOGBOOK §6.2 for a perfectly valid log. Both e2e tests (`test_e2e_fullgame.py:63, 126`) run `our_color="w"` only, so this is unmasked by the suite.
**Fix:** Seed from the game's actual first mover, which is always white:
```python
expect_side = "w"  # chess: white always moves first (LOGBOOK §1.4)
```
Add an e2e/lint test with `# our-color b` and a white-first row.

### CR-04: GameTracer — the only Phase 2 log producer — hardcodes `# time-control 15+10` and writes **initial** passthrough clocks as the trailer's "final clocks"

**File:** `console/src/console/main.py:553-594` (lines 570, 574-575, 586-587) vs `console/src/console/log/movelog.py:128-159`
**Issue:** Three graded-artefact falsifications in the tracer's `_write_log`, which bypasses `MoveLog.write_header/write_trailer` entirely: (1) `# time-control 15+10` is hardcoded while the run's actual `--clock-ms` may be anything (the e2e itself runs `w=60000,b=60000` — logged as 15+10); (2) `# final-clocks w={w_ms} b={b_ms}` writes `self.clock_ms` — the **initial** passthrough values, never observed remaining time; LOGBOOK §5.2 requires "both final clocks as observed"; (3) `# net-sha256 1a298aa575a0 (…)` is a 12-char prefix plus prose, a different format from what a §5.1 consumer parsing a sha256 expects, and inconsistent with `write_header`'s parameter contract. Since the interactive game path never writes a `.log` in Phase 2, every log produced this phase comes from this code path.
**Fix:** Call `MoveLog.write_header/write_trailer` with real values; thread observed final clocks through the session (tracked per half-move) into the trailer; record actual time-control from `--clock-ms`; either emit the full net sha256 (hash the `.nnue` file like `engine_sha256` does) or get a dated LOGBOOK revision blessing the prefix form.

## Medium Issues

### CR-05: Terminal `(none)` row logs `last_info` carried over from a previous search

**File:** `console/src/console/engine/session.py:240-263` with `session.py:221-229`
**Issue:** `self.last_info` is never cleared between searches. For `bestmove (none)`, `score` defaults to `self.last_info.get("score", "mate 0")` and `engine_ms` to `self.last_info.get("time", 0)`. If the terminal search streams no `info` lines before the bestmove (instant TB answer, or a peer that terminates search 2 before emitting info — not forbidden by PROTOCOL §4.2), the row logs the **previous search's** score/time from an unrelated position. A well-formed `cp 35` as the terminal evaluation of a mate position is a graded-log lie that lint cannot detect (the field is well-formed and non-empty).
**Fix:** Clear `self.last_info = {}` at the top of `_start_search()` and `enter_pondering()`; in the `(none)` path, if this search produced no score, derive from `outcome()` (e.g. `mate 0`) rather than trusting the carried value.

### CR-06: `assert wall_ms >= engine_ms` in `_on_bestmove` — when it fires, the AssertionError is swallowed by `drain_events`' bare except and the bestmove row is silently lost

**File:** `console/src/console/engine/session.py:284-295` interacting with `console/src/console/ui/loop.py:96-103`
**Issue:** The code's own comment says a peer claiming more than wall "still fires the assert". `engine_ms` comes from `last_info` (never cleared — CR-05), so a stale `time` from a long previous search paired with a fresh bestmove makes `wall_ms < engine_ms` reachable. When the assert fires: the `_announce` (line 278) has already run but the `MOVE_LOGGED` emit never does; the `AssertionError` propagates into `OperatorLoop.drain_events`, whose `except Exception: return` (CR-10) swallows it and abandons the rest of the queue. Net effect: the operator **heard the announce**, the replica advanced, but the journal has **no row for this half-move** and the FSM is stuck in OUR_SEARCH (state assignment at line 304 never runs) — a Rule-9 mandatory-field loss with no signal, exactly what log_lint exists to prevent and cannot see post-hoc. A crash would at least be loud; this is fail-silent.
**Fix:** Replace the assert with a clamp + journaled anomaly (`ENGINE_FAULT` naming the anomaly, `wall_ms = max(wall_ms, engine_ms)`), and fix CR-10 so handler exceptions are not swallowed.

### CR-07: `enter_pondering` assembles the §3.5 ponder go literal by string-slicing the §3.1 builder's output

**File:** `console/src/console/engine/session.py:353-361`
**Issue:** `self.transport.send("go ponder " + self._go_line()[len("go "):])` reassembles the frozen ponder literal by surgery instead of calling `go_ponder_line(w_ms, b_ms)` — which exists precisely for this and is contract-tested (`test_contract.py:104-107`). Byte-identical today, but the §3.5 guarantee now rides on `go_line`'s implementation; any Phase 3 change to `go_line` (TM-09 reserve discounting) silently flows into the untested ponder path.
**Fix:** `self.transport.send(go_ponder_line(*self.clock_passthrough_ms))`.

### CR-08: Ponder-miss race — a bestmove arriving before `stop` is sent leaves `_consume_owed_bestmove` blocked on an event that never comes, then crashing on uncaught `queue.Empty`

**File:** `console/src/console/engine/session.py:363-394, 396-413`
**Issue:** In `on_opp_move_during_ponder`, the flag ordering is `send("stop")` → `mark_discarding()`. If the engine's bestmove lands in the window between the push and the stop send (engine finished naturally during the journal write), it is dispatched as a **current** bestmove (`discarding` still False, sid matches), sunk by the `state == PONDERING` check — and `outstanding` is cleared. Then `mark_discarding()` arms the flag and `_consume_owed_bestmove()` blocks for the full 30 s timeout waiting for an answer already consumed. When the timeout expires, `events.get` raises `queue.Empty`, which `_consume_owed_bestmove` does not catch (only `finally` re-queues) → unhandled exception → console exit. Non-live in Phase 2 games (Ponder=false) but exercised by the Phase 2 test path, and the crash-on-timeout is unconditional.
**Fix:** Set `mark_discarding()` **before** `send("stop")`; catch `queue.Empty` in `_consume_owed_bestmove` and treat it as fatal-with-diagnostic (distinguish "already consumed" by checking `transport.outstanding is None` first).

### CR-09: `wait_for_bestmove` / `_consume_owed_bestmove` re-queue deferred events behind events that arrived later — causal order inversion

**File:** `console/src/console/transport/uci.py:298-320` and `console/src/console/engine/session.py:396-413`
**Issue:** Both drains collect non-matching events in `deferred` and re-`put` them in a `finally`. `queue.Queue.put` appends at the tail, so deferred (older) events land **behind** events the reader thread enqueued during the drain window — inverting arrival order in the queue relative to the transcript. A consumer can then ingest search N+1's `info` before search N's deferred `info`, corrupting `last_info` pairing (feeds CR-05/CR-06). Not reachable in the Phase 2 live loop (the loop drains FIFO and never calls `wait_for_bestmove`), but both functions are the documented §1.3 consume primitives for Phase 3.
**Fix:** Return the deferred list to the caller instead of re-queuing (single-consumer discipline), or drain-then-splice under a lock held against the reader's enqueue.

### CR-10: `OperatorLoop.drain_events` catches bare `Exception` — fail-silent where the phase's own discipline is fail-closed

**File:** `console/src/console/ui/loop.py:96-103`
**Issue:** `except Exception: return` is intended for `queue.Empty` from `get_nowait()` but also swallows anything raised by `session.on_engine_event` — the CR-06 assert, a KeyError on a malformed event, a journal `OSError`. Every exception aborts the drain mid-queue: remaining events (possibly the bestmove) are never dispatched, no journal record, no display, FSM frozen. The failure leaves zero evidence on the sink.
**Fix:** `except queue.Empty: return`; let other exceptions propagate, or catch-and-journal an `ENGINE_FAULT` with the traceback before continuing.

### CR-11: Journal `append_event` ignores `os.write`'s return value — short writes durably commit torn JSON lines

**File:** `console/src/console/game/journal.py:45-62`
**Issue:** `os.write` may write fewer bytes than requested (signal interruption, ENOSPC on a near-full disk). The count is discarded; the remainder is never written; `os.fsync` then durably commits a torn line. `iter_records()` runs `json.loads` per line and does not catch `JSONDecodeError`, so `replay()` and the tracer's `_records()`/`_move_rows()` crash on the first torn line — on event day, a disk-space condition converts a log incident into a console crash mid-game.
**Fix:** Loop the write (`memoryview` slice until exhausted), fsync, and wrap `iter_records`' `json.loads` to raise a named `JournalCorruptionError` (or surface a failure record) instead of a bare decoder error.

### CR-12: `Session.options` sends `setoption name SyzygyPath value <empty>` — a bogus path, violating §2.3's "absolute local directory"

**File:** `console/src/console/engine/session.py:82-85`
**Issue:** The §2.3 startup set is flushed verbatim to the engine every game with the literal placeholder `<empty>` as the path. The engine accepts the option but TB probing is silently mis-configured (probe failures surface only as `info string` warnings), while the log header asserts a §2.3-compliant option set and `SyzygyProbeLimit 5`. A competition game that reaches a 5-piece ending logs TB guidance that was never active.
**Fix:** Require a real SyzygyPath (CLI flag validated at startup, absolute-path check) or omit the option and record the absence honestly in the header — never send a placeholder the console knows is invalid.

### CR-13: lint never cross-checks the row's `side` against the replay board's turn — a fabricated side column passes with legal moves

**File:** `console/src/console/log/lint.py:127-160`
**Issue:** Legality is checked by `board.push_uci` and alternation by `expect_side` — two independent mechanisms. The `side` column is never compared to the colour actually moving in the replay. A log whose `side` values are fabricated but alternate (e.g. an entire game's sides flipped, or rows relabelled after tampering) passes every check: uci sequence legality and w/b alternation are both satisfied. LOGBOOK §6.1's intent — that each row's colour is the mover of that ply in the replayed position — is only half-implemented.
**Fix:** Capture `turn_before = board.turn` before `push_uci`, then after a successful push require `"w" if turn_before == chess.WHITE else "b" == pairs["side"]`, else fail with the ply number.

### CR-14: `_parse_header` scans trailer lines too; missing `our-color` cascades into misleading alternation failures; duplicate header keys silently ignored

**File:** `console/src/console/log/lint.py:50-59, 85-86`
**Issue:** `_parse_header` accepts any `# key value` line, including `# result`/`# final-clocks`/`# log-sha256` from the trailer; `setdefault` makes a duplicated `# our-color` line (post-hoc tampering) silently ignored — first value wins, contradicting the fail-closed posture. And when `our-color` is absent (already a header failure), alternation still seeds from the `"w"` default, producing a cascade of side-alternation failures that buries the one root cause.
**Fix:** Parse only lines before the first move row; flag duplicate header keys as failures; when `our-color` is missing, emit the header failure and skip alternation checks (one root failure) instead of seeding a guess.

## Low Issues

### IN-01: `time.monotonic_ns() // 1_000_000` re-implemented inline in three modules

**File:** `console/src/console/engine/session.py:113`, `console/src/console/game/journal.py:53`, `console/src/console/transport/uci.py:101`
**Issue:** The console-wide timing source (LOG-03) is copy-pasted; Phase 3's ClockModel must change all three consistently.
**Fix:** One `now_ms()` helper in a shared module.

### IN-02: `_readline_unlocked` constructs a new `DefaultSelector` per read call

**File:** `console/src/console/transport/uci.py:117-139`
**Issue:** Selector create/register/close per framing attempt. Correct but wasteful in the hottest loop.
**Fix:** One selector instance for the reader thread's lifetime.

### IN-03: Function-local `from console.transport.uci import go_line` on every search

**File:** `console/src/console/engine/session.py:108`
**Issue:** Re-imported per call; the dependency is hidden from module readers.
**Fix:** Top-level import.

### IN-04: Dead `tracer = None` assignment in `run_game`

**File:** `console/src/console/main.py:364`
**Issue:** Assigned, then unconditionally reassigned at line 374 before any use.
**Fix:** Remove line 364.

### IN-05: Tracer `_next_opp_token` replays the full move list into a scratch board on every poll tick

**File:** `console/src/console/main.py:503-522`
**Issue:** O(plies²) at 20 Hz polling. Correct; wasteful; Phase 3's clock thread shares the tick.
**Fix:** Cache the scratch board, invalidate when `board.moves` length changes.

### IN-06: `mock_none_engine.py` ignores `stop` — a stop-owed consumer hangs until timeout

**File:** `tools/mock_none_engine.py:22-41`
**Issue:** Answers `go` but has no `stop` branch; PROTOCOL §1.5/§4.3 consumers would block. Only used by the throwaway smoke probe today, but cited as a contract fixture.
**Fix:** Treat `stop` like `go` (emit the same info + `bestmove (none)`).

### IN-07: `FORBIDDEN_GO_TOKENS` guard is test-only — never enforced at runtime in the builders

**File:** `console/src/console/transport/uci.py:40-56`
**Issue:** The §3.2 token guard exists as data and is contract-tested, but `go_line`/`go_ponder_line` never check their own output; a future builder edit that bypasses the tests ships a violating line.
**Fix:** `assert not any(t in line.split() for t in FORBIDDEN_GO_TOKENS)` in both builders (cheap, structural).

### IN-08: `_parse_header`/`handshake` second loop uses per-get timeout without an overall deadline

**File:** `console/src/console/transport/uci.py:250-256`
**Issue:** `self.events.get(timeout=timeout)` inside `while True` resets the wait on every non-readyok event; a chatty engine can extend the handshake past the §2.1 10 s budget indefinitely.
**Fix:** Deadline-check `time.monotonic()` in the loop condition.

---

## Cross-cutting verification notes

- **§3.1 go literal:** three-way doc ↔ mock ↔ console agreement genuinely tested (`test_contract.py:89-116`); builders correct.
- **§7.3 discard orderings:** all three orderings transport- and session-tested; `search_id` pairing in `_dispatch_bestmove` is correct for the tested sequences. Residual risk is the CR-09 re-queue inversion on the non-live consume primitives.
- **§5.2 time units:** parser keeps wire ms verbatim; `engine_ms` logged unconverted. Correct.
- **Journal durability:** fsync-per-record real; O_APPEND-only enforced structurally and by source-walk test. CR-11 is the single partial-write gap.
- **Lint fail-closed:** every check is a named failure, no WARN tier — confirmed. CR-03/CR-13/CR-14 are correctness holes inside that posture, not tier violations.
- **ASVS L1 surface (offline single-user):** operator input length-bounded at 32 chars with an 8 KiB raw-fd guard; `--game-id` validated to alnum+dash (path-traversal safe); no eval/exec/SQL/network; engine output whitelisted-parsed with garbage lines inert. Threat posture appropriate; the journal is the only machine-written parse target and stays inside the trust domain.

---

_Reviewed: 2026-10-27_
_Reviewer: the agent (gsd-code-reviewer)_
_Depth: deep_
