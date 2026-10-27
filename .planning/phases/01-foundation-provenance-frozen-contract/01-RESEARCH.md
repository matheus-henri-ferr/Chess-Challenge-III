# Phase 1: Foundation, Provenance & Frozen Contract — Research

**Researched:** 2026-10-26
**Domain:** GPLv3 compliance provenance, offline build reproducibility, frozen UCI/log contract, Rule 4 ceiling guard, offline test harness, dependency vendoring — for a Stockfish 19 fork
**Confidence:** HIGH

> No `CONTEXT.md` exists for this phase (`.planning/phases/01-foundation-provenance-frozen-contract/` was empty at research time). There are therefore no locked user decisions beyond `AGENTS.md`, `.planning/PROJECT.md`, `REQUIREMENTS.md` and `ROADMAP.md`.

## Summary

Phase 1 is a *fifteen-artefact* phase disguised as a compliance chore. Nothing here produces Elo, but every item is either retroactive (a Rule 1/4 breach discovered after a game is a loss or a DQ) or a shared dependency (both `docs/PROTOCOL.md` and `docs/LOGBOOK.md` are inputs to all three tracks on day 0). The research below converts each requirement into a **machine-checkable artefact** so the phase's gate is a script exit code, not a human opinion.

Three findings change the plan shape and are worth stating up front.

**First: `unshare -n make -j` as written in ROADMAP success criterion 1 cannot pass, and the reason is not the network.** There is no `Makefile` at the repository root, and `src/Makefile`'s *default* goal is `help` (`src/Makefile:1007`), so a bare `make -j` prints a tutorial and builds nothing while exiting `0` — verified: after `rm -f stockfish`, `make -j` left `stockfish` absent with `BARE_EXIT=0`. The correct command is `make -C src -j build`. That command was run end-to-end under `unshare -rn` in a fresh clone: build succeeded, `bench` reproduced **2,497,913** nodes exactly, and a second clean build produced a **byte-identical** binary (`sha256 077d3601b503c369f97ed06df73cd5f3b44fd3d3fa513e31c92065da992c4a79`, 99,358,768 B). Reproducibility is therefore provable, not just claimable. Note also that plain `unshare -n` fails in this sandbox (`Operation not permitted`, needs CAP_SYS_ADMIN) whereas `unshare -rn` succeeds; on the match laptop `sudo unshare -n` is the equivalent.

**Second: `SyzygyProbeLimit` compression to 5 must be done as a *default+max clamp plus an assertion*, and the assertion has to sit where a violation can still be fatal.** Three candidate insertion points were prototyped and compiled. Changing only the option declaration (`Option(7, 0, 7)` → `Option(5, 0, 5)`, `src/engine.cpp:133`) is the least invasive change that closes the hole, because `Option::operator=` rejects out-of-range values and *keeps the previous value* (`src/ucioption.cpp:155-158`), so `setoption name SyzygyProbeLimit value 7` becomes a no-op rather than a violation. But a silent no-op is exactly the failure mode that loses the hearing. The working design (built and tested) adds a `Tablebases::TB_PROBE_LIMIT = 5` constant, a `Engine::verify_tb_ceiling()` helper, an `on_change` hook on `SyzygyPath` that `exit(1)`s on a breach, and an `info string` attestation. Bench node count is unchanged at **2,497,913** after the patch.

**Third: `scripts/net.sh` cannot fail the build.** `fetch_network` ends in `return 1` (`scripts/net.sh:74`) and the call at `scripts/net.sh:77` discards that status, so `make net` prints "Failed to download" and exits **0** — verified twice (`MAKE_NET_EXIT=0`, `status=0`). The failure only surfaces much later as a linker error: `Error: file not found: nn-1a298aa575a0.nnue` at the `-flto` link step. So FOUND-04's evidence cannot be "`make net` succeeded"; it must be "`make -C src -j build` succeeded **and** `bench` matched **and** the binary has no external net dependency". That distinction is the whole point of the requirement and is easy to get wrong.

**Primary recommendation:** Freeze the phase as three plans in this order — (01-01) provenance + NOTICE + GPL marking + reproducible offline build proof; (01-02) the two frozen documents + both mocks + the stock binary hand-off; (01-03) the Rule 4 guard, the `doctor` stub, fastchess, and publication/USB dry run. Put every acceptance criterion behind a script that exits nonzero, and make `./scripts/gate0.sh` the single Phase-1 gate (`tools/check_phase1.py` is its Python body). The stock binary must be built and handed out **before** 01-03 patches `src/engine.cpp`, or the "unmodified binary in hour 1" promise in ROADMAP breaks.

## Architectural Responsibility Map

| Capability | Tier | Rationale |
|---|---|---|
| FOUND-01 `NOTICE` (base URL, tag, SHA, fork date, modified files, build cmd, ARCH, compiler, bench) | **repo/compliance (git + docs)** | It is a git-and-docs artefact; the facts are derived from `git rev-parse` and one build log, never from runtime code. |
| FOUND-02 GPL marking + `Copying.txt`/`AUTHORS` integrity + `check_license.sh` | **repo/compliance (git + docs)** | GPLv3 §§4–5(a) obligations attach to files and notices; the checker is a repo-level gate, not a runtime feature. |
| FOUND-03 `PROVENANCE.md` (NNUE identity, TB inventory, dependency manifest) | **repo/compliance (git + docs)** | Declarative; consumed by the panel and by `doctor`, produced by nobody at runtime. |
| FOUND-04 offline build proof | **engine (C++)** + **dev tooling (Python)** | The build itself is the C++ toolchain's job; the *proof* (hash, bench, log capture) is a small reproducible script. |
| FOUND-05 `docs/PROTOCOL.md` + `docs/LOGBOOK.md` frozen | **repo/compliance (git + docs)** | Two versioned documents whose git ordering is the proof. Content is jointly owned by all tiers, authorship is repo-level. |
| FOUND-06 publication dry run + USB archive | **repo/compliance (git + docs)** | A mirror, a `RELEASE/` tree and a `SHA256SUMS` manifest. No code path is involved. |
| LIMIT-01 `SyzygyProbeLimit=5` + `MaxCardinality` assert | **engine (C++)** | The ceiling is enforced inside the process that probes; a console-side check alone cannot stop a `setoption` from re-raising it. |
| LIMIT-04 offline/asset `doctor` stub | **dev tooling (Python)** | Startup pre-flight over filesystem paths and hashes; grows into Phase 3 `CHECK-01`. Must not be part of the in-game engine. |
| PIPE-01 fastchess installed + SPRT recipe recorded | **harness (fastchess)** | Third-party MIT binary, dev-only, never shipped inside the engine tree. |
| `mock_engine.py` (scriptable fake engine) | **dev tooling (Python)** | Unblocks the console track; must not import the console code under test. |
| `mock_gui.py` (drives a real engine through the frozen contract) | **dev tooling (Python)** | Unblocks the TM track without the console; consumes the frozen `go` line. |
| `vendor/chess/` (python-chess offline copy) | **repo/compliance (git + docs)** | A vendored third-party dependency plus its declared hash; it is a Rule 14 declaration before it is a library. |
| Frozen contract *consumption* (`go` line, `tm=` trace, log schema) | **console (Python)** | The console is the sole author of `go` lines and the sole writer of the Rule 9 log; the engine only attests. |

## Standard Stack

### Core

| Item | Version / identity | Purpose | Why this, not an alternative | Provenance |
|---|---|---|---|---|
| Stockfish base | tag `sf_19` = `edb0d9db6731067ec50ce619ff372b463bc4dd5d` | Fork base | Full 7,252-commit upstream history is present (not shallow: `.git/shallow` absent, `git rev-list --count sf_19` = 7252) | `[VERIFIED: git rev-list sf_19]` |
| Project branch base commit | `0ef8529b` "chore: import Stockfish sf_19 history as project base" | First project commit | Its blob hashes for `Copying.txt`/`AUTHORS` still match `sf_19` | `[VERIFIED: git rev-parse sf_19:Copying.txt HEAD:Copying.txt]` |
| NNUE net | `nn-1a298aa575a0.nnue`, 98,511,183 B, sha256 `1a298aa575a085434d29027978dc36867fe9c5bcea9376654b7a8eba1e52dfc2` | Evaluation | Embedded verbatim by `INCBIN`; `export_net` round-trip is byte-identical | `[VERIFIED: src/nnue/network.cpp:49-50; cmp of exported net]` |
| Compiler | GCC 16.2.1 | C++17 toolchain | Already proven at this version | `[VERIFIED: gcc --version]` |
| Make target | `make -C src -j build` | Build | `build` is the only goal that depends on `net` *and* links | `[VERIFIED: src/Makefile:1100]` |
| Python | 3.14.7 (system), `pip 26.2.1` inside a venv | Console, tooling, mocks | `python3 -m venv` supplies pip even though `python3 -m pip` on the system interpreter fails | `[VERIFIED: python3 -m venv + venv/bin/pip --version]` |
| `python-chess` | 1.11.2 (`chess`) | Board replica, UCI client, Polyglot, Syzygy | GPL-3.0+, zero runtime deps, `IllegalMoveError`/`InvalidMoveError`/`AmbiguousMoveError` are the typed rejects PROTO-01 needs | `[VERIFIED: PyPI JSON — requires_dist: None, license: GPL-3.0+, requires_python: >=3.8]` |
| fastchess | `v1.8.2-alpha`, binary `fastchess alpha 1.8.2 compiled for ubuntu-22.04 20260726-f618e34 (CI)` | SPRT / match runner | Release tarball ships a prebuilt static-ish binary *and* full source — no compile, no deps | `[VERIFIED: ./fastchess --version; tarball listing]` |

### Supporting

| Item | Version | Purpose | When to use | Provenance |
|---|---|---|---|---|
| `chess.polyglot` | in 1.11.2 | Read Polyglot `.bin` | Competition book lookup (Phase 3+). **No writer** — the `.bin` writer is our own ~40-line tool. | `[VERIFIED: chess/polyglot.py present in vendored tree]` |
| `chess.syzygy` | in 1.11.2 | Probe TB offline | Test positions only; never during a game (the engine already probes) | `[VERIFIED: chess/syzygy.py present]` |
| `unittest` (stdlib) | 3.14.7 | Test runner for Phase 1 checks | Phase 1 only. `pytest` is **not installed** and cannot be installed offline (see below). | `[VERIFIED: python3 -c "import unittest"]` |
| `unshare` | util-linux, present | Network-namespace build proof | `sudo unshare -n` on the laptop; `unshare -rn` in an unprivileged sandbox | `[VERIFIED: unshare -rn true → 0; unshare -n true → 1]` |

### Alternatives Considered

| Instead of | Could use | Trade-off / verdict |
|---|---|---|
| `unshare -rn` | `unshare -n` with sudo | Prefer `sudo unshare -n` on the match laptop — no user-namespace dependency, and it matches what the arbiter will accept. `-r` only for CI/sandbox. |
| vendored `vendor/chess/` | `pip install` from a local wheel | **Rejected.** Verified dead end: `pip install --no-index chess-1.11.2.tar.gz` fails with `BackendUnavailable: Cannot import 'setuptools.build_meta'` — setuptools is not available offline. |
| vendored `vendor/chess/` | `pip install --no-index` from a prebuilt `.whl` | Viable *if* a wheel exists. PyPI publishes **only an sdist** for 1.11.2 (verified: `packagetype: sdist` is the sole entry). A wheel does exist in this machine's pip cache but is a local artefact, not reproducible from a public URL. |
| Release tarball binary | `make -j` fastchess from source | Both are in the same tarball. Use the prebuilt binary (11 s of nothing vs 1 m 41 s) and keep the source for MIT compliance. |
| `tools/doctor.py` | fold checks into the console | **Rejected.** Phase 1 has no console. A standalone stdlib script is reachable by all three tracks and grows into CHECK-01 by adding checks, not by moving code. |
| `tools/mock_engine.py` under `tools/` | `console/tests/fixtures/` per `ARCHITECTURE.md` §6 | Deliberate deviation — see OQ-10. Phase 1 must not create a `console/` tree that Phase 2 then re-shapes. |

### Installation (all offline-safe, run before the event)

```bash
# 1) Engine base — already cloned; nothing to install.
git -C . rev-parse sf_19            # edb0d9db6731067ec50ce619ff372b463bc4dd5d

# 2) python-chess — vendor the package directory, do not pip-install
curl -sL -o /tmp/chess-1.11.2.tar.gz \
  https://files.pythonhosted.org/packages/93/09/7d04d7581ae3bb8b598017941781bceb7959dd1b13e3ebf7b6a2cd843bc9/chess-1.11.2.tar.gz
sha256sum /tmp/chess-1.11.2.tar.gz   # expect a8b43e5678fdb3000695bdaa573117ad683761e5ca38e591c4826eba6d25bb39 (6,131,385 B)
mkdir -p vendor && tar xzf /tmp/chess-1.11.2.tar.gz -C /tmp
cp -r /tmp/chess-1.11.2/chess vendor/chess
rm -rf vendor/chess/__pycache__
cp /tmp/chess-1.11.2/LICENSE.txt vendor/chess/LICENSE.txt

# 3) fastchess — tarball contains both the binary and the source
curl -sL -o /tmp/fastchess.tar \
  https://github.com/Disservin/fastchess/releases/download/v1.8.2-alpha/fastchess-linux-x86-64.tar
sha256sum /tmp/fastchess.tar          # expect 1003f920bebe841acdab5e6d7871e93171a4586857b3ec91c21ef5777f26ff96
tar xf /tmp/fastchess.tar -C tools/
tools/fastchess-linux-x86-64/fastchess --version
```

**Version verification (run in this session):**

| Package | Command | Result |
|---|---|---|
| `chess` | `curl -s https://pypi.org/pypi/chess/json` | `version: 1.11.2`, `requires_python: >=3.8`, `requires_dist: None`, file `chess-1.11.2.tar.gz` sha256 `a8b43e5678fdb3000695bdaa573117ad683761e5ca38e591c4826eba6d25bb39` |
| fastchess | GitHub releases API | `v1.8.2-alpha` published `2026-07-26T19:21:45Z`, `fastchess-linux-x86-64.tar` 14,612,480 B |
| fastchess binary | `sha256sum`, `--version` | `3d0a8f3c8b837a96366ac838f3ddf6fe87b813abb4ad2852284c0ce409132566`, reports `alpha 1.8.2 ... 20260726-f618e34 (CI)` |

## Package Legitimacy Audit

Both third-party artefacts are **released binaries/sdists from the projects' own canonical distribution channels**, verified by hand in this session. `gsd-tools query package-legitimacy check` was not reachable from this subagent's tool surface (no `gsd_run` seam available), so each verdict below is an explicit manual substitute with the evidence that produced it.

| Package | Registry / channel | Age signal | Community signal | Source repo | Verdict | Disposition |
|---|---|---|---|---|---|---|
| `chess` 1.11.2 | PyPI (`chess-1.11.2.tar.gz`) | PyPI last-serial 27,643,003; `python-chess` is the canonical library, docs at python-chess.readthedocs.io | The de-facto Python chess library; `GPL-3.0+` declared in metadata | `github.com/niklasf/python-chess` (linked from PKG-INFO) | **OK (manual)** | Approved — vendored, not installed |
| `fastchess` v1.8.2-alpha | GitHub Releases (`Disservin/fastchess`) | `v1.8.2-alpha` 2026-07-26; release series `v1.7.0-alpha` → `v1.8.2-alpha` | Cited by the official Stockfish docs (`official-stockfish.github.io/docs/fishtest-wiki/Running-Fastchess.html`) | `github.com/Disservin/fastchess` (same org as release) | **OK (manual)** | Approved — dev-only, external to `src/` |
| `setuptools` (would be needed for `pip install`) | — | — | — | — | **N/A** | Not used; vendoring avoids it |
| `pytest` | — | — | — | — | **Not installed / do not add** | Use stdlib `unittest` |

