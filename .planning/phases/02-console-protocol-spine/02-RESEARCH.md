# Phase 2: Console Protocol Spine — Research

**Researched:** 2026-10-27
**Domain:** Python operator console — UCI subprocess transport, strict move parsing, board replica, explicit state machine, append-only journal, Rule 9 log projection, `log_lint`
**Confidence:** HIGH — every behavioural claim below was verified this session against the built binary (`./src/stockfish`), the vendored `python-chess` 1.11.2 tree, the frozen contract documents, and the Phase 1 mocks. No web sources were needed or used: the authoritative sources are all in-repo (frozen docs + mocks + vendored library), and live engine behaviour was probed directly.

---

<user_constraints>
## User Constraints

No `CONTEXT.md` exists for this phase (user chose to continue without `/gsd-discuss-phase`). The authoritative scope statements are the ROADMAP Phase 2 section and the frozen contract. **The following are LOCKED — research them, do not propose alternatives.**

### Frozen contract (change-controlled, commit bd349ec3, docs-only)

- `docs/PROTOCOL.md` (11 sections, frozen 2026-10-26) is the console↔engine contract. §3.1 pins the exact go literal: `go wtime <int_ms> btime <int_ms> winc 10000 binc 10000` [VERIFIED: docs/PROTOCOL.md:56-77]. §5 (info fields consumed) and §7 (bestmove handling) are what Phase 2 parses [VERIFIED: docs/PROTOCOL.md:99-157]. Amendment requires a new dated revision + `PROVENANCE.md` note (§11) [VERIFIED: docs/PROTOCOL.md:193-203].
- `docs/LOGBOOK.md` (frozen 2026-10-26) is the Rule 9 log schema: eight mandatory fields per half-move (both colours), `log_lint` fail-closed contract (§6), `src=` variant set (§4), header/trailer (§5), §7.3-style stale discard referenced from PROTOCOL §7.3 [VERIFIED: docs/LOGBOOK.md:27-108].
- `tools/mock_engine.py` and `tools/mock_gui.py` speak the same frozen literals; the console must agree with them. `mock_gui.CSV_COLUMNS = ["move_no","side","uci","depth","nodes","score","engine_ms","wall_ms","pv","tm_trace"]` [VERIFIED: tools/mock_gui.py:43-44]; `bestmove_of` takes the first token after `bestmove` (real SF appends `ponder …`) [VERIFIED: tools/mock_gui.py:128-131]; `go_line()` hardcodes `winc 10000 binc 10000` [VERIFIED: tools/mock_gui.py:146-149].
- Contract regression tests exist and must stay green: `tools/tests/test_contract.py` asserts doc ↔ mock ↔ driver agreement, including `LOG_KEYS = ("move_no","side","uci","depth","nodes","score","pv","engine_ms","wall_ms")` [VERIFIED: tools/tests/test_contract.py:41-42]. Suite currently passes: `python3 -m unittest discover -s tools/tests -t .` → 31 tests OK [VERIFIED: live run 2026-10-27].

### ROADMAP-locked plan shape (Phase 2, 3 plans)

- **02-01** — wire-format spike on the built binary, then ~250-line UCI transport: framing, whitelisted line parsing, monotonic `search_id`, `discarding` flag, stderr drain, option queue applied at `IDLE` (never mid-ponder) [VERIFIED: .planning/ROADMAP.md:70].
- **02-02** — strict UCI parser with typed rejects; board replica + legality gate in both directions; explicit `IDLE → OUR_SEARCH → ANNOUNCE_PENDING → AWAIT_OPP_CONFIRM → OPP_TURN/PONDERING` machine with side-to-move guard; keyboard-only operator loop with instant echo; ANNOUNCE locked to `bestmove`; resync-by-replaying-last-N-moves; **`test_ponder_discard.py` written before the handler** [VERIFIED: .planning/ROADMAP.md:71].
- **02-03** — append-only `fsync` journal + `MoveLog` projection (eight fields for every half-move, `src=ponder|book`, `d=0 n=0`, `engine_ms` and `wall_ms`, bound flags verbatim) + `log_lint`; full game against stock Stockfish [VERIFIED: .planning/ROADMAP.md:72].

### Load-bearing findings encoded by the roadmap (must not be lost)

- **CF-7:** the stale ponder `bestmove` is the most likely game-losing bug — `search_id` + `discarding` flag + one outstanding `go`, with `test_ponder_discard.py` written **before** the handler [VERIFIED: .planning/ROADMAP.md:318].
- **Wire format before parser:** 02-01 spike proves `info string` is not analysis, `bestmove (none)` exists, and `sf_19` exits on an illegal `position` [VERIFIED: .planning/ROADMAP.md:323].
- **`setoption` during a ponder deadlocks the console** — option queue applied at `IDLE`; `TM Latency` is applied there too in Phase 4 [VERIFIED: .planning/ROADMAP.md:324].
- **Ponder stays OFF in Phase 2** (`Ponder=false` frozen until Phase 5 / TM-13) [VERIFIED: docs/PROTOCOL.md:50, :160-161]. The discard machinery is still built and tested now (success criterion 4); actually sending `go ponder` in a game is Phase 5.
- **Clock authority is Phase 3.** Phase 2 never computes budgets: it sends the frozen go line with numbers given to it (for the Phase 2 game, simple remaining-clock passthrough is acceptable as a placeholder until `ClockModel` lands). The console must not pause/adjust any clock on rejection — reject without touching time [VERIFIED: .planning/research/ARCHITECTURE.md:757-763].

### Environment decisions inherited from Phase 1

- Python 3.14.7, **no pip**. `python-chess` 1.11.2 is vendored at `vendor/chess/`, used via `PYTHONPATH=vendor`. Console code imports only stdlib + `chess` from the vendored tree [VERIFIED: `PYTHONPATH=vendor python3 -c "import chess; print(chess.__version__)"` → 1.11.2].
- Real engine binary `./src/stockfish` (SF19 + Rule 4 TB guard), sha256 `527fa7ac4a23e124d207ebe342bbf0cf7c379277770a4073964ef17ce6ed5134` [VERIFIED: evidence/01-binary.sha256; live `sha256sum src/stockfish`].
- Offline during games; no new dependencies may be introduced this phase.
- New Python files carry the GPLv3 header block; new docs carry the `License: GPL-3.0-or-later.` footer (Phase 1 convention) [VERIFIED: .planning/phases/01-*/01-PATTERNS.md:450-461, :661].
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description (from REQUIREMENTS.md) | Research Support |
|----|------------------------------------|------------------|
| PROTO-01 | Strict UCI parser: accept `e2e4`,`g1f3`,`e7e8q`, castles `e1g1`/`e1c1`; tolerate case/spaces; reject SAN (`Nf3`,`e4`,`O-O`), `0000`, malformed tokens with typed errors; every rejected token logged as evidence | `parse_uci` verified behaviour (§Parsing (verified live)); normalization recipe; typed error mapping to `InvalidMoveError`/`IllegalMoveError`; `0000` special case |
| PROTO-02 | Board replica: authoritative FEN + ordered move list, advanced only by validated moves, both sides | python-chess `Board` + `push_uci`; replay path `position startpos moves …`; fullmove/ply semantics verified |
| PROTO-03 | Illegal announced move: no state advance, loop stays live, operator re-announces, event logged with timestamp; illegal `bestmove` never displayed | Legality gate on both directions (§Legality gate); engine `bestmove` validated before ANNOUNCE; REJECT journal record |
| PROTO-04 | ANNOUNCE populated only by `bestmove`, uppercase hyphenated (`E2-E4`, `E7-E8=Q`), visually distinct from PV, locked until bestmove | ANNOUNCE formatter (§Code Examples); PV displayed separately; ANNOUNCE empty until §7.1 line arrives |
| PROTO-05 | Explicit FSM `IDLE → OUR_SEARCH → ANNOUNCE_PENDING → AWAIT_OPP_CONFIRM → OPP_TURN/PONDERING`, transition table, side-to-move guard rejecting two consecutive same-side moves | Full state table (§State machine); guard implemented on the replica's `board.turn` |
| PROTO-06 | Keyboard-only operator entry, always focused, paste-tolerant, instant echo of parsed move + resulting FEN, audible/visual reject cue | `select()`-based main loop pattern (§Operator loop); echo format from Phase-1 research TS-10 |
| PROTO-07 | Resync from board: prefer re-entering last N moves over free FEN edit, with confirmation, `RESYNC` record appended to journal and log, history never rewritten | Resync-by-replay flow (§Resync); log representation flagged in Open Questions |
| PROTO-08 | Opponent clock captured each hand-off via single shortcut (`t 7:42`), tolerant of alternate formats, stored in journal and log | `t` command parsing; journal record; "and log" tension with frozen LOGBOOK schema flagged in Open Questions |
| LOG-01 | One `.log` per game, append-only, incremental flush, all eight fields for every half-move incl. opponent's | `MoveLog` projection over journal (§MoveLog); fsync evidence (§Journal) |
| LOG-02 | Eight fields; `score` verbatim incl. `mate N` and bound flags | Field sources table (§Log fields, verified); bound-flag capture recipe |
| LOG-03 | `engine_ms` (from UCI `info time`, wire ms) AND `wall_ms` (monotonic delta) | PROTOCOL §5.2 + §10.3; `wall_ms ≥ engine_ms` invariant + log_lint check |
| LOG-04 | Book moves `src=book d=0 n=0`; terminal moves logged non-empty (`src=none`, `uci=(none)`, `mate 0`) | LOGBOOK §4.2/§4.6 verbatim; verified live: `info depth 0 score mate 0` precedes `bestmove (none)` |
</phase_requirements>

