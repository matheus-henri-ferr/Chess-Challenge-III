---
phase: 01-foundation-provenance-frozen-contract
reviewed: 2026-10-27T14:20:00Z
depth: deep
files_reviewed: 17
files_reviewed_list:
  - src/engine.cpp
  - src/engine.h
  - src/syzygy/tbprobe.h
  - tools/check_notice.py
  - tools/check_provenance.py
  - tools/check_contract_order.py
  - tools/doctor.py
  - tools/mock_engine.py
  - tools/mock_gui.py
  - tools/offline_build.sh
  - tools/sprt.sh
  - scripts/check_license.sh
  - scripts/archive_usb.sh
  - scripts/gate0.sh
  - tools/tests/test_provenance.py
  - tools/tests/test_contract.py
  - tools/tests/test_tb_ceiling.py
  - tools/tests/test_doctor.py
findings:
  critical: 1
  warning: 4
  info: 10
  total: 15
status: issues_found
---

# Phase 1: Code Review Report

**Reviewed:** 2026-10-27T14:20:00Z
**Depth:** deep
**Files Reviewed:** 17 (+4 test files)
**Status:** issues_found

## Summary

Reviewed the Rule 4 TB-ceiling C++ guard (diffed against `sf_19`), the provenance/contract checkers, the contract mocks, doctor, and the build/SPRT/archive scripts. Core enforcement chain verified sound: `SyzygyProbeLimit` option clamped to `Option(5, 0, 5)`, `rank_root_moves` (tbprobe.cpp:1917-1927) derives `config.cardinality` from that option, and search.cpp:927 probes only when `piecesCount <= tbConfig.cardinality` — so no position with more than 5 pieces is ever probed. The 6-man WDL fatal-exit path works (test_04, zero-byte file, exit 1). Suite: 30/30 pass; check_notice/check_provenance/check_contract_order all exit 0 live; NOTICE binary hash matches `sha256sum src/stockfish`; book SHA256SUMS matches.

One real enforcement hole: the fatal guard keys off `MaxCardinality`, which tbprobe.cpp:595 only updates when a **WDL** (`.rtbw`) file is found — a directory containing only 6-man **DTZ** files passes `verify_tb_ceiling()` and the engine runs. Plus enforcement asymmetry: the mid-game re-attestations in `go()`/`search_clear()` are print-only. Python-side: mock_gui leaks the engine subprocess on failure and ignores `--tc`. No injection, no secrets, no `shell=True` anywhere.

## Critical Issues

### CR-01: 6-man DTZ-only tablebase directory is not fatal — Rule 4 possession violation runs silently

**File:** `src/engine.cpp:292-307` (verify_tb_ceiling), root cause `src/syzygy/tbprobe.cpp:580-595`
**Issue:** `TBTables::add` returns early when only the `.rtbz` file exists (`if (!file.is_open()) return;` at tbprobe.cpp:589 fires after the DTZ check at :581-585), so `MaxCardinality` is never updated. A `SyzygyPath` containing `KQRRBvK.rtbz` (6-man DTZ, no WDL) yields `max_loaded=0` → `verify_tb_ceiling()` returns OK → no `exit(1)`. The commit contract ("exit on forbidden tablebase") and PROVENANCE.md:28 claim fatal-on-6-man-directory; the shipped engine guard does not deliver it for DTZ-only content. doctor.py:163-166 catches it (checks both suffixes) but doctor is a dev-side gate, not the judged artifact. Probing is still ceiling-safe (no WDL table is ever created), but the engine accepts a forbidden tablebase in its declared path.
**Fix:**
```cpp
// src/engine.cpp, in the SyzygyPath on_change lambda — count files, not just
// loaded tables, before/after Tablebases::init(o):
int six_man_files = 0;
for (const auto& dir : Tablebases::indexed_paths()) { /* or replicate the split() */
    // cheaper: mirror doctor.py's piece_count over the path's .rtbw/.rtbz entries
}
if (six_man_files) { /* CRITICAL ERROR ... std::exit(1); */ }
```
Minimal alternative: expose a `Tablebases::forbidden_files(path)` helper next to `init()` that reuses `TBFile::Paths` splitting and applies the doctor.py `piece_count` rule (stem split on `v`, sum both sides > 5 → fatal). Add a test_04b with a 6-man `.rtbz`-only directory asserting exit 1.

