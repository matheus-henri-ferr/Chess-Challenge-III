# Feature Research

**Domain:** Competition chess engine — Stockfish fork + spoken-UCI operator console, Best-of-3, 15+10, offline
**Researched:** 2026-10-26
**Confidence:** HIGH on rules-derived requirements (read verbatim rulebook), HIGH on engine-capability claims (read Stockfish source), MEDIUM on competitive/EV judgments (inference, no field data)

**Sources of truth used:**
`docs/competition-rules.md` (R1–R15, cited inline), `.planning/PROJECT.md`, and Stockfish upstream source (`src/timeman.cpp`, `src/uci.cpp`, `src/engine.cpp`, `src/position.cpp`, 2026 master).

---

## How To Read This

- **Rule references** (`R7`, `R10`…) point to `docs/competition-rules.md` §7, §10…
- **Complexity** is *implementation* cost for one competent C++/Python dev, not calendar time:
  - **S** ≈ 0.5–1.5 person-days
  - **M** ≈ 2–3 person-days
  - **L** ≈ 4–7 person-days
- **Depends on** lists hard prerequisites only. A feature can be built before its dependency *exists*, but not *work*.

---

## Scope Verdict (read this first)

**The single most important finding: this product's risk is not engine strength, it is the operator loop.** A Stockfish fork at default settings already plays at a level nobody in a student competition will out-calculate in 2 weeks. What loses matches is (a) a time forfeit caused by the *spoken protocol's human latency*, (b) a board/software divergence that desynchronizes the game, (c) a missing log field at judge hand-off, and (d) losing the Rule 12 tiebreak to a team that spent less time per move.

**Second finding, and it changes the shape of the project:** with a 10-second increment, the per-move cost of the spoken protocol is *comparable to the increment itself*. Our clock runs from the opponent's press to our press. Inside that window we must: type/confirm the opponent's move (2–5 s), search, then announce, physically move the piece, and press (3–8 s). Stockfish's `Move Overhead` default is **10 ms** (`engine.cpp`). A fork that leaves that at default will burn 4–8 seconds per move of pure protocol overhead — roughly 3–5 minutes over a 40-move game, i.e. the entire Rule 12 tiebreak, handed over for free. **Pondering is not just an Elo feature; it is the mechanism that collapses the end-of-turn overhead to ~1 s, because the reply is already known when the opponent presses.**

**Third finding:** table stakes, estimated per item below, cost **~21–24 raw person-days**. Three people over 10 working days is ~30 person-days at 100% and ~21 at realistic efficiency — **table stakes alone consume the budget**, and that is only achievable via three specific compressions: (a) reuse a chess library for board + legality (R14 explicitly permits it), (b) make the journal and the mandatory log the **same append-only writer** with two projections, (c) build **one** protocol state machine instead of per-feature guards. Therefore the differentiators must be *designed into* the table-stakes code from day 1 (a policy interface and a clock interface), not bolted on in week 2. Anything in the anti-feature list is not "later" — it is "never, in this milestone."

**Scope call for 3 people / 2 weeks:** build **TS-1 through TS-21** (all are load-bearing; the ones that look optional are the ones that lose a match). Of the twelve differentiators, commit to **four**: DF-1 (authored time manager), DF-2 (latency calibration), DF-5 (ponder wiring), and DF-3+DF-4 treated as **one** policy function (match-aware draw value + time shadow price). DF-6, DF-8, and DF-9 are then just parameter sets on that function — essentially free once it exists. DF-10 (simulation harness) is not optional either; it is how the table stakes get verified. DF-7, DF-11, and DF-12 are the third person's opportunistic work and must not expand into their own phase.

---

## Feature Landscape

### Table Stakes — Group A: Compliance & Environment

Without these the team is disqualified or forfeits on inspection, regardless of play strength.

