"""
Visibility-graph path planning around rectangular keep-out zones (e.g. the
solution tube's footprint). Works purely in 2D space, automatically
stripping Z-coordinates if 3D points are passed in.
"""

import heapq
import math
from dataclasses import dataclass
from typing import Iterable, List, Optional, Tuple

# Using a generic Iterable to accept tuples, lists, or BoardPoints
PointLike = Iterable[float]
Point2D = Tuple[float, float]


def _to_2d(p: PointLike) -> Point2D:
    """Safely extracts X and Y from any point-like object (including 3D)."""
    iterator = iter(p)
    return (next(iterator), next(iterator))


@dataclass(frozen=True)
class Rect:
    x_min: float
    x_max: float
    y_min: float
    y_max: float

    def inflated(self, amount: float) -> "Rect":
        """Grow outward by `amount` on every side, for clearance."""
        return Rect(
            self.x_min - amount,
            self.x_max + amount,
            self.y_min - amount,
            self.y_max + amount,
        )

    def corners(self) -> List[Point2D]:
        return [
            (self.x_min, self.y_min),
            (self.x_max, self.y_min),
            (self.x_max, self.y_max),
            (self.x_min, self.y_max),
        ]

    def contains(self, p: PointLike) -> bool:
        x, y = _to_2d(p)
        return self.x_min < x < self.x_max and self.y_min < y < self.y_max

    def intersects(self, other: "Rect") -> bool:
        return not (
            self.x_max <= other.x_min
            or self.x_min >= other.x_max
            or self.y_max <= other.y_min
            or self.y_min >= other.y_max
        )


def _segment_intersects_rect(p1: Point2D, p2: Point2D, rect: Rect) -> bool:
    """
    True if p1->p2 cuts through the rect's interior (Liang-Barsky clipping).
    Grazing an edge or corner doesn't count -- routes trace those on purpose.
    """
    x1, y1 = p1
    x2, y2 = p2
    dx, dy = x2 - x1, y2 - y1

    t_min, t_max = 0.0, 1.0

    for p, q in (
        (-dx, x1 - rect.x_min),
        (dx, rect.x_max - x1),
        (-dy, y1 - rect.y_min),
        (dy, rect.y_max - y1),
    ):
        if p == 0:
            if q < 0:
                return False  # Parallel to this boundary and outside it
            continue
        t = q / p
        if p < 0:
            t_min = max(t_min, t)
        else:
            t_max = min(t_max, t)
        if t_min > t_max:
            return False

    mid_t = (t_min + t_max) * 0.5
    midpoint = (x1 + dx * mid_t, y1 + dy * mid_t)
    return rect.contains(midpoint)


def crosses_keepout(start: Point2D, goal: Point2D, rects: List[Rect]) -> bool:
    """True if the segment cuts through the interior of any rectangle."""
    return any(_segment_intersects_rect(start, goal, r) for r in rects)


def find_path(start_raw: PointLike, goal_raw: PointLike, rects: List[Rect]) -> List[Point2D]:
    """Shortest route around the keep-out rects: visibility graph + Dijkstra."""

    # Ensure all coordinates are strictly 2D to prevent math.dist crashes
    start = _to_2d(start_raw)
    goal = _to_2d(goal_raw)

    if not crosses_keepout(start, goal, rects):
        return [start, goal]

    nodes: List[Point2D] = [start, goal]
    for r in rects:
        for corner in r.corners():
            # A corner sitting inside another zone isn't a usable waypoint.
            if not any(other.contains(corner) for other in rects if other != r):
                nodes.append(corner)

    n = len(nodes)
    start_idx, goal_idx = 0, 1

    def visible(i: int, j: int) -> bool:
        return not crosses_keepout(nodes[i], nodes[j], rects)

    dist = [math.inf] * n
    prev: List[Optional[int]] = [None] * n
    visited = [False] * n

    dist[start_idx] = 0.0
    heap: List[Tuple[float, int]] = [(0.0, start_idx)]

    while heap:
        d, u = heapq.heappop(heap)
        if visited[u]:
            continue
        visited[u] = True

        if u == goal_idx:
            break

        for v in range(n):
            if v == u or visited[v] or not visible(u, v):
                continue

            nd = d + math.dist(nodes[u], nodes[v])
            if nd < dist[v]:
                dist[v] = nd
                prev[v] = u
                heapq.heappush(heap, (nd, v))

    if dist[goal_idx] == math.inf:
        raise ValueError(f"No collision-free route found from {start} to {goal}.")

    path_idx = []
    cur: Optional[int] = goal_idx
    while cur is not None:
        path_idx.append(cur)
        cur = prev[cur]
    path_idx.reverse()

    return [nodes[i] for i in path_idx]
