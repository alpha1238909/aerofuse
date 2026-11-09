"""Portable, self-contained HTML reports; no dashboard or web hosting required."""
from __future__ import annotations

from html import escape
from pathlib import Path


def _trajectory_svg(states: list[dict]) -> str:
    if not states:
        return "<p>No state estimates were produced.</p>"
    width, height, padding = 720, 220, 28
    time = [state["time_s"] for state in states]
    altitude = [state["altitude_m"] for state in states]
    min_time, max_time = min(time), max(time)
    min_altitude, max_altitude = min(altitude), max(altitude)
    span_time = max(max_time - min_time, 1e-9)
    span_altitude = max(max_altitude - min_altitude, 1e-9)
    points = " ".join(
        f"{padding + (value_time - min_time) / span_time * (width - 2*padding):.1f},{height-padding - (value_altitude - min_altitude) / span_altitude * (height - 2*padding):.1f}"
        for value_time, value_altitude in zip(time, altitude)
    )
    return f'''<svg viewBox="0 0 {width} {height}" role="img" aria-label="Estimated altitude over time">
      <rect width="{width}" height="{height}" fill="#0a1525" rx="8"/>
      <line x1="{padding}" y1="{height-padding}" x2="{width-padding}" y2="{height-padding}" stroke="#496075"/>
      <polyline points="{points}" fill="none" stroke="#b7ff4d" stroke-width="3"/>
      <text x="{padding}" y="18" fill="#dce9f2" font-size="12">Estimated altitude</text>
      <text x="{padding}" y="{height-8}" fill="#a5bac9" font-size="10">{min_time:.2f} s</text>
      <text x="{width-padding-35}" y="{height-8}" fill="#a5bac9" font-size="10">{max_time:.2f} s</text>
      <text x="{width-padding-60}" y="18" fill="#a5bac9" font-size="10">peak {max_altitude:.2f} m</text>
    </svg>'''


