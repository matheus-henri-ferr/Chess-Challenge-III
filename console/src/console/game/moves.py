#!/usr/bin/env python3
# ChessChallendIII — typed-reject move parse layer, PROTO-01 (plan 02-02)
# Copyright (C) 2026 ChessChallendIII
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.  See Copying.txt for the full text.

"""Typed-reject parse layer between the operator keyboard and the replica.

PROTO-01: strict UCI tokens only — tolerate case and spaces, reject SAN
(Nf3, e4, O-O), `0000` and malformed tokens with typed errors, and surface
every rejection with machine-readable kind + raw token (T-02-08 evidence).

Verified library edge behaviour this layer guards (RESEARCH §Parsing,
live probes on vendor/chess 1.11.2):
  - `parse_uci('0000')` returns Move.null() WITHOUT raising → the NULL
    guard runs BEFORE parse_uci (Pitfall 2);
  - `parse_uci('E2E4')` raises InvalidMoveError → normalize first;
  - SAN strings fail the length/shape gate and raise InvalidMoveError →
    MALFORMED (never route through parse_san — silent translation is a
    PROTO-01 violation);
  - `parse_uci('e2e5')` raises IllegalMoveError → ILLEGAL.

Promotion ambiguity (`e7e8` with four legal promos) is NOT silently
resolved: the Reject reason names the four legal suffixes (re-prompt, the
loop's job).
"""

import enum

import chess
from chess import IllegalMoveError, InvalidMoveError


class RejectKind(enum.Enum):
    """Typed rejection vocabulary (RESEARCH Code Examples)."""

    MALFORMED = "malformed"  # syntax: SAN-shaped, wrong length, pasted junk
    NULL = "null"            # '0000' — PROTO-01 rejects; engine terminal is '(none)'
    ILLEGAL = "illegal"      # legal syntax, illegal in the current position


class Reject(Exception):
    """One rejected token, carrying the typed kind + raw input (T-02-08)."""

    def __init__(self, kind, raw, reason):
        super().__init__(reason)
        self.kind = kind
        self.raw = raw
        self.reason = reason


def normalize_token(raw):
    """Strip → squeeze internal whitespace → lowercase (PROTO-01)."""
    return " ".join(raw.split()).lower().replace(" ", "")


def _reason_for(kind, raw, token, exc):
    if kind is RejectKind.NULL:
        return "0000 is not a move (PROTO-01); the engine's terminal token is (none)"
    if kind is RejectKind.MALFORMED:
        return f"not a UCI move: {token!r} (expected e2e4 form; SAN like 'Nf3' is not accepted)"
    if kind is RejectKind.ILLEGAL:
        return f"illegal in the current position: {token!r}"
    return f"rejected: {raw!r}"


def operator_move(board, raw):
    """One operator token → a legal chess.Move, or Reject (never both).

    Order is load-bearing (Pitfall 2): normalize → 0000 guard BEFORE
    parse_uci → parse_uci with the two error classes mapped to kinds.
    """
    token = normalize_token(raw)
    if not token:
        raise Reject(RejectKind.MALFORMED, raw, "empty input is not a move")
    if token == "0000":
        raise Reject(RejectKind.NULL, raw,
                     _reason_for(RejectKind.NULL, raw, token, None))
    if len(token) not in (4, 5):
        raise Reject(
            RejectKind.MALFORMED, raw,
            f"not a UCI move: {token!r} (expected e2e4 form; SAN like 'Nf3' is not accepted)")
    # Promotion ambiguity: a bare move to a promotion square with several
    # legal promos must re-prompt naming the four suffixes, never guess
    # (RESEARCH §Parsing; verified: parse_uci('a7a8') itself raises
    # IllegalMoveError, so this gate must run before parse_uci).
    if len(token) == 4:
        from_square = chess.parse_square(token[0:2])
        to_square = chess.parse_square(token[2:4])
        promo_matches = [
            m for m in board.legal_moves
            if m.from_square == from_square and m.to_square == to_square
            and m.promotion is not None
        ]
        if promo_matches:
            raise Reject(
                RejectKind.MALFORMED, raw,
                f"promotion needs a suffix: {token}q, {token}r, {token}b or {token}n")
    try:
        return board.parse_uci(token)
    except InvalidMoveError as exc:
        raise Reject(RejectKind.MALFORMED, raw,
                     _reason_for(RejectKind.MALFORMED, raw, token, exc)) from exc
    except IllegalMoveError as exc:
        raise Reject(RejectKind.ILLEGAL, raw,
                     _reason_for(RejectKind.ILLEGAL, raw, token, exc)) from exc


def announce_form(uci):
    """e2e4 → E2-E4; e7e8q → E7-E8=Q; e1g1 → E1-G1. `(none)` never reaches here."""
    frm, to = uci[0:2].upper(), uci[2:4].upper()
    promo = f"={uci[4].upper()}" if len(uci) == 5 else ""
    return f"{frm}-{to}{promo}"
