"""
Configurable HTML Report Generator

Generates styled HTML evaluation reports with support for different column layouts
and themes. Supports base config plus theme-specific overrides.
"""

import os
import html
from datetime import datetime
from collections import Counter
from typing import Optional, Dict, Any, Tuple, List

from reporter.styles import (
    COLORS, FONTS, SPACING, SCORE_STYLES, SEVERITY_STYLES,
    STYLES, badge_style, badge_rate_style
)


class ReportConfig:
    """Configuration for HTML report generation."""

    def __init__(self, **kwargs):
        # Column visibility
        self.show_expected_output = kwargs.get("show_expected_output", False)
        self.show_notes_full = kwargs.get("show_notes_full", False)  # True = full display, False = tooltip
        self.show_latency = kwargs.get("show_latency", True)
        self.show_severity = kwargs.get("show_severity", True)

        # Report metadata
        self.title = kwargs.get("title", "LLM Evaluation Report")
        self.title_icon = kwargs.get("title_icon", "")
        self.description = kwargs.get("description", "")

        # Color theme overrides
        self.colors = {**COLORS, **kwargs.get("colors", {})}

        # Font overrides
        self.fonts = {**FONTS, **kwargs.get("fonts", {})}


def _badge(score: str, config: ReportConfig) -> str:
    """Generate a badge for test scores (PASS/FAIL/N/A/ERROR)."""
    s = str(score).upper()
    emoji, color = SCORE_STYLES.get(s, ("?", config.colors["text_tertiary"]))
    if s == "N/A":
        return f'<span style="color:{config.colors["muted"]};font-size:0.85em;font-weight:500">—</span>'
    return f'<span style="{badge_style(color)}">{emoji} {score}</span>'


def _severity_badge(severity: str, config: ReportConfig) -> str:
    """Generate a severity level badge (Critical/Major/Minor)."""
    bg, text, border = SEVERITY_STYLES.get(
        severity, (config.colors["minor_bg"], config.colors["text_tertiary"], config.colors["minor_border"])
    )
    return (
        f'<span style="{STYLES["severity_pill"].format(bg=bg, text=text, border=border)}">'
        f'{html.escape(severity or "—")}</span>'
    )


def _truncate(text: str, max_len: int = 120) -> str:
    """Truncate text with ellipsis."""
    if not text:
        return ""
    text = str(text)
    return text if len(text) <= max_len else text[:max_len].rstrip() + "…"


def _get_pass_rate_badge(pct: int, config: ReportConfig) -> Tuple[str, str]:
    """Get color and emoji for a pass rate percentage."""
    if pct == 100:
        return config.colors["success"], "✓"
    elif pct == 0:
        return config.colors["danger"], "✗"
    else:
        return config.colors["warning"], "~"


def _build_summary(all_results: list, config: ReportConfig) -> Tuple[str, str]:
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

    # Build metric summary rows
    metric_rows = ""
    for metric, t in totals.items():
        countable = t["pass"] + t["fail"]
        if countable == 0:
            rate_badge = _badge("N/A", config)
            detail = f'<span style="color:{config.colors["muted"]}">No scored cases</span>'
        else:
            pct = round(t["pass"] / countable * 100)
            color, emoji = _get_pass_rate_badge(pct, config)
            rate_badge = f'<span style="{badge_rate_style(color)}">{emoji} {pct}%</span>'
            detail = f'<span style="color:{config.colors["text_primary"]}">{t["pass"]}</span> pass &nbsp;·&nbsp; '
            detail += f'<span style="color:{config.colors["danger"]}">{t["fail"]}</span> fail'
            if t["na"]:
                detail += f' &nbsp;·&nbsp; <span style="color:{config.colors["muted"]}">{t["na"]} skipped</span>'
            if t["error"]:
                detail += f' &nbsp;·&nbsp; <span style="color:{config.colors["warning"]}">{t["error"]} error</span>'

        metric_rows += (
            f"<tr>"
            f"<td style='padding:{SPACING['lg']};font-weight:600;color:{config.colors["text_primary"]}'>"
            f"{html.escape(metric)}</td>"
            f"<td style='padding:{SPACING['lg']}'>{rate_badge}</td>"
            f"<td style='padding:{SPACING['lg']};font-size:0.88em'>{detail}</td>"
            f"</tr>"
        )

    # Build failure category breakdown
    cat_rows = ""
    if category_counts:
        total_fails = sum(category_counts.values())
        for cat, count in category_counts.most_common():
            pct = min(100, round(count / total_fails * 100))
            bar = (
                f'<div style="background:{config.colors["bg_lighter"]};border-radius:4px;height:8px;width:160px">'
                f'<div style="background:{config.colors["danger"]};height:8px;border-radius:4px;width:{pct}%;min-width:4px"></div>'
                f'</div>'
            )
            cat_rows += (
                f"<tr>"
                f"<td style='padding:{SPACING['lg']};font-weight:600'>{html.escape(cat)}</td>"
                f"<td style='padding:{SPACING['lg']};color:{config.colors["danger"]};font-weight:600'>{count}</td>"
                f"<td style='padding:{SPACING['lg']}'>{bar}</td>"
                f"</tr>"
            )
    else:
        cat_rows = (
            f"<tr><td colspan='3' style='padding:{SPACING['lg']};color:{config.colors["success"]}'>"
            f"No failures recorded</td></tr>"
        )

    return metric_rows, cat_rows