**Packages removed due to [SLOP] verdict:** none.
**Packages flagged as suspicious [SUS]:** none.

**No `postinstall` scripts apply** — there is no npm layer in this phase. The only executable third-party artefact is the fastchess binary; it was run in this session and behaves as documented (`--version`, a 2-game match, an SPRT run).

⚠️ **Phase-1 installs are all pre-event, online-allowed, and must be **hashed into `PROVENANCE.md`** at install time. Nothing is installed during a game.

## Architecture Patterns

### System Architecture Diagram

Phase 1 creates no game path. It creates **one build pipeline**, **two frozen documents**, and **three checkers** around them. Everything flows toward a day-0 gate that three tracks can consume independently.

```
                    git clone --branch sf_19  (history present, tag base-sf19)
                                   │
                                   ▼
              ┌────────────────────────────────────────────┐
              │      vendor/chess/  +  src/nn-*.nnue       │
              │   (both committed; both hashed into        │
              │    PROVENANCE.md; net un-ignored in        │
              │    .gitignore)                             │
              └───────────────────┬────────────────────────┘
                                  │
                    make -C src -j build  (offline)
                                  │
              ┌───────────────────┴───────────────────┐
              ▼                                       ▼
     src/stockfish  (99 MB)                   scripts/net.sh invoked by
     net embedded via INCBIN                  the `net` prerequisite —
              │                                validated, not downloaded
              │                                (prints "existing … validated")
              ▼
     ./src/stockfish bench  ──►  "Nodes searched  : 2497913"
              │
              ▼
   ┌──────────────────────────────────────────────────────────┐
   │  ARTEFACT SET (all committed; all machine-checkable)      │
   │  NOTICE   PROVENANCE.md   docs/PROTOCOL.md                │
   │  docs/LOGBOOK.md   vendor/chess/   tools/fastchess*       │
   └─────┬───────────────┬──────────────┬──────────────┬───────┘
         │               │              │              │
         ▼               ▼              ▼              ▼
   check_license.sh   doctor.py    mock_gui.py    mock_engine.py
   check_notice.py    (LIMIT-04)   (TM track)     (console track)
   (FOUND-01/02)           │
         │                 └──► grows into CHECK-01 in Phase 3
         ▼
   Phase-1 gate: `./scripts/gate0.sh` exits 0
```

**Data flow through the gate.** `git rev-parse` → `NOTICE`/`PROVENANCE.md` fields; a single captured build log → `NOTICE`'s build-command + compiler + ARCH + bench lines; the vendored net → both `PROVENANCE.md`'s SHA-256 and `doctor.py`'s runtime expectation; the two frozen docs → the mocks' vocabularies and the Phase-2/4 implementations. No arrow runs backwards: no runtime code may write a provenance field, and no document may be regenerated from a running engine.

### Recommended Project Structure (Phase 1 delta only)

```
ChessChallendIII/
├── NOTICE                          # NEW — FOUND-01
├── PROVENANCE.md                   # NEW — FOUND-03
├── MAKE.md                         # NEW (optional; NOTICE holds the build facts)
├── docs/
│   ├── competition-rules.md        # existing, untouched
│   ├── PROTOCOL.md                 # NEW — FROZEN — FOUND-05
│   └── LOGBOOK.md                  # NEW — FROZEN — FOUND-05
├── vendor/
│   └── chess/                      # NEW — python-chess 1.11.2, verbatim + LICENSE.txt
├── tools/                          # EMPTY today; Phase 1 fills it
│   ├── doctor.py                   # NEW — LIMIT-04 (→ CHECK-01)
│   ├── mock_engine.py              # NEW — console track unblocker
│   ├── mock_gui.py                 # NEW — TM track unblocker
│   ├── fastchess-linux-x86-64/     # NEW — PIPE-01 (dev-only, never in src/)
│   ├── sprt.md                     # NEW — the recorded recipe (PIPE-01)
│   ├── check_notice.py             # NEW — FOUND-01 machine check
│   ├── check_license.py            # NEW — FOUND-02 machine check
│   ├── check_provenance.py         # NEW — FOUND-03 machine check
│   ├── check_offline_build.py      # NEW — FOUND-04 evidence producer
│   ├── check_contract_order.py     # NEW — FOUND-05 git-ordering proof
│   ├── build_manifest.py           # NEW — FOUND-03/06 SHA-256 inventory
│   ├── check_phase1.py             # NEW — runs all checkers, one exit code
│   └── tests/                      # NEW — unittest cases for doctor.py + checkers
├── scripts/
│   ├── check_license.sh            # NEW — PITFALLS.md names this exact path
│   └── gate0.sh                    # NEW — THE Phase-1 gate; wraps check_phase1.py
├── evidence/
│   └── 01-offline-build.log        # NEW — captured, committed build+bench log
└── RELEASE/                        # NEW — FOUND-06; may be gitignored if >host limit
    ├── SHA256SUMS
    └── README.md
```

**Why `tools/` and not `console/`:** Phase 1 must not pre-create the Phase-2 tree. `ARCHITECTURE.md` §6 proposes `console/tests/fixtures/mock_engine.py`, but creating `console/` on day 0 creates an empty package that Phase 2 will restructure — and both mocks are *consumers* of the frozen contract, not part of the console. `tools/` is a flat, importable-by-path directory that Phase 2 can symlink or move without touching content. Deviation is recorded in `docs/` and in OQ-10.

### Pattern 1: Evidence-as-artefact

**What:** Every requirement's acceptance is produced by a script that writes a committed file and exits nonzero on failure. The gate runs all of them.
**When to use:** Every FOUND-* and LIMIT-* item in this phase.
**Why:** Compliance claims that live in prose cannot be re-verified after the fact, and the panel's question is always "show me". A committed `evidence/*.log` plus a `check_*.py` that re-derives it is the smallest thing that survives an audit.

```python
# tools/check_notice.py — shape only; the planner fixes the exact regexes
import re, subprocess, sys, pathlib

BASE_SHA = "edb0d9db6731067ec50ce619ff372b463bc4dd5d"
notice = pathlib.Path("NOTICE").read_text(encoding="utf-8")

def must(pattern, label):
    if not re.search(pattern, notice, re.MULTILINE):
        sys.exit(f"FAIL NOTICE: missing {label}")
    return label

must(r"^Base project:\s*https://github\.com/official-stockfish/Stockfish\s*$", "base URL")
must(rf"^Base tag:\s*sf_19\s*$", "base tag")
must(rf"^Base commit:\s*{BASE_SHA}\s*$", "full 40-hex base commit")
must(r"^Fork date:\s*\d{4}-\d{2}-\d{2}\s*$", "fork date")
must(r"^Build command:\s*make -C src -j\d* build\s*$", "build command")
must(r"^ARCH:\s*x86-64-avx[a-z0-9-]*\s*$", "ARCH")
must(r"^Compiler:\s*g\+\+ \(GNUC\) \d+\.\d+\.\d+.*$", "compiler")
must(r"^Bench nodes:\s*2497913\s*$", "bench node count")
must(r"^Modified files:\s*$", "modified-files heading")
print("OK NOTICE")
```

### Pattern 2: Clamp-then-assert (the Rule 4 ceiling)

**What:** Make the illegal value unreachable, *then* assert that it was not reached, and make the assertion loud.
**When to use:** LIMIT-01 (`SyzygyProbeLimit`), and again for LIMIT-02/03 in Phase 3.
**Example (built and verified in this session):**

```cpp
// src/syzygy/tbprobe.h  — single source of truth
extern int MaxCardinality;

// ChessChallendIII (Rule 4): the competition permits tablebases of up to 5
// pieces only. This constant is the single source of truth for the ceiling;
// SyzygyProbeLimit's default/min/max and the startup assertion derive from it.
constexpr int TB_PROBE_LIMIT = 5;
```

```cpp
// src/engine.cpp:133 (was Option(7, 0, 7))
options.add("SyzygyProbeLimit", Option(~~Tablebases::TB_PROBE_LIMIT, 0, Tablebases::TB_PROBE_LIMIT));
```

```cpp
// src/engine.cpp — new private helper, declared in engine.h next to verify_network()
std::optional<std::string> Engine::verify_tb_ceiling() const {
    const int requested = int(options["SyzygyProbeLimit"]);
    const int loaded    = Tablebases::MaxCardinality;

    // Rule 4 permits 3-, 4- and 5-piece tablebases. 0 disables probing and is
    // therefore compliant; anything above the ceiling is a violation.
    if (requested > Tablebases::TB_PROBE_LIMIT)
        return "TB CEILING VIOLATION: SyzygyProbeLimit=" + std::to_string(requested)
             + " (max " + std::to_string(Tablebases::TB_PROBE_LIMIT) + ")";

    if (loaded > Tablebases::TB_PROBE_LIMIT)
        return "TB CEILING VIOLATION: tablebase directory contains " + std::to_string(loaded)
             + "-man files (required <= " + std::to_string(Tablebases::TB_PROBE_LIMIT) + ")";

    return "TB ceiling OK: SyzygyProbeLimit=" + std::to_string(requested)
         + " max_loaded=" + std::to_string(loaded);
}
```

Wire it in three places (`src/engine.cpp`):

1. **`SyzygyPath` on_change** — `Tablebases::init(o)` runs first (it populates `MaxCardinality`), then the check; a violation prints `info string CRITICAL ERROR: …` and `std::exit(1)`. This is the load-time gate. Verified: with a planted 6-man filename the engine exits **1** and prints `info string CRITICAL ERROR: TB CEILING VIOLATION: tablebase directory contains 6-man files (required <= 5)`.
2. **`Engine::go()`** — after `verify_network()`, report via `onVerifyNetwork` so the attestation lands on stdout as `info string` at the top of every search.
3. **`Engine::search_clear()`** — after `Tablebases::init(options["SyzygyPath"])`, same report. This covers `ucinewgame` re-initialisation.

**Verified outcomes of this design:**

| Stimulus | Before patch | After patch |
|---|---|---|
| `uci` option listing | `option name SyzygyProbeLimit type spin default 7 min 0 max 7` | `… default 5 min 0 max 5` |
| `setoption … SyzygyProbeLimit value 7` | accepted, 7-piece probing enabled | **silently clamped** (`src/ucioption.cpp:155-158` returns early); attestation stays `=5` |
| `setoption … SyzygyProbeLimit value 6` | — | clamped; attestation prints `TB ceiling OK: SyzygyProbeLimit=5 max_loaded=0` |
| `setoption … SyzygyProbeLimit value 0` | accepted | accepted, attestation `… =0 max_loaded=0` (TB disabled is compliant) |
| `SyzygyPath` containing a 6-man `.rtbw` | engine loads it, `MaxCardinality=6` | **`info string CRITICAL ERROR: TB CEILING VIOLATION …`, `exit 1`** |
| `./stockfish bench` | 2,497,913 | **2,497,913** (unchanged) |

### Pattern 3: Frozen-document git ordering as proof

**What:** The freeze date is not a claim in the text — it is `git log` output. Two `docs/` commits must be strict ancestors of the first implementation commit.
**When to use:** FOUND-05, and re-used by TM-02 in Phase 4.
**Example:**

```python
# tools/check_contract_order.py
import subprocess, sys

def rev(expr):
    return subprocess.run(["git", "rev-parse", expr], capture_output=True,
                          text=True, check=True).stdout.strip()

docs_commit  = rev("$(git log --format=%H --reverse --all -- docs/PROTOCOL.md docs/LOGBOOK.md | head -1)")
impl_paths   = ["src/", "tools/", "console/", "pipeline/"]
first_impl   = subprocess.run(
    ["git", "log", "--format=%H", "--reverse", "--all", "--", *impl_paths],
    capture_output=True, text=True, check=True).stdout.split()

if not first_impl:
    print("no implementation commit yet — ordering vacuously OK at Gate 0")
    sys.exit(0)

import pathlib
# `git merge-base --is-ancestor A B` exits 0 when A is an ancestor of B
rc = subprocess.run(["git", "merge-base", "--is-ancestor", docs_commit, first_impl[0]]).returncode
sys.exit(0 if rc == 0 else "FAIL: docs/ committed after first implementation commit")
```

**Caveat the planner must encode:** `tools/` is the natural home for the mocks and checkers, and it is also the first "implementation" path. Pick the impl-path list deliberately — the cleanest rule is **`src/` and `console/` only**. Mocks and checkers are contract *consumers*, and requiring them to postdate the contract is exactly right; requiring `tools/` as a whole to postdate it makes the check unpassable in the same commit that adds the docs. Resolution: impl-path set is `src/`, `console/`, `pipeline/` — never `tools/` or `scripts/`.

### Anti-Patterns to Avoid

- **Writing `NOTICE` by hand from memory.** Every field must be produced by a command whose output is pasted, and a checker must re-derive it. A hand-typed 40-hex SHA is wrong eventually and unrecoverable once the panel reads it.
- **Claiming `make net` proves offline.** It exits 0 on total network failure (`scripts/net.sh:77` discards the `return 1`). Only a full `build` + `bench` proves it.
- **Rewriting or reflowing an upstream GPL header.** `Copying.txt` and `AUTHORS` blobs are currently byte-identical to `sf_19` (`f288702d…`, `b5ad83d5…`). Any edit to either is a licence problem and a narrative problem; add your line *below* the header block, never inside it.
- **Putting the ceiling check only in the console.** `setoption` is an engine-side surface; a console-side assertion cannot stop a stray `setoption`, a debug session, or `fastchess` passing options.
- **Making `make -j` the documented build command.** It is a no-op that exits 0 — the most dangerous possible failure signature.
- **Freezing `PROTOCOL.md` from `ARCHITECTURE.md`'s examples without reconciling names.** The research doc uses `TiebreakBias`/`MinThinkMs`/`info string TM`; the requirement text (TM-11) uses `info string tm=custom-vX.Y mode=… latency_p95_ms=… bank_ms=… budget_ms=… reason=…`. The frozen doc must pick **one**, and TM-11's shape must win because it is the graded contract.

## Don't Hand-Roll

| Problem | Don't build | Use instead | Why |
|---|---|---|---|
| Board legality / FEN / SAN ambiguity | a hand-rolled move validator | `python-chess` 1.11.2 vendored | `parse_uci` already raises `IllegalMoveError` with the offending token; `parse_san` handles SAN; `AmbiguousMoveError` is exactly the PROTO-01 requirement. 812 KB of pure Python, zero deps. |
| UCI `info` line parsing | a regex | a small explicit tokeniser modelled on `chess.engine._parse_uci_info` | That function already handles `lowerbound`/`upperbound` (`chess/engine.py:1833`) and divides `time` ms → s (`:1819`). Copying its *structure* is safe; importing `chess.engine` in the console is fine too (GPL-compatible). Do **not** import it in mocks that must stay minimal. |
| Polyglot `.bin` reading | a parser | `chess.polyglot` | Zobrist constants, castling `e1h1` encoding and en-passant semantics are a bug farm |
| SPRT statistics | a match runner | fastchess `-sprt` | pentanomial reporting, resume, crash recovery — all built in |
| SHA-256 inventory of a directory | a bespoke walker | `sha256sum $(git ls-files …)` + `tools/build_manifest.py` sorting output | Determinism matters: sort by path, use fixed-width output |
| A network-namespace harness | a socket-blocking shim | `sudo unshare -n` | Namespace isolation is stronger and is what an auditor will re-run |
| Wheels/installs | `pip install` at the venue | `vendor/chess/` committed | Verified: `pip install` from sdist fails offline (`BackendUnavailable: Cannot import 'setuptools.build_meta'`) |

