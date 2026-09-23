from chess.chess_exception import ChessException
from chess.chess_match import ChessMatch
from chess.chess_position import ChessPosition
from chess.color import Color

# https://stackoverflow.com/questions/5762491/how-to-print-color-in-console-using-system-out-println
ANSI_RESET = "[0m"
ANSI_WHITE = "[37m"
ANSI_YELLOW = "[33m"
ANSI_BLUE_BACKGROUND = "[44m"


def clear_screen():
    print("\033[H\033[2J", end="")


def read_chess_position(input_fn=input) -> ChessPosition:
    try:
        s = input_fn()
        column = s[0]
        row = int(s[1:])
        return ChessPosition(column, row)
    except (ChessException, ValueError, IndexError):
        raise ValueError("Error reading ChessPosition. Valid values are from a1 to h8.")


def print_match(chess_match: ChessMatch, captured):
    print_board(chess_match.get_pieces())
    print()
    print_captured_pieces(captured)
    print()
    print(f"Turn : {chess_match.turn}")
    if not chess_match.check_mate:
        print(f"Waiting player: {chess_match.current_player}")
        if chess_match.check:
            print("CHECK!")
    else:
        print("CHECKMATE!")
        print(f"Winner: {chess_match.current_player}")


def print_board(pieces, possible_moves=None):
    for i, row in enumerate(pieces):
        print(8 - i, end=" ")
        for j, piece in enumerate(row):
            background = possible_moves[i][j] if possible_moves else False
            _print_piece(piece, background)
        print()
    print("  a b c d e f g h")


def _print_piece(piece, background: bool):
    if background:
        print(ANSI_BLUE_BACKGROUND, end="")
    if piece is None:
        print(f"-{ANSI_RESET}", end="")
    else:
        color = ANSI_WHITE if piece.color == Color.WHITE else ANSI_YELLOW
        print(f"{color}{piece}{ANSI_RESET}", end="")
    print(" ", end="")


def print_captured_pieces(captured):
    white = [p for p in captured if p.color == Color.WHITE]
    black = [p for p in captured if p.color == Color.BLACK]
    print("Captured pieces:")
    print("White: ", end="")
    print(ANSI_WHITE, end="")
    print("[" + ", ".join(str(p) for p in white) + "]")
    print(ANSI_RESET, end="")
    print("Black: ", end="")
    print(ANSI_YELLOW, end="")
    print("[" + ", ".join(str(p) for p in black) + "]")
    print(ANSI_RESET, end="")
    print()
