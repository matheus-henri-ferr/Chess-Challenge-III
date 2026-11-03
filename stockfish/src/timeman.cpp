/*
  Stockfish, a UCI chess playing engine derived from Glaurung 2.1
  Copyright (C) 2004-2026 The Stockfish developers (see AUTHORS file)

  Stockfish is free software: you can redistribute it and/or modify
  it under the terms of the GNU General Public License as published by
  the Free Software Foundation, either version 3 of the License, or
  (at your option) any later version.

  Stockfish is distributed in the hope that it will be useful,
  but WITHOUT ANY WARRANTY; without even the implied warranty of
  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
  GNU General Public License for more details.

  You should have received a copy of the GNU General Public License
  along with this program.  If not, see <http://www.gnu.org/licenses/>.
*/

// ChessChallenge III: the allocation formula in init() is authored by the team
// and replaces the original Stockfish 19 formula (commit edb0d9db).

#include "timeman.h"

#include <algorithm>
#include <cassert>
#include <cmath>

#include "search.h"
#include "ucioption.h"

namespace Stockfish {

TimePoint TimeManagement::optimum() const { return optimumTime; }
TimePoint TimeManagement::maximum() const { return maximumTime; }

void TimeManagement::clear() {
    availableNodes = -1;  // When in 'nodes as time' mode
}

void TimeManagement::advance_nodes_time(i64 nodes) {
    assert(useNodesTime);
    availableNodes = std::max(i64(0), availableNodes - nodes);
}

namespace {

// Expected number of our moves still to be played, from the full-move number.
double expected_moves_left(int fullmove) { return std::max(18.0, 48.0 - 0.6 * fullmove); }

// Weight of the current move relative to an average move. Opening moves are
// cheap, the early middlegame (where games are decided) gets the most time.
// The pool is recomputed every move, so overspending corrects itself.
double phase_weight(int fullmove) {
    if (fullmove <= 4)
        return 0.55;
    if (fullmove <= 10)
        return 0.55 + (fullmove - 4) * (0.65 / 6.0);
    if (fullmove <= 35)
        return 1.2;
    if (fullmove <= 50)
        return 1.2 - (fullmove - 35) * (0.2 / 15.0);
    return 1.0;
}

}  // namespace

// Called at the beginning of the search and calculates the bounds of time
// allowed for the current move. "Move Overhead" is the clock time lost per move
// outside the search: in the event, entering the opponent's move, announcing
// ours, waiting for the repetition, moving the piece and pressing the clock.
void TimeManagement::init(Search::LimitsType& limits,
                          Color               us,
                          int                 ply,
                          const OptionsMap&   options,
                          double&             originalTimeAdjust) {
    (void) originalTimeAdjust;
    TimePoint npmsec = TimePoint(options["nodestime"]);

    startTime    = limits.startTime;
    useNodesTime = npmsec != 0;

    if (useNodesTime)
        limits.movetime *= npmsec;

    if (limits.time[us] == 0)
    {
        optimumTime = maximumTime = NoBound;
        return;
    }

    TimePoint moveOverhead = TimePoint(options["Move Overhead"]);

    if (useNodesTime)
    {
        if (availableNodes == -1)
            availableNodes = npmsec * limits.time[us];

        limits.time[us] = TimePoint(availableNodes);
        limits.inc[us] *= npmsec;
        limits.npmsec = npmsec;
        moveOverhead *= npmsec;
    }

    const double scale    = useNodesTime ? double(npmsec) : 1.0;
    const double time     = double(limits.time[us]);
    const double inc      = double(limits.inc[us]);
    const double overhead = double(moveOverhead);
    const int    fullmove = ply / 2 + 1;

    // Part of the clock we never plan to use: relay delays and misread clocks.
    const double reserve = overhead + 0.02 * time + std::min(2000.0 * scale, 0.05 * time);
    // Increment really gained per move once the relay cost is paid.
    const double netInc = std::max(0.0, inc - overhead);
    // Absolute ceiling: the search must end with the relay cost still on the clock.
    const double hardLimit = time - overhead - 300.0 * scale;

    const double mtg = limits.movestogo ? std::clamp(double(limits.movestogo), 1.0, 50.0)
                                        : expected_moves_left(fullmove);

    const double usable = time - reserve;
    double       opt, maxT;

    if (usable <= 0)
    {
        // Emergency: a small slice of what is left plus half the net increment.
        opt  = std::max(0.0, time - overhead) / 20.0 + netInc * 0.5;
        maxT = opt * 2.0;
    }
    else
    {
        const double pool = usable + netInc * (mtg - 1);
        // The increment only counts partially: the relay overhead can be underestimated.
        opt  = std::min(pool / mtg * phase_weight(fullmove), usable * 0.10 + netInc * 0.6);
        maxT = std::min(opt * (fullmove <= 4 ? 2.0 : 3.0), usable * 0.12 + netInc * 0.6);
    }

    const double floorT = 10.0 * scale;
    const double cap    = std::max(floorT, hardLimit);
    opt                 = std::clamp(opt, floorT, cap);
    maxT                = std::clamp(maxT, opt, cap);

    optimumTime = TimePoint(opt);
    maximumTime = TimePoint(maxT);

    if (options["Ponder"])
        optimumTime = std::min(maximumTime, optimumTime + optimumTime / 4);
}

}  // namespace Stockfish
