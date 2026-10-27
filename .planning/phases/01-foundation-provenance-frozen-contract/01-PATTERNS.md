# Phase 1: Foundation, Provenance & Frozen Contract — Pattern Map

**Mapped:** 2026-10-26
**Files analyzed:** 35 (22 new, 5 modified, 8 vendored/generated artefacts)
**Analogs found:** 17 / 35 (18 files are docs/provenance with no in-repo analog — see §No Analog Found)

**Source of file list:** `01-RESEARCH.md` §Recommended Project Structure (lines 171-206), §Q2 touched-file table (lines 638-647), §Q4 evidence artefact (783-791), §Q7 doctor check list (885-906), §Q8 install recipe (912-949), §Q9 mocks (953-977), §Q10 vendoring (979-988).

**Tracked-source gate:** every analog below was verified with `git ls-files -- <path>` (non-empty). No `.gsd/capabilities/` mirrors exist in this repo; nothing to substitute.

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `src/syzygy/tbprobe.h` | engine constant | transform (policy value) | `src/syzygy/tbprobe.h:64` (`extern int MaxCardinality;`) | exact |
| `src/syzygy/tbprobe.cpp` | engine constant (adjacent edit) | transform | `src/syzygy/tbprobe.cpp:105` (`constexpr int TBPIECES = 7;`) | exact |
| `src/engine.cpp` (option decl) | engine config | request-response (UCI `setoption`) | `src/engine.cpp:69-139` (option registration block) | exact |
| `src/engine.cpp` (`verify_tb_ceiling`, `go`, `search_clear`) | engine verify | request-response | `src/engine.cpp:266-299` (`verify_network`) | exact |
| `src/engine.h` | engine header | — | `src/engine.h:93-100`, `:135` | exact |
| `.gitignore` | config | — | `.gitignore:18-24` (already carries the net negation) | exact (already modified) |
| `scripts/check_license.sh` | shell checker | batch | `tests/signature.sh` | role-match |
| `scripts/gate0.sh` | shell gate | batch | `tests/perft.sh` + `tests/signature.sh` | role-match |
| `tools/offline_build.sh` | shell evidence producer | batch / file-I/O | `tests/signature.sh` (+ `scripts/net.sh` for POSIX style) | role-match |
| `tools/check_notice.py` | python checker | file-I/O | `tests/instrumented.py` (argparse + exit-code shape) | partial |
| `tools/check_provenance.py` | python checker | file-I/O | same | partial |
| `tools/check_offline_build.py` | python checker | file-I/O + subprocess | `tests/testing.py:264-330` (`Stockfish` subprocess wrapper) | role-match |
| `tools/check_contract_order.py` | python checker | batch (git subprocess) | `tests/testing.py:264-330` (subprocess capture) | partial |
| `tools/build_manifest.py` | python tool | file-I/O | `tests/testing.py:71-97` (`Syzygy` path helper) | partial |
| `tools/check_phase1.py` | python driver | batch | `tests/instrumented.py:__main__` block | role-match |
| `tools/doctor.py` | python CLI | file-I/O + subprocess | `tests/instrumented.py` (argparse CLI) + `tests/testing.py:264-330` | role-match |
| `tools/mock_engine.py` | python process | request-response (stdin/stdout loop) | `src/uci.cpp:95-140` (read-loop) + `tests/testing.py:290-330` | partial |
| `tools/mock_gui.py` | python driver | request-response (subprocess pipe) | `tests/testing.py:264-370` (`Stockfish` class) | role-match |
| `tools/tests/test_doctor.py` (+ peers) | python test | unit | `tests/instrumented.py` (test class layout) | role-match |
| `tools/sprt.sh` | shell wrapper | batch | `tests/signature.sh` | role-match |
| `tools/sprt.md` | doc (recipe) | — | none | none |
| `NOTICE` | doc/compliance | — | none | none |
| `PROVENANCE.md` | doc/compliance | — | none | none |
| `docs/PROTOCOL.md` | doc/spec (frozen) | — | `docs/competition-rules.md` (format only) | partial |
| `docs/LOGBOOK.md` | doc/spec (frozen) | — | `docs/competition-rules.md` (format only) | partial |
| `docs/build.md` | doc | — | `README.md:88-106` ("Compiling Stockfish") | partial |
| `requirements-game.txt` | config (declaration) | — | none | none |
| `evidence/01-offline-build.log` | generated artefact | file-I/O | none (output of `tools/offline_build.sh`) | n/a |
| `evidence/01-contract-freeze.txt` | generated artefact | file-I/O | none (output of `check_contract_order.py`) | n/a |
| `RELEASE/SHA256SUMS` | generated artefact | file-I/O | none (output of `build_manifest.py`) | n/a |
| `RELEASE/README.md` | doc | — | `README.md` | partial |
| `vendor/chess/` | vendored third-party | — | none in-repo | none |
| `vendor/chess/LICENSE.txt` | vendored licence | — | `Copying.txt` (role only) | partial |
| `tools/fastchess-linux-x86-64/` | vendored third-party binary | — | none in-repo | none |
| `AGENTS.md` | generated doc | — | self (GSD-generated; do not hand-edit) | n/a |

---

## Pattern Assignments

### `src/syzygy/tbprobe.h` + `src/syzygy/tbprobe.cpp` (engine constant)

**Analog:** `src/syzygy/tbprobe.h` (the `MaxCardinality` declaration), `src/syzygy/tbprobe.cpp:105` (`TBPIECES`).