def _get_latency_color(ms: float, config: ReportConfig) -> str:
    """Get color for latency value based on thresholds."""
    if ms < 500:
        return config.colors["success"]
    elif ms < 1500:
        return config.colors["warning"]
    else:
        return config.colors["danger"]


def _build_latency_card(all_results: list, config: ReportConfig) -> str:
    """Build latency statistics card if latency data exists."""
    latencies = [r["latency_ms"] for r in all_results if r.get("latency_ms") is not None]
    if not latencies:
        return ""

    avg_lat = sum(latencies) / len(latencies)
    p95_lat = sorted(latencies)[int(len(latencies) * 0.95)] if len(latencies) >= 2 else max(latencies)

    stats = [
        ("Average", f"{avg_lat:.0f} ms", _get_latency_color(avg_lat, config)),
        ("Fastest", f"{min(latencies):.0f} ms", config.colors["success"]),
        ("Slowest", f"{max(latencies):.0f} ms", _get_latency_color(max(latencies), config)),
        ("p95", f"{p95_lat:.0f} ms", _get_latency_color(p95_lat, config)),
    ]

    stat_html = "".join(
        f'<div style="text-align:center;padding:{SPACING["xl"]} {SPACING["xxl"]}">'
        f'<div style="font-size:1.5em;font-weight:700;color:{color}">{value}</div>'
        f'<div style="font-size:0.8em;color:{config.colors["text_tertiary"]};margin-top:4px;font-weight:500">{label}</div>'
        f'</div>'
        for label, value, color in stats
    )

    return f"""
  <div class="card" style="margin-bottom:24px">
    <h2>Response Latency</h2>
    <div style="display:flex;gap:8px;flex-wrap:wrap">{stat_html}</div>
    <p style="font-size:0.78em;color:{config.colors["muted"]};margin-top:12px;margin-bottom:0">
      Measures bot response time only. Excludes evaluator LLM calls.
    </p>
  </div>"""


def _metric_cell(data: dict, config: ReportConfig) -> str:
    """Generate a metric result cell (PASS/FAIL/N/A/ERROR with details)."""
    score = str(data.get("score", "N/A")).upper()
    reason = data.get("reason", "")
    fc = data.get("failure_category", "")
    fc_clean = str(fc).lower() not in ("null", "none", "") and fc

    # N/A cells: minimal
    if score == "N/A":
        return (
            f"<td style='padding:10px 12px;text-align:center;vertical-align:middle'>"
            f"<span style='color:{config.colors["text_disabled"]};font-size:0.85em'>—</span>"
            f"</td>"
        )

    badge = _badge(score, config)

    # PASS cells: just the badge, reason in tooltip
    if score == "PASS":
        title = html.escape(reason) if reason else ""
        return (
            f"<td style='padding:10px 12px;vertical-align:top;text-align:center' title='{title}'>"
            f"{badge}</td>"
        )

    # FAIL / ERROR cells: badge + failure category pill + short reason
    fc_pill = ""
    if fc_clean:
        fc_style = STYLES["failure_category_pill"].format(
            bg=config.colors["error_bg"],
            text=config.colors["error_text"],
            border=config.colors["error_border"]
        )
        fc_pill = (
            f'<div style="margin-top:5px">'
            f'<span style="{fc_style}">'
            f'{html.escape(str(fc))}</span>'
            f'</div>'
        )

    reason_snippet = ""
    if reason:
        short = _truncate(reason, 90)
        reason_snippet = (
            f'<div style="margin-top:5px;font-size:0.84em;color:{config.colors["text_tertiary"]};line-height:1.4" '
            f'title="{html.escape(reason)}">{html.escape(short)}</div>'
        )

    return (
        f"<td style='padding:10px 12px;vertical-align:top'>"
        f"{badge}{fc_pill}{reason_snippet}</td>"
    )


