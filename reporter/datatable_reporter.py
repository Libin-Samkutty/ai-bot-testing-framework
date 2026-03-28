"""
DataTables Reporter — interactive HTML report using DataTables.js.
Requires an internet connection to load CDN assets when opening the HTML file.
"""
import os
import html
from datetime import datetime

from reporter.html_reporter import (
    _badge,
    _severity_badge,
    _truncate,
    _build_summary,
    _build_latency_card,
    _metric_cell,
)

_CDN_HEAD = """
  <!-- jQuery -->
  <script src="https://code.jquery.com/jquery-3.7.1.min.js"
          integrity="sha256-/JqT3SQfawRcv/BIHPThkBvs0OEvtFFmqPF/lYI/Cxo=" crossorigin="anonymous"></script>
  <!-- DataTables core -->
  <link rel="stylesheet" href="https://cdn.datatables.net/1.13.8/css/jquery.dataTables.min.css">
  <script src="https://cdn.datatables.net/1.13.8/js/jquery.dataTables.min.js"></script>
  <!-- FixedHeader extension -->
  <link rel="stylesheet" href="https://cdn.datatables.net/fixedheader/3.4.0/css/fixedHeader.dataTables.min.css">
  <script src="https://cdn.datatables.net/fixedheader/3.4.0/js/dataTables.fixedHeader.min.js"></script>
  <!-- Buttons + ColVis extension -->
  <link rel="stylesheet" href="https://cdn.datatables.net/buttons/2.4.2/css/buttons.dataTables.min.css">
  <script src="https://cdn.datatables.net/buttons/2.4.2/js/dataTables.buttons.min.js"></script>
  <script src="https://cdn.datatables.net/buttons/2.4.2/js/buttons.colVis.min.js"></script>"""


