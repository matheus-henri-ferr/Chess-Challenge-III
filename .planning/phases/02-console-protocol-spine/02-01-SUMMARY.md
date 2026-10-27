---
phase: 02-console-protocol-spine
plan: 01
subsystem: api
tags: [uci, transport, subprocess, threading, protocol-contract]

# Dependency graph
requires:
  - phase: 01-competition-rules-freeze
    provides: frozen docs/PROTOCOL.md (§1–§11), tools/mock_engine.py contract mock with fault injectors, tools/mock_gui.py EngineProc pipe discipline, wire-spike evidence convention
provides:
  - console/src/console/transport/uci.py — EngineTransport: framing, reader thread, search_id, discarding, option queue, stderr drain, frozen go builders
  - console/src/console/transport/parser.py — whitelisted line→event parser, bestmove_of
  - console/src/console/main.py — argparse wiring + --transport-smoke (5 wire facts, rc=0 on ./src/stockfish)
  - console/tests/test_transport.py — 9 transport discipline tests (discard orderings, option queue, stderr, garbage, hang)
  - tools/tests/test_contract.py — console↔document↔mock go agreement + console source walk (13→19 tests)
  - evidence/02-wire-spike.log — committed transcript: 5 wire facts on the real binary (2 runs)
affects: [02-02, 02-03, 04-time-management, phase-4-journal]

# Actuals (#2632) — pairs with the plan's `estimate` to calibrate future estimates.
actuals:
  tokens: 21376
  tasks: 3
  commits: 7

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "mock_gui EngineProc pipe discipline as EngineTransport (bufsize=0 raw fd, selector readline, daemon reader thread → queue.Queue)"
    - "stderr to dedicated drain daemon — never merged into the UCI stream (console delta vs mock_gui)"
    - "monotonic search_id 1:1 with one outstanding go; stale bestmoves become typed events, never consumed moves"
    - "option queue flushable only at IDLE behind an isready/readyok sync (§1.4)"
    - "evidence-as-artefact: append-mode --record transcript committed under evidence/"

key-files:
  created:
    - console/src/console/transport/uci.py
    - console/src/console/transport/parser.py
    - console/src/console/main.py
    - console/tests/test_transport.py
    - tools/mock_none_engine.py
    - evidence/02-wire-spike.log
  modified:
    - console/src/console/__init__.py
    - tools/tests/test_contract.py

key-decisions:
  - "wait_for_bestmove raises TimeoutError, not queue.Empty (plan test contract)"
  - "start_search re-flags unconsumed queued bestmoves stale BEFORE handing out the new search_id (RESEARCH Pattern 1, ordering 3)"
  - "ConsoleSourceTests exempts only the FORBIDDEN_GO_TOKENS tuple in uci.py — the §3.2 guard definition is the prohibition, not a use"
  - "Python 3.14 stdlib only; subprocesses with explicit timeout=; tmp artefacts via addCleanup"

patterns-established:
  - "TransportTestBase (make/mock/stub/drain/poll_event) for real-subprocess transport tests"
  - "Scripted UCI stub via python3 -c for discard-ordering injection"
  - "Frozen literals as importable module data asserted across doc/mock/console"

requirements-completed: [PROTO-04]

