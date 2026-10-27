# PROVENANCE — ChessChallendIII

License: GPL-3.0-or-later. See Copying.txt and NOTICE.

## 1. Evaluation network (NNUE)

| Property | Value |
|---|---|
| File | nn-1a298aa575a0.nnue |
| Bytes | 98511183 |
| SHA-256 | 1a298aa575a085434d29027978dc36867fe9c5bcea9376654b7a8eba1e52dfc2 |
| Architecture | SFNNv16 (Stockfish 19 single-net; the secondary small net was retired in SF16.1+) |
| Source URL | https://tests.stockfishchess.org/api/nn/nn-1a298aa575a0.nnue |
| Mirror | https://github.com/official-stockfish/networks/raw/master/nn-1a298aa575a0.nnue |
| License | CC0-1.0 (public domain dedication, official-stockfish/networks) |
| Embedded in binary | yes — INCBIN of EvalFileDefaultName (src/nnue/network.cpp); `export_net` round-trip is byte-identical (evidence/01-offline-build.log) |
| Authorship | NOT AUTHORED BY THE TEAM. Official Stockfish 19 network, unmodified. Rule 15: third-party weights do not count as authorship; the team has no training code. |
| Authorization | Rule 15: weights may be delivered on physical media with an origin declaration; Rule 14: no network access is required at run time. |

## 2. Tablebases

| Property | Value |
|---|---|
| Permitted by rule | 3, 4 and 5 pieces only (Rule 4) |
| Retrieved from | https://tablebase.sesse.net/syzygy/3-4-5/ (mirror: https://syzygy-tables.info) |
| Retrieval date | not yet fetched |
| Local path (game) | /opt/tb/3-4-5 (absolute; never relative) |
| Engine option | SyzygyPath, with SyzygyProbeLimit=5 enforced by Tablebases::TB_PROBE_LIMIT (src/syzygy/tbprobe.h), clamped at the option layer (default 5 min 0 max 5), attested at every search (`info string TB ceiling OK: …`), and fatal on a 6-man directory (`CRITICAL ERROR: TB CEILING VIOLATION`, exit 1) — see evidence/01-tb-ceiling.log |
| File count | not yet fetched (expected 378 .rtbw + 561 .rtbz, 939 MiB total) |
| Total bytes | not yet fetched |
| Manifest | tb/SHA256SUMS at the tablebase root (see §2.1) |
| Authorship | Not authored by the team; data, not code. |

### 2.1 Tablebase inventory

Not yet fetched — the tablebase directory does not exist on this machine.
Fetch before the event, then regenerate this block with
`cd /opt/tb/3-4-5 && sha256sum *.rtbw *.rtbz | sort -k2`.

Every filename must tokenise to at most 5 piece codes (e.g. `KQvK.rtbw` = 3,
`KQRRBvK` = 6 — forbidden); `tools/check_provenance.py` enforces it, and the
engine itself refuses a directory containing a 6-man file (exit 1,
`CRITICAL ERROR: TB CEILING VIOLATION`).

## 3. Dependencies

| Name | Version | Pin mechanism | SHA-256 | License | Shipped? | Purpose |
|---|---|---|---|---|---|---|
| python-chess (`chess`) | 1.11.2 | vendored at `vendor/chess/` (no resolver; sdist verified then tree-pinned in `vendor/chess/SHA256SUMS`) | sdist a8b43e5678fdb3000695bdaa573117ad683761e5ca38e591c4826eba6d25bb39 | GPL-3.0-or-later | yes | board replica, UCI client, Polyglot, Syzygy probing (console/tooling) |
| fastchess | 1.8.2-alpha (20260726-f618e34) | prebuilt release binary + MIT source at `tools/fastchess-linux-x86-64/` (dev-only) | tarball 1003f920bebe841acdab5e6d7871e93171a4586857b3ec91c21ef5777f26ff96 | MIT | no | SPRT / match runner (development only, never inside the engine tree) |
| UHO_Lichess_4852_v1.epd | official-stockfish/books (16 plies) | pinned in `tools/books/SHA256SUMS` (sourced from `UHO_Lichess_4852_v1.epd.zip` in the same repo) | 7a7f6470615a69c6cf23d565417701d38732876f480af90d67b42abade35644a | CC0-1.0 | no | SPRT openings (harness only — the competition book is separate, Rule 3) |
| GCC / libstdc++ | 16.2.1 | system toolchain | n/a | GPL-3.0-or-later with GCC Runtime Library Exception | n/a | build only |
| Python | 3.14.7 | system interpreter (stdlib only for Phase-1 tooling; `chess` vendored, never pip-installed) | n/a | PSF-2.0 | n/a | console + tooling |
| Openings books (harness) | official-stockfish/books | downloaded pre-event into `tools/books/`; see the UHO_Lichess_4852_v1.epd row above | recorded in `tools/books/SHA256SUMS` | CC0-1.0 | no | SPRT openings |
| Syzygy 3-4-5 | 2026-08 snapshot (pending fetch) | downloaded pre-event; hash manifest at the tablebase root | (see §2.1) | probe code GPLv3 (src/syzygy/); data unrestricted | yes (media) | endgame play-off |

## 4. Not authored by the team

- The Stockfish engine (GPLv3, tag `sf_19`, commit `f879373d916914de3a478aabb4226e6460c17d15`) — every file under `src/` except the three dated modifications recorded in NOTICE.
- The NNUE network (`nn-1a298aa575a0.nnue`, CC0-1.0) — official, unmodified.
- Syzygy tablebase data.
- Harness opening books (`official-stockfish/books`, CC0-1.0).
- `python-chess` (GPL-3.0-or-later, vendored verbatim), `fastchess` (MIT, dev-only), `incbin.h` (public domain, `src/incbin/UNLICENCE`).

Authored by the team: the time manager (`src/timeman.*`, Phase 4), the console, the pipeline tooling, and the documents in `docs/`. See AUTHORSHIP.md when it exists.

## 5. Publication (FOUND-06)

| Property | Value |
|---|---|
| Panel URL | https://github.com/matheus-henri-ferr/Chess-Challenge-III |
| Panel access confirmed | OUTSTANDING — human step (`user_setup`): confirm the repository is public or grant the panel a verified read account |
| USB media | OUTSTANDING — human step (`user_setup`): run `scripts/archive_usb.sh --dest /media/<user>/<label>/CHESSCHALLENDIII` with a ≥ 4 GiB device |

The URL above is derived from `git remote get-url origin`; the confirmation
that the panel can actually reach it is a human step recorded in the phase's
`user_setup` dashboard and surfaced as a WARN by `tools/check_provenance.py`,
never silently assumed.
