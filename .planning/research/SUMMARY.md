# Project Research Summary

**Project:** ChessChallendIII — Stockfish fork for the III Chess Challenge
**Domain:** Competition chess engine + human-mediated spoken-UCI console + offline test pipeline
**Researched:** 2026-10-26
**Confidence:** HIGH on *what to build and how*; MEDIUM on *how long it takes with three specific people* and *what the field looks like*

---

## Executive Summary

This is not an engine-strength project. Stockfish 19 at defaults is ~3650 CCRL and will out-calculate anything in a student field; all four research files converge on the same conclusion — **matches are lost by the software, not by the chess.** Six failure classes account for every way to leave without the trophy: disqualification (authorship/compliance), loss on the clock, loss on the protocol, loss on the machine, loss on the tiebreak, and a non-compliant log. The product is therefore a **reliability-and-clock system wrapped around a strong engine**: a Python console that is the sole authority over the board replica, the clock, the match state and the Rule 9 log; a narrow, frozen UCI contract; a C++ fork that decides only *how* to spend a budget it is told; and an authored time manager inside the engine that is simultaneously the Rule 2 deliverable and the Rule 12 tiebreak lever.

The recommended build is **contract-first, then two parallel tracks behind that contract.** On day 0 all three people freeze `docs/PROTOCOL.md` (the exact `go` line, the TM trace format, the `info` fields consumed, one-outstanding-`go`) and `docs/LOGBOOK.md` (the Rule 9 schema including book/terminal variants), ship the *unmodified* Stockfish binary, and ship two mocks. Nothing then blocks: the console owner codes against `mock_engine.py`, the TM owner codes against `mock_gui.py`, the infra owner does provenance/offline/guards/harness. The tracks converge on one non-negotiable **day 6/7 WIN GATE**: a complete simulated best-of-3 at 15+10, offline, on the match laptop, spoken protocol, every half-move logged with all eight fields, zero timeouts, stale-bestmove and `kill -9` injections green, and cumulative remaining clock ≥ the upstream-TM baseline. Only if that gate is green does the match-policy layer start. Compliance artifacts are built *during* development because they are the authorship evidence — a design document committed after the code is the strongest single signal *against* an authorship claim.

The risks are specific and already quantified, not speculative. Default Stockfish is actively harmful under this protocol: `Move Overhead` is 10 ms against a 4–8 s human tail (worth 3–5 min/game — the entire tiebreak); the untouched allocator spends **19,757 ms on move 1** and **20,785 ms on move 2** at 15+10, a net **−10 s per move** against the bank; `Ponder` adds 25 % to `optimumTime` and does not reset `startTime` on `ponderhit`; `SyzygyProbeLimit` defaults to **7**, an automatic Rule 4 violation; and sending `movetime` sets `time[us]=0`, silently disabling the very component the team must defend. The binding constraint is the calendar: table stakes are 21–24 person-days against ~21 effective person-days in two weeks. A two-week plan has zero slack; a one-week plan can only ship a survival entry. This synthesis therefore prescribes the cut order in advance — and notes the one piece of good news: **the winning edge, the clock, is the cheapest artifact in the project.** A team that ships only the survival subset still beats a better-tuned fork that left `Move Overhead` at 10.

**One-sentence strategy:** own the clock end-to-end (console reserve + authored in-engine allocator + ponder as a time-*saver*), turn every rule violation into a startup assertion, and prove authorship with artifacts created *before* the code.

**Verdict:** winnable in 2 weeks with disciplined scope; in 1 week viable only as a survival entry, and only if the book and the policy layer are dropped on day 0.

---

## Critical Technical Findings (read these before planning anything)

Eight findings decide the match. Each is followed by the mechanism that makes it impossible rather than merely discouraged.

### CF-1 — 10 ms `Move Overhead` against a 4–8 s human tail is the tiebreak, handed over for free

Stockfish assumes a GUI presses the clock within milliseconds of `bestmove`. Our clock runs from the opponent's press to *our* press and includes: typing/confirming their move (2–5 s), searching, announcing, waiting for the repeat-back, moving the piece, pressing (3–8 s). Over 40 moves that is **3–5 minutes per game** — precisely the Rule 12 tiebreak.

The option cannot fix this, and raising it is a trap. It is amortised `moveOverhead × (2 + mtg)` against the projected horizon: at 10 ms that is 520 ms over 50 moves (invisible); at the 5000 ms maximum it subtracts **260 s** from `timeLeft`, crushing the allocator while still not modelling the tail. Simulation (model, MEDIUM confidence, not a measured game): 12 s/ply overhead at 15+10 flags at ply 19 (move 10); with `Ponder=true`, ply 16; with `Move Overhead=5000`, ply 23 — still flags. Even with *no* human in the loop, 24 games at `tc=10+0.1` with default overhead produced **1 timeout** (measured).

**Enforcement:** two layers, no double count. Console reserves the human tail and sends a reserve-discounted `wtime`. Engine `Move Overhead = 100` (IPC/OS only) and is asserted at startup. The authored TM carries the human overhead as an explicit `H × overhead` term. Every move logs `wall_ms − engine_ms`; that residual *is* the measured latency and the calibration input.

### CF-2 — `SyzygyProbeLimit` defaults to 7; that is a Rule 4 violation waiting to happen

Upstream's default silently permits 6- and 7-piece probing, and Rule 4 forbids the tables outright. The realistic path to the violation is mundane: someone downloads "all Syzygy" for analysis and the game laptop points at that directory.

**Enforcement:** `setoption name SyzygyProbeLimit value 5`, `Syzygy50MoveRule true`, a startup assertion `Tablebases::MaxCardinality <= 5`, a filename piece-count parse over the TB directory that refuses to start on any 6/7-piece name, `tb_game/` vs `tb_analysis/` segregation (same laptop is fine — same *directory* is not), and a SHA-256 inventory in `PROVENANCE.md`.

### CF-3 — The untouched allocator spends ~20 s on move 1 at 15+10

Measured on the built `sf_19`: `go wtime 150000 btime 150000 winc 10000 binc 10000` → **19,757 ms**, depth 28, 4.14 M nodes on move 1; **20,785 ms** on move 2 after `1.e4 e5`. Against a 10 s increment that is a **net −10 s per move** — the bank drains from move 1 and the tiebreak is lost before the middlegame. This is the empirical justification for the whole authored component; it belongs in `docs/timeman/00-DESIGN.md` as the baseline figure because it is measurable in 20 seconds.

**Enforcement:** the authored TM's explicit solvency condition is `spend < inc − overhead` (break-even ≈ 6.5 s at a 3.5 s overhead), with an early/middlegame target of 2–4 s and **"banked seconds" as a first-class output**, not a side effect.

### CF-4 — Ponder: +25 % spend and a `startTime` that is never reset

Two verified side effects, and inheriting either one wrongly costs the game:
1. `if (options["Ponder"]) optimumTime += optimumTime/4;` — **every normal move** gets 25 % more time while the option is on. That directly fights the tiebreak.
2. `startTime` is set when `go` is parsed and is **not** reset on `ponderhit`. `check_time()` also returns early while pondering, and the engine sets `stopOnPonderhit` instead of stopping.

The second is not a bug to fix — see contradiction R6. After a long ponder, elapsed already exceeds `maximum`, so a `ponderhit` returns the deep result **almost instantly at zero cost to our clock**. Patching `startTime` would take that free move away.

**Enforcement:** in the authored TM, **delete the +25 % clause** and treat pondering as a *saving* (overhead drops to ~1 s on a hit, so the budget shrinks). Keep `startTime` behaviour as upstream. Set `Ponder=false` in the game config until the authored TM is default and verified; then `true`. Cap ponder by depth/nodes for thermal safety; log hit/miss/pondered-time.

### CF-5 — `movetime` disables the authored time manager (a direct Rule 2 exposure)

