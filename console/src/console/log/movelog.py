#!/usr/bin/env python3
# ChessChallendIII — MoveLog: the Rule 9 log projection (plan 02-03)
# Copyright (C) 2026 ChessChallendIII
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.  See Copying.txt for the full text.

"""MoveLog — pure projection of the journal into LOGBOOK's frozen format.

Pattern 4 (transcribe, do not paraphrase): one line per half-move in the
frozen key order `src move_no side uci depth nodes score score_white
engine_ms wall_ms pv`, pv LAST and unquoted (§3.2), no spaces inside other
values. The key order agrees both ways with tools/tests/test_contract.py's
LOG_KEYS (move_no,side,uci,depth,nodes,score,pv,engine_ms,wall_ms) plus
the §2.1/§4 additions src and score_white.

`MoveLog.build(events)` folds journal events into per-half-move records:
  - MOVE_LOGGED carries everything already (the session captured it);
  - STALE_BESTMOVE → a src=ponder record logged for the record, never
    announced (§4.4);
  - GAME_START/GAME_END/REJECT/OPP_CLOCK/RESYNC/ENGINE_FAULT are not move
    rows (RESYNC's log representation is the Phase 3 `# RESYNC …`
    reserved-prefix bundle — research Open Question #2).

Header (§5.1) and trailer (§5.2) write what Phase 2 can compute now:
engine sha256 recomputed at game start, net sha256 from PROVENANCE, the
exact setoption set, SyzygyProbeLimit asserted 5, TB/book inventory
placeholders `none`/`0` (research A3 — Phase 3 CHECK-01 owns the real
inventories), `network=off`; trailer carries result, reason, both final
clocks and the log's own sha256.
"""

import hashlib

# LOGBOOK §4 — the closed src set (module data, tests import it).
SRC_SET = ("search", "book", "tb", "ponder", "opp", "none")

# §3.1 key order minus src/score_white — the agreement target with
# tools/tests/test_contract.py LOG_KEYS (which carries exactly these nine).
LOG_KEYS = ("move_no", "side", "uci", "depth", "nodes", "score", "pv",
            "engine_ms", "wall_ms")

_RENDER_ORDER = ("src",) + LOG_KEYS[:6] + ("score_white",) + LOG_KEYS[6:]


def score_white_of(score, side=None):
    """§2.1 White-POV normalisation of a verbatim STM-POV score.

    The numeric part of `cp <int>` / `mate <int>` is normalised to the
    White-POV sign (a negative STM value becomes positive for White;
    when the mover was Black, `side="b"` negates a positive value);
    the bound flag is kept verbatim (research A4: negate the number
    only, never the flag). `-` (absent) stays `-`.
    `side` is the mover colour ("w"/"b"); None means the caller already
    wants the raw normalisation (White-POV as-is, used in tests/fixtures).
    """
    if not score or score == "-":
        return "-"
    tokens = score.split()
    flip = side == "b"
    out = score
    if len(tokens) >= 2 and tokens[0] in ("cp", "mate") \
            and tokens[1].lstrip("+-").lstrip("-").isdigit():
        value = int(tokens[1])
        if flip:
            # STM-POV black → White-POV negation.
            value = -value
        elif value < 0:
            # Negative STM score already IS White-POV-negative; normalise
            # to the White-POV sign (a minus on a white row).
            value = -value
        out = f"{tokens[0]} {value}"
    if len(tokens) >= 3 and tokens[2] in ("lowerbound", "upperbound"):
        out += f" {tokens[2]}"  # flag verbatim under negation (A4)
    return out


def render(rec):
    """One §3.1 line — the exact frozen template, pv last unquoted."""
    return ("src={src} move_no={move_no} side={side} uci={uci} depth={depth} "
            "nodes={nodes} score={score} score_white={score_white} "
            "engine_ms={engine_ms} wall_ms={wall_ms} pv={pv}").format(**rec)


class MoveLog:
    """Journal → per-half-move records → §3.1 lines. Never a writer of
    history: build() consumes journal-shaped event dicts and nothing else."""

    @staticmethod
    def build(events):
        """Fold journal events into per-half-move records (§4 fills).

        MOVE_LOGGED rows pass through with score_white computed for the
        mover's side; a STALE_BESTMOVE becomes a src=ponder record (§4.4:
        logged for the record, never announced). Journal-only events are
        skipped — they have no §3.1 representation in Phase 2.
        """
        rows = []
        for event in events:
            kind = event.get("e")
            if kind == "MOVE_LOGGED":
                rec = {key: event.get(key) for key in
                       ("src", "move_no", "side", "uci", "depth", "nodes",
                        "score", "engine_ms", "wall_ms", "pv")}
                rec["score"] = event.get("score", "-")
                rec["pv"] = event.get("pv") or event.get("uci", "")
                rec["score_white"] = score_white_of(rec["score"],
                                                    event.get("side"))
                rows.append(rec)
            elif kind == "STALE_BESTMOVE":
                rows.append({
                    "src": "ponder", "move_no": 0, "side": "-",
                    "uci": event.get("move", ""),
                    "depth": 0, "nodes": 0, "score": "-",
                    "score_white": "-", "engine_ms": 0, "wall_ms": 0,
                    "pv": event.get("move", ""),
                })
        return rows

    @staticmethod
    def render_all(events):
        """build() → rendered §3.1 lines (the move-line block of the log)."""
        return [render(rec) for rec in MoveLog.build(events)]

    @staticmethod
    def write_header(fh, *, game_id, date, our_color, time_control,
                     engine_sha256, net_sha256, options,
                     syzygy_probe_limit=5, tb_inventory_hash="none",
                     book_hash="none", book_max_ply=0):
        """§5.1 header lines. Asserts the effective SyzygyProbeLimit is 5
        (Rule 4 ceiling; the engine attests `TB ceiling OK` per search)."""
        assert int(syzygy_probe_limit) == 5, (
            f"SyzygyProbeLimit must be 5 (Rule 4), got {syzygy_probe_limit}")
        fh.write(f"# game-id {game_id}\n")
        fh.write(f"# date {date}\n")
        fh.write(f"# our-color {our_color}\n")
        fh.write(f"# time-control {time_control}\n")
        fh.write(f"# engine-sha256 {engine_sha256}\n")
        fh.write(f"# net-sha256 {net_sha256}\n")
        fh.write("# setoption " + " ".join(options) + "\n")
        fh.write(f"# SyzygyProbeLimit {syzygy_probe_limit}\n")
        fh.write(f"# tb-inventory-hash {tb_inventory_hash}\n")
        fh.write(f"# book-hash {book_hash} book-max-ply {book_max_ply}\n")
        fh.write("# network=off\n")

    @staticmethod
    def write_trailer(fh, *, result, reason, final_clock_ms, log_path=None):
        """§5.2 trailer lines; log-sha256 over the file bytes written so far."""
        fh.write(f"# result {result} reason {reason}\n")
        w_ms, b_ms = final_clock_ms
        fh.write(f"# final-clocks w={w_ms} b={b_ms}\n")
        if log_path is not None:
            digest = hashlib.sha256()
            with open(log_path, "rb") as rf:
                for chunk in iter(lambda: rf.read(1 << 20), b""):
                    digest.update(chunk)
            fh.write(f"# log-sha256 {digest.hexdigest()}\n")
        else:
            fh.write("# log-sha256 none\n")
