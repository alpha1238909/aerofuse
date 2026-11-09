# AeroFuse

![Tests](https://github.com/alpha1238909/aerofuse/actions/workflows/test.yml/badge.svg) ![License](https://img.shields.io/badge/license-MIT-2ea44f) ![Python](https://img.shields.io/badge/python-3.10%2B-3776ab)

**Turn raw ESP32 and Arduino logs into calibrated flight states, labelled matrices, engineering calculations, and reproducible evidence.**

AeroFuse is an offline telemetry-intelligence core for model rockets, drone tests, rovers, and student sensor projects. It fuses vertical accelerometer and barometer data, estimates optional 3D attitude from an IMU, evaluates signal quality, and exposes the same log as a labelled NumPy matrix for analysis, calculation, streaming, MATLAB export, and predicted-versus-real validation. It is intentionally not a dashboard or cloud service.

## Two workflows, one core

| Workflow | Purpose | Command |
|---|---|---|
| **AeroFuse Log** | Document, calibrate, analyse, and export one real sensor log. | `aerofuse flight.csv --out report.json --html-out report.html` |
| **AeroFuse Compare** | Compare that real log with a predicted trajectory and produce measurable differences plus evidence-based hypotheses. | `aerofuse flight.csv --predicted predicted.csv --out comparison.json --comparison-html-out comparison.html` |

They intentionally share the same importer, calibration, event logic, and report schema. A team can use Log on every test, then use Compare when it has a simulation or design prediction to validate.

## Install

The PyPI package will be published with the first GitHub release. Until then, cloning is the supported two-minute installation:

```bash
git clone https://github.com/<owner>/aerofuse.git
cd aerofuse
python -m pip install .
```

After publication, this becomes:

```bash
python -m pip install aerofuse
```

## Quick start

```python
from aerofuse import load_csv, fuse

report = fuse(load_csv("my_esp32_log.csv"))
print(round(report.apogee_m, 1))
print([event.name for event in report.events])
```

```bash
aerofuse examples/rocket_log.csv --resample 0.02 --out mission-report.json --html-out mission-report.html
```

The bundled synthetic example prints:

```json
{
  "apogee_m": 8.2,
  "flight_time_s": 1.1,
  "max_absolute_vertical_velocity_mps": 8.2,
  "events_detected": ["launch", "burnout", "apogee"]
}
```

This is the rounded summary from [`examples/rocket_log.csv`](examples/rocket_log.csv). Its full expected JSON report is committed as [`examples/rocket_log.expected.json`](examples/rocket_log.expected.json).

## AeroFuse Compare

Compare takes a real log plus a model/simulator trajectory. The prediction CSV requires only this:

```csv
time_s,altitude_m
0.0,0.0
0.1,1.2
```

`vertical_velocity_mps` and `range_m` are optional; velocity is calculated from the altitude curve if it is absent. Run the bundled example:

```bash
aerofuse examples/rocket_log.csv \
  --predicted examples/predicted_rocket.csv \
  --out comparison.json \
  --comparison-html-out comparison.html
```

The comparison report calculates apogee, time-to-apogee, peak speed, optional GPS range, and altitude RMSE. It then states evidence-backed **hypotheses**, not false certainty—for example, a material apogee mismatch can be consistent with drag, mass, thrust, wind, or sensor-calibration differences.

## Matrix and analysis workbench

The same log can be used as a named numerical matrix instead of being trapped in a CSV or spreadsheet:

```python
from aerofuse import TelemetryMatrix, analyze, load_csv

matrix = TelemetryMatrix.from_samples(load_csv("my_esp32_log.csv"))
uniform = matrix.resample(0.02)  # 50 Hz grid for signal analysis

vertical_acceleration = uniform.column("vertical_acceleration_mps2")
jerk = uniform.derivative("vertical_acceleration_mps2")
acceleration_area = uniform.integral("vertical_acceleration_mps2")
pressure_stats = uniform.statistics("pressure_pa")
vibration = uniform.spectral_peaks("vertical_acceleration_mps2")

report = analyze(uniform)
```

Each `TelemetryMatrix` preserves time and units by column name. It supports:

| Operation | Use |
|---|---|
| `column(name)` / `as_matrix()` | Extract a labelled signal or ordinary NumPy matrix |
| `calibrate(name, scale, offset)` | Apply sensor calibration without overwriting raw logs |
| `resample(step_s)` | Align irregular telemetry onto a uniform grid |
| `derivative(name)` / `integral(name)` | Calculate jerk, rate of pressure change, impulse-like quantities, and more |
| `moving_average(name, window)` | Reduce visible sensor noise for exploration |
| `statistics(name)` | Count, missing values, min, max, mean, standard deviation |
| `spectral_peaks(name)` | Find dominant vibration frequencies using an FFT |
| `analyze(matrix)` | Combine fusion, events, statistics, and spectral output in one report |

### MATLAB export

Install the optional exporter:

```bash
python -m pip install "aerofuse[matlab]"
```

Then write a MATLAB-readable matrix directly from the command line:

```bash
aerofuse flight.csv --resample 0.02 --matlab-out flight.mat --out report.json
```

The `.mat` file contains `aerofuse.time_s`, `aerofuse.values`, and `aerofuse.columns`, so MATLAB users can inspect or calculate with the exact same telemetry without manual CSV cleaning.

## Calibration, attitude, quality, and live use

For an MPU6050/ICM-style six-axis log, AeroFuse can estimate stationary bias, correct a copy of the data, and then calculate roll, pitch, yaw, and Earth-frame acceleration. The raw matrix is never overwritten.

```python
from aerofuse import (
    apply_calibration, estimate_attitude, estimate_calibration,
    load_matrix_csv,
)

raw = load_matrix_csv("flight.csv", acceleration_unit="g")
calibration = estimate_calibration(raw, duration_s=2.0)  # only if the first 2 s are stationary
corrected = apply_calibration(raw, calibration)
attitude = estimate_attitude(corrected)
print(attitude.states[-1].yaw_deg)
```

For live transports—serial bridges, MQTT, WebSocket code, or a Raspberry Pi service—AeroFuse deliberately only owns analysis, not the network or hardware connection:

```python
from aerofuse import StreamingAnalyzer

stream = StreamingAnalyzer()
update = stream.ingest_mapping({"time_s": 2.04, "az": 19.8, "pressure": 101260})
print(update.phase, update.new_events)
```

This separation lets users connect their own ESP32 or Pi transport without exposing device credentials or locking the package to one platform.

## Input

Pass an iterable of `TelemetrySample` objects or a CSV file. The CSV importer recognizes these common headings:

| Measurement | Accepted headings | Unit |
|---|---|---|
| Time | `time_s`, `time`, `timestamp_s`, `seconds`, `t` | seconds |
| Vertical acceleration | `vertical_acceleration_mps2`, `az_mps2`, `accel_z_mps2`, `az`, `acc_z` | m/s² by default |
| Pressure | `pressure_pa`, `pressure`, `baro_pa`, `bmp_pressure` | Pa |
| GPS altitude | `gps_altitude_m`, `gps_alt_m`, `altitude_gps_m` | m |

Additional recognised optional headings include `ax`/`ay`, `gx`/`gy`/`gz`, `mx`/`my`/`mz`, `temperature_c`, `humidity_percent`, `gps_latitude_deg`, `gps_longitude_deg`, `gps_speed_mps`, `voltage_v`, `current_a` or `current_ma`, `battery_percent`, `distance_m` or `distance_cm`, and `turbidity_ntu`.

For logs measured in `g`, use `aerofuse flight.csv --acceleration-unit g`.

At rest, AeroFuse expects an upward vertical acceleration near **+9.80665 m/s²**. Transform sensor axes before import if your device uses another convention.

## Output

`report.to_dict()` returns a versioned JSON-serializable object:

| Field | Meaning |
|---|---|
| `schema_version` | Output format version, currently `1.1.0` |
| `summary.apogee_m` | Highest estimated relative altitude, in metres |
| `summary.max_absolute_vertical_velocity_mps` | Largest estimated vertical speed magnitude, in m/s |
| `events` | Detected `launch`, `burnout`, `apogee`, and/or `landing` events with confidence and reasoning |
| `anomalies` | Time gaps, invalid readings, empty samples, and data-quality warnings |
| `states` | Full time series of estimated altitude, vertical velocity, phase, and barometric altitude |
| `analysis` | Per-column statistics and frequency peaks calculated from the telemetry matrix |
| `analysis.quality` | Coverage, longest gaps, and transparent data-quality score for every available signal |
| `analysis.attitude` | Quaternion-based complementary-filter orientation results when all six IMU axes exist |

## Optional sensor support

Every supported sensor is optional. AeroFuse keeps columns it recognises, skips absent ones, and reports a sensor-capability inventory inside `report.analysis.sensors`; it never fills a missing sensor with fake data.

| Sensor family | Fields used when present | Current use |
|---|---|---|
| MPU6050 / ICM20602-style IMU | `ax`, `ay`, `az`, `gx`, `gy`, `gz` | Matrix analysis and vibration/rotation statistics; orientation fusion planned |
| BMP280 / BME280-style barometer | pressure, temperature, humidity | Relative altitude; temperature/humidity statistics |
| HMC5883L / QMC5883L-style magnetometer | `mx`, `my`, `mz` | Magnetic-field and heading-data analysis |
| NEO-6M-style GPS | latitude, longitude, altitude, speed | Position/speed preserved; GPS altitude retained as an independent signal |
| INA219 / INA226-style monitor | voltage, current, battery percentage | Battery and power-consumption analysis |
| HC-SR04 / ToF rangefinder | distance | Near-ground / obstacle telemetry |
| Turbidity sensor | NTU | Water-quality telemetry, including rover and station projects |
| Generic ESP32/Arduino CSV | Any recognised subset | Supported immediately |

## Limitations

- The baseline vertical model assumes near-vertical motion and a correctly transformed vertical axis.
- The vertical estimator uses a transparent alpha-beta observer, not a full EKF.
- Attitude is a six-axis complementary filter; magnetometer columns are preserved but not yet used for magnetic yaw correction.
- It needs a pre-launch pressure reference for barometric altitude.
- It is for analysis and prototyping, **not** a safety-critical flight controller or launch-authorization system.

## Development

```bash
python -m unittest discover -s tests -v
python -m aerofuse.cli examples/rocket_log.csv --out mission-report.json
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). A real, permissioned, sanitized log is especially valuable because it validates assumptions that synthetic tests cannot. If a log does not parse, open the included issue form with its header and a small safe excerpt.

## License

[MIT](LICENSE)
