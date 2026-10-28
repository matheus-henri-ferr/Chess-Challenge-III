#!/usr/bin/env python3
# ChessChallendIII — MoveLog projection + fail-closed log_lint tests (plan 02-03)
# Copyright (C) 2026 ChessChallendIII
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.  See Copying.txt for the full text.

"""MoveLog + lint tests (plan 02-03 Task 2, TDD — written before impl).

Covers the plan's acceptance criteria:
  - rendered line key order equals LOG_KEYS + src + score_white, asserted
    BOTH directions against tools/tests/test_contract.py's frozen constant;
  - every §4 variant fill asserted per row (search full fields, opp zeros,
    none terminal with non-empty score, ponder present);
  - bound-flag scores (`cp 35 lowerbound`, `mate 3`) round-trip verbatim
    while score_white negates ONLY the number, flag kept verbatim (A4);
  - lint failure fixtures: missing key (names the key), side alternation
    break, wall_ms < engine_ms, src=banana, missing header/trailer — each
    produces a NAMED failure; the golden full-game log passes with zero
    failures; the lint CLI exit codes asserted both ways (0 / 1);
  - MoveLog is a pure projection: build(events) folds journal records,
    never a parallel history.
"""

import pathlib
import subprocess
import sys
import tempfile
import unittest

REPO = pathlib.Path(__file__).parent.resolve().parent.parent
sys.path.insert(0, str(REPO / "vendor"))
sys.path.insert(0, str(REPO / "console" / "src"))

import chess  # noqa: E402

from console.log.lint import lint_log  # noqa: E402
from console.log.movelog import (  # noqa: E402
    LOG_KEYS, SRC_SET, MoveLog, render, score_white_of)

TOOLS = REPO / "tools" / "tests" / "test_contract.py"
FIXTURES = pathlib.Path(__file__).parent / "fixtures"

# The eleven §3.1 key names (the render-order agreement target).
_RENDER_KEY_SET = {"src", "move_no", "side", "uci", "depth", "nodes",
                   "score", "score_white", "engine_ms", "wall_ms", "pv"}

HEADER_LINES = [
    "# game-id test01",
    "# date 2026-10-27",
    "# our-color w",
    "# time-control 15+10",
    "# engine-sha256 " + "a" * 64,
    "# net-sha256 " + "b" * 64,
    "# setoption Threads=1 Hash=2048 SyzygyPath=<empty> "
    "SyzygyProbeLimit=5 Move_Overhead=100 Ponder=false",
    "# SyzygyProbeLimit 5",
    "# tb-inventory-hash none",
    "# book-hash none book-max-ply 0",
    "# network=off",
]

TRAILER_LINES = [
    "# result 1-0 reason checkmate",
    "# final-clocks w=123456 b=234567",
    "# log-sha256 " + "c" * 64,
]


def valid_line(src="search", move_no=1, side="w", uci="e2e4", depth=8,
               nodes=1000, score="cp 35", engine_ms=10, wall_ms=20,
               pv="e2e4 e7e5", **_):
    return (f"src={src} move_no={move_no} side={side} uci={uci} "
            f"depth={depth} nodes={nodes} score={score} "
            f"score_white={score_white_of(score)} engine_ms={engine_ms} "
            f"wall_ms={wall_ms} pv={pv}")


def write_log(rows, header=True, trailer=True):
    lines = []
    if header:
        lines.extend(HEADER_LINES)
    lines.extend(rows)
    if trailer:
        lines.extend(TRAILER_LINES)
    return "\n".join(lines) + "\n"


