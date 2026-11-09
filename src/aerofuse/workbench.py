"""Labelled numerical workbench for flight and sensor telemetry.

This module keeps the convenience of a table while exposing ordinary NumPy
matrices, so results can move cleanly between Python, MATLAB, and embedded
project tooling.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
from numpy.typing import NDArray

from .models import TelemetrySample

FloatVector = NDArray[np.float64]
FloatMatrix = NDArray[np.float64]


@dataclass(frozen=True, slots=True)
class SpectralPeak:
    frequency_hz: float
    amplitude: float


@dataclass(frozen=True, slots=True)
class TelemetryMatrix:
    """A time-aligned, labelled numeric matrix.

    ``time_s`` is shape ``(n,)``; ``values`` is shape ``(n, m)``; column names
    describe each numeric column. Missing sensor readings are represented as
    ``NaN`` instead of silently being coerced to zero.
    """

    time_s: FloatVector
    values: FloatMatrix
    columns: tuple[str, ...]

    def __post_init__(self) -> None:
        time = np.asarray(self.time_s, dtype=float)
        values = np.asarray(self.values, dtype=float)
        if time.ndim != 1:
            raise ValueError("time_s must be a one-dimensional vector.")
        if values.ndim != 2 or values.shape[0] != time.size:
            raise ValueError("values must be a 2D matrix with one row per timestamp.")
        if values.shape[1] != len(self.columns):
            raise ValueError("columns must describe every matrix column.")
        if len(set(self.columns)) != len(self.columns):
            raise ValueError("column names must be unique.")
        if not np.isfinite(time).all():
            raise ValueError("time_s must contain only finite values.")
        if time.size > 1 and not np.all(np.diff(time) > 0):
            raise ValueError("time_s must be strictly increasing.")
        object.__setattr__(self, "time_s", time.copy())
        object.__setattr__(self, "values", values.copy())

    @classmethod
    def from_samples(cls, samples: Iterable[TelemetrySample]) -> "TelemetryMatrix":
        rows = list(samples)
        return cls(
            np.asarray([sample.time_s for sample in rows], dtype=float),
            np.asarray([
                [
                    np.nan if sample.vertical_acceleration_mps2 is None else sample.vertical_acceleration_mps2,
                    np.nan if sample.pressure_pa is None else sample.pressure_pa,
                    np.nan if sample.gps_altitude_m is None else sample.gps_altitude_m,
                ]
                for sample in rows
            ], dtype=float).reshape(len(rows), 3),
            ("vertical_acceleration_mps2", "pressure_pa", "gps_altitude_m"),
        )

    @property
    def shape(self) -> tuple[int, int]:
        return self.values.shape

    @property
    def duration_s(self) -> float:
        return float(self.time_s[-1] - self.time_s[0]) if self.time_s.size > 1 else 0.0

    def column(self, name: str) -> FloatVector:
        try:
            index = self.columns.index(name)
        except ValueError as exc:
            raise KeyError(f"Unknown column {name!r}. Available: {', '.join(self.columns)}") from exc
        return self.values[:, index].copy()

    def as_matrix(self, *, include_time: bool = True) -> FloatMatrix:
        """Return a standard NumPy matrix; time is the first column by default."""
        return np.column_stack((self.time_s, self.values)) if include_time else self.values.copy()

    def calibrate(self, name: str, *, scale: float = 1.0, offset: float = 0.0) -> "TelemetryMatrix":
        """Apply ``new_value = old_value × scale + offset`` to one sensor column."""
        index = self.columns.index(name)
        values = self.values.copy()
        values[:, index] = values[:, index] * scale + offset
        return TelemetryMatrix(self.time_s, values, self.columns)

    def resample(self, step_s: float) -> "TelemetryMatrix":
        """Linearly resample each finite column onto a uniform time grid."""
        if step_s <= 0:
            raise ValueError("step_s must be positive.")
        if self.time_s.size < 2:
            return self
        count = int(np.floor(self.duration_s / step_s)) + 1
        target = self.time_s[0] + np.arange(count + 1, dtype=float) * step_s
        target = target[target <= self.time_s[-1] + step_s * 1e-9]
        result = np.full((target.size, self.values.shape[1]), np.nan)
        for index in range(self.values.shape[1]):
            source = self.values[:, index]
            valid = np.isfinite(source)
            if valid.sum() >= 2:
                result[:, index] = np.interp(target, self.time_s[valid], source[valid], left=np.nan, right=np.nan)
        return TelemetryMatrix(target, result, self.columns)

    def derivative(self, name: str) -> FloatVector:
        """Central-difference derivative in the native unit per second."""
        series = self.column(name)
        valid = np.isfinite(series)
        if self.time_s.size < 2 or valid.sum() < 2:
            return np.full(self.time_s.size, np.nan)
        filled = np.interp(self.time_s, self.time_s[valid], series[valid])
        derivative = np.gradient(filled, self.time_s)
        derivative[~valid] = np.nan
        return derivative

    def integral(self, name: str) -> float:
        """Trapezoidal integral over finite contiguous observations."""
        series = self.column(name)
        valid = np.isfinite(series)
        if valid.sum() < 2:
            return float("nan")
        return float(np.trapezoid(series[valid], self.time_s[valid]))

    def moving_average(self, name: str, window: int) -> FloatVector:
        if window < 1:
            raise ValueError("window must be at least 1.")
        series = self.column(name)
        if window == 1:
            return series
        result = np.full(series.size, np.nan)
        for index in range(series.size):
            segment = series[max(0, index - window + 1):index + 1]
            finite = segment[np.isfinite(segment)]
            if finite.size:
                result[index] = finite.mean()
        return result

    def spectral_peaks(self, name: str, *, count: int = 3, minimum_frequency_hz: float = 0.0) -> list[SpectralPeak]:
        """Return dominant non-DC FFT peaks for a uniformly resampled signal."""
        if count < 1:
            raise ValueError("count must be at least 1.")
        if self.time_s.size < 4:
            return []
        dt = np.diff(self.time_s)
        if not np.allclose(dt, dt[0], rtol=1e-3, atol=1e-9):
            raise ValueError("spectral_peaks needs uniformly sampled time; call resample(step_s) first.")
        series = self.column(name)
        valid = np.isfinite(series)
        if valid.sum() < 4:
            return []
        filled = np.interp(self.time_s, self.time_s[valid], series[valid])
        centered = filled - filled.mean()
        amplitude = np.abs(np.fft.rfft(centered)) * 2 / filled.size
        frequency = np.fft.rfftfreq(filled.size, d=float(dt[0]))
        candidates = np.where(frequency >= max(minimum_frequency_hz, 1e-12))[0]
        chosen = candidates[np.argsort(amplitude[candidates])[::-1][:count]]
        return [SpectralPeak(float(frequency[index]), float(amplitude[index])) for index in chosen]

    def statistics(self, name: str) -> dict[str, float | int]:
        series = self.column(name)
        finite = series[np.isfinite(series)]
        if not finite.size:
            return {"count": 0, "missing_count": int(series.size)}
        return {
            "count": int(finite.size), "missing_count": int(series.size - finite.size),
            "minimum": float(finite.min()), "maximum": float(finite.max()),
            "mean": float(finite.mean()), "standard_deviation": float(finite.std(ddof=0)),
        }

    def to_matlab(self, path: str | Path, *, variable_name: str = "aerofuse") -> None:
        """Write a labelled matrix to MATLAB ``.mat`` format (requires ``aerofuse[matlab]``)."""
        try:
            from scipy.io import savemat
        except ImportError as exc:
            raise RuntimeError("MATLAB export needs SciPy. Install with: python -m pip install 'aerofuse[matlab]'") from exc
        savemat(Path(path), {variable_name: {"time_s": self.time_s, "values": self.values, "columns": np.asarray(self.columns, dtype=object)}})
