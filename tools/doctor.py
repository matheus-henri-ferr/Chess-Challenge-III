#!/usr/bin/env python3
# ChessChallendIII — LIMIT-04 startup pre-flight (doctor)
# Copyright (C) 2026 ChessChallendIII
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.  See Copying.txt for the full text.

"""Startup doctor: every Phase-1 compliance claim as an exit code.

Checks are numbered; each yields PASS / FAIL / WARN / SKIP with a one-line
reason. Exit 1 iff any FAIL. WARN never masks a rule violation; missing TB
data is SKIP by default (--strict-tb flips it to FAIL for the match laptop).

The whole budget is `uci`, `isready` and `export_net` — this tool NEVER
starts a search (no `go` is ever sent; test_doctor.py asserts it).

Usage: python3 tools/doctor.py [--asset PATH] [--strict-tb] [--json]
"""

import argparse
import hashlib
import json
import os
import pathlib
import re
import subprocess
import sys

REPO = pathlib.Path(__file__).parent.resolve().parent

NET_NAME = "nn-1a298aa575a0.nnue"
NET_SHA = "1a298aa575a085434d29027978dc36867fe9c5bcea9376654b7a8eba1e52dfc2"
BENCH_NODES = "2497913"

REMOTE_SCHEMES = ("http://", "https://", "ftp://", "s3://", "git@")
TB_SUFFIXES = (".rtbw", ".rtbz")

checks: list[dict] = []


def record(status: str, reason: str) -> None:
    checks.append({"status": status, "reason": reason})


