#!/usr/bin/env python3
# ChessChallendIII — transport discipline tests: discard orderings, option
# queue at IDLE, stderr isolation (plan 02-01)
# Copyright (C) 2026 ChessChallendIII
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.  See Copying.txt for the full text.

"""EngineTransport discipline tests (plan 02-01 Task 2).

In-process tests drive REAL subprocesses — tools/mock_engine.py with its
fault injectors for the mock-driven cases, and a scripted UCI stub for the
discard orderings — following the test_contract.RuntimeEndToEndTests
pattern (cwd-independent absolute paths, explicit timeout= on every wait,
addCleanup on tmp artefacts). Covered cases, by name:

- GarbageToleranceTests.test_garbage_lines_are_inert_and_search_completes
- SilentHangTests.test_wait_for_bestmove_raises_timeouterror
- OptionQueueTests.test_flush_at_idle_sends_options_and_mock_survives
- OptionQueueTests.test_flush_while_outstanding_raises_without_sending
- DiscardOrderingTests.test_late_bestmove_with_no_outstanding_go_is_stale
- DiscardOrderingTests.test_discarding_then_owed_bestmove_is_stale_and_cleared
- DiscardOrderingTests.test_unconsumed_bestmove_reflagged_before_new_search_id
- OneOutstandingTests.test_start_search_with_go_outstanding_raises
- StderrIsolationTests.test_stderr_lands_in_drain_capture_never_in_events
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

# Scripted UCI stub: minimal PROTOCOL speaker with per-mode behaviour for
# the three discard orderings and the stderr-isolation probe.
STUB = r'''
import sys, time
mode = sys.argv[1]
for raw in sys.stdin:
    line = raw.strip()
    if line == "uci":
        if mode == "stderr":
            sys.stderr.write("stderr-noise line\n"); sys.stderr.flush()
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


class TransportTestBase(unittest.TestCase):
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
        """Next event of type `want`; non-matching events are dropped
        (test scaffolding — wait_for_bestmove owns the re-queue duty)."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                event = t.events.get(timeout=0.1)
            except queue.Empty:
                continue
            if event.get("type") == want:
                return event
        self.fail(f"no {want!r} event within {timeout}s")

    def run_search(self, t, timeout=10.0):
        sid = t.start_search()
        t.send("position startpos moves e2e4")
        t.send(go_line(600000, 600000))
        return sid, t.wait_for_bestmove(timeout)


class GarbageToleranceTests(TransportTestBase):
    def test_garbage_lines_are_inert_and_search_completes(self):
        t = self.mock("--garbage")
        sid, event = self.run_search(t)
        # The search completed with exactly one bestmove...
        self.assertEqual(event["type"], "bestmove")
        self.assertEqual(event["search_id"], sid)
        self.assertEqual(event["move"], "e7e5")  # mock answers ply 1
        # ...the garbage lines arrived as inert events with no state
        # effect (the search still answered), and no second bestmove.
        rest = self.drain(t)
        garbage = [e for e in rest if e["type"] == "garbage"]
        self.assertGreaterEqual(len(garbage), 2, rest)
        self.assertEqual([e for e in rest if e["type"] == "bestmove"], [])


class SilentHangTests(TransportTestBase):
    def test_wait_for_bestmove_raises_timeouterror(self):
        t = self.mock("--silent-hang")
        t.start_search()
        t.send("position startpos moves e2e4")
        t.send(go_line(600000, 600000))
        with self.assertRaises(TimeoutError):
            t.wait_for_bestmove(timeout=2.0)


