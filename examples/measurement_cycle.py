"""
Brass-sample measurement cycle for an Ender 3 (inspired by
run_measurement_cycle.py). No ENDER_PORT -> replays the cycle on a NullPrinter
and animates it; set ENDER_PORT to drive a real printer.

    python examples/measurement_cycle.py
    ENDER_PORT=COM3 python examples/measurement_cycle.py
"""

import os
import random

from board_stage import (
    Board,
    BoardConfig,
    BoardObject,
    BoardPoint,
    Ender3_printer,
    GridAction,
    Pen,
    PrinterPoint,
    SinglePointAction,
    dry_run,
    setup_board,
)

brass_action = GridAction(start=BoardPoint(x=5.0, y=30.0), end=BoardPoint(x=95.0, y=30.0), steps=10, z=1.0)

board_config = BoardConfig(
    pen=Pen(width=2.0),
    objects={
        "solution": BoardObject(
            id="solution",
            x=0.0,
            y=0.0,
            width=40.0,
            height=40.0,
            safe_z=55.0,
            margin=5.0,
            default_action=SinglePointAction(point=BoardPoint(x=25.0, y=25.0, z=23.0)),
        ),
        "dryer": BoardObject(
            id="dryer",
            x=55.0,
            y=0.0,
            width=30.0,
            height=55.0,
            safe_z=15.0,
            default_action=SinglePointAction(point=BoardPoint(x=15.0, y=50.0, z=6.0)),
        ),
        "brass": BoardObject(
            id="brass",
            x=130.0,
            y=9.0,
            width=99.0,
            height=65.0,
            safe_z=10.0,
            actions=[brass_action],
        ),
    },
)


def cycle(printer, board: Board) -> None:
    """Dip, air-dry twice, then measure at every brass point."""
    board.park()

    dryer = board.objects["dryer"]
    for i in range(len(board.objects["brass"].local_action_points)):
        with board.at("solution"):
            pass
        for _ in range(2):
            # random point in the top-centre of the dryer
            x = random.uniform(dryer.width / 2 - 5, dryer.width / 2 + 5)
            y = random.uniform(dryer.height - 10, dryer.height - 5)
            with board.at("dryer", coords=(x, y)):
                pass
        with board.at("brass", action_index=i):
            pass  # run the measurement here


def main() -> None:
    port = os.environ.get("ENDER_PORT")

    if port:
        printer = Ender3_printer(port, origin=PrinterPoint(6.0, -14.0, 13.0))
        with Board(printer, board_config) as board:
            setup_board(board)
            cycle(printer, board)
            board.park()
        return

    board = dry_run(board_config, cycle, bed_width=230)
    try:
        from board_stage.visualize import animate
    except ImportError:
        print("Install the plot extra to animate: pip install -e '.[plot]'")
        return
    animate(board.printer.history, board, board.printer, highlight_id="brass")


if __name__ == "__main__":
    main()
