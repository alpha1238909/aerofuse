"""Stationary-period calibration for affordable student sensors."""
from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np

from .workbench import TelemetryMatrix


ACCEL_COLUMNS = ("acceleration_x_mps2", "acceleration_y_mps2", "vertical_acceleration_mps2")
GYRO_COLUMNS = ("gyro_x_dps", "gyro_y_dps", "gyro_z_dps")


@dataclass(frozen=True, slots=True)
class CalibrationResult:
    stationary_sample_count: int
    acceleration_bias_mps2: dict[str, float]
    gyroscope_bias_dps: dict[str, float]
    baseline_pressure_pa: float | None
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return asdict(self)


def estimate_calibration(matrix: TelemetryMatrix, *, duration_s: float = 2.0, gravity_mps2: float = 9.80665) -> CalibrationResult:
    """Estimate sensor offsets from the first stationary portion of a log.

    The method assumes an upright sensor at rest should read ``[0, 0, +g]`` and
    zero angular rate. It reports warnings rather than silently applying an
    unsafe assumption when the necessary sensor fields are absent.
    """
    if duration_s <= 0:
        raise ValueError("duration_s must be positive.")
    window = matrix.time_s <= matrix.time_s[0] + duration_s if matrix.time_s.size else np.asarray([], dtype=bool)
    warnings: list[str] = []
    acceleration_bias: dict[str, float] = {}
    gyro_bias: dict[str, float] = {}
    expected = {"acceleration_x_mps2": 0.0, "acceleration_y_mps2": 0.0, "vertical_acceleration_mps2": gravity_mps2}
    sample_count = 0
    for name in ACCEL_COLUMNS:
        if name not in matrix.columns:
            continue
        values = matrix.column(name)[window]
        values = values[np.isfinite(values)]
        if values.size:
            sample_count = max(sample_count, int(values.size))
            acceleration_bias[name] = float(values.mean() - expected[name])
    for name in GYRO_COLUMNS:
        if name not in matrix.columns:
            continue
        values = matrix.column(name)[window]
        values = values[np.isfinite(values)]
        if values.size:
            sample_count = max(sample_count, int(values.size))
            gyro_bias[name] = float(values.mean())
    baseline_pressure = None
    if "pressure_pa" in matrix.columns:
        pressure = matrix.column("pressure_pa")[window]
        pressure = pressure[np.isfinite(pressure) & (pressure > 0)]
        if pressure.size:
            baseline_pressure = float(np.median(pressure))
    if not acceleration_bias:
        warnings.append("No accelerometer axis was available for stationary calibration.")
    if not gyro_bias:
        warnings.append("No gyroscope axis was available for stationary calibration.")
    if baseline_pressure is None:
        warnings.append("No valid pressure readings were available for baseline calibration.")
    if sample_count < 5:
        warnings.append("Calibration is based on fewer than five readings; collect a longer stationary baseline.")
    return CalibrationResult(sample_count, acceleration_bias, gyro_bias, baseline_pressure, tuple(warnings))


def apply_calibration(matrix: TelemetryMatrix, calibration: CalibrationResult) -> TelemetryMatrix:
    """Return a calibrated copy; raw data remains unchanged in the source matrix."""
    values = matrix.values.copy()
    index = {name: position for position, name in enumerate(matrix.columns)}
    for name, bias in {**calibration.acceleration_bias_mps2, **calibration.gyroscope_bias_dps}.items():
        if name in index:
            values[:, index[name]] -= bias
    return TelemetryMatrix(matrix.time_s, values, matrix.columns)
