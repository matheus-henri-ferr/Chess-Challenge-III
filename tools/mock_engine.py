#!/usr/bin/env python3
# ChessChallendIII — mock UCI engine speaking docs/PROTOCOL.md (plan 01-02)
# Copyright (C) 2026 ChessChallendIII
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.  See Copying.txt for the full text.

"""A fake UCI engine that speaks exactly docs/PROTOCOL.md, so the console
track can develop before src/stockfish is rebuilt — and can deliberately
misbehave in ways Stockfish will not.

Stdlib only. It imports neither the console nor `chess` nor any project
module: it is a peer of the engine, not a test double for our code.

Scenario flags (one per misbehaviour, RESEARCH Q9):
  --delay-ms N        sleep N ms before every answer
  --crash-after N     exit mid-search after N searches, without bestmove
  --stale-bestmove    answer a later go with a move for the previous position
  --silent-hang       accept go, never answer
  --illegal-bestmove  emit bestmove e2e5 regardless of legality
  --none-bestmove     emit bestmove (none)
  --crash-on-option   exit if a setoption arrives mid-search
  --garbage           emit non-UCI lines on stdout
  --slow-ready        delay readyok by 1.5 s
  --tm-trace          emit the frozen tm= line (PROTOCOL §6.1) per search
  --record <path>     transcript: every stdin/stdout line + monotonic stamps
"""

import argparse
import json
import sys
import time

# PROTOCOL §3.1 — the frozen literal this mock accepts on `go`. Tests assert
# document ↔ mock agreement; keep in sync with docs/PROTOCOL.md.
GO_LITERAL = "go wtime <int_ms> btime <int_ms> winc 10000 binc 10000"

TM_MODES = ("increment", "sudden_death", "armageddon")
TM_REASONS = ("reserve", "bank_positive", "low_clock", "instant", "book_exit", "scramble")


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


