"""Partida fisica: Stockfish 19 com a gestao de tempo da equipe (stockfish_tm.exe).

Uso:
  python partida.py white partida-01.log
  python partida.py black partida-02.log
  python partida.py white partida-01.log --retomar   # continua apos queda do programa
"""
import argparse
import os
import pathlib
import re
import sys
import time

import chess
import chess.engine

ROOT = pathlib.Path(__file__).resolve().parent
HEADER = "lance\tcor\tuci\tprofundidade\tnos\tavaliacao_brancas\tpv\ttempo_ms\torigem"


def score_text(info):
    score = info.get("score")
    if score is None:
        return "?"
    white = score.white()
    if white.is_mate():
        return f"#{white.mate()}"
    return f"{white.score() / 100:+.2f}"


def pv_text(info):
    return " ".join(m.uci() for m in info.get("pv", [])) or "-"


def board_text(board, pov):
    ranks = range(7, -1, -1) if pov == chess.WHITE else range(8)
    files = list(range(8)) if pov == chess.WHITE else list(range(7, -1, -1))
    lines = []
    for r in ranks:
        cells = []
        for f in files:
            piece = board.piece_at(chess.square(f, r))
            cells.append(piece.symbol() if piece else ".")
        lines.append(f"{r + 1}  " + " ".join(cells))
    lines.append("   " + " ".join("abcdefgh"[f] for f in files))
    return "\n".join(lines)


def parse_move(board, text):
    try:
        move = chess.Move.from_uci(text.strip().lower())
    except ValueError:
        return None, "Formato invalido. Use UCI, ex.: e2e4, g1f3, e7e8q."
    if move in board.legal_moves:
        return move, None
    if move.promotion is None and chess.Move(move.from_square, move.to_square, chess.QUEEN) in board.legal_moves:
        return None, "Promocao precisa da peca no final: e7e8q (q, r, b ou n)."
    return None, "Lance ilegal nesta posicao. Confira o tabuleiro fisico."


def ask(prompt):
    try:
        return input(prompt).strip()
    except EOFError:
        return "sair"


def check_syzygy(path):
    folder = pathlib.Path(path)
    files = [p for p in folder.iterdir() if p.suffix.lower() in (".rtbw", ".rtbz")]
    if not files:
        sys.exit(f"Nenhuma tablebase Syzygy em {folder}.")
    too_big = [p.name for p in files if len(re.sub(r"[^KQRBNP]", "", p.stem.upper())) > 5]
    if too_big:
        sys.exit("Regulamento: tablebases so ate 5 pecas. Remova: " + ", ".join(sorted(too_big)[:10]))


