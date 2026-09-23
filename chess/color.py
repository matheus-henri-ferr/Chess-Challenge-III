from enum import Enum


class Color(Enum):
    BLACK = "BLACK"
    WHITE = "WHITE"

    def __str__(self):
        return self.name
