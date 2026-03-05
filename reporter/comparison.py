"""
Generate comparison reports between two evaluation runs.
"""
import json
from pathlib import Path
from datetime import datetime
import html as html_module


def load_results(filepath: str) -> dict:
    """Load evaluation results from JSON file."""
    with open(filepath, encoding="utf-8") as f:
        return json.load(f)


def compare_results(results1: dict, results2: dict) -> dict:
    """Compare two evaluation runs and identify differences."""
    r1 = {r["test_id"]: r for r in results1["results"]}
    r2 = {r["test_id"]: r for r in results2["results"]}

    comparison = {
        "run1_timestamp": results1.get("timestamp"),
        "run2_timestamp": results2.get("timestamp"),
        "identical": [],
        "improved": [],
        "regressed": [],
        "new_failures": [],
        "new_passes": [],
        "changed": [],
    }

    for test_id in set(list(r1.keys()) + list(r2.keys())):
        if test_id not in r1:
            # New test in run2
            comparison["new_failures"].append({"test_id": test_id, "result": r2[test_id]})
        elif test_id not in r2:
            # Test removed in run2
            continue
        else:
            # Compare results
            metrics1 = r1[test_id].get("metrics", {})
            metrics2 = r2[test_id].get("metrics", {})

            pass_count1 = sum(1 for m in metrics1.values() if m.get("score") == "PASS")
            pass_count2 = sum(1 for m in metrics2.values() if m.get("score") == "PASS")

            if pass_count1 == pass_count2:
                comparison["identical"].append(test_id)
            elif pass_count2 > pass_count1:
                comparison["improved"].append(
                    {"test_id": test_id, "before": pass_count1, "after": pass_count2}
                )
            else:
                comparison["regressed"].append(
                    {"test_id": test_id, "before": pass_count1, "after": pass_count2}
                )

            # Track specific changes
            for metric_name in set(list(metrics1.keys()) + list(metrics2.keys())):
                m1 = metrics1.get(metric_name, {})
                m2 = metrics2.get(metric_name, {})
                if m1.get("score") != m2.get("score"):
                    if m1.get("score") == "PASS" and m2.get("score") == "FAIL":
                        comparison["new_failures"].append(
                            {
                                "test_id": test_id,
                                "metric": metric_name,
                                "reason": m2.get("reason"),
                            }
                        )
                    elif m1.get("score") == "FAIL" and m2.get("score") == "PASS":
                        comparison["new_passes"].append(
                            {"test_id": test_id, "metric": metric_name}
                        )
                    else:
                        comparison["changed"].append(
                            {
                                "test_id": test_id,
                                "metric": metric_name,
                                "before": m1.get("score"),
                                "after": m2.get("score"),
                            }
                        )

    return comparison


