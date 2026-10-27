---
phase: 01-foundation-provenance-frozen-contract
verified: 2026-10-27T15:06:07Z
status: human_needed
score: 8/9 must-haves verified
covered_files:
  - .planning/phases/01-foundation-provenance-frozen-contract/01-01-PLAN.md
  - .planning/phases/01-foundation-provenance-frozen-contract/01-01-SUMMARY.md
  - .planning/phases/01-foundation-provenance-frozen-contract/01-02-PLAN.md
  - .planning/phases/01-foundation-provenance-frozen-contract/01-02-SUMMARY.md
  - .planning/phases/01-foundation-provenance-frozen-contract/01-03-PLAN.md
  - .planning/phases/01-foundation-provenance-frozen-contract/01-03-SUMMARY.md
  - NOTICE
  - PROVENANCE.md
  - RELEASE/SHA256SUMS
  - RELEASE/stock-binary/SHA256SUMS
  - docs/LOGBOOK.md
  - docs/PROTOCOL.md
  - docs/build.md
  - docs/sprt.md
  - evidence/01-binary.sha256
  - evidence/01-contract-transcript.log
  - evidence/01-offline-build.log
  - evidence/01-sprt-smoke.log
  - evidence/01-tb-ceiling.log
  - scripts/archive_usb.sh
  - scripts/check_license.sh
  - scripts/gate0.sh
  - src/engine.cpp
  - src/engine.h
  - src/syzygy/tbprobe.h
  - tools/check_contract_order.py
  - tools/check_notice.py
  - tools/check_provenance.py
  - tools/doctor.py
  - tools/mock_engine.py
  - tools/mock_gui.py
  - tools/offline_build.sh
  - tools/sprt.sh
  - tools/tests/test_contract.py
  - tools/tests/test_doctor.py
  - tools/tests/test_provenance.py
  - tools/tests/test_tb_ceiling.py
covered_digest: "v4:sha256:721b4657e679e65c3f53aa4c56d7e985c59847f613472fa3896e38e9d9f4e0ef"
behavior_unverified: 0
overrides_applied: 0
re_verification:
  previous_status: gaps_found
  previous_score: 7/9
  gaps_closed:
    - "G1 CLOSED — FOUND-05/SC3 mocks now run end-to-end at HEAD: mock_gui --games 2 → 'OK mock_gui: 8 searches across 2 game(s)' rc=0; real-stockfish --games 1 → 'OK mock_gui: 2 searches across 1 game(s)' rc=0 (the deterministic deadlock repro now passes); 31/31 unittest incl. new RuntimeEndToEndTests; bench 2497913 unchanged; regression spot-checks green (gate0 --skip-build rc=0, check_notice OK, check_contract_order OK, check_provenance OK)"
  gaps_remaining: []
  regressions: []
human_verification:
  - test: "FOUND-06 / ROADMAP SC5: confirm https://github.com/matheus-henri-ferr/Chess-Challenge-III is public (or grant the panel a verified read account)"
    expected: "Panel can open the repository without credentials"
    why_human: "Requires logging into GitHub as the panel would; cannot be verified from the dev box"
  - test: "FOUND-06 / ROADMAP SC5: run scripts/archive_usb.sh --dest /media/<user>/<label>/CHESSCHALLENDIII on a ≥4 GiB USB device and verify SHA256SUMS in place"
    expected: "Archive holds source tarball, binary, net, licence set; sha256sum -c passes at the destination"
    why_human: "Requires physical media"
  - test: "FOUND-04 assumption A1: reproduce the offline build on the MATCH laptop with sudo unshare -n make -j (dev box used unshare -rn)"
    expected: "Clean clone builds network-severed, bench 2497913, binary hash recorded"
    why_human: "Requires the match laptop hardware and sudo"
deferred:
  - truth: "LIMIT-01: effective SyzygyProbeLimit appears in the pre-game checklist"
    addressed_in: "Phase 3"
    evidence: "ROADMAP Phase 3: 'TB/book asserts, pre-game checklist'"
  - truth: "LOGBOOK §6 log_lint implementation (fail-closed linter)"
    addressed_in: "Phase 2"
    evidence: "ROADMAP Phase 2: 'log_lint reports zero missing fields'; LOGBOOK §6.1 defers to Phase 2"
---

# Phase 1: Foundation, Provenance & Frozen Contract — Verification Report

