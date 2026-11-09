"""AeroFuse: practical, transparent telemetry fusion for student hardware."""
from .analysis import AnalysisReport, analyze
from .core import fuse, pressure_to_altitude_m
from .csvio import load_csv, load_matrix_csv
from .models import Anomaly, Event, FlightPhase, FusionConfig, FusionReport, StateEstimate, TelemetrySample
from .workbench import SpectralPeak, TelemetryMatrix
from .sensors import SensorProfile, SensorStatus, inspect_sensors
from .calibration import CalibrationResult, apply_calibration, estimate_calibration
from .attitude import AttitudeConfig, AttitudeReport, AttitudeState, estimate_attitude
from .quality import SignalQuality, assess_quality
from .reporting import write_comparison_html, write_html_report
from .streaming import StreamUpdate, StreamingAnalyzer
from .comparison import ComparedMetric, ComparisonFinding, ComparisonReport, PredictedTrajectory, compare, load_prediction_csv

__all__ = [
    "AnalysisReport", "Anomaly", "AttitudeConfig", "AttitudeReport", "AttitudeState", "CalibrationResult", "ComparedMetric", "ComparisonFinding", "ComparisonReport", "Event", "FlightPhase", "FusionConfig", "FusionReport", "PredictedTrajectory", "SignalQuality", "SpectralPeak", "StreamUpdate", "StreamingAnalyzer",
    "SensorProfile", "SensorStatus", "StateEstimate", "TelemetryMatrix", "TelemetrySample", "analyze", "fuse",
    "apply_calibration", "assess_quality", "compare", "estimate_attitude", "estimate_calibration", "inspect_sensors", "load_csv", "load_matrix_csv", "load_prediction_csv", "pressure_to_altitude_m", "write_comparison_html", "write_html_report",
]

__version__ = "1.1.0"