def generate_report(all_results: list, output_dir: str = "outputs") -> str:
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = os.path.join(output_dir, f"report_datatable_{timestamp}.html")

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
        f"<th>{html.escape(m)}</th>"
        for m in all_metrics
    )

    test_rows = ""
    for r in all_results:
        cells = "".join(
            _metric_cell(r["metrics"].get(m, {"score": "N/A", "reason": "Not evaluated", "failure_category": None}))
            for m in all_metrics
        )

        severity = r.get("severity", "")
        notes = r.get("notes", "")
        input_text = r.get("input", "")
        bot_response = r.get("bot_response", "")
        latency_ms = r.get("latency_ms")

        notes_cell = ""
        if notes:
            notes_cell = (
                f'<span style="color:#94a3b8;cursor:default;font-size:0.85em" '
                f'title="{html.escape(notes)}">📋</span>'
            )

        if latency_ms is not None:
            lat_color = "#22c55e" if latency_ms < 500 else "#f59e0b" if latency_ms < 1500 else "#ef4444"
            latency_cell = (
                f"<td style='text-align:right;white-space:nowrap;color:{lat_color};"
                f"font-size:0.85em;font-weight:600;vertical-align:top'>{latency_ms:.0f}&thinsp;ms</td>"
            )
        else:
            latency_cell = "<td style='text-align:right;color:#cbd5e1;vertical-align:top'>—</td>"

        bot_short = _truncate(bot_response, 140)
        bot_cell_content = (
            f'<span style="color:#475569;font-size:0.82em;line-height:1.5" '
            f'title="{html.escape(bot_response)}">{html.escape(bot_short)}</span>'
        )

        test_rows += f"""
        <tr>
          <td style="font-weight:700;color:#0f172a;white-space:nowrap;vertical-align:top">{html.escape(r['test_id'])}</td>
          <td style="vertical-align:top">{_severity_badge(severity)}</td>
          <td style="max-width:180px;font-size:0.88em;color:#1e293b;vertical-align:top">{html.escape(input_text)}</td>
          <td style="max-width:220px;vertical-align:top">{bot_cell_content}</td>
          <td style="text-align:center;vertical-align:top">{notes_cell}</td>
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
<title>LLM Eval Report (DataTables) — {timestamp}</title>
{_CDN_HEAD}
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
  .page-meta {{ color: #64748b; font-size: 0.85em; }}
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
  table.summary {{ border-collapse: collapse; width: 100% }}
  table.summary thead th {{
    background: #1e293b;
    color: #e2e8f0;
    padding: 10px 14px;
    text-align: left;
    font-size: 0.8em;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }}
  table.summary tbody tr:hover td {{ background: #f0f9ff }}
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
  .dt-badge {{
    background: #e0f2fe;
    color: #0369a1;
    border: 1px solid #bae6fd;
    border-radius: 6px;
    padding: 2px 8px;
    font-size: 0.75em;
    font-weight: 600;
    margin-left: 8px;
    vertical-align: middle;
  }}
  /* DataTables overrides */
  #results-table_wrapper {{ font-size: 0.88em; }}
  #results-table thead th {{
    background: #1e293b !important;
    color: #e2e8f0 !important;
    border-bottom: none !important;
    white-space: nowrap;
  }}
  #results-table thead th.sorting::after,
  #results-table thead th.sorting_asc::after,
  #results-table thead th.sorting_desc::after {{ color: #94a3b8; }}
  #results-table tbody tr:hover td {{ background: #f0f9ff; }}
  #results-table tbody td {{ vertical-align: top; padding: 10px 12px; border-bottom: 1px solid #e2e8f0; }}
  .dataTables_filter input {{
    border: 1px solid #e2e8f0;
    border-radius: 6px;
    padding: 5px 10px;
    font-size: 0.9em;
    outline: none;
  }}
  .dataTables_filter input:focus {{ border-color: #3b82f6; box-shadow: 0 0 0 2px rgba(59,130,246,0.15); }}
  div.dt-buttons button {{
    background: #1e293b;
    color: #e2e8f0;
    border: none;
    border-radius: 6px;
    padding: 5px 12px;
    font-size: 0.82em;
    font-weight: 600;
    cursor: pointer;
  }}
  div.dt-buttons button:hover {{ background: #334155; }}
  @media (max-width: 900px) {{
    .grid2 {{ grid-template-columns: 1fr }}
    .page-header {{ flex-direction: column; align-items: flex-start }}
  }}
</style>
</head>
<body>

<div class="page-header">
  <div>
    <h1 class="page-title">LLM Evaluation Report <span class="dt-badge">DataTables</span></h1>
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
    <table class="summary">
      <thead><tr><th>Metric</th><th>Rate</th><th>Detail</th></tr></thead>
      <tbody>{metric_rows}</tbody>
    </table>
  </div>
  <div class="card">
    <h2>Failure Category Breakdown</h2>
    <table class="summary">
      <thead><tr><th>Category</th><th>Count</th><th>Share</th></tr></thead>
      <tbody>{cat_rows}</tbody>
    </table>
  </div>
</div>

{latency_card}

<div class="card">
  <h2>Per-Test Results</h2>
  <table id="results-table" style="width:100%">
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
  <p style="font-size:0.75em;color:#94a3b8;margin-top:12px;margin-bottom:0">
    Use the search box to filter rows. Click column headers to sort. Use <strong>Column visibility</strong> to show/hide metrics.
    Hover over truncated text or PASS badges for full details.
  </p>
</div>

<script>
$(document).ready(function() {{
  $('#results-table').DataTable({{
    fixedHeader: true,
    pageLength: 25,
    dom: 'Bfrtip',
    buttons: [
      {{
        extend: 'colvis',
        text: 'Column visibility',
        columns: ':gt(5)'
      }}
    ],
    order: [],
    language: {{
      search: 'Search all columns:',
      lengthMenu: 'Show _MENU_ tests per page',
      info: 'Showing _START_ to _END_ of _TOTAL_ tests',
    }}
  }});
}});
</script>

</body>
</html>"""

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(html_content)

    return filepath