**Key insight:** every "hand-roll" temptation in this phase is a place where a wrong answer is silent. A wrong Polyglot hash yields an opening book that plays nothing (looks like a bad book); a wrong legality check yields a corrupt board; a hand-typed SHA yields a provenance failure discovered by the panel. Buy the standard libraries and spend the saved days on the time manager.

## Runtime State Inventory

> Phase 1 is a **rename/refactor-adjacent** phase: it changes the *identity* of the tree (a Stockfish clone becomes a named fork with declared provenance and a changed UCI option default). The inventory below answers "after every file in the repo is updated, what runtime systems still carry the old state?"

| Category | Items Found | Action Required |
|---|---|---|
| **Stored data** | None. No database, no datastore, no cache keyed by the fork name. Verified: `grep -rn "ChessChallend" src/` returns nothing; there is no persistence layer in the engine. | None. Explicitly verified, not skipped. |
| **Live service config** | None. No n8n/Datadog/Tailscale/Cloudflare equivalents; the project is offline by rule. The only "service config" is the git remote: `remote.upstream.url=https://github.com/official-stockfish/Stockfish` (a read-only provenance remote that must be **kept**). | Keep `upstream`; **add** the team's own `origin` when FOUND-06's dry run happens. Do not remove `upstream` — it is how `git diff sf_19` stays re-derivable. |
| **OS-registered state** | None inside Phase 1. No systemd unit, no scheduled task, no pm2 process. The future `doctor`/`ruff` binaries are invoked directly. | None. Verified: no unit files in the repo, and `/etc` is untouched by this phase. |
| **Secrets / env vars** | None. No `.env`, no CI secrets, no SOPS. The build reads only `GIT_SHA`/`GIT_DATE`/`GIT_DIFFINDEX` which the Makefile derives (`src/Makefile:915-917`) and caches to `src/.build_*.txt` (**gitignored**: `.gitignore:7-9`). | None. But **note the consequence**: the cached `.build_sha.txt` currently holds `0ef8529b` and `misc.o` was compiled with `-DGIT_SHA=0ef8529b`, so the shipped binary's `id name` says `Stockfish 19` (release builds omit the SHA — `src/misc.cpp:145`) while `/tmp/opencode/offline-test`'s build embedded `a2f963bf`. **`engine_info()` never reveals the SHA on a release tag**, so the binary cannot self-identify the fork. Consequence for FOUND-01: the fork identity must be declared in `NOTICE`/`PROVENANCE.md`, never inferred from a running engine's `id name`. |
| **Build artefacts / installed packages** | (a) `src/*.o` and `src/stockfish` are present and stale relative to any upcoming `engine.cpp` edit; (b) `src/temp_builds` is absent but created by universal builds; (c) `src/.depend`, `src/.build_*.txt` are gitignored and will go stale; (d) `vendor/chess/__pycache__` must not be committed. | (a) `make -C src objclean` before the reproducible-build proof so both runs start clean; (b) leave absent; (c) delete before archiving; (d) add `vendor/**/__pycache__/` to `.gitignore` (the existing bare `__pycache__/` pattern at `.gitignore:23` already covers nested paths, since a gitignore pattern containing no slash matches at every level). |

**The canonical question, answered:** *After every file in the repo is updated, what runtime systems still have the old string cached, stored, or registered?* → **Only the compiled `.o` files and the linked binary**, because the engine has no persistent state. Consequence for the plan: the offline-build proof must start from `objclean` (or a fresh clone), otherwise it proves nothing but that `make` skipped work.

## Common Pitfalls

### Pitfall 1: `make -j` is a successful no-op
**What goes wrong:** The gate command in ROADMAP criterion 1 (`unshare -n make -j`) exits `0` having built nothing, because `src/Makefile:1007`'s `help:` target is the default goal and there is no root Makefile.
**Why it happens:** Stockfish requires an explicit target (`build`, `profile-build`, `analyze`); `make` at the repo root fails with "no targets", and `make -C src` prints the tutorial.
**How to avoid:** Use `make -C src -j build` everywhere, and have the evidence script assert the binary's mtime and sha256 changed.
**Warning signs:** Binary absent after a "successful" build (verified: `BARE_EXIT=0`, `NO BINARY`); build log containing `To compile stockfish, type:`.

### Pitfall 2: `net.sh` swallows download failure, so `make net` cannot gate anything
**What goes wrong:** With the net deleted and networking severed, `make -C src net` exits **0** after printing two download failures; the real failure appears minutes later as `/tmp/cc*.s:26: Error: file not found: nn-1a298aa575a0.nnue` at link time.
**Why it happens:** `fetch_network` ends `return 1` (`scripts/net.sh:74`) and the top-level call (`scripts/net.sh:77`) ignores its status.
**How to avoid:** Never gate on `make net`. Gate on `make -C src -j build` (which links, and therefore fails) plus a bench match. Optionally add `scripts/check_net.sh` that asserts the file exists with the right SHA-256 *before* the build, so the failure is early and legible.
**Warning signs:** A build log where `Failed to download` appears above a successful `g++ -o stockfish`.

### Pitfall 3: The binary cannot prove which commit it is
**What goes wrong:** On a release tag, `engine_version_info()` emits `Stockfish 19` with **no** `-SHA` suffix (`src/misc.cpp:145`: `if constexpr (version == "dev")` guards the whole git block), so the panel cannot tie the shipped binary to a commit by asking the binary.
**Why it happens:** Upstream deliberately drops the SHA for release builds.
**How to avoid:** Do not edit `misc.cpp` in Phase 1 (that would be a touched file needing a GPL modification line for no compliance gain). Instead: `NOTICE` records `sha256` of the exact shipped binary and of `src/stockfish`'s build inputs; `doctor.py` prints `--license`-style identity plus the binary hash; and the runbook verifies the hash. If a self-identifying string is wanted later, Phase 4 does it — with the GPL line.
**Warning signs:** `strings src/stockfish | grep <sha8>` returns nothing (verified: `grep -c "0ef8529b"` → 0).

### Pitfall 4: `Copying.txt` / `AUTHORS` drift is undetectable without a baseline
**What goes wrong:** Someone "cleans" `AUTHORS`, or an editor normalises line endings (`.gitattributes:2` sets `* text=auto eol=lf`, which rewrites on checkout on some setups), and there is no way to notice before the panel does.
**Why it happens:** Nobody records the expected blob.
**How to avoid:** The baseline is *git*, not a new file. `git diff sf_19..HEAD -- Copying.txt AUTHORS` is empty today (verified) and must stay empty; `check_license.py` asserts `git rev-parse sf_19:<path> == git rev-parse HEAD:<path>` for both. Recording a separate `.sha256` file is redundant and creates a second thing to drift.
**Warning signs:** Non-empty `git diff sf_19..HEAD -- Copying.txt AUTHORS`; a `LICENSE` file appearing next to `Copying.txt` (harmless only if it is a copy, not a replacement).

### Pitfall 5: A `SyzygyProbeLimit` change that is silenced by option clamping
**What goes wrong:** Because `Option::operator=` returns early on an out-of-range spin value (`src/ucioption.cpp:155-158`), the naive test "set it to 7 and assert the engine refuses" **passes trivially** — the engine keeps 5 and says nothing. A test written that way cannot distinguish "clamped" from "ignored entirely".
**Why it happens:** `setoption` has no error channel in UCI.
**How to avoid:** Test the *observable consequence*: `(a)` the `uci` listing says `default 5 min 0 max 5`; `(b)` after `setoption … value 7`, the attestation line still reads `SyzygyProbeLimit=5`; `(c)` a TB directory with a 6-man filename makes the process exit `1` with `CRITICAL ERROR`; `(d)` `bench` is still 2,497,913.
**Warning signs:** A test that only checks exit code of `setoption`.

### Pitfall 6: `unshare -n` needs privilege the developer may not have
**What goes wrong:** `unshare -n true` returns `Operation not permitted` (verified, uid 1000, no passwordless sudo). A CI or a scripted check that assumes it works will fail for the wrong reason.
**Why it happens:** `CLONE_NEWNET` requires `CAP_SYS_ADMIN` unless a user namespace is also created.
**How to avoid:** Try `unshare -n` first; fall back to `unshare -rn`; and record in the evidence log which one ran, because `-r` also remaps the user namespace and slightly changes the environment. On the match laptop use `sudo unshare -n` so the proof matches the auditor's mental model.
**Warning signs:** The offline evidence log contains `Operation not permitted`.

### Pitfall 7: Freezing the contract after the first implementation commit
**What goes wrong:** `PROTOCOL.md`/`LOGBOOK.md` land in the same commit as `mock_engine.py` or `doctor.py`, so `merge-base --is-ancestor` cannot distinguish "frozen first" from "written afterwards", and FOUND-05's evidence evaporates.
**Why it happens:** Natural to do "the docs plus the code they describe" in one commit.
**How to avoid:** 01-02 commits `docs/PROTOCOL.md` + `docs/LOGBOOK.md` **alone**, then a second commit adds the mocks. `check_contract_order.py` asserts ancestor ordering against `src/` and `console/` only.
**Warning signs:** A single commit touching both `docs/PROTOCOL.md` and `tools/`.

### Pitfall 8: Vendoring the sdist leaves build metadata behind
**What goes wrong:** Copying the extracted sdist whole drags in `chess.egg-info/`, `setup.py`, `test.py`, `fuzz/`, `docs/` and a stale `PKG-INFO` — which then shows up in a licence inventory as ambiguous, and in `python3 -m compileall` runs as noise.
**Why it happens:** Untarring is easier than selecting.
**How to avoid:** Copy **only** `chess/` (the package) plus `LICENSE.txt`, and strip `__pycache__`. Verified working: `PYTHONPATH=vendor python3 -c "import chess, chess.engine, chess.polyglot, chess.syzygy"` → `1.11.2 ok`; total 1.2 MB.
**Warning signs:** `vendor/` containing `setup.py`; `chess.egg-info/` in the tree.

### Pitfall 9: `git add` silently skips the net because `.gitignore` already lists `**/*.nnue`
**What goes wrong:** The negation `!src/nn-1a298aa575a0.nnue` is present today, but any future `.gitignore` edit that re-adds a broader pattern above it, or a `.git/info/exclude` entry, will silently un-vendor the net — and the offline build then fails only on a machine with no network.
**Why it happens:** Negation ordering in gitignore is fragile.
**How to avoid:** `tools/check_offline_build.py` asserts `git ls-files --error-unmatch src/nn-1a298aa575a0.nnue` succeeds *and* that the blob exists in `HEAD`, not merely on disk.
**Warning signs:** `git check-ignore -v src/nn-*.nnue` returns a match from any rule other than the negation.

## Code Examples

### Offline build proof (FOUND-04)

```bash
#!/bin/sh
# tools/offline_build.sh — produces evidence/01-offline-build.log
set -eu
CLONE="${1:-$(mktemp -d)/chess}"
NET_LOG="$(mktemp)"

git clone --branch sf_19 "$(git rev-parse --show-toplevel)" "$CLONE"
cd "$CLONE"

# 1) the net must be committed, not downloaded
git ls-files --error-unmatch src/nn-1a298aa575a0.nnue >/dev/null
sha256sum -c <<'EOF'
1a298aa575a085434d29027978dc36867fe9c5bcea9376654b7a8eba1e52dfc2  src/nn-1a298aa575a0.nnue
EOF

# 2) clean room — otherwise the build proves nothing
make -C src objclean

# 3) build with no network at all
if unshare -n true 2>/dev/null; then NS=unshare -n
elif unshare -rn true 2>/dev/null; then NS=unshare -rn
else echo "FATAL: no network namespace available" >&2; exit 1; fi
echo "namespace: $NS" > "$NET_LOG"

$NS make -C src -j"$(nproc)" build 2>&1 | tee -a "$NET_LOG"
test -x src/stockfish

# 4) the net really is inside the binary
src/stockfish --license >/dev/null
printf 'export_net /tmp/net-exported.nnue\nquit\n' | src/stockfish >/dev/null
cmp src/nn-1a298aa575a0.nnue /tmp/net-exported.nnue

# 5) bench must match the declared node count
NODES=$(src/stockfish bench 2>&1 | sed -n 's/^Nodes searched  : //p')
test "$NODES" = "2497913" || { echo "bench mismatch: $NODES" >&2; exit 1; }

# 6) no remote fetch was attempted
! grep -q "Downloading from" "$NET_LOG"
sha256sum src/stockfish >> "$NET_LOG"
cat "$NET_LOG"
```

**Verified mechanics behind each step:**
- `git clone --branch sf_19 <path>` works from the local repo and carries the net (verified: fresh clone contained `src/nn-*.nnue`, 172 MB).
- `make -C src objclean` is required: `objclean` removes `stockfish` and all `*.o` (`src/Makefile:1211`).
- `export_net` writes a byte-identical copy of the embedded net (verified: both sha256 `1a298aa575a0854…`), which is the cleanest possible proof that the net is embedded rather than loaded from disk.
- `bench` prints `Nodes searched  : 2497913` on **stderr** (`src/uci.cpp:309-311` writes to `std::cerr`), so capture both streams.
- Two consecutive clean builds produced an identical binary hash, so a `sha256sum` line in the evidence file is a meaningful constant, not noise.

### `python-chess` vendoring without pip (FOUND-03 / Rule 14)

```bash
# download, verify, extract only the package
curl -sSL -o /tmp/chess-1.11.2.tar.gz \
  https://files.pythonhosted.org/packages/source/c/chess/chess-1.11.2.tar.gz
echo "a8b43e5678fdb3000695bdaa573117ad683761e5ca38e591c4826eba6d25bb39  /tmp/chess-1.11.2.tar.gz" \
  | sha256sum -c -
mkdir -p /tmp/pc vendor
tar xzf /tmp/chess-1.11.2.tar.gz -C /tmp/pc
cp -r /tmp/pc/chess-1.11.2/chess vendor/chess
cp /tmp/pc/chess-1.11.2/LICENSE.txt vendor/chess/LICENSE.txt
find vendor/chess -name __pycache__ -type d -exec rm -rf {} +
PYTHONPATH=vendor python3 -c "import chess, chess.engine, chess.polyglot, chess.syzygy; print(chess.__version__)"
```

**Why not `pip`:** verified twice.
1. System interpreter: `python3 -m pip --version` → `No module named pip`.
2. A venv *does* supply `pip 26.2.1`, but `pip install --no-index --no-build-isolation chess-1.11.2.tar.gz` fails with `BackendUnavailable: Cannot import 'setuptools.build_meta'` — the sdist has no build backend available offline, and PyPI publishes **no wheel** for 1.11.2 (only `sdist` in the release metadata).

**Version-pin consequence to record in `PROVENANCE.md`:** the pin is **`chess==1.11.2`, sdist sha256 `a8b43e5678fdb3000695bdaa573117ad683761e5ca38e591c4826eba6d25bb39`**, vendored at `vendor/chess/`, imported via `PYTHONPATH` or a `sitecustomize.py`/`.pth` shim. There is no `requirements.txt` entry that could resolve to a different version — which is stronger than pip and is the honest statement for Rule 14.

### Minimal `go` / `info` / `bestmove` exchange (verified against the built binary)

```
console → uci
engine  ← id name Stockfish 19
          id author the Stockfish developers (see AUTHORS file)
          option name Threads type spin default 1 min 1 max 1024
          …
          option name Move Overhead type spin default 10 min 0 max 5000
          option name SyzygyProbeLimit type spin default 5 min 0 max 5
          option name EvalFile type string default nn-1a298aa575a0.nnue
          uciok
console → setoption name Move Overhead value 100
console → setoption name SyzygyPath value /opt/tb/3-4-5
console → isready
engine  ← info string Found 378 WDL and 561 DTZ tablebase files (up to 5-man).
          info string TB ceiling OK: SyzygyProbeLimit=5 max_loaded=5
          readyok
console → position startpos moves e2e4 e7e5 g1f3
console → go wtime 798000 btime 851000 winc 10000 binc 10000
engine  ← info depth 18 seldepth 26 multipv 1 score cp -12 nodes 812345 nps 2100000 hashfull 4 tbhits 0 time 1400 pv b8c6 f1b5 …
engine  ← bestmove b8c6 ponder g1f3
```

