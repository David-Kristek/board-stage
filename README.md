# board_stage

Generic Ender 3 XY(Z) positioning library: raw motion, board-frame calibration, and obstacle-avoiding routing between named board objects.

## Features

- **Printer abstraction (`printer.py`)**: Serial communication with Ender 3, coordinate transformations between Base, Printer, and Board frames.
- **Board & Object configuration (`board_config.py`)**: Define physical board objects (samples, tubes, wash stations) and action points.
- **Board Controller (`board.py`)**: High-level movement orchestration, event publishing, and safety checks.
- **Path Planning (`path_planning.py`)**: A* grid routing with obstacle avoidance across defined board objects.
- **Simulation (`sim.py`, `visualize.py`)**: Dry-run execution and Matplotlib visualization of planned paths.

## Installation

```bash
pip install -e .
```

Or using `uv`:

```bash
uv add --path ../board-stage board-stage
```
