from boardgame.board import Board
from boardgame.position import Position
from chess.chess_exception import ChessException
from chess.chess_position import ChessPosition
from chess.color import Color
from chess.pieces.bishop import Bishop
from chess.pieces.king import King
from chess.pieces.knight import Knight
from chess.pieces.pawn import Pawn
from chess.pieces.queen import Queen
from chess.pieces.rook import Rook


class ChessMatch:

    def __init__(self):
        self.board = Board(8, 8)
        self.turn = 1
        self.current_player = Color.WHITE
        self.check = False
        self.check_mate = False
        self.en_passant_vulnerable = None
        self.promoted = None

        self.pieces_on_the_board = []
        self.captured_pieces = []

        self._initial_setup()

    def get_pieces(self):
        mat = [[None] * self.board.columns for _ in range(self.board.rows)]
        for i in range(self.board.rows):
            for j in range(self.board.columns):
                mat[i][j] = self.board.piece(i, j)
        return mat

    def possible_moves(self, source_position: ChessPosition):
        position = source_position.to_position()
        self._validate_source_position(position)
        return self.board.piece(position).possible_moves()

    def perform_chess_move(self, source_position: ChessPosition, target_position: ChessPosition):
        source = source_position.to_position()
        target = target_position.to_position()
        self._validate_source_position(source)
        self._validate_target_position(source, target)
        captured_piece = self._make_move(source, target)

        if self._test_check(self.current_player):
            self.undo_move(source, target, captured_piece)
            raise ChessException("You can't put yourself in check")

        moved_piece = self.board.piece(target)

        # #specialmove promotion
        self.promoted = None
        if isinstance(moved_piece, Pawn):
            if ((moved_piece.color == Color.WHITE and target.row == 0)
                    or (moved_piece.color == Color.BLACK and target.row == 7)):
                self.promoted = self.board.piece(target)
                self.promoted = self.replace_promoted_piece("Q")

        self.check = self._test_check(self._opponent(self.current_player))

        if self._test_check_mate(self._opponent(self.current_player)):
            self.check_mate = True
        else:
            self._next_turn()

        # #specialmove en passant
        if isinstance(moved_piece, Pawn) and (target.row == source.row - 2 or target.row == source.row + 2):
            self.en_passant_vulnerable = moved_piece
        else:
            self.en_passant_vulnerable = None

        return captured_piece

    def _validate_source_position(self, position: Position):
        if not self.board.there_is_a_piece(position):
            raise ChessException("There is no piece on the source position")
        if self.current_player != self.board.piece(position).color:
            raise ChessException("The chosen piece is not yours")
        if not self.board.piece(position).is_there_any_possible_move():
            raise ChessException("There is no possible moves for the chosen piece")

    def _validate_target_position(self, source: Position, target: Position):
        if not self.board.piece(source).possible_move(target):
            raise ChessException("The chosen piece can't move to target position")

    def _next_turn(self):
        self.turn += 1
        self.current_player = Color.BLACK if self.current_player == Color.WHITE else Color.WHITE

    def replace_promoted_piece(self, type_letter: str):
        if self.promoted is None:
            raise ValueError("There is no piece to be promoted")
        if type_letter not in ("B", "N", "R", "Q"):
            return self.promoted

        pos = self.promoted.get_chess_position().to_position()
        p = self.board.remove_piece(pos)
        self.pieces_on_the_board.remove(p)

        new_piece = self._new_piece(type_letter, self.promoted.color)
        self.board.place_piece(new_piece, pos)
        self.pieces_on_the_board.append(new_piece)

        return new_piece

    def _new_piece(self, type_letter: str, color: Color):
        if type_letter == "B":
            return Bishop(self.board, color)
        if type_letter == "N":
            return Knight(self.board, color)
        if type_letter == "Q":
            return Queen(self.board, color)
        return Rook(self.board, color)

    def _make_move(self, source: Position, target: Position):
        p = self.board.remove_piece(source)
        p.increase_move_count()
        captured_piece = self.board.remove_piece(target)
        self.board.place_piece(p, target)

        if captured_piece is not None:
            self.pieces_on_the_board.remove(captured_piece)
            self.captured_pieces.append(captured_piece)

        # #specialmove castling kingside rook
        if isinstance(p, King) and target.column == source.column + 2:
            source_t = Position(source.row, source.column + 3)
            target_t = Position(source.row, source.column + 1)
            rook = self.board.remove_piece(source_t)
            self.board.place_piece(rook, target_t)
            rook.increase_move_count()

        # #specialmove castling queenside rook
        if isinstance(p, King) and target.column == source.column - 2:
            source_t = Position(source.row, source.column - 4)
            target_t = Position(source.row, source.column - 1)
            rook = self.board.remove_piece(source_t)
            self.board.place_piece(rook, target_t)
            rook.increase_move_count()

        # #specialmove en passant
        if isinstance(p, Pawn):
            if source.column != target.column and captured_piece is None:
                if p.color == Color.WHITE:
                    pawn_position = Position(target.row + 1, target.column)
                else:
                    pawn_position = Position(target.row - 1, target.column)
                captured_piece = self.board.remove_piece(pawn_position)
                self.captured_pieces.append(captured_piece)
                self.pieces_on_the_board.remove(captured_piece)

        return captured_piece

    def undo_move(self, source: Position, target: Position, captured_piece):
        p = self.board.remove_piece(target)
        p.decrease_move_count()
        self.board.place_piece(p, source)

        if captured_piece is not None:
            self.board.place_piece(captured_piece, target)
            self.captured_pieces.remove(captured_piece)
            self.pieces_on_the_board.append(captured_piece)

        # #specialmove castling kingside rook
        if isinstance(p, King) and target.column == source.column + 2:
            source_t = Position(source.row, source.column + 3)
            target_t = Position(source.row, source.column + 1)
            rook = self.board.remove_piece(target_t)
            self.board.place_piece(rook, source_t)
            rook.decrease_move_count()

        # #specialmove castling queenside rook
        if isinstance(p, King) and target.column == source.column - 2:
            source_t = Position(source.row, source.column - 4)
            target_t = Position(source.row, source.column - 1)
            rook = self.board.remove_piece(target_t)
            self.board.place_piece(rook, source_t)
            rook.decrease_move_count()

        # #specialmove en passant
        if isinstance(p, Pawn):
            if source.column != target.column and captured_piece is self.en_passant_vulnerable:
                pawn = self.board.remove_piece(target)
                pawn_position = Position(3, target.column) if p.color == Color.WHITE else Position(4, target.column)
                self.board.place_piece(pawn, pawn_position)

    def _opponent(self, color: Color) -> Color:
        return Color.BLACK if color == Color.WHITE else Color.WHITE

    def _king(self, color: Color):
        for p in self.pieces_on_the_board:
            if p.color == color and isinstance(p, King):
                return p
        raise RuntimeError(f"There is no {color} king on the board")

    def _test_check(self, color: Color) -> bool:
        king_position = self._king(color).get_chess_position().to_position()
        opponent_pieces = [p for p in self.pieces_on_the_board if p.color == self._opponent(color)]
        for p in opponent_pieces:
            mat = p.possible_moves()
            if mat[king_position.row][king_position.column]:
                return True
        return False

    def _test_check_mate(self, color: Color) -> bool:
        if not self._test_check(color):
            return False
        pieces = [p for p in self.pieces_on_the_board if p.color == color]
        for p in pieces:
            mat = p.possible_moves()
            for i in range(self.board.rows):
                for j in range(self.board.columns):
                    if mat[i][j]:
                        source = p.get_chess_position().to_position()
                        target = Position(i, j)
                        captured_piece = self._make_move(source, target)
                        test_check = self._test_check(color)
                        self.undo_move(source, target, captured_piece)
                        if not test_check:
                            return False
        return True

    def _place_new_piece(self, column: str, row: int, piece):
        self.board.place_piece(piece, ChessPosition(column, row).to_position())
        self.pieces_on_the_board.append(piece)

    def _initial_setup(self):
        self._place_new_piece('a', 1, Rook(self.board, Color.WHITE))
        self._place_new_piece('b', 1, Knight(self.board, Color.WHITE))
        self._place_new_piece('c', 1, Bishop(self.board, Color.WHITE))
        self._place_new_piece('d', 1, Queen(self.board, Color.WHITE))
        self._place_new_piece('e', 1, King(self.board, Color.WHITE, self))
        self._place_new_piece('f', 1, Bishop(self.board, Color.WHITE))
        self._place_new_piece('g', 1, Knight(self.board, Color.WHITE))
        self._place_new_piece('h', 1, Rook(self.board, Color.WHITE))
        for column in "abcdefgh":
            self._place_new_piece(column, 2, Pawn(self.board, Color.WHITE, self))

        self._place_new_piece('a', 8, Rook(self.board, Color.BLACK))
        self._place_new_piece('b', 8, Knight(self.board, Color.BLACK))
        self._place_new_piece('c', 8, Bishop(self.board, Color.BLACK))
        self._place_new_piece('d', 8, Queen(self.board, Color.BLACK))
        self._place_new_piece('e', 8, King(self.board, Color.BLACK, self))
        self._place_new_piece('f', 8, Bishop(self.board, Color.BLACK))
        self._place_new_piece('g', 8, Knight(self.board, Color.BLACK))
        self._place_new_piece('h', 8, Rook(self.board, Color.BLACK))
        for column in "abcdefgh":
            self._place_new_piece(column, 7, Pawn(self.board, Color.BLACK, self))
