# Phase 2: Console Protocol Spine - Pattern Map

**Mapped:** 2026-10-27
**Files analyzed:** 18 (17 new + 1 modified)
**Analogs found:** 17 / 18 (all files have at least a role-match analog; `console/src/console/ui/loop.py` is the weakest — no select-on-stdin + queue precedent exists, use RESEARCH.md Pattern 1 + ARCHITECTURE.md anti-pattern 7)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `console/src/console/__init__.py` (and per-subpackage) | package marker | — | `tools/tests/__init__.py` | exact (trivial) |
| `console/src/console/main.py` | entrypoint / wiring | request-response | `tools/mock_gui.py` `main()` | role-match |
| `console/src/console/transport/uci.py` | service (subprocess owner) | streaming | `tools/mock_gui.py` `EngineProc` | exact |
| `console/src/console/transport/parser.py` | utility (line → event) | streaming | `tools/mock_gui.py` `search()` info walk | exact |
| `console/src/console/engine/session.py` | state machine | event-driven | `tools/mock_engine.py` `MockEngine.run()` dispatch | role-match |
| `console/src/console/game/board.py` | model | CRUD | `vendor/chess/__init__.py` `Board` API (external lib — no in-repo analog) | partial |
| `console/src/console/game/moves.py` | utility (typed-reject gate) | request-response | `vendor/chess/__init__.py:160-170` error classes + `tools/mock_gui.py:128-131` `bestmove_of` | role-match |
| `console/src/console/game/journal.py` | service (append-only log) | file-I/O | `tools/mock_engine.py` `Recorder` | role-match |
| `console/src/console/log/movelog.py` | model / projection | transform | `tools/mock_gui.py` `CSV_COLUMNS` + row dicts | role-match |
| `console/src/console/log/lint.py` | validator | batch | `tools/tests/test_contract.py` assertions + `tools/doctor.py` `record()` | role-match |
| `console/src/console/ui/loop.py` | controller (operator loop) | event-driven | **none** — RESEARCH.md §Operator loop / ARCHITECTURE anti-pattern 7 | no analog |
| `console/tests/test_ponder_discard.py` | test (CF-7, written first) | event-driven | `tools/tests/test_doctor.py` + `tools/mock_engine.py --stale-bestmove` | role-match |
| `console/tests/test_transport.py` | test | streaming | `tools/tests/test_contract.py` `RuntimeEndToEndTests` | exact |
| `console/tests/test_moves.py` | test (reject matrix) | request-response | `tools/tests/test_tb_ceiling.py` (`subTest` matrix style) | exact |
| `console/tests/test_board.py` | test | CRUD | `tools/tests/test_doctor.py` class-per-behaviour | role-match |
| `console/tests/test_journal.py` | test | file-I/O | `tools/tests/test_contract.py` tmp-file + `addCleanup` pattern | role-match |
| `console/tests/test_movelog.py` | test | transform | `tools/tests/test_contract.py` `LogbookCsvTests` | exact |
| `tools/tests/test_contract.py` (**MODIFIED** — extend FORBIDDEN grep to `console/src`) | test | batch | itself | exact |

All analogs verified git-tracked: `git ls-files` returns `tools/doctor.py`, `tools/mock_engine.py`, `tools/mock_gui.py`, `tools/tests/{__init__,test_contract,test_doctor,test_tb_ceiling}.py`, `vendor/chess/__init__.py`. No mirror paths.

---

## Pattern Assignments

### `console/src/console/transport/uci.py` (service, streaming)

**Analog:** `tools/mock_gui.py` `EngineProc` — copy this pipe discipline verbatim; do not reinvent.

**Imports pattern** (`tools/mock_gui.py:25-33`):
```python
import argparse
import csv
import json
import os
import random
import selectors
import subprocess
import sys
import time
```