**Phase Goal:** Every unrecoverable compliance and contract decision is fixed and provable on day 0: licence/provenance gates, frozen console protocol, Rule 4 tablebase ceiling enforced in code, and a reproducible offline build — so no Phase-2+ work can silently invalidate them.
**Verified:** 2026-10-27T15:06:07Z
**Status:** PASS (with 3 open human items — G1 resolved; no code gaps remain)
**Re-verification:** Yes — after gap closure (fix commit 66d7b078)

## Goal Achievement

### Observable Truths (per-requirement verdicts)

| # | Requirement | Verdict | Evidence (all re-derived live, not from SUMMARY) |
|---|-------------|---------|--------------------------------------------------|
| 1 | FOUND-01 — real sf_19 fork, NOTICE complete & command-derived | ✅ PASS (carried) | Prior live evidence stands: `git rev-parse sf_19` = `edb0d9db…` == NOTICE Base commit; `python3 tools/check_notice.py` → `OK NOTICE` re-run at 66d7b078 (re-derives base SHA, bench 2497913, net SHA, Modified-files vs `git diff sf_19`) |
| 2 | FOUND-02 — Copying.txt/AUTHORS byte-intact, dated mod lines | ✅ PASS (carried) | `git diff sf_19 HEAD -- Copying.txt AUTHORS` empty; dated mod lines in src/engine.cpp:19, src/engine.h:19, src/syzygy/tbprobe.h:19; 66d7b078 touches none of them |
| 3 | FOUND-03 — PROVENANCE.md: net identity, NOT AUTHORED, manifest | ✅ PASS (carried) | check_provenance → `OK PROVENANCE` re-run at 66d7b078; net/TB/dep manifest unchanged |
| 4 | FOUND-04 — reproducible offline build, net embedded | ✅ PASS (carried) | evidence/01-offline-build.log @ 6a64b1fb complete (unshare -rn, net cmp identical, bench 2497913, zero downloads); binary hash 527fa7ac… still matches live src/stockfish (unchanged by 66d7b078 — Python-only commit); match-laptop repro remains open human item |
| 5 | FOUND-05 — frozen docs pre-implementation + **both mocks run end-to-end** | ✅ **PASS (G1 RESOLVED)** | Docs part carried: freeze commit 2fd4bf4f docs-only, predates impl, `check_contract_order.py` → `OK CONTRACT ORDER` re-run. Mocks part now live-verified at HEAD (66d7b078): `python3 tools/mock_gui.py --engine tools/mock_engine.py --games 2 --max-plies 4 --tc 15:10 --require-tm` → **`OK mock_gui: 8 searches across 2 game(s)`, rc=0**; `python3 tools/mock_gui.py --engine ./src/stockfish --games 1 --max-plies 2 --tc 0.05:0.01` → **`OK mock_gui: 2 searches across 1 game(s)`, rc=0** (the 5/5-deterministic deadlock repro now passes). Code inspection: readline() rebuilt on `os.read` raw-fd + own buffer with `bufsize=0` (no TextIO to starve select); `bestmove_of()` takes the FIRST token ('bestmove e2e4 ponder c7c5' no longer corrupts the move); go_line staticmethod pins winc/binc 10000 per frozen §3.1; mock_engine reports real elapsed time. ROADMAP SC3 met by the code at HEAD |
| 6 | FOUND-06 — repo public/panel access + USB archive started | ⚠️ HUMAN | Carried: dry-run artifacts verified (RELEASE/SHA256SUMS committed, archive_usb.sh guards, panel URL in PROVENANCE §5). Panel confirmation + physical USB = open human items |
| 7 | LIMIT-01 — SyzygyProbeLimit forced to 5, fatal on 6-man | ✅ PASS (carried) | Live-verified pre-fix: option line `default 5 min 0 max 5`, clamp+attest, planted KQRRBvK.rtbw/.rtbz → exit 1, KQvK accepted; bench unchanged at 66d7b078 confirms engine behaviour intact |
| 8 | LIMIT-04 — doctor.py fails on remote/relative asset paths | ✅ PASS (carried) | Live-verified: 13 checks exit 0, remote/`~` assets exit 1 with named reason; 7/7 test_doctor in the 31/31 run |
| 9 | PIPE-01 — fastchess installed + SPRT smoke with LLR line + documented recipe | ✅ PASS (carried) | fastchess alpha 1.8.2; LLR line in results + evidence log; docs/sprt.md normative recipe; book hashes OK |

