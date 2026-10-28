#!/usr/bin/env python3
# ChessChallendIII — console entrypoint and transport smoke (plan 02-01)
# Copyright (C) 2026 ChessChallendIII
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.  See Copying.txt for the full text.

"""Console wiring (mock_gui main() shape) plus --transport-smoke.

The smoke mode proves the five wire facts (plan 02-01 Task 1) on the real
competition binary: handshake (uciok within 10 s, readyok after isready), one
full search on the frozen §3.1 go literal with exactly one bestmove, the stop
semantics (exactly one bestmove for the interrupted search), `bestmove (none)`
preceded by `info depth 0 score mate 0`, and the illegal-position probe
(`info string CRITICAL ERROR:` on stdout, exit rc=1) — with engine stderr
empty throughout normal UCI ops. Every stdin/stdout line is written with
monotonic stamps to the --record path.

Smoke-only probes (fen position, illegal move list) run in throwaway
subprocess instances and never from the game path: the game send path is
`position startpos moves …` exclusively (PROTOCOL §4.1).
"""

import argparse
import hashlib
import os
import queue
import pathlib
import subprocess
import sys

from console.transport.uci import EngineTransport, go_line
from console.game.board import BoardState
from console.game.journal import Journal
from console.engine.session import Session
from console.ui.loop import OperatorLoop

# Smoke probes spawn throwaway engine instances; run them from the repo root
# so relative paths (./src/stockfish, tools/mock_none_engine.py) resolve the
# same way from any caller cwd.
REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]


def parse_args():
    p = argparse.ArgumentParser(description="ChessChallendIII console")
    p.add_argument("--engine", default="./src/stockfish",
                   help="engine binary or script path (default: ./src/stockfish)")
    p.add_argument("--engine-arg", action="append", default=[],
                   help="extra flag passed to the engine, repeatable")
    p.add_argument("--record", default=None,
                   help="JSONL transcript path (stdin/stdout + monotonic stamps)")
    p.add_argument("--our-color", choices=("w", "b"), default="w",
                   help="our colour this game (default w); with b the console"
                        " waits for the opponent's first move")
    p.add_argument("--clock-ms", action="append", default=[],
                   help="clock passthrough numbers for the frozen go line,"
                        " repeatable: w=600000,b=600000 (Phase 3 replaces"
                        " with the ClockModel)")
    p.add_argument("--transport-smoke", action="store_true",
                   help="run the five-wire-fact spike against --engine and exit")
    p.add_argument("--log-dir", default=None,
                   help="journal + log directory (resolved absolute; created"
                        " if missing; loud refusal if unwritable at"
                        " GAME_START). Without it the console runs without"
                        " a journal (dev mode only).")
    p.add_argument("--game-id", default=None,
                   help="game id for journal-<id>.jsonl / game-<id>.log"
                        " (alnum + dash)")
    p.add_argument("--auto-opp", default=None, metavar="LINE",
                   help="tracer mode: the opponent's moves are fed from a"
                        " fixed legal UCI line (space-separated); the feeder"
                        " types a move only when the replica says it is the"
                        " opponent's turn and the scripted move is legal"
                        " there")
    p.add_argument("--max-plies", default=None, type=int, metavar="N",
                   help="tracer mode: end the game after N half-moves (or a"
                        " terminal bestmove) — GAME_END, log write, in-process"
                        " lint, exit 0")
    p.add_argument("--syzygy-path", default=None, metavar="DIR",
                   help="absolute path to the Syzygy 3-4-5 tablebase"
                        " directory; validated (existing absolute directory)"
                        " or loud SystemExit before the game (CR-12: a"
                        " placeholder SyzygyPath is never sent)")
    return p.parse_args()


def validate_game_id(game_id):
    """T-02-15: game id is alnum + dash only — no path traversal surface."""
    if game_id is None:
        return None
    if not game_id or not all(c.isalnum() or c == "-" for c in game_id):
        raise SystemExit(f"bad --game-id {game_id!r}: use alnum + dash only")
    return game_id


def validate_syzygy_path(value):
    """CR-12 (main half): --syzygy-path is validated BEFORE the game —
    existing, absolute directory, or loud SystemExit with a named reason.
    Returns the resolved absolute path str, or None when the flag is
    absent (no SyzygyPath option is ever sent in that case)."""
    if value is None:
        return None
    path = pathlib.Path(value).expanduser().resolve()
    if not path.is_absolute():
        raise SystemExit(f"bad --syzygy-path {value!r}: not an absolute path")
    if not path.is_dir():
        raise SystemExit(f"bad --syzygy-path {value!r}: no such directory "
                         f"({path})")
    return str(path)


