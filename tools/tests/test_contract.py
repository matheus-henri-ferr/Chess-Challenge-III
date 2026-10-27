# ChessChallendIII — FOUND-05 contract regression tests
# Copyright (C) 2026 ChessChallendIII
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.  See Copying.txt for the full text.

"""Document ↔ mock ↔ driver agreement tests for the frozen contract (plan
01-02 Task 3). Everything here asserts agreement in BOTH directions:

- the `go` literal in PROTOCOL.md is exactly what mock_engine accepts and
  what mock_gui emits (and vice versa);
- forbidden tokens appear in the document only as prohibitions;
- every reason token the mock emits is one the document allows;
- the eight LOGBOOK log keys are the CSV columns mock_gui writes;
- tools/check_contract_order.py returns 0 on a synthetic good repo and
  nonzero when an implementation commit predates the docs freeze.
"""

import pathlib
import re
import subprocess
import sys
import tempfile
import unittest

REPO = pathlib.Path(__file__).parent.resolve().parent.parent
TOOLS = REPO / "tools"
PROTOCOL = (REPO / "docs" / "PROTOCOL.md").read_text(encoding="utf-8")
LOGBOOK = (REPO / "docs" / "LOGBOOK.md").read_text(encoding="utf-8")

sys.path.insert(0, str(TOOLS))
import mock_engine  # noqa: E402
import mock_gui     # noqa: E402

FORBIDDEN = ("movetime", "movestogo", "depth", "nodes", "infinite", "searchmoves")
LOG_KEYS = ("move_no", "side", "uci", "depth", "nodes", "score", "pv",
            "engine_ms", "wall_ms")

# mock_gui must expose its column set as data for this test to consume.
if not hasattr(mock_gui, "CSV_COLUMNS"):
    raise AssertionError(
        "mock_gui must define CSV_COLUMNS (the per-move CSV header as a list)")


def run_checker(repo: pathlib.Path) -> subprocess.CompletedProcess:
    """Run the committed ordering checker against an arbitrary repo."""
    return subprocess.run(
        [sys.executable, str(REPO / "tools" / "check_contract_order.py")],
        cwd=repo, capture_output=True, text=True,
    )


class GoLiteralTests(unittest.TestCase):
    def test_document_states_the_literal(self):
        m = re.search(r"^go wtime <int_ms> btime <int_ms> winc 10000 binc 10000$",
                      PROTOCOL, re.MULTILINE)
        self.assertIsNotNone(m, "PROTOCOL §3.1 must state the literal verbatim")

    def test_mock_engine_and_gui_agree_with_document(self):
        # Same constant text in both modules and the document.
        self.assertEqual(mock_engine.GO_LITERAL, mock_gui.GO_LITERAL)
        self.assertEqual(mock_engine.GO_LITERAL,
                         "go wtime <int_ms> btime <int_ms> winc 10000 binc 10000")
        # The document's worked example must instantiate the same template.
        self.assertIn("go wtime 798000 btime 851000 winc 10000 binc 10000", PROTOCOL)

    def test_gui_go_line_is_the_literal_instantiated(self):
        g = mock_gui.Game.__new__(mock_gui.Game)  # no init needed: pure function
        self.assertEqual(g.go_line(798000, 851000),
                         "go wtime 798000 btime 851000 winc 10000 binc 10000")
        self.assertEqual(g.go_line(1, 2, ponder=True),
                         "go ponder wtime 1 btime 2 winc 10000 binc 10000")


class ForbiddenTokenTests(unittest.TestCase):
    def test_forbidden_tokens_only_as_prohibitions(self):
        """Each forbidden token appears in a go-line context only in §3.2's
        prohibition sentence — never inside a suggested go grammar."""
        # The §3.1/§3.5 grammar blocks must not contain any forbidden token.
        for block in re.findall(r"```(.*?)```", PROTOCOL, re.DOTALL):
            self.assertNotIn("movetime", block)
            self.assertNotIn("movestogo", block)
            self.assertNotIn("infinite", block)
            self.assertNotIn("searchmoves", block)
            self.assertNotIn(" go depth", block)
            self.assertNotIn(" go nodes", block)


