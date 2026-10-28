---
phase: 02-console-protocol-spine
reviewed: 2026-10-28
depth: deep
scope: gap-closure round (commits 90368f13..ceee1b62; merge 17c275b6 + 9f3e6e89, HEAD ceee1b62)
files_reviewed: 14
files_reviewed_list:
  - console/src/console/engine/session.py
  - console/src/console/ui/loop.py
  - console/src/console/game/journal.py
  - console/src/console/main.py
  - console/src/console/log/movelog.py
  - console/src/console/log/lint.py
  - console/src/console/transport/uci.py
  - console/src/console/transport/parser.py
  - console/src/console/game/board.py
  - console/tests/test_session.py
  - console/tests/test_journal.py
  - console/tests/test_movelog.py
  - console/tests/test_e2e_fullgame.py
  - console/tests/fixtures/golden-game.log
findings:
  critical: 0
  high: 1
  medium: 2
  low: 4
  total: 7
status: issues_found
---

# Phase 2 Gap-Closure Round: Code Review Report

**Reviewed:** 2026-10-28
**Depth:** deep (changed paths only; not a re-review of unchanged phase-2 code)
**Files Reviewed:** 14
**Status:** issues_found

## Summary

This review covers only the gap-closure round's changed code paths: the CR-01 undo repair, the fail-silent repairs (CR-06/10/11/12), and the log-truth fixes (CR-02/03/04 + CR-12 main half).

**The four targeted fixes are real.** CR-01's reproduced crash sequence (undo during OUR_SEARCH → corrected opp-move re-entry) is fixed and regression-pinned; CR-02's sign rule is now the correct White-POV normalisation with the `elif value < 0` branch gone; CR-03 seeds alternation from `"w"` unconditionally, matching LOGBOOK §1.4; CR-04's tracer now rides `MoveLog.write_header`/`write_trailer`, derives time-control from the run's clock values, labels the trailer's passthrough clocks honestly, and carries a full 64-hex net digest. The trailer digest flush fix is verified against the committed golden fixture: the file's `# log-sha256` equals the sha256 of the bytes preceding that line (recomputed independently in this review). Verified during review: `PYTHONPATH=vendor:console/src python3 -m unittest console.tests.test_session console.tests.test_journal console.tests.test_movelog` → Ran 67, OK; golden fixture → OK LOG_LINT, rc 0; `git diff 90368f13..ceee1b62 -- docs/PROTOCOL.md docs/LOGBOOK.md` → empty (freeze commit `bd349ec3` predates the round and is an ancestor of its base).

However, the undo repair — the round's centerpiece — has two defects of exactly the class it set out to close: an uncaught crash path when the engine dies during the repair (the console exits instead of surviving, contradicting the round's own "the operator prompt must survive" invariant), and a race window in which an already-answered search's move is validated and played on the rewound board. The header truth fix reintroduces a subtler falsification by omitting the frozen 10-second increment from `# time-control`. Findings below; all line numbers refer to HEAD `ceee1b62`.

---

## High Issues

### H-1: `undo_last_ply` kills the console when the engine dies during the repair — uncaught `RuntimeError`, prompt-survival invariant violated

**File:** `console/src/console/engine/session.py:384-398` with `console/src/console/engine/session.py:453-470` and `console/src/console/transport/uci.py:191-196`; entry `console/src/console/ui/loop.py:136-142, 192-238`

**Issue:** The repair block guards only `queue.Empty`. Two realistic engine-death paths raise instead:

1. The engine has already exited when the operator types `u` (PROTOCOL §9.2 explicitly anticipates mid-game engine death): `self.transport.send("stop")` at `session.py:385` raises `RuntimeError(f"engine exited rc={...}")` (`uci.py:192-193`).
2. The engine dies between the stop and the owed bestmove: the reader thread queues `{"type": "eof"}`, and `_consume_owed_bestmove` raises `RuntimeError("engine EOF before the owed bestmove")` at `session.py:466` — the exception type is not caught by the `except queue.Empty` at `session.py:390`.

In both cases the exception propagates out of `undo_last_ply` → `handle_line` (no try/except on the `u` branch) → `run()` → `run_game`; the console exits mid-game with a traceback. This is the same failure class CR-01 was closed to eliminate, and it directly contradicts the code's own stated intent (`session.py:391-393`: "the operator prompt must survive"; `loop.py` docstring: "the prompt that never dies"). Secondary damage in case 2: the `eof` event is consumed and dropped (not re-queued by the `finally`), and the `RESYNC(applied, plies=1)` record at `session.py:405` is never journaled even though `board.pop()` already ran — so the journal's move list diverges from the live replica exactly when the console dies.

