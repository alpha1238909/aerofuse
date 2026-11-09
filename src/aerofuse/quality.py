"""Data coverage, timing, and sensor-quality assessment."""
from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np

from .workbench import TelemetryMatrix


@dataclass(frozen=True, slots=True)
class SignalQuality:
    column: str
    coverage_percent: float
    longest_gap_s: float
    score: float
    notes: tuple[str, ...]

    def to_dict(self) -> dict:
        return asdict(self)


def assess_quality(matrix: TelemetryMatrix) -> list[SignalQuality]:
    """Score each available measurement without pretending score equals truth."""
    if not matrix.time_s.size:
        return []
    default_step = float(np.median(np.diff(matrix.time_s))) if matrix.time_s.size > 1 else 0.0
    reports: list[SignalQuality] = []
    for column in matrix.columns:
        values = matrix.column(column)
        valid = np.isfinite(values)
        coverage = 100.0 * valid.mean()
        notes: list[str] = []
        if valid.sum() < 2:
            longest_gap = matrix.duration_s
        else:
            valid_times = matrix.time_s[valid]
            gaps = np.diff(valid_times)
            longest_gap = float(gaps.max()) if gaps.size else 0.0
            if default_step and longest_gap > 5 * default_step:
                notes.append("Long telemetry gap detected.")
        if coverage < 100:
            notes.append("One or more samples are missing.")
        score = max(0.0, min(100.0, coverage - (25.0 if notes and "Long telemetry gap detected." in notes else 0.0)))
        reports.append(SignalQuality(column, float(coverage), longest_gap, score, tuple(notes)))
    return reports
