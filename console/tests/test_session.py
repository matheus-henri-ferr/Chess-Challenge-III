#!/usr/bin/env python3
# ChessChallendIII — Session FSM tests: transition table, guard, FAULT, resync (plan 02-02)
# Copyright (C) 2026 ChessChallendIII
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.  See Copying.txt for the full text.

"""Session transition-table tests (RESEARCH Pattern 2, data-driven subTests),
side-to-move guard in both directions, illegal-bestmove FAULT path (mock
--illegal-bestmove), PV-never-ANNOUNCE, resync happy path + confirmation
gate, and the B1 game-start trigger (both colours, mock --record
transcript). Loop-level tests live in LoopTests (plan 02-02 Task 3).
"""

import json
import os
import pathlib
import queue
import sys
import tempfile
import time
import unittest

REPO = pathlib.Path(__file__).parent.resolve().parent.parent
MOCK = REPO / "tools" / "mock_engine.py"

sys.path.insert(0, str(REPO / "vendor"))
sys.path.insert(0, str(REPO / "console" / "src"))

import chess  # noqa: E402

from console.engine.session import Session  # noqa: E402
from console.game.board import BoardState  # noqa: E402


class FakeTransport:
    """In-memory transport double: same send/search-id/option surface."""

    def __init__(self):
        self.sent = []
        self.events = queue.Queue()
        self.search_id = 0
        self.outstanding = None
        self.discarding = False
        self._pending_options = []
        self.closed = False

    def send(self, line):
        self.sent.append(line)

    def start_search(self):
        if self.outstanding is not None:
            raise RuntimeError("start_search with a go outstanding")
        self.search_id += 1
        self.outstanding = self.search_id
        return self.search_id

    def queue_option(self, name, value):
        self._pending_options.append((name, value))

    def flush_pending_options(self):
        while self._pending_options:
            name, value = self._pending_options.pop()
            self.sent.append(f"setoption name {name} value {value}")

    def mark_discarding(self):
        self.discarding = True

    def finish_search(self, move="e7e5"):
        self.outstanding = None
        self.events.put({"type": "bestmove", "move": move,
                         "ponder": None, "search_id": self.search_id})

    # close() used by the loop's shutdown path
    def close(self):
        self.closed = True


def make_session(our="w", transport=None, board=None):
    t = transport or FakeTransport()
    sink, announces, pvs, lines = [], [], [], []
    session = Session(t, board or BoardState(), sink=sink.append,
                      our_color=our, announce_cb=announces.append,
                      pv_cb=pvs.append, display_cb=lines.append)
    return session, t, {"sink": sink, "announces": announces,
                        "pvs": pvs, "lines": lines}


def pump(session, t, until=None, timeout=3.0):
    """Feed queued transport events into the session until until() is true."""
    fed = []
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        try:
            ev = t.events.get(timeout=0.05)
        except queue.Empty:
            if until is not None and until(fed):
                break
            continue
        session.on_engine_event(ev)
        fed.append(ev.get("type"))
        if until is not None and until(fed):
            break
    return fed


