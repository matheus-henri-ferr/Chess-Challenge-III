#!/usr/bin/env python3
# ChessChallendIII — mock none engine (plan 02-01)
# Copyright (C) 2026 ChessChallendIII
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.  See Copying.txt for the full text.

"""Minimal UCI engine that answers `position fen ...` + go with
`info depth 0 ... score mate 0 ...` then `bestmove (none)` (PROTOCOL §7.2).

Used ONLY by the transport smoke's (none) probe — a throwaway subprocess that
mirrors the verified stockfish shape without depending on the real binary
(so the smoke's fact-4 assertion is deterministic).
"""

import sys
import time


def main() -> int:
    for raw in sys.stdin:
        line = raw.rstrip("\n")
        if not line.strip():
            continue
        token = line.split()[0]
        if token == "uci":
            print("id name MockNoneEngine 1.0", flush=True)
            print("id author ChessChallendIII", flush=True)
            print("uciok", flush=True)
        elif token == "isready":
            print("readyok", flush=True)
        elif token == "go":
            print("info depth 0 seldepth 0 multipv 1 score mate 0 "
                  f"nodes 0 nps 0 hashfull 0 tbhits 0 time 0", flush=True)
            time.sleep(0.05)
            print("bestmove (none)", flush=True)
        elif token == "quit":
            return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
