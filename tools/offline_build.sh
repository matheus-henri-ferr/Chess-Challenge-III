#!/bin/sh
# ChessChallendIII — FOUND-04 offline build proof
# Copyright (C) 2026 ChessChallendIII
# SPDX-License-Identifier: GPL-3.0-or-later
#
# Builds the engine inside a network namespace from a FRESH LOCAL CLONE at the
# default-branch HEAD (which carries the vendored net), proves bench reproduces
# 2,497,913 nodes and that the binary embeds the committed net byte-for-byte,
# and writes evidence/01-offline-build.log.
#
# Never gates on `make net`: scripts/net.sh returns 1 from fetch_network and
# discards it, so `make net` exits 0 even when every download fails. Only a
# full `build` + `bench` + `export_net` proves offline reproducibility.
set -eu

REPO=$(git rev-parse --show-toplevel)
cd "$REPO"
LOG="$REPO/evidence/01-offline-build.log"
EVIDENCE_DIR="$REPO/evidence"
BUILD_COMMIT=$(git rev-parse HEAD)
CLONE=$(mktemp -d)/chesschallendiii
mkdir -p "$EVIDENCE_DIR"

sha256sum=$( (command -v sha256sum >/dev/null 2>&1 && echo "sha256sum") ||
  (command -v shasum >/dev/null 2>&1 && echo "shasum -a 256"))

# Sever the network. unshare -n needs CAP_SYS_ADMIN; unshare -rn is the
# unprivileged fallback (user namespace + network namespace). The choice is
# recorded in the evidence log. On the match laptop prefer `sudo unshare -n`.
NS=""
if unshare -n true 2>/dev/null; then
  NS="unshare -n"
elif unshare -rn true 2>/dev/null; then
  NS="unshare -rn"
else
  echo "FATAL: no network namespace available" >&2; exit 1
fi

{
  echo "ChessChallendIII offline build proof (FOUND-04)"
  echo "build commit (default branch HEAD): $BUILD_COMMIT"
  echo "namespace: $NS"
  echo "id -u: $(id -u)"
  echo "date: $(date -u '+%Y-%m-%dT%H:%M:%SZ')"

  # 1) The build commit must descend from the declared upstream base — this
  #    provenance assertion replaces a `--branch sf_19` clone (the vendored net
  #    and the .gitignore negation postdate sf_19).
  git merge-base --is-ancestor sf_19 HEAD
  echo "provenance: sf_19 is an ancestor of HEAD: OK"

  # 2) Fresh local clone — history intact, net tracked, hash checked.
  git clone -q "$REPO" "$CLONE"
  cd "$CLONE"
  test "$(git rev-parse HEAD)" = "$BUILD_COMMIT" || {
    echo "FATAL: clone HEAD != build commit" >&2; exit 1; }
  echo "git clone <local repo> at $BUILD_COMMIT: OK"
  git ls-files --error-unmatch src/nn-1a298aa575a0.nnue >/dev/null
  echo "git ls-files --error-unmatch src/nn-1a298aa575a0.nnue: OK"
  $sha256sum -c <<'EOF'
1a298aa575a085434d29027978dc36867fe9c5bcea9376654b7a8eba1e52dfc2  src/nn-1a298aa575a0.nnue
EOF
  echo "Existing nn-1a298aa575a0.nnue validated, skipping download"

  # 3) Clean room in the clone — otherwise the build proves nothing.
  make -C src objclean

  # 4) Build with no network at all (this IS the evidence: full log captured).
  echo
  echo "## namespace build (clone, objclean first)"
  $NS make -C src -j"$(nproc)" build
  test -x src/stockfish
  echo "binary built and executable: OK"

  # 5) The committed net really is inside the binary.
  echo
  echo "## embedded-net proof"
  printf 'export_net /tmp/net-exported.nnue\nquit\n' | src/stockfish >/dev/null
  cmp src/nn-1a298aa575a0.nnue /tmp/net-exported.nnue
  rm -f /tmp/net-exported.nnue
  echo "export_net cmp: identical"

  # 6) Bench must match the declared node count. bench prints its summary on
  #    STDERR — capture both streams.
  echo
  echo "## bench (stderr captured)"
  src/stockfish bench 2>&1 | tail -5
  NODES=$(src/stockfish bench 2>&1 | sed -n 's/^Nodes searched  : //p')
  test "$NODES" = "2497913" || { echo "bench mismatch: $NODES" >&2; exit 1; }
  echo "bench nodes: $NODES"

  # 7) Identity of the namespace-built binary (a DIFFERENT artifact from the
  #    working-tree binary; both are recorded in evidence/01-binary.sha256).
  echo
  echo "## namespace build identity"
  $sha256sum src/stockfish
  stat -c '%y %s' src/stockfish

  NAMESPACE_HASH=$($sha256sum src/stockfish | awk '{print $1}')

  # 8) No remote fetch may appear anywhere in this log.
  if grep -q "Downloading from" "$LOG" 2>/dev/null; then
    echo "FATAL: evidence log contains a download" >&2; exit 1
  fi

  # 9) Clean-room rebuild of the WORKING TREE at the same commit so
  #    src/stockfish stays a clean HEAD build (the artifact 01-03's
  #    precondition gates on). Expected byte-identical to the clone build.
  cd "$REPO"
  make -C src objclean
  $NS make -C src -j"$(nproc)" build >/dev/null 2>&1
  test -x src/stockfish
  WORKING_HASH=$($sha256sum src/stockfish | awk '{print $1}')

  {
    echo "# ChessChallendIII binary identities (plan 01-01 Task 3)"
    echo "# line 1 = working-tree binary at HEAD, clean objclean rebuild (the artifact 01-03 gates on)"
    echo "# line 2 = namespace-severed fresh-clone build (the offline proof)"
    echo "$WORKING_HASH"
    echo "$NAMESPACE_HASH"
  } > "$EVIDENCE_DIR/01-binary.sha256"

  echo
  echo "## working-tree rebuild (clean, same commit)"
  echo "working-tree sha256: $WORKING_HASH"
  echo "OFFLINE BUILD PROOF COMPLETE"
} > "$LOG" 2>&1

# 10) Assert the log's required content.
grep -q "^namespace: unshare" "$LOG"
grep -q "Existing nn-1a298aa575a0.nnue validated, skipping download" "$LOG"
grep -q "Nodes searched  : 2497913" "$LOG"
! grep -q "Downloading from" "$LOG"

rm -rf "$CLONE"
$sha256sum src/stockfish
echo "evidence written: $LOG"
echo "OFFLINE BUILD PROOF COMPLETE"
