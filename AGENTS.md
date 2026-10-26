<!-- GSD:project-start source:PROJECT.md -->

## Project

**ChessChallendIII — Motor para a III Chess Challenge**

Um motor de xadrez para competir na III Chess Challenge: fork do Stockfish em C++, com gestão de tempo escrita pela equipe, um console próprio que opera o protocolo falado da competição e cumpre o log obrigatório, e um pipeline de IA offline que treina e testa o motor antes do evento. Roda 100% local, sem rede, num notebook da própria equipe, sob controle de tempo 15 minutos + 10 segundos por lance.

O objetivo não é participar: é vencer. Toda decisão de escopo abaixo é filtrada por essa pergunta — isto aumenta a chance de ganhar partidas no dia?

**Core Value:** **Fechar cada partida com mais tempo restante no relógio do que o adversário, sem nunca perder por tempo.** A competição desempata confrontos empatados pelo tempo total restante somado nas três partidas (Regra 12). Isso torna a gestão de tempo simultaneamente o componente de autoria exigido pela Regra 2 e a alavanca de desempate que nenhuma equipe adversária provavelmente vai modelar.

### Constraints

- **Licença**: GPLv3 herdada do Stockfish — o repositório precisa ser publicado e disponibilizado à banca (Regra 1). Irrelevante na prática porque o código é entregue de qualquer forma, mas obriga a manter os headers e o aviso de licença intactos.
- **Prazo**: 1 a 2 semanas até o evento — define o escopo; nenhuma fase pode depender de pesquisa longa.
- **Offline**: nenhuma requisição externa durante partidas — toda dependência precisa estar instalada e declarada antes do evento (Regra 14).
- **Protocolo de lance**: UCI falado, confirmação em voz alta, movimento físico, inserção manual no software; o tabuleiro físico é a fonte da verdade e resolve divergências (Regra 10).
- **Book**: máximo 10 meios-lances, depois disso o software decide sozinho (Regra 3).
- **Tablebase**: máximo 5 peças (Regra 4).
- **Log**: formato obrigatório por lance, entregue à banca ao final de cada partida (Regra 9).
- **Hardware**: notebook forte com muitas threads — suficiente para build e SPRT paralelo; define o orçamento de tuning.

<!-- GSD:project-end -->

<!-- GSD:stack-start source:research/STACK.md -->

## Technology Stack

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

## 1. Stockfish Fork Mechanics

### What a current Stockfish source tree actually contains (verified, `sf_19`)

### Build procedure (verified end-to-end on a 12-core Linux box)

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

### NNUE embedding — how it actually works in SF19

### What must be preserved for GPLv3 (and how)

### Current stable series and strength

- **Stockfish 19**, tag `sf_19`, published **2026-09-05**. Previous: 18 (2026-01-31), 17.1 (2025-03-30).
- **CCRL 40/15, 4CPU: 3650** (Wikipedia cites 3653 for September 2026). CCRL's conditions are "general books up to 12 moves, 3-4-5 piece EGTB" — i.e. *easier* than your 10-ply book rule, so treat 3650 as an upper bound for the same engine under your constraints.
- +44 Elo over SF18 in upstream testing; wins >3× the game pairs it loses.
- Development snapshots exist (`stockfish-dev-YYYYMMDD-<sha>` released nightly). **Do not** build from a dev snapshot: you cannot cite a stable origin commit, and nightly bisect churn is a distraction. Use `sf_19`.

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
- **Legally:** the official nets are **CC0-1.0** (public domain dedication). They impose no copyleft, no attribution requirement, and no license interaction with your GPLv3 engine. You can ship, mirror, or modify them freely.
- **Competition-wise:** Rule 15 states weights downloaded from third parties **do not count as authorship**; only team-trained weights count, and only when accompanied by training code. Rule 2 excludes "mere parameter tweaking" and the LLM/NN path was already ruled out of scope in `PROJECT.md`.
- **Therefore:** use the official SF19 net unchanged. Do **not** fine-tune it and present the result as authorship — that is the single fastest way to lose the technical hearing. Fine-tuning also risks burning a week for a regression.
- Do not run `make net` variants with `NNUE_EMBEDDING_OFF` for the shipped binary — you get a 1-byte stub and a runtime failure if `EvalFile` is wrong.
- Do not ship both an embedded net and a *different* `EvalFile` — the engine will silently load the file, and your binary no longer matches the source+net you published.
- Do not try to accelerate NNUE on GPU. SFNNv16 inference is a handful of int8/int16 dot products sized for CPU SIMD; a GPU offload would add latency and break nothing useful.
- Do not present the net as your own work in the write-up, even implicitly ("our neural network"). Say "official Stockfish 19 network, unmodified".