**Fix:** Widen the catch, clear the outstanding go, and journal before proceeding:

```python
if self.transport.outstanding is not None:
    try:
        self.transport.send("stop")            # §1.5: stop first…
    except (RuntimeError, OSError):
        self.transport.outstanding = None
        self._emit({"e": "ENGINE_FAULT", "reason":
                    "undo repair: stop send failed (engine dead?)"})
    else:
        self.transport.mark_discarding()
        self.discarding = True
        try:
            self._consume_owed_bestmove()
        except queue.Empty:
            ...  # existing ENGINE_FAULT path
        except RuntimeError as exc:  # eof before the owed bestmove
            self.transport.outstanding = None
            self._emit({"e": "ENGINE_FAULT", "reason":
                        f"undo repair aborted: {exc}"})
            self.display_cb(f"ENGINE FAULT: {exc}")
        finally:
            self.discarding = False
```

Also re-queue or journal the `eof` event inside `_consume_owed_bestmove` instead of dropping it, and add a test driving `undo_last_ply` with a transport whose `send` raises `RuntimeError` and one whose queue yields `{"type": "eof"}` — neither exists today.

---

## Medium Issues

### M-1: Undo race — an answered-but-unconsumed bestmove bypasses the repair and is played on the rewound board

**File:** `console/src/console/engine/session.py:384` (the `outstanding is not None` gate) with `console/src/console/transport/uci.py:171-188` and `console/src/console/engine/session.py:401-404`

**Issue:** The repair branch keys on `transport.outstanding is not None`, but `_dispatch_bestmove` clears `outstanding` the moment the reader thread receives the current bestmove (`uci.py:180-181`) — before the session has consumed the event. Sequence: opp move X accepted → go outstanding (sid 2) → operator types `u` → the engine's answer M for position P+X arrives in the window after the tick's `drain_events()` but before `undo_last_ply`'s check (the select poll alone makes this window up to ~50 ms; `drain_events` → `select` → `os.read` → `handle_line`) → reader dispatches M as a **current** bestmove and clears `outstanding` → undo sees `outstanding is None`, skips the entire repair, pops X, and re-derives state to `AWAIT_OPP_CONFIRM` without reconciling the queue → the next tick drains M: state is not PONDERING and M is not flagged stale, so `_on_bestmove` validates M against the **rewound replica P**. If M is legal in P (common), it is pushed, announced, and journaled as `src=search` — the engine's answer to a search over the position the operator just rejected is played as our move. If M is illegal in P, the FAULT path catches it; the legal case is silent and lands on the graded artefact path. The round's own piped-smoke notes record that the mock answers in <1 ms — this window is exactly how that smoke raced.

**Fix:** Treat an unanswered live search as repair-needed even when `outstanding` was already cleared — the session's `state` is the discriminator:

```python
if self.state == self.OUR_SEARCH:
    if self.transport.outstanding is not None:
        ...  # existing stop + mark_discarding + consume
    else:
        # answered-but-undrained: sink the stale-position answer
        self.transport._reconcile_queued_bestmoves()
```

`_reconcile_queued_bestmoves` re-flags any queued `bestmove` as `stale_bestmove`, so the drained event is sunk as evidence and never validated against the rewound replica. Add a regression test: `state == OUR_SEARCH`, `outstanding = None`, one `{"type": "bestmove"}` queued, then `undo_last_ply` — assert a `STALE_BESTMOVE` record and no board advance.

### M-2: `format_time_control` omits the frozen 10 s increment — the header understates the actual time control on every log

**File:** `console/src/console/main.py:182-190` (used at `main.py:645`); increment frozen in `console/src/console/transport/uci.py:47-50` and `docs/PROTOCOL.md` §3.1

**Issue:** CR-04.1 replaced the hardcoded `# time-control 15+10` with a derivation from `--clock-ms` — but the derivation computes only the base budget (`w_ms // 60000 + (w_ms % 60000) // 1000`) and ignores the increment, which is not operator-configurable at all: the frozen §3.1 go literal hardwires `winc 10000 binc 10000` on every search. The result is wrong in both directions: a competition run at 15+10 logs `# time-control 15+0`, and the e2e/golden runs at `w=60000,b=60000` log `# time-control 1+0` while actually playing 1+0.1. This is the same graded-artefact falsification class CR-04.1 was closed to remove, reintroduced by omission — and it will be visible to the technical hearing on every delivered log. `format_time_control`'s docstring documents the w≠b deferral but never mentions the increment.

