# Roadmap: ChessChallendIII

## Overview

Ten calendar days (26 Oct → 5 Nov 2026), three people, one hard deadline, zero slack. The project is not an engine-strength problem — Stockfish 19 at defaults out-calculates the field — it is a **reliability-and-clock system wrapped around a strong engine**: a console that is the sole authority over board replica, clock, match state and the Rule 9 log; a narrow frozen UCI contract; a C++ fork that decides only *how* to spend a budget it is told; and an authored time manager inside the engine that is simultaneously the Rule 2 deliverable and the Rule 12 tiebreak lever.

The sequence below is **ordered by gate, not by person-week**. Three tracks run in parallel inside each phase; a phase ends at a gate all three tracks pass. Day 0 freezes the contract and the compliance artefacts, because compliance is retroactive and the contract is the only real shared dependency. The console track then gates the schedule; the time-manager track gates the trophy; the infra track produces the evidence. Everything converges on one non-negotiable **WIN GATE on day 6/7**. Nothing after the gate starts if it fails.

Table stakes are 21–24 person-days against ~21 effective person-days in ten days. **This plan does not contain slack, and it is not padded to imply any.** The cut order, the minimum viable entry floor and the non-negotiable list are written *before* work starts, because deciding them under pressure is how teams lose.

---

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): planned milestone work
- Decimal phases (2.1, 2.2): urgent insertions (marked with INSERTED)

- [x] **Phase 1: Foundation, Provenance & Frozen Contract** - Day-0 compliance, pinned fork, offline build, frozen protocol/log schema, ship the stock binary and both mocks
- [ ] **Phase 2: Console Protocol Spine** - Strict UCI parse, board replica, state machine, ANNOUNCE from `bestmove` only, journal and Rule 9 log
- [ ] **Phase 3: Clock Authority, Resilience & Rule-Ceiling Guards** - Backdated dual clock, SYNC, watchdog, crash/engine-death recovery, match model, TB/book asserts, pre-game checklist
- [ ] **Phase 4: Authored Time Manager (+ WIN GATE)** - Rewritten allocator as game default with per-search attestation, ablation evidence, and the non-negotiable day 6/7 WIN GATE
- [ ] **Phase 5: Match Policy, Ponder & Calibration (CONDITIONAL)** - Tiebreak edge only if the WIN GATE is green: calibrated latency, ponder as a saving, match-aware policy, book content
- [ ] **Phase 6: Adversarial Verification & Dress Rehearsal** - Fault injection, physical-board Bo3 with the real operator, thermal + offline proof, regression gate, freeze
- [ ] **Phase 7: Game-Day Operations & Authorship Defense** - Signed per-game pre-flight, log delivery ritual, 3-minute demo, hostile arguição rehearsal

## Phase Details

### Phase 1: Foundation, Provenance & Frozen Contract
**Goal**: Every unrecoverable compliance and contract decision is fixed and provable on day 0, and all three tracks are unblocked by a stock binary and two mocks.
**Mode:** mvp
**Depends on**: Nothing (first phase)
**Window**: Day 0 — 26 Oct. **Gate 0.**
**Requirements**: FOUND-01, FOUND-02, FOUND-03, FOUND-04, FOUND-05, FOUND-06, LIMIT-01, LIMIT-04, PIPE-01
**Success Criteria** (what must be TRUE):
  1. On the match laptop with networking severed (`unshare -n make -j`), the engine builds from a clean clone, `bench` reproduces the recorded node count, and the binary carries its net embedded — no asset is fetched or resolved from a remote or relative path.
  2. An auditor can open `NOTICE` and `PROVENANCE.md` and trace the base project to a full SHA and tag, see the NNUE net marked explicitly as *not authored by the team* with its SHA-256, and see `Copying.txt`/`AUTHORS` byte-intact with a dated modification line on every touched file.
  3. `docs/PROTOCOL.md` and `docs/LOGBOOK.md` appear in the first commits, before any implementation commit, and both `mock_engine.py` and `mock_gui.py` run end-to-end against them.
  4. The engine refuses to start when `SyzygyProbeLimit` is not 5 or when any asset path is remote/relative, printing the effective value it will use in a game.
  5. The panel can reach the repository (public URL or verified panel access) and a USB archive already holds source, net, binary and tablebase inventory.
**Plans**: 3 plans

Plans:
**Wave 1**
- [ ] 01-01-PLAN.md — Provenance and offline build proof: `NOTICE` + `PROVENANCE.md` derived from commands, GPL dated lines, vendored `python-chess`, namespace build evidence, `RELEASE/` + USB archive script
- [ ] 01-02-PLAN.md — Frozen contract: `docs/PROTOCOL.md` + `docs/LOGBOOK.md` in a docs-only commit, `mock_engine.py` + `mock_gui.py` speaking them to each other, ordering proof