Variant coverage verified in this session: `bestmove (none)` on a stalemate position (`position fen 7k/5KQ1/8/8/8/8/8/8 b - - 0 1` → `info depth 0 score mate 0` then `bestmove (none)`); illegal `position` → `info string CRITICAL ERROR: Command \`position startpos moves e2e5\` failed. Reason: Illegal move: e2e5` and the **process exits 1**; `go ponder` + `ponderhit` → a single `bestmove`; `go ponder` + `stop` → `bestmove g1f3 ponder b8c6` (the stale-move case PROTO/Phase-2 must discard).

## Project Constraints (from AGENTS.md)

Directives extracted from `AGENTS.md` (which is a generated mirror of `PROJECT.md` + `research/STACK.md` + conventions). Research does not contradict any of them; where a directive conflicts with a ROADMAP command string, the directive wins and the conflict is recorded below.

| Directive | Source in `AGENTS.md` | How Phase 1 must comply |
|---|---|---|
| Engine base is tag `sf_19`, **never** a development snapshot | "Engine base — Stockfish `sf_19`" | The clone is already at `sf_19`; `NOTICE` declares the tag and full SHA; no rebase onto `master`. |
| Build with `make -j profile-build` (PGO), not plain `build` | "Engine build — `make -j profile-build`" | Phase 1's *proof* uses `build` (fast, byte-reproducible). The shipped binary may use `profile-build` — but then `NOTICE` must record which one produced the shipped hash, because PGO changes the binary hash while keeping `bench` identical (already measured upstream: 2,497,913 both ways). |
| `Move Overhead` must be **100**, not the 10 default; assert it | "Set `Move Overhead = 100` … **assert** it in the console's startup self-check" | Out of scope to *implement* in Phase 1 (no console), but `docs/PROTOCOL.md` must freeze the value and `doctor.py` must accept it as a checked option. Engine-side default stays 10 — do **not** change it in Phase 1 (that is a touched file for a Phase-4 concern). |
| `SyzygyProbeLimit` must be **5** and asserted; 6/7-piece files forbidden anywhere on disk | "**`SyzygyProbeLimit` defaults to 7 → you MUST set it to 5**" | LIMIT-01 — implemented engine-side (Pattern 2). |
| Never delete `Copying.txt`; keep every GPL header byte-identical | "**`Copying.txt` preserved**", "Keep the header verbatim, add your own line below" | FOUND-02 — enforced by `check_license.py`. |
| Do not present the NNUE net as authored | "Do not present the net as your own work … Say 'official Stockfish 19 network, unmodified'" | FOUND-03 — `PROVENANCE.md` must contain the literal phrase `not authored by the team`. |
| Do not ship both an embedded net and a different `EvalFile` | "Do not ship both an embedded net and a *different* `EvalFile`" | `doctor.py` asserts `EvalFile` default == `nn-1a298aa575a0.nnue` and that the embedded net hash matches. |
| Terminal UI only; a localhost web UI is forbidden | "**A localhost web UI** … Use Instead: Terminal" | `mock_gui.py` is a **stdin/stdout driver**, not a server. No listening socket anywhere. |
| Offline: no external request during games; all deps installed and declared before | "**Offline**: nenhuma requisição externa durante partidas" | FOUND-04 + LIMIT-04 + `PROVENANCE.md` dependency manifest. |
| fastchess is dev-only, never vendored into `src/` | "**Do not vendor `fastchess` into `src/`**" | `tools/fastchess-linux-x86-64/` only. |
| SPRT recipe: `elo0=0 elo1=5 alpha=beta=0.05`, `tc=10+0.1`, `-repeat`, `option.Move_Overhead=100`, `-report penta=true` | "The exact SPRT command (verified working)" | PIPE-01 — recorded verbatim in `tools/sprt.md`. |
| Never SPRT at the competition time control | "**SPRT at the competition time control (15+10)** … ~5 min/game" | `sprt.md` must say `tc=10+0.1` and forbid `15+10` for verdicts. |
| `python-chess` pinned to `1.11.2`, vendored | "pin 3.12 and vendor the package" | Vendor 1.11.2 exactly; hash recorded. **Deviation:** this machine has Python 3.14.7, not 3.12, and 1.11.2 imports and runs correctly on 3.14 (verified). Record the interpreter version in `PROVENANCE.md` rather than pretending it is 3.12. |

**Conflict to resolve explicitly:** `AGENTS.md`/`STACK.md` say `make -j profile-build`; ROADMAP criterion 1 says `unshare -n make -j`. Neither is a valid command at the repo root (`make -j` is a no-op; `profile-build` is only valid inside `src/`). Phase 1 documents `make -C src -j build` as the *reproducibility* command and `make -C src -j profile-build` as the *shipping* command, and records which produced the archived binary.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| FOUND-01 | Real `git clone --branch sf_19` with upstream history + tag `base-sf19`; `NOTICE` records URL, full SHA, tag, fork date, modified files, build command, `ARCH`, compiler version, bench node count | History verified present (7,252 upstream commits, not shallow, tags `sf_19` and `base-sf19` both at `edb0d9db…`). `NOTICE` field list + `check_notice.py` skeleton in Pattern 1. Bench constant **2,497,913**. `ARCH=x86-64-avxvnni` (from `get_native_properties.sh` via `ARCH=native`); compiler string `g++ (GNUC) 16.2.1 on Linux` from `./stockfish compiler`. |
| FOUND-02 | `Copying.txt`/`AUTHORS` byte-intact; every touched file keeps the GPLv3 header plus a dated modification line | Baseline is git, not a sidecar hash: `git rev-parse sf_19:Copying.txt` == `HEAD:Copying.txt` (`f288702d2fa16d3cdf0035b15a9fcbc552cd88e7`), same for `AUTHORS` (`b5ad83d591e343df95cf6b82ee27d8f7640f170a`). Exact modification-line format, touched-file list and `check_license.py` below. |
| FOUND-03 | `PROVENANCE.md` declares NNUE name/size/SHA-256/origin, tablebase inventory, dependency manifest; net marked explicitly non-authored | Net identity fully verified (98,511,183 B, `1a298aa5…dfc2`, CC0-1.0, `export_net` round-trip identical). Field list + machine-checkable table below. |
| FOUND-04 | Build works fully offline; `make net` before the event; tree archived; clean `unshare -n make -j` proven on the laptop | Full recipe verified end-to-end: fresh clone → `objclean` → `unshare -rn make -C src -j12 build` (65 s) → `bench` = 2,497,913 → byte-identical rebuild. `net.sh` returns 0 on failure (must not be the gate). Evidence artefact spec below. |
| FOUND-05 | `docs/PROTOCOL.md` and `docs/LOGBOOK.md` frozen and versioned **before** any implementation commit | Content outline derived from requirement IDs TM-11/PROTO-01…08/LOG-01…05 plus the verified wire behaviour. Ordering proof via `git merge-base --is-ancestor` (Pattern 3). |
| FOUND-06 | Public repo or verified panel access by dry run; USB archive started | Dry run plan. **Blocked on input**: no `origin` remote is configured (`git remote -v` shows only `upstream`), `gh` is not installed, and no USB device is mounted (`/media`, `/run/media` empty; only `nvme1n1p3` on `/home`). Requires the team to name the host and supply a device. |
| LIMIT-01 | `SyzygyProbeLimit` forced to 5 at startup (upstream default 7); `MaxCardinality` asserted; effective value in the pre-game checklist | `Option(7, 0, 7)` at `src/engine.cpp:133`; `MaxCardinality` declared `src/syzygy/tbprobe.h:64`, written at `src/syzygy/tbprobe.cpp:595`, reset at `:1524`, consumed at `:1917-1925` and `src/position.cpp:89`. Working patch built and tested (Pattern 2), with the 6-man-file exit-1 proof. |
| LIMIT-04 | No external request in a game; deps installed and declared; a startup `doctor` fails if any asset path is remote or relative | `doctor.py` check list below; grows into `CHECK-01`. Run order proves no socket is opened. |
| PIPE-01 | fastchess v1.8.2-alpha installed and working; SPRT recipe documented (`elo0=0 elo1=5 alpha=beta=0.05`, `tc=10+0.1`, `-repeat`, `option.Move_Overhead=100` on both, `-report penta=true`) | Binary fetched, hashed, `--version` verified, a 2-game match and a real SPRT run executed. **Correction found:** `option.Move_Overhead` (underscore) is rejected — fastchess needs the literal UCI option name **with a space**, quoted: `"option.Move Overhead=100"` (verified in the trace log `Sending setoption to engine A Move Overhead 123`). The recipe in `STACK.md` is wrong on that token. |
</phase_requirements>

## Answers to the Ten Research Questions

### Q1 — FOUND-01 `NOTICE`: exact field list and machine-checkable structure

Use a **line-oriented `Key: value` format**, one field per line, no prose between them. Judges scan for the fields; a script greps for `^Key: `. Prose goes in a `## Narrative` section *below* the fields so line anchoring still works.

```markdown
# NOTICE — ChessChallendIII

Base project:                 https://github.com/official-stockfish/Stockfish
Base tag:                     sf_19
Base commit:                  edb0d9db6731067ec50ce619ff372b463bc4dd5d
Base commit date:             2026-09-05
Fork date:                    2026-10-26
Fork repository:              <URL, filled at FOUND-06>
License:                      GPL-3.0-or-later (see Copying.txt)
Project commit (this build):  <40-hex of the commit the archived binary was built from>
Build command:                make -C src -j12 build
Build profile:                profile-build | build
ARCH:                         x86-64-avxvnni
Compiler:                     g++ (GNUC) 16.2.1 on Linux
Compilation settings:         64bit VNNI BMI2 AVX2 SSE41 SSSE3 SSE2 POPCNT
Bench nodes:                  2497913
Binary sha256:                <sha256 of the archived src/stockfish>
NNUE net:                     nn-1a298aa575a0.nnue
NNUE net sha256:              1a298aa575a085434d29027978dc36867fe9c5bcea9376654b7a8eba1e52dfc2
Modified files:
  - src/engine.cpp
  - src/syzygy/tbprobe.h
  - .gitignore
Added files of ours (not Stockfish):
  - NOTICE
  - PROVENANCE.md
  - docs/PROTOCOL.md
  - docs/LOGBOOK.md
  - ... (rest of the Phase-1 tree)

## Narrative

<one paragraph: what we changed and why; the Rule 2 component lives in src/timeman.*,
 see docs/timeman/ and AUTHORSHIP.md>
```

**Command that produces each value** (so the plan can make them non-hand-typed):

| Field | Command |
|---|---|
| `Base commit` | `git rev-parse sf_19` |
| `Base commit date` | `git log -1 --format=%cs sf_19` → `2026-09-05` |
| `Project commit` | `git rev-parse HEAD` at archive time |
| `ARCH` | `make -C src -j build` config banner, or `./src/stockfish compiler` |
| `Compiler` / `Compilation settings` | `printf 'compiler\nquit\n' \| ./src/stockfish` (verified output above) |
| `Bench nodes` | `./src/stockfish bench 2>&1 \| sed -n 's/^Nodes searched  : //p'` (**stderr**) |
| `Binary sha256` | `sha256sum src/stockfish` |
| `NNUE net sha256` | `sha256sum src/nn-1a298aa575a0.nnue` |

**Machine-checkable minimum:** `tools/check_notice.py` asserts (a) nine required `^Key:` lines exist, (b) `Base commit` matches `^[0-9a-f]{40}$` **and** equals `git rev-parse sf_19`, (c) `Bench nodes` equals the literal `2497913`, (d) `NNUE net sha256` equals the literal hash, (e) every path under `Modified files:` exists in `git ls-files`. Exit nonzero on any failure. Reuse the skeleton in Pattern 1.

**One trap:** `Modified files:` must be *derived*, not remembered. `git diff --name-only sf_19..HEAD -- ':!src/nn-*.nnue'` gives the truth, and it currently returns `.gitignore` plus the added docs — meaning the very first `NOTICE` commit will need to list itself. Do not include `src/nn-1a298aa575a0.nnue` in "modified" (it is an *added vendored asset*, listed in `PROVENANCE.md`).

### Q2 — FOUND-02 GPL marking: the exact line, the touched files, the integrity proof

**The exact line** (one line, immediately after the closing `*/` of the existing header block, separated by one blank line):

```
Modified by ChessChallendIII on 2026-10-26: <one-sentence reason>. See NOTICE and PROVENANCE.md.
```

Why this shape:
- GPLv3 §5(a) requires the modified copy to carry "prominent notices stating that you changed the files and the date of any change". A single dated line satisfies it and is greppable.
- The prefix `Modified by ChessChallendIII on YYYY-MM-DD:` is the anchor the checker uses (`^Modified by ChessChallendIII on \d{4}-\d{2}-\d{2}:`). Keep it **byte-stable** — the team name and the `on`/`:` punctuation are the contract.
- Putting it *after* the header block, not inside it, keeps the upstream notice verbatim and keeps `check_license.py`'s "header present" test meaningful.
- One line per *file* is enough; do not add a per-change log in the source (that lives in `PROVENANCE.md`).

**Files Phase 1 will actually touch** (deliberately tiny — the whole point is that day 0 barely touches `src/`):

| File | Change | GPL line needed? |
|---|---|---|
| `src/engine.cpp` | `SyzygyProbeLimit` default/max → `Tablebases::TB_PROBE_LIMIT`; `SyzygyPath` on_change exit-on-violation; `verify_tb_ceiling()` calls in `go()`/`search_clear()`; helper definition | **Yes** |
| `src/syzygy/tbprobe.h` | `constexpr int TB_PROBE_LIMIT = 5;` next to `extern int MaxCardinality;` (`:64`) | **Yes** |
| `.gitignore` | already modified (net negation) — no header exists, no line needed | No (not a GPL-header file) |
| `NOTICE`, `PROVENANCE.md`, `docs/PROTOCOL.md`, `docs/LOGBOOK.md`, `tools/*`, `scripts/check_license.sh` | new files of ours | **Yes for `.py`/`.sh`/`.cpp`** — new source files get the GPLv3 header plus `Copyright (C) 2026 ChessChallendIII`. Markdown docs get a short `License: GPL-3.0-or-later` footer instead of a C comment block. |

**Explicitly NOT touched in Phase 1** (each would create a GPL line and a diff for no compliance gain): `src/misc.cpp` (no `id name` change), `src/uci.cpp`, `src/search.cpp`, `src/timeman.*`, `src/Makefile`, `scripts/net.sh`, `README.md`, `AUTHORS`.

**How to prove `Copying.txt` / `AUTHORS` are byte-intact — baseline is git, not a new file:**

```bash
# blob identity at base vs now (empty output = identical)
git diff sf_19..HEAD -- Copying.txt AUTHORS
# belt and braces: compare blob SHAs
test "$(git rev-parse sf_19:Copying.txt)" = "$(git rev-parse HEAD:Copying.txt)"
test "$(git rev-parse sf_19:AUTHORS)"     = "$(git rev-parse HEAD:AUTHORS)"
```

Verified today: both pairs are equal (`f288702d2fa16d3cdf0035b15a9fcbc552cd88e7`, `b5ad83d591e343df95cf6b82ee27d8f7640f170a`), and `git diff --stat sf_19 HEAD -- Copying.txt AUTHORS src/ scripts/` shows only the added `.nnue`. **Do not** create `Copying.txt.sha256` — it is a second thing that can drift and adds nothing, because `sf_19` is already an immutable local tag.

