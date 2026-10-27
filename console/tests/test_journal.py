#!/usr/bin/env python3
# ChessChallendIII — journal durability, append-only + replay tests (plan 02-03)
# Copyright (C) 2026 ChessChallendIII
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.  See Copying.txt for the full text.

"""Journal tests (plan 02-03 Task 1): durability, append-only, replay.

Covers the plan's four behavioural demands plus the acceptance criteria:
  - 120 synthetic events append + iter_records returns all 120 in order
    (wall cost recorded, fsync-per-record asserted by the append path);
  - replay of a scripted 8-ply event stream reproduces the exact final
    FEN + move list;
  - append-only proof: file bytes written before a later append are
    unchanged (byte-prefix stability);
  - kill-safety: records written before a simulated crash (just stop
    appending) all survive and replay cleanly;
  - every event type round-trips; the vocabulary agrees with
    console.engine.session.EVENTS;
  - Journal.append does not disturb the event dict (the session may hand
    the same dict to other sinks);
  - replay() of a journal with an applied RESYNC reproduces the realigned
    state; replaying an impossible uci raises (corrupt journal is loud).
"""

import os
import pathlib
import sys
import tempfile
import time
import unittest

REPO = pathlib.Path(__file__).parent.resolve().parent.parent
sys.path.insert(0, str(REPO / "vendor"))
sys.path.insert(0, str(REPO / "console" / "src"))

from console.game.board import BoardState  # noqa: E402
from console.game.journal import EVENTS, Journal, append_event  # noqa: E402


class AppendOrderTests(unittest.TestCase):
    """120 fsynced records: order survives, wall cost recorded."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="journal-t1-")
        self.path = os.path.join(self.tmp, "journal-01.jsonl")
        self.journal = Journal(self.path)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_120_events_append_and_iterate_in_order(self):
        events = [{"e": "MOVE_LOGGED", "src": "opp", "seq": i,
                   "uci": f"a{i}a{i}"} for i in range(120)]
        t0 = time.monotonic_ns()
        for event in events:
            self.journal.append(event)
        wall_ms = (time.monotonic_ns() - t0) // 1_000_000
        records = self.journal.iter_records()
        self.assertEqual(len(records), 120)
        self.assertEqual([r["seq"] for r in records], list(range(120)))
        # Every record is stamped from the console-wide timing source and
        # monotonic within the run.
        stamps = [r["t_mono_ms"] for r in records]
        self.assertTrue(all(s > 0 for s in stamps))
        self.assertEqual(stamps, sorted(stamps))
        # Wall cost is recorded (durable budget: fsync per record must stay
        # negligible at game scale — T-02-14 accepts with this evidence).
        self.assertLess(wall_ms, 5000,
                        f"120 fsynced records took {wall_ms} ms")

    def test_append_event_stamps_without_mutating_caller_dict(self):
        event = {"e": "OPP_CLOCK", "raw": "7:42", "parsed_ms": 462000}
        append_event(self.path, event)
        self.assertNotIn("t_mono_ms", event)  # caller's dict untouched
        (record,) = self.journal.iter_records()
        self.assertEqual(record["raw"], "7:42")
        self.assertIn("t_mono_ms", record)


class VocabularyTests(unittest.TestCase):
    """Every event type round-trips; the set agrees with session.EVENTS."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="journal-t2-")
        self.path = os.path.join(self.tmp, "journal.jsonl")
        self.journal = Journal(self.path)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_every_event_type_round_trips(self):
        for name in EVENTS:
            self.journal.append({"e": name, "note": f"probe-{name}"})
        kinds = [r["e"] for r in self.journal.iter_records()]
        self.assertEqual(kinds, list(EVENTS))

    def test_vocabulary_agrees_with_session_events(self):
        from console.engine.session import Session  # noqa: F401
        from console.engine.session import EVENTS as SESSION_EVENTS
        self.assertEqual(set(EVENTS), set(SESSION_EVENTS),
                         "journal and session event vocabularies diverged")


