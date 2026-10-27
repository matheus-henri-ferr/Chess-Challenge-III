#!/usr/bin/env python3
# ChessChallendIII — mock GUI/driver speaking docs/PROTOCOL.md (plan 01-02)
# Copyright (C) 2026 ChessChallendIII
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.  See Copying.txt for the full text.

"""Drives a real (or mock) UCI engine through the frozen contract so the TM
track can measure budgets without the console.

Runs any UCI engine as a subprocess (stdlib only — the DRIVER does no legality
work; legality is the console's job in Phase 2). Run as:
    python3 tools/mock_gui.py --engine tools/mock_engine.py ...

The driver sends ONLY the frozen `go` literal of PROTOCOL §3.1:
    go wtime <int_ms> btime <int_ms> winc 10000 binc 10000
(ponder variant under --ponder), and maintains exactly one outstanding `go`.

Per-move CSV columns: move_no,side,uci,depth,nodes,score,engine_ms,wall_ms,pv,tm_trace
(the eight mandatory LOGBOOK §2 keys plus the TM trace).
"""

import argparse
import csv
import json
import random
import selectors
import subprocess
import sys
import time

# PROTOCOL §3.1 — the frozen literal. Tests assert document ↔ driver agreement;
# keep in sync with docs/PROTOCOL.md.
GO_LITERAL = "go wtime <int_ms> btime <int_ms> winc 10000 binc 10000"

OPENING_BOOK = ["e2e4", "e7e5", "g1f3", "b8c6", "f1b5", "a7a6", "b5a4", "g8f6"]

# The per-move CSV header, exposed as data: tests assert it carries every
# LOGBOOK §2 key. Order: identity, search fields, wall/engine time, PV, TM.
CSV_COLUMNS = ["move_no", "side", "uci", "depth", "nodes", "score",
               "engine_ms", "wall_ms", "pv", "tm_trace"]


class EngineProc:
    """Subprocess wrapper with read-until-predicate and hard timeouts."""

    def __init__(self, argv, tm_trace, record):
        argv = list(argv)
        if tm_trace and "--tm-trace" not in argv:
            argv.append("--tm-trace")
        self.popen = subprocess.Popen(
            argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, universal_newlines=True, bufsize=1,
        )
        self.rec = open(record, "a", encoding="utf-8") if record else None
        self.pending_bestmove = None  # a bestmove nobody consumed yet (stale)

    def _record(self, direction, line):
        if self.rec:
            self.rec.write(json.dumps({"t": time.monotonic_ns(),
                                       "dir": direction, "line": line}) + "\n")
            self.rec.flush()

    def send(self, line):
        if self.popen.poll() is not None:
            raise RuntimeError(f"engine exited rc={self.popen.returncode}")
        self._record("in", line)
        self.popen.stdin.write(line + "\n")
        self.popen.stdin.flush()

    def readline(self, timeout=30.0):
        """One line with a REAL timeout: a hung engine (--silent-hang) raises
        instead of blocking in stdout.readline() forever."""
        sel = selectors.DefaultSelector()
        sel.register(self.popen.stdout, selectors.EVENT_READ)
        try:
            if not sel.select(timeout):
                raise TimeoutError(f"engine silent for {timeout}s (hung or dead)")
            raw = self.popen.stdout.readline()
        finally:
            sel.close()
        if raw == "":  # EOF: engine died (PROTOCOL §9.2 territory)
            raise RuntimeError("engine EOF (crashed or quit mid-exchange)")
        line = raw.rstrip("\n")
        if not line.strip():
            return self.readline(timeout)  # skip blank, budget resets
        self._record("out", line)
        return line

    def expect(self, exact):
        """Consume lines until one equals `exact`."""
        while True:
            line = self.readline()
            if line == exact:
                return

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


def bestmove_of(line):
    return line[len("bestmove "):]