**Wave 2** *(blocked on Wave 1 completion)*
- [ ] 01-03-PLAN.md — Rule ceilings and harness: `TB_PROBE_LIMIT=5` clamp + fatal exit, `doctor.py` pre-flight, fastchess + SPRT recipe, `scripts/gate0.sh`

**Why this phase**: Both halves of day 0 are unrecoverable later. Compliance failures are **retroactive** — a game won with a 6-piece tablebase becomes a loss or a DQ after the fact — and the frozen contract is the only shared dependency between the three tracks. Shipping the *unmodified* Stockfish binary in hour 1 is what makes the three people genuinely parallel instead of nominally parallel.

---

### Phase 2: Console Protocol Spine
**Goal**: A complete game can be played through the console against stock Stockfish, with every half-move logged in the Rule 9 schema and no illegal move — theirs or the engine's — ever reaching the board replica.
**Mode:** mvp
**Depends on**: Phase 1
**Window**: Days 1–2 — 27–28 Oct. **Gate 1.**
**Requirements**: PROTO-01, PROTO-02, PROTO-03, PROTO-04, PROTO-05, PROTO-06, PROTO-07, PROTO-08, LOG-01, LOG-02, LOG-03, LOG-04
**Success Criteria** (what must be TRUE):
  1. The operator types `Nf3`, `0000`, or a malformed token: the console refuses it with a typed error, keeps the prompt live, echoes the reason, logs the rejected token as evidence — and the clock keeps running.
  2. The operator enters a legal move: the board replica advances, the echoed FEN and move list match the physical board, and that half-move appears in the log with all eight fields.
  3. The ANNOUNCE field stays blank until `bestmove` arrives, then shows exactly the engine's move in uppercase hyphenated form (`E2-E4`, `E7-E8=Q`); a PV that deepens on screen never leaks into it.
  4. A ponder miss — `stop` followed by a late `bestmove` for the speculative position — produces no move on the board, no state change and a `STALE_BESTMOVE` journal record, with the test written before the handler.
  5. After a full game against stock Stockfish, `log_lint` reports zero missing fields, including opponent half-moves and terminal moves.
**Plans**: 1/3 plans executed

Plans:
- [x] 02-01: Thirty-minute wire-format spike on the built binary (`info`, `info string`, `bestmove (none)`, `CRITICAL ERROR` on illegal `position`), then the ~250-line UCI transport: framing, whitelisted line parsing, monotonic `search_id`, `discarding` flag, stderr drain, and an option queue applied at `IDLE` (never mid-ponder)
- [ ] 02-02: Strict UCI parser with typed rejects; board replica + legality gate in both directions; explicit `IDLE → OUR_SEARCH → ANNOUNCE_PENDING → AWAIT_OPP_CONFIRM → OPP_TURN/PONDERING` machine with side-to-move guard; keyboard-only operator loop with instant echo; ANNOUNCE locked to `bestmove`; resync-by-replaying-last-N-moves; `test_ponder_discard.py` first
- [ ] 02-03: Append-only `fsync` journal + `MoveLog` projection (eight fields for every half-move, `src=ponder|book`, `d=0 n=0`, `engine_ms` and `wall_ms`, bound flags verbatim) + `log_lint`; full game against stock Stockfish

**Why this phase**: The console is the critical path — nothing is end-to-end verifiable without it, and it sits on one person. This phase builds its spine, and everything later attaches to it. The time-manager owner must not wait for it: that track codes against `mock_gui.py` from day 1.

---

