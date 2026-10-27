#!/usr/bin/env python3
# ChessChallendIII — log_lint: the fail-closed Rule 9 linter (plan 02-03)
# Copyright (C) 2026 ChessChallendIII
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.  See Copying.txt for the full text.

"""log_lint — LOGBOOK §6 contract, fail closed (no WARN tier exists).

Every check is a failure with a NAMED reason:
  - all ten keys (src, the eight §2 fields, score_white) present per line;
  - move_no monotonically non-decreasing; side alternates w/b (first
    mover colour from the header's our-color);
  - uci legal in the replayed position — every move is pushed through a
    fresh chess.Board from startpos, the same replay the engine got
    (T-02-12: a log that claims an impossible move fails);
  - pv non-empty (the move itself counts for book/tb);
  - wall_ms >= engine_ms (T-02-13 re-check);
  - no src outside the §4 set (SRC_SET);
  - header present with all §5.1 fields; trailer present with
    result/reason/clocks/sha256 (§5).

Lines starting with the reserved `# ` prefix are non-move records
(RESYNC's Phase 3 representation lands there) — lint skips them except
for the header/trailer structural checks.

CLI: `python3 -m console.log.lint <path>` → zero failures prints
`OK LOG_LINT` and exits 0; otherwise prints each failure and exits 1
(doctor's exit-1-iff-any-FAIL discipline).
"""

import chess
from chess import IllegalMoveError, InvalidMoveError

from console.log.movelog import SRC_SET

_LINE_KEYS = ("src", "move_no", "side", "uci", "depth", "nodes", "score",
              "score_white", "engine_ms", "wall_ms", "pv")

_HEADER_FIELDS = ("# game-id", "# date", "# our-color", "# time-control",
                  "# engine-sha256", "# net-sha256", "# setoption",
                  "# SyzygyProbeLimit", "# tb-inventory-hash", "# book-hash",
                  "# network=off")

_TRAILER_FIELDS = ("# result", "# final-clocks", "# log-sha256")


def _parse_header(lines):
    """Header dict from `# key value` lines; our-color drives alternation."""
    header = {}
    for line in lines:
        if not line.startswith("# ") or line == "# network=off":
            continue
        parts = line[2:].split(None, 1)
        if len(parts) == 2:
            header.setdefault(parts[0], parts[1])
    return header


def lint_log(path):
    """Lint one .log file → list of failure strings (empty = certified).

    Replay discipline (Pattern 5): every `uci` is pushed through a fresh
    chess.Board from startpos; a parse or legality failure names the move
    and the ply it died at. All checks run — one bad line never masks
    another's failure (fail closed, collect everything).
    """
    failures = []
    with open(path, "r", encoding="utf-8") as fh:
        lines = [line.rstrip("\n") for line in fh if line.strip()]

    header = _parse_header(lines)
    for field in _HEADER_FIELDS:
        if field == "# network=off":
            if "# network=off" not in lines:
                failures.append("header missing network=off")
        elif not any(line.startswith(field) for line in lines):
            failures.append(f"header missing {field[2:]}")
    for field in _TRAILER_FIELDS:
        if not any(line.startswith(field) for line in lines):
            failures.append(f"trailer missing {field[2:]}")

    first_mover = header.get("our-color", "w")
    expect_side = first_mover if first_mover in ("w", "b") else "w"

    board = chess.Board()
    prev_move_no = None
    move_rows = [line for line in lines if not line.startswith("#")]
    for idx, line in enumerate(move_rows, start=1):
        where = f"line {idx}"
        # Token-walk with continuation: score and score_white carry a
        # space inside their value (`cp 35`, `mate -3 lowerbound`) and pv
        # is space-separated by definition (§3.2) — every token after a
        # known key that is not itself `key=value` continues that value.
        pairs = {}
        last_key = None
        for token in line.split(" "):
            key, sep, value = token.partition("=")
            if sep and key in _LINE_KEYS:
                pairs[key] = value
                last_key = key
            elif last_key is not None:
                pairs[last_key] += " " + token
            else:
                failures.append(f"{where}: malformed token {token!r} "
                                f"(key=value expected)")
        missing = [key for key in _LINE_KEYS if key not in pairs]
        if missing:
            failures.append(f"{where}: missing keys {', '.join(missing)}")
            continue
        src = pairs["src"]
        if src not in SRC_SET:
            failures.append(f"{where}: src={src!r} outside the §4 set "
                            f"{SRC_SET}")
        try:
            move_no = int(pairs["move_no"])
        except ValueError:
            failures.append(f"{where}: move_no {pairs['move_no']!r} not int")
            move_no = None
        if move_no is not None:
            if prev_move_no is not None and move_no < prev_move_no:
                failures.append(f"{where}: move_no {move_no} < previous "
                                f"{prev_move_no} (monotonic non-decreasing)")
            prev_move_no = move_no
        side = pairs["side"]
        if side not in ("w", "b"):
            failures.append(f"{where}: side {side!r} not w|b")
        elif side != expect_side:
            failures.append(f"{where}: side {side} breaks w/b alternation "
                            f"(expected {expect_side})")
        else:
            expect_side = "b" if side == "w" else "w"
        try:
            engine_ms = int(pairs["engine_ms"])
            wall_ms = int(pairs["wall_ms"])
        except ValueError:
            failures.append(f"{where}: engine_ms/wall_ms not int "
                            f"({pairs['engine_ms']!r}/{pairs['wall_ms']!r})")
        else:
            if wall_ms < engine_ms:
                failures.append(
                    f"{where}: wall_ms {wall_ms} < engine_ms {engine_ms} "
                    f"(impossible timing, §2.2)")
        if not pairs["pv"]:
            failures.append(f"{where}: pv empty (§6.1)")
        uci = pairs["uci"]
        if uci == "(none)":
            if src != "none":
                failures.append(f"{where}: uci=(none) requires src=none")
            if not pairs["score"] or pairs["score"] == "-":
                failures.append(f"{where}: terminal row needs a non-empty "
                                f"score (§4.6)")
            continue  # terminal row: nothing to replay
        try:
            board.push_uci(uci)
        except (InvalidMoveError, IllegalMoveError, ValueError) as exc:
            failures.append(f"{where}: uci {uci!r} not legal at ply "
                            f"{len(board.move_stack)}: {exc}")
    return failures


def main(argv=None):
    import sys
    argv = list(sys.argv[1:]) if argv is None else list(argv)
    if len(argv) != 1:
        print("usage: python3 -m console.log.lint <game.log>", flush=True)
        return 2
    try:
        failures = lint_log(argv[0])
    except OSError as exc:
        print(f"LINT ERROR: {exc}", flush=True)
        return 1
    if failures:
        for failure in failures:
            print(f"FAIL {failure}", flush=True)
        print(f"LOG_LINT FAILED: {len(failures)} failure(s)", flush=True)
        return 1
    print("OK LOG_LINT", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
