"""Self-play with simulated relay delays charged to the clock (scaled 15+10 -> 90+1).

Uso: python tests/sim_relay.py MOTOR_A MOTOR_B [jogos] [overhead_ms]
"""
import concurrent.futures
import pathlib
import random
import sys
import time

import chess
import chess.engine

ROOT = pathlib.Path(__file__).resolve().parents[1]
OPENINGS = ROOT / "tools" / "fastchess-windows-x86-64" / "app" / "tests" / "data" / "openings.epd"
BASE, INC = 90.0, 1.0


def play(game, exes, overhead, fen):
    rng = random.Random(game)
    white_first = game % 2 == 0
    order = (0, 1) if white_first else (1, 0)
    engines = [chess.engine.SimpleEngine.popen_uci(str(exes[i])) for i in order]
    for e in engines:
        e.configure({"Threads": 1, "Hash": 64, "Move Overhead": overhead})
    board = chess.Board(fen)
    clock = [BASE, BASE]
    low = [BASE, BASE]
    result = None
    try:
        while result is None:
            side = 0 if board.turn == chess.WHITE else 1
            pre, post = rng.uniform(0.2, 0.6), rng.uniform(0.2, 0.5)
            reading = clock[side] - pre
            if reading <= 0:
                result = "flag"
                break
            other = clock[1 - side]
            limit = chess.engine.Limit(
                white_clock=reading if side == 0 else other, black_clock=reading if side == 1 else other,
                white_inc=INC, black_inc=INC)
            t = time.monotonic()
            move = engines[side].play(board, limit).move
            clock[side] -= pre + (time.monotonic() - t) + post
            low[side] = min(low[side], clock[side])
            if clock[side] <= 0:
                result = "flag"
                break
            clock[side] += INC
            board.push(move)
            outcome = board.outcome(claim_draw=True)
            if outcome:
                result = outcome.result()
            elif board.ply() >= 300:
                result = "1/2-1/2"
    finally:
        for e in engines:
            e.quit()
    names = [exes[i].stem for i in order]
    loser = names[0 if board.turn == chess.WHITE else 1] if result == "flag" else "-"
    return (f"jogo {game}: {names[0]}(B) x {names[1]}(P) -> {result} perdeu_por_tempo={loser} "
            f"lances={board.fullmove_number} min_relogio B={low[0]:.1f}s P={low[1]:.1f}s")


def main():
    exes = [ROOT / sys.argv[1], ROOT / sys.argv[2]]
    games = int(sys.argv[3]) if len(sys.argv) > 3 else 8
    overhead = int(sys.argv[4]) if len(sys.argv) > 4 else 800
    fens = [l.strip() for l in OPENINGS.read_text().splitlines() if l.strip()]
    with concurrent.futures.ThreadPoolExecutor(4) as pool:
        jobs = [pool.submit(play, g, exes, overhead, fens[g // 2]) for g in range(games)]
        for j in jobs:
            print(j.result(), flush=True)


if __name__ == "__main__":
    main()
