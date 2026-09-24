# board_stage

Generic Ender 3 XY(Z) positioning library: raw motion, board-frame calibration, and obstacle-avoiding routing between named board objects.

## Features

- **Printer abstraction (`printer.py`)**: Serial communication with Ender 3, coordinate transformations between Base, Printer, and Board frames.
- **Board & Object configuration (`board_config.py`)**: Define physical board objects (samples, tubes, wash stations) and action points.
- **Board Controller (`board.py`)**: High-level movement orchestration, safety checks, and `setup_board` calibration.
- **Path Planning (`path_planning.py`)**: Visibility-graph routing with obstacle avoidance across defined board objects.
- **Simulation (`sim.py`, `visualize.py`)**: Dry-run execution and Matplotlib visualization of planned paths.

## Installation

```bash
pip install -e .
```

Or using `uv`:

```bash
uv add --path ../board-stage board-stage
```

Plotting extras for `visualize.py`:

```bash
pip install -e ".[plot]"
```

## Development

```bash
pip install -e ".[dev]"
ruff format .
ruff check .
```

## Quickstart

Describe the board once, then drive the pen to named objects. Action points are
local to each object and translated to the board frame for you.

```python
from board_stage import (
    Board,
    BoardConfig,
    BoardObject,
    BoardPoint,
    Ender3_printer,
    GridAction,
    Pen,
    PrinterPoint,
    SinglePointAction,
    setup_board,
)

brass = BoardObject(
    id="brass",
    x=130.0,
    y=9.0,
    width=99.0,
    height=65.0,
    safe_z=10.0,
    actions=[GridAction(start=BoardPoint(x=5.0, y=30.0), end=BoardPoint(x=95.0, y=30.0), steps=10, z=1.0)],
)

board_config = BoardConfig(
    pen=Pen(width=2.0),
    objects={
        "solution": BoardObject(
            id="solution",
            x=0.0,
            y=0.0,
            width=40.0,
            height=40.0,
            safe_z=55.0,
            margin=5.0,
            default_action=SinglePointAction(point=BoardPoint(x=25.0, y=25.0, z=23.0)),
        ),
        "brass": brass,
    },
)

printer = Ender3_printer("/dev/ttyUSB0", origin=PrinterPoint(6.0, -14.0, 13.0))

with Board(printer, board_config) as board:
    setup_board(board)  # force_calibrate=True to home first
    board.park()

    with board.at("solution"):
        pass  # dips in, then retracts on exit

    for i in range(len(board.objects["brass"].local_action_points)):
        with board.at("brass", action_index=i):
            ...  # run your measurement here

    board.park()
```

`board.at(object_id, ...)` raises to a safe Z, routes around other objects,
descends onto the target, and retracts when the block exits. Pass
`coords=(x, y)` for an ad-hoc point, or `descend=False` to just hover.

### Calibration

`setup_board` hovers above a reference object and asks whether the pen is over
it; if not (or `force_calibrate=True`) it homes and checks again, raising
`ValueError` if it still doesn't line up. Pass `confirm`/`notify` to drive it
from a UI or test instead of the terminal:

```python
setup_board(board, reference_id="solution")
```

## Dry run and visualization

Run the same cycle with no printer:

```python
from board_stage import dry_run
from board_stage.visualize import animate, plot_layout

plot_layout(board_config, highlight_id="brass")


def cycle(printer, board):
    with board.at("solution"):
        pass
    with board.at("brass", action_index=0):
        pass


board = dry_run(board_config, cycle, bed_width=230)
animate(board.printer.history, board, board.printer, highlight_id="brass")
```

`dry_run` catches layout bugs (overlaps, out-of-bounds points, unreachable
routes, a pen parked in a keep-out zone) before any hardware is connected.

See [`examples/measurement_cycle.py`](examples/measurement_cycle.py) for a fuller
runnable version.

## Project layout

```text
board-stage/
├── pyproject.toml
├── examples/
│   └── measurement_cycle.py
└── src/
    └── board_stage/
        ├── __init__.py        # public API
        ├── printer.py
        ├── board_config.py
        ├── board.py
        ├── path_planning.py
        ├── sim.py
        └── visualize.py
```

## Public API

```python
from board_stage import (
    Printer,
    Ender3_printer,
    BasePoint,
    BoardPoint,
    PrinterPoint,
    AnyPoint,
    Point,
    Board,
    setup_board,
    Action,
    SinglePointAction,
    CenterAction,
    GridAction,
    BoardConfig,
    BoardObject,
    Pen,
    Rect,
    find_path,
    NullPrinter,
    dry_run,
)
```
