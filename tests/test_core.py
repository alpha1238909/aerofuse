import json
import unittest

from aerofuse import FlightPhase, FusionConfig, TelemetrySample, fuse, pressure_to_altitude_m


class AeroFuseTests(unittest.TestCase):
    def test_pressure_baseline_is_zero_altitude(self):
        self.assertAlmostEqual(pressure_to_altitude_m(101325, 101325), 0.0)

    def test_detects_launch_and_apogee_from_synthetic_flight(self):
        samples = [
            TelemetrySample(0.0, 9.81, 101325),
            TelemetrySample(0.1, 18.0, 101320),
            TelemetrySample(0.2, 18.0, 101300),
            TelemetrySample(0.3, 18.0, 101260),
            TelemetrySample(0.4, 5.0, 101220),
            TelemetrySample(0.5, -20.0, 101190),
            TelemetrySample(0.6, -20.0, 101184),
            TelemetrySample(0.7, -20.0, 101190),
            TelemetrySample(0.8, -20.0, 101205),
            TelemetrySample(0.9, -20.0, 101225),
            TelemetrySample(1.0, -20.0, 101245),
            TelemetrySample(1.1, -20.0, 101270),
        ]
        report = fuse(samples)
        self.assertIn("launch", [event.name for event in report.events])
        self.assertIn("apogee", [event.name for event in report.events])
        self.assertGreater(report.apogee_m, 0)
        self.assertEqual(report.states[-1].phase, FlightPhase.DESCENT)

    def test_flags_bad_timestamp_without_crashing(self):
        report = fuse([TelemetrySample(1.0, 9.8, 101325), TelemetrySample(0.5, 9.8, 101325)])
        self.assertEqual(report.anomalies[0].code, "NON_MONOTONIC_TIME")

    def test_report_is_json_serializable(self):
        report = fuse([TelemetrySample(0.0, 9.8, 101325)])
        json.dumps(report.to_dict())

    def test_nonfinite_sensor_value_becomes_anomaly_not_broken_state(self):
        report = fuse([TelemetrySample(0.0, float("nan"), float("nan"))])
        self.assertEqual(report.states[0].altitude_m, 0.0)
        self.assertIn("INVALID_ACCELERATION", [item.code for item in report.anomalies])
        self.assertIn("INVALID_PRESSURE", [item.code for item in report.anomalies])

    def test_invalid_configuration_fails_early(self):
        with self.assertRaises(ValueError):
            FusionConfig(maximum_gap_s=0)


if __name__ == "__main__":
    unittest.main()
