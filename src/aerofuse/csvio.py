"""Conservative CSV import that accepts common Arduino and ESP32 headings."""
from __future__ import annotations

import csv
from collections.abc import Iterator
from pathlib import Path

import numpy as np

from .models import TelemetrySample
from .workbench import TelemetryMatrix

ALIASES: dict[str, tuple[str, ...]] = {
    "time_s": ("time_s", "time", "timestamp_s", "seconds", "t", "time_ms", "timestamp_ms", "time_boot_ms", "time_us", "timestamp_us", "timeus"),
    "acceleration_x_mps2": ("acceleration_x_mps2", "ax_mps2", "accel_x_mps2", "ax", "acc_x"),
    "acceleration_y_mps2": ("acceleration_y_mps2", "ay_mps2", "accel_y_mps2", "ay", "acc_y"),
    "vertical_acceleration_mps2": ("vertical_acceleration_mps2", "az_mps2", "accel_z_mps2", "az", "acc_z"),
    "gyro_x_dps": ("gyro_x_dps", "gx_dps", "gyro_x", "gx"),
    "gyro_y_dps": ("gyro_y_dps", "gy_dps", "gyro_y", "gy"),
    "gyro_z_dps": ("gyro_z_dps", "gz_dps", "gyro_z", "gz"),
    "magnetic_x_ut": ("magnetic_x_ut", "mx_ut", "mag_x_ut", "mx"),
    "magnetic_y_ut": ("magnetic_y_ut", "my_ut", "mag_y_ut", "my"),
    "magnetic_z_ut": ("magnetic_z_ut", "mz_ut", "mag_z_ut", "mz"),
    "pressure_pa": ("pressure_pa", "pressure", "baro_pa", "bmp_pressure"),
    "temperature_c": ("temperature_c", "temp_c", "temperature", "temp"),
    "humidity_percent": ("humidity_percent", "humidity_pct", "humidity", "rh_percent"),
    "gps_latitude_deg": ("gps_latitude_deg", "latitude_deg", "latitude", "lat"),
    "gps_longitude_deg": ("gps_longitude_deg", "longitude_deg", "longitude", "lon", "lng"),
    "gps_altitude_m": ("gps_altitude_m", "gps_alt_m", "altitude_gps_m"),
    "gps_speed_mps": ("gps_speed_mps", "gps_speed", "ground_speed_mps", "speed_mps"),
    "voltage_v": ("voltage_v", "bus_voltage_v", "battery_voltage_v", "voltage"),
    "current_a": ("current_a", "current_ma", "current"),
    "battery_percent": ("battery_percent", "battery_pct", "soc_percent"),
    "distance_m": ("distance_m", "range_m", "distance_cm", "range_cm"),
    "turbidity_ntu": ("turbidity_ntu", "ntu", "turbidity"),
}


def _find_heading(fieldnames: list[str], field: str) -> str | None:
    normalized = {name.strip().lower(): name for name in fieldnames}
    return next((normalized[name] for name in ALIASES[field] if name in normalized), None)


def _time_scale(heading: str) -> float:
    """Normalize common exported millisecond/microsecond clocks to seconds."""
    normalized = heading.strip().lower().replace("_", "")
    if normalized.endswith("us"):
        return 1e-6
    if normalized.endswith("ms"):
        return 1e-3
    return 1.0


def load_matrix_csv(path: str | Path, *, acceleration_unit: str = "mps2") -> TelemetryMatrix:
    """Import every recognised optional sensor column into one labelled matrix.

    ``acceleration_unit`` is ``mps2`` by default. Use ``g`` for logs whose
    accelerometer axes are expressed in gravitational units. Optional sensor
    columns are preserved when present and silently skipped when absent.
    """
    if acceleration_unit not in {"mps2", "g"}:
        raise ValueError("acceleration_unit must be 'mps2' or 'g'.")
    with Path(path).open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise ValueError("CSV needs a header row.")
        names = {key: _find_heading(reader.fieldnames, key) for key in ALIASES}
        if names["time_s"] is None:
            raise ValueError(f"Could not find time column. Supported headings: {', '.join(ALIASES['time_s'])}")
        columns = tuple(name for name in ALIASES if name != "time_s" and names[name] is not None)
        times: list[float] = []
        rows: list[list[float]] = []
        for row_number, row in enumerate(reader, start=2):
            try:
                def number(key: str) -> float:
                    heading = names[key]
                    raw = row.get(heading, "") if heading else ""
                    return float(raw) if raw and raw.strip() else float("nan")
                time_s = number("time_s") * _time_scale(names["time_s"] or "")
                if not np.isfinite(time_s):
                    raise ValueError("time column is empty.")
                values = []
                for column in columns:
                    measurement = number(column)
                    if acceleration_unit == "g" and column in {"acceleration_x_mps2", "acceleration_y_mps2", "vertical_acceleration_mps2"}:
                        measurement *= 9.80665
                    if column == "current_a" and names[column] and names[column].strip().lower() == "current_ma":
                        measurement /= 1000
                    if column == "distance_m" and names[column] and names[column].strip().lower() in {"distance_cm", "range_cm"}:
                        measurement /= 100
                    values.append(measurement)
                times.append(time_s)
                rows.append(values)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"Invalid numeric value on CSV row {row_number}.") from exc
    return TelemetryMatrix(np.asarray(times, dtype=float), np.asarray(rows, dtype=float).reshape(len(rows), len(columns)), columns)


def load_csv(path: str | Path, *, acceleration_unit: str = "mps2") -> Iterator[TelemetrySample]:
    """Yield the fusion-relevant subset of a sensor CSV for backwards compatibility."""
    matrix = load_matrix_csv(path, acceleration_unit=acceleration_unit)
    index = {name: position for position, name in enumerate(matrix.columns)}

    def measurement(row: int, name: str) -> float | None:
        position = index.get(name)
        return None if position is None else float(matrix.values[row, position])

    for row, time_s in enumerate(matrix.time_s):
        yield TelemetrySample(float(time_s), measurement(row, "vertical_acceleration_mps2"), measurement(row, "pressure_pa"), measurement(row, "gps_altitude_m"))