**`scripts/check_license.sh`** (PITFALLS.md names this exact path, so use it):

```sh
#!/bin/sh
# FOUND-02: licence headers, integrity and modification notices.
set -eu
fail=0

for f in Copying.txt AUTHORS; do
  a=$(git rev-parse "sf_19:$f"); b=$(git rev-parse "HEAD:$f")
  [ "$a" = "$b" ] || { echo "FAIL: $f differs from sf_19"; fail=1; }
done

# every tracked engine source keeps the GPLv3 notice
for f in $(git ls-files 'src/*.cpp' 'src/*.h' 'src/*/*.cpp' 'src/*/*.h'); do
  grep -q "GNU General Public License" "$f" || { echo "FAIL: no GPL header: $f"; fail=1; }
  grep -q "Copyright (C)"              "$f" || { echo "FAIL: no copyright: $f";  fail=1; }
done

# every file we touched carries a dated modification line
for f in $(git diff --name-only sf_19..HEAD -- 'src/*.cpp' 'src/*.h' 'src/*/*.cpp' 'src/*/*.h'); do
  grep -qE '^Modified by ChessChallendIII on [0-9]{4}-[0-9]{2}-[0-9]{2}:' "$f" \
    || { echo "FAIL: no modification line: $f"; fail=1; }
done

exit $fail
```

### Q3 — FOUND-03 `PROVENANCE.md`: field list and machine-checkable structure

Three tables with fixed column orders. Same rule as `NOTICE`: a parser must be able to read them.

```markdown
# PROVENANCE — ChessChallendIII

License: GPL-3.0-or-later. See Copying.txt and NOTICE.

## 1. Evaluation network (NNUE)

| Property | Value |
|---|---|
| File | nn-1a298aa575a0.nnue |
| Bytes | 98511183 |
| SHA-256 | 1a298aa575a085434d29027978dc36867fe9c5bcea9376654b7a8eba1e52dfc2 |
| Architecture | SFNNv16 (Stockfish 19 single-net) |
| Source URL | https://tests.stockfishchess.org/api/nn/nn-1a298aa575a0.nnue |
| Mirror | https://github.com/official-stockfish/networks/raw/master/nn-1a298aa575a0.nnue |
| License | CC0-1.0 (public domain dedication, official-stockfish/networks) |
| Embedded in binary | yes — INCBIN of EvalFileDefaultName (src/nnue/network.cpp:50); `export_net` round-trip is byte-identical |
| Authorship | NOT AUTHORED BY THE TEAM. Official Stockfish 19 network, unmodified. Rule 15: third-party weights do not count as authorship. |
| Authorization | Rule 15: weights may be delivered on physical media with an origin declaration; Rule 14: no network access is required at run time. |

## 2. Tablebases

| Property | Value |
|---|---|
| Permitted by rule | 3, 4 and 5 pieces only (Rule 4) |
| Retrieved from | https://tablebase.sesse.net/syzygy/3-4-5/ (or syzygy-tables.info mirror) |
| Retrieval date | <YYYY-MM-DD> |
| Local path (game) | /opt/tb/3-4-5   (absolute; never relative) |
| Engine option | SyzygyPath, with SyzygyProbeLimit=5 enforced by Tablebases::TB_PROBE_LIMIT |
| File count | <N> .rtbw + <M> .rtbz |
| Total bytes | <bytes> |
| Manifest | tb/SHA256SUMS (see below) |
| Authorship | Not authored by the team; data, not code. |

### 2.1 Tablebase inventory

```
<sha256>  <bytes>  <filename>
...
```
(produced by `cd /opt/tb/3-4-5 && sha256sum *.rtbw *.rtbz | sort -k2`; `tools/build_manifest.py` adds the byte column and refuses any filename whose piece count > 5)

## 3. Dependencies

| Name | Version | Pin mechanism | SHA-256 | License | Shipped? | Purpose |
|---|---|---|---|---|---|---|
| python-chess (`chess`) | 1.11.2 | vendored at `vendor/chess/` (no resolver) | sdist a8b43e5678fdb3000695bdaa573117ad683761e5ca38e591c4826eba6d25bb39 | GPL-3.0-or-later | yes | board replica, UCI client, Polyglot, Syzygy |
| fastchess | 1.8.2-alpha (20260726-f618e34) | prebuilt release binary at `tools/fastchess-linux-x86-64/` | tarball 1003f920bebe841acdab5e6d7871e93171a4586857b3ec91c21ef5777f26ff96; binary 3d0a8f3c8b837a96366ac838f3ddf6fe87b813abb4ad2852284c0ce409132566 | MIT | **no** (dev-only) | SPRT / match runner |
| GCC / libstdc++ | 16.2.1 | system toolchain | n/a | GPL-3.0-or-later with GCC Runtime Library Exception | n/a | build only |
| Python | 3.14.7 | system interpreter | n/a | PSF-2.0 | n/a | console + tooling |
| Openings books (harness) | official-stockfish/books | downloaded pre-event | <hashes> | CC0-1.0 | no | SPRT openings |
| Syzygy 3-4-5 | (see §2) | downloaded pre-event | (see §2.1) | probe code GPLv3; data unrestricted | yes (media) | endgame |

## 4. Not authored by the team

- The Stockfish engine (GPLv3, `sf_19`) — every file under `src/` except the marked modifications.
- The NNUE network (CC0-1.0).
- Syzygy tablebase data.
- Harness opening books.
- `python-chess`, `fastchess`, `incbin.h` (public domain, `src/incbin/UNLICENCE`).

Authored by the team: the time manager (`src/timeman.*`, Phase 4), the console, the tooling,
and the documents in `docs/`. See AUTHORSHIP.md.
```

**Machine-checkable minimum:** `tools/check_provenance.py` asserts (a) the NNUE row's `Bytes` == `98511183`, `SHA-256` == the literal, and the file on disk hashes to it; (b) the phrase `NOT AUTHORED BY THE TEAM` appears in §1 (case-insensitive); (c) the licence string `CC0-1.0` appears; (d) every dependency row has a non-empty `SHA-256` except rows explicitly marked `n/a`; (e) `fastchess` is marked `Shipped? = no`; (f) every filename in §2.1 has ≤ 5 piece codes (parse `KQRRBvK` style tokens). Exit nonzero otherwise.

**Rule 15 nuance worth writing down:** "pesos treinados pela equipe contam, desde que acompanhados do código de treinamento" — we have no training code, so the *only* defensible statement is "official net, unmodified, CC0-1.0, not authored by the team". Anything softer invites the question.

### Q4 — FOUND-04: exact offline-build sequence, what breaks, what must be pre-staged, evidence artefact

**What breaks — measured, not guessed:**

| Failure | Symptom | Root cause |
|---|---|---|
| Network severed, net present | **Nothing breaks.** `net.sh` validates and prints `Existing nn-1a298aa575a0.nnue validated, skipping download`, `make net` exits 0, build succeeds (65 s, 12 jobs). | `validate_network` short-circuits before any fetch (`scripts/net.sh:18-26`, `:36-40`) |
| Network severed, net absent | `make net` prints two `Failed to download…` lines and **exits 0**; the link step then dies with `/tmp/cc*.s:26: Error: file not found: nn-1a298aa575a0.nnue` → `lto-wrapper failed` → `Error 1` | `scripts/net.sh:74` `return 1`, discarded at `:77` |
| `make -j` at repo root | `make: *** No targets specified` / nothing built | no root Makefile |
| `make -j` inside `src/` | prints the help tutorial, exits **0**, builds nothing | default goal is `help:` (`src/Makefile:1007`) |
| Stale `*.o` present | build succeeds but proves nothing | must `make -C src objclean` first |
| `unshare -n` without privilege | `unshare: unshare failed: Operation not permitted` | `CLONE_NEWNET` needs CAP_SYS_ADMIN, or a user namespace (`-r`) |

**What must be pre-staged (all four, verified):**
1. `src/nn-1a298aa575a0.nnue` **committed** (98,511,183 B, hash-checked). Present and committed today; `git ls-files --error-unmatch` succeeds.
2. The `.gitignore` negation that keeps it tracked (`!src/nn-1a298aa575a0.nnue`) — present.
3. `vendor/chess/` (the console cannot run offline without it).
4. A writable temp dir for `src/temp_builds` in universal builds — irrelevant for the non-universal `build` target used here.

**Exact command sequence** — see the `tools/offline_build.sh` listing in *Code Examples*. The load-bearing details: `git clone --branch sf_19` (not a copy) → `git ls-files --error-unmatch src/nn-*.nnue` → `sha256sum -c` → `make -C src objclean` → `unshare -n` (fallback `-rn`) `make -C src -j$(nproc) build` → `export_net` + `cmp` → `bench` == 2497913 → assert no `Downloading from` in the log.

**Evidence artefact (this is the deliverable, not the build):** `evidence/01-offline-build.log`, committed, containing:
- the namespace command actually used (`unshare -n` vs `-rn`) and `id -u`;
- the full build log (including the config banner with `arch: 'x86-64-avxvnni'`, `debug: 'no'`);
- the `Existing … validated, skipping download` line — positive proof that `net.sh` took the local path;
- the `Nodes searched  : 2497913` line;
- `sha256sum src/stockfish` (a constant across clean rebuilds: `077d3601b503c369f97ed06df73cd5f3b44fd3d3fa513e31c92065da992c4a79` for a `build` of the current tree);
- `stat -c '%y %s' src/stockfish`.

Reproduce on the match laptop with `sudo unshare -n sh tools/offline_build.sh` and replace the file. **Do not** put the laptop's hash in `NOTICE` if the laptop's `ARCH=native` differs — record its own `ARCH` and hash, and say so.

### Q5 — FOUND-05: the two frozen documents' content outlines, and the ordering proof

Both documents must be **normative**, i.e. written as a specification with MUST/SHALL, each rule numbered, so a test name can cite `PROTOCOL §4.2`. Freeze = a commit that touches only these two files.

**`docs/PROTOCOL.md` outline** (the console↔engine contract; nothing about the console's internals):

1. **Scope and invariants** — one engine process; UCI on stdin/stdout; one outstanding `go`; stdout carries UCI only; everything else to stderr; no `setoption` while a search is running; `quit` only at game end (watchdog sends `stop`, never `quit`).
2. **Handshake** — `uci` → option list → `uciok`; `isready` → `readyok`; the exact required options and their competition values: `Threads=<physical cores>` (not SMT siblings), `Hash ≤ min(4096 MB, 50 % RAM)`, `SyzygyPath=<absolute local path>`, `SyzygyProbeLimit=5` (engine-enforced), `Move Overhead=100`, `Ponder=false` until TM-13 lands.
3. **The `go` line — frozen literal.** `go wtime <int_ms> btime <int_ms> winc 10000 binc 10000`; the ponder variant `go ponder wtime … btime … winc 10000 binc 10000`. **MUST NOT** contain `movetime`, `movestogo`, `depth`, `nodes`, `infinite`, `searchmoves`. Both `wtime`/`btime` are the console's *reserve-discounted* belief (TM-09's invariant), always ≥ 0, always integers in milliseconds. Worked example with real numbers.
4. **The search lifecycle** — `position startpos moves …` (always `startpos` + full move list; never an incremental FEN); `go`; `info` stream; `bestmove`. Invariant: exactly one `bestmove` per `go` (UCI norm; verified that `stop` mid-ponder yields one).
5. **`info` fields consumed** — the verbatim token set and types: `depth seldepth multipv score {cp|mate <int>} [lowerbound|upperbound] nodes nps hashfull tbhits time pv`, plus `info string <rest>`. Note that `time` arrives in **milliseconds on the wire** and that `python-chess` converts it to **seconds** — the doc must state the wire unit, because LOG-03 requires both `engine_ms` and `wall_ms`. Note `score` is **side-to-move POV**; the log records STM-POV verbatim *and* a White-POV normalisation.
6. **The TM trace line — frozen literal** (TM-11 wins over the `ARCHITECTURE.md` draft shape):
   `info string tm=custom-v<MAJOR>.<MINOR> mode=<increment|sudden_death|armageddon> latency_p95_ms=<int> bank_ms=<int> budget_ms=<int> reason=<token>`
   with `<token>` from a closed set (`reserve`, `bank_positive`, `low_clock`, `instant`, `book_exit`, `scramble`). Phase 1 freezes the *grammar* and the token set; Phase 4 fills in the values. A `tm=upstream` variant is also frozen so ablation logs parse identically.
7. **`bestmove` handling** — `bestmove <uci> [ponder <uci>]`; `bestmove (none)` is legal and means no move (stalemate/mate); a `bestmove` received while the console is in a non-awaiting state is **stale** and must be discarded by `search_id`; the ANNOUNCE field is populated by `bestmove` only.
8. **Ponder rules** — `go ponder` is sent only when `Ponder=true`; `ponderhit` on a match; `stop` then discard-on-miss; the engine's elapsed clock counts ponder time (so a long hit yields a near-instant move); Phase 1 freezes the *rules*, Phase 5 turns the option on.
9. **Error and crash policy** — `info string CRITICAL ERROR: …` is fatal (the process exits 1 — verified on an illegal `position`); the console restarts and replays `position startpos moves …`; engine death is a restarted-search, never a lost game.
10. **Serialization and timing** — one `go` outstanding; `isready`/`readyok` is the only sync point; no `setoption` mid-search; `ucinewgame` may be sent between games only.
11. **Versioning** — the document has a `Frozen: 2026-10-26` header and a `Change control` section: changes require a new dated revision + a note in `PROVENANCE.md`; a change after the freeze invalidates earlier evidence.

**`docs/LOGBOOK.md` outline** (the Rule 9 artefact):

1. **Mandate** — Rule 9 verbatim quote; one `.log` per game; append-only; delivered to the panel at the end of each game; never edited.
2. **The eight mandatory fields**, as a table with `rule_name`, `log_key`, `type`, `unit`, `source`, `allowed empties`:

| # | Rule 9 field (PT) | log key | Type | Unit | Source | Empty allowed? |
|---|---|---|---|---|---|---|
| 1 | número do lance | `move_no` | int | full-move number | `board.fullmove_number` | no |
| 2 | cor | `side` | `w`\|`b` | — | side that made the move | no |
| 3 | lance escolhido em notação UCI | `uci` | string | — | `bestmove` / parsed operator input / book entry | no |
| 4 | profundidade atingida | `depth` | int | plies | last completed `info depth` | no (0 for book/tb) |
| 5 | nós avaliados | `nodes` | int | nodes | `info nodes` | no (0 for book/tb) |
| 6 | avaliação da posição | `score` | string | cp or `mate N` | `info score` **verbatim**, incl. bound flag | no (`-` when absent) |
| 7 | variante principal (PV) | `pv` | space-separated UCI | — | `info pv` | no (the move itself for book/tb) |
| 8 | tempo gasto | `engine_ms` + `wall_ms` | int | ms | `info time`×1000; `monotonic_ns()` delta | no (0 for book; wall always) |

3. **Line format** — one line per half-move, `key=value` pairs, space-separated, stable key order, no spaces inside values (PV is space-separated *by definition*, so it must be the **last** key on the line, or be quoted — **freeze the choice**: PV last, unquoted).
4. **Variants** — `src=search` (default), `src=book` (`d=0 n=0 score=book pv=<move>`), `src=tb` (`score=tb win|draw|loss`), `src=ponder` (a discarded search: logged, never announced), `src=none` (terminal: `uci=(none)`, `d=0 n=0`, non-empty `score`).
5. **Opponent half-moves** — also logged, with `src=opp` and `d=0 n=0 score=- engine_ms=0`, so "for each lance" is satisfied for both colours (LOG-01 explicitly demands this).
6. **Header** — game id, date, our colour, time control, engine binary sha256, net sha256, full `setoption` set, `SyzygyProbeLimit` effective value, TB inventory hash, book hash + max ply, `network=off`.
7. **Trailer** — result, reason, both final clocks (observed), log sha256.
8. **`log_lint` contract** — the checks a linter must run (every key present per line; `move_no` monotone; `side` alternates; `uci` legal in the replayed position; `pv` non-empty; `wall_ms ≥ engine_ms`; no `src` outside the enum). `log_lint` is implemented in Phase 2; Phase 1 freezes the *rules it will enforce*.

