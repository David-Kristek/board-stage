# Simulation

You can run a whole cycle with **no printer attached**. This catches board-layout
bugs early: overlapping objects, out-of-bounds points, unreachable routes, or a
pen parked inside a keep-out zone.

## `dry_run`

`dry_run` swaps the real `Printer` for a `NullPrinter` that records every move
instead of sending G-code:

```python
from board_stage import dry_run

def cycle(printer, board):
    with board.at("solution"):
        pass
    with board.at("brass", point=board.action_points("brass")[0]):
        pass

board = dry_run(board_config, cycle, bed_width=230)
board.printer.history  # [(x, y, z), ...] in the board frame
```

It returns the `Board`, so `board.printer.history` is the recorded route. Extra
keyword arguments (`bed_width`, `bed_height`, `origin`, `default`) go to the
`NullPrinter`.

![A simulated dip, dry and measure cycle](images/cycle.gif)

*A simulated dip → dry → measure cycle replayed from the recorded history — no
hardware attached.*

## Visualizing

With the `plot` extra installed (`pip install -e ".[plot]"`):

```python
from board_stage.visualize import animate, plot_layout

plot_layout(board_config, highlight_id="brass")     # static top-down layout
animate(board.printer.history, board, board.printer)  # 3D playback
```

- `plot_layout` needs only a `BoardConfig` – useful before a `Board` even exists.
  It draws objects, their inflated keep-out margins, and action points.
- `animate` replays the recorded history as a moving pen in 3D.

## Runnable example

[`examples/measurement_cycle.py`](../examples/measurement_cycle.py) runs a full
dip → dry → measure cycle. Without `ENDER_PORT` it simulates and animates; set
the variable to drive real hardware:

```bash
python examples/measurement_cycle.py
ENDER_PORT=COM3 python examples/measurement_cycle.py
```
