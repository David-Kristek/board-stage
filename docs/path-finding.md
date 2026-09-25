# Path finding

Whenever the pen moves, `Board` refuses to drag it through an object it would
collide with. Instead it plans a collision-free route with `find_path` — a
visibility graph + Dijkstra over 2D keep-out rectangles.

![The planner routing around keep-out zones](images/routing.png)

*To reach the bottom of `brass`, the pen avoids `solution` and the rack stacked
above it. The red dashed line is what it would take to lift over the rack; the
black line is the route it actually takes — around in XY.*

## Why route instead of lift?

The Z axis is slow (a lead screw). Lifting the pen above a tall object's
`safe_z`, crossing, and coming back down means a lot of Z travel: in the picture
above, clearing the rack at `safe_z=110` from `Z=20` costs `2 x 90 = 180 mm` of
slow Z. Detouring around it in XY costs essentially nothing extra (~2 mm here)
and no Z at all. So keeping the pen at travel Z and going around is usually much
faster — which is exactly what the planner does.

## When routing happens

For each move the pen travels at `travel_z = max(current_z, target.safe_z)`.
Any **other** object with `travel_z < obj.safe_z` becomes an obstacle:

- Below its `safe_z`, the object's footprint is a keep-out zone and the move is
  rerouted around it.
- At or above `safe_z`, the pen clears it and the move is a straight line.

The target object itself is never an obstacle for its own move, so the pen can
descend onto it.

## Keep-out zones

An obstacle is the object's rectangle inflated for clearance
(`margin + pen.width / 2`):

```python
rect = obj.get_rect(pen)  # -> Rect(x_min, x_max, y_min, y_max)
```

`Rect` also has `inflated(amount)`, `contains(point)`, and `intersects(other)`.

## The algorithm

`find_path(start, goal, rects)` works in plain 2D (any Z is ignored):

1. **Straight-line test.** If the segment `start → goal` doesn't cut through the
   interior of any rectangle, return `[start, goal]`.
2. **Visibility graph.** Otherwise use the start, the goal, and every rectangle
   corner as nodes. Two nodes are connected when the segment between them
   doesn't cut through any rectangle's interior. Grazing an edge or corner is
   allowed on purpose — routes deliberately hug the boundary for the shortest
   path.
3. **Dijkstra.** Find the shortest route through that graph.
4. If the goal is unreachable, raise `ValueError`.

## Using it directly

`find_path` and `Rect` are exported, so you can plan in your own code:

```python
from board_stage import Rect, find_path

obstacles = [Rect(50, 90, 0, 60)]
route = find_path((0, 20), (150, 20), obstacles)  # [(0, 20), (50, 0), (90, 0), (150, 20)]
```

You rarely need to: `Board.move_to_object` / `board.at(...)` call it for you
throughout a move. `Board` also guards the other direction with
`_assert_pen_clear`, which raises if the pen is already parked inside an object's
keep-out footprint while below its `safe_z`.
