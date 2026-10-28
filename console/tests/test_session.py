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
import io

REPO = pathlib.Path(__file__).parent.resolve().parent.parent
MOCK = REPO / "tools" / "mock_engine.py"

sys.path.insert(0, str(REPO / "vendor"))
sys.path.insert(0, str(REPO / "console" / "src"))

import chess  # noqa: E402

from console.engine.session import Session  # noqa: E402
from console.game.board import BoardState  # noqa: E402
from console.ui.loop import OperatorLoop  # noqa: E402


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


class LoopTests(unittest.TestCase):
    """OperatorLoop: scripted stdin end-to-end + queue-drain liveness."""

    def _make_io(self):
        import io
        stdin = io.StringIO()
        stdout = io.StringIO()

        class _Stdin:
            def fileno(self):
                return 0  # real fd 0; the scripted text is pre-loaded

        return stdin, stdout

    def test_scripted_stdin_move_garbage_clock(self):
        # Scripted session: opp move e7e5 accepted (FEN echo), a malformed
        # token typed-rejected while the opp is still to move, `t 7:42`
        # journals OPP_CLOCK.
        import io
        board = BoardState()
        board.try_push_token("e2e4")  # we already moved: opp (black) to move
        s, t, o = make_session(our="w", board=board)
        text = "e7e5\nNf3\nt 7:42\nq\n"
        loop = OperatorLoop(s, t, stdin=io.StringIO(text),
                            stdout=io.StringIO())
        # Drive handle_line directly with the scripted lines (the StringIO
        # has no real fd; the fd path is covered by the piped smoke). The
        # search the accepted move triggers is answered offstage, then the
        # replica is rewound one ply so the malformed token arrives in a
        # wait-for-opp context (rejection must be shape-typed, not
        # wrong-side-typed).
        loop.handle_line("e7e5")
        self.assertIn("E7-E5  FEN:", loop.stdout.getvalue())
        t.outstanding = None  # search answered offstage
        s.board.pop()         # still the opp's move to enter
        loop.handle_line("Nf3")
        loop.handle_line("t 7:42")
        loop.handle_line("q")
        out = loop.stdout.getvalue() + "\n".join(o["lines"])
        self.assertIn("E7-E5  FEN:", out)          # instant accepted echo
        self.assertIn("REJECTED malformed:", out)  # SAN-shaped typed reject
        self.assertIn("opp clock: 7:42 = 462000 ms", out)
        opp = [r for r in o["sink"] if r.get("e") == "OPP_CLOCK"]
        self.assertEqual(len(opp), 1, o["sink"])
        self.assertEqual(opp[0]["raw"], "7:42")
        self.assertEqual(opp[0]["parsed_ms"], 462000)
        self.assertEqual(s.board.moves, ["e2e4"])

    def test_select_loop_drains_events_while_stdin_idle(self):
        # Liveness: with NO stdin input, queued engine events still reach
        # the session — ANNOUNCE appears while the operator sits at prompt.
        import io
        s, t, o = make_session(our="w")
        t.finish_search("e2e4")  # an engine answer already queued
        loop = OperatorLoop(s, t, stdin=io.StringIO(),
                            stdout=io.StringIO())
        loop.drain_events()  # the tick's queue-drain half
        self.assertEqual(o["announces"], ["E2-E4"])
        self.assertEqual(s.state, Session.ANNOUNCE_PENDING)

    def test_length_bound_and_empty_input(self):
        import io
        s, t, o = make_session(our="w")
        loop = OperatorLoop(s, t, stdin=io.StringIO(),
                            stdout=io.StringIO())
        loop.handle_line("x" * 40)
        loop.handle_line("")
        out = loop.stdout.getvalue()
        self.assertIn("REJECTED malformed: input longer than 32", out)
        self.assertIn("empty input", out)

    def test_resync_command_and_confirmation(self):
        import io
        board = BoardState()
        for uci in ("e2e4", "e7e5", "g1f3", "b8c6"):
            board.try_push_token(uci)
        s, t, o = make_session(our="w", board=board)
        loop = OperatorLoop(s, t, stdin=io.StringIO(),
                            stdout=io.StringIO())
        loop.handle_line("r 1")
        self.assertIn("resync armed (1 plies)", loop.stdout.getvalue())
        self.assertIn("confirm with: y", loop.stdout.getvalue())
        # Unconfirmed: board untouched.
        self.assertEqual(s.board.moves[-1], "b8c6")
        loop.handle_line("y")
        self.assertEqual(s.board.moves, ["e2e4", "e7e5", "g1f3"])
        self.assertEqual(loop.stdout.getvalue().count("resynced to"), 1)

    def test_undo_command(self):
        import io
        board = BoardState()
        board.try_push_token("e2e4")
        s, t, o = make_session(our="w", board=board)
        loop = OperatorLoop(s, t, stdin=io.StringIO(),
                            stdout=io.StringIO())
        loop.handle_line("u")
        out = loop.stdout.getvalue()
        self.assertIn("undone: e2e4", out)
        self.assertEqual(s.board.moves, [])

    def test_piped_multiline_stdin_reaches_handle_line(self):
        # Regression (02-04 piped smoke): a typed-ahead script arrives in
        # ONE os.read; lines past the first must be buffered and consumed
        # line-by-line, never discarded — the smoke feeds 'e7e5\nu\n…\nq'
        # and every line must reach handle_line.
        import io
        s, t, o = make_session(our="w")
        loop = OperatorLoop(s, t, stdin=io.StringIO(),
                            stdout=io.StringIO())
        loop._stdin_buf = b"e7e5\nu\nq\n"
        loop.stdin_fd = None  # no real fd: buffered lines only, then EOF
        first = loop._read_line()
        second = loop._read_line()
        third = loop._read_line()
        fourth = loop._read_line()
        self.assertEqual((first, second, third, fourth),
                         ("e7e5", "u", "q", None),
                         "buffered lines must be consumed in order, "
                         "then EOF")

    def test_parse_clock_token_forms(self):
        from console.ui.loop import parse_clock_token
        self.assertEqual(parse_clock_token("7:42"), 462000)
        self.assertEqual(parse_clock_token("1:07:30"), 4050000)
        self.assertEqual(parse_clock_token("2.30"), 150000)
        self.assertEqual(parse_clock_token("90"), 90000)
        self.assertIsNone(parse_clock_token("abc"))
        self.assertIsNone(parse_clock_token("7:"))


