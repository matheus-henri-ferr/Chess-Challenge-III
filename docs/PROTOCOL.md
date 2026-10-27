# PROTOCOL — Console ↔ Engine Contract (ChessChallendIII)

> Normative specification. This document is the single shared dependency of the
> console, engine, and pipeline tracks. The keywords MUST, MUST NOT, SHALL, and
> MAY are to be interpreted as described in RFC 2119. Tests cite sections as
> `PROTOCOL §N`. After the freeze, changes require a new dated revision and a
> note in `PROVENANCE.md` (see §11).
>
> Frozen: 2026-10-26

License: GPL-3.0-or-later. See Copying.txt and NOTICE.

## 1. Scope and invariants

1.1. There is exactly one engine process per game. The console owns its lifecycle.

1.2. The engine speaks UCI on stdin/stdout. stdout MUST carry UCI tokens only.
     Every diagnostic MUST travel as `info string <text>` — never as a bare line.

1.3. Exactly one `go` MAY be outstanding at any time. The console MUST NOT send
     a second `go` before consuming the `bestmove` (or an error) of the first.

1.4. The console MUST NOT send `setoption` while a search is running.

1.5. A watchdog shutting the engine down MUST send `stop` first, consume the
     resulting `bestmove`, and only then send `quit`. Sending `quit` mid-search
     is a contract violation.

1.6. The physical board is the source of truth. On any disagreement between
     engine output and the board, the board wins and the software resynchronises.

## 2. Handshake and required options

2.1. Startup: console sends `uci`; engine replies `id name …`, `id author …`,
     the option list, then `uciok`. Console MUST treat absence of `uciok`
     within 10 seconds as a failed handshake.

2.2. Console sends `isready`; engine replies `readyok`. This is the only
     synchronisation point (see §10).

2.3. The console MUST set, before the first search:

| Option | Competition value | Rationale |
|---|---|---|
| `Threads` | physical cores (not SMT siblings) | latency over throughput |
| `Hash` | ≤ min(4096 MB, 50 % of RAM) | OOM mid-game loses the game |
| `SyzygyPath` | absolute local directory | Rule 14; §5 of PROVENANCE.md |
| `SyzygyProbeLimit` | 5 (engine-enforced ceiling) | Rule 4 |
| `Move Overhead` | 100 | operator-in-the-loop latency; upstream default 10 is unsafe here |
| `Ponder` | false | frozen off until TM-13 (Phase 5) |

2.4. `ucinewgame` MAY be sent between games only, never during one.

## 3. The `go` line — frozen literal

3.1. The console's search command MUST be exactly this literal, with `<int_ms>`
     replaced by non-negative integers:

```
go wtime <int_ms> btime <int_ms> winc 10000 binc 10000
```

3.2. The line MUST NOT contain `movetime`, `movestogo`, `depth`, `nodes`,
     `infinite`, or `searchmoves`. Any of these tokens in a `go` line is a
     contract violation: `movetime` bypasses the authored time manager
     (Rule 2 exposure), `movestogo` selects the wrong upstream time-management
     branch, and `depth`/`nodes`/`infinite`/`searchmoves` are not time-managed.

3.3. `wtime` and `btime` are the console's reserve-discounted belief of the
     remaining clock (TM-09 invariant), always ≥ 0, always integers in
     milliseconds. The engine never sees the raw clock.

3.4. Worked example at 15+10 with 798000/851000 ms believed remaining:

```
go wtime 798000 btime 851000 winc 10000 binc 10000
```

3.5. The ponder variant, sent only when `Ponder=true` (§8):

```
go ponder wtime <int_ms> btime <int_ms> winc 10000 binc 10000
```

## 4. Search lifecycle

4.1. Before every `go`, the console MUST send the position as
     `position startpos moves <uci> <uci> …` — always `startpos` plus the full
     move list. An incremental FEN MUST NOT be used: the full list is the
     replayable truth (Rule 10).

4.2. After `go`, the engine streams `info` lines and terminates the search with
     exactly one `bestmove` (§7).

4.3. `stop` mid-search produces exactly one `bestmove` for the interrupted
     search. It is a stale move only when a newer search has since been
     issued (§7.3).

## 5. `info` fields consumed