class RenderOrderTests(unittest.TestCase):
    """§3.1 key order is frozen and agreed with test_contract's constant."""

    def test_render_key_order_covers_contract_constant(self):
        """Agreement with test_contract's frozen LOG_KEYS: every §2 field
        our line carries is in the constant, spelled identically (the
        constant's tuple order is a data contract, not the line order —
        the line order is LOGBOOK §3.1 verbatim, pv last)."""
        import importlib.util
        spec = importlib.util.spec_from_file_location("tc", TOOLS)
        tc = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(tc)
        self.assertEqual(LOG_KEYS, tc.LOG_KEYS)
        self.assertTrue(set(SRC_SET) == {"search", "book", "tb", "ponder",
                                         "opp", "none"})

    def test_render_emits_keys_in_frozen_line_order(self):
        """The §3.1 LINE order (pv last) is independent of LOG_KEYS' tuple
        order — the contract constant is a set-with-canonical-spell, the
        line order is LOGBOOK §3.1 verbatim."""
        rec = {"src": "search", "move_no": 1, "side": "w", "uci": "e2e4",
               "depth": 8, "nodes": 1000, "score": "cp 35",
               "score_white": "cp 35", "engine_ms": 10, "wall_ms": 20,
               "pv": "e2e4 e7e5"}
        line = render(rec)
        self.assertEqual(
            line,
            "src=search move_no=1 side=w uci=e2e4 depth=8 nodes=1000 "
            "score=cp 35 score_white=cp 35 engine_ms=10 wall_ms=20 "
            "pv=e2e4 e7e5")
        # Keys are the `name=` tokens; pv's continuation moves ride along.
        keys = [tok for tok in line.split() if "=" in tok]
        key_names = [tok.split("=", 1)[0] for tok in keys
                     if tok.split("=", 1)[0] in _RENDER_KEY_SET]
        self.assertEqual(key_names[0], "src")
        self.assertEqual(key_names[-1], "pv")
        self.assertEqual(set(key_names),
                         {"src"} | set(LOG_KEYS) | {"score_white"})
        # Every LOGBOOK §2 key present exactly once.
        self.assertEqual(len(key_names), 11)

    def test_pv_last_unquoted(self):
        line = render({"src": "search", "move_no": 1, "side": "w",
                       "uci": "e2e4", "depth": 8, "nodes": 1,
                       "score": "cp 10", "score_white": "cp 10",
                       "engine_ms": 1, "wall_ms": 2,
                       "pv": "e2e4 e7e5 g1f3"})
        self.assertTrue(line.endswith("pv=e2e4 e7e5 g1f3"))


class VariantFillTests(unittest.TestCase):
    """§4 per-variant fills, folded by MoveLog.build from journal events."""

    def _events(self):
        return [
            {"e": "GAME_START", "game_id": "g1", "our_color": "w",
             "clock_ms": {"w": 900000, "b": 900000}},
            {"e": "MOVE_LOGGED", "src": "search", "move_no": 1, "side": "w",
             "uci": "e2e4", "depth": 12, "nodes": 50000,
             "score": "cp 35 lowerbound", "engine_ms": 980, "wall_ms": 1000,
             "pv": "e2e4 e7e5"},
            {"e": "MOVE_LOGGED", "src": "opp", "move_no": 1, "side": "b",
             "uci": "e7e5", "depth": 0, "nodes": 0, "score": "-",
             "engine_ms": 0, "wall_ms": 1500, "pv": "e7e5"},
            {"e": "STALE_BESTMOVE", "move": "a7a6", "search_id": 2},
            {"e": "MOVE_LOGGED", "src": "none", "uci": "(none)",
             "move_no": 2, "side": "w", "depth": 0, "nodes": 0,
             "score": "mate 0", "engine_ms": 0, "wall_ms": 40,
             "pv": "(none)"},
            {"e": "GAME_END", "reason": "checkmate", "result": "1-0"},
        ]

    def test_build_folds_search_opp_ponder_none(self):
        rows = MoveLog.build(self._events())
        by_src = {r["src"]: r for r in rows}
        self.assertEqual([r["src"] for r in rows],
                         ["search", "opp", "ponder", "none"])
        # search: full captured fields.
        self.assertEqual(by_src["search"]["depth"], 12)
        self.assertEqual(by_src["search"]["nodes"], 50000)
        self.assertEqual(by_src["search"]["score"], "cp 35 lowerbound")
        self.assertEqual(by_src["search"]["engine_ms"], 980)
        self.assertEqual(by_src["search"]["wall_ms"], 1000)
        # opp: §4.5 zeros (asserted on the RENDERED line too).
        opp_line = render(by_src["opp"])
        self.assertIn("depth=0", opp_line)
        self.assertIn("nodes=0", opp_line)
        self.assertIn("score=-", opp_line)
        self.assertIn("engine_ms=0", opp_line)
        self.assertIn("wall_ms=1500", opp_line)
        self.assertIn("uci=e7e5", opp_line)
        # ponder: STALE_BESTMOVE logged for the record, never announced.
        self.assertEqual(by_src["ponder"]["uci"], "a7a6")
        self.assertEqual(by_src["ponder"]["depth"], 0)
        # none: §4.6 terminal — uci=(none), non-empty score.
        self.assertEqual(by_src["none"]["uci"], "(none)")
        self.assertEqual(by_src["none"]["score"], "mate 0")
        self.assertTrue(by_src["none"]["score"])

    def test_score_white_negates_number_keeps_flag(self):
        self.assertEqual(score_white_of("cp 35"), "cp 35")
        self.assertEqual(score_white_of("cp -35"), "cp 35")
        self.assertEqual(score_white_of("mate -3"), "mate 3")
        self.assertEqual(score_white_of("cp 35 lowerbound"),
                         "cp 35 lowerbound")
        self.assertEqual(score_white_of("cp -12 upperbound"),
                         "cp 12 upperbound")
        self.assertEqual(score_white_of("-"), "-")
        # STM black with a cp score flips the sign for White's POV.
        rows = MoveLog.build([
            {"e": "MOVE_LOGGED", "src": "search", "move_no": 1, "side": "b",
             "uci": "e7e5", "depth": 8, "nodes": 100, "score": "cp -30",
             "engine_ms": 5, "wall_ms": 9, "pv": "e7e5"}])
        self.assertEqual(rows[0]["score_white"], "cp 30")

    def test_opp_line_lint_shape_wall_ge_engine(self):
        rows = MoveLog.build(self._events())
        for rec in rows:
            self.assertGreaterEqual(rec["wall_ms"], rec["engine_ms"])