### Phase 3: Clock Authority, Resilience & Rule-Ceiling Guards
**Goal**: The console is the authority over the clock and the match, survives a console crash or an engine death mid-game, and structurally cannot breach the book or tablebase ceilings.
**Mode:** mvp
**Depends on**: Phase 2
**Window**: Days 3–4 — 29–30 Oct. **Gate 2.**
**Requirements**: CLOCK-01, CLOCK-02, CLOCK-03, CLOCK-04, CLOCK-05, CLOCK-06, CLOCK-07, CLOCK-08, CLOCK-09, LIMIT-02, LIMIT-03, LOG-05, CHECK-01, PIPE-03
**Success Criteria** (what must be TRUE):
  1. The operator enters the opponent's move 4 s after the opponent pressed: the belief moves *back* by the measured input latency rather than forward from the typing moment, and the displayed drift matches a manual calculation against the physical clock.
  2. Pressing SYNC mid-search snaps the estimate to the observed clock, shows `predicted/observed/delta`, demands a second confirmation beyond 5 s, and lets the search continue; a console watchdog fires `stop` (never `quit`) before the flag and switches to scramble mode below the emergency floor.
  3. `kill -9` on the console mid-game: `resume` reconstructs board, both clocks, match standing and log with no lost or duplicated half-move in under 10 s; killing the engine mid-search restarts it, replays `position`, and always leaves a legal fallback move available from the last complete PV.
  4. The console refuses to start with a planted 6-piece filename in the tablebase directory, the boundary test proves no book decision is made at half-move counter ≥ 10 (`BOOK_MAX_PLY = 10`), and threefold/50-move detection raises an arbiter alert.
  5. Before game 3 the match model reports that game 3 repeats game 1's colour, records both end-of-game clocks and running tiebreak totals, and `doctor`/the pre-game checklist prints and asserts engine identity, base commit, effective `SyzygyProbeLimit`, book line/ply count, writable log path, local absolute asset paths, threads, hash, GPU declaration and clean-network assertion.
**Plans**: 3 plans

Plans:
- [ ] 03-01: `ClockModel` from `monotonic_ns()` deltas (never ticked) with `MOVE_ENTERED` backdating, increment on press, drift EMA/σ, opponent-clock capture at every hand-off, SYNC key with second confirmation, console watchdog + scramble mode
- [ ] 03-02: Supervision/restart/`position` replay/always-available fallback, journal `resume`, threefold + 50-move detection, `MatchController` (R11 colour sequence, per-game time, running tiebreak, Armageddon flag), result + both end clocks, `export-log` with option-set header and log-hash trailer, `log_lint` inside the game loop
- [ ] 03-03: Rule-ceiling guards and pre-game authority — TB inventory + fail-loud piece-count scan, book loader cap + boundary test, `doctor`/CHECK-01 — plus the fault-injection harness driving stdin with jittered 0.5–6 s delays and asserting no double move, no advance on illegal input, no missing log field, correct side to move, correct cumulative time and zero timeouts

**Why this phase**: The clock is the win condition and the watchdog is the last line of defence; neither can exist before the spine. The Rule 3 / Rule 4 guards are folded in here rather than given their own phase — at ~1 person-day they would be a phase that slips silently, whereas as gate items they cannot.

---

### Phase 4: Authored Time Manager
**Goal**: The engine spends the clock by our own decision procedure, running as the game default on every search, and the artefact that proves it was authored predates the code.
**Mode:** mvp
**Depends on**: Phase 1 (frozen contract + `mock_gui.py`) for all coding; Phase 3 for the WIN GATE. **Coding starts day 1 and must not wait for the console.**
**Window**: Days 1–6 in parallel; convergence days 5–6; **Gate 3 + WIN GATE days 6–7 — 1–2 Nov.**
**Requirements**: TM-01, TM-02, TM-03, TM-04, TM-05, TM-06, TM-07, TM-08, TM-09, TM-10, TM-11, TM-12, TM-13, AUTH-02, AUTH-03, AUTH-05, AUTH-06, AUTH-07
**Success Criteria** (what must be TRUE):
  1. Two humans play a complete 15+10 game offline on the match laptop through the real console and the real fork with `TimeManager=custom` as the default, 3-4-5 tablebases and the frozen book (or none): every half-move is logged with all eight fields **and** the `tm=custom-…` attestation carrying mode, latency p95, bank, budget and reason.
  2. Across that Bo3 with tiebreak accounting: zero timeouts, zero double moves, correct R11 colour sequence, and the stale-bestmove and `kill -9` injections green.
  3. A scripted near-flag position cannot be made to flag: every search respects `maximum ≤ time[us] − exec_tail − safety`, and the low-clock path still leaves a legal move.
  4. On the same binary, `TimeManager=upstream` and `custom` at 15+10 under simulated human latency produce different budgets **and different kinds of decision** (instant-move to bank, spend because the match bank is positive); the ablation reports Elo, W/L/D, time forfeits, average remaining clock and tiebreak wins; `git log base-sf19..HEAD -- src/timeman.*` shows `00-DESIGN.md` committed before the first implementation commit.
  5. The game path provably contains no `movetime` or `movestogo` (CI grep fails if one appears), `Move_Overhead` is asserted at 100 with the human tail reserved by the console and carried in the TM as `H × overhead` with no double count, `SyzygyProbeLimit` is 5 at startup, and `Ponder=true` ships only after the upstream +25 % clause is deleted — all confirmed by the startup self-test and the per-search trace.
