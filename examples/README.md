# Example data

`rocket_log.csv` is a **synthetic** 1D student-rocket telemetry sequence. It exists to make the first run reproducible and to exercise the launch, burnout, and apogee detector; it is not presented as real-flight evidence.

`all_optional_sensors.csv` is a **synthetic header reference** showing every currently recognised optional sensor field in one ESP32/Arduino-compatible CSV. You can remove every column your project does not have; the importer keeps what remains and reports which sensor capabilities are available.

`predicted_rocket.csv` is a synthetic simulator-style trajectory used by **AeroFuse Compare**. It documents the smallest portable prediction format: `time_s` and `altitude_m` are required; `vertical_velocity_mps` and `range_m` are optional.

Generate the expected report yourself:

```bash
aerofuse rocket_log.csv --out report.json
```

`rocket_log.expected.json` is the checked-in output for AeroFuse 1.1.0. A future real flight log should be added only with permission and with sensitive location data removed.
