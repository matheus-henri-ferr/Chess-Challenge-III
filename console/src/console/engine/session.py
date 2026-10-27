#!/usr/bin/env python3
# ChessChallendIII — Session FSM: the locked transition table (plan 02-02)
# Copyright (C) 2026 ChessChallendIII
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.  See Copying.txt for the full text.

"""Session — the explicit operator↔engine state machine (RESEARCH Pattern 2).

States (ROADMAP-locked names): IDLE, OUR_SEARCH, ANNOUNCE_PENDING,
AWAIT_OPP_CONFIRM, OPP_TURN, PONDERING, plus the internal DISCARDING flag
mirroring the transport's. The replica's `board.turn` is the side-to-move
guard — the session never trusts engine-side state to know whose move it
is (PROTO-05). The operator has exactly ONE move-entry stream: the input's
role is resolved from `expected_mover()`, so a token typed while it is our
turn is a wrong-side reject (reason names the expected side) and two
consecutive same-side inputs are structurally impossible (the first push
flips `board.turn`).

Non-negotiables implemented here:
  - ANNOUNCE is written ONLY by the bestmove handler (Pitfall 5); info
    events feed the PV callback and never the announce buffer;
  - a current bestmove is validated against the replica BEFORE display;
    an illegal answer is a FAULT record, never announced, never pushed
    (T-02-07); a legal one is pushed immediately and announced;
  - a stale bestmove produces NO board advance, NO announce and a
    STALE_BESTMOVE sink record (CF-7 / §7.3) — likewise a bestmove landing
    while PONDERING is the speculative search's answer and is sunk;
  - `start_game()` fires search #1 automatically when our colour moves
    first (B1 fix); with the opponent to move it sends nothing;
  - resync is replay-last-N through the legal gate on a FRESH BoardState
    with explicit confirmation — history is never rewritten, no free FEN
    edit exists (PROTO-07, T-02-10);
  - setoption reaches the transport's IDLE-only queue from any state;
    the flush stays at IDLE (§1.4, Pitfall 9).

Ponder machinery exists and is table-visible but is never live in Phase 2
games (Ponder=false frozen, §8.1); the ponderhit path raises
NotImplementedError until Phase 5. Clock numbers ride through verbatim
(research A2 placeholder); Phase 3's ClockModel replaces the setter.
"""

import time

from console.game.moves import Reject, announce_form, operator_move

# Event vocabulary (RESEARCH Pattern 3 — Phase 3 extends, never rewrites):
# GAME_START, MOVE_LOGGED, REJECT, STALE_BESTMOVE, OPP_CLOCK, RESYNC,
# ENGINE_FAULT, GAME_END. FAULT marks an illegal engine bestmove (T-02-07).
EVENTS = ("GAME_START", "MOVE_LOGGED", "REJECT", "STALE_BESTMOVE",
          "OPP_CLOCK", "RESYNC", "ENGINE_FAULT", "FAULT", "GAME_END")