**Plans**: 3 plans

Plans:
- [ ] 04-01: Allocator rewrite behind the retained `TimeManagement` interface (`init`/`optimum`/`maximum`/`elapsed`/`clear`, no `search.cpp` edits) — new inputs (measured latency p50/p95, opponent clock, match bank, game index, Armageddon context), new state (bank, latency model, reserve, spend history), reserve-constrained control law over expected remaining moves, new outputs (budget, instant-move flag, reason code), `sudden_death`/`armageddon` modes, hard maximum invariant, `TM Latency` clamped `[1200, 6000]` ms default 3500 applied at `IDLE`, ponder +25 % clause deleted, `TimeManager=upstream|custom` switch with loud startup self-test, `info string tm=…` trace; `00-DESIGN.md` committed first with the 19,757 ms / 20,785 ms baseline measured in 20 seconds
- [ ] 04-02: Ablation and written evidence — `experiments/timeman-ablation/run.sh` reproducing the table in one command on the same binary at 15+10 with simulated human latency, `01-ALGORITHM.md`, `04-DECISIONS.md`, the revert test (removing one constant removes a decision the engine can no longer make), and the SPRT wrapper
- [ ] 04-03: Integration and the WIN GATE — reserve-discounted `wtime`, trace copied into every log line, `Move_Overhead=100` asserted, option queue honoured, then the full Bo3 on the match laptop with both injections

**Why this phase**: This is the Rule 2 deliverable and the Rule 12 lever in one artefact, and it must be default-on in the shipped binary *before* the win gate proves it. The code starts on day 1 against `mock_gui.py`, so the phase is convergence and calibration, not the beginning. Its Gate 3 is a strength-and-clock gate, not a tournament: custom ≥ stock in Elo **and** ahead in cumulative remaining clock, then constants freeze.

---

### Phase 5: Match Policy, Ponder & Calibration — CONDITIONAL
**Goal**: *If and only if the WIN GATE is green*, convert released days into tiebreak edge: calibrated latency, ponder as a time saver, a match-aware policy and prepared book content.
**Mode:** mvp
**Depends on**: **Phase 4 WIN GATE passing.** On a red gate this phase does not start — the only permitted work is fixing Phase 4.
**Window**: Days 7–9 — 2–4 Nov. No gate of its own; it consumes the only slack in the plan.
**Requirements**: None. This phase owns **zero v1 requirements by design** — cutting it loses no legality, no survival and no authorship claim.
**v2 promoted (not v1)**: POL-01, POL-02, POL-03, POL-04, POL-05, BOOK-01, BOOK-02, DIAG-01
**Success Criteria** (what must be TRUE):
  1. With `Ponder=true` in a real game, a ponder hit costs the clock ~1 s of overhead instead of a full search, normal moves show no 25 % budget inflation, and a miss discards the stale `bestmove` with a logged `STALE_BESTMOVE`.
  2. After a dress-rehearsal game the latency model's `overhead_ms` differs from the 3500 default and matches the measured `wall_ms − engine_ms` p95 within tolerance, with the evidence in the log.
  3. Two 3-game tiebreak simulations with different `shadow_price` presets report cumulative remaining clock, and the chosen preset is recorded with the match-state inputs on every decision line.
  4. Armageddon as both colours behaves differently by design: Black spends less and trades into drawn endings, White spends more and avoids mass simplification — each decision traceable to its state inputs.
  5. A self-generated book of ≤10 half-moves emits `.bin` and `.epd`, book moves log `src=book d=0 n=0`, and ply 11 goes to search alone.
**Plans**: 3 plans

Plans:
- [ ] 05-01: Latency calibration from real logs (typing window measured, announcement and return tail inferred from SYNC residuals), ponder FSM (`go ponder` / `ponderhit` / `stop` + `search_id` discard, sync-during-ponder rebase, depth/node cap, hit-rate metric), and `Ponder=true` enabled **only here**
- [ ] 05-02: Policy function (shadow price of time + match-aware draw value, pure and unit-testable) tuned against 3-game tiebreak simulations with latency distributions; Armageddon presets as parameter sets only
- [ ] 05-03: Own ≤10-half-move book + ply-11 handoff timing, and the log-driven post-game diagnosis one-pager (cut first if the calendar moves)

**Why this phase**: It is conditional **by design**, and the conditioning is precise: the *hook* ships in Phase 4 (the `shadow_price`/bank/Armageddon interfaces and the ponder options exist before this phase opens); only the *tuning* is gated. It is also the only phase that needs a spike rather than research — the match-level shadow price has no external reference, so it gets timeboxed simulation, not a whiteboard.