**Subprocess spawn — binary, unbuffered, the load-bearing buffering comment** (`tools/mock_gui.py:54-63`):
```python
# Binary, unbuffered pipes: select() must see every byte the child
# writes. TextIO buffering here deadlocks (buffer drains the fd,
# select then times out on data we already own — verifier G1).
self.popen = subprocess.Popen(
    argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT, bufsize=0,
)
self.rec = open(record, "a", encoding="utf-8") if record else None
self.pending_bestmove = None  # a bestmove nobody consumed yet (stale)
self._buf = b""
```
Console delta: use `stderr=subprocess.PIPE` + a drain daemon thread (or `DEVNULL`), **never** `STDOUT` — mock_gui merges because it is a dev driver; the console must keep stderr out of the UCI stream (RESEARCH.md anti-pattern "Merging stderr into the UCI stream").

**Selector readline on the raw fd** (`tools/mock_gui.py:78-103`):
```python
def readline(self, timeout=30.0):
    """One line with a REAL timeout, on raw fd + own buffer.

    TextIO buffering cannot be combined with select(): the buffer drains
    the pipe and select() starves on bytes we already hold. So: select()
    on the raw fd, os.read into our own buffer, split on newlines.
    EOF (engine died) → RuntimeError (PROTOCOL §9.2 territory)."""
    while b"\n" not in self._buf:
        sel = selectors.DefaultSelector()
        sel.register(self.popen.stdout, selectors.EVENT_READ)
        try:
            if not sel.select(timeout):
                raise TimeoutError(
                    f"engine silent for {timeout}s (hung or dead)")
            chunk = os.read(self.popen.stdout.fileno(), 65536)
        finally:
            sel.close()
        if not chunk:
            raise RuntimeError("engine EOF (crashed or quit mid-exchange)")
        self._buf += chunk
    raw, self._buf = self._buf.split(b"\n", 1)
    line = raw.decode(errors="replace").rstrip("\r")
    if not line.strip():
        return self.readline(timeout)  # skip blank, budget resets
    self._record("out", line)
    return line
```
Console delta: run this loop in a **reader thread** pushing parsed lines into a `queue.Queue`; the operator loop polls queue + stdin (Pitfall 8). Keep the blank-line skip and `rstrip("\r")`.

**Send + liveness check** (`tools/mock_gui.py:71-76`):
```python
def send(self, line):
    if self.popen.poll() is not None:
        raise RuntimeError(f"engine exited rc={self.popen.returncode}")
    self._record("in", line)
    self.popen.stdin.write((line + "\n").encode())
    self.popen.stdin.flush()
```

**Reap on every path** (`tools/mock_gui.py:112-125`):
```python
def close(self):
    """Reap the engine on every path — quit first, then kill + wait, so
    no hung mock (e.g. --silent-hang) survives the driver."""
    try:
        self.send("quit")
    except (BrokenPipeError, RuntimeError, OSError):
        pass
    try:
        self.popen.wait(timeout=5)
    except subprocess.TimeoutExpired:
        self.popen.kill()
        self.popen.wait()
    if self.rec:
        self.rec.close()
```

**Handshake + option sends** (`tools/mock_gui.py:267-275`) — console queues options and flushes only at `IDLE`:
```python
# Handshake (PROTOCOL §2)
proc.send("uci")
proc.expect("uciok")
for opt in args.option:
    if "=" in opt:
        k, v = opt.split("=", 1)
        proc.send(f"setoption name {k} value {v}")
proc.send("isready")
proc.expect("readyok")
```

**`pending_bestmove` discipline — the seed of `search_id`/`discarding`** (`tools/mock_gui.py:153-155`):
```python
if self.proc.pending_bestmove is not None:
    # PROTOCOL §7.3: a bestmove with no matching go is stale; discard.
    self.proc.pending_bestmove = None
```
Console upgrades this to the monotonic `search_id` + `discarding` handler from RESEARCH.md §Search-id discard handler (CF-7) — same idea, id-tagged.

**Frozen go literal as module data** (`tools/mock_gui.py:35-37`):
```python
# PROTOCOL §3.1 — the frozen literal. Tests assert document ↔ driver agreement;
# keep in sync with docs/PROTOCOL.md.
GO_LITERAL = "go wtime <int_ms> btime <int_ms> winc 10000 binc 10000"
```
Console exposes its instantiated builder the same way (`tools/mock_gui.py:145-149`):
```python
@staticmethod
def go_line(w_ms, b_ms, ponder=False):
    if ponder:
        return f"go ponder wtime {w_ms} btime {b_ms} winc 10000 binc 10000"
    return f"go wtime {w_ms} btime {b_ms} winc 10000 binc 10000"
```