---

## Summary

Phase 2 builds the console spine: a Python process that owns a Stockfish subprocess over UCI pipes, a strict input/parse layer, a python-chess board replica, an explicit finite state machine, an append-only journal, and the Rule 9 log projection with a fail-closed linter. The plan shape (transport → parser/FSM/operator loop → journal/log/lint + full game) is already locked in the ROADMAP; this research verifies every wire-level and library-level fact those plans depend on, so the planner can write tasks without re-deriving behaviour.

All load-bearing behaviour was **verified live this session** against the built binary and the vendored library. The engine answers `bestmove <move> ponder <move>`, emits `bestmove (none)` on mate/stalemate preceded by `info depth 0 score mate 0`, exits with code 1 after printing `info string CRITICAL ERROR: …` on an illegal `position` line, answers exactly one `bestmove` per `go` (including after `stop`, and after a double `stop`), says nothing on `stop` with no search running, and emits the `info string TB ceiling OK: SyzygyProbeLimit=5 max_loaded=0` attestation on every search. `go ponder` + `stop` returns the bestmove **for the speculative position** — the exact stale-move hazard CF-7 warns about. Engine stderr is empty during normal UCI operation (only `bench` writes stderr), startup to `uciok`/`readyok` is ~1.1 s (NNUE load dominates), and `fsync`-per-record journaling measured 0.010 ms/record at game scale — durability is free.

On the library side, `Board.parse_uci()` raises `InvalidMoveError` for malformed/SAN-shaped tokens and `IllegalMoveError` for legal-syntax-but-illegal moves — but it **accepts `0000`** (null move) without raising, does **not** accept uppercase (`E2E4` raises), silently normalises Chess960-style castle targets (`e1h1` → `e1g1`), and `Move.null()` is never in `legal_moves`. The console therefore needs a small explicit normalization + reject layer *in front of* `parse_uci` to get PROTO-01's typed rejects exactly right. The `parse_san` path exists but must never be reachable from the operator loop in Phase 2 (SAN rejection is a requirement, not an accident).

**Primary recommendation:** build the transport exactly as 02-01 sketches (raw pipes, `bufsize=0`, selector on the raw fd, reader thread → queue, monotonic `search_id`, `discarding` flag, option queue drained at `IDLE`), gate every move in both directions through one `parse_uci`-based function preceded by a normalizer, write `test_ponder_discard.py` first against `mock_engine --stale-bestmove`, and make `MoveLog` a pure projection of the fsynced journal so the log can never diverge from the event history.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| UCI wire transport (framing, search_id, discard) | Console process (Python) | — | UCI has no request ids; serialisation + ids are the only correct discipline (PROTOCOL §1.3, §7.3) |
| `info` line parsing (whitelisted) | Console process | — | Engine output is untrusted text; whitelist prevents state corruption (PROTOCOL §9.3) |
| Board replica + legality gate | Console process (python-chess) | — | R5/R10: both sides mirrored in software; engine is never the source of truth |
| State machine + side-to-move guard | Console process | — | Single authority over protocol phase; engine has no notion of game phase |
| Operator entry loop (keyboard) | Console process | — | R10 spoken protocol; Rule 9 declares CLI sufficient |
| ANNOUNCE rendering | Console process | — | UI-only concern; derived exclusively from `bestmove` |
| Opponent-clock capture (`t` shortcut) | Console process (journal) | Clock model (Phase 3 consumer) | Phase 2 stores observations; interpretation is CLOCK-01's job |
| Journal (append-only, fsync) | Console process | — | Crash-recovery substrate for Phase 3 `resume` (CLOCK-06) |
| Rule 9 log + `log_lint` | Console process | — | R9 deliverable is console-authored (LOGBOOK §1.1) |
| Search/time allocation | Engine process | — | Console sends reserve-discounted `wtime/btime`; never `movetime` (PROTOCOL §3.2) |
| Clock belief/watchdog/scramble | **Phase 3 — do not build** | — | CLOCK-01…05; Phase 2 only avoids contradicting it |

---

## Standard Stack

### Core

| Component | Version | Purpose | Why Standard | Confidence |
|-----------|---------|---------|--------------|------------|
| Python | 3.14.7 (host) | Console runtime | Only runtime available; no pip | HIGH [VERIFIED: `python3 --version`] |
| `vendor/chess` (python-chess) | 1.11.2 | Board, legality, FEN, move objects | R14-permitted; vendored Phase 1; zero deps | HIGH [VERIFIED: live import] |
| `./src/stockfish` | SF19 + TB guard, sha256 527fa7ac… | Engine subprocess | The competition binary; provenance recorded | HIGH [VERIFIED: evidence/01-binary.sha256] |
| stdlib `subprocess`, `selectors`, `threading`, `queue` | 3.14 | Pipe transport, reader thread, event queue | `selectors`+raw-fd pattern already proven in `mock_gui.py` | HIGH [VERIFIED: tools/mock_gui.py:78-103] |
| stdlib `unittest` | 3.14 | Test framework | Phase 1 decision: pytest absent, cannot install offline | HIGH [VERIFIED: 01-PATTERNS.md:605; suite runs] |
| stdlib `os` (`O_APPEND`, `fsync`) | 3.14 | Journal durability | Verified 0.010 ms per fsynced record at game scale | HIGH [VERIFIED: live microbenchmark] |

### Supporting

| Component | Version | Purpose | When to Use |
|-----------|---------|---------|-------------|
| `tools/mock_engine.py` | Phase 1 | Contract-faithful misbehaving engine (11 scenario flags) | All transport/FSM unit tests [VERIFIED: tools/mock_engine.py:218-234] |
| `tools/mock_gui.py` | Phase 1 | Reference driver patterns (`bestmove_of`, `go_line`, selector readline) | Copy patterns, not code — console is a different process shape |
| `tools/tests/test_contract.py` | Phase 1 | Doc↔mock↔driver agreement tests | Extend with console↔doc agreement tests |
| `readline` (stdlib) | 3.14 | Prompt line editing | Available on host [VERIFIED: live import]; optional nicety for the operator prompt |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Hand-rolled UCI transport | `chess.engine` (vendored async client) | The vendored client works (verified: `popen_uci` + `play()` with `INFO_ALL` returns depth/time correctly). **Rejected because plan 02-01 is locked**: the console needs `search_id`, `discarding`, and queue semantics the client does not expose, and the client's `time` is converted to seconds (float) while the log needs wire milliseconds (PROTOCOL §5.2). Keep the client for tooling only. |
| Threads + selectors | asyncio | The locked plan and Phase 1 mocks are synchronous/select-based; asyncio adds a second concurrency model to a 2-day phase for no gain. |
| `input()` for the operator loop | `select()` on fd 0 | A blocking `input()` hides ANNOUNCE updates while the operator sits at the prompt. The loop must poll both the engine queue and stdin (ARCHITECTURE anti-pattern 7). `select()` on Linux stdin is verified available. |