If the console sends `movetime` instead of clock fields, `limits.time[us]` stays 0 and `TimeManagement::init` takes the early return `optimumTime = maximumTime = NoBound`. **The authored component never executes.** During the arguição you would be defending a component that was dead in every game. `movestogo` is the same class of error: `limits.movestogo != 0` selects the "x moves in y seconds" branch (`optScale = min((0.88 + ply/116.4)/mtg, …)`), silently degrading the allocator. 15+10 is sudden death.

**Enforcement:** `PROTOCOL.md` freezes `go [ponder] wtime <int> btime <int> winc 10000 binc 10000` and forbids both tokens. A CI grep fails if `movetime` appears in the game path. The engine emits a `tm=custom-…` attestation on every search and the console copies it into the log line — so the log itself proves the component ran. The console watchdog is the only hard bound, applied out-of-band with `stop`.

### CF-6 — Rule 11: game 3 repeats game 1's colour

A naive 1-2-3 alternation gets the decider wrong and can cost the match. The colour sequence is **external input** (which side of the pairing we are on), not something to infer.

**Enforcement:** `MatchController` holds an explicit `COLOR_SEQUENCE` derived from "we are White in game 1", unit-tested for both cases, printed in the pre-game checklist, and logged in every game header. Prep must cover both colours because pairings are unknown at build time.

### CF-7 — The stale ponder `bestmove` is the most likely game-losing bug

On a ponder miss the console sends `stop`; the engine still owes — and will send — a `bestmove` **for the speculative position**, arriving while the console is preparing the real search. A single-handler console plays a move for a board that does not exist. It appears only against a real opponent, because mocks are usually too well-behaved.

**Enforcement:** monotonic `search_id` on every `go`; drop any `bestmove` whose id is not current **or** while `discarding == True`; assert exactly one outstanding `go`; journal `STALE_BESTMOVE`. Write `test_ponder_discard.py` **before** the handler — a fixture that scripts `stop` followed by a delayed `bestmove`.

### CF-8 — The compliance artifacts *are* the authorship evidence; retrofitting fails