def _get_overall_pass_rate(all_results: list, config: ReportConfig) -> Tuple[int, str]:
    """Calculate overall pass rate and return (percentage, color)."""
    total_pass = total_scored = 0
    for r in all_results:
        for m, d in r["metrics"].items():
            s = str(d["score"]).upper()
            if s in ("PASS", "FAIL"):
                total_scored += 1
                if s == "PASS":
                    total_pass += 1
    overall_pct = round(total_pass / total_scored * 100) if total_scored else 0
    if overall_pct >= 80:
        color = config.colors["success"]
    elif overall_pct >= 60:
        color = config.colors["warning"]
    else:
        color = config.colors["danger"]
    return overall_pct, color


def _get_metric_names(all_results: list) -> List[str]:
    """Extract all unique metric names in order of first appearance."""
    all_metrics = []
    for r in all_results:
        for k in r["metrics"]:
            if k not in all_metrics:
                all_metrics.append(k)
    return all_metrics


def _build_latency_cell(latency_ms, config: ReportConfig, bot_cached: bool = False) -> str:
    """Build latency cell HTML with cache indicator."""
    if latency_ms is None:
        return f"<td style='padding:10px 12px;text-align:right;color:{config.colors["text_disabled"]};vertical-align:top'>—</td>"

    lat_color = _get_latency_color(latency_ms, config)
    cache_emoji = "💾" if bot_cached else "⚡"
    cache_title = "Cached response" if bot_cached else "Fresh API call"
    return (
        f"<td style='padding:10px 12px;text-align:right;white-space:nowrap;color:{lat_color};"
        f"font-size:0.90em;font-weight:600;vertical-align:top' title='{cache_title}'>"
        f"{latency_ms:.0f}&thinsp;ms {cache_emoji}</td>"
    )


