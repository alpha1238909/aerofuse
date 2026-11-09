"""Dependency-free complementary attitude estimator for 6-axis IMU logs."""
from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np

from .workbench import TelemetryMatrix


@dataclass(frozen=True, slots=True)
class AttitudeConfig:
    accelerometer_gain: float = 1.6
    gravity_mps2: float = 9.80665
    maximum_timestep_s: float = 0.25


@dataclass(frozen=True, slots=True)
class AttitudeState:
    time_s: float
    roll_deg: float
    pitch_deg: float
    yaw_deg: float
    world_acceleration_mps2: tuple[float, float, float]


@dataclass(slots=True)
class AttitudeReport:
    states: list[AttitudeState]
    method: str = "6-axis complementary quaternion filter"

    def to_dict(self) -> dict:
        return {"method": self.method, "states": [asdict(state) for state in self.states]}


REQUIRED_COLUMNS = frozenset({"acceleration_x_mps2", "acceleration_y_mps2", "vertical_acceleration_mps2", "gyro_x_dps", "gyro_y_dps", "gyro_z_dps"})


def _normalize(quaternion: np.ndarray) -> np.ndarray:
    magnitude = np.linalg.norm(quaternion)
    return quaternion / magnitude if magnitude else np.asarray([1.0, 0.0, 0.0, 0.0])


def _multiply(left: np.ndarray, right: np.ndarray) -> np.ndarray:
    w1, x1, y1, z1 = left
    w2, x2, y2, z2 = right
    return np.asarray([w1*w2 - x1*x2 - y1*y2 - z1*z2, w1*x2 + x1*w2 + y1*z2 - z1*y2, w1*y2 - x1*z2 + y1*w2 + z1*x2, w1*z2 + x1*y2 - y1*x2 + z1*w2])


def _rotate(quaternion: np.ndarray, vector: np.ndarray) -> np.ndarray:
    return _multiply(_multiply(quaternion, np.asarray([0.0, *vector])), np.asarray([quaternion[0], -quaternion[1], -quaternion[2], -quaternion[3]]))[1:]


def _euler_degrees(quaternion: np.ndarray) -> tuple[float, float, float]:
    w, x, y, z = quaternion
    roll = np.arctan2(2*(w*x + y*z), 1 - 2*(x*x + y*y))
    pitch = np.arcsin(np.clip(2*(w*y - z*x), -1.0, 1.0))
    yaw = np.arctan2(2*(w*z + x*y), 1 - 2*(y*y + z*z))
    return tuple(float(np.degrees(value)) for value in (roll, pitch, yaw))


def estimate_attitude(matrix: TelemetryMatrix, config: AttitudeConfig | None = None) -> AttitudeReport:
    """Estimate orientation from acceleration and angular-rate columns.

    Magnetometer data remains available to the matrix but is deliberately not
    forced into this first complementary filter, because uncalibrated magnetic
    readings easily make yaw less reliable than gyro integration alone.
    """
    missing = REQUIRED_COLUMNS - set(matrix.columns)
    if missing:
        raise ValueError(f"3D attitude needs these columns: {', '.join(sorted(missing))}")
    cfg = config or AttitudeConfig()
    q = np.asarray([1.0, 0.0, 0.0, 0.0])  # body -> world
    states: list[AttitudeState] = []
    ax, ay, az = (matrix.column(name) for name in ("acceleration_x_mps2", "acceleration_y_mps2", "vertical_acceleration_mps2"))
    gx, gy, gz = (matrix.column(name) for name in ("gyro_x_dps", "gyro_y_dps", "gyro_z_dps"))
    for index, time_s in enumerate(matrix.time_s):
        dt = 0.0 if index == 0 else float(matrix.time_s[index] - matrix.time_s[index - 1])
        if dt > cfg.maximum_timestep_s:
            dt = 0.0
        acceleration = np.asarray([ax[index], ay[index], az[index]])
        gyro = np.radians(np.asarray([gx[index], gy[index], gz[index]]))
        if np.isfinite(acceleration).all() and np.linalg.norm(acceleration) > 1e-9:
            measured_gravity = acceleration / np.linalg.norm(acceleration)
            conjugate = np.asarray([q[0], -q[1], -q[2], -q[3]])
            expected_gravity = _rotate(conjugate, np.asarray([0.0, 0.0, 1.0]))
            gyro += cfg.accelerometer_gain * np.cross(measured_gravity, expected_gravity)
        if np.isfinite(gyro).all() and dt:
            q = _normalize(q + 0.5 * _multiply(q, np.asarray([0.0, *gyro])) * dt)
        world_acceleration = _rotate(q, acceleration) - np.asarray([0.0, 0.0, cfg.gravity_mps2]) if np.isfinite(acceleration).all() else np.asarray([np.nan, np.nan, np.nan])
        roll, pitch, yaw = _euler_degrees(q)
        states.append(AttitudeState(float(time_s), roll, pitch, yaw, tuple(float(value) for value in world_acceleration)))
    return AttitudeReport(states)
