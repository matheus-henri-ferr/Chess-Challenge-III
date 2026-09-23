from application import ui
from chess.chess_exception import ChessException
from chess.chess_match import ChessMatch


def main():
    chess_match = ChessMatch()
    captured = []

    while not chess_match.check_mate:
        try:
            ui.clear_screen()
            ui.print_match(chess_match, captured)
            print()
            print("Source: ", end="")
            source = ui.read_chess_position()

            possible_moves = chess_match.possible_moves(source)
            ui.clear_screen()
            ui.print_board(chess_match.get_pieces(), possible_moves)
            print()
            print("Target: ", end="")
            target = ui.read_chess_position()

            captured_piece = chess_match.perform_chess_move(source, target)

            if captured_piece is not None:
                captured.append(captured_piece)

            if chess_match.promoted is not None:
                print("Enter piece for promotion (B/N/R/Q): ", end="")
                type_letter = input().upper()
                while type_letter not in ("B", "N", "R", "Q"):
                    print("Invalid value! Enter piece for promotion (B/N/R/Q): ", end="")
                    type_letter = input().upper()
                chess_match.replace_promoted_piece(type_letter)
        except (ChessException, ValueError) as e:
            print(e)
            input()

    ui.clear_screen()
    ui.print_match(chess_match, captured)


if __name__ == "__main__":
    main()
