class Position:

    def __init__(self, row: int = 0, column: int = 0):
        self.row = row
        self.column = column

    def set_values(self, row: int, column: int):
        self.row = row
        self.column = column

    def __repr__(self):
        return f"{self.row}, {self.column}"