---

### `console/src/console/transport/parser.py` (utility, streaming)

**Analog:** `tools/mock_gui.py` `search()` — token-walk over whitelisted keys, never whole-line regex.

**Core info-line walk** (`tools/mock_gui.py:164-192`):
```python
depth, nodes, score, time_ms, pv, tm = 0, 0, "-", 0, "", ""
t0 = time.monotonic_ns()
while True:
    line = self.proc.readline(timeout=60.0)
    if line.startswith("info depth"):
        toks = line.split()
        for i, tok in enumerate(toks):
            if tok == "depth" and i + 1 < len(toks):
                depth = int(toks[i + 1])
            elif tok == "nodes" and i + 1 < len(toks):
                nodes = int(toks[i + 1])
            elif tok == "time" and i + 1 < len(toks):
                time_ms = int(toks[i + 1])
        if " score " in line:
            toks = line.split()
            i = toks.index("score")
            score = toks[i + 1]
            if i + 2 < len(toks) and toks[i + 2] not in ("nodes", "nps", "lowerbound", "upperbound"):
                score = f"{score} {toks[i + 2]}"
            if " lowerbound" in line:
                score += " lowerbound"
            elif " upperbound" in line:
                score += " upperbound"
        if " pv " in line:
            pv = line.split(" pv ", 1)[1]
    elif line.startswith("info string tm="):
        tm = line[len("info string "):]
    elif line.startswith("bestmove"):
        wall_ms = (time.monotonic_ns() - t0) // 1_000_000
```
This is the verified two-token `score` shape + bound-flag capture; `time` stays wire **milliseconds**. Console wraps this in a whitelist parser (only `info`, `info string`, `bestmove`, `id`, `option`, `uciok`, `readyok` reach the FSM; all else tolerated garbage per PROTOCOL §9.3).

**bestmove token extraction** (`tools/mock_gui.py:128-131`):
```python
def bestmove_of(line):
    # "bestmove e2e4 ponder c7c5" — the move token is the FIRST word after
    # bestmove; a ponder suffix belongs to the engine, not the move list.
    return line[len("bestmove "):].split()[0]
```

**Contractual anchor discipline** (`tools/mock_gui.py:288-295`):
```python
# Driver invariants (self-asserting contract checks)
if args.require_tm:
    for r in all_rows:
        assert r["tm_trace"], f"missing tm= trace on move {r['move_no']}: {r}"
for r in all_rows:
    assert int(r["depth"]) >= 0 and int(r["nodes"]) >= 0
    assert int(r["wall_ms"]) >= int(r["engine_ms"]), \
        f"wall_ms >= engine_ms violated: {r}"
```
`t0` anchored at the `go` write (line 165), read at bestmove receipt (line 192) — this is `wall_ms ≥ engine_ms`'s correct anchor; log_lint re-checks it.

---

### `console/src/console/engine/session.py` (state machine, event-driven)

**Analog:** `tools/mock_engine.py` `MockEngine.run()` — the token-dispatch shape; the FSM table itself is new (RESEARCH.md Pattern 2 is the spec).

**Dispatch-loop shape** (`tools/mock_engine.py:177-215`):
```python
# --- main loop (imitates src/uci.cpp read-loop: EOF == quit) --------
def run(self):
    self.searching = False
    if self.args.slow_ready:
        self.ready_delay = 1.5
    for raw in sys.stdin:
        line = raw.rstrip("\n")
        if not line.strip():
            continue
        self.rec.log("in", line)
        token = line.split()[0]
        if token == "quit" or token == "stop":
            ...
        elif token == "uci":
            self.handle_uci()
        elif token == "isready":
            ...
        elif token == "setoption":
            self.handle_setoption(line)
        elif token == "position":
            self.handle_position(line)
        elif token == "go":
            ...
        elif token == "ponderhit":
            pass
        elif token == "ucinewgame":
            self.moves = []
        else:
            self.send(f"info string unknown command: {token}")
    return 0  # stdin EOF behaves like quit (PROTOCOL §1; uci.cpp:104-107)
```
Console mirrors this as `(state, event) → (next_state, action)` table methods (`on_info`, `on_bestmove`, `on_operator_move`, `on_opp_clock`…). Per RESEARCH.md Pattern 2: states `IDLE`, `OUR_SEARCH`, `ANNOUNCE_PENDING`, `AWAIT_OPP_CONFIRM`, `OPP_TURN`, `PONDERING` (+ internal `DISCARDING`); side-to-move guard reads `board.turn` before accepting any operator move; `setoption` flush reachable **only** from `IDLE`.