5.1. The console consumes exactly this token set:
     `depth seldepth multipv score {cp|mate <int>} [lowerbound|upperbound]
     nodes nps hashfull tbhits time pv`, plus `info string <rest>`.

5.2. `time` is **milliseconds on the wire**. (The `python-chess` client
     converts it to seconds; the Rule 9 log records `engine_ms` in
     milliseconds — LOGBOOK §2, field 8.)

5.3. `score` is **side-to-move POV**. The log records the STM-POV value
     verbatim, including any `lowerbound`/`upperbound` flag, and additionally
     a White-POV normalisation (LOGBOOK §2, field 6).

5.4. `pv` is a space-separated list of UCI moves. The console records it
     verbatim.

5.5. `bestmove (none)` handling is §7.2; `info string` payloads are §9.

## 6. The TM trace line — frozen grammar

6.1. When the authored time manager is active, every search MUST emit exactly
     one line with this grammar (TM-11; it supersedes the ARCHITECTURE.md
     draft shape):

```
info string tm=custom-v<MAJOR>.<MINOR> mode=<increment|sudden_death|armageddon> latency_p95_ms=<int> bank_ms=<int> budget_ms=<int> reason=<token>
```

6.2. `<token>` comes from the closed set:
     `reserve`, `bank_positive`, `low_clock`, `instant`, `book_exit`,
     `scramble`.

6.3. Ablation runs against upstream time management MUST emit the same shape
     with `tm=upstream` so logs parse identically:

```
info string tm=upstream mode=<increment|sudden_death|armageddon>
```

6.4. Phase 1 freezes the grammar and the token set; Phase 4 fills in the
     values. Consumers MUST treat an unknown `tm=` prefix or an unknown reason
     token as a parse failure, not a warning.

## 7. `bestmove` handling

7.1. `bestmove <uci> [ponder <uci>]` terminates exactly one search. The
     console MUST receive exactly one per `go`.

7.2. `bestmove (none)` is legal and means no move exists (stalemate or mate).
     It is logged (`src=none`, LOGBOOK §4) and the game ends per the rules.

7.3. A `bestmove` received while the console is not awaiting one is **stale**
     and MUST be discarded, keyed by a `search_id` the console assigns per
     `go`. The ANNOUNCE field of the spoken protocol is populated by the
     current search's `bestmove` only — never by a stale one.

7.4. The move announced to the operator comes from `bestmove` only.

## 8. Ponder rules

8.1. `go ponder …` (§3.5) is sent only when `Ponder=true`. Phase 1 freezes the
     grammar; the option is off until TM-13 (Phase 5).

8.2. On a ponder hit the console sends `ponderhit`; on a miss, `stop` and the
     resulting `bestmove` is discarded as stale (§7.3).

8.3. The engine's elapsed clock counts ponder time: a long ponder hit yields a
     near-instant move afterwards. The console's clock model MUST account for
     it.

## 9. Error and crash policy

9.1. `info string CRITICAL ERROR: …` is fatal: the upstream engine exits with
     code 1 after printing it (verified on an illegal `position`).

9.2. On engine crash or critical error mid-game, the console restarts the
     engine, replays `position startpos moves …` with the current line, and
     re-issues the `go`. Engine death is a restarted search, never a lost game.

9.3. Diagnostics other than `info string` on stdout (garbage lines) MUST be
     tolerated by the parser without state corruption; `tools/mock_engine.py
     --garbage` exists to test this.

## 10. Serialization and timing

10.1. One `go` outstanding (§1.3); `isready`/`readyok` is the only sync point
      (§2.2); no `setoption` mid-search (§1.4).

10.2. `ucinewgame` between games only (§2.4).

10.3. The console measures wall-clock per search independently of the engine's
      reported `time` (both are logged: `engine_ms` and `wall_ms`).

## 11. Versioning and change control

11.1. This document froze on 2026-10-26. The freeze commit touches only
      `docs/PROTOCOL.md` and `docs/LOGBOOK.md`; `tools/check_contract_order.py`
      proves it predates every implementation commit.

11.2. A change requires: a new dated revision header, a note in
      `PROVENANCE.md`, and re-running the contract tests. A change after
      implementation begins invalidates evidence produced under the old
      revision.

11.3. Nothing in this document describes console internals; it is the
      console↔engine boundary only.
