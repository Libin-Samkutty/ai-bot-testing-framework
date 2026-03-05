import os
import html
from datetime import datetime
from collections import Counter


SCORE_STYLES = {
    "PASS":  ("✅", "#22c55e"),
    "FAIL":  ("❌", "#ef4444"),
    "N/A":   ("–",  "#94a3b8"),
    "ERROR": ("⚠️", "#f59e0b"),
}

SEVERITY_STYLES = {
    "Critical": "#ef4444",
    "Major":    "#f59e0b",
    "Minor":    "#64748b",
}


def _badge(score: str) -> str:
    emoji, color = SCORE_STYLES.get(str(score).upper(), ("?", "#64748b"))
    return (
        f'<span style="background:{color};color:#fff;padding:2px 10px;'
        f'border-radius:12px;font-weight:600;font-size:0.82em">{emoji} {score}</span>'
    )


def _severity_badge(severity: str) -> str:
    color = SEVERITY_STYLES.get(severity, "#94a3b8")
    return (
        f'<span style="background:{color};color:#fff;padding:2px 8px;'
        f'border-radius:10px;font-size:0.78em;font-weight:600">{severity or "—"}</span>'
    )


def _build_summary(all_results: list) -> tuple[str, str]:
    """Returns (metric_summary_rows, category_breakdown_rows)."""
    totals: dict[str, dict] = {}
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
            detail = "No scored cases"
        else:
            pct = round(t["pass"] / countable * 100)
            if pct == 100:
                rate_badge = _badge("PASS")
            elif pct == 0:
                rate_badge = _badge("FAIL")
            else:
                rate_badge = (
                    f'<span style="background:#f59e0b;color:#fff;padding:2px 10px;'
                    f'border-radius:12px;font-weight:600;font-size:0.82em">⚠️ {pct}%</span>'
                )
            detail = f'{t["pass"]} pass / {t["fail"]} fail'
            if t["na"]:
                detail += f' / {t["na"]} skipped'
            if t["error"]:
                detail += f' / {t["error"]} error{"s" if t["error"] > 1 else ""}'
        metric_rows += (
            f"<tr><td style='padding:8px;font-weight:600'>{html.escape(metric)}</td>"
            f"<td style='padding:8px'>{rate_badge}</td>"
            f"<td style='padding:8px;color:#475569;font-size:0.9em'>{detail}</td></tr>"
        )

    # Failure category breakdown
    cat_rows = ""
    if category_counts:
        total_fails = sum(category_counts.values())
        for cat, count in category_counts.most_common():
            pct = min(100, round(count / total_fails * 100))  # Cap at 100% to avoid overflow
            bar = f'<div style="background:#ef4444;height:8px;border-radius:4px;width:{pct}%;min-width:4px"></div>'
            cat_rows += (
                f"<tr><td style='padding:8px;font-weight:600'>{html.escape(cat)}</td>"
                f"<td style='padding:8px'>{count} failure{'s' if count>1 else ''}</td>"
                f"<td style='padding:8px;width:160px'>{bar}</td></tr>"
            )
    else:
        cat_rows = "<tr><td colspan='3' style='padding:8px;color:#64748b'>No failures recorded</td></tr>"

    return metric_rows, cat_rows


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

    metric_headers = "".join(
        f"<th style='padding:8px 12px;background:#1e293b;color:#fff;white-space:nowrap'>{html.escape(m)}</th>"
        for m in all_metrics
    )

    test_rows = ""
    for r in all_results:
        cells = ""
        for metric in all_metrics:
            data = r["metrics"].get(metric, {"score": "N/A", "reason": "Not evaluated", "failure_category": None, "method": ""})
            fc = data.get("failure_category")
            fc_html = (
                f'<br><small style="background:#fef2f2;color:#b91c1c;padding:1px 6px;'
                f'border-radius:8px;font-size:0.75em">{html.escape(str(fc))}</small>'
            ) if fc and str(fc).lower() not in ("null", "none", "") else ""
            cells += (
                f"<td style='padding:8px 12px;vertical-align:top'>"
                f"{_badge(data['score'])}{fc_html}<br>"
                f"<small style='color:#64748b'>{html.escape(data.get('method',''))}</small><br>"
                f"<small style='color:#334155'>{html.escape(data.get('reason',''))}</small>"
                f"</td>"
            )

        severity = r.get("severity", "")
        notes    = r.get("notes", "")
        test_rows += f"""
        <tr style="border-bottom:1px solid #e2e8f0">
          <td style="padding:8px 12px;font-weight:600;color:#0f172a;white-space:nowrap">{html.escape(r['test_id'])}</td>
          <td style="padding:8px 12px;vertical-align:top">{_severity_badge(severity)}</td>
          <td style="padding:8px 12px;max-width:200px;font-size:0.9em;vertical-align:top">{html.escape(r['input'])}</td>
          <td style="padding:8px 12px;max-width:240px;color:#475569;font-size:0.9em;vertical-align:top">{html.escape(r['bot_response'])}</td>
          <td style="padding:8px 12px;max-width:180px;color:#64748b;font-size:0.82em;vertical-align:top;font-style:italic">{html.escape(notes)}</td>
          {cells}
        </tr>"""

    metric_rows, cat_rows = _build_summary(all_results)

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>LLM Eval Report — {timestamp}</title>
<style>
  body {{ font-family: system-ui, -apple-system, sans-serif; background:#f8fafc; color:#1e293b; margin:0; padding:24px }}
  h1 {{ font-size:1.6em; margin-bottom:4px }}
  h2 {{ font-size:1.1em; margin-top:0; color:#0f172a }}
  .meta {{ color:#64748b; font-size:0.9em; margin-bottom:24px }}
  .card {{ background:#fff; border-radius:12px; padding:20px 24px; margin-bottom:24px; box-shadow:0 1px 4px rgba(0,0,0,0.08) }}
  .grid2 {{ display:grid; grid-template-columns:1fr 1fr; gap:24px }}
  table {{ border-collapse:collapse; width:100% }}
  th {{ text-align:left; background:#1e293b; color:#fff; padding:8px 12px }}
  tr:hover td {{ background:#f1f5f9 }}
  .scroll {{ overflow-x:auto }}
  .note {{ background:#fffbeb;border:1px solid #fde68a;border-radius:8px;padding:10px 14px;font-size:0.85em;color:#92400e;margin-bottom:16px }}
  @media(max-width:900px){{ .grid2{{grid-template-columns:1fr}} }}
</style>
</head>
<body>
<h1>🧪 LLM Evaluation Report</h1>
<div class="meta">
  Generated: {datetime.now().strftime("%B %d, %Y %H:%M:%S")}
  &nbsp;|&nbsp; {len(all_results)} test cases
  &nbsp;|&nbsp; {len(all_metrics)} metrics evaluated
</div>

<div class="note">
  ⚠️ <strong>Note on Accuracy metric:</strong> LLM-as-Judge is unreliable for factual accuracy and domain-specific correctness.
  Treat accuracy scores as indicative only. Validate against ground truth manually for critical test cases.
</div>

<div class="grid2">
  <div class="card">
    <h2>📊 Pass Rates by Metric</h2>
    <table>
      <tr><th>Metric</th><th>Pass Rate</th><th>Detail</th></tr>
      {metric_rows}
    </table>
  </div>
  <div class="card">
    <h2>🏷️ Failure Category Breakdown</h2>
    <table>
      <tr><th>Category</th><th>Count</th><th>Share</th></tr>
      {cat_rows}
    </table>
  </div>
</div>

<div class="card">
  <h2>🔍 Per-Test Results</h2>
  <div class="scroll">
  <table>
    <tr>
      <th>Test ID</th>
      <th>Severity</th>
      <th>Input</th>
      <th>Bot Response</th>
      <th>Notes</th>
      {metric_headers}
    </tr>
    {test_rows}
  </table>
  </div>
</div>
</body>
</html>"""

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(html_content)

    return filepath
