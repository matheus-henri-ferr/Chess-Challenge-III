# ChessChallendIII history rewrite record (2026-10-27)

## What happened

The first `git push` to GitHub was rejected (GH001): a large file exceeded the
100 MB hard limit.

- File: `tools/books/UHO_Lichess_4852_v1.epd` (174,889,110 bytes / 166.79 MiB)
- Introduced by: old commit `1e4f0482` (feat(01-03): fastchess + SPRT recipe + gate0.sh)
- The file was also present in the grafted upstream history (the sf_19 import),
  so ~3,097 commits referenced its blob.

## What was done

`git filter-repo --invert-paths --path tools/books/UHO_Lichess_4852_v1.epd --force`

Every commit that carried the blob was rewritten, including the grafted
Stockfish history. All commit hashes from the first changed commit onward are
different. The full old→new mapping is preserved in `.git/filter-repo/commit-map`
(local only, not tracked).

## Key identity remaps

| Object | Old | New |
|---|---|---|
| `sf_19` / `base-sf19` tag target | `edb0d9db6731067ec50ce619ff372b463bc4dd5d` | `f879373d916914de3a478aabb4226e6460c17d15` |
| sf_19 import commit (project base) | `0ef8529b9e8dc455bdc8d75a9f2a75d32a4d160f` | `f3c886956071c51cc61d9b9c47c4152c48e6a2c9` |
| Freeze commit (PROTOCOL+LOGBOOK) | `2fd4bf4f279c9160fda64a58cfc126f6a7b93f45` | `bd349ec3c5157a4c04a617513793b643d3e61fa3` |
| Pre-rewrite HEAD | `e0d9ecec23b27baed77245774a7fcd66c3340028` | `c783691e670af59ab09e6dc78dedd80749a820a3` |

Tag message, author and committer metadata are unchanged; only tree hashes
differ (the removed blob). The tag still resolves to the official "Stockfish 19"
release commit content minus nothing that matters: the book file was never part
of upstream — it sat in our `tools/books/` addition on the import merge lineage.

## Integrity policy applied after the rewrite

- `NOTICE`, `.planning/` documents, `PROVENANCE.md` and
  `tools/check_contract_order.py` were remapped to the new hashes so live
  checkers (`check_notice.py`, `check_contract_order.py`, gate0) stay green.
- Verbatim run records were **left untouched** — their hashes were true when
  captured and editing them would falsify the record:
  - `evidence/01-offline-build.log` (build commit `6a64b1fb…` old-namespace)
  - `evidence/01-sprt-smoke.log` (commit `3fa911f5…` old-namespace)
  - `evidence/01-tb-ceiling.log` (commit `feb0d88e…` old-namespace)
  - `results/sprt-20261027T130846Z.log`
  - `RELEASE/SHA256SUMS` (dry-run manifest against the pre-rewrite tree)
- Binary identity is unaffected: `src/stockfish` sha256
  `527fa7ac4a23e124d207ebe342bbf0cf7c379277770a4073964ef17ce6ed5134`, bench
  2,497,913 — the rewrite touched no `src/` bytes and no built artifact.

## Consequences

- The book file is no longer in git. `tools/books/SHA256SUMS` pins its sha256
  (`7a7f6470615a69c6cf23d565417701d38732876f480af90d67b42abade35644a`); fetch
  `UHO_Lichess_4852_v1.epd.zip` from official-stockfish/books and verify before
  running `tools/sprt.sh`. `doctor.py` reports the missing file as SKIP.
- `RELEASE/stock-binary/stockfish-sf19-unmodified` (94.76 MB) stays in git: it
  is under the 100 MB hard limit (warning only).
- Old clones must re-clone; the remote history was force-pushed after this note.

License: GPL-3.0-or-later. See Copying.txt and NOTICE.
