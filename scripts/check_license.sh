#!/bin/sh
# FOUND-02: licence headers, integrity and modification notices.
# Copyright (C) 2026 ChessChallendIII
# SPDX-License-Identifier: GPL-3.0-or-later
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.  See Copying.txt for the full text.
set -eu
fail=0

# 1) Copying.txt / AUTHORS must stay byte-identical to sf_19 (baseline is git,
#    not a sidecar hash file).
for f in Copying.txt AUTHORS; do
  a=$(git rev-parse "sf_19:$f"); b=$(git rev-parse "HEAD:$f")
  [ "$a" = "$b" ] || { echo "FAIL: $f differs from sf_19"; fail=1; }
done

# 2) Every engine source this project touched keeps its upstream GPLv3 header
#    AND carries the dated modification line, below the untouched header. The
#    vendored net is a CC0 binary asset — no text line can be added to it, so
#    it is excluded. (Upstream files we never touched, e.g. the public-domain
#    src/incbin/incbin.h, are out of scope: the baseline is git, not a rule
#    about every file in the tree.)
for f in $(git diff --name-only sf_19 -- 'src/*.cpp' 'src/*.h' 'src/*/*.cpp' 'src/*/*.h' ':!src/nn-*.nnue'); do
  grep -q "GNU General Public License" "$f" || { echo "FAIL: no GPL header: $f"; fail=1; }
  grep -q "Copyright (C)"              "$f" || { echo "FAIL: no copyright: $f";  fail=1; }
  grep -qE '^[[:space:]]*(// )?\*? ?Modified by ChessChallendIII on [0-9]{4}-[0-9]{2}-[0-9]{2}:' "$f" \
    || { echo "FAIL: no modification line: $f"; fail=1; }
done

exit $fail
