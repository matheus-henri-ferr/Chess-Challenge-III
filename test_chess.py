from chess.chess_match import ChessMatch
from chess.chess_position import ChessPosition
from chess.color import Color
from chess.pieces.pawn import Pawn
from chess.pieces.queen import Queen


def pos(s):
    return ChessPosition(s[0], int(s[1]))


def test_initial_setup():
    match = ChessMatch()
    pieces = match.get_pieces()
    assert isinstance(pieces[1][0], Pawn)  # a7, black
    assert pieces[1][0].color == Color.BLACK
    assert isinstance(pieces[6][0], Pawn)  # a2, white
    assert pieces[6][0].color == Color.WHITE
    assert pieces[4][0] is None


def test_pawn_move_and_turn_switch():
    match = ChessMatch()
    match.perform_chess_move(pos("e2"), pos("e4"))
    assert match.current_player == Color.BLACK
    assert match.turn == 2
    assert match.get_pieces()[4][4] is not None


def test_capture():
    match = ChessMatch()
    match.perform_chess_move(pos("e2"), pos("e4"))
    match.perform_chess_move(pos("d7"), pos("d5"))
    captured = match.perform_chess_move(pos("e4"), pos("d5"))
    assert captured is not None
    assert len(match.captured_pieces) == 1


def test_cannot_move_into_check():
    match = ChessMatch()
    try:
        match.perform_chess_move(pos("e1"), pos("e2"))
        assert False, "expected ChessException"
    except Exception as e:
        assert "possible moves" in str(e)


def test_en_passant():
    match = ChessMatch()
    match.perform_chess_move(pos("e2"), pos("e4"))
    match.perform_chess_move(pos("a7"), pos("a6"))
    match.perform_chess_move(pos("e4"), pos("e5"))
    match.perform_chess_move(pos("d7"), pos("d5"))
    assert match.en_passant_vulnerable is not None
    captured = match.perform_chess_move(pos("e5"), pos("d6"))
    assert captured is not None
    assert match.get_pieces()[3][3] is None


def test_castling_kingside():
    match = ChessMatch()
    match.perform_chess_move(pos("g1"), pos("f3"))
    match.perform_chess_move(pos("a7"), pos("a6"))
    match.perform_chess_move(pos("g2"), pos("g3"))
    match.perform_chess_move(pos("a6"), pos("a5"))
    match.perform_chess_move(pos("f1"), pos("g2"))
    match.perform_chess_move(pos("a5"), pos("a4"))
    match.perform_chess_move(pos("e1"), pos("g1"))
    pieces = match.get_pieces()
    assert pieces[7][6] is not None  # king on g1
    assert pieces[7][5] is not None  # rook on f1


def test_promotion():
    match = ChessMatch()
    for src, dst in [("a2", "a4"), ("h7", "h6"), ("a4", "a5"), ("h6", "h5"),
                      ("a5", "a6"), ("g7", "g6"), ("a6", "b7"), ("g6", "g5")]:
        match.perform_chess_move(pos(src), pos(dst))
    match.perform_chess_move(pos("b7"), pos("a8"))
    assert match.promoted is not None
    assert isinstance(match.get_pieces()[0][0], Queen)


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print(f"OK  {t.__name__}")
    print(f"\n{len(tests)} tests passed")
