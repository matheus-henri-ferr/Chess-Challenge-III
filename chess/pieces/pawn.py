from boardgame.position import Position
from chess.chess_piece import ChessPiece
from chess.color import Color


class Pawn(ChessPiece):

    def __init__(self, board, color, chess_match):
        super().__init__(board, color)
        self.chess_match = chess_match

    def __repr__(self):
        return "P"

    def possible_moves(self):
        mat = [[False] * self.board.columns for _ in range(self.board.rows)]

        p = Position(0, 0)
        forward = -1 if self.color == Color.WHITE else 1
        start_row = 3 if self.color == Color.WHITE else 4

        p.set_values(self.position.row + forward, self.position.column)
        if self.board.position_exists(p) and not self.board.there_is_a_piece(p):
            mat[p.row][p.column] = True

        p.set_values(self.position.row + 2 * forward, self.position.column)
        p2 = Position(self.position.row + forward, self.position.column)
        if (self.board.position_exists(p) and not self.board.there_is_a_piece(p)
                and self.board.position_exists(p2) and not self.board.there_is_a_piece(p2)
                and self.move_count == 0):
            mat[p.row][p.column] = True

        p.set_values(self.position.row + forward, self.position.column - 1)
        if self.board.position_exists(p) and self.is_there_opponent_piece(p):
            mat[p.row][p.column] = True

        p.set_values(self.position.row + forward, self.position.column + 1)
        if self.board.position_exists(p) and self.is_there_opponent_piece(p):
            mat[p.row][p.column] = True

        # #specialmove en passant
        if self.position.row == start_row:
            left = Position(self.position.row, self.position.column - 1)
            if (self.board.position_exists(left) and self.is_there_opponent_piece(left)
                    and self.board.piece(left) is self.chess_match.en_passant_vulnerable):
                mat[left.row + forward][left.column] = True

            right = Position(self.position.row, self.position.column + 1)
            if (self.board.position_exists(right) and self.is_there_opponent_piece(right)
                    and self.board.piece(right) is self.chess_match.en_passant_vulnerable):
                mat[right.row + forward][right.column] = True

        return mat
