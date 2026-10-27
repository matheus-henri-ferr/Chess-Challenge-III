# Build — ChessChallendIII

Normative. The only supported build command:

```sh
make -C src -j"$(nproc)" build
```

## Why not the obvious variants

| Command | Why it is wrong |
|---|---|
| bare `make` (repo root) | builds **nothing**: there is no root Makefile; the only Makefile is `src/Makefile` (and a target-less `make -C src` errors: no default goal is declared for this use). |
| `make net` | can never be a gate: `scripts/net.sh:74` returns 1 from `fetch_network` and line 77 **discards** it, so `make net` exits 0 even when every download failed. Only a full `build` + `bench` + `export_net` proves anything (see `tools/offline_build.sh`). |
| `make -C src profile-build` | valid but a **different artifact**: PGO instruments, benches, and rebuilds. Bench nodes stay identical (2,497,913) but the binary hash differs from a plain `build`. If the shipped binary is a profile-build, `NOTICE` must record that profile and its own hash — never mix the two. |

## Build identity

- `ARCH=native` auto-detects the ISA (`x86-64-avxvnni` on this box).
- Compiler string: `printf 'compiler\nquit\n' | ./src/stockfish`.
- Reproducibility: clean rebuilds of the same commit produce the byte-identical
  binary (proven in `evidence/01-offline-build.log`, hash `077d3601…` for the
  pre-01-03 tree).
- Offline: `tools/offline_build.sh` runs the whole build inside `unshare -rn`
  from a fresh clone; the net is vendored and hash-checked, never downloaded.

## After any `src/` change

1. `make -C src -j"$(nproc)" build`
2. `./src/stockfish bench` → must report `Nodes searched  : 2497913`
3. `python3 -m unittest discover -s tools/tests -t .`
4. `bash scripts/gate0.sh --skip-build` (or full, when the tree must prove
   itself end-to-end).