`PROVENANCE.md`, a dated design document committed **before** the implementation, an `upstream|custom` runtime switch defaulting to `custom`, granular per-author git history, and an `experiments/` directory with raw results. A design doc whose first commit is after the code is the strongest single signal *against* an authorship claim. Rule 2 excludes "mero ajuste de parâmetros já existentes" — the dossier must demonstrate a different *decision procedure*, not different numbers. Full contents in [Authorship Defense](#authorship-defense-the-dossier-a-judge-will-accept).

### Three findings that are easy to miss and expensive to miss

- **The clock must be backdated at move entry.** If our clock starts when the operator finishes typing instead of at the opponent's press, our belief is `L` ms too generous **on every move** — 72 s of phantom time over 60 moves at 1.2 s, i.e. a loss on time that looks impossible. `since = T_typed − input_latency_ema`. This is the single highest-value line of clock code in the project.
- **Verify the wire format on the built binary before writing the parser.** `info string` lines are not analysis; the last `info` can carry `upperbound`/`lowerbound`; `bestmove (none)` and `0000` exist; and `sf_19` **terminates the process** with `info string CRITICAL ERROR` on an illegal `position`. Whitelist line types; never regex-hack.
- **`setoption` during a ponder deadlocks the console.** It calls `wait_for_search_finished()` and a ponder never finishes on its own — the console hangs with the clock running. Queue option changes and apply them at the next `IDLE`, before the next `position`.

---

## Key Findings

### Recommended Stack

Pin **Stockfish 19 (`sf_19`, 2026-09-05)** — never a nightly, never master. `sf_19` has no `timeAdvantage` clause at all, while master added one plus a different default net (`nn-c9e480e92425.nnue` vs `nn-1a298aa575a0.nnue`); a moving target makes the provenance declaration and the net name match unverifiable. The clone must be a real `git clone --branch sf_19` with history retained and tagged `base-sf19` — the reference SHA is `f879373d916914de3a478aabb4226e6460c17d15`, to be verified at clone time rather than copied blind.

The console is Python 3.12 + `python-chess` 1.11.2 (GPL-3.0-or-later, zero runtime dependencies, vendored so no `pip` at the venue). The harness is **fastchess v1.8.2-alpha** (MIT, `make -j`, no external deps, pentanomial SPRT, `-recover`), not cutechess-cli (Qt ≥ 6.8 is an offline-install risk and it lags at high concurrency). Tablebases are 3-4-5 Syzygy only (939 MiB, 290 files) — **downloaded, not generated**. No GPU; NNUE inference on CPU is the right shape and a GPU adds thermal risk for nothing.

Two decisive packaging facts from STACK: a normal `make build` produces a **self-contained 95 MB binary with the net embedded**, so ship that (no `EvalFile` path to get wrong); and **the build is not offline until `make net` has run** — do it before the event, archive the tree, and prove a clean `unshare -n make -j` on the match laptop. `profile-build` (PGO) measured **2 m 47 s**, *faster* than plain `build` (3 m 11 s) because the instrumented pass skips LTO, and it produces an identical bench node count (2,497,913) — do it once on the final tree.

**Core technologies:**

| Layer | Choice | Why |
|---|---|---|
| Engine base | Stockfish 19 (`sf_19`) | +44 Elo over SF18; single-net SFNNv16 removes dual-net complexity; stable origin commit to declare |
| Authored component | From-scratch `TimeManagement` allocator in `src/timeman.{h,cpp}` | Rule 2 deliverable *and* Rule 12 lever in one artifact |
| Console | Python 3.12 + `python-chess` 1.11.2 | `parse_uci` raises on illegality; Polyglot reader; zero deps; Rule 14 explicitly permits it |
| UCI transport | **Own ~250-line transport** (not `engine.play()`) | `play()` debits our own search time from the next budget and hides the stale-bestmove race |
| Harness | fastchess v1.8.2-alpha | No deps, pentanomial SPRT, EPD openings, resumable |
| Book | Own-generated Polyglot `.bin`, ≤10 half-moves | Python reader; **no writer in python-chess** → ~40 lines of `struct.pack(">QHHI")` |
| Endgame | Syzygy 3-4-5 only | 939 MiB on an internal SSD; probe limit **must** be overridden to 5 |
| Licence | GPL-3.0-or-later throughout (console included) | Stockfish headers say "or later"; `python-chess` is GPL-3.0+ so an MIT console would conflict |

**Verified numbers to plan against** (measured on a 12-thread box; treat as a floor for a stronger laptop):

| Metric | Value |
|---|---|
| `build` / `profile-build` | 3 m 11 s / 2 m 47 s |
| Binary, net embedded | 95 MB (net 98,511,183 B = 93.9 MiB) |
| `bench` | 2,497,913 nodes (identical pre/post PGO) |
| nps, 1 / 4 / 12 threads | 274k / 779k / 1,330k |
| **SF19 at 15+10, move 1 / move 2** | **19,757 ms / 20,785 ms** |
| fastchess `10+0.1`, concurrency 12 | 24 games / 84 s ≈ **1,000 games/h**, 1 timeout at default overhead |
| fastchess `1+0.01`, concurrency 12 | 80 games / 30 s ≈ 9,600 games/h (smoke tests only) |

**SPRT discipline:** `elo0=0 elo1=5 alpha=beta=0.05`, `tc=10+0.1`, `-repeat`, `option.Move_Overhead=100` on **both** engines, `-report penta=true`, `-pgnout … timeleft=true`. Resolution is typically 400–2,000 games = 25 min – 2 h. **Never SPRT at 15+10** (~5 min/game). SPRT results never justify changing a constant the same day: run the test, keep the PGN, mine the losses, then change the algorithm.

### Expected Features

The single most important product finding: **the operator loop is the product**, and the console is heavier than `PROJECT.md`'s three-front split implies — **~13–15 person-days on its own**. Table stakes cost **21–24 raw person-days**, which against ~21 effective person-days in two weeks means the budget is fully consumed before a single differentiator.

**Must have — compliance and environment:** pinned fork provenance with declared base SHA and a published repo (TS-1); offline-clean runtime with an asset-path assertion (TS-2); hard rule ceilings in code — `SyzygyProbeLimit=5`, book ≤10 half-moves, startup assert (TS-3); single laptop, single process (TS-4).

**Must have — spoken protocol and board replication (the core):** strict UCI parse/normalise/reject-SAN with a typed error (TS-5); board replica advanced only by validated moves (TS-6); illegal-announcement handling in both directions, clock keeps running (TS-7); an **ANNOUNCE field populated only by `bestmove`**, large and unmissable (TS-8); an explicit phase state machine with side-to-move guards (TS-9); keyboard-only operator loop with instant echo (TS-10); resync-from-board + undo that appends a `RESYNC` record rather than rewriting history (TS-11); opponent-clock capture at every hand-off (TS-12).

**Must have — lifecycle and resilience:** dual clock with a single SYNC key, pessimistic-of-two deadlines, visible drift (TS-13); crash-safe append-only journal with `resume` (TS-14); engine supervision, restart, replay, and an always-available legal fallback move (TS-15); an independent console-side watchdog that sends `stop`, never `quit` (TS-16); the Rule 9 log — all eight fields for **every half-move including the opponent's**, `engine_ms` *and* `wall_ms`, bound flags preserved (TS-17); console-side threefold/50-move detection and arbiter alert (TS-18); result + **both clocks at game end** (TS-19); Bo3 match model with the R11 colour rule and running tiebreak totals (TS-20); a pre-game checklist / arbiter-inspection mode (TS-21).

**Should have — the four committed differentiators:** DF-1 authored TM; DF-2 latency calibration; DF-5 ponder wiring; DF-3+DF-4 as **one** policy function (match-aware draw value + shadow price of time). DF-8 (Armageddon), DF-6 (resign advisor) and DF-9 (book handoff) then fall out as parameter sets. DF-10 (fault-injection harness) is not a differentiator — it is how the table stakes get verified. DF-7 (book) and DF-12 (log diagnosis) are opportunistic week-2 work and must not become their own phase.

**Defer / never:** any GUI (0 Elo, new concurrency bug surface); own NNUE or own eval (cannot beat the shipped net in the time available, and it is the worst subsystem to fight); camera board recognition; electronic-clock integration; anything network or cloud (Rule 14); tournament/bracket UI; >10-ply or large downloaded books; 6/7-piece TBs; own search/engine; LLM in-game; a "move pipe" to the opponent (bypasses the four-step protocol that catches errors); full UCI GUI parity; contempt-as-authorship; distributed SPRT; a PGN dashboard.

**The exploitable asymmetry is the last row of FEATURES' competitor table: nobody models the tiebreak.** A team that measures its overhead, wires ponder as a *saving*, and spends 3–4 s/move early while banking arrives at a drawn match minutes ahead of an identical engine at defaults.

### Architecture Approach

A Python console is the sole authority over time, board state and the log; it drives a C++ Stockfish fork through a narrow, **instrumented** UCI contract; **the engine decides *how* to spend a budget it is told, never *what* the budget is.** Separate OS processes, UCI over pipes, no FFI — chosen for crash isolation, because the console must be able to `stop` a process that shares nothing with it, and because the same binary is the SPRT subject.

**Three invariants do most of the work:**

1. **The engine never learns wall-clock time; the console never reads engine internals.** Authority flows one way (console → engine), observation the other (engine → console, via `info` and one `info string TM …` trace line).
2. **Exactly one `go` is outstanding at any time.** UCI has no request ids, so serialisation plus a monotonic `search_id` is the only correct discipline.
3. **The Rule 9 log is a projection of the journal, never a parallel write path.** Board, clock belief, match standing and log are all recomputed from an fsynced append-only event stream — which also gives crash recovery and loss mining for free.

**Major components:**

| Component | Owns | Must not own |
|---|---|---|
| **TimeManager** (engine) | `(time, inc, ply, options)` → `optimum`, `maximum`, instant-move decision | The real clock, input latency, tiebreak standing |
| **UCI transport** (console) | Pipe lifecycle, line framing, `search_id`, `info` cache, watchdog | Legality, time policy |
| **BoardState** (console) | Replica, move list, legality, game-over detection | Being the source of truth (the physical board is) |
| **ClockModel** (console) | Belief of both clocks, sync snapping, drift/latency EMAs | Allocating per-move search time |
| **BudgetPolicy** (console) | `reserve` and the `wtime` projection | Choosing `optimum`/`maximum` |
| **MatchController** (console) | Game index, colours, cumulative time, Armageddon | Per-move play |
| **Journal → MoveLog** | Every event; Rule 9 projection | Deciding anything |
| **Book** (console) / **TB** (engine) | First ≤10 half-moves / ≤5-piece probing | — |

The book/TB split is deliberate and asymmetric: the book lives in the console because Rule 3 caps it and the decision must be attributable in the log (`src=book`, `d=0 n=0 score=none`); the tablebase stays in the engine because Stockfish's probing is already correct, and Rule 4 compliance is enforced by *which directory* `SyzygyPath` points at.

**Build-order insight:** nothing blocks on the fork. Stockfish is already a working UCI engine, so shipping the *unmodified* binary in hour 1 unblocks both other tracks. The only real shared dependency is **two frozen documents**.

### Critical Pitfalls

Beyond CF-1…CF-8, five pitfall families decide games:

1. **Board/software divergence "fixed" by replaying from memory.** Rule 10 makes the physical board the source of truth, so divergence *will* happen. Mitigation: display the board + FEN every move; a `VERIFY` that diffs a typed FEN against the replica; `RESYNC` that stops, validates, confirms, and logs; prefer re-entering the last N moves over free-form FEN editing (a FEN resync loses repetition history and takes `rule50` only from the FEN). **Never auto-apply a predicted/ponder move to the committed board.**
2. **The operator announces a PV instead of `bestmove`.** The PV's first move changes between depths and is on screen before `bestmove` arrives. Mitigation: one ANNOUNCE field, locked until `bestmove`, visually distinct from the PV; during play the PV is not a primary line; log announced-vs-bestmove and treat a mismatch as a bug.
3. **Fatal-engine-exit class.** `position … moves <illegal>` → `terminate_on_critical_error` → `exit(1)`. `Hash` too large → `Failed to allocate … for transposition table` → exit. Undrained stderr → the engine blocks. Missing `ucinewgame` → `originalTimeAdjust`, `previousTimeReduction`, `bestPreviousScore` and the TT leak across games. Mitigation: validate every move twice (generator + physical board), `Hash ≤ min(4096 MB, 50 % RAM)`, stderr to a file thread, `ucinewgame` + `isready` at every game start.
4. **Log non-compliance.** Most common omissions are PV, nodes and time; then opponent moves; then blank fields for book/terminal moves; then `.csv` as the only artifact (the rule says `.txt`/`.log`). Mitigation: one line per half-move, schema frozen in `LOGBOOK.md` on day 0, `log_lint` after every game, `fsync` per line, export at the table.
5. **Game-day environment.** Wi-Fi re-enabled by an updater or a saved SSID (the arbiter checks at the start of *each* game, so a mid-game re-enable can go unnoticed and is still a violation); undeclared GPU; unpinned dependencies; thermal collapse (nps −20–40 % after 5–15 min, MEDIUM confidence) breaking the TM's assumptions; no assigned roles. Mitigation: `rfkill block all` + airplane mode + disable auto-connect/updaters + `unshare -n` rehearsal; `requirements-game.txt` split from dev; 30–60 min sustained-load run; `doctor` green; Operator/Timekeeper/Coach assigned with a one-page runbook.

**Strategic pitfall (H1):** optimising Elo when the field is all Stockfish forks. Treat Elo as a **constraint** ("do not regress"), never the objective. The scoreboard metrics are: zero time forfeits, zero protocol incidents, 100 % log compliance, positive time bank, tiebreak win rate, crash recovery time.

---

## Contradictions Resolved

The four files disagree in eight places. Averaging them would produce a plan that is wrong in the specific ways that lose matches, so each is resolved explicitly with a decision.

| # | Conflict | Sources | Resolution |
|---|---|---|---|
| **R1** | **Phase order.** provenance → logging → book → TM → tuning (STACK) vs compliance → offline baseline → TM → console → guards → pipeline → rehearsal (PITFALLS) vs contract-first parallel tracks + serial gates (ARCHITECTURE) vs console-first (FEATURES) | all four | Adopt ARCHITECTURE's **structure** (frozen contract, parallel tracks, gates), FEATURES' **weighting** (console = critical path), STACK's **day-0 content** (provenance, pinned base, offline build), and PITFALLS' **content coverage** as the compliance checklist. **Reject PITFALLS' order** (TM before console) — its own text says the phases are provisional and map "by deliverable," not by schedule. Result: one sequence, P1→P7 below. |
| **R2** | **Critical path.** FEATURES says console-first; STACK puts TM early | FEATURES, STACK | **Both are true, on different axes.** The console gates the *schedule* (~13–15 pd, nothing end-to-end verifiable without it, and it sits on one person). The TM gates the *trophy* (Rule 2 deliverable + tiebreak lever) but gates nothing else, because it is written against `mock_gui.py` from day 1 behind the frozen `go` contract. Neither track may wait on the other; the day-0 contract freeze is what makes that possible. |
| **R3** | **Timeline.** 21–24 person-days of table stakes vs ~21 effective | FEATURES | **2 weeks = zero slack; 1 week = survival entry only.** Do not plan to "find" the difference. Pre-decide the cut order (below), and treat the WIN GATE as fixed and the scope as variable. |
| **R4** | **`Move Overhead` value.** 100 ms (STACK, ARCHITECTURE) vs measured p95 capped at 5000 (PITFALLS) vs 4–8 s real (FEATURES) | all four | **Two layers, no double count.** Console reserves the human tail (`return_latency_p95 + abs(drift) + 2σ + IPC slack`) and sends a reserve-discounted `wtime`. Engine stays at **100** (IPC/OS only) and is asserted. The authored TM carries the human overhead explicitly as `H × overhead`. 5000 is not a fix: amortised × (2+mtg) it subtracts 260 s from `timeLeft` and crushes the allocator. |
| **R5** | **Ponder option.** `Ponder=true` is "correct here, ponder time is free" (ARCHITECTURE) vs "+25 % on every normal move is harmful" (STACK, FEATURES, PITFALLS) | ARCH vs others | **Both true in different code states.** With upstream `timeman.cpp`, `Ponder=true` costs 25 % on non-ponder moves → **off**. Once the authored TM deletes that clause and treats ponder as a saving → **on**. Never ship `Ponder=true` with upstream time management. |
| **R6** | **`ponderhit` and `startTime`.** Reset `startTime` to now (PITFALLS option a) vs never reset it (ARCHITECTURE §5.1) | PITFALLS vs ARCH | **Do not reset.** Upstream's non-reset means a long ponder produces an almost instant, deep, free reply — exactly the behaviour we want. The authored divergence is removing the +25 % and crediting overhead, not breaking the free move. (PITFALLS' option (b), a console-side `stop`+re-`go`, remains the fallback if TT behaviour misbehaves.) |
| **R7** | **Book ply cap.** `board.ply() < 10` (STACK) vs `ply <= 10`, "the 10th half-move may be a book move, the 11th must be search" (FEATURES, PITFALLS) | STACK vs others | **STACK is right; the others are off by one.** Define the counter as *half-moves already played* (0 at start). The decision made at counter = 9 produces the 10th half-move, so a book move is legal only while `halfmoves_played < 10`; the first search move is chosen at counter = 10. `ply <= 10` would permit an **11th** half-move. One constant `BOOK_MAX_PLY = 10`, one boundary test, and the operator display shows `ply / book_remaining`. |
| **R8** | **Console implementation.** `python-chess` `engine.play(info=INFO_ALL)` (STACK) vs a custom transport (ARCHITECTURE) | STACK vs ARCH | **Split by layer.** `python-chess` for `Board`, legality, Polyglot (read) and Syzygy (read, tests only). **Own transport** for the game path: ~250 lines with `search_id`, a `discarding` flag, stderr drain, and a whitelisted `info`/`bestmove` parser. `play()`'s clock adjustment debits our own search time from the next budget, ignores input latency and physical sync, and hides the ponder-miss race. `play()` is fine for prototyping and SPRT glue, never for the match. |

