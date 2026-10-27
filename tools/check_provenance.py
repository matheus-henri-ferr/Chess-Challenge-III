# ChessChallendIII — FOUND-03 PROVENANCE checker
# Copyright (C) 2026 ChessChallendIII
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.  See Copying.txt for the full text.

"""Machine check for PROVENANCE.md (FOUND-03).

Asserts the NNUE net identity against the on-disk file, the non-authorship
markers, the dependency manifest's column discipline, and the tablebase
inventory's five-piece ceiling. Run from the repository root:

    python3 tools/check_provenance.py [path-to-PROVENANCE.md]

Exit 0 only when every hard check passes. Human steps (panel URL
confirmation, physical USB copy) surface as WARN, never FAIL.
"""

import hashlib
import pathlib
import re
import subprocess
import sys

REPO = pathlib.Path(__file__).parent.resolve().parent

NET_NAME = "nn-1a298aa575a0.nnue"
NET_BYTES = 98511183
NET_SHA = "1a298aa575a085434d29027978dc36867fe9c5bcea9376654b7a8eba1e52dfc2"
DEPENDENCY_COLUMNS = 7  # Name | Version | Pin mechanism | SHA-256 | License | Shipped? | Purpose

warnings: list[str] = []


def fail(msg: str):
    sys.exit(f"FAIL PROVENANCE: {msg}")


def sha256_file(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def git(*args: str) -> str:
    out = subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True)
    if out.returncode != 0:
        sys.exit(f"FAIL PROVENANCE: git {' '.join(args)} failed: {out.stderr.strip()}")
    return out.stdout.strip()


def piece_count(filename: str) -> int:
    """Count pieces in a Syzygy filename stem like KQRRBvK.rtbw (left v right)."""
    stem = re.sub(r"\.(rtbw|rtbz)$", "", filename)
    sides = stem.split("v", 1)
    if len(sides) == 1:
        return len(sides[0])
    return len(sides[0]) + len(sides[1])


def check_net_table(text: str):
    m = re.search(r"^\| File \| (\S+) \|$", text, re.MULTILINE)
    if not m or m.group(1) != NET_NAME:
        fail(f"NNUE table must name {NET_NAME}")
    m = re.search(r"^\| Bytes \| (\d+) \|$", text, re.MULTILINE)
    if not m:
        fail("missing | Bytes | row in §1")
    if int(m.group(1)) != NET_BYTES:
        fail(f"Bytes row says {m.group(1)}, expected {NET_BYTES}")
    m = re.search(r"^\| SHA-256 \| ([0-9a-f]{64}) \|$", text, re.MULTILINE)
    if not m:
        fail("missing | SHA-256 | row in §1")
    if m.group(1) != NET_SHA:
        fail(f"declared net sha256 {m.group(1)} != {NET_SHA}")

    net = REPO / "src" / NET_NAME
    if not net.is_file():
        fail(f"{NET_NAME} missing from src/")
    actual = sha256_file(net)
    if actual != NET_SHA:
        fail(f"on-disk net sha256 {actual} != declared {NET_SHA}")
    if net.stat().st_size != NET_BYTES:
        fail(f"on-disk net is {net.stat().st_size} bytes, expected {NET_BYTES}")
    git("ls-files", "--error-unmatch", f"src/{NET_NAME}")  # tracked, not just on disk

    if "CC0-1.0" not in text:
        fail("net license CC0-1.0 not declared")
    if "NOT AUTHORED BY THE TEAM" not in text:
        fail("non-authorship marker missing — must read 'NOT AUTHORED BY THE TEAM' verbatim")


