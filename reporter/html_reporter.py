import os
import html
from datetime import datetime
from collections import Counter


SCORE_STYLES = {
    "PASS":  ("✓", "#22c55e"),
    "FAIL":  ("✗", "#ef4444"),
    "N/A":   ("–", "#94a3b8"),
    "ERROR": ("!", "#f59e0b"),
}

SEVERITY_STYLES = {
    "Critical": ("#fef2f2", "#b91c1c", "#fecaca"),
    "Major":    ("#fffbeb", "#92400e", "#fde68a"),
    "Minor":    ("#f8fafc", "#475569", "#e2e8f0"),
}


def _badge(score: str) -> str:
    s = str(score).upper()
    emoji, color = SCORE_STYLES.get(s, ("?", "#64748b"))
    if s == "N/A":
        return (
            f'<span style="color:#94a3b8;font-size:0.85em;font-weight:500">—</span>'
        )
    return (
        f'<span style="display:inline-flex;align-items:center;gap:4px;background:{color};'
        f'color:#fff;padding:3px 10px;border-radius:20px;font-weight:700;font-size:0.78em;'
        f'letter-spacing:0.03em">{emoji} {score}</span>'
    )


def _severity_badge(severity: str) -> str:
    bg, text, border = SEVERITY_STYLES.get(severity, ("#f8fafc", "#64748b", "#e2e8f0"))
    return (
        f'<span style="background:{bg};color:{text};border:1px solid {border};'
        f'padding:2px 8px;border-radius:20px;font-size:0.75em;font-weight:700;'
        f'white-space:nowrap">{html.escape(severity or "—")}</span>'
    )


def _truncate(text: str, max_len: int = 120) -> str:
    """Truncate text with ellipsis."""
    if not text:
        return ""
    text = str(text)
    return text if len(text) <= max_len else text[:max_len].rstrip() + "…"


def _build_summary(all_results: list) -> tuple:
    """Returns (metric_summary_rows, category_breakdown_rows)."""
    totals: dict = {}
    category_counts: Counter = Counter()

    for r in all_results:
        test_fcs: set = set()
        for metric, data in r["metrics"].items():
            if metric not in totals:
                totals[metric] = {"pass": 0, "fail": 0, "na": 0, "error": 0}
            s = str(data["score"]).upper()
            if s == "PASS":
                totals[metric]["pass"] += 1
            elif s == "FAIL":
                totals[metric]["fail"] += 1
                fc = data.get("failure_category")
                if fc and fc.lower() not in ("null", "none", ""):
                    test_fcs.add(fc)
            elif s == "N/A":
                totals[metric]["na"] += 1
            else:
                totals[metric]["error"] += 1
        for fc in test_fcs:
            category_counts[fc] += 1

    # Metric rows
    metric_rows = ""
    for metric, t in totals.items():
        countable = t["pass"] + t["fail"]
        if countable == 0:
            rate_badge = _badge("N/A")
            detail = '<span style="color:#94a3b8">No scored cases</span>'
        else:
            pct = round(t["pass"] / countable * 100)
            color = "#22c55e" if pct == 100 else "#ef4444" if pct == 0 else "#f59e0b"
            emoji = "✓" if pct == 100 else "✗" if pct == 0 else "~"
            rate_badge = (
                f'<span style="display:inline-flex;align-items:center;gap:4px;background:{color};'
                f'color:#fff;padding:3px 10px;border-radius:20px;font-weight:700;font-size:0.78em">'
                f'{emoji} {pct}%</span>'
            )
            detail = f'<span style="color:#0f172a">{t["pass"]}</span> pass &nbsp;·&nbsp; '
            detail += f'<span style="color:#ef4444">{t["fail"]}</span> fail'
            if t["na"]:
                detail += f' &nbsp;·&nbsp; <span style="color:#94a3b8">{t["na"]} skipped</span>'
            if t["error"]:
                detail += f' &nbsp;·&nbsp; <span style="color:#f59e0b">{t["error"]} error</span>'
        metric_rows += (
            f"<tr>"
            f"<td style='padding:10px 14px;font-weight:600;color:#1e293b'>{html.escape(metric)}</td>"
            f"<td style='padding:10px 14px'>{rate_badge}</td>"
            f"<td style='padding:10px 14px;font-size:0.88em'>{detail}</td>"
            f"</tr>"
        )

    # Failure category breakdown
    cat_rows = ""
    if category_counts:
        total_fails = sum(category_counts.values())
        for cat, count in category_counts.most_common():
            pct = min(100, round(count / total_fails * 100))
            bar = (
                f'<div style="background:#f1f5f9;border-radius:4px;height:8px;width:160px">'
                f'<div style="background:#ef4444;height:8px;border-radius:4px;width:{pct}%;min-width:4px"></div>'
                f'</div>'
            )
            cat_rows += (
                f"<tr>"
                f"<td style='padding:10px 14px;font-weight:600'>{html.escape(cat)}</td>"
                f"<td style='padding:10px 14px;color:#ef4444;font-weight:600'>{count}</td>"
                f"<td style='padding:10px 14px'>{bar}</td>"
                f"</tr>"
            )
    else:
        cat_rows = "<tr><td colspan='3' style='padding:10px 14px;color:#22c55e'>No failures recorded</td></tr>"

    return metric_rows, cat_rows


