from boardgame.position import Position
from chess.chess_exception import ChessException


class ChessPosition:

    def __init__(self, column: str, row: int):
        if column < 'a' or column > 'h' or row < 1 or row > 8:
            raise ChessException("Error instantiating ChessPosition. Valid values are from a1 to h8.")
        self.column = column
        self.row = row

    def to_position(self) -> Position:
        return Position(8 - self.row, ord(self.column) - ord('a'))

    @staticmethod
    def from_position(position: Position) -> "ChessPosition":
        return ChessPosition(chr(ord('a') + position.column), 8 - position.row)

    def __repr__(self):
        return f"{self.column}{self.row}"