## Warnings

### WR-01: go()/search_clear() ceiling attestation is print-only — mid-game tablebase swap degrades to an info string

**File:** `src/engine.cpp:173-174, 190-191`
**Issue:** The fatal exit exists only in the `SyzygyPath` on_change lambda (:133-140). `go()` and `search_clear()` route any violation through `onVerifyNetwork` = `print_info_string` (uci.cpp:91) — no `CRITICAL ERROR` prefix, no exit. If the TB directory's contents are swapped between `setoption` and a later `go` (files added to the live path), the engine reloads 6-man tables at `search_clear()` (engine.cpp:187) and keeps searching, emitting `info string TB CEILING VIOLATION: max_loaded=6 ...` into a stream nobody gates. Probe safety holds (cardinality clamp), but the attestation guarantee "fatal, not advisory" (engine.cpp:129-130) is not upheld on these paths.
**Fix:** Factor the fatal branch into a private `Engine::enforce_tb_ceiling()` that prints `CRITICAL ERROR` + `std::exit(1)` on a violation, and call it from all three sites (on_change, go, search_clear).

### WR-02: mock_gui.py never kills the engine subprocess — orphaned hung engine on every failure path

**File:** `tools/mock_gui.py:69-74, 89-92, 242-247`
**Issue:** `EngineProc.close()` only closes the transcript file. On `RuntimeError("engine EOF")` (:74), on `TimeoutError` after 60 s (:80), or on any exception inside `Game.play()`, the `finally` in `main()` sends `quit` (which a `--silent-hang` engine by definition never answers — mock_engine.py:117-118 ignores `stop` too) and then exits, leaving the child alive holding the pipe. Repeated contract runs with misbehaving-engine scenarios accumulate orphan processes.
**Fix:**
```python
def close(self):
    try:
        self.popen.kill()
    except OSError:
        pass
    self.popen.wait(timeout=5)
    if self.rec:
        self.rec.close()
```

### WR-03: mock_gui.py ignores --tc — clocks hardcoded to 15+10, main() parses and drops the values

**File:** `tools/mock_gui.py:170-171, 216-219`
**Issue:** `main()` computes `base_ms`/`inc` from `--tc` (:216-218) and `p50, p95` (:219) but never passes them to `Game`; `play()` hardcodes `clocks = [15*60_000, 15*60_000]` and `inc = 10_000` (:170-171) and re-parses latency itself (:185). `base_ms`, `inc`, and the main() `p50/p95` are dead variables. `--tc 5:3` silently measures TM budgets against 15+10 clocks — the docstring says the driver exists to "measure TM budgets"; non-15+10 runs produce wrong `wtime/btime` on the wire and therefore wrong budget data.
**Fix:** `Game(args, proc, g)` already holds `args`; parse tc once in `__init__` (`self.base_ms`, `self.inc`) and use them in `play()`; delete the dead locals in `main()`.

### WR-04: fixed predictable /tmp paths for net export — symlink-following file overwrite (CWE-377)

**File:** `tools/doctor.py:134-143`; `tools/offline_build.sh:78-80`
**Issue:** Both write a 94 MB export to a fixed, world-writable location: `/tmp/doctor-net-export.nnue` and `/tmp/net-exported.nnue`. A local pre-planted symlink at those paths makes the engine (and `cmp`) follow it and overwrite the target with the net — silent corruption of an arbitrary user-owned file. Single-user event laptop limits impact, but these run unattended in gate0 and CI contexts where /tmp is shared.
**Fix:** `tempfile.NamedTemporaryFile(delete=False)` / `mktemp`-based unique path in both; doctor already unlinks in all paths — with `tempfile.TemporaryDirectory()` the cleanup is automatic. In offline_build.sh use `NET_OUT=$(mktemp)` and `trap 'rm -f "$NET_OUT"' EXIT`.

## Info

### IN-01: --ponder CLI flag is dead — never read, ponder variant unreachable

**File:** `tools/mock_gui.py:199, 121`
**Issue:** `args.ponder` is never used; `search()` hardcodes `go_line(w_ms, b_ms, ponder=False)` (:121). Docstring :16-18 promises "ponder variant under --ponder".
**Fix:** Thread `self.args.ponder` into `go_line`, or remove the flag and the docstring claim.

