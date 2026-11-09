# Changelog

All notable changes are documented here.

## 1.1.0 — 2026-11-09

- Added AeroFuse Compare: a predicted-versus-real trajectory workflow with apogee, time-to-apogee, speed, GPS range, altitude-RMSE, and evidence-based findings.
- Added a generic predicted-trajectory CSV importer, comparison JSON schema, offline overlay report, and reproducible example pair.
- Bumped package and report schema to `1.1.0`.

## 1.0.0 — 2026-11-09

- Added stationary-period accelerometer, gyroscope, and barometer calibration without overwriting raw data.
- Added a quaternion-based six-axis complementary attitude estimator with roll, pitch, yaw, and Earth-frame acceleration outputs.
- Added per-signal data quality metrics, an in-process live-streaming API, and an offline self-contained HTML engineering report.
- Added automatic normalisation of common seconds/milliseconds/microseconds CSV timestamps.
- Bumped the package and report schema to `1.0.0`.

## 0.3.0 — 2026-11-09

- Added optional telemetry support for acceleration, gyroscope, magnetometer, environmental, GPS, power, rangefinder, and turbidity readings.
- Added labelled CSV normalisation for common ESP32/Arduino column headings and automatic current/distance unit conversion.
- Added a sensor-capability inventory to every high-level analysis report; absent hardware is explicitly skipped, never fabricated.

## 0.2.0 — 2026-11-09

- Added `TelemetryMatrix`: named NumPy matrices with calibration, resampling, differentiation, integration, rolling averages, statistics, and FFT peak detection.
- Added `analyze()` to combine numerical analysis, fusion, event detection, and data-quality reporting.
- Added optional SciPy-powered MATLAB `.mat` export and CLI support for resampling/export.
- Bumped the machine-readable output schema to `0.2.0`.

## 0.1.0 — 2026-11-07

- First public-core release: dependency-free 1D barometric/inertial fusion.
- CSV adapter for common ESP32/Arduino telemetry headings.
- Launch, burnout, apogee, and landing event detection.
- Structured anomaly reports and a JSON-exporting CLI.
- Versioned JSON schema with apogee, flight-time, velocity, event, and anomaly outputs.
- Unit tests, a complete synthetic example report, and a Python 3.10–3.13 GitHub Actions workflow.