**Option state as a plain dict** (`tools/mock_engine.py:62-65`) — console queues intended changes instead of applying immediately:
```python
self.options = {
    "Threads": 1, "Hash": 16, "SyzygyPath": "<empty>",
    "SyzygyProbeLimit": 5, "Move Overhead": 100, "Ponder": False,
}
```

**Crash-on-mid-search-option contract** (`tools/mock_engine.py:88-91`) — the deadlock hazard the queue exists to avoid:
```python
def handle_setoption(self, line):
    if self.searching and self.args.crash_on_option:
        sys.exit(1)
```

---

### `console/src/console/game/moves.py` (utility, request-response)

**Analog:** RESEARCH.md §Typed-reject parse layer (the spec, verified against live probes) + `vendor/chess/__init__.py:160-170` (the typed-error vocabulary, git-tracked):
```python
class InvalidMoveError(ValueError):
    """Raised when move notation is not syntactically valid"""


class IllegalMoveError(ValueError):
    """Raised when the attempted move is illegal in the current position"""
```

**The layer to implement (RESEARCH.md Code Examples — copy with test matrix):**
```python
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
```
Order matters (Pitfall 2): strip → lowercase → `0000` check **before** `parse_uci` (the library accepts `0000` and rejects `E2E4`). Caller journals `REJECT(token, kind)`, echoes reason, prompt stays live, clock untouched. Never route through `parse_san` (SAN rejection is a requirement).

**ANNOUNCE formatter (RESEARCH.md Code Examples — `console/src/console/ui/loop.py` concern):**
```python
# e2e4 → "E2-E4"; e7e8q → "E7-E8=Q"; e1g1 → "E1-G1". (none) never reaches here.
def announce_form(uci: str) -> str:
    frm, to = uci[0:2].upper(), uci[2:4].upper()
    promo = f"={uci[4].upper()}" if len(uci) == 5 else ""
    return f"{frm}-{to}{promo}"
```

---

### `console/src/console/game/board.py` (model, CRUD)

**Analog:** none in-repo — `vendor/chess` `Board` is the sanctioned substrate (R14). Verified API facts to build on (RESEARCH.md §Parsing, live-probed 2026-10-27):

- `board.parse_uci(token)` raises `InvalidMoveError` / `IllegalMoveError`; accepts `0000` (guard upstream) and Chess960 `e1h1` (harmless, never advertise).
- `board.fullmove_number` = move **in progress**; `side` = `"w" if board.turn == chess.WHITE else "b"` **before** the push; `board.ply()` for book-cap/replay bookkeeping.
- `board.outcome(claim_draw=False)` → `Outcome(termination=…, winner=…)`; Phase 2 detects and displays terminal state, never self-adjudicates.

**Independent cross-check formula for tests** (`tools/mock_gui.py:194-202`):
```python
self.rows.append({
    "move_no": (len(moves) + 2) // 2,
    "side": "w" if len(moves) % 2 == 0 else "b",
    "uci": mv,
    ...
```
`test_board.py` asserts the replica's `fullmove_number`/`turn` capture agrees with this formula.

**Board authority rule (Pitfall 3):** the *only* producer of `position … moves` lines is the validated replica's move list — `tools/mock_gui.py:157-158` shows the send shape:
```python
self.proc.send("position startpos moves " + " ".join(moves)
               if moves else "position startpos")
```

---

### `console/src/console/game/journal.py` (service, file-I/O)

**Analog:** `tools/mock_engine.py` `Recorder` (JSONL append + flush shape) and `tools/mock_gui.py` `_record` — then upgrade to `os.fsync` per record.