### IN-02: dead no-op branch in check_contract_order.py

**File:** `tools/check_contract_order.py:107-110`
**Issue:** `if any(...) and not any(...): pass` — condition computed, body `pass`. Either a half-removed filter or a placeholder; pure noise in a compliance checker.
**Fix:** Delete the four lines.

### IN-03: unused constant BASE_SHA in check_notice.py

**File:** `tools/check_notice.py:31`
**Issue:** `BASE_SHA = "f879373d..."` defined, never referenced — the live value is re-derived via `git rev-parse sf_19` (:58). Stale duplicate of a provenance literal invites drift.
**Fix:** Delete it (the comment on :54-58 of NOTICE explains why it is derived, not remembered).

### IN-04: mock_gui.py docstring claims legality checking via `chess` — no such import or check exists

**File:** `tools/mock_gui.py:13-14, 181`
**Issue:** "Imports stdlib plus `chess` from vendor/ for legality" — the module imports neither `chess` nor enforces legality (line 181 concedes "legal-ish"). Misleads a reader about what the driver validates.
**Fix:** Reword the docstring to "stdlib only; the scripted opening is assumed legal".

### IN-05: dead loop body in test_contract.py test_04

**File:** `tools/tests/test_contract.py:104-107`
**Issue:** `for line in lines: out.append(line); if not injected and ...: pass` — loop and `out` list unused; the real mutation is the `text.replace` below. Dead scaffolding obscures the test's intent.
**Fix:** Delete the loop and `out`; keep the `text.replace(...)` mutation.

### IN-06: no-op replace builds the `mutated` fixture in test_provenance.py test_03

**File:** `tools/tests/test_provenance.py:64-67`
**Issue:** `mutated = text.replace("| fastchess |", "| fastchess |")` — replaces a string with itself; `mutated` is then written unchanged at :82. Harmless but misleading (suggests a mutation happened).
**Fix:** `mutated = text` with a comment, or drop the variable.

### IN-07: archive_usb.sh never checks the sha256sum/shasum fallback resolution

**File:** `scripts/archive_usb.sh:30-31, 58-60`
**Issue:** If neither tool exists, `$sha256sum` is empty; the script copies the full release set, then fails at manifest time with "command not found" — a partial archive with no SHA256SUMS, i.e. exactly the "unverified copy" the header says is worse than none.
**Fix:** `[ -n "$sha256sum" ] || { echo "FATAL: no sha256 tool" >&2; exit 2; }` immediately after resolution.

### IN-08: offline_build.sh step 9 swallows the working-tree rebuild output

**File:** `tools/offline_build.sh:111`
**Issue:** `$NS make -C src -j"$(nproc)" build >/dev/null 2>&1` — a build failure surfaces only as a bare nonzero exit with no diagnostics, after the clone evidence was already written; debugging requires re-running by hand.
**Fix:** Drop `2>&1 >/dev/null` masking or redirect to a second log file under `evidence/`.

### IN-09: string-prefix dispatch on the violation message couples behavior to wording

**File:** `src/engine.cpp:133-135`
**Issue:** `violation->rfind("TB CEILING VIOLATION", 0) == 0` — the fatal path depends on a literal also produced 170 lines away in `verify_tb_ceiling()`. Editing the message wording silently degrades the guard to advisory. The comment at :131-132 already acknowledges the awkwardness.
**Fix:** Return a small struct or an enum (`enum class TbCeiling { OK, VIOLATION }`) plus message, or match against a `constexpr std::string_view` constant shared by both sites.

### IN-10: mock_engine.py FEN positions do not reset move history — bestmove parity wrong after `position fen`

**File:** `tools/mock_engine.py:101-108, 163-168`
**Issue:** `handle_position` for a `fen` keeps `self.moves` from a previous `startpos` line; `best_move()` derives the move from `len(self.moves)`, so after `position fen ...` + `go` the mock answers with the wrong book-ply move.
**Fix:** In the `fen` branch: `self.moves = []` (there is no move list after a bare fen).

---

_Reviewed: 2026-10-27T14:20:00Z_
_Reviewer: the agent (gsd-code-reviewer)_
_Depth: deep_
