# Core concepts

## Two coordinate frames

Everything positions in one of two frames:

- **Board frame** – millimetres measured from the **bottom-left corner of the
  board**. `Z = 0` means the pen is touching the board surface.
- **Printer frame** – the Ender's own machine coordinates.

These are *not* interchangeable, so points are tagged with their frame:

| Type | Frame |
| --- | --- |
| `BoardPoint` | Board |
| `PrinterPoint` | Printer |
| `BasePoint` | Shared base class (has `x`, `y`, `z`) |

Adding or subtracting points from different frames raises a `TypeError`, so mix
ups surface immediately instead of moving the pen somewhere wrong. `Point` is a
backwards-compatible alias for `BoardPoint`.

### The bridge: `origin`

The link between the frames is a single `PrinterPoint` called `origin`. It says:

- where the board's `(0, 0)` sits in machine coordinates, and
- which machine Z corresponds to the pen touching the board (`board Z = 0`).

```python
printer = Ender3_printer("/dev/ttyUSB0", origin=PrinterPoint(6.0, -14.0, 13.0))
```

The conversions are:

```text
printer = (board.x - origin.x, board.y - origin.y, board.z + origin.z)
board   = (printer.x + origin.x, printer.y + origin.y, printer.z - origin.z)
```

You normally only ever talk in the **board frame**. The `Board` converts for you
when it sends G-code.

## Board objects

A `BoardObject` is a named rectangle on the bed – a sample, a tube, a wash
station. Positions are in the board frame.

| Field | Meaning |
| --- | --- |
| `id` | Name, also the key in `BoardConfig.objects` |
| `x`, `y` | Board-frame position of the object's bottom-left corner |
| `width`, `height` | Size of the rectangle (must be > 0) |
| `safe_z` | Z at or above which the pen can safely pass over the object |
| `margin` | Extra clearance added around the footprint |
| `default_action` | Where to go when no specific point is given |
| `actions` | The list of points to visit (see below) |

Objects also know their own **local frame**: `(0, 0)` is the object's bottom-left
corner. Action points are written in local coordinates and must stay inside the
rectangle; the library checks this when the object is created.

## Actions

An `Action` is a recipe that produces points inside an object, in local
coordinates. Built-in actions:

| Action | Produces |
| --- | --- |
| `SinglePointAction(point=BoardPoint(...))` | Exactly that one point |
| `CenterAction(z=...)` | The object's centre at height `z` |
| `GridAction(start=..., end=..., steps=..., z=...)` | `steps` points evenly spaced from `start` to `end` (inclusive) at height `z` |

`.resolve(obj)` turns an action into `BoardPoint`s in the object's local frame.
The `BoardObject` then exposes resolved **`ActionPoint`s**, which carry both
frames at once:

```python
point = board.action_points("brass")[0]
point.object_id   # 'brass'
point.index       # 0
point.action      # the Action that created it
point.local       # (5.0, 30.0, 1.0)   object-relative
point.board       # (135.0, 39.0, 1.0) absolute
```

The `default_action` is the fallback target and is **not** included in
`action_points`.

## The pen and keep-out zones

`Pen(width=...)` describes the tool. Each object's keep-out footprint is its
rectangle grown by `margin + pen.width / 2`:

```python
obj.get_rect(pen)  # -> Rect, inflated for clearance
```

While the pen travels **below** an object's `safe_z`, that object's footprint is
treated as an obstacle and the route is planned around it. At or above
`safe_z`, the pen simply travels in a straight line over the object. This is why
every object needs a realistic `safe_z`: too low and you crash, too high and
every move is a long detour.