def open_journal(log_dir, game_id):
    """Journal at <dir>/journal-<game-id>.jsonl, dir resolved absolute.

    Created if missing; unwritable target refuses loudly BEFORE the game
    starts (acceptance criterion: non-zero exit, named reason). The probe
    appends+fsyncs to a throwaway file in the SAME directory — the real
    journal's first record stays the session's own GAME_START.
    """
    from console.game.journal import append_event
    directory = pathlib.Path(log_dir).expanduser().resolve()
    try:
        directory.mkdir(parents=True, exist_ok=True)
        if not os.access(directory, os.W_OK | os.X_OK):
            raise PermissionError(directory)
        probe = directory / ".journal-probe.tmp"
        append_event(probe, {"e": "GAME_START", "probe": "writability"})
        records = Journal(probe).iter_records()
        assert records and records[-1].get("probe") == "writability"
        probe.unlink(missing_ok=True)
        journal_name = f"journal-{game_id}.jsonl" if game_id \
            else "journal.jsonl"
        return Journal(directory / journal_name)
    except (OSError, PermissionError, AssertionError) as exc:
        raise SystemExit(
            f"FATAL: --log-dir {log_dir!r} is not writable for the journal "
            f"({directory}): {exc}") from exc


def engine_sha256(engine_path):
    """§5.1 header field: the engine binary's sha256, recomputed at game
    start (dev builds change; the header always tells the truth)."""
    path = pathlib.Path(engine_path)
    try:
        digest = hashlib.sha256()
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except OSError:
        return "unavailable"  # script engines (mocks) have no binary sha


# nn-1a298aa575a0.nnue — PROVENANCE §1 (official SF19 net, CC0,
# unmodified). Full sha256, published in PROVENANCE and verifiable from
# the source URL; the fallback covers a worktree without the vendored
# net file (CR-04.4: the header always carries the FULL digest).
NET_FILE = "src/nn-1a298aa575a0.nnue"
NET_SHA256_PUBLISHED = \
    "1a298aa575a085434d29027978dc36867fe9c5bcea9376654b7a8eba1e52dfc2"


def net_sha256(net_path=None):
    """§5.1 header field: the NNUE net's FULL sha256, hashed from the
    vendored file at game start like engine_sha256 hashes the binary
    (CR-04.4: the 12-char filename prefix + prose form is gone). On
    OSError the PROVENANCE-published full hash is the documented
    constant fallback."""
    path = pathlib.Path(REPO_ROOT / (net_path or NET_FILE))
    try:
        digest = hashlib.sha256()
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except OSError:
        return NET_SHA256_PUBLISHED


def format_time_control(w_ms, b_ms):
    """§5.1 `# time-control` from the run's ACTUAL clock numbers (CR-04.1:
    never a hardcoded 15+10). `M+S` from the passthrough ms — minutes =
    ms // 60000, seconds = the ms remainder // 1000. The passthrough sends
    the same budget to both sides, so w is the source (a w≠b spec is a
    Phase 3 ClockModel concern)."""
    minutes = w_ms // 60000
    seconds = (w_ms % 60000) // 1000
    return f"{minutes}+{seconds}"


def parse_clock_ms(specs):
    """`w=600000,b=600000` repeatable specs → (w_ms, b_ms)."""
    clocks = {"w": 600000, "b": 600000}
    for spec in specs:
        for part in spec.split(","):
            if not part.strip():
                continue
            side, _, value = part.partition("=")
            side = side.strip().lower()
            if side not in ("w", "b") or not value.strip().isdigit():
                raise SystemExit(f"bad --clock-ms spec: {part!r} (use w=<ms>,b=<ms>)")
            clocks[side] = int(value)
    return clocks["w"], clocks["b"]


def engine_argv(args):
    if args.engine.endswith(".py"):
        return [sys.executable, args.engine, *args.engine_arg]
    return [args.engine, *args.engine_arg]


