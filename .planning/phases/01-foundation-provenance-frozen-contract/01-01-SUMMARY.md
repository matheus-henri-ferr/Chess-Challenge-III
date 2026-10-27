---
phase: 01-foundation-provenance-frozen-contract
plan: 01
subsystem: compliance-provenance
tags: [gplv3, provenance, offline-build, nnue, syzygy, notice, sha256]

# Dependency graph
requires:
  - phase: none
    provides: sf_19 import (0ef8529b), vendored net (a2f963bf), stock Stockfish 19 build
provides:
  - NOTICE with command-derived provenance fields + tools/check_notice.py machine gate
  - PROVENANCE.md (NNUE identity, TB section, dependency manifest) + tools/check_provenance.py
  - scripts/check_license.sh (GPL header/modification-line/blob-integrity gate)
  - vendor/chess/ = python-chess 1.11.2 vendored by tree + SHA256SUMS pin
  - tools/offline_build.sh → evidence/01-offline-build.log (unshare -rn namespace build, bench 2497913, export_net identical)
  - evidence/01-binary.sha256 (working-tree + namespace-build identities, byte-identical)
  - scripts/archive_usb.sh + RELEASE/ (manifest + README; USB/panel human steps outstanding)
  - dated modification lines on src/engine.cpp, src/engine.h, src/syzygy/tbprobe.h (headers only; the clamp itself is 01-03)
affects: [Phase 2 console track (vendor/chess), 01-03 (src patch precondition + gate0), Phase 3 doctor/CHECK-01, Phase 6 SPRT, panel hearing]

# Actuals (#2632) — pairs with the plan's `estimate` to calibrate future estimates.
actuals:
  tokens: 42870
  tasks: 3
  commits: 5

