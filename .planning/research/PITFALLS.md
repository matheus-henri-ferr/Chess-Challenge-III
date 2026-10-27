# Pitfalls Research

**Domain:** Competition chess engine (Stockfish fork) for a human-mediated, spoken-UCI tournament — III Chess Challenge, 15 min + 10 s increment, best of 3, team of 3, 1–2 week build.
**Researched:** 2026-10-26
**Confidence:** HIGH for rule-derived and source-verified claims; MEDIUM for simulation and judge-behavior claims; LOW for field composition (no data on the actual opponent pool).

> Every pitfall below is tied to a numbered rule in `docs/competition-rules.md` or to a documented competitive dynamic (human latency, clock ownership, tiebreak arithmetic). Stockfish behavior was verified against the pinned release `sf_19` (`f879373d916914de3a478aabb4226e6460c17d15`, 2026-09-05) and master `ff3a6c50` (2026-10-25). Where `sf_19` and master differ, it is called out.

---

## How Teams Actually Lose

There are only six ways to leave this tournament without the trophy. Every pitfall in this document maps to one of them.

| Failure class | Concrete trigger | Rule | Recoverable? |
|---|---|---|---|
| **Disqualification / claim rejected** | Time-management claim judged "mero ajuste de parâmetros"; base commit or license not declared/published; network on; GPU undeclared; book >10 plies; tablebase >5 pieces | 1, 2, 3, 4, 8, 14 | No — decision is retroactive and can void wins |
| **Loss on the clock** | Flag fall; engine burns the bank; human execution tail consumes the last seconds | 7, 12 | No — game lost, and the flag contributes 0 to the tiebreak |
| **Loss on the protocol** | Illegal move annulled with clock running; board/software divergence; operator announces a PV instead of `bestmove`; promotion suffix lost | 5, 10 | Sometimes — only with a rehearsed recovery path |
| **Loss on the machine** | Engine exits mid-game (`position` illegal move, `Hash` OOM); console hangs (`setoption` during ponder); thermal collapse | — | Sometimes — only with supervision + persisted state |
| **Loss on the tiebreak** | Match ends 1–1–1 or 0–0–0; opponent conserved more total clock across the three games | 12 | No — decided by arithmetic |
| **Non-compliance** | Log missing PV/nodes/time, only our moves, or delivered after the event instead of after each game | 9 | No — the log is the evidence |

**Key asymmetry:** a violation is not just a lost game. The panel reads the log, the repo, and the declarations. A game you won with a 6-piece tablebase or a book move at ply 11 can become a loss or a DQ after the fact. The cheapest insurance in the whole project is compliance evidence built *during* development, not after.

---

## Phase Key (provisional — reconcile with ROADMAP.md)

The roadmap does not exist yet. These provisional phases are used for the "Phase to address" field. If the roadmap merges or renames them, the mapping still holds by deliverable.

| ID | Provisional phase | Deliverable |
|---|---|---|
| **P1** | Compliance & Provenance Foundation | Repo imported with history, `Copying.txt`/`AUTHORS` intact, `PROVENANCE.md`, base commit declared, dependency manifests, publication dry run, `AUTHORSHIP.md` scaffold |
| **P2** | Engine Baseline & Reproducible Offline Build | Pinned base, vendored NNUE, fixed build flags, UCI option baseline, sustained-load benchmark, clean offline build |
| **P3** | Authored Time Manager | Design doc before code, replacement `TimeManagement` in the engine, match/latency inputs, sudden-death and Armageddon modes, ablation harness, runtime attestation |
| **P4** | Operator Console & Spoken Protocol | UCI state machine, ponder lifecycle, board mirror + resync, legality gate, panic/announce flow, timer sync, log writer, supervisor |
| **P5** | Book & Tablebase Guardrails | 10-ply counter, book provenance/validation, TB directory segregation, `SyzygyProbeLimit=5`, inventory |
| **P6** | Offline Test Pipeline & Opponent Prep | Realistic TC + latency simulation, 3-game match/tiebreak sims, SPRT, fault injection, protocol drills, opponent/color prep |
| **P7** | Game-Day Operations & Argumentation | Preflight checklist, network-off proof, dependency freeze, thermal run, role assignment, log delivery, authorship defense rehearsal |

---

## Critical Pitfalls

### Group A — Authorship & qualification (Rule 2)

#### A1. The "parameter tweak dressed as a component" rejection

**What goes wrong:**
The team claims authored time management, but the change is Stockfish's `TimeManagement::init` with different constants, a thin wrapper that rescales `optimumTime`, or a faithful re-implementation of the same heuristic in a new file. The judge applies Rule 2's explicit exclusion list — *"reformatação de código, tradução de comentários, renomeação de variáveis, nem o mero ajuste de parâmetros já existentes"* — and the claim fails. The team is then treated as not having a qualifying modification, with whatever consequence the organizers apply (likely disqualification or non-classification), regardless of results.

**Why it happens:**
Stockfish's Timeman is already strong and heavily tuned; the lowest-risk path under a two-week deadline is to nudge it. Teams also believe "different numbers = different algorithm," and they minimize the diff to avoid breaking strength. That is precisely the shape the rule excludes.

