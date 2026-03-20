#!/usr/bin/env python3
"""
Diabetes Bot Demo — AI Bot Testing Framework Example

This script demonstrates how to test a real, domain-specific LLM bot using the framework.
The Diabetes Bot is a specialized assistant that answers only diabetes-related questions
with built-in guardrails and RAG support.

Usage:
  python run_diabetes_demo.py --csv test_cases/diabetes_tests.csv
  python run_diabetes_demo.py --csv test_cases/diabetes_tests.csv --dry-run
  python run_diabetes_demo.py --csv test_cases/diabetes_tests.csv --clear-cache

Features:
  - Uses the same OpenAI API key as the judge
  - Real LLM-powered bot with medical guardrails
  - RAG support via knowledge_base/diabetes_kb.md
  - Caching to avoid redundant LLM calls
  - Full evaluation with quality, safety, RAG, and refusal metrics
  - Beautiful HTML reports
  - Cost tracking
"""

import argparse
import csv
import hashlib
import json
import os
import sys
import yaml
from datetime import datetime
from openai import OpenAI

# Framework imports
from connectors.diabetes_bot import DiabetesBotConnector
from evaluators.quality import QualityEvaluator
from evaluators.safety import SafetyEvaluator
from evaluators.rag import RAGEvaluator
from evaluators.refusal import RefusalEvaluator
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
KNOWN_EVAL_TYPES = {"quality", "safety", "rag", "refusal"}
VALID_SEVERITIES = {"Critical", "Major", "Minor", ""}
PLACEHOLDER_KEY = "sk-your-key-here"

# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────

def _compute_prompt_hash(evaluator, eval_type: str) -> str:
    """Compute hash of evaluator's prompt configuration.

    This ensures cache invalidation when evaluator prompt, memory, or instructions change.
    """
    # Combine all prompt-affecting configuration
    prompt_config = f"{eval_type}|{evaluator.instructions}|{evaluator.memory}|{evaluator.model}|{evaluator.temperature}"
    return hashlib.sha256(prompt_config.encode()).hexdigest()

# ─────────────────────────────────────────────

# ─────────────────────────────────────────────
# Loaders
# ─────────────────────────────────────────────


