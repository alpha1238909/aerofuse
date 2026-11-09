"""Optional sensor capability detection for a telemetry matrix.

Profiles describe available measurements, not a claim that a physical device is
present. A project may use any subset of the columns without breaking analysis.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

from .workbench import TelemetryMatrix


@dataclass(frozen=True, slots=True)
class SensorProfile:
    name: str
    required_columns: frozenset[str]
    optional_columns: frozenset[str] = frozenset()
    purpose: str = ""


@dataclass(frozen=True, slots=True)
class SensorStatus:
    name: str
    available: bool
    used_columns: tuple[str, ...]
    skipped_columns: tuple[str, ...]
    purpose: str

    def to_dict(self) -> dict:
        return asdict(self)


SENSOR_PROFILES: tuple[SensorProfile, ...] = (
    SensorProfile(
        "vertical accelerometer",
        frozenset({"vertical_acceleration_mps2"}),
        purpose="One-axis motion, event detection, and vertical-state estimation.",
    ),
    SensorProfile(
        "3-axis accelerometer",
        frozenset({"acceleration_x_mps2", "acceleration_y_mps2", "vertical_acceleration_mps2"}),
        purpose="Linear acceleration, vibration, and motion analysis.",
    ),
    SensorProfile(
        "6-axis IMU (MPU6050/ICM20602-style)",
        frozenset({"acceleration_x_mps2", "acceleration_y_mps2", "vertical_acceleration_mps2", "gyro_x_dps", "gyro_y_dps", "gyro_z_dps"}),
        purpose="Acceleration and angular-rate analysis; orientation fusion is a future backend.",
    ),
    SensorProfile(
        "3-axis magnetometer (HMC5883L/QMC5883L-style)",
        frozenset({"magnetic_x_ut", "magnetic_y_ut", "magnetic_z_ut"}),
        purpose="Heading and magnetic-field analysis.",
    ),
    SensorProfile(
        "barometer (BMP280/BME280-style)",
        frozenset({"pressure_pa"}),
        frozenset({"temperature_c", "humidity_percent"}),
        "Relative altitude and atmospheric measurements.",
    ),
    SensorProfile(
        "GPS (NEO-6M-style)",
        frozenset({"gps_latitude_deg", "gps_longitude_deg"}),
        frozenset({"gps_altitude_m", "gps_speed_mps"}),
        "Position, speed, and independent altitude reference.",
    ),
    SensorProfile(
        "battery monitor (INA219/INA226-style)",
        frozenset({"voltage_v"}),
        frozenset({"current_a", "battery_percent"}),
        "Power consumption and battery-health analysis.",
    ),
    SensorProfile(
        "rangefinder (HC-SR04/ToF-style)",
        frozenset({"distance_m"}),
        purpose="Near-ground or obstacle-distance telemetry.",
    ),
    SensorProfile(
        "turbidity sensor",
        frozenset({"turbidity_ntu"}),
        purpose="Water-quality readings for environmental and rover projects.",
    ),
)


def inspect_sensors(matrix: TelemetryMatrix) -> list[SensorStatus]:
    """Report which optional sensor capabilities a log can actually support."""
    present = set(matrix.columns)
    statuses: list[SensorStatus] = []
    for profile in SENSOR_PROFILES:
        used = tuple(sorted(profile.required_columns & present))
        optional_used = tuple(sorted(profile.optional_columns & present))
        statuses.append(SensorStatus(
            name=profile.name,
            available=profile.required_columns.issubset(present),
            used_columns=used + optional_used,
            skipped_columns=tuple(sorted((profile.required_columns | profile.optional_columns) - present)),
            purpose=profile.purpose,
        ))
    return statuses