def _build_test_row(result: dict, all_metrics: list, row_index: int, config: ReportConfig) -> str:
    """Build a single test result table row."""
    bg = "#ffffff" if row_index % 2 == 0 else config.colors["bg_light"]
    cells = "".join(
        _metric_cell(result["metrics"].get(m, {"score": "N/A", "reason": "Not evaluated", "failure_category": None}), config)
        for m in all_metrics
    )

    severity = result.get("severity", "")
    notes = result.get("notes", "")
    input_text = result.get("input", "")
    expected_output = result.get("expected_output", "")
    bot_response = result.get("bot_response", "")
    latency_ms = result.get("latency_ms")

    # Build row cells based on config
    row_cells = f"<td style='padding:10px 14px;font-weight:700;color:{config.colors["text_primary"]};white-space:nowrap;vertical-align:top'>{html.escape(result['test_id'])}</td>"

    if config.show_severity:
        row_cells += f"<td style='padding:10px 14px;vertical-align:top'>{_severity_badge(severity, config)}</td>"

    # Input cell
    input_short = _truncate(input_text, 100)
    input_cell = (
        f'<span style="color:{config.colors["text_secondary"]};font-size:0.88em;line-height:1.5">'
        f'{html.escape(input_short)}</span>'
    )
    row_cells += f"<td style='padding:10px 14px;max-width:120px;font-size:0.88em;color:{config.colors["text_primary"]};vertical-align:top'>{input_cell}</td>"

    # Expected output cell (if enabled)
    if config.show_expected_output:
        expected_short = _truncate(expected_output, 100)
        expected_cell = (
            f'<span style="color:{config.colors["text_tertiary"]};font-size:0.88em;line-height:1.5;font-weight:500">'
            f'{html.escape(expected_short)}</span>'
        )
        row_cells += f"<td style='padding:10px 14px;max-width:120px;font-size:0.88em;color:#7c3aed;vertical-align:top;font-weight:500'>{expected_cell}</td>"

    # Bot response cell
    bot_short = _truncate(bot_response, 140)
    bot_cell = (
        f'<span style="color:{config.colors["text_secondary"]};font-size:0.88em;line-height:1.5" '
        f'title="{html.escape(bot_response)}">{html.escape(bot_short)}</span>'
    )
    row_cells += f"<td style='padding:10px 14px;max-width:150px;vertical-align:top'>{bot_cell}</td>"

    # Notes cell (format depends on config)
    if config.show_notes_full:
        # Full display
        if notes:
            notes_short = _truncate(notes, 120)
            notes_cell = (
                f'<span style="color:{config.colors["text_tertiary"]};font-size:0.84em;line-height:1.4">'
                f'{html.escape(notes_short)}</span>'
            )
        else:
            notes_cell = f'<span style="color:{config.colors["text_disabled"]};font-size:0.90em">—</span>'
        row_cells += f"<td style='padding:10px 14px;max-width:140px;vertical-align:top'>{notes_cell}</td>"
    else:
        # Tooltip only (icon)
        notes_cell = ""
        if notes:
            notes_cell = (
                f'<span style="color:{config.colors["muted"]};cursor:default;font-size:0.85em" '
                f'title="{html.escape(notes)}">📋</span>'
            )
        row_cells += f"<td style='padding:10px 14px;text-align:center;vertical-align:top'>{notes_cell}</td>"

    # Latency cell (if enabled)
    if config.show_latency:
        latency_cell = _build_latency_cell(latency_ms, config, result.get("bot_response_cached", False))
        row_cells += latency_cell

    # Metric cells
    row_cells += cells

    return f"""
        <tr style="background:{bg};border-bottom:1px solid {config.colors["minor_border"]}">
          {row_cells}
        </tr>"""


def _build_metric_headers(all_metrics: list, config: ReportConfig) -> str:
    """Build metric column headers."""
    return "".join(
        f"<th style='padding:{SPACING["md"]} {SPACING["lg"]};white-space:nowrap;font-weight:600;text-align:center;border-bottom:2px solid {config.colors["border"]};vertical-align:bottom'>{html.escape(m)}</th>"
        for m in all_metrics
    )


def _build_table_headers(config: ReportConfig) -> str:
    """Build all table headers based on config."""
    headers = "<th>Test ID</th>"
    if config.show_severity:
        headers += "<th>Severity</th>"
    headers += "<th>Input</th>"
    if config.show_expected_output:
        headers += "<th>Expected</th>"
    headers += "<th>Bot Response</th>"
    if config.show_notes_full:
        headers += "<th>Notes</th>"
    else:
        headers += "<th title='Hover icon for full notes'>Notes</th>"
    if config.show_latency:
        headers += "<th>Latency</th>"
    return headers


