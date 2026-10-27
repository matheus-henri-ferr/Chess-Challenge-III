#!/usr/bin/env bash
# ChessChallendIII — Phase 1 gate (plan 01-03 Task 3)
# Copyright (C) 2026 ChessChallendIII
# SPDX-License-Identifier: GPL-3.0-or-later
#
# The single Phase-1 gate: every claim as an exit code.
#   bash scripts/gate0.sh              # full, incl. the namespace build
#   bash scripts/gate0.sh --skip-build # skip tools/offline_build.sh
set -uo pipefail
trap 'echo "FATAL: scripts/gate0.sh line $LINENO" >&2' ERR

REPO=$(git rev-parse --show-toplevel)
cd "$REPO"
SKIP_BUILD=0
[ "${1:-}" = "--skip-build" ] && SKIP_BUILD=1

TESTS_FAILED=0
fail() { echo "GATE0 FAIL: $*" >&2; TESTS_FAILED=1; }

run() { # run <label> <cmd...>
  local label=$1; shift
  echo "==> $label"
  if "$@"; then
    echo "    OK: $label"
  else
    fail "$label exited nonzero"
  fi
}

# 1) Licence gate
run "check_license" sh scripts/check_license.sh

# 2) Provenance checkers
run "check_notice"     python3 tools/check_notice.py
run "check_provenance" python3 tools/check_provenance.py
run "check_contract_order" python3 tools/check_contract_order.py

# 3) Full test suite
run "unittests" python3 -m unittest discover -s tools/tests -t . -v

# 4) Namespace build proof (the slow one)
if [ "$SKIP_BUILD" -eq 0 ]; then
  run "offline_build" sh tools/offline_build.sh
else
  echo "==> offline_build SKIPPED (--skip-build)"
fi

# 5) Bench assertion (stderr capture; never trust stdout for bench)
BENCH=$(./src/stockfish bench 2>&1 | sed -n 's/^Nodes searched  : //p')
if [ "$BENCH" = "2497913" ]; then
  echo "    OK: bench 2497913"
else
  fail "bench reported '$BENCH', expected 2497913"
fi

# 6) Doctor (plain: missing TB is SKIP on the dev box)
run "doctor" python3 tools/doctor.py --asset /opt/tb/3-4-5

# 7) FOUND-06 dry run: ancestry, origin, release manifest
if git merge-base --is-ancestor sf_19 HEAD; then
  echo "    OK: sf_19 is ancestor of HEAD"
else
  fail "sf_19 is NOT an ancestor of HEAD"
fi
if git remote get-url origin >/dev/null 2>&1; then
  echo "    OK: origin remote: $(git remote get-url origin)"
else
  fail "no origin remote configured"
fi
if [ -f RELEASE/SHA256SUMS ]; then
  echo "    OK: RELEASE/SHA256SUMS present"
else
  fail "RELEASE/SHA256SUMS missing (physical-media dry run not recorded)"
fi

echo
if [ "$TESTS_FAILED" -eq 0 ]; then
  echo "GATE0 PASS — every Phase-1 claim reproduced"
  exit 0
fi
echo "GATE0 FAIL — see GATE0 FAIL lines above" >&2
exit 1