---

### Phase 6: Adversarial Verification & Dress Rehearsal
**Goal**: The system survives the failure modes that only appear under a real clock, a real opponent and a real laptop — proven by injection and by two full rehearsals before freeze.
**Mode:** mvp
**Depends on**: Phase 4 (and Phase 5 if it ran; if Phase 5 was cut, this phase follows Phase 4 directly)
**Window**: Days 8–9 — 3–4 Nov. **Gate 4: rehearsal #1 → fix only what it found → rehearsal #2 + freeze.**
**Requirements**: PIPE-02, PIPE-04, PIPE-05, OPS-02, OPS-06
**Success Criteria** (what must be TRUE):
  1. The fault-injection suite drives stdin with jittered 0.5–6 s delays and every scenario passes — duplicate move, illegal move, SAN instead of UCI, `kill -9`, laptop-sleep gap, network re-enable attempt, `bestmove (none)` — with no double move, no advance on illegal input, no missing log field, correct side to move, correct cumulative time and zero timeouts at simulated 15+10.
  2. A complete Bo3 on the physical board, with the real operator, spoken UCI, offline, on the match laptop, logs all eight fields per half-move and leaves `log_lint` green.
  3. A clean clone builds under `unshare -n make` on the match laptop, `check_license.sh` and `doctor` are green, and a 60-minute sustained run keeps nps inside the range the TM assumes, into game 3.
  4. The 200–400 game regression gate against the upstream TM passes with `Move_Overhead=100` on both engines, and the declared resource profile (physical cores, not SMT siblings; `Hash ≤ min(4096 MB, 50 % RAM)`) matches the machine.
  5. Rehearsal #2 runs on the frozen configuration and the freeze is declared — after it, only defect fixes found by a rehearsal are permitted.
**Plans**: 3 plans

Plans:
- [ ] 06-01: Complete the injection suite and the artifact gates (`log_lint`, `doctor`, `check_license.sh`), plus a clean-clone offline build on the match laptop
- [ ] 06-02: Rehearsal #1 — full Bo3 + Armageddon on the physical board with the real operator and spoken UCI; assign Operator / Timekeeper-Adjudicator / Coach-Analyst with a one-page runbook; measure the laptop resource profile; 60-minute thermal run
- [ ] 06-03: Fix only what rehearsal found; run the 200–400 game regression gate as a gate (not a campaign); rehearsal #2 on the frozen configuration and declare freeze

**Why this phase**: The console's failure modes are *timing* failure modes, and unit tests cannot find timing bugs — injection can. Rehearsal #1 must be early enough to fix what it finds, and rehearsal #2 must run on exactly the configuration that plays. Freeze means freeze: the most common way a team with a winning engine loses is a change made in the last 20 % of the calendar.

---

### Phase 7: Game-Day Operations & Authorship Defense
**Goal**: On game day nothing about the environment, the log delivery or the authorship argument is improvised.
**Mode:** mvp
**Depends on**: Phase 6 (freeze declared)
**Window**: Days 9–10 — 4–5 Nov, all artifacts closed before the first round.
**Requirements**: AUTH-01, AUTH-04, OPS-01, OPS-03, OPS-04, OPS-05
**Success Criteria** (what must be TRUE):
  1. Before every game the operator completes and signs the pre-flight — `rfkill block all`, airplane mode, auto-connect and updaters off, no background analysis, `Hash`/`Threads` verified, performance power profile, plugged in, hard surface — and `network=off` appears in the log header.
  2. At the end of each game the log goes to USB **and** paper without editing, with a header carrying the full option set and asset hashes and a trailer carrying final clocks, computed bank and log hash — and the panel receives that file.
  3. The 3-minute offline demo switches `upstream|custom` on a scripted position and clock, shows a different budget **and a different kind of decision**, a real log line with the attestation, and the ablation table — with no network anywhere in the loop.
  4. Each of the three members answers the 15 anticipated questions and explains the algorithm, the evidence and the `src/timeman.*` diff without notes; the claim, the Rule 2 mapping, the inherited `file:line` table and the explicit non-claims fit on two pages.
  5. A hostile rehearsal with a person playing the panel is run and its findings are closed before the first round.

**Plans**: 3 plans

Plans:
- [ ] 07-01: `AUTHORSHIP.md` (one-sentence claim, Rule 2 mapping table, what is new, inherited `file:line` table, explicit non-claims, 60-second verification recipe, evidence index) and `03-DEFENSE.md` (3-minute script + 15 questions) — judge-facing docs in Portuguese, code comments minimal and upstream-style
- [ ] 07-02: 3-minute offline demo on a scripted position/clock, one-page handout, hostile arguição rehearsal, all three members drilled on algorithm, evidence and diff
- [ ] 07-03: Signed per-game pre-flight, log delivery ritual (USB + paper, never edited), USB/panel archive audit and first-round dry run