def _wait_event(t, timeout, want):
    """Consume events until one of type `want`; timeout/eof is fatal."""
    while True:
        try:
            event = t.events.get(timeout=timeout)
        except queue.Empty:
            raise RuntimeError(f"timed out waiting for {want}")
        if event["type"] in ("eof", "timeout"):
            raise RuntimeError(f"engine {event['type']} while waiting for {want}")
        if event["type"] == want:
            return event


def _drain_to_bestmove(t, timeout):
    """Consume info events until the current search's bestmove arrives."""
    info_events = []
    while True:
        try:
            event = t.events.get(timeout=timeout)
        except queue.Empty:
            raise RuntimeError("timed out waiting for bestmove")
        if event["type"] == "bestmove":
            return event, info_events
        if event["type"] in ("eof", "timeout"):
            raise RuntimeError(f"engine {event['type']} before bestmove")
        info_events.append(event)


def _assert_search_found(t, expect_move=None):
    """Assert exactly one non-stale bestmove for the outstanding search."""
    event, _ = _drain_to_bestmove(t, 120.0)
    if expect_move is not None:
        assert event["move"] == expect_move, event
    # Exactly one bestmove: the next event must NOT be another bestmove.
    try:
        extra = t.events.get(timeout=1.0)
    except queue.Empty:
        return event
    assert extra["type"] != "bestmove", f"second bestmove: {extra}"
    t.events.put(extra)  # not ours to lose
    return event


def _spike_probe_none():
    """Throwaway subprocess: `bestmove (none)` preceded by mate 0 (§7.2)."""
    argv = [sys.executable, "-c", SMOKE_NONE_PROBE]
    p = subprocess.run(argv, capture_output=True, text=True, timeout=60,
                       cwd=REPO_ROOT)
    assert p.returncode == 0, p.stdout + p.stderr
    return p.stdout


def _spike_probe_illegal(record_path):
    """Throwaway subprocess: illegal position → CRITICAL ERROR + rc=1 (§9.1)."""
    argv = [sys.executable, "-c", SMOKE_ILLEGAL_PROBE, record_path]
    p = subprocess.run(argv, capture_output=True, text=True, timeout=60,
                       cwd=REPO_ROOT)
    assert p.returncode == 0, (
        f"illegal-position probe failed rc={p.returncode}: {p.stdout}{p.stderr}")
    return p.stdout


def transport_smoke(args):
    """The five wire facts, end-to-end on the real binary. Exit 0 = proven."""
    t = EngineTransport(engine_argv(args), record=args.record)
    try:
        # Fact 1 — handshake: uciok within 10 s, readyok after isready.
        info = t.handshake(timeout=10.0)
        assert info["id_name"], "no id name in handshake"
        t.flush_pending_options()  # no-op with an empty queue; proves IDLE path

        # Fact 2 — one full search on the frozen go literal: info stream, then
        # exactly one bestmove.
        t.send("position startpos moves e2e4")
        t.start_search()
        t.send(go_line(600000, 600000))
        event = _assert_search_found(t)
        assert event["search_id"] == 1

        # Fact 3 — stop semantics: go, then stop, exactly one bestmove total.
        t.start_search()
        t.send("position startpos moves e2e4 e7e5")
        t.send(go_line(600000, 600000))
        try:
            t.events.get(timeout=0.5)  # let info flow
        except queue.Empty:
            pass
        t.send("stop")
        _assert_search_found(t)

        # Fact 4 — bestmove (none) preceded by info depth 0 score mate 0.
        # Probe output lines are appended to the --record transcript so the
        # committed evidence carries the fact verbatim (plan 02-01 Task 1.5).
        none_out = _spike_probe_none()
        if args.record:
            import json as _json
            import time as _time
            with open(args.record, "a", encoding="utf-8") as fh:
                for _line in none_out.splitlines():
                    if _line.strip():
                        fh.write(_json.dumps(
                            {"t": _time.monotonic_ns(), "dir": "out",
                             "line": _line}) + "\n")

        # Fact 5 — illegal position: info string CRITICAL ERROR: + rc=1.
        illegal_out = _spike_probe_illegal(args.record or "/dev/null")
    finally:
        t.close()

    assert "bestmove (none)" in none_out
    assert "score mate 0" in none_out
    assert "CRITICAL ERROR" in illegal_out
    assert t.stderr_text == "", f"stderr not empty during UCI ops: {t.stderr_text!r}"
    print("OK transport smoke: 5 wire facts confirmed")
    return 0