def check_dependencies(text: str):
    m = re.search(r"^## 3\. Dependencies\s*$", text, re.MULTILINE)
    if not m:
        fail("missing '## 3. Dependencies' section")
    tail = text[m.end():]
    next_section = re.search(r"^## \d", tail, re.MULTILINE)
    if next_section:
        tail = tail[: next_section.start()]

    fastchess_shipped = None
    rows_seen = 0
    for line in tail.splitlines():
        if not line.startswith("|") or set(line) <= {"|", "-", " "}:
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if cells[0] == "Name":  # header row
            if len(cells) != DEPENDENCY_COLUMNS:
                fail(f"dependency header has {len(cells)} columns, expected {DEPENDENCY_COLUMNS}")
            continue
        rows_seen += 1
        if len(cells) != DEPENDENCY_COLUMNS:
            fail(f"dependency row '{cells[0]}' has {len(cells)} columns, expected {DEPENDENCY_COLUMNS}")
        name = cells[0]
        for i, cell in enumerate(cells):
            if cell == "":
                fail(f"dependency row '{name}' column {i + 1} is empty (use 'n/a' when not applicable)")
        shipped = cells[5].lower()
        if name.startswith("fastchess"):
            fastchess_shipped = shipped
        if name.startswith("python-chess") and "a8b43e5678fdb3000695bdaa573117ad683761e5ca38e591c4826eba6d25bb39" not in cells[3]:
            fail("python-chess row must carry the sdist sha256 pin")
    if rows_seen == 0:
        fail("dependency table has no data rows")
    if fastchess_shipped != "no":
        fail(f"fastchess must be marked Shipped? = no (dev-only, never inside the engine tree); got '{fastchess_shipped}'")


def check_inventory(text: str):
    m = re.search(r"^### 2\.1 Tablebase inventory\s*$", text, re.MULTILINE)
    if not m:
        fail("missing '### 2.1 Tablebase inventory' section")
    tail = text[m.end():]
    fence = re.search(r"^```", tail, re.MULTILINE)
    if fence:
        block = tail[fence.end():]
        end = re.search(r"^```", block, re.MULTILINE)
        if end:
            block = block[: end.start()]
        entries = 0
        for line in block.splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            filename = parts[-1]
            entries += 1
            n = piece_count(filename)
            if n > 5:
                fail(f"inventory filename '{filename}' implies {n} pieces — Rule 4 permits at most 5")
            if not re.search(r"\.(rtbw|rtbz)$", filename):
                fail(f"inventory entry '{filename}' is not a .rtbw/.rtbz file")
        if entries:
            return
    if "not yet fetched" not in tail.lower():
        fail("inventory block has no entries and does not state 'not yet fetched'")


def check_authorship_and_footer(text: str):
    if not re.search(r"^## 4\. Not authored by the team\s*$", text, re.MULTILINE):
        fail("missing '## 4. Not authored by the team' section")
    if not re.search(r"^License: GPL-3\.0-or-later\. See Copying\.txt and NOTICE\.\s*$",
                     text, re.MULTILINE):
        fail("missing license footer line")


def check_panel_url(text: str):
    m = re.search(r"^\| Panel URL \| (\S*) \|$", text, re.MULTILINE)
    if not m:
        # tolerated alternative: Fork repository recorded in the same document
        m = re.search(r"^\| Fork repository \| (\S*) \|$", text, re.MULTILINE)
    if not m or m.group(1) in ("", "<URL>"):
        warnings.append("panel URL not yet recorded (FOUND-06 human step)")
        return
    try:
        origin = git("remote", "get-url", "origin")
    except SystemExit:
        origin = ""
    if origin and not (
        origin.split("@")[-1].split(":")[0].split("/")[0]
        .replace("git.", "").replace("ssh.", "")
        in m.group(1).replace("https://", "").replace("http://", "")
        or m.group(1) in origin
        or origin.endswith(".git") and origin[:-4].split("/")[-1] in m.group(1)
    ):
        warnings.append(f"panel URL '{m.group(1)}' does not obviously match origin '{origin}'")


def main() -> int:
    path = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else REPO / "PROVENANCE.md"
    text = path.read_text(encoding="utf-8")

    check_net_table(text)
    check_dependencies(text)
    check_inventory(text)
    check_authorship_and_footer(text)
    check_panel_url(text)

    for w in warnings:
        print(f"WARN PROVENANCE: {w}")
    print("OK PROVENANCE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
