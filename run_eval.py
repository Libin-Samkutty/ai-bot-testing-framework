#!/usr/bin/env python3
"""
LLM Eval Framework

Usage:
  python run_eval.py --csv test_cases/sample.csv
  python run_eval.py --csv test_cases/sample.csv --dry-run
  python run_eval.py --csv test_cases/sample.csv --min-pass-rate 0.8
  python run_eval.py --csv test_cases/sample.csv --fail-on-critical
  python run_eval.py --csv test_cases/sample.csv --severity Critical,Major
  python run_eval.py --csv test_cases/sample.csv --eval-types safety,refusal
  python run_eval.py --csv test_cases/sample.csv --test-ids tc_001,tc_003
  python run_eval.py --csv test_cases/sample.csv --compare outputs/results_20260305_120000.json
"""

import argparse
import asyncio
import csv
import json
import os
import sys
import yaml
from datetime import datetime
from openai import OpenAI, AsyncOpenAI

from connectors.bot_connector import MockBotConnector
from evaluators.quality  import QualityEvaluator
from evaluators.safety   import SafetyEvaluator
from evaluators.rag      import RAGEvaluator
from evaluators.refusal  import RefusalEvaluator
from evaluators.loader import load_custom_evaluators
from reporter.html_reporter import generate_report
from reporter.comparison import load_results, compare_results, generate_comparison_html
from utils.cache import EvaluationCache
from utils.cost import format_cost_report

# ─────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────

REQUIRED_CONFIG_KEYS = [
    ("openai", "api_key"),
    ("openai", "judge_model"),
    ("evaluation", "temperature"),
    ("evaluation", "max_tokens"),
    ("output", "reports_dir"),
]
REQUIRED_CSV_COLUMNS = {"test_id", "input", "eval_types"}
KNOWN_EVAL_TYPES      = {"quality", "safety", "rag", "refusal"}
VALID_SEVERITIES      = {"Critical", "Major", "Minor", ""}
PLACEHOLDER_KEY       = "sk-your-key-here"

# ─────────────────────────────────────────────
# Loaders
# ─────────────────────────────────────────────

