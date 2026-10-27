#!/usr/bin/env python3
# ChessChallendIII — Rule 9 log package (plan 02-03)
# Copyright (C) 2026 ChessChallendIII
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.  See Copying.txt for the full text.

"""Rule 9 game log: MoveLog projection (movelog) + fail-closed linter (lint).

The .log file is rendered FROM the fsynced journal — MoveLog never writes
a parallel history, so journal↔log divergence is structurally impossible
(T-02-11). lint_log replays every uci through a fresh chess.Board and
fails closed (LOGBOOK §6): every check is a failure, never a warning.
"""
