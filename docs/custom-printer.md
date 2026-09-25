# Adding your own printer

`Board` doesn't care that the machine is an Ender 3 — it only needs a small
"printer" object that can move the tool and report where it is, **in the board
frame**. Built-in `Printer` (aliased `Ender3_printer`) is just one implementation,
and `NullPrinter` is another. Here's how to add your own.

## What `Board` needs

| Member | Used for |
| --- | --- |
| `__enter__` / `__exit__` | Open and close the connection (`Board` uses the printer as a context manager) |
| `bed_width`, `bed_height` | Layout validation — do all objects fit on the bed? |
| `default` | A `BoardPoint` to park at |
| `current` | `BoardPoint` — where the tool is right now, in board coordinates |
| `move_absolute(target, feedrate=1000, block=True)` | Perform a move to a `BoardPoint` (or `PrinterPoint`) |
| `calibrate()` | Home / zero the machine; called by `setup_board` |

That's the whole contract. Everything you expose is in the board frame; machine
coordinates stay private to your class.

## Option 1: Marlin-style machine — subclass `Printer`

If your machine speaks Marlin G-code over serial but differs in details (command
names, speeds, homing), subclass `Printer` and override the G-code layer.
Coordinate handling and position tracking are inherited.

```python
from board_stage import Printer


class MyMarlin(Printer):
    def _move(self, x=None, y=None, z=None, feedrate=5000):
        ...  # build and send your G-code dialect

    def _send_cmd(self, cmd, timeout=120.0):
        ...  # write the command, wait for the controller's "ok"
```

Override `__enter__` too if the connection setup differs.

## Option 2: any other controller — implement the interface

For a non-Marlin controller, write a small adapter much like the built-in
`NullPrinter`. The important part is the **frame conversion**: track machine
coordinates internally, and convert to/from the board frame with `origin`.

```python
from board_stage import BoardPoint, PrinterPoint


class MyPrinter:
    def __init__(self, port, origin=PrinterPoint(0, 0, 0),
                 default=BoardPoint(0, 0, 100), bed_width=300.0, bed_height=300.0):
        self.origin = origin
        self.default = default
        self.bed_width = bed_width
        self.bed_height = bed_height
        self._pos = PrinterPoint(0, 0, 0)  # machine coords — your source of truth

    def __enter__(self):
        # open the link to your controller
        return self

    def __exit__(self, *exc):
        # close it
        ...

    @property
    def current(self):
        return self._to_board(self._pos)

    def move_absolute(self, target, feedrate=1000, block=True):
        self._pos = self._to_printer(target)
        # send the move to your controller here

    def calibrate(self):
        self._pos = PrinterPoint(0, 0, 0)  # or run a real homing routine

    def _to_printer(self, p):
        return p if isinstance(p, PrinterPoint) else PrinterPoint(
            p.x - self.origin.x, p.y - self.origin.y, p.z + self.origin.z)

    def _to_board(self, p):
        return p if isinstance(p, BoardPoint) else BoardPoint(
            p.x + self.origin.x, p.y + self.origin.y, p.z - self.origin.z)
```

Then use it exactly like the built-in printer:

```python
with Board(MyPrinter("COM3"), board_config) as board:
    setup_board(board)
    board.park()
```

## Conventions to respect

- **Frame contract.** `current` and `move_absolute` speak `BoardPoint`. Keep
  machine coordinates internal and convert with `origin` — the point where the
  board's `(0, 0)` sits on the machine, and the machine Z at which the pen
  touches the board.
- **Block by default.** Only return from `move_absolute` once the move has
  actually finished (`block=True`), or `Board` will run its collision checks
  against a stale position.
- **`origin` is the only calibration number.** If a move lands in the wrong
  place, fix `origin`, not the board layout.

## Test it without hardware

Swap in a stand-in (like `NullPrinter`) and run your cycle with `dry_run`; see
[Simulation](simulation.md).
