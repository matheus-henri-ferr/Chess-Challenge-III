#!/usr/bin/env bash
# ChessChallendIII — SPRT runner (plan 01-03 Task 3, PIPE-01)
# Copyright (C) 2026 ChessChallendIII
# SPDX-License-Identifier: GPL-3.0-or-later
#
# Runs the verified SPRT recipe of docs/sprt.md and records an audit trail.
# Env overrides: BASE, CUSTOM, ROUNDS, CONCURRENCY.
#   BASE=./src/stockfish CUSTOM=./src/stockfish ROUNDS=2 sh tools/sprt.sh
set -euo pipefail
trap 'echo "FATAL: tools/sprt.sh line $LINENO" >&2' ERR

REPO=$(git rev-parse --show-toplevel)
cd "$REPO"

BASE=${BASE:-./src/stockfish}
CUSTOM=${CUSTOM:-./src/stockfish}
ROUNDS=${ROUNDS:-2}
CONCURRENCY=${CONCURRENCY:-4}
BOOK=tools/books/UHO_Lichess_4852_v1.epd
FC=tools/fastchess-linux-x86-64/fastchess

mkdir -p results
STAMP=$(date -u '+%Y%m%dT%H%M%SZ')
LOG="results/sprt-$STAMP.log"

{
  echo "# invocation: BASE=$BASE CUSTOM=$CUSTOM ROUNDS=$ROUNDS CONCURRENCY=$CONCURRENCY"
  echo "# date: $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
  echo "# commit: $(git rev-parse HEAD)"
  echo "# base sha256:   $(sha256sum "$BASE")"
  echo "# custom sha256: $(sha256sum "$CUSTOM")"
  echo "# book sha256:   $(sha256sum "$BOOK")"
} > "$LOG"

"$FC" \
  -engine name=base cmd="$BASE" \
  -engine name=custom cmd="$CUSTOM" \
  -each proto=uci tc=10+0.1 "option.Move Overhead=100" \
  -openings file="$BOOK" format=epd order=random \
  -rounds "$ROUNDS" -repeat -concurrency "$CONCURRENCY" \
  -sprt elo0=0 elo1=5 alpha=0.05 beta=0.05 model=normalized \
  -report penta=true -recover \
  -pgnout file="results/sprt-$STAMP.pgn" notation=uci | tee -a "$LOG"

grep -q "LLR:" "$LOG" || { echo "FATAL: no LLR: line in $LOG" >&2; exit 1; }
echo "results: $LOG"
