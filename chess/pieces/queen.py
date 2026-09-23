from boardgame.position import Position
from chess.chess_piece import ChessPiece


class Queen(ChessPiece):

    def __repr__(self):
        return "Q"

    def possible_moves(self):
        mat = [[False] * self.board.columns for _ in range(self.board.rows)]

        p = Position(0, 0)

        directions = ((-1, 0), (0, -1), (0, 1), (1, 0), (-1, -1), (-1, 1), (1, 1), (1, -1))
        for d_row, d_col in directions:
            p.set_values(self.position.row + d_row, self.position.column + d_col)
            while self.board.position_exists(p) and not self.board.there_is_a_piece(p):
                mat[p.row][p.column] = True
                p.set_values(p.row + d_row, p.column + d_col)
            if self.board.position_exists(p) and self.is_there_opponent_piece(p):
                mat[p.row][p.column] = True

        return mat
