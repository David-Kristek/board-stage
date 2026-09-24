"""
Drives Board.move_to_object/retract_from against a NullPrinter-backed board
and animates the recorded (x, y, z) history with matplotlib -- for
verifying keep-out routing and Z clearances with no printer attached.
"""

import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from matplotlib.patches import Rectangle
from mpl_toolkits.mplot3d import Axes3D  # noqa: F401 -- registers the 3d projection

from board_stage.board import Board
from board_stage.board_config import BoardConfig


def plot_layout(board_config: BoardConfig, bed_width=220, bed_height=220, highlight_id=None):
    """
    Static top-down plot of a board layout: object footprints, their
    inflated keep-out margins, and action points. Takes just a BoardConfig --
    no Board, printer, or move history needed -- so you can eyeball a layout
    (e.g. spot two objects overlapping) before ever building a Board with it.
    """

    fig, ax = plt.subplots(figsize=(8, 8))
    ax.set_xlabel("X (mm)")
    ax.set_ylabel("Y (mm)")
    ax.set_aspect("equal")
    ax.set_xlim(0, bed_width)
    ax.set_ylim(0, bed_height)
    ax.add_patch(Rectangle((0, 0), bed_width, bed_height, fill=False, edgecolor="gray", linewidth=1, label="bed"))

    for object_id, obj in board_config.objects.items():
        color = "tab:red" if object_id == highlight_id else "tab:blue"
        ax.add_patch(Rectangle((obj.x, obj.y), obj.width, obj.height, fill=False, edgecolor=color))

        center_x = obj.x + obj.width / 2.0
        center_y = obj.y + obj.height / 2.0
        ax.text(center_x, center_y, object_id, color=color, ha="center", va="center")

        # Inflated footprint other moves actually route around once their
        # travel Z dips below this object's safe_z.
        r = obj.get_rect(board_config.pen)
        ax.add_patch(
            Rectangle(
                (r.x_min, r.y_min),
                r.x_max - r.x_min,
                r.y_max - r.y_min,
                fill=False,
                edgecolor="tab:red",
                linestyle="--",
            )
        )

        # Plot all resolved action points for the object
        for pt in obj.board_action_points:
            marker = "^" if object_id == highlight_id else "x"
            ax.scatter(pt.x, pt.y, color=color, marker=marker, s=60, zorder=3)

    ax.legend()
    plt.show()
    return fig


def simulate(board: Board, object_ids):
    """
    Visit object_ids in order (move_to_object + retract_from each).
    It loops through all available action points for each object,
    returning the recorded (x, y, z) history.
    """

    # Begin from the rest position, like a real printer after homing (otherwise a
    # NullPrinter parked at z=0 can start inside an object's keep-out).
    board.park()

    for object_id in object_ids:
        obj = board.objects[object_id]
        # Visit every action point configured for this object
        for point in obj.action_points:
            board.move_to_object(object_id, point=point)
            board.retract_from(object_id)

    return board.printer.history


def _draw_rect(ax, x_min, x_max, y_min, y_max, z=0, **kwargs):
    xs = [x_min, x_max, x_max, x_min, x_min]
    ys = [y_min, y_min, y_max, y_max, y_min]
    ax.plot(xs, ys, [z] * 5, **kwargs)


def animate(history, board: Board, printer, interval=300, highlight_id=None):
    fig = plt.figure(figsize=(9, 8))
    ax = fig.add_subplot(projection="3d")

    ax.set_xlabel("X (mm)")
    ax.set_ylabel("Y (mm)")
    ax.set_zlabel("Z (mm)")

    max_z = max(z for _, _, z in history) if history else 10
    ax.set_xlim(0, printer.bed_width)
    ax.set_ylim(0, printer.bed_height)
    ax.set_zlim(0, max(max_z * 1.1, 10))

    _draw_rect(ax, 0, printer.bed_width, 0, printer.bed_height, color="gray", linewidth=1, label="bed")

    for object_id, obj in board.objects.items():
        color = "tab:red" if object_id == highlight_id else "tab:blue"
        _draw_rect(ax, obj.x, obj.x + obj.width, obj.y, obj.y + obj.height, color=color)

        center_x = obj.x + obj.width / 2.0
        center_y = obj.y + obj.height / 2.0
        ax.text(center_x, center_y, 0, object_id, color=color)

        # Inflated footprint other moves actually route around once their
        # travel Z dips below this object's safe_z.
        if obj.margin > 0:
            rect = obj.get_rect(board.pen)
            _draw_rect(ax, rect.x_min, rect.x_max, rect.y_min, rect.y_max, color="tab:red", linestyle="--")

        # Plot all resolved action points for the object at Z=0 for reference
        for pt in obj.board_action_points:
            marker = "^" if object_id == highlight_id else "x"
            ax.scatter([pt.x], [pt.y], [0], color=color, marker=marker, s=60)

    xs, ys, zs = zip(*history)

    (trail,) = ax.plot([], [], [], color="black", linewidth=1.5)
    (pen_point,) = ax.plot([], [], [], color="black", marker="o", markersize=8)
    (drop_line,) = ax.plot([], [], [], color="black", linewidth=0.8, linestyle=":")
    title = ax.set_title("")

    def update(frame):
        trail.set_data(xs[: frame + 1], ys[: frame + 1])
        trail.set_3d_properties(zs[: frame + 1])

        pen_point.set_data([xs[frame]], [ys[frame]])
        pen_point.set_3d_properties([zs[frame]])

        drop_line.set_data([xs[frame], xs[frame]], [ys[frame], ys[frame]])
        drop_line.set_3d_properties([0, zs[frame]])

        title.set_text(f"Move {frame}/{len(history) - 1}  X={xs[frame]:.1f} Y={ys[frame]:.1f} Z={zs[frame]:.1f}")
        return trail, pen_point, drop_line, title

    anim = FuncAnimation(fig, update, frames=len(history), interval=interval, blit=False, repeat=True)
    ax.legend()
    plt.show()
    return anim
