import tempfile
import unittest
from pathlib import Path

import numpy as np

from aerofuse import (
    StreamingAnalyzer, TelemetryMatrix, TelemetrySample, analyze, apply_calibration,
    assess_quality, compare, estimate_attitude, estimate_calibration, load_matrix_csv,
    load_prediction_csv, write_comparison_html, write_html_report,
)


class AdvancedAeroFuseTests(unittest.TestCase):
    def test_stationary_calibration_removes_accelerometer_and_gyro_bias(self):
        matrix = TelemetryMatrix(
            np.array([0.0, 0.1, 0.2, 0.3, 0.4]),
            np.array([[0.2, -0.1, 10.00665, 1.5, -0.5, 0.25, 101325]] * 5),
            ("acceleration_x_mps2", "acceleration_y_mps2", "vertical_acceleration_mps2", "gyro_x_dps", "gyro_y_dps", "gyro_z_dps", "pressure_pa"),
        )
        calibration = estimate_calibration(matrix, duration_s=1.0)
        calibrated = apply_calibration(matrix, calibration)
        self.assertAlmostEqual(calibrated.column("vertical_acceleration_mps2")[0], 9.80665)
        self.assertAlmostEqual(calibrated.column("gyro_x_dps")[0], 0.0)
        self.assertAlmostEqual(calibration.baseline_pressure_pa, 101325)

    def test_attitude_integrates_a_yaw_rotation(self):
        time = np.arange(0.0, 1.01, 0.1)
        values = np.column_stack((np.zeros_like(time), np.zeros_like(time), np.full_like(time, 9.80665), np.zeros_like(time), np.zeros_like(time), np.full_like(time, 90.0)))
        matrix = TelemetryMatrix(time, values, ("acceleration_x_mps2", "acceleration_y_mps2", "vertical_acceleration_mps2", "gyro_x_dps", "gyro_y_dps", "gyro_z_dps"))
        yaw = estimate_attitude(matrix).states[-1].yaw_deg
        self.assertAlmostEqual(yaw, 90.0, delta=1.0)

    def test_quality_detects_missing_data(self):
        matrix = TelemetryMatrix(np.array([0.0, 0.1, 1.0]), np.array([[1.0], [np.nan], [2.0]]), ("signal",))
        quality = assess_quality(matrix)[0]
        self.assertLess(quality.coverage_percent, 100)
        self.assertIn("One or more samples are missing.", quality.notes)

    def test_html_report_contains_evidence_tables(self):
        matrix = TelemetryMatrix.from_samples([
            TelemetrySample(0.0, 9.81, 101325), TelemetrySample(0.1, 20.0, 101320),
            TelemetrySample(0.2, 20.0, 101300), TelemetrySample(0.3, 20.0, 101270),
        ])
        with tempfile.TemporaryDirectory() as directory:
            path = write_html_report(analyze(matrix), Path(directory) / "report.html")
            text = path.read_text(encoding="utf-8")
        self.assertIn("Data quality", text)
        self.assertIn("Sensor capabilities", text)

    def test_streaming_api_produces_a_state_without_transport_dependency(self):
        stream = StreamingAnalyzer()
        first = stream.ingest_mapping({"time_s": 0.0, "az": 9.81, "pressure": 101325})
        second = stream.ingest_mapping({"time_s": 0.1, "az": 20.0, "pressure": 101320})
        self.assertIsNotNone(first.altitude_m)
        self.assertIsNotNone(second.vertical_velocity_mps)

    def test_compare_generates_metrics_findings_and_offline_report(self):
        project_root = Path(__file__).resolve().parents[1]
        matrix = load_matrix_csv(project_root / "examples" / "rocket_log.csv")
        compared = compare(analyze(matrix), matrix, load_prediction_csv(project_root / "examples" / "predicted_rocket.csv"))
        self.assertIsNotNone(compared.altitude_rmse_m)
        self.assertEqual(compared.metrics[0].name, "apogee")
        self.assertTrue(compared.findings)
        with tempfile.TemporaryDirectory() as directory:
            output = write_comparison_html(compared, Path(directory) / "comparison.html")
            self.assertIn("Numerical comparison", output.read_text(encoding="utf-8"))
