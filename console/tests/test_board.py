#!/usr/bin/env python3
# ChessChallendIII — board replica tests: replay, side capture, position line (plan 02-02)
# Copyright (C) 2026 ChessChallendIII
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.  See Copying.txt for the full text.

"""BoardState tests: replay agreement with an independent chess.Board,
move_no/side capture vs mock_gui's independent formula
((len(moves)+2)//2, parity — tools/mock_gui.py:194-202), position_line
round-trip through mock_engine's --record transcript, terminal detection
on a mate FEN, and the expected_mover guard substrate.
"""

import json
import os
import pathlib
import queue
import subprocess
import sys
import tempfile
import time
import unittest

REPO = pathlib.Path(__file__).parent.resolve().parent.parent
MOCK = REPO / "tools" / "mock_engine.py"

sys.path.insert(0, str(REPO / "vendor"))
sys.path.insert(0, str(REPO / "console" / "src"))

import chess  # noqa: E402

from console.game.board import BoardState  # noqa: E402
from console.game.moves import RejectKind  # noqa: E402

REPLAY = ["e2e4", "e7e5", "g1f3", "b8c6", "f1b5", "a7a6"]


class ReplayAgreementTests(unittest.TestCase):
    def test_fen_agrees_with_independent_board_after_n_pushes(self):
        for n in range(0, len(REPLAY) + 1):
            with self.subTest(n=n):
                state = BoardState()
                reference = chess.Board()
                for uci in REPLAY[:n]:
                    state.push_validated(chess.Move.from_uci(uci))
                    reference.push_uci(uci)
                self.assertEqual(state.fen(), reference.fen())
                self.assertEqual(state.moves, REPLAY[:n])

    def test_try_push_token_matches_operator_move_directly(self):
        state = BoardState()
        move, meta = state.try_push_token("  E2 E4 ")
        self.assertEqual(move.uci(), "e2e4")
        self.assertEqual(meta, {"move_no": 1, "side": "w", "uci": "e2e4"})
        # A black reply and a wrong-side attempt through the same gate.
        move, meta = state.try_push_token("e7e5")
        self.assertEqual(meta["side"], "b")
        move, reject = state.try_push_token("e4e5")
        self.assertIsNone(move)
        self.assertEqual(reject.kind, RejectKind.ILLEGAL)


class SideCaptureTests(unittest.TestCase):
    def test_move_no_and_side_match_mock_gui_formula(self):
        state = BoardState()
        metas = []
        for uci in REPLAY:
            metas.append(state.try_push_token(uci)[1])
        for i, meta in enumerate(metas):
            before_count = i  # moves already on the board when this was pushed
            with self.subTest(i=i, uci=meta["uci"]):
                # mock_gui's independent formula (len(moves)+2)//2 evaluated
                # BEFORE the push, and parity for the side.
                self.assertEqual(meta["move_no"], (before_count + 2) // 2)
                self.assertEqual(meta["side"],
                                 "w" if before_count % 2 == 0 else "b")
        # After white's e2e4 the fullmove number is still 1 (verified live).
        self.assertEqual(metas[0]["move_no"], 1)
        self.assertEqual(metas[1]["move_no"], 1)
        self.assertEqual(metas[2]["move_no"], 2)


class PositionLineTests(unittest.TestCase):
    def test_empty_state_is_bare_startpos(self):
        self.assertEqual(BoardState().position_line(), "position startpos")

    def test_line_carries_full_validated_list(self):
        state = BoardState()
        for uci in REPLAY:
            state.try_push_token(uci)
        self.assertEqual(state.position_line(),
                         "position startpos moves " + " ".join(REPLAY))

    def test_position_line_round_trips_through_mock_engine(self):
        # The engine must accept the line (never rc=1 — Pitfall 3) and the
        # mock's derived best_move ply must match the replayed list length.
        path = tempfile.mktemp(prefix="pos-line-", suffix=".jsonl")
        self.addCleanup(lambda: os.path.exists(path) and os.unlink(path))
        argv = [sys.executable, str(MOCK), "--record", path]
        env = {**os.environ}
        proc = subprocess.Popen(argv, stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE, bufsize=0,
                                cwd=str(REPO), env=env)
        self.addCleanup(proc.kill)
        self.addCleanup(proc.stdin.close)
        self.addCleanup(proc.stdout.close)

        def send(line):
            proc.stdin.write((line + "\n").encode())
            proc.stdin.flush()

        send("uci")
        send("isready")
        state = BoardState()
        for uci in REPLAY:
            state.try_push_token(uci)
        send(state.position_line())
        sid_ply = len(state.moves)
        # mock's best_move() indexes by ply: ply 6 → a7a6 in the opening list.
        expected = ["e2e4", "e7e5", "g1f3", "b8c6", "f1b5", "a7a6",
                    "b5a4", "g8f6"][sid_ply % 8]
        send("go wtime 600000 btime 600000 winc 10000 binc 10000")
        deadline = time.monotonic() + 15.0
        answered = None
        while time.monotonic() < deadline and answered is None:
            line = proc.stdout.readline().decode(errors="replace").strip()
            if line.startswith("bestmove "):
                answered = line.split()[1]
        self.assertEqual(answered, expected)
        self.assertIsNone(proc.poll(), "engine must survive the position line")
        with open(path, encoding="utf-8") as fh:
            recs = [json.loads(line) for line in fh if line.strip()]
        ins = [r["line"] for r in recs if r["dir"] == "in"]
        self.assertIn(state.position_line(), ins)


class TerminalDetectionTests(unittest.TestCase):
    def test_mate_fen_reports_outcome(self):
        state = BoardState()
        state.board = chess.Board("6k1/5ppp/8/8/8/8/8/4R2K w - - 0 1")
        state.try_push_token("e1e8")  # Re8# — the mate fixture
        outcome = state.outcome()
        self.assertIsNotNone(outcome)
        self.assertEqual(outcome.termination, chess.Termination.CHECKMATE)
        self.assertEqual(outcome.winner, chess.WHITE)

    def test_startpos_has_no_outcome(self):
        self.assertIsNone(BoardState().outcome())


class ExpectedMoverTests(unittest.TestCase):
    def test_guard_substrate_alternates(self):
        state = BoardState()
        self.assertEqual(state.expected_mover(), "w")
        state.try_push_token("e2e4")
        self.assertEqual(state.expected_mover(), "b")
        state.try_push_token("e7e5")
        self.assertEqual(state.expected_mover(), "w")

    def test_pop_realigns_without_restart(self):
        state = BoardState()
        state.try_push_token("e2e4")
        state.try_push_token("e7e5")
        self.assertEqual(state.pop(), "e7e5")
        self.assertEqual(state.expected_mover(), "b")
        reference = chess.Board()
        reference.push_uci("e2e4")
        self.assertEqual(state.fen(), reference.fen())


if __name__ == "__main__":
    unittest.main()
