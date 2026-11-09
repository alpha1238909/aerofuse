"""A transparent, dependency-free 1D barometric/inertial fusion engine."""
from __future__ import annotations

import math
from collections.abc import Iterable

from .models import Anomaly, Event, FlightPhase, FusionConfig, FusionReport, StateEstimate, TelemetrySample


def pressure_to_altitude_m(pressure_pa: float, sea_level_pressure_pa: float) -> float:
    """Calculate relative barometric altitude using the ISA approximation."""
    if pressure_pa <= 0 or sea_level_pressure_pa <= 0:
        raise ValueError("Pressure values must be positive.")
    return 44_330.0 * (1.0 - (pressure_pa / sea_level_pressure_pa) ** 0.190294957)


def fuse(samples: Iterable[TelemetrySample], config: FusionConfig | None = None) -> FusionReport:
    """Fuse a chronological telemetry sequence into vertical state estimates.

    This is an alpha-beta observer, not a black-box claim of perfect precision.
    It is intentionally small enough to audit, tune, and port to MicroPython/C++.
    """
    cfg = config or FusionConfig()
    ordered = list(samples)
    anomalies: list[Anomaly] = []
    events: list[Event] = []
    states: list[StateEstimate] = []
    if not ordered:
        return FusionReport(states, events, anomalies, None)

    baseline = next((sample.pressure_pa for sample in ordered if sample.pressure_pa is not None and math.isfinite(sample.pressure_pa) and sample.pressure_pa > 0), None)
    altitude = 0.0
    velocity = 0.0
    phase = FlightPhase.PAD
    previous_time: float | None = None
    launch_streak = 0
    coast_seen = False
    apogee_seen = False

    for sample in ordered:
        if previous_time is not None and sample.time_s <= previous_time:
            anomalies.append(Anomaly("NON_MONOTONIC_TIME", sample.time_s, "Sample ignored because timestamps must increase.", "error"))
            continue
        dt = 0.0 if previous_time is None else sample.time_s - previous_time
        if dt > cfg.maximum_gap_s:
            anomalies.append(Anomaly("TELEMETRY_GAP", sample.time_s, f"Gap of {dt:.3f} s exceeds configured maximum."))
        previous_time = sample.time_s

        acceleration = None
        if sample.vertical_acceleration_mps2 is not None and math.isfinite(sample.vertical_acceleration_mps2):
            acceleration = sample.vertical_acceleration_mps2 - cfg.gravity_mps2
            altitude += velocity * dt + 0.5 * acceleration * dt * dt
            velocity += acceleration * dt
        elif sample.vertical_acceleration_mps2 is not None:
            anomalies.append(Anomaly("INVALID_ACCELERATION", sample.time_s, "Vertical acceleration is not finite."))

        barometric_altitude = None
        if baseline is not None and sample.pressure_pa is not None and math.isfinite(sample.pressure_pa) and sample.pressure_pa > 0:
            barometric_altitude = pressure_to_altitude_m(sample.pressure_pa, baseline)
            residual = barometric_altitude - altitude
            altitude += cfg.barometer_gain * residual
            if dt > 0:
                velocity += cfg.velocity_gain * residual / dt
        elif sample.pressure_pa is not None and (not math.isfinite(sample.pressure_pa) or sample.pressure_pa <= 0):
            anomalies.append(Anomaly("INVALID_PRESSURE", sample.time_s, "Pressure must be finite and positive."))

        if sample.vertical_acceleration_mps2 is None and sample.pressure_pa is None and sample.gps_altitude_m is None:
            anomalies.append(Anomaly("EMPTY_SAMPLE", sample.time_s, "No usable sensor measurement was supplied.", "info"))
        if sample.gps_altitude_m is not None and not math.isfinite(sample.gps_altitude_m):
            anomalies.append(Anomaly("INVALID_GPS_ALTITUDE", sample.time_s, "GPS altitude is not finite."))
        if sample.pressure_pa is not None and not 30_000 <= sample.pressure_pa <= 120_000:
            anomalies.append(Anomaly("IMPLAUSIBLE_PRESSURE", sample.time_s, f"Pressure {sample.pressure_pa:.1f} Pa is outside expected surface range."))

        if phase is FlightPhase.PAD and acceleration is not None:
            launch_streak = launch_streak + 1 if acceleration >= cfg.launch_acceleration_mps2 else 0
            if launch_streak >= cfg.launch_confirm_samples:
                phase = FlightPhase.ASCENT
                events.append(Event("launch", sample.time_s, min(1.0, launch_streak / (cfg.launch_confirm_samples + 1)), "Sustained upward net acceleration detected."))
        elif phase is FlightPhase.ASCENT and acceleration is not None and acceleration < -1.0:
            phase = FlightPhase.COAST
            coast_seen = True
            events.append(Event("burnout", sample.time_s, 0.72, "Acceleration fell below gravity-compensated coast threshold."))
        elif phase in (FlightPhase.ASCENT, FlightPhase.COAST) and velocity < 0 and not apogee_seen:
            phase = FlightPhase.DESCENT
            apogee_seen = True
            events.append(Event("apogee", sample.time_s, 0.78 if coast_seen else 0.58, "Estimated vertical velocity crossed downward."))
        elif phase is FlightPhase.DESCENT and abs(velocity) <= cfg.landing_speed_mps and barometric_altitude is not None and barometric_altitude < 3:
            phase = FlightPhase.LANDED
            events.append(Event("landing", sample.time_s, 0.54, "Low estimated speed and near-baseline barometric altitude."))

        states.append(StateEstimate(sample.time_s, altitude, velocity, phase, barometric_altitude))

    if baseline is None:
        anomalies.append(Anomaly("NO_BAROMETER", ordered[0].time_s, "No pressure samples: altitude will drift from acceleration integration.", "info"))
    if not events:
        anomalies.append(Anomaly("NO_FLIGHT_EVENTS", ordered[-1].time_s, "No launch event was detected; verify axis orientation and acceleration units.", "info"))
    return FusionReport(states, events, anomalies, baseline, {
        "model": "alpha-beta barometric/inertial observer",
        "input_sample_count": len(ordered),
        "processed_sample_count": len(states),
    })