**JSONL append shape** (`tools/mock_engine.py:44-55`):
```python
class Recorder:
    def __init__(self, path):
        self.fh = open(path, "a", encoding="utf-8") if path else None

    def log(self, direction, line):
        if self.fh:
            self.fh.write(json.dumps({
                "t": time.monotonic_ns(),
                "dir": direction,
                "line": line,
            }) + "\n")
            self.fh.flush()
```

**Durability upgrade — the full mechanism (RESEARCH.md Code Examples, measured 0.010 ms/record):**
```python
def append(event: dict) -> None:
    event["t_mono_ms"] = time.monotonic_ns() // 1_000_000
    line = json.dumps(event, separators=(",", ":")) + "\n"
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
    os.write(fd, line.encode())
    os.fsync(fd)
    os.close(fd)
```
Phase 2 event vocabulary (Phase 3 extends, never rewrites): `GAME_START`, `MOVE_LOGGED`, `REJECT`, `STALE_BESTMOVE`, `OPP_CLOCK`, `RESYNC`, `ENGINE_FAULT`, `GAME_END`. Append-only; replay must reproduce board + log; kill -9 tolerance is a `test_journal.py` case.

---

### `console/src/console/log/movelog.py` (model, transform)

**Analog:** `tools/mock_gui.py` — per-move record as a dict with the exact key set, exposed as module data for tests.

**Keys-as-data pattern** (`tools/mock_gui.py:41-44`):
```python
# The per-move CSV header, exposed as data: tests assert it carries every
# LOGBOOK §2 key. Order: identity, search fields, wall/engine time, PV, TM.
CSV_COLUMNS = ["move_no", "side", "uci", "depth", "nodes", "score",
               "engine_ms", "wall_ms", "pv", "tm_trace"]
```

**Frozen line format — transcribe, do not paraphrase (RESEARCH.md Pattern 4, source docs/LOGBOOK.md:50-58):**
```python
def render(rec: dict) -> str:
    return ("src={src} move_no={move_no} side={side} uci={uci} depth={depth} "
            "nodes={nodes} score={score} score_white={score_white} "
            "engine_ms={engine_ms} wall_ms={wall_ms} pv={pv}").format(**rec)
    # pv LAST, unquoted. rec["pv"] is a space-joined UCI string (may be the single move).
```
Per-variant fills (RESEARCH.md Pattern 4): `opp` → `depth=0 nodes=0 score=- engine_ms=0`, wall measured; `book` → `d=0 n=0 score=book pv=<move> engine_ms=0`; `none` → `uci=(none) depth=0 nodes=0` non-empty score (`mate 0` verified live). `score` verbatim incl. `lowerbound`/`upperbound`; `score_white` White-POV, `-` when absent. Header: game id, date, colour, TC, engine sha256 (recompute at start), net sha256, exact `setoption` set, `SyzygyProbeLimit` (assert 5), `network=off`; TB/book hashes placeholder `none`/`0` in Phase 2 (RESEARCH A3). Trailer: result, reason, final clocks, log sha256.

**`MoveLog` is a pure projection of the journal** — it never writes a parallel history (RESEARCH.md Pattern 3).

---

### `console/src/console/log/lint.py` (validator, batch)

**Analog:** `tools/doctor.py` fail-closed check/record shape + `tools/tests/test_contract.py` assertion discipline.

**Fail-closed check recording** (`tools/doctor.py:40-44`):
```python
checks: list[dict] = []


def record(status: str, reason: str) -> None:
    checks.append({"status": status, "reason": reason})
```
Doctor's contract discipline (`tools/doctor.py:10-15` docstring) is the model — "Exit 1 iff any FAIL. WARN never masks a rule violation". `log_lint` has no WARN at all: every check fails closed (LOGBOOK §6):
- all ten keys (`src`, eight fields, `score_white`) present per move line;
- `move_no` monotonic non-decreasing; `side` alternates `w`,`b`;
- `uci` legal in the replayed position (or `(none)` for `src=none`);
- `pv` non-empty; `wall_ms ≥ engine_ms`;
- no `src=` outside `{search, book, tb, ponder, opp, none}`;
- header and trailer present and complete.

Implementation: replay the log's `uci` sequence through a fresh `chess.Board` from startpos — same replay the engine gets.

---

### `console/src/console/ui/loop.py` (controller, event-driven)