def _build_latency_card(all_results: list) -> str:
    latencies = [r["latency_ms"] for r in all_results if r.get("latency_ms") is not None]
    if not latencies:
        return ""
    avg_lat = sum(latencies) / len(latencies)
    p95_lat = sorted(latencies)[int(len(latencies) * 0.95)] if len(latencies) >= 2 else max(latencies)

    def lat_color(ms):
        if ms < 500:
            return "#22c55e"
        if ms < 1500:
            return "#f59e0b"
        return "#ef4444"

    stats = [
        ("Average", f"{avg_lat:.0f} ms", lat_color(avg_lat)),
        ("Fastest", f"{min(latencies):.0f} ms", "#22c55e"),
        ("Slowest", f"{max(latencies):.0f} ms", lat_color(max(latencies))),
        ("p95", f"{p95_lat:.0f} ms", lat_color(p95_lat)),
    ]
    stat_html = "".join(
        f'<div style="text-align:center;padding:16px 24px">'
        f'<div style="font-size:1.5em;font-weight:700;color:{color}">{value}</div>'
        f'<div style="font-size:0.8em;color:#64748b;margin-top:4px;font-weight:500">{label}</div>'
        f'</div>'
        for label, value, color in stats
    )
    return f"""
  <div class="card" style="margin-bottom:24px">
    <h2>Response Latency</h2>
    <div style="display:flex;gap:8px;flex-wrap:wrap">{stat_html}</div>
    <p style="font-size:0.78em;color:#94a3b8;margin-top:12px;margin-bottom:0">
      Measures bot response time only. Excludes evaluator LLM calls.
    </p>
  </div>"""


def _metric_cell(data: dict) -> str:
    score = str(data.get("score", "N/A")).upper()
    reason = data.get("reason", "")
    if isinstance(reason, list):
        reason = " ".join(str(r) for r in reason)
    elif not isinstance(reason, str):
        reason = str(reason)
    fc = data.get("failure_category", "")
    fc_clean = str(fc).lower() not in ("null", "none", "") and fc

    # N/A cells: minimal
    if score == "N/A":
        return (
            "<td style='padding:10px 12px;text-align:center;vertical-align:middle'>"
            "<span style='color:#cbd5e1;font-size:0.85em'>—</span>"
            "</td>"
        )

    badge = _badge(score)

    # PASS cells: just the badge, reason in tooltip
    if score == "PASS":
        title = html.escape(reason) if reason else ""
        return (
            f"<td style='padding:10px 12px;vertical-align:top;text-align:center' title='{title}'>"
            f"{badge}"
            f"</td>"
        )

    # FAIL / ERROR cells: badge + failure category pill + short reason
    fc_pill = ""
    if fc_clean:
        fc_pill = (
            f'<div style="margin-top:5px">'
            f'<span style="background:#fef2f2;color:#b91c1c;border:1px solid #fecaca;'
            f'padding:1px 7px;border-radius:20px;font-size:0.72em;font-weight:600">'
            f'{html.escape(str(fc))}</span>'
            f'</div>'
        )

    reason_snippet = ""
    if reason:
        short = _truncate(reason, 90)
        reason_snippet = (
            f'<div style="margin-top:5px;font-size:0.78em;color:#64748b;line-height:1.4" '
            f'title="{html.escape(reason)}">{html.escape(short)}</div>'
        )

    return (
        f"<td style='padding:10px 12px;vertical-align:top'>"
        f"{badge}{fc_pill}{reason_snippet}"
        f"</td>"
    )