def write_html_report(report, path: str | Path, *, title: str = "AeroFuse telemetry report") -> Path:
    """Write one offline HTML file containing results, quality and event evidence."""
    payload = report.to_dict()
    summary = payload["summary"]
    events = payload.get("events", [])
    analysis = payload.get("analysis", {})
    metrics = "".join(f"<article><span>{escape(str(key).replace('_', ' '))}</span><strong>{escape(str(value))}</strong></article>" for key, value in summary.items())
    event_rows = "".join(f"<tr><td>{escape(event['name'])}</td><td>{event['time_s']:.3f} s</td><td>{event['confidence']:.0%}</td><td>{escape(event['details'])}</td></tr>" for event in events) or "<tr><td colspan='4'>No events detected</td></tr>"
    quality_rows = "".join(f"<tr><td>{escape(item['column'])}</td><td>{item['coverage_percent']:.1f}%</td><td>{item['longest_gap_s']:.3f} s</td><td>{item['score']:.0f}/100</td></tr>" for item in analysis.get("quality", [])) or "<tr><td colspan='4'>No quality data</td></tr>"
    sensor_rows = "".join(f"<tr><td>{escape(item['name'])}</td><td>{'available' if item['available'] else 'skipped'}</td><td>{escape(', '.join(item['used_columns']) or '—')}</td></tr>" for item in analysis.get("sensors", []))
    html = f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{escape(title)}</title><style>
      body{{margin:0;background:#07111f;color:#e9f4fa;font:14px/1.5 system-ui,sans-serif;padding:32px;max-width:1100px}} h1,h2{{letter-spacing:-.04em}} .sub{{color:#a5bac9}} .metrics{{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:10px;margin:22px 0}} article,table{{background:#0d1d31;border:1px solid #284057;border-radius:8px}} article{{padding:15px}} article span{{display:block;color:#a5bac9;text-transform:capitalize;font-size:11px}} article strong{{font-size:18px}} svg{{width:100%;margin:12px 0}} table{{width:100%;border-collapse:collapse;overflow:hidden}}td,th{{padding:10px;text-align:left;border-bottom:1px solid #284057}}th{{color:#b7ff4d}} .available{{color:#b7ff4d}}</style></head><body>
      <h1>{escape(title)}</h1><p class="sub">AeroFuse schema {escape(payload['schema_version'])} · offline, reproducible analysis</p>
      <section class="metrics">{metrics}</section><h2>Trajectory</h2>{_trajectory_svg(payload.get('states', []))}
      <h2>Events</h2><table><tr><th>Event</th><th>Time</th><th>Confidence</th><th>Evidence</th></tr>{event_rows}</table>
      <h2>Data quality</h2><table><tr><th>Signal</th><th>Coverage</th><th>Longest gap</th><th>Score</th></tr>{quality_rows}</table>
      <h2>Sensor capabilities</h2><table><tr><th>Capability</th><th>Status</th><th>Columns used</th></tr>{sensor_rows}</table>
    </body></html>'''
    destination = Path(path)
    destination.write_text(html, encoding="utf-8")
    return destination


def write_comparison_html(report, path: str | Path, *, title: str = "AeroFuse predicted-versus-real comparison") -> Path:
    """Write a portable report that overlays actual and predicted altitude."""
    payload = report.to_dict()
    actual = payload["trajectories"]["actual"]
    predicted = payload["trajectories"]["predicted"]
    width, height, padding = 720, 260, 30
    all_time = actual["time_s"] + predicted["time_s"]
    all_altitude = actual["altitude_m"] + predicted["altitude_m"]
    min_time, max_time = min(all_time), max(all_time)
    min_altitude, max_altitude = min(all_altitude), max(all_altitude)
    span_time, span_altitude = max(max_time-min_time, 1e-9), max(max_altitude-min_altitude, 1e-9)
    def points(times, heights):
        return " ".join(f"{padding+(time-min_time)/span_time*(width-2*padding):.1f},{height-padding-(altitude-min_altitude)/span_altitude*(height-2*padding):.1f}" for time, altitude in zip(times, heights))
    def metric_row(item: dict) -> str:
        percentage = "—" if item["percent_error"] is None else f"{item['percent_error']:.2f}%"
        return f"<tr><td>{escape(item['name'].replace('_', ' '))}</td><td>{item['actual']}</td><td>{item['predicted']}</td><td>{item['absolute_error']}</td><td>{percentage}</td></tr>"
    metric_rows = "".join(metric_row(item) for item in payload["metrics"])
    findings = "".join(f"<article class='{escape(item['severity'])}'><strong>{escape(item['title'])}</strong><p>{escape(item['evidence'])}</p><small>{escape(' · '.join(item['hypotheses']))}</small></article>" for item in payload["findings"])
    html = f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{escape(title)}</title><style>
      body{{margin:0;max-width:1100px;padding:32px;background:#07111f;color:#e9f4fa;font:14px/1.5 system-ui,sans-serif}}h1,h2{{letter-spacing:-.04em}}.sub,small{{color:#a5bac9}}svg,table,article{{background:#0d1d31;border:1px solid #284057;border-radius:8px}}svg{{width:100%;margin:12px 0}}table{{border-collapse:collapse;width:100%}}td,th{{padding:10px;text-align:left;border-bottom:1px solid #284057}}th{{color:#b7ff4d}}article{{padding:14px;margin:10px 0}}article.warning{{border-left:3px solid #ffb454}}article.info{{border-left:3px solid #65c8ff}}</style></head><body>
      <h1>{escape(title)}</h1><p class="sub">Comparison findings are hypotheses supported by telemetry, not proof of a single physical cause.</p>
      <svg viewBox="0 0 {width} {height}" role="img" aria-label="Actual and predicted altitude comparison"><rect width="{width}" height="{height}" fill="#0a1525" rx="8"/><line x1="{padding}" y1="{height-padding}" x2="{width-padding}" y2="{height-padding}" stroke="#496075"/><polyline points="{points(predicted['time_s'], predicted['altitude_m'])}" fill="none" stroke="#ffb454" stroke-width="3"/><polyline points="{points(actual['time_s'], actual['altitude_m'])}" fill="none" stroke="#b7ff4d" stroke-width="3"/><text x="{padding}" y="18" fill="#b7ff4d" font-size="12">Actual</text><text x="{padding+58}" y="18" fill="#ffb454" font-size="12">Predicted</text></svg>
      <h2>Numerical comparison</h2><table><tr><th>Metric</th><th>Actual</th><th>Predicted</th><th>Error</th><th>% error</th></tr>{metric_rows}</table><h2>Evidence and hypotheses</h2>{findings}
    </body></html>'''
    destination = Path(path)
    destination.write_text(html, encoding="utf-8")
    return destination