class TransitionTableTests(unittest.TestCase):
    """The RESEARCH Pattern 2 table as data-driven subTests."""

    def test_table_rows(self):
        def row_idle_opp_move_to_search():
            # White already moved (e2e4 pushed) → mover is b ≠ our w.
            board = BoardState()
            board.try_push_token("e2e4")
            s, t, o = make_session(our="w", board=board)
            s.on_operator_move("e7e5")
            return s.state

        def row_idle_start_game_ours():
            s, t, o = make_session(our="w")
            s.start_game()
            return s.state

        def row_idle_start_game_opps():
            s, t, o = make_session(our="b")
            s.start_game()
            return s.state

        def row_our_search_info_stays():
            s, t, o = make_session(our="w")
            s.start_game()
            s.on_engine_event({"type": "info", "depth": 9,
                               "pv": "e2e4 e7e5", "score": "cp 12"})
            return s.state

        def row_our_search_bestmove_to_announce_pending():
            # Black replied e7e5 already (replica has e2e4 e7e5, our move) →
            # the engine's current bestmove g1f3 validates legal.
            board = BoardState()
            board.try_push_token("e2e4")
            board.try_push_token("e7e5")
            s2, t2, o2 = make_session(our="w", board=board)
            s2.state = Session.OUR_SEARCH
            t2.events.put({"type": "bestmove", "move": "g1f3", "ponder": None,
                           "search_id": t2.search_id})
            pump(s2, t2, until=lambda fed: "bestmove" in fed)
            return s2.state

        def row_announce_pending_confirm():
            board = BoardState()
            board.try_push_token("e2e4")
            board.try_push_token("e7e5")
            s, t, o = make_session(our="w", board=board)
            s.state = Session.OUR_SEARCH
            t.events.put({"type": "bestmove", "move": "g1f3", "ponder": None,
                          "search_id": t.search_id})
            pump(s, t, until=lambda fed: "bestmove" in fed)
            self.assertEqual(s.state, Session.ANNOUNCE_PENDING)
            s.on_operator_confirm()
            return s.state

        def row_opp_turn_t_command_stays():
            board = BoardState()
            board.try_push_token("e2e4")
            s, t, o = make_session(our="w", board=board)
            s.on_operator_move("e7e5")  # opp move → OUR_SEARCH
            s.state = Session.OPP_TURN  # table row: operator confirms handoff
            s.on_opp_clock("7:42", 462000)
            return s.state

        def row_reject_leaves_state():
            s, t, o = make_session(our="b")
            board = BoardState()
            board.try_push_token("e2e4")
            s.board = board
            s.state = Session.OPP_TURN
            s.on_operator_move("Nf3")  # SAN reject — state must not move
            return s.state

        def row_eof_to_idle():
            s, t, o = make_session(our="w")
            s.start_game()
            s.on_engine_event({"type": "eof"})
            return s.state

        rows = [
            ("IDLE + legal opp move", row_idle_opp_move_to_search,
             Session.OUR_SEARCH),
            ("IDLE + start_game(our move)", row_idle_start_game_ours,
             Session.OUR_SEARCH),
            ("IDLE + start_game(opp move)", row_idle_start_game_opps,
             Session.IDLE),
            ("OUR_SEARCH + info", row_our_search_info_stays,
             Session.OUR_SEARCH),
            ("OUR_SEARCH + current bestmove", row_our_search_bestmove_to_announce_pending,
             Session.ANNOUNCE_PENDING),
            ("ANNOUNCE_PENDING + confirm", row_announce_pending_confirm,
             Session.AWAIT_OPP_CONFIRM),
            ("OPP_TURN + t command", row_opp_turn_t_command_stays,
             Session.OPP_TURN),
            ("any + typed reject", row_reject_leaves_state,
             Session.OPP_TURN),
            ("OUR_SEARCH + engine EOF", row_eof_to_idle, Session.IDLE),
        ]
        for name, fn, want in rows:
            with self.subTest(row=name):
                self.assertEqual(fn(), want)


class SideToMoveGuardTests(unittest.TestCase):
    def test_guard_rejects_in_both_directions(self):
        # Direction 1: it is OUR move (mover == our colour) — an operator
        # token is a wrong-side reject naming the expected side.
        s, t, o = make_session(our="w")  # fresh startpos: white = us
        s.on_operator_move("e7e5")
        self.assertEqual(s.state, Session.IDLE)
        self.assertEqual(s.board.moves, [])
        rejects = [r for r in o["sink"] if r.get("e") == "REJECT"]
        self.assertEqual(len(rejects), 1, o["sink"])
        self.assertEqual(rejects[0]["kind"], "wrong_side")
        self.assertIn("OUR move", rejects[0]["reason"])

        # Direction 2: it is the OPP's move — after our push another
        # "opp-role" input for our side is rejected (two consecutive
        # same-side inputs are structurally impossible).
        board = BoardState()
        board.try_push_token("e2e4")  # we (white) already moved
        s2, t2, o2 = make_session(our="w", board=board)
        s2.state = Session.AWAIT_OPP_CONFIRM
        s2.on_operator_move("e7e5")  # opp's move — accepted
        self.assertEqual(s2.state, Session.OUR_SEARCH)
        t2.outstanding = None  # search answered offstage
        s2.on_operator_move("g8f6")  # now OUR turn (g1f3 territory): reject
        rejects2 = [r for r in o2["sink"] if r.get("e") == "REJECT"]
        self.assertEqual(len(rejects2), 1, o2["sink"])
        self.assertEqual(rejects2[0]["kind"], "wrong_side")

    def test_two_consecutive_opp_moves_impossible(self):
        board = BoardState()
        board.try_push_token("e2e4")
        s, t, o = make_session(our="w", board=board)
        s.on_operator_move("e7e5")  # opp #1 accepted
        s.on_operator_move("g8f6")  # opp #2: it is OUR turn → wrong-side
        self.assertEqual(s.board.moves, ["e2e4", "e7e5"])