class MockEngine:
    def __init__(self, args):
        self.args = args
        self.rec = Recorder(args.record)
        self.options = {
            "Threads": 1, "Hash": 16, "SyzygyPath": "<empty>",
            "SyzygyProbeLimit": 5, "Move Overhead": 100, "Ponder": False,
        }
        self.moves = []
        self.search_count = 0
        self.last_position = "startpos"

    # --- output helpers -------------------------------------------------
    def send(self, line):
        self.rec.log("out", line)
        print(line, flush=True)

    # --- protocol -------------------------------------------------------
    def handle_uci(self):
        self.send("id name MockEngine 1.0 (ChessChallendIII contract mock)")
        self.send("id author ChessChallendIII")
        self.send("option name Threads type spin default 1 min 1 max 1024")
        self.send("option name Hash type spin default 16 min 1 max 4096")
        self.send("option name SyzygyPath type string default <empty>")
        self.send("option name SyzygyProbeLimit type spin default 5 min 0 max 5")
        self.send("option name Move Overhead type spin default 100 min 0 max 5000")
        self.send("option name Ponder type check default false")
        self.send("uciok")

    def handle_setoption(self, line):
        if self.searching and self.args.crash_on_option:
            sys.exit(1)
        rest = line[len("setoption "):]
        if " value " in rest:
            name, value = rest.split(" value ", 1)
        else:
            name, value = rest, ""
        name = name.replace("name ", "", 1).strip()
        self.options[name] = value
        if name not in ("Threads", "Hash", "SyzygyPath", "SyzygyProbeLimit",
                        "Move Overhead", "Ponder"):
            self.send(f"info string unknown option: {name}")

    def handle_position(self, line):
        tokens = line.split()
        if tokens[1] == "startpos":
            self.last_position = "startpos"
            if "moves" in tokens:
                self.moves = tokens[tokens.index("moves") + 1:]
        elif tokens[1] == "fen":
            self.last_position = " ".join(tokens[2:8])

    def handle_go(self, line):
        self.search_count += 1
        self.searching = True
        self.rec.log("state", f"go accepted (search {self.search_count})")

        if self.args.crash_after and self.search_count > self.args.crash_after:
            sys.exit(1)
        if self.args.silent_hang:
            return
        if self.args.delay_ms:
            time.sleep(self.args.delay_ms / 1000.0)

        # A real engine emits one deepest-first info script. Keep it honest:
        # depth strictly increases, then exactly one bestmove (PROTOCOL §7.1).
        base_nodes = 800_000 + 31_000 * len(self.moves)
        for depth, mult in ((9, 1), (13, 3), (16, 7)):
            nodes = base_nodes * mult
            nps = 2_100_000
            t_ms = int(nodes / nps * 1000)
            pv = self.pv_for(depth)
            self.send(f"info depth {depth} seldepth {depth + 6} multipv 1 "
                      f"score cp {12 - depth} nodes {nodes} nps {nps} "
                      f"hashfull {300 + depth} tbhits 0 time {t_ms} pv {pv}")
        if self.args.tm_trace:
            mode = "increment"  # 15+10 is an increment TC
            reason = "reserve"
            self.send(f"info string tm=custom-v1.0 mode={mode} "
                      f"latency_p95_ms=12 bank_ms=4500 budget_ms=18000 "
                      f"reason={reason}")
        self.searching = False

        if self.args.none_bestmove:
            self.send("bestmove (none)")
            return
        if self.args.illegal_bestmove:
            self.send("bestmove e2e5")
            return
        if self.args.stale_bestmove and self.search_count > 1:
            # Answer the CURRENT go with the PREVIOUS position's move.
            self.send(f"bestmove {self.stale_move()}")
            return
        self.send(f"bestmove {self.best_move()}")

    def pv_for(self, depth):
        opening = ["e2e4", "e7e5", "g1f3", "b8c6", "f1b5", "g8f6", "d2d3", "f8c5"]
        # PV grows with depth but never exceeds the scripted opening.
        return " ".join(opening[: min(depth, len(opening))])

    def best_move(self):
        # Move for the position we were given: derive from ply parity so the
        # mock answers the position, not a constant.
        opening = ["e2e4", "e7e5", "g1f3", "b8c6", "f1b5", "a7a6", "b5a4", "g8f6"]
        ply = len(self.moves)
        return opening[ply % len(opening)]

    def stale_move(self):
        return self.moves[-1] if self.moves else "e2e4"

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
                if token == "quit":
                    self.rec.log("state", "quit")
                    return 0
                # stop: a real engine answers with one bestmove; here the
                # search already answered inline, so nothing to do.
            elif token == "uci":
                self.handle_uci()
            elif token == "isready":
                if self.args.slow_ready:
                    time.sleep(self.ready_delay)
                self.send("readyok")
            elif token == "setoption":
                self.handle_setoption(line)
            elif token == "position":
                self.handle_position(line)
            elif token == "go":
                if self.args.garbage:
                    self.send("this line is not UCI at all")
                    self.send("*** GARBAGE ###")
                self.handle_go(line)
            elif token == "ponderhit":
                pass
            elif token == "ucinewgame":
                self.moves = []
            else:
                self.send(f"info string unknown command: {token}")
        return 0  # stdin EOF behaves like quit (PROTOCOL §1; uci.cpp:104-107)


def parse_args():
    p = argparse.ArgumentParser(description="ChessChallendIII contract mock engine")
    p.add_argument("--delay-ms", type=int, default=0)
    p.add_argument("--crash-after", type=int, default=0,
                   help="exit mid-search after N searches without bestmove")
    p.add_argument("--stale-bestmove", action="store_true")
    p.add_argument("--silent-hang", action="store_true")
    p.add_argument("--illegal-bestmove", action="store_true")
    p.add_argument("--none-bestmove", action="store_true")
    p.add_argument("--crash-on-option", action="store_true")
    p.add_argument("--garbage", action="store_true")
    p.add_argument("--slow-ready", action="store_true")
    p.add_argument("--tm-trace", action="store_true",
                   help="emit the frozen PROTOCOL §6.1 tm= line per search")
    p.add_argument("--record", default=None,
                   help="append every stdin/stdout line + monotonic stamps as JSONL")
    return p.parse_args()


if __name__ == "__main__":
    sys.exit(MockEngine(parse_args()).run())