**Where the constant goes — `src/syzygy/tbprobe.h:55-66` (existing):**
```cpp
// Possible states after a probing operation
enum ProbeState {
    FAIL              = 0,   // Probe failed (missing file table)
    OK                = 1,   // Probe successful
    CHANGE_STM        = -1,  // DTZ should check the other side
    ZEROING_BEST_MOVE = 2    // Best move zeroes DTZ (capture or pawn move)
};

extern int MaxCardinality;


void     init(const std::string& paths);
```
Add the new constant immediately after `extern int MaxCardinality;` (RESEARCH Q6, line 1178), following the existing `constexpr int` idiom at `src/syzygy/tbprobe.cpp:105`:
```cpp
constexpr int TBPIECES = 7;  // Max number of supported pieces
```
→ new line: `constexpr int TB_PROBE_LIMIT = 5;  // ChessChallendIII Rule 4 ceiling (3-4-5 only)`

**Two hard constraints from RESEARCH (do not deviate):**
1. `TBPIECES` **must stay 7** (`tbprobe.cpp:105`, and the `NO_TABLEBASES` stub block at `tbprobe.cpp:63-96` defines `int MaxCardinality;` separately). Reducing `TBPIECES` is a buffer-overflow risk, not a compliance win (RESEARCH line 879, A5).
2. `constexpr` at namespace scope in the header is fine — it is used by `src/engine.cpp`, which already `#include "syzygy/tbprobe.h"` at line 42.

**GPL modification line (FOUND-02):** both files need it, one line after the closing `*/` of the header block (`tbprobe.h:1-17` and `tbprobe.cpp:1-17` both carry the upstream GPLv3 block verbatim — do not edit inside it):
```
Modified by ChessChallendIII on 2026-10-26: enforce the Rule 4 five-piece tablebase ceiling. See NOTICE and PROVENANCE.md.
```

---

### `src/engine.cpp` — option declaration (config, request-response)

**Analog:** `src/engine.cpp:69-139` — the whole option-registration block in `Engine::Engine`. This is the single most important pattern in Phase 1.

**Existing shape, verbatim (`src/engine.cpp:83-139`):**
```cpp
    options.add(  //
      "Threads", Option(1, 1, MaxThreads, [this](const Option&) {
          resize_threads();
          return thread_allocation_information_as_string();
      }));

    options.add(  //
      "Hash", Option(16, 1, MaxHashMB, [this](const Option& o) {
          set_tt_size(o);
          return std::nullopt;
      }));
    ...
    options.add(  //
      "SyzygyPath", Option("", [](const Option& o) {
          Tablebases::init(o);
          return std::nullopt;
      }));

    options.add("SyzygyProbeDepth", Option(1, 1, 100));

    options.add("Syzygy50MoveRule", Option(true));

    options.add("SyzygyProbeLimit", Option(7, 0, 7));
```

**What changes (RESEARCH Q6, lines 850-868):**
- Line 133 → `options.add("SyzygyProbeLimit", Option(Tablebases::TB_PROBE_LIMIT, 0, Tablebases::TB_PROBE_LIMIT));`
- Lines 124-127 → the `SyzygyPath` lambda gains the post-`init` ceiling check and `std::exit(1)` on breach.

**Why the `on_change` return value is the *reporting* channel** — `src/ucioption.cpp:176-184`:
```cpp
    if (on_change)
    {
        const auto ret = on_change(*this);

        if (ret && parent != nullptr && parent->info != nullptr)
            parent->info(ret);
    }
```
`OnChange = std::function<std::optional<std::string>(const Option&)>` (`src/ucioption.h:44`). A returned string becomes `info string <line>` via `src/uci.cpp:60-67`. **Returning a string cannot block the operation** — for the fatal case the lambda must print and `exit(1)`.

**Why a loud exit is required, not an error return** — `src/ucioption.cpp:151-158`:
```cpp
Option& Option::operator=(const std::string& v) {

    assert(!type.empty());

    if ((type != "button" && type != "string" && v.empty())
        || (type == "check" && v != "true" && v != "false")
        || (type == "spin" && !value_in_range(v, min, max)))
        return *this;      // ← silent no-op: `setoption … value 7` is swallowed
```
This is exactly RESEARCH Pitfall 5. The test must assert the *observable consequence* (option listing text + attestation line + 6-man-directory exit 1), never the return code of `setoption`.

**Copy the `on_change` idiom exactly:** trailing `//` comment for clang-format control, lambda captures `[]`/`[this]` matched to need, `return std::nullopt;` when there is nothing to report. `.clang-format` uses `BasedOnStyle: WebKit`, `AlignConsecutiveAssignments: Consecutive`, 4-space indent, 100-col limit.

**GPL line** required for `src/engine.cpp`.

---

### `src/engine.cpp` — `verify_tb_ceiling()` + call sites (engine verify)

**Analog:** `src/engine.cpp:266-299` (`Engine::verify_network`) — the attestation pattern to imitate.

**Existing verify pattern, verbatim (`src/engine.cpp:266-299`, excerpt):**
```cpp
void Engine::verify_network() const {
    const auto file = path_from_utf8(std::string(options["EvalFile"]));
    network->verify(onVerifyNetwork, networkFile, file);

    auto statuses = network.get_status_and_errors();
    for (usize i = 0; i < statuses.size(); ++i)
    {
        const auto [status, error] = statuses[i];
        std::string message        = "Network replica " + std::to_string(i + 1) + ": ";
        ...
        if (error.has_value())
        {
            message += " " + *error;
        }

        onVerifyNetwork(message);
    }
}
```

**Where it is called (the two hook points Phase 1 needs):**
```cpp
void Engine::go(Search::LimitsType& limits) {   // src/engine.cpp:153-158
    assert(limits.perft == 0);
    verify_network();

    threads.start_thinking(options, pos, states, limits);
}

void Engine::search_clear() {                   // src/engine.cpp:161-169
    wait_for_search_finished();

    tt.clear(threads);
    threads.clear();

    // TODO: does not work with multiple instances
    Tablebases::init(options["SyzygyPath"]);  // Free mapped files
}
```

