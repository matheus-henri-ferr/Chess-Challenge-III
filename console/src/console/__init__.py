#!/usr/bin/env python3
# ChessChallendIII — console package (plan 02-01)
# Copyright (C) 2026 ChessChallendIII
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.  See Copying.txt for the full text.

"""Console package.

Layout: code lives in console/src/console (this dir, via PYTHONPATH); the
plan-mandated test tree is console/tests (repo root, a sibling of console/).
The frozen verify command `python3 -m unittest console.tests.test_transport`
needs console.tests importable, so the repo-root console/ dir is registered
here as a second package-path entry (pkgutil-style __path__ extension): the
finder looks for a `tests/` subdir inside each entry.
"""

import os as _os

_console_root = _os.path.abspath(
    _os.path.join(_os.path.dirname(__file__), "..", ".."))
# Appended only when it actually carries the tests portion (worktree-safe).
if _os.path.isdir(_os.path.join(_console_root, "tests")):
    __path__.append(_console_root)  # noqa: F821 — __path__ is package machinery