class UndoRealignmentTests(unittest.TestCase):
    """CR-01 closure: `u` through the session, with §1.3 transport repair.

    (a) undo during OUR_SEARCH — the reproduced crash sequence: opp move
    accepted → go outstanding → undo → corrected opp move must end in
    OUR_SEARCH with zero exceptions (T-02-20).
    (b) undo with no go outstanding re-fires the search (our move undone).
    (c) undo with nothing on the board returns None.
    (d) loop routing: `u` calls session.undo_last_ply exactly once.
    """

    def test_a_undo_during_our_search_repair_and_reentry(self):
        board = BoardState()
        board.try_push_token("e2e4")  # our w move already on the replica
        s, t, o = make_session(our="w", board=board)
        s.on_operator_move("e7e5")  # opp move → OUR_SEARCH, go outstanding
        self.assertEqual(s.state, Session.OUR_SEARCH)
        self.assertIsNotNone(t.outstanding)
        # The real transport's reader thread delivers exactly this after a
        # `stop`: the interrupted search's owed bestmove.
        t.events.put({"type": "bestmove", "move": "g1f3", "ponder": None,
                      "search_id": t.search_id})
        removed = s.undo_last_ply()
        self.assertEqual(removed, "e7e5")
        self.assertIn("stop", t.sent, "§1.5: stop first")
        # L-1 fold (02-06): after the repair consumed the owed bestmove,
        # the discard purpose is fulfilled — both mirrors clear (the real
        # transport's _dispatch_bestmove clears the flag on the consumed
        # stale answer; the repair's finally is the belt-and-braces).
        self.assertFalse(t.discarding, "discard flag clear post-repair")
        self.assertFalse(s.discarding, "session flag cleared after repair")
        # The owed answer was consumed and sunk as stale — no board advance.
        stale = [r for r in o["sink"] if r.get("e") == "STALE_BESTMOVE"]
        self.assertEqual(len(stale), 1, o["sink"])
        self.assertEqual(s.board.moves, ["e2e4"])
        # RESYNC record: replay() pops exactly 1 ply for this shape.
        resyncs = [r for r in o["sink"] if r.get("e") == "RESYNC"]
        self.assertEqual(len(resyncs), 1, o["sink"])
        self.assertEqual(resyncs[0]["phase"], "applied")
        self.assertEqual(resyncs[0]["plies"], 1)
        self.assertEqual(resyncs[0]["via"], "undo")
        self.assertIn("fen", resyncs[0])
        self.assertIsNone(s.last_announced)
        self.assertIsNone(s.pending_resync)
        # expected_mover is now the opponent → AWAIT_OPP_CONFIRM.
        self.assertEqual(s.state, Session.AWAIT_OPP_CONFIRM)
        # The CR-01 repro: corrected opp move re-enters without raising.
        t.outstanding = None  # transport reader-side effect of the stop
        move = s.on_operator_move("e7e6")
        self.assertIsNotNone(move)
        self.assertEqual(s.state, Session.OUR_SEARCH)
        self.assertEqual(s.board.moves, ["e2e4", "e7e6"])

    def test_a_undo_no_answer_to_stop_prompt_survives(self):
        # The engine never answers the stop within the budget: the undo
        # must still complete (queue.Empty path) — prompt survives.
        board = BoardState()
        board.try_push_token("e2e4")
        s, t, o = make_session(our="w", board=board)
        s.on_operator_move("e7e5")
        s.wait_for_bestmove_timeout = 0.05  # shrink the budget for the test
        removed = s.undo_last_ply()
        self.assertEqual(removed, "e7e5")
        self.assertIn("stop", t.sent)
        faults = [r for r in o["sink"] if r.get("e") == "ENGINE_FAULT"]
        self.assertEqual(len(faults), 1, o["sink"])
        self.assertIn("no bestmove to the stop", faults[0]["reason"])
        self.assertEqual(s.state, Session.AWAIT_OPP_CONFIRM)
        # L-1 + outstanding clearance (plan 02-06 Task 1d): the timeout
        # path must leave BOTH transport mirrors clear so the corrected
        # re-entry cannot die on start_search's §1.3 guard.
        self.assertFalse(t.discarding,
                         "transport discarding cleared, not only the mirror")
        self.assertIsNone(t.outstanding,
                          "timeout path clears the outstanding go")
        # The CR-01 corrected re-entry (the same idiom as test_a above).
        move = s.on_operator_move("e7e6")
        self.assertIsNotNone(move)
        self.assertEqual(s.state, Session.OUR_SEARCH)
        self.assertEqual(s.board.moves, ["e2e4", "e7e6"])

    def test_b_undo_without_outstanding_go_refires_search(self):
        board = BoardState()
        board.try_push_token("e2e4")
        board.try_push_token("e7e5")
        s, t, o = make_session(our="w", board=board)
        s.state = Session.OUR_SEARCH
        t.events.put({"type": "bestmove", "move": "g1f3", "ponder": None,
                      "search_id": t.search_id})
        pump(s, t, until=lambda fed: "bestmove" in fed)
        self.assertEqual(s.state, Session.ANNOUNCE_PENDING)
        self.assertIsNone(t.outstanding)
        removed = s.undo_last_ply()  # pops our g1f3
        self.assertEqual(removed, "g1f3")
        self.assertNotIn("stop", t.sent, "no go outstanding: no stop sent")
        self.assertEqual(s.state, Session.OUR_SEARCH,
                         "our move undone → the engine re-thinks")
        self.assertIsNotNone(t.outstanding)

    def test_c_undo_empty_board_returns_none(self):
        s, t, o = make_session(our="w")
        self.assertIsNone(s.undo_last_ply())
        self.assertNotIn("stop", t.sent)
        self.assertEqual(
            [r for r in o["sink"] if r.get("e") == "RESYNC"], [])

    def test_d_loop_routes_u_through_session(self):
        board = BoardState()
        board.try_push_token("e2e4")
        calls = []

        class StubSession:
            def __init__(self):
                self.board = board
                self.pending_resync = None

            def undo_last_ply(self):
                calls.append(1)
                return board.moves.pop() if board.moves else None

        loop = OperatorLoop(StubSession(), FakeTransport(),
                            stdin=io.StringIO(), stdout=io.StringIO())
        loop.handle_line("u")
        self.assertEqual(len(calls), 1, "undo_last_ply called exactly once")
        self.assertIn("undone: e2e4", loop.stdout.getvalue())
        board.try_push_token("e2e4")
        loop.handle_line("u")
        loop.handle_line("u")
        self.assertEqual(len(calls), 3)
        self.assertIn("nothing to undo", loop.stdout.getvalue())