def generate_comparison_html(
    results1: dict, results2: dict, comparison: dict, output_path: str
) -> str:
    """Generate HTML comparison report."""
    r1 = {r["test_id"]: r for r in results1["results"]}
    r2 = {r["test_id"]: r for r in results2["results"]}

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Summary stats
    total_improved = len(comparison["improved"])
    total_regressed = len(comparison["regressed"])
    total_new_passes = len(comparison["new_passes"])
    total_new_failures = len(comparison["new_failures"])

    # Build improved tests HTML
    improved_rows = ""
    for item in comparison["improved"]:
        improved_rows += f"""
        <tr>
            <td style="padding:8px;font-weight:600">{html_module.escape(item['test_id'])}</td>
            <td style="padding:8px">{item['before']} → {item['after']} metrics passing</td>
            <td style="padding:8px;color:#22c55e;font-weight:600">✓ Improved</td>
        </tr>"""

    # Build regressed tests HTML
    regressed_rows = ""
    for item in comparison["regressed"]:
        regressed_rows += f"""
        <tr>
            <td style="padding:8px;font-weight:600">{html_module.escape(item['test_id'])}</td>
            <td style="padding:8px">{item['before']} → {item['after']} metrics passing</td>
            <td style="padding:8px;color:#ef4444;font-weight:600">✗ Regressed</td>
        </tr>"""

    # Build newly fixed rows
    new_passes_rows = ""
    for item in comparison["new_passes"]:
        new_passes_rows += f"""
        <tr>
            <td style="padding:8px;font-weight:600">{html_module.escape(item['test_id'])}</td>
            <td style="padding:8px">{html_module.escape(item['metric'])} now PASS</td>
            <td style="padding:8px;color:#22c55e;font-weight:600">✓ Fixed</td>
        </tr>"""

    # Build newly broken rows
    new_failures_rows = ""
    for item in comparison["new_failures"]:
        if "metric" in item:
            new_failures_rows += f"""
        <tr>
            <td style="padding:8px;font-weight:600">{html_module.escape(item['test_id'])}</td>
            <td style="padding:8px">{html_module.escape(item['metric'])} now FAIL: {html_module.escape(item.get('reason', ''))}</td>
            <td style="padding:8px;color:#ef4444;font-weight:600">✗ Broken</td>
        </tr>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Evaluation Comparison Report</title>
    <style>
        * {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }}
        body {{ background:#f8fafc; margin:0; padding:20px; }}
        .container {{ max-width:1200px; margin:0 auto; }}
        h1 {{ color:#0f172a; margin-top:0; }}
        .summary {{ display:grid; grid-template-columns:repeat(auto-fit, minmax(200px, 1fr)); gap:16px; margin:20px 0; }}
        .summary-card {{ background:#fff; padding:16px; border-radius:8px; box-shadow:0 1px 3px rgba(0,0,0,0.1); }}
        .summary-card h3 {{ margin:0 0 8px 0; color:#64748b; font-size:0.9em; }}
        .summary-card .number {{ font-size:2em; font-weight:bold; }}
        .summary-card.improved .number {{ color:#22c55e; }}
        .summary-card.regressed .number {{ color:#ef4444; }}
        .summary-card.fixed .number {{ color:#22c55e; }}
        .summary-card.broken .number {{ color:#ef4444; }}
        table {{ width:100%; border-collapse:collapse; background:#fff; margin:20px 0; box-shadow:0 1px 3px rgba(0,0,0,0.1); }}
        th {{ background:#1e293b; color:#fff; padding:12px; text-align:left; font-weight:600; }}
        tr:hover {{ background:#f1f5f9; }}
        td {{ border-bottom:1px solid #e2e8f0; padding:12px; }}
        .timestamp {{ color:#64748b; font-size:0.9em; }}
        .section {{ margin:30px 0; }}
        .section h2 {{ color:#1e293b; border-bottom:2px solid #e2e8f0; padding-bottom:8px; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 Evaluation Comparison Report</h1>
        <p class="timestamp">Generated {timestamp}</p>

        <div class="section">
            <h2>Summary</h2>
            <div class="summary">
                <div class="summary-card improved">
                    <h3>Tests Improved</h3>
                    <div class="number">{total_improved}</div>
                </div>
                <div class="summary-card regressed">
                    <h3>Tests Regressed</h3>
                    <div class="number">{total_regressed}</div>
                </div>
                <div class="summary-card fixed">
                    <h3>Metrics Fixed</h3>
                    <div class="number">{total_new_passes}</div>
                </div>
                <div class="summary-card broken">
                    <h3>Metrics Broken</h3>
                    <div class="number">{total_new_failures}</div>
                </div>
            </div>
        </div>

        {f'''<div class="section">
            <h2>✓ Improved Tests ({len(comparison["improved"])})</h2>
            <table>
                <thead>
                    <tr>
                        <th>Test ID</th>
                        <th>Change</th>
                        <th>Status</th>
                    </tr>
                </thead>
                <tbody>
                    {improved_rows if improved_rows else "<tr><td colspan='3' style='color:#64748b'>No improvements</td></tr>"}
                </tbody>
            </table>
        </div>''' if improved_rows else ""}

        {f'''<div class="section">
            <h2>✗ Regressed Tests ({len(comparison["regressed"])})</h2>
            <table>
                <thead>
                    <tr>
                        <th>Test ID</th>
                        <th>Change</th>
                        <th>Status</th>
                    </tr>
                </thead>
                <tbody>
                    {regressed_rows if regressed_rows else "<tr><td colspan='3' style='color:#64748b'>No regressions</td></tr>"}
                </tbody>
            </table>
        </div>''' if regressed_rows else ""}

        {f'''<div class="section">
            <h2>✓ Newly Fixed Metrics ({len(comparison["new_passes"])})</h2>
            <table>
                <thead>
                    <tr>
                        <th>Test ID</th>
                        <th>Details</th>
                        <th>Status</th>
                    </tr>
                </thead>
                <tbody>
                    {new_passes_rows if new_passes_rows else "<tr><td colspan='3' style='color:#64748b'>No new fixes</td></tr>"}
                </tbody>
            </table>
        </div>''' if new_passes_rows else ""}

        {f'''<div class="section">
            <h2>✗ Newly Broken Metrics ({len(comparison["new_failures"])})</h2>
            <table>
                <thead>
                    <tr>
                        <th>Test ID</th>
                        <th>Details</th>
                        <th>Status</th>
                    </tr>
                </thead>
                <tbody>
                    {new_failures_rows if new_failures_rows else "<tr><td colspan='3' style='color:#64748b'>No new failures</td></tr>"}
                </tbody>
            </table>
        </div>''' if new_failures_rows else ""}

    </div>
</body>
</html>"""

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    return output_path