**One scope clarification, not a contradiction:** "from-scratch time manager" means a from-scratch **decision procedure**, not from-scratch class scaffolding. Keep the `TimeManagement` interface (`init`, `optimum`, `maximum`, `elapsed`, `clear`) so `search.cpp` needs no edits, and replace the body with new state, new inputs, a new control law and new outputs. Minimal diff surface, maximal authorship — and `git diff base-sf19..HEAD -- src/timeman.*` is legible to a judge.

---

## Authorship Defense: the dossier a judge will accept

Rule 2's exclusions are explicit: reformatting, translated comments, renamed variables, **and mere adjustment of existing parameters** do not count. A judge therefore asks four questions: *Is it authored? Is it decisive? Is it running in games? Can they defend it?* A 50-page document loses; a two-page claim plus a 60-second live demo wins. The artifact must be built **during** development — the only ordering that matters is `00-DESIGN.md` before code, evidence as you go, defence last.

### The self-test that tells you whether you have a component

Revert your change to a single constant or a single scale factor. If behaviour is qualitatively unchanged, you have parameter tweaking. If reverting removes a decision the engine can no longer make — "instant-move in a dead-equal position to bank tiebreak time", "spend big because the match bank is +3 min", "cap at `remaining − exec_tail` so a flag is impossible" — you have a component. Write the answer down before writing the code.

### Dossier contents

```
AUTHORSHIP.md                          # 2 pages, repo root — the claim
PROVENANCE.md                          # base project, SHA, net/book/TB inventory, licences
DECLARATIONS/accreditation-copy.md     # exact copy of what was submitted (base + commit + GPU)
docs/timeman/
  00-DESIGN.md                         # dated BEFORE the implementation commit
  01-ALGORITHM.md                      # pseudocode, invariants, failure modes, complexity
  02-EVIDENCE.md                       # ablation, SPRT, 3-game matches, forfeits, bank
  03-DEFENSE.md                        # 3-minute script + 15 anticipated questions
  04-DECISIONS.md                      # dated decision log: why X, why not Y
experiments/timeman-ablation/
  run.sh                               # one command reproduces the table
  configs/                             # upstream vs custom, latency models, TCs
  results/                             # raw output, not just the summary
scripts/{check_license.sh, log_lint.py, doctor.py}
docs/PROTOCOL.md, docs/LOGBOOK.md      # the frozen contract, cited in the claim
```

**`AUTHORSHIP.md` must contain, in this order:**