**Score:** 8/9 requirements verified — 1 human (FOUND-06); zero FAILED. G1 gap closed.

### Re-verification: What the G1 fix touched (66d7b078 — all re-run live)

| Check | Command | Result | Status |
|-------|---------|--------|--------|
| SC3 mock end-to-end (2 games, TM required) | `python3 tools/mock_gui.py --engine tools/mock_engine.py --games 2 --max-plies 4 --tc 15:10 --require-tm` | `OK mock_gui: 8 searches across 2 game(s)`, rc=0 | ✓ PASS |
| Real-engine session (deadlock repro) | `python3 tools/mock_gui.py --engine ./src/stockfish --games 1 --max-plies 2 --tc 0.05:0.01` | `OK mock_gui: 2 searches across 1 game(s)`, rc=0 | ✓ PASS |
| Full test suite | `python3 -m unittest discover -s tools/tests -t .` | **31/31 OK** (95.8 s), incl. new RuntimeEndToEndTests spawning mock_gui ↔ mock_engine | ✓ PASS |
| Bench unchanged | `./src/stockfish bench` | `Nodes searched : 2497913` | ✓ PASS |

Fix claims confirmed in code at HEAD (tools/mock_gui.py, tools/mock_engine.py, tools/tests/test_contract.py): readline() at :78-92 reads via `os.read(fd, 65536)` into an owned buffer with `bufsize=0` (TextIO eliminated — the starvation mechanism cannot recur); `bestmove_of()` at :128 takes the first token; `go_line` staticmethod at :144-149 pins `winc 10000 binc 10000` (frozen §3.1) while the --tc ledger keeps the operator increment; mock_engine reports `time = min(script, cap, real elapsed)`; `RuntimeEndToEndTests` at test_contract.py:120 spawns the real driver↔engine pair inside unittest — exactly the regression test the original gap demanded.

### Regression spot-check (nothing else moved)

| Check | Result | Status |
|-------|--------|--------|
| `bash scripts/gate0.sh --skip-build` | rc=0, all gates green | ✓ PASS |
| `python3 tools/check_notice.py` | `OK NOTICE` | ✓ PASS |
| `python3 tools/check_contract_order.py` | `OK CONTRACT ORDER: freeze 2fd4bf4f is ancestor of first implementation commit 6a64b1fb` | ✓ PASS |
| `python3 tools/check_provenance.py` | `OK PROVENANCE` | ✓ PASS |
| Working tree vs 66d7b078 | clean except this VERIFICATION.md | ✓ PASS |
| Binary hash | src/stockfish untouched by 66d7b078 (Python-only commit) — 527fa7ac… carried | ✓ PASS |

No regression found. Carried PASS verdicts for FOUND-01…04, LIMIT-01, LIMIT-04, PIPE-01 rest on prior live evidence plus fresh checker/gate0 re-runs; bench re-confirmed.

### REVIEW.md Dispositions (15 findings — all dispositioned)

| Finding | Claimed fix in HEAD? | Live evidence |
|---|---|---|
| **CR-01** DTZ-only 6-man dir not fatal (critical) | ✅ Fixed | filename scan in src/engine.cpp; planted `.rtbz` → exit 1 (prior live); shared `TbCeilingViolation` constant |
| WR-01 go()/search_clear() attestation print-only | ✅ Fixed | `Engine::enforce_tb_ceiling()` fatal from all three sites (prior live attestation) |
| WR-02 mock_gui never reaps engine | ✅ Fixed (G1 companion defect now also fixed) | close() quit → wait(5) → kill; **and** readline() rebuilt on os.read — deadlock resolved, real-SF session completes rc=0 |
| WR-03 --tc parsed then dropped | ✅ Fixed | Game carries base_ms/inc; go_line pins winc/binc 10000 per §3.1, ledger separate |
| WR-04 fixed /tmp net-export paths (CWE-377) | ✅ Fixed | tempfile.TemporaryDirectory + mktemp dirs |
| IN-01 dead --ponder flag | ✅ Fixed | Flag removed; go_line keeps ponder param as staticmethod contract |
| IN-02 dead no-op branch in check_contract_order | ✅ Fixed | Removed |
| IN-03 unused BASE_SHA in check_notice | ✅ Fixed | no matches |
| IN-04 docstring claims `chess` legality import | ✅ Fixed | "stdlib only" docstring |
| IN-05 dead loop in test_contract test_04 | ✅ Fixed | Removed |
| IN-06 no-op replace in test_provenance | ✅ Fixed | Removed |
| IN-07 archive_usb.sh missing sha tool | ✅ Fixed | FATAL + exit 2 present |
| IN-08 offline_build step 9 swallows output | ✅ Fixed | streamed into committed log |
| IN-09 string-prefix dispatch on wording | ✅ Fixed | shared constexpr |
| IN-10 mock_engine fen doesn't reset moves | ✅ Fixed | `self.moves = []` |