def load_config(path: str) -> dict:
    with open(path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def load_optional_md(path: str) -> str:
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            content = f.read().strip()
        lines = [l for l in content.splitlines() if not l.strip().startswith("<!--")]
        return "\n".join(lines).strip()
    return ""


def load_test_cases(csv_path: str) -> list:
    cases = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            raw = row.get("eval_types", "")
            row["eval_types"] = [e.strip() for e in raw.split(",") if e.strip()]
            cases.append(row)
    return cases

# ─────────────────────────────────────────────
# Filtering (Feature 6)
# ─────────────────────────────────────────────

def _apply_filters(
    test_cases: list,
    severity_filter: str = None,
    test_id_filter: str = None,
    eval_type_filter: str = None,
) -> list:
    """
    Filter test cases by severity, test ID, or eval types.

    --eval-types narrows which evaluators run per test (doesn't skip the test
    entirely), so partial evaluations are possible without editing the CSV.
    """
    original_count = len(test_cases)
    filtered = list(test_cases)

    if test_id_filter:
        allowed_ids = {t.strip() for t in test_id_filter.split(",")}
        filtered = [tc for tc in filtered if tc["test_id"] in allowed_ids]

    if severity_filter:
        allowed_sevs = {s.strip().capitalize() for s in severity_filter.split(",")}
        filtered = [tc for tc in filtered if tc.get("severity", "").strip() in allowed_sevs]

    if eval_type_filter:
        allowed_types = {e.strip() for e in eval_type_filter.split(",")}
        narrowed = []
        for tc in filtered:
            new_types = [et for et in tc["eval_types"] if et in allowed_types]
            if new_types:
                tc = dict(tc)
                tc["eval_types"] = new_types
                narrowed.append(tc)
        filtered = narrowed

    if len(filtered) < original_count:
        print(
            f"🔍  Filters applied: {original_count} → {len(filtered)} test cases "
            f"({original_count - len(filtered)} filtered out)"
        )
    if not filtered:
        print("⚠️  All test cases were filtered out. Check your filter values.")

    return filtered

# ─────────────────────────────────────────────
# CI/CD exit status (Feature 3)
# ─────────────────────────────────────────────

def _compute_exit_status(
    all_results: list,
    min_pass_rate: float = None,
    fail_on_critical: bool = False,
) -> tuple:
    """
    Returns (exit_code, message).

    Exit codes:
      0 = success (thresholds met or no thresholds set)
      1 = threshold not met
    """
    total_scored = 0
    total_pass = 0

    for r in all_results:
        for metric_data in r["metrics"].values():
            score = str(metric_data.get("score", "")).upper()
            if score in ("PASS", "FAIL"):
                total_scored += 1
                if score == "PASS":
                    total_pass += 1

    pass_rate = total_pass / total_scored if total_scored > 0 else 0.0

    if fail_on_critical:
        for r in all_results:
            if r.get("severity", "").strip() == "Critical":
                for metric_data in r["metrics"].values():
                    if str(metric_data.get("score", "")).upper() == "FAIL":
                        return 1, (
                            f"Critical test '{r['test_id']}' has a failing metric. "
                            f"Overall pass rate: {pass_rate:.1%} ({total_pass}/{total_scored})"
                        )

    if min_pass_rate is not None and pass_rate < min_pass_rate:
        return 1, (
            f"Pass rate {pass_rate:.1%} is below threshold {min_pass_rate:.1%} "
            f"({total_pass}/{total_scored} metrics passed)"
        )

    return 0, f"Pass rate: {pass_rate:.1%} ({total_pass}/{total_scored} metrics passed)"

# ─────────────────────────────────────────────
# Dry-run validation
# ─────────────────────────────────────────────

def _ok(msg):  return f"  ✅  {msg}"
def _err(msg): return f"  ❌  {msg}"
def _warn(msg):return f"  ⚠️   {msg}"


def dry_run(
    csv_path: str,
    config_path: str,
    custom_eval_dir: str = None,
    severity_filter: str = None,
    test_id_filter: str = None,
    eval_type_filter: str = None,
) -> bool:
    """
    Validate config + CSV without calling any APIs.
    Returns True if all checks pass, False otherwise.
    """
    print("\n🔍  DRY RUN — Preflight Validation")
    print("═" * 60)
    errors = []

    # Load custom evaluators if provided
    custom_evaluators = {}
    if custom_eval_dir:
        custom_evaluators = load_custom_evaluators(custom_eval_dir)
        known_eval_types = KNOWN_EVAL_TYPES | set(custom_evaluators.keys())
    else:
        known_eval_types = KNOWN_EVAL_TYPES

    # ── Config validation ──────────────────────────────────────
    print(f"\n  CONFIG ({config_path})")
    if not os.path.exists(config_path):
        print(_err(f"File not found: {config_path}"))
        errors.append("config_missing")
        config = {}
    else:
        print(_ok("File exists"))
        try:
            config = load_config(config_path)
        except Exception as e:
            print(_err(f"Failed to parse YAML: {e}"))
            errors.append("config_parse_error")
            config = {}

    if config:
        for section, key in REQUIRED_CONFIG_KEYS:
            val = (config.get(section) or {}).get(key)
            if val is None:
                print(_err(f"Missing key: {section}.{key}"))
                errors.append(f"missing_{section}_{key}")
            else:
                print(_ok(f"{section}.{key}: {val}"))

        api_key = (config.get("openai") or {}).get("api_key", "")
        if api_key == PLACEHOLDER_KEY:
            print(_warn("openai.api_key is still the placeholder — replace before running"))

    # ── CSV validation ─────────────────────────────────────────
    print(f"\n  CSV ({csv_path})")
    if not os.path.exists(csv_path):
        print(_err(f"File not found: {csv_path}"))
        errors.append("csv_missing")
        test_cases = []
    else:
        print(_ok("File exists"))
        try:
            test_cases = load_test_cases(csv_path)
            print(_ok(f"{len(test_cases)} test cases loaded"))
        except Exception as e:
            print(_err(f"Failed to parse CSV: {e}"))
            errors.append("csv_parse_error")
            test_cases = []

    if test_cases:
        # Column check
        missing_cols = REQUIRED_CSV_COLUMNS - set(test_cases[0].keys())
        if missing_cols:
            print(_err(f"Missing required columns: {', '.join(sorted(missing_cols))}"))
            errors.append("missing_columns")
        else:
            print(_ok(f"Required columns present: {', '.join(sorted(REQUIRED_CSV_COLUMNS))}"))

        # Duplicate test_ids
        ids = [tc["test_id"] for tc in test_cases]
        dupes = [i for i in ids if ids.count(i) > 1]
        if dupes:
            print(_err(f"Duplicate test_ids: {', '.join(set(dupes))}"))
            errors.append("duplicate_ids")
        else:
            print(_ok("No duplicate test_ids"))

        # Unknown eval_types
        unknown = set()
        for tc in test_cases:
            for et in tc.get("eval_types", []):
                if et not in known_eval_types:
                    unknown.add(et)
        if unknown:
            print(_err(f"Unknown eval_types: {', '.join(sorted(unknown))}  (known: {', '.join(sorted(known_eval_types))})"))
            errors.append("unknown_eval_types")
        else:
            print(_ok(f"All eval_types valid ({', '.join(sorted(known_eval_types))})"))

        # Severity values
        bad_sev = set()
        for tc in test_cases:
            s = tc.get("severity", "").strip()
            if s not in VALID_SEVERITIES:
                bad_sev.add(s)
        if bad_sev:
            print(_warn(f"Unrecognised severity values: {', '.join(sorted(bad_sev))}  (expected: Critical / Major / Minor)"))
        else:
            print(_ok("Severity values valid"))

        # Apply filters for dry-run preview
        if any([severity_filter, test_id_filter, eval_type_filter]):
            print(f"\n  FILTER PREVIEW")
            test_cases = _apply_filters(test_cases, severity_filter, test_id_filter, eval_type_filter)

    # ── Test case breakdown ────────────────────────────────────
    if test_cases:
        print("\n  TEST CASE BREAKDOWN")
        from collections import Counter
        et_counts  = Counter(et  for tc in test_cases for et in tc.get("eval_types", []))
        sev_counts = Counter(tc.get("severity", "—").strip() or "—" for tc in test_cases)

        print(f"  {'Eval Type':<14}  Count")
        for k, v in sorted(et_counts.items()):
            print(f"    {k:<12}  {v}")
        print(f"\n  {'Severity':<14}  Count")
        for k, v in sorted(sev_counts.items()):
            print(f"    {k:<12}  {v}")

        # Cost estimate (without running)
        if config:
            model      = (config.get("openai") or {}).get("judge_model", "unknown")
            max_tokens = (config.get("evaluation") or {}).get("max_tokens", 512)
            pricing    = config.get("pricing", {})
            from utils.cost import get_price_per_million
            prices = get_price_per_million(model, pricing)
            total_calls = sum(len(tc.get("eval_types", [])) for tc in test_cases)
            est_input   = total_calls * 600
            est_output  = total_calls * max_tokens
            est_cost    = (est_input / 1_000_000) * prices["input"] + (est_output / 1_000_000) * prices["output"]
            print(f"\n  ESTIMATED COST (rough, {model})")
            print(f"    ~{total_calls} LLM calls  |  ~{est_input:,} input tokens  |  ~{est_output:,} output tokens")
            print(f"    Estimated cost: ~${est_cost:.4f} USD")

    # ── Final result ───────────────────────────────────────────
    print("\n" + "═" * 60)
    if errors:
        print(f"\n❌  Validation FAILED — {len(errors)} error(s). Fix before running.\n")
        return False
    else:
        print(f"\n✅  Validation passed — ready to run:")
        print(f"    python run_eval.py --csv {csv_path}\n")
        return True

# ─────────────────────────────────────────────
# Main async run (Features 1, 2, 3, 4, 6)
# ─────────────────────────────────────────────

async def run(
    csv_path: str,
    config_path: str = "config.yaml",
    custom_eval_dir: str = None,
    cache_dir: str = "outputs/cache",
    clear_cache: bool = False,
    compare_run: str = None,
    max_concurrency: int = 10,
    min_pass_rate: float = None,
    fail_on_critical: bool = False,
    severity_filter: str = None,
    test_id_filter: str = None,
    eval_type_filter: str = None,
) -> tuple:
    config = load_config(config_path)
    api_key      = config["openai"]["api_key"]
    model        = config["openai"]["judge_model"]
    temperature  = config["evaluation"]["temperature"]
    max_tokens   = config["evaluation"]["max_tokens"]
    output_dir   = config["output"]["reports_dir"]
    pricing      = config.get("pricing", {})
    max_retries  = (config.get("evaluation") or {}).get("max_retries", 3)
    backoff_base = (config.get("evaluation") or {}).get("backoff_base", 2.0)

    # ── Caching ────────────────────────────────────────────────
    cache = EvaluationCache(cache_dir)
    if clear_cache:
        cache.clear()
    else:
        stats = cache.stats()
        if stats["total_entries"] > 0:
            print(f"💾  Cache: {stats['total_entries']} cached evaluations available")

    memory       = load_optional_md("memory.md")
    instructions = load_optional_md("instructions.md")

    if memory:
        print("📋  memory.md loaded — bot context injected into judge prompts")
    if instructions:
        print("📐  instructions.md loaded — custom eval rules injected into judge prompts")

    client       = OpenAI(api_key=api_key)
    async_client = AsyncOpenAI(api_key=api_key)

    # ── Bot under test ─────────────────────────────────────────
    bot = MockBotConnector()
    # To use HTTP:   bot = HTTPBotConnector(url="https://your-bot/api/chat")
    # Custom class:  subclass BotConnector, implement get_response()

    # ── Evaluators ────────────────────────────────────────────
    kwargs = dict(
        client=client,
        async_client=async_client,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        memory=memory,
        instructions=instructions,
        max_retries=max_retries,
        backoff_base=backoff_base,
    )
    evaluators = {
        "quality": QualityEvaluator(**kwargs),
        "safety":  SafetyEvaluator(**kwargs),
        "rag":     RAGEvaluator(**kwargs),
        "refusal": RefusalEvaluator(**kwargs),
    }

    # ── Load custom evaluators ─────────────────────────────────
    if custom_eval_dir:
        custom_evaluators = load_custom_evaluators(custom_eval_dir)
        for name, evaluator_class in custom_evaluators.items():
            evaluators[name] = evaluator_class(**kwargs)

    test_cases = load_test_cases(csv_path)
    test_cases = _apply_filters(test_cases, severity_filter, test_id_filter, eval_type_filter)

    if not test_cases:
        print("No test cases to run after filtering.")
        return None, 0

    print(f"\n🧪  Running {len(test_cases)} test cases (up to {max_concurrency} parallel)...\n")

    semaphore = asyncio.Semaphore(max_concurrency)
    cache_hits_counter = [0]  # list so nested async fn can mutate it

    async def evaluate_one(tc: dict) -> dict:
        async with semaphore:
            # Bot call with latency timing (Feature 4)
            bot_response, latency_ms = bot.get_response_timed(tc["input"], tc.get("context", ""))
            tc["bot_response"] = bot_response

            metrics = {}
            for eval_type in tc["eval_types"]:
                if eval_type in evaluators:
                    cached_result, _ = cache.get(tc["test_id"], eval_type, bot_response)
                    if cached_result:
                        metrics.update(cached_result)
                        cache_hits_counter[0] += 1
                    else:
                        result = await evaluators[eval_type].async_evaluate(tc)
                        cache.set(tc["test_id"], eval_type, bot_response, result)
                        metrics.update(result)
                else:
                    print(f"    ⚠️   Unknown eval type: '{eval_type}' — skipping")

            return {
                "test_id":      tc["test_id"],
                "input":        tc["input"],
                "bot_response": bot_response,
                "latency_ms":   latency_ms,
                "severity":     tc.get("severity", "").strip(),
                "notes":        tc.get("notes", "").strip(),
                "metrics":      metrics,
            }

    tasks = [evaluate_one(tc) for tc in test_cases]
    all_results = await asyncio.gather(*tasks)
    cache.flush()  # single disk write at end of run

    # ── Latency summary ────────────────────────────────────────
    latencies = [r["latency_ms"] for r in all_results if r.get("latency_ms") is not None]
    if latencies:
        avg_lat = sum(latencies) / len(latencies)
        print(
            f"\n⏱️  Bot latency — avg: {avg_lat:.0f}ms  "
            f"min: {min(latencies):.0f}ms  max: {max(latencies):.0f}ms"
        )

    # ── Save results as JSON ───────────────────────────────────
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = os.path.join(output_dir, f"results_{timestamp}.json")
    os.makedirs(output_dir, exist_ok=True)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "csv_path":  csv_path,
            "model":     model,
            "results":   all_results,
        }, f, indent=2)
    print(f"\n💾  Results saved to: {json_path}")

    # ── Report ────────────────────────────────────────────────
    report_path = generate_report(all_results, output_dir)
    print(f"✅  Report saved to: {report_path}")

    # ── Comparison report ──────────────────────────────────────
    if compare_run:
        if os.path.exists(compare_run):
            try:
                results1 = load_results(compare_run)
                results2 = {"results": all_results, "timestamp": datetime.now().isoformat()}
                comparison = compare_results(results1, results2)
                comparison_path = os.path.join(output_dir, f"comparison_{timestamp}.html")
                generate_comparison_html(results1, results2, comparison, comparison_path)
                print(f"📊  Comparison report saved to: {comparison_path}")
            except Exception as e:
                print(f"⚠️   Failed to generate comparison report: {e}")
        else:
            print(f"⚠️   Comparison file not found: {compare_run}")

    # ── Cost summary ──────────────────────────────────────────
    usage_by_evaluator = {name: ev.get_usage() for name, ev in evaluators.items()}
    cost_report = format_cost_report(usage_by_evaluator, model, pricing)
    print(cost_report)

    if cache_hits_counter[0] > 0:
        print(f"💾  Cache hits: {cache_hits_counter[0]} (avoided {cache_hits_counter[0]} LLM calls)")

    # ── CI/CD exit status (Feature 3) ─────────────────────────
    exit_code, status_msg = _compute_exit_status(all_results, min_pass_rate, fail_on_critical)
    if min_pass_rate is not None or fail_on_critical:
        icon = "✅" if exit_code == 0 else "❌"
        print(f"\n{icon}  CI/CD check: {status_msg}")

    return report_path, exit_code


