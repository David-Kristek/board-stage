from contextlib import ExitStack, contextmanager
from typing import Callable, Optional

from board_stage.board_config import BoardConfig
from board_stage.path_planning import find_path
from board_stage.printer import BoardPoint, Printer


class Board:
    def __init__(self, printer: Printer, board_config: BoardConfig):
        self.printer = printer

        board_config.check_fits_bed(printer.bed_width, printer.bed_height)
        board_config.check_objects_no_overlap()

        self.objects = board_config.objects
        self.pen = board_config.pen

    def __str__(self):
        return f"{len(self.objects)} object(s) loaded: {sorted(self.objects.keys())}."

    def __enter__(self) -> "Board":
        self._stack = ExitStack()
        self._stack.enter_context(self.printer)
        return self

    def __exit__(self, *exc):
        return self._stack.__exit__(*exc)

    def validate_object_id(self, object_id: str):
        if object_id not in self.objects:
            raise ValueError(f"Invalid object id: {object_id!r}.")

    def _keepout_rects(self, travel_z: float, exclude_id: Optional[str] = None):
        return [
            obj.get_rect(self.pen)
            for obj_id, obj in self.objects.items()
            if obj_id != exclude_id and travel_z < obj.safe_z
        ]

    def _assert_pen_clear(self):
        pen = self.printer.current
        for object_id, obj in self.objects.items():
            if pen.z < obj.safe_z and obj.get_rect(self.pen).contains(pen):
                raise ValueError(
                    f"Pen is parked inside object {object_id!r}'s keep-out footprint at Z={pen.z} "
                    f"(safe_z={obj.safe_z}). Move the pen up first to avoid crashing into it."
                )

    def _travel_avoiding_obstacles(
        self, target_xy: tuple[float, float], feedrate: int, travel_z: float, exclude_id: Optional[str] = None
    ):
        rects = self._keepout_rects(travel_z, exclude_id=exclude_id)
        pen = self.printer.current

        if not rects:
            self.printer.move_absolute(BoardPoint(target_xy[0], target_xy[1], pen.z), feedrate=feedrate)
            return

        route = find_path((pen.x, pen.y), target_xy, rects)

        for board_x, board_y in route[1:]:
            self.printer.move_absolute(BoardPoint(board_x, board_y, pen.z), feedrate=feedrate)

    def retract_from(self, object_id: str, feedrate: int = 1000):
        self.validate_object_id(object_id)
        pen = self.printer.current
        self.printer.move_absolute(BoardPoint(pen.x, pen.y, self.objects[object_id].safe_z), feedrate=feedrate)

    def park(self, feedrate: int = 1000):
        clearance = max((obj.safe_z for obj in self.objects.values()), default=0.0)
        pen = self.printer.current
        z = max(pen.z, clearance, self.printer.default.z)
        self.printer.move_absolute(BoardPoint(pen.x, pen.y, z), feedrate=feedrate)
        self.printer.move_absolute(BoardPoint(self.printer.default.x, self.printer.default.y, z), feedrate=feedrate)

    def move_to_object(
        self,
        object_id: str,
        action_index: int = 0,
        coords: Optional[tuple[float, float]] = None,
        descend_to: Optional[float] = None,
        feedrate: int = 1000,
        descend: bool = True,
    ):
        self.validate_object_id(object_id)
        obj = self.objects[object_id]
        self._assert_pen_clear()

        if coords is not None:
            if not (0 <= coords[0] <= obj.width) or not (0 <= coords[1] <= obj.height):
                raise ValueError(
                    f"Coordinates {coords} are outside object {object_id!r}'s dimensions "
                    f"(width={obj.width}, height={obj.height})."
                )
            target_xy = (obj.x + coords[0], obj.y + coords[1])

            if descend_to is None:
                descend_to = obj.local_action_points[0].z

        else:
            try:
                target_pt = obj.local_action_points[action_index]
            except IndexError:
                raise ValueError(
                    f"Action index {action_index} is out of range for object {object_id!r}. "
                    f"Object has {len(obj.local_action_points)} point(s) available."
                )
            target_xy = (obj.x + target_pt.x, obj.y + target_pt.y)

            if descend_to is None:
                descend_to = target_pt.z

        travel_z = max(self.printer.current.z, obj.safe_z)
        self.printer.move_absolute(
            BoardPoint(self.printer.current.x, self.printer.current.y, travel_z), feedrate=feedrate
        )

        self._travel_avoiding_obstacles(target_xy, feedrate, travel_z, exclude_id=object_id)

        if descend:
            print(f"Descending onto {object_id}: Z={descend_to}")
            pen = self.printer.current
            self.printer.move_absolute(BoardPoint(pen.x, pen.y, descend_to), feedrate=feedrate)

    @contextmanager
    def at(
        self,
        object_id: str,
        action_index: int = 0,
        coords: Optional[tuple[float, float]] = None,
        descend_to: Optional[float] = None,
        feedrate: int = 1000,
        descend: bool = True,
    ):
        self.move_to_object(
            object_id,
            action_index=action_index,
            coords=coords,
            descend_to=descend_to,
            feedrate=feedrate,
            descend=descend,
        )
        try:
            yield self.objects[object_id]
        finally:
            self.retract_from(object_id, feedrate=feedrate)

    def go_around_all_objects(self, feedrate: int = 1000):
        """Circles around all objects borders to check your dimensions."""
        self._assert_pen_clear()

        for object_id, obj in self.objects.items():
            corners = [(0, 0), (obj.width, 0), (obj.width, obj.height), (0, obj.height)]

            first = True
            for local_xy in corners:
                self.move_to_object(object_id, coords=local_xy, descend=False, feedrate=feedrate)

                if first:
                    pen = self.printer.current
                    self.printer.move_absolute(BoardPoint(pen.x, pen.y, obj.safe_z), feedrate=feedrate)
                    first = False

        self.park()


def _terminal_confirm(prompt: str) -> bool:
    """Default `confirm` callback: ask on the terminal; Enter (or y/yes) means yes."""
    return input(f"{prompt} [Y/n] ").strip().lower() in {"", "y", "yes"}


def setup_board(
    board: Board,
    reference_id: str = "solution",
    *,
    force_calibrate: bool = False,
    confirm: Optional[Callable[[str], bool]] = None,
    notify: Callable[[str], None] = print,
) -> bool:
    """Hover over `reference_id` and confirm the printer is calibrated, homing if
    needed (or if `force_calibrate`). Must run inside `with board:`. Returns True
    if calibration ran. Override `confirm`/`notify` to drive it from a UI or test."""
    board.validate_object_id(reference_id)
    confirm = confirm or _terminal_confirm
    notify("Make sure there is nothing in the way of the pen.")

    def pen_over(object_id: str) -> bool:
        board.move_to_object(object_id, descend=False)
        return confirm(f"Is the pen over {object_id!r}?")

    if not force_calibrate and pen_over(reference_id):
        return False

    notify("Calibration is needed. Check nothing is in the way of the pen.")
    board.printer.calibrate()
    notify("Printer calibrated.")
    if not pen_over(reference_id):
        raise ValueError(
            f"Calibration failed: the pen is not over {reference_id!r}. "
            f"Check the board layout for correct {reference_id!r} coordinates."
        )
    return True
