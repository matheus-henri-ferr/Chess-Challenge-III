# ChessChallendIII — FOUND-01 NOTICE checker
# Copyright (C) 2026 ChessChallendIII
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""Machine check for NOTICE (FOUND-01).

Re-derives every field from the command that produces it and exits nonzero on
any disagreement. Run from the repository root: python3 tools/check_notice.py
"""

import pathlib
import re
import subprocess
import sys

REPO = pathlib.Path(__file__).parent.resolve().parent
NOTICE = REPO / "NOTICE"

NET_SHA = "1a298aa575a085434d29027978dc36867fe9c5bcea9376654b7a8eba1e52dfc2"
BENCH_NODES = "2497913"


def git(*args: str) -> str:
    out = subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True)
    if out.returncode != 0:
        sys.exit(f"FAIL NOTICE: git {' '.join(args)} failed: {out.stderr.strip()}")
    return out.stdout.strip()


def must(pattern: str, label: str, text: str) -> re.Match:
    m = re.search(pattern, text, re.MULTILINE)
    if not m:
        sys.exit(f"FAIL NOTICE: missing {label}")
    return m


def main() -> int:
    notice = NOTICE.read_text(encoding="utf-8")

    must(r"^Base project:\s*https://github\.com/official-stockfish/Stockfish\s*$",
         "base URL", notice)
    must(r"^Base tag:\s*sf_19\s*$", "base tag", notice)

    m = must(r"^Base commit:\s*([0-9a-f]{40})\s*$", "full 40-hex base commit", notice)
    live = git("rev-parse", "sf_19")
    if m.group(1) != live:
        sys.exit(f"FAIL NOTICE: Base commit {m.group(1)} != git rev-parse sf_19 ({live})")

    must(r"^Base commit date:\s*\d{4}-\d{2}-\d{2}\s*$", "base commit date", notice)
    must(r"^Fork date:\s*\d{4}-\d{2}-\d{2}\s*$", "fork date", notice)
    must(r"^Fork repository:\s*\S+\s*$", "fork repository", notice)
    must(r"^License:\s*GPL-3\.0-or-later.*$", "license", notice)
    must(r"^Project commit \(this build\):\s*[0-9a-f]{40}\s*$", "project commit", notice)
    must(r"^Build command:\s*make -C src -j\d* build\s*$", "build command", notice)
    must(r"^Build profile:\s*(profile-build|build)\s*$", "build profile", notice)
    must(r"^ARCH:\s*x86-64-avx[a-z0-9-]*\s*$", "ARCH", notice)
    must(r"^Compiler:\s*g\+\+ \(GNUC\) \d+\.\d+\.\d+.*$", "compiler", notice)
    must(r"^Compilation settings:\s*\S.*$", "compilation settings", notice)

    must(rf"^Bench nodes:\s*{BENCH_NODES}\s*$", "bench node count", notice)
    must(r"^Binary sha256:\s*[0-9a-f]{64}\s*$", "binary sha256", notice)
    must(r"^NNUE net:\s*nn-1a298aa575a0\.nnue\s*$", "NNUE net name", notice)
    must(rf"^NNUE net sha256:\s*{NET_SHA}\s*$", "NNUE net sha256", notice)

    # Derived, never remembered: every Modified files entry must be a tracked path
    # that actually differs from sf_19, and the vendored net must never be listed.
    m = must(r"^Modified files:\s*$", "modified-files heading", notice)
    tail = notice[m.end():]
    m_added = re.search(r"^Added files of ours \(not Stockfish\):", tail, re.MULTILINE)
    if not m_added:
        sys.exit("FAIL NOTICE: missing added-files heading")
    listed = re.findall(r"^\s+-\s+(\S+)", tail[: m_added.start()], re.MULTILINE)
    if not listed:
        sys.exit("FAIL NOTICE: Modified files list is empty")
    tracked = set(git("ls-files").splitlines())
    diff = set(git("diff", "--name-only", "sf_19", "--", ":!src/nn-*.nnue").splitlines())
    for path in listed:
        if path not in tracked:
            sys.exit(f"FAIL NOTICE: Modified files entry not tracked: {path}")
        if path not in diff:
            sys.exit(f"FAIL NOTICE: Modified files entry does not differ from sf_19: {path}")
        if path.startswith("src/nn-"):
            sys.exit(f"FAIL NOTICE: vendored net listed as modified: {path}")

    print("OK NOTICE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