coverage:
  - id: D1
    description: "EngineTransport completes the PROTOCOL §2 handshake with ./src/stockfish and one full search cycle (frozen §3.1 go literal → whitelisted info → exactly one bestmove) in one runnable command"
    requirement: PROTO-04
    verification:
      - kind: integration
        ref: "PYTHONPATH=vendor:console/src python3 -m console.main --transport-smoke --engine ./src/stockfish --record evidence/02-wire-spike.log (prints 'OK transport smoke: 5 wire facts confirmed', rc=0)"
        status: pass
      - kind: unit
        ref: "console/tests/test_transport.py#GarbageToleranceTests.test_garbage_lines_are_inert_and_search_completes"
        status: pass
    human_judgment: false
  - id: D2
    description: "Go line is the §3.1 literal instantiated in plain and ponder variants; contract tests assert console↔document agreement in both directions"
    requirement: PROTO-04
    verification:
      - kind: unit
        ref: "tools/tests/test_contract.py#GoLiteralTests.test_console_literal_three_way_agreement"
        status: pass
      - kind: unit
        ref: "tools/tests/test_contract.py#GoLiteralTests.test_console_go_line_is_the_document_worked_example"
        status: pass
      - kind: unit
        ref: "tools/tests/test_contract.py#GoLiteralTests.test_console_go_ponder_line_is_the_document_variant"
        status: pass
      - kind: unit
        ref: "tools/tests/test_contract.py#GoLiteralTests.test_console_builder_output_has_no_forbidden_tokens"
        status: pass
    human_judgment: false
  - id: D3
    description: "Bestmove discarded as stale (typed event, no consumer sees it) in all three orderings: late bestmove with no outstanding go; discarding-then-owed-bestmove (flag cleared); unconsumed bestmove re-flagged before the new search id"
    requirement: PROTO-04
    verification:
      - kind: unit
        ref: "console/tests/test_transport.py#DiscardOrderingTests.test_late_bestmove_with_no_outstanding_go_is_stale"
        status: pass
      - kind: unit
        ref: "console/tests/test_transport.py#DiscardOrderingTests.test_discarding_then_owed_bestmove_is_stale_and_cleared"
        status: pass
      - kind: unit
        ref: "console/tests/test_transport.py#DiscardOrderingTests.test_unconsumed_bestmove_reflagged_before_new_search_id"
        status: pass
    human_judgment: false
  - id: D4
    description: "Queued setoption lines flush only at IDLE after isready/readyok; flush while a go is outstanding raises without sending (mock --crash-on-option + record transcript prove the mid-search path unreachable)"
    requirement: PROTO-04
    verification:
      - kind: unit
        ref: "console/tests/test_transport.py#OptionQueueTests.test_flush_at_idle_sends_options_and_mock_survives"
        status: pass
      - kind: unit
        ref: "console/tests/test_transport.py#OptionQueueTests.test_flush_while_outstanding_raises_without_sending"
        status: pass
    human_judgment: false
  - id: D5
    description: "Engine stderr never reaches the stdout parse stream; garbage stdout lines are inert events with no state corruption"
    requirement: PROTO-04
    verification:
      - kind: unit
        ref: "console/tests/test_transport.py#StderrIsolationTests.test_stderr_lands_in_drain_capture_never_in_events"
        status: pass
      - kind: unit
        ref: "console/tests/test_transport.py#GarbageToleranceTests.test_garbage_lines_are_inert_and_search_completes"
        status: pass
    human_judgment: false
  - id: D6
    description: "Spike transcript shows the five live wire facts on the competition binary (CRITICAL ERROR + rc=1, bestmove (none) after score mate 0, one bestmove per go incl. after stop, empty stderr, frozen go literal)"
    requirement: PROTO-04
    verification:
      - kind: other
        ref: "evidence/02-wire-spike.log (greps: 'bestmove (none)', 'CRITICAL ERROR', 'go wtime 600000 btime 600000 winc 10000 binc 10000' all match)"
        status: pass
    human_judgment: false

# Metrics
duration: 24min
completed: 2026-10-27
status: complete
---

# Phase 2 Plan 01: Console UCI Transport Summary

**EngineTransport on the real ./src/stockfish: framed, whitelisted, id-tagged wire with all three stale-bestmove discard orderings proven, setoption locked to IDLE, stderr isolated — 5 wire facts in evidence/02-wire-spike.log.**

## Performance

- **Duration:** 24 min
- **Started:** 2026-10-27T18:29:53Z
- **Completed:** 2026-10-27T18:53:00Z
- **Tasks:** 3
- **Files modified:** 10

## Accomplishments
- EngineTransport drives ./src/stockfish through handshake → frozen go → info stream → exactly one bestmove; smoke prints `OK transport smoke: 5 wire facts confirmed`, rc=0
- All three §7.3 stale orderings tested; setoption queue provably flushable only at IDLE; stderr and garbage isolated
- Contract suite extended: console↔document↔mock three-way go agreement, §3.4/§3.5 worked examples, console source walk for forbidden tokens (13→19 tests)
- Full regression surface green: smoke rc=0, console suite 9 tests, tools suite 37 tests, `OK CONTRACT ORDER`

