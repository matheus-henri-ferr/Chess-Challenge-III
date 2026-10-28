#!/usr/bin/env python3
# ChessChallendIII — OperatorLoop: select-on-stdin + queue poll (plan 02-02)
# Copyright (C) 2026 ChessChallendIII
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.  See Copying.txt for the full text.

"""OperatorLoop — the prompt that never dies (RESEARCH system diagram).

The loop polls the engine event queue AND fd 0 via select(); NEVER a
blocking input() that would hide ANNOUNCE updates while the operator sits
at the prompt (Pitfall 8, T-02-09: prompt latency independent of engine
nps). Every accepted move echoes `E2-E4  FEN: <fen>` immediately; every
reject echoes `REJECTED <kind>: <reason>` immediately and never sleeps or
blocks (anti-pattern 8); ANNOUNCE renders as `>> ANNOUNCE: E2-E4` — a
field written only by the bestmove handler (Pitfall 5), visually distinct
from the `  PV:` lines.

Paste tolerance (T-02-05): one line per read, stripped, internal
whitespace collapsed, length-bounded at 32 chars — a longer paste is a
MALFORMED-shaped reject, never multi-line execution.

Commands: `t <time>` (M:SS / H:MM:SS / M.SS; bare digits echo the chosen
interpretation prominently — seconds — and journal raw+parsed, never
guessing silently), `r <N>` / `resync <N>` + `y` confirmation,
`u` (undo last ply — the board is the source of truth, Rule 10), `q`
(clean shutdown: stop-if-searching, then transport.close).
"""

import queue
import re
import select
import sys
import time
import traceback

from console.game.moves import Reject, RejectKind, announce_form

MAX_INPUT_LEN = 32
POLL_SECONDS = 0.05

_PROMPT = "move> "


def parse_clock_token(text):
    """`t <time>` grammar: M:SS, H:MM:SS, M.SS → ms (or None).

    Bare digits are the operator's ambiguity: the caller echoes the chosen
    interpretation (seconds) and journals raw+parsed — never guesses
    silently (RESEARCH Open Question 3).
    """
    text = text.strip()
    if re.fullmatch(r"\d+:\d{1,2}:\d{1,2}", text):        # H:MM:SS
        h, m, s = (int(part) for part in text.split(":"))
        return ((h * 60 + m) * 60 + s) * 1000
    if re.fullmatch(r"\d{1,3}:\d{1,2}", text):            # M:SS
        m, s = text.split(":")
        return (int(m) * 60 + int(s)) * 1000
    if re.fullmatch(r"\d{1,3}\.\d{1,2}", text):           # M.SS
        m, s = text.split(".")
        return (int(m) * 60 + int(s)) * 1000
    if re.fullmatch(r"\d+", text):                        # bare digits
        return int(text) * 1000  # seconds interpretation, echoed
    return None


