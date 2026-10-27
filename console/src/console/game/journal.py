#!/usr/bin/env python3
# ChessChallendIII — append-only fsync event journal (plan 02-03)
# Copyright (C) 2026 ChessChallendIII
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.  See Copying.txt for the full text.

"""Journal — the append-only audit twin (RESEARCH Pattern 3).

Every session event lands here as one compact JSON line with os.fsync per
record (measured 0.010 ms/record at game scale — durability is free,
threat T-02-14 accepted with that evidence). Append-only is structural:
the only write mode in this module is O_APPEND, no method may modify
existing bytes, and the .log file is rendered FROM this journal (T-02-11:
a post-hoc edit has no producer to pretend to be).

replay() reconstructs (BoardState, move_rows) by pushing every
MOVE_LOGGED uci through the legal gate in order and honouring applied
RESYNC records (plies=N → the last N moves are gone) — replaying the
journal must reproduce the live state byte-for-byte on FEN and move list
(Phase 3 `resume` substrate, CLOCK-06; vocabulary frozen from today).

Event vocabulary is Phase 2's (session.py EVENTS — Phase 3 extends,
never rewrites): GAME_START, MOVE_LOGGED (src=search|opp|none|ponder,
with captured search fields), REJECT, STALE_BESTMOVE, OPP_CLOCK, RESYNC,
ENGINE_FAULT, FAULT, GAME_END. OPP_CLOCK lands here with raw token +
parsed ms (PROTO-08 journal half; the log-side representation is deferred
to Phase 3's amendment bundle — research Open Question #1 decision).
"""

import json
import os
import time

from console.game.moves import Reject

# Phase 2 event vocabulary (mirrors console.engine.session.EVENTS; kept
# identical by test_journal's round-trip + agreement assertions).
EVENTS = ("GAME_START", "MOVE_LOGGED", "REJECT", "STALE_BESTMOVE",
          "OPP_CLOCK", "RESYNC", "ENGINE_FAULT", "FAULT", "GAME_END")


def append_event(path, event):
    """One fsynced append — the entire durability mechanism.

    Stamps t_mono_ms from time.monotonic_ns() (the console-wide timing
    source), then os.open(O_WRONLY|O_CREAT|O_APPEND, 0o644) → os.write →
    os.fsync → os.close per record. No rewrite path exists.
    """
    event = dict(event)
    event["t_mono_ms"] = time.monotonic_ns() // 1_000_000
    line = json.dumps(event, separators=(",", ":")) + "\n"
    fd = os.open(os.fspath(path), os.O_WRONLY | os.O_CREAT | os.O_APPEND,
                 0o644)
    try:
        os.write(fd, line.encode("utf-8"))
        os.fsync(fd)
    finally:
        os.close(fd)


class Journal:
    """One game's JSONL journal: append(event) / iter_records() / replay()."""

    def __init__(self, path):
        self.path = os.fspath(path)

    def append(self, event):
        """Append one event (the session's sink signature: callable(dict))."""
        append_event(self.path, event)

    def iter_records(self):
        """Re-read the file as dicts, in append order."""
        records = []
        with open(self.path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    records.append(json.loads(line))
        return records

    def replay(self):
        """Reconstruct (board_state, move_rows) from the journal.

        BoardState is pushed through every MOVE_LOGGED uci in order via
        the same legal gate the live session used (an illegal replay uci
        is a journal-corruption bug and raises). An applied RESYNC drops
        its `plies` last moves — exactly what confirm_resync did live —
        so replay reproduces the live FEN and move list byte-for-byte.
        move_rows are the MOVE_LOGGED records themselves, in order.
        """
        from console.game.board import BoardState
        board = BoardState()
        move_rows = []
        for rec in self.iter_records():
            kind = rec.get("e")
            if kind == "MOVE_LOGGED":
                uci = rec.get("uci")
                move, reject = board.try_push_token(uci)
                if isinstance(reject, Reject):  # failure shape: (None, Reject)
                    raise ValueError(
                        f"journal replay: uci {uci!r} illegal at ply "
                        f"{len(board.moves)} (corrupt journal)")
                move_rows.append(rec)
            elif kind == "RESYNC" and rec.get("phase") == "applied":
                for _ in range(int(rec.get("plies", 0))):
                    board.pop()
        return board, move_rows
