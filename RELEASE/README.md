# RELEASE — ChessChallendIII

This directory holds the release manifest produced by
`scripts/archive_usb.sh --dest <dir>`: the complete corresponding source
(`git archive` tarball of the build commit), the built binary, the official
NNUE network, and the licence/provenance set.

## Contents of an archive run

| File | What it is | Why |
|---|---|---|
| `ChessChallendIII-<commit>.tar.gz` | `git archive` of the build commit | GPLv3 §6: complete corresponding source for the exact binary |
| `stockfish` | the built engine binary | the competition artefact |
| `nn-1a298aa575a0.nnue` | official Stockfish 19 network, unmodified | embedded in the binary; media delivery permitted by Rule 15 |
| `NOTICE`, `PROVENANCE.md` | provenance declarations | Rule 1 origin declaration; Rule 15 weights origin |
| `Copying.txt`, `AUTHORS` | upstream GPL licence and authors, byte-identical to `sf_19` | GPLv3 §4 |
| `SHA256SUMS` | manifest of everything above, verified in place by the script | an unverified copy is worse than none |

## Why media delivery is permitted

Rule 15 allows evaluation weights on physical media accompanied by an origin
declaration: `PROVENANCE.md` §1 declares the net (bytes, SHA-256, CC0-1.0,
NOT AUTHORED BY THE TEAM) and `NOTICE` ties the binary to the exact commit.

## Outstanding human steps (recorded in the phase `user_setup`)

1. **Panel URL confirmation** — confirm
   https://github.com/matheus-henri-ferr/Chess-Challenge-III is public (or
   grant the panel a verified read account) and hand the URL to the team.
2. **Physical USB copy** — provide a ≥ 4 GiB USB device and run
   `scripts/archive_usb.sh --dest /media/<user>/<label>/CHESSCHALLENDIII`;
   the script verifies `SHA256SUMS` at the destination. This repository
   contains only the dry-run manifest (`SHA256SUMS` produced against a local
   temporary directory), not the physical copy.

License: GPL-3.0-or-later. See Copying.txt and NOTICE.
