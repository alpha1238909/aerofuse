"""Predicted-versus-real trajectory comparison with evidence-based findings."""
from __future__ import annotations

import csv
import math
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

from .analysis import AnalysisReport
from .workbench import TelemetryMatrix


@dataclass(frozen=True, slots=True)
class PredictedTrajectory:
    time_s: NDArray[np.float64]
    altitude_m: NDArray[np.float64]
    vertical_velocity_mps: NDArray[np.float64]
    range_m: NDArray[np.float64] | None = None

    def __post_init__(self) -> None:
        time = np.asarray(self.time_s, dtype=float)
        altitude = np.asarray(self.altitude_m, dtype=float)
        velocity = np.asarray(self.vertical_velocity_mps, dtype=float)
        if time.ndim != 1 or altitude.shape != time.shape or velocity.shape != time.shape:
            raise ValueError("Prediction time, altitude, and velocity must be equally sized one-dimensional arrays.")
        if time.size < 2 or not np.all(np.diff(time) > 0):
            raise ValueError("Prediction needs at least two strictly increasing timestamps.")
        if not (np.isfinite(time).all() and np.isfinite(altitude).all() and np.isfinite(velocity).all()):
            raise ValueError("Prediction arrays must be finite.")
        if self.range_m is not None:
            distance = np.asarray(self.range_m, dtype=float)
            if distance.shape != time.shape or not np.isfinite(distance).all():
                raise ValueError("range_m must be finite and have the same length as time_s.")
            object.__setattr__(self, "range_m", distance)
        object.__setattr__(self, "time_s", time)
        object.__setattr__(self, "altitude_m", altitude)
        object.__setattr__(self, "vertical_velocity_mps", velocity)


@dataclass(frozen=True, slots=True)
class ComparedMetric:
    name: str
    unit: str
    actual: float | None
    predicted: float | None
    absolute_error: float | None
    percent_error: float | None


@dataclass(frozen=True, slots=True)
class ComparisonFinding:
    severity: str
    title: str
    evidence: str
    hypotheses: tuple[str, ...]


@dataclass(slots=True)
class ComparisonReport:
    metrics: list[ComparedMetric]
    altitude_rmse_m: float | None
    shared_duration_s: float | None
    findings: list[ComparisonFinding]
    actual_time_s: list[float]
    actual_altitude_m: list[float]
    predicted_time_s: list[float]
    predicted_altitude_m: list[float]

    def to_dict(self) -> dict:
        return {
            "metrics": [asdict(metric) for metric in self.metrics],
            "altitude_rmse_m": self.altitude_rmse_m,
            "shared_duration_s": self.shared_duration_s,
            "findings": [{**asdict(finding), "hypotheses": list(finding.hypotheses)} for finding in self.findings],
            "trajectories": {
                "actual": {"time_s": self.actual_time_s, "altitude_m": self.actual_altitude_m},
                "predicted": {"time_s": self.predicted_time_s, "altitude_m": self.predicted_altitude_m},
            },
        }


PREDICTION_ALIASES = {
    "time_s": ("time_s", "time", "timestamp_s", "t"),
    "altitude_m": ("altitude_m", "altitude", "height_m", "height", "z_m"),
    "vertical_velocity_mps": ("vertical_velocity_mps", "velocity_mps", "vertical_speed_mps", "vz_mps"),
    "range_m": ("range_m", "distance_m", "downrange_m", "x_m"),
}


def _column(fieldnames: list[str], name: str) -> str | None:
    normalized = {field.strip().lower(): field for field in fieldnames}
    return next((normalized[alias] for alias in PREDICTION_ALIASES[name] if alias in normalized), None)


def load_prediction_csv(path: str | Path) -> PredictedTrajectory:
    """Read a simple predicted trajectory CSV from a simulator or custom model.

    Required: ``time_s`` and ``altitude_m`` (common aliases accepted). Velocity
    is optional and calculated from altitude when absent. ``range_m`` is optional.
    """
    with Path(path).open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise ValueError("Predicted trajectory CSV needs a header row.")
        headings = {name: _column(reader.fieldnames, name) for name in PREDICTION_ALIASES}
        if headings["time_s"] is None or headings["altitude_m"] is None:
            raise ValueError("Prediction CSV requires time_s and altitude_m columns.")
        rows = list(reader)
    def extract(name: str) -> np.ndarray | None:
        heading = headings[name]
        if heading is None:
            return None
        try:
            return np.asarray([float(row[heading]) for row in rows], dtype=float)
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"Prediction column {heading!r} contains a non-numeric value.") from exc
    time = extract("time_s")
    altitude = extract("altitude_m")
    velocity = extract("vertical_velocity_mps")
    if velocity is None:
        if time is None or altitude is None or time.size < 2:
            raise ValueError("Prediction needs at least two rows to calculate velocity.")
        velocity = np.gradient(altitude, time)
    return PredictedTrajectory(time, altitude, velocity, extract("range_m"))


def _metric(name: str, unit: str, actual: float | None, predicted: float | None) -> ComparedMetric:
    if actual is None or predicted is None:
        return ComparedMetric(name, unit, actual, predicted, None, None)
    error = actual - predicted
    percentage = None if abs(predicted) < 1e-12 else 100 * error / abs(predicted)
    return ComparedMetric(name, unit, actual, predicted, error, percentage)


