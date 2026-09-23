from boardgame.position import Position
from chess.chess_piece import ChessPiece


class Knight(ChessPiece):

    def __repr__(self):
        return "N"

    def _can_move(self, position) -> bool:
        p = self.board.piece(position)
        return p is None or p.color != self.color

    def possible_moves(self):
        mat = [[False] * self.board.columns for _ in range(self.board.rows)]

        offsets = ((-1, -2), (-2, -1), (-2, 1), (-1, 2), (1, 2), (2, 1), (2, -1), (1, -2))
        for d_row, d_col in offsets:
            p = Position(self.position.row + d_row, self.position.column + d_col)
            if self.board.position_exists(p) and self._can_move(p):
                mat[p.row][p.column] = True

        return mat
