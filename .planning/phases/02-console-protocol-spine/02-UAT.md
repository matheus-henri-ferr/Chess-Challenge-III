---
status: testing
phase: 02-console-protocol-spine
source: [02-01-SUMMARY.md, 02-02-SUMMARY.md, 02-03-SUMMARY.md, 02-04-SUMMARY.md, 02-05-SUMMARY.md, 02-06-SUMMARY.md]
started: 2026-10-28T19:00:00Z
updated: 2026-10-28T19:00:00Z
---

## Current Test

number: 1
name: Undo survives a dead engine (the H-1 death drill)
expected: |
  Start a live console game against ./src/stockfish (python3 -m console.main --engine ./src/stockfish --our-color b --clock-ms w=600000,b=600000). Type an opponent move (e.g. e2e4). While OUR_SEARCH is running, kill the stockfish process (kill -9 <pid>). Then type `u` at the move> prompt.
  Observe: a one-line `ENGINE FAULT: undo repair: …` notice (readable, not lost in scrollback), then `undone: e2e4` echo (or a fault line), and the `move>` prompt still accepting input. No traceback, no exit. A corrected opponent move is then accepted and the game continues.
awaiting: user response

## Tests

### 1. Undo survives a dead engine (the H-1 death drill)
expected: See above — fault line + undone echo + prompt alive, game continues after corrected move.
result: pending

### 2. Interactive feel of the spine (live session)
expected: Run a live session vs ./src/stockfish. Wrong-side move typing shows a readable reject cue; ANNOUNCE appears while idle as `>> ANNOUNCE: <MOVE>` (visually distinct, uppercase, hyphenated); prompt survives typos (Nf3, O-O, 0000, e2e5) with instant typed-error feedback; clock line renders on `t 7:42`.
result: pending

### 3. Full-game happy path both colours (quick confirmation)
expected: A short real game through the console reaches `# result` in the log; log passes log_lint (OK LOG_LINT); both our-color w and b sessions work.
result: pending

## Summary

total: 3
passed: 0
issues: 0
pending: 3
skipped: 0

## Gaps

[none yet]

## Auto-passed (automated coverage)


### 4. EngineTransport completes the PROTOCOL §2 handshake with ./src/stockfish and one full search cycle (frozen §3.1 go literal → whitelisted inf
expected: EngineTransport completes the PROTOCOL §2 handshake with ./src/stockfish and one full search cycle (frozen §3.1 go literal → whitelisted inf
result: pass
source: automated
coverage_id: D1

### 5. Go line is the §3.1 literal instantiated in plain and ponder variants; contract tests assert console↔document agreement in both directions
expected: Go line is the §3.1 literal instantiated in plain and ponder variants; contract tests assert console↔document agreement in both directions
result: pass
source: automated
coverage_id: D2

### 6. Bestmove discarded as stale (typed event, no consumer sees it) in all three orderings: late bestmove with no outstanding go; discarding-then
expected: Bestmove discarded as stale (typed event, no consumer sees it) in all three orderings: late bestmove with no outstanding go; discarding-then
result: pass
source: automated
coverage_id: D3

### 7. Queued setoption lines flush only at IDLE after isready/readyok; flush while a go is outstanding raises without sending (mock --crash-on-opt
expected: Queued setoption lines flush only at IDLE after isready/readyok; flush while a go is outstanding raises without sending (mock --crash-on-opt
result: pass
source: automated
coverage_id: D4

### 8. Engine stderr never reaches the stdout parse stream; garbage stdout lines are inert events with no state corruption
expected: Engine stderr never reaches the stdout parse stream; garbage stdout lines are inert events with no state corruption
result: pass
source: automated
coverage_id: D5

### 9. Spike transcript shows the five live wire facts on the competition binary (CRITICAL ERROR + rc=1, bestmove (none) after score mate 0, one be
expected: Spike transcript shows the five live wire facts on the competition binary (CRITICAL ERROR + rc=1, bestmove (none) after score mate 0, one be
result: pass
source: automated
coverage_id: D6

### 10. Session-owned undo_last_ply: the CR-01 sequence (opp move accepted → go outstanding → undo → corrected opp move e7e6) completes with zero ex
expected: Session-owned undo_last_ply: the CR-01 sequence (opp move accepted → go outstanding → undo → corrected opp move e7e6) completes with zero ex
result: pass
source: automated
coverage_id: D1

### 11. Loop routes `u` through session.undo_last_ply; no direct board.pop in the u branch; prompt survives undo during search (incl. stop-then-sile
expected: Loop routes `u` through session.undo_last_ply; no direct board.pop in the u branch; prompt survives undo during search (incl. stop-then-sile
result: pass
source: automated
coverage_id: D2

### 12. Fail-silent repairs: wall_ms<engine_ms journals ENGINE_FAULT and clamps (no bare assert); handler exception journals ENGINE_FAULT with trace
expected: Fail-silent repairs: wall_ms<engine_ms journals ENGINE_FAULT and clamps (no bare assert); handler exception journals ENGINE_FAULT with trace
result: pass
source: automated
coverage_id: D3

### 13. Journal durability: short-write recovery loop before fsync; torn/garbage line raises JournalCorruptionError with path+line on iter_records a
expected: Journal durability: short-write recovery loop before fsync; torn/garbage line raises JournalCorruptionError with path+line on iter_records a
result: pass
source: automated
coverage_id: D4

### 14. CR-02 closed: score_white_of negates only for side=='b' — white-mover cp -30 stays cp -30; black-mover negates; bound flags ride verbatim; '
expected: CR-02 closed: score_white_of negates only for side=='b' — white-mover cp -30 stays cp -30; black-mover negates; bound flags ride verbatim; '
result: pass
source: automated
coverage_id: D1

### 15. CR-03 closed: a valid '# our-color b' white-first log passes log_lint with zero failures; alternation stays enforced (black-first still fail
expected: CR-03 closed: a valid '# our-color b' white-first log passes log_lint with zero failures; alternation stays enforced (black-first still fail
result: pass
source: automated
coverage_id: D2

### 16. CR-04 closed: the tracer writes real time-control (M+S from --clock-ms), honestly-labelled final-clocks, and a full 64-hex net sha256 throug
expected: CR-04 closed: the tracer writes real time-control (M+S from --clock-ms), honestly-labelled final-clocks, and a full 64-hex net sha256 throug
result: pass
source: automated
coverage_id: D3

### 17. CR-12 closed across both halves: --syzygy-path validated (absolute + existing dir) or loud SystemExit; validated path reaches the engine as 
expected: CR-12 closed across both halves: --syzygy-path validated (absolute + existing dir) or loud SystemExit; validated path reaches the engine as 
result: pass
source: automated
coverage_id: D4


total_auto_passed: 14