**15/15 fixed. WR-02's companion defect (G1) resolved in 66d7b078.**

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| NOTICE | complete provenance fields | ✓ VERIFIED | check_notice OK re-run; binary hash matches |
| PROVENANCE.md | net/TB/deps declarations | ✓ VERIFIED | check_provenance OK |
| docs/PROTOCOL.md | frozen console↔engine contract | ✓ VERIFIED | 11 sections; §3.1 frozen go literal; docs-only commit 2fd4bf4f |
| docs/LOGBOOK.md | frozen Rule-9 log spec | ✓ VERIFIED | 8 mandatory fields + score_white + src= variants + log_lint §6 |
| tools/mock_engine.py | contract-speaking UCI mock | ✓ VERIFIED | drives full session inside RuntimeEndToEndTests + prior live handshake/search |
| tools/mock_gui.py | contract driver | ✓ VERIFIED (was BROKEN) | end-to-end vs mock AND real stockfish, rc=0 both; os.read readline at HEAD |
| tools/check_contract_order.py | freeze-predates-impl proof | ✓ VERIFIED | OK, non-vacuous |
| tools/doctor.py | 13-check startup pre-flight | ✓ VERIFIED | prior live PASS/FAIL/SKIP + --json; 7/7 tests in 31/31 |
| tools/offline_build.sh → evidence log | network-severed build proof | ✓ VERIFIED | log complete, hashes identical, bench 2497913 |
| tools/sprt.sh + docs/sprt.md | audit-trailed SPRT | ✓ VERIFIED | LLR line in results + evidence |
| scripts/gate0.sh | single phase gate | ✓ VERIFIED | `--skip-build` rc=0 re-run at 66d7b078 |
| scripts/check_license.sh | GPL header gate | ✓ VERIFIED | exit 0 (prior live; inputs untouched by 66d7b078) |
| scripts/archive_usb.sh | USB archiver | ✓ VERIFIED | dry-run manifest; IN-07 guard |
| vendor/chess/ | python-chess 1.11.2 vendored | ✓ VERIFIED | import check prior live; untouched |
| tools/fastchess-linux-x86-64/ | fastchess 1.8.2 + MIT source | ✓ VERIFIED | alpha 1.8.2 prior live |
| tools/books/UHO_Lichess_4852_v1.epd | harness book | ✓ VERIFIED | hash check OK prior live |
| RELEASE/ + RELEASE/stock-binary/ | stock binary archived pre-patch | ✓ VERIFIED | SHA256SUMS committed |
| src/stockfish | patched binary | ✓ VERIFIED | bench 2497913 re-run at HEAD; hash carried (Python-only fix commit) |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|----|--------|---------|
| mock_engine / mock_gui | docs/PROTOCOL.md §3.1 | GO_LITERAL + test_contract doc↔mock↔gui assertions | ✓ WIRED | 12/12 + 2 new RuntimeEndToEnd tests = 31/31 pass |
| LOGBOOK §2 keys | mock_gui CSV_COLUMNS | test asserts keys ⊆ CSV_COLUMNS | ✓ WIRED | |
| SyzygyPath on_change | Tablebases::init → verify → enforce | enforce_tb_ceiling() | ✓ WIRED | prior live exit 1 on 6-man |
| Engine::go()/search_clear() | enforce_tb_ceiling | fatal on violation | ✓ WIRED | prior live attestation |
| engine binary | embedded NNUE | INCBIN + export_net round-trip | ✓ WIRED | bench re-run loads net |
| doctor.py | NOTICE/PROVENANCE/RELEASE | delegates to checkers | ✓ WIRED | |
| gate0.sh | all gates | check_license, checkers, tests, bench, doctor, ancestry, RELEASE | ✓ WIRED | rc=0 re-run |
| mock_gui → mock_engine subprocess | **the day-1 TM measurement path** | EngineProc os.read readline over pipes | ✓ **WIRED (G1 RESOLVED)** | both end-to-end sessions rc=0 live; RuntimeEndToEndTests covers it in-suite |