**Analog:** none — no select-on-stdin + queue-poll precedent exists in-repo. Use RESEARCH.md Architecture Patterns (system diagram, lines 217-244) + anti-pattern list as the spec:

- Main loop **polls** the engine event queue **and** fd 0 via `select()`; never a blocking `input()` that hides ANNOUNCE updates (ARCHITECTURE anti-pattern 7).
- ANNOUNCE is a separate field written **only** by the `bestmove` handler, empty until then, visually distinct from PV (Pitfall 5; success criterion 3).
- Reject path: typed error echo, prompt stays live, clock untouched (no sleep/block on reject — anti-pattern 8).
- Commands: `t <time>` (PROTO-08, accept `M:SS`/`H:MM:SS`/`M.SS`; bare digits echo interpretation, journal raw+parsed, never guess silently — Open Question 3), resync-by-replaying-last-N with confirmation (PROTO-07), `u`-style undo if the planner wants it.
- Paste tolerance: one line per read, strip, collapse internal whitespace, length-bound, never multi-line execution (RESEARCH.md Security Domain V5).
- Optional stdlib `readline` import for prompt editing (verified available; RESEARCH.md Supporting stack).

---

### `console/src/console/main.py` (entrypoint, wiring)

**Analog:** `tools/mock_gui.py` `main()` — config → subprocess → session → loop wiring with `try/finally: proc.close()`.

**Structure** (`tools/mock_gui.py:252-286`):
```python
def main() -> int:
    args = parse_args()
    ...
    proc = EngineProc(engine_argv, args.require_tm, args.record)

    try:
        # Handshake (PROTOCOL §2)
        proc.send("uci")
        proc.expect("uciok")
        ...
    finally:
        proc.close()
```
Plus `parse_args()` in the `tools/mock_gui.py:233-249` style (argparse, every flag documented in `help=`). Console wires: config (engine path, log dir via `Path(...).resolve()`, our colour) → `Transport` → `Session` → `OperatorLoop`; GAME_START asserts `SyzygyProbeLimit=5` (startup check; engine attests `info string TB ceiling OK`).

---

### Package `__init__.py` files

**Analog:** `tools/tests/__init__.py` (empty package marker). `console/src/console/...` subpackages each get a minimal `__init__.py`. Import path: tests run with `PYTHONPATH=vendor:console/src` (vendored `chess` import — RESEARCH.md Environment: `PYTHONPATH=vendor python3 -c "import chess"` → 1.11.2).

---

## Test Pattern Assignments

### `console/tests/test_ponder_discard.py` (written BEFORE the handler — CF-7)

**Analog:** `tools/tests/test_doctor.py` — subprocess-driven behaviour test class; scenario injection via `tools/mock_engine.py --stale-bestmove` flag (`tools/mock_engine.py:223`):
```python
p.add_argument("--stale-bestmove", action="store_true")
```
whose behaviour is exactly the hazard (`tools/mock_engine.py:156-159`):
```python
if self.args.stale_bestmove and self.search_count > 1:
    # Answer the CURRENT go with the PREVIOUS position's move.
    self.send(f"bestmove {self.stale_move()}")
    return
```

**Subprocess-runner helper pattern** (`tools/tests/test_doctor.py:32-36`):
```python
def run_doctor(*args: str, cwd: pathlib.Path = REPO) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(DOCTOR), *args], cwd=cwd,
        capture_output=True, text=True, timeout=300,
    )
```
Console variant drives `tools/mock_engine.py` through the console's transport (in-process, not subprocess) and asserts: late bestmove with no outstanding `go` → `STALE_BESTMOVE` journaled, FSM unchanged, no ANNOUNCE; post-`stop` owed bestmove consumed before next `go`; unconsumed bestmove at send time discarded. Cover all three orderings from RESEARCH.md Pattern 1.

### `console/tests/test_transport.py`