class IllegalBestmoveFaultTests(unittest.TestCase):
    def test_illegal_bestmove_fault_never_announced(self):
        # mock_engine --illegal-bestmove answers bestmove e2e5 (illegal in
        # the replica after e2e4): FAULT sink record, ANNOUNCE never fired,
        # no board advance.
        sys.path.insert(0, str(REPO / "console" / "src"))
        from console.transport.uci import EngineTransport
        t = EngineTransport([sys.executable, str(MOCK), "--illegal-bestmove"])
        self.addCleanup(t.close)
        t.handshake()
        sink, announces, pvs, lines = [], [], [], []
        s = Session(t, BoardState(), sink=sink.append, our_color="w",
                    announce_cb=announces.append, pv_cb=pvs.append,
                    display_cb=lines.append)
        s.start_game()  # our move first: mock answers e2e5 → ILLEGAL
        pump(s, t, until=lambda fed: "bestmove" in fed
             or any(r.get("e") == "FAULT" for r in sink), timeout=5.0)
        faults = [r for r in sink if r.get("e") == "FAULT"]
        self.assertEqual(len(faults), 1, sink)
        self.assertEqual(faults[0]["uci"], "e2e5")
        self.assertEqual(announces, [], "illegal move must never be announced")
        self.assertEqual(s.board.moves, [], "illegal move must never be pushed")
        self.assertTrue(any("FAULT" in line for line in lines), lines)


class PvNeverAnnounceTests(unittest.TestCase):
    def test_info_pv_never_writes_announce(self):
        s, t, o = make_session(our="w")
        s.start_game()
        pump(s, t, until=lambda fed: "bestmove" in fed, timeout=0.5)
        # (FakeTransport emits nothing from start_game: no bestmove event.
        # The replica is untouched — mock answers arrive only in the
        # subprocess tests below.)
        self.assertEqual(s.state, Session.OUR_SEARCH)
        o["announces"].clear()
        s.on_engine_event({"type": "info", "depth": 16,
                           "pv": "e2e4 e7e5 g1f3 b8c6", "score": "cp -4",
                           "nodes": 123456, "time": 250})
        self.assertEqual(o["announces"], [],
                         "an info event wrote the ANNOUNCE buffer")
        self.assertEqual(o["pvs"], ["e2e4 e7e5 g1f3 b8c6"])
        self.assertEqual(s.last_info["depth"], 16)
        # ...and only the bestmove handler owns the field afterwards:
        # board is startpos, e2e4 is legal (our colour, white).
        t.finish_search("e2e4")
        pump(s, t, until=lambda fed: "bestmove" in fed)
        self.assertEqual(o["announces"], ["E2-E4"])
        self.assertEqual(s.board.moves, ["e2e4"])


