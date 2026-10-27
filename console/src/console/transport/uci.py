#!/usr/bin/env python3
# ChessChallendIII — console UCI transport (plan 02-01)
# Copyright (C) 2026 ChessChallendIII
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.  See Copying.txt for the full text.

"""One disciplined UCI channel to the engine (docs/PROTOCOL.md).

Framing, reader thread, search_id, discarding flag, option queue, stderr
drain, and the frozen go builders. Pipe discipline copied from
tools/mock_gui.py EngineProc (plan 01-02): binary unbuffered pipes
(bufsize=0 — a TextIO pipe here reintroduces the verified G1 starvation
deadlock: the buffer drains the fd and select() times out on bytes we
already own), send with poll() liveness check, selector readline on the
raw fd into an owned buffer split on b"\\n", reap via quit → wait(5) →
kill → wait.

PROTOCOL invariants enforced here:
  §1.3  exactly one `go` outstanding (start_search raises otherwise);
  §1.4  setoption only at IDLE, after an isready/readyok sync;
  §2.1  uciok within 10 s or the handshake fails;
  §7.3  a bestmove with no matching outstanding go, a stale search_id, or
        an arrival while `discarding` is set is flagged stale and dropped.
"""

import json
import os
import queue
import selectors
import subprocess
import threading
import time

# PROTOCOL §3.1 — the frozen literal. Tests assert document ↔ mock ↔ console
# agreement; keep in sync with docs/PROTOCOL.md, tools/mock_engine.py and
# tools/mock_gui.py.
GO_LITERAL = "go wtime <int_ms> btime <int_ms> winc 10000 binc 10000"

# PROTOCOL §3.2 — any of these tokens in a `go` line is a contract violation.
FORBIDDEN_GO_TOKENS = ("movetime", "movestogo", "depth", "nodes",
                       "infinite", "searchmoves")


def go_line(w_ms, b_ms):
    """The frozen §3.1 go literal instantiated (never any other grammar)."""
    assert int(w_ms) >= 0 and int(b_ms) >= 0, "clocks are non-negative ms (§3.3)"
    return f"go wtime {int(w_ms)} btime {int(b_ms)} winc 10000 binc 10000"


def go_ponder_line(w_ms, b_ms):
    """The frozen §3.5 ponder variant (sent only when Ponder=true, §8)."""
    assert int(w_ms) >= 0 and int(b_ms) >= 0, "clocks are non-negative ms (§3.3)"
    return f"go ponder wtime {int(w_ms)} btime {int(b_ms)} winc 10000 binc 10000"


from console.transport import parser as _parser  # noqa: E402


