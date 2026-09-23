"""
Hardware-free stand-in for Ender_3D.Ender3_printer. Mirrors just the
interface Board needs (bed size, board-frame `current`,
move_absolute/move_relative, block, calibrate) with no Serial connection,
and records every commanded board-frame position so visualize.py can
replay a Board move sequence with no printer attached.
"""

from typing import Callable, Any
from board_stage.board import Board
from board_stage.printer import BoardPoint, PrinterPoint, AnyPoint


class NullPrinter:
    def __init__(
        self,
        origin: PrinterPoint = PrinterPoint(0, 0, 0),
        default: BoardPoint = BoardPoint(0, 0, 100),
        bed_width: float = 220,
        bed_height: float = 220,
    ):
        self.origin = origin
        self.default = default
        self.bed_width = bed_width
        self.bed_height = bed_height

        self._current_printer_pos = PrinterPoint(0, 0, 0)

        # (x, y, z) in the board frame after every commanded move, start included.
        self.history = [(self.current.x, self.current.y, self.current.z)]

    def __enter__(self) -> "NullPrinter":
        return self

    def __exit__(self, *exc) -> None:
        return None

    @property
    def current(self) -> BoardPoint:
        return self._to_board_coords(self._current_printer_pos)

    def _to_printer_coords(self, p: AnyPoint) -> PrinterPoint:
        if isinstance(p, PrinterPoint):
            return p
        return PrinterPoint(x=p.x - self.origin.x, y=p.y - self.origin.y, z=p.z + self.origin.z)

    def _to_board_coords(self, p: AnyPoint) -> BoardPoint:
        if isinstance(p, BoardPoint):
            return p
        return BoardPoint(x=p.x + self.origin.x, y=p.y + self.origin.y, z=p.z - self.origin.z)

    def move_absolute(self, target: AnyPoint, feedrate: int = 1000, block: bool = True):
        p = self._to_printer_coords(target)
        self._current_printer_pos = p

        board_pos = self.current
        print(f"New position: {board_pos.x}, {board_pos.y}, {board_pos.z}")
        self.history.append((board_pos.x, board_pos.y, board_pos.z))

    def move_relative(self, delta: AnyPoint, feedrate: int = 5000, block: bool = True):
        # Convert delta to BoardPoint to satisfy type-checked addition
        delta_board = BoardPoint(delta.x, delta.y, delta.z)

        new_board = self.current + delta_board
        self._current_printer_pos = self._to_printer_coords(new_board)

        self.history.append((new_board.x, new_board.y, new_board.z))

    def block(self):
        pass

    def calibrate(self):
        """Stand-in for Ender3_printer.calibrate() -- resets the tracked position to home, then moves to default."""
        self._current_printer_pos = PrinterPoint(0, 0, 0)
        self.move_absolute(self.default)


def dry_run(board_config, cycle: Callable[[NullPrinter, Board], Any], **printer_kwargs) -> Board:
    """
    Run `cycle(printer, board)` against a NullPrinter-backed Board instead of
    real hardware -- catches board-layout bugs (overlapping objects,
    out-of-bounds coordinates, unreachable routes, pen-parked-in-keepout
    moves) with no printer attached. Returns the Board (its `.printer.history`
    is the recorded (x, y, z) moves; pass board and board.printer straight to
    visualize.animate to watch them).
    """
    printer = NullPrinter(**printer_kwargs)
    board = Board(printer, board_config)
    with board:
        cycle(printer, board)
    return board