## 3. Time Management Internals (the authored component)

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

### `Move Overhead` semantics (exactly)

- Read at the top of `init()` and subtracted **`(2 + mtg)` times** from the projected `timeLeft` — i.e. it is amortised over the remaining move horizon, not subtracted from this move.
- Also subtracted once from the hard ceiling: `0.8097 * limits.time[us] - moveOverhead`.
- Also used by `syzygy_extend_pv()` (`src/search.cpp:2144`) as a **wall-clock abort budget of `moveOverhead / 2` ms** for TB PV extension — set it too low and you truncate TB PVs; too high and you burn clock extending them.
- Default 10 ms is tuned for a GUI/pipe on localhost. Your reality includes a **human operator announcing moves** and a possible `stop`/`go` cycle. Empirically, 24 games at `tc=10+0.1`, concurrency 12, default overhead, produced **1 timeout** (see [Verified Empirical Data](#verified-empirical-data)) — at 10 ms you are already on the edge. Set **`Move Overhead = 100`** (range 100–300) for competition and **assert** it in the console's startup self-check.

### Extension points, ranked by blast radius (use #1)

### Rule 2 traps to avoid in the TM work

- ❌ "Same formula, new constants." Retuning `optConstant`/`maxConstant` is explicitly excluded by Rule 2 ("mero ajuste de parâmetros já existentes").
- ❌ "Rename `TimeManagement` to `TeamTimeManager` and reformat." Excluded verbatim.
- ❌ Only changing `Move Overhead`'s default. Excluded.
- ✅ A different **decision structure**: e.g. a budget controller that (a) reserves a tiebreak surplus proportional to expected remaining moves, (b) measures actual clock drain vs. engine-reported elapsed and subtracts a learned latency term, (c) allocates by game phase and position complexity rather than by a closed-form polynomial in `ply`, (d) keeps a hard `maximum()` invariant that makes flagging impossible. Document the algorithm in `docs/` in Portuguese with a state diagram, and keep a `git log` that shows the file rewritten.
- ✅ Defend it with data: 20 games at 15+10 vs. the unmodified engine, reporting **clock remaining at game end** — that is the Rule 12 metric, not Elo.

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

### Verified throughput (this research machine: 12 hardware threads)

| Configuration | Games | Wall time | Throughput |
|---|---|---|---|
| `tc=10+0.1`, 1 thread/engine, `-concurrency 12` | 24 | 84 s | **~1,000 games/hour** |
| `tc=1+0.01`, 1 thread/engine, `-concurrency 12` | 80 | 30 s | **~9,600 games/hour** |

### The exact SPRT command (verified working)

# from the directory containing ./fastchess and your two engine builds

- `option.Move_Overhead=100` — spaces in UCI option names become underscores. Also apply this to `Base` for an apples-to-apples test.
- `-repeat` plays each opening twice with colors swapped (mandatory for pair statistics).
- `-each tc=10+0.1` matches cutechess's `moves/minutes:seconds+inc` format; your event TC is `15+10` but **never SPRT at 15+10** — a single game takes ~5 min of wall clock.
- `-report penta=true` gives the pentanomial LLR/penta counts that converge faster than trinomial.
- `-recover` restarts crashed engines instead of aborting; keep it for multi-hour runs.
- `-pgnout ... timeleft=true` gives you the per-move clock trace, which is exactly what you need to audit the TM.

### Scripting the SPRT loop

#!/usr/bin/env bash

# tools/sprt.sh  — runs a named experiment, logs LLR, stops on accept/reject

### Harness opening books (distinct from the competition book)

| Book | Lines | Depth (plies) | Use |
|---|---|---|---|
| `noob_5moves.epd` | 455,287 | **10** | **Exact match to Rule 3's 10-ply cap.** Use for "what happens after the book ends" testing |
| `UHO_Lichess_4852_v1.epd` | 2,632,036 | 16 | Balanced, low-draw-rate; the standard for strong engines. `order=random` |
| `8mvs_+90_+99.epd` | 8,533 | 16 | Smaller, faster to iterate |
| `8moves_v3.pgn` | 34,700 | 16 | PGN-format alternative if you prefer `-openings format=pgn` |

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
- `python-chess` already provides the whole read path: `chess.polyglot.open_reader(path)`, `reader.find_all(board)`, `reader.find(board)`, `reader.weighted_choice(board)`, and `chess.polyglot.zobrist_hash(board)`. It is well-tested against the reference implementation (the docs example even probes `performance.bin`).
- `python-chess` has **no writer**. Write ~40 lines yourself: compute `zobrist_hash` per position, pack `<QHHI` big-endian (or `struct.pack(">QHHI", …)`), sort by key, write. Keep it in `tools/build_book.py`. This is a small, genuinely authored artifact and it makes the Rule 3 story clean ("our generator, our selection criteria, our book").
- A C++ reader would mean transcribing the 781-constant table and re-deriving the castling/en-passant edge cases. That is 1–2 days of your 7–14, with a class of bugs that only shows up in rare positions. **Do not.**

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

## 6. Logging: Depth / Nodes / Eval / PV / Time

### Stockfish's own output is sufficient — do not write a C++ logger

### Extraction — use `python-chess`, not a regex

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

### Log format: two files, one source of truth

# log/game-<id>.log — Rule 9 mandatory artifact

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

## 7. Spoken-Move Input Layer (operator enters opponent's UCI move)

### Decision: **no speech recognition.** Keyboard + legality gate + confirmation.

### Design that actually survives tournament pressure

- Normalise input: `strip().lower().replace(" ", "")`. Accept `e2e4`, `E2E4`, ` e2 e4 `.
- Accept SAN as a *fallback* via `board.parse_san()` — useful when the opponent announces "bispo para b5" and the operator transcribes; reject ambiguity with a clear list.
- Promotion: require the suffix (`e7e8q`). If the operator types `e7e8`, detect multiple promotion moves and re-prompt rather than guessing.
- **Undo:** `u` reverts the last ply, `U` reverts a full move pair. Non-negotiable — the board is the source of truth (Rule 10), so when they disagree you must be able to realign the software to the board without restarting.
- **Resync from board:** `sync <FEN>` sets the position outright and re-derives the clock. Use it when the physical board wins an argument.
- **Clock sync key:** a single keypress (`s`) opens "physical clock says MM:SS >" and snaps the internal timer. This is the `PROJECT.md` requirement and it doubles as the measurement input for your TM's latency term.
- **Two-phase entry:** accept the opponent's move *while our engine is still pondering* (`PROJECT.md`/Rule 13). The console must accept input in a background thread and, on the move arriving, send `stop` then `go` — see the TM section.
- **Refuse to proceed on board/engine disagreement:** after every push, assert `not board.is_valid()` is false and `board.fen()` round-trips.

## Installation

# ── 1. Engine base (pinned to the stable tag, never master) ────────────────────

# ── 2. Match harness (no dependencies) ───────────────────────────────────────

# pin the commit you actually built:

# ── 3. Console (pure Python; vendor it so no pip is needed at the event) ─────

#   OR, strictly offline-safe: copy the pure-Python `chess/` package into the repo

#   (it has zero runtime dependencies) and `import chess` from there.

# ── 4. Opening books for the harness (CC0-1.0) ───────────────────────────────

# ── 5. Syzygy 3-4-5 (939 MiB, 290 files) ─────────────────────────────────────

# from https://syzygy-tables.info or a mirror, e.g.:

#   wget -r -np -nH --cut-dirs=2 -A '*.rtbw,*.rtbz' https://tablebase.sesse.net/syzygy/3-4-5/ -P tb345

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

## GPLv3 Compliance Checklist (actionable)

- [ ] **Keep `Copying.txt`** at the repo root, byte-identical, same filename. (Add `LICENSE` as a copy if a tool expects it — never rename.)
- [ ] **Keep `AUTHORS`** verbatim; append your team members at the end under a new heading (`# ChessChallendIII authors`).
- [ ] **Keep the GPL header block in every `.cpp`/`.h` you touch**, including files you rewrite from scratch. In `src/timeman.cpp` and `src/timeman.h` add exactly one line below the existing copyright:
- [ ] **Add `NOTICE`** containing: base project (`https://github.com/official-stockfish/Stockfish`), tag `sf_19`, **full origin commit SHA** (from `git rev-parse HEAD` after the clone), date of fork, list of modified files, one-paragraph description of the changes, build command + `ARCH` + compiler version, and the `bench` node count.
- [ ] **Net provenance** in `NOTICE`: `nn-1a298aa575a0.nnue`, 98,511,183 bytes, SHA-256, source URL, licence **CC0-1.0**, "unmodified; not authored by the team".
- [ ] **Third-party dependency declaration** (Rule 14) with licences: `python-chess` 1.11.2 (GPL-3.0-or-later, shipped), `fastchess` (MIT, dev-only), Syzygy 3-4-5 (probe code unrestricted; data from `syzygy-tables.info`), opening books (`official-stockfish/books`, CC0-1.0), `pytest` (MIT, dev-only). Commit `requirements.txt` (with hashes if you vendor).
- [ ] **Publish the complete corresponding source for the exact binary**: engine tree + `Makefile` + net + console + book tooling + `docs/build.md`. Rule 1 asks for the repo anyway; GPLv3 §6 asks for the same thing.
- [ ] **Do not add a more restrictive licence** anywhere, and do not add "All rights reserved" to any file in the tree.
- [ ] **Do not vendor `fastchess` into `src/`** — keep it as an external dev tool so the engine tree stays a clean Stockfish derivative.
- [ ] **Tag the release**: `git tag v1.0-event` on the exact commit you build the competition binary from, and note the tag in `NOTICE`. This is what makes "we declare commit X" verifiable.
- [ ] **Authorship evidence** (Rule 2, not GPL): `docs/time-management.md` (algorithm + state diagram, Portuguese), a `git log --stat` showing `timeman.cpp` rewritten, and the SPRT/clock-remaining evidence. This is a *competition* requirement, not a licence one — but it is the one that decides whether you place.

## Verified Empirical Data

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
- Python 3.14 execution of `python-chess` 1.11.2 — no `pip` in this sandbox. Mitigation: pin 3.12 and vendor the package.
- Clang build of `sf_19` — no Clang installed. Mitigation: use GCC.
- PGO speedup on the target laptop — measured wall-clock 2 m 47 s on this 12-thread box, but the sandbox was too noisy to quantify the nps gain (bench ranged 280–350 knps).
- Exact throughput on the team's laptop — scale the ~1,000 games/h figure by core count and clock.
- fastchess's precise speed advantage over cutechess-cli in games/s (no published benchmark) — the decision rests on dependency weight, concurrency behaviour, and SPRT features, which are documented.

<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->

## Conventions

Conventions not yet established. Will populate as patterns emerge during development.
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->

## Architecture

Architecture not yet mapped. Follow existing patterns found in the codebase.
<!-- GSD:architecture-end -->

<!-- GSD:skills-start source:skills/ -->

## Project Skills

No project skills found. Add skills to any of: `.claude/skills/`, `.agents/skills/`, `.cursor/skills/`, `.github/skills/`, or `.codex/skills/` with a `SKILL.md` index file.
<!-- GSD:skills-end -->

<!-- GSD:workflow-start source:GSD defaults -->

## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd-fast` for a trivial task inline, with no subagents and no PLAN.md
- `/gsd-quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd-debug` for investigation and bug fixing
- `/gsd-execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->

<!-- GSD:profile-start -->

## Developer Profile

> Profile not yet configured. Run `/gsd-profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
