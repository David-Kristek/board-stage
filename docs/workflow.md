# Using the board

A `Board` is the thing that actually moves the pen. Build it from a `Printer`
and a `BoardConfig`, then use it as a context manager (which opens the serial
connection for you):

```python
board = Board(printer, board_config)

with board:
    setup_board(board)
    with board.at("solution"):
        pass
    board.park()
```

At construction the `Board` validates the layout:

- every object fits on the bed (`check_fits_bed`), and
- no two objects overlap, margins included (`check_objects_no_overlap`).

## Calibration

`setup_board(board)` confirms the printer knows where the board is. It hovers
over a reference object and asks whether the pen is actually above it. If not
(or with `force_calibrate=True`) it homes, checks again, and raises if it still
doesn't line up.

```python
setup_board(board)                              # ask on the terminal
setup_board(board, reference_id="solution")     # use a different object
setup_board(board, force_calibrate=True)        # always home first
```

Pass `confirm=` / `notify=` callbacks to drive it from a UI or a test instead of
the terminal.

## `board.at(...)` – the main move

`board.at(object_id, ...)` is a context manager. Entering it:

1. raises the pen to at least the object's `safe_z`,
2. routes to the target while avoiding other objects' keep-out zones,
3. descends onto the target point.

On exit it **retracts** back up to the object's `safe_z`. Whatever runs inside
the `with` block happens with the pen parked on the target.

```python
with board.at("solution"):                 # object's default_action
    pass

with board.at("brass", point=some_point):  # a specific ActionPoint
    pass

with board.at("dryer", coords=(15, 50)):   # ad-hoc local (x, y)
    pass

with board.at("brass", descend=False):     # hover only, don't lower
    pass
```

Target rules:

- No target → the object's `default_action`.
- `point=<ActionPoint>` → one of `action_points` (must belong to that object).
- `coords=(x, y)` → local coordinates inside the object; the target Z comes from
  the object's `default_action`.
- Pass either `point` or `coords`, never both.

## Visiting many points

`board.action_points(object_id)` lists the object's resolved points in visit
order (the `default_action` excluded). Iterate them and open one `at` block per
point:

```python
for point in board.action_points("brass"):
    with board.at("brass", point):
        ...  # measure here
```

## Other moves

| Call | What it does |
| --- | --- |
| `board.park()` | Lift to at least the highest `safe_z` (and default Z), then go to the printer's default XY |
| `board.move_to_object(...)` | Move/descend without a context manager |
| `board.retract_from(object_id)` | Lift straight up to the object's `safe_z` |
| `board.go_around_all_objects()` | Trace every object's border to check dimensions |

Safety note: before moving, the `Board` checks that the pen isn't already parked
**inside** an object's keep-out footprint while below its `safe_z`. If it is, it
raises rather than crashing into the object.

## Routing in one line

While travelling below an object's `safe_z`, that object's inflated footprint
becomes an obstacle and the path is planned around it with a visibility graph +
Dijkstra (`find_path`). Above `safe_z`, moves are straight lines.