**Why this phase**: These failures are cheap to prevent and impossible to recover from. The arguição is where a winning engine becomes a trophy or a DQ, and the log handed to the banca — carrying the attestation on every move — is the only artefact that proves the authored component actually ran.

---

## Phase Ordering, Gates & Critical Path

**Execution order:** 1 → 2 → 3 → 4 → 5 *(only if the WIN GATE is green)* → 6 → 7. If Phase 5 is cut, 4 → 6.

| Phase | Gate | Day | Gate condition |
|---|---|---|---|
| 1 | Gate 0 | 0 | Contract frozen; both mocks pass; stock binary builds and benches offline on the match laptop |
| 2 | Gate 1 | 2 | Complete game vs stock Stockfish, all eight fields logged, SYNC works, `test_ponder_discard` green, `log_lint` green |
| 3 | Gate 2 | 4 | Console vs the fork with ponder on; mid-game restart replays; TM trace parsed; `kill -9` recovery < 10 s; TB assert fires on a planted 6-piece file; book boundary test proves no decision at counter ≥ 10 |
| 4 | Gate 3 | 6 | Custom TM ≥ upstream in Elo **and** ahead in cumulative remaining clock under simulated latency; constants frozen |
| 4 | **WIN GATE** | 6–7 | Full offline Bo3 on the match laptop, real console + real fork, custom TM default — see below. **No later phase starts if this fails.** |
| 5 | — | 7–9 | Conditional; no gate of its own |
| 6 | Gate 4 | 8–9 | Rehearsal #1 passed → fix only what it found → rehearsal #2 + freeze |
| 7 | Ship | 9–10 | Pre-flight signed, log ritual drilled, demo and hostile rehearsal closed |

**Two tracks, two different gates — both are real:**
- **The console track (Phases 2 → 3) gates the schedule.** It is ~13–15 person-days on one person; nothing is end-to-end verifiable without it. A slip here slips everything.
- **The time-manager track (Phase 4) gates the trophy.** It carries the Rule 2 deliverable and the Rule 12 lever, but gates nothing else — it is written against `mock_gui.py` from day 1 behind the frozen `go` contract. Neither track may wait on the other; the day-0 contract freeze is what makes that possible.
- **The infra track** (Phase 1, then harness and evidence) is the third leg: it produces the artefacts that prove the other two, and it never blocks them.

**No phase carries a `UI hint`.** The console is a line-oriented terminal loop, Rule 9 declares command line sufficient, and any GUI is explicitly out of scope — a UI design phase would spend days and win zero Elo.

**Frozen contract rule:** `docs/PROTOCOL.md` and `docs/LOGBOOK.md` are the interface for all three tracks. A change to either is a cross-track event, costs the rest of the day, and requires all three owners.

---

## The WIN GATE (Non-Negotiable, Day 6/7)

On the **match laptop**, **offline**, with the **real console** and the **real fork**, `TimeManager=custom` as the default, the **3-4-5 tablebase directory**, and the **frozen book (or none)**:

1. Two humans play a complete **15+10** game through the spoken four-step protocol with jittered latency — **Bo3 with tiebreak accounting if the day allows**.
2. **Every half-move** is logged with all eight Rule 9 fields **plus the `tm=custom-…` attestation** (mode, latency p95, bank, budget, reason).
3. **Zero timeouts.**
4. **Zero double moves**, correct side to move throughout.
5. The **stale-bestmove** injection is green.
6. The **`kill -9`** injection is green (resume with no lost half-move).
7. The match model reports the **correct R11 colour sequence** (game 3 repeats game 1).
8. Cumulative remaining clock is **not behind** the upstream-TM baseline measured in Gate 3.

**If any item fails, the only permitted work until it passes is fixing it.** Phase 5 does not open on a red gate; Phase 6 does not start; the schedule absorbs the loss by cutting, in the order below — never by moving the gate.

---

## Schedule Reality

| | Person-days |
|---|---|
| Table stakes (console, clock, protocol, log, compliance, harness) | 21–24 raw |
| Available: 10 days × 3 people at 100 % | 30 |
| Available at realistic efficiency (~70 %) | ~21 |
| Slack | **zero** |

Ten calendar days is a **2-week-equivalent plan compressed to the deadline**, not a comfortable one-week plan. There is no version of this schedule with slack. The honest response is to decide the cuts in advance and treat the WIN GATE as fixed and scope as variable.