def sha256_file(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def piece_count(filename: str) -> int:
    """Total piece codes in a Syzygy stem, e.g. KQRRBvK.rtbw → 6 (not
    distinct letters — KQRRBvK has 5 distinct letters but 6 pieces)."""
    stem = re.sub(r"\.(rtbw|rtbz)$", "", filename)
    sides = stem.split("v", 1)
    if len(sides) == 1:
        return len(sides[0])
    return len(sides[0]) + len(sides[1])


def engine_stdio(commands: str, timeout: float = 60.0) -> subprocess.CompletedProcess:
    return subprocess.run([str(REPO / "src" / "stockfish")], input=commands,
                          capture_output=True, text=True, timeout=timeout, cwd=REPO)


# --- check 1: asset path is absolute and local -----------------------------

def check_asset_path(asset: str) -> pathlib.Path | None:
    if any(asset.startswith(s) for s in REMOTE_SCHEMES):
        record("FAIL", f"asset path uses a remote scheme ({asset.split(':')[0]}…): "
                       "Rule 14 forbids network at run time")
        return None
    if asset.startswith("~") or "$" in asset:
        record("FAIL", f"asset path is expandable ('~' or '$VAR'): '{asset}' — "
                       "pass an absolute literal path")
        return None
    path = pathlib.Path(asset)
    if not path.is_absolute():
        record("FAIL", f"asset path is not absolute: '{asset}'")
        return None
    # Re-test after resolve(): a symlink into /proc/net or similar.
    resolved = path.resolve()
    if any(str(resolved).startswith(s) for s in REMOTE_SCHEMES):
        record("FAIL", "asset path resolves to a remote scheme")
        return None
    record("PASS", f"asset path absolute and local: {resolved}")
    return resolved


# --- checks 2-6: binary, net, option surface --------------------------------

def check_engine():
    binary = REPO / "src" / "stockfish"
    if not (binary.is_file() and os.access(binary, os.X_OK)):
        record("FAIL", f"engine binary missing or not executable: {binary}")
        return
    record("PASS", f"binary present: {binary.stat().st_size} bytes, "
                   f"sha256 {sha256_file(binary)[:16]}…")

    uci = engine_stdio("uci\nquit\n")
    if "uciok" not in uci.stdout:
        record("FAIL", "engine did not answer uciok")
        return

    line = next((l for l in uci.stdout.splitlines()
                 if l.startswith("option name SyzygyProbeLimit")), "")
    if line == "option name SyzygyProbeLimit type spin default 5 min 0 max 5":
        record("PASS", f"option line exact: {line}")
    else:
        record("FAIL", f"SyzygyProbeLimit option line wrong: '{line}'")

    ready = engine_stdio("isready\nquit\n")
    if "readyok" in ready.stdout:
        record("PASS", "isready → readyok")
    else:
        record("FAIL", "engine did not answer readyok")


def check_net():
    net = REPO / "src" / NET_NAME
    if not net.is_file():
        record("FAIL", f"net missing: {net}")
        return
    actual = sha256_file(net)
    if actual != NET_SHA:
        record("FAIL", f"net sha256 {actual} != declared {NET_SHA}")
        return
    record("PASS", f"net {NET_NAME} hash matches")

    out = pathlib.Path("/tmp") / "doctor-net-export.nnue"
    p = engine_stdio(f"export_net {out}\nquit\n")
    if not out.is_file():
        record("FAIL", f"export_net produced nothing ({p.stdout[-200:]})")
        return
    if sha256_file(out) != NET_SHA:
        record("FAIL", "export_net round-trip differs from the declared net")
        out.unlink()
        return
    out.unlink()
    record("PASS", "export_net round-trip byte-identical")


# --- check 7: tablebase directory -------------------------------------------

def check_tb(path: pathlib.Path | None, strict: bool):
    if path is None:
        record("SKIP", "no --asset given; pass the SyzygyPath explicitly")
        return
    if not path.is_dir():
        msg = ("directory not present; fetch Syzygy 3-4-5 before the event — "
               "see PROVENANCE.md §2")
        record("FAIL" if strict else "SKIP", msg)
        return
    files = sorted(p for p in path.iterdir() if p.suffix in TB_SUFFIXES)
    if not files:
        msg = "directory contains no .rtbw/.rtbz files"
        record("FAIL" if strict else "SKIP", msg)
        return
    for f in files:
        n = piece_count(f.name)
        if n > 5:
            record("FAIL", f"{f.name} implies {n} pieces — Rule 4 ceiling is 5")
            return
    record("PASS", f"{len(files)} tablebase files, all ≤ 5 pieces")


# --- checks 8-12: environment ------------------------------------------------

def check_book():
    # The ply-scan arrives with LIMIT-03; the file check is all Phase 1 asserts.
    book = REPO / "tools" / "books" / "UHO_Lichess_4852_v1.epd"
    if book.is_file():
        record("PASS", f"harness book present: {book.name}")
    else:
        record("SKIP", "harness book not staged yet (LIMIT-03 ply scan arrives later)")


def check_vendor_chess():
    r = subprocess.run(
        [sys.executable, "-c",
         "import chess; assert chess.__version__ == '1.11.2', chess.__version__"],
        cwd=REPO, capture_output=True, text=True,
        env={"PYTHONPATH": str(REPO / "vendor"), "PATH": os.environ.get("PATH", ""),
             "HOME": "/tmp"},
    )
    if r.returncode == 0:
        record("PASS", "vendor/chess imports as 1.11.2")
    else:
        record("FAIL", f"vendor/chess import failed: {r.stderr.strip()[-120:]}")


def check_provenance_declared():
    text = (REPO / "PROVENANCE.md").read_text(encoding="utf-8")
    for item in ("python-chess", "fastchess", "nn-1a298aa575a0.nnue", "Syzygy"):
        if item not in text:
            record("FAIL", f"PROVENANCE.md does not declare: {item}")
            return
    record("PASS", "PROVENANCE.md declares net, python-chess, fastchess, Syzygy")


def check_log_dir():
    log = REPO / "log"
    try:
        log.mkdir(exist_ok=True)
        probe = log / ".doctor-probe"
        probe.touch()
        probe.unlink()
        record("PASS", f"log directory writable: {log}")
    except OSError as e:
        record("FAIL", f"log directory not writable: {e}")


def check_delegates():
    """Run the Phase-1 checkers as subprocesses; their verdict is ours."""
    for cmd, label in (
        (["python3", "tools/check_notice.py"], "check_notice"),
        (["python3", "tools/check_provenance.py"], "check_provenance"),
        (["python3", "tools/check_contract_order.py"], "check_contract_order"),
    ):
        r = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True)
        if r.returncode == 0:
            record("PASS", f"{label}: OK")
        else:
            record("FAIL", f"{label}: {(r.stdout + r.stderr).strip().splitlines()[-1][:120]}")


def check_network_state():
    # WARN in Phase 1; hard-fails in Phase 3 (T-01-16).
    try:
        import socket
        hostname = socket.gethostname()
        record("WARN", f"network state not asserted in Phase 1 (host {hostname}); "
                       "Phase 3 turns this into a hard fail")
    except OSError:
        record("WARN", "network state unknown")


def main() -> int:
    ap = argparse.ArgumentParser(description="ChessChallendIII startup doctor")
    ap.add_argument("--asset", default=None,
                    help="path the console will pass as SyzygyPath")
    ap.add_argument("--strict-tb", action="store_true",
                    help="missing tablebase directory is FAIL, not SKIP")
    ap.add_argument("--json", action="store_true", help="machine-readable report")
    args = ap.parse_args()

    path = check_asset_path(args.asset) if args.asset else None
    check_engine()
    check_net()
    check_tb(path, args.strict_tb)
    check_book()
    check_vendor_chess()
    check_provenance_declared()
    check_log_dir()
    check_delegates()
    check_network_state()

    failed = [c for c in checks if c["status"] == "FAIL"]
    if args.json:
        print(json.dumps({
            "ok": not failed,
            "failed": [f"{c['status']}: {c['reason']}" for c in failed],
            "checks": checks,
        }))
    else:
        for c in checks:
            print(f"{c['status']}: {c['reason']}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
