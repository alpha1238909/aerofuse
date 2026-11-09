"""Stable public data models for AeroFuse."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
import math
from typing import Any


class FlightPhase(str, Enum):
    PAD = "pad"
    ASCENT = "ascent"
    COAST = "coast"
    DESCENT = "descent"
    LANDED = "landed"


@dataclass(frozen=True, slots=True)
class TelemetrySample:
    """One time-aligned telemetry observation.

    ``vertical_acceleration_mps2`` is the upward accelerometer reading *including
    gravity*; a stationary, upright sensor therefore measures approximately +9.81.
    Pressure is optional, but barometric altitude is much more stable than inertial
    integration alone for all but very short intervals.
    """

    time_s: float
    vertical_acceleration_mps2: float | None = None
    pressure_pa: float | None = None
    gps_altitude_m: float | None = None

    def __post_init__(self) -> None:
        if not math.isfinite(self.time_s):
            raise ValueError("time_s must be finite.")


@dataclass(frozen=True, slots=True)
class FusionConfig:
    """Tunable, deliberately understandable parameters for the 1D fusion model."""

    gravity_mps2: float = 9.80665
    barometer_gain: float = 0.16
    velocity_gain: float = 0.035
    launch_acceleration_mps2: float = 7.0
    launch_confirm_samples: int = 3
    landing_speed_mps: float = 1.5
    maximum_gap_s: float = 1.5

    def __post_init__(self) -> None:
        if not 0 < self.barometer_gain <= 1:
            raise ValueError("barometer_gain must be in (0, 1].")
        if not 0 <= self.velocity_gain <= 1:
            raise ValueError("velocity_gain must be in [0, 1].")
        if self.launch_confirm_samples < 1:
            raise ValueError("launch_confirm_samples must be at least one.")
        if self.maximum_gap_s <= 0:
            raise ValueError("maximum_gap_s must be positive.")


@dataclass(frozen=True, slots=True)
class StateEstimate:
    time_s: float
    altitude_m: float
    vertical_velocity_mps: float
    phase: FlightPhase
    barometric_altitude_m: float | None


@dataclass(frozen=True, slots=True)
class Event:
    name: str
    time_s: float
    confidence: float
    details: str


@dataclass(frozen=True, slots=True)
class Anomaly:
    code: str
    time_s: float
    details: str
    severity: str = "warning"


@dataclass(slots=True)
class FusionReport:
    states: list[StateEstimate]
    events: list[Event]
    anomalies: list[Anomaly]
    baseline_pressure_pa: float | None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def apogee_m(self) -> float | None:
        return max((state.altitude_m for state in self.states), default=None)

    @property
    def flight_time_s(self) -> float | None:
        if not self.states:
            return None
        return self.states[-1].time_s - self.states[0].time_s

    @property
    def max_absolute_vertical_velocity_mps(self) -> float | None:
        return max((abs(state.vertical_velocity_mps) for state in self.states), default=None)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "1.1.0",
            "summary": {
                "apogee_m": self.apogee_m,
                "flight_time_s": self.flight_time_s,
                "max_absolute_vertical_velocity_mps": self.max_absolute_vertical_velocity_mps,
                "events_detected": [event.name for event in self.events],
            },
            "baseline_pressure_pa": self.baseline_pressure_pa,
            "events": [asdict(event) for event in self.events],
            "anomalies": [asdict(anomaly) for anomaly in self.anomalies],
            "states": [{**asdict(state), "phase": state.phase.value} for state in self.states],
            "metadata": self.metadata,
        }