---

## Cut Order

Cut from the top until the calendar fits. **Never reorder** — each cut is safe for the reason given, and cutting in this order preserves legality, survival and the authorship claim for as long as possible.

| # | Cut | Why it is safe |
|---|---|---|
| 1 | Match-policy **tuning** (beyond defaults) | The hook ships in Phase 4; a constant `shadow_price = 1.0` is a legal, correct default that forfeits only tiebreak edge |
| 2 | Book **content** | Rule 3 permits no book at all; a book is worth ≤1 ply of preparation at ~3650 Elo. Keep the loader, the cap and `src=book` logging |
| 3 | SPRT campaign, tuning, loss mining | Keep the 200–400 game regression gate. The TM's value is measured against the **console**, not a large SPRT batch |
| 4 | Ponder | It saves ~2.5 min/game and is the largest source of game-losing bugs. Enable only if `test_ponder_discard` is green and the WIN GATE passed |
| 5 | Profiling beyond one sustained run, resign advisor, log-diagnosis one-pager | Conveniences, not survival |
| 6 | Armageddon specialisation | Keep a `sudden_death` flag with zero-increment reserve floors; drop colour-specific draw-value policy |
| 7 | Resync sophistication | Fall back to "re-enter the last N verified moves" — never to free-form FEN editing as the primary path |

**If only five working days remain**, there is no path to a from-scratch console plus a calibrated TM. The only defensible entry is stock `sf_19` plus a thin console with our own clock model, watchdog, legal gate and log layered around `engine.play()`, accepting that ponder, calibration and transport-level authorship are lost — taken deliberately and documented, not discovered on day 4.

---

## Minimum Viable Competition Entry Floor

The floor beneath which entering is not worth the trip. Everything above it is upside.

1. Pinned `sf_19` clone with upstream history, `base-sf19` tag, `NOTICE`/`PROVENANCE`, GPL headers + modification notices, clean `unshare -n make` on the match laptop, net vendored.
2. Tablebase directory containing only 3-4-5; `SyzygyProbeLimit=5`; `Syzygy50MoveRule=true`; startup assert `MaxCardinality ≤ 5`; SHA-256 inventory.
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

**Note:** item 12 is reachable only through the WIN GATE; items 1–11 are the cut-order floor and are the reason the compliance and clock work sits in Phases 1 and 3 rather than in a "polish" phase.

---

## Non-Negotiables — Never Cut, Under Any Calendar

- Provenance + offline build (`unshare -n make` proof, vendored net, declared dependencies).
- `SyzygyProbeLimit=5` + `MaxCardinality` assert + directory inventory and fail-loud scan.
- Strict UCI parse + legal gate + explicit state machine.
- Dual clock + `MOVE_ENTERED` backdating + console watchdog.
- Append-only journal + `resume`.
- The eight-field log for **every half-move**, including the opponent's.
- The R11 match model + both end-of-game clocks + running tiebreak.
- The pre-flight checklist.
- **One** full rehearsal on the real laptop with the real operator.
- `00-DESIGN.md` committed before the implementation commit.
- The WIN GATE itself.

---

## Load-Bearing Findings — Where Each One Is Enforced

These eight findings decide the match. Each is encoded in a phase requirement or gate item so it cannot be lost in planning or execution.