**Placement rule from RESEARCH (Q6, lines 850-868):** the `search_clear` call must come **after** `Tablebases::init(...)` (line 168), because `init` is what populates `MaxCardinality` (`src/syzygy/tbprobe.cpp:1519-1524`):
```cpp
void Tablebases::init(const std::string& paths) {

    TBTables.clear();
    MaxCardinality = 0;
    TBFile::Paths.clear();
```

**Signature and header placement** — copy `verify_network`'s declaration style, `src/engine.h:95-100`:
```cpp
    // network related

    void                                 verify_network() const;
    std::unique_ptr<Eval::NNUE::Network> get_default_network();
    void                                 load_network(const std::filesystem::path& file);
    void                                 save_network(const std::optional<std::filesystem::path>& file);
```
→ add `std::optional<std::string> verify_tb_ceiling() const;` in a new `// tablebase related` group directly below, and add to the private section near `:135`:
```cpp
    std::function<void(std::string_view)> onVerifyNetwork;
```

**Reporting to stdout:** the string produced by `verify_tb_ceiling()` is fed to the existing `onVerifyNetwork` sink, so no new plumbing is needed. Registration side is `src/uci.cpp:91`:
```cpp
    engine.set_on_verify_network([](const auto& s) { print_info_string(s); });
```
and the formatter is `src/uci.cpp:60-67`:
```cpp
void UCIEngine::print_info_string(std::string_view str) {
    sync_cout_start();
    for (auto& line : split(str, "\n"))
    {
        if (!is_whitespace(line))
        {
            std::cout << "info string " << line << '\n';
        }
    }
    sync_cout_end();
}
```
**Consequence for the plan:** multi-line strings are legal (split on `\n`), but each becomes its own `info string` line. Keep `verify_tb_ceiling()` single-line so `grep -q 'TB ceiling OK: SyzygyProbeLimit=5'` stays a valid assertion.

**Fatal-path pattern to copy** — `src/uci.cpp:697-703`:
```cpp
void UCIEngine::terminate_on_critical_error(const std::string& message) {
    sync_cout << "info string CRITICAL ERROR: Command `" << currentCmd
              << "` failed. Reason: " << message << '\n'
              << sync_endl;
    std::exit(1);
}
```
**Do not call this function** from `engine.cpp` (it is a `UCIEngine` private member, `src/uci.h:79`). Instead replicate the *output shape* from inside the `SyzygyPath` lambda, keeping the verified literal prefix `info string CRITICAL ERROR: TB CEILING VIOLATION: …` so the Phase-1 test regex `CRITICAL ERROR: TB CEILING VIOLATION` matches. Use `sync_cout` (from `misc.h`, already included at `src/engine.cpp:34`).

**Verified behaviour to reproduce exactly (RESEARCH lines 288-297):**

| Stimulus | Expected |
|---|---|
| `uci` | `option name SyzygyProbeLimit type spin default 5 min 0 max 5` |
| `setoption … value 7` | silently clamped; attestation still `=5` |
| `setoption … value 0` | accepted; attestation `=0 max_loaded=0` |
| `SyzygyPath` with a 6-man `.rtbw` | `info string CRITICAL ERROR: TB CEILING VIOLATION: tablebase directory contains 6-man files (required <= 5)` then exit 1 |
| `bench` | 2,497,913 (unchanged) |

---

### `scripts/check_license.sh` (shell checker, batch)

**Analog:** `tests/signature.sh` — the closest existing "compare against a reference and exit nonzero" shell gate in the tree.

**Analog, verbatim (`tests/signature.sh:1-38`):**
```bash
#!/bin/bash
# obtain and optionally verify Bench / signature
# if no reference is given, the output is deliberately limited to just the signature

STDOUT_FILE=$(mktemp)
STDERR_FILE=$(mktemp)

error()
{
  echo "running bench for signature failed on line $1"
  echo "===== STDOUT ====="
  cat "$STDOUT_FILE"
  echo "===== STDERR ====="
  cat "$STDERR_FILE"
  rm -f "$STDOUT_FILE" "$STDERR_FILE"
  exit 1
}
trap 'error ${LINENO}' ERR

EXE=${EXE:-./stockfish}
eval "$RUN_PREFIX $EXE bench" > "$STDOUT_FILE" 2> "$STDERR_FILE" || error ${LINENO}
signature=$(grep "Nodes searched  : " "$STDERR_FILE" | awk '{print $4}')
```
Conventions worth copying: `#!/bin/bash`, `error()` helper with `trap 'error ${LINENO}' ERR`, `EXE=${EXE:-./stockfish}` style env override, `2> "$STDERR_FILE"` because **bench writes to stderr** (`src/uci.cpp:309-311` uses `std::cerr`), and `exit 1` on any mismatch.

**POSIX-sh alternative** for scripts that must run without bash — `scripts/net.sh:1-12`:
```sh
#!/bin/sh

# download commands with a 5min time-out to ensure things fail if the server stalls
wget_or_curl=$( (command -v wget >/dev/null 2>&1 && echo "wget -qO- --timeout=300 --tries=1") ||
  (command -v curl >/dev/null 2>&1 && echo "curl -skL --max-time 300"))

sha256sum=$( (command -v shasum >/dev/null 2>&1 && echo "shasum -a 256") ||
  (command -v sha256sum >/dev/null 2>&1 && echo "sha256sum"))
```
Use this `command -v` capability-probe idiom for `sha256sum`/`shasum` in `gate0.sh` and `offline_build.sh` — it is the in-tree convention and it works on macOS too.

