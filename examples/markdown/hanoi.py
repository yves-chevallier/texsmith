from __future__ import annotations

from collections.abc import Iterable


Move = tuple[int, str, str]


def tower_of_hanoi(n: int, source: str, destination: str, auxiliary: str) -> list[Move]:
    """Compute the move sequence for the Tower of Hanoi puzzle."""
    moves: list[Move] = []

    def _solve(disks: int, start: str, end: str, spare: str) -> None:
        if disks == 0:
            return
        _solve(disks - 1, start, spare, end)
        moves.append((disks, start, end))
        _solve(disks - 1, spare, end, start)

    _solve(n, source, destination, auxiliary)
    return moves


def render_solution(moves: Iterable[Move]) -> str:
    """Return a human-readable description of the move sequence."""
    return "\n".join(
        f"Move disk {disk} from source {start} to destination {end}" for disk, start, end in moves
    )