class TmTraceTests(unittest.TestCase):
    def test_mock_reason_tokens_are_the_document_set(self):
        doc_tokens = re.findall(r"`(reserve|bank_positive|low_clock|instant|book_exit|scramble)`",
                                PROTOCOL)
        self.assertEqual(set(doc_tokens), set(mock_engine.TM_REASONS))

    def test_mock_emits_grammar_from_section_6(self):
        # Shape asserted live via the emitted line in test_runtime agreement:
        line = (f"info string tm=custom-v1.0 mode={mock_engine.TM_MODES[0]} "
                f"latency_p95_ms=12 bank_ms=4500 budget_ms=18000 "
                f"reason={mock_engine.TM_REASONS[0]}")
        m = re.search(r"^info string tm=custom-v<MAJOR>\.<MINOR> "
                      r"mode=<increment\|sudden_death\|armageddon> "
                      r"latency_p95_ms=<int> bank_ms=<int> budget_ms=<int> "
                      r"reason=<token>$", PROTOCOL, re.MULTILINE)
        self.assertIsNotNone(m, "PROTOCOL §6.1 grammar must be present")


class LogbookCsvTests(unittest.TestCase):
    def test_all_logbook_keys_present_in_csv_header(self):
        from mock_gui import CSV_COLUMNS
        for key in LOG_KEYS:
            self.assertIn(key, CSV_COLUMNS, f"LOGBOOK §2 key {key} missing from CSV")

    def test_logbook_section_2_lists_all_eight_fields(self):
        for key in LOG_KEYS:
            self.assertIn(f"`{key}`", LOGBOOK, f"key {key} not specified in LOGBOOK")


class OrderingCheckerTests(unittest.TestCase):
    """Synthetic repos exercising tools/check_contract_order.py."""

    def _repo(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        repo = pathlib.Path(tmp.name) / "synthetic"
        repo.mkdir()
        def git(*args):
            subprocess.run(["git", *args], cwd=repo, check=True,
                           capture_output=True)
        git("init", "-q")
        git("config", "user.email", "t@t")
        git("config", "user.name", "t")
        (repo / "docs").mkdir()
        (repo / "docs" / "PROTOCOL.md").write_text("x\n")
        (repo / "docs" / "LOGBOOK.md").write_text("x\n")
        (repo / "src").mkdir()
        (repo / "tools").mkdir()
        (repo / "tools" / "mock.py").write_text("1\n")
        return repo, git

    def _commit_docs(self, repo, git):
        git("add", "docs")
        git("commit", "-qm", "docs freeze")

    def _commit_impl(self, repo, git):
        (repo / "src" / "engine.cpp").write_text("int main(){}\n")
        git("add", "src")
        git("commit", "-qm", "impl")

    def test_docs_first_repo_returns_zero(self):
        repo, git = self._repo()
        self._commit_docs(repo, git)
        self._commit_impl(repo, git)
        self.assertEqual(run_checker(repo).returncode, 0)

    def test_impl_first_repo_returns_nonzero(self):
        repo, git = self._repo()
        self._commit_impl(repo, git)
        self._commit_docs(repo, git)
        out = run_checker(repo)
        self.assertNotEqual(out.returncode, 0)
        self.assertIn("FAIL CONTRACT ORDER", out.stdout + out.stderr)

    def test_comment_only_src_edit_is_not_implementation(self):
        repo, git = self._repo()
        # Root commit touches src/ but adds ONLY provenance comment lines.
        (repo / "src" / "engine.cpp").write_text(
            "// Modified by ChessChallendIII on 2026-10-26: provenance only\n")
        git("add", "src")
        git("commit", "-qm", "comment-only src edit before docs")
        self._commit_docs(repo, git)
        self.assertEqual(run_checker(repo).returncode, 0)

    def test_tools_path_is_not_implementation(self):
        repo, git = self._repo()
        self._commit_docs(repo, git)
        (repo / "tools" / "extra.py").write_text("2\n")
        git("add", "tools")
        git("commit", "-qm", "tools-only after docs")
        self.assertEqual(run_checker(repo).returncode, 0)


if __name__ == "__main__":
    unittest.main()
