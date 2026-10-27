# Walking Skeleton — ChessChallendIII

**Phase:** 1
**Generated:** 2026-10-26

## Capability Proven End-to-End

> Como equipe, quero compliance provável e contrato congelado no dia 0, para que nenhuma decisão irrecuperável fique para depois.

Concretely: an auditor on the match laptop, with the network severed, rebuilds the engine from a fresh clone, reproduces `bench` 2,497,913, exports the embedded net byte-identically, and reads `NOTICE`/`PROVENANCE.md` to a full SHA and tag — while a mock engine and a mock driver complete a real search by speaking only the frozen `go` line from `docs/PROTOCOL.md`.

## Architectural Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Engine base | Stockfish 19, tag `sf_19` = `edb0d9db6731067ec50ce619ff372b463bc4dd5d`, real clone with full 7,252-commit history | Rule 1 needs a citable origin commit; a copy or a shallow clone cannot be declared to the panel. Tag `base-sf19` marks our branch point. |
| Build command | `make -C src -j$(nproc) build` — the only one | There is no root Makefile, and `make -C src` defaults to `help:` (`src/Makefile:1007`), exiting 0 having built nothing: the most dangerous failure signature available. |
| Offline proof | Build inside `unshare -n` (fallback `unshare -rn`), choice recorded in `evidence/01-offline-build.log` | Rule 14 is retroactive. `make net` exits 0 on a failed fetch (`scripts/net.sh:74` returns 1, `:77` discards it), so only a full build + `bench` + `export_net` `cmp` proves offline. |
| Evaluation net | Official `nn-1a298aa575a0.nnue`, 98,511,183 B, sha256 `1a298aa575a085434d29027978dc36867fe9c5bcea9376654b7a8eba1e52dfc2`, committed and embedded | Vendored in git so the clone builds with no network; CC0-1.0 needs no attribution but Rule 15 forbids presenting it as ours — hence the explicit non-authorship marker. |
| Authored component scope | A structural rewrite of `TimeManagement` (`src/timeman.cpp`/`.h`), not parameter tweaks | Rule 2 excludes "mero ajuste de parâmetros"; a different decision structure with a documented algorithm is defensible and testable by clock-remaining, the Rule 12 metric. |
| Contract location | `docs/PROTOCOL.md` + `docs/LOGBOOK.md`, frozen in a docs-only commit before any `src/`/`console/`/`pipeline/` change | The freeze is a git fact (`git merge-base --is-ancestor`), not a claim in prose; it is the only shared dependency between the three tracks. |
| Rule 4 enforcement tier | Engine-side clamp + attestation (`TB_PROBE_LIMIT = 5`), with `doctor.py` as defence in depth | `setoption` is an engine surface; fastchess, a debug shell or a stray line bypasses any console check. `TBPIECES` stays 7 — it sizes internal arrays. |
| Python dependency | `python-chess` 1.11.2 vendored at `vendor/chess/`, pinned by tree hash | No pip offline: PyPI publishes only an sdist for 1.11.2 and `pip install --no-index` fails on missing `setuptools`. Tree copy + `SHA256SUMS` is the honest Rule 14 statement. |
| Test harness | fastchess v1.8.2-alpha, dev-only, SPRT at `tc=10+0.1` | No Qt dependency, prebuilt binary, pentanomial SPRT. Recipe token is `"option.Move Overhead=100"` with a space — the underscore form is rejected. Never SPRT at `15+10`. |
| Directory layout | `src/` (engine fork) · `docs/` (normative specs) · `tools/` (mocks, checkers, dev binaries) · `scripts/` (gates) · `vendor/` (pinned third party) · `evidence/` (committed proof) · `RELEASE/` (panel manifest) | Keeps the engine tree a clean Stockfish derivative (GPL story intact), keeps dev-only MIT tooling out of `src/`, and makes every claim a file rather than a sentence. |
| Gate | `scripts/gate0.sh` — one exit code | Phase 1's acceptance is a script exit code, not a human opinion. |

## Stack Touched in Phase 1

- [x] Scaffold — real clone with history, tags `sf_19` and `base-sf19`, `.gitignore` net negation, build verified end to end
- [x] Build reproducibility — namespace build, byte-identical `bench` node count, `export_net` round-trip, committed evidence log
- [x] Delivery path — `RELEASE/SHA256SUMS`, `scripts/archive_usb.sh`, panel access recorded (human step)
- [x] Runtime contract — two normative documents plus two mocks that speak them to each other with a committed transcript
- [x] Rule ceilings — engine-side TB guard with fatal exit, startup `doctor` rejecting remote/relative asset paths
- [x] Test harness — fastchess installed, SPRT recipe documented and smoke-run with `LLR:` output
- [x] Stock binary hand-off — unmodified binary archived and hashed before the first `src/engine.cpp` edit
- [ ] Console — none in this phase, by design (Phase 2)
- [ ] User-visible gameplay — none in this phase, by design (Phase 2)

## Out of Scope (Deferred to Later Slices)

- Any console code, board replica, legality gate, or operator loop (Phase 2)
- Clock authority, latency measurement, crash resilience, book/ply enforcement, log `log_lint` implementation (Phase 3)
- The `TimeManagement` rewrite itself and the `tm=` values behind the frozen grammar (Phase 4)
- Ponder-on, `Ponder` option flip, and ponder-miss handling (Phase 5)
- SPRT verdicts and Elo claims — Phase 1 only proves the harness runs (Phase 6)
- Tablebase data download; Phase 1 declares the inventory and the ceiling, it does not fetch 939 MiB
- Public release packaging polish beyond the manifest and the USB script
- Fine-tuning or claiming the NNUE net: permanently out of scope (Rule 15)

## Subsequent Slice Plan

Each later phase adds one vertical slice on top of this skeleton without altering its architectural decisions:

- Phase 2: A complete game playable through the console against stock Stockfish, every half-move logged in the Rule 9 schema, no illegal move reaching the board replica.
- Phase 3: The console is clock authority, survives a crash or engine death mid-game, and cannot breach the book or tablebase ceilings.
- Phase 4: The authored `TimeManagement` is in place and defended by clock-remaining evidence against `mock_gui`.
- Phase 5: Ponder is on and a ponder miss is a tested, logged non-event.
- Phase 6: SPRT verdicts and a tuned build, produced by the recipe frozen here.
- Phase 7: Event-day rehearsal, USB restore drill, and the panel hand-over.