**Analog:** `tools/tests/test_contract.py` `RuntimeEndToEndTests` — spawn real processes, assert on artefacts, cleanup, generous timeout, vendored `PYTHONPATH` (`tools/tests/test_contract.py:125-140`):
```python
def test_gui_drives_mock_engine_end_to_end(self):
    csv_path = tempfile.mktemp(prefix="gui-e2e-", suffix=".csv")
    self.addCleanup(lambda: os.path.exists(csv_path) and os.unlink(csv_path))
    p = subprocess.run(
        [sys.executable, "tools/mock_gui.py",
         "--engine", "tools/mock_engine.py",
         "--games", "1", "--max-plies", "4", "--tc", "15:10",
         "--csv", csv_path],
        cwd=REPO, capture_output=True, text=True, timeout=180,
        env={**os.environ, "PYTHONPATH": str(REPO / "vendor")},
    )
    self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
```
Repo-root resolution idiom (`tools/tests/test_contract.py:30-37`):
```python
REPO = pathlib.Path(__file__).parent.resolve().parent.parent
TOOLS = REPO / "tools"
...
sys.path.insert(0, str(TOOLS))
import mock_engine  # noqa: E402
```

### `console/tests/test_moves.py`

**Analog:** `tools/tests/test_tb_ceiling.py` — `subTest` matrix style (`tools/tests/test_tb_ceiling.py:59-70`):
```python
def test_04_six_piece_directory_is_fatal(self):
    for name in ("KQRRBvK.rtbw", "KQRRBvK.rtbz"):  # WDL and DTZ-only
        with self.subTest(file=name):
```
Matrix must include all six verified live rejects: `'0000'` (TYPED_NULL), `'E2E4'` (normalize→accept), `'Nf3'`, `'O-O'` (TYPED_SAN→MALFORMED), `'e2-e4'` (reject), `'e2e5'` (TYPED_ILLEGAL) — plus `' e2 e4 '` spaces and promotion-ambiguity re-prompt (`e7e8` with four suffixes `a7a8q/r/b/n` legal).

### `console/tests/test_board.py`, `test_journal.py`, `test_movelog.py`

**Analog:** `tools/tests/test_doctor.py` class-per-behaviour grouping; `tools/tests/test_contract.py` tmp-dir + `addCleanup` idiom; `LogbookCsvTests` key-iteration style (`tools/tests/test_contract.py:109-117`):
```python
class LogbookCsvTests(unittest.TestCase):
    def test_all_logbook_keys_present_in_csv_header(self):
        from mock_gui import CSV_COLUMNS
        for key in LOG_KEYS:
            self.assertIn(key, CSV_COLUMNS, f"LOGBOOK §2 key {key} missing from CSV")
```
- `test_board.py`: replay (`position startpos moves …`), side-to-move guard both directions, terminal detection vs `mock_gui`'s independent `move_no`/`side` formula.
- `test_journal.py`: replay == live state; append-only (no rewrite); kill -9 tolerance; every event type round-trips.
- `test_movelog.py`: rendered line vs LOGBOOK §3.1 key order (assert against `LOG_KEYS` + `score_white` + `src`); `log_lint` cases (alternation break, `wall_ms < engine_ms`, bad `src=`, missing header → lint fails closed).

### `console/tests/test_e2e_fullgame.py`

