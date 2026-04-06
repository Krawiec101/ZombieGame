from __future__ import annotations


def interpolate_points(
    start: tuple[float, float],
    end: tuple[float, float],
    progress: float,
) -> tuple[float, float]:
    clamped_progress = min(max(progress, 0.0), 1.0)
    return (
        start[0] + (end[0] - start[0]) * clamped_progress,
        start[1] + (end[1] - start[1]) * clamped_progress,
    )

