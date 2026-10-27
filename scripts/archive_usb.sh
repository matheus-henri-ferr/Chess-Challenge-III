#!/bin/sh
# ChessChallendIII — FOUND-06 release / USB archive
# Copyright (C) 2026 ChessChallendIII
# SPDX-License-Identifier: GPL-3.0-or-later
#
# Copies the complete release set to --dest <dir>, writes SHA256SUMS at the
# destination root and verifies it in place. Refuses relative destinations and
# destinations inside the repository (an unverified copy is worse than none).
set -eu

usage() { echo "usage: $0 --dest <absolute-directory>" >&2; exit 2; }

[ $# -eq 2 ] && [ "$1" = "--dest" ] || usage
DEST=$2

case "$DEST" in
  /*) ;;                       # must be absolute
  *) echo "FATAL: destination must be absolute: $DEST" >&2; usage ;;
esac

REPO=$(git rev-parse --show-toplevel)
BUILD_COMMIT=$(git rev-parse HEAD)

case "$DEST/" in
  "$REPO"/*) echo "FATAL: refusing to write inside the repository: $DEST" >&2; exit 2 ;;
esac

mkdir -p "$DEST"

sha256sum=$( (command -v sha256sum >/dev/null 2>&1 && echo "sha256sum") ||
  (command -v shasum >/dev/null 2>&1 && echo "shasum -a 256"))
if [ -z "$sha256sum" ]; then
  echo "FATAL: neither sha256sum nor shasum found; cannot hash the archive" >&2
  exit 2
fi

echo "archiving to $DEST (build commit $BUILD_COMMIT)"

# 1) Complete corresponding source: git archive of the build commit.
git archive --format=tar.gz --prefix="ChessChallendIII-$BUILD_COMMIT/" \
  -o "$DEST/ChessChallendIII-$BUILD_COMMIT.tar.gz" "$BUILD_COMMIT"

# 2) Binary + net (weights on physical media are permitted by Rule 15).
cp src/stockfish "$DEST/stockfish"
cp src/nn-1a298aa575a0.nnue "$DEST/nn-1a298aa575a0.nnue"

# 3) Licence + provenance set.
cp NOTICE "$DEST/NOTICE"
cp PROVENANCE.md "$DEST/PROVENANCE.md"
cp Copying.txt "$DEST/Copying.txt"
cp AUTHORS "$DEST/AUTHORS"

# 4) Tablebase inventory (the manifest of the declared Rule 4 assets; the
#    939 MiB tablebase tree itself is copied separately when present).
if [ -f tb/SHA256SUMS ]; then
  mkdir -p "$DEST/tb"
  cp tb/SHA256SUMS "$DEST/tb/SHA256SUMS"
fi

# 5) Manifest at the destination root, then verify in place.
cd "$DEST"
$sha256sum ChessChallendIII-$BUILD_COMMIT.tar.gz stockfish nn-1a298aa575a0.nnue \
  NOTICE PROVENANCE.md Copying.txt AUTHORS > SHA256SUMS
$sha256sum -c SHA256SUMS --quiet
echo "SHA256SUMS written and verified at $DEST"