**How to avoid:**
Define the authored component as a **different decision procedure**, not a different constant. It must have at least three of:
1. **New state** the base engine does not have (match time bank, per-opponent latency model, game index, tiebreak delta).
2. **New external inputs** (measured human entry/execution latency, opponent's remaining clock, match score, Armageddon color/draw rule, bank after each game).
3. **A new control law** (e.g., a reserve-constrained budget over expected remaining moves, instead of a fraction of `timeLeft`).
4. **A measurable behavioral difference** that survives an ablation: same binary, one switch, different allocation and different results.

Put the component **inside the engine's decision path** (`src/timeman.cpp` / `src/timeman.h` plus a few `search.cpp` hooks), exposed through new UCI options (`MatchBank`, `LatencyP95`, `Armageddon`, `TimeManager=upstream|custom`). If the console computes a `movetime` and the engine merely obeys it, the engine's Timeman is bypassed; a judge can reasonably say the engine was not modified and the "component" is an external script. The console should pass *context*, not the budget.

The self-test for "is this parameter tweaking?": revert your change to a single constant or a single scale factor. If behavior is qualitatively unchanged, it is parameter tweaking. If reverting removes a decision the engine can no longer make (e.g., "instant-move in a dead-equal position to bank tiebreak time," "spend big when the match bank is +3 min"), it is a component.

Also: claim **one** component, deeply. Do not claim evaluation, search, book, and tablebase in the same breath. Rule 3 says a third-party book does not count as authorship, Rule 4 says tablebases do not count, and neither is a qualifying Rule 2 component. Claiming them weakens the credible claim. State explicitly in the dossier: *"Claimed: time management. Not claimed: evaluation, search, book, tablebase."*

**Warning signs:**
- The diff is mostly numeric constants or a single multiplier.
- `git log` shows the design document committed *after* the implementation.
- Nobody can name a position/clock where the custom manager makes a different *kind* of decision than upstream.
- The defense uses the word "tuned" or "adjusted" instead of "computes," "allocates," "constrains."
- The dossier lists more than one claimed component.

**Phase to address:**
P3 (design first), with the dossier scaffold in P1. Verified in P7.

---

#### A2. The authored component is not actually running during games

**What goes wrong:**
The custom manager exists but is behind a flag that defaults to `upstream`; the console sends a fixed `go movetime` so the engine's Timeman never decides; a catch-all fallback silently reverts to Stockfish on any exception; or two allocators fight (console computes a budget, engine re-allocates inside it). The judge asks "show me it running," and the log shows Stockfish behavior.

**Why it happens:**
Integration pressure. A fixed `movetime` makes the console work in an hour; fallbacks are added for robustness and never removed; the custom path is only exercised in unit tests, not in the game binary.

**How to avoid:**
- One declared source of truth, written in `AUTHORSHIP.md` and enforced in code.
- **Runtime attestation:** at the start of every search the engine emits an `info string tm=custom-vX.Y mode=increment|sudden_death|armageddon latency_p95_ms=... bank_ms=... budget_ms=... reason=...` line; the console copies it into the move's log line. The log itself proves the component ran.
- A startup self-test that fails loudly if the custom path is not active (`TimeManager=custom` by default in the game config).
- `TimeManager=upstream` exists **only** for ablation and drills, never for the event.
- An integration test on a scripted position/clock asserting the custom budget differs from upstream by a documented amount.

**Warning signs:**
- `grep -rn "movetime" console/` shows it is always set in the game path.
- The default value of the switch is `upstream`.
- No log line identifies which manager ran.
- The ablation binary and the game binary are the same file with a flag that is off on game day.

**Phase to address:**
P3 + P4; verified in P6 drills.

---

#### A3. Evidence assembled after the fact

**What goes wrong:**
At the arguição the team has code but no design record, no experiment, no ablation, and no per-author history. Everything landed in one "initial commit," or history was squashed for cleanliness, or the fork was imported from a zip. The judge sees a small diff and concludes "tweak."

**Why it happens:**
Teams treat evidence as documentation, and documentation is always postponed. They also rewrite history to look tidy, destroying exactly the record that proves independent work.

**How to avoid:**
Build evidence while building the component:
- Commit `docs/timeman/00-DESIGN.md` **before** the implementation commit. Its timestamp is the strongest single signal of independent conception.
- Keep the upstream history: `git remote add upstream`, fetch the pinned tag, never squash the import. Tag `base-sf19`.
- Make granular commits by each author, with messages that reference design decisions.
- Create `experiments/timeman-ablation/` with a runnable script and raw results from day one.
- If the repo really was imported as a zip, reconstruct provenance now: apply your changes as a patch series on top of the upstream tag, or at minimum record the base SHA and the exact diff in `PROVENANCE.md`.

**Warning signs:**
- `git log --oneline | wc -l` is suspiciously small.
- First commit message is "initial commit" with the entire fork.
- The design doc's first commit is after the implementation.
- No `experiments/` directory.
- The base commit is not in history.

**Phase to address:**
P1 + P3.

### Group B — License, provenance, and publication (Rules 1, 15)

#### B1. License headers stripped, notices deleted, modifications unmarked

**What goes wrong:**
`Copying.txt` and `AUTHORS` are deleted as "not needed"; per-file GPL headers are removed by reformatting or by copying functions into new files; the original copyright line is replaced with the team's name; no file states that it was modified. Rule 1's GPLv3 obligation is breached even though the code still runs.

**Why it happens:**
Teams tidy the repo; new-file templates omit the header; and because the code is delivered to the panel anyway, they assume GPL is irrelevant. PROJECT.md itself says GPL is "irrelevant in practice" — that is true for *permission*, false for *compliance*. GPLv3 §5(a) requires prominent notices that you modified the work, with a date; §4 requires keeping copyright, license, and warranty notices; §6 requires the Corresponding Source when you convey the binary.

**How to avoid:**
- A pre-commit check (`scripts/check_license.sh`) that fails if any tracked `src/**/*.cpp|*.h` lacks `GNU General Public License` and a `Copyright (C)` line.
- Never delete `Copying.txt` or `AUTHORS`. Add a `NOTICE` describing the fork, the base commit, and the modified files.
- Add a modification line to each modified file, e.g. `Modified by <Team> on 2026-10-28: replaced TimeManagement::init with match-aware allocator.` Keep the original copyright.
- New files get the GPLv3 header plus the team's copyright.
- The console should print a license notice at startup or respond to `--license`. Stockfish already supports `--license`.
- License the console GPLv3 as well. `python-chess` is GPL-3.0+; an MIT console that links it is a license conflict. Since the repo is GPLv3 anyway, use GPLv3 throughout and keep third-party notices in `LICENSES/`.

**Warning signs:**
- `grep -L "GNU General Public License" $(git ls-files 'src/*.cpp' 'src/*.h')` returns files.
- `git diff base-sf19..HEAD -- Copying.txt AUTHORS` shows deletions.
- New files have no header.
- No modification notices anywhere.

**Phase to address:**
P1, enforced continuously in CI/pre-commit.

---

#### B2. Base commit undeclared or unreproducible

**What goes wrong:**
The accreditation form says "Stockfish 17" or "latest"; the fork was imported from a zip or a shallow clone and then squashed; the exact commit is not recorded; the panel cannot reproduce the binary from the published source. Rule 1 requires the base project **and the commit/version of origin** at accreditation.

**Why it happens:**
Teams download a release zip, not a git clone; they rebase/squash for a clean history; they update mid-project and lose track of which upstream state they forked.

**How to avoid:**
- Pin a specific base. As of research: release `sf_19` = `f879373d916914de3a478aabb4226e6460c17d15` (published 2026-09-05); master = `ff3a6c508ed731f0dcf253f4ddf646df19a62f84` (2026-10-25). Prefer the release tag for reproducibility; if you need post-release fixes, pin the master SHA and say so.
- Keep the full upstream history and tag `base-sf19`.
- Record the SHA, date, URL, and the exact build recipe (compiler, flags, net file hash) in `PROVENANCE.md` **and** in the accreditation form.
- If you merge upstream later, record the new base and the merge commit; update the declaration if the submitted version changes.
- Make the binary self-identifying: add the base SHA and your fork version to the `id name` string or a startup `info string`.

**Warning signs:**
- `git log --all --oneline | grep -i stockfish` is empty.
- No tag, no `PROVENANCE.md`, or a vague "Stockfish latest."
- The `uci` id string does not identify the base or the fork.
- The accreditation form was filled by someone who does not know the SHA.

**Phase to address:**
P1 + P2.

---

#### B3. The repository is not actually available to the panel

**What goes wrong:**
Rule 1 requires the repository to be made available to the panel at the end of the event. The team develops in a private repo and forgets to grant access or export; the repo contains multi-GB Syzygy/book/net files and cannot be pushed; Git LFS stores pointers without the objects; there is no network at the venue to publish anything. A win becomes a compliance failure.

**Why it happens:**
"We'll publish at the end" with no rehearsal; private-by-default hosting; large binary assets; no offline release artifact.

**How to avoid:**
- Do a publication dry run in P1, not P7: create the public mirror (or grant panel access) early and verify it.
- Prepare a self-contained `RELEASE/` archive on a USB drive: source + `Copying.txt` + `AUTHORS` + `NOTICE` + `PROVENANCE.md` + `BUILD.md` + dependency lockfiles + SHA-256 inventory of net/book/tablebase files. Rule 15 explicitly allows large weights on physical media with an origin declaration.
- Keep large binaries out of git; document their paths and checksums, or ship them on the USB.
- Test on a clean machine: `git clone <mirror> && cd repo && unshare -n make -j` must succeed.

**Warning signs:**
- A clean clone fails or is incomplete.
- `git lfs ls-files` shows only pointers.
- Repo size exceeds the host limit.
- No USB archive exists.
- "We'll publish after the event" appears in the plan.

**Phase to address:**
P1 + P7 rehearsal.

---

#### B4. Model-weight provenance undocumented — and the offline build downloads a net

**What goes wrong:**
The default network is embedded in the binary, so it is invisible in the repo. The pinned base (`sf_19`, commit `f879373d`) names it `nn-1a298aa575a0.nnue`; current master (`ff3a6c50`) names it `nn-c9e480e92425.nnue`. The team swaps in a "stronger net" from a forum without recording where it came from, or modifies `EvalFileDefaultName` and forgets. Rule 15 requires an origin declaration for weights; downloaded third-party weights do not count as authorship. Separately, Stockfish's Makefile has a `net` target that downloads the net during build; on the venue laptop with Wi-Fi off, a clean build fails.

**Why it happens:**
The net is embedded, so it feels like part of the compiler; builds are done once at home with network and never tested offline.

**How to avoid:**
- Keep the base net. It is the simplest, most defensible choice, and it is already declared by the base project. Record its filename and SHA-256.
- If you swap nets, treat it as a new asset: source, license, SHA-256, and a note that it is not authored by the team. Rule 15 allows team-trained weights only with the training code; that is out of scope here.
- Vendor the exact `.nnue` file in the repo (or a documented `nets/` path) and use `make net` **before** the event so the build never needs the network.
- Test a clean offline build: `unshare -n make -j$(nproc)` on a fresh clone.
- Declare the net at accreditation alongside the base commit.

**Warning signs:**
- Build logs contain `curl`/`wget`.
- No `.nnue` file in the repo or USB archive.
- `EvalFileDefaultName` differs from the base with no explanation.
- No SHA-256 inventory.

**Phase to address:**
P1 + P2.

---

### Group C — Clock and time forfeit (Rules 7, 12, 13)

#### C1. Stockfish's `Move Overhead` is 10 ms; the human loop is 10–25 seconds

**What goes wrong:**
The engine reserves 10 ms per move for GUI/network overhead. Rule 7 fixes the budget (15 minutes per team, 10 seconds increment per move) and says the software must manage its own time. In this competition the real per-move overhead is: entering the opponent's move, thinking, announcing, waiting for confirmation, moving the piece on the physical board, and pressing the clock. That is seconds, not milliseconds. The engine plans to spend nearly the whole budget; the human tail then consumes the rest; the team flags.

This is not a tuning problem. The verified source shows:

```cpp
mtg = limits.movestogo ? min(limits.movestogo, 50) : 50;
timeLeft = max(1, time[us] + inc[us]*(mtg-1) - moveOverhead*(2+mtg));
optimumTime = optScale * timeLeft;
maximumTime = max(optimumTime,
                  min(0.8097*time[us] - moveOverhead, maxScale*optimumTime));
if (options["Ponder"]) optimumTime += optimumTime/4;
```

With `Move Overhead = 10`, the engine subtracts only `10 × 52 = 520 ms` across the whole 50-move horizon. The option's maximum is **5000 ms** — it cannot express a 12-second human loop. Raising it to 5000 subtracts `5000 × 52 = 260 s` from `timeLeft`, which crushes the allocator's effective budget and still does not model the real tail.

A simulation of the sf_19 allocator (each move spends `optimumTime`, increment added after the move, human overhead charged twice per ply for entry + announce/move/press) gives:

| Scenario | Human overhead per ply | First flag |
|---|---|---|
| 15+10, no human overhead | 0 s | none through 80 plies (≈32 s left) |
| 15+10 | 6 s | ply 26 (move 14) |
| 15+10 | 12 s | **ply 19 (move 10)** |
| 15+10 + `Ponder=true` | 12 s | **ply 16 (move 9)** |
| 15+10, `Move Overhead=5000` | 12 s | ply 23 (move 12) — still flags |
| Armageddon 5+0 (White) | 8 s | ply 14 (move 8) |
| Armageddon 4+0 (Black) | 8 s | ply 12 (move 7) |

*Model, not a measurement: real games vary because the engine sometimes uses less than `optimumTime` and sometimes extends toward `maximumTime` when the best move changes. The direction — default Stockfish time management is not solvent under a seconds-scale human loop — is robust. Confidence: MEDIUM.*

**Why it happens:**
The default is tuned for online GUI play where the "move overhead" is network latency, not a human reading a move aloud, waiting for a repeat-back, moving a piece, and pressing a clock. Rule 13 explicitly says the team must handle the input delay; it does not say the engine already does.

**How to avoid:**
- Replace the fraction-of-`timeLeft` heuristic with a **budget over expected remaining moves**: `available_for_thinking = remaining_clock + H*increment − H*measured_overhead − reserve`, where `H` is the expected number of your remaining moves and `measured_overhead` is the p95 of the real human loop.
- Measure the loop in drills: timestamp opponent's clock press → your entry done → `go` → `bestmove` → announcement → confirmation → piece moved → your clock press. Use p50 and p95, not a guess.
- Keep a **hard execution reserve**: never let the engine think below `exec_tail_p95 + safety` (e.g., 10 s). The deadline is the clock press, not the `bestmove` line. At 10 s remaining **with the 10 s increment**, `timeLeft` still includes 49 future increments, so Stockfish's `maximumTime` can allocate ~8 s, leaving ~2 s for a 5–10 s human tail — a guaranteed flag. Even without increment, the reserve is a fraction of the clock, not a measured execution tail. The custom manager must cap at `remaining − exec_tail − safety`, even if that means an instant move.
- Add an **instant-move mode** below ~30 s: stop the search, play the current best move, log `source=instant`.
- Calibrate against the real console, not theory. Re-measure after any UI change.
- If you keep Stockfish's Timeman as a fallback, set `Move Overhead` to the measured p95 (capped at 5000) **and** verify the `timeLeft` subtraction; do not assume it solves the problem.

**Warning signs:**
- `Move Overhead` is still 10 in the game config.
- `info ... time` is close to the remaining clock on any move.
- Any move completed with less than 10 s on the physical clock.
- A flag in practice, or a "we almost flagged" story.
- The team says "Stockfish manages time well" without having measured the human loop.

**Phase to address:**
P3 (policy) + P4 (measurement) + P6 (calibration).

---

#### C2. Ponder is enabled without understanding its two side effects

**What goes wrong:**
Rule 13 allows pondering, so the team sets `Ponder=true` and sends `go ponder`. Two verified side effects bite:
1. `if (options["Ponder"]) optimumTime += optimumTime/4;` — **every normal move gets 25% more time** while the option is on, directly fighting the Rule 12 time bank.
2. Stockfish sets `startTime` when the `go` command is parsed and **does not reset it on `ponderhit`**. After a long opponent think, the engine believes it has already used that time; on `ponderhit` it stops almost immediately (under-using your clock, losing strength) or, if the console naively restarts with a fresh budget, it can overspend.

**Why it happens:**
Pondering looks like free strength; the UCI semantics are subtle and version-specific; nobody reads `timeman.cpp` or `search.cpp`.

**How to avoid:**
- Treat ponder as a first-class state in the console (`PONDERING`), not a flag.
- Choose one policy and document it:
  - **(a) Engine-side reset:** add an authored `ponderhit` handler that resets the time manager's `startTime` to now (and recomputes the budget from the real clock). This is a legitimate part of the authored time manager.
  - **(b) Console-side restart:** on `ponderhit`, send `stop`, drain to `bestmove`, then send `position` + `go` with the real remaining budget. The TT survives in the same process, so most of the ponder value is retained.
- Never leave `Ponder=true` when you are not pondering.
- Cap ponder by depth or nodes (thermal safety); log the ponder move, hit/miss, and time pondered.
- Test with a scripted opponent that thinks 1 s, 30 s, and 5 min.

**Warning signs:**
- `Ponder true` in the game config with no `ponderhit` handler in the console.
- `bestmove` arrives instantly after a long opponent think.
- Ponder search runs uncapped on all cores for minutes.
- No ponder hit-rate metric.

**Phase to address:**
P3 + P4; tested in P6.

---

#### C3. Burning clock for Elo loses the Rule 12 tiebreak

**What goes wrong:**
The team optimizes game score and spends the bank on small edges. Matches end 1–1–1 or 0–0–0; Rule 12 decides by **total remaining time summed across the three games**. The opponent conserved. Worse, a flag fall contributes **0** to your bank for that game: you lose the game and the tiebreak at once.

Two version facts matter:
- `sf_19` has **no** "decrease time usage if behind" clause at all. Master added it (the `timeAdvantage` block) after the release. So a fork of `sf_19` is even less tiebreak-aware than a fork of master.
- Even master only *reduces* time when behind, **within the current game**, and never spends more when ahead. It has no concept of a three-game match bank.

**Why it happens:**
The tiebreak is unusual and easy to miss; engine tuning assumes single-game score; time feels like a resource to spend, not a score to accumulate.

**How to avoid:**
- Make the **match time bank** an explicit input to the authored manager: `bank_ms = sum of final clocks in previous games − opponent's sum` (or the raw running sum).
- Define a per-game policy: game 1 baseline; games 2–3 adjust by bank delta and match score. If you are +3 min on the bank, you can spend for a win; if you are −3 min, you must conserve and win on the board.
- Add a **bank mode** that trades tiny expected-score losses for large time savings in stable/dead positions: instant-move in a forced draw or dead-equal position; avoid 60-second thinks when the eval has been flat for several moves; resign objectively lost games early to stop the clock (but never resign a drawable position — a half-point is worth more than time).
- Record both clock readings at the end of every game (photo + log trailer). A tiebreak you cannot document is a tiebreak you lose.
- Simulate 3-game matches in the offline pipeline and report **tiebreak win rate** as a first-class metric next to Elo.

**Warning signs:**
- The harness only measures single-game results.
- The log has no field for end-of-game clock readings.
- The team cannot state the current bank mid-match.
- The engine spends 60 s on a dead-equal move 15.
- The team plays on in a hopeless position "for practice."

**Phase to address:**
P3 (bank input) + P6 (match simulation).

---

#### C4. Sudden death and Armageddon with no increment

**What goes wrong:**
Armageddon is 5 minutes for White, 4 for Black, **draw classifies Black**; no increment is stated in Rule 12. Stockfish's formula is tuned for increment; with zero increment, the human overhead is uncompensated and one long think is unrecoverable. The team reuses the 15+10 config and has no color-specific policy: as Black a draw wins, so reckless play is irrational; as White only a win avoids losing.

**Why it happens:**
Armageddon is a rare format; teams assume the main time control covers it; no drill.

**How to avoid:**
- Add a `sudden_death` mode: hard reserve floor, per-move cap as a fraction of remaining (e.g., never exceed 15% before move 20), no assumption of future increment.
- Add an `armageddon` mode that knows the color and the draw rule. Black: solid, trade pieces, avoid risk, steer toward drawn endings within the 10-ply book; White: must win, can spend, choose a sharper plan.
- Confirm with the organizers whether Armageddon truly has no increment; the rule does not mention one. Do not assume.
- Drill a 5+0 and a 4+0 game with the real console and the real clock.
- Log `mode=armageddon color=black|white`.

**Warning signs:**
- No zero-increment test in the harness.
- The same time config is used for all games.
- No Armageddon drill.
- The engine uses 90 s on move 12 with 4 min left.

**Phase to address:**
P3 + P6.

---

#### C5. The internal timer drifts from the physical clock, and the execution tail is unmodeled

**What goes wrong:**
The console times `go → bestmove`, but the physical clock runs from the opponent's press to your press, including your entry of their move and your announce/confirm/move/press. Over a game the internal timer is minutes off. The operator trusts it and flags, or over-reserves and loses the tiebreak. At the end, the engine can return `bestmove` with 2 s left while the physical tail needs 6–10 s — flag before the press.

**Why it happens:**
Two clocks with different start/stop events; manual sync is easy to forget; developers model only the engine, not the protocol. The rule's sequence (announce → repeat → move piece → press → enter) puts the entire human tail on the mover's clock.

**How to avoid:**
- Model the physical clock explicitly: start on the opponent's clock press (or on hearing the move), stop on **your** press. Display both internal and last-synced physical time.
- A single `SYNC` key that sets the internal clock from the physical reading; log every sync. Sync at every capture, promotion, castling, time trouble, and at least every 10 moves.
- A `PRESSED` timestamp button; the log records it. Rehearse the ritual: move piece → press clock → then type your own move (typing your own move happens on the opponent's clock, so it is free for you).
- Announce thresholds out loud at 5:00, 2:00, 1:00, 0:30.
- Reserve the **execution tail** (announce + confirmation + piece move + press) separately from the input tail (entering the opponent's move); both are inside the manager's budget.
- Below ~30 s, use instant-move mode; below ~10 s, the only legal plan is to move immediately.

**Warning signs:**
- Drift greater than 10 s at any sync.
- The operator says "the clock says X" and the software says Y.
- No sync lines in the log.
- Any `bestmove` with less than 5 s left.
- The team never measured the tail.

**Phase to address:**
P4 + P6.

### Group D — Spoken protocol and board state (Rules 5, 10, 13)

#### D1. The operator announces a PV instead of `bestmove`

**What goes wrong:**
The console streams `info` lines, each with a PV whose first move changes between depths. Under pressure the operator reads the top line and announces it. The engine later returns a different `bestmove`; the announced move may be illegal or simply bad. If illegal, Rule 10 annuls it and the clock keeps running.

**Why it happens:**
The PV looks like the answer; the console displays it prominently; the operator is rushed; `bestmove` arrives after the PV, so there is always a window where the PV is the only thing on screen.

**How to avoid:**
- The UI has one unambiguous **ANNOUNCE** field, populated only by the `bestmove` line. It is visually distinct from the PV and cannot be confused with it.
- Lock the announce field until `bestmove`; a press-to-reveal step prevents reading a moving target.
- During a game, do not display the PV as a primary line; keep it in the log/analysis pane.
- Log the announced string and the `bestmove` string; a mismatch is a bug.
- Drill: 30 positions, operator announces only from the ANNOUNCE field while an assistant reads distracting PV lines.

**Warning signs:**
- The announced move differs from the log's `bestmove`.
- Multiple candidate moves are visible on screen during play.
- The log timestamp shows announcement before `bestmove`.

**Phase to address:**
P4.

---

#### D2. Spoken-notation ambiguity and a confirmation step nobody listens to

**What goes wrong:**
`e7e8q` is spoken as "e7e8" and the promotion suffix is lost; `g1f3` and `g8f6` sound alike; `b1c3` and `b8c6` differ by one digit; `e4` and `e5` are one syllable apart; letters and digits collide in Portuguese/English; someone says "cavalo de f3" or "e2-e4" instead of UCI. The opponent repeats a different move, nobody catches it, and the piece is moved on the wrong square. Illegal move annulled, clock running, or board/software divergence.

**Why it happens:**
UCI strings are not designed for speech; the rule explicitly bans algebraic notation because of this ambiguity; fatigue and venue noise make it worse.

**How to avoid:**
- A fixed phonetic read-back protocol: files as **Alpha, Bravo, Charlie, Delta, Echo, Foxtrot, Golf, Hotel**; digits spoken individually ("one," not "eleven"); promotion as "queen — Q," "rook — R," "bishop — B," "knight — N." Never "queen" alone without the letter.
- The console displays the exact UCI string including the promotion suffix and offers a **SPELL** mode that reads it out character by character.
- The announcing team **listens** to the repetition and says "correct" before moving the piece. Treat the repeat as a checksum, not a formality.
- Write the move on a shared scoresheet visible to both teams.
- Normalize case and hyphens in software (Stockfish's `to_move` lowercases input); accept `E7E8Q` but display lowercase.
- Drill 50 random legal moves with a partner in a noisy room; include promotions, en passant, castling, and near-miss squares.

**Warning signs:**
- Any annulled move in practice.
- "I thought he said…" at the board.
- A promotion announced without a suffix.
- A hyphenated or algebraic announcement.
- No phonetic drill.

**Phase to address:**
P4 + P6 drills.

---

#### D3. Illegal move annulled, clock running, no recovery plan

**What goes wrong:**
Rule 10: an illegal announced move is annulled and the team must announce a legal move **with the clock running**. Teams freeze, argue with the opponent, or re-announce the same illegal move; the clock drains. If the illegal move came from a divergent board, the next "legal" move is also wrong.

**Why it happens:**
No pre-agreed procedure; the engine's suggestion was based on a wrong internal position; panic; the instinct is to explain rather than move.

**How to avoid:**
- A **PANIC / ANNULLED** command in the console that: stops the search; validates the current physical position; proposes the best legal move at low depth (or the first legal move); displays the exact UCI string; and logs an incident record.
- A pre-agreed phrase ("illegal — we are choosing a new move") and a rule that nobody argues during the clock. Notify the arbiter after the move is made.
- If the cause is board/software divergence, run the resync flow first (D4); do not play a move validated against a wrong board.
- Drill: inject an illegal move in practice and measure time-to-legal-move. Target under 10 s.

**Warning signs:**
- No panic path in the console.
- No drill.
- The operator's first instinct is to talk.
- The replacement move is also illegal.

**Phase to address:**
P4 + P6.

---

#### D4. Board/software divergence is "fixed" by replaying moves from memory

**What goes wrong:**
The software state differs from the physical board: a missed en passant, a castling-rights error, a promotion piece mismatch, a move entered twice, or the opponent's move entered as yours. Rule 10 says the physical board is the source of truth. Teams try to patch the software by replaying from memory; the error propagates. Or they keep playing on the wrong internal position, so the engine's `bestmove` is illegal on the real board.

**Why it happens:**
Manual entry on both sides; no verification step; the console's board is not displayed; Rule 5 makes each team responsible for mirroring both sides, but nothing enforces it.

**How to avoid:**
- Display a large ASCII/Unicode board after every move, plus the FEN and the move list.
- A `VERIFY` command: type the FEN read off the physical board; the console diffs it against the internal position and shows the difference. A `RESYNC` flow: stop the engine → enter the FEN (including side to move, castling, en passant, halfmove clock, fullmove number) → validate legality → confirm → resume with `position fen <FEN>`.
- Resync loses repetition history (Stockfish's `Position::set` starts a fresh `StateInfo`; the 50-move count is only as good as the FEN's `rule50` field). For a normal game, prefer `position startpos moves <full list>`; after a resync, reconstruct the move list from the last verified point so repetition and the 50-move rule remain correct.
- Verify after every capture, promotion, castling, en passant, and at every clock sync. Use a two-person check at critical moments.
- Never auto-apply a predicted/ponder move to the committed board; keep prediction and commitment separate.
- Mirror the committed state to disk after every move so a console crash can be recovered.

**Warning signs:**
- The internal FEN differs from the board.
- The console rejects a move that was played on the board.
- "Where did that bishop come from?"
- The engine's `bestmove` is illegal on the physical board.
- The console does not display a board.

**Phase to address:**
P4 + P6.

---

#### D5. UCI state-machine races, blocking commands, and fatal engine exits

**What goes wrong:**
- The console sends `position`/`go` before draining the previous `bestmove`; it reads a stale `bestmove` and plays it.
- It sends `setoption` while the engine is pondering. Verified: `setoption` calls `wait_for_search_finished()`, and a ponder search never finishes on its own — the console hangs with the clock running.
- It sends `position ... moves <illegal>` or `go` with a malformed number. Verified: Stockfish calls `terminate_on_critical_error` and `std::exit(1)` — the engine dies mid-game.
- It treats `bestmove (none)` (mate/stalemate) or `bestmove 0000` (null move) as a real move and sends it to the board.
- It parses `info string ...` (NUMA/thread messages printed after `go`) as an analysis line.
- It ignores stderr; a full stderr pipe can block the engine.

**Why it happens:**
UCI is a text protocol with implicit state; the engine's error handling is fatal; console code is written ad hoc under deadline; happy-path testing.

**How to avoid:**
- A formal state machine: `IDLE → THINKING → PONDERING → STOPPING → IDLE`, with exactly one in-flight `go` and a generation counter attached to every command/response.
- Always `stop` and drain to `bestmove` before `setoption`, `ucinewgame`, or a new `position`.
- Validate every move with a legal move generator **and** against the physical board before sending `position`. The engine will not forgive a bad move; it exits.
- Handle `(none)` and `0000` explicitly; end the game or request a resync.
- Whitelist line types: `id`, `uciok`, `readyok`, `option`, `info` (with `depth`), `info string` (ignore), `bestmove` (parse the first move and the optional `ponder` move).
- Capture stderr to a file/thread; never leave a pipe undrained.
- Send `ucinewgame` + `isready` at the start of every game; never mid-game. Without it, `previousTimeReduction`, `bestPreviousScore`, `originalTimeAdjust`, and the TT leak across games.
- Unit-test with a fake engine and fault injection: kill -9, garbage line, slow response, `(none)`, illegal position.

**Warning signs:**
- `setoption` appears in the move loop.
- No drain after `stop`.
- "Illegal move" or `CRITICAL ERROR` in test logs.
- `(none)`/`0000` unhandled.
- No state-machine diagram.
- No stderr capture.

**Phase to address:**
P4.

---

### Group E — Book and tablebase (Rules 3, 4)

#### E1. The book silently keeps playing past 10 plies

**What goes wrong:**
A Polyglot lookup at every position will happily return moves beyond ply 10; the console or GUI keeps using the book, violating Rule 3. Off-by-one variants: counting 5 full moves instead of 10 half-moves; counting only our moves; starting the count after the opponent's first move; a book move at ply 10 vs ply 11; a GUI book with its own settings. The result is a rule violation that the log itself documents.

**Why it happens:**
The book is position-keyed and has no notion of the competition rule; the cap is a competition rule, not a chess rule; nobody tests the boundary.

**How to avoid:**
- A single authoritative **ply counter**, incremented exactly once per half-move from the start position.
- Gate lookup with `ply <= 10`: the 10th half-move may be a book move; the 11th must be a search move. Display `ply / book_remaining` in the console.
- Log `source=book|search` for every move.
- Unit test with a synthetic book that has a move at every ply, asserting no book move at ply 11. A self-play integration test asserts the first search move is at ply 11.
- If using a GUI, disable its book and let only the console's gated lookup play book moves.

**Warning signs:**
- A game where both sides are still in book at move 6+.
- The counter lives in the console but the engine/GUI also has a book.
- No `source` field in the log.
- No boundary test.

**Phase to address:**
P5 + P6 audit.

---

#### E2. Third-party book provenance, legality, and the authorship trap

**What goes wrong:**
A downloaded Polyglot book has no recorded origin or license; it is tuned for a different engine and its lines are inconsistent with yours; the file is corrupt and returns an illegal move; or the team claims it as authored, which Rule 3 explicitly denies ("Book de terceiros não conta como autoria").

**Why it happens:**
Books are easy to download and look like free strength; the 10-ply cap makes most of that depth irrelevant, so the marginal value is small.

**How to avoid:**
- Prefer a small self-generated book (authored tool, reproducible, capped at 10 plies). It can be mentioned as tooling, not as the Rule 2 component.
- If using a third-party book, record name/version/source/license/SHA-256 in `PROVENANCE.md`; validate every book move with a legal move generator at load time; test the first 10 plies against your engine.
- Never claim the book as authorship. Rule 3 is explicit.

**Warning signs:**
- Book file with no provenance.
- No legal validation.
- Book lines that lose material in testing.
- "We'll claim the book as our own" in the dossier.

**Phase to address:**
P5.

---

#### E3. Tablebase limit violation and probe traps

**What goes wrong:**
`SyzygyProbeLimit` defaults to **7**. If `SyzygyPath` contains 6- or 7-piece files, the engine will probe them — a Rule 4 violation, and the rule's rationale is explicit: 6/7-piece TBs would substitute the endgame logic being evaluated. Common path: the team downloads "all Syzygy" for analysis and forgets to segregate the game directory. Secondary traps: probing at depth 1 on a slow external drive causes latency spikes; `Syzygy50MoveRule` interacts with 50-move draws; TB scores are large `cp` values and must be logged correctly; TB use does not count as authorship.

**Why it happens:**
The default is 7; file presence is the only enforcement; teams mix analysis and game assets.

**How to avoid:**
- Two directories: `tb_game/` containing only 3-4-5-piece files, and `tb_analysis/` that never touches the game laptop.
- Set `SyzygyProbeLimit=5` as defense in depth; a startup self-test asserts `Tablebases::MaxCardinality <= 5` and logs it.
- Pre-game inventory: list every TB file, piece count, and SHA-256 in `PROVENANCE.md`.
- Put TB files on the internal SSD; tune `SyzygyProbeDepth` (default 1 probes at every node with ≤5 pieces); test 5-piece endgames under time pressure.
- Log `tbhits` per move. Do not claim TB as authored.

**Warning signs:**
- `SyzygyProbeLimit` is 7.
- 6/7-man files anywhere on the game laptop.
- `tbhits` in a position with 6+ pieces.
- No inventory.
- nps collapses in 5-piece endings.

**Phase to address:**
P5 + P7 preflight.

---

### Group F — The mandatory log (Rule 9)

#### F1. The log is missing required fields

**What goes wrong:**
Rule 9 requires, for each move: move number, color, chosen move in UCI, depth reached, nodes searched, position evaluation, principal variation (PV), and time spent. The most common omissions are **PV, nodes, and time spent**. Other failures: logging only our moves, not the opponent's; blank fields for book and terminal moves; a single eval number without `cp`/`mate`; a truncated PV; `depth` without `seldepth`; a `.csv` or `.jsonl` file (the rule says `.txt` or `.log`); engine search time without wall time (or vice versa).

**Why it happens:**
The console author picks fields ad hoc; Stockfish's `info` line has most but not all; book/terminal moves bypass the engine; "tempo gasto" is not a UCI field.

**How to avoid:**
- One line per **half-move**, including opponent moves. A schema with all eight required fields plus extras:
  `fullmove`, `ply`, `color`, `move_uci`, `depth`, `seldepth`, `nodes`, `score` (`cp`/`mate` + bound), `pv` (full), `engine_ms`, `wall_ms`, `source` (`search|book|ponder|instant|terminal`), `tbhits`, `tm` attestation, `clock_ms`, `bank_ms`, `incident`.
- For opponent moves, log the ponder/analysis snapshot with `source=ponder` (it has depth/nodes/eval/PV/time), or `source=none` explicitly. Do not leave blanks.
- For book moves: `source=book`, `depth=0`, `nodes=0`, `pv=<move>`, `engine_ms=0`. For mate/stalemate: `source=terminal`, `move_uci=(none)`.
- Log the raw UCI score (side-to-move perspective) **and** a White-perspective conversion, labeled. A sign flip in the log looks like an error to a judge.
- Write `.log` (or `.txt`), not `.csv`; a CSV can be an extra artifact, not the required one.
- Run a `log_lint` script against the schema after every game.

**Warning signs:**
- Empty PV on any line.
- No `nodes` field.
- No opponent moves in the log.
- No lines for book or terminal moves.
- `time 0` everywhere.
- A `.csv` is the only artifact.

**Phase to address:**
P4 (writer) + P6 (lint).

---

#### F2. The log is produced after the game or after the event

**What goes wrong:**
Rule 9 says the log is delivered to the panel **at the end of each game**. Teams plan to export at the end of the event, or after the match, or reconstruct from the PGN. A retroactive log lacks real depth/nodes/PV/time and cannot be trusted; if the laptop crashes, everything is lost. Fabricating the missing fields is worse than omitting them.

**Why it happens:**
"We'll do it later" under game pressure; no export workflow; the log file is buried in `/tmp`.

**How to avoid:**
- Append-only writer with `flush` + `fsync` after each line.
- One file per game: `YYYY-MM-DD_roundX_gameY_<color>_vs_<opponent>.log`.
- A header with date, opponents, colors, base commit, engine version, the full UCI option set, and SHA-256 of net/book/TB files.
- Auto-export at game end to a USB drive and print a paper copy; a human checklist step before leaving the table.
- Never edit the log after the fact. If a correction is needed, append a timestamped correction block; do not rewrite history.
- A trailer with final clock readings (both sides), the computed bank, and a SHA-256 of the log.
- Mirror to a second file/device in real time.

**Warning signs:**
- No export step in the runbook.
- Log files in `/tmp` or a temp directory.
- No `fsync`.
- "We'll generate it from the PGN."
- No USB drive.
- The log is edited after the game.

**Phase to address:**
P4 + P7.

### Group G — Game-day operations (Rules 8, 14)

#### G1. The network is on, or comes back on

**What goes wrong:**
Rule 14 requires Wi-Fi and mobile data off, verified by the arbiter **at the start of each game**. The realistic failure is not the team deliberately going online; it is a background service re-enabling the radio mid-game: Windows Update, a driver updater, Steam, OneDrive, a saved SSID auto-connecting, phone hotspot auto-join, Bluetooth tethering. Or a browser/LLM/API tool left running. The arbiter checks only at the start, so a mid-game re-enable may go unnoticed — and is still a violation.

**Why it happens:**
The check is treated as a one-time ritual; OS services are not disabled; the team tests with network on and never exercises the offline path.

**How to avoid:**
- Hard radio kill: `rfkill block all` (Linux) / airplane mode (Windows/macOS), plus disable auto-connect for every saved network.
- Disable or uninstall updaters and cloud sync for the game session; use a dedicated user account with a minimal startup.
- Run the console in a network namespace (`unshare -n`) or add a startup assertion that no socket is opened; log `network=off` at game start.
- Pre-flight script: assert no default route, no Wi-Fi radio, no listening sockets; print a signed checklist.
- Re-check at the start of **every** game, not just the first.
- Grep the console and pipeline for `requests`, `urllib`, `curl`, `wget`, API keys; remove them from the game path.

**Warning signs:**
- `nmcli radio` shows Wi-Fi enabled.
- A saved SSID auto-connects.
- Update notifications during testing.
- HTTP calls anywhere in the console.
- The arbiter's check is the only network check.

**Phase to address:**
P7 + P6 dry run.

---

#### G2. Dependencies or the GPU are not installed/declared before the event

**What goes wrong:**
`python-chess` missing or the wrong version; a C++ runtime/library missing; the Syzygy path wrong; a GPU tool used but not declared (Rule 8), or declared but CUDA/driver not installed; `pip install` attempted at the venue with no network; a monolithic `requirements.txt` that includes heavy ML packages the game laptop does not have. Rule 14 requires dependencies to be declared (`requirements.txt`, `package.json`, or equivalent).

**Why it happens:**
The dev laptop is not the venue laptop; the environment drifted; the pipeline and the game share one requirements file; nobody tested a fresh install offline.

**How to avoid:**
- Freeze the game environment (`pip freeze`, lockfile) and vendor wheels; install into a fresh VM/user account and test with `unshare -n`.
- Split `requirements-game.txt` (minimal: python-chess, stdlib) from `requirements-dev.txt` (pipeline/ML). Declare both at the repo root.
- A `doctor` command that checks every dependency, the TB path and piece counts, the book, the net, UCI options, and prints a green/red report. Run it before every game.
- Declare the GPU in the accreditation form and `PROVENANCE.md`. If the GPU is only for offline training, keep it out of the game path (power/thermal risk). If it is used in-game, verify the driver and test the exact model.
- Use the same laptop for all drills as for the event; do not discover a hardware difference on game day.

**Warning signs:**
- `pip install` appears in the runbook.
- No lockfile.
- GPU code in the game path.
- No `doctor`.
- The venue laptop differs from the dev laptop.

**Phase to address:**
P7 + P2.

---

#### G3. Thermal throttling and power collapse during a 15-minute think

**What goes wrong:**
The laptop is benchmarked cold. During a 15-minute think on all cores it downclocks (or thermal-shuts); nps drops 20–40%; the time manager's assumptions (fixed nps, fixed depth per second) break. On battery, the power limit drops further; a closed lid, a cloth table, or a soft surface makes it worse; an oversized `Hash` causes swap.

**Why it happens:**
Benchmarks are short; the game is long; nobody runs a sustained-load test; the laptop is treated as a desktop.

**How to avoid:**
- A 30–60 minute sustained-load stress test (e.g., a loop of `stockfish bench` or a long self-play game) recording nps and temperature over time.
- Performance power profile, plugged in, hard surface, cooling pad, clean fans; consider undervolting/repasting if the hardware allows.
- Cap `Threads` at a sustainable count (often physical cores, not SMT); more threads can lose nps to heat and contention.
- `Hash` ≤ ~50% of RAM, with margin; verify no swap. Stockfish exits with `Failed to allocate … for transposition table` if the allocation fails (`tt.cpp`), so an oversized Hash is a mid-game crash, not a slowdown.
- Disable sleep, screensaver, notifications, and updates for the session.
- Measure **sustained** nps and use it in the time manager's calibration; log nps each move and alert on a drop.

**Warning signs:**
- nps at minute 15 is much lower than at minute 1.
- Fan at maximum; package temperature near the throttle limit.
- Battery below 100% or on battery power.
- `Hash` above ~50% of RAM.
- The laptop is on a bed, cloth, or soft table.

**Phase to address:**
P2 (baseline) + P7 (preflight).

---

#### G4. Engine or console crash mid-game with no recovery path

**What goes wrong:**
The engine exits (illegal `position`, `Hash` allocation failure, OS update, stack issue) or the console crashes. There is no supervisor; the operator stares at a dead terminal while the clock runs. The game is lost. A crash at move 10 is recoverable in 5 seconds with the right tooling and fatal without it.

**Why it happens:**
Happy-path development; crashes are rare in testing but catastrophic on game day; state lives only in memory.

**How to avoid:**
- A supervisor loop that detects process death, restarts the engine, and replays `position fen <last verified>` (or `position startpos moves <list>`) + `go` with the remaining budget.
- A **panic move**: if recovery cannot complete within a deadline (e.g., 10 s), play a legal move immediately (first legal move or the last known best move), press the clock, then continue recovery.
- Persist the committed position, move list, clock, and bank to disk after every move; the console can restart from that state.
- Run the console and the engine as separate processes; use process groups so an orphaned engine is killed.
- Keep a second device (phone/tablet/paper) with the scoresheet and PGN.
- Drill `kill -9` at random points in a scripted game; measure recovery time. Target under 10 s.

**Warning signs:**
- No restart logic.
- No persisted state.
- Recovery never tested.
- `Hash` near or above RAM.
- A single process for console + engine.

**Phase to address:**
P4 + P6.

---

#### G5. Three people, one laptop, no roles or runbook

**What goes wrong:**
Everyone talks, no one presses the clock, the log is not exported, the network check is skipped, and the operator and the coach disagree about the move — all on the clock. Coordination overhead is real time.

**Why it happens:**
The team is three friends, not a pit crew; roles feel bureaucratic; drills are solo.

**How to avoid:**
- Assign roles for every game:
  - **Operator:** types, announces, moves the piece, presses the clock.
  - **Timekeeper/Adjudicator:** clock sync, bank tracking, resignation policy, rules/arbiter communication.
  - **Coach/Analyst:** opponent prep, post-game log mining, authorship/arguição lead.
- Rotate roles in drills so everyone can cover.
- A one-page runbook with four sections: pre-game, per-move, per-game, emergency. A checklist that is physically ticked.
- A handoff phrase for the operator ("my move") and a rule that only the operator speaks to the opponent.
- Rehearse the full loop with a practice opponent, including a clock and a noisy room.

**Warning signs:**
- No role assignment.
- The runbook is in someone's head.
- Drills are solo.
- The team argues during a game.
- The clock is pressed by whoever remembers.

**Phase to address:**
P7 + P6 drills.

---

### Group H — Strategy and preparation

#### H1. Optimizing Elo when the field is all Stockfish forks

**What goes wrong:**
Two weeks go into evaluation/search tuning for a few Elo, while every opponent is also an SF fork. The match is decided by forfeits, protocol incidents, the tiebreak, book/TB compliance, and operations. Tuning under fixed `movetime` does not transfer to 15+10 with human latency.

**Why it happens:**
Elo is the obvious metric; tuning feels like "real" engine work; compliance and drills feel like bureaucracy.

**How to avoid:**
- Define winning metrics beyond Elo: **zero time forfeits, zero protocol incidents, 100% log compliance, positive time bank, tiebreak win rate, crash recovery time**.
- Treat Elo as a constraint ("do not regress") rather than the objective.
- Measure strength only under the real time control + latency model; use SPRT at 15+10 with simulated overhead.
- Allocate roadmap time explicitly to compliance, console, and drills; do not let tuning consume the buffer.
- Prepare for the likely match shape: near-equal engines → many draws → the tiebreak decides. That is the edge the project's Core Value already identifies.

**Warning signs:**
- The roadmap is all tuning.
- No drill time.
- No forfeit/incident metric.
- Benchmarks use `go movetime 1000` or fixed nodes.
- The team cannot state its tiebreak plan.

**Phase to address:**
Roadmap-level + P6.

---

#### H2. Ignoring ponder and the input-latency window

**What goes wrong:**
Not pondering leaves free strength on the table. Rule 13 explicitly says the move arrives verbally and the team must handle the input delay — the team that searches during the announcement/entry window gains seconds per move. Conversely, naive pondering creates the clock/thermal/state risks in C2.

**Why it happens:**
Ponder is seen as an optimization, not a protocol feature; the console has no `PONDERING` state; the team does not measure hit rate.

**How to avoid:**
- Start pondering immediately after your `bestmove`, before the opponent announces.
- On hearing the move: if it matches the ponder move, `ponderhit`; otherwise `stop`, drain, `position`, `go` with the real budget.
- Use the ponder window to pre-validate the predicted move against the physical board.
- Measure hit rate and entry latency; a low hit rate means the prediction is bad or the opponent is unpredictable — still useful, but cap the thermal cost.
- Cap ponder by depth/nodes; log `source=ponder`, hit/miss, and time pondered.

**Warning signs:**
- No ponder in the console.
- Ponder implemented but hit rate unmeasured.
- The engine idles during the opponent's 30-second think.
- Ponder runs all cores for minutes with no cap.

**Phase to address:**
P3 + P4 + P6.

---

#### H3. No preparation for the exact opponent pool, colors, or schedule

**What goes wrong:**
No knowledge of the field (all SF forks? a Leela? a weak engine?), no color plan, no opening plan within the 10-ply cap, no tiebreak/Armageddon scenario. Rule 11: the team on the left plays White in game 1; colors alternate; game 3 repeats game 1's color. So if you are White in game 1, you are White in game 3. A team that has not internalized this prepares the wrong color.

**Why it happens:**
The schedule and pairings feel out of the team's control; opening prep is capped at 10 plies, so it feels pointless; no scouting.

**How to avoid:**
- Scout the field from public information and previous editions; classify opponents (SF fork, weaker engine, human-assisted).
- Prepare 2–3 short opening plans per color, all within 10 plies and all legal under the book cap; prepare a "must win" and a "must draw" plan.
- Simulate the schedule: 3 games, colors, bank, possible Armageddon.
- Prepare for a much weaker opponent (do not burn clock) and a much stronger one (bank time, play solid, aim for the tiebreak).
- Rehearse the arguição as part of preparation, not after.

**Warning signs:**
- No opponent notes.
- One opening for both colors.
- No color-specific plan.
- No schedule simulation.
- Nobody knows the Rule 11 color sequence.

**Phase to address:**
P6.

---

#### H4. Testing under the wrong conditions

**What goes wrong:**
SPRT with fixed nodes or 10+0.1, no human latency, no ponder, no console in the loop. Results do not transfer; a change that wins at fixed nodes loses on time. The harness never produces a forfeit, so the team never sees the failure mode that will decide the match.

**Why it happens:**
Fixed-node tests are fast and low-variance; the console is hard to automate; the team optimizes for iteration speed.

**How to avoid:**
- An offline harness that drives the **real console + engine over UCI**, with a simulated operator that has a latency distribution and a typo/illegal-move rate.
- Enforce the physical clock model (press-to-press), ponder, and the 10-ply book cap.
- Run 3-game matches with the tiebreak and report forfeits, incidents, and bank alongside Elo.
- SPRT at 15+10 with the latency model; fixed-node tests only for engine-strength smoke tests.
- Fault injection: engine kill, network re-enable attempt, malformed move, `(none)`, board divergence.

**Warning signs:**
- The harness bypasses the console.
- No latency simulation.
- No forfeit counter.
- Tests use `movetime` or fixed nodes.
- The console is only tested manually.

**Phase to address:**
P6.

---

#### H5. The arguição is treated as a formality

**What goes wrong:**
The code is ready but the argument is not. The judge asks: "What exactly is yours?", "Why isn't this parameter tweaking?", "Show me it running," "What happens if you revert it?", "Who wrote this function?" The team fumbles, or one member answers everything and the other two cannot explain the algorithm.

**Why it happens:**
The team focuses on the tournament; the arguição feels like a formality; nobody rehearses a hostile review.

**How to avoid:**
- A hostile rehearsal with someone outside the team, using the questions above.
- A 3-minute demo: switch `TimeManager=upstream|custom` on a scripted position/clock; show the different budget; show a real log line with the attestation; show the ablation table. No network in the demo.
- A one-page printed handout: claim, Rule 2 mapping, algorithm diagram, ablation table, evidence index.
- All three members can explain the algorithm, the evidence, and the diff. The judge may ask the least-involved person.
- Prepare the **revert test** explicitly: same position, same clock, upstream vs custom, explain why the decisions differ.
- Know the exact diff vs the base commit; be able to point to file:line.

**Warning signs:**
- No rehearsal.
- No handout.
- Only one member can explain the component.
- The demo requires network or a notebook that is not charged.
- The team cannot answer "what did you copy?"

**Phase to address:**
P7.

---

## The Authorship Dossier — the artifact that actually persuades a judge

A judge has limited time and a checklist: *Is it authored? Is it functional in games? Can they defend it?* A 50-page document loses; a 2-page claim plus a 60-second live demo wins. Build this artifact **during** development. The only order that matters: `00-DESIGN.md` before code, evidence as you go, defense last.

### File tree

```
AUTHORSHIP.md                          # 2-page claim, repo root
PROVENANCE.md                          # base project, commit, net/book/TB inventory, licenses
DECLARATIONS/accreditation-copy.md     # exact copy of what was submitted (base + commit + GPU)
docs/timeman/
  00-DESIGN.md                         # dated BEFORE implementation
  01-ALGORITHM.md                      # pseudocode, invariants, failure modes, complexity
  02-EVIDENCE.md                       # ablation, SPRT, 3-game matches, forfeits, bank
  03-DEFENSE.md                        # 3-minute script + 15 anticipated questions
  04-DECISIONS.md                      # dated decision log (why X, why not Y)
experiments/timeman-ablation/
  run.sh                               # one command reproduces the table
  configs/                             # upstream vs custom, latency models, TCs
  results/                             # raw output, not just the summary
scripts/check_license.sh
scripts/log_lint.py
scripts/doctor.py
```

### What goes in `AUTHORSHIP.md`

1. **Claim (one sentence).** "We replaced Stockfish's `TimeManagement::init` with a match-aware, latency-constrained budget allocator that decides how much time to spend on each move and when to instant-move; it runs in every game and is switchable for ablation."
2. **Rule 2 mapping table.**

| Rule 2 requirement | Evidence |
|---|---|
| Authored by the team | `docs/timeman/00-DESIGN.md` committed before code; per-author git history; `04-DECISIONS.md` |
| A decisive component | The allocator sets `optimumTime` / `maximumTime` / instant-move decisions in `src/timeman.cpp`; `TimeManager=custom` is the game default |
| Functional during matches | The engine emits a `tm=custom-vX.Y ... budget_ms=... reason=...` attestation at the start of every search; the console records it in every game log; startup self-test |
| Defensible in the technical argument | `03-DEFENSE.md`; live switch demo; `02-EVIDENCE.md` ablation; all three members rehearsed |

3. **What is new.** New inputs (match bank, measured latency p50/p95, opponent clock, game index, Armageddon color/draw rule), new state (bank, latency model, reserve), new control law (reserve-constrained budget over expected remaining moves), new outputs (budget + instant-move flag + reason code).
4. **What is inherited.** A table of file:line for every upstream function/constant still used. Naming what you did *not* write is what makes the claim credible.
5. **Explicit non-claims.** "Not claimed: evaluation, search, book, tablebase. The book is self-generated tooling; tablebases are standard 3-4-5 Syzygy files."
6. **60-second verification recipe.** Exact commands: `git log base-sf19..HEAD -- src/timeman.cpp`, the `setoption name TimeManager value upstream|custom` switch, a scripted `go wtime ... btime ... winc ... binc ...`, and `tail -1` of a real game log. A judge should be able to falsify the claim without reading the whole repo.
7. **Evidence index.** One line per artifact, with the claim it supports.

### The experiments that persuade

`02-EVIDENCE.md` should contain, at minimum:

- **Ablation A/B:** same binary, `TimeManager=upstream` vs `custom`, SPRT at 15+10 with a simulated human latency (p50 8 s, p95 14 s). Report Elo, W/L/D, **time forfeits**, average remaining clock, and tiebreak wins.
- **3-game match simulation:** the actual Rule 12 format, sum of final clocks, including 1–1–1 and 0–0–0 paths. Report tiebreak win rate.
- **Stress scenarios:** 10 s left, 30 s left, sudden death 5+0/4+0, Armageddon as White and Black, opponent with 5 min vs 20 s.
- **Revert test:** a scripted position/clock where upstream and custom choose different budgets and different *kinds* of decisions; the explanation of why.
- **Real game logs:** at least one full game with the attestation line, showing the custom manager active on every move.

### What does **not** persuade

- A design doc written after the code.
- A 500-line diff that is mostly comments translated to Portuguese.
- "We tested it and it felt better."
- A claim that the book or tablebase is authored (Rules 3/4 explicitly deny this).
- A demo that requires network, a missing dongle, or a laptop that is not charged.
- One person answering every question.

---

## Technical Debt Patterns

Shortcuts that look reasonable in week 1 and cost the match in week 2.

| Shortcut | Immediate benefit | Long-term cost | When acceptable |
|---|---|---|---|
| Console sends a fixed `go movetime` | Works in an hour; no engine change | Bypasses the authored manager; no latency/tiebreak; flags or under-uses; authorship claim collapses | Never in the game path; only as a P2 smoke test |
| Reuse one engine process across games without `ucinewgame` | Saves a second of startup | `previousTimeReduction`, `bestPreviousScore`, `originalTimeAdjust`, and TT leak; first-move misallocation | Never |
| Log only the fields Stockfish's `info` already prints | Fast | No wall time, no opponent moves, no book/terminal lines; non-compliant | Never |
| Single-file Python console with no state machine | Fast | Stale `bestmove`, `setoption` deadlock, fatal `position`; unfixable under deadline | Only for a throwaway prototype |
| Manual board only, no FEN/resync | No UI work | Divergence unrecoverable; Rule 10 says the board wins; loss | Never |
| Rely on `Move Overhead` for human latency | One option | Max 5000 ms; multiplied by the horizon; still flags in simulation | Never as the only mechanism |
| Third-party Polyglot book as "prep" | Free strength | 10-ply cap makes it marginal; provenance/license/authorship risk | Acceptable as a documented fallback, not as authored |
| Fixed-node or `movetime` testing | Fast, low variance | Doesn't transfer to 15+10 + latency; hides forfeits | Engine-strength smoke tests only |
| `position fen` before every move | Simple, avoids replaying illegal history | Loses repetition history; the 50-move count is only as good as the FEN | Only for resync, then reconstruct the move list |
| One monolithic `requirements.txt` | One file | Game laptop doesn't need ML deps; offline install fails | Never; split game/dev |

---

## Integration Gotchas

| Integration | Common mistake | Correct approach |
|---|---|---|
| UCI stdout | Parsing every line as `info`; treating `info string` as analysis | Whitelist line types; ignore `info string`; parse `bestmove <move> [ponder <move>]` |
| `position` | Sending an unvalidated move list | Validate with a legal generator **and** the physical board; an illegal move makes Stockfish `exit(1)` |
| `setoption` | Sending it during a ponder/search | It calls `wait_for_search_finished()`; a ponder never finishes → console hangs. `stop` + drain first |
| `ucinewgame` | Forgetting it between games | Send at game start + `isready`; otherwise cross-game state leaks |
| `Ponder` | Setting it `true` globally | Adds 25% to `optimumTime` on every normal move; manage it explicitly |
| `UCI_Chess960` | Stale `true` from testing | Castling becomes `e1h1`; the spoken protocol breaks. Set `false` explicitly |
| `MultiPV`, `Skill Level`, `UCI_LimitStrength` | Stale test values | Weaker/slower engine; set **every** option explicitly at game start and log the full option set |
| `SyzygyProbeLimit` | Default 7 | Rule 4 violation; set 5 and segregate directories |
| Build | `make` downloads the NNUE net | Offline build fails; vendor the net, test `unshare -n make` |
| stderr | Not draining the pipe | The engine can block on a full pipe; redirect to a file/thread |
| Process | `kill` without `quit` | Orphaned engine; log not flushed; send `quit`, wait, then kill the process group |
| python-chess | `SimpleEngine.play(ponder=True)` not handled | Lost ponder or wrong move; handle `PonderResult` or write an explicit UCI loop |
| Book | Polyglot hash/format mismatch | Book silently unused or wrong; validate known positions at load |
| Tablebases | Path on an external drive | First-probe latency; internal SSD, tune `SyzygyProbeDepth` |
| Log | Console and engine write to the same file | Interleaved/corrupt log; separate files, console is the only writer of the required log |

---

## Performance Traps

| Trap | Symptoms | Prevention | When it breaks |
|---|---|---|---|
| Thermal throttle | nps drops 20–40% after 5–15 min; fan max; temps at limit | 30–60 min stress test; performance profile; cooling; cap threads | Long thinks, games 2–3 |
| `Hash` > RAM | Swap; `Failed to allocate … for transposition table` and exit | `Hash` ≤ ~50% RAM; test; monitor | Startup or first deep search |
| Oversubscribed threads | Flat or negative nps; heat | Tune on sustained load; physical cores | 15-minute think |
| Ponder + game engine on all cores | Both slow; heat | One engine; pin/limit; no second engine | Every opponent think |
| TB probe at depth 1 on a slow disk | nps collapse in 5-piece endings | Internal SSD; raise `SyzygyProbeDepth`; preload | Endgames |
| Background SPRT/analysis during a game | CPU steal; heat | Kill all test processes pre-game; checklist | Game day |
| Battery / soft surface | Power limit; blocked vents | Plug in; hard surface; cooling pad | Any game |
| Log `fsync` every line | Tiny stall (acceptable) | Keep it; measure | Never a problem at this scale |

---

## Compliance & Security Mistakes

Domain-specific, not generic web security.

| Mistake | Risk | Prevention |
|---|---|---|
| Wi-Fi re-enabled by updater/auto-connect | Rule 14 violation; DQ | `rfkill`, airplane mode, disable auto-connect/updaters, `unshare -n`, signed checklist |
| Undeclared GPU | Rule 8 violation | Declare it; or keep GPU out of the game path; document in `PROVENANCE.md` |
| Undeclared or missing dependencies | Rule 14; cannot run | Lockfile, vendored wheels, `doctor`, offline install test |
| License headers stripped | GPLv3 breach; Rule 1 failure | `check_license.sh`, keep `Copying.txt`/`AUTHORS`, modification notices |
| Vague base commit | Rule 1; unreproducible | Pin SHA, tag, `PROVENANCE.md`, update the accreditation form |
| Net/book/TB provenance missing | Rules 15/3/4; authorship doubt | SHA-256 + source + license + inventory |
| Private repo / no archive | Rule 1 | Publish early; USB archive; clean-clone offline build test |
| Log edited after the game | Credibility; non-compliance | Append-only, `fsync`, timestamps, hash, correction blocks |
| 6/7-piece TB on the game laptop | Rule 4 | Segregate; limit 5; startup assert; inventory |
| A second engine/analysis running during a game | CPU/thermal; perception of external help | Ban it; kill processes; checklist |

---

## Operator UX Pitfalls

The console is a cockpit. Every extra second or ambiguity is on your clock.

| Pitfall | User impact | Better approach |
|---|---|---|
| PV shown as actionable | Wrong/illegal announcement | One ANNOUNCE field populated only by `bestmove` |
| No board display | Divergence unnoticed | Large board + FEN + move list, updated every move |
| No panic/instant key | Flag in time trouble | One key: stop search, play current best legal move, show UCI string |
| No sync key | Timer drift | `SYNC` + `PRESSED` timestamps; show internal vs physical clock |
| Mouse-driven entry | Slow; entry is on your clock | Keyboard-only, single line, history, aliases, auto-complete |
| No phonetic spelling | Ambiguity | Alpha–Hotel files, digit-by-digit, promotion letter, SPELL mode |
| No confirmation gate | Illegal move | Repeat-back + explicit "correct" before moving the piece |
| No incident markers | Log gaps | `ANNULLED`, `RESYNC`, `SYNC`, `PANIC`, `BOOK_OFF` commands, all logged |
| Notifications/popups | Focus steal; delay | Do Not Disturb; dedicated session; close apps |
| Bluetooth peripherals | Drop mid-game | Wired keyboard/mouse |

---

## "Looks Done But Isn't" Checklist

Run these before you believe any of it is finished.

- [ ] **Authored time manager:** `TimeManager=custom` is the default in the game config; a startup self-test fails if it is not active; every log line carries the `tm=...` attestation; `TimeManager=upstream` is only for ablation.
- [ ] **Revert test:** on a scripted position/clock, upstream and custom choose different budgets and different *kinds* of decisions; you can explain why in one sentence.
- [ ] **Base commit:** `base-sf19` tag exists; the SHA is in `PROVENANCE.md` **and** in the accreditation form; `git log` contains upstream history.
- [ ] **License:** every tracked `src/**/*.cpp|*.h` has a GPL header; `Copying.txt` and `AUTHORS` are present; modified files have a dated modification notice; the console has a license notice.
- [ ] **Repository availability:** a clean clone on a fresh machine builds with `unshare -n make -j`; a USB archive contains source + license + provenance + build instructions + checksums; no LFS pointers.
- [ ] **Network asset:** the exact `.nnue` is vendored; SHA-256 and origin are documented; the build does not download anything.
- [ ] **Book:** single ply counter; no book move at ply 11; `source=book|search` logged; a synthetic-book test proves the boundary; third-party provenance recorded or a self-generated book used.
- [ ] **Tablebase:** `tb_game/` contains only 3-4-5-piece files; `SyzygyProbeLimit=5`; startup asserts `MaxCardinality <= 5`; inventory with SHA-256.
- [ ] **Log schema:** all eight required fields for **every half-move**, including opponent moves; book/terminal moves have explicit lines; full PV; `cp`/`mate` + bound; `depth` + `seldepth`; `engine_ms` + `wall_ms`.
- [ ] **Log delivery:** append + `fsync`; one file per game with metadata header; auto-export at game end to USB + paper; trailer with final clocks and a hash; `log_lint` passes.
- [ ] **Protocol:** legal-move gate before every `position`; board displayed every move; `RESYNC` from a physical FEN; `PANIC` plays a legal move in <10 s; phonetic drill done; confirmation listened to.
- [ ] **UCI state machine:** one in-flight `go`; drain to `bestmove`; `setoption`/`ucinewgame` only when idle; `(none)`/`0000` handled; `info string` ignored; stderr captured; supervisor + panic move.
- [ ] **Clock:** measured p50/p95 human overhead; execution reserve; instant-move below ~30 s; `SYNC` at thresholds; no drift >10 s in a full drill game.
- [ ] **Tiebreak:** bank is an input; final clocks are recorded; 3-game match simulation reports tiebreak win rate; resignation policy written.
- [ ] **Armageddon:** 5+0 and 4+0 modes tested; color-specific policy written; increment confirmed with the organizers.
- [ ] **Network:** `rfkill`/airplane mode; auto-connect disabled; updaters disabled; `unshare -n` or socket assertion; signed pre-flight checklist; re-check every game.
- [ ] **Dependencies/GPU:** game and dev requirements split; lockfile; fresh offline install passes; `doctor` green; GPU declared or out of the game path.
- [ ] **Thermal:** 60-minute sustained-load run; sustained nps recorded; performance profile; plugged in; cooling; `Hash` ≤ ~50% RAM.
- [ ] **Roles/runbook:** Operator/Timekeeper/Coach assigned; one-page runbook; full-loop drill with a practice opponent; emergency procedures rehearsed.
- [ ] **Arguição:** 3-minute demo works offline; one-page handout printed; all three members can explain the algorithm and the evidence; hostile rehearsal done.

---

## Recovery Strategies

When prevention fails, these are the only paths that do not lose the game twice.

| Pitfall | Recovery cost | Recovery steps |
|---|---|---|
| Flag imminent (<15 s) | LOW if a panic key exists | `PANIC` → stop search → play current best legal move (or first legal) → press clock → log `source=instant` → sync → continue |
| Illegal move annulled | LOW–MEDIUM | `ANNULLED` command → keep the position → if divergence, resync first → re-announce the corrected UCI string → press → log incident → notify the arbiter after the move |
| Board/software divergence | MEDIUM | Stop → read the board into a FEN → validate legality/side/castling/ep/halfmove → show the diff → confirm → resume with `position fen` → reconstruct the move list if repetition matters → log |
| Engine crash | MEDIUM | Supervisor restarts → `position fen <last verified>` → `go` with the remaining budget; if >10 s, panic move first → log the gap |
| Console crash | MEDIUM–HIGH | Restart from the persisted state → check whether the engine is still alive → reattach or kill the process group → reconstruct the last position → log the gap |
| Network discovered on | HIGH (violation) | Turn it off immediately → call the arbiter → document the time and cause → fix before the next game; assume the worst |
| Book overrun discovered | HIGH (violation) | Disable the book immediately → switch to search → document → notify the arbiter; fix the counter before the next game |
| 6/7-piece TB discovered | HIGH (violation) | Remove the files → set `SyzygyProbeLimit=5` → restart the engine → document → notify the arbiter; inventory the laptop |
| Log lost/corrupt | HIGH | Recover from the mirror/USB → if impossible, produce a signed reconstruction from the PGN + engine replay and disclose it; never fabricate timings |
| Thermal throttle | MEDIUM | Plug in → performance profile → reduce threads → cooling → resume; log nps and the throttle event |
| Opponent slow to confirm | LOW | Announce → brief pause → move and press; do not stall; if repeated, call the arbiter |
| Armageddon draw as Black | WIN | Verify the rule with the arbiter; claim the draw; log the final clocks and the bank |

---

## Pitfall-to-Phase Mapping

| Phase | Pitfalls prevented | Verification |
|---|---|---|
| **P1 — Compliance & Provenance** | A1 (scaffold), A3, B1, B2, B3, B4, G2 (declaration) | `check_license.sh` green; `PROVENANCE.md` has SHA + inventory; clean-clone offline build; accreditation copy filed |
| **P2 — Engine Baseline** | B2, B4, G3 | Pinned tag; vendored net; sustained-load nps curve; `Hash` fits RAM; offline build |
| **P3 — Authored Time Manager** | A1, A2, C1, C2, C3, C4, H2 | Design doc before code; `TimeManager` switch; ablation at 15+10 + latency; 3-game/tiebreak sims; Armageddon modes |
| **P4 — Operator Console** | C5, D1, D2, D3, D4, D5, F1, G4 | State-machine tests; fault injection; `kill -9` recovery <10 s; board resync drill; `log_lint` green |
| **P5 — Book & Tablebase** | E1, E2, E3 | Synthetic-book boundary test; TB startup assert; inventory; provenance |
| **P6 — Test Pipeline & Prep** | C3, C4, D2, D3, F1, F2, G3, G4, G5, H1, H2, H3, H4 | Full-loop harness with latency/typos/ponder/clock; 3-game matches; protocol drills; opponent/color plans |
| **P7 — Game Day & Arguição** | B3, G1, G2, G3, G5, H5 | Pre-flight checklist signed; network-off proof; `doctor` green; thermal run; 3-minute demo + handout; all three rehearsed |

---

## Top 5 If You Only Fix Five Things

1. **Make the time manager execution-tail-aware (C1, C5).** Stockfish's default 10 ms `Move Overhead` is three orders of magnitude too small for a human-mediated protocol. The simulation flags around move 10 at 15+10 with a 12-second human loop, and `Move Overhead=5000` only delays it. This is both the biggest game-loss risk and the authored component — fix it first.
2. **Build the authorship dossier while you build the component (A1, A3).** A design doc committed before the code, a live `upstream|custom` switch, an ablation table, and per-author history are the difference between a trophy and a DQ. Retroactive evidence does not persuade.
3. **Make the physical board the single source of truth with a resync and a panic path (D3, D4).** Rule 10 resolves divergence in favor of the board. Without a FEN resync and a panic move, one typo costs the game.
4. **Log every half-move with all eight fields and deliver it after each game (F1, F2).** The log is both the Rule 9 deliverable and your authorship/tiebreak evidence. Append-only, `fsync`, exported at the table.
5. **Run the game-day pre-flight: network off, dependencies frozen, thermal stress, roles assigned (G1, G2, G3, G5).** These failures are cheap to prevent and impossible to recover from.

If there is a sixth: **guard the book and tablebase boundaries (E1, E3).** They are silent violations that turn wins into losses after the fact.

---

## Evidence & Confidence

| Claim | Evidence | Confidence |
|---|---|---|
| All rule requirements and exclusions | `docs/competition-rules.md` (verbatim FAQ, rules 1–15) | HIGH |
| `Move Overhead` default 10, max 5000; `Ponder` +25%; `maximumTime` formula | Stockfish `sf_19`/master `src/timeman.cpp`, `src/engine.cpp` | HIGH |
| `position` with an illegal move exits the process; `setoption` blocks during search | `src/uci.cpp`, `src/engine.cpp` | HIGH |
| `ponderhit` does not reset `startTime` | `src/uci.cpp`, `src/search.cpp`, `src/engine.cpp` (no other `startTime` assignment) | HIGH |
| `ucinewgame` resets `originalTimeAdjust`/`previousTimeReduction`; skipping it leaks state | `src/thread.cpp` `ThreadPool::clear` | HIGH |
| FEN set loses repetition history; `rule50` comes only from the FEN | `src/position.cpp` `Position::set` starts a fresh `StateInfo` | HIGH |
| `SyzygyProbeLimit` default 7; `Hash` allocation failure exits | `src/engine.cpp`, `src/tt.cpp`, `src/syzygy/tbprobe.cpp` | HIGH |
| Build downloads the NNUE net; default net name | `src/Makefile` `net` target, `src/evaluate.h`, `src/universal/nnue_embed.cpp` | HIGH |
| GPLv3 obligations (notices, source, modification marking) | `Copying.txt`, GPLv3 §§4–6, Stockfish `README.md` | HIGH |
| Simulation flag points (move ~10 at 15+10 with 12 s overhead) | Model of `optimumTime` allocation; not a real-game measurement | MEDIUM |
| Judge rejects "mere parameter tweaking" | Rule 2 wording + inference about arguição behavior | MEDIUM |
| Thermal nps drop of 20–40% | General laptop behavior; not measured on this hardware | MEDIUM |
| Field composition / opponent strength | No data on the actual III Chess Challenge field | LOW |

---

## Sources

- `docs/competition-rules.md` — III Chess Challenge FAQ, verbatim; rules 1–15 (authoritative for this project).
- Stockfish release `sf_19`, tag commit `f879373d916914de3a478aabb4226e6460c17d15` (published 2026-09-05): `src/timeman.cpp`, `src/timeman.h`, `src/engine.cpp`, `src/uci.cpp`, `src/search.cpp`, `src/thread.cpp`, `src/tt.cpp`, `src/position.cpp`, `src/syzygy/tbprobe.cpp`, `src/Makefile`, `src/evaluate.h`, `src/universal/nnue_embed.cpp`.
- Stockfish `master` at `ff3a6c508ed731f0dcf253f4ddf646df19a62f84` (2026-10-25): used to confirm the post-`sf_19` `timeAdvantage` addition in `timeman.cpp` and the current embedded-net build path.
- GNU General Public License v3, `Copying.txt` (Stockfish distribution): §§4, 5, 6.
- Stockfish `README.md`, license section: requirement to include the license and the full source (or a pointer) for the exact binary.
- `python-chess` metadata: `license="GPL-3.0+"` (relevant to console licensing and Rule 14's allowance for local chess libraries).
- Simulation model: derived from the `timeman.cpp` formula quoted in C1 (each move spends `optimumTime`; increment added after the move; human overhead charged twice per ply). Reproducible in ~30 lines; not a real-game measurement.

---

*Pitfalls research for: III Chess Challenge — Stockfish fork, spoken-UCI console, 15+10, best of 3*
*Researched: 2026-10-26*