**What `check_license.sh` must contain:** RESEARCH Q2, lines 663-687, gives the exact script. Key shape (note `fail=0` accumulator + `exit $fail`, so *every* violation is reported in one run rather than the first):
```sh
#!/bin/sh
# FOUND-02: licence headers, integrity and modification notices.
set -eu
fail=0

for f in Copying.txt AUTHORS; do
  a=$(git rev-parse "sf_19:$f"); b=$(git rev-parse "HEAD:$f")
  [ "$a" = "$b" ] || { echo "FAIL: $f differs from sf_19"; fail=1; }
done
```
**Baseline is git, not a sidecar hash** — do not create `Copying.txt.sha256` (RESEARCH line 659). Verified today both blobs match: `Copying.txt` → `f288702d2fa16d3cdf0035b15a9fcbc552cd88e7`, `AUTHORS` → `b5ad83d591e343df95cf6b82ee27d8f7640f170a`.

**Permissions:** existing `scripts/*.sh` are `-rwxr-xr-x`. Chmod new scripts to match (`chmod +x`).

---

### `scripts/gate0.sh` (shell gate, batch)

**Analog:** `tests/perft.sh` — multi-check script with a `TESTS_FAILED` accumulator and a single final exit code.

**Analog, verbatim (`tests/perft.sh:1-15, 87-93`):**
```bash
#!/bin/bash
# verify perft numbers (positions from https://www.chessprogramming.org/Perft_Results)

TESTS_FAILED=0

error()
{
  echo "perft testing failed on line $1"
  exit 1
}
trap 'error ${LINENO}' ERR

echo "perft testing started"

EXPECT_SCRIPT=$(mktemp)
...
rm -f $EXPECT_SCRIPT
echo "perft testing completed"

if [ $TESTS_FAILED -ne 0 ]; then
  echo "Some tests failed"
  exit 1
fi
```
Conventions to copy: `#!/bin/bash`, banner `echo "<name> testing started"`, `trap ... ERR`, temp-file via `mktemp` and `rm -f` before exit, aggregate failure → single nonzero exit.

**Structure for `gate0.sh` (RESEARCH line 1085 + Validation Architecture 1076-1080):** sequential, fail-fast, each step one line of output, one final exit code:
1. `scripts/check_license.sh`
2. `python3 tools/check_notice.py`
3. `python3 tools/check_provenance.py`
4. `python3 tools/check_contract_order.py`
5. `python3 -m unittest discover -s tools/tests -t . -v`
6. `tools/offline_build.sh` (or the fast path when `--skip-build` is passed)
7. `./src/stockfish bench 2>&1 | grep -q '^Nodes searched *: *2497913$'`
8. `python3 tools/check_phase1.py` (aggregator with `--json`)

**Never** write `make -j` or `make` in this script. The only valid build command is `make -C src -j"$(nproc)" build` (RESEARCH Pitfall 1: root has no Makefile; `make -C src` default goal is `help:` at `src/Makefile:1007` and exits 0 building nothing).

---

### `tools/offline_build.sh` (shell evidence producer, batch/file-I/O)

**Analog:** `tests/signature.sh` for the "capture stderr, grep the node count, exit nonzero on mismatch" core; `scripts/net.sh` for POSIX-sh capability probing.

**Full script skeleton is given in RESEARCH lines 428-469** (`tools/offline_build.sh`, `set -eu`, `CLONE="${1:-$(mktemp -d)/chess}"`, `NET_LOG="$(mktemp)"`). Load-bearing fragments to preserve verbatim:
```sh
# 2) clean room — otherwise the build proves nothing
make -C src objclean

# 3) build with no network at all
if unshare -n true 2>/dev/null; then NS=unshare -n
elif unshare -rn true 2>/dev/null; then NS=unshare -rn
else echo "FATAL: no network namespace available" >&2; exit 1; fi
echo "namespace: $NS" > "$NET_LOG"

$NS make -C src -j"$(nproc)" build 2>&1 | tee -a "$NET_LOG"
test -x src/stockfish
```
```sh
# 5) bench must match the declared node count
NODES=$(src/stockfish bench 2>&1 | sed -n 's/^Nodes searched  : //p')
test "$NODES" = "2497913" || { echo "bench mismatch: $NODES" >&2; exit 1; }
```
Notes the planner must encode: `bench` writes its summary to **stderr** (both streams captured with `2>&1`); `objclean` is mandatory (`src/Makefile:1211`); the `unshare -n` → `unshare -rn` fallback must be recorded in the evidence log (RESEARCH Pitfall 6 / A1); **never** gate on `make net` (`scripts/net.sh:74` ends `return 1`, discarded at `:77`, so it exits 0 on total failure).

---

### `tools/check_notice.py`, `tools/check_provenance.py` (python checkers, file-I/O)

**Analog:** `tests/instrumented.py` — the only tracked Python CLI-with-exit-code in the tree.

**Analog, `tests/instrumented.py:1-27` (imports + module constants):**
```python
import argparse
import re
import sys
import subprocess
import pathlib
import os
import fnmatch

from testing import (
    EPD,
    Stockfish as Engine,
    MiniTestFramework,
    OrderedClassMembers,
    Valgrind,
    Syzygy,
)

PATH = pathlib.Path(__file__).parent.resolve()
CWD = os.getcwd()
```
**Copy:** `pathlib` for all paths, `re` for regex assertions, `sys.exit(...)` for the verdict, `pathlib.Path(__file__).parent.resolve()` to anchor file lookups (this is the in-tree idiom for "find my own directory").