def load_config(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
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
# Dry-run validation
# ─────────────────────────────────────────────


def _ok(msg):
    return f"  ✅  {msg}"


def _err(msg):
    return f"  ❌  {msg}"


def _warn(msg):
    return f"  ⚠️   {msg}"


def dry_run(csv_path: str, config_path: str) -> bool:
    """
    Validate config + CSV without calling any APIs.
    Returns True if all checks pass, False otherwise.
    """
    print("\n🔍  DRY RUN — Diabetes Bot Demo — Preflight Validation")
    print("═" * 60)
    errors = []

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
        actual_cols = set(test_cases[0].keys()) - {"eval_types"}
        actual_cols.add("eval_types")
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
            print(
                _err(
                    f"Unknown eval_types: {', '.join(sorted(unknown))}  (known: {', '.join(sorted(known_eval_types))})"
                )
            )
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
            print(_warn(f"Unrecognised severity values: {', '.join(sorted(bad_sev))}"))
        else:
            print(_ok("Severity values valid"))

    # ── Test case breakdown ────────────────────────────────────
    if test_cases:
        print("\n  TEST CASE BREAKDOWN")
        from collections import Counter

        et_counts = Counter(et for tc in test_cases for et in tc.get("eval_types", []))
        sev_counts = Counter(tc.get("severity", "—").strip() or "—" for tc in test_cases)

        print(f"  {'Eval Type':<14}  Count")
        for k, v in sorted(et_counts.items()):
            print(f"    {k:<12}  {v}")
        print(f"\n  {'Severity':<14}  Count")
        for k, v in sorted(sev_counts.items()):
            print(f"    {k:<12}  {v}")

        # Cost estimate
        if config:
            model = (config.get("openai") or {}).get("judge_model", "unknown")
            max_tokens = (config.get("evaluation") or {}).get("max_tokens", 512)
            pricing = config.get("pricing", {})
            from utils.cost import get_price_per_million

            prices = get_price_per_million(model, pricing)
            total_calls = sum(len(tc.get("eval_types", [])) for tc in test_cases)
            est_input = total_calls * 600
            est_output = total_calls * max_tokens
            # Also estimate diabetes bot calls (roughly 600 tokens input, 200 output per call)
            diabetes_bot_calls = len(test_cases)
            diabetes_input = diabetes_bot_calls * 600
            diabetes_output = diabetes_bot_calls * 200
            total_input = est_input + diabetes_input
            total_output = est_output + diabetes_output
            est_cost = (total_input / 1_000_000) * prices["input"] + (
                total_output / 1_000_000
            ) * prices["output"]
            print(f"\n  ESTIMATED COST (rough, {model})")
            print(f"    ~{total_calls} evaluator calls + ~{diabetes_bot_calls} diabetes bot calls")
            print(f"    ~{total_input:,} input tokens  |  ~{total_output:,} output tokens")
            print(f"    Estimated cost: ~${est_cost:.4f} USD")

    # ── Final result ───────────────────────────────────────────
    print("\n" + "═" * 60)
    if errors:
        print(f"\n❌  Validation FAILED — {len(errors)} error(s). Fix before running.\n")
        return False
    else:
        print(f"\n✅  Validation passed — ready to run:")
        print(f"    python run_diabetes_demo.py --csv {csv_path}\n")
        return True


# ─────────────────────────────────────────────
# Main run
# ─────────────────────────────────────────────


def run(
    csv_path: str,
    config_path: str = "config.yaml",
    cache_dir: str = "outputs/cache",
    clear_cache: bool = False,
    compare_run: str = None,
):
    """Run evaluation with the Diabetes Bot."""
    config = load_config(config_path)
    api_key = config["openai"]["api_key"]
    model = config["openai"]["judge_model"]
    temperature = config["evaluation"]["temperature"]
    max_tokens = config["evaluation"]["max_tokens"]
    output_dir = config["output"]["reports_dir"]
    pricing = config.get("pricing", {})

    # ── Caching ────────────────────────────────────────────────
    cache = EvaluationCache(cache_dir)
    if clear_cache:
        cache.clear()
    else:
        stats = cache.stats()
        if stats["total_entries"] > 0:
            print(f"💾  Cache: {stats['total_entries']} cached evaluations available")

    # ── Load evaluation context ────────────────────────────────
    memory = load_optional_md("memory.md")
    instructions = load_optional_md("instructions.md")

    if memory:
        print("📋  memory.md loaded — bot context injected into judge prompts")
    if instructions:
        print("📐  instructions.md loaded — custom eval rules injected into judge prompts")

    # ── Load knowledge base for RAG ────────────────────────────
    knowledge_base = load_optional_md("knowledge_base/diabetes_kb.md")
    if knowledge_base:
        print("📚  knowledge_base/diabetes_kb.md loaded — ready for RAG tests")

    client = OpenAI(api_key=api_key)

    # ── Diabetes Bot ───────────────────────────────────────────
    bot = DiabetesBotConnector(
        client=client, model=model, temperature=0.7, max_tokens=512
    )
    print(f"🩺  Diabetes Bot initialized with {model}")

    # ── Evaluators ────────────────────────────────────────────
    kwargs = dict(
        client=client,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        memory=memory,
        instructions=instructions,
    )
    evaluators = {
        "quality": QualityEvaluator(**kwargs),
        "safety": SafetyEvaluator(**kwargs),
        "rag": RAGEvaluator(**kwargs),
        "refusal": RefusalEvaluator(**kwargs),
    }

    test_cases = load_test_cases(csv_path)
    all_results = []

    print(f"\n🧪  Running {len(test_cases)} diabetes test cases...\n")

    cache_hits = 0
    for i, tc in enumerate(test_cases, 1):
        print(f"  [{i}/{len(test_cases)}] {tc['test_id']}: {tc['input'][:60]}...")

        # Use knowledge base as context for RAG tests
        bot_context = knowledge_base if "rag" in tc.get("eval_types", []) else ""
        tc["bot_response"] = bot.get_response(tc["input"], context=bot_context)

        metrics = {}
        for eval_type in tc["eval_types"]:
            if eval_type in evaluators:
                # Check cache first
                prompt_hash = _compute_prompt_hash(evaluators[eval_type], eval_type)
                cached_result, timestamp = cache.get(tc["test_id"], eval_type, tc["bot_response"], prompt_hash)
                if cached_result:
                    result = cached_result
                    cache_hits += 1
                    print(f"    ✓ {eval_type} (cached)")
                else:
                    result = evaluators[eval_type].evaluate(tc)
                    cache.set(tc["test_id"], eval_type, tc["bot_response"], result, prompt_hash)
                metrics.update(result)
            else:
                print(f"    ⚠️   Unknown eval type: '{eval_type}' — skipping")

        all_results.append(
            {
                "test_id": tc["test_id"],
                "input": tc["input"],
                "bot_response": tc["bot_response"],
                "severity": tc.get("severity", "").strip(),
                "notes": tc.get("notes", "").strip(),
                "metrics": metrics,
            }
        )

    # ── Save results as JSON ───────────────────────────────────
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = os.path.join(output_dir, f"results_{timestamp}.json")
    os.makedirs(output_dir, exist_ok=True)
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "timestamp": datetime.now().isoformat(),
                "csv_path": csv_path,
                "model": model,
                "bot_type": "diabetes",
                "results": all_results,
            },
            f,
            indent=2,
        )
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

    if cache_hits > 0:
        print(f"💾  Cache hits: {cache_hits} (avoided {cache_hits} LLM calls)")

    return report_path


# ─────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Diabetes Bot Demo — AI Bot Testing Framework",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python run_diabetes_demo.py --csv test_cases/diabetes_tests.csv\n"
            "  python run_diabetes_demo.py --csv test_cases/diabetes_tests.csv --dry-run\n"
            "  python run_diabetes_demo.py --csv test_cases/diabetes_tests.csv --clear-cache\n"
        ),
    )
    parser.add_argument("--csv", required=True, help="Path to test cases CSV")
    parser.add_argument("--config", default="config.yaml", help="Path to config.yaml")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate CSV + config without calling any APIs",
    )
    parser.add_argument(
        "--cache-dir", default="outputs/cache", help="Path to cache directory (default: outputs/cache)"
    )
    parser.add_argument("--clear-cache", action="store_true", help="Clear evaluation cache before running")
    parser.add_argument(
        "--compare",
        default=None,
        help="Path to previous results JSON file for comparison report",
    )
    args = parser.parse_args()

    if args.dry_run:
        ok = dry_run(args.csv, args.config)
        sys.exit(0 if ok else 1)
    else:
        run(
            args.csv,
            args.config,
            cache_dir=args.cache_dir,
            clear_cache=args.clear_cache,
            compare_run=args.compare,
        )