| # | Finding | Enforced by |
|---|---|---|
| CF-1 | Default `Move Overhead = 10 ms` against a 4–8 s human tail hands over 3–5 min/game — the entire Rule 12 tiebreak. Raising the option is a trap (amortised ×(2+mtg), 5000 subtracts 260 s and still flags) | **Two layers, no double count:** console reserves the human tail and sends reserve-discounted `wtime` (CLOCK-03, Phase 3); engine stays at `Move_Overhead=100`, asserted in `doctor`/CHECK-01 (Phase 3) and carried as an explicit `H × overhead` term in the TM (TM-07, TM-09, Phase 4). Every move logs `wall_ms − engine_ms` |
| CF-2 | `SyzygyProbeLimit` defaults to **7**, not 5 — an automatic Rule 4 violation | LIMIT-01 (Phase 1 override + assert), LIMIT-02 (Phase 3 directory scan + inventory), CHECK-01 (Phase 3 effective value printed) |
| CF-3 | The untouched allocator spends **19,757 ms / 20,785 ms** on moves 1 and 2 at 15+10 — net −10 s per move against the bank | TM-05 (reserve-constrained law), TM-08 (solvency `spend < inc − overhead`, 2–4 s target, `banked_seconds` first-class), baseline recorded in TM-02 `00-DESIGN.md` (Phase 4) |
| CF-4 | `Ponder=true` adds **25 %** to `optimumTime` on every normal move; `startTime` is *not* reset on `ponderhit` (keep that — it is the free move) | TM-13 (+25 % clause deleted, Phase 4); `Ponder=true` ships only in Phase 5 after the WIN GATE, and never with upstream timeman |
| CF-5 | `movetime` sets `time[us]=0` and the authored TM never runs — a direct Rule 2 exposure | FOUND-05 (frozen `go` line forbids it, Phase 1), TM-11 (per-search attestation copied into the log, Phase 4), CI grep in Phase 4 criterion 5 |
| CF-6 | Rule 11: game 3 repeats game 1's colour — naive alternation gets the decider wrong | CLOCK-09 (explicit colour sequence, unit-tested both cases, printed in the checklist, Phase 3) |
| CF-7 | The stale ponder `bestmove` is the most likely game-losing bug | `search_id` + `discarding` flag + one outstanding `go`, Phase 2 criterion 4 and plan 02-02, with `test_ponder_discard.py` written **before** the handler; re-proved inside the WIN GATE |
| CF-8 | The compliance artefacts **are** the authorship evidence; retrofitting fails | FOUND-05 (contract frozen day 0), TM-02 (`00-DESIGN.md` before code), TM-12 (`upstream|custom` switch), AUTH-03/AUTH-06 (raw results + one-command reproduction), AUTH-01/AUTH-04 (Phase 7) |

**Three easy-to-miss, expensive-to-miss findings, also encoded:**
- **Clock backdating** (`since = T_typed − input_latency_ema`) — CLOCK-01, Phase 3, criterion 1. Without it the belief is too generous on *every* move; 72 s of phantom time over 60 moves is a loss on time that looks impossible.
- **Wire format verified before the parser** — Phase 2 plan 02-01 spike; `info string` is not analysis, `bestmove (none)` exists, and `sf_19` exits on an illegal `position`.
- **`setoption` during a ponder deadlocks the console** — Phase 2 plan 02-01 option queue applied at `IDLE`; `TM Latency` is applied there too (TM-07, Phase 4).

---

## Coverage Validation

| Phase | Requirements | Count |
|---|---|---|
| 1. Foundation, Provenance & Frozen Contract | FOUND-01…06, LIMIT-01, LIMIT-04, PIPE-01 | 9 |
| 2. Console Protocol Spine | PROTO-01…08, LOG-01…04 | 12 |
| 3. Clock Authority, Resilience & Rule-Ceiling Guards | CLOCK-01…09, LIMIT-02, LIMIT-03, LOG-05, CHECK-01, PIPE-03 | 14 |
| 4. Authored Time Manager | TM-01…13, AUTH-02, AUTH-03, AUTH-05, AUTH-06, AUTH-07 | 18 |
| 5. Match Policy, Ponder & Calibration (conditional) | — (promotes v2 only) | 0 |
| 6. Adversarial Verification & Dress Rehearsal | PIPE-02, PIPE-04, PIPE-05, OPS-02, OPS-06 | 5 |
| 7. Game-Day Operations & Authorship Defense | AUTH-01, AUTH-04, OPS-01, OPS-03, OPS-04, OPS-05 | 6 |
| **Total** | | **64** |

✓ **64/64 v1 requirements mapped, each to exactly one phase.**
✓ **Zero orphans, zero duplicates.**
✓ Phase 5 owns no v1 requirement — deleting it costs no coverage, no legality, no survival and no authorship claim.

> **Count correction:** earlier documents said 58 v1 requirements. The enumerated ID list in `REQUIREMENTS.md` (FOUND 6 + LIMIT 4 + PROTO 8 + CLOCK 9 + LOG 5 + CHECK 1 + TM 13 + AUTH 7 + PIPE 5 + OPS 6) totals **64**; the figure of 58 omitted `OPS-01…06`. Coverage is validated against the real IDs.

---

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → (5, conditional) → 6 → 7

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Foundation, Provenance & Frozen Contract | 0/3 | Not started | - |
| 2. Console Protocol Spine | 1/3 | In Progress | - |
| 3. Clock Authority, Resilience & Rule-Ceiling Guards | 0/3 | Not started | - |
| 4. Authored Time Manager | 0/3 | Not started | - |
| 5. Match Policy, Ponder & Calibration (conditional) | 0/3 | Not started | - |
| 6. Adversarial Verification & Dress Rehearsal | 0/3 | Not started | - |
| 7. Game-Day Operations & Authorship Defense | 0/3 | Not started | - |