**Installation:** none. No new packages. `Package Legitimacy Audit` below is trivially satisfied.

---

## Package Legitimacy Audit

No external packages are installed by this phase (offline rule; everything is stdlib or already-vendored Phase 1 artefacts).

| Package | Registry | Age | Downloads | Source Repo | Verdict | Disposition |
|---------|----------|-----|-----------|-------------|---------|-------------|
| *(none — no installs this phase)* | — | — | — | — | — | — |

- `python-chess` 1.11.2 was vetted and vendored in Phase 1 with `SHA256SUMS` tree pinning [VERIFIED: PROVENANCE.md dependency table; vendor/chess/SHA256SUMS exists].
- **Packages removed due to [SLOP] verdict:** none.
- **Packages flagged as suspicious [SUS]:** none.

---

## Verified Wire Facts (live probes, 2026-10-27)

Every row below was produced by driving `./src/stockfish` (sha256 527fa7ac…) over pipes this session. These are the facts 02-01's spike must re-confirm before the parser is written.

| Stimulus | Verified response |
|---|---|
| `uci` | `id name Stockfish 19`, `id author …`, full option list, `uciok` (last) |
| `isready` | `readyok` |
| Handshake wall time | ~1.1 s total process start→readyok (NNUE load dominates; consistent across runs) |
| `position startpos` + `go wtime 5000 btime 5000 winc 10000 binc 10000` | `info depth N … time <ms> pv …` stream, then `bestmove e2e4 ponder e7e5` |
| `bestmove` token shape | first token after `bestmove` is the move; optional `ponder <move>` suffix follows [VERIFIED: matches `mock_gui.bestmove_of`] |
| Stalemate/mate position (`7k/5Q2/6K1/8/8/8/8/8 b`) | `info depth 0 … score mate 0 …` then `bestmove (none)` |
| Illegal `position startpos moves z9z9` | `info string CRITICAL ERROR: Command `position startpos moves z9z9` failed. Reason: Illegal move: z9z9` on **stdout**, then process exit **rc=1** |
| `stop` during search | exactly **1** `bestmove` for the interrupted search |
| `stop` twice during one search | still exactly **1** `bestmove` |
| `stop` with no search running | no output, no error |
| `go ponder` (speculative position) then `stop` | `bestmove` **for the speculative position** (verified: position `…g1f3 b8c6` → `bestmove a2a3`, a move valid only after `b8c6`) — the stale-move hazard |
| `go ponder` then `ponderhit` | `bestmove f1b5 ponder g8e7` — the reply to the pondered position |
| During ponder search | `info` lines stream normally (~16 lines in 1.5 s at 1 thread; scales with Threads) |
| Every search start | `info string TB ceiling OK: SyzygyProbeLimit=5 max_loaded=0` (Phase 1 attestation; console may assert it) |
| stderr during all UCI ops | **empty** (only `bench` writes stderr) |
| Option names on the wire | `Threads`, `Hash`, `Ponder`, `Move Overhead`, `SyzygyPath`, `SyzygyProbeLimit` (spaces in option names are literal) |

Wire facts already proven by Phase 1 and cited by the frozen docs: `time` is milliseconds on the wire (PROTOCOL §5.2) [VERIFIED: docs/PROTOCOL.md:105-107]; `score` is side-to-move POV (§5.3); the consumed token set is exactly §5.1's whitelist (§5.1); one `go` outstanding (§1.3); no `setoption` mid-search (§1.4).

---

## Parsing (verified live, `vendor/chess` 1.11.2)

`Board.parse_uci()` is the legality core, but its exact edge behaviour dictates a thin console wrapper in front of it:

| Input (startpos) | Verified result | Console action |
|---|---|---|
| `'e2e4'` | returns `Move` | push |
| `'E2E4'` | raises `InvalidMoveError: invalid uci: 'E2E4'` | **normalize to lowercase first** (PROTO-01: tolera caixa) |
| `' e2 e4 '` | — | strip spaces before parse (PROTO-01: tolera espaços) |
| `'e2-e4'` | raises `InvalidMoveError` | reject (hyphen is output-only formatting) |
| `'Nf3'` (SAN) | raises `InvalidMoveError: expected uci string to be of length 4 or 5` | reject with TYPED_SAN — but see note below |
| `'O-O'` | raises `InvalidMoveError` (length) | reject TYPED_SAN |
| `'0000'` | **returns `Move.null()` without raising** | reject **before** `parse_uci` — TYPED_NULL (PROTO-01 explicitly rejects `0000`) |
| `'xyz'` | raises `InvalidMoveError: expected uci string to be of length 4 or 5` | reject TYPED_MALFORMED |
| `'e2e5'` (illegal) | raises `IllegalMoveError: illegal uci: 'e2e5' in <fen>` | reject TYPED_ILLEGAL |
| `'e1h1'` (Chess960 castle spelling, on a castling board) | returns the **e1g1** move silently | accept-and-normalise is harmless; PROTO-01's accepted forms are `e1g1`/`e1c1` — no special handling needed, but do not advertise `e1h1` in help text |
| `'e7e8'` (missing promo, multiple promos legal) | raises (needs suffix) | detect promotion-ambiguity and re-prompt with the four legal suffixes (`a7a8q/r/b/n` verified) |
| `'e5f6'` (en passant, given the right FEN) | returns the ep move | push normally; python-chess handles ep state |
| `chess.Move.null() in board.legal_moves` | `False` (always) | second layer of the `0000` guard |

Two error classes, both `ValueError` subclasses, are the typed-reject vocabulary [VERIFIED: vendor/chess/__init__.py:160-170]:

```python
class InvalidMoveError(ValueError):   # syntax: malformed, SAN-shaped, wrong length
    """Raised when move notation is not syntactically valid"""

class IllegalMoveError(ValueError):   # legal syntax, illegal in position
    """Raised when the attempted move is illegal in the current position"""
```

**Note on SAN rejection:** `parse_san('Nf3')` works and returns `g1f3`. PROTO-01 requires SAN to be **rejected with a typed error**, not silently translated. Do not route operator input through `parse_san` at all in Phase 2; the length-4/5 gate plus the fact that SAN strings are not valid UCI gives the rejection for free. (If the team later wants SAN fallback for the operator, that is a Phase 6+ drill-driven decision — out of scope here.)

**Side metadata for the log** [VERIFIED: live]:
- `board.fullmove_number` is the number of the move **in progress** (after white's `e2e4` it is still 1; after black's reply it is 2) → `move_no` = `fullmove_number` at the moment the move is made. `mock_gui`'s independent formula `(len(moves)+2)//2` agrees [VERIFIED: tools/mock_gui.py:195].
- `side` = `"w" if board.turn == chess.WHITE else "b"` **before** the push (the side that made the move).
- `board.ply()` counts half-moves from the start position — useful for book-cap and replay bookkeeping.
- `board.outcome(claim_draw=False)` returns `Outcome(termination=Termination.*, winner=None|WHITE|BLACK)`; the `Termination` enum carries `CHECKMATE, STALEMATE, INSUFFICIENT_MATERIAL, SEVENTYFIVE_MOVES, FIVEFOLD_REPETITION, FIFTY_MOVES, THREEFOLD_REPETITION, VARIANT_*` [VERIFIED: live]. Phase 2 logs terminal state; *claiming* draws is the arbiter's (R12) — detect and display, never self-adjudicate.

