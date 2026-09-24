import re
import time
from dataclasses import dataclass
from typing import TypeVar

from serial import Serial

T = TypeVar("T", bound="BasePoint")


@dataclass(frozen=True)
class BasePoint:
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0

    def __add__(self: T, other: T) -> T:
        if type(self) is not type(other):
            raise TypeError(f"Frame mismatch: Cannot add {type(other).__name__} to {type(self).__name__}")
        return type(self)(self.x + other.x, self.y + other.y, self.z + other.z)

    def __sub__(self: T, other: T) -> T:
        if type(self) is not type(other):
            raise TypeError(f"Frame mismatch: Cannot subtract {type(other).__name__} from {type(self).__name__}")
        return type(self)(self.x - other.x, self.y - other.y, self.z - other.z)

    def __iter__(self):
        yield self.x
        yield self.y
        yield self.z


@dataclass(frozen=True)
class BoardPoint(BasePoint):
    pass


@dataclass(frozen=True)
class PrinterPoint(BasePoint):
    pass


AnyPoint = BoardPoint | PrinterPoint


class Printer:
    def __init__(
        self,
        port_num: str,
        name: str = "Ender3",
        default: BoardPoint = BoardPoint(0, 0, 100),
        origin: PrinterPoint = PrinterPoint(0, 0, 0),
        bed_width: float = 230,
        bed_height: float = 220,
    ):
        self.name = name
        self.port_num = port_num

        self.default = default
        self.origin = origin
        self._current_printer_pos = PrinterPoint(0, 0, 0)

        self.bed_width = bed_width
        self.bed_height = bed_height
        self.connection = None

    def __enter__(self) -> "Printer":
        self.connection = Serial(port=self.port_num, baudrate=115200, timeout=1)
        time.sleep(2)  # give printer time after serial connection
        self._sync_position()  # get the printer's actual position after connecting
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def __str__(self):
        return (
            f"The {self.name} is an Ender3 printer connected to {self.port_num}. "
            f"Default position is {self.default}. "
            f"Pen at machine home points to board X:{self.origin.x}, Y:{self.origin.y}. "
            f"Pen touches the board surface at machine Z:{self.origin.z}."
        )

    # --------------------------------------------------
    # Command sender
    # --------------------------------------------------

    def _send_cmd(self, cmd):
        self.connection.write(f"{cmd}\n".encode("ASCII"))
        # print(f"{cmd} has been sent to {self.name}")

        while True:
            line = self.connection.readline().decode("ASCII").strip()
            if "ok" in line.lower():
                break

    # --------------------------------------------------
    # Position tracking
    # --------------------------------------------------

    @property
    def current(self) -> BoardPoint:
        """Last commanded position, in the board frame."""
        return self._to_board_coords(self._current_printer_pos)

    def _to_printer_coords(self, p: AnyPoint) -> PrinterPoint:
        if isinstance(p, PrinterPoint):
            return p
        return PrinterPoint(x=p.x - self.origin.x, y=p.y - self.origin.y, z=p.z + self.origin.z)

    def _to_board_coords(self, p: AnyPoint) -> BoardPoint:
        if isinstance(p, BoardPoint):
            return p
        return BoardPoint(x=p.x + self.origin.x, y=p.y + self.origin.y, z=p.z - self.origin.z)

    # --------------------------------------------------
    # Basic G-code movement
    # --------------------------------------------------

    def _move(self, x=None, y=None, z=None, feedrate=5000):
        command = "G0"

        if x is not None:
            command += f" X{x}"
        if y is not None:
            command += f" Y{y}"
        if z is not None:
            command += f" Z{z}"

        command += f" F{feedrate}"
        self._send_cmd(command)

    def block(self):
        self._send_cmd("M400")

    def move_absolute(self, target: AnyPoint, feedrate: int = 1000, block: bool = True):
        p = self._to_printer_coords(target)
        self._send_cmd("G90")
        self._move(x=p.x, y=p.y, z=p.z, feedrate=feedrate)

        self._current_printer_pos = p

        if block:
            self.block()

    def move_relative(self, delta: AnyPoint, feedrate: int = 1000, block: bool = True):
        self._send_cmd("G91")
        self._move(x=delta.x, y=delta.y, z=delta.z, feedrate=feedrate)
        self._send_cmd("G90")

        delta_board = self._to_board_coords(delta)
        current_board = self.current

        new_board = current_board + delta_board
        self._current_printer_pos = self._to_printer_coords(new_board)

        if block:
            self.block()

    def _sync_position(self) -> BoardPoint:
        """Query the printer's actual machine position and return it in board coordinates."""
        self.connection.write(b"M114\n")
        position = None

        while True:
            line = self.connection.readline().decode("ASCII", errors="replace").strip()
            if not line:
                raise TimeoutError("Timed out waiting for the printer's M114 response.")

            if position is None:
                values = {}
                for axis in ("X", "Y", "Z"):
                    match = re.search(r"(?:^|\s)" + axis + r":\s*([-+]?(?:\d+(?:\.\d*)?|\.\d+))", line)
                    if match:
                        values[axis] = float(match.group(1))
                if len(values) == 3:
                    # Používáme nový PrinterPoint místo Enum
                    position = PrinterPoint(values["X"], values["Y"], values["Z"])

            if "ok" in line.lower():
                break

        if position is None:
            raise ValueError("The printer returned no X/Y/Z position in response to M114.")

        # Ukládáme do nové proměnné pro interní stav
        self._current_printer_pos = position
        return self.current

    # --------------------------------------------------
    # Home / close
    # --------------------------------------------------

    def _autohome(self):
        self._send_cmd("G28")

    def calibrate(self):
        self._autohome()
        self.move_absolute(self.default)

    def close(self):
        if self.connection and self.connection.is_open:
            self.connection.close()
            print(f"Connection to {self.name} closed.")


# Backwards compatibility aliases
Ender3_printer = Printer
Point = BoardPoint