| ID | Feature | Rule | Complexity | Depends on | Notes |
|----|---------|------|------------|-----------|-------|
| TS-1 | **Fork provenance & GPLv3 compliance** — pinned upstream commit recorded, `GPLv3` + AUTHORS headers retained, repo published/handable to judges, dependency manifest (`requirements.txt`/`CMakeLists.txt`), declared network weights with origin | R1, R14, R15 | S | build | Add `info string fork <name> base <sha>` so the engine self-identifies in the log; the judge can verify the declaration against the binary. Do not strip headers "to clean up." Declare third-party NNUE weights explicitly as third-party (R15: they don't count as authorship). |
| TS-2 | **Offline-clean runtime** — zero outbound requests; all assets (book, Syzygy, NNUE, libs) resolved from local paths; startup self-check fails loudly if a remote/relative asset path is used | R14 | S | none | Arbiter physically verifies Wi-Fi/mobile data off at the start of *each* game. Practical equivalent: no telemetry, no auto-update, no `curl` in build scripts used at the event, no cloud eval. A 30-line startup assertion ("all asset paths absolute and local") is cheap insurance against an accidental network call in a dependency. |
| TS-3 | **Hard rule ceilings enforced in code** — `SyzygyProbeLimit = 5` (upstream default is **7** — must be overridden), book loader rejects any line > 10 plies, book file provenance recorded | R3, R4 | S | TS-1 | This is a table stake, not a tuning knob: exceeding either limit is a rules violation. Upstream `SyzygyProbeLimit` default of 7 is a live foot-gun — assert the effective value at startup and print it in the pre-game checklist (TS-21). Book: enforce by *ply count from the game start*, not by "line depth in the book file," which is easy to mis-implement. |
| TS-4 | **Single-laptop, single-process deployment** — no client/server split, no shared state, no second machine | R6 | S | none | One laptop per team, all games. A localhost server is acceptable only if it is one launchable script and survives laptop restart. Do not build anything that assumes a second device. |

### Table Stakes — Group B: Spoken Protocol & Board Replication

This is the core of the product. It is where the project is won or lost.

| ID | Feature | Rule | Complexity | Depends on | Notes |
|----|---------|------|------------|-----------|-------|
| TS-5 | **Strict UCI move parser / normalizer** — accepts `e2e4`, `g1f3`, `e7e8q` (and `e1g1`/`e1c1` castling), tolerant of case and surrounding whitespace, **rejects** SAN (`Nf3`, `e4`, `O-O`), rejects null move `0000`, rejects 5-char non-promotion garbage; returns a typed error with the offending token | R10 | S | none | The rulebook is explicit that UCI is used *because* spoken algebraic is ambiguous. A parser that silently "helpfully" accepts `Nf3` will accept the wrong move under clock pressure. Normalize + reject is safer than guess. Log every rejected token (it is evidence). |
| TS-6 | **Board-state replication for both sides** — authoritative FEN + ordered move list, advanced only by validated moves; both colors entered | R5, R10 | M | TS-5 | Every team must replicate *both* sides. Do this with a real chess library (R14 explicitly permits `python-chess` for board representation and legal move generation) or by exposing Stockfish's `Position` — do not hand-roll move generation. Reusing a library removes ~90% of the correctness risk here and costs nothing at judging, because R14 says the evaluated layer is *decision*, not board mechanics. |
| TS-7 | **Legal-move validation + illegal-announcement handling** — announced move illegal in our replication ⇒ do **not** advance state, keep listening, prompt operator to say "illegal, announce another", log the event with timestamp | R10 | S | TS-5, TS-6 | Two distinct cases: (a) *opponent's* illegal announcement — annulled, their clock runs, they must re-announce; our software just refuses and keeps the input loop live. (b) *our own* engine returns a move that is illegal in our position — catastrophic under a running clock. Guard by validating `bestmove` against the move list before it is ever displayed, then failing over (TS-15, TS-16). |
| TS-8 | **Outbound move presentation for verbal announcement** — large unambiguous rendering (`E2-E4`, `E7-E8=Q`), plus an explicit "announced + confirmed by opponent" acknowledgement key | R10 | S | TS-6 | The announcement is a *human* step and a legal requirement; the software's job is to make it impossible to misread at a glance. Uppercase, dash-separated, coordinates only, never SAN or figurine notation. The ack key is what advances the state machine to "awaiting opponent confirmation" — see TS-9. |
| TS-9 | **Turn/state machine with explicit phases** — `IDLE → OUR_SEARCH → ANNOUNCE_PENDING → AWAIT_OPP_CONFIRM → OPP_TURN / PONDERING`, with a side-to-move guard that rejects any input that would cause two consecutive moves by one side | R10, R13 | M | TS-6 | This is the feature that prevents the two worst bugs: double-move (both teams enter the same move) and stale search (we start searching a position before the opponent's latest move was entered). Every input command asserts a legal phase transition. Make this a real enum + transition table, not scattered `if`s. |
| TS-10 | **Operator entry UX under time pressure** — keyboard-only, always-focused prompt, paste tolerant, instant visual echo of the parsed move + resulting FEN diff, audible/visual reject cue, no mouse required anywhere | R10 | S | TS-5, TS-9 | 100% of move entry happens with a clock running. A mouse-driven UI or a modal dialog costs seconds per move. Two-line protocol: `> e2e4` → echo `WHITE e2e4  (e2e4, legal, 20 legal replies)`. |
| TS-11 | **Resync-from-board workflow + undo/correction** — operator can declare "software is wrong, board says X": rebuild state from a corrected move list or pasted FEN, with a confirmation step and a logged correction event | R10 | M | TS-6 | The physical board is the source of truth (R10), so divergence *will* happen and the software must be able to lose gracefully. Resync must never silently rewrite history: append a `RESYNC` record to the journal (TS-14) and the game log so the judge sees exactly what happened. Prefer "re-enter the last N moves" over free-form FEN editing, because FEN editing is how you get an unplayable side-to-move/castling state. |
| TS-12 | **Opponent-clock observation entry** — operator records the opponent's remaining clock at each turn hand-off (and optionally by keypress), because the tiebreak (R12) and the engine's own time-advantage term both require it | R7, R12 | M | TS-13 | We cannot read the physical clock electronically. Manual capture at each move is ~2 s of operator work and is the *only* way to know the match-level time delta. Make it one keystroke (`t 7:42`), tolerate `7.42`/`442`, and store it in the journal and log. Without this, DF-3/DF-4/DF-8 are uncomputable. |

### Table Stakes — Group C: Game Lifecycle & Resilience

| ID | Feature | Rule | Complexity | Depends on | Notes |
|----|---------|------|------------|-----------|-------|
| TS-13 | **Dual-clock model** — our clock (15:00 + 10 s) and opponent's clock; our clock is *estimated* from turn boundaries, opponent's from manual entry; a single **sync key** re-bases the estimate to the physical clock and records the drift | R7, R12 | M | TS-9 | The physical clock is authoritative; the software clock is advisory. Design rule: **every deadline computation uses the pessimistic of (software estimate, physical estimate)**. Show drift explicitly (`est 7:41 / synced 7:36, drift −5s`). A hidden drift is a time forfeit waiting to happen. |
| TS-14 | **Crash-safe append-only journal** — every accepted move, clock reading, sync, resync, and result appended and flushed to disk *before* the next action; `resume` reconstructs the full game from the journal | R5 | M | TS-6 | Laptop sleep, battery, a stray Ctrl-C, or an engine segfault must not cost the game. `fdatasync`-per-move is cheap at this volume (a few hundred records). Test by `kill -9` mid-game. This is also your audit trail for R9/R10 disputes. |
| TS-15 | **Engine subprocess supervision + legal fallback move** — console owns the engine; detects death/hang, restarts it, replays `position`; if no `bestmove` arrives before the hard deadline, emits the best move from the last completed iteration (or any legal move) immediately | R5, R7, R10 | M | TS-6, TS-9 | Never let the *engine* be the reason we flag. Keep the last fully-parsed PV in memory at all times; a legal move from it is a valid emergency answer. Log the fallback as an event. |
| TS-16 | **Hard time-loss guard (dual watchdog)** — console-side absolute deadline = min(estimated clock, physical clock) − safety margin; at the deadline, send `stop` and force the current best move out | R7 | M | TS-13, TS-15 | Do not rely on Stockfish's internal `maximumTime` alone: it is computed from the numbers *we* gave it, which may be optimistic relative to the physical clock. The console's watchdog is the last line of defence and must be independent of the engine's own timer. |
| TS-17 | **Mandatory per-move log with all eight fields** — move number, color, chosen move in UCI, depth reached, nodes, evaluation, PV, time spent; `.txt`/`.log`, one file per game, incremental flush, `export-log` for judge hand-off | R9 | M | TS-15 | Six of eight fields come straight off Stockfish's `info` line (`depth`, `nodes`, `score`, `pv`, `time`; `seldepth` as a bonus) — see `uci.cpp::on_update_full`. The console must add **move number**, **color**, and **the move actually played** (not merely `bestmove`; they can differ after an illegal-announcement or fallback event). **Log both `time` (search ms from UCI) and wall-clock ms** for the move, because "tempo gasto" is ambiguous and wall clock is what the arbiter's clock measured. Record `score` verbatim including `mate N` / bound flags (`lowerbound`/`upperbound`). Never rewrite the file after the game: judges get the raw artifact. |
| TS-18 | **Threefold-repetition and 50-move tracking in the console, independent of the engine** — maintain the official position-key history and half-move counter; alert the operator "THREEFOLD — call the arbiter" / "50-MOVE — call the arbiter" | R12 | S | TS-6 | R12 says the arbiter declares these automatically, so the software's job is to *detect and alert*, never to self-adjudicate silently. Critical: Stockfish's internal `is_draw()` uses `rule50 > 99` and its repetition test is search-scoped (`position.cpp`), so the engine's opinion is **not** the official claim state. Keep a console-side Zobrist/FEN-key history of the whole game. |
| TS-19 | **Game result, resign, draw, and end-of-game clock capture** — record result, reason, and **both clocks at the moment the game ends**; support resign and agreed draw; freeze the log | R9, R12 | S | TS-13, TS-17 | The tiebreak is the *sum of remaining time across three games*, so the end-of-game clock reading is a scored quantity, not a nicety. If it isn't captured at game end it cannot be reconstructed. One command, one journal record, and it appears in the log header and in the match file. |
| TS-20 | **Match/series model** — game index (1/2/3), our color per game (**game 3 repeats game 1's color**, R11), per-game remaining-time record, running tiebreak totals, Armageddon flag; persisted as a single local JSON file | R11, R12 | M | TS-19 | Not "just bookkeeping": R11's color rule is non-obvious (a naive 1-2-3 alternation gets game 3 wrong and can cost the decider), and R12's tiebreak is a *match-level* objective. The model must exist before week 2 or every policy in the differentiator list is unimplementable. |
| TS-21 | **Pre-game checklist / arbiter-inspection mode** — one command that prints and asserts: engine identity + base commit, effective `SyzygyProbeLimit`, book line count and max ply, log path writable, asset paths local/absolute, threads/hash, GPU declared-or-not, network-clean assertion | R1, R3, R4, R8, R14 | S | TS-1, TS-2, TS-3 | The arbiter inspects at the start of *each* game (R14). A deterministic checklist turns a 3-minute nervy manual verification into a screenshot. It doubles as the pre-event dress-rehearsal gate. |

### Rule Traceability Matrix (no orphan rules)

| Rule | Subject | Covered by | Gap? |
|------|---------|-----------|------|
| R1 | Fork allowed; declare base commit; repo to judges; GPLv3 | TS-1, TS-21 | No |
| R2 | One **authored** decision component (eval / search / time mgmt), functional + defensible | **DF-1**, DF-3, DF-4 (the authored layer); TS-1 (provenance proof) | No — but note: DF-1 alone at "tuned constants" does **not** satisfy R2. See DF-1 notes. |
| R3 | Opening book ≤ 10 plies, local | TS-3, DF-7 | No |
| R4 | Tablebases ≤ 5 pieces | TS-3 (overrides upstream default 7) | No |
| R5 | Replicate **both** sides; keep state consistent; own laptop | TS-6, TS-14, TS-15 | No |
| R6 | One laptop per team, all games | TS-4 | No |
| R7 | No CPU/thread/RAM limit; 15 min + 10 s; software manages its own time | TS-12, TS-13, TS-16, **DF-1** | No |
| R8 | GPU allowed if local + declared | TS-21 (declaration), DF-11 | No |
| R9 | No specific UI required (CLI OK); mandatory per-move log, 8 fields, handed to judges after each game | TS-17, TS-19 | No |
| R10 | 4-step spoken protocol; UCI not SAN; board is truth; illegal move annulled | TS-5, TS-6, TS-7, TS-8, TS-9, TS-10, TS-11 | No |
| R11 | Colors by pairing; alternate; game 3 repeats game 1 | TS-20, DF-7 | No |
| R12 | Auto threefold/50-move; tiebreak by total remaining time; Armageddon 5/4, draw → Black, colors by lot | TS-18, TS-19, TS-20, **DF-3, DF-4, DF-8** | No |
| R13 | Pondering allowed; input delay is the team's problem; no guaranteed sync | **DF-2, DF-5**, TS-13 | No |
| R14 | Local libs allowed (e.g. `python-chess`); zero external requests; deps declared; arbiter verifies | TS-2, TS-21 | No |
| R15 | No repo size limit; weights by origin; team-trained weights count as authorship | TS-1 | No |

---

### Differentiators — Competitive Advantage

Ordered by expected match-win contribution per person-day. **DF-1, DF-2, DF-5, DF-8 are the committed four.**

| ID | Feature | Value Proposition | Rule | Complexity | Depends on |
|----|---------|-------------------|------|------------|-----------|
| DF-1 | **Authored time manager replacing `TimeManagement::init`** — protocol-latency-aware per-move budget with a match-level objective | The R2 authorship component *and* the R12 tiebreak lever. Ships the required deliverable and the highest-EV behaviour in one artifact. | R2, R7, R12 | L | TS-13, TS-16 |
| DF-2 | **Latency calibration** — measure announce→search-start and search-end→clock-press per move; feed a single `overhead_ms` into DF-1; re-estimate continuously from the log | Removes the single largest time-loss cause. Stockfish's default `Move Overhead` is **10 ms**; the real value here is **4,000–8,000 ms**. Uncalibrated, this alone can flag a team. | R13, R7 | M | TS-9, TS-13, TS-17 |
| DF-3 | **Match-aware draw policy** — a *policy layer* that sets draw value from match state (game index, score, time delta), not from a constant contempt | Turns "avoid draws" into "avoid draws **when a draw loses the tiebreak**." A constant contempt is a parameter tweak (explicitly *not* R2 authorship) and is wrong in at least half the match states. | R12, R2 | M | TS-20, DF-1 |
| DF-4 | **Total-remaining-time optimizer** — allocate time against Σ(remaining) across three games, not against the current game | The genuinely novel idea here. Time spent in a lost or dead-drawn game is a *tiebreak* cost, not just a game cost. Nobody else will model it. | R12 | M | TS-20, DF-1, DF-3 |
| DF-5 | **Ponder wiring (`go ponder` / `ponderhit` / `stop`)** — ponder the predicted reply; on match, `ponderhit` and keep searching; on mismatch, `stop` and re-`go` on the real move | Doubles as a time-saver: if the reply is already computed when the opponent presses, end-of-turn overhead collapses from ~5 s to ~1 s. Over 40 moves that is ~2.5 min banked — often the whole tiebreak. | R13 | M | TS-9, TS-15, DF-1 |
| DF-6 | **Resign / draw-offer advisor** — expected-value decision using position eval, match score, and remaining-time delta | Resigning a dead-lost game early *banks tiebreak time*. Compute-only teams never think about this. Explicitly an advisor: the human presses the key. | R12 | S/M | DF-3, DF-4 |
| DF-7 | **Opponent preparation: authored ≤10-ply book + line scouting** — a small, deliberately chosen book, and a record of what each likely opponent plays | At near-equal engine strength, the first 10 plies are where variance lives. Also the cheapest way to arrive at move 11 with full clock (book moves cost 0 s). | R3, R11 | M | TS-3, DF-1 |
| DF-8 | **Armageddon profile** — separate TM + draw policy for 5 vs 4 with **no increment**: as Black, draw = win (draw value strongly positive, trade into endings); as White, draw = loss (avoid simplification, take risk) | A whole match can end in Armageddon. One extra parameter set on top of DF-1/DF-3, essentially free once the policy layer exists. | R12 | S | DF-1, DF-3, TS-20 |
| DF-9 | **Book-to-engine handoff timing** — zero-time book moves, then a deliberate pre-warm/threshold at ply 11 | Avoids "wasting" budget on moves the book already answered, and avoids the classic ply-11 time spike when the engine takes over cold. | R3 | S | TS-3, DF-1 |
| DF-10 | **Operator-simulation harness** — replay games through the console with injected verbal delays, typos, illegal announcements, and off-by-one move entries | The only way to *test* a spoken-protocol console. Catches time losses and state-machine bugs before the event instead of during game 1. Highest reliability-per-day item on the list. | R10, R13 | M | TS-9, TS-10, TS-17 |
| DF-11 | **Event-hardware resource profile** — threads/hash/large-pages measured on the *event laptop*, not the dev box; declared GPU/NNUE config | R7 imposes no CPU limit, so leaving performance on the table is free Elo. Measure, don't assume; a dev-box-optimal thread count can be slower on the event machine. | R7, R8 | S | TS-21 |
| DF-12 | **Log-driven post-game diagnosis** — per-move time curve, eval swings, "where did we lose time / eval", blunder re-search at higher depth; produce a 1-page between-games brief | In a same-day Bo3 this is a between-games feedback loop. Also the artifact that makes the R2 argument concrete at judging ("here is the measured effect of our TM"). | R2, R9 | M | TS-17 |

#### DF-1 in detail — the authored time manager (the R2 deliverable)

R2 requires a *real* rewrite, and explicitly excludes "mere adjustment of existing parameters." So the deliverable must differ structurally from upstream, not just in constants. The defensible design:

**Objective statement (this is what you say at judging):** *choose the per-move time budget that maximizes expected match-win probability, where the objective includes the R12 total-remaining-time tiebreak and a hard constraint of P(time forfeit) ≈ 0 under spoken-protocol latency.*

**Four terms upstream does not have:**

1. **Protocol overhead budget.** Upstream: `optimumTime` from a log-fit of `timeLeft`, minus `Move Overhead` (default 10 ms). Ours: `overhead_ms` is a *measured, per-event* quantity covering (a) typing/confirming the opponent's move at turn start, (b) announcing, physically moving, and pressing at turn end. Clamp to `[1200, 6000]`, default **3500**, recalibrated from the log (DF-2).
2. **Increment-aware banking goal.** Required per-move spend to break even is `spend < 10 000 ms − overhead_ms`. With `overhead_ms ≈ 3500`, the break-even search time is ~6.5 s. So the early/middlegame target is deliberately **below** that (e.g. 2–4 s) to accumulate a buffer, with an explicit "banked seconds" counter as a first-class quantity. This is a different *policy shape* than upstream's `optScale`, which is a smooth function of remaining time only.
3. **Match-level time value.** `shadow_price_of_time` ∈ [0, 1] derived from match state: high when the match is likely to reach the tiebreak (scores level, game 1–2, no large time deficit); near zero in a must-win game or when already behind on cumulative time. Multiply the per-move budget by a function of this shadow price. This is the term that makes DF-3/DF-4/DF-8 possible.
4. **Ponder credit.** Upstream gives `+ optimumTime/4` when `Ponder` is on (`timeman.cpp`) — a blunt strength bonus that *spends more time*, the opposite of what we want. Ours: pondering is a *saving* mechanism. If a ponder hit is likely (reply matched our prediction), the end-of-turn overhead is ~1 s, so `overhead_ms` is reduced for that move and the budget shrinks accordingly.

**Anti-regression constraint:** never let the banked-time policy starve the engine below a floor that measurably costs Elo. Set a floor of ~1.5–2 s early, and validate with DF-10/DF-11 at 15+10 with simulated latency. If the SPRT/gauntlet shows a strength loss above a small threshold, the tiebreak gain may still dominate — but that is a *measured* decision, not a guess. Log the decision.

**Complexity:** L (4–6 pd) *because* it needs calibration data; the code itself is ~300 lines. Two of those days are measurement, and that is the part that makes it defensible at judging.

#### DF-3 / DF-4 in detail — the match-aware policy layer

Model it as a small pure function so it is unit-testable and arguable:

```
inputs : game_index(1..3), our_score, time_delta_s, game_phase, eval, is_armageddon, our_color
outputs: draw_value_cp, resign_threshold_cp, spend_multiplier, offer_draw(bool)
```

Concrete states worth encoding on day 1:

| Match state | Draw value | Spend multiplier | Behaviour |
|---|---|---|---|
| Game 1, scores level, time healthy | ≈ 0 (neutral) | 1.0 | Normal play; bank increment |
| Game 1–2, we lead the match | mildly draw-seeking | 0.9 | Trade into safe structures; protect the lead |
| Behind on match **and** behind on cumulative time | strongly draw-avoiding | 1.0–1.2 | Must win; spend freely, this game's clock is cheaper than losing the tiebreak outright |
| Leading the match, large time deficit | mildly draw-avoiding | 0.8 | We need the win or the clock; avoid long grinds |
| Game 3, match decided | n/a | 0.6 | Bank time; the result is already determined |
| Armageddon, we are Black | **strongly draw-seeking (draw = win)** | 0.8 | Solid, simplify, offer trades |
| Armageddon, we are White | **strongly draw-avoiding (draw = loss)** | 1.0 | Imbalance, avoid mass simplification |

Two guard-rails: (a) the policy may change *time and draw preference*, never legality or the log; (b) every policy decision is written to the log as an event so the judge sees the authored component operating live (this is what makes R2 defensible during the games, not just in the interview).

#### DF-10 in detail — why the simulation harness is not optional

The console's failure modes are *timing* failure modes and cannot be found by unit tests. Build a driver that:

- replays a scripted game through the console's stdin with **jittered, human-scale delays** (0.5–6 s) between the four protocol steps;
- injects: a duplicate move, an illegal move, a SAN-instead-of-UCI token, a mid-game `kill -9`, a clock-sync keypress, and a laptop-sleep gap;
- asserts: no double-move, no state advance on illegal input, no missed log field, correct side-to-move, correct cumulative-time accounting, and **zero timeouts** under a simulated 15+10 clock.

A full simulated three-game match is the dress rehearsal gate. Budget half a day; it will find the bugs that would otherwise appear in game 1.

---

### Anti-Features — Deliberately Not Built

Each of these is plausibly attractive to a 3-person team under deadline and each is a trap. The "Alternative" column is the *actual* thing to do instead.

| ID | Anti-feature | Why it looks good | Why it's a trap in 2 weeks | Alternative |
|----|--------------|-------------------|----------------------------|-------------|
| AF-1 | **GUI / graphical board** | Feels like a real product; nicer to demo | R9 states a command line is sufficient. A GUI contributes **0 Elo**, and every hour on it is an hour not spent on the latency/TM loop that decides the match. It also adds an event-loop concurrency bug surface next to the protocol state machine. | Plain terminal: a text board or FEN one-liner + big move echo (TS-8). If a board is wanted, reuse a library's ASCII/Unicode renderer in 20 lines. |
| AF-2 | **Own NNUE training / own evaluation function** | R2 lists evaluation as an acceptable authored component; training a net feels like "real AI" | Cannot train a competitive net in the time available; high regression risk vs the shipped Stockfish net; PROJECT.md already rules it out. Choosing eval as the R2 component also means fighting Stockfish's strongest subsystem. | Author the **time manager** (DF-1). It is the smallest surface area with the largest match-EV impact, and it is the one component nobody else authors. |
| AF-3 | **Camera / vision board-state recognition** | Automates the most error-prone step; sounds like a differentiator | Brittle under lighting/piece-occlusion, large effort, and R10 assigns board maintenance to *humans* and makes the board the source of truth — the software is not required to see it. One misread mid-game costs the match. | Operator entry + confirmation (TS-10) + resync (TS-11). Cheap, auditable, and the log proves what happened. |
| AF-4 | **Electronic clock integration / hardware bridge** | Removes manual clock tracking; precise tiebreak data | The regulation provides no data-output clock (PROJECT.md already scoped this out), so there is nothing to integrate with. Reverse-engineering a clock at the venue is a game-day disaster. | Internal dual-clock + one sync key (TS-13) + opponent-clock capture at hand-off (TS-12). |
| AF-5 | **Cloud / network anything** (sync, eval service, telemetry, remote logging) | Convenient dev workflow, dashboards | R14: Wi-Fi and mobile data must be **off** and are verified by the arbiter at the start of each game. Any dependency on a network path is a forfeit or a mid-game failure. Also R6: one laptop, no second device. | Everything local files (TS-2, TS-4, TS-14). Declare deps (TS-21). |
| AF-6 | **Tournament manager / bracket UI / multi-team support** | Feels like the "real" competition product | We are one team in one match at a time, on one laptop. Zero value, non-trivial state. | One local JSON match file (TS-20) and a printed checklist (TS-21). |
| AF-7 | **Opening book beyond 10 plies / large Polyglot book** | Stronger openings, "free" theory | **Illegal** (R3). A large book also tempts the team into believing prep is done. | Authored ≤10-ply book, hard-enforced in the loader (TS-3), chosen for the field (DF-7). |
| AF-8 | **6- or 7-piece tablebases** | Stronger endgames; upstream supports it (`SyzygyProbeLimit` default 7) | **Illegal** (R4), and storage/IO is heavy. The upstream default is a live hazard — assert 5 at startup. | 5-piece Syzygy only, `SyzygyProbeLimit = 5`, `Syzygy50MoveRule = true`, asserted in TS-21. |
| AF-9 | **Own search rewrite / engine from scratch** | "Real authorship"; avoids GPL questions | Ceiling ~2200–2500 Elo in two weeks (PROJECT.md); loses to any Stockfish fork. GPL is a non-issue because the repo is delivered anyway. | Keep Stockfish search; author the TM (DF-1). R2 is satisfied by *one* component, not by volume. |
| AF-10 | **LLM / network assistance during play** | Novel, sounds powerful | Prohibited in effect by R14 (no network) and unusable at 10 s/move latency. | Offline AI as a *factory*: SPRT, gauntlet, log mining (DF-12) — before the event, never during. |
| AF-11 | **Digital move transmission to the opponent** (a "move pipe", chat sync, shared state) | Seems to solve the "no synchronization guarantee" problem in R13 | R10 mandates a *four-step spoken protocol* with verbal confirmation; bypassing it is a rules-compliance risk and removes the very confirmation step that catches errors. R13 explicitly puts the delay burden on the team, not on a protocol addition. | Console *prompts the human script* (announce → confirm → move → press → enter) and treats input delay as a scheduling problem (DF-2, DF-5). |
| AF-12 | **Full UCI GUI-protocol parity** (MultiPV panels, WDL bars, analysis mode, `currmove` streaming) | "We already have the engine, just expose it" | Not needed to play; MultiPV and per-iteration `info` streaming cost nodes and pollute the mandatory log. | Emit only what the console consumes; parse the final `info` before `bestmove` plus periodic heartbeats (TS-17). |
| AF-13 | **Treating a contempt/parameter tweak as the R2 authored component** | One-line change, feels like authorship | R2 explicitly excludes "mere adjustment of parameters already existing in the base project." Claiming it invites a failed technical defence. | DF-1's structural rewrite (new objective, new terms) + DF-3's policy layer, both logged live. |
| AF-14 | **Distributed / multi-node SPRT cluster or cloud tuning** | Faster tuning, "we have threads to spare" | R7 gives no CPU limit on the *event laptop*, but there is still one laptop (R6) and no network (R14). Building orchestration is pure overhead. | Local SPRT across threads on the one strong laptop, time-boxed (DF-11). |
| AF-15 | **Elaborate PGN viewer / web dashboard for the logs** | Nice for the post-mortem story | The deliverable is a `.txt`/`.log` (R9); judges read files, not dashboards. | `grep`/`awk` one-pagers from the log (DF-12), plus a 1-page between-games brief. |

---

## Feature Dependencies

```
TS-1 build/provenance ──────────────┬──> TS-3 rule ceilings ──> TS-21 checklist
TS-2 offline-clean ─────────────────┘                          ▲
                                                               │
TS-5 UCI parse ──> TS-6 board replication ──> TS-18 repetition/50-move
                        │                             ▲
                        ├──> TS-7 illegal handling    │
                        ├──> TS-9 state machine ──> TS-10 operator UX ──> DF-10 sim harness
                        │            │
                        │            └──> TS-8 announce/confirm
                        │            │
                        │            └──> TS-13 clock ──> TS-12 opponent clock capture
                        │                   │  │
                        │                   │  └──> TS-16 time-loss guard
                        │                   │              ▲
                        ├──> TS-14 journal ─┤              │
                        │                   │              │
                        └──> TS-15 engine supervision ─────┘
                                     │
                                     └──> TS-17 mandatory log ──> DF-12 diagnosis
                                                   │
TS-19 result/end-clock ────────────────────────────┤
                                                   ▼
                                     TS-20 match model
                                        │      │      │
                                        │      │      └──> DF-8 Armageddon
                                        │      └──> DF-3 draw policy ──> DF-6 resign/draw advisor
                                        └──> DF-4 time optimizer
                                                   │
DF-2 latency calibration ──> DF-1 authored time manager <── TS-13, TS-16
                                     │  ▲
                          DF-5 ponder┘  └── DF-9 book handoff
                                     ▲
DF-7 authored book (≤10 ply) ────────┘        DF-11 hardware profile ──> TS-21
```

### Dependency Notes

- **TS-6 → everything.** Board replication is the spine. If it is wrong, every downstream feature is confidently wrong. Build and test it first; use a library (R14 permits it) rather than hand-rolling movegen.
- **TS-9 (state machine) must precede TS-10 and DF-10.** The simulation harness tests transitions; it cannot test a console whose phases are implicit.
- **TS-13 (clock) blocks DF-1, DF-2, DF-3, DF-4, DF-6, DF-8.** The clock interface should be defined on day 1 even if the implementation is a stub — otherwise the TM author and the console author integrate in the last two days and lose the whole calibration window.
- **TS-12 (opponent clock capture) is a hidden blocker.** Every match-aware policy needs the opponent's remaining time. It is manual and it needs operator buy-in from game 1, so it must be a day-1 console feature, not a week-2 idea.
- **TS-17 (log) enhances DF-12 and DF-2.** The log is the measurement substrate for both latency calibration and post-game diagnosis. Log generously from the first runnable build — retrofitting fields is how you lose the calibration data you needed.
- **DF-5 (ponder) improves DF-1 and DF-2.** Ponder hits reduce end-of-turn overhead, which *is* the term DF-2 measures. Sequence Ponder before final TM calibration, or calibrate twice.
- **DF-3 and DF-4 are the same mechanism, two uses:** one `shadow_price_of_time`/`draw_value` function consumed by the TM. Do not build them as two workstreams.

### Conflicts to Resolve Explicitly

| Conflict | Why | Resolution |
|---|---|---|
| Ponder vs. clock budget | Upstream adds `+optimumTime/4` when `Ponder` is on (`timeman.cpp`) — i.e. it *spends more* time. A naive port double-charges: engine spends more *and* our console reserves overhead. | Own the `Ponder` semantics: treat pondering as a *saving* (reduce `overhead_ms`), and do not inherit upstream's `+25%` rule. |
| Log verbosity vs. search speed | Streaming every `info` line (MultiPV, `currmove`) costs nodes and pollutes the R9 log. | Log the **last complete** `info` block before `bestmove`, plus a low-frequency heartbeat. Never log per-iteration in the mandatory file; write a separate `--debug` stream if needed. |
| Ponder search vs. TT pollution | Pondering the wrong move wastes TT entries that are then misleading on the real move. | On `stop` + re-`go`, send `ucinewgame` too aggressively? No — it clears the TT and loses the pre-warm. Prefer: keep the TT, accept some pollution, but *always* re-issue the full `position ... moves` so the root is correct. Measure both variants in DF-10. |
| Match-aware draw policy vs. R2 defence | A policy that deliberately steers toward draws can look like "not trying to win." | Log every policy decision with its match-state inputs. The defence is: *"the objective function is match win, and in this state a draw improves it"* — with data. |
| Resync-from-board vs. journal integrity | Resync rewrites state, which conflicts with an append-only truth log. | Journal is append-only; resync appends a `RESYNC` record with old and new state. The log remains a faithful history of *what we believed, when*. |

---

## MVP Definition

### Launch With — v1 (must be playable, end-to-end, by **day 6–7**)

The gate is: *can two people play a full simulated 15+10 game through the console against a peer engine, with correct log, correct clocks, and zero timeouts?* If yes on day 7, the tournament is winnable. If not, everything else is decoration.

- [ ] **TS-1** fork provenance, pinned commit, GPL headers, `info string` identity
- [ ] **TS-2** offline-clean assertion
- [ ] **TS-3** `SyzygyProbeLimit=5`, book ≤ 10 plies enforced
- [ ] **TS-5** strict UCI parse/normalize/reject
- [ ] **TS-6** board replication (library-backed)
- [ ] **TS-7** illegal-announcement handling (both directions)
- [ ] **TS-8** announce-and-confirm presentation
- [ ] **TS-9** explicit protocol state machine
- [ ] **TS-10** keyboard-only operator loop
- [ ] **TS-13** dual clock + sync key
- [ ] **TS-14** crash-safe journal + `resume`
- [ ] **TS-15 / TS-16** engine supervision + dual watchdog + forced legal move
- [ ] **TS-17** all eight log fields, flushed per move
- [ ] **TS-18** threefold / 50-move detection + arbiter alert
- [ ] **TS-19 / TS-20** result, end-of-game clock capture, Bo3 model with R11 color rule
- [ ] **TS-21** pre-game checklist
- [ ] **DF-1 (v0)** authored TM with a *simple but real* objective (overhead + increment-aware banking); enough to satisfy R2 and to be improvable

### Add After Validation — v1.x (days 8–11)

- [ ] **DF-2** latency calibration from measured logs — *trigger: v1 plays a full game*
- [ ] **DF-5** ponder wiring (`ponder`/`ponderhit`/`stop`) — *trigger: state machine stable*
- [ ] **DF-8** Armageddon profile — *trigger: DF-3 exists*
- [ ] **DF-3 / DF-4** match-aware draw + time optimizer (one function, one shadow price) — *trigger: TS-20 + TS-12 populated across a simulated Bo3*
- [ ] **DF-10** operator simulation harness + full simulated Bo3 — *trigger: v1 runnable; run before every TM change*
- [ ] **DF-7** authored ≤10-ply book + handoff timing (DF-9)
- [ ] **DF-12** log diagnosis one-pager
- [ ] **DF-11** event-laptop resource profile
- [ ] **DF-1 (v1)** final tuned TM, with measurement recorded for the R2 defence

### Future Consideration — v2+ (post-event; do not schedule)

- [ ] **DF-6** resign/draw-offer advisor — nice, but only if DF-3/DF-4 have settled; the human can resign.
- [ ] Any GUI, vision, network, bracket UI, NNUE work — see anti-features. These are v2 for a *different* product, not a deferred part of this one.
- [ ] Richer opponent scouting database — needs games against the field, which you don't have before the event.

### Team Allocation Reality Check

PROJECT.md proposes three parallel fronts (time / console / pipeline). The research says **the console is heavier than that framing implies**: the console slice (TS-5…TS-11, TS-13…TS-20) is ~13–15 person-days on its own. Recommended re-split for the 2 weeks:

| Person | Week 1 | Week 2 |
|---|---|---|
| **A — time & policy** | DF-1 v0 against a *mock* console (a 50-line driver that speaks UCI); define the clock/policy interface on day 1 | DF-2 calibration on the real console, DF-3/DF-4, DF-8, DF-1 v1 + measurement writeup for R2 |
| **B — console core** | TS-5, TS-6, TS-7, TS-9, TS-10, TS-8 (the protocol loop) | TS-13, TS-16, TS-18, TS-19, TS-20, TS-11 |
| **C — infrastructure & harness** | TS-1, TS-2, TS-3, TS-21, TS-14, TS-15, TS-17 (log) | DF-10 harness + dress rehearsal, DF-11 profiling, DF-12 diagnosis, DF-7 book, overflow on console |

Pipeline work (SPRT automation) is deliberately **not** a week-1 item: DF-1's value comes from measurement against the *console*, not from large-scale SPRT. Compress the pipeline to "SPRT works, one gauntlet, one tuning pass" and put the saved days into TS-14/TS-16/DF-10 — reliability beats a fifth Elo point.

---

## Feature Prioritization Matrix

User value here means **probability of winning the match**, not user delight.

| Feature | Match-Win Value | Implementation Cost | Priority |
|---|---|---|---|
| TS-17 mandatory log (8 fields) | HIGH — judge hand-off / disqualification | MEDIUM | **P1** |
| TS-6 board replication | HIGH — game integrity | MEDIUM | **P1** |
| TS-5 strict UCI parse | HIGH — wrong move = wrong game | LOW | **P1** |
| TS-7 illegal-announcement handling | HIGH — R10 exposes us every move | LOW | **P1** |
| TS-9 state machine | HIGH — prevents double-move/stale search | MEDIUM | **P1** |
| TS-13 / TS-16 clock + watchdog | HIGH — never lose on time | MEDIUM | **P1** |
| TS-14 journal + resume | HIGH — crash mid-game is fatal | MEDIUM | **P1** |
| TS-19 / TS-20 result + match model | HIGH — tiebreak is the win condition | MEDIUM | **P1** |
| TS-3 rule ceilings | HIGH — illegal = disqualification | LOW | **P1** |
| TS-1 provenance | HIGH — R1/R2 gate | LOW | **P1** |
| DF-1 authored TM | HIGH — R2 *and* tiebreak | HIGH | **P1** (start day 1) |
| DF-2 latency calibration | HIGH — biggest time-loss cause | MEDIUM | **P1** |
| DF-5 ponder wiring | MEDIUM-HIGH — banks ~2.5 min/game | MEDIUM | **P2** |
| DF-3 / DF-4 match-aware policy | MEDIUM-HIGH — the differentiator | MEDIUM | **P2** |
| DF-10 simulation harness | MEDIUM-HIGH — finds P1 bugs | MEDIUM | **P2** |
| DF-8 Armageddon profile | MEDIUM — only if match reaches it | LOW | **P2** |
| DF-7 book + DF-9 handoff | MEDIUM — variance and clock | MEDIUM | **P3** |
| DF-12 log diagnosis | MEDIUM — between-games feedback | MEDIUM | **P3** |
| DF-11 hardware profile | LOW-MEDIUM — free Elo | LOW | **P3** |
| DF-6 resign advisor | LOW-MEDIUM | LOW | **P3** |
| All anti-features | ZERO or negative | HIGH | **Do not build** |

---

## Competitor Feature Analysis

Field assumption: most teams are Stockfish forks at or near default settings, with a hand-rolled prompt loop. That is the baseline to beat.

| Feature | Typical Stockfish-fork team | Typical from-scratch team | Our Approach |
|---|---|---|---|
| Time management | Stockfish `Timeman` untouched, `Move Overhead` left at **10 ms** | Simple fixed fraction of remaining time | Authored TM with measured protocol overhead, increment-aware banking, match-level shadow price (DF-1/DF-2/DF-4) |
| Spoken protocol handling | Human reads `bestmove` off the terminal; no state machine; no illegal-move guard | Same, plus weaker engine | Explicit phase machine, validated in/out, illegal-announce logging, resync-from-board (TS-5/7/9/11) |
| Clock | Types `go wtime ...` from a wall clock, often stale | Same | Dual clock, pessimistic-of-two deadlines, sync key, opponent-clock capture (TS-12/13/16) |
| Mandatory log | `tee` of stdout; missing move number / color | PGN, missing depth/nodes | All eight fields, both search-time and wall-time, crash-flushed, judge-ready (TS-17) |
| Pondering | Off (or on, but mis-wired) | Off | Wired as a *time-saving* mechanism, not a strength bonus (DF-5) |
| Draw policy | Constant contempt, or none | None | Match-state draw value; Armageddon-specific inversion (DF-3/DF-8) |
| Crash resilience | None — restart loses the game | None | Journal + resume + engine respawn + forced legal move (TS-14/15) |
| Opening book | Large downloaded Polyglot book (**violates R3**) or none | None | Authored ≤10-ply, enforced, chosen for the field (TS-3/DF-7) |
| Tablebases | 5-piece, often with upstream default probe limit 7 | None | 5-piece, `SyzygyProbeLimit=5` asserted (TS-3/TS-21) |
| Tiebreak awareness | None — the most common blind spot | None | Explicit Σ-remaining-time accounting and time policy (TS-19/20, DF-4) |

**The exploitable asymmetry is the last row.** R12's tiebreak is a *match-level* objective that almost nobody models, and the same lever (protocol overhead, ~3–5 min/game) is the mechanism. A team that measures its overhead, wires ponder, and spends 3–4 s/move early while banking the rest will arrive at a drawn match with minutes more than an identical engine at defaults.

---

## Open Questions / Gaps

- **Does the increment apply in Armageddon?** R12 states only the base times (5 / 4 min). Assumed **no increment**; the TM must be told `winc 0`/`binc 0`. Confirm with the organizers — this materially changes DF-8.
- **Do the clocks keep running after the game ends, and does the loser's remaining time count in the tiebreak?** R12 says the sum is over three games; it is not explicit about games that end early by resignation or mate. Assumed: the clock stops at game end and that reading is the one summed. Capture it regardless (TS-19), and ask.
- **Is "tempo gasto" in R9 search time or wall-clock time?** Ambiguous. Log both (TS-17) — cheap, and removes the question.
- **Does the arbiter expect the log per game or per match?** R9 says handed over after *each* game. One file per game, plus an export command.
- **How much input delay is realistic?** No field data. DF-2 exists precisely to replace the guess with a measurement; default 3500 ms until calibrated. Measure at the dress rehearsal with the actual operator, on the actual laptop.
- **Actual strength delta from aggressive banking** is unknown without SPRT against the field. Treat as a measured trade-off, not a guess; the policy's floor is the safety valve.
- **R11 pairing order** determines whether we are White in games 1 and 3. This is external information we do not have at research time; the match model must accept it as an input, and prep must cover both colors.

---

## Sources

- `docs/competition-rules.md` — verbatim organizer FAQ, R1–R15. **Primary source for every table-stakes trace in this document.** (HIGH)
- `.planning/PROJECT.md` — project framing, out-of-scope decisions, three-front team split. (HIGH, internal)
- Stockfish `src/timeman.cpp` (master, 2026) — `TimeManagement::init`, `optimumTime`/`maximumTime`, `Move Overhead`, `+optimumTime/4` ponder rule, `timeAdvantage` damping. Read directly. (HIGH)
- Stockfish `src/uci.cpp` (master, 2026) — `info` line field set (`depth seldepth multipv score nodes nps hashfull tbhits time pv`), `go ponder`/`ponderhit`/`stop` semantics, `position ... moves`, `bestmove ... ponder`. Read directly. (HIGH)
- Stockfish `src/engine.cpp` (master, 2026) — option defaults: `Move Overhead 10`, `Ponder false`, `MultiPV 1`, `SyzygyProbeLimit 7`, `Syzygy50MoveRule true`. Read directly. (HIGH)
- Stockfish `src/position.cpp` (master, 2026) — `is_draw()` (`rule50 > 99`) and `is_repetition()`; establishes that engine-internal draw detection is search-scoped and not an official claim state. Read directly. (HIGH)
- Web search providers (Exa/Brave/Tavily/Firecrawl/Ref) are disabled in `.planning/config.json`; live competitive data on this specific competition was not retrievable. All competitive judgments above are inference from the rulebook + engine source and are marked MEDIUM. (LOW coverage, MEDIUM confidence)

---

*Feature research for: competition chess engine (Stockfish fork + spoken-UCI console)*
*Researched: 2026-10-26*
