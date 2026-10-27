#!/usr/bin/env python3
# ChessChallendIII — typed-reject matrix tests: the six verified tokens (plan 02-02)
# Copyright (C) 2026 ChessChallendIII
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.  See Copying.txt for the full text.

"""PROTO-01 typed-reject matrix (RESEARCH §Parsing, live-probed tokens).

Covers all six verified tokens (`0000`, `E2E4`, `Nf3`, `O-O`, `e2-e4`,
`e2e5`) plus space tolerance, promotion ambiguity (four suffixes surfaced),
and castling spelling on a castling-ready position (`e1g1` is ILLEGAL at
bare startpos — the accept case needs the right FEN).
"""

import pathlib
import sys
import unittest

REPO = pathlib.Path(__file__).parent.resolve().parent.parent
sys.path.insert(0, str(REPO / "vendor"))
sys.path.insert(0, str(REPO / "console" / "src"))

import chess  # noqa: E402

from console.game.board import BoardState  # noqa: E402
from console.game.moves import (  # noqa: E402
    Reject,
    RejectKind,
    announce_form,
    normalize_token,
    operator_move,
)

# Castling-ready: both kings and rooks on origin squares, rights intact.
CASTLE_FEN = "r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1"
# Promotion: a7 pawn, every suffix legal.
PROMO_FEN = "8/P7/8/8/8/8/7k/K7 w - - 0 1"


class NormalizeTests(unittest.TestCase):
    def test_case_and_space_tolerance(self):
        for raw, want in ((" e2 e4 ", "e2e4"), ("E2E4", "e2e4"),
                          ("G1F3", "g1f3"), ("\te7e5\n", "e7e5"),
                          ("  A7   A8Q ", "a7a8q")):
            with self.subTest(raw=raw):
                self.assertEqual(normalize_token(raw), want)


class AcceptMatrixTests(unittest.TestCase):
    def test_accepts_legal_tokens(self):
        cases = [("e2e4", "e2e4", ""), ("G1F3", "g1f3", ""),
                 (" e2 e4 ", "e2e4", ""), ("A7A8Q", "a7a8q", PROMO_FEN)]
        for raw, want, fen in cases:
            with self.subTest(raw=raw):
                board = chess.Board(fen) if fen else chess.Board()
                move = operator_move(board, raw)
                self.assertEqual(move.uci(), want)

    def test_accepts_e1g1_on_castling_ready_position(self):
        # e1g1 is ILLEGAL at bare startpos (verified live) — the accept case
        # needs a position where the castle is actually legal.
        board = chess.Board(CASTLE_FEN)
        move = operator_move(board, "e1g1")
        self.assertEqual(move.uci(), "e1g1")
        self.assertTrue(board.is_castling(move))


class RejectMatrixTests(unittest.TestCase):
    def test_the_six_verified_tokens(self):
        board = chess.Board()
        cases = [
            ("0000", RejectKind.NULL),
            ("Nf3", RejectKind.MALFORMED),   # SAN-shaped
            ("e4", RejectKind.MALFORMED),    # SAN pawn push
            ("O-O", RejectKind.MALFORMED),   # SAN castle
            ("e2-e4", RejectKind.MALFORMED), # hyphen is output-only
            ("xyz", RejectKind.MALFORMED),
            ("e2e5", RejectKind.ILLEGAL),    # legal syntax, illegal here
        ]
        for raw, kind in cases:
            with self.subTest(raw=raw):
                with self.assertRaises(Reject) as ctx:
                    operator_move(board, raw)
                self.assertEqual(ctx.exception.kind, kind)
                self.assertEqual(ctx.exception.raw, raw)
                self.assertTrue(ctx.exception.reason)

    def test_reject_carries_raw_not_normalized(self):
        board = chess.Board()
        with self.assertRaises(Reject) as ctx:
            operator_move(board, "  E2 - E4  ")
        self.assertEqual(ctx.exception.raw, "  E2 - E4  ")

    def test_reject_never_pushes_the_replica(self):
        state = BoardState()
        for raw in ("0000", "Nf3", "e2e5", "xyz", ""):
            with self.subTest(raw=raw):
                move, reject = state.try_push_token(raw)
                self.assertIsNone(move)
                self.assertIsInstance(reject, Reject)
                self.assertEqual(state.moves, [])


class PromotionAmbiguityTests(unittest.TestCase):
    def test_missing_suffix_reprompts_with_four_legal_suffixes(self):
        board = chess.Board(PROMO_FEN)
        with self.assertRaises(Reject) as ctx:
            operator_move(board, "a7a8")
        self.assertEqual(ctx.exception.kind, RejectKind.MALFORMED)
        for suffix in ("a7a8q", "a7a8r", "a7a8b", "a7a8n"):
            self.assertIn(suffix, ctx.exception.reason)
        # Every surfaced suffix then parses legal.
        for suffix in ("q", "r", "b", "n"):
            move = operator_move(board, f"a7a8{suffix}")
            self.assertEqual(
                move.promotion, chess.PIECE_SYMBOLS.index(suffix))


class AnnounceFormTests(unittest.TestCase):
    def test_uppercase_hyphenated(self):
        for uci, want in (("e2e4", "E2-E4"), ("e7e8q", "E7-E8=Q"),
                          ("e1g1", "E1-G1"), ("b8c6", "B8-C6")):
            with self.subTest(uci=uci):
                self.assertEqual(announce_form(uci), want)


if __name__ == "__main__":
    unittest.main()
