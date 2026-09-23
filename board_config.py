from typing import Dict, List, Sequence
from abc import ABC, abstractmethod
from pydantic import BaseModel, ConfigDict, Field, model_validator

from board_stage.path_planning import Rect
from board_stage.printer import BoardPoint

class FrozenModel(BaseModel):
    model_config = ConfigDict(frozen=True)

class Pen(FrozenModel):
    width: float = 0.0

class Action(BaseModel, ABC):
    model_config = ConfigDict(frozen=True)

    @abstractmethod
    def resolve(self, obj: "BoardObject") -> Sequence[BoardPoint]:
        """Resolves local points relative to the object's origin (0, 0)."""
        pass

class SinglePointAction(Action):
    point: BoardPoint

    def resolve(self, obj: "BoardObject") -> Sequence[BoardPoint]:
        return [self.point]

class CenterAction(Action):
    z: float

    def resolve(self, obj: "BoardObject") -> Sequence[BoardPoint]:
        cx, cy = obj.width / 2.0, obj.height / 2.0
        return [BoardPoint(x=cx, y=cy, z=self.z)]

class GridAction(Action):
    start: BoardPoint
    end: BoardPoint
    steps: int = Field(..., ge=1)
    z: float

    def resolve(self, obj: "BoardObject") -> Sequence[BoardPoint]:
        if self.steps == 1:
            return [BoardPoint(x=self.start.x, y=self.start.y, z=self.z)]

        dx = (self.end.x - self.start.x) / (self.steps - 1)
        dy = (self.end.y - self.start.y) / (self.steps - 1)
        return [BoardPoint(x=self.start.x + i * dx, y=self.start.y + i * dy, z=self.z) for i in range(self.steps)]

class BoardObject(FrozenModel):
    id: str
    x: float
    y: float
    width: float = Field(..., gt=0)
    height: float = Field(..., gt=0)
    safe_z: float
    margin: float = 0.0
    default_action: Action = Field(default_factory=lambda: CenterAction(z=0.0))
    actions: List[Action] = Field(default_factory=list)

    @property
    def local_action_points(self) -> List[BoardPoint]:
        """Returns the list of action points in local coordinates (relative to the object's origin). If no actions are defined, returns the default action point."""
        all_actions = [self.default_action] if not self.actions else self.actions
        return [pt for act in all_actions for pt in act.resolve(self)]

    @property
    def board_action_points(self) -> List[BoardPoint]:
        """Returns the list of action points in board coordinates (absolute)."""
        return [BoardPoint(x=self.x + pt.x, y=self.y + pt.y, z=pt.z) for pt in self.local_action_points]

    def get_rect(self, pen: Pen) -> Rect:
        """Computes the footprint dynamically based on current state and pen width."""
        return Rect(self.x, self.x + self.width, self.y, self.y + self.height).inflated(
            self.margin + pen.width / 2
        )

    @model_validator(mode="after")
    def _validate_points_within_bounds(self) -> "BoardObject":
        for pt in self.local_action_points:
            if not (0 <= pt.x <= self.width and 0 <= pt.y <= self.height):
                raise ValueError(
                    f"Action point ({pt.x}, {pt.y}) in object '{self.id}' "
                    f"exceeds bounds (width={self.width}, height={self.height})."
                )
        return self

def _check_not_below_board(z: float, what: str):
    if z < 0:
        raise ValueError(
            f"{what} is {z}, but board-frame Z can't go below 0 (0 = "
            f"touching the board surface). Check your board layout."
        )

class BoardConfig(FrozenModel):
    objects: Dict[str, BoardObject]
    pen: Pen = Field(default_factory=Pen)

    @model_validator(mode="after")
    def _check_z_not_below_board(self) -> "BoardConfig":
        for obj in self.objects.values():
            _check_not_below_board(obj.safe_z, f"Object {obj.id!r} safe_z")
            for pt in obj.local_action_points:
                _check_not_below_board(pt.z, f"Object {obj.id!r} action point Z")
        return self

    def check_fits_bed(self, bed_width: float, bed_height: float) -> "BoardConfig":
        for obj in self.objects.values():
            x_min, x_max = obj.x, obj.x + obj.width
            y_min, y_max = obj.y, obj.y + obj.height
            if x_min < 0 or y_min < 0 or x_max > bed_width or y_max > bed_height:
                raise ValueError(
                    f"Object {obj.id} bounding box "
                    f"(x: {x_min}-{x_max}, y: {y_min}-{y_max}) "
                    f"does not fit on bed ({bed_width} x {bed_height})."
                )
        return self

    def check_objects_no_overlap(self) -> "BoardConfig":
        """Check that no two objects overlap (including their margins)."""
        objs = list(self.objects.values())
        rects = [obj.get_rect(self.pen) for obj in objs]
        
        for i, obj1 in enumerate(objs):
            for j, obj2 in enumerate(objs):
                if i >= j:
                    continue
                if rects[i].intersects(rects[j]):
                    raise ValueError(
                        f"Objects {obj1.id} and {obj2.id} overlap (including margins). Check your board layout."
                    )
        return self