class ResyncTests(unittest.TestCase):
    def test_resync_replay_happy_path(self):
        s, t, o = make_session(our="w")
        for uci in ("e2e4", "e7e5", "g1f3"):
            s.board.try_push_token(uci)
        good_fen = s.board.fen()
        s.board.try_push_token("b8c6")  # the "extra" move to unwind
        fen = s.request_resync(1)
        self.assertIsNotNone(fen)
        # Resync(1) re-derives e2e4 e7e5 g1f3 — the position before b8c6.
        self.assertEqual(fen.split()[0], good_fen.split()[0])
        # Unconfirmed request applied nothing (confirmation gate).
        self.assertEqual(s.board.moves[-1], "b8c6")
        self.assertTrue(s.confirm_resync(1))
        self.assertEqual(s.board.fen(), good_fen)
        self.assertEqual(s.board.moves, ["e2e4", "e7e5", "g1f3"])
        resyncs = [r for r in o["sink"] if r.get("e") == "RESYNC"]
        self.assertEqual([r["phase"] for r in resyncs],
                         ["requested", "applied"], o["sink"])

    def test_resync_confirmation_gate_blocks_unconfirmed(self):
        s, t, o = make_session(our="w")
        s.board.try_push_token("e2e4")
        before = s.board.fen()
        s.request_resync(1)
        self.assertEqual(s.board.fen(), before,
                         "an unconfirmed resync must apply nothing")
        # Wrong ply count at confirm: nothing applied either.
        self.assertFalse(s.confirm_resync(2))
        self.assertEqual(s.board.fen(), before)
        self.assertTrue(s.confirm_resync(1))

    def test_resync_rejects_out_of_range(self):
        s, t, o = make_session(our="w")
        self.assertIsNone(s.request_resync(3))
        self.assertIsNone(s.request_resync(-1))


class GameStartTriggerTests(unittest.TestCase):
    """B1 fix: our colour first → search #1 auto-fires; opp first → quiet."""

    def _run_colour(self, our):
        path = tempfile.mktemp(prefix=f"game-start-{our}-", suffix=".jsonl")
        self.addCleanup(lambda: os.path.exists(path) and os.unlink(path))
        sys.path.insert(0, str(REPO / "console" / "src"))
        from console.transport.uci import EngineTransport
        argv = [sys.executable, str(MOCK), "--record", path]
        t = EngineTransport(argv)
        self.addCleanup(t.close)
        t.handshake()
        sink, announces = [], []
        s = Session(t, BoardState(), sink=sink.append, our_color=our,
                    announce_cb=announces.append)
        s.clock_passthrough_ms = (600000, 600000)
        s.start_game()
        if our == "w":
            pump(s, t, until=lambda fed: "bestmove" in fed, timeout=5.0)
        else:
            time.sleep(0.3)  # nothing should arrive
        t.send("quit")
        with open(path, encoding="utf-8") as fh:
            recs = [json.loads(line) for line in fh if line.strip()]
        ins = [r["line"] for r in recs if r["dir"] == "in"]
        return ins, s, announces

    def test_our_colour_first_fires_search_one(self):
        ins, session, announces = self._run_colour("w")
        self.assertIn("position startpos", ins)
        self.assertIn("go wtime 600000 btime 600000 winc 10000 binc 10000",
                      ins, ins)
        self.assertEqual(session.state, Session.ANNOUNCE_PENDING)
        self.assertEqual(announces, ["E2-E4"],
                         "mock answers ply 0 with e2e4 — announced")
        self.assertEqual(session.board.moves, ["e2e4"])

    def test_opp_colour_first_sends_nothing(self):
        ins, session, announces = self._run_colour("b")
        self.assertNotIn("position startpos", ins, ins)
        self.assertFalse([line for line in ins if line.startswith("go ")],
                         ins)
        self.assertEqual(session.state, Session.IDLE)
        self.assertEqual(announces, [])


class OptionFlushTests(unittest.TestCase):
    def test_startup_set_queues_and_flushes_at_idle(self):
        s, t, o = make_session(our="w")
        s.apply_startup_options()
        sent = t.sent
        self.assertIn("setoption name SyzygyProbeLimit value 5", sent)
        self.assertIn("setoption name Move Overhead value 100", sent)
        self.assertIn("setoption name Ponder value False", sent)
        self.assertIn("setoption name Threads value 1", sent)
        self.assertIn("setoption name Hash value 2048", sent)
        self.assertEqual(t._pending_options, [], "flush must drain the queue")

    def test_setoption_reachable_from_any_state_queue_only(self):
        s, t, o = make_session(our="w")
        s.start_game()  # OUR_SEARCH
        s.setoption("Hash", "4096")
        self.assertEqual(t._pending_options, [("Hash", "4096")],
                         "queueing must not send mid-search")


if __name__ == "__main__":
    unittest.main()