# Tech tracking
tech-stack:
  added: [python-chess 1.11.2 (vendored), stdlib unittest suite in tools/tests/]
  patterns: [evidence-as-artefact (script → committed log → checker re-derives), git-as-baseline (blob compare, no sidecar hashes), working-tree diff checks (git diff sf_19), WARN-don't-FAIL for outstanding human steps]

key-files:
  created:
    - NOTICE
    - PROVENANCE.md
    - tools/check_notice.py
    - tools/check_provenance.py
    - tools/tests/test_provenance.py
    - tools/tests/__init__.py
    - tools/offline_build.sh
    - scripts/check_license.sh
    - scripts/archive_usb.sh
    - vendor/chess/ (12 files)
    - RELEASE/README.md
    - RELEASE/SHA256SUMS
    - evidence/01-offline-build.log
    - evidence/01-binary.sha256
  modified:
    - src/engine.cpp
    - src/engine.h
    - src/syzygy/tbprobe.h

key-decisions:
  - "check_license.sh GPL-header check scoped to files this fork touched (git diff sf_19), not every src/ file — src/incbin/incbin.h is upstream public domain and a blanket loop false-fails"
  - "Modification-line regex allows a '// ' comment prefix — the bare ^Modified anchor from RESEARCH Q2 cannot appear in compilable C++; line content after the prefix is unchanged"
  - "vendor/chess/ layout = package directory directly (PYTHONPATH=vendor works), matching the RESEARCH Q10 recipe, not a nested chess/chess/ copy"
  - "vendor/chess/SHA256SUMS excludes itself so 'sha256sum -c' verifies in place"
  - "offline_build.sh captures the build log from the namespaced CLONE build itself (first draft rebuilt post-capture would have proven nothing — RESEARCH Pitfall 'stale *.o'), then clean-rebuilds the working tree to the identical hash"
  - "NOTICE Binary sha256 = 077d3601… (a `build`, not profile-build); NOTICE Narrative records that a profile-build ships a different hash with identical bench, and which profile produced which hash must be stated if the shipped binary is a profile-build"
  - "TB inventory section states 'not yet fetched' (no tablebase directory exists on this box) with the regeneration command — the section and its ≤5-piece guard are live"
  - "Panel URL derived from git remote origin and recorded in PROVENANCE.md §5; panel confirmation + physical USB copy stay outstanding human steps (WARN in checker, never FAIL)"

# Deviations from the plan (Rules 1–3 auto-fixes, none needed Rule 4 STOP)
deviations:
  - "RESEARCH Q2's check_license.sh prototype ran GPL checks over ALL tracked src/ files; committed version scopes them to fork-touched files (incbin.h is public domain). Substance preserved: every touched file is header+date-checked; Copying.txt/AUTHORS blob identity unchanged."
  - "offline_build.sh restructured from the RESEARCH skeleton: single clone-build capture + clean working-tree rebuild (first draft's post-capture rebuild would have been a stale-object build). All load-bearing fragments preserved verbatim (objclean, unshare probe, stderr bench, export_net cmp, no-download assert)."

must_be_informed:
  - "FOUND-06 human steps are OPEN: (1) confirm https://github.com/matheus-henri-ferr/Chess-Challenge-III is public/panel-reachable; (2) run scripts/archive_usb.sh onto a ≥4 GiB USB device. Both are user_setup dashboard items; checkers emit WARN, never block."
  - "Tablebase fetch (939 MiB) is still pending — PROVENANCE §2 says 'not yet fetched'; needed before the event and before doctor.py's TB checks (01-03) have data."
  - "Match laptop must reproduce the proof with sudo unshare -n (assumption A1); unshare -n lacks privilege on this dev box, unshare -rn used and recorded."
---

# Plan 01-01 — Provenance & Offline Build Proof: SUMMARY

## What was built

Three command-derived compliance artefacts plus their machine gates, a vendored
dependency, and a network-severed build proof:

- **NOTICE** — every field produced by a command (`git rev-parse sf_19`,
  `printf 'compiler\nquit\n' | ./src/stockfish`, bench on stderr, `sha256sum`),
  never typed from memory. `tools/check_notice.py` re-derives `Base commit`,
  `Bench nodes` (2497913), `NNUE net sha256`, and validates the `Modified files:`
  list against `git diff sf_19` (every entry tracked, genuinely differing, and
  never the vendored net).
- **PROVENANCE.md** — NNUE table (98,511,183 B, full SHA-256, `NOT AUTHORED BY
  THE TEAM` verbatim), tablebase section (permitted set, retrieval source,
  `not yet fetched` inventory with a live ≤5-piece guard), seven-column
  dependency manifest (`fastchess` marked `Shipped? = no`), §4 non-authorship,
  §5 panel URL derived from `origin`.
- **scripts/check_license.sh** — `Copying.txt`/`AUTHORS` blob identity against
  `sf_19` (`f288702d…`/`b5ad83d5…`), GPL header + dated modification line on
  every fork-touched engine source, `fail` accumulator so all violations report
  in one run.
- **vendor/chess/** — python-chess 1.11.2 by tree, not resolver: sdist hash
  verified (`a8b43e56…`), only `chess/` + `LICENSE.txt` copied, tree pinned by
  committed `SHA256SUMS`, imports clean on CPython 3.14.7 with
  `PYTHONPATH=vendor`.
- **tools/offline_build.sh → evidence/01-offline-build.log** — fresh local
  clone at HEAD (provenance via `git merge-base --is-ancestor sf_19 HEAD`), net
  tracked + hash-checked, `objclean`, `unshare -rn` build (fallback probe
  recorded, `id -u` recorded), `export_net` byte-identical to the committed
  net, bench `2497913` captured from stderr, zero `Downloading from` lines.
  Working tree then rebuilt clean to the **same hash**.
- **scripts/archive_usb.sh + RELEASE/** — absolute-only destination, refuses
  paths inside the repo, `git archive` source + binary + net + licence set,
  `SHA256SUMS` written and re-verified at the destination; dry-run manifest
  committed as `RELEASE/SHA256SUMS`.

## Verification evidence

| Gate | Result |
|---|---|
| `python3 tools/check_notice.py` | `OK NOTICE` |
| `python3 tools/check_provenance.py` | `OK PROVENANCE` |
| `sh scripts/check_license.sh` | exit 0 |
| `sh tools/offline_build.sh` | exit 0; `namespace: unshare -rn`; bench `2497913`; `export_net cmp: identical` |
| `python3 -m unittest discover -s tools/tests -t .` | 5/5 pass (TDD: all 5 RED before PROVENANCE.md existed) |
| `PYTHONPATH=vendor python3 -c "…assert chess.__version__ == '1.11.2'"` | pass |
| `(cd vendor/chess && sha256sum -c SHA256SUMS --quiet)` | pass |
| `printf 'uci\nquit\n' | ./src/stockfish | grep 'SyzygyProbeLimit … default 7'` | still upstream 7 — clamp lands in 01-03 by design |
| `git rev-parse sf_19:Copying.txt == HEAD:Copying.txt` (and AUTHORS) | equal |

Reproducibility: clean rebuilds at the same commit produced the byte-identical
binary `077d3601b503c369f97ed06df73cd5f3b44fd3d3fa513e31c92065da992c4a79`
(matching the research baseline), recorded for both the working tree and the
namespace build in `evidence/01-binary.sha256`.

## Requirements coverage

| Req | Evidence |
|---|---|
| FOUND-01 | NOTICE + `check_notice.py` (re-derives from commands) — pass |
| FOUND-02 | `check_license.sh` blob identity + dated lines on engine.cpp/engine.h/tbprobe.h — pass |
| FOUND-03 | PROVENANCE.md + `check_provenance.py` + 5 unittest cases — pass |
| FOUND-04 | `offline_build.sh` → committed evidence log, `unshare -rn`, bench 2497913, net embedded byte-identical — pass |
| FOUND-06 | `archive_usb.sh` verified dry run + `RELEASE/SHA256SUMS` committed; panel URL recorded; **human steps (panel confirmation, physical USB) outstanding as `user_setup`** |
| FOUND-05 | Not in this plan — owned by 01-02 (`docs/PROTOCOL.md` + `docs/LOGBOOK.md` freeze) |

## Commits

- `345d1376` feat(01-01): NOTICE + licence gate end-to-end
- `a84a87d7` feat(01-01): PROVENANCE.md + vendored python-chess pinned by tree
- `273af4f1` feat(01-01): network-severed build proof + release/USB manifest
- `59beaccd` fix(01-01): sync NOTICE project-commit with final evidence run

## User setup (human steps produced by this plan)

1. **github** — confirm https://github.com/matheus-henri-ferr/Chess-Challenge-III
   is public (or grant the panel a verified read account); FOUND-06, Rule 1.
2. **usb-media** — provide a ≥ 4 GiB USB device and run
   `scripts/archive_usb.sh --dest /media/<user>/<label>/CHESSCHALLENDIII`;
   FOUND-06, Rule 15.

## Leftovers for later plans/phases

- Tablebase fetch (939 MiB) + `tb/SHA256SUMS` regeneration → before 01-03's
  doctor TB checks have data; PROVENANCE §2.1 stays "not yet fetched" until then.
- `docs/timeman/` + AUTHORSHIP.md cited in NOTICE Narrative arrive with the
  Phase 4 authorship component.
- Laptop reproduction of the offline proof with `sudo unshare -n` (assumption
  A1) — dev box used `unshare -rn`, recorded in the log.
