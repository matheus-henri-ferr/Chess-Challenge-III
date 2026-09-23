from boardgame.position import Position
from chess.chess_piece import ChessPiece
from chess.pieces.rook import Rook


class King(ChessPiece):

    def __init__(self, board, color, chess_match):
        super().__init__(board, color)
        self.chess_match = chess_match

    def __repr__(self):
        return "K"

    def _can_move(self, position) -> bool:
        p = self.board.piece(position)
        return p is None or p.color != self.color

    def _test_rook_castling(self, position) -> bool:
        p = self.board.piece(position)
        return p is not None and isinstance(p, Rook) and p.color == self.color and p.move_count == 0

    def possible_moves(self):
        mat = [[False] * self.board.columns for _ in range(self.board.rows)]

        for d_row, d_col in ((-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (-1, 1), (1, -1), (1, 1)):
            p = Position(self.position.row + d_row, self.position.column + d_col)
            if self.board.position_exists(p) and self._can_move(p):
                mat[p.row][p.column] = True

        # #specialmove castling
        if self.move_count == 0 and not self.chess_match.check:
            # #specialmove castling kingside rook
            pos_t1 = Position(self.position.row, self.position.column + 3)
            if self._test_rook_castling(pos_t1):
                p1 = Position(self.position.row, self.position.column + 1)
                p2 = Position(self.position.row, self.position.column + 2)
                if self.board.piece(p1) is None and self.board.piece(p2) is None:
                    mat[self.position.row][self.position.column + 2] = True

            # #specialmove castling queenside rook
            pos_t2 = Position(self.position.row, self.position.column - 4)
            if self._test_rook_castling(pos_t2):
                p1 = Position(self.position.row, self.position.column - 1)
                p2 = Position(self.position.row, self.position.column - 2)
                p3 = Position(self.position.row, self.position.column - 3)
                if self.board.piece(p1) is None and self.board.piece(p2) is None and self.board.piece(p3) is None:
                    mat[self.position.row][self.position.column - 2] = True

        return mat