---

## Architecture Patterns

### System Architecture Diagram

```
                ┌────────────────────────────────────────────────────────────┐
                │                     CONSOLE PROCESS (Python 3.14)          │
                │                                                            │
 operator ──▶──▶│  ┌──────────────┐   parsed    ┌───────────────────────┐    │
 keyboard       │  │ OperatorLoop │◀── events ──│   EngineEvent queue   │    │
 (select fd 0)  │  │ (prompt, echo│   (queue)   └───────────▲───────────┘    │
                │  │  ANNOUNCE,   │                         │ parse          │
                │  │  commands)   │                         │ (whitelist)    │
                │  └──────┬───────┘              ┌──────────┴───────────┐    │
                │         │ validated actions    │  Transport (02-01)   │    │
                │         ▼                      │  reader thread       │    │
                │  ┌──────────────┐   go/stop/  │  search_id counter   │    │
                │  │   Session    │──▶ position │  discarding flag     │    │
                │  │ (FSM, guard) │    go       │  option queue@IDLE   │    │
                │  └──────┬───────┘             └──────────┬───────────┘    │
                │         │ move_logged / reject /         │ pipes          │
                │         ▼ stale_bestmove / resync       ▼                │
                │  ┌──────────────┐                ┌──────────────┐        │
                │  │   Journal    │                │ src/stockfish│        │
                │  │ (append-only │                │ (SF19, TB≤5) │        │
                │  │  + fsync)    │                └──────────────┘        │
                │  └──────┬───────┘                                        │
                │         │ replay                                         │
                │         ▼                                                │
                │  ┌──────────────┐   ┌─────────────┐                      │
                │  │  BoardState  │──▶│  MoveLog    │──▶ game-<id>.log     │
                │  │ (python-chess│   │ (projection)│   (8 fields/line)    │
                │  │  legality)   │   └─────────────┘        ▲              │
                │  └──────────────┘                          │ log_lint    │
                │                                            └─ fail-closed │
                └────────────────────────────────────────────────────────────┘
```

Trace of the primary use case: operator types opponent's move → normalize → `parse_uci` (typed reject on failure, loop stays live, REJECT journal record) → push to replica → journal `MOVE_LOGGED(src=opp)` → FSM OPP_TURN → OUR_SEARCH: `position startpos moves …` + frozen go line → engine streams `info` (whitelisted parse; PV displayed as PV) → `bestmove` arrives → validate against replica → ANNOUNCE field shows uppercase hyphenated form only now → operator announces, moves, presses → next opponent move.

### Recommended Project Structure

```
console/
├── src/console/
│   ├── __init__.py
│   ├── main.py                 # wiring only: config → transport → session → loop
│   ├── transport/
│   │   ├── __init__.py
│   │   ├── uci.py              # subprocess, reader thread, search_id, discarding,
│   │   │                       #   option queue, stderr drain, go_line builder
│   │   └── parser.py           # whitelisted info/bestmove/option line → events
│   ├── engine/
│   │   ├── __init__.py
│   │   └── session.py          # FSM: IDLE/OUR_SEARCH/ANNOUNCE_PENDING/
│   │                           #   AWAIT_OPP_CONFIRM/OPP_TURN/PONDERING/DISCARDING
│   ├── game/
│   │   ├── __init__.py
│   │   ├── board.py            # BoardState: replica + normalization + legality gate
│   │   ├── moves.py            # typed-reject parse layer (PROTO-01)
│   │   └── journal.py          # append-only fsync event log + replay
│   ├── log/
│   │   ├── __init__.py
│   │   ├── movelog.py          # Rule 9 projection (LOGBOOK §3 line format)
│   │   └── lint.py             # log_lint (LOGBOOK §6, fail-closed)
│   └── ui/
│       ├── __init__.py
│       └── loop.py             # operator prompt, echo, ANNOUNCE, command dispatch
└── tests/
    ├── __init__.py
    ├── test_ponder_discard.py  # WRITTEN FIRST (CF-7)
    ├── test_transport.py
    ├── test_moves.py           # typed-reject matrix incl. 0000/uppercase/SAN
    ├── test_board.py           # replica replay, side guard, terminal detection
    ├── test_journal.py         # replay == live state; kill -9 tolerance
    ├── test_movelog.py         # line format vs LOGBOOK §3; log_lint cases
    └── test_e2e_fullgame.py    # mock-driven full game incl. opp + terminal moves
```

Package names above are the ARCHITECTURE.md §6 layout restricted to Phase 2 scope; `clock/`, `game/match.py`, `book/` are deliberately absent (Phases 3/5) [VERIFIED: .planning/research/ARCHITECTURE.md:587-613]. Layout rationale: `src/` stays a clean Stockfish derivative; console lives in its own top-level tree.

### Pattern 1: Transport — one outstanding `go`, monotonic `search_id`, `discarding` flag

**What:** The transport owns the pipe discipline. Exactly one `go` in flight (PROTOCOL §1.3); every `go` increments `search_id`; any `bestmove` whose id is not the current one, or that arrives while `discarding` is set, is journaled as `STALE_BESTMOVE` and dropped [VERIFIED: docs/PROTOCOL.md:151-154; .planning/research/ARCHITECTURE.md:665-686].

**When to use:** Always. This is CF-7, the single most likely game-losing bug.

**Three discard orderings the tests must cover:**

1. **Late bestmove, no go outstanding** — engine answers after the console already consumed a bestmove and moved on (search_id mismatch / `outstanding is None`).
2. **Post-stop drain** — ponder miss: console sends `stop`, sets `discarding=True`, **waits for the owed bestmove before the next `go`** (PROTOCOL §1.3 forbids two outstanding), records `STALE_BESTMOVE`, then issues the real search. Verified: the engine always owes exactly one bestmove after `stop`.
3. **Unconsumed bestmove at send time** — a bestmove nobody consumed yet when a new search is prepared (the `mock_gui.pending_bestmove` case) [VERIFIED: tools/mock_gui.py:62, :153-155].

**Pipe mechanics — copy mock_gui's proven pattern, do not reinvent:**

```python
# Source: tools/mock_gui.py:53-103 (verified in-repo; the buffering comment is load-bearing)
# Binary, unbuffered pipes: select() must see every byte the child writes.
# TextIO buffering here deadlocks (buffer drains the fd, select then times out
# on data we already own — verifier G1).
self.popen = subprocess.Popen(
    argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
    stderr=subprocess.DEVNULL,   # console: drain-and-discard (bench is the only writer)
    bufsize=0,
)
# readline(): select() on the raw fd, os.read into own buffer, split on b"\n",
# real timeout, EOF → RuntimeError("engine EOF …")  (PROTOCOL §9.2 territory)
```

