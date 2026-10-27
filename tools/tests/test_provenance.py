# ChessChallendIII — FOUND-03 PROVENANCE checker tests
# Copyright (C) 2026 ChessChallendIII
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.  See Copying.txt for the full text.

"""Unit tests for tools/check_provenance.py (plan 01-01 Task 2).

Each test mutates a TEMP copy of PROVENANCE.md — never the committed file —
and asserts the checker's exit code on that copy.
"""

import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO = pathlib.Path(__file__).parent.resolve().parent.parent
CHECKER = REPO / "tools" / "check_provenance.py"
PROVENANCE = REPO / "PROVENANCE.md"

NET_BYTES = "98511183"
NET_SHA = "1a298aa575a085434d29027978dc36867fe9c5bcea9376654b7a8eba1e52dfc2"


def run_checker(path: pathlib.Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(CHECKER), str(path)],
        cwd=REPO, capture_output=True, text=True,
    )


class ProvenanceCheckerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.copy = pathlib.Path(self.tmp.name) / "PROVENANCE.md"
        shutil.copyfile(PROVENANCE, self.copy)

    def tearDown(self):
        self.tmp.cleanup()

    def test_01_passes_on_committed_file_and_fails_on_wrong_net_bytes(self):
        self.assertEqual(run_checker(PROVENANCE).returncode, 0)
        text = self.copy.read_text(encoding="utf-8")
        self.assertIn(f"| Bytes | {NET_BYTES} |", text)
        self.copy.write_text(text.replace(f"| Bytes | {NET_BYTES} |", "| Bytes | 98511182 |"),
                             encoding="utf-8")
        self.assertNotEqual(run_checker(self.copy).returncode, 0)

    def test_02_fails_when_non_authorship_marker_removed(self):
        text = self.copy.read_text(encoding="utf-8")
        self.assertIn("NOT AUTHORED BY THE TEAM", text)
        self.copy.write_text(text.replace("NOT AUTHORED BY THE TEAM", "network by the team"),
                             encoding="utf-8")
        self.assertNotEqual(run_checker(self.copy).returncode, 0)

    def test_03_fails_on_missing_shipped_value_and_on_fastchess_marked_shipped(self):
        # A dependency row missing its Shipped? cell (6 cells instead of 7):
        # drop one cell value from the fastchess row.
        text = self.copy.read_text(encoding="utf-8")
        lines = text.splitlines()
        out = []
        for line in lines:
            if line.startswith("| fastchess |"):
                cells = line.split("|")
                # cells: ['', name, version, pin, sha, license, shipped, purpose, '']
                del cells[6]
                line = "|".join(cells)
            out.append(line)
        self.copy.write_text("\n".join(out) + "\n", encoding="utf-8")
        self.assertNotEqual(run_checker(self.copy).returncode, 0)

        # fastchess marked shipped = yes must fail (dev-only, never in the engine
        # tree). Reset to the pristine copy first: the first mutation removed
        # the shipped cell this second mutation needs to flip.
        self.copy.write_text(text, encoding="utf-8")
        lines = text.splitlines()
        out = []
        replaced = False
        for line in lines:
            if line.startswith("| fastchess |") and "| no |" in line:
                line = line.replace("| no |", "| yes |")
                replaced = True
            out.append(line)
        self.assertTrue(replaced, "fastchess row must carry a '| no |' shipped cell")
        self.copy.write_text("\n".join(out) + "\n", encoding="utf-8")
        self.assertNotEqual(run_checker(self.copy).returncode, 0)

    def test_04_fails_on_six_piece_tablebase_filename(self):
        text = self.copy.read_text(encoding="utf-8")
        # Inject a 6-man inventory line into the §2.1 code block.
        self.assertIn("### 2.1 Tablebase inventory", text)
        lines = text.splitlines()
        out = []
        injected = False
        for line in lines:
            out.append(line)
            if not injected and line.strip().startswith("```") and "### 2.1" not in line:
                pass
        # Simpler: append after the inventory header's code fence.
        text = text.replace(
            "### 2.1 Tablebase inventory",
            "### 2.1 Tablebase inventory\n\n"
            "```\n"
            f"{'a'*64}  123456  KQRRBvK.rtbw\n"
            "```",
            1,
        )
        self.copy.write_text(text, encoding="utf-8")
        self.assertNotEqual(run_checker(self.copy).returncode, 0)

    def test_05_vendored_chess_imports_and_manifest_verifies(self):
        r = subprocess.run(
            [sys.executable, "-c",
             "import chess, chess.engine, chess.polyglot, chess.syzygy; "
             "assert chess.__version__ == '1.11.2', chess.__version__; print('ok')"],
            cwd=REPO, capture_output=True, text=True,
            env={"PYTHONPATH": str(REPO / "vendor"), "PATH": "/usr/bin:/bin:/usr/local/bin",
                 "HOME": "/tmp"},
        )
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("ok", r.stdout)

        sums = REPO / "vendor" / "chess" / "SHA256SUMS"
        self.assertTrue(sums.is_file(), "vendor/chess/SHA256SUMS must exist")
        v = subprocess.run(["sha256sum", "-c", "SHA256SUMS", "--quiet"],
                           cwd=REPO / "vendor" / "chess", capture_output=True, text=True)
        self.assertEqual(v.returncode, 0, v.stdout + v.stderr)

        # The net identity literals must match the on-disk net.
        net = REPO / "src" / "nn-1a298aa575a0.nnue"
        self.assertEqual(net.stat().st_size, int(NET_BYTES))
        self.assertIn(NET_SHA, PROVENANCE.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