class UndoPromptSurvivalTests(unittest.TestCase):
    """H-1 closure (plan 02-06): every engine-death shape during an
    operator undo completes the realignment — zero escaping exceptions,
    an ENGINE_FAULT record per failure mode, and the RESYNC(applied,
    plies=1, via=undo) record journaled on every post-pop path."""

    def test_stop_send_raises_engine_dead_prompt_survives(self):
        # Death shape (a): the engine already exited when the operator
        # types `u` — the real transport's send raises RuntimeError
        # ("engine exited rc=-9", uci.py:192-193) instead of queueing.
        board = BoardState()
        board.try_push_token("e2e4")  # our w move on the replica
        s, t, o = make_session(our="w", board=board)
        s.on_operator_move("e7e5")  # opp move → OUR_SEARCH, go outstanding
        self.assertEqual(s.state, Session.OUR_SEARCH)
        self.assertIsNotNone(t.outstanding)

        class DyingEngineTransport(FakeTransport):
            """Models the dead-poll send at uci.py:192-193."""

            def __init__(self, base):
                self.__dict__.update(base.__dict__)

            def send(self, line):
                if self.dead:
                    raise RuntimeError("engine exited rc=-9")
                self.sent.append(line)

        t.dead = False
        dying = DyingEngineTransport(t)
        s.transport = dying
        dying.dead = True
        removed = s.undo_last_ply()  # must NOT raise
        self.assertEqual(removed, "e7e5")
        faults = [r for r in o["sink"] if r.get("e") == "ENGINE_FAULT"]
        self.assertEqual(len(faults), 1, o["sink"])
        self.assertIn("stop send failed", faults[0]["reason"])
        self.assertIsNone(dying.outstanding,
                          "dead-stop path must clear the outstanding go")
        resyncs = [r for r in o["sink"] if r.get("e") == "RESYNC"]
        self.assertEqual(len(resyncs), 1, o["sink"])
        self.assertEqual(resyncs[0]["phase"], "applied")
        self.assertEqual(resyncs[0]["plies"], 1)
        self.assertEqual(resyncs[0]["via"], "undo")
        self.assertEqual(s.board.moves, ["e2e4"])
        self.assertEqual(s.state, Session.AWAIT_OPP_CONFIRM)
        self.assertIsNone(s.last_announced)
        # The realignment leaves the session usable: engine healthy again.
        dying.dead = False
        move = s.on_operator_move("e7e6")
        self.assertIsNotNone(move)
        self.assertEqual(s.state, Session.OUR_SEARCH)
        self.assertEqual(s.board.moves, ["e2e4", "e7e6"])

    def test_eof_before_owed_bestmove_journaled_and_survives(self):
        # Death shape (b): the engine dies between the stop and the owed
        # bestmove — the reader queues {"type": "eof"} and
        # _consume_owed_bestmove raises RuntimeError (session.py:466).
        board = BoardState()
        board.try_push_token("e2e4")
        s, t, o = make_session(our="w", board=board)
        s.on_operator_move("e7e5")
        self.assertEqual(s.state, Session.OUR_SEARCH)
        t.events.put({"type": "eof"})  # BEFORE the undo, as the reader does
        removed = s.undo_last_ply()  # must NOT raise
        self.assertEqual(removed, "e7e5")
        faults = [r for r in o["sink"] if r.get("e") == "ENGINE_FAULT"]
        self.assertEqual(len(faults), 2, o["sink"])  # eof evidence + abort
        self.assertIn("EOF before the owed", faults[0]["reason"])
        self.assertIn("consumed event", faults[0]["reason"])
        self.assertIn("undo repair aborted", faults[1]["reason"])
        self.assertIsNone(t.outstanding)
        resyncs = [r for r in o["sink"] if r.get("e") == "RESYNC"]
        self.assertEqual(len(resyncs), 1, o["sink"])
        self.assertEqual(resyncs[0]["via"], "undo")
        moves = [r for r in o["sink"] if r.get("e") == "MOVE_LOGGED"]
        self.assertEqual([r["uci"] for r in moves], ["e7e5"],
                         "only the operator's e7e5 row — no phantom advance "
                         "after the pop (the e7e5 row predates the undo)")
        self.assertFalse(t.discarding)
        self.assertFalse(s.discarding)
        self.assertEqual(s.state, Session.AWAIT_OPP_CONFIRM)

    def test_refire_send_raises_lands_idle_with_resync(self):
        # Death shape (c): no stop path exercised (search already answered
        # → ANNOUNCE_PENDING, outstanding None); the death hits the
        # re-fire _start_search after the pop.
        board = BoardState()
        board.try_push_token("e2e4")
        board.try_push_token("e7e5")
        s, t, o = make_session(our="w", board=board)
        s.state = Session.OUR_SEARCH
        t.events.put({"type": "bestmove", "move": "g1f3", "ponder": None,
                      "search_id": t.search_id})
        pump(s, t, until=lambda fed: "bestmove" in fed)
        self.assertEqual(s.state, Session.ANNOUNCE_PENDING)
        self.assertIsNone(t.outstanding)

        class DyingRefireTransport(FakeTransport):
            def __init__(self, base):
                self.__dict__.update(base.__dict__)

            def send(self, line):
                if getattr(self, "dead", False) and line != "stop":
                    raise RuntimeError("engine exited rc=-9")
                self.sent.append(line)

        t.dead = True
        dying = DyingRefireTransport(t)
        s.transport = dying
        removed = s.undo_last_ply()  # must NOT raise (today it propagates)
        self.assertEqual(removed, "g1f3",
                         "the pushed our-move g1f3 is what the pop removes")
        faults = [r for r in o["sink"] if r.get("e") == "ENGINE_FAULT"]
        self.assertEqual(len(faults), 1, o["sink"])
        self.assertIn("re-fire", faults[0]["reason"])
        resyncs = [r for r in o["sink"] if r.get("e") == "RESYNC"]
        self.assertEqual(len(resyncs), 1, o["sink"])
        self.assertEqual(resyncs[0]["phase"], "applied")
        self.assertEqual(resyncs[0]["plies"], 1)
        self.assertEqual(s.state, Session.IDLE, "the _on_fault precedent")
        self.assertIsNone(dying.outstanding)