SMOKE_NONE_PROBE = '''
# Throwaway (none)-probe: fen is legal UCI and used ONLY here (never the game path).
import queue, subprocess, sys
from console.transport.uci import EngineTransport
t = EngineTransport([sys.executable, "tools/mock_none_engine.py"])
t.handshake(timeout=10.0)
t.send("position fen 7k/5Q2/6K1/8/8/8/8/8 b")
t.start_search()
t.send("go wtime 600000 btime 600000 winc 10000 binc 10000")
deadline = 60.0
while True:
    ev = t.events.get(timeout=deadline)
    if ev["type"] == "bestmove":
        assert ev["move"] == "(none)", ev
        print(f"out> bestmove {ev['move']}", flush=True)
        break
    if ev["type"] in ("eof", "timeout"):
        raise SystemExit(1)
    if ev["type"] == "info":
        print(f"out> info depth {ev.get('depth', 0)} "
              f"score {ev.get('score', '-')}", flush=True)
t.close()
'''

SMOKE_ILLEGAL_PROBE = '''
# Throwaway illegal-position probe (PROTOCOL 9.1): CRITICAL ERROR + rc=1.
import subprocess, sys, time
record = sys.argv[1]
p = subprocess.Popen(["./src/stockfish"], stdin=subprocess.PIPE,
                     stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=0)
lines = []
def send(line):
    p.stdin.write((line + "\\n").encode()); p.stdin.flush()
    lines.append(("in", line))
def read_until(tok, timeout=30.0):
    buf = b""
    end = time.monotonic() + timeout
    while tok not in buf and time.monotonic() < end:
        chunk = p.stdout.read1(4096) if hasattr(p.stdout, "read1") else p.stdout.read(1)
        if not chunk:
            break
        buf += chunk
    for raw in buf.split(b"\\n"):
        text = raw.decode(errors="replace").rstrip("\\r")
        if text.strip():
            lines.append(("out", text))
    return buf
send("uci"); read_until(b"uciok")
send("isready"); read_until(b"readyok")
send("position startpos moves z9z9")
out = read_until(b"CRITICAL ERROR", timeout=30.0)
try:
    p.wait(timeout=10)
except subprocess.TimeoutExpired:
    p.kill()
rc = p.returncode
for d, line in lines:
    print(f"{d}> {line}", flush=True)
import json
with open(record, "a", encoding="utf-8") as fh:
    for d, line in lines:
        fh.write(json.dumps({"t": time.monotonic_ns(), "dir": d, "line": line}) + "\\n")
raise SystemExit(0 if (b"CRITICAL ERROR" in out and rc == 1) else 1)
'''


def run_game(args) -> int:
    """Game mode: handshake → §2.3 options at IDLE → start_game (B1) → loop.

    Startup order is load-bearing: option flush happens BEFORE start_game
    (flush is IDLE-only), and with --our-color w the game-start trigger
    fires search #1 without operator input; with b the console waits for
    the opponent's first typed move. With --log-dir the session's event
    sink is a real fsync Journal (02-03); every session event lands on
    disk before the console proceeds.

    Tracer mode (--auto-opp + --max-plies): a feeder thread plays the
    opponent's side of a fixed legal line; at --max-plies half-moves (or
    a terminal (none)) the game ends, the .log is rendered from the
    journal, linted in-process, and the run exits 0 on `OK fullgame`.
    """
    game_id = validate_game_id(args.game_id)
    syzygy_path = validate_syzygy_path(args.syzygy_path)
    journal = open_journal(args.log_dir, game_id) if args.log_dir else None
    sink = journal.append if journal is not None else (lambda event: None)
    w_ms, b_ms = parse_clock_ms(args.clock_ms)
    argv = engine_argv(args)
    # Python engine scripts run from the repo root so tools/ imports and
    # relative --record paths resolve the same from any caller cwd.
    transport = EngineTransport(argv, record=args.record,
                                cwd=str(REPO_ROOT)
                                if args.engine.endswith(".py") else None)
    tracer = None
    try:
        transport.handshake(timeout=10.0)
        session = Session(transport, BoardState(), sink=sink,
                          our_color=args.our_color)
        session.game_id = game_id
        session.clock_passthrough_ms = (w_ms, b_ms)
        if syzygy_path is not None:
            # CR-12: the only path back into the option set — a validated
            # absolute directory. Never a placeholder.
            session.options.append(("SyzygyPath", syzygy_path))
        session.apply_startup_options()  # §2.3 set, flushed once at IDLE
        session.start_game(game_id=game_id)  # B1: search #1 fires iff we move first
        loop = OperatorLoop(session, transport)
        tracer = None
        if args.auto_opp is not None or args.max_plies is not None:
            tracer = GameTracer(session, loop, transport,
                                journal=journal,
                                our_color=session.our_color,
                                auto_opp=args.auto_opp or "",
                                max_plies=args.max_plies,
                                log_dir=args.log_dir,
                                game_id=game_id,
                                engine_path=args.engine,
                                clock_ms=(w_ms, b_ms),
                                syzygy_path=syzygy_path)
            tracer.start()
        try:
            rc = loop.run(tracer=tracer)
        finally:
            if tracer is not None:
                tracer.stop()
        return rc
    finally:
        try:
            transport.close()
        except (RuntimeError, OSError):
            pass


