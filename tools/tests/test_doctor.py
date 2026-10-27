# ChessChallendIII — LIMIT-04 doctor.py tests
# Copyright (C) 2026 ChessChallendIII
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.  See Copying.txt for the full text.

"""Behaviour tests for tools/doctor.py (plan 01-03 Task 2).

Each test runs the real script in a subprocess. The plan's seven behaviours:
  1. --asset /srv/tb/3-4-5 → exit 0 (path valid even when directory absent)
  2. --asset https://… → exit 1, reason names the remote scheme
  3. s3:// / git@ / ftp:// → exit 1 each
  4. relative / ~ / $VAR → exit 1, reason names non-absolute or expandable
  5. 6-piece tablebase dir → exit 1 naming the file; 5-piece dir → exit 0
  6. --json failed list matches exit code; human report one line per check
  7. real tree passes end to end; doctor never sends `go`
"""

import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

REPO = pathlib.Path(__file__).parent.resolve().parent.parent
DOCTOR = REPO / "tools" / "doctor.py"


def run_doctor(*args: str, cwd: pathlib.Path = REPO) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(DOCTOR), *args], cwd=cwd,
        capture_output=True, text=True, timeout=300,
    )


class AssetPathTests(unittest.TestCase):
    def test_01_absolute_path_passes_even_if_absent(self):
        p = run_doctor("--asset", "/srv/tb/3-4-5")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)

    def test_02_https_rejected(self):
        p = run_doctor("--asset", "https://example.com/tb")
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("https", (p.stdout + p.stderr).lower())

    def test_03_other_remote_schemes_rejected(self):
        for asset in ("s3://bucket/tb", "git@host:repo", "ftp://host/tb"):
            with self.subTest(asset=asset):
                p = run_doctor("--asset", asset)
                self.assertNotEqual(p.returncode, 0)

    def test_04_relative_home_var_rejected(self):
        for asset in ("tb/3-4-5", "~/tb", "$HOME/tb"):
            with self.subTest(asset=asset):
                p = run_doctor("--asset", asset)
                self.assertNotEqual(p.returncode, 0)
                low = (p.stdout + p.stderr).lower()
                self.assertTrue("absolute" in low or "expand" in low, low)


class TablebaseContentTests(unittest.TestCase):
    def test_05_six_piece_dir_fails_five_piece_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = pathlib.Path(tmp) / "bad"
            bad.mkdir()
            (bad / "KQRRBvK.rtbw").touch()   # 6 piece codes
            (bad / "KQvK.rtbz").touch()      # 3
            p = run_doctor("--asset", str(bad))
            self.assertNotEqual(p.returncode, 0)
            self.assertIn("KQRRBvK", p.stdout)

            good = pathlib.Path(tmp) / "good"
            good.mkdir()
            (good / "KQvK.rtbw").touch()     # 3
            (good / "KQvKvK.rtbz").touch()   # 5
            p = run_doctor("--asset", str(good))
            self.assertEqual(p.returncode, 0, p.stdout)


class JsonAndRealTreeTests(unittest.TestCase):
    def test_06_json_matches_exit_code(self):
        p = run_doctor("--asset", "https://example.com/tb", "--json")
        self.assertNotEqual(p.returncode, 0)
        report = json.loads(p.stdout)
        self.assertTrue(report["failed"], "json.failed empty but exit nonzero")

        q = run_doctor("--json")
        self.assertEqual(q.returncode, 0, q.stdout)
        report = json.loads(q.stdout)
        self.assertFalse(report["failed"], report["failed"])

        # Human report: one line per check, PASS/FAIL/WARN/SKIP prefix.
        h = run_doctor()
        for line in h.stdout.splitlines():
            if line.strip():
                self.assertRegex(line, r"^(PASS|FAIL|WARN|SKIP)")

    def test_07_real_tree_passes_and_never_searches(self):
        p = run_doctor()
        self.assertEqual(p.returncode, 0, p.stdout)
        self.assertNotIn("bestmove", p.stdout)  # doctor never starts a search


if __name__ == "__main__":
    unittest.main()
