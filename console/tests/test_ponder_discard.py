#!/usr/bin/env python3
# ChessChallendIII — CF-7 ponder-discard suite: stale bestmove never played (plan 02-02)
# Copyright (C) 2026 ChessChallendIII
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.  See Copying.txt for the full text.

"""Stale-bestmove discard tests, written BEFORE the session handler (CF-7).

Three transport-level orderings (RESEARCH Pattern 1) plus the session-level
guarantee: a stale bestmove produces NO board advance, NO announce callback
and a STALE_BESTMOVE record on the session's event sink. Drives the 02-01
EngineTransport against tools/mock_engine.py --stale-bestmove plus a
scripted late-arrival stub (test_transport.py STUB pattern). The
session-level cases were red first (ModuleNotFoundError on console.engine)
and are skip-guarded until plan 02-02 Task 2 lands the handler.
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

sys.path.insert(0, str(REPO / "console" / "src"))
from console.transport.uci import EngineTransport, go_line  # noqa: E402
from console.game.board import BoardState  # noqa: E402
try:
    from console.engine.session import Session  # noqa: E402
except ImportError:  # CF-7 red state: the handler does not exist yet
    Session = None

# Scripted UCI stub: minimal PROTOCOL speaker with per-mode behaviour for
# the discard orderings (same proven script as test_transport.py).
STUB = r'''
import sys, time
mode = sys.argv[1]
for raw in sys.stdin:
    line = raw.strip()
    if line == "uci":
        print("id name Scripted", flush=True)
        print("uciok", flush=True)
    elif line == "isready":
        print("readyok", flush=True)
    elif line.startswith("go"):
        print("info depth 1 nodes 1 time 1 pv e2e4", flush=True)
        print("bestmove e2e4", flush=True)
        if mode == "late":
            time.sleep(0.05)
            print("bestmove a7a6", flush=True)
    elif line == "stop" and mode == "spontaneous":
        print("bestmove b8c6", flush=True)
    elif line == "quit":
        break
'''


class PonderTestBase(unittest.TestCase):
    """Shared: transport construction with cleanup, event helpers."""

    def make(self, argv, record=None):
        t = EngineTransport(argv, record=record)
        self.addCleanup(t.close)
        return t

    def mock(self, *flags, record=None):
        argv = [sys.executable, str(MOCK), *flags]
        if record:
            argv += ["--record", record]
        t = self.make(argv, record=record)
        t.handshake()
        return t

    def stub(self, mode, record=None):
        t = self.make([sys.executable, "-c", STUB, mode], record=record)
        t.handshake()
        return t

    def tmp_path(self, prefix):
        path = tempfile.mktemp(prefix=prefix, suffix=".jsonl")
        self.addCleanup(lambda: os.path.exists(path) and os.unlink(path))
        return path

    @staticmethod
    def drain(t):
        """Every event currently queued (non-blocking)."""
        out = []
        while True:
            try:
                out.append(t.events.get_nowait())
            except queue.Empty:
                return out

    def poll_event(self, t, want, timeout=2.0):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                event = t.events.get(timeout=0.1)
            except queue.Empty:
                continue
            if event.get("type") == want:
                return event
        self.fail(f"no {want!r} event within {timeout}s")

    def run_search(self, t, moves="e2e4", timeout=10.0):
        sid = t.start_search()
        t.send(f"position startpos moves {moves}".strip())
        t.send(go_line(600000, 600000))
        return sid, t.wait_for_bestmove(timeout)


class TransportStaleOrderingTests(PonderTestBase):
    """The three discard orderings of RESEARCH Pattern 1 (CF-7)."""

    def test_ordering1_late_bestmove_with_no_outstanding_go_is_stale(self):
        # The engine answers a second time after the console already consumed
        # the owed bestmove: no go outstanding → flagged stale, and the event
        # carries NO consumer-visible move of its own search.
        t = self.stub("late")
        _, event = self.run_search(t)
        self.assertEqual(event["type"], "bestmove")
        self.assertIsNone(t.outstanding)
        stale = self.poll_event(t, "stale_bestmove")
        self.assertEqual(stale["move"], "a7a6")
        self.assertIsNone(stale["search_id"])
        self.assertEqual([e for e in self.drain(t)
                          if e["type"] == "bestmove"], [])

    def test_ordering2_post_stop_owed_bestmove_stale_before_next_search(self):
        # Ponder-miss stop path: discarding set, the owed bestmove arrives,
        # is flagged stale, clears the flag, and only then may the next go go.
        t = self.stub("spontaneous")
        _, event = self.run_search(t)
        self.assertEqual(event["type"], "bestmove")
        t.mark_discarding()
        self.assertTrue(t.discarding)
        t.send("stop")
        stale = self.poll_event(t, "stale_bestmove")
        self.assertEqual(stale["move"], "b8c6")
        self.assertFalse(t.discarding,
                         "first consumed bestmove must clear discarding")
        # The owed bestmove was consumed BEFORE the next search: start_search
        # must succeed with a fresh id and no stale traffic in between.
        sid2 = t.start_search()
        self.assertEqual(sid2, event["search_id"] + 1)

    def test_ordering3_unconsumed_bestmove_reflagged_stale_before_new_id(self):
        # A bestmove still unconsumed in the queue when a new search is
        # prepared is stale BEFORE the new search id is handed out.
        t = self.stub("late")
        sid1 = t.start_search()
        t.send("position startpos moves e2e4")
        t.send(go_line(600000, 600000))
        time.sleep(0.4)  # both engine answers arrive; NEITHER is consumed
        before = self.drain(t)
        self.assertEqual(
            [e["type"] for e in before if e["type"] == "bestmove"],
            ["bestmove"], "exactly one live bestmove must be pending")
        self.assertIn("stale_bestmove", [e["type"] for e in before])
        for e in before:
            t.events.put(e)  # queue again holds the unconsumed bestmove
        sid2 = t.start_search()
        self.assertEqual(sid2, sid1 + 1)
        after = self.drain(t)
        stales = [e for e in after if e["type"] == "stale_bestmove"]
        self.assertEqual([e["type"] for e in after
                          if e["type"] == "bestmove"], [],
                         "no unconsumed bestmove may survive start_search")
        self.assertEqual(len(stales), 2, after)


class MockStaleBestmoveTests(PonderTestBase):
    """tools/mock_engine.py --stale-bestmove: the CF-7 hazard as a peer."""

    def test_mock_answers_current_go_with_previous_position_move(self):
        # Search #2's answer is a move for the PREVIOUS position: the
        # transport cannot know (the search_id matches), so it arrives as a
        # CURRENT bestmove — exactly why the session must validate against
        # the replica before display (T-02-07, second independent check).
        path = self.tmp_path("stale-mock-")
        t = self.mock("--stale-bestmove", record=path)
        sid1, first = self.run_search(t)
        self.assertEqual(first["move"], "e7e5")  # ply-1 position: honest answer
        sid2, second = self.run_search(t, moves="e2e4 e7e5")
        self.assertEqual(second["type"], "bestmove")
        self.assertEqual(second["search_id"], sid2)
        self.assertEqual(second["move"], "e7e5",
                         "mock answered the CURRENT go with the PREVIOUS "
                         "position's move (stale_move = moves[-1])")


@unittest.skipUnless(Session is not None,
                     "Session lands in plan 02-02 Task 2 (CF-7 red state)")
class SessionStaleBestmoveTests(PonderTestBase):
    """Session-level CF-7 guarantee: stale bestmove is sunk, never played.

    The skip guard reads the module-level Session (None until Task 2), not
    a captured reference — tests unskip automatically when the handler lands.
    """

    def make_session(self, t, our="w"):
        sink, announces, pvs = [], [], []
        session = Session(t, BoardState(), sink=sink, our_color=our,
                          announce_cb=announces.append, pv_cb=pvs.append)
        return session, sink, announces, pvs

    def pump(self, session, t, until=None, timeout=3.0):
        """Feed queued transport events into the session until
        until(fed_types) is true (or timeout)."""
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

    def test_stale_bestmove_no_board_advance_no_announce_sink_record(self):
        # Ordering 1 through the session: the late a7a6 must leave NO trace
        # beyond the STALE_BESTMOVE record.
        t = self.stub("late")
        session, sink, announces, _ = self.make_session(t)
        session.start_game()  # our colour w: search #1 fires
        self.pump(session, t, until=lambda fed: "bestmove" in fed)
        self.assertEqual(announces, ["E2-E4"])
        self.assertEqual(session.board.moves, ["e2e4"])
        time.sleep(0.2)  # let the late a7a6 land
        self.pump(session, t, until=lambda fed: "stale_bestmove" in fed)
        stale_recs = [r for r in sink if r.get("e") == "STALE_BESTMOVE"]
        self.assertEqual(len(stale_recs), 1, sink)
        self.assertEqual(stale_recs[0]["move"], "a7a6")
        # NO board advance, NO announce, NO state change.
        self.assertEqual(session.board.moves, ["e2e4"])
        self.assertEqual(announces, ["E2-E4"])
        self.assertEqual(session.state, Session.ANNOUNCE_PENDING)

    def test_mock_stale_bestmove_yields_fault_not_announce(self):
        # mock --stale-bestmove: search #2's CURRENT bestmove is illegal in
        # the replica → FAULT record, never displayed, no board advance.
        t = self.mock("--stale-bestmove")
        session, sink, announces, _ = self.make_session(t)
        session.start_game()
        self.pump(session, t, until=lambda fed: "bestmove" in fed)
        self.assertEqual(session.board.moves, ["e2e4"])
        session.on_operator_move("e7e5")  # legal opp move → search #2
        self.pump(session, t,
                  until=lambda fed: fed.count("bestmove") >= 1
                  and any(r.get("e") == "FAULT" for r in sink))
        faults = [r for r in sink if r.get("e") == "FAULT"]
        self.assertEqual(len(faults), 1, sink)
        self.assertEqual(faults[0]["uci"], "e7e5")
        self.assertEqual(announces, ["E2-E4"],
                         "the illegal stale answer must never be announced")
        self.assertEqual(session.board.moves, ["e2e4", "e7e5"])
        self.assertEqual(session.state, Session.IDLE)

    def test_ponder_miss_discards_then_searches_real_position(self):
        # Ordering 2 through the session: enter_pondering → differing opp
        # move → stop + discarding → owed stale bestmove sunk → the REAL
        # position + go goes out (OUR_SEARCH).
        path = self.tmp_path("ponder-miss-")
        t = self.stub("spontaneous", record=path)
        session, sink, announces, _ = self.make_session(t)
        session.start_game()
        self.pump(session, t, until=lambda fed: "bestmove" in fed)
        self.assertEqual(session.board.moves, ["e2e4"])
        session.enter_pondering("e7e5")
        self.assertEqual(session.state, Session.PONDERING)
        # The speculative ponder search's own answer must be sunk too.
        self.pump(session, t, until=lambda fed: fed.count("stale_bestmove") >= 1
                  or fed.count("bestmove") >= 1)
        session.on_opp_move_during_ponder("d7d5")
        self.assertEqual(session.state, Session.DISCARDING)
        self.pump(session, t,
                  until=lambda fed: any(r.get("e") == "STALE_BESTMOVE"
                                        for r in sink)
                  and session.state == Session.OUR_SEARCH)
        self.assertEqual(session.state, Session.OUR_SEARCH)
        self.assertEqual(session.board.moves, ["e2e4", "d7d5"])
        with open(path, encoding="utf-8") as fh:
            recs = [json.loads(line) for line in fh if line.strip()]
        ins = [r["line"] for r in recs if r["dir"] == "in"]
        self.assertIn("position startpos moves e2e4 e7e5", ins,
                      "speculative ponder position must be sent")
        self.assertIn("position startpos moves e2e4 d7d5", ins,
                      "the real position must follow the discarded bestmove")
        go_ponder = [line for line in ins if line.startswith("go ponder ")]
        self.assertEqual(len(go_ponder), 1, ins)


if __name__ == "__main__":
    unittest.main()