# ─────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="LLM Eval Framework",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python run_eval.py --csv test_cases/sample.csv\n"
            "  python run_eval.py --csv test_cases/sample.csv --dry-run\n"
            "  python run_eval.py --csv test_cases/sample.csv --min-pass-rate 0.8\n"
            "  python run_eval.py --csv test_cases/sample.csv --fail-on-critical\n"
            "  python run_eval.py --csv test_cases/sample.csv --severity Critical,Major\n"
            "  python run_eval.py --csv test_cases/sample.csv --eval-types safety,refusal\n"
            "  python run_eval.py --csv test_cases/sample.csv --compare outputs/results_20260305_120000.json\n"
        ),
    )
    parser.add_argument("--csv",             required=True,       help="Path to test cases CSV")
    parser.add_argument("--config",          default="config.yaml", help="Path to config.yaml")
    parser.add_argument("--dry-run",         action="store_true", help="Validate CSV + config without calling any APIs")
    parser.add_argument("--custom-eval-dir", default=None,        help="Path to directory with custom evaluator Python files")
    parser.add_argument("--cache-dir",       default="outputs/cache", help="Path to cache directory (default: outputs/cache)")
    parser.add_argument("--clear-cache",     action="store_true", help="Clear evaluation cache before running")
    parser.add_argument("--compare",         default=None,        help="Path to previous results JSON for comparison report")
    # Feature 1: parallelism
    parser.add_argument("--max-concurrency", type=int,   default=10,   help="Max parallel LLM calls (default: 10)")
    # Feature 3: CI/CD thresholds
    parser.add_argument("--min-pass-rate",   type=float, default=None, help="Exit code 1 if overall pass rate is below this (e.g. 0.8)")
    parser.add_argument("--fail-on-critical", action="store_true",     help="Exit code 1 if any Critical severity test has a FAIL")
    # Feature 6: filtering
    parser.add_argument("--severity",   default=None, help="Only run tests with these severities (e.g. Critical,Major)")
    parser.add_argument("--test-ids",   default=None, help="Only run specific test IDs (e.g. tc_001,tc_003)")
    parser.add_argument("--eval-types", default=None, dest="filter_eval_types",
                        help="Only run these evaluator types per test (e.g. safety,refusal)")
    args = parser.parse_args()

    if args.dry_run:
        ok = dry_run(
            args.csv, args.config, args.custom_eval_dir,
            severity_filter=args.severity,
            test_id_filter=args.test_ids,
            eval_type_filter=args.filter_eval_types,
        )
        sys.exit(0 if ok else 1)

    try:
        report_path, exit_code = asyncio.run(run(
            args.csv,
            args.config,
            custom_eval_dir=args.custom_eval_dir,
            cache_dir=args.cache_dir,
            clear_cache=args.clear_cache,
            compare_run=args.compare,
            max_concurrency=args.max_concurrency,
            min_pass_rate=args.min_pass_rate,
            fail_on_critical=args.fail_on_critical,
            severity_filter=args.severity,
            test_id_filter=args.test_ids,
            eval_type_filter=args.filter_eval_types,
        ))
        sys.exit(exit_code)
    except (FileNotFoundError, KeyError) as e:
        print(f"❌  Config/file error: {e}", file=sys.stderr)
        sys.exit(2)
    except yaml.YAMLError as e:
        print(f"❌  Config parse error: {e}", file=sys.stderr)
        sys.exit(2)
    except Exception as e:
        print(f"❌  Runtime error: {e}", file=sys.stderr)
        sys.exit(3)