class ScoreWhiteSignTests(unittest.TestCase):
    """CR-02 regression: score_white is a correct White-POV normalisation
    (LOGBOOK §2.1). UCI `score` is side-to-move POV, so a white-mover row
    is ALREADY White-POV — negation happens ONLY when the mover was black.
    The deleted `elif value < 0` branch flipped every white-mover negative
    score (the "we are worse" losing-game line) to the wrong sign."""

    def test_white_mover_negative_keeps_sign(self):
        # The live path CR-02 broke: side="w" negative STM score must stay
        # negative (White is worse) — pinned verbatim per the plan.
        self.assertEqual(score_white_of("cp -30", "w"), "cp -30")

    def test_white_mover_positive_unchanged(self):
        self.assertEqual(score_white_of("cp 30", "w"), "cp 30")

    def test_black_mover_negates_both_signs(self):
        self.assertEqual(score_white_of("cp -30", "b"), "cp 30")
        self.assertEqual(score_white_of("cp 30", "b"), "cp -30")

    def test_mate_scores_follow_same_rule(self):
        self.assertEqual(score_white_of("mate -3", "w"), "mate -3")
        self.assertEqual(score_white_of("mate 3", "b"), "mate -3")

    def test_bound_flag_rides_verbatim_under_negation(self):
        self.assertEqual(score_white_of("cp 35 lowerbound", "b"),
                         "cp -35 lowerbound")

    def test_absent_score_stays_dash(self):
        self.assertEqual(score_white_of("-", None), "-")

    def test_build_white_negative_row_pins_regression(self):
        rows = MoveLog.build([
            {"e": "MOVE_LOGGED", "src": "search", "move_no": 1, "side": "w",
             "uci": "e2e4", "depth": 8, "nodes": 100, "score": "cp -30",
             "engine_ms": 5, "wall_ms": 9, "pv": "e2e4"}])
        self.assertEqual(rows[0]["score_white"], "cp -30")


class AlternationSeedTests(unittest.TestCase):
    """CR-03 regression: side alternation seeds expect_side="w"
    unconditionally — white always moves first (LOGBOOK §1.4); the
    header's our-color is the console's colour, never the first mover.
    A valid black-side log (our-color b, white-first rows) must lint
    clean; pre-fix code failed it with 'side w breaks w/b alternation'."""

    def lint_text(self, text):
        fh = tempfile.NamedTemporaryFile("w", suffix=".log", delete=False)
        fh.write(text)
        fh.close()
        self.addCleanup(pathlib.Path(fh.name).unlink)
        return lint_log(fh.name)

    def black_side_log(self):
        header = ["# game-id black01",
                  "# date 2026-10-28",
                  "# our-color b",
                  "# time-control 1+0",
                  "# engine-sha256 " + "a" * 64,
                  "# net-sha256 " + "b" * 64,
                  "# setoption Threads=1 Hash=2048 "
                  "SyzygyProbeLimit=5 Move_Overhead=100 Ponder=false",
                  "# SyzygyProbeLimit 5",
                  "# tb-inventory-hash none",
                  "# book-hash none book-max-ply 0",
                  "# network=off"]
        rows = [valid_line(side="w", uci="e2e4"),
                valid_line(side="b", uci="e7e5", move_no=1,
                           score="cp -30"),
                valid_line(side="w", uci="g1f3", move_no=2),
                valid_line(side="b", uci="b8c6", move_no=2)]
        trailer = ["# result * reason max-plies 4 reached",
                   "# final-clocks w=60000 b=60000",
                   "# log-sha256 " + "c" * 64]
        return "\n".join(header + rows + trailer) + "\n"

    def test_valid_black_side_log_lints_clean(self):
        """# our-color b + white-first first row = a VALID log; the
        fail-closed linter must accept it with zero failures."""
        self.assertEqual(self.lint_text(self.black_side_log()), [])

    def test_black_side_alternation_still_enforced(self):
        """Seeding w unconditionally does not weaken the check: a
        black-first log (impossible game) still fails."""
        text = self.black_side_log().replace(
            'side=w uci=e2e4', 'side=b uci=e2e4', 1)
        failures = self.lint_text(text)
        self.assertTrue(any("alternation" in f for f in failures), failures)