**Analog:** `tools/tests/test_contract.py` `RuntimeEndToEndTests` (subprocess, `PYTHONPATH=vendor`, `cwd=REPO`, `timeout=180+`, `addCleanup`). Real engine (`./src/stockfish`) + opponent moves fed to console stdin (second stockfish instance or fixed legal line — planner's call, Open Question 4); must include book/opp/terminal rows and one full `log_lint` pass on the produced log.

**Keep tests fast (Pitfall 10):** mock-based by default; real-engine spawns only here and one smoke. `mock_engine --slow-ready` / `--delay-ms` / `--silent-hang` / `--crash-after` / `--garbage` are the fault injectors (`tools/mock_engine.py:218-234`).

---

### `tools/tests/test_contract.py` (MODIFIED)

**Analog:** itself. Extend the FORBIDDEN check to grep `console/src` — the frozen literal must be the only go grammar in the console send path (RESEARCH.md Code Examples, line 503):
```python
FORBIDDEN = ("movetime", "movestogo", "depth", "nodes", "infinite", "searchmoves")
LOG_KEYS = ("move_no", "side", "uci", "depth", "nodes", "score", "pv",
            "engine_ms", "wall_ms")
```
Add a test asserting console's `go_line(w, b) == "go wtime {w} btime {b} winc 10000 binc 10000"` and that `tools/mock_gui.py:84-90`'s FORBIDDEN tokens appear nowhere in `console/src`. Console exposes its builder + key constants as importable module data (mock_gui `CSV_COLUMNS` pattern) so this test can import them.

---

## Shared Patterns

### GPLv3 header — every new Python file
**Source:** `tools/mock_gui.py:1-8` (all Phase 1 Python files carry it)
```python
#!/usr/bin/env python3
# ChessChallendIII — mock GUI/driver speaking docs/PROTOCOL.md (plan 01-02)
# Copyright (C) 2026 ChessChallendIII
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.  See Copying.txt for the full text.
```
Header line 2 carries the file's purpose + plan id (e.g. "— console UCI transport (plan 02-01)"). Applies to all 17 new files.

### Frozen literals as importable module data
**Source:** `tools/mock_engine.py:36-38`, `tools/mock_gui.py:35-37, 41-44`; consumed by `tools/tests/test_contract.py:63-76`
Doc ↔ mock ↔ driver agreement is asserted by importing constants, not parsing source. Console exposes `GO_LITERAL`-equivalent builder, `LOG_KEYS`-equivalent key order, and `SRC_SET` as module data; `test_contract.py` and `test_movelog.py` import them.

### Fail-closed validation with typed evidence
**Source:** `tools/doctor.py:10-15, 43-44` + `vendor/chess/__init__.py:160-170`
Apply to: `game/moves.py` (typed rejects), `transport/parser.py` (whitelist, garbage tolerated), `log/lint.py` (all-checks-fail-closed). Every rejection carries machine-readable kind + raw token to the journal; human-readable one-line reason to the operator (doctor's `record(status, reason)` shape).

### Subprocess hygiene
**Source:** `tools/mock_gui.py:57-59, 71-76, 112-125`
`Popen(argv_list)` never `shell=True` (RESEARCH.md Security Domain); send checks `poll()`; reap via `quit` → `wait(timeout)` → `kill()` in `finally`. Applies to transport + e2e tests.

### Timing discipline
**Source:** `tools/mock_gui.py:165, 192`; `tools/mock_engine.py:50-51`
`time.monotonic_ns()` everywhere; `wall_ms = (monotonic_ns() - t0) // 1_000_000`; `t0` anchored at the `go` write; `wall_ms ≥ engine_ms` asserted at write time AND re-checked by `log_lint`. `time.monotonic()` only inside mock_engine (peer process, not console code).

### Test framework + env
**Source:** `tools/tests/test_contract.py:30-37, 134`; Phase 1 decision (pytest absent, stdlib `unittest` only)
- `unittest.TestCase`, `python3 -m unittest discover` runnable.
- `REPO = pathlib.Path(__file__).parent.resolve().parent.parent` repo-root idiom.
- `env={**os.environ, "PYTHONPATH": str(REPO / "vendor")}` for anything importing `chess`.
- `self.addCleanup` for every tmp artefact; explicit `timeout=` on every subprocess call.

---

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `console/src/console/ui/loop.py` | controller | event-driven | No select-on-stdin + engine-queue-poll precedent exists. Phase 1 tools are batch drivers. Use RESEARCH.md system diagram (lines 217-244) + Pitfalls 5/8 + ARCHITECTURE anti-patterns 7/8 as the spec; the transport/FSM analogs supply the other half of the loop. |

Everything else has an in-repo analog; `game/board.py` is thin glue over the externally-vendored `chess.Board` (R14-permitted; RESEARCH.md "spend zero custom code on chess itself").

---

## Metadata

**Analog search scope:** `tools/`, `tools/tests/`, `vendor/chess/` (targeted line reads only)
**Files scanned:** 8 read in full or part (`mock_gui.py` 308L, `mock_engine.py` 238L, `doctor.py` 1-120, `test_contract.py` 207L, `test_doctor.py` 108L, `test_tb_ceiling.py` 87L, `vendor/chess/__init__.py:150-199`, `tools/tests/__init__.py` glob-verified); 16 Python files enumerated via glob
**Tracked-source gate:** all named analogs verified via `git ls-files` (non-empty); no `.gsd` mirrors exist
**Pattern extraction date:** 2026-10-27