def _gps_range_m(matrix: TelemetryMatrix) -> float | None:
    required = {"gps_latitude_deg", "gps_longitude_deg"}
    if not required.issubset(matrix.columns):
        return None
    latitude = matrix.column("gps_latitude_deg")
    longitude = matrix.column("gps_longitude_deg")
    valid = np.isfinite(latitude) & np.isfinite(longitude)
    if valid.sum() < 2:
        return None
    first, last = np.flatnonzero(valid)[[0, -1]]
    radius = 6_371_000.0
    lat1, lat2 = np.radians([latitude[first], latitude[last]])
    delta_lat = lat2 - lat1
    delta_lon = np.radians(longitude[last] - longitude[first])
    h = math.sin(delta_lat / 2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(delta_lon / 2)**2
    return float(2 * radius * math.asin(math.sqrt(h)))


def compare(real: AnalysisReport, matrix: TelemetryMatrix, predicted: PredictedTrajectory) -> ComparisonReport:
    """Compare a real analysed log with a model trajectory without overclaiming causes."""
    states = real.fusion.states
    if len(states) < 2:
        raise ValueError("Real analysis needs at least two state estimates for comparison.")
    launch = next((event.time_s for event in real.fusion.events if event.name == "launch"), states[0].time_s)
    post_launch = [state for state in states if state.time_s >= launch]
    if len(post_launch) < 2:
        raise ValueError("Real analysis does not contain enough post-launch estimates for comparison.")
    actual_time = np.asarray([state.time_s - launch for state in post_launch], dtype=float)
    actual_altitude = np.asarray([state.altitude_m for state in post_launch], dtype=float)
    actual_velocity = np.asarray([state.vertical_velocity_mps for state in post_launch], dtype=float)
    predicted_time = predicted.time_s - predicted.time_s[0]
    shared_duration = min(float(actual_time[-1]), float(predicted_time[-1]))
    rmse = None
    if shared_duration > 0:
        grid = np.linspace(0.0, shared_duration, min(250, max(2, int(shared_duration / 0.02))))
        real_grid = np.interp(grid, actual_time, actual_altitude)
        predicted_grid = np.interp(grid, predicted_time, predicted.altitude_m)
        rmse = float(np.sqrt(np.mean((real_grid - predicted_grid) ** 2)))
    actual_apogee = float(actual_altitude.max())
    predicted_apogee = float(predicted.altitude_m.max())
    actual_apogee_time = float(actual_time[np.argmax(actual_altitude)])
    predicted_apogee_time = float(predicted_time[np.argmax(predicted.altitude_m)])
    actual_range = _gps_range_m(matrix)
    predicted_range = None if predicted.range_m is None else float(predicted.range_m[-1] - predicted.range_m[0])
    metrics = [
        _metric("apogee", "m", actual_apogee, predicted_apogee),
        _metric("time_to_apogee", "s", actual_apogee_time, predicted_apogee_time),
        _metric("peak_vertical_speed", "m/s", float(np.max(np.abs(actual_velocity))), float(np.max(np.abs(predicted.vertical_velocity_mps)))),
        _metric("ground_range", "m", actual_range, predicted_range),
    ]
    findings: list[ComparisonFinding] = []
    apogee = metrics[0]
    if apogee.percent_error is not None and abs(apogee.percent_error) >= 10:
        direction = "lower" if apogee.percent_error < 0 else "higher"
        hypotheses = ("actual mass, drag coefficient, and motor thrust differed from the model", "wind or launch-rail angle affected the real flight", "barometer baseline or accelerometer calibration should be reviewed")
        findings.append(ComparisonFinding("warning", f"Actual apogee was {abs(apogee.percent_error):.1f}% {direction} than predicted.", "Difference exceeds the 10% comparison threshold.", hypotheses))
    if rmse is not None and rmse > max(5.0, predicted_apogee * 0.1):
        findings.append(ComparisonFinding("warning", "Altitude trajectories diverged materially during shared flight time.", f"Altitude RMSE was {rmse:.2f} m over {shared_duration:.2f} s.", ("compare thrust curve and vehicle mass", "review drag and wind assumptions", "check timing alignment and sensor quality")))
    if actual_range is None:
        findings.append(ComparisonFinding("info", "Ground-range comparison was skipped.", "The real log does not contain at least two valid GPS latitude/longitude readings.", ("add GPS latitude and longitude columns to compare landing distance",)))
    quality_issues = [item.column for item in real.quality if item.score < 75]
    if quality_issues:
        findings.append(ComparisonFinding("info", "Some real signals have limited coverage.", f"Quality score below 75 for: {', '.join(quality_issues)}.", ("treat mismatch explanations as hypotheses until the data gaps are resolved",)))
    if not findings:
        findings.append(ComparisonFinding("info", "No large mismatch was found by the current thresholds.", "AeroFuse comparison checks did not find a >10% apogee difference or high altitude RMSE.", ("validate with more than one real flight before tuning the physical model",)))
    return ComparisonReport(metrics, rmse, shared_duration if shared_duration > 0 else None, findings, actual_time.tolist(), actual_altitude.tolist(), predicted_time.tolist(), predicted.altitude_m.tolist())