class LintFailureTests(unittest.TestCase):
    """Every §6.1 check fails closed with a NAMED failure."""

    def lint_text(self, text):
        fh = tempfile.NamedTemporaryFile("w", suffix=".log", delete=False)
        fh.write(text)
        fh.close()
        self.addCleanup(pathlib.Path(fh.name).unlink)
        return lint_log(fh.name)

    def test_missing_key_failure_names_the_key(self):
        line = valid_line().replace(" nodes=1000", "")
        failures = self.lint_text(write_log([line]))
        self.assertTrue(any("nodes" in f for f in failures), failures)

    def test_side_alternation_break_fails(self):
        rows = [valid_line(side="w", uci="e2e4"),
                valid_line(side="w", uci="e7e5", move_no=1)]
        failures = self.lint_text(write_log(rows))
        self.assertTrue(any("side" in f for f in failures), failures)

    def test_wall_below_engine_fails(self):
        line = valid_line(engine_ms=100, wall_ms=50)
        failures = self.lint_text(write_log([line]))
        self.assertTrue(any("wall_ms" in f for f in failures), failures)

    def test_bad_src_fails(self):
        line = valid_line().replace("src=search", "src=banana", 1)
        failures = self.lint_text(write_log([line]))
        self.assertTrue(any("banana" in f for f in failures), failures)

    def test_missing_header_fails_and_missing_trailer_fails(self):
        failures = self.lint_text(write_log([valid_line()], header=False))
        self.assertTrue(any("header" in f for f in failures), failures)
        failures = self.lint_text(write_log([valid_line()], trailer=False))
        self.assertTrue(any("trailer" in f for f in failures), failures)

    def test_move_no_regression_fails(self):
        rows = [valid_line(move_no=2),
                valid_line(move_no=1, side="b", uci="e7e5")]
        failures = self.lint_text(write_log(rows))
        self.assertTrue(any("move_no" in f for f in failures), failures)

    def test_illegal_uci_replay_fails(self):
        rows = [valid_line(uci="e4e6")]
        failures = self.lint_text(write_log(rows))
        self.assertTrue(any("e4e6" in f or "legal" in f for f in failures),
                        failures)

    def test_reserved_prefix_lines_skipped(self):
        rows = ["# RESYNC applied plies=2 (operator confirmed)",
                valid_line()]
        failures = self.lint_text(write_log(rows))
        self.assertEqual(failures, [])


class LintCliTests(unittest.TestCase):
    """`python3 -m console.log.lint <path>` exit codes both ways."""

    @unittest.skipUnless((FIXTURES / "golden-game.log").exists(),
                         "golden log lands with plan 02-03 Task 3 (e2e)")
    def test_cli_ok_on_golden_log(self):
        p = subprocess.run(
            [sys.executable, "-m", "console.log.lint",
             str(FIXTURES / "golden-game.log")],
            capture_output=True, text=True, timeout=60,
            cwd=REPO,
            env={"PYTHONPATH": f"{REPO / 'vendor'}:{REPO / 'console' / 'src'}",
                 "PATH": "/usr/bin:/bin", "HOME": "/tmp"})
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn("OK LOG_LINT", p.stdout)

    def test_cli_exit_1_on_bad_log(self):
        fh = tempfile.NamedTemporaryFile("w", suffix=".log", delete=False)
        fh.write(write_log([valid_line().replace(" depth=8", "")]))  # no depth
        fh.close()
        self.addCleanup(pathlib.Path(fh.name).unlink)
        p = subprocess.run(
            [sys.executable, "-m", "console.log.lint", fh.name],
            capture_output=True, text=True, timeout=60,
            cwd=REPO,
            env={"PYTHONPATH": f"{REPO / 'vendor'}:{REPO / 'console' / 'src'}",
                 "PATH": "/usr/bin:/bin", "HOME": "/tmp"})
        self.assertEqual(p.returncode, 1, p.stdout + p.stderr)
        self.assertNotIn("OK LOG_LINT", p.stdout)
        self.assertIn("depth", p.stdout)

    def test_in_process_lint_ok_on_good_log(self):
        fh = tempfile.NamedTemporaryFile("w", suffix=".log", delete=False)
        fh.write(write_log([valid_line(),
                            valid_line(side="b", uci="e7e5", score="cp -15")]))
        fh.close()
        self.addCleanup(pathlib.Path(fh.name).unlink)
        self.assertEqual(lint_log(fh.name), [])


if __name__ == "__main__":
    unittest.main()
