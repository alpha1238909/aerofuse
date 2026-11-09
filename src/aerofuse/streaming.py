"""Small real-time interface for serial, WebSocket, or MQTT bridge code."""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Mapping

from .core import fuse
from .models import FusionConfig, TelemetrySample


@dataclass(frozen=True, slots=True)
class StreamUpdate:
    altitude_m: float | None
    vertical_velocity_mps: float | None
    phase: str | None
    new_events: tuple[str, ...]


class StreamingAnalyzer:
    """Incrementally analyse samples without taking ownership of transport I/O."""

    def __init__(self, config: FusionConfig | None = None, *, history_size: int = 2_000) -> None:
        self.config = config
        self._history: deque[TelemetrySample] = deque(maxlen=history_size)
        self._event_count = 0

    def ingest(self, sample: TelemetrySample) -> StreamUpdate:
        self._history.append(sample)
        report = fuse(self._history, self.config)
        latest = report.states[-1] if report.states else None
        events = tuple(event.name for event in report.events[self._event_count:])
        self._event_count = len(report.events)
        return StreamUpdate(
            None if latest is None else latest.altitude_m,
            None if latest is None else latest.vertical_velocity_mps,
            None if latest is None else latest.phase.value,
            events,
        )

    def ingest_mapping(self, reading: Mapping[str, float]) -> StreamUpdate:
        """Convenience bridge for decoded JSON/MQTT/serial dictionaries."""
        return self.ingest(TelemetrySample(
            time_s=float(reading["time_s"]),
            vertical_acceleration_mps2=reading.get("vertical_acceleration_mps2", reading.get("az_mps2", reading.get("az"))),
            pressure_pa=reading.get("pressure_pa", reading.get("pressure")),
            gps_altitude_m=reading.get("gps_altitude_m"),
        ))
