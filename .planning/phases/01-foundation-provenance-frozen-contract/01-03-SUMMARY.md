---
phase: 01-foundation-provenance-frozen-contract
plan: 03
subsystem: limits-harness
tags: [syzygy, tb-ceiling, doctor, sprt, fastchess, gate0, rule-4, rule-14]

# Dependency graph
requires:
  - plan: 01-01 (RELEASE/SHA256SUMS + evidence/01-offline-build.log + binary-hash precondition)
  - plan: 01-02 (freeze commit bd349ec3 — first impl commit must postdate it; proven)
provides:
  - Tablebases::TB_PROBE_LIMIT=5 + clamped option (default 5 min 0 max 5) + verify_tb_ceiling() attestation at go/search_clear/SyzygyPath-on-change + fatal exit on 6-man directory
  - tools/doctor.py (13-check startup pre-flight, --json, --strict-tb) + tools/tests/test_doctor.py (7 cases)
  - tools/tests/test_tb_ceiling.py (6 cases incl. planted KQRRBvK.rtbw → exit 1)
  - tools/fastchess-linux-x86-64/ (v1.8.2-alpha, sha-pinned tarball, MIT source kept)
  - tools/books/UHO_Lichess_4852_v1.epd + SHA256SUMS (CC0-1.0, 2,632,036 lines)
  - tools/sprt.sh (audit-trailed SPRT runner) + docs/sprt.md (normative recipe + 3 corrections) + docs/build.md
  - scripts/gate0.sh (single Phase-1 gate, full run PASS incl. namespace build)
  - evidence/01-tb-ceiling.log (4 streams) + evidence/01-sprt-smoke.log (LLR line)
  - RELEASE/stock-binary/ (unmodified sf_19 binary archived + hashed pre-patch)
affects: [Phase 3 (doctor → CHECK-01 growth path, network WARN→FAIL), Phase 4 (SPRT is the TM verdict tool), Phase 6 (recipe reuse unedited)]

# Actuals (#2632) — pairs with the plan's `estimate` to calibrate future estimates.
actuals:
  tokens: 47000
  tasks: 3
  commits: 4