1. **One-sentence claim.** "We replaced Stockfish's `TimeManagement::init` with a match-aware, latency-constrained budget allocator that decides how much time to spend on each move and when to instant-move; it runs in every game and is switchable for ablation." Get the names right: in `sf_19` the type is `TimeManagement` at `src/timeman.h:38` and the function is `src/timeman.cpp:46`. There is **no** `Timeman`/`TimeManager` type — a write-up that says "we replaced `Timeman`" tells a judge you did not read the source.
2. **Rule 2 mapping table** — four rows: authored by the team (`00-DESIGN.md` committed before code; per-author history; `04-DECISIONS.md`); a decisive component (sets `optimumTime`/`maximumTime`/instant-move; `TimeManager=custom` is the game default); functional during matches (per-search attestation; console records it in every log line; startup self-test fails if inactive); defensible (03-DEFENSE + live switch demo + 02-EVIDENCE ablation; all three members rehearsed).
3. **What is new** — *new inputs* (measured latency p50/p95, opponent clock, match bank, game index, Armageddon colour/draw rule); *new state* (bank, latency model, reserve, spend history); *new control law* (reserve-constrained budget over expected remaining moves instead of a closed-form polynomial in `ply`); *new outputs* (budget + instant-move flag + reason code).
4. **What is inherited**, as a table of file:line for every upstream function or constant still used. Naming what you did *not* write is what makes the claim credible — e.g. "iteration rescaling at `search.cpp:570-610` is upstream and unchanged; the `Ponder` +25 % clause was deleted; `originalTimeAdjust` was replaced by the bank-derived multiplier. Note that `sf_19` has **no** `timeAdvantage` clause (master added it later); our allocator goes beyond both."
5. **Explicit non-claims.** "Not claimed: evaluation, search, book, tablebase. The book is self-generated tooling; tablebases are standard 3-4-5 Syzygy files; the NNUE net is the official Stockfish 19 network, unmodified, CC0-1.0." Claiming four things in one breath destroys the one credible claim — Rule 3 and Rule 4 say book and TB do not count.
6. **60-second verification recipe** — exact, runnable, offline: `git log base-sf19..HEAD --stat -- src/timeman.*`; `setoption name TimeManager value upstream|custom` on a scripted position/clock; the resulting `info string tm=… budget_ms=… reason=…`; `tail -1` of a real game log. A judge should be able to falsify the claim without reading the repo.
7. **Evidence index** — one line per artifact with the claim it supports.

**Runtime proof, which is what actually closes the argument:** the engine emits, at the start of every search, `info string tm=custom-vX.Y mode=increment|sudden_death|armageddon latency_p95_ms=… bank_ms=… budget_ms=… reason=…`, and the console copies it into that move's log line. The log handed to the banca therefore proves the component ran on every move of every game — nothing else in the dossier does that. `TimeManager=upstream` exists only for ablation and drills and is never the game default; a startup self-test fails loudly if the custom path is not active.

**`02-EVIDENCE.md` must contain** (these are the experiments that persuade): an ablation A/B on the **same binary** at 15+10 with a simulated human latency (p50 8 s / p95 14 s) reporting Elo, W/L/D, **time forfeits**, average remaining clock and tiebreak wins; a 3-game match simulation using the real Rule 12 format including 1–1–1 and 0–0–0 paths; stress scenarios (10 s left, 30 s left, 5+0 and 4+0 sudden death, Armageddon as both colours, opponent with 5 min vs 20 s); a **revert test** on a scripted position/clock where upstream and custom choose different budgets and different *kinds* of decision, with a one-sentence explanation of why; and at least one full real game log showing the attestation on every move.

### What does not persuade

A design doc written after the code. A 500-line diff that is mostly comments translated into Portuguese. "We tested it and it felt better." A claim that the book or tablebase is authored. A demo that needs network, a dongle, or a laptop that is not charged. One member answering every question. A dossier that lists more than one claimed component. The words "tuned" or "adjusted" where "computes", "allocates", "constrains" belong.

**Language rule:** write the design, evidence and defence documents in Portuguese (that is the audience), keep code comments minimal and in English matching upstream style — and count neither as the contribution. Translated comments are explicitly excluded, so they are evidence *against* you if they are the bulk of the diff.

---

## Implications for Roadmap

### Reconciled phase sequence

Seven phases, **ordered by gate rather than by person-week**. Three tracks run in parallel inside each phase; a phase ends at a gate that all three tracks pass. This is ARCHITECTURE's structure with FEATURES' weighting and PITFALLS' coverage. (ARCHITECTURE labels the gates G0–G4; they are written here as **Gate 0–4** to avoid colliding with PITFALLS' pitfall IDs `G1`–`G5`, which are a different namespace.)

| Phase | Gate | 2-week day | 1-week day |
|---|---|---|---|
| **1. Foundation, Provenance & Frozen Contract** | Gate 0 | 0 | 0 |
| **2. Console Protocol Spine** | Gate 1 | 2 | 3 |
| **3. Clock Authority, Resilience & Rule-Ceiling Guards** | Gate 2 | 4 | 4 |
| **4. Authored Time Manager** (parallel from day 1) | Gate 3 + **WIN GATE** | 6–7 | 5–6 |
| **5. Match Policy, Ponder & Calibration** *(conditional)* | — | 7–9 | dropped |
| **6. Adversarial Verification & Dress Rehearsal** | Gate 4 | 8 and 10 | 6–7 |
| **7. Game-Day Operations & Authorship Defense** | ship | 10 | 7 |

| Phase | Track A — TM / policy | Track B — console | Track C — infra / harness / evidence |
|---|---|---|---|
| 1 | stock binary hour 1; `mock_gui.py`; TM skeleton + interface | `mock_engine.py`; console skeleton | repo import, NOTICE/PROVENANCE/GPL, offline build, TB dir, `doctor` stub |
| 2 | TM v0 against the mock (trace line, budget shape) | parse, board, FSM, UX, journal, log | log schema lint, book loader + cap, TB assert |
| 3 | TM v1 first draft; options registered | clock + backdating, watchdog, supervision, resume, match model, end clocks, checklist | fault-injection harness, `kill -9` + thermal runs, inventory |
| 4 | TM v1 + ablation, modes, attestation, design docs, SPRT gate | integration; TM trace into the log | SPRT wrapper, 3-game sim harness |
| 5 | latency calibration, policy function, Armageddon, ponder credit | ponder FSM; policy events in the log | Bo3 + tiebreak + Armageddon sims, bank accounting |
| 6 | tuning freeze | fix only what rehearsal finds | rehearsal, `doctor`, thermal, clean-clone, `log_lint` |
| 7 | demo switch + ablation table | runbook drills | pre-flight, USB archive, arguição rehearsal |

> **ID conventions in the phase sections.** `Addresses:` uses FEATURES.md IDs (`TS-n` = table stake, `DF-n` = differentiator). `Avoids:` uses PITFALLS.md group IDs (`A1`–`A3` authorship, `B1`–`B4` licence/provenance, `C1`–`C5` clock, `D1`–`D5` protocol, `E1`–`E3` book/tablebase, `F1`–`F2` log, `G1`–`G5` game day, `H1`–`H5` strategy) and this document's `CF-n` findings.

---

### Phase 1: Foundation, Provenance & Frozen Contract

**Rationale:** Two things must happen on day 0 because both are unrecoverable later. Compliance failures are **retroactive** — a game you won with a 6-piece tablebase or a book move past the cap becomes a loss or a DQ after the fact — and the frozen contract is the only real shared dependency in the project. STACK's "provenance first" and ARCHITECTURE's "contract first" are the same phase with different owners. Shipping the *unmodified* binary in hour 1 unblocks both other tracks immediately.

**Delivers:** repo imported from a real `git clone --branch sf_19` with upstream history retained and tagged `base-sf19`; `Copying.txt`/`AUTHORS` byte-intact; GPL headers preserved plus a dated modification line on every file touched; `NOTICE` (base URL, full SHA, tag, fork date, modified files, build command, `ARCH`, compiler version, bench node count, net provenance); `PROVENANCE.md` (net filename/size/SHA-256/CC0/"unmodified, not authored by the team", TB inventory, dependency manifest); vendored `.nnue` and a verified clean `unshare -n make -j` on the **match laptop**; `docs/PROTOCOL.md` and `docs/LOGBOOK.md` frozen; both mocks; skeleton compliance assertions (TB limit + `MaxCardinality`, book loader cap, offline asset-path check, `doctor` stub); publication dry run (public mirror or panel access verified, USB archive started).

**Addresses:** TS-1, TS-2, TS-3 (assertions), TS-21 (skeleton), DF-11 (baseline).
**Avoids:** A3, B1, B2, B3, B4, G2.
**Gate 0:** contract frozen; both mocks pass; stock binary builds and benches offline on the match laptop.

### Phase 2: Console Protocol Spine

**Rationale:** The console is the critical path and this is its spine — everything else attaches to it. Person B owns it; person C supports the log projection; **person A must not wait for it.**

