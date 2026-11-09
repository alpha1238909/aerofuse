import math
import tempfile
import unittest
from pathlib import Path

import numpy as np

from aerofuse import TelemetryMatrix, TelemetrySample, analyze


class TelemetryMatrixTests(unittest.TestCase):
    def setUp(self):
        self.matrix = TelemetryMatrix(
            np.asarray([0.0, 1.0, 2.0]),
            np.asarray([[0.0, 100.0], [1.0, 101.0], [4.0, 102.0]]),
            ("signal", "pressure_pa"),
        )

    def test_extract_calibrate_and_convert_to_ordinary_matrix(self):
        calibrated = self.matrix.calibrate("signal", scale=2, offset=1)
        np.testing.assert_allclose(calibrated.column("signal"), [1.0, 3.0, 9.0])
        self.assertEqual(calibrated.as_matrix().shape, (3, 3))

    def test_derivative_integral_statistics_and_resampling(self):
        np.testing.assert_allclose(self.matrix.derivative("signal"), [1.0, 2.0, 3.0])
        self.assertAlmostEqual(self.matrix.integral("signal"), 3.0)
        self.assertEqual(self.matrix.statistics("signal")["maximum"], 4.0)
        self.assertEqual(self.matrix.resample(0.5).time_s.size, 5)

    def test_fft_identifies_known_frequency(self):
        time_s = np.arange(0, 2, 0.01)
        signal = np.sin(2 * np.pi * 4 * time_s)
        matrix = TelemetryMatrix(time_s, signal.reshape(-1, 1), ("signal",))
        peak = matrix.spectral_peaks("signal", count=1)[0]
        self.assertAlmostEqual(peak.frequency_hz, 4.0, places=6)
        self.assertGreater(peak.amplitude, 0.9)

    def test_missing_measurements_are_nan_not_zero(self):
        matrix = TelemetryMatrix.from_samples([TelemetrySample(0.0), TelemetrySample(1.0, 9.81)])
        self.assertTrue(math.isnan(matrix.column("pressure_pa")[0]))
        self.assertAlmostEqual(matrix.column("vertical_acceleration_mps2")[1], 9.81)

    def test_analysis_attaches_matrix_statistics(self):
        matrix = TelemetryMatrix.from_samples([
            TelemetrySample(0.0, 9.81, 101325), TelemetrySample(0.1, 20.0, 101320),
            TelemetrySample(0.2, 20.0, 101300), TelemetrySample(0.3, 20.0, 101270),
        ])
        report = analyze(matrix)
        self.assertIn("vertical_acceleration_mps2", report.statistics)
        self.assertEqual(report.to_dict()["schema_version"], "1.1.0")
        self.assertIn("sensors", report.to_dict()["analysis"])

    def test_matlab_export_when_optional_dependency_is_installed(self):
        try:
            import scipy  # noqa: F401
        except ImportError:
            self.skipTest("SciPy optional extra not installed")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "flight.mat"
            self.matrix.to_matlab(path)
            self.assertGreater(path.stat().st_size, 0)