**Do NOT copy:** `import requests` from `tests/testing.py:17`, and do **not** copy `from testing import …`. Phase-1 tools must be stdlib-only and importable from the repo root, because `doctor.py` runs with no `PYTHONPATH` tricks (RESEARCH Q7, line 883). Also `tests/testing.py` downloads Syzygy over the network (`Syzygy.download_syzygy`, lines 77-97) — a Rule 14 violation if reused.

**Analog, `tests/instrumented.py` exit-code tail (lines 1055-1073 of that file, `__main__` block):**
```python
if __name__ == "__main__":
    args = parse_args()
    ...
    if framework.has_failed():
        sys.exit(1)

    sys.exit(0)
```
**Copy this shape:** `parse_args()` → do work → `sys.exit(0|1)`. Nothing else.

**Body shape** is fixed by RESEARCH Pattern 1 (lines 216-238): a `must(pattern, label)` helper that `sys.exit(f"FAIL NOTICE: missing {label}")`, then one `must(...)` call per required field, then `print("OK NOTICE")`. Reuse the skeleton verbatim; only the regexes change. Required `^Key:` set for `NOTICE` is RESEARCH Q1 lines 609-620; for `PROVENANCE.md` it is Q3 line 758.

**GPL header:** new `.py` files are "new source files of ours" and need a header (RESEARCH Q2, line 645). Adapt the C block from `src/engine.cpp:1-17` into a Python docstring — no existing Python file in the tree has one, so this is spec'd by RESEARCH, not by analogy:
```python
# ChessChallendIII — FOUND-01 NOTICE checker
# Copyright (C) 2026 ChessChallendIII
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# ... (rest of GPLv3 block) ...
```

---

### `tools/doctor.py` (python CLI, file-I/O + subprocess)

**Analog:** `tests/instrumented.py` for the argparse CLI; `tests/testing.py:264-330` for the engine-subprocess plumbing.

**CLI pattern, `tests/instrumented.py` (`parse_args`):**
```python
def parse_args():
    parser = argparse.ArgumentParser(description="Run Stockfish with testing options")
    parser.add_argument("--valgrind", action="store_true", help="Run valgrind testing")
    ...
    parser.add_argument("stockfish_path", type=str, help="Path to Stockfish binary")

    return parser.parse_args()
```
Copy: `argparse` with `action="store_true"` flags and a positional path. `doctor.py` needs `--json` from day 0 (RESEARCH line 904) so CHECK-01 can assert on the report.

**Subprocess pattern, `tests/testing.py:264-333` (the `Stockfish` class) — the closest thing in-repo to "start a UCI process and read its output":**
```python
        self.process = subprocess.Popen(
            self.prefix + [self.path] + self.args,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            bufsize=1,
        )
        self.reader_thread = threading.Thread(
            target=self._read_process_output, daemon=True
        )
        self.reader_thread.start()
```
and the liveness guard (line 285-289):
```python
    def _check_process_alive(self):
        if not self.process or self.process.poll() is not None:
            print("\n".join(self.output))
            raise RuntimeError("Stockfish process has terminated")
```
**Copy:** `Popen(..., stdin/stdout=PIPE, universal_newlines=True, bufsize=1)` + reader thread + queue, and always `poll()` before writing — the engine can `exit(1)` on a TB violation, and a write to a dead pipe raises `BrokenPipeError`.
**Add beyond the analog:** an explicit `timeout` per read (the analog uses `MAX_TIMEOUT = 60 * 5` at line 26 but only in the test framework). `doctor.py` must never hang: `uci`/`isready`/`export_net` only, hard wall-clock cap, `finally: proc.kill()`.

**Check list to implement** is enumerated in RESEARCH Q7, lines 887-902 (14 checks). Two of them decide the phase:
- check 1 — reject `http://`, `https://`, `ftp://`, `git@`, `s3://`, `~`, `$VAR`, and any non-`/`-leading path, then `Path.resolve()` and re-test. LIMIT-04's "fails if any asset path is remote or relative" is *this* check.
- check 7 — tokenise `KQRRBvK` → 6 pieces → `FAIL`. LIMIT-01's defence-in-depth layer.

**Hard rule:** `doctor.py` must not start a search (RESEARCH line 906). `uci`, `isready`, `export_net` only.

---

### `tools/mock_engine.py` (python process, request-response stdin/stdout loop)

**Analog:** `src/uci.cpp:95-140` is the *behaviour* being imitated (the reference read-loop); `tests/testing.py:334-346` is the closest in-repo Python for writing UCI commands.

**Reference loop, `src/uci.cpp:95-140` (excerpt):**
```cpp
        if (cli.argc == 1
            && !getline(std::cin, cmd))  // Wait for an input or an end-of-file (EOF) indication
            cmd = "quit";

        currentCmd = cmd;
        std::istringstream is(cmd);

        token.clear();  // Avoid a stale if getline() returns nothing or a blank line
        is >> token;

        if (token == "quit" || token == "stop")
            engine.stop();
        ...
        else if (token == "uci")
        {
            sync_cout << "id name " << engine_info(true) << "\n"
                      << engine.get_options() << sync_endl;

            sync_cout << "uciok" << sync_endl;
        }

        else if (token == "setoption")
            setoption(is);
```
**Copy these invariants into the mock:** EOF on stdin behaves like `quit` and exits 0 (verified at `src/uci.cpp:104-107`); token is cleared before parsing; `uci` reply is `id name …` + the option list + `uciok`; `stop` is legal without a search.

