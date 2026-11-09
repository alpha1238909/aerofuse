"""High-level bridge from a labelled sensor matrix to a complete report."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .core import fuse
from .models import FusionConfig, FusionReport, TelemetrySample
from .sensors import SensorStatus, inspect_sensors
from .quality import SignalQuality, assess_quality
from .attitude import AttitudeReport, estimate_attitude
from .workbench import SpectralPeak, TelemetryMatrix


@dataclass(slots=True)
class AnalysisReport:
    fusion: FusionReport
    statistics: dict[str, dict[str, float | int]]
    spectral_peaks: dict[str, list[SpectralPeak]]
    sensors: list[SensorStatus]
    quality: list[SignalQuality]
    attitude: AttitudeReport | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = self.fusion.to_dict()
        payload["analysis"] = {
            "statistics": self.statistics,
            "spectral_peaks": {
                column: [{"frequency_hz": peak.frequency_hz, "amplitude": peak.amplitude} for peak in peaks]
                for column, peaks in self.spectral_peaks.items()
            },
            "sensors": [sensor.to_dict() for sensor in self.sensors],
            "quality": [item.to_dict() for item in self.quality],
            "attitude": None if self.attitude is None else self.attitude.to_dict(),
        }
        return payload


def analyze(matrix: TelemetryMatrix, config: FusionConfig | None = None, *, spectral_peak_count: int = 3) -> AnalysisReport:
    """Fuse a labelled matrix and attach useful numerical analysis in one call."""
    names = set(matrix.columns)
    def value(row: int, name: str):
        return float(matrix.column(name)[row]) if name in names else None
    samples = [TelemetrySample(
        float(matrix.time_s[index]),
        value(index, "vertical_acceleration_mps2"),
        value(index, "pressure_pa"),
        value(index, "gps_altitude_m"),
    ) for index in range(matrix.time_s.size)]
    statistics = {name: matrix.statistics(name) for name in matrix.columns}
    peaks: dict[str, list[SpectralPeak]] = {}
    if matrix.time_s.size > 3:
        for name in matrix.columns:
            try:
                peaks[name] = matrix.spectral_peaks(name, count=spectral_peak_count)
            except ValueError:
                peaks[name] = []
    try:
        attitude = estimate_attitude(matrix)
    except ValueError:
        attitude = None
    return AnalysisReport(fuse(samples, config), statistics, peaks, inspect_sensors(matrix), assess_quality(matrix), attitude)