class Session:
    """One game's FSM over the 02-01 EngineTransport."""

    IDLE = "IDLE"
    OUR_SEARCH = "OUR_SEARCH"
    ANNOUNCE_PENDING = "ANNOUNCE_PENDING"
    AWAIT_OPP_CONFIRM = "AWAIT_OPP_CONFIRM"
    OPP_TURN = "OPP_TURN"
    PONDERING = "PONDERING"
    DISCARDING = "DISCARDING"  # internal flag-state between PONDERING and go

    def __init__(self, transport, board, sink, our_color="w",
                 announce_cb=None, pv_cb=None, display_cb=None,
                 wait_for_bestmove_timeout=30.0):
        self.transport = transport
        self.board = board
        self.sink = sink                # journal-shaped callable(dict) (02-03)
        self.our_color = "w" if our_color == "w" else "b"
        self.announce_cb = announce_cb  # ANNOUNCE field writer (loop-owned)
        self.pv_cb = pv_cb              # PV display callback (loop-owned)
        self.display_cb = display_cb or (lambda line: None)
        self.wait_for_bestmove_timeout = wait_for_bestmove_timeout
        self.state = self.IDLE
        self.discarding = False         # mirrors transport.discarding
        # §2.3 competition option set — queued, flushed once at IDLE after
        # the handshake (Pitfall 9: never mid-search).
        self.options = [
            ("Threads", 1), ("Hash", 2048), ("SyzygyPath", "<empty>"),
            ("SyzygyProbeLimit", 5), ("Move Overhead", 100), ("Ponder", False),
        ]
        self.clock_passthrough_ms = (600000, 600000)  # A2: verbatim numbers
        self.last_info = {}             # depth/nodes/score/time/pv capture
        self.last_announced = None      # the validated current bestmove
        self.pending_resync = None      # (n, fresh_state) armed by request
        self.ponder_spec = None         # the speculative ponder move
        self.opp_clock_raw = None       # last `t` reading (raw + parsed)
        self.opp_clock_ms = None
        self.search_t0_ms = None        # wall_ms anchor: stamped at the go write
        self.game_t0_ms = None          # wall anchor for the game's first row
        self.last_move_wall_ms = None   # receipt time of the last logged row
        self.game_id = None             # header field (main.py owns the id)
        self.log_ctx = {}               # header ctx: net sha, TC, option set

    # --- plumbing -------------------------------------------------------------
    def _emit(self, event):
        self.sink(event)

    def _announce(self, text):
        if self.announce_cb is not None:
            self.announce_cb(text)

    def _go_line(self):
        from console.transport.uci import go_line
        w_ms, b_ms = self.clock_passthrough_ms
        return go_line(w_ms, b_ms)

    def _wall_ms_now(self):
        """monotonic_ns() → ms (LOG-03 timing source, console-wide)."""
        return time.monotonic_ns() // 1_000_000

    # --- startup (B1 fix + §2.3) ------------------------------------------------
    def apply_startup_options(self):
        """Queue the §2.3 set then flush once — IDLE only, after handshake."""
        for name, value in self.options:
            self.setoption(name, value)
        self.transport.flush_pending_options()

    def start_game(self, game_id=None):
        """Game-start trigger: search #1 fires automatically when our colour
        moves first; with the opponent to move, send nothing and wait.

        GAME_START carries the game id and the clock passthrough values the
        frozen go line will use (the §5.1 header's numbers, journaled too).
        """
        w_ms, b_ms = self.clock_passthrough_ms
        self.game_t0_ms = self._wall_ms_now()
        self.last_move_wall_ms = self.game_t0_ms
        self._emit({"e": "GAME_START", "game_id": game_id,
                    "our_color": self.our_color,
                    "clock_ms": {"w": w_ms, "b": b_ms},
                    "fen": self.board.fen()})
        if self.board.expected_mover() == self.our_color:
            self._start_search()
        # Opponent to move: stay at IDLE — the operator's first typed move
        # is the opponent's (AWAIT_OPP_CONFIRM-equivalent).

    # --- send side (the position line is ALWAYS the replica's, §4.1) ---------
    def _start_search(self):
        """position_line + frozen go via transport.start_search → OUR_SEARCH.

        wall_ms anchor (Pitfall 7): t0 is stamped HERE, at the go write —
        never at the position send. Bestmove handlers read it back.
        """
        sid = self.transport.start_search()  # §1.3: raises if one outstanding
        self.transport.send(self.board.position_line())
        self.transport.send(self._go_line())
        self.search_t0_ms = self._wall_ms_now()  # wall_ms anchor: the go write
        self.state = self.OUR_SEARCH
        return sid

    # --- operator input ---------------------------------------------------------
    def on_operator_move(self, raw):
        """One typed move token — the opponent's announced move.

        Role resolution IS the guard: an opp move is expected exactly when
        `expected_mover() != our_color`. A token typed while it is our turn
        is a typed reject naming the expected side; after any successful
        push `board.turn` flips, so two consecutive same-side inputs cannot
        both pass. Legal opp move → push, MOVE_LOGGED(src=opp), position+go
        via start_search → OUR_SEARCH. Reject never touches state or clock.
        """
        mover = self.board.expected_mover()
        if mover == self.our_color:
            reason = (f"wrong side: it is OUR move ({self.our_color}) — "
                      f"wait for the engine's ANNOUNCE")
            self._emit({"e": "REJECT", "raw": raw, "kind": "wrong_side",
                        "reason": reason})
            self.display_cb(f"REJECTED wrong_side: {reason}")
            return None
        try:
            move = operator_move(self.board.board, raw)
        except Reject as reject:
            self._emit({"e": "REJECT", "raw": reject.raw,
                        "kind": reject.kind.value, "reason": reject.reason})
            self.display_cb(f"REJECTED {reject.kind.value}: {reject.reason}")
            return None
        meta = self.board.push_validated(move)
        # §4.5 fill: depth=0 nodes=0 score=- engine_ms=0, wall measured.
        # Anchor: the last logged row's receipt (bestmove for us, or game
        # start) — the interval the opponent actually took + entry time.
        now = self._wall_ms_now()
        anchor = self.last_move_wall_ms if self.last_move_wall_ms is not None \
            else self.game_t0_ms
        wall_ms = max(0, now - (anchor if anchor is not None else now))
        self._emit({"e": "MOVE_LOGGED", "src": "opp", **meta,
                    "depth": 0, "nodes": 0, "score": "-",
                    "engine_ms": 0, "wall_ms": wall_ms, "pv": move.uci()})
        self.last_move_wall_ms = now
        self.state = self.OPP_TURN
        self._start_search()  # our turn now: the engine answers
        return move

    def on_operator_confirm(self):
        """`y` — the announced move was played on the physical board."""
        if self.state == self.ANNOUNCE_PENDING:
            self.state = self.AWAIT_OPP_CONFIRM
            return self.last_announced
        return None

    # --- engine events ------------------------------------------------------------
    def on_engine_event(self, event):
        etype = event.get("type")
        if etype == "info":
            self._on_info(event)
        elif etype == "bestmove":
            self._on_bestmove(event, stale=False)
        elif etype == "stale_bestmove":
            self._on_bestmove(event, stale=True)
        elif etype == "eof":
            self._on_fault("engine EOF")
        elif etype == "timeout":
            self._on_fault("engine read timeout")
        elif etype == "garbage":
            self._on_fault(f"garbage on stdout: {event.get('line', '')!r}")

    def _on_info(self, event):
        if "string" in event:
            return  # diagnostics / §6 traces never touch PV or ANNOUNCE
        for key in ("depth", "seldepth", "nodes", "nps", "time", "score",
                    "pv", "multipv", "hashfull", "tbhits"):
            if key in event:
                self.last_info[key] = event[key]
        if self.pv_cb is not None and event.get("pv"):
            self.pv_cb(event["pv"])  # PV display ONLY — never ANNOUNCE

    def _on_bestmove(self, event, stale):
        move_token = event.get("move", "")
        if stale or self.state == self.PONDERING:
            # CF-7 discard point: no board change, no announce; while
            # PONDERING even a current-id answer belongs to the speculative
            # search and is sunk the same way. Evidence record only.
            self._emit({"e": "STALE_BESTMOVE", "move": move_token,
                        "search_id": event.get("search_id")})
            return
        if move_token == "(none)":
            # §7.2: no legal move exists — game over per the rules.
            # Terminal row first (LOGBOOK §4.6: src=none, uci=(none),
            # depth=0 nodes=0, non-empty score — `mate 0` verified live on
            # the wire immediately before `bestmove (none)`), then GAME_END.
            outcome = self.board.outcome()
            score = self.last_info.get("score", "mate 0")
            now = self._wall_ms_now()
            anchor = self.last_move_wall_ms if self.last_move_wall_ms \
                is not None else self.game_t0_ms
            wall_ms = max(0, now - (anchor if anchor is not None else now))
            mover = self.board.expected_mover()
            move_no = self.board.board.fullmove_number
            self._emit({"e": "MOVE_LOGGED", "src": "none", "uci": "(none)",
                        "move_no": move_no, "side": mover,
                        "depth": 0, "nodes": 0, "score": score,
                        "engine_ms": self.last_info.get("time", 0),
                        "wall_ms": wall_ms, "pv": "(none)"})
            self._emit({"e": "GAME_END",
                        "reason": outcome.termination.name if outcome
                        else "no-legal-move",
                        "result": (outcome.result() if outcome else "*"),
                        "uci": "(none)"})
            self.state = self.IDLE
            return
        # T-02-07: validate against the replica BEFORE display.
        try:
            move = operator_move(self.board.board, move_token)
        except Reject as reject:
            self._emit({"e": "FAULT", "uci": move_token, "reason":
                        f"engine bestmove illegal in replica: "
                        f"{move_token!r} ({reject.reason})"})
            self.display_cb(f"FAULT: engine suggested illegal move "
                            f"{move_token!r} — NOT played; you are on move")
            self.state = self.IDLE
            return
        # Legal: push now (the replica stays the authority), announce, log.
        meta = self.board.push_validated(move)
        self._announce(announce_form(move.uci()))
        self.last_announced = move
        # wall_ms: monotonic delta from the go-write anchor (Pitfall 7);
        # engine_ms is the wire `info time` milliseconds (§5.2). The
        # wall_ms ≥ engine_ms invariant is asserted here at write time and
        # re-checked fail-closed by log_lint (T-02-13).
        engine_ms = self.last_info.get("time", 0)
        wall_ms = 0
        if self.search_t0_ms is not None:
            # Floor 1: a completed search spans at least one pipe+thread
            # round trip — below the log's 1 ms quantum. The floor keeps
            # the §2.2 invariant writable for instant searches; a peer
            # claiming MORE than wall (impossible timing, T-02-13) still
            # fires the assert below.
            wall_ms = max(1, self._wall_ms_now() - self.search_t0_ms)
        assert wall_ms >= engine_ms, (
            f"wall_ms {wall_ms} < engine_ms {engine_ms} "
            f"(timing anchor bug, Pitfall 7)")
        self._emit({"e": "MOVE_LOGGED", "src": "search", **meta,
                    "depth": self.last_info.get("depth", 0),
                    "nodes": self.last_info.get("nodes", 0),
                    "score": self.last_info.get("score", "-"),
                    "engine_ms": engine_ms,
                    "wall_ms": wall_ms,
                    "pv": self.last_info.get("pv", move.uci())})
        self.last_move_wall_ms = self._wall_ms_now()
        self.state = self.ANNOUNCE_PENDING

    # --- clock capture (PROTO-08: capture now, interpret in Phase 3) ----------
    def on_opp_clock(self, raw, parsed_ms):
        self.opp_clock_raw = raw
        self.opp_clock_ms = parsed_ms
        self._emit({"e": "OPP_CLOCK", "raw": raw, "parsed_ms": parsed_ms})

    # --- resync (PROTO-07: replay-last-N + confirmation, no free FEN) ---------
    def request_resync(self, n):
        """Arm a resync: re-derive the position n plies back by re-entering
        the verified move prefix through the legal gate on a FRESH
        BoardState. Applies nothing until confirm_resync(n)."""
        n = int(n)
        if n < 0 or n > len(self.board.moves):
            self.display_cb(f"cannot resync {n} plies "
                            f"({len(self.board.moves)} on record)")
            return None
        moves = self.board.moves[:len(self.board.moves) - n] if n else \
            list(self.board.moves)
        fresh = type(self.board)()
        for uci in moves:
            _, reject = fresh.try_push_token(uci)
            if isinstance(reject, Reject):  # cannot happen for verified moves
                self._emit({"e": "FAULT", "reason":
                            f"resync replay failed on {uci!r}: {reject.reason}"})
                self.pending_resync = None
                return None
        self.pending_resync = (n, fresh)
        self._emit({"e": "RESYNC", "phase": "requested", "plies": n,
                    "fen_before": self.board.fen(),
                    "fen_after": fresh.fen()})
        return fresh.fen()

    def confirm_resync(self, n):
        """Apply the armed resync — the explicit `y` gate (T-02-10)."""
        n = int(n)
        if self.pending_resync is None or self.pending_resync[0] != n:
            self.display_cb("no armed resync for this ply count")
            return False
        _, fresh = self.pending_resync
        self.pending_resync = None
        self.board = fresh
        self._emit({"e": "RESYNC", "phase": "applied", "plies": n,
                    "fen": fresh.fen()})
        self.display_cb(f"resynced to {fresh.fen()}")
        return True

    # --- ponder (Phase 5 machinery, built + table-visible now) -----------------
    def enter_pondering(self, spec_move):
        """Enter PONDERING on a speculation (§8: `go ponder …`, Ponder=true
        only — Phase 2 exercises this via tests/mocks, never live games)."""
        sid = self.transport.start_search()
        self.transport.send(self.board.position_line() + f" {spec_move}")
        self.transport.send("go ponder " + self._go_line()[len("go "):])
        self.ponder_spec = spec_move
        self.state = self.PONDERING
        return sid

    def on_opp_move_during_ponder(self, raw):
        """PONDERING + typed opp move: equal to the speculation → ponderhit
        (Phase 5 stub); differing → stop + discarding, sink the owed
        bestmove, then the REAL position + go → OUR_SEARCH."""
        try:
            move = operator_move(self.board.board, raw)
        except Reject as reject:
            self._emit({"e": "REJECT", "raw": reject.raw,
                        "kind": reject.kind.value, "reason": reject.reason})
            self.display_cb(f"REJECTED {reject.kind.value}: {reject.reason}")
            return None
        if self.ponder_spec == move.uci():
            raise NotImplementedError(
                "ponderhit path is Phase 5 (TM-13) — not wired in Phase 2")
        # Miss: the position changed on the physical board.
        meta = self.board.push_validated(move)
        now = self._wall_ms_now()
        anchor = self.last_move_wall_ms if self.last_move_wall_ms is not None \
            else self.game_t0_ms
        wall_ms = max(0, now - (anchor if anchor is not None else now))
        self._emit({"e": "MOVE_LOGGED", "src": "opp", **meta,
                    "depth": 0, "nodes": 0, "score": "-",
                    "engine_ms": 0, "wall_ms": wall_ms, "pv": move.uci()})
        self.last_move_wall_ms = now
        self.transport.send("stop")
        self.transport.mark_discarding()
        self.discarding = True
        self.state = self.DISCARDING
        self._consume_owed_bestmove()
        self.discarding = False
        self._start_search()  # the REAL position + go → OUR_SEARCH
        return move

    def _consume_owed_bestmove(self):
        """Drain until ONE bestmove-shaped event is consumed (the stop-owed
        answer), re-queuing everything else (§1.3: consume before next go)."""
        deferred = []
        try:
            while True:
                event = self.transport.events.get(
                    timeout=self.wait_for_bestmove_timeout)
                etype = event.get("type")
                if etype in ("bestmove", "stale_bestmove"):
                    self._on_bestmove(event, stale=True)
                    return event
                if etype == "eof":
                    raise RuntimeError("engine EOF before the owed bestmove")
                deferred.append(event)
        finally:
            for event in deferred:
                self.transport.events.put(event)

    # --- fault surface (Phase 2 detects + surfaces, never corrupts) -----------
    def _on_fault(self, reason):
        self._emit({"e": "ENGINE_FAULT", "reason": reason})
        self.display_cb(f"ENGINE FAULT: {reason}")
        self.state = self.IDLE

    def setoption(self, name, value):
        """Queue an option change — safe from any state (the flush is
        transport-owned and IDLE-only, §1.4)."""
        self.transport.queue_option(name, value)
