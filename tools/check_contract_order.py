# ChessChallendIII — FOUND-05 contract ordering checker
# Copyright (C) 2026 ChessChallendIII
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.  See Copying.txt for the full text.

"""Machine proof that the PROTOCOL/LOGBOOK freeze predates implementation.

Finds the freeze commit (the one that added docs/PROTOCOL.md and
docs/LOGBOOK.md together, touching only those two files), then walks every
commit that touches the implementation paths src/, console/, pipeline/ —
deliberately excluding tools/ and scripts/, which exist alongside the docs.

Comment-only provenance edits in src/ (added lines matching
`^Modified by ChessChallendIII on <date>:` or blank lines, plan 01-01) do not
count as implementation. Verdict per commit: git merge-base --is-ancestor.

Usage: python3 tools/check_contract_order.py [repo-root]
(repo-root defaults to the enclosing git toplevel of the working directory.)

Prints `OK CONTRACT ORDER` and exits 0 when every implementation commit
descends from the freeze commit (or none exists yet — vacuously OK).
"""

import pathlib
import re
import subprocess
import sys

DOCS = ("docs/PROTOCOL.md", "docs/LOGBOOK.md")
IMPL_PREFIXES = ("src/", "console/", "pipeline/")
MODIFIED_LINE = re.compile(
    r"^\+? ?(// )?\*? ?Modified by ChessChallendIII on \d{4}-\d{2}-\d{2}:.*$"
)


def repo_root() -> pathlib.Path:
    if len(sys.argv) > 1:
        return pathlib.Path(sys.argv[1]).resolve()
    out = subprocess.run(["git", "rev-parse", "--show-toplevel"],
                         capture_output=True, text=True)
    if out.returncode != 0:
        sys.exit("FAIL CONTRACT ORDER: not a git repository (and no repo-root given)")
    return pathlib.Path(out.stdout.strip()).resolve()


REPO = repo_root()


def git(*args: str, check: bool = True) -> str:
    out = subprocess.run(["git", "-C", str(REPO), *args],
                         capture_output=True, text=True)
    if check and out.returncode != 0:
        sys.exit(f"FAIL CONTRACT ORDER: git {' '.join(args)} failed: {out.stderr.strip()}")
    return out.stdout if out.returncode == 0 else ""


def find_freeze_commit() -> str:
    """The one commit whose full changed-file set is exactly the two docs.

    Ambiguous (0 or >1) → FAIL: an ambiguous freeze is no freeze.
    """
    shas = git("log", "--format=%H", "--diff-filter=A", "--", DOCS[0]).split()
    freezes = []
    for sha in shas:
        files = git("diff-tree", "--no-commit-id", "--name-only", "-r",
                    "--root", sha).split()
        if set(files) == set(DOCS):
            freezes.append(sha)
    if len(freezes) != 1:
        sys.exit(f"FAIL CONTRACT ORDER: expected exactly 1 docs-only freeze commit, "
                 f"found {len(freezes)}")
    return freezes[0]


def is_comment_only(sha: str) -> bool:
    """True when the src/ diff of this commit adds only provenance lines."""
    # --root: a root commit's diff-tree is empty without it.
    diff = git("diff-tree", "--no-commit-id", "-r", "-U0", "--root", sha, "--", "src/")
    for line in diff.splitlines():
        if not line.startswith("+") or line.startswith("+++"):
            continue  # headers, context and deletions are not added code
        added = line[1:]
        if added.strip() and not MODIFIED_LINE.match("+" + added):
            return False
    return True


def main() -> int:
    freeze = find_freeze_commit()
    print(f"freeze commit: {freeze}")

    impl_shas = []
    # Project commits only — upstream sf_19 history touches src/ endlessly and
    # is not ours to gate (the import commit 0ef8529b grafts it, HEAD ^sf_19
    # skips it). Synthetic repos without sf_19 fall back to plain HEAD.
    base = "HEAD ^sf_19" if git("rev-parse", "--verify", "-q",
                                "sf_19", check=False).strip() else "HEAD"
    for sha in git("rev-list", *base.split()).split():
        files = git("diff-tree", "--no-commit-id", "--name-only", "-r",
                    "--root", sha).split()
        if any(f.startswith(p) for p in IMPL_PREFIXES for f in files):
            if sha == freeze:
                continue
            impl_shas.append(sha)

    if not impl_shas:
        print("no implementation commits touching src/ console/ pipeline/ yet — "
              "OK CONTRACT ORDER (vacuous)")
        return 0

    first_impl = None
    for sha in impl_shas:
        if is_comment_only(sha):
            continue
        first_impl = sha
        break

    if first_impl is None:
        print("all implementation-path commits so far are comment-only provenance "
              "edits — OK CONTRACT ORDER (vacuous)")
        return 0

    if subprocess.run(["git", "merge-base", "--is-ancestor", freeze, first_impl],
                      cwd=REPO).returncode == 0:
        print(f"OK CONTRACT ORDER: freeze {freeze[:8]} is ancestor of first "
              f"implementation commit {first_impl[:8]}")
        return 0
    sys.exit(f"FAIL CONTRACT ORDER: implementation commit {first_impl[:8]} does NOT "
             f"descend from freeze commit {freeze[:8]}")


if __name__ == "__main__":
    sys.exit(main())
