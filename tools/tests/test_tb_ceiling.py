# ChessChallendIII — LIMIT-01 TB ceiling tests
# Copyright (C) 2026 ChessChallendIII
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.  See Copying.txt for the full text.

"""End-to-end tests for the Rule 4 tablebase ceiling (plan 01-03 Task 1).

Every test spawns the built binary src/stockfish and asserts on its stdout /
exit code. Nothing here touches the setoption return path: ucioption.cpp
silently keeps the previous value on an out-of-range assignment, so only the
option listing and the attestation line prove the clamp.
"""

import pathlib
import subprocess
import sys
import tempfile
import unittest

REPO = pathlib.Path(__file__).parent.resolve().parent.parent
BINARY = REPO / "src" / "stockfish"

BENCH_NODES = "2497913"


def run_uci(commands: str, timeout: float = 60.0) -> subprocess.CompletedProcess:
    return subprocess.run(
        [str(BINARY)], input=commands, capture_output=True, text=True,
        timeout=timeout, cwd=REPO,
    )


@unittest.skipUnless(BINARY.is_file(), "src/stockfish not built")
class TBCeilingTests(unittest.TestCase):
    def test_01_option_line_is_clamped(self):
        out = run_uci("uci\nquit\n").stdout
        self.assertIn(
            "option name SyzygyProbeLimit type spin default 5 min 0 max 5",
            out.splitlines(),
        )

    def test_02_out_of_range_7_clamped_and_attested(self):
        out = run_uci(
            "setoption name SyzygyProbeLimit value 7\n"
            "position startpos\ngo depth 1\nquit\n"
        ).stdout
        self.assertIn("info string TB ceiling OK: SyzygyProbeLimit=5", out)

    def test_03_zero_is_compliant_and_attested(self):
        out = run_uci(
            "setoption name SyzygyProbeLimit value 0\n"
            "position startpos\ngo depth 1\nquit\n"
        ).stdout
        self.assertIn("info string TB ceiling OK: SyzygyProbeLimit=0", out)

    def test_04_six_piece_directory_is_fatal(self):
        for name in ("KQRRBvK.rtbw", "KQRRBvK.rtbz"):  # WDL and DTZ-only
            with self.subTest(file=name):
                with tempfile.TemporaryDirectory() as tmp:
                    tb = pathlib.Path(tmp) / "tb"
                    tb.mkdir()
                    (tb / name).touch()  # 6 piece codes, zero-byte is enough
                    p = run_uci(f"setoption name SyzygyPath value {tb}\nquit\n")
                    self.assertEqual(p.returncode, 1, p.stdout)
                    self.assertIn(
                        "info string CRITICAL ERROR: TB CEILING VIOLATION:", p.stdout)

    def test_05_five_piece_directory_is_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            tb = pathlib.Path(tmp) / "tb"
            tb.mkdir()
            (tb / "KQvK.rtbw").touch()
            out = run_uci(f"setoption name SyzygyPath value {tb}\nquit\n").stdout
            self.assertNotIn("TB CEILING VIOLATION", out)

    def test_06_bench_unchanged(self):
        p = subprocess.run([str(BINARY), "bench"], capture_output=True, text=True,
                           timeout=300, cwd=REPO)
        combined = p.stdout + p.stderr
        self.assertIn(f"Nodes searched  : {BENCH_NODES}", combined)


if __name__ == "__main__":
    unittest.main()