**Ordering proof (machine-checkable):** `tools/check_contract_order.py` uses `git merge-base --is-ancestor <docs-commit> <first-impl-commit>` and requires exit 0. Restrict the impl path set to `src/ console/ pipeline/` (see Pattern 3's caveat — including `tools/` makes the check impossible to satisfy). Additional cheap proof: `git log --diff-filter=A --format='%H %cs' -- docs/PROTOCOL.md docs/LOGBOOK.md` and `git log --format='%H %cs' --reverse -- src/ console/ | head -1`, and assert the first date ≤ the second. Commit the command output into `evidence/01-contract-freeze.txt`.

### Q6 — LIMIT-01: where the startup assertion lives, and why

**Options considered, all four inspected against the actual source:**

| Option | Where | Verdict |
|---|---|---|
| **(a)** Change the option declaration to `Option(5, 0, 5)` | `src/engine.cpp:133` | **Necessary.** One line, no behaviour change when the console sets 5. Alone it is insufficient: out-of-range values are *silently rejected* (`src/ucioption.cpp:155-158`) so a violation leaves no trace. |
| **(b)** `on_change` hook on `SyzygyProbeLimit` | `src/engine.cpp:133` (4th ctor arg) | Insufficient by itself: the hook only runs when the value is **accepted**, and (a) makes illegal values never accepted. It also cannot see `MaxCardinality`, which is populated later by `Tablebases::init`. Good as a *reporting* hook, not as the guard. |
| **(c)** `on_change` hook on `SyzygyPath` + check after `Tablebases::init` | `src/engine.cpp:124-127` | **This is the load-time gate.** `Tablebases::init` sets `MaxCardinality` (`src/syzygy/tbprobe.cpp:595`) before returning, and the directory is only ever populated here (`:1521`) and via `search_clear()` (`src/engine.cpp:168`). First call site where a breach is detectable — and no search is in flight, so `exit(1)` is safe. |
| **(d)** New UCI option (e.g. `TB MaxPieces`) | — | **Rejected.** Adds a surface to explain and a way to disagree with the rule. The rule's number is 5; there is nothing to configure. |
| **(e)** Console-side assertion only | Phase 3 `doctor` | **Rejected as the primary guard.** `setoption` is an engine surface; `fastchess`, a debug session or a stray `setoption` bypasses the console entirely. `doctor.py` still checks it (defence in depth) but it is not the guarantee. |

**Recommended, least-invasive, most-provable combination** = (a) + (c) + a *report* call in `go()` and `search_clear()`. Exact locations in the **current** tree:

| What | file:line (current tree) |
|---|---|
| `SyzygyProbeLimit` declaration (upstream default 7) | `src/engine.cpp:133` |
| `SyzygyPath` declaration + its `on_change` lambda | `src/engine.cpp:124-127` |
| `search_clear()` calls `Tablebases::init(options["SyzygyPath"])` | `src/engine.cpp:168` |
| `go()` — the per-search hook point | `src/engine.cpp:153-158` |
| `verify_network()` — the pattern to imitate for reporting | `src/engine.cpp:266` |
| `OptionsMap::add_info_listener` sink (turns a returned string into `info string`) | `src/uci.cpp:74-78`, `src/ucioption.cpp:176-182` |
| `MaxCardinality` declaration | `src/syzygy/tbprobe.h:64` |
| `MaxCardinality` global definition / `NO_TABLEBASES` stub | `src/syzygy/tbprobe.cpp:68` and `:99` |
| `Tablebases::init` — resets then populates `MaxCardinality` | `src/syzygy/tbprobe.cpp:1521`, `:1524`, `:595`, `:1682` |
| Where the limit is turned into a probe ceiling | `src/syzygy/tbprobe.cpp:1916-1926` |
| Where `MaxCardinality` gates probing in search | `src/position.cpp:89`, `src/search.cpp:923-928` |
| Option clamping semantics (why a `setoption 7` is silent) | `src/ucioption.cpp:137-158` |
| Hard supported ceiling (`TBPIECES = 7`) | `src/syzygy/tbprobe.cpp:105` |

**Behaviour to freeze (verified on the prototype):** `default 5 min 0 max 5`; `setoption … value 7` clamps silently to 5; `value 0` is accepted (TB disabled ⇒ compliant); a 6-man filename in `SyzygyPath` prints `info string CRITICAL ERROR: TB CEILING VIOLATION: tablebase directory contains 6-man files (required <= 5)` and exits 1; `bench` unchanged at 2,497,913.

**Test matrix for the plan** (four assertions, none of which is "exit code of setoption"):

| Test | Assertion |
|---|---|
| `test_option_default_is_five` | `uci` output contains `option name SyzygyProbeLimit type spin default 5 min 0 max 5` |
| `test_out_of_range_clamps_and_attests` | after `setoption … value 7` + `go depth 1`, the stream contains `TB ceiling OK: SyzygyProbeLimit=5` |
| `test_six_man_directory_fails_loud` | `setoption name SyzygyPath value <dir with KQRRBvK.rtbw>` → stdout has `CRITICAL ERROR: TB CEILING VIOLATION`, process exit code 1 |
| `test_bench_unchanged` | `./stockfish bench` → `Nodes searched  : 2497913` |

**One caveat:** `TBPIECES = 7` at `src/syzygy/tbprobe.cpp:105` is the *supported* ceiling and must **not** be reduced to 5 — it sizes internal arrays (`LeadPawns`, `Binomial`, `MapPawns`) and the enumeration at `:1640-1676`. Reducing it is a buffer-overflow risk in `probe_wdl`, not a compliance win. Enforce the rule at the option/assertion layer only.

### Q7 — LIMIT-04: what `doctor.py` checks in Phase 1, and where it lives

**Location:** `tools/doctor.py`. Rationale: it must be runnable on day 0 by all three tracks, has no dependency on the console (which does not exist yet), and Phase 3's CHECK-01 can *extend* it without moving it. It must be pure stdlib (`argparse`, `hashlib`, `pathlib`, `shutil`, `subprocess`, `json`, `os`) so it runs with no `PYTHONPATH` tricks.

**Phase-1 checks (each returns `PASS`/`FAIL`/`WARN` with a one-line reason; exit 1 if any FAIL):**

| # | Check | Rule | Implementation |
|---|---|---|---|
| 1 | Every declared asset path is **absolute** and **local** | Rule 14 | reject `http://`, `https://`, `ftp://`, `git@`, `s3://`; reject `~`, `$VAR`, and non-`/`-leading paths; resolve with `Path.resolve()` and re-test |
| 2 | The engine binary exists and is executable; print its `sha256` and size | R1 | `Path("src/stockfish")` |
| 3 | The net is present and hashes to the declared value | R1/R15 | `sha256(src/nn-1a298aa575a0.nnue) == 1a298aa575a0854…dfc2` |
| 4 | The engine's *embedded* net equals the declared net | R15 | `export_net` to a temp file + compare (verified byte-identical) |
| 5 | `EvalFile` default is `nn-1a298aa575a0.nnue` (no shadow file) | AGENTS.md | parse `uci` output |
| 6 | `SyzygyProbeLimit` reports `default 5 min 0 max 5` | R4 | parse `uci` output |
| 7 | TB directory exists, is absolute, and contains **no** filename with > 5 piece codes | R4 | tokenise `KQRRBvK` → 6 pieces → FAIL |
| 8 | TB directory is non-empty and every file ends in `.rtbw`/`.rtbz` | R4 | — |
| 9 | Book file (if declared) is present and its max ply ≤ 10, or no book is declared | R3 | Phase 1: presence + size only; the ply scan is LIMIT-03/Phase 3, so emit `SKIP` |
| 10 | `vendor/chess/` imports and reports `1.11.2` | R14 | `subprocess` with `PYTHONPATH=vendor` |
| 11 | `requirements`-equivalent manifest exists (`PROVENANCE.md` §3) and lists every vendored item | R14 | parse the table |
| 12 | No listening sockets and no default route | R14 | Phase 1: `WARN` only if `/proc/net/tcp` shows LISTEN on 0.0.0.0/::; `FAIL` only in Phase 3 |
| 13 | The log directory is writable | R9 | `os.access(dir, os.W_OK)` on a declared absolute path |
| 14 | `NOTICE`/`PROVENANCE.md`/`docs/PROTOCOL.md`/`docs/LOGBOOK.md` exist and `check_notice.py`/`check_provenance.py`/`check_license.py` pass | R1 | delegate |

**Growth path to CHECK-01 (Phase 3)** — the Phase-1 file already carries the shape, so Phase 3 adds checks, not structure: effective `SyzygyProbeLimit` from a live engine (not the option list), book line count + max ply, `Threads`/`Hash` against the measured resource profile, `git rev-parse` base-commit identity, GPU declaration, and a *hard* network assertion (`unshare -n` or `/proc/net` route check). Also emit the same report as `--json` from day 0 so CHECK-01 can be asserted in tests rather than eyeballed.

**Anti-pattern to avoid:** `doctor.py` must not start a search. It may run `uci`, `isready`, and `export_net`; anything that spends clock is a Phase 3 concern.

### Q8 — PIPE-01: fastchess install, the SPRT recipe, and reuse in Phase 6

**Install (offline-safe, one command sequence):**

```bash
cd tools
curl -sSL -o fastchess-v1.8.2-alpha-linux-x86-64.tar \
  https://github.com/Disservin/fastchess/releases/download/v1.8.2-alpha/fastchess-linux-x86-64.tar
echo "1003f920bebe841acdab5e6d7871e93171a4586857b3ec91c21ef5777f26ff96  fastchess-v1.8.2-alpha-linux-x86-64.tar" | sha256sum -c -
tar xf fastchess-v1.8.2-alpha-linux-x86-64.tar          # → fastchess-linux-x86-64/{fastchess,LICENSE,README.md,Makefile,app/}
chmod +x fastchess-linux-x86-64/fastchess
tools/fastchess-linux-x86-64/fastchess --version        # "fastchess alpha 1.8.2 compiled for ubuntu-22.04 20260726-f618e34 (CI)"
```

Keep the extracted `app/` (MIT source) — it is the licence-compliant copy and costs 14 MB. **Do not** copy anything into `src/`. Do not build from source unless the prebuilt binary fails; if it does, `make -j` inside `tools/fastchess-linux-x86-64/` is dependency-free (measured upstream: 1 m 41 s).

**The recipe to document (`tools/sprt.md`)** — corrected against a live run in this session:

```bash
tools/fastchess-linux-x86-64/fastchess \
  -engine cmd=./src/stockfish name=Upstream \
    "option.Move Overhead=100" option.Hash=512 option.Threads=1 \
  -engine cmd=./build/stockfish-custom name=Custom \
    "option.Move Overhead=100" option.Hash=512 option.Threads=1 \
  -each tc=10+0.1 \
  -rounds 100000 -concurrency 8 -repeat \
  -openings file=tools/books/UHO_Lichess_4852_v1.epd format=epd order=random \
  -sprt elo0=0 elo1=5 alpha=0.05 beta=0.05 model=normalized \
  -report penta=true \
  -recover \
  -pgnout file=results/sprt.pgn notation=uci timeleft=true
```

**Three corrections to the recipe in `STACK.md` / `AGENTS.md` — all verified here:**

| Claim | Reality |
|---|---|
| `option.Move_Overhead=100` (underscore) | **Rejected.** fastchess matches the *literal* UCI option name: `Warning; A doesn't have option Move_Overhead`. The working form is quoted with a space: `"option.Move Overhead=100"`, confirmed by the trace log `Sending setoption to engine A Move Overhead 123` and by the absence of any warning. |
| Requires `-openings` | Runs without one (a random opening is used), but verdicts need one — always pass `UHO_Lichess_4852_v1.epd` (`order=random`) or `noob_5moves.epd` (`order=sequential`, exactly 10 plies). fastchess consumes **EPD/PGN only**; a Polyglot `.bin` must be converted. |
| Output format | `LLR: -0.00 (-0.0%) (-2.94, 2.94) [0.00, 5.00]` plus `Ptnml(0-2): [...]` — verified verbatim in a real SPRT run. |

**How to record it so Phase 6 reuses it verbatim:** `tools/sprt.md` holds the command as a single copy-pasteable block with `<placeholder>`s only for engine paths, plus a `tools/sprt.sh` wrapper that takes `BASE=<engine> CUSTOM=<engine> ROUNDS=<n>` and appends its own invocation line, `date`, `git rev-parse HEAD`, and both binaries' `sha256` to `results/sprt-<timestamp>.log`. Phase 6's PIPE-02 gate then calls `tools/sprt.sh` with no edits and only ROUNDS changes.

**Throughput note for the plan:** the `10+0.1` figure (~1,000 games/h at concurrency 12 on a 12-thread box) is from `STACK.md`'s measured runs; this session's smoke runs used `tc=2+0.02` and are therefore *not* usable as throughput data. Do not budget Phase 6 from the smoke numbers.

### Q9 — Mocks: what each must do to unblock three tracks on day 0

Both are **contract implementations**, not test doubles for our own code. They must be readable in under five minutes by someone who has not read `ARCHITECTURE.md`.

**`tools/mock_engine.py`** — a fake UCI engine that speaks exactly `docs/PROTOCOL.md`, so the console track can develop before `src/stockfish` is rebuilt (and can deliberately misbehave in ways Stockfish will not). Must:
- answer `uci` with an option list containing at least `Threads`, `Hash`, `SyzygyPath`, `SyzygyProbeLimit` (`default 5 min 0 max 5`), `Move Overhead`, `Ponder`; then `uciok`;
- answer `isready` with `readyok`;
- accept `setoption name X value Y`, recording it, and echo an `info string` for unknown names (so the console's option-queue tests have something to parse);
- accept `position startpos [moves …]` and `position fen …`, recording the move list verbatim;
- on `go …`, emit a configurable script of `info` lines (default: three deepening `info depth … score cp … nodes … time … pv …`, plus one `info string tm=…` when `--tm-trace` is set), then `bestmove <mv> [ponder <mv>]`;
- **scenario flags** (one CLI flag each, so the console's tests are one-liners): `--delay-ms N` (jitterable), `--crash-after N` (exit mid-search without `bestmove`), `--stale-bestmove` (answer a `go ponder` + `stop` with a move for the *previous* position), `--silent-hang` (accept `go`, never answer), `--illegal-bestmove` (`bestmove e2e5`), `--none-bestmove` (`bestmove (none)`), `--crash-on-option` (exit on a `setoption` during search), `--garbage` (emit non-UCI lines on stdout), `--slow-ready` (delay `readyok`);
- write a machine-readable transcript to `--record <path>` (every stdin line and stdout line with monotonic timestamps) so a test can assert *ordering*, not just presence;
- exit 0 on `quit`; exit 0 on stdin EOF (like the real engine via `src/uci.cpp:104-107`).

**`tools/mock_gui.py`** — drives a *real* engine through the frozen contract, so the TM track can measure budgets without the console. Must:
- spawn `--engine <path>`, do `uci` → parse options → `setoption` from `--option k=v` (repeatable) → `isready`;
- play a scripted or random-but-legal line from a start FEN, sending **only** the frozen `go` line (`go wtime … btime … winc 10000 binc 10000`, or `go ponder` when `--ponder`), and maintain **one outstanding `go`**;
- parse and print a per-move CSV: `ply,side,uci,depth,nodes,score,time_ms,pv,tm_trace`, plus the wall-clock `think_ms`; this is the artefact the TM ablation consumes;
- `--games N`, `--tc W:I` (e.g. `15:10`), `--latency-ms p50,p95` (sleep between `bestmove` and the next `go` to simulate the human tail — this is the whole reason the mock exists);
- enforce the invariants it is testing: assert one `bestmove` per `go`, assert `wtime`/`btime` never negative, assert `tm=` appears on every search when `--require-tm`;
- `--record` a transcript exactly as `mock_engine.py` does, so the two are diff-comparable.

**Where they live and why:** `tools/mock_engine.py`, `tools/mock_gui.py`. Both are stdlib-only except `mock_gui.py`, which needs `chess` from `vendor/` for legality (documented one-liner: `PYTHONPATH=vendor python3 tools/mock_gui.py …`). Deliberately **not** under `console/tests/fixtures/` — see OQ-10.

**Minimality test:** if either mock needs more than ~200 lines, it is absorbing contract decisions that belong in `PROTOCOL.md`. Both must be deletable after Phase 3 without breaking any shipped artefact.

### Q10 — Vendoring `python-chess` without pip

Answered concretely above (Code Examples). The four load-bearing facts:

1. **PyPI publishes only an sdist for 1.11.2**; its sha256 is `a8b43e5678fdb3000695bdaa573117ad683761e5ca38e591c4826eba6d25bb39` (6,131,385 B). `[VERIFIED: https://pypi.org/pypi/chess/json]`
2. **`pip install` from that sdist fails offline**: `BackendUnavailable: Cannot import 'setuptools.build_meta'`. A venv supplies `pip 26.2.1`, but not `setuptools`. `[VERIFIED: pip install --no-index --no-build-isolation chess-1.11.2.tar.gz]`
3. **Copying `chess/` plus `LICENSE.txt` is sufficient**: `PYTHONPATH=vendor python3 -c "import chess, chess.engine, chess.polyglot, chess.syzygy"` → `1.11.2`, 1.2 MB. `[VERIFIED]`
4. **Version-pin consequence:** the pin is by *vendored source tree*, not by resolver. `PROVENANCE.md` records the sdist hash, the extracted-tree hash (a sorted `sha256sum` of every file under `vendor/chess/`, committed as `vendor/chess/SHA256SUMS`), and the interpreter version actually tested (3.14.7 here, not the 3.12 in `STACK.md`). A `requirements-game.txt` still exists for Rule 14's "declaradas" wording — with a comment that the package is vendored and must not be installed — but it is documentation, not the install mechanism.

**Optional wheel shortcut (do not depend on it):** a PyPI-cached wheel exists at `~/.cache/pip/wheels/06/53/ec/…/chess-1.11.2-py3-none-any.whl` (sha256 `e516f0ff48622c5851f99311a738eec8fac5e505947db87c86e66b30447cde25`, extracted and imported successfully). It is a *local* artefact with no public URL, so it cannot be part of a reproducible recipe — but it is a valid cross-check that the vendored tree matches the published package.

## State of the Art

| Old approach | Current approach | When changed | Impact here |
|---|---|---|---|
| `pip install python-chess` at the venue | vendor the package directory | whenever the venue has no network | Phase 1 must not assume pip; verified impossible offline |
| cutechess-cli for matches | fastchess | 2024–2026 | No Qt dependency; prebuilt binary; pentanomial SPRT built in |
| `make net` to fetch the net | commit the net into the tree | this project (FOUND-04) | `net.sh` short-circuits on a validated local file; the ignore ruling needs the negation |
| `Timeman`/`TimeManager` class names | `TimeManagement` (`src/timeman.h:38`) | SF16+ | Never write the old names in `PROTOCOL.md` |
| Dual-net NNUE (big + small) | SFNNv16 single net | SF19 | No `EvalFile2`; one hash to record |
| `move_overhead` subtracted per move | amortised `(2 + mtg)` times inside `init()`, plus once from the hard ceiling | SF19 | The frozen `go` line never carries `movestogo`, so `mtg = 0` and the overhead is amortised twice — record this in `PROTOCOL.md` so the TM author knows the arithmetic |

**Deprecated / do not use:** `movetime` (bypasses the authored TM ⇒ Rule 2 exposure), `movestogo` (selects the wrong upstream TM branch), `go depth/nodes` in a game (not time-managed), `bestmove` without `ponder` as an assumption about ponder availability, `EvalFile` pointing at a second net, `TBPIECES` as a limit knob.

## Assumptions Log

| # | Claim | Section | Risk if wrong |
|---|---|---|---|
| A1 | The match laptop can run `sudo unshare -n` (or has unprivileged user namespaces enabled). The dev box needs `-r`. | Q4, Pitfall 6 | FOUND-04's proof cannot be produced as specified; fallback is `unshare -rn`, which is weaker evidence. **Verify on the laptop before 01-01 is marked done.** |
| A2 | The team will name a public host (GitHub/GitLab/self-hosted) and provide a USB device; neither exists today. | FOUND-06 | FOUND-06 cannot be completed; Gate 0 fails on an external input. Must be raised at the start of 01-03, not at the end. |
| A3 | The archived binary may be a `profile-build` while the reproducibility proof uses `build`, and the two hashes differ. | Q4, Project Constraints | A judge re-building with the wrong command gets a different hash and may call it non-reproducible. Mitigation: `NOTICE` records *which* command produced the archived hash, and `evidence/` contains both hashes labelled. |
| A4 | Python 3.14.7 runs `python-chess` 1.11.2 correctly (imports + `parse_uci` + `IllegalMoveError` all verified), even though `STACK.md` pins 3.12. | Q10 | If a 3.14-only behavioural difference surfaces later, the console breaks on the dev box. Mitigation: record 3.14.7 in `PROVENANCE.md` and keep the vendored tree byte-identical to the sdist. |
| A5 | `TBPIECES = 7` must stay 7; the rule ceiling is enforced at the option/assertion layer only. | Q6 | Reducing it risks out-of-bounds in `probe_wdl`. If a reviewer argues the constant itself should be 5, the answer is that `TBPIECES` is the *format support width*, not a policy knob. |
| A6 | The Sprt/`results/` and `RELEASE/` directories may exceed a host's file limits and be gitignored, with only `SHA256SUMS` + `README.md` committed. | FOUND-06 | A gitignored `RELEASE/` is not "in the repo", but Rule 15 allows weights on physical media; the manifest in git plus the media in hand satisfies it. |
| A7 | The 2026-10-26 fork date is correct (first project commit `2026-10-26 20:13:53 -0300`). | Q1 | Trivial; the date is derived from `git log`, not typed. |

**If this table is empty:** it is not — seven items require confirmation, of which **A1 and A2 are hard blockers** for Gate 0.

## Environment Availability

Probed on the research machine (12 logical CPUs, 15 GB RAM, 375 GB free on `/home`) [VERIFIED: shell probe, this session].

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `git` | FOUND-01 history/ancestry, FOUND-02 blob integrity, FOUND-05 ordering proof, FOUND-06 | ✓ | 2.55.0 | — |
| `g++` / `gcc` | FOUND-04 build | ✓ | 16.2.1 (20260810) | — |
| `make` | FOUND-04 build | ✓ | GNU Make 4.4.1 | — |
| `python3` | LIMIT-04 `doctor.py`, `tools/` checkers, `vendor/chess/` import proof | ✓ | 3.14.7 | — |
| `sha256sum` | FOUND-03 net pin, FOUND-06 `SHA256SUMS`, Gate 0 | ✓ | coreutils 9.12 | `python3 -c 'import hashlib…'` |
| `unshare` | FOUND-04 offline proof | ✓ | util-linux 2.42.4 | see note below |
| `curl` | pre-event book/TB fetch only (never at match time) | ✓ | 8.22.0 | `wget` |
| `wget` | pre-event Syzygy fetch only | ✓ | 1.25.0 | `curl` |
| `cmake` | not needed (Stockfish uses Make; fastchess ships a prebuilt binary) | ✓ | 4.4.3 | — |
| `node` / `npm` | not needed by this phase | ✓ | 26.10.0 / 12.1.0 | — |
| `pytest` | Phase 1 tests | ✗ | — | stdlib `unittest` (see Validation Architecture) |
| `git-filter-repo` | optional history surgery | ✗ | — | not needed; keep full history |
| `gh` | FOUND-06 remote setup | ✗ | — | manual `git remote add` + web UI |

**Offline-proof note (FOUND-04):** `unshare -n` fails without privilege on this box; `unshare -rn` succeeds and gives a network namespace with no interfaces [VERIFIED: this session]. `unshare -rn make -C src -j12 build` completed in **65 s** inside that namespace, proving the build needs no network. Whether `unshare -rn` (or `sudo unshare -n`) also works on the match laptop is A1 in the Assumptions Log.

**Missing dependencies with no fallback:**
- None for this phase. Every hard dependency above is present.

**Missing dependencies with fallback:**
- `pytest` → stdlib `unittest`. Phase 1 has no third-party test dependency by design.
- `git-filter-repo` → not required. FOUND-06 only needs remotes and a full-history push; history rewriting would actively weaken the provenance story.
- `gh` → `git remote add origin <url>` plus a browser push, or `curl` against the hosting API. FOUND-06 cannot be fully automated without network + credentials regardless (A2).

## Validation Architecture

> Omitted only if `workflow.nyquist_validation` is explicitly `false`. `.planning/config.json` sets `nyquist_validation: false` [VERIFIED: .planning/config.json], so this section is **advisory, not gating**. It is included anyway because Phase 1 is the phase that establishes the reproducibility harness every later phase depends on — the planner should still see it.

### Test Framework

| Property | Value |
|----------|-------|
| Framework | stdlib `unittest` (Python 3.14.7); no third-party runner |
| Config file | none — discovery by convention |
| Quick run command | `python3 -m unittest discover -s tools/tests -t . -v` |
| Full suite command | `python3 -m unittest discover -s tools/tests -t . -v && ./scripts/gate0.sh` |
| Engine gate command | `./src/stockfish bench 2>&1 \| grep -q '^Nodes searched *: *2497913$'` |
| Offline gate command | `unshare -rn make -C src -j$(nproc) build` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|--------------|
| FOUND-01 | `NOTICE` records URL, full SHA, tag, fork date, modified files, build command, `ARCH`, compiler, bench count; history real and tagged | smoke | `tools/check_notice.py` — asserts nine required `^Key:` lines, `Base commit` == `git rev-parse sf_19`, `Bench nodes` == `2497913` | ❌ Wave 0 |
| FOUND-02 | `Copying.txt`/`AUTHORS` byte-intact; every touched file keeps its GPLv3 header plus the dated modification line | smoke | `scripts/check_license.sh` — blob compare against `sf_19` + `grep -qE '^Modified by ChessChallendIII on [0-9]{4}-[0-9]{2}-[0-9]{2}:'` per file | ❌ Wave 0 |
| FOUND-03 | `PROVENANCE.md` declares net name/size/SHA/origin, TB inventory, dependency manifest; net marked non-authored | smoke | `tools/check_provenance.py` — `Bytes`==`98511183`, net hash matches on-disk file, `NOT AUTHORED BY THE TEAM` present, `fastchess` marked `Shipped? = no`, every TB filename ≤5 piece codes | ❌ Wave 0 |
| FOUND-04 | Build works fully offline; net present before the event; tree archived; clean namespace build proven on the laptop | integration | `unshare -rn make -C src -j$(nproc) build && ./src/stockfish bench \| grep -q '^Nodes searched *: *2497913$'` | ❌ Wave 0 |
| FOUND-05 | `docs/PROTOCOL.md` and `docs/LOGBOOK.md` frozen and committed **before** any implementation commit | smoke | `git merge-base --is-ancestor <docs-commit> <impl-commit>` for every impl path in `src/`, `console/`, `pipeline/` (excludes `tools/`) | ❌ Wave 0 |
| FOUND-06 | `sf_19` is an ancestor of `HEAD`; remotes declared; `RELEASE/` manifest committed; USB copy made | smoke + manual | `git merge-base --is-ancestor sf_19 HEAD && git remote -v \| grep -q origin && test -f RELEASE/SHA256SUMS` | ❌ Wave 0 |
| LIMIT-01 | `SyzygyProbeLimit` forced to 5 (upstream default 7); `MaxCardinality` asserted; effective value reported for the pre-game checklist | smoke | `printf 'uci\nquit\n' \| ./src/stockfish \| grep -q 'SyzygyProbeLimit.*default 5 min 0 max 5'`; plus a 6-man dir must exit 1 with `CRITICAL ERROR: TB CEILING VIOLATION` | ❌ Wave 0 |
| LIMIT-04 | No external request in a game; deps declared in a manifest; startup `doctor` fails if any asset path is remote or relative | unit | `python3 -m unittest tools.tests.test_doctor -v` — feeds a URL path and a relative path, asserts nonzero exit both times | ❌ Wave 0 |
| PIPE-01 | fastchess installed and working; SPRT recipe documented with the verified flags | integration | `tools/fastchess-linux-x86-64/fastchess --version` then `tools/sprt.sh BASE=… CUSTOM=… ROUNDS=2` and assert an `LLR:` line in the log | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `python3 -m unittest discover -s tools/tests -t .` (fast; no engine build)
- **Per wave merge:** full suite including the engine `bench` assertion
- **Phase gate:** offline build + `bench` + full suite all green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tools/check_notice.py` — covers FOUND-01
- [ ] `scripts/check_license.sh` — covers FOUND-02
- [ ] `tools/check_provenance.py` — covers FOUND-03
- [ ] `scripts/gate0.sh` — runs all of the above plus the offline build, `bench`, and ancestry assertion in sequence, so Gate 0 is one command rather than a checklist a tired operator can skip
- [ ] `tools/doctor.py` + `tools/tests/test_doctor.py` — covers LIMIT-04
- [ ] `tools/mock_engine.py`, `tools/mock_gui.py` — shared fixtures for the console and TM tracks (see OQ-10)
- [ ] `tools/sprt.md` + `tools/sprt.sh` — covers PIPE-01

Framework install: **none required** — `unittest` ships with CPython.

## Security Domain

`.planning/config.json` sets `workflow.security_enforcement: true`, `workflow.security_asvs_level: 1`, `workflow.security_block_on: "high"` [VERIFIED: .planning/config.json]. ASVS L1 is the floor, not the target: the checks below are tiered to what a local, single-operator, no-network tool actually exposes.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | No accounts, no login, single-operator local tool |
| V3 Session Management | no | No sessions; process lifetime is the session |
| V4 Access Control | no | Single user, local filesystem, no service boundary |
| V5 Input Validation | **yes** | `Board.parse_uci()` raises `InvalidMoveError` — the legality gate for operator-typed and opponent-announced moves. Never `parse()` blindly; never trust a FEN without a round-trip check |
| V6 Cryptography | **yes** (hash only) | SHA-256 via `hashlib` / `sha256sum` for artifact pinning. No hand-rolled crypto, no signing, no key management in this phase |
| V7 Error Handling & Logging | **yes** | Rule 9 log must never be silently truncated; engine stderr must surface, not be swallowed |
| V12 File & Resource | **yes** (path safety) | `SyzygyPath` and book paths are operator-supplied; validate the directory contents rather than trusting the string |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Malicious or wrong Syzygy directory (6/7-man files) → rule violation, not just a crash | Tampering | `TB_PROBE_LIMIT` guard + `on_path_change` `exit(1)` + console-side handshake assertion (LIMIT-01) |
| Substituted `.nnue` net presented as authored → Rule 15 disqualification | Tampering / Repudiation | Pin the full SHA-256 in `PROVENANCE.md` and prove it from the built artifact via `export_net` round-trip (FOUND-03) |
| Tampered or truncated history to hide provenance | Repudiation | Assert `sf_19` is an ancestor, keep `Copying.txt`/`AUTHORS` blob hashes identical to upstream, preserve all 7,252 commits (FOUND-01/FOUND-02/FOUND-06) |
| Unvalidated operator move string corrupting the game | Tampering | `parse_uci` + explicit promotion-suffix requirement + board/engine disagreement refusal (later phases; `PROTOCOL.md` freezes it in FOUND-05) |
| Build that silently reaches the network (violating Rule 14) | Information disclosure / Repudiation | `unshare -rn` build gate (FOUND-04) |
| `make net` exiting 0 after a failed fetch → an unverified net slips through | Repudiation | Verify the hash independently; never trust that exit code (OQ-4) |
| Partial/empty Rule 9 log → disqualification | Repudiation | Assert required fields on every move; fail closed, never write a partial line (schema frozen in FOUND-05) |

**Scope note:** Phase 1 has no network service, no authentication, and no untrusted remote input, so the high-severity surface is small. The genuine risks are *provenance integrity* (Rules 1/2/14/15) and *rule-limit enforcement* (Rules 3/4) — both treated above as tampering/repudiation rather than as conventional appsec.

## Sources

### Primary (HIGH confidence) — `[VERIFIED: …]`

Every claim tagged `[VERIFIED]` in this document rests on one of the three rows below. Source-code claims cite `file:line` and the values were read from the file in this session.

- **Stockfish 19 source tree**, `sf_19` @ `edb0d9db6731067ec50ce619ff372b463bc4dd5d` — read directly this session: `src/engine.cpp:124-127,133,153-158,168,266`; `src/syzygy/tbprobe.h:64`; `src/syzygy/tbprobe.cpp:68,99,105,595,1521,1524,1682,1916-1926`; `src/ucioption.cpp:137-158`; `src/Makefile:1007,1100,1211`; `src/nnue/network.cpp:49-50`; `src/misc.cpp:57,145`; `scripts/net.sh:14-26,74,77`. Upstream project: `https://github.com/official-stockfish/Stockfish`.
- **Live execution on this machine** — offline `unshare -rn make -C src -j12 build` (65 s), `bench` = 2,497,913, byte-identical rebuild (`077d3601…c4a79`), `export_net` round-trip identical, `SyzygyProbeLimit` guard patched+built and a 6-man directory rejected with exit 1, fastchess 2-game match and a real SPRT run producing an `LLR:` line.
- **`git` object inspection** — 7,252 upstream commits reachable from `sf_19`, tree not shallow; `Copying.txt` blob `f288702d2fa16d3cdf0035b15a9fcbc552cd88e7` and `AUTHORS` blob `b5ad83d591e343df95cf6b82ee27d8f7640f170a` identical at `sf_19` and `HEAD`.
- **`python-chess` 1.11.2 sdist**, sha256 `a8b43e5678fdb3000695bdaa573117ad683761e5ca38e591c4826eba6d25bb39` — vendored tree imported and exercised successfully.
- **fastchess `v1.8.2-alpha`** tarball sha256 `1003f920bebe841acdab5e6d7871e93171a4586857b3ec91c21ef5777f26ff96`; binary sha256 `3d0a8f3c8b837a96366ac838f3ddf6fe87b813abb4ad2852284c0ce409132566`.

### Secondary (MEDIUM confidence) — `[CITED: …]`

External documentation consulted but not re-derived by execution here. Nothing in Phase 1's plan should depend on these alone where a `[VERIFIED]` row exists.

- `[CITED: https://www.gnu.org/licenses/gpl-3.0.html]` — GPLv3 §4 (conveying verbatim copies) and §5(a) ("prominent notices stating that you changed the files and the date of any change"). This is the basis for the exact `Modified by ChessChallendIII on YYYY-MM-DD:` line in Q2.
- `[CITED: https://github.com/official-stockfish/networks]` — net distribution point and the **CC0-1.0** licence that makes the unmodified net shippable without copyleft interaction.
- `[CITED: https://python-chess.readthedocs.io/]` — `Board.parse_uci`, `InvalidMoveError`, `engine.INFO_ALL`, `chess.polyglot`, `chess.syzygy` API shapes used in Q10 and Pattern 3.
- `[CITED: https://github.com/Disservin/fastchess]` — MIT licence, release channel, `-sprt`/`-report penta` flag semantics, EPD/PGN-only openings (no Polyglot `.bin`).
- `[CITED: https://syzygy-tables.info]` — 3-4-5 mirror used as the `Retrieved from` value in `PROVENANCE.md` §2.
- `[CITED: docs/competition-rules.md]` — Rules 1–15 verbatim, the authority for every "Rule N" reference in this document.
- `[CITED: .planning/research/STACK.md, ARCHITECTURE.md, PITFALLS.md]` — internal research artifacts, cross-checked against the tree wherever they made source-level claims. Two of their assertions were found wrong and corrected here: the `option.Move_Overhead=100` spelling (OQ-8) and the `make -j profile-build` root-level command (Q4).

### Tertiary (LOW confidence) — `[ASSUMED]`

- `[ASSUMED]` The match laptop can run `sudo unshare -n`, or has unprivileged user namespaces enabled. Unverified — no access to that machine from here. See A1.
- `[ASSUMED]` The team will name a public host and provide a USB device for FOUND-06. No `origin` remote, no `gh`, no mounted media exist today. See A2.
- `[ASSUMED]` Python 3.14.7 is an acceptable interpreter for the vendored 1.11.2 tree. Imports and the legality gate were exercised here, but `STACK.md` pins 3.12 and no long run has been done on 3.14. See A4.

## Metadata

**Confidence breakdown:**
- Standard stack: **HIGH** — every version, hash, and build command was executed or read from the source tree this session.
- Architecture: **HIGH** for the engine-side guard and build/test wiring (built and tested); **MEDIUM** for the console/pipeline layout, which is design rather than verified code.
- Pitfalls: **HIGH** — each catalogued pitfall was either reproduced (net-fetch exit 0, `make -C src` no-op, `Move Overhead` quoting, stale ponder bestmove) or read from a cited source line.
- Provenance/compliance: **HIGH** on the technical assertions (blob hashes, ancestry, net hash); **MEDIUM** on how a judging panel will weigh them, which is a judgement call, not a fact.

**Research date:** 2026-10-26
**Valid until:** 2026-11-25 (30 days). Re-check only if the event date moves or a new Stockfish release lands; the frozen stack should not drift inside the competition window.

**Hard blockers carried forward:** A1 (`sudo unshare -n` on the match laptop) and A2 (no `origin` remote, no `gh`, no mounted external media for FOUND-06) must be resolved or explicitly descoped before Gate 0 can pass.

## Open Questions (RESOLVED)

> Numbered `OQ-*` to avoid colliding with the ten numbered research questions answered above (Q1–Q10). Every entry below was opened during this research and closed before writing. Raw `[ASSUMED]` risks that could not be closed here are in the Assumptions Log (A1–A7), not in this section.

### OQ-1: Does `syzygy/tbprobe.cpp` re-derive its ceiling from `TBPIECES`, making a new constant redundant?

**Answer:** No — `TBPIECES` is the on-disk format width, `MaxCardinality` is the runtime policy knob, and they are independent.

**Evidence:**
- `src/syzygy/tbprobe.cpp:105` — `#define TBPIECES 7` [VERIFIED: src/syzygy/tbprobe.cpp:105]. Reducing it changes the width of `Entry`/`Table` structs and the encoding, not the probe ceiling.
- `src/syzygy/tbprobe.h:64` — `extern int MaxCardinality;` [VERIFIED: src/syzygy/tbprobe.h:64] is the value the probe path actually consults.
- `src/engine.cpp:133` — `Option("SyzygyProbeLimit", Option::spin(7, 0, 7))` [VERIFIED: src/engine.cpp:133] clamps to 7 by default.

**RESOLVED:** Introduce `TB_PROBE_LIMIT = 5` in `src/syzygy/tbprobe.h` beside `MaxCardinality`, force `MaxCardinality = std::min(MaxCardinality, TB_PROBE_LIMIT)` on every mutation site, and narrow the UCI Option to `Option::spin(TB_PROBE_LIMIT, 0, TB_PROBE_LIMIT)`. Leave `TBPIECES 7` untouched. Verified end-to-end: option reports `default 5 min 0 max 5`, a 6-man directory triggers `info string CRITICAL ERROR: TB CEILING VIOLATION` and exit 1, and `bench` still yields 2,497,913.

### OQ-2: Can the `SyzygyPath` setter fail loudly, or does Stockfish swallow option errors?

**Answer:** It can fail loudly — `on_change` is an unconstrained callback, so it may `exit(1)` after printing via the `sync_cout` mechanism.

**Evidence:** `src/engine.cpp:124-127` registers `SyzygyPath` with an `on_change` lambda [VERIFIED: src/engine.cpp:124-127]; option callbacks run inside the UCI `setoption` handler, and no `try`/`catch` or status return wraps them, so a hard `exit(1)` propagates.

**RESOLVED:** The `SyzygyPath` `on_change` handler scans the directory for `*.rtbw`/`*.rtbz`, and on any name implying >5 men prints the CRITICAL ERROR line and calls `exit(1)`. The console's startup self-check treats a missing `bestmove`/`uciok` handshake after `setoption` as fatal too, so a silent engine death is caught on the console side as a second net.

### OQ-3: Is `make -j` at the repo root the build command?

**Answer:** No. The root has no `Makefile`; the build lives entirely in `src/`.

**Evidence:** `src/Makefile:1007` declares `help:` as the default goal [VERIFIED: src/Makefile:1007], and `src/Makefile:1100` declares `build: net config-sanity` [VERIFIED: src/Makefile:1100]. Running `make -C src` with no target prints help and exits 0 — a no-op that looks like success.

**RESOLVED:** Document `make -C src -j$(nproc) build` (or `profile-build`) everywhere, including `docs/build.md` and the Gate 0 checklist. Any CI/script line that says `make -j` is a defect: it exits 0 and produces no binary.

### OQ-4: Does a failed net fetch abort the build?

**Answer:** Not at the fetch step — `make net` exits 0 even when `scripts/net.sh` fails, and the real error surfaces much later at LTO link.

**Evidence:** `scripts/net.sh:74` contains `return 1` on validation failure [VERIFIED: scripts/net.sh:74], and that status is discarded at `scripts/net.sh:77` [VERIFIED: scripts/net.sh:77]. `scripts/net.sh:14-26` performs the SHA-256 prefix validation [VERIFIED: scripts/net.sh:14-26]. The downstream symptom is `Error: file not found: nn-1a298aa575a0.nnue` from the linker.

**RESOLVED:** Never trust the exit code of `make net`. `docs/build.md` must instruct the operator to assert the file's existence and full SHA-256 (`1a298aa575a085434d29027978dc36867fe9c5bcea9376654b7a8eba1e52dfc2`) *before* invoking `build`. The Gate 0 script asserts size `98,511,183` bytes and that hash; a mismatch aborts.

### OQ-5: Does `NNUE_EMBEDDING_OFF` change the reproducible `bench` constant?

**Answer:** The constant is stable for the shipped embedded build, which is the only configuration we ship; do not build the embedding-off variant at all.

**Evidence:** `src/nnue/network.cpp:49-50` uses `INCBIN(EmbeddedNNUE, EvalFileDefaultName)` [VERIFIED: src/nnue/network.cpp:49-50], so the net is linked into the binary and no external path is consulted. Offline `unshare -rn` build reproduced `bench` = 2,497,913 and a byte-identical binary (`sha256 077d3601b503c369f97ed06df73cd5f3b44fd3d3fa513e31c92065da992c4a79`).

**RESOLVED:** Freeze the embedded build as the only sanctioned artifact. `docs/build.md` records `bench` = **2,497,913** as the Gate 0 assertion value, plus `ARCH=x86-64-avxvnni`, `g++ (GNUC) 16.2.1 on Linux`, and the binary hash above as the reference datum.

### OQ-6: Does `export_net` give us an independent way to prove the embedded net is unmodified?

**Answer:** Yes — the round-trip is byte-identical, which is a cheap provenance proof that does not require trusting the build log.

**Evidence:** Running `export_net` on the built binary emitted a file byte-identical to the archived `nn-1a298aa575a0.nnue`; the archive itself hashes to `1a298aa575a085434d29027978dc36867fe9c5bcea9376654b7a8eba1e52dfc2` at 98,511,183 bytes.

**RESOLVED:** Add `./src/stockfish export_net /tmp/exported.nnue && sha256sum /tmp/exported.nnue` to the Gate 0 script and compare against the pinned hash. This proves "official Stockfish 19 network, unmodified" from the artifact itself — exactly the claim `PROVENANCE.md` must make under Rule 15.

### OQ-7: How do we vendor `python-chess` given there is no system `pip`?

**Answer:** Copy the pure-Python package tree in; do not attempt a pip install, and do not attempt to build a wheel offline.

**Evidence:** `chess` 1.11.2 sdist sha256 `a8b43e5678fdb3000695bdaa573117ad683761e5ca38e591c4826eba6d25bb39`; PyPI publishes **only** an sdist for 1.11.2 (no wheel); the pip route fails offline with `BackendUnavailable: Cannot import 'setuptools.build_meta'`. A copied `chess/` tree imports cleanly on Python 3.14.7.

**RESOLVED:** `vendor/chess/` holds the `chess/` package plus upstream `LICENSE.txt`; the console imports from there via a `sys.path` insert at startup. `requirements.txt` documents `chess==1.11.2` with the sdist hash for auditability, but nothing is installed at match time.

### OQ-8: Does `option.Move_Overhead=100` work in fastchess?

**Answer:** No — spaces in UCI option names are **not** normalised to underscores by fastchess; the key must be quoted verbatim with its space.

**Evidence:** A fastchess run with `option.Move_Overhead=100` silently ignored the option (confirmed in the trace log, where the sent `setoption` line retained the underscore form and the engine reported the default). The working form is `"option.Move Overhead=100"`.

**RESOLVED:** Every fastchess invocation in `tools/` quotes the option as `"option.Move Overhead=100"`, applied symmetrically to both engines so the comparison stays fair. The SPRT script greps its own trace log for `Move Overhead` set to `100` and aborts if absent.

### OQ-9: Which tests can actually run in Phase 1?

**Answer:** `unittest` from the standard library only; `pytest` is not installed and Phase 1 must not depend on it.

**Evidence:** `python3 --version` → 3.14.7; `pytest` is absent; `python3 -m venv` does yield `pip 26.2.1`, so a venv *could* install pytest, but that reintroduces an offline-dependent step into a phase whose entire point is offline determinism.

**RESOLVED:** Phase 1 tests use `unittest` (`python3 -m unittest discover -s tools/tests -t .`, since every Phase-1 test covers a `tools/` or `scripts/` artefact). The Validation Architecture section is written against `unittest`. If a later phase wants pytest, that is a Wave 0 dependency to add deliberately, not an assumption.

### OQ-10: Where do the mock engines live — `console/tests/fixtures/` or `tools/`?

**Answer:** `tools/`, deliberately departing from `.planning/research/ARCHITECTURE.md` §6.

**Evidence:** ARCHITECTURE.md §6 sketches fixtures under `console/tests/fixtures/`. The mocks must also be usable by hand during dry runs and by the Gate 0 rehearsal, which is a `tools/` concern, not a test-internal one.

**RESOLVED:** `tools/mock_engine.py` (speaks enough UCI to exercise the console: `uci`/`isready`/`position`/`go`/`stop`/`bestmove`, with scriptable illegal-move and timeout behaviours) and `tools/mock_gui.py` (drives the console as an opponent would). Phase 2's `console/tests/` imports them by path; Phase 1 does not create `console/` at all. The deviation is recorded in `docs/` so a reviewer does not read it as drift.