class LoopUndoSurvivalTests(unittest.TestCase):
    """H-1 last-resort layer (plan 02-06 Task 2): a residual exception
    escaping the hardened session's undo still never kills the prompt —
    the loop journals ENGINE_FAULT with a traceback and keeps accepting
    input (the CR-10 drain_events discipline, applied to the `u` branch)."""

    def test_loop_u_survives_session_crash_and_stays_functional(self):
        board = BoardState()
        board.try_push_token("e2e4")
        sink = []

        class CrashingUndoSession:
            """Models an unanticipated residual exception escaping the
            hardened session — the last-resort layer must still hold."""

            def __init__(self):
                self.board = board
                self.pending_resync = None
                self.sink = sink.append

            def display_cb(self, line):
                sink.append({"e": "_DISPLAY", "line": line})

            def undo_last_ply(self):
                raise RuntimeError("boom")

        loop = OperatorLoop(CrashingUndoSession(), FakeTransport(),
                            stdin=io.StringIO(), stdout=io.StringIO())
        loop.handle_line("u")  # must NOT raise (today it propagates)
        faults = [r for r in sink if r.get("e") == "ENGINE_FAULT"]
        self.assertEqual(len(faults), 1, sink)
        self.assertIn("undo failed", faults[0]["reason"])
        self.assertIn("RuntimeError('boom')", faults[0]["reason"])
        self.assertIn("traceback", faults[0])
        self.assertIn("RuntimeError", faults[0]["traceback"])
        self.assertIn("ENGINE FAULT", loop.stdout.getvalue())
        # The loop object is not wedged: `q` sets the quit flag, and a
        # subsequent `u` still reaches undo_last_ply.
        loop.handle_line("q")
        self.assertTrue(loop._quit)
        loop.handle_line("u")
        faults = [r for r in sink if r.get("e") == "ENGINE_FAULT"]
        self.assertEqual(len(faults), 2,
                         "the loop still routes `u` after `q` — not wedged")


