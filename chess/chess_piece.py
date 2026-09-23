from abc import ABC

from boardgame.piece import Piece
from chess.chess_position import ChessPosition


class ChessPiece(Piece, ABC):

    def __init__(self, board, color):
        super().__init__(board)
        self.color = color
        self.move_count = 0

    def increase_move_count(self):
        self.move_count += 1

    def decrease_move_count(self):
        self.move_count -= 1

    def get_chess_position(self) -> ChessPosition:
        return ChessPosition.from_position(self.position)

    def is_there_opponent_piece(self, position) -> bool:
        p = self.board.piece(position)
        return p is not None and p.color != self.color