def generate_report(all_results: list, output_dir: str = "outputs") -> str:
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = os.path.join(output_dir, f"report_{timestamp}.html")

    # Collect all metric names in order of first appearance
    all_metrics = []
    for r in all_results:
        for k in r["metrics"]:
            if k not in all_metrics:
                all_metrics.append(k)

    # Overall pass rate for headline
    total_pass = total_scored = 0
    for r in all_results:
        for m, d in r["metrics"].items():
            s = str(d["score"]).upper()
            if s in ("PASS", "FAIL"):
                total_scored += 1
                if s == "PASS":
                    total_pass += 1
    overall_pct = round(total_pass / total_scored * 100) if total_scored else 0
    headline_color = "#22c55e" if overall_pct >= 80 else "#f59e0b" if overall_pct >= 60 else "#ef4444"

    metric_headers = "".join(
        f"<th style='padding:10px 14px;white-space:nowrap;font-weight:600'>{html.escape(m)}</th>"
        for m in all_metrics
    )

    test_rows = ""
    for i, r in enumerate(all_results):
        bg = "#ffffff" if i % 2 == 0 else "#f8fafc"
        cells = "".join(_metric_cell(r["metrics"].get(m, {"score": "N/A", "reason": "Not evaluated", "failure_category": None})) for m in all_metrics)

        severity = r.get("severity", "")
        notes = r.get("notes", "")
        input_text = r.get("input", "")
        bot_response = r.get("bot_response", "")
        latency_ms = r.get("latency_ms")

        # Notes: show as small icon with tooltip if present, else nothing
        notes_cell = ""
        if notes:
            notes_cell = (
                f'<span style="color:#94a3b8;cursor:default;font-size:0.85em" '
                f'title="{html.escape(notes)}">📋</span>'
            )

        # Latency cell
        if latency_ms is not None:
            lat_color = "#22c55e" if latency_ms < 500 else "#f59e0b" if latency_ms < 1500 else "#ef4444"
            latency_cell = (
                f"<td style='padding:10px 12px;text-align:right;white-space:nowrap;color:{lat_color};"
                f"font-size:0.85em;font-weight:600;vertical-align:top'>{latency_ms:.0f}&thinsp;ms</td>"
            )
        else:
            latency_cell = "<td style='padding:10px 12px;text-align:right;color:#cbd5e1;vertical-align:top'>—</td>"

        # Bot response: truncated with tooltip
        bot_short = _truncate(bot_response, 140)
        bot_cell_content = (
            f'<span style="color:#475569;font-size:0.82em;line-height:1.5" '
            f'title="{html.escape(bot_response)}">{html.escape(bot_short)}</span>'
        )

        test_rows += f"""
        <tr style="background:{bg};border-bottom:1px solid #e2e8f0">
          <td style="padding:10px 14px;font-weight:700;color:#0f172a;white-space:nowrap;vertical-align:top">{html.escape(r['test_id'])}</td>
          <td style="padding:10px 14px;vertical-align:top">{_severity_badge(severity)}</td>
          <td style="padding:10px 14px;max-width:180px;font-size:0.88em;color:#1e293b;vertical-align:top">{html.escape(input_text)}</td>
          <td style="padding:10px 14px;max-width:220px;vertical-align:top">{bot_cell_content}</td>
          <td style="padding:10px 14px;text-align:center;vertical-align:top">{notes_cell}</td>
          {latency_cell}
          {cells}
        </tr>"""

    metric_rows, cat_rows = _build_summary(all_results)
    latency_card = _build_latency_card(all_results)

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>LLM Eval Report — {timestamp}</title>
<style>
  *, *::before, *::after {{ box-sizing: border-box }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background: #f1f5f9;
    color: #1e293b;
    margin: 0;
    padding: 32px 24px;
    line-height: 1.5;
  }}
  .page-header {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 28px;
    flex-wrap: wrap;
    gap: 12px;
  }}
  .page-title {{
    font-size: 1.5em;
    font-weight: 800;
    color: #0f172a;
    margin: 0;
  }}
  .page-meta {{
    color: #64748b;
    font-size: 0.85em;
  }}
  .headline-score {{
    font-size: 2.4em;
    font-weight: 800;
    color: {headline_color};
    line-height: 1;
  }}
  .headline-label {{
    font-size: 0.75em;
    font-weight: 600;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    margin-top: 4px;
  }}
  .card {{
    background: #fff;
    border-radius: 12px;
    padding: 20px 24px;
    margin-bottom: 20px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.06), 0 1px 2px rgba(0,0,0,0.04);
  }}
  .card h2 {{
    font-size: 0.95em;
    font-weight: 700;
    color: #0f172a;
    margin: 0 0 16px 0;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }}
  .grid2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px }}
  table {{ border-collapse: collapse; width: 100% }}
  thead th {{
    background: #1e293b;
    color: #e2e8f0;
    padding: 10px 14px;
    text-align: left;
    font-size: 0.8em;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    white-space: nowrap;
  }}
  tbody tr:hover td {{ background: #f0f9ff !important }}
  .scroll {{ overflow-x: auto; border-radius: 8px }}
  .notice {{
    background: #fffbeb;
    border: 1px solid #fde68a;
    border-radius: 8px;
    padding: 10px 14px;
    font-size: 0.82em;
    color: #92400e;
    margin-bottom: 20px;
    display: flex;
    gap: 8px;
    align-items: flex-start;
  }}
  @media (max-width: 900px) {{
    .grid2 {{ grid-template-columns: 1fr }}
    .page-header {{ flex-direction: column; align-items: flex-start }}
  }}
</style>
</head>
<body>

<div class="page-header">
  <div>
    <h1 class="page-title">LLM Evaluation Report</h1>
    <div class="page-meta">
      {datetime.now().strftime("%B %d, %Y at %H:%M")}
      &nbsp;&middot;&nbsp; {len(all_results)} test cases
      &nbsp;&middot;&nbsp; {len(all_metrics)} metrics
    </div>
  </div>
  <div style="text-align:right">
    <div class="headline-score">{overall_pct}%</div>
    <div class="headline-label">Overall Pass Rate</div>
  </div>
</div>

<div class="notice">
  <span>⚠️</span>
  <span><strong>Accuracy metric note:</strong> LLM-as-judge is indicative for factual accuracy.
  Validate Critical test failures manually against ground truth.</span>
</div>

<div class="grid2">
  <div class="card">
    <h2>Pass Rates by Metric</h2>
    <table>
      <thead><tr><th>Metric</th><th>Rate</th><th>Detail</th></tr></thead>
      <tbody>{metric_rows}</tbody>
    </table>
  </div>
  <div class="card">
    <h2>Failure Category Breakdown</h2>
    <table>
      <thead><tr><th>Category</th><th>Count</th><th>Share</th></tr></thead>
      <tbody>{cat_rows}</tbody>
    </table>
  </div>
</div>

{latency_card}

<div class="card">
  <h2>Per-Test Results</h2>
  <div class="scroll">
  <table>
    <thead>
      <tr>
        <th>Test ID</th>
        <th>Severity</th>
        <th>Input</th>
        <th>Bot Response</th>
        <th title="Hover icon for full notes">Notes</th>
        <th>Latency</th>
        {metric_headers}
      </tr>
    </thead>
    <tbody>
      {test_rows}
    </tbody>
  </table>
  </div>
  <p style="font-size:0.75em;color:#94a3b8;margin-top:12px;margin-bottom:0">
    Hover over truncated text or PASS badges to see full reasons. Hover over 📋 for test notes.
  </p>
</div>

</body>
</html>"""

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(html_content)

    return filepath