class TimingAnomalyTests(unittest.TestCase):
    """CR-06: a lying engine_ms (stale info time > wall delta) must clamp +
    journal an anomaly — never an AssertionError that drain_events swallows,
    silently dropping the MOVE_LOGGED row."""

    def test_stale_engine_ms_is_clamped_and_journaled(self):
        board = BoardState()
        board.try_push_token("e2e4")
        board.try_push_token("e7e5")
        s, t, o = make_session(our="w", board=board)
        s.state = Session.OUR_SEARCH
        s.last_info = {"depth": 9, "nodes": 50000, "score": "cp 30",
                       "time": 999999, "pv": "g1f3"}
        s.search_t0_ms = s._wall_ms_now()  # fresh anchor: wall delta ≈ 0
        t.events.put({"type": "bestmove", "move": "g1f3", "ponder": None,
                      "search_id": t.search_id})
        pump(s, t, until=lambda fed: "bestmove" in fed)
        rows = [r for r in o["sink"] if r.get("e") == "MOVE_LOGGED"]
        self.assertEqual(len(rows), 1,
                         "the row is never silently lost")
        self.assertGreaterEqual(rows[0]["wall_ms"], rows[0]["engine_ms"])
        faults = [r for r in o["sink"] if r.get("e") == "ENGINE_FAULT"]
        self.assertEqual(len(faults), 1, o["sink"])
        self.assertIn("CR-06", faults[0]["reason"])
        self.assertEqual(s.state, Session.ANNOUNCE_PENDING,
                         "FSM advances on every path (the assert skipped it)")


