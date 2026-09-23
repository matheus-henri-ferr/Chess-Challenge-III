from boardgame.board_exception import BoardException


class Board:

    def __init__(self, rows: int, columns: int):
        if rows < 1 or columns < 1:
            raise BoardException("Error creating board: there must be at least 1 row and 1 column")
        self.rows = rows
        self.columns = columns
        self._pieces = [[None] * columns for _ in range(rows)]

    def piece(self, row, column=None):
        if column is None:
            position = row
            if not self.position_exists(position):
                raise BoardException("Position not on the board")
            return self._pieces[position.row][position.column]
        if not self._in_bounds(row, column):
            raise BoardException("Position not on the board")
        return self._pieces[row][column]

    def place_piece(self, piece, position):
        if self.there_is_a_piece(position):
            raise BoardException(f"There is already a piece on position {position}")
        self._pieces[position.row][position.column] = piece
        piece.position = position

    def remove_piece(self, position):
        if not self.position_exists(position):
            raise BoardException("Position not on the board")
        if self.piece(position) is None:
            return None
        aux = self.piece(position)
        aux.position = None
        self._pieces[position.row][position.column] = None
        return aux

    def _in_bounds(self, row: int, column: int) -> bool:
        return 0 <= row < self.rows and 0 <= column < self.columns

    def position_exists(self, position) -> bool:
        return self._in_bounds(position.row, position.column)

    def there_is_a_piece(self, position) -> bool:
        if not self.position_exists(position):
            raise BoardException("Position not on the board")
        return self.piece(position) is not None