# Tech tracking
tech-stack:
  added: [fastchess v1.8.2-alpha (dev-only, prebuilt), UHO_Lichess_4852_v1.epd (harness book)]
  patterns: [clamp-then-assert (ucioption silently keeps old value on out-of-range setoption — attestation is the real guard), fatal-at-option-layer (returned string can't block; exit(1)), audit-trailed harness runs (invocation+date+commit+hashes), evidence-rerun-hash-sync (NOTICE cites HEAD of last committed evidence run)]

key-files:
  created:
    - src/syzygy/tbprobe.h (TB_PROBE_LIMIT constant; file already carried the dated line from 01-01)
    - tools/doctor.py
    - tools/tests/test_tb_ceiling.py
    - tools/tests/test_doctor.py
    - tools/fastchess-linux-x86-64/ (fastchess + LICENSE + app/ + Makefile + README)
    - tools/books/UHO_Lichess_4852_v1.epd
    - tools/books/SHA256SUMS
    - tools/sprt.sh
    - docs/sprt.md
    - docs/build.md
    - scripts/gate0.sh
    - evidence/01-tb-ceiling.log
    - evidence/01-sprt-smoke.log
    - RELEASE/stock-binary/ (stockfish-sf19-unmodified + SHA256SUMS)
  modified:
    - src/engine.cpp (option clamp, verify_tb_ceiling, 3 call sites, <cstdlib>)
    - src/engine.h (verify_tb_ceiling declaration)
    - NOTICE (modified-files note + binary hash history)
    - PROVENANCE.md (guard description + UHO book row)

key-decisions:
  - "TBPIECES stays 7 (format width/sizing); the Rule 4 ceiling lives only at the option/assertion layer (TB_PROBE_LIMIT=5 in tbprobe.h)"
  - "verify_tb_ceiling returns a single line — print_info_string splits on newlines, so multi-line messages break line-anchored assertions"
  - "Fatal case is exit(1) inside the SyzygyPath on_change lambda: a returned string cannot block anything; terminate_on_critical_error is private to UCIEngine so only its output shape ('info string CRITICAL ERROR: …') is replicated"
  - "6-man detection uses MaxCardinality (populated by Tablebases::init BEFORE the check runs), not filename scanning in C++ — a zero-byte KQRRBvK.rtbw raises cardinality to 6 and trips the guard"
  - "doctor.py piece_count counts TOTAL piece codes (KQRRBvK=6), not distinct letters (5) — distinct-letter counting would pass a forbidden file"
  - "Missing TB directory is SKIP by default, --strict-tb flips to FAIL (match laptop opt-in); gate0 runs plain"
  - "fastchess: tarball sha256 verified before extraction; release layout is nested (fastchess-linux-x86-64/) — flattened in place; engine syntax is cmd= not positional; -pgnout needs file= notation= (v1.8.2 CLI)"
  - "Book: UHO_Lichess_4852_v1.epd only exists inside a .zip upstream (raw .epd URL is 404 / HTML); zip sha recorded alongside"
  - "Stock binary archived + hashed BEFORE the first src edit (RELEASE/stock-binary/), satisfying the day-0 hand-off promise"
  - "Binary hash legitimately changed post-guard (077d3601… → 795056df…); bench unchanged 2,497,913 proves no search-behaviour drift; NOTICE records both hashes and the history"

# Deviations from the plan (Rules 1–3 auto-fixes, none needed Rule 4 STOP)
deviations:
  - "sprt.sh adds audit-trail hashing of BOTH binaries + the book (plan asked for commit+date+invocation; hashes are the same pattern one level deeper — evidence-grade provenance)"
  - "docs/sprt.md documents the cmd=/file= fastchess CLI forms discovered while running (plan's command shape was close but used positional engine args and 'fi' shorthand that v1.8.2 rejects)"
  - "RELEASE/stock-binary/ is an extra artifact beyond the plan's file list — it is the mechanism for the plan's own truth ('stock binary archived and hash-recorded before the first src edit')"

must_be_informed:
  - "Binary hash changed with the guard (795056df…); any downstream doc citing 077d3601… refers to the STOCK binary (archived in RELEASE/stock-binary/)"
  - "TB data (939 MiB) still not fetched — doctor SKIPs the TB checks on this box; --strict-tb on the match laptop will fail until the fetch happens"
  - "SPRT smoke was self-play (base == custom) — proves the harness, not any Elo claim; never quote its LLR as a strength result"
  - "REQUIREMENTS.md PIPE-01 records the underscore option token; docs/sprt.md is the corrected normative copy (space form verified by running fastchess)"
---

# Plan 01-03 — TB Ceiling + Doctor + SPRT Harness: SUMMARY

## What was built

**Task 1 — Rule 4 TB ceiling (LIMIT-01):**
- `TB_PROBE_LIMIT = 5` in `src/syzygy/tbprobe.h` (comment names Rule 4;
  `TBPIECES` untouched at 7).
- Option declared `Option(Tablebases::TB_PROBE_LIMIT, 0, Tablebases::TB_PROBE_LIMIT)`
  — clamped, but ucioption keeps the old value silently on out-of-range
  setoption, so:
- `Engine::verify_tb_ceiling()` attests every search: `info string TB ceiling
  OK: SyzygyProbeLimit=5 max_loaded=0` (0 = TB disabled, compliant).
- Fatal path: 6-man directory → `info string CRITICAL ERROR: TB CEILING
  VIOLATION: max_loaded=6 exceeds the Rule 4 ceiling 5`, exit 1.
- Wired at `SyzygyPath` on_change (fatal), `Engine::go()`, `search_clear()`
  (both feed the existing `onVerifyNetwork` sink).
- 6-test suite + committed evidence log with all four observed streams.
- `bench` unchanged: 2,497,913.

**Task 2 — doctor.py (LIMIT-04):** TDD (7 RED → 7 GREEN). Remote schemes,
`~`, `$VAR`, relative paths all rejected with named reasons (re-tested after
`Path.resolve()`); binary/net/option/export_net checks; TB piece counting by
total codes; book SKIPs pending LIMIT-03; vendor/chess 1.11.2; PROVENANCE §3
delegation check; `--json` consistent with exit code; never sends `go`.

**Task 3 — fastchess + SPRT (PIPE-01):** sha-pinned tarball install (binary +
MIT source kept, nothing in `src/`); book downloaded from the upstream zip and
hash-pinned; `tools/sprt.sh` with audit trail; `docs/sprt.md` normative recipe
with the three corrections (space-form option token verified by running);
`docs/build.md`; 2-round smoke SPRT → `LLR:` line committed;
`scripts/gate0.sh` — full run (incl. namespace build) **GATE0 PASS**.

## Verification evidence

| Gate | Result |
|---|---|
| `make -C src -j build` | OK |
| `python3 -m unittest tools.tests.test_tb_ceiling -v` | 6/6 |
| `python3 -m unittest tools.tests.test_doctor -v` | 7/7 (RED-first TDD) |
| `printf 'uci\nquit\n' \| ./src/stockfish \| grep -qx '…default 5 min 0 max 5'` | exact match |
| `./src/stockfish bench` (stderr) | `Nodes searched  : 2497913` |
| 6-man directory | exit 1, `CRITICAL ERROR: TB CEILING VIOLATION` |
| `fastchess --version` | `alpha 1.8.2` |
| `grep '"option.Move Overhead=100"' docs/sprt.md` + `! grep 'option.Move_Overhead'` | both hold |
| `sh tools/sprt.sh … ROUNDS=2` | `LLR: -0.02 … [0.00, 5.00]` |
| `bash scripts/gate0.sh` (FULL, namespace build) | `GATE0 PASS` |
| `python3 tools/check_contract_order.py` | freeze `bd349ec3` is ancestor of first impl commit `b12a3693` — real (non-vacuous) proof now |
| `sh scripts/check_license.sh`, `check_notice.py`, `check_provenance.py` | all OK |

## Requirements coverage

| Req | Evidence |
|---|---|
| LIMIT-01 | option line exact; clamp+attestation; 6-man → exit 1; bench unchanged |
| LIMIT-04 | doctor.py: remote/relative/~/\$VAR rejected; real tree passes; --json consistent |
| PIPE-01 | fastchess 1.8.2; SPRT smoke with LLR line; docs/sprt.md normative recipe |

## Commits

- `b12a3693` feat(01-03): Rule 4 TB ceiling — clamp, attest, exit on forbidden tablebase
- `3d7d6791` feat(01-03): doctor.py startup pre-flight (LIMIT-04)
- `724b3174` feat(01-03): fastchess + SPRT recipe + gate0.sh (PIPE-01)
- `626bd400` fix(01-03): sync NOTICE binary hash with post-guard evidence run

## Leftovers for later plans/phases

- TB fetch (939 MiB) still pending → doctor TB checks SKIP here; `--strict-tb`
  fails on the match laptop until fetched; then PROVENANCE §2.1 regeneration.
- Phase 3: doctor's network-state WARN becomes a hard fail; listening-socket
  check (T-01-16) lands then.
- Phase 4: SPRT is the TM verdict tool; `docs/sprt.md` reused unedited.
- LIMIT-03 book ply-scan arrives in its own plan (doctor's book check SKIPs).