class Log:
    def __init__(self, path, resume):
        self.path = pathlib.Path(path)
        self.entries = []
        if resume:
            if not self.path.exists():
                sys.exit(f"{self.path} nao existe; nada para retomar.")
            for line in self.path.read_text(encoding="utf-8").splitlines()[1:]:
                if line.strip():
                    self.entries.append(line)
        elif self.path.exists() and self.path.stat().st_size > 0:
            sys.exit(f"{self.path} ja existe. Use outro nome, ou --retomar para continuar essa partida.")
        self.write()

    def moves(self):
        return [line.split("\t")[2] for line in self.entries]

    def add(self, board, move, info, elapsed_ms, origin):
        color = "brancas" if board.turn == chess.WHITE else "pretas"
        fields = [board.fullmove_number, color, move.uci(), info.get("depth", 0), info.get("nodes", 0),
                  score_text(info), pv_text(info), elapsed_ms, origin]
        self.entries.append("\t".join(str(f) for f in fields))
        self.write()

    def pop(self):
        self.entries.pop()
        self.write()

    def write(self):
        tmp = self.path.with_name(self.path.name + ".tmp")
        with open(tmp, "w", encoding="utf-8", newline="\n") as f:
            f.write(HEADER + "\n")
            for line in self.entries:
                f.write(line + "\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, self.path)


def flush_typeahead():
    # Text typed during the search must not be taken as the confirmation.
    if os.name == "nt" and sys.stdin.isatty():
        import msvcrt
        while msvcrt.kbhit():
            msvcrt.getwch()


def parse_clock(text):
    text = text.replace(",", ".")
    try:
        if ":" in text:
            minutes, seconds = text.split(":", 1)
            value = int(minutes) * 60 + float(seconds)
        else:
            value = float(text)
    except ValueError:
        return None
    return value if 0 < value <= 3600 else None


def read_clock(estimate):
    """Returns our remaining clock in ms, or a command string."""
    while True:
        current = estimate()
        hint = f" [Enter = estimativa {current / 1000:.0f}s]" if current is not None else ""
        text = ask(f"Tempo RESTANTE do NOSSO relogio (s ou mm:ss){hint}: ")
        if text in ("sair", "tabuleiro", "desfazer"):
            return text
        if not text:
            current = estimate()
            if current is not None:
                return current
            print("Sem estimativa: leia o relogio fisico e digite o tempo.")
            continue
        seconds = parse_clock(text)
        if seconds is not None:
            return int(seconds * 1000)
        print("Tempo invalido. Exemplos: 812, 812.5, 13:32.")


def our_score(info, color):
    score = info.get("score")
    if score is None:
        return "?"
    pov = score.pov(color)
    return f"mate em {pov.mate()}" if pov.is_mate() else f"{pov.score() / 100:+.2f}"


def open_engine(args):
    exe = pathlib.Path(args.motor)
    if not exe.exists():
        sys.exit(f"Motor nao encontrado: {exe}")
    options = {"Threads": args.threads, "Hash": args.hash, "Move Overhead": args.overhead}
    if args.syzygy:
        check_syzygy(args.syzygy)
        options["SyzygyPath"] = args.syzygy
    engine = chess.engine.SimpleEngine.popen_uci(str(exe))
    try:
        engine.configure(options)
    except chess.engine.EngineError as error:
        engine.quit()
        sys.exit(f"Opcao recusada pelo motor: {error}")
    return engine


def main():
    parser = argparse.ArgumentParser(description="Partida fisica com stockfish_tm.exe")
    parser.add_argument("cor", choices=["white", "black"], help="cor do NOSSO motor")
    parser.add_argument("log", help="arquivo .log desta partida")
    parser.add_argument("--retomar", action="store_true", help="continua a partida gravada no log")
    parser.add_argument("--motor", default=str(ROOT / "stockfish_tm.exe"))
    parser.add_argument("--threads", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    parser.add_argument("--hash", type=int, default=2048, help="MB")
    parser.add_argument("--overhead", type=int, default=6000, help="ms perdidos por lance fora da busca")
    parser.add_argument("--syzygy", help="pasta com tablebases Syzygy de ate 5 pecas")
    parser.add_argument("--tempo-inicial", type=float, default=900, help="segundos (Armageddon: 300 ou 240)")
    parser.add_argument("--incremento", type=float, default=10, help="segundos por lance (Armageddon: 0)")
    args = parser.parse_args()

    log = Log(args.log, args.retomar)
    board = chess.Board()
    for uci in log.moves():
        move = chess.Move.from_uci(uci)
        if move not in board.legal_moves:
            sys.exit(f"Log invalido: lance {uci} ilegal na posicao reconstruida.")
        board.push(move)

    ours = chess.WHITE if args.cor == "white" else chess.BLACK
    inc_ms = int(args.incremento * 1000)
    # Our clock estimate: value at the moment our clock started running.
    clock_ms = None if args.retomar else int(args.tempo_inicial * 1000)
    clock_started = time.monotonic()

    def estimate():
        if clock_ms is None:
            return None
        return max(1000, clock_ms - int((time.monotonic() - clock_started) * 1000))

    engine = open_engine(args)
    game_id = object()
    print(f"Motor: {pathlib.Path(args.motor).name}  threads={args.threads} hash={args.hash}MB "
          f"overhead={args.overhead}ms  relogio={args.tempo_inicial:g}+{args.incremento:g}")
    print(f"Nosso motor joga de {'BRANCAS' if ours == chess.WHITE else 'PRETAS'}. Log: {log.path}")
    print("Comandos em qualquer prompt: tabuleiro, desfazer, sair. Lances sempre em UCI (e2e4, e7e8q).")
    print(board_text(board, ours))

    try:
        while True:
            outcome = board.outcome(claim_draw=True)
            if outcome:
                print(f"FIM: {outcome.termination.name} - resultado {outcome.result()}. Confirme com o arbitro.")
                break

            if board.turn == ours:
                answer = read_clock(estimate)
                if answer == "sair":
                    break
                if answer == "tabuleiro":
                    print(board_text(board, ours))
                    continue
                if answer == "desfazer":
                    if not log.entries:
                        print("Nada para desfazer.")
                        continue
                    board.pop()
                    log.pop()
                    clock_ms = None
                    print("Ultimo meio-lance removido do estado e do log. Confira o tabuleiro fisico.")
                    print(board_text(board, ours))
                    continue

                my_ms = answer
                clock_read = time.monotonic()
                limit = chess.engine.Limit(white_clock=my_ms / 1000, black_clock=my_ms / 1000,
                                           white_inc=inc_ms / 1000, black_inc=inc_ms / 1000)
                print(f"Pensando (relogio {my_ms / 1000:.1f}s)...")
                t0 = time.monotonic()
                result = engine.play(board, limit, info=chess.engine.INFO_ALL, game=game_id)
                elapsed_ms = int((time.monotonic() - t0) * 1000)
                info = result.info
                flush_typeahead()
                print(f"\n>>> ANUNCIE: {result.move.uci()} <<<   pensou {elapsed_ms / 1000:.1f}s, prof {info.get('depth', '?')}\n")

                played, origin = None, "motor"
                while played is None:
                    text = ask("Apos anuncio, repeticao, peca movida e relogio apertado: Enter ou ok. "
                               "Se o lance fisico foi outro, digite-o em UCI: ").lower()
                    if text in ("", "ok"):
                        played = result.move
                    elif text == "sair":
                        return
                    elif text == "tabuleiro":
                        print(board_text(board, ours))
                    else:
                        move, error = parse_move(board, text)
                        if error:
                            print(error)
                        elif move == result.move:
                            played = move
                        else:
                            played, origin = move, f"manual(sugerido={result.move.uci()})"
                log.add(board, played, info, elapsed_ms, origin)
                board.push(played)
                clock_ms = my_ms - int((time.monotonic() - clock_read) * 1000) + inc_ms
                print(board_text(board, ours))
                continue

            # Opponent's turn: our engine keeps thinking on this position (rule 13).
            analysis = engine.analysis(board, game=game_id)
            t0 = time.monotonic()
            action = None
            while action is None:
                text = ask("Lance do ADVERSARIO em UCI (apos repeticao e peca no tabuleiro), ou comando: ").lower()
                if text in ("sair", "desfazer"):
                    action = text
                elif text == "tabuleiro":
                    print(board_text(board, ours))
                elif text:
                    move, error = parse_move(board, text)
                    if error:
                        print(error)
                    else:
                        action = move
            analysis.stop()
            info = dict(analysis.info)
            analysis.wait()
            if action == "sair":
                break
            if action == "desfazer":
                if not log.entries:
                    print("Nada para desfazer.")
                else:
                    board.pop()
                    log.pop()
                    clock_ms = None
                    print("Ultimo meio-lance removido do estado e do log. Confira o tabuleiro fisico.")
                    print(board_text(board, ours))
                continue
            predicted = info.get("pv") or []
            origin = "adversario"
            if predicted and predicted[0] == action:
                origin = "adversario(previsto)"
            else:
                if predicted:
                    origin = f"adversario(previsto={predicted[0].uci()})"
                info["pv"] = [action]
            log.add(board, action, info, int((time.monotonic() - t0) * 1000), origin)
            board.push(action)
            # Our clock started when the opponent pressed theirs, shortly before this entry.
            clock_started = time.monotonic() - 2.0
            print(board_text(board, ours))
    finally:
        engine.quit()


if __name__ == "__main__":
    main()