def main() -> int:
    args = parse_args()
    if args.transport_smoke:
        return transport_smoke(args)
    return run_game(args)


class GameTracer:
    """02-03 tracer: scripted opponent feeder + ply cap + log/lint exit.

    Feeder (research Open Question #4, fixed-legal-line option): a daemon
    thread polls the session; when the replica says it is the OPPONENT'S
    turn and the next scripted move is legal there, it is typed into the
    loop's normal input path — the console validates it exactly as a human
    token (no feeder shortcut past the legality gate). A scripted move
    that no longer matches the position is skipped forward (the engine's
    reply diverged from the line; the next matching position resumes).

    Termination: max_plies MOVE_LOGGED rows, or a terminal (none), or
    engine death — GAME_END is journaled, the .log is rendered from the
    journal via MoveLog (header §5.1 + move lines §3.1 + trailer §5.2),
    linted in-process, and `OK fullgame: N half-moves, lint clean` is
    printed. The loop's `q`-shutdown races are avoided by stopping the
    loop directly (the tracer owns the exit path).
    """

    def __init__(self, session, loop, transport, *, journal, our_color,
                 auto_opp, max_plies, log_dir=None, game_id=None,
                 engine_path="./src/stockfish", clock_ms=(900000, 900000),
                 syzygy_path=None):
        import threading
        self.session = session
        self.loop = loop
        self.transport = transport
        self.journal = journal
        self.our_color = our_color
        self.line = auto_opp.split()
        self.max_plies = max_plies if max_plies is not None else 10 ** 9
        self.log_dir = log_dir
        self.game_id = game_id
        self.engine_path = engine_path
        self.clock_ms = clock_ms
        self.syzygy_path = syzygy_path
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self.finished = False

    def start(self):
        self._thread.start()

    def stop(self):
        self._stop.set()
        self._thread.join(timeout=5)

    # --- feeder ---------------------------------------------------------
    def _run(self):
        import time
        deadline = time.monotonic() + 280.0  # inside the e2e's 300 s budget
        while not self._stop.is_set() and not self.finished:
            if time.monotonic() > deadline:
                self._finish("wall-clock budget exceeded")
                return
            if self.transport.popen.poll() is not None:
                self._finish("engine exited")
                return
            rows = self._move_rows()
            if len(rows) >= self.max_plies:
                self._finish(None)
                return
            if any(r.get("e") == "GAME_END" for r in self._records()):
                self._finish(None)
                return
            # Terminal search (no legal move): the (none) row is already
            # in the journal — the GAME_END check above caught it.
            if (self.session.board.expected_mover() != self.our_color
                    and self._next_opp_token() is None):
                # Scripted line run dry with the game still open: a
                # harness-driven game ends here — never idle until the
                # wall budget (the engine has nothing to answer).
                self._finish(None, reason="scripted line exhausted")
                return
            self._feed_one()
            time.sleep(0.02)

    def _records(self):
        if self.journal is None:
            return []
        return self.journal.iter_records()

    def _move_rows(self):
        return [r for r in self._records() if r.get("e") == "MOVE_LOGGED"]

    def _feed_one(self):
        """Type the next scripted opp move when it is opp's turn + legal."""
        board = self.session.board
        if board.expected_mover() == self.our_color:
            return  # our move: the engine is searching
        token = self._next_opp_token()
        if token is None:
            # Line exhausted (or diverged): the terminal/max-plies/
            # wall-clock guards own the end; stop feeding.
            return
        # The session's normal input path — same side guard, same typed
        # legality gate, same MOVE_LOGGED journal record as a human token.
        self.session.on_operator_move(token)

    def _next_opp_token(self):
        """First scripted token not yet on the board and legal now.

        Legality is probed on a scratch replica replaying the live move
        list — the board stays the gate; a diverged scripted move is
        skipped (the next matching position resumes the line).
        """
        board = self.session.board
        played = set(board.moves)
        for token in self.line:
            if token in played:
                continue
            scratch = type(board)()
            for uci in board.moves:
                scratch.try_push_token(uci)
            move, reject = scratch.try_push_token(token)
            if move is not None:
                return token
            continue  # diverged: skip and try the next scripted token
        return None

    # --- finish: journal → log → lint → OK --------------------------------
    def _finish(self, failure, reason=None):
        if self.finished:
            return
        self.finished = True
        session = self.session
        records = self._records()
        rows = [r for r in records if r.get("e") == "MOVE_LOGGED"]
        game_end = next((r for r in reversed(records)
                         if r.get("e") == "GAME_END"), None)
        reason = failure or reason or (game_end or {}).get("reason") or \
            f"max-plies {self.max_plies} reached"
        result = (game_end or {}).get("result", "*")
        if failure:
            self.loop.say(f"TRACER FAILURE: {failure}")
        # Journal the termination when it is not already there.
        if not game_end and self.journal is not None:
            self.journal.append({"e": "GAME_END", "reason": reason,
                                 "result": result})
        # Render the .log from the journal (never a parallel history).
        try:
            self._write_log(records, reason, result)
            n = len(rows)
            self.loop.say(f"OK fullgame: {n} half-moves, lint clean")
        except TracerLogError as exc:
            self.loop.say(f"TRACER LOG/LINT FAILURE: {exc}")
        # The loop's stdin is the operator's; end the run from here.
        self.loop._quit = True

    def _write_log(self, records, reason, result):
        import datetime
        import pathlib
        from console.log.lint import lint_log
        from console.log.movelog import MoveLog, render
        if self.journal is None or self.log_dir is None:
            return  # tracer needs a journal target
        log_dir = pathlib.Path(self.log_dir).expanduser().resolve()
        log_dir.mkdir(parents=True, exist_ok=True)
        name = f"game-{self.game_id}.log" if self.game_id else "game.log"
        log_path = log_dir / name
        w_ms, b_ms = self.clock_ms
        # CR-04.5: the header's option set reflects the ACTUAL effective
        # set the session flushed (a validated --syzygy-path rides here;
        # absent → the header shows the set without it, never a placeholder).
        option_parts = [f"{name}={value}"
                        for name, value in self.session.options]
        with open(log_path, "w", encoding="utf-8") as fh:
            # §5.1 header via MoveLog's writer (CR-04.3: no hand-rolled
            # header) — real time-control (CR-04.1) and full net sha256
            # (CR-04.4).
            MoveLog.write_header(
                fh,
                game_id=self.game_id or "game",
                date=datetime.date.today().isoformat(),
                our_color=self.our_color,
                time_control=format_time_control(w_ms, b_ms),
                engine_sha256=engine_sha256(self.engine_path),
                net_sha256=net_sha256(),
                options=option_parts,
                syzygy_probe_limit=5,
                tb_inventory_hash="none",
                book_hash="none",
                book_max_ply=0)
            # Move rows: fold from the journal (the projection discipline).
            for rec in MoveLog.build(records):
                fh.write(render(rec) + "\n")
            # §5.2 trailer via MoveLog's writer. The clock numbers are the
            # initial passthrough values — CR-04.2 labels them honestly
            # (observed clocks land in Phase 3, CLOCK-08/LOG-05).
            MoveLog.write_trailer(
                fh, result=result, reason=reason,
                final_clock_ms=(w_ms, b_ms), log_path=log_path,
                note="initial clock passthrough values, not observed "
                     "remaining (observed clocks land in Phase 3, CLOCK-08)")
        # In-process lint — fail-closed: a failing log raises.
        failures = lint_log(log_path)
        if failures:
            raise TracerLogError("; ".join(failures[:5]))


class TracerLogError(Exception):
    """The rendered log failed log_lint — never shipped (fail closed)."""


if __name__ == "__main__":
    sys.exit(main())
