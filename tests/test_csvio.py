import tempfile
import unittest
import json
from pathlib import Path

from aerofuse import fuse, inspect_sensors, load_csv, load_matrix_csv


class CsvImportTests(unittest.TestCase):
    def test_common_esp32_headings_are_normalized(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "telemetry.csv"
            path.write_text("timestamp_s,az,baro_pa\n0,1.0,101325\n0.1,1.2,101320\n", encoding="utf-8")
            samples = list(load_csv(path, acceleration_unit="g"))
        self.assertEqual(len(samples), 2)
        self.assertAlmostEqual(samples[0].vertical_acceleration_mps2, 9.80665)
        self.assertEqual(samples[1].pressure_pa, 101320)

    def test_time_column_is_required(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.csv"
            path.write_text("az,pressure\n1.0,101325\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                list(load_csv(path))

    def test_millisecond_and_microsecond_timestamps_are_normalized_to_seconds(self):
        with tempfile.TemporaryDirectory() as directory:
            ms_path = Path(directory) / "milliseconds.csv"
            us_path = Path(directory) / "microseconds.csv"
            ms_path.write_text("time_boot_ms,az\n0,1\n250,1\n", encoding="utf-8")
            us_path.write_text("TimeUS,az\n0,1\n250000,1\n", encoding="utf-8")
            self.assertAlmostEqual(load_matrix_csv(ms_path).time_s[-1], 0.25)
            self.assertAlmostEqual(load_matrix_csv(us_path).time_s[-1], 0.25)

    def test_committed_example_matches_its_expected_report(self):
        project_root = Path(__file__).resolve().parents[1]
        actual = fuse(load_csv(project_root / "examples" / "rocket_log.csv")).to_dict()
        expected = json.loads((project_root / "examples" / "rocket_log.expected.json").read_text(encoding="utf-8"))
        self.assertEqual(actual, expected)

    def test_optional_sensor_columns_are_kept_and_detected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "full-sensor-log.csv"
            path.write_text(
                "time_s,ax,ay,az,gx,gy,gz,mx,my,mz,pressure,temp,humidity,lat,lon,gps_alt_m,gps_speed,voltage,current_ma,battery_pct,distance_cm,ntu\n"
                "0,0.1,0.2,1.0,1,2,3,10,11,12,101325,21,45,51.1,71.4,350,2,11.7,320,98,135,4\n",
                encoding="utf-8",
            )
            matrix = load_matrix_csv(path, acceleration_unit="g")
        self.assertIn("magnetic_z_ut", matrix.columns)
        self.assertAlmostEqual(matrix.column("current_a")[0], 0.32)
        self.assertAlmostEqual(matrix.column("distance_m")[0], 1.35)
        statuses = {status.name: status for status in inspect_sensors(matrix)}
        self.assertTrue(statuses["6-axis IMU (MPU6050/ICM20602-style)"].available)
        self.assertTrue(statuses["barometer (BMP280/BME280-style)"].available)
        self.assertTrue(statuses["GPS (NEO-6M-style)"].available)
