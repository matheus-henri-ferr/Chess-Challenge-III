from abc import ABC, abstractmethod


class Piece(ABC):

    def __init__(self, board):
        self.board = board
        self.position = None

    @abstractmethod
    def possible_moves(self):
        ...

    def possible_move(self, position):
        return self.possible_moves()[position.row][position.column]

    def is_there_any_possible_move(self):
        return any(any(row) for row in self.possible_moves())