## Task Commits

Each task was committed atomically:

1. **Task 1: Wire-format spike + transport** - `89db2255` (feat), `ab87e610` (chore: transcript regen), `543da126` (feat: final transport)
2. **Task 2: search_id + discard + option queue + tests** - `3229385e` (feat)
3. **Task 3: Contract test extension** - `42601640` (feat)
4. **Auto-fix: console `__path__` shim** - `8e0384c0` (fix)
5. **Plan verification evidence** - `0d208f83` (chore: transcript append)

**Plan metadata:** pending (docs commit lands after this summary)

_Note: TDD tasks may have multiple commits (test → feat → refactor)_

## Files Created/Modified
- `console/src/console/transport/uci.py` - EngineTransport + frozen go builders
- `console/src/console/transport/parser.py` - whitelisted line→event parser, bestmove_of
- `console/src/console/main.py` - argparse + --transport-smoke
- `console/src/console/__init__.py` - pkgutil-style `__path__` shim (console.tests importable)
- `console/tests/test_transport.py` - 9 transport discipline tests
- `tools/tests/test_contract.py` - console agreement + source walk (13→19 tests)
- `tools/mock_none_engine.py` - (none)-probe helper for the smoke
- `evidence/02-wire-spike.log` - committed wire transcript (2 runs)

## Decisions Made
- `wait_for_bestmove` raises TimeoutError (plan's test contract expects TimeoutError, not queue.Empty)
- `start_search` re-flags unconsumed queued bestmoves stale before the new id is handed out (RESEARCH Pattern 1, ordering 3)
- ConsoleSourceTests exempts only the `FORBIDDEN_GO_TOKENS = (...)` assignment in uci.py — the guard definition is the §3.2 prohibition, not a use
- close() closes stdin (ResourceWarning hygiene)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] console package `__path__` shim**
- **Found during:** plan-level verification (discovered in working tree mid-session)
- **Issue:** the frozen verify command `python3 -m unittest console.tests.test_transport` resolves `console` to console/src/console, which has no tests/ portion — the import errors out
- **Fix:** pkgutil-style `__path__` extension registering the repo-root console/ dir when it carries tests/
- **Files modified:** console/src/console/__init__.py
- **Verification:** stash probe — frozen command errors without the shim (Ran 1 test, errors=1), passes with it (9/9 OK); GPL header intact
- **Committed in:** 8e0384c0

**2. [Rule 2 - Missing Critical] (none)-probe helper**
- **Found during:** Task 1
- **Issue:** smoke's fact-4 probe needs an engine that answers `bestmove (none)` on a legal position
- **Fix:** tools/mock_none_engine.py — deterministic UCI stub (deviation helper file, tools/ scope)
- **Files modified:** tools/mock_none_engine.py
- **Verification:** smoke probe asserts `info depth 0 score mate 0` then `bestmove (none)`
- **Committed in:** 89db2255

---

**Total deviations:** 2 auto-fixed (2 missing-critical)
**Impact on plan:** Both necessary for the frozen verify command to run. No scope creep.

## Issues Encountered
- A shell backtick in one commit message triggered command substitution, garbling it (console shim + evidence commits). Fixed via soft reset to the pre-commit state and recommitted with clean messages; hashes ad153e0c/011b0e2c superseded by 8e0384c0/0d208f83.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- 02-02 (typed-reject parse layer, board replica, session FSM, operator loop) builds directly on EngineTransport's event queue, search_id and discard machinery
- Symbols ready for 02-02: EngineTransport (send, close, events, queue_option, flush_pending_options, handshake, outstanding, discarding, start_search, wait_for_bestmove, mark_discarding), parse_line, bestmove_of, go_line, go_ponder_line, GO_LITERAL, FORBIDDEN_GO_TOKENS, --transport-smoke
- `test_ponder_discard.py` (02-02, CF-7 test-first) inherits DiscardOrderingTests patterns

---
*Phase: 02-console-protocol-spine*
*Completed: 2026-10-27*
