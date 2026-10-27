#!/usr/bin/env python3
# ChessChallendIII — board replica: legality gate + position lines (plan 02-02)
# Copyright (C) 2026 ChessChallendIII
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.  See Copying.txt for the full text.

"""BoardState — the validated replica (PROTOCOL §1.6, §4.1).

The replica is the authority: `board.turn` guards the side-to-move check,
the validated move list is the ONLY producer of `position startpos moves …`
lines (an illegal entry there exits the engine rc=1 — Pitfall 3, T-02-07),
and side metadata (move_no/side) is captured BEFORE the push (Pitfall 6,
off-by-one guard; cross-checked in tests against mock_gui's independent
formula (len(moves)+2)//2).
"""

import chess

from console.game.moves import Reject, normalize_token, operator_move


class BoardState:
    """startpos board + ordered uci move list + validated send path."""

    def __init__(self):
        self.board = chess.Board()
        self.moves = []  # ordered uci strings — the replayable truth (§4.1)

    # --- validated mutation ----------------------------------------------
    def push_validated(self, move):
        """Push a legal move, capturing move_no/side BEFORE the push."""
        move_no = self.board.fullmove_number
        side = "w" if self.board.turn == chess.WHITE else "b"
        self.board.push(move)
        self.moves.append(move.uci())
        return {"move_no": move_no, "side": side, "uci": move.uci()}

    def try_push_token(self, raw):
        """Normalize + 0000 + parse_uci + push. Returns (move, None) on
        success or (None, Reject) — the typed-reject gate, never raising."""
        try:
            move = operator_move(self.board, raw)
        except Reject as reject:
            return None, reject
        meta = self.push_validated(move)
        return move, meta

    # --- sends (the only producer, §4.1) ------------------------------------
    def position_line(self):
        """`position startpos moves …` — or bare `position startpos`."""
        if not self.moves:
            return "position startpos"
        return "position startpos moves " + " ".join(self.moves)

    # --- guards and display -------------------------------------------------
    def expected_mover(self):
        """The colour that must move now (the side-to-move guard reads this)."""
        return "w" if self.board.turn == chess.WHITE else "b"

    def fen(self):
        return self.board.fen()

    def outcome(self, claim_draw=False):
        """Terminal state (detect + display; never self-adjudicating)."""
        return self.board.outcome(claim_draw=claim_draw)

    # --- realignment (the board is the source of truth, Rule 10) -----------
    def pop(self):
        """Undo the last ply; returns the removed uci token (or None)."""
        if not self.moves:
            return None
        self.board.pop()
        return self.moves.pop()
