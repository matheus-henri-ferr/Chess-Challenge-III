#!/usr/bin/env python3
# ChessChallendIII — whitelisted UCI line parser (plan 02-01)
# Copyright (C) 2026 ChessChallendIII
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.  See Copying.txt for the full text.

"""Line → event whitelist for the engine stdout stream (PROTOCOL §5.1, §9.3).

The engine is a hostile peer: every line is untrusted text. Only the
whitelisted prefixes below produce typed events; anything else becomes an
inert {"type": "garbage"} event (tolerated, never raising — §9.3). No
whole-line regex on info lines: token-walk only (bound flags, `info string`
and the PV-last ordering defeat naive regexes).

`time` stays wire MILLISECONDS (PROTOCOL §5.2) — never converted to seconds.
`score` stays the verbatim STM-POV string including a trailing
`lowerbound`/`upperbound` flag and the two-token `cp <int>` / `mate <int>`
shape (PROTOCOL §5.3). `tm=`-prefixed `info string` payloads pass through
unchanged for Phase 4 (PROTOCOL §6).
"""

_INFO_INT_FIELDS = ("depth", "seldepth", "multipv", "nodes", "nps",
                    "hashfull", "tbhits", "time")
_BOUNDS = ("lowerbound", "upperbound")


def bestmove_of(line):
    # "bestmove e2e4 ponder c7c5" — the move token is the FIRST word after
    # bestmove; a ponder suffix belongs to the engine, not the move list.
    # "bestmove (none)" is legal (PROTOCOL §7.2) and is returned verbatim.
    tokens = line[len("bestmove "):].split()
    if not tokens:
        return "", None
    move = tokens[0]
    ponder = None
    if len(tokens) >= 3 and tokens[1] == "ponder":
        ponder = tokens[2]
    return move, ponder


def _parse_info(tokens):
    event = {"type": "info"}
    i, n = 0, len(tokens)
    while i < n:
        tok = tokens[i]
        if tok == "string":
            # info string <payload> — one event; `tm=` payloads (PROTOCOL §6.1)
            # pass through unchanged for Phase 4.
            event["string"] = " ".join(tokens[i + 1:])
            event["is_tm_trace"] = event["string"].startswith("tm=")
            break
        if tok == "score" and i + 2 < n:
            # Two-token shape: cp <int> | mate <int> (PROTOCOL §5.1).
            kind, value = tokens[i + 1], tokens[i + 2]
            if kind in ("cp", "mate") and value.lstrip("+-").isdigit():
                score = f"{kind} {value}"
                j = i + 3
                if j < n and tokens[j] in _BOUNDS:
                    score += f" {tokens[j]}"  # bound flag verbatim (§5.3)
                    j += 1
                event["score"] = score
                event["score_kind"] = kind
                event["score_value"] = int(value)
                i = j
                continue
        if tok == "pv":
            # Raw remainder after ` pv ` (PROTOCOL §5.4) — recorded verbatim.
            event["pv"] = " ".join(tokens[i + 1:])
            break
        if tok in _INFO_INT_FIELDS and i + 1 < n and tokens[i + 1].lstrip("+-").isdigit():
            event[tok] = int(tokens[i + 1])  # wire milliseconds stay ms (§5.2)
            i += 2
            continue
        i += 1
    return event


def parse_line(line):
    """One engine stdout line → one event dict (or None for blank lines).

    Whitelist (PROTOCOL §5.1 + §9.3): info, info string, bestmove, id,
    option, uciok, readyok. Everything else → {"type": "garbage", "line": ...}.
    """
    if not line.strip():
        return None
    tokens = line.split()
    head = tokens[0]

    if head == "info":
        return _parse_info(tokens)
    if head == "bestmove":
        move, ponder = bestmove_of(line)
        return {"type": "bestmove", "move": move, "ponder": ponder}
    if head == "id" and len(tokens) >= 2:
        return {"type": "id", "key": tokens[1],
                "value": " ".join(tokens[2:])}
    if head == "option" and len(tokens) >= 3 and tokens[1] == "name":
        # option name <X> type <T> ... — X may contain spaces ("Move Overhead").
        try:
            tidx = tokens.index("type", 2)
        except ValueError:
            return {"type": "garbage", "line": line}
        return {"type": "option", "name": " ".join(tokens[2:tidx]),
                "spec": " ".join(tokens[tidx + 1:])}
    if head == "uciok":
        return {"type": "uciok"}
    if head == "readyok":
        return {"type": "readyok"}
    return {"type": "garbage", "line": line}