class Game:
    def __init__(self, args, proc, game_no, base_ms, inc):
        self.args = args
        self.proc = proc
        self.game_no = game_no
        self.base_ms = base_ms  # --tc minutes:inc, parsed once in main()
        self.inc = inc
        self.rows = []

    # --- the frozen go line (PROTOCOL §3.1) -----------------------------
    def go_line(self, w_ms, b_ms, ponder=False):
        if ponder:
            return f"go ponder wtime {w_ms} btime {b_ms} winc 10000 binc 10000"
        return f"go wtime {w_ms} btime {b_ms} winc 10000 binc 10000"

    def search(self, moves, side_ms):
        """One full search cycle; returns the engine's chosen move token."""
        if self.proc.pending_bestmove is not None:
            # PROTOCOL §7.3: a bestmove with no matching go is stale; discard.
            self.proc.pending_bestmove = None

        self.proc.send("position startpos moves " + " ".join(moves)
                       if moves else "position startpos")
        w_ms, b_ms = (max(0, int(x)) for x in side_ms)
        assert w_ms >= 0 and b_ms >= 0  # driver invariant: never negative
        line = self.go_line(w_ms, b_ms, ponder=False)
        self.proc.send(line)

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
                mv = bestmove_of(line)
                self.rows.append({
                    "move_no": (len(moves) + 2) // 2,
                    "side": "w" if len(moves) % 2 == 0 else "b",
                    "uci": mv,
                    "depth": depth,
                    "nodes": nodes,
                    "score": score,
                    "engine_ms": time_ms,
                    "wall_ms": wall_ms,
                    "pv": pv,
                    "tm_trace": tm,
                })
                return mv

    def play(self):
        moves = []
        clocks = [self.base_ms, self.base_ms]
        inc = self.inc
        for _ in range(self.args.max_plies):
            mover = "w" if len(moves) % 2 == 0 else "b"
            side_idx = 0 if mover == "w" else 1
            mv = self.search(moves, clocks)
            if mv == "(none)":
                break
            moves.append(mv)
            clocks[side_idx] += inc - int(self.rows[-1]["wall_ms"])
            clocks[side_idx] = max(clocks[side_idx], 0)
            # book: keep the scripted opening legal-ish for BOTH mocks
            if len(moves) >= len(OPENING_BOOK):
                break
            # latency tail: the human/operator delay this mock exists to model
            p50, p95 = (int(x) for x in self.args.latency_ms.split(","))
            time.sleep(random.uniform(p50, p95) / 1000.0)
        return moves


def parse_args():
    p = argparse.ArgumentParser(description="ChessChallendIII contract driver")
    p.add_argument("--engine", default="tools/mock_engine.py")
    p.add_argument("--games", type=int, default=1)
    p.add_argument("--max-plies", type=int, default=16)
    p.add_argument("--start-fen", default=None, help="logged; mock plays the scripted opening")
    p.add_argument("--tc", default="15:10",
                   help="minutes:increment per side, e.g. 15:10 (drives the clocks)")
    p.add_argument("--latency-ms", default="5,20", help="p50,p95 operator tail in ms")
    p.add_argument("--option", action="append", default=[], help="k=v, repeatable")
    p.add_argument("--require-tm", action="store_true",
                   help="launch engine with --tm-trace and assert tm= on every search")
    p.add_argument("--engine-arg", action="append", default=[],
                   help="extra flag passed to the engine, e.g. --engine-arg=--delay-ms=2800")
    p.add_argument("--record", default=None, help="JSONL transcript path")
    p.add_argument("--csv", default=None, help="per-move CSV path")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    if args.engine.endswith(".py"):
        engine_argv = [sys.executable, args.engine, *args.engine_arg]
    else:
        engine_argv = [args.engine, *args.engine_arg]

    minutes, inc_s = args.tc.split(":")
    base_ms = int(float(minutes) * 60_000)
    inc = int(float(inc_s) * 1000)
    p50, p95 = (int(x) for x in args.latency_ms.split(","))

    proc = EngineProc(engine_argv, args.require_tm, args.record)

    try:
        # Handshake (PROTOCOL §2)
        proc.send("uci")
        proc.expect("uciok")
        for opt in args.option:
            if "=" in opt:
                k, v = opt.split("=", 1)
                proc.send(f"setoption name {k} value {v}")
        proc.send("isready")
        proc.expect("readyok")

        all_rows = []
        for g in range(args.games):
            game = Game(args, proc, g, base_ms, inc)
            moves = game.play()
            all_rows.extend(game.rows)
            # ucinewgame between games only (PROTOCOL §2.4)
            if g + 1 < args.games:
                proc.send("ucinewgame")
    finally:
        proc.close()

    # Driver invariants (self-asserting contract checks)
    if args.require_tm:
        for r in all_rows:
            assert r["tm_trace"], f"missing tm= trace on move {r['move_no']}: {r}"
    for r in all_rows:
        assert int(r["depth"]) >= 0 and int(r["nodes"]) >= 0
        assert int(r["wall_ms"]) >= int(r["engine_ms"]), \
            f"wall_ms >= engine_ms violated: {r}"

    if args.csv:
        with open(args.csv, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=CSV_COLUMNS)
            writer.writeheader()
            writer.writerows(all_rows)

    print(f"OK mock_gui: {len(all_rows)} searches across {args.games} game(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
