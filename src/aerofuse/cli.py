from __future__ import annotations

import argparse
import json
from pathlib import Path

from .csvio import load_matrix_csv
from .analysis import analyze
from .calibration import apply_calibration, estimate_calibration
from .reporting import write_html_report
from .reporting import write_comparison_html
from .comparison import compare, load_prediction_csv


def main() -> None:
    parser = argparse.ArgumentParser(description="Fuse IMU and barometric telemetry into a flight report.")
    parser.add_argument("input", type=Path, help="CSV telemetry file")
    parser.add_argument("--out", type=Path, help="Write the complete machine-readable report as JSON")
    parser.add_argument("--acceleration-unit", choices=("mps2", "g"), default="mps2")
    parser.add_argument("--resample", type=float, metavar="SECONDS", help="Resample onto a uniform grid before analysis")
    parser.add_argument("--matlab-out", type=Path, metavar="FILE", help="Export the labelled telemetry matrix to MATLAB .mat")
    parser.add_argument("--html-out", type=Path, metavar="FILE", help="Write a self-contained offline HTML engineering report")
    parser.add_argument("--calibrate", action="store_true", help="Estimate offsets from the initial stationary readings before analysis")
    parser.add_argument("--calibration-duration", type=float, default=2.0, metavar="SECONDS", help="Initial stationary window used by --calibrate (default: 2.0)")
    parser.add_argument("--predicted", type=Path, metavar="FILE", help="Predicted trajectory CSV for AeroFuse Compare")
    parser.add_argument("--comparison-html-out", type=Path, metavar="FILE", help="Write an offline predicted-versus-real HTML report")
    args = parser.parse_args()
    matrix = load_matrix_csv(args.input, acceleration_unit=args.acceleration_unit)
    if args.resample:
        matrix = matrix.resample(args.resample)
    calibration = estimate_calibration(matrix, duration_s=args.calibration_duration) if args.calibrate else None
    if calibration:
        matrix = apply_calibration(matrix, calibration)
    if args.matlab_out:
        matrix.to_matlab(args.matlab_out)
    report = analyze(matrix)
    payload = report.to_dict()
    if calibration:
        payload["analysis"]["calibration"] = calibration.to_dict()
    comparison = None
    if args.predicted:
        comparison = compare(report, matrix, load_prediction_csv(args.predicted))
        payload["comparison"] = comparison.to_dict()
    print(json.dumps(payload["summary"], indent=2))
    if args.out:
        args.out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"Wrote {args.out}")
    if args.html_out:
        write_html_report(report, args.html_out)
        print(f"Wrote {args.html_out}")
    if args.comparison_html_out:
        if comparison is None:
            parser.error("--comparison-html-out requires --predicted FILE")
        write_comparison_html(comparison, args.comparison_html_out)
        print(f"Wrote {args.comparison_html_out}")


if __name__ == "__main__":
    main()