def generate_report(all_results: list, output_dir: str = "outputs", config: Optional[ReportConfig] = None) -> str:
    """
    Generate HTML report from evaluation results.

    Parameters
    ----------
    all_results : list
        List of result dictionaries from evaluation
    output_dir : str
        Directory to write report file to
    config : ReportConfig, optional
        Report configuration. If None, uses defaults.

    Returns
    -------
    str
        Path to generated HTML file
    """
    if config is None:
        config = ReportConfig()

    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = os.path.join(output_dir, f"report_{timestamp}.html")

    all_metrics = _get_metric_names(all_results)
    overall_pct, headline_color = _get_overall_pass_rate(all_results, config)

    metric_headers = _build_metric_headers(all_metrics, config)

    test_rows = "".join(
        _build_test_row(r, all_metrics, i, config)
        for i, r in enumerate(all_results)
    )

    table_headers = _build_table_headers(config)
    metric_rows, cat_rows = _build_summary(all_results, config)
    latency_card = _build_latency_card(all_results, config)

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{html.escape(config.title)} — {timestamp}</title>
<style>
  *, *::before, *::after {{ box-sizing: border-box }}
  body {{
    font-family: {config.fonts["family"]};
    background: {config.colors["bg_lighter"]};
    color: {config.colors["text_primary"]};
    margin: 0;
    padding: {SPACING["xxxl"]} {SPACING["xxl"]};
    line-height: 1.5;
  }}
  .page-header {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 28px;
    flex-wrap: wrap;
    gap: {SPACING["md"]};
  }}
  .page-title {{
    font-size: 1.5em;
    font-weight: {config.fonts["weight_extrabold"]};
    color: #0f172a;
    margin: 0;
  }}
  .page-meta {{
    color: {config.colors["text_tertiary"]};
    font-size: 0.85em;
  }}
  .headline-score {{
    font-size: 2.4em;
    font-weight: {config.fonts["weight_extrabold"]};
    color: {headline_color};
    line-height: 1;
  }}
  .headline-label {{
    font-size: 0.75em;
    font-weight: {config.fonts["weight_semibold"]};
    color: {config.colors["text_tertiary"]};
    text-transform: uppercase;
    letter-spacing: 0.06em;
    margin-top: 4px;
  }}
  .card {{
    background: #fff;
    border-radius: 12px;
    padding: {SPACING["xl"]} {SPACING["xxl"]};
    margin-bottom: {SPACING["xxl"]};
    box-shadow: 0 1px 3px rgba(0,0,0,0.04);
  }}
  .card h2 {{
    margin: 0 0 {SPACING["xl"]} 0;
    font-size: 1.1em;
    font-weight: {config.fonts["weight_bold"]};
    color: #0f172a;
  }}
  .notice {{
    background: {config.colors["warning_bg"]};
    border: 1px solid {config.colors["warning_border"]};
    border-radius: 8px;
    padding: 10px 14px;
    font-size: 0.82em;
    color: {config.colors["warning_text"]};
    margin-bottom: 20px;
    display: flex;
    gap: 8px;
    align-items: flex-start;
  }}
  table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 0.95em;
  }}
  thead {{
    background: {config.colors["bg_light"]};
    border-bottom: 2px solid {config.colors["border"]};
  }}
  th {{
    padding: {SPACING["md"]} {SPACING["lg"]};
    text-align: left;
    font-weight: {config.fonts["weight_semibold"]};
    color: {config.colors["text_secondary"]};
    white-space: nowrap;
    vertical-align: bottom;
    border-bottom: 2px solid {config.colors["border"]};
  }}
  td {{
    padding: 10px {SPACING["lg"]};
    vertical-align: top;
  }}
  .grid2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px }}
  .scroll {{ overflow-x: auto; overflow-y: auto; max-height: calc(100vh - 280px); border-radius: 8px }}
  tbody tr:hover td {{ background: #f0f9ff !important }}
  @media (max-width: 900px) {{
    .grid2 {{ grid-template-columns: 1fr }}
    .page-header {{ flex-direction: column; align-items: flex-start }}
  }}
</style>
</head>
<body>

<div class="page-header">
  <div>
    <h1 class="page-title">{config.title_icon} {html.escape(config.title)}</h1>
    <div class="page-meta">
      {datetime.now().strftime("%B %d, %Y at %H:%M")}
      &nbsp;&middot;&nbsp; {len(all_results)} test cases
      &nbsp;&middot;&nbsp; {len(all_metrics)} metrics
    </div>
  </div>
  <div style="text-align:right">
    <div class="headline-score">{overall_pct}%</div>
    <div class="headline-label">Pass Rate</div>
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
        {table_headers}
        {metric_headers}
      </tr>
    </thead>
    <tbody>
      {test_rows}
    </tbody>
  </table>
  </div>
  <p style="font-size:0.75em;color:{config.colors["text_tertiary"]};margin-top:12px;margin-bottom:0">
    Hover over truncated text or PASS badges to see full reasons. Hover over 📋 for test notes.
  </p>
</div>

</body>
</html>"""

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(html_content)

    return filepath