class EngineTransport:
    """Subprocess owner for exactly one engine process (PROTOCOL §1.1)."""

    def __init__(self, argv, record=None, read_timeout=30.0):
        argv = list(argv)
        # Binary, unbuffered pipes: select() must see every byte the child
        # writes. TextIO buffering here deadlocks (buffer drains the fd,
        # select then times out on data we already own — verifier G1).
        # stderr NEVER merges into the UCI stream (mock_gui merges because
        # it is a dev driver — this console must not; T-02-03).
        self.popen = subprocess.Popen(
            argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, bufsize=0,
        )
        self.rec = open(record, "a", encoding="utf-8") if record else None
        self.read_timeout = read_timeout
        self.events = queue.Queue()  # unbounded parsed-event queue
        # search_id pairs 1:1 with an outstanding go; every bestmove event
        # carries the id of the go it answers (§7.3).
        self.search_id = 0
        self.outstanding = None      # the search_id of the go in flight
        self.discarding = False      # set by the session (ponder-miss stop)
        self._buf = b""
        self._eof = False
        self._pending_options = []   # setoption lines held until IDLE (§1.4)
        self.stderr_text = ""        # drained capture — never the parse stream
        self._stderr_chunks = []
        self._closing = False
        self._drain = threading.Thread(target=self._stderr_drain, daemon=True)
        self._reader = threading.Thread(target=self._reader_loop, daemon=True)
        self._drain.start()
        self._reader.start()

    # --- transcript ------------------------------------------------------
    def _record(self, direction, line):
        if self.rec:
            self.rec.write(json.dumps({"t": time.monotonic_ns(),
                                       "dir": direction, "line": line}) + "\n")
            self.rec.flush()

    # --- stderr drain (dedicated daemon thread, T-02-03) ------------------
    def _stderr_drain(self):
        try:
            for chunk in iter(lambda: self.popen.stderr.read(4096), b""):
                self._stderr_chunks.append(chunk)
        except (OSError, ValueError):
            pass
        finally:
            self.stderr_text = b"".join(self._stderr_chunks).decode(
                errors="replace")

    # --- framing (mock_gui pattern, reader-thread form) -------------------
    def _readline_unlocked(self, timeout):
        """One raw line from the fd with a REAL timeout. EOF → None."""
        while b"\n" not in self._buf:
            if self._eof:
                return None
            sel = selectors.DefaultSelector()
            sel.register(self.popen.stdout, selectors.EVENT_READ)
            try:
                if not sel.select(timeout):
                    raise TimeoutError(
                        f"engine silent for {timeout}s (hung or dead)")
                chunk = os.read(self.popen.stdout.fileno(), 65536)
            finally:
                sel.close()
            if not chunk:
                self._eof = True
                return None
            self._buf += chunk
        raw, self._buf = self._buf.split(b"\n", 1)
        line = raw.decode(errors="replace").rstrip("\r")
        if not line.strip():
            return self._readline_unlocked(timeout)  # skip blank, budget resets
        return line

    def _reader_loop(self):
        """Reader daemon: frame lines, parse, push typed events (Pitfall 8).

        Reader-loop failures surface as events too: EOF → {"type": "eof"},
        read silence past the per-read timeout → {"type": "timeout"}.
        """
        while not self._closing:
            try:
                line = self._readline_unlocked(self.read_timeout)
            except TimeoutError:
                self.events.put({"type": "timeout"})
                continue
            except (OSError, ValueError):
                # fd torn down by close() — normal shutdown, stop quietly.
                return
            if line is None:
                self.events.put({"type": "eof"})
                return
            self._record("out", line)
            event = _parser.parse_line(line)
            if event is None:
                continue
            if event["type"] == "bestmove":
                sid = self.outstanding
                move, ponder = event["move"], event["ponder"]
                self._dispatch_bestmove(move, ponder, sid)
                continue
            self.events.put(event)

    # --- §7.3 stale-bestmove machinery ------------------------------------
    def _dispatch_bestmove(self, move, ponder, sid):
        """Tag a bestmove with the id of the go it answers; flag stale.

        `consume_bestmove` semantics: the event is stale when sid is None
        (late bestmove, no go outstanding), sid != self.search_id, or
        self.discarding is True — and the first consumed bestmove clears
        the discarding flag.
        """
        stale = (sid is None or sid != self.search_id or self.discarding)
        if sid is not None and sid == self.outstanding:
            self.outstanding = None  # the matching go is answered
        if stale:
            self.discarding = False  # first consumed bestmove after it was set
            self.events.put({"type": "stale_bestmove", "move": move,
                             "ponder": ponder, "search_id": sid})
        else:
            self.events.put({"type": "bestmove", "move": move,
                             "ponder": ponder, "search_id": sid})

    # --- send / lifecycle (mock_gui send + close, verbatim discipline) ----
    def send(self, line):
        if self.popen.poll() is not None:
            raise RuntimeError(f"engine exited rc={self.popen.returncode}")
        self._record("in", line)
        self.popen.stdin.write((line + "\n").encode())
        self.popen.stdin.flush()

    def close(self):
        """Reap the engine on every path — quit first, then kill + wait."""
        self._closing = True
        try:
            self.send("quit")
        except (BrokenPipeError, RuntimeError, OSError):
            pass
        try:
            self.popen.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.popen.kill()
            self.popen.wait()
        try:
            self.popen.stdout.close()
            self.popen.stderr.close()
        except (OSError, ValueError):
            pass
        if self.rec:
            self.rec.close()
            self.rec = None

    # --- handshake (PROTOCOL §2.1 / §2.2) ---------------------------------
    def handshake(self, timeout=10.0):
        """`uci` → consume events until uciok (absence within 10 s = failed
        handshake, raise); collect id/option lines; then isready → readyok."""
        self.send("uci")
        deadline = time.monotonic() + timeout
        id_name, id_author, options = None, None, []
        uciok = False
        while time.monotonic() < deadline:
            remaining = max(0.05, deadline - time.monotonic())
            try:
                event = self.events.get(timeout=remaining)
            except queue.Empty:
                break
            etype = event["type"]
            if etype in ("eof", "timeout"):
                break
            if etype == "uciok":
                uciok = True
                break
            if etype == "id" and event["key"] == "name":
                id_name = event["value"]
            elif etype == "id" and event["key"] == "author":
                id_author = event["value"]
            elif etype == "option":
                options.append(event)
        if not uciok:
            raise RuntimeError(
                "failed handshake: no uciok within 10 s (PROTOCOL §2.1)")
        self.send("isready")
        while True:
            event = self.events.get(timeout=timeout)
            if event["type"] == "readyok":
                return {"id_name": id_name, "id_author": id_author,
                        "options": options}
            if event["type"] in ("eof", "timeout"):
                raise RuntimeError("failed handshake: engine died before readyok")

    # --- search ids (§1.3 one outstanding go) ------------------------------
    def start_search(self):
        """Begin one search: increments the monotonic search_id and hands it
        out. Raises if a go is currently outstanding (§1.3 hard invariant)."""
        if self.outstanding is not None:
            raise RuntimeError(
                "start_search with a go outstanding (PROTOCOL §1.3)")
        self.search_id += 1
        self.outstanding = self.search_id
        return self.search_id

    def mark_discarding(self):
        """Ponder-miss stop path (§8.2): the owed bestmove must be discarded."""
        self.discarding = True

    def wait_for_bestmove(self, timeout):
        """Drain the event queue until the bestmove for the current search
        arrives, re-queuing everything else (§1.3: consume the owed bestmove
        before the next go). TimeoutError when it never arrives."""
        deferred = []
        try:
            while True:
                event = self.events.get(timeout=timeout)
                if event["type"] == "bestmove" and \
                        event.get("search_id") == self.search_id:
                    return event
                if event["type"] in ("eof", "timeout"):
                    raise RuntimeError(
                        f"engine {event['type']} before bestmove")
                deferred.append(event)
        finally:
            for event in deferred:
                self.events.put(event)

    # --- option queue (§1.4: never mid-search) ------------------------------
    def queue_option(self, name, value):
        """Store a setoption line; sent only by flush_pending_options()."""
        self._pending_options.append((name, str(value)))

    def flush_pending_options(self):
        """Send queued setoption lines — ONLY at IDLE: asserts no go is
        outstanding, then isready/readyok sync, then the setoption lines."""
        if self.outstanding is not None:
            raise RuntimeError(
                "flush_pending_options with a go outstanding (PROTOCOL §1.4)")
        if not self._pending_options:
            return
        self.send("isready")
        while True:
            event = self.events.get(timeout=self.read_timeout)
            if event["type"] == "readyok":
                break
            if event["type"] in ("eof", "timeout"):
                raise RuntimeError("engine died during option-flush sync")
        for name, value in self._pending_options:
            self.send(f"setoption name {name} value {value}")
        self._pending_options = []