class ReplayTests(unittest.TestCase):
    """replay() reproduces the live state byte-for-byte on FEN + moves."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="journal-t3-")
        self.path = os.path.join(self.tmp, "journal.jsonl")
        self.journal = Journal(self.path)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _scripted_8ply_journal(self):
        """8-ply game: live push each token, journal what the session
        would emit."""
        board = BoardState()
        for uci in ("e2e4", "e7e5", "g1f3", "b8c6", "f1c4", "g8f6",
                    "d2d4", "e5d4"):
            move, meta = board.try_push_token(uci)
            self.assertIsNotNone(move, uci)
            self.journal.append({"e": "MOVE_LOGGED", "src": "search",
                                 **meta})
        return board

    def test_replay_reproduces_scripted_8ply_game(self):
        board = BoardState()
        tokens = ("e2e4", "e7e5", "g1f3", "b8c6", "f1c4", "g8f6",
                  "d2d4", "e5d4")
        for uci in tokens:
            move, meta = board.try_push_token(uci)
            self.journal.append({"e": "MOVE_LOGGED", "src": "search",
                                 **meta})
        replayed, move_rows = self.journal.replay()
        self.assertEqual(replayed.fen(), board.fen())
        self.assertEqual(replayed.moves, list(tokens))
        self.assertEqual([r["uci"] for r in move_rows], list(tokens))
        self.assertEqual(len(move_rows), 8)

    def test_replay_of_live_session_flow(self):
        """The real sink path: session events land in the journal, replay
        reproduces the session's board."""
        from console.tests.test_session import FakeTransport, make_session
        journal = Journal(self.path)
        session, transport, _ = make_session(
            our="w", transport=FakeTransport())
        session.sink = journal.append
        session.start_game()
        transport.finish_search("e2e4")
        session.on_engine_event({"type": "bestmove", "move": "e2e4",
                                 "search_id": transport.search_id})
        session.on_operator_move("e7e5")
        replayed, move_rows = journal.replay()
        self.assertEqual(replayed.fen(), session.board.fen())
        self.assertEqual(replayed.moves, session.board.moves)
        self.assertEqual([r["src"] for r in move_rows],
                         ["search", "opp"])

    def test_replay_honours_applied_resync(self):
        # 4 plies, then resync back 2 plies (the applied record).
        for uci in ("e2e4", "e7e5", "g1f3", "b8c6"):
            self.journal.append({"e": "MOVE_LOGGED", "src": "search",
                                 "uci": uci})
        self.journal.append({"e": "RESYNC", "phase": "applied", "plies": 2})
        board = BoardState()
        for uci in ("e2e4", "e7e5"):
            board.try_push_token(uci)
        replayed, move_rows = self.journal.replay()
        self.assertEqual(replayed.fen(), board.fen())
        self.assertEqual(replayed.moves, ["e2e4", "e7e5"])
        self.assertEqual(len(move_rows), 4)  # rows keep every logged move

    def test_replay_illegal_uci_is_loud(self):
        self.journal.append({"e": "MOVE_LOGGED", "src": "search",
                             "uci": "e4e6"})
        with self.assertRaises(ValueError):
            self.journal.replay()


class AppendOnlyTests(unittest.TestCase):
    """T-02-11: no rewrite path — later appends never disturb old bytes."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="journal-t4-")
        self.path = os.path.join(self.tmp, "journal.jsonl")
        self.journal = Journal(self.path)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_byte_prefix_stability_across_appends(self):
        for seq in range(10):
            self.journal.append({"e": "REJECT", "seq": seq})
        with open(self.path, "rb") as fh:
            prefix = fh.read()
        for seq in range(10, 40):
            self.journal.append({"e": "REJECT", "seq": seq})
        with open(self.path, "rb") as fh:
            after = fh.read()
        self.assertTrue(after.startswith(prefix),
                        "a later append modified earlier bytes")
        # Exactly 30 more records, each one line.
        self.assertEqual(len(after.splitlines()),
                         len(prefix.splitlines()) + 30)

    def test_kill_safety_records_survive_simulated_crash(self):
        for seq in range(25):
            self.journal.append({"e": "OPP_CLOCK", "seq": seq,
                                 "parsed_ms": seq})
        # Simulated crash: the process just stops appending. Everything
        # fsynced before the stop must survive and replay cleanly.
        journal2 = Journal(self.path)
        records = journal2.iter_records()
        self.assertEqual(len(records), 25)
        board, _ = Journal(self.path).replay()
        self.assertEqual(board.fen(), BoardState().fen())

    def test_only_append_mode_exists_in_module_source(self):
        src = pathlib.Path(REPO, "console/src/console/game/journal.py"
                           ).read_text(encoding="utf-8")
        self.assertIn("os.O_APPEND", src)
        self.assertNotIn("O_TRUNC", src)
        # The only text open() in the module is iter_records' read-only
        # reader; the append path goes through os.open(O_APPEND).
        for line in src.splitlines():
            if ".open(" in line and "os.open" not in line:
                self.assertIn('"r"', line)


if __name__ == "__main__":
    unittest.main()