class DrainFaultTests(unittest.TestCase):
    """CR-10: a handler exception journals ENGINE_FAULT with traceback and
    the drain CONTINUES — never an aborting bare except with zero evidence."""

    def test_handler_exception_journals_fault_and_keeps_draining(self):
        board = BoardState()
        s, t, o = make_session(our="w", board=board)
        calls = []

        def raising_on_first(event):
            calls.append(event.get("type"))
            if len(calls) == 1:
                raise KeyError("boom")
        s.on_engine_event = raising_on_first
        loop = OperatorLoop(s, t, stdin=io.StringIO(),
                            stdout=io.StringIO())
        loop.session = _DrainSessionDouble(s, o)
        t.events.put({"type": "info", "depth": 1})
        t.events.put({"type": "info", "depth": 2})
        loop.drain_events()  # must not raise
        self.assertEqual(calls, ["info", "info"],
                         "the second event must still be dispatched")
        faults = [r for r in o["sink"] if r.get("e") == "ENGINE_FAULT"]
        self.assertEqual(len(faults), 1, o["sink"])
        self.assertIn("traceback", faults[0])
        self.assertIn("KeyError", faults[0]["traceback"])
        self.assertIn("event dispatch error", faults[0]["reason"])

    def test_options_carry_no_placeholder_paths(self):
        # CR-12 session half: the console never sends a path it knows is
        # bogus — no option value equals "<empty>".
        s, t, o = make_session(our="w")
        for name, value in s.options:
            self.assertNotEqual(value, "<empty>",
                                f"placeholder path on {name}")
        self.assertFalse([n for n, v in s.options if n == "SyzygyPath"],
                         "no SyzygyPath option until 02-05's validated flag")


class _DrainSessionDouble:
    """Wraps a real session: overrides sink/display for fault assertions,
    keeps on_engine_event dispatch (the drain's real consumer)."""

    def __init__(self, session, o):
        self._session = session
        self._o = o
        self.display_lines = []

    @property
    def sink(self):
        return self._o["sink"].append

    def display_cb(self, line):
        self.display_lines.append(line)

    def on_engine_event(self, event):
        self._session.on_engine_event(event)


if __name__ == "__main__":
    unittest.main()