**Option-list rendering to imitate** — `src/ucioption.cpp:187-212`:
```cpp
                os << "\noption name " << it.first << " type " << o.type;
                ...
                else if (o.type == "spin")
                    os << " default " << stoi(o.defaultValue) << " min " << o.min << " max "
                       << o.max;
```
So the mock must print exactly `option name SyzygyProbeLimit type spin default 5 min 0 max 5` (RESEARCH line 958 and the verified snapshot at line 509).

**Verbose-op support, `tests/testing.py:334-346`:**
```python
    def setoption(self, name: str, value: str):
        self.send_command(f"setoption name {name} value {value}")

    def send_command(self, command: str):
        if not self.process:
            raise RuntimeError("Stockfish process is not started")
```
Copy the `setoption name {name} value {value}` string shape verbatim — it is what the console will emit and what the mock must parse (name and value may contain spaces; parse by splitting on the ` value ` keyword, mirroring `src/ucioption.cpp:48-54`).

**Non-analog requirements** (no in-repo precedent — take from RESEARCH Q9, lines 957-965): the eight scenario flags (`--delay-ms`, `--crash-after`, `--stale-bestmove`, `--silent-hang`, `--illegal-bestmove`, `--none-bestmove`, `--crash-on-option`, `--garbage`, `--slow-ready`), `--tm-trace`, and `--record <path>` with monotonic timestamps for ordering assertions. Stdlib only; target ≤ ~200 lines (RESEARCH line 977).

---

### `tools/mock_gui.py` (python driver, request-response subprocess pipe)

**Analog:** `tests/testing.py:264-370` (`Stockfish` class) — spawn, write, read-until-predicate, assert.

**Predicate-matching idiom worth copying (`tests/testing.py:346-370`):**
```python
    def equals(self, expected_output: str):
        for line in self.readline():
            if line == expected_output:
                return

    def expect(self, expected_output: str):
        for line in self.readline():
            if fnmatch.fnmatch(line, expected_output):
                return
    ...
    def contains(self, expected_output: str):
        ...
    def starts_with(self, expected_output: str):
        ...
    def check_output(self, callback):
```
This is the in-repo pattern for "consume output lines until the one I want". `await uciok` / `await readyok` / `await bestmove` in `mock_gui.py` should be the same read-until-predicate loop with a timeout, not a fixed `sleep`.

**Where it deviates:** `mock_gui.py` needs `chess` for legality (RESEARCH line 975) → `PYTHONPATH=vendor python3 tools/mock_gui.py …`. `tests/testing.py` does *not* import `chess` (it uses `requests` and shell-outs), so this import is new. Keep `mock_engine.py` stdlib-only and `mock_gui.py` the only one touching `vendor/chess/`.

**Non-analog requirements** (RESEARCH Q9, lines 967-973): `--engine`, repeatable `--option k=v`, `--tc W:I`, `--games N`, `--latency-ms p50,p95`, `--ponder`, `--require-tm`, `--record`; per-move CSV `ply,side,uci,depth,nodes,score,time_ms,pv,tm_trace`; assert one `bestmove` per `go` and non-negative `wtime`/`btime`. The frozen `go` line is `go wtime <int_ms> btime <int_ms> winc 10000 binc 10000` (RESEARCH line 801) — never `movetime`/`movestogo`/`depth`/`nodes`/`infinite`/`searchmoves`.

---

### `tools/tests/test_doctor.py` (+ checker tests) (python test, unit)

**Analog:** `tests/instrumented.py` — the only tracked test module; its class-based grouping is the in-tree layout.

**Copy:** `pathlib.Path(__file__).parent.resolve()` for fixture paths; `sys.exit(1)` on failure; one class per subject (`TestCLI`, `TestInteractive`, `TestSyzygy`, … run via a single driver).
**Change:** Phase 1 uses **stdlib `unittest`**, not `MiniTestFramework` — `pytest` is absent and cannot be installed offline (RESEARCH OQ-9, lines 1236-1242). Discovery command: `python3 -m unittest discover -s tools/tests -t . -v`.

**Required cases (RESEARCH Validation Architecture, lines 1066-1074):**
- `test_doctor` — feed a URL path (`https://…`) and a relative path (`tb/3-4-5`); assert nonzero exit both times (LIMIT-04).
- `test_notice` / `test_provenance` / `test_license` — assert each checker exits nonzero on a deliberately mutated fixture, zero on the real file. A checker that only ever passes is untested.
- Limit-01 matrix (RESEARCH line 870-877) belongs with the engine gate, not `unittest`: `test_option_default_is_five`, `test_out_of_range_clamps_and_attests`, `test_six_man_directory_fails_loud`, `test_bench_unchanged`. These need the built binary, so they go in `check_phase1.py` / `gate0.sh`.

---

### `tools/sprt.sh` (shell wrapper, batch)

**Analog:** `tests/signature.sh` — the env-override + run + assert shape.

**Copy:** `EXE=${EXE:-./stockfish}` → here `BASE=${BASE:-./src/stockfish}`, `CUSTOM=${CUSTOM:-./build/stockfish-custom}`, `ROUNDS=${ROUNDS:-100000}`; `#!/bin/bash`; append invocation + `date` + `git rev-parse HEAD` + both `sha256sum`s to `results/sprt-<timestamp>.log` (RESEARCH line 949).

**Command body is fixed by RESEARCH Q8, lines 926-949.** Two corrections the script must enforce, because `STACK.md`/`AGENTS.md` are wrong:
- ❌ `option.Move_Overhead=100` → ✅ `"option.Move Overhead=100"` (quoted, **literal space**). fastchess rejects the underscore form with `Warning; A doesn't have option Move_Overhead`.
- `-each tc=10+0.1`; `-report penta=true`; `-repeat`; `-recover`; `-openings file=tools/books/UHO_Lichess_4852_v1.epd format=epd order=random`; `-sprt elo0=0 elo1=5 alpha=0.05 beta=0.05 model=normalized`; `-pgnout file=results/sprt.pgn notation=uci timeleft=true`.

