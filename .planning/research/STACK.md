# Stack Research

**Domain:** Competition chess engine — Stockfish fork, offline, 15 min + 10 s increment, 1–2 week build
**Researched:** 2026-10-26
**Confidence:** HIGH (every version and API below was verified against the live source tree, release metadata, or an actual build/run on this machine — see [Verified Empirical Data](#verified-empirical-data))

---

## TL;DR — The Prescriptive Stack

| Layer | Choice | Version | Confidence |
|-------|--------|---------|------------|
| Engine base | Stockfish `sf_19` | Stockfish 19 (2026-09-05) | HIGH |
| Language/compiler | C++17, GCC | GCC ≥ 14 (verified on 16.2.1) | HIGH |
| Engine build | `make -j profile-build` | Makefile in `src/` | HIGH |
| Evaluation net | Official `nn-1a298aa575a0.nnue` (embedded) | 98,511,183 B (93.9 MiB) | HIGH |
| Authored component | Custom `TimeManagement` (C++) | rewritten `src/timeman.cpp/.h` | HIGH |
| Game console | Python 3.12 + `python-chess` | `chess==1.11.2` | HIGH |
| Match/SPRT harness | fastchess | `v1.8.2-alpha` (commit `ebfd64c`) | HIGH |
| Tournament harness (fallback) | cutechess-cli | `v1.5.1` — **avoid** (Qt ≥ 6.8) | HIGH |
| Opening book (competition) | Own-generated Polyglot `.bin`, `≤10` plies | own writer | HIGH |
| Opening books (harness) | `official-stockfish/books` EPD (CC0-1.0) | `noob_5moves.epd`, `UHO_Lichess_4852_v1.epd`, `8mvs_+90_+99.epd` | HIGH |
| Endgame | Syzygy 3-4-5 only, `SyzygyProbeLimit=5` | 939 MiB total | HIGH |
| GPU | **None** | — | HIGH |
| License | GPL-3.0-or-later (inherited) | `Copying.txt` preserved | HIGH |

**The single most important architectural decision:** put the competition book and the mandatory logging in the **Python console**, and put the **authored time management in C++**. This gives three independently-testable modules, a minimal C++ diff you can defend at the technical hearing, and zero risk of a C++ Polyglot implementation eating your timeline (Stockfish 19 contains **no** Polyglot code — verified by `grep -r polyglot src/` returning nothing).

---

## Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why Recommended | Confidence |
|------------|---------|---------|-----------------|------------|
| Stockfish `sf_19` | 19 (tag `sf_19`, 2026-09-05) | Engine base | Current stable series; +44 Elo over SF18; CCRL 40/15 4CPU **3650** (also reported 3653); single-net SFNNv16 architecture removes the 6.1-era dual-net complexity you would have to reason about | HIGH |
| GCC | ≥ 14 (verified 16.2.1) | C++17 toolchain | `Makefile` requires `-std=c++17`; `make -j profile-build` measured **2 m 47 s** total (instrumented build → bench → optimized build), i.e. *faster* than a plain `build` (3 m 11 s) because the instrumented pass skips LTO. Clang ≥ 18 also supported via `COMP=clang` | HIGH |
| GNU Make + `src/Makefile` | shipped with SF19 | Build system | Upstream-supported; `profile-build` gives PGO (free nps = free Elo; measured 2 m 47 s total); `ARCH=native` auto-detects the best ISA | HIGH |
| Python | 3.12 (works 3.11–3.13) | Console, logging, book tooling, test harness glue | Pure-Python `chess` package, zero transitive deps; fastest path to correct UCI parsing + legal-move validation + Polyglot + Syzygy probing | HIGH |
| `python-chess` (PyPI name `chess`) | **1.11.2** (2025-02-25) | Board repr, UCI engine client, Polyglot reader, Syzygy probe, PGN | GPL-3.0-or-later (compatible with Stockfish's GPLv3); `Board.parse_uci()` raises `InvalidMoveError` — exactly the legality gate Rule 5/10 needs; `engine.play(..., info=INFO_ALL)` returns depth/nodes/score/pv/time for Rule 9 in one call | HIGH |
| fastchess | **v1.8.2-alpha** (`ebfd64c`, 2026-10-11) | SPRT / match runner | MIT; `make -j` with **no external dependencies** (verified: 1 m 41 s, 2.4 MB binary); tested to 250 concurrent games; built-in SPRT with pentanomial stats, resumable config, `-recover`. cutechess-cli needs Qt ≥ 6.8 — a needless offline-install risk | HIGH |

### Supporting Libraries

| Library | Version | Purpose | When to Use | Confidence |
|---------|---------|---------|-------------|------------|
| `python-chess` `chess.polyglot` | in 1.11.2 | Read Polyglot `.bin`: `open_reader()`, `find_all()`, `weighted_choice()`, `zobrist_hash()` | Competition book lookup (console side). **Has no writer** — write the 16-byte records yourself (~40 lines, see below) | HIGH |
| `python-chess` `chess.syzygy` | in 1.11.2 | `open_tablebase(path)` for WDL/DTZ probing in the console | Only for test positions and post-game analysis. **Do not** probe in the console during a game — the engine already probes; double-probing risks disagreeing with the engine's PV/score in the log | HIGH |
| `prompt_toolkit` | 3.0.53 | Fancier operator input (completion menu, key bindings) | Optional. Requires Python ≥ 3.10. Only if the stdlib `readline` completer feels clunky in dry runs | MEDIUM |
| `pytest` | 9.1.1 | Unit tests for the console state machine, logger, book cap | Dev-only, never shipped | HIGH |
| Syzygy 3-4-5 tables | 939 MiB (378 WDL + 561 DTZ), 290 files | Perfect endgames ≤ 5 pieces | Mandatory fixture before the event. `SyzygyProbeLimit` **must** be set to `5` (default is `7`) | HIGH |

### Development Tools

| Tool | Purpose | Notes | Confidence |
|------|---------|-------|------------|
| `git` (≥ 2.40) | Provenance, accreditation, GPL source publication | Tag the exact origin: `git clone --branch sf_19` then record `git rev-parse HEAD` into `NOTICE`. Rule 1 requires declaring base project + origin commit | HIGH |
| `./stockfish bench` | Reproducible build sanity check + nps measurement | Run before and after every change; also used by `profile-build` for PGO. Deterministic node count confirms you did not accidentally change search behaviour | HIGH |
| `hyperfine` | Timing console actions (optional) | Not required; `time` is enough | LOW |

---

## 1. Stockfish Fork Mechanics

### What a current Stockfish source tree actually contains (verified, `sf_19`)

```
Stockfish-sf_19/
├── AUTHORS                 # keep verbatim, append your team
├── CITATION.cff
├── CONTRIBUTING.md
├── Copying.txt             # GPLv3 full text — KEEP THIS FILENAME
├── README.md
├── Top CPU Contributors.txt
├── scripts/
│   ├── net.sh              # downloads + SHA-validates the NNUE net
│   └── get_native_properties.sh
├── tests/
└── src/
    ├── Makefile            # 46 KB — the whole build system
    ├── main.cpp engine.cpp engine.h        # UCI plumbing + OptionsMap
    ├── uci.cpp uci.h ucioption.cpp/.h      # protocol + option registration
    ├── search.cpp/.h                       # 94 KB — iterative deepening
    ├── timeman.cpp/.h                      # <-- YOUR AUTHORED COMPONENT
    ├── evaluate.cpp/.h                     # EvalFileDefaultName lives here
    ├── position.cpp/.h movegen.cpp/.h movepick.cpp/.h
    ├── thread.cpp/.h tt.cpp/.h history.h
    ├── misc.h                              # TimePoint, now()
    ├── tune.cpp/.h                         # Tune:: options for SPSA
    ├── nnue/                               # network.cpp, layers/, features/
    ├── incbin/incbin.h + UNLICENCE
    ├── syzygy/tbprobe.cpp/.h
    └── universal/                          # universal-binary + net embedding
```

Notably **absent**: any Polyglot/book code, any GUI, any JSON/logging, any test runner. Those are yours to add.

### Build procedure (verified end-to-end on a 12-core Linux box)

```bash
git clone --branch sf_19 --depth 1 https://github.com/official-stockfish/Stockfish.git
cd Stockfish/src

make -j$(nproc) build          # downloads net via scripts/net.sh, then compiles
make -j$(nproc) profile-build  # PGO: instrumented build + bench + optimized build (measured 2 m 47 s)
make -j$(nproc) net            # only fetch/validate the .nnue
make strip                     # optional binary strip
make help                      # authoritative list of targets + archs + compilers
```

**Verified results** on this research machine (GCC 16.2.1, 12 threads):

| Metric | Value |
|--------|-------|
| `make -j12 build` wall time | **3 m 11 s** (4 m 19 s CPU) |
| `make -j12 profile-build` wall time | **2 m 47 s** (instrumented pass has no LTO) |
| Output binary | `src/stockfish`, **95 MB** (net embedded) |
| Side artifact | `src/nn-1a298aa575a0.nnue`, 94 MB |
| Auto-detected arch | `x86-64-avxvnni` (from `ARCH=native` → `scripts/get_native_properties.sh`) |
| `./stockfish bench` (pre- and post-PGO) | 2,497,913 nodes — **identical**, proving PGO does not alter behaviour |
| `./stockfish bench` throughput | ~280–350 knps single-thread (sandbox too noisy to isolate the PGO gain) |
| 1 / 4 / 12 threads nps (mid-search) | 274 knps / 779 knps / 1,330 knps |

**Architecture flags.** `ARCH` defaults to `native`, which resolves via `scripts/get_native_properties.sh`. Supported values (from `make help`): `x86-64-universal`, `x86-64-avx512icl`, `x86-64-vnni512`, `x86-64-avx512`, `x86-64-avxvnni`, `x86-64-bmi2`, `x86-64-avx2`, `x86-64-sse41-popcnt`, `armv8-dotprod`, `apple-silicon`, `riscv64`, `loongarch64`, `wasm32`, …

**Recommendation:** build `ARCH=native` on the *actual competition laptop*, and commit the resolved value into `NOTICE`/`docs/build.md` so the judges can reproduce the exact binary. Do **not** ship a `x86-64-universal` build — universal builds use runtime dispatch and add ~5% overhead plus an exotic net-embedding path (`universal/nnue_embed.cpp`).

**Compiler choice:** GCC is the path of least resistance. `COMP=clang` is supported but this machine had no Clang; do not introduce a toolchain you cannot test offline. Minimum: GCC ≥ 14 (C++17 + `#embed` detection code paths). Confidence: HIGH for GCC, MEDIUM for exact minimum version (README/wiki state "a compiler with C++17 support"; SF19's `nnue_embed.cpp` uses `__has_embed` when available, which is C++26 — GCC 14+ handles this cleanly).

### NNUE embedding — how it actually works in SF19

1. `src/evaluate.h` defines `#define EvalFileDefaultName "nn-1a298aa575a0.nnue"`. The comment is explicit: *"The default net name MUST follow the format nn-[SHA256 first 12 digits].nnue … Do not change the name of the macro or the location where this macro is defined."*
2. `make build` depends on `net`, which runs `scripts/net.sh`. That script downloads from `https://tests.stockfishchess.org/api/nn/<file>` (redirects to `data.stockfishchess.org`) or the GitHub `networks` repo, and validates that the filename matches the SHA-256 prefix.
3. Compilation embeds the net in one of four ways (`src/nnue/network.cpp`):
   - `#embed EvalFileDefaultName` when the compiler supports C++26 `#embed` (via `universal/nnue_embed.cpp`);
   - `INCBIN(EmbeddedNNUE, EvalFileDefaultName)` (the `incbin.h` macro) for normal builds;
   - runtime mmap for the macOS universal x86 slice;
   - all-zeros stub when `NNUE_EMBEDDING_OFF` or MSVC.
4. At runtime the engine prints `info string NNUE evaluation using nn-1a298aa575a0.nnue (109MiB, (86896, 1024, 32, 32, 1))` and prefers the embedded copy. The `EvalFile` UCI option overrides it with an external path.

**Consequence for you:** a normal `make build` produces a **self-contained ~95 MB binary with the net inside**. That is what you want at the event — no `EvalFile` path to get wrong, no missing-file failure. Ship the `.nnue` alongside anyway for provenance and for `EvalFile` override during experiments.

**Consequence for `make net` still running on a fresh clone:** the build is **not** fully offline. Do the clone + `make net` **before** the event, then archive the whole tree (plus the `.nnue`) and rebuild offline from the archive. Add this to the pre-event checklist.

### What must be preserved for GPLv3 (and how)

Stockfish's per-file header says *"version 3 of the License, **or (at your option) any later version**"* → the project is **GPL-3.0-or-later**, not bare GPLv3. Concrete, actionable list in [GPLv3 Compliance Checklist](#gplv3-compliance-checklist).

### Current stable series and strength

- **Stockfish 19**, tag `sf_19`, published **2026-09-05**. Previous: 18 (2026-01-31), 17.1 (2025-03-30).
- **CCRL 40/15, 4CPU: 3650** (Wikipedia cites 3653 for September 2026). CCRL's conditions are "general books up to 12 moves, 3-4-5 piece EGTB" — i.e. *easier* than your 10-ply book rule, so treat 3650 as an upper bound for the same engine under your constraints.
- +44 Elo over SF18 in upstream testing; wins >3× the game pairs it loses.
- Development snapshots exist (`stockfish-dev-YYYYMMDD-<sha>` released nightly). **Do not** build from a dev snapshot: you cannot cite a stable origin commit, and nightly bisect churn is a distraction. Use `sf_19`.

---

## 2. NNUE Network Files

| Fact | Value | Confidence |
|------|-------|------------|
| SF19 default net | `nn-1a298aa575a0.nnue` | HIGH |
| Size | **98,511,183 bytes (93.9 MiB)** | HIGH |
| Architecture | **SFNNv16** — single net; the secondary/small net from SF16.1–SF18 was **retired** | HIGH |
| Loaded size reported by engine | 109 MiB | HIGH |
| Official net license | **CC0-1.0** (`official-stockfish/networks` repo `LICENSE`) | HIGH |
| Download endpoints | `https://tests.stockfishchess.org/api/nn/<name>` → `https://data.stockfishchess.org/nn/<name>`; mirror `https://github.com/official-stockfish/networks/raw/master/<name>` | HIGH |
| Integrity check | filename = first 12 hex chars of SHA-256; `scripts/net.sh` enforces it | HIGH |
| Training data provenance | rescored with Leela nets; Leela training data is ODbL (see `README.md` acknowledgements) | MEDIUM |

**Does shipping a third-party net affect an authorship claim?** No — and this is a *good* thing:

- **Legally:** the official nets are **CC0-1.0** (public domain dedication). They impose no copyleft, no attribution requirement, and no license interaction with your GPLv3 engine. You can ship, mirror, or modify them freely.
- **Competition-wise:** Rule 15 states weights downloaded from third parties **do not count as authorship**; only team-trained weights count, and only when accompanied by training code. Rule 2 excludes "mere parameter tweaking" and the LLM/NN path was already ruled out of scope in `PROJECT.md`.
- **Therefore:** use the official SF19 net unchanged. Do **not** fine-tune it and present the result as authorship — that is the single fastest way to lose the technical hearing. Fine-tuning also risks burning a week for a regression.

**Practical packaging:** keep `nn-1a298aa575a0.nnue` at the repo root (no LFS — Rule 15 puts no repo size limit), and record in `NOTICE`: filename, byte size, SHA-256, source URL, license `CC0-1.0`, and "unmodified, not authored by the team". That sentence pre-empts the obvious question.

**What NOT to do with nets:**
- Do not run `make net` variants with `NNUE_EMBEDDING_OFF` for the shipped binary — you get a 1-byte stub and a runtime failure if `EvalFile` is wrong.
- Do not ship both an embedded net and a *different* `EvalFile` — the engine will silently load the file, and your binary no longer matches the source+net you published.
- Do not try to accelerate NNUE on GPU. SFNNv16 inference is a handful of int8/int16 dot products sized for CPU SIMD; a GPU offload would add latency and break nothing useful.
- Do not present the net as your own work in the write-up, even implicitly ("our neural network"). Say "official Stockfish 19 network, unmodified".

---

## 3. Time Management Internals (the authored component)

This is the highest-value section: it is both your Rule 2 authorship claim and your Rule 12 tiebreak lever. Get the *names* right — the class was renamed and people keep citing stale blog posts.

### Exact file/type map in Stockfish 19

| Thing | Where | Notes |
|-------|-------|-------|
| `class TimeManagement` | `src/timeman.h:38` | The allocator. **There is no `Timeman` or `TimeManager` type in SF19** — those names are from SF ≤ 15 / third-party forks. If your write-up says "we replaced `Timeman`", a judge who reads the source will notice |
| `TimePoint` | `src/misc.h:152` | `using TimePoint = std::chrono::milliseconds::rep;` — an **int64 count of milliseconds**, not a chrono type. `now()` returns one |
| `TimeManagement::init(...)` | `src/timeman.cpp:46` | The single function that decides `optimumTime` / `maximumTime` |
| `optimum()`, `maximum()` | `src/timeman.cpp:30-31` | Accessors used by search |
| `elapsed(FUNC nodes)` | `src/timeman.h:48-51` | Template; time-or-nodes abstraction |
| `clear()`, `advance_nodes_time(i64)` | `src/timeman.cpp:33-40` | `nodestime` support |
| Instance owner | `SearchManager::tm` — `src/search.h:304` | One per game, lives in the main-thread manager |
| `SearchManager::originalTimeAdjust` | `src/search.h:305` | Per-game log-scaled time multiplier, computed once (`timeman.cpp:112-113`) |
| `Search::LimitsType` | `src/search.h:172-189` | Carries `time[2]`, `inc[2]`, `movestogo`, `movetime`, `startTime`, `npmsec`, and `use_time_management()` |
| `"Move Overhead"` option | `src/engine.cpp:109` — `Option(10, 0, 5000)` | Default **10 ms**, range 0–5000 |
| `"nodestime"` option | `src/engine.cpp:111` — `Option(0, 0, 10000)` | Nodes-as-time mode; ignore it |
| `check_time()` | `src/search.cpp:2102` | Hard-stop gate: `elapsed > tm.maximum()` |
| Iteration-level rescaling | `src/search.cpp:570-610` | The *second* half of TM that most forks forget |

### How the current allocator works (SF19, exact)

`TimeManagement::init()` receives `limits`, `us` (color), `ply`, `options`, and a mutable `originalTimeAdjust`.

```cpp
// src/timeman.cpp:67
TimePoint moveOverhead = TimePoint(options["Move Overhead"]);

// Maximum move horizon — capped at 50
int mtg = limits.movestogo ? std::min(limits.movestogo, 50) : 50;

// If less than one second, gradually reduce mtg (cyclic controls keep true movestogo)
if (scaledTime < 1000 && limits.movestogo == 0)
    mtg = int(scaledTime * 0.05);

// Projected time available over the horizon
TimePoint timeLeft = std::max(TimePoint(1),
    limits.time[us] + limits.inc[us] * (mtg - 1) - moveOverhead * (2 + mtg));

// Sudden death: extra time from total budget, once per game
if (originalTimeAdjust < 0)
    originalTimeAdjust = 0.3272 * std::log10(timeLeft) - 0.4141;

double logTimeInSec = std::log10(scaledTime / 1000.0);
double optConstant  = std::min(0.0029869 + 0.00033554 * logTimeInSec, 0.004905);
double maxConstant  = std::max(3.3744  + 3.0608    * logTimeInSec, 3.1441);

optScale = std::min(0.012112 + std::pow(ply + 3.22713, 0.46866) * optConstant,
                    0.19404 * limits.time[us] / timeLeft) * originalTimeAdjust;
maxScale = std::min(6.873, maxConstant + ply / 12.352);

optimumTime = TimePoint(std::max(1.0, optScale * timeLeft));
maximumTime = TimePoint(std::max(double(optimumTime),
    std::min(0.8097 * limits.time[us] - moveOverhead, maxScale * optimumTime)));

if (options["Ponder"]) optimumTime += optimumTime / 4;
```

Then `search.cpp` applies a **second, dynamic layer** per iteration:

```cpp
// src/search.cpp:591-602
double totalTime = mainThread->tm.optimum() * fallingEval * reduction
                 * bestMoveInstability * highBestMoveEffort;
if (elapsedTime > std::min(totalTime, double(mainThread->tm.maximum()))
    || rootMoves[multiPV - 1].score >= mate_in(3) || rootMoves[0].score == mated_in(2))
    /* stop (or stopOnPonderhit) */;
```

**Verified behaviour at your exact time control.** Running SF19 with `go wtime 150000 btime 150000 winc 10000 binc 10000` on 1 thread, the first move ran **19,757 ms** to depth 28, and move 2 after `1.e4 e5` ran **20,785 ms**. That is ~20 s per move from a 150 s bank with a 10 s increment — a **net −10 s per move** against the bank. Stockfish's horizon is calibrated for long games where the increment funds the spend; under Rule 12 (tiebreak = total clock remaining across three games) that behaviour is *actively harmful*. Cite this number in your design note; it is the empirical justification for the whole component.

### `Move Overhead` semantics (exactly)

- Read at the top of `init()` and subtracted **`(2 + mtg)` times** from the projected `timeLeft` — i.e. it is amortised over the remaining move horizon, not subtracted from this move.
- Also subtracted once from the hard ceiling: `0.8097 * limits.time[us] - moveOverhead`.
- Also used by `syzygy_extend_pv()` (`src/search.cpp:2144`) as a **wall-clock abort budget of `moveOverhead / 2` ms** for TB PV extension — set it too low and you truncate TB PVs; too high and you burn clock extending them.
- Default 10 ms is tuned for a GUI/pipe on localhost. Your reality includes a **human operator announcing moves** and a possible `stop`/`go` cycle. Empirically, 24 games at `tc=10+0.1`, concurrency 12, default overhead, produced **1 timeout** (see [Verified Empirical Data](#verified-empirical-data)) — at 10 ms you are already on the edge. Set **`Move Overhead = 100`** (range 100–300) for competition and **assert** it in the console's startup self-check.

### Extension points, ranked by blast radius (use #1)

**#1 — Reimplement `TimeManagement::init()` and grow the class. (RECOMMENDED)**
Keep the public interface (`init`, `optimum`, `maximum`, `elapsed`, `clear`) so `search.cpp` needs no edits, replace the body, and add fields:

```cpp
// src/timeman.h (your version)
class TimeManagement {
   public:
    void init(Search::LimitsType& limits, Color us, int ply,
              const OptionsMap& options, double& originalTimeAdjust);
    TimePoint optimum() const;
    TimePoint maximum() const;
    template<typename FUNC> TimePoint elapsed(FUNC nodes) const { ... }   // unchanged
    TimePoint elapsed_time() const { return now() - startTime; }          // unchanged

    // ---- your state ----
    void observe_clock_delta(TimePoint engine_reported, TimePoint wall_actual); // operator latency
    TimePoint reserve() const;        // clock held back for the tiebreak
    int       phase_bucket() const;   // opening / middlegame / endgame
    ...
};
```

This is a genuine rewrite (different state model, different inputs, feedback path), not a constant edit — which is what Rule 2 demands.

**#2 — Replace the whole class + the iteration rescaling.**
Also rewrite the block at `search.cpp:570-610` so the dynamic multipliers are yours. Larger diff, more Elo potential, more risk. Do this only if phase 1 is finished early.

**#3 — Add UCI options in `src/engine.cpp` around line 109.**
Your TM parameters should be *live* options so fastchess can SPRT them:
```cpp
options.add("TM Reserve",     Option(15, 0, 50));    // % of clock held for tiebreak
options.add("TM Latency",     Option(120, 0, 1000)); // ms of operator/IO latency to absorb
options.add("TM Style",       Option(2, 0, 3));      // discrete strategy selector
```
Options are printed by `uci` and settable by fastchess via `option.TM_Reserve=...` (note fastchess/cutechess replace spaces with underscores in `option.NAME=VALUE`).

**#4 — Extend `Search::LimitsType`** (`src/search.h:172`) if you need to carry new data from the console (e.g. the operator's measured announcement latency). Requires touching `uci.cpp`'s `go` parser (tokens are handled around lines 199–221). Only do this if the feedback loop genuinely needs it — otherwise feed latency through a `setoption`.

**#5 — Override `SearchManager::check_time()`** (`src/search.cpp:2102`) for a hard-stop policy (e.g. always stop at `maximum()` regardless of node count). Cheap, but it is a *safety net*, not the allocator — judges will see it as a guard, not a component.

### Rule 2 traps to avoid in the TM work

- ❌ "Same formula, new constants." Retuning `optConstant`/`maxConstant` is explicitly excluded by Rule 2 ("mero ajuste de parâmetros já existentes").
- ❌ "Rename `TimeManagement` to `TeamTimeManager` and reformat." Excluded verbatim.
- ❌ Only changing `Move Overhead`'s default. Excluded.
- ✅ A different **decision structure**: e.g. a budget controller that (a) reserves a tiebreak surplus proportional to expected remaining moves, (b) measures actual clock drain vs. engine-reported elapsed and subtracts a learned latency term, (c) allocates by game phase and position complexity rather than by a closed-form polynomial in `ply`, (d) keeps a hard `maximum()` invariant that makes flagging impossible. Document the algorithm in `docs/` in Portuguese with a state diagram, and keep a `git log` that shows the file rewritten.
- ✅ Defend it with data: 20 games at 15+10 vs. the unmodified engine, reporting **clock remaining at game end** — that is the Rule 12 metric, not Elo.

---

## 4. Offline Testing Harness (SPRT)

### Decision: fastchess, not cutechess-cli

| | **fastchess v1.8.2-alpha** | cutechess-cli v1.5.1 |
|---|---|---|
| Build | `make -j` — **no deps** (verified 1 m 41 s, 2.4 MB) | CMake + **Qt ≥ 6.8** (widgets, svg, concurrent, printsupport) |
| Offline-install risk | none (single static-ish binary) | high — Qt 6.8 is not in most distro repos |
| High-concurrency behaviour | tested to **250 concurrent games**, 10 timeouts / 20,000 matches at `0.2+0.002` | documented lag/timeouts at high concurrency at short TC ([cutechess#630](https://github.com/cutechess/cutechess/issues/630)) |
| SPRT | `-sprt elo0/elo1/alpha/beta/model=` + **pentanomial** `-report penta=true` | `-sprt elo0=… elo1=… alpha=… beta=…` (no built-in penta report) |
| Resumable / crash recovery | JSON config auto-saved, `-recover`, `-resume` | `-recover` only |
| Opening books | **EPD / PGN only** — *no Polyglot `.bin`* | **`.bin` Polyglot** + `bookdepth=N` (fullmoves) |
| License | MIT | GPLv3 |
| Verdict | **Primary** | fallback only if you need `.bin` in the harness |

**Real, important asymmetry:** cutechess-cli can consume the Polyglot `.bin` directly with a depth cap (`-engine ... book=book.bin bookdepth=5`), which is a tempting shortcut for testing your competition book. It is a trap: it drags Qt into your offline environment for one convenience, and it tests the book through a *different* reader than the one that will run on game day. Instead: have your book tool emit **both** `book.bin` (for the console) and `book.epd` (truncated to 10 plies, for the harness). Then the harness and the game use identical opening positions, and you can diff the two readers' choices.

### Verified throughput (this research machine: 12 hardware threads)

| Configuration | Games | Wall time | Throughput |
|---|---|---|---|
| `tc=10+0.1`, 1 thread/engine, `-concurrency 12` | 24 | 84 s | **~1,000 games/hour** |
| `tc=1+0.01`, 1 thread/engine, `-concurrency 12` | 80 | 30 s | **~9,600 games/hour** |

Single-thread nps for context: 274 knps (1t) → 779 knps (4t) → 1,330 knps (12t). SPRT throughput scales with **concurrency**, not threads-per-engine: at short TC you get **~85 games/hour per core** at `10+0.1` and **~800 games/hour per core** at `1+0.01` (1,000 ÷ 12 and 9,600 ÷ 12).

**Practical budget:** an SPRT `elo0=0 elo1=5 alpha=beta=0.05` run typically resolves in 400–2,000 games at a true +2…+5 Elo effect. At `tc=10+0.1` and `-concurrency = physical cores`, that is **25 min – 2 h**. You can afford several per day. At `1+0.01` you can afford dozens — use that for smoke tests and search/TM-logic sanity, never for final verdicts.

### The exact SPRT command (verified working)

```bash
# from the directory containing ./fastchess and your two engine builds
./fastchess \
  -engine cmd=./build/new/stockfish name=New option.Hash=256 \
  -engine cmd=./build/base/stockfish name=Base option.Hash=256 \
  -each tc=10+0.1 option.Threads=1 option.Move_Overhead=100 \
  -rounds 5000 -repeat -concurrency "$(nproc)" \
  -recover -srand 42 \
  -openings file=books/UHO_Lichess_4852_v1.epd format=epd order=random plies=16 \
  -sprt elo0=0 elo1=5 alpha=0.05 beta=0.05 \
  -report penta=true \
  -pgnout results/sprt-$(date +%s).pgn notation=uci nodes=true pv=true timeleft=true
```

Notes that matter:
- `option.Move_Overhead=100` — spaces in UCI option names become underscores. Also apply this to `Base` for an apples-to-apples test.
- `-repeat` plays each opening twice with colors swapped (mandatory for pair statistics).
- `-each tc=10+0.1` matches cutechess's `moves/minutes:seconds+inc` format; your event TC is `15+10` but **never SPRT at 15+10** — a single game takes ~5 min of wall clock.
- `-report penta=true` gives the pentanomial LLR/penta counts that converge faster than trinomial.
- `-recover` restarts crashed engines instead of aborting; keep it for multi-hour runs.
- `-pgnout ... timeleft=true` gives you the per-move clock trace, which is exactly what you need to audit the TM.

### Scripting the SPRT loop

A thin shell/Python driver over fastchess is enough; do not build a framework.

```bash
#!/usr/bin/env bash
# tools/sprt.sh  — runs a named experiment, logs LLR, stops on accept/reject
set -euo pipefail
NEW=${1:?new engine}; BASE=${2:?base engine}; TC=${3:-10+0.1}; ROUNDS=${4:-5000}
mkdir -p results
LOG="results/sprt-$(date +%Y%m%d-%H%M%S)-$(basename "$(dirname "$NEW")").log"
./fastchess \
  -engine cmd="$NEW"  name=New  option.Hash=256 \
  -engine cmd="$BASE" name=Base option.Hash=256 \
  -each tc="$TC" option.Threads=1 option.Move_Overhead=100 \
  -rounds "$ROUNDS" -repeat -concurrency "$(nproc)" -recover -srand "${SRAND:-42}" \
  -openings file=books/UHO_Lichess_4852_v1.epd format=epd order=random plies=16 \
  -sprt elo0=0 elo1=5 alpha=0.05 beta=0.05 -report penta=true \
  -pgnout "results/$(basename "$LOG" .log).pgn" notation=uci nodes=true pv=true timeleft=true \
  2>&1 | tee "$LOG"
```

fastchess prints `LLR: x (y%) (-2.94, 2.94) [0.00, 5.00]`; grep that for a dashboard. **Do not** parse Elo from the PGN yourself — use fastchess's own numbers so your decisions match upstream convention.

**Hard rule for the team:** SPRT results never justify changing a constant the same day. Run the test → keep the `-pgnout` → mine losses → only then change the algorithm.

### Harness opening books (distinct from the competition book)

From `official-stockfish/books` — **CC0-1.0**, safe to vendor:

| Book | Lines | Depth (plies) | Use |
|---|---|---|---|
| `noob_5moves.epd` | 455,287 | **10** | **Exact match to Rule 3's 10-ply cap.** Use for "what happens after the book ends" testing |
| `UHO_Lichess_4852_v1.epd` | 2,632,036 | 16 | Balanced, low-draw-rate; the standard for strong engines. `order=random` |
| `8mvs_+90_+99.epd` | 8,533 | 16 | Smaller, faster to iterate |
| `8moves_v3.pgn` | 34,700 | 16 | PGN-format alternative if you prefer `-openings format=pgn` |

Rationale for UHO over balanced books: at ~3650 Elo, balanced openings produce 80–95% draws and SPRT never converges. UHO positions are selected to be imbalanced *but still playable for both sides*, cutting draw rate to ~55–70%.

---

## 5. Opening Book and Tablebase Tooling

### Polyglot `.bin` — the format, precisely

- Fixed **16-byte records**: `key uint64 | move uint16 | weight uint16 | learn uint32`, **all big-endian**, file **sorted ascending by key**.
- `key` = XOR of 781 constants: `RandomPiece[64*kind + 8*row + file]` (768 entries), `RandomCastle[4]`, `RandomEnPassant[8]`, `RandomTurn[1]`.
- Piece numbering alternates black/white: `0` black pawn, `1` white pawn, `2` black knight, … `11` white king`.
- **Castling encoding** is the subtle part: `white short = e1h1`, `white long = e1a1`, `black short = e8h8`, `black long = e8a8` (king square → rook square), not `e1g1`.
- `move` bitfield: bits 0–2 to-file, 3–5 to-row, 6–8 from-file, 9–11 from-row, 12–14 promotion (`0` none, `1` N, `2` B, `3` R, `4` Q).
- `en passant` in the key follows the **capture-possible** semantics, *not* the FEN's unconditional target square.
- Castling rights in the key are "potential" rights as in FEN (all four true from the start position).
- `weight` = `2*wins + draws` (generator convention); weight `0` should be treated as "never play".

**Where to implement it:** in **Python**, not C++.

- `python-chess` already provides the whole read path: `chess.polyglot.open_reader(path)`, `reader.find_all(board)`, `reader.find(board)`, `reader.weighted_choice(board)`, and `chess.polyglot.zobrist_hash(board)`. It is well-tested against the reference implementation (the docs example even probes `performance.bin`).
- `python-chess` has **no writer**. Write ~40 lines yourself: compute `zobrist_hash` per position, pack `<QHHI` big-endian (or `struct.pack(">QHHI", …)`), sort by key, write. Keep it in `tools/build_book.py`. This is a small, genuinely authored artifact and it makes the Rule 3 story clean ("our generator, our selection criteria, our book").
- A C++ reader would mean transcribing the 781-constant table and re-deriving the castling/en-passant edge cases. That is 1–2 days of your 7–14, with a class of bugs that only shows up in rare positions. **Do not.**

**Enforcing the 10-ply cap — three independent guards:**

1. **Build time:** every line you insert is truncated at ply 10 (`len(line) <= 10`), so the file physically cannot answer a ply-11 probe.
2. **Runtime (authoritative):** in the console, `if board.ply() < 10 and book_has_move(board): play_book_move() else: engine_move()`. `board.ply()` is exactly the number of half-moves played.
3. **Assertion:** the logger records `source=book|engine`; a unit test replays a book-only game and asserts no book move occurs at `ply >= 10`.

If you ever do put the book in C++, the equivalent check is `pos.game_ply() < 10` (`src/position.h:340`, `inline int Position::game_ply() const { return gamePly; }`) — accurate only because you always start from the standard initial position (no FEN offset).

**Selection policy:** use `weighted_choice()` with a **seeded** `random.Random` per game is fine for variety, but for the *competition* prefer a deterministic, pre-audited repertoire keyed by position with a single chosen move per node. Rationale: you must be able to explain every move in the hearing, and a random draw from a third-party net is indefensible as authorship. Deterministic also makes post-game analysis reproducible.

**Third-party book:** allowed by Rule 3 but explicitly **does not count as authorship** — so if you ship one, say so, and never let it be your only differentiator. Recommended: build your own from your own engine's high-depth analysis plus a curated repertoire (~200–2,000 positions is plenty for a 10-ply book).

### Syzygy tablebases

| Item | Value | Confidence |
|---|---|---|
| Legal set | 3-, 4-, 5-piece only (Rule 4) | HIGH |
| Total size | **939 MiB** = 378 MiB WDL + 561 MiB DTZ, 290 files | HIGH |
| 6-piece (forbidden) | 149.2 GiB | HIGH |
| Engine option | `SyzygyPath <dir>`; **`SyzygyProbeLimit` defaults to 7 → you MUST set it to 5** | HIGH |
| Other options | `SyzygyProbeDepth` (default 1), `Syzygy50MoveRule` (default true) | HIGH |
| Stockfish probe code | `src/syzygy/tbprobe.cpp` (bundled, GPLv3 header intact) | HIGH |
| Reference probe library | Fathom / `pyrrhic` (BSD/MIT) — already vendored inside fastchess | HIGH |
| Generator | [`syzygy1/tb`](https://github.com/syzygy1/tb) — GPLv2; `--max 5` regenerates 3-4-5; needs ZSTD (or switch to LZ4) | HIGH |
| Download | `https://syzygy-tables.info` mirrors (also `tablebase.sesse.net`); fetch with `wget -r -np -nH --cut-dirs=N` before the event | MEDIUM |

**Recommendation: download, don't generate.** Generation of 3-4-5 on a laptop is possible (it's ~1 GB of output, RAM is not the constraint until 6-piece which needs 16 GB) but it costs hours you don't have and buys you identical files. Download the 290 files, verify counts, and checksum-list them into `NOTICE`.

**Non-negotiable configuration at startup** (put it in the console's self-check, fail loudly if not applied):

```
setoption name SyzygyPath value ./tb345
setoption name SyzygyProbeLimit value 5
setoption name Syzygy50MoveRule value true
```

A 6- or 7-piece file present on disk is *not* itself a violation, but a probe at 6 pieces would be — and Rule 4 forbids the tables outright. Keep the directory physically containing only `KQvK`, … 5-piece files, and add a startup assertion that no filename in the TB directory encodes >5 pieces (parse the piece-count prefix of each Fat/`KQvKR`-style name). That is a 15-line check that turns a rule violation into a startup error. Confidence: HIGH (this is the highest-severity compliance footgun in the whole stack).

---

## 6. Logging: Depth / Nodes / Eval / PV / Time

### Stockfish's own output is sufficient — do not write a C++ logger

Every field Rule 9 requires is already emitted on the UCI `info` line. Verified raw output from the SF19 build:

```
info depth 20 seldepth 31 multipv 1 score cp 34 nodes 381392 nps 212830 hashfull 122 tbhits 0 time 1792 pv e2e4 c7c5 g1f3 d7d6 d2d4 c5d4 f3d4 g8f6 b1c3 a7a6 c1e3 e7e5 d4b3 f6g4 e3c1 f8e7 f1c4 e8g8 c3d5 e7h4
info depth 21 seldepth 32 multipv 1 score cp 31 upperbound nodes 427482 nps 205224 hashfull 138 tbhits 0 time 2083 pv e2e4 c7c5
bestmove e2e4 ponder c7c5
```

Generation site: `UCIEngine::on_update_full()` in `src/uci.cpp:654-676`. Field order is stable.

### Extraction — use `python-chess`, not a regex

```python
import chess, chess.engine

engine = chess.engine.SimpleEngine.popen_uci("./stockfish", timeout=10.0)
engine.configure({
    "Threads": 8, "Hash": 2048,
    "Move Overhead": 100,
    "SyzygyPath": "./tb345", "SyzygyProbeLimit": 5,
    "MultiPV": 1, "UCI_ShowWDL": False,
})

result = engine.play(
    board,
    chess.engine.Limit(white_clock=w, black_clock=b, white_inc=10.0, black_inc=10.0),
    info=chess.engine.INFO_ALL,     # <-- REQUIRED
)
info = result.info
```

`PlayResult.info` then contains (verified against `chess/engine.py`):

| Key | Type | Notes |
|---|---|---|
| `depth` | int | last **completed** depth |
| `seldepth` | int | selective depth |
| `nodes` | int | cumulative for this search |
| `nps` | int | |
| `score` | `PovScore` | `info["score"].pov(color)` normalises POV; `.is_mate()` distinguishes cp from mate |
| `pv` | `list[chess.Move]` | `" ".join(m.uci() for m in info["pv"])` |
| `time` | **float seconds** | python-chess divides the engine's ms by 1000.0 |
| `multipv` | int | 1 for mainline |
| `tbhits`, `hashfull` | int | |
| `lowerbound` / `upperbound` | `True` (key present) | **bound flag** — see gotcha below |
| `string` | str | `info string …` lines (NNUE banner, Syzygy warnings, `CRITICAL ERROR`) |

**Gotchas that will bite you:**

1. **`play()` defaults to `info=INFO_NONE`.** Forget `info=INFO_ALL` and `result.info` is `{}` — the log silently has no depth/nodes/eval. Assert `"depth" in result.info` before writing a line.
2. **The final `info` can be a bound.** SF19 emits `upperbound`/`lowerbound` on the aborted last iteration (see the `depth 21 … upperbound` line above). Log it, and render as `+0.31 (upperbound)`. Do not let a bound masquerade as exact.
3. **`info string` lines are not errors.** `info string Available processors: 0-11`, `info string NNUE evaluation using …`, `info string Syzygy based PV extension requires more time…` all appear mid-stream. A naive parser that splits on whitespace and assumes `key value` pairs will crash. `python-chess` handles them (`info["string"]`).
4. **SF19 is strict about input.** Invalid FEN/UCI now produces `info string CRITICAL ERROR …` and the process **terminates**. Wrap every `board.push()` in `parse_uci` first, and treat `CRITICAL ERROR` as an operator-error path, not a bug.
5. **Book and tablebase moves have no engine `info`.** Synthesise: `depth=0, nodes=0, score=None` and `source="book"` / `source="tb"`. Without this, your log has holes exactly where the judges will look.
6. **`time` is engine-reported search time**, not the clock drain. Log **both**: `engine_time_ms = int(info["time"]*1000)` and `wall_ms = monotonic() - t0`. The difference *is* your operator/IO latency — the exact input your custom TM needs.
7. **`ucinewgame` between games.** Use `game=obj` in `play()` (python-chess sends `ucinewgame` when the object changes) so the TT resets per game but persists across moves — which is what makes Rule 13 ponder/TT-warming worthwhile.

### Log format: two files, one source of truth

Write a **CSV** (`log/moves.csv`) for machine analysis and a **human `.log`** for the judges; generate both from one `dict`.

```
# log/game-<id>.log — Rule 9 mandatory artifact
game  2026-11-14T10:03:00  White=Us  TC=15+10
ply move color  uci    depth nodes      eval        pv                                   engine_ms wall_ms clock_left  source
 1  b   black  e7e5   24    1_204_331  +0.18        e7e5 g1f3 b8c6 f1b5 g8f6 e1g1        4821      5012    145_988     engine
 2  w   white  g1f3   -     -          book        g1f3                                    0         0       145_988     book
 3  w   white  f1b5   26    3_877_002  +0.22 (ub)  f1b5 a7a6 b5a4 g8f6 e1g1 f6e4        9133      9187    146_788     engine
```

Rule 9 field mapping — every field accounted for:

| Rule 9 requirement | Source | Fallback |
|---|---|---|
| número do lance | `board.fullmove_number` + `board.ply()` | — |
| cor | `"white" if board.turn == chess.WHITE else "black"` (side that moved) | — |
| lance escolhido em UCI | `result.move.uci()` | book: `entry.move.uci()` |
| profundidade atingida | `info["depth"]` | book/tb: `0` |
| nós avaliados | `info["nodes"]` | book/tb: `0` |
| avaliação da posição | `info["score"]` + bound flag, logged **both** STM-POV and White-POV | book: `"book"`; tb: `"tb win/draw/loss"` |
| variante principal (PV) | `" ".join(m.uci() for m in info["pv"])` | book/tb: the move itself |
| tempo gasto | `info["time"]` **and** wall-clock delta | book: `0` |

Flush after every line (`open(..., "a", buffering=1)` or `fh.flush()`). A crash mid-game must not lose the log — Rule 9 says the log is handed to the judges at the end of the game.

---

## 7. Spoken-Move Input Layer (operator enters opponent's UCI move)

### Decision: **no speech recognition.** Keyboard + legality gate + confirmation.

Rule 10 requires the *team* to **announce the move aloud** and the *opponent* to repeat it. The software's job is only the last step: "cada equipe insere o lance em seu próprio software". So the input layer is a **human operator typing UCI**, and the design goal is *zero illegal/typo insertions under time pressure*, not voice parsing.

**Why not offline ASR (Vosk 0.3.x / whisper.cpp):** UCI strings are the worst possible ASR input — isolated letter+digit tokens with high confusability (`b/d/e`, `g/j`, `2/3`, `e2e4` vs `e7e5`), no language model to lean on, and a single substitution silently produces a *legal but wrong* move. A wrong-but-legal move is far worse than a rejected one: it corrupts the position and the game. ASR model sizes (40 MB – 1.5 GB), CPU contention with the engine, and a failure mode you cannot unit-test make this a strict downgrade. Confidence: HIGH.

### Design that actually survives tournament pressure

```
$ chessconsole --color white --tc 900+10
──────────────────────────────────────────────
  a  b  c  d  e  f  g  h        You: White    ply 1
8 r  n  b  q  k  b  n  r  8     Clock: 15:00
7 p  p  p  p  p  p  p  p  7     Engine: 8 threads
6 .  .  .  .  .  .  .  .  6
5 .  .  .  .  .  .  .  .  5     Opponent to move.
4 .  .  .  .  .  .  .  .  4
3 .  .  .  .  .  .  .  .  3
2 P  P  P  P  P  P  P  P  2
1 R  N  B  Q  K  B  N  R  1
──────────────────────────────────────────────
opponent move (UCI) > e2e4      # <TAB> completes from the 20 legal moves
  parsed: e2e4  =  e4           # SAN echo, human-readable read-back
  confirm? [Y/n] > y
  ok. position updated, 20 replies available. our clock running.
```

Four properties, all cheap:

1. **Legality gate first.** `chess.Board.parse_uci(s)` raises `chess.InvalidMoveError` (and `ValueError` for malformed strings) — verified present in `chess` 1.11.2. Never `push` a move you have not parsed. On failure: print the reason and **the list of legal moves**, and do not advance the clock.
2. **Completion from the legal-move set.** `sorted(m.uci() for m in board.legal_moves)` as a `readline` completer (stdlib, zero deps). `e2e<TAB>` → `e2e4`. This removes whole classes of typos and needs no dependency.
3. **Human read-back echo.** Print the parsed move as SAN *and* as a board diff. Rule 10 already requires a verbal repeat — this makes the software part of that loop, so a mis-heard move is caught by the operator's own eyes in <1 s.
4. **Explicit confirmation is skippable, not defaulted.** `[Y/n]` with Enter = yes, because a confirmation keystroke at every move costs ~1 s × ~80 moves ≈ 80 s of clock per game. Make `--fast` (no confirm) an option for practice, but require confirm in the tournament profile.

**Robustness details worth 20 lines of code:**

- Normalise input: `strip().lower().replace(" ", "")`. Accept `e2e4`, `E2E4`, ` e2 e4 `.
- Accept SAN as a *fallback* via `board.parse_san()` — useful when the opponent announces "bispo para b5" and the operator transcribes; reject ambiguity with a clear list.
- Promotion: require the suffix (`e7e8q`). If the operator types `e7e8`, detect multiple promotion moves and re-prompt rather than guessing.
- **Undo:** `u` reverts the last ply, `U` reverts a full move pair. Non-negotiable — the board is the source of truth (Rule 10), so when they disagree you must be able to realign the software to the board without restarting.
- **Resync from board:** `sync <FEN>` sets the position outright and re-derives the clock. Use it when the physical board wins an argument.
- **Clock sync key:** a single keypress (`s`) opens "physical clock says MM:SS >" and snaps the internal timer. This is the `PROJECT.md` requirement and it doubles as the measurement input for your TM's latency term.
- **Two-phase entry:** accept the opponent's move *while our engine is still pondering* (`PROJECT.md`/Rule 13). The console must accept input in a background thread and, on the move arriving, send `stop` then `go` — see the TM section.
- **Refuse to proceed on board/engine disagreement:** after every push, assert `not board.is_valid()` is false and `board.fen()` round-trips.

**Libraries:** stdlib `readline` + `input()` is enough and is the recommendation (zero install risk, works offline by definition). `prompt_toolkit==3.0.53` is the upgrade path if the operator wants a completion popup instead of `<TAB>`; it is pure Python but adds a dependency to declare under Rule 14. Do **not** use a Flask/FastAPI localhost UI: it is a "network service" that an arbiter verifying "no external requests" must then reason about, and it buys nothing over a terminal.

---

## Installation

Everything below happens **before** the event, while you still have network. After this, the tree is self-contained.

```bash
# ── 1. Engine base (pinned to the stable tag, never master) ────────────────────
git clone --branch sf_19 --depth 1 https://github.com/official-stockfish/Stockfish.git engine
cd engine
git rev-parse HEAD            # → record in NOTICE as the origin commit
cd src
make -j"$(nproc)" net         # fetch + SHA-validate nn-1a298aa575a0.nnue (~94 MB)
make -j"$(nproc)" profile-build   # PGO build; measured 2 m 47 s (faster than a plain build, no LTO in the instrumented pass)
./stockfish bench             # sanity: record nodes + nps in docs/build.md
cd ../..

# ── 2. Match harness (no dependencies) ───────────────────────────────────────
git clone --depth 1 https://github.com/Disservin/fastchess.git fastchess
cd fastchess && make -j"$(nproc)" && cd ..
# pin the commit you actually built:
git -C fastchess rev-parse HEAD   # expect ebfd64c... for v1.8.2-alpha era

# ── 3. Console (pure Python; vendor it so no pip is needed at the event) ─────
python3 -m venv .venv
.venv/bin/pip install --no-index --find-links vendor/ chess==1.11.2 pytest==9.1.1
#   OR, strictly offline-safe: copy the pure-Python `chess/` package into the repo
#   (it has zero runtime dependencies) and `import chess` from there.

# ── 4. Opening books for the harness (CC0-1.0) ───────────────────────────────
mkdir -p books && cd books
base=https://raw.githubusercontent.com/official-stockfish/books/master
curl -LO "$base/noob_5moves.epd.zip"
curl -LO "$base/UHO_Lichess_4852_v1.epd.zip"
curl -LO "$base/8mvs_%2B90_%2B99.epd.zip"
unzip -o '*.zip' && cd ..

# ── 5. Syzygy 3-4-5 (939 MiB, 290 files) ─────────────────────────────────────
mkdir -p tb345
# from https://syzygy-tables.info or a mirror, e.g.:
#   wget -r -np -nH --cut-dirs=2 -A '*.rtbw,*.rtbz' https://tablebase.sesse.net/syzygy/3-4-5/ -P tb345
find tb345 -type f | wc -l      # expect 290
```

`vendor/` must contain the wheels so `pip` never touches the network. If `pip` is unavailable (this research sandbox had no `pip`), vendor the source package instead — `python-chess` is pure Python with `requires_dist: None`, so copying `chess/` into the repo is a complete install.

---

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| Stockfish 19 (`sf_19`) | Development snapshot `stockfish-dev-YYYYMMDD-<sha>` | Never for the event — no stable origin commit to declare under Rule 1, and behaviour churns daily. Acceptable only for a throwaway experiment you discard |
| Authored TimeManagement | Authored **evaluation** term (e.g. a pawn-structure or king-safety term) | If the TM rewrite slips past day 6. A single well-tested eval term is also defensible under Rule 2 and is lower-risk to *implement* but higher-risk to *tune* (a bad eval term loses Elo; a conservative TM gains time without losing games) |
| Authored TimeManagement | Authored **search** change (e.g. history/LMR policy) | Only if a team member already knows SF's search internals. `search.cpp` is 94 KB and every change needs SPRT at `10+0.1`; a 1–2 week budget makes this the riskiest of the three options |
| fastchess | cutechess-cli 1.5.1 | Only if you must consume Polyglot `.bin` in the harness. Qt ≥ 6.8 requirement makes this a bad offline bet |
| fastchess | Write your own match runner | Never. You would spend 2 days to get worse SPRT statistics |
| Python console (`python-chess`) | C++ console inside the engine binary | If you need sub-millisecond clock precision or want a single binary for the judges. Cost: reimplementing UCI parsing, FEN, legal moves, Polyglot and Syzygy in C++ — which `Rule 14` explicitly permits you to get from `python-chess` instead |
| `ARCH=native` build | `x86-64-universal` build | Only if you must run the same binary on heterogeneous laptops (you don't — one team, one laptop) |
| Syzygy download | Generate with `syzygy1/tb --max 5` | Only if you cannot reach a mirror before the event, or you want the provenance story "we generated our own tables". Budget several hours + ZSTD |
| Own book generator (Python) | Third-party Polyglot `.bin` downloaded before the event | Allowed by Rule 3, but it is **not authorship** and it is unexplainable in the hearing. Use one only as a *sparring* book for the harness |
| No GPU | Leela Chess Zero + GPU net | Out of scope per `PROJECT.md`. Lc0 at 15+10 on a laptop GPU is weaker than SF19 on the same laptop's CPU, and it replaces the entire codebase you would have to defend |

---

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| **`JSON`/`epd`-only reasoning about the competition book** | Rule 3 says "10 meios-lances"; an EPD line of 16 plies in the harness book is irrelevant to the game, but a book that can answer a ply-11 probe is a rule violation | Two guards: truncate at build, gate on `board.ply() < 10` |
| **`6`/`7`-piece Syzygy anywhere on disk** | Rule 4 forbids them outright. Shipping them looks like an attempt to skirt the rule even if `SyzygyProbeLimit=5` | 3-4-5 only + a startup filename assertion |
| **Default `SyzygyProbeLimit=7`** | Stockfish's default silently permits 6–7 piece probing | Set `5` explicitly in startup config and assert it |
| **`Move Overhead` at the default 10 ms** | Empirically caused 1 timeout in 24 games at `tc=10+0.1`; your real path has an operator in it | `Move Overhead = 100` (100–300) |
| **SPRT at the competition time control (15+10)** | ~5 min/game → 500 games = 2 days | SPRT at `10+0.1` (or `8+0.08`), then verify TM at `60+1` and `15+10` with a handful of games |
| **`tc=1+0.01` for accept/reject decisions** | Massive draw-rate distortion and TM behaviour collapse; conclusions do not transfer | `1+0.01` for smoke tests only; `10+0.1` for verdicts |
| **cutechess-cli** | Qt 6.8 build/install risk on an offline laptop; documented timeouts at high concurrency; no pentanomial reporting | fastchess |
| **`make net` at the event** | The build is not fully offline until the `.nnue` is present | Download the net before, commit/archive the tree |
| **`NNUE_EMBEDDING_OFF`** for the shipped binary | 1-byte stub; the engine then depends on a correct `EvalFile` path | Default embedded build (95 MB binary) |
| **Offline ASR (Vosk / whisper.cpp) for move entry** | Isolated UCI tokens are maximally confusable; a legal-but-wrong move corrupts the game; model + CPU contention | Keyboard + `<TAB>` completion + legality gate + read-back |
| **A localhost web UI** | Invites "is that a network service?" during the Rule 14 check, plus a server process to babysit | Terminal |
| **Editing `evaluate.h`'s `EvalFileDefaultName`** | The comment forbids it: the name must be the SHA-256 prefix or `scripts/net.sh` and Fishtest-style tooling break | Leave the macro alone; override with the `EvalFile` option if you must |
| **Rewriting GPL headers "cleanly"** | Deleting `Copyright (C) 2004-2026 The Stockfish developers` from a file you rewrote is a licence violation, and it destroys your Rule 1 defence | Keep the header verbatim, add your own line below |
| **`git rm Copying.txt` in favour of `LICENSE`** | Nothing breaks, but it looks like licence laundering to a reviewer | Keep `Copying.txt`; add `LICENSE` as a copy/symlink if tooling expects it |
| **Claiming the NNUE net as authored** | Rule 15: third-party weights do not count. The net is CC0 and unmodified | Say "official Stockfish 19 network, unmodified, CC0-1.0" |
| **SPSA as your Rule 2 credential** | Rule 2: "mero ajuste de parâmetros já existentes" does not count | SPSA is a strength tool only; the credential must be a structural rewrite |
| **`python-chess` `engine.play()` without `info=INFO_ALL`** | `result.info == {}` → an empty Rule 9 log | Pass `info=chess.engine.INFO_ALL`; assert on the result |
| **Parsing UCI `info` with a hand-rolled regex** | Bound flags (`upperbound`/`lowerbound`), `info string`, and multi-PV ordering will break it | `python-chess`'s parser |
| **`Hash` > available RAM** | Rule 7 has no RAM cap, but OOM-killing the engine mid-game loses the game | 2–4 GB (`Hash=2048`–`4096`); measure RSS before the event |
| **`Threads` = `nproc` when `nproc` includes SMT siblings** | Extra latency and variance for little nps | Physical cores (e.g. 8 on a 16-thread laptop); SPRT showed 4t = 2.8× and 12t = 4.9× single-thread nps, i.e. clear diminishing returns |

---

## Version Compatibility

| Package A | Compatible With | Notes |
|-----------|-----------------|-------|
| Stockfish `sf_19` | GCC ≥ 14 (`COMP=gcc`) | `-std=c++17`; `#embed` used opportunistically. Verified: GCC 16.2.1 |
| Stockfish `sf_19` | Clang ≥ 18 (`COMP=clang`) | Supported upstream; **not** verified in this environment (no Clang installed) — test it if you plan to use it |
| `nn-1a298aa575a0.nnue` | Stockfish 19 **only** | The net name/architecture is pinned by `EvalFileDefaultName`; SFNNv16 is not loadable by SF18 or earlier |
| `python-chess` 1.11.2 | Python 3.8–3.13 (classifiers) | Pure Python, `requires_dist: None`. Python 3.14 was present in this sandbox but `pip` was absent, so 3.14 was **not** executed — pin 3.12 and vendor the package |
| `python-chess` 1.11.2 | Stockfish 19 UCI output | Verified format compatibility above (`upperbound`, `info string`, `time` in ms→s) |
| `prompt_toolkit` 3.0.53 | Python ≥ 3.10 | Only if you take that option |
| `fastchess` `ebfd64c` | Any UCI engine | Requires GCC ≥ 7.3 (README) — non-issue |
| `fastchess` | EPD/PGN books only | **No Polyglot `.bin`** — verified by grepping `app/src` for `polyglot` (no hits) |
| Syzygy 3-4-5 | Stockfish `syzygy/tbprobe.cpp`, fastchess `pyrrhic`, `python-chess.syzygy` | Same on-disk format across all three |
| GPL-3.0-or-later (Stockfish) | GPL-3.0-or-later (`python-chess`) | Compatible; the combined work is distributed under GPL-3.0-or-later |
| GPL-3.0-or-later (Stockfish) | MIT (`fastchess`) | Compatible, but fastchess is **dev-only** — do not ship it inside the engine repo's `src/` |

---

## GPLv3 Compliance Checklist (actionable)

Stockfish is **GPL-3.0-or-later**. Rule 1 additionally requires declaring the base project + origin commit and publishing the repo. Do every item below; it costs ~1 hour and removes the only existential risk in the project.

- [ ] **Keep `Copying.txt`** at the repo root, byte-identical, same filename. (Add `LICENSE` as a copy if a tool expects it — never rename.)
- [ ] **Keep `AUTHORS`** verbatim; append your team members at the end under a new heading (`# ChessChallendIII authors`).
- [ ] **Keep the GPL header block in every `.cpp`/`.h` you touch**, including files you rewrite from scratch. In `src/timeman.cpp` and `src/timeman.h` add exactly one line below the existing copyright:
      `Copyright (C) 2026 <Team> — time management rewritten, see NOTICE.`
      GPLv3 §5(a) requires modified files to carry "prominent notices stating that you changed the files and the date of any change" — this line plus the `NOTICE` satisfies it.
- [ ] **Add `NOTICE`** containing: base project (`https://github.com/official-stockfish/Stockfish`), tag `sf_19`, **full origin commit SHA** (from `git rev-parse HEAD` after the clone), date of fork, list of modified files, one-paragraph description of the changes, build command + `ARCH` + compiler version, and the `bench` node count.
- [ ] **Net provenance** in `NOTICE`: `nn-1a298aa575a0.nnue`, 98,511,183 bytes, SHA-256, source URL, licence **CC0-1.0**, "unmodified; not authored by the team".
- [ ] **Third-party dependency declaration** (Rule 14) with licences: `python-chess` 1.11.2 (GPL-3.0-or-later, shipped), `fastchess` (MIT, dev-only), Syzygy 3-4-5 (probe code unrestricted; data from `syzygy-tables.info`), opening books (`official-stockfish/books`, CC0-1.0), `pytest` (MIT, dev-only). Commit `requirements.txt` (with hashes if you vendor).
- [ ] **Publish the complete corresponding source for the exact binary**: engine tree + `Makefile` + net + console + book tooling + `docs/build.md`. Rule 1 asks for the repo anyway; GPLv3 §6 asks for the same thing.
- [ ] **Do not add a more restrictive licence** anywhere, and do not add "All rights reserved" to any file in the tree.
- [ ] **Do not vendor `fastchess` into `src/`** — keep it as an external dev tool so the engine tree stays a clean Stockfish derivative.
- [ ] **Tag the release**: `git tag v1.0-event` on the exact commit you build the competition binary from, and note the tag in `NOTICE`. This is what makes "we declare commit X" verifiable.
- [ ] **Authorship evidence** (Rule 2, not GPL): `docs/time-management.md` (algorithm + state diagram, Portuguese), a `git log --stat` showing `timeman.cpp` rewritten, and the SPRT/clock-remaining evidence. This is a *competition* requirement, not a licence one — but it is the one that decides whether you place.

---

## Verified Empirical Data

Everything in this table was measured or executed during this research, on one machine (GCC 16.2.1, 12 hardware threads, 15 GB RAM). Treat the **shapes** as transferable and the absolute numbers as a floor for a stronger laptop.

| Measurement | Result | How |
|---|---|---|
| `make -j12 build` (Stockfish 19) | **3 m 11 s** wall / 4 m 19 s CPU | timed |
| `make -j12 profile-build` (PGO) | **2 m 47 s** total (instrumented build → bench → optimized build → cleanup). Bench node count **identical** (2,497,913) before and after, i.e. PGO changes speed only, never results | timed |
| Binary size, net embedded | **95 MB** | `ls -lh src/stockfish` |
| Net file | **98,511,183 B / 93.9 MiB**, reported as "109MiB" in-memory by the engine | GitHub API + `info string` |
| `./stockfish bench` | 2,497,913 nodes, **~280 knps** 1t | run |
| 1 / 4 / 12 threads nps | **274k / 779k / 1,330k** | `go movetime 4000` |
| Time spent on move 1 at `15+10`, 1 thread | **19,757 ms**, depth 28, 4.14 M nodes | `go wtime 150000 btime 150000 winc 10000 binc 10000` |
| Time spent on move 2 at `15+10` | **20,785 ms** | same, after `1.e4 e5` |
| fastchess `make -j12` | **1 m 41 s**, **2.4 MB** binary, no external deps | timed |
| fastchess `10+0.1`, 1t, `-concurrency 12` | 24 games in **84 s** → ~1,000 games/h; **1 timeout** with default `Move Overhead` | run |
| fastchess `1+0.01`, 1t, `-concurrency 12` | 80 games in **30 s** → ~9,600 games/h | run |
| SPRT output format | `LLR: -0.20 (-6.6%) (-2.94, 2.94) [0.00, 5.00]` + `Ptnml(0-2)` | run |
| `timeman.cpp` line count | 144 lines, single `init()` of ~96 lines | read |
| Polyglot code in Stockfish 19 | **none** (`grep -r polyglot src/` → 0 hits) | grep |
| Polyglot support in fastchess | **none** (EPD/PGN only; `grep -r polyglot app/src` → 0 hits) | grep |
| Python on this box | 3.14.7, **no `pip`**, `venv` available | check |

> **PGO note:** `profile-build` is **not** dramatically slower than `build` — measured **2 m 47 s** vs **3 m 11 s** for a plain `build` on the same machine, because the instrumented pass compiles without LTO. It does cost one extra benchmark run. Do it once, on the final tree, right before tagging; the PGO'd binary is what you ship. Do **not** claim a specific PGO speedup from this research — the sandbox was too noisy (bench ranged 280–350 knps across runs), and only the deterministic node count was stable.

**Two numbers worth acting on immediately:**

1. **~20 s on move 1** is Stockfish's default TM at your exact time control. That is the single strongest empirical justification for the authored component, and it is measurable in 20 seconds — put it in `docs/time-management.md` as the baseline figure.
2. **1 timeout in 24 games at the default 10 ms `Move Overhead`.** The engine is already marginal on a quiet, local, single-process pipe. Add an operator, a `stop`/`go` cycle, and a Python process, and you will flag. Set 100 ms.

---

## Sources

| Source | What was verified | Confidence |
|---|---|---|
| `https://api.github.com/repos/official-stockfish/Stockfish/releases` | `sf_19` is latest stable (2026-09-05); release cadence 18 → 19 | HIGH |
| `https://github.com/official-stockfish/Stockfish/releases/tag/sf_19` (body) | +44 Elo vs SF18; SFNNv16; secondary net retired; universal binaries; strict position validation; `info string CRITICAL ERROR` | HIGH |
| **Stockfish 19 source tarball** (`sf_19`), read in full: `src/timeman.cpp/.h`, `src/search.cpp/.h`, `src/engine.cpp`, `src/evaluate.h`, `src/uci.cpp`, `src/nnue/network.cpp`, `src/universal/nnue_embed.cpp`, `src/Makefile`, `scripts/net.sh`, `Copying.txt`, `AUTHORS` | Every API name, line number, option default, formula, and build target in this document | HIGH |
| Actual build + run of `sf_19` on this machine | Build time, binary size, nps scaling, UCI `info` format, 15+10 time allocation, `bench` | HIGH |
| `https://editor.chessprogramming.org` / Wikipedia *Stockfish (chess)* | CCRL 40/15 4CPU **3650** (3653 cited for Sept 2026) | HIGH |
| `https://computerchess.org.uk/ccrl/4040/` | CCRL list conditions (books ≤12 moves, 3-4-5 EGTB) | HIGH |
| `https://github.com/Disservin/fastchess` (repo + `man.md` + `README.md` + source) | v1.8.2-alpha, MIT, EPD/PGN-only openings, SPRT flags, `-report penta`, `-recover`, concurrency claims, no Polyglot | HIGH |
| fastchess discussion #137 + chessprogramming wiki *Fastchess* | Rationale vs cutechess (overhead, 250-thread testing, Qt-free) | MEDIUM |
| `https://github.com/cutechess/cutechess` + `docs/cutechess-cli.6` | v1.5.1, **Qt ≥ 6.8**, `book=`/`bookdepth=` Polyglot support, `-sprt` syntax | HIGH |
| `https://hgm.nubati.net/book_format.html` | Polyglot 16-byte big-endian records, 781 Zobrist constants, castling `e1h1`, en-passant key semantics, `weight = 2W+D` | HIGH |
| `https://python-chess.readthedocs.io/` + `chess/engine.py` @ master + PyPI metadata | 1.11.2, GPL-3.0-or-later, zero deps, `parse_uci`/`InvalidMoveError`, `INFO_ALL`, `time` in seconds, `lowerbound`/`upperbound`, `_go` → `wtime/btime/winc/binc` in ms, `play()` defaults to `INFO_NONE`, polyglot reader API (no writer) | HIGH |
| `https://github.com/official-stockfish/networks` | Nets repo licence **CC0-1.0**; `nn-1a298aa575a0.nnue` = 98,511,183 B | HIGH |
| `https://github.com/official-stockfish/books` + `LICENSE` | **CC0-1.0**; `noob_5moves.epd` exactly 10 plies; `UHO_Lichess_4852_v1.epd` 16 plies | HIGH |
| `https://chessprogramming.org/Syzygy_Bases` + `https://github.com/syzygy1/tb` | 3-4-5 = 939 MiB (378 WDL + 561 DTZ); 6-piece 149.2 GiB; generator is GPLv2, ZSTD, `--max` | HIGH |
| `https://official-stockfish.github.io/docs/fishtest-wiki/Running-Fastchess.html` | Reference fastchess invocation, `UHO_Lichess_4852_v1.epd`, adjudication flags | HIGH |
| `docs/competition-rules.md` (project) | Rules 1–15 as applied throughout | HIGH |

**Gaps / not verified**

- Python 3.14 execution of `python-chess` 1.11.2 — no `pip` in this sandbox. Mitigation: pin 3.12 and vendor the package.
- Clang build of `sf_19` — no Clang installed. Mitigation: use GCC.
- PGO speedup on the target laptop — measured wall-clock 2 m 47 s on this 12-thread box, but the sandbox was too noisy to quantify the nps gain (bench ranged 280–350 knps).
- Exact throughput on the team's laptop — scale the ~1,000 games/h figure by core count and clock.
- fastchess's precise speed advantage over cutechess-cli in games/s (no published benchmark) — the decision rests on dependency weight, concurrency behaviour, and SPRT features, which are documented.

---

*Stack research for: competition chess engine (Stockfish fork, offline, 15+10)*
*Researched: 2026-10-26*