class OperatorLoop:
    """select-on-stdin + transport-queue poll → Session dispatch."""

    def __init__(self, session, transport, stdin=None, stdout=None,
                 input_fd=None):
        self.session = session
        self.transport = transport
        self.stdout = stdout if stdout is not None else sys.stdout
        if input_fd is not None:
            self.stdin_fd = input_fd
        elif stdin is not None:
            self.stdin = stdin           # scripted/text source (tests)
            self.stdin_fd = None
        else:
            self.stdin = sys.stdin
            self.stdin_fd = self.stdin.fileno()
        self._quit = False
        self._stdin_buf = b""  # bytes read past the first newline (piped input)
        self._announced = None  # last ANNOUNCE (confirmation gate state)

    # --- output helpers -----------------------------------------------------
    def say(self, line):
        self.stdout.write(line + "\n")
        self.stdout.flush()

    def prompt(self):
        self.stdout.write(_PROMPT)
        self.stdout.flush()

    # --- event drain (T-02-09: the queue never blocks the prompt) ------------
    def drain_events(self):
        """Feed every queued engine event to the session, then render.

        CR-10: a handler crash is journalled and drained, never fatal —
        the prompt survives, the remaining queued events still dispatch."""
        while True:
            try:
                event = self.transport.events.get_nowait()
            except queue.Empty:
                return
            try:
                self.session.on_engine_event(event)
            except Exception as exc:  # CR-10: journal + keep draining
                sink = getattr(self.session, "sink", None)
                if callable(sink):
                    sink({"e": "ENGINE_FAULT", "reason":
                          f"event dispatch error: {exc!r}",
                          "traceback": traceback.format_exc()})
                display_cb = getattr(self.session, "display_cb", None)
                if callable(display_cb):
                    display_cb(f"ENGINE_FAULT: event dispatch error "
                               f"{exc!r} — drained, continuing")

    # --- input handling --------------------------------------------------------
    def handle_line(self, raw):
        line = " ".join(raw.split())
        if len(line) > MAX_INPUT_LEN:
            self.say(f"REJECTED malformed: input longer than "
                     f"{MAX_INPUT_LEN} chars — one move, one line")
            return
        if not line:
            self.say("empty input — type a move (e2e4), t <time>, "
                     "r <N>, u, or q")
            return
        if line == "q":
            self._quit = True
            return
        if line == "u":
            removed = self.session.undo_last_ply()
            if removed is None:
                self.say("nothing to undo")
            else:
                self.say(f"undone: {removed}  FEN: {self.session.board.fen()}")
            return
        if line == "y":
            if self.session.pending_resync is not None:
                n = self.session.pending_resync[0]
                if self.session.confirm_resync(n):
                    self.say(f"resynced to {self.session.board.fen()}")
                return
            move = self.session.on_operator_confirm()
            if move is None:
                self.say("nothing pending confirmation")
            return
        if line.startswith("t ") or line.startswith("t\t"):
            self._handle_clock(line[1:].strip())
            return
        if line.startswith("r ") or line.startswith("resync "):
            n_text = line.split(None, 1)[1].strip() if " " in line else ""
            self._handle_resync(n_text)
            return
        # Default: a move token for the opponent (or wrong-side reject).
        self._handle_move(line)

    def _handle_clock(self, text):
        parsed = parse_clock_token(text)
        if parsed is None:
            self.say(f"REJECTED malformed: cannot read clock {text!r} "
                     f"(use M:SS, H:MM:SS, M.SS or seconds)")
            return
        bare = text.isdigit()
        if bare:
            self.say(f"read as SECONDS: {text}s = {parsed // 60000}:" 
                     f"{(parsed // 1000) % 60:02d}")
        self.session.on_opp_clock(text, parsed)
        self.say(f"opp clock: {text} = {parsed} ms")

    def _handle_resync(self, n_text):
        if not n_text.isdigit():
            self.say("usage: resync <plies>  then y to confirm")
            return
        fen = self.session.request_resync(int(n_text))
        if fen is not None:
            self.say(f"resync armed ({n_text} plies) → {fen}")
            self.say("confirm with: y")

    def _handle_move(self, token):
        move = self.session.on_operator_move(token)
        if move is None:
            return  # the session already echoed the typed reject
        self.say(f"{announce_form(move.uci())}  FEN: {self.session.board.fen()}")

    # --- main loop ---------------------------------------------------------------
    def run(self, max_ticks=None, tracer=None):
        """Poll queue + stdin until `q`, EOF, or tracer end. max_ticks
        bounds tests.

        With a scripted (non-fd) stdin, lines are consumed without select.
        `tracer` (02-03): when set, the operator stdin is NOT owned by the
        run — EOF on it is ignored (the tracer owns the exit path); the
        loop ends only when the tracer finished or `q` arrives.
        """
        ticks = 0
        self.prompt()
        while not self._quit:
            if max_ticks is not None and ticks >= max_ticks:
                break
            ticks += 1
            self.drain_events()
            if tracer is not None and tracer.finished:
                break
            if self.stdin_fd is not None:
                ready, _, _ = select.select([self.stdin_fd], [], [],
                                            POLL_SECONDS)
                if self.stdin_fd not in ready:
                    if tracer is not None and tracer.finished:
                        break
                    self.prompt()
                    continue
                line = self._read_line()
            else:
                line = self.stdin.readline()
                if line == "":
                    line = None
                else:
                    line = line.rstrip("\n")
            if line is None:  # EOF — clean shutdown
                if tracer is not None and not tracer.finished:
                    # Tracer mode: stdin EOF is not the game's end (the
                    # console is driven by a harness); keep polling.
                    time.sleep(POLL_SECONDS)
                    continue
                self._shutdown()
                break
            self.handle_line(line)
            if self._quit:
                self._shutdown()
                break
            self.prompt()
        return 0

    def _read_line(self):
        """One line from the raw fd (os.read → own buffer semantics).

        Leftover bytes read past the first newline stay in `self._stdin_buf`
        and are consumed first on the next call — a piped/typed-ahead script
        must reach handle_line line-by-line, never be truncated at the
        first os.read (a discarded remainder silently loses operator input
        queued behind the first line).
        """
        import os
        if b"\n" in self._stdin_buf:  # drain the buffer before reading fd
            head, self._stdin_buf = self._stdin_buf.split(b"\n", 1)
            return head.decode(errors="replace").rstrip("\r")
        chunks = self._stdin_buf
        self._stdin_buf = b""
        while b"\n" not in chunks:
            if self.stdin_fd is None:  # scripted source: buffer is all there is
                line = chunks.decode(errors="replace").rstrip("\r") \
                    if chunks else None
                chunks = b""
                return line[:4096] if line else None
            try:
                chunk = os.read(self.stdin_fd, 4096)
            except OSError:
                self._stdin_buf = chunks  # keep for the next call
                return None
            if not chunk:
                if chunks:  # no trailing newline: last unterminated line
                    line = chunks.decode(errors="replace").rstrip("\r")
                    chunks = b""
                    self._stdin_buf = b""
                    return line[:4096]
                return None  # EOF
            chunks += chunk
            if len(chunks) > 8192:  # hostile paste guard
                head, rest = chunks.split(b"\n", 1)
                self._stdin_buf = rest[:8192]
                return head.decode(errors="replace")[:4096]
        head, rest = chunks.split(b"\n", 1)
        self._stdin_buf = rest[:8192]
        return head.decode(errors="replace").rstrip("\r")

    def _shutdown(self):
        """EOF/`q`: stop-if-searching, then close (PROTOCOL §1.5 order)."""
        self.say("")
        if self.transport.outstanding is not None:
            try:
                self.transport.send("stop")
            except (RuntimeError, OSError):
                pass
        try:
            self.transport.close()
        except (RuntimeError, OSError):
            pass