Add the self-check RESEARCH line 1234 demands: grep the trace log for `Move Overhead` set to `100`, abort if absent. Verify with `grep -q '^LLR:' <log>` as the pass condition (Validation Architecture, line 1074).

---

### `docs/build.md` (doc)

**Analog:** `README.md:88-106` ("Compiling Stockfish") — the existing build documentation whose command is **wrong for this project**.

`README.md:100` says `make -j profile-build`. At the repo root that is a no-op; inside `src/` it is valid. `docs/build.md` must state the two commands explicitly and when each applies (RESEARCH line 546):
- reproducibility proof → `make -C src -j"$(nproc)" build`
- shipping artefact → `make -C src -j"$(nproc)" profile-build`

Plus the two gotchas README omits: `make -C src` alone prints the help tutorial and exits 0 (`src/Makefile:1007`), and the net must be verified by hash *before* the build because `make net` cannot fail the build (`scripts/net.sh:74`, `:77`).

---

### `docs/PROTOCOL.md`, `docs/LOGBOOK.md` (frozen specs)

**Analog:** `docs/competition-rules.md` for house format only — it establishes the doc conventions the team already uses:
```markdown
# FAQ – III Chess Challenge

> Documento transcrito verbatim do FAQ oficial da competição.
> Fonte da verdade para requisitos de conformidade. Não editar sem confrontar com a organização.

## 1. Fork de Stockfish ou Modelos LLM são permitidos?
```
Copy: `# Title` + a `>` blockquote stating the document's authority and edit policy, then numbered `## N.` sections. That blockquote slot is where `Frozen: 2026-10-26` and the change-control notice go.
**Do not copy:** Portuguese prose for these two files — they are normative English specs in which tests cite section numbers (RESEARCH line 795). `docs/competition-rules.md` is Portuguese because it is a transcription; these are authored.

**Content skeleton:** RESEARCH Q5 lines 797-834 (11 sections for PROTOCOL, 8 for LOGBOOK). The eight mandatory Rule-9 fields table (lines 818-827) and the `log_lint` contract (line 834) are the graded parts — transcribe them, do not paraphrase.

**Two decisions the doc must freeze rather than hedge:**
- the `tm=` grammar is TM-11's shape, not `ARCHITECTURE.md`'s (`info string tm=custom-v<MAJOR>.<MINOR> mode=… latency_p95_ms=… bank_ms=… budget_ms=… reason=<token>`, RESEARCH line 805) — the two drafts disagree and TM-11 wins.
- PV goes **last and unquoted** on each log line (RESEARCH line 829).
- `time` is **milliseconds on the wire**, seconds in `python-chess` (RESEARCH line 803). State the wire unit.

**License footer instead of a C header** (RESEARCH Q2, line 645): `License: GPL-3.0-or-later. See Copying.txt and NOTICE.` as the last line.

---

### `vendor/chess/` (vendored third-party)

**No in-repo analog.** Install recipe: RESEARCH lines 480-492 and 912-921. Hard constraints:
- copy **only** `chess/` + `LICENSE.txt`, strip `__pycache__` (Pitfall 8 — no `setup.py`, no `chess.egg-info/`).
- pin by vendored tree, not by resolver: record sdist sha256 `a8b43e5678fdb3000695bdaa573117ad683761e5ca38e591c4826eba6d25bb39` and commit `vendor/chess/SHA256SUMS` (sorted `sha256sum` of every file).
- `.gitignore:23` already has `__pycache__/` with no leading slash, so it matches at every depth — nothing to  add (RESEARCH line 364).
- verify: `PYTHONPATH=vendor python3 -c "import chess, chess.engine, chess.polyglot, chess.syzygy; print(chess.__version__)"` → `1.11.2`.

### `.gitignore` (modified — analysis only, already done)

Current state (lines 18-24) is correct and must not be touched again:
```
**/*.nnue
# ChessChallendIII: the official SF19 net is vendored so `unshare -n make` works
# offline (FOUND-04 / R14). Provenance and SHA-256 are in PROVENANCE.md.
!src/nn-1a298aa575a0.nnue
```
The planner must **not** re-edit this file. The guarantee is instead enforced by `tools/offline_build.py` asserting `git ls-files --error-unmatch src/nn-1a298aa575a0.nnue` succeeds (RESEARCH Pitfall 9, line 421) — disk presence is not enough.

---

## Shared Patterns

### GPLv3 modification notice (FOUND-02)
**Source:** `01-RESEARCH.md` Q2, lines 626-636. No in-tree precedent exists (this is the first fork).
**Apply to:** `src/engine.cpp`, `src/engine.h`, `src/syzygy/tbprobe.h` (and `src/syzygy/tbprobe.cpp` if touched). One line, immediately after the closing `*/` of the upstream header block, preceded and followed by one blank line:

```
Modified by ChessChallendIII on 2026-10-26: <one-sentence reason>. See NOTICE and PROVENANCE.md.
```
The prefix is byte-stable — `check_license.sh` greps `^Modified by ChessChallendIII on [0-9]{4}-[0-9]{2}-[0-9]{2}:`. Keep `src/engine.cpp:1-17` untouched above it.