Console-specific deltas vs the mock driver:
- **stderr**: separate pipe drained by a daemon thread (or `DEVNULL`); never merged into the UCI stream — a stderr line interleaved into stdout parsing would corrupt framing. Verified stderr is empty in normal ops, but `bench`/crash text must never reach the parser.
- **Reader thread** (not inline readline): the operator loop must stay live while `info` floods. Reader thread → `queue.Queue` → main loop polls [VERIFIED: .planning/research/ARCHITECTURE.md:751-755 anti-pattern 7].
- **Timeouts**: per-read selector timeout (hang detection is Phase 3's watchdog, but Phase 2 still needs a read timeout so a `--silent-hang` mock cannot wedge tests); `uciok` timeout of 10 s is contractual (PROTOCOL §2.1) [VERIFIED: docs/PROTOCOL.md:35-36].
- **Option queue**: `setoption` lines are queued by the session and flushed **only at `IDLE`**, immediately after handshake and after every drain-to-bestmove — never mid-search, never during PONDERING (PROTOCOL §1.4; deadlock hazard CF Roadmap) [VERIFIED: docs/PROTOCOL.md:23-24; .planning/ROADMAP.md:324].

### Pattern 2: Session FSM — the transition table

States (ROADMAP-locked names): `IDLE`, `OUR_SEARCH`, `ANNOUNCE_PENDING`, `AWAIT_OPP_CONFIRM`, `OPP_TURN`, `PONDERING` (+ internal `DISCARDING` between PONDERING and the next go).

| State | Event | Next state | Action |
|---|---|---|---|
| `IDLE` | operator enters opp move (legal) | `OUR_SEARCH` | push replica, journal `MOVE_LOGGED(src=opp)`, send `position startpos moves …` + frozen go line, `search_id += 1` |
| `IDLE` | queued options pending | `IDLE` | flush option queue, `isready`/`readyok` sync first |
| `OUR_SEARCH` | `info` line | `OUR_SEARCH` | update PV display, capture last depth/nodes/score/time/pv for the move record |
| `OUR_SEARCH` | `bestmove` (current id) | `ANNOUNCE_PENDING` | validate vs replica; on illegal → fallback + FAULT (PROTO-03: never displayed); on `(none)` → terminal path; else ANNOUNCE = format(move); journal `MOVE_LOGGED(src=search)` |
| `ANNOUNCE_PENDING` | operator confirms announced/moved/pressed | `AWAIT_OPP_CONFIRM` | operator-side step; console just records the hand-off |
| `AWAIT_OPP_CONFIRM` | opp announces + repeats | `AWAIT_OPP_CONFIRM` | nothing to the engine; this is human protocol time |
| `AWAIT_OPP_CONFIRM` | opp move typed (legal) | `OPP_TURN`→ wait — see guard below | side-to-move guard: it is still OUR colour to move conceptually — the opp move is entered only after they announce at their turn |
| `OPP_TURN` | opp move typed (legal) | `OUR_SEARCH` (via IDLE step) | push, journal `MOVE_LOGGED(src=opp)`, new search |
| `OPP_TURN` | `t <time>` | `OPP_TURN` | journal `OPP_CLOCK(raw, parsed_ms)` (PROTO-08) |
| `OPP_TURN` | (`Ponder=true`, Phase 5 only) after our bestmove carries `ponder X` | `PONDERING` | send speculative `position … moves … X` + `go ponder` |
| `PONDERING` | opp move == speculation | `OUR_SEARCH` | `ponderhit` (Phase 5) |
| `PONDERING` | opp move ≠ speculation | `DISCARDING` | `stop`; `discarding = True`; **wait** for owed bestmove → `STALE_BESTMOVE` → then real position + go |
| any | engine EOF / `CRITICAL ERROR` | `IDLE` (+ fault banner) | journal `ENGINE_FAULT`; restart+replay is Phase 3 supervision (CLOCK-05), but Phase 2 must detect, surface, and not corrupt state |
| any | typed illegal / malformed / wrong-side input | unchanged | typed reject, prompt stays live, clock untouched, journal `REJECT(token, reason)` |

**Side-to-move guard (PROTO-05):** the replica's `board.turn` is the guard. Before accepting any operator move, assert the side that must move now matches the input's role (opp move expected when `board.turn` == opponent colour). Two consecutive same-side moves are structurally impossible after a successful push — a second opp move without our move in between fails the guard because `board.turn` still says opponent... precisely: after the opp move is pushed it is *our* turn, so another "opp move" input is rejected as wrong-side. Unit-test both directions.

**Reachability note:** with `Ponder=false` frozen for Phase 2 [VERIFIED: docs/PROTOCOL.md:50], `PONDERING`/`DISCARDING` are unreachable in real games this phase — the machinery is still required and is exercised by `test_ponder_discard.py` via `mock_engine --stale-bestmove` and via direct transport-level injection. This is a planning decision, not an engine fact; the ROADMAP success criterion 4 demands the test regardless [VERIFIED: .planning/ROADMAP.md:65].

### Pattern 3: Event-sourced journal, log as projection

**What:** every accepted move, reject, stale bestmove, resync, opp-clock reading, and fault appends an immutable record to one JSONL file with `os.fsync` per record. `MoveLog` is a pure projection; it never writes a parallel history [VERIFIED: .planning/research/ARCHITECTURE.md:633-664; .planning/research/FEATURES.md TS-14/TS-17].

**Cost:** verified negligible — 120 fsynced records took 1.3 ms total (0.010 ms each) on this machine [VERIFIED: live microbenchmark]. A game is ~120–300 records.

```python
# journal.py — the entire mechanism (ARCHITECTURE.md Pattern 1, verified shape)
def append(event: dict) -> None:
    event["t_mono_ms"] = time.monotonic_ns() // 1_000_000
    line = json.dumps(event, separators=(",", ":")) + "\n"
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
    os.write(fd, line.encode())
    os.fsync(fd)
    os.close(fd)
```

Phase 2 event vocabulary (Phase 3 extends, never rewrites): `GAME_START`, `MOVE_LOGGED`, `REJECT`, `STALE_BESTMOVE`, `OPP_CLOCK`, `RESYNC`, `ENGINE_FAULT`, `GAME_END`. Resume-from-journal is Phase 3 (CLOCK-06); Phase 2 only guarantees the journal is complete enough to replay the board + log.

### Pattern 4: MoveLog line format — transcribe, do not paraphrase

Frozen line format [VERIFIED: docs/LOGBOOK.md:50-58]:

```
src=<src> move_no=<int> side=<w|b> uci=<uci> depth=<int> nodes=<int> score=<score> score_white=<score|-> engine_ms=<int> wall_ms=<int> pv=<moves>
```

- `pv` goes **last, unquoted** (frozen choice, no alternatives) [VERIFIED: docs/LOGBOOK.md:56-58].
- Key order is stable; no per-line keys may be invented (§3.3).
- `src` closed set: `search`, `book`, `tb`, `ponder`, `opp`, `none` [VERIFIED: docs/LOGBOOK.md:63-82].
- `score` is STM-POV **verbatim** including `lowerbound`/`upperbound`; `score_white` is the additional White-POV normalisation, `-` when absent [VERIFIED: docs/LOGBOOK.md:40-42].
- `engine_ms` = `info time` wire milliseconds; `wall_ms` = `monotonic_ns()` delta; `wall_ms ≥ engine_ms` always [VERIFIED: docs/LOGBOOK.md:44-46; enforced by mock_gui.py:292-295].
- Per-variant fills: `opp` → `depth=0 nodes=0 score=- engine_ms=0`, wall measured, `uci` = parsed input; `book` → `d=0 n=0 score=book pv=<move> engine_ms=0`; `none` → `uci=(none) depth=0 nodes=0`, non-empty score (`mate 0` verified live); `ponder` → logged for the record, never announced [VERIFIED: docs/LOGBOOK.md:63-82].

**Bound-flag capture:** walk tokens after `score`: value is `cp <int>` or `mate <int>` (two tokens), then an optional trailing `lowerbound`/`upperbound`. Keep the raw substring for `score=`; compute `score_white` from the numeric part (see Open Questions for the flag-under-negation decision). The `mock_gui` parser demonstrates the two-token + flag shape [VERIFIED: tools/mock_gui.py:177-186].

**Header/trailer (§5):** Phase 2 writes a complete header with values it can compute now — game id, date, our colour, time control, engine binary sha256 (recompute at game start), net sha256 (from PROVENANCE/`vendor` data), the exact `setoption` set sent, effective `SyzygyProbeLimit` (assert 5 at startup; the engine attests it), `network=off` — and placeholder-safe values for TB inventory hash / book hash+max ply (no book and no TB directory decision belongs to Phase 2/3; use `none`/`0` and let Phase 3's CHECK-01 own the real inventories). Trailer: result, reason, both final clocks as observed, log sha256. log_lint checks presence and shape, not asset correctness, in Phase 2 (see Open Questions).

### Pattern 5: `log_lint` — fail closed [VERIFIED: docs/LOGBOOK.md:94-108]

Every check is a failure, never a warning:
- all ten keys (`src`, eight fields, `score_white`) present per move line;
- `move_no` monotonically non-decreasing; `side` alternates `w`,`b`;
- `uci` legal in the replayed position (or `(none)` for `src=none`);
- `pv` non-empty (the move itself counts for book/tb);
- `wall_ms ≥ engine_ms`;
- no `src=` outside the §4 set;
- header and trailer present and complete (§5).

Implementation shape: replay the log's `uci` sequence through a fresh `chess.Board` from `startpos` (or the header's start), pushing each move — the same replay the engine gets. A log that passes is the deliverable; a failing log is a game incident.

### Anti-Patterns to Avoid

- **Playing the ponder `bestmove`** — a single bestmove handler with no ids plays a move for a position that does not exist. search_id + `discarding` + test-first. (ARCHITECTURE anti-pattern 3; CF-7.)
- **`setoption` mid-search** — queues at `IDLE` only. (Anti-pattern 6; verified deadlock hazard in PITFALLS D5.)
- **TextIO + select()** — `bufsize=0` raw fd reads only. The buffering deadlock is documented and verified in mock_gui (verifier G1).
- **Blocking console** — never `communicate()`/inline-blocking read of bestmove; reader thread + queues. (Anti-pattern 7.)
- **Pausing the clock on rejection** — reject without touching time; show "clock running". Phase 2 has no clock model, but the loop must not sleep/block on reject either. (Anti-pattern 8.)
- **Merging stderr into the UCI stream** — drain separately. (mock_gui merges because it is a dev driver; the console must not.)
- **Rebuilding the board from the engine's position string** — `BoardState` + journal are authoritative; the engine is re-fed the corrected list. (Anti-pattern 5.)
- **Free-FEN resync** — prefer re-entering the last N moves (PROTO-07); free FEN editing is how unplayable side-to-move/castling states happen (PITFALLS D4).
- **Parsing `info` with regex over the whole line** — token-walk the whitelisted set; bound flags, `info string`, and PV-last ordering will defeat naive regexes (PITFALLS D5; STACK.md "Parsing UCI info with a hand-rolled regex" avoided).
- **Treating `bestmove 0000`/`(none)` as a move** — `(none)` verified live; handle both explicitly (PITFALLS D5).

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Legality, FEN, ep, castling, promotion, outcome | Custom move generation | `vendor/chess` (`Board`, `parse_uci`, `legal_moves`, `outcome`) | R14 explicitly permits; edge cases (ep FEN semantics, 960 castle normalisation) are a bug farm [VERIFIED: live probes] |
| Zobrist/position keys (threefold) | Custom hashing | `chess.polyglot.zobrist_hash` / transposition-key | Phase 3 needs it (CLOCK-07); python-chess provides |
| Durable append log | Buffered file writes without fsync | `os.O_APPEND` + `os.write` + `os.fsync` per record | Verified cost 0.010 ms; durability is the requirement (CLOCK-06 foundation) |
| Clock/timing source | `time.time()`, tick loops | `time.monotonic_ns()` deltas | Anti-pattern 4; CLOCK-01 builds on this in Phase 3 |
| Typed move errors | String-matching ad hoc | `InvalidMoveError` / `IllegalMoveError` catch + console error taxonomy | Library already distinguishes syntax vs legality [VERIFIED: vendor/chess/__init__.py:160-170] |
| Line framing | Incremental str reads on text handles | `selectors` on raw fd + own buffer (mock_gui pattern) | Verified deadlock otherwise |

**Key insight:** the engine is a hostile peer — it exits on an illegal `position` (verified rc=1), its output floods, and UCI has no request ids. Every custom mechanism in this phase exists to survive that hostility: whitelist parsing, one-outstanding-go, ids, discard, journal. The *chess* itself, by contrast, is a solved problem — spend zero custom code there.

---

## Common Pitfalls

### Pitfall 1: The stale ponder `bestmove` (CF-7)
**What goes wrong:** after a ponder miss (`stop`), the engine still owes a bestmove **for the speculative position** (verified live). A naive handler plays it — a move for a board that does not exist.
**Why:** UCI has no request ids; the engine must answer every `go`, and `stop` inherits the outstanding search.
**How to avoid:** monotonic `search_id` per `go`; `discarding` flag set on miss; after `stop`, **consume the owed bestmove before the next `go`** (PROTOCOL §1.3); journal `STALE_BESTMOVE`; `test_ponder_discard.py` written before the handler, driven by `mock_engine --stale-bestmove` (which answers a later `go` with the previous position's move) plus a transport-level late-arrival injection.
**Warning signs:** any test where a bestmove arrives without a matching awaited go and the FSM advances anyway.

### Pitfall 2: `parse_uci` accepts `0000` and rejects uppercase
**What goes wrong:** PROTO-01 requires rejecting `0000` and tolerating case — but the library does the opposite on both (`0000` parses to a null move silently; `E2E4` raises).
**Why:** `parse_uci` implements full UCI incl. null moves; UCI squares are conventionally lowercase.
**How to avoid:** console normalization layer: strip/squeeze whitespace → lowercase → reject `0000` explicitly (TYPED_NULL) → then `parse_uci`; catch its two error classes for TYPED_MALFORMED vs TYPED_ILLEGAL. Log every rejected token (evidence requirement).
**Warning signs:** any test suite for PROTO-01 that does not include `'0000'`, `'E2E4'`, `'Nf3'`, `'O-O'`, `'e2-e4'`, `'e2e5'` — all six verified live.

### Pitfall 3: Engine exits on illegal `position` — the legality gate must run *before* every send
**What goes wrong:** `position startpos moves … <illegal>` → `info string CRITICAL ERROR: …` + exit(1) mid-game (verified).
**Why:** upstream treats an illegal move list as a fatal input error, not a recoverable one.
**How to avoid:** the *only* producer of `position … moves` lines is the validated replica's move list; the bestmove path validates against the replica before ANNOUNCE **and** before any subsequent `position` send (two independent checks — ARCHITECTURE §9.2(d)).
**Warning signs:** `CRITICAL ERROR` anywhere in a test transcript that did not inject it deliberately.

### Pitfall 4: TextIO buffering + select deadlock
**What goes wrong:** mixing buffered text pipes with `selectors` starves reads — data sits in the Python buffer while select times out on the fd.
**Why:** the buffer drains the pipe; select sees nothing.
**How to avoid:** `bufsize=0` binary pipes; `os.read` into an own buffer; split on `\n` (mock_gui pattern, comment verified in-repo).
**Warning signs:** intermittent 30 s timeouts under load in tests.

### Pitfall 5: PV leaking into ANNOUNCE
**What goes wrong:** the operator reads the deepening PV and announces it; `bestmove` later differs → wrong/illegal announced move (R10 exposure, PITFALLS D1).
**Why:** PV updates on screen continuously; `bestmove` arrives last.
**How to avoid:** ANNOUNCE is a separate field written **only** by the `bestmove` handler, empty until then, visually distinct; PV lives in its own scrolling area; success criterion 3 is exactly this.
**Warning signs:** any code path where an `info` line can write the ANNOUNCE buffer.

### Pitfall 6: `move_no`/`side` off-by-one in the log
**What goes wrong:** wrong move numbers or swapped colours fail `log_lint`'s alternation and monotonicity checks (§6.1).
**Why:** `fullmove_number` semantics (verified: still 1 after white's first move) and side = mover, not side-to-move-after.
**How to avoid:** capture both from the replica **before** the push; cross-check against the independent `mock_gui` formula in a test.
**Warning signs:** `side` column with two `w` in a row; `move_no` decreasing.

### Pitfall 7: `wall_ms < engine_ms` in the log
**What goes wrong:** log_lint fails (§6.1).
**Why:** measuring wall time from the wrong anchor (e.g. from `position` send instead of `go` send), or trusting engine `time` after a mock `--delay-ms`.
**How to avoid:** anchor `t0` at the `go` write, read at bestmove receipt; both keys always present (`engine_ms` 0 for book/opp/none, `wall_ms` always measured).
**Warning signs:** the mock_gui self-assert `wall_ms >= engine_ms` (tools/mock_gui.py:292-295) firing in CI.

### Pitfall 8: Engine floods and the UI freezes
**What goes wrong:** operator input dead while `info` streams (8-thread search produces far more than the 16 lines/1.5 s measured at 1 thread).
**Why:** single-threaded read-and-then-prompt design.
**How to avoid:** reader thread → unbounded queue; main loop polls queue + stdin via `select`; throttle PV redraws.
**Warning signs:** prompt latency proportional to engine nps.

### Pitfall 9: Option queue leaks into a live search
**What goes wrong:** `setoption` mid-search — deadlock risk while pondering (verified hazard, PITFALLS C2/D5); contract violation (PROTOCOL §1.4).
**How to avoid:** session queues option changes; transport flushes at `IDLE` only, after `isready`/`readyok`.
**Warning signs:** any `setoption` send reachable from a state other than `IDLE`.

### Pitfall 10: Tests too slow from engine spawns
**What goes wrong:** every unit test paying ~1.1 s engine startup makes the suite minutes long (Phase 1's 31 tests already take ~112 s).
**How to avoid:** mock-based tests by default; real-engine tests only in the 02-03 e2e (full game) and one smoke; batch assertions per engine process.

---

## Code Examples

### The frozen go line (builder + agreement test)

```python
# Source: docs/PROTOCOL.md §3.1 (frozen literal); mirrors tools/mock_gui.py:146-149
def go_line(w_ms: int, b_ms: int) -> str:
    assert w_ms >= 0 and b_ms >= 0
    return f"go wtime {int(w_ms)} btime {int(b_ms)} winc 10000 binc 10000"
# Test: assert go_line(798000, 851000) == "go wtime 798000 btime 851000 winc 10000 binc 10000"
# (PROTOCOL §3.4 worked example). Forbidden tokens (movetime/movestogo/depth/nodes/
# infinite/searchmoves) must appear NOWHERE in the console's send path — extend
# tools/tests/test_contract.py FORBIDDEN check to grep console/src (test_contract.py:42).
```

### Typed-reject parse layer (PROTO-01)

```python
# Verified behaviour: vendor/chess/__init__.py:160-170, :3243-3265 + live probes 2026-10-27
from chess import InvalidMoveError, IllegalMoveError  # both ValueError subclasses

class RejectKind(enum.Enum):
    MALFORMED = "malformed"   # syntax (incl. SAN-shaped: Nf3, e4, O-O — length gate)
    NULL = "null"             # '0000' — PROTO-01 rejects; engine terminal is '(none)'
    ILLEGAL = "illegal"       # legal syntax, illegal in position

def operator_move(board, raw: str) -> chess.Move:
    token = raw.strip().lower().replace(" ", "")
    if token == "0000":
        raise Reject(RejectKind.NULL, raw)
    try:
        return board.parse_uci(token)   # raises InvalidMoveError | IllegalMoveError
    except InvalidMoveError as e:
        raise Reject(RejectKind.MALFORMED, raw) from e
    except IllegalMoveError as e:
        raise Reject(RejectKind.ILLEGAL, raw) from e
    # caller: journal REJECT(token, kind); echo reason; prompt stays live; clock untouched
```

### Search-id discard handler (CF-7 — test first)

```python
# Source: .planning/research/ARCHITECTURE.md:665-686 (Pattern 2), PROTOCOL §7.3
def _on_bestmove(self, move_token: str, ponder_token: str | None) -> None:
    sid, self.outstanding = self.outstanding, None
    if sid is None or sid != self.search_id or self.discarding:
        self.discarding = False
        journal.append({"e": "STALE_BESTMOVE", "search_id": sid, "move": move_token})
        return                      # the discard point — no board change, no ANNOUNCE
    self.session.on_bestmove(move_token, ponder_token)   # validate vs replica → ANNOUNCE
```

### ANNOUNCE formatter (PROTO-04)

```python
# e2e4 → "E2-E4"; e7e8q → "E7-E8=Q"; e1g1 → "E1-G1". (none) never reaches here.
def announce_form(uci: str) -> str:
    frm, to = uci[0:2].upper(), uci[2:4].upper()
    promo = f"={uci[4].upper()}" if len(uci) == 5 else ""
    return f"{frm}-{to}{promo}"
```

### MoveLog line render (LOGBOOK §3.1 — verbatim key order)

```python
# Source: docs/LOGBOOK.md:50-58; keys also pinned by tools/tests/test_contract.py:41-42
def render(rec: dict) -> str:
    return ("src={src} move_no={move_no} side={side} uci={uci} depth={depth} "
            "nodes={nodes} score={score} score_white={score_white} "
            "engine_ms={engine_ms} wall_ms={wall_ms} pv={pv}").format(**rec)
    # pv LAST, unquoted. rec["pv"] is a space-joined UCI string (may be the single move).
```

### Journal append (verified cost)

```python
# 120 fsynced records measured at 1.3 ms total on this machine (2026-10-27)
def append(event: dict) -> None:
    event["t_mono_ms"] = time.monotonic_ns() // 1_000_000
    line = json.dumps(event, separators=(",", ":")) + "\n"
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
    os.write(fd, line.encode()); os.fsync(fd); os.close(fd)
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Console as `python-chess.engine` client | Hand-rolled transport with ids/discard (plan 02-01) | Locked in ROADMAP (2026-10-26) | Client remains available for tools; its seconds-float `time` and missing id semantics make it wrong for the game path [VERIFIED: live `play()` probe shows float seconds] |
| cutechess-style GUI harness | Purpose-built operator console | Project decision | GUIs are out of scope (R9: CLI sufficient) |
| Blocking readline console | Reader thread + queue + select loop | Established pattern (ARCHITECTURE anti-pattern 7) | Operator stays live during info floods |

**Deprecated/outdated for this phase:**
- `parse_san` on the operator path: exists and works, but PROTO-01 mandates typed rejection of SAN — keep it unreachable in Phase 2.
- `chess.engine`'s `time` (float seconds) for the log: wire is milliseconds (PROTOCOL §5.2) — parse raw `info` instead.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `PONDERING`/`DISCARDING` are unreachable in real Phase 2 games (`Ponder=false`); the discard path is exercised only via mock/injected events | State machine | Low — criterion 4 requires the test either way; if the team chooses to enable ponder in a Phase 2 integration game, only the e2e changes |
| A2 | Phase 2 sends placeholder-derived clock values in the go line (e.g. raw remaining minus a simple constant) and Phase 3 replaces them with the reserve-discounted belief | Architecture (clock boundary) | Low — go literal shape is frozen; only the integers vary |
| A3 | Header TB-inventory/book-hash fields may carry `none`/`0` in Phase 2, with real inventories landing in Phase 3 (CHECK-01) | MoveLog | Medium — if the panel-facing header must be final from Phase 2, 02-03 needs stub asset hashes; cheap to add |
| A4 | `score_white` for a bound-flagged score keeps the numeric negation and drops/keeps the flag per planner decision (recommendation: keep flag verbatim, negation applied to the number only) | MoveLog | Low — cosmetic for lint; graded field is `score` verbatim, which is unambiguous |

---

## Open Questions

1. **Where do per-move opponent-clock readings live in the *log*?** (PROTO-08 says "journal e log"; LOGBOOK §3.3 forbids inventing per-line keys, and the §4 `src=` set has no opp-clock variant.)
   - What we know: the journal can carry `OPP_CLOCK` records today; LOGBOOK §5.2's trailer carries final clocks only.
   - What's unclear: whether "log" in PROTO-08 means the Rule 9 file (needs a LOGBOOK §7.2 amendment) or the console's own audit record (journal suffices).
   - Recommendation: Phase 2 stores in the journal only; do **not** amend the frozen docs mid-phase; raise the LOGBOOK amendment (new dated revision) in Phase 3 together with LOG-05's header design, where export-log is built anyway.
2. **RESYNC representation in the log file** (PROTO-07: "anexado ao journal e ao log").
   - What we know: no `src=resync` exists in the frozen `src=` set; §3.1 says "one line per half-move".
   - Recommendation: journal-authoritative `RESYNC` record now; in the log file, emit a non-move event line with a reserved prefix (e.g. `# RESYNC …`) that `log_lint` skips; keep `src=` lines strictly per-half-move. Same amendment question as #1 — bundle them.
3. **Bare-integer `t 442` interpretation** (PROTO-08 "formatos alternativos").
   - What we know: FEATURES TS-12 lists `7.42`/`442` as tolerated; `442` could be seconds (7:22) or `M:SS` (4:42) — genuinely ambiguous.
   - Recommendation: accept `M:SS`, `H:MM:SS`, `M.SS`; for bare digits echo the parsed interpretation prominently and journal both raw token and parsed ms; never guess silently. Final tolerance matrix is a Phase 3 CLOCK-02 concern.
4. **Does the 02-03 full game need a real opponent engine instance or a scripted move feeder?**
   - What we know: criterion 5 says "full game against stock Stockfish"; the console's opp input is keyboard-driven.
   - Recommendation: e2e test drives the console's stdin with the opponent's moves taken from a second `src/stockfish` instance (or a fixed legal line), capping length by playing a known short decisive line; terminal `src=none` row needs a scripted mate/stalemate position. Planner picks per test-budget taste; both are offline.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| python3 | everything | ✓ | 3.14.7 | — |
| `vendor/chess` | board/legality | ✓ | 1.11.2 (import verified) | — |
| `./src/stockfish` | real-engine tests + full game | ✓ | SF19, sha256 527fa7ac… | `tools/mock_engine.py` for all unit tests |
| `tools/mock_engine.py` | fault injection | ✓ | Phase 1 (11 flags verified) | — |
| stdlib `selectors/threading/queue/unittest/readline` | transport, tests, prompt | ✓ | 3.14 | — |
| pip / pytest | — | ✗ (by design) | — | stdlib unittest (Phase 1 decision) |
| network | nothing | must stay off in games | — | research-time net use is fine |

**Missing dependencies with no fallback:** none.
**Missing dependencies with fallback:** pip/pytest → unittest (already the project standard).

---

## Security Domain

`security_enforcement: true`, `security_asvs_level: 1` [VERIFIED: .planning/config.json:49-50]. Phase 2 is a local, offline, single-user CLI — most ASVS categories do not apply; the ones that do are input handling, output handling, and file integrity.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | no users/remote surface |
| V3 Session Management | no | single local process |
| V4 Access Control | no | operator is the local user |
| V5 Input Validation | **yes** | the typed-reject layer IS the control: whitelist UCI grammar, whitelist engine line types, bounded token lengths, no eval/exec on any input |
| V6 Cryptography | no | sha256 for integrity only (hashlib) |
| V7 Errors & Logging | **yes** | typed errors to the operator; full raw evidence (rejected tokens) to the journal; no secrets in logs |
| V8 Data Protection | **yes (light)** | append-only log; fsync; never rewrite delivered artefacts |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Engine output interpreted as commands (a hostile/corrupt engine line driving console state) | Tampering | whitelist parser: only §5.1 tokens + `bestmove` + `option` + `id` + `uciok`/`readyok` reach the FSM; everything else → tolerated garbage (PROTOCOL §9.3, tested via `--garbage`) |
| Malformed operator input smuggling (e.g. pasted multi-line, control chars) | Tampering | read one line, strip, length-bound, strict grammar; paste-tolerance = collapse whitespace, never multi-line execution |
| Log tampering after the fact | Repudiation | append-only + fsync + trailer sha256 (Phase 3 adds delivery ritual); journal is the audit twin |
| Engine DoS (hang, flood, crash) | DoS | per-read timeouts now; full watchdog in Phase 3 (CLOCK-04/05); reader thread isolates flood from UI |
| Subprocess shell injection | Tampering/Elevation | `Popen(argv_list)` — never `shell=True` (mock_gui pattern verified) |
| Path traversal via `--log-dir` style args | Tampering | `Path(...).resolve()`, refuse non-writable targets at GAME_START (full asset-path doctoring is Phase 3 CHECK-01) |

---

## Sources

### Primary (HIGH confidence — all verified this session)

- `docs/PROTOCOL.md` — read in full; §3.1 literal, §5 token set, §7 bestmove/stale, §8 ponder, §9 errors, §10 timing [VERIFIED: docs/PROTOCOL.md:54-192]
- `docs/LOGBOOK.md` — read in full; §2 field table, §3 line format, §4 src set, §5 header/trailer, §6 log_lint [VERIFIED: docs/LOGBOOK.md:27-108]
- `tools/mock_engine.py` — read in full; GO_LITERAL, 11 scenario flags, TM trace shape, recorder [VERIFIED: tools/mock_engine.py:38, :218-234]
- `tools/mock_gui.py` — read in full; CSV_COLUMNS, bufsize=0 selector readline, bestmove_of, go_line, wall≥engine assert, pending_bestmove [VERIFIED: tools/mock_gui.py:43-44, :53-103, :128-131, :146-149, :292-295]
- `vendor/chess/__init__.py` — error classes (:160-170), `parse_uci`/`push_uci` docs+code (:3243-3290) [VERIFIED this session]
- `./src/stockfish` live probes — bestmove shape, `(none)`, CRITICAL ERROR rc=1, stop semantics, ponder/stop → speculative bestmove, ponderhit, TB attestation, stderr silence, handshake timing [VERIFIED: 2026-10-27 probes listed in §Verified Wire Facts]
- `tools/tests/test_contract.py` — LOG_KEYS, FORBIDDEN tokens, agreement tests [VERIFIED: tools/tests/test_contract.py:41-46]; suite green (31 tests)
- `.planning/ROADMAP.md` — Phase 2 section, plan split, Gate 1 condition, CF-7, three easy-to-miss findings [VERIFIED: .planning/ROADMAP.md:55-75, :202, :318-324]
- `.planning/research/ARCHITECTURE.md` — FSM table, search-id pattern, journal pattern, anti-patterns, failure modes [VERIFIED: sections §5.2, §7, §8, §9]
- `.planning/research/PITFALLS.md` — D1 (PV/announce), D4 (resync), D5 (UCI races/`(none)`/stderr), C2 (ponder side effects) [VERIFIED: group D sections]
- `evidence/01-binary.sha256` — engine identity [VERIFIED: file read; live sha256sum matches]
- `.planning/config.json` — nyquist_validation=false, security L1 on [VERIFIED: .planning/config.json:25, :49-50]

### Secondary (MEDIUM confidence)

- `.planning/research/FEATURES.md` — TS-10/11/12/14/15/17 operator-UX and journal detail (design guidance, not contract)
- Phase 1 `01-PATTERNS.md` — unittest decision, GPL header convention, checker shapes

### Tertiary (LOW confidence)

- None — no web sources used; all claims are in-repo or live-probed.

---

## Metadata

**Confidence breakdown:**
- Wire/engine behaviour: HIGH — every row probed live against the competition binary this session
- Library behaviour (python-chess): HIGH — probed live on the vendored 1.11.2 tree, error classes read from source
- Architecture/patterns: HIGH — locked by ROADMAP plan split + frozen docs; ARCHITECTURE.md patterns transcribed, not invented
- Pitfalls: HIGH for the ten listed (all trace to verified probes, frozen docs, or in-repo verified comments); MEDIUM for UI ergonomics details (drill territory)
- Open questions (4): explicit, with recommendations; none block planning

**Research date:** 2026-10-27
**Valid until:** 2026-11-03 (engine binary and vendored library are pinned; nothing here rots faster than the event itself)