class OptionQueueTests(TransportTestBase):
    def test_flush_at_idle_sends_options_and_mock_survives(self):
        t = self.mock("--crash-on-option")
        t.queue_option("Threads", "4")
        t.flush_pending_options()  # IDLE: isready/readyok sync, then setoption
        # The mock (--crash-on-option) did NOT exit: the setoption raced no
        # search, and a subsequent search completes normally.
        _, event = self.run_search(t)
        self.assertEqual(event["type"], "bestmove")
        self.assertIsNone(t.popen.poll())

    def test_flush_while_outstanding_raises_without_sending(self):
        path = self.tmp_path("opt-flush-")
        t = self.mock("--crash-on-option", record=path)
        t.queue_option("Hash", "64")
        t.start_search()  # outstanding set — §1.4 forbids setoption now
        with self.assertRaises(RuntimeError):
            t.flush_pending_options()
        # The search completes unharmed; the queued option flushes only at
        # the next IDLE — after the bestmove, never between go and bestmove.
        t.send("position startpos moves e2e4")
        t.send(go_line(600000, 600000))
        event = t.wait_for_bestmove(10.0)
        self.assertEqual(event["type"], "bestmove")
        t.flush_pending_options()
        with open(path, encoding="utf-8") as fh:
            recs = [json.loads(line) for line in fh if line.strip()]
        ins = [(i, r["line"]) for i, r in enumerate(recs)
               if r["dir"] == "in"]
        go_idx = [i for i, line in ins if line.startswith("go ")]
        bm_idx = [i for i, r in enumerate(recs) if r["dir"] == "out"
                  and r["line"].startswith("bestmove")]
        so_idx = [i for i, line in ins if line.startswith("setoption")]
        self.assertTrue(so_idx, "the post-search flush must have sent it")
        for g in go_idx:
            for b in bm_idx:
                if b > g:
                    for s in so_idx:
                        self.assertFalse(
                            g < s < b,
                            "setoption raced a search (PROTOCOL §1.4)")


class DiscardOrderingTests(TransportTestBase):
    def test_late_bestmove_with_no_outstanding_go_is_stale(self):
        # Ordering 1: engine answers a second time after the console already
        # consumed the owed bestmove — no go outstanding (sid None).
        t = self.stub("late")
        _, event = self.run_search(t)
        self.assertEqual(event["type"], "bestmove")
        self.assertIsNone(t.outstanding)
        stale = self.poll_event(t, "stale_bestmove")
        self.assertEqual(stale["move"], "a7a6")
        self.assertIsNone(stale["search_id"])
        self.assertEqual([e for e in self.drain(t)
                          if e["type"] == "bestmove"], [])

    def test_discarding_then_owed_bestmove_is_stale_and_cleared(self):
        # Ordering 2: ponder-miss stop path — discarding set, the owed
        # bestmove arrives, is flagged stale, and the flag clears.
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

    def test_unconsumed_bestmove_reflagged_before_new_search_id(self):
        # Ordering 3: a bestmove still unconsumed in the queue is stale the
        # moment start_search() runs — BEFORE the new id is handed out.
        t = self.stub("late")
        sid1 = t.start_search()
        t.send("position startpos moves e2e4")
        t.send(go_line(600000, 600000))
        time.sleep(0.4)  # both engine answers arrive; NEITHER is consumed
        before = self.drain(t)
        self.assertEqual(
            [e["type"] for e in before if e["type"] == "bestmove"],
            ["bestmove"], "exactly one live bestmove must be pending")
        self.assertIn("stale_bestmove", [e["type"] for e in before],
                      "the late answer was already flagged stale (ordering 1)")
        for e in before:
            t.events.put(e)  # put back: the queue again holds the unconsumed bestmove
        sid2 = t.start_search()
        self.assertEqual(sid2, sid1 + 1)
        after = self.drain(t)
        stales = [e for e in after if e["type"] == "stale_bestmove"]
        self.assertEqual([e["type"] for e in after
                          if e["type"] == "bestmove"], [],
                         "no unconsumed bestmove may survive start_search")
        self.assertEqual(len(stales), 2, after)
        self.assertEqual({e["search_id"] for e in stales}, {sid1, None},
                         "the pending live bestmove was re-flagged with its "
                         "original id BEFORE the new search id was handed out")
        self.assertEqual(t.outstanding, sid2)


class OneOutstandingTests(TransportTestBase):
    def test_start_search_with_go_outstanding_raises(self):
        t = self.stub("plain")
        t.start_search()
        t.send("position startpos moves e2e4")
        t.send(go_line(600000, 600000))
        with self.assertRaises(RuntimeError):
            t.start_search()  # §1.3 hard invariant


class StderrIsolationTests(TransportTestBase):
    def test_stderr_lands_in_drain_capture_never_in_events(self):
        t = self.stub("stderr")
        self.assertEqual(self.drain(t), [],
                         "handshake leaves no events; stderr must not add any")
        t.close()
        deadline = time.monotonic() + 2.0
        while "stderr-noise line" not in t.stderr_text \
                and time.monotonic() < deadline:
            time.sleep(0.05)  # drain thread assigns stderr_text at pipe EOF
        self.assertIn("stderr-noise line", t.stderr_text)


if __name__ == "__main__":
    unittest.main()