**Fix:** Derive from the same frozen constant the go line uses:

```python
GO_WINC_MS = 10_000  # §3.1 frozen literal — single source with go_line

def format_time_control(w_ms, b_ms):
    minutes = w_ms // 60_000
    seconds = (w_ms % 60_000) // 1000 + GO_WINC_MS // 1000
    return f"{minutes}+{seconds}"
```

(Or define the increment constant once in `console/transport/uci.py` next to `GO_LITERAL` and import it, so the header cannot drift from the wire.) Update the golden fixture and the `# time-control 1+0` assertions in `test_e2e_fullgame.py` accordingly.

---

## Low Issues

### L-1: `queue.Empty` path in the undo repair leaves `transport.discarding` armed forever

**File:** `console/src/console/engine/session.py:390-398` with `console/src/console/transport/uci.py:179-188, 293-296`

**Issue:** The `finally` clears only `self.discarding` (the session's mirror). If `_consume_owed_bestmove` times out — the engine never answered the stop — `transport.discarding` stays `True`, and per `_dispatch_bestmove` the *first* bestmove after that is force-staled and the flag cleared. If the engine recovers and its next answer is the new search's (the stopped search's answer never came), that answer is sunk as stale: no board advance, no announce, and the session sits in `AWAIT_OPP_CONFIRM` with the operator waiting for a move that was discarded. Clearing the transport flag on the timeout path is safe: a late answer to the stopped search is already staled by the `sid != self.search_id` check. Requires a pathological engine (no bestmove within 30 s of stop, then a fresh search answered), hence Low. The FakeTransport used in `test_a_undo_no_answer_to_stop_prompt_survives` does not model `_dispatch_bestmove`'s flag-clearing, so the test cannot see this.

**Fix:** In the `except queue.Empty` branch add `self.transport.discarding = False` (and assert it in the no-answer test against a double that models the real dispatch semantics).

### L-2: `validate_syzygy_path` accepts control characters — UCI line injection and log-header line injection; dead absolute-path check

**File:** `console/src/console/main.py:98-111`; sink into the wire at `console/src/console/engine/session.py` (option queue) → `console/src/console/transport/uci.py:342-343` and into the graded header at `main.py:634-635` → `console/src/console/log/movelog.py:139`

**Issue:** The validation checks existence and (nominally) absoluteness but not content. A `--syzygy-path` containing a newline (`$'/home/x/TB\nquit'`) is written verbatim into `setoption name SyzygyPath value <path>` — injecting a second command into the engine stream — and into the `# setoption` header line of the graded log, injecting an attacker-chosen header line (log-sha256 is computed after the fact, so the injected line is covered by the digest — the artefact silently attests the injected line). The offline single-user context makes this self-inflicted rather than an ASVS L1 boundary crossing, but the flag's whole purpose is to reject bogus input before it reaches the wire, and the existing `--game-id` validator (alnum+dash) sets the project's own bar. Separately, the `if not path.is_absolute()` branch at `main.py:106-107` is dead code: `pathlib.Path(value).expanduser().resolve()` always returns an absolute path, so the check can never fire — the advertised "not an absolute path" rejection does not exist.

**Fix:** Reject control characters and whitespace-breaking content: `if any(c in value for c in "\n\r") or not value.strip(): raise SystemExit(...)`. Either drop the dead `is_absolute` branch or check absoluteness on the pre-`resolve()` string if the absolute-input requirement is meant to be real.

### L-3: Undo's journal shape diverges from the log projection — a rendered log containing an undo fails lint; phantom rows in the replay substrate

**File:** `console/src/console/engine/session.py:405-406` (RESYNC emitted) with `console/src/console/log/movelog.py:89-117` (`build` ignores RESYNC) and `console/src/console/log/lint.py:95-165` (pushes every `uci` row, skips only `# ` lines)

**Issue:** `undo_last_ply` journals the undone ply's original `MOVE_LOGGED` row (append-only — correct), then a `RESYNC(applied, plies=1)`, then the corrected ply's row. `Journal.replay()` honours this for board state, but `MoveLog.build` renders every `MOVE_LOGGED` row and ignores RESYNC records entirely, and `lint_log` replays all `uci` tokens with no pop. Any log rendered from a journal containing an undo therefore carries two consecutive same-side rows (the undone ply and its correction) and an impossible replay sequence — the fail-closed linter fails it on alternation and legality, i.e. a guaranteed "game incident" per LOGBOOK §6.2 for every undo-containing game. `Journal.replay()`'s returned `move_rows` likewise keep the phantom row, which Phase 3's resume will inherit. This is a documented deferral (research Open Question #2; both SUMMARYs record "log-side RESYNC representation remains Phase-3's amendment bundle"), and no Phase 2 artefact path renders an interactive-game log (only the tracer, which cannot undo) — so it is graded Low here, but the undo feature baked the divergence into the substrate this round, and the `undo_last_ply` docstring's "T-02-11 stays aligned" claim is true only for board state, not for the move-row projection.

**Fix (Phase 3, or cheaply now):** Have `MoveLog.build` fold `RESYNC(applied)` into a `# RESYNC …` reserved-prefix line (lint already skips `# ` lines) and have the projection drop the popped rows, or at minimum correct the docstring's alignment claim and file the Phase 3 requirement explicitly.

### L-4: Dead code in `lint.py` — `header` variable and `_parse_header` unused after the CR-03 fix

**File:** `console/src/console/log/lint.py:51-61, 76`

**Issue:** `lint_log` still computes `header = _parse_header(lines)` at line 76, but after the CR-03 change the alternation seed no longer reads `our-color`, and nothing else consumes `header`. `_parse_header`'s only caller is this dead assignment, so the helper is dead too. The docstring patch ("structural reads only") acknowledges the change but the code was not removed. A future reader will assume header parsing still feeds the checks (CR-14's trailer-scan critique of `_parse_header` also becomes moot once it is deleted).

**Fix:** Delete line 76 and `_parse_header` (lines 51-61), or keep it only if a same-round consumer exists (none does).

---

## Verified positives (evidence, not findings)

- **CR-01 repair order is correct for the tested paths:** stop → `mark_discarding` → consume-any-bestmove-shaped-event; the consume-anything design tolerates the reader dispatching a natural bestmove between `send("stop")` and `mark_discarding()` (it is consumed and sunk either way), and `start_search`'s `_reconcile_queued_bestmoves` covers the queued-bestmove case on the refire path. The reproduced crash sequence is pinned by `UndoRealignmentTests`.
- **CR-02 sign rule:** side="w"/None passes the STM value through; only side="b" negates; bound flags ride verbatim; `mate 0` survives negation (`-0 == 0`). Matrix pinned in `ScoreWhiteSignTests` (7 cases).
- **CR-03 seed:** `expect_side = "w"` unconditional; a black-first log still fails (regression-pinned), so the check was not weakened. Real-SF black-side e2e added.
- **CR-11 durability:** the `memoryview` completion loop writes every slice before the single fsync (short-write test monkeypatches a halving `os.write` and proves the record survives intact); `JournalCorruptionError` names path + 1-based line and propagates through `replay()`. The `except (ValueError, json.JSONDecodeError)` clause is redundant (JSONDecodeError subclasses ValueError) but harmless.
- **CR-06 clamp:** the assert is gone; the anomaly path journals `ENGINE_FAULT` and the `MOVE_LOGGED` row is never lost; FSM advances on every path (`TimingAnomalyTests`).
- **Trailer digest:** golden fixture's `# log-sha256 71ff7d53…` independently recomputed as sha256 of the file bytes preceding that line — the `fh.flush()` fix is correct on the committed artefact.
- **Contracts:** `docs/PROTOCOL.md` and `docs/LOGBOOK.md` untouched by the round (empty diff `90368f13..ceee1b62`; last-touch commit `bd349ec3` is an ancestor of the round's base). The full-digest net-sha256 decision satisfies LOGBOOK §5.1 without editing the frozen doc.
- **Test gates re-run in this review:** session+journal+movelog → Ran 67, OK; golden fixture lint → OK LOG_LINT rc 0.

---

## Findings count by severity

| Severity | Count |
|----------|-------|
| critical | 0 |
| high | 1 |
| medium | 2 |
| low | 4 |
| **total** | **7** |

---

_Reviewed: 2026-10-28_
_Reviewer: the agent (gsd-code-reviewer)_
_Depth: deep (changed paths only)_
_Scope note: unchanged phase-2 code was not re-reviewed; CR-05/07/08/09/13/14 and IN-01..08 remain open per 02-REVIEW-DISPOSITION._