### Behavioral Spot-Checks (re-verification runs)

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Mock 2-game TM session | `python3 tools/mock_gui.py --engine tools/mock_engine.py --games 2 --max-plies 4 --tc 15:10 --require-tm` | OK, 8 searches, rc=0 | ✓ PASS |
| Real-SF session (former repro) | `python3 tools/mock_gui.py --engine ./src/stockfish --games 1 --max-plies 2 --tc 0.05:0.01` | OK, 2 searches, rc=0 | ✓ PASS |
| Full suite | `python3 -m unittest discover -s tools/tests -t .` | 31/31 OK | ✓ PASS |
| Bench | `./src/stockfish bench` | 2497913 | ✓ PASS |
| gate0 (skip-build) | `bash scripts/gate0.sh --skip-build` | rc=0 | ✓ PASS |
| check_notice / contract order / provenance | three checkers | OK × 3 | ✓ PASS |

(Carried prior-live spot-checks — option line, clamp+attest, 6-man fatal WDL/DTZ, 5-man accept, doctor rejects, book hash, fastchess version — all inputs untouched by 66d7b078.)

### Probe Execution

| Probe | Command | Result | Status |
|-------|---------|--------|--------|
| gate0 (phase gate, --skip-build) | `bash scripts/gate0.sh --skip-build` | exit 0 at 66d7b078 | PASS |
| gate0 full (namespace build) | covered by committed evidence/01-offline-build.log @ 6a64b1fb (unshare -rn, bench 2497913, identical hashes); src/ unchanged since | — | PASS (evidence-backed) |

### Requirements Coverage

All 9 Phase-1 requirement IDs (FOUND-01…06, LIMIT-01, LIMIT-04, PIPE-01) are claimed by plans 01-01/01-02/01-03. No orphaned Phase-1 requirements in REQUIREMENTS.md. Verdicts in the table above.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| tools/mock_gui.py | 19 | docstring still says "(ponder variant under --ponder)" but IN-01 removed the flag | ℹ️ Info | Minor doc drift, carried |
| tools/check_contract_order.py | ~93-103 | "first implementation commit" label selects the NEWEST impl commit (rev-list newest-first) | ℹ️ Info | Verdict sound under linear history; misnomer only |

Former 🛑 Blocker (select()-gated readline deadlock) RESOLVED in 66d7b078 — no blocker remains. No TBD/FIXME/XXX markers in phase-touched files.

### Human Verification Required

Three open items, all environmental (unchanged from initial verification):

### 1. Panel repository access (FOUND-06 / SC5)

**Test:** Confirm https://github.com/matheus-henri-ferr/Chess-Challenge-III is public (or grant the panel a verified read account).
**Expected:** Panel opens the repo without credentials.
**Why human:** Requires logging into GitHub as the panel would.

### 2. USB archive (FOUND-06 / SC5)

**Test:** Run `scripts/archive_usb.sh --dest /media/<user>/<label>/CHESSCHALLENDIII` on a ≥4 GiB USB device; verify SHA256SUMS in place.
**Expected:** Archive holds source tarball, binary, net, licence set; `sha256sum -c` passes at the destination.
**Why human:** Requires physical media.

### 3. Match-laptop offline build (FOUND-04 / A1)

**Test:** On the match laptop: `sudo unshare -n make -j` from a clean clone.
**Expected:** Builds network-severed; bench 2497913; binary hash recorded.
**Why human:** Requires the match laptop hardware and sudo.

### Gaps Summary

None. G1 (mock_gui TextIO/select starvation deadlock) is closed by commit 66d7b078: readline() now owns its buffer over raw os.read (TextIO eliminated via bufsize=0), so select() can never starve on bytes already consumed; bestmove parsing no longer corrupts 'bestmove e2e4 ponder c7c5'; go lines match the frozen §3.1 literal exactly; and the suite now spawns the real driver↔engine pair (RuntimeEndToEndTests) — the coverage hole that let the regression ship is itself closed. Both the 2-game mock session and the real-stockfish session that deterministically deadlocked now complete with rc=0; 31/31 tests; bench unchanged at 2497913; gate0 and all three checkers re-run green. Status is `human_needed` solely for the three environmental items (GitHub panel access, physical USB archive, match-laptop offline build) — no code work remains for Phase 1.

---

_Verified: 2026-10-27T15:06:07Z_
_Verifier: the agent (gsd-verifier)_