### GPLv3 header for new files of ours
**Source:** `src/engine.cpp:1-17` (adapt the block) — apply to every new `.py`/`.sh`. Markdown docs (NOTICE, PROVENANCE.md, docs/*.md) get the one-line footer instead.
**Never** apply to `Copying.txt`, `AUTHORS`, `CITATION.cff`, `README.md`, `.gitignore` — those must stay byte-identical to `sf_19` (verified baseline: `f288702d…`, `b5ad83d5…`).

### `sys.exit` / `exit $fail` as the single verdict
**Source:** `tests/instrumented.py` (`sys.exit(1)` / `sys.exit(0)`) and `tests/perft.sh` (`TESTS_FAILED` → `exit 1`).
**Apply to:** every `check_*.py`, `check_license.sh`, `gate0.sh`, `check_phase1.py`. No checker may exit 0 after a failure, and no checker may `print` a verdict without setting the exit code — the gate reads exit codes, not logs.

### `info string` is the only engine→console channel for diagnostics
**Source:** `src/uci.cpp:60-67` (`print_info_string`), `src/uci.cpp:76-79` (option listener), `src/uci.cpp:91` (`set_on_verify_network`), `src/ucioption.cpp:176-182` (return value → listener).
**Apply to:** the TB attestation line, the TB violation line, every future TM `tm=` trace. Stdout carries UCI only; `std::cerr` is for the bench summary and human noise (`src/uci.cpp:309-311`).

### Numbered error helper + `trap ERR`
**Source:** `tests/signature.sh:8-18`, `tests/perft.sh:6-11`.
**Apply to:** `scripts/gate0.sh`, `scripts/check_license.sh`, `tools/offline_build.sh`, `tools/sprt.sh`. Report the failing line, dump captured output, `exit 1`.

### `EXE=${EXE:-./stockfish}` env override
**Source:** `tests/signature.sh:21`.
**Apply to:** every script that names an engine binary — makes the script reusable for base vs. custom engines without editing (Phase 6 depends on this).

### GPL line discipline and "touched file" minimalism
**Source:** `01-RESEARCH.md` Q2 lines 638-647.
**Apply to the whole phase:** the Phase-1 `src/` diff is exactly `engine.cpp`, `engine.h`, `syzygy/tbprobe.h`. `misc.cpp`, `uci.cpp`, `search.cpp`, `timeman.*`, `Makefile`, `scripts/net.sh`, `README.md`, `AUTHORS` must **not** appear in `git diff sf_19..HEAD` for Phase 1 — each would add a GPL line and a diff for no compliance gain.

---

## No Analog Found

Files with no close match in the codebase. The planner should use the RESEARCH.md section named in the last column instead of an analog.

| File | Role | Data Flow | Reason | Use instead |
|---|---|---|---|---|
| `NOTICE` | doc/compliance | — | Upstream has no `NOTICE`; the repo has no machine-readable compliance doc | RESEARCH Q1, lines 566-620 (field list + per-field derivation commands) |
| `PROVENANCE.md` | doc/compliance | — | Same | RESEARCH Q3, lines 689-760 (three fixed-column tables + checker minimum) |
| `tools/sprt.md` | doc (recipe) | — | No harness documentation exists in-tree | RESEARCH Q8, lines 924-951 (verified command + three corrections) |
| `requirements-game.txt` | config | — | No dependency manifest exists (no pip, no requirements file in `sf_19`) | RESEARCH Q10, line 986 — declaration only, must carry a "do not install" comment |
| `vendor/chess/` | vendored third-party | — | No vendored Python dependency exists | RESEARCH Q10, lines 479-498 + 912-921 |
| `tools/fastchess-linux-x86-64/` | vendored binary | — | No third-party binary is vendored anywhere in `sf_19` | RESEARCH Q8, lines 912-922 |
| `RELEASE/SHA256SUMS`, `RELEASE/README.md` | generated artefact | file-I/O | No release/publishing artefact exists | RESEARCH FOUND-06 + `tools/build_manifest.py` spec (line 348) |
| `evidence/*.log`, `evidence/*.txt` | generated artefact | file-I/O | No evidence directory exists | RESEARCH Q4, lines 783-791 (required log contents) |

**Also note:** `AGENTS.md` is generated from `PROJECT.md` + `research/STACK.md` (`<!-- GSD:stack-start -->` … `<!-- GSD:stack-end -->`). Two of its statements are **wrong** and must be corrected at the source, not in `AGENTS.md` (RESEARCH lines 941-947, 546): `option.Move_Overhead=100` and root-level `make -j profile-build`.

---

## Metadata

**Analog search scope:** `src/` (engine + syzygy + nnue headers), `scripts/`, `tests/`, `docs/`, repo root (`.gitignore`, `README.md`, `CITATION.cff`), `.planning/phases/01-*/`.
**Files scanned:** 14 read in full or targeted (`src/engine.cpp`, `src/engine.h`, `src/uci.cpp`, `src/ucioption.cpp`, `src/ucioption.h`, `src/syzygy/tbprobe.h`, `src/syzygy/tbprobe.cpp`, `src/evaluate.h`, `scripts/net.sh`, `scripts/get_native_properties.sh`, `tests/signature.sh`, `tests/perft.sh`, `tests/testing.py`, `tests/instrumented.py`) + `docs/competition-rules.md`, `README.md`, `CITATION.cff`, `.gitignore`.
**Tracked check:** all 14 analog files confirmed via `git ls-files -- <path>`. No gitignored mirror paths anywhere in this document.
**Pattern extraction date:** 2026-10-26
**Analogs deliberately not used:**
- `tests/reprosearch.sh` — `expect`-based; `expect` is not a declared dependency (RESEARCH Environment Availability, lines 1021-1035) and Phase 1 must not add one.
- `scripts/check_universal*.sh` — build-matrix scripts, no relevant pattern.
- `src/timeman.cpp` — Phase 4 target; touching or citing it in Phase 1 would imply a change that must not happen now.
