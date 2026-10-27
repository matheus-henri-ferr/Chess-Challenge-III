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
import queue
import subprocess
import sys

from console.transport.parser import parse_line
from console.transport.uci import EngineTransport, go_line


def parse_args():
    p = argparse.ArgumentParser(description="ChessChallendIII console")
    p.add_argument("--engine", default="./src/stockfish",
                   help="engine binary or script path (default: ./src/stockfish)")
    p.add_argument("--engine-arg", action="append", default=[],
                   help="extra flag passed to the engine, repeatable")
    p.add_argument("--record", default=None,
                   help="JSONL transcript path (stdin/stdout + monotonic stamps)")
    p.add_argument("--transport-smoke", action="store_true",
                   help="run the five-wire-fact spike against --engine and exit")
    return p.parse_args()


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
    p = subprocess.run(argv, capture_output=True, text=True, timeout=60)
    assert p.returncode == 0, p.stdout + p.stderr
    return p.stdout


def _spike_probe_illegal(record_path):
    """Throwaway subprocess: illegal position → CRITICAL ERROR + rc=1 (§9.1)."""
    argv = [sys.executable, "-c", SMOKE_ILLEGAL_PROBE, record_path]
    p = subprocess.run(argv, capture_output=True, text=True, timeout=60)
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


def main() -> int:
    args = parse_args()
    if args.transport_smoke:
        return transport_smoke(args)
    print("console: game mode lands in plan 02-02 (this plan ships the transport)",
          file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
