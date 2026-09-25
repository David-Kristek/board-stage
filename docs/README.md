# board_stage docs

Simple, concept-first notes for `board_stage`. If you just want to run
something, start with the [root README](../README.md). These docs explain the
ideas the code is built on.

| Doc | What it covers |
| --- | --- |
| [Core concepts](concepts.md) | Frames, points, board objects, actions, the pen, keep-out zones |
| [Path finding](path-finding.md) | Keep-out zones, visibility graph + Dijkstra, straight-line moves |
| [Using the board](workflow.md) | The `Board` lifecycle: open, calibrate, `at(...)`, park, routing |
| [Simulation](simulation.md) | Running cycles without hardware and drawing them |
| [Adding your own printer](custom-printer.md) | The printer interface, adapting another machine |

## In one paragraph

The bed is described as **named rectangular objects** (a sample tube, a dryer, a
brass slide). Each object can carry **actions** that resolve to the exact points
you want to visit. A **`Board`** takes that description plus a **`Printer`** and
does the motion for you: it raises the pen, **routes around other objects** when
it would otherwise pass too low over them, lowers onto the target, and lifts
again on the way out.

```python
with Board(printer, board_config) as board:
    setup_board(board)
    with board.at("solution"):                          # dip into the solution
        pass
    point = board.action_points("brass")[0]
    with board.at("brass", point):                      # move to one measurement point
        ...                                             # do the measurement
    board.park()
```

## Glossary

- **Frame** – a coordinate system. `BoardPoint` vs `PrinterPoint`.
- **BoardObject** – a rectangle on the bed with a name.
- **Action** – a recipe that resolves to points inside an object (local coordinates).
- **ActionPoint** – one resolved point, in both local and board coordinates.
- **safe_z** – the Z at or above which it is safe to pass over an object.
- **keep-out** – an object's footprint inflated by its margin and the pen
  radius, avoided by routes while travelling below its `safe_z`.