**Delivers:** strict UCI parser (normalise case/whitespace; reject SAN, `0000`, and malformed 5-char tokens with a typed error; log every rejected token as evidence); board replica via `python-chess` advanced only by validated moves; legality gate in both directions (their illegal announcement → refuse, keep the loop live, clock keeps running; our illegal `bestmove` → never displayed); **ANNOUNCE field populated only by `bestmove`**; explicit phase FSM with side-to-move guards; keyboard-only operator loop with `<TAB>` completion from the legal-move set, SAN echo, and explicit confirm; append-only journal with `fsync` + replay; `MoveLog` as a projection carrying all eight Rule 9 fields for **every half-move** — including opponent moves (`src=ponder|none`), book moves (`d=0 n=0 score=book`), and terminal moves.

**Addresses:** TS-5, TS-6, TS-7, TS-8, TS-9, TS-10, TS-14 (foundation), TS-17.
**Avoids:** D1, D2, D3, D5, F1.
**Gate 1 (end day 2):** a **complete** game against *stock* Stockfish; every move logged with all eight fields; SYNC works; `test_ponder_discard.py` green (written before the handler, against the mock); `log_lint` green.

### Phase 3: Clock Authority, Resilience & Rule-Ceiling Guards

**Rationale:** The clock is the win condition and the console watchdog is the last line of defence; neither can exist before the spine. The Rule 3/Rule 4 guards are **folded in here rather than given their own phase** (PITFALLS' P5) because they are ~1 person-day and a phase that small is a phase that slips silently — as a gate item they cannot.

**Delivers:** `ClockModel` with belief computed from `monotonic_ns()` deltas (never ticked), **`MOVE_ENTERED` backdating** by the input-latency EMA, increment added on press, drift EMA/σ; SYNC key that works mid-search, shows `predicted/observed/delta`, demands a second keystroke beyond 5 s; opponent-clock capture at every hand-off; console watchdog (`stop`, never `quit`, at `belief − 250 ms`) with scramble mode below the emergency floor; engine supervision + restart + `position` replay + **always-available legal fallback**; journal `resume` after `kill -9`; console-side threefold/50-move detection with arbiter alert; result + **both end-of-game clocks**; `MatchController` with the R11 colour sequence, per-game time records, running tiebreak totals, Armageddon flag; pre-game checklist / `doctor`; book loader with `BOOK_MAX_PLY = 10` + boundary test + dual `book.bin`/`book.epd` emit; TB directory assert and SHA-256 inventory.

**Addresses:** TS-3, TS-12, TS-13, TS-14, TS-15, TS-16, TS-18, TS-19, TS-20, TS-21; DF-10 (start).
**Avoids:** C5, D4, E1, E2, E3, F2, G4.
**Gate 2 (end day 4):** console vs the **fork** with ponder on; a mid-game restart replays correctly; TM trace parsed and logged; `kill -9` recovery <10 s; the TB assert fires on a planted 6-piece filename; the boundary test proves no book decision at counter ≥ 10.

### Phase 4: Authored Time Manager

**Rationale:** This is the Rule 2 deliverable and the tiebreak lever, and it must be **default-on in the shipped binary before the win gate proves it**. The code starts on day 1 against `mock_gui.py`, so this phase is convergence and calibration, not the beginning.

**Delivers:** a from-scratch allocator behind the retained interface, with — (a) a **measured protocol-overhead term** clamped to `[1200, 6000]` ms, default 3500, carried in via a `TM Latency` option applied at `IDLE`; (b) **increment-aware banking**, solvency `spend < inc − overhead`, target 2–4 s early, `banked_seconds` as a first-class value; (c) a **shadow price of time** and draw value as one pure, unit-testable function of match state; (d) **ponder credit** (overhead → ~1 s on a hit) with the upstream +25 % clause **deleted**; (e) a **hard maximum invariant** `maximum ≤ time[us] − exec_tail − safety` that makes flagging structurally impossible; (f) instant-move mode and `sudden_death` / `armageddon` modes; (g) `info string TM …` trace + `tm=custom` attestation + the `TimeManager=upstream|custom` switch defaulting to custom with a startup self-test; (h) `00-DESIGN.md` committed **before** the implementation.

**Addresses:** DF-1, DF-2 (first pass), DF-3/DF-4 (hook only), DF-8 (mode flags).
**Avoids:** A1, A2, C1, C2, C3, C4, CF-5.
**Gate 3 (end day 6):** SPRT at 15+10 with a simulated 1.5 s input delay — custom **≥** stock (no Elo regression) **and** higher cumulative remaining clock; constants frozen.
**WIN GATE (day 6/7, non-negotiable):** on the match laptop, offline, real console + real fork + custom TM default + 3-4-5 TB dir + the frozen book (or none), two humans play a complete 15+10 game with jittered spoken-protocol latency — **Bo3 with tiebreak accounting if the day allows** — every half-move logged with all eight fields and the attestation, **zero timeouts**, zero double-moves, stale-bestmove and `kill -9` injections green, and the match model reporting the correct R11 colour sequence. If this fails, the only permitted work until it passes is fixing it.

### Phase 5: Match Policy, Ponder & Calibration *(conditional)*

**Rationale:** Conditional **by design**, and the conditioning is precise: the *hook* ships in Phase 4, only the *tuning* is gated. FEATURES is explicit that these must be designed into the table-stakes code from day 1, not bolted on in week 2 — which is why the `shadow_price` interface and the options exist before this phase opens. It consumes the only slack in the plan, so it starts only if the WIN GATE is green.

**Delivers:** latency calibration from real logs (typing window measured exactly; announcement and return tail inferred from SYNC residuals; `overhead_ms` re-estimated continuously); the ponder FSM (`go ponder` on the speculated position, `ponderhit` on match, `stop` + search-id discard on miss, sync-during-ponder rebase, depth/node cap, hit-rate metric) and `Ponder=true` enabled **only now**; policy tuning (draw value, resign threshold, spend multiplier, offer-draw) with every decision logged with its match-state inputs; Armageddon profiles (Black: draw = win → spend 0.8, simplify, trade into drawn endings; White: draw = loss → spend 1.0, imbalance, avoid mass simplification; 5+0/4+0 reserve floors, never >15 % of remaining before move 20); book content (DF-7) and book→engine handoff timing (DF-9).

**Addresses:** DF-2, DF-3/DF-4, DF-5, DF-6, DF-7, DF-8, DF-9, DF-12.
**Avoids:** C2, C3, C4, H2, H3.
**Note:** this is the **one phase that needs a spike, not literature** — the shadow-price policy has no external reference; it must be tuned against 3-game tiebreak simulations.

### Phase 6: Adversarial Verification & Dress Rehearsal

**Rationale:** The console's failure modes are *timing* failure modes and unit tests cannot find them. Rehearsal #1 must be early enough to fix what it finds; rehearsal #2 must run on the frozen configuration.

**Delivers:** the fault-injection suite (duplicate move, illegal move, SAN-instead-of-UCI token, `kill -9`, clock-sync keypress, laptop-sleep gap, network re-enable attempt, `(none)`) driving the console's stdin with jittered 0.5–6 s delays and asserting no double-move, no advance on illegal input, no missed log field, correct side-to-move, correct cumulative-time accounting, **zero timeouts** at a simulated 15+10; a full Bo3 + Armageddon on the physical board with the real operator, spoken UCI, offline; `log_lint` / `doctor` / `check_license.sh`; a clean-clone `unshare -n make`; a 60-minute sustained-load thermal run; SPRT as a **gate only** (200–400 games); the event-laptop resource profile (physical cores, not SMT siblings; `Hash ≤ min(4096 MB, 50 % RAM)`).

**Addresses:** DF-10, DF-11, TS-21 (final).
**Avoids:** G1, G2, G3, G4, G5, H4, C5.
**Gate 4:** rehearsal #1 passed (day 8) → fix only what it found (day 9) → rehearsal #2 + **freeze** (day 10).

### Phase 7: Game-Day Operations & Authorship Defense

**Rationale:** These failures are cheap to prevent and impossible to recover from — and the arguição is where a winning engine becomes a trophy or a DQ.

**Delivers:** a signed per-game pre-flight (`rfkill block all`, airplane mode, auto-connect and updaters disabled, no background analysis or SPRT, `Hash`/`Threads` verified, performance power profile, plugged in, hard surface, `network=off` logged) re-run **before every game**; role assignment (Operator / Timekeeper-Adjudicator / Coach-Analyst) with a one-page runbook covering pre-game, per-move, per-game and emergency, roles rotated in drills, only the operator speaks to the opponent; the log delivery ritual (one file per game, header with the full option set and asset hashes, trailer with final clocks + computed bank + log hash, auto-export to USB **and** paper, never edited); the 3-minute offline demo (`upstream|custom` on a scripted position/clock, different budget *and* different kind of decision, a real log line with the attestation, the ablation table); a one-page handout; a hostile rehearsal with the 15 questions; all three members able to explain the algorithm, the evidence and the diff.

**Avoids:** B3, G1, G2, G5, H5.
**Freeze means freeze** — no feature work in the last 20 % of the timeline. The most common way a team with a winning engine loses is a change made on day 9.

### Phase Ordering Rationale

- **Compliance and contract share day 0** because one is retroactive and the other is the only shared dependency. Doing either later is the single most expensive scheduling mistake available.
- **Console → clock → match model is a hard chain** (each is a prerequisite of the next). The TM is deliberately *not* in that chain: it runs against a mock from day 1, which is what makes three people genuinely parallel instead of nominally parallel.
- **Book and TB guards are folded into Phases 1 and 3** rather than a standalone phase, because a one-person-day phase is a phase that slips silently. They are gate items, not backlog.
- **The policy layer comes last and conditionally** because it needs the clock, the match model and the TM to exist first — and it is the only work in the plan that can be deleted without losing legality, survival or the authorship claim.
- **Rehearsal precedes freeze precedes game day**, because timing bugs are found by injection, not inspection, and because the plan's most likely failure is a last-minute change.

### Timeline reality check

**Table stakes are 21–24 raw person-days. Two weeks × 3 people is 30 at 100 % and ~21 at realistic efficiency. One week × 3 is 15 at 100 % and ~10–11 realistic.** There is no version of this plan with slack. The only honest response is to decide the cuts in advance.

| | 1 week (days 0–7) | 2 weeks (days 0–10) |
|---|---|---|
| Phase 1 | same | same |
| Phase 2 | days 1–3; drop resync polish to "re-enter last N moves" | days 1–2 |
| Phase 3 | day 4; clock + watchdog + journal + match model + guards-as-assertions only | days 3–4 |
| Phase 4 | days 1–5 in parallel; TM v1 with overhead + banking + hard cap; no tuning | days 1–6 in parallel |
| WIN GATE | day 5–6; one full game + injections (Bo3 only if the day allows) | day 6–7; full Bo3 with tiebreak accounting |
| Phase 5 | **dropped** — only the defaults wired in Phase 4 survive (TiebreakBias hook, Armageddon mode flag, `Ponder` stays off unless the discard test is green) | days 7–9; full policy + ponder + calibration + book |
| Phase 6 | days 6–7; one rehearsal + the injection suite | days 8 and 10; two rehearsals |
| Phase 7 | day 7 | day 10 |

**What gets cut, in this order** (cut from the top until the calendar fits; never reorder):

| # | Cut | Why it is safe to cut |
|---|---|---|
| 1 | Match policy *tuning* (DF-3/4/8 beyond defaults) | The hook ships in Phase 4; a constant `shadow_price = 1.0` is a legal, correct default that just forfeits some tiebreak edge |
| 2 | Book *content* (DF-7/DF-9) | Rule 3 permits **no book at all**; a book is worth ≤1 ply of preparation and zero Elo at ~3650. Keep the loader, the cap and the `src=book` logging |
| 3 | SPRT campaign, tuning, loss mining (DF-12) | Keep a 200–400 game regression gate against the upstream TM. The value of the TM comes from measurement against the *console*, not from a large SPRT batch |
| 4 | Ponder (DF-5) | It saves ~2.5 min/game, but it is also the largest source of game-losing bugs (CF-7). Only enable it if `test_ponder_discard` is green and the WIN GATE passed |
| 5 | DF-11 profiling beyond one sustained run, DF-6 resign advisor, log-diagnosis one-pager | Conveniences, not survival |
| 6 | Armageddon specialisation | Keep a `sudden_death` mode flag with zero-increment reserve floors; drop the colour-specific draw-value policy |
| 7 | Resync sophistication | Fall back to "re-enter the last N verified moves"; never to free-form FEN editing as the primary path |

**Do not cut, under any calendar:** provenance + offline build; `SyzygyProbeLimit=5` + assert + inventory; strict parse + legal gate; explicit FSM; dual clock + backdating + watchdog; journal + resume; the eight-field log for every half-move; the R11 match model + end-of-game clocks; pre-flight checklist; **one** full rehearsal.

**Minimum viable competition entry** — the floor beneath which entering is not worth the trip. This is the 1-week target; everything above it is upside:

1. Pinned `sf_19` clone with upstream history, `base-sf19` tag, NOTICE/PROVENANCE, GPL headers + modification notices, clean `unshare -n make` on the match laptop, net vendored.
2. TB directory containing only 3-4-5; `SyzygyProbeLimit=5`; `Syzygy50MoveRule=true`; startup assert `MaxCardinality ≤ 5`; SHA-256 inventory.
3. Book absent (legal) **or** own ≤10-half-move book with loader cap, boundary test and `src=book` logging.
4. Console: strict UCI parse + legal gate + explicit state machine + ANNOUNCE from `bestmove` only + resync + panic/instant key.
5. Clock: dual clock with `MOVE_ENTERED` backdating, SYNC key, console watchdog at `belief − floor`, execution reserve.
6. Engine supervision: restart + replay + always-available legal fallback.
7. Append-only journal with `fsync` and `resume`.
8. `.log` per game, all eight fields for every half-move including the opponent's, book/terminal variants, `engine_ms` **and** `wall_ms`, flushed, exported at game end.
9. Match model: game index, R11 colours (3 = 1), both end-of-game clocks, running tiebreak total.
10. Custom TM default-on with per-search attestation, measured overhead term, increment-aware banking, hard maximum invariant, instant-move mode.
11. Pre-flight checklist: network off, dependencies frozen, `Hash`/`Threads` sane, no background processes.
12. One full simulated game plus stale-bestmove and `kill -9` injections green.

**If the deadline is truly five working days,** there is no path to a from-scratch console plus a calibrated TM. The only defensible entry is stock `sf_19` plus a thin console built on `engine.play()` — our own clock model, watchdog, legal gate and log layered around it — accepting that ponder, calibration and the transport-level authorship are lost. Take that path deliberately, and document it, rather than discovering it on day 4.

### Research Flags

**No phase needs literature research.** All four files are source-verified (Stockfish `sf_19` read directly, UCI spec, `python-chess` source, Polyglot format, rulebook verbatim) and the design is specified to the level of line numbers and formulas. What is missing is **measurement** and **organizer answers**, not research.

Phases with standard patterns — skip `--research-phase`:

- **Phase 1** — git, GPL compliance, `make`, vendored assets. Execution, not research.
- **Phase 2** — the parser/FSM/log are specified in `PROTOCOL.md` + `LOGBOOK.md`. One 30-minute spike: dump the real `info`/`bestmove`/`info string` line shapes from the built binary before writing the parser.
- **Phase 3** — the clock model, backdating formula, reserve decomposition and watchdog are fully specified (ARCHITECTURE §2); only the *constants* need rehearsal data, which is execution.
- **Phase 4** — the algorithm is specified; it needs calibration runs, not research.
- **Phase 6 / 7** — fault injection and ops runbooks are well-trodden.

Phase that needs a spike before planning:

- **Phase 5** — the match-level shadow price (how aggressively to convert a time lead into risk) has no external literature and no field data. Run a timeboxed simulation (3-game matches, tiebreak accounting, latency distribution) to pick 2–3 policy presets; do not design it on a whiteboard.

Open **organizer questions** to resolve before Phase 5 (they change the design, not just the numbers): does Armageddon have an increment; do the clocks stop at game end and does a resignation contribute the resigning side's remaining time to the tiebreak; is "tempo gasto" in Rule 9 search time or wall time; and how does the arbiter read "10 meios-lances" at the boundary.

---

## Confidence Assessment

| Area | Confidence | Notes |
|---|---|---|
| **Stack** | **HIGH** | Versions, option defaults, file/line map, build times, nps scaling and the 15+10 move-1/move-2 timings were verified by reading `sf_19` and running it. Two gaps: Clang untested; `python-chess` 1.11.2 not executed on Python 3.14 (pin 3.12). |
| **Features** | **HIGH (rules) / MEDIUM (competitive)** | Every requirement traces to a verbatim rule, and all 15 rules are mapped with no orphan. The 21–24 person-day estimate, the EV ordering and the field assumptions are inference — web search is disabled in `.planning/config.json`, so no live field data exists. |
| **Architecture** | **HIGH (mechanism) / MEDIUM-HIGH (build order)** | Process boundary, clock backdating, ponder discard and journal projection all derive from verified UCI and Stockfish semantics. Day-level estimates assume three full-time people. |
| **Pitfalls** | **HIGH (rule + source) / MEDIUM (simulation) / LOW (field)** | Flag-point simulation is a *model*, not a measured game — the direction (default TM is insolvent under a seconds-scale human loop) is robust; the exact ply is not. Judge behaviour and field composition are inference. |
| **Overall** | **HIGH on what/how; MEDIUM on when/who** | The design is not the risk. The schedule and the opponent field are. |

### Gaps to Address

- **Armageddon increment.** Rule 12 states only 5/4 minutes. Assume **no increment**, set `winc 0`/`binc 0`, and confirm with the organizers — it materially changes every reserve in Phase 5.
- **Tiebreak accounting at game end.** Whether clocks stop and whether a resignation or mate contributes the loser's remaining time. Capture both readings regardless (TS-19); ask.
- **"Tempo gasto" semantics.** Log `engine_ms` *and* `wall_ms`; the ambiguity disappears and both are defensible.
- **R11 pairing order / which colour we are in game 1.** External input, unknown at build time. The match model must accept it; prep both colours; never infer.
- **Real human latency distribution.** No field data at all. Default `overhead_ms = 3500`; replace with a measurement at the dress rehearsal, with the actual operator, on the actual laptop, with the physical clock.
- **Strength cost of aggressive banking.** Unknown without SPRT under a latency model. Treat it as a *measured* trade-off; the 1.5–2 s floor is the safety valve, and the tiebreak gain may legitimately dominate a small Elo loss.
- **Book ply boundary interpretation.** Implement `halfmoves_played < BOOK_MAX_PLY (10)`, keep the constant one-line changeable to 9, and ask the arbiter before game 1.
- **Field composition.** No data. Assume SF19 forks at or near defaults — which is exactly the baseline the clock edge beats.
- **Match-laptop thermal behaviour.** Unmeasured. A 60-minute sustained run is the only way to know whether the TM's nps assumptions hold in game 3.
- **Toolchain edge cases.** Clang unverified (use GCC); Python 3.14 untested with `python-chess` (pin 3.12 and vendor the pure-Python package).

---

## Sources

### Research inputs (the four files this document synthesizes)

- `.planning/research/STACK.md` — prescriptive stack: `sf_19` pin, build/offline mechanics, TM internals by file:line, fastchess SPRT recipe, Polyglot/Syzygy tooling, logging extraction, spoken-input layer. **Empirically verified** (build, bench, 15+10 run).
- `.planning/research/FEATURES.md` — 21 table stakes + 12 differentiators + 15 anti-features, traced rule-by-rule (R1–R15, no orphan), with person-day estimates and the team-allocation reality check.
- `.planning/research/ARCHITECTURE.md` — process boundary, clock authority model, the full UCI dialogue and ponder cycle, event-sourced journal, anti-patterns, the frozen-contract build order and gates.
- `.planning/research/PITFALLS.md` — six ways to lose, pitfall groups A–H, the authorship dossier, the "looks done but isn't" checklist, recovery strategies, and the top-five-if-you-only-fix-five.

### Primary (HIGH confidence)

- `docs/competition-rules.md` — verbatim organizer FAQ, Rules 1–15. **Authoritative for every compliance requirement and exclusion in this document.**
- `.planning/PROJECT.md` — framing, out-of-scope decisions, three-front split, core value (clock + tiebreak).
- **Stockfish `sf_19`** (`f879373d916914de3a478aabb4226e6460c17d15`, 2026-09-05): `src/timeman.{h,cpp}`, `search.{h,cpp}`, `uci.cpp`, `engine.cpp`, `thread.cpp`, `tt.cpp`, `position.cpp`, `syzygy/tbprobe.cpp`, `evaluate.h`, `nnue/network.cpp`, `universal/nnue_embed.cpp`, `Makefile`, `scripts/net.sh`, `Copying.txt`, `AUTHORS` — plus an actual build, `bench`, and a 15+10 run on this machine.
- **Stockfish `master`** (`ff3a6c50`, 2026-10-25) — used only to confirm post-`sf_19` drift (`timeAdvantage` addition, different default net).
- UCI specification, April 2006 (Huber / Meyer-Kahlen) — `go ponder` semantics ("the last move in the position string is the ponder move"), the `bestmove` obligation, `setoption` timing.
- `python-chess` 1.11.2 source (`chess/engine.py`, `chess/polyglot.py`, `chess/syzygy.py`) and docs — `parse_uci`/`InvalidMoveError`, `INFO_ALL`, `time` in seconds, `lowerbound`/`upperbound`, `play()` defaulting to `INFO_NONE`, the naive ponder clock adjustment, reader-only Polyglot.
- `Disservin/fastchess` v1.8.2-alpha (`ebfd64c`) — MIT, EPD/PGN-only openings, SPRT flags, `-report penta`, `-recover`, no Polyglot.
- `hgm.nubati.net/book_format.html` — Polyglot 16-byte big-endian records, 781 Zobrist constants, castling `e1h1`, en-passant key semantics, `weight = 2W+D`.
- `official-stockfish/networks` — net licence **CC0-1.0**; `nn-1a298aa575a0.nnue` = 98,511,183 B.
- `official-stockfish/books` — CC0-1.0; `noob_5moves.epd` is exactly 10 plies; UHO is 16.
- `chessprogramming.org/Syzygy_Bases`, `github.com/syzygy1/tb` — 3-4-5 = 939 MiB (290 files), 6-piece = 149.2 GiB.
- GNU GPLv3 (`Copying.txt`) §§4–6 — notices, modification marking, corresponding source.

### Secondary (MEDIUM confidence)

- CCRL 40/15 4CPU **3650** (3653 for Sept 2026) and CCRL's conditions (books ≤12 moves, 3-4-5 EGTB) — an upper bound under our tighter constraints.
- `cutechess` v1.5.1 docs and issue #630 — Qt ≥ 6.8 requirement, high-concurrency lag.
- fastchess discussion #137 + chessprogramming wiki — rationale vs cutechess.
- Laptop thermal behaviour (nps −20–40 % under sustained load) — general hardware behaviour, not measured here.
- Judge behaviour in the arguição — inferred from Rule 2's wording, not observed.

### Tertiary (LOW confidence)

- Field composition and opponent strength for the III Chess Challenge — no data; web search providers are disabled in `.planning/config.json`.
- Exact flag ply under a 12 s human loop — a 30-line model of the `sf_19` allocator, not a measured game. Directionally robust, numerically indicative.

---

*Research synthesized: 2026-10-26*
*Ready for roadmap: yes*
*Recommended first action: freeze `PROTOCOL.md` + `LOGBOOK.md` and commit `docs/timeman/00-DESIGN.md` on day 0 — before any implementation commit.*
