"""
Token cost estimation utilities.
Pricing is read from config.yaml (pricing section).
Falls back to hardcoded defaults if model not found in config.
"""

# Fallback pricing (USD per 1M tokens) if not in config
FALLBACK_PRICING = {
    "gpt-4o":         {"input": 2.50,  "output": 10.00},
    "gpt-4o-mini":    {"input": 0.15,  "output": 0.60},
    "gpt-4-turbo":    {"input": 10.00, "output": 30.00},
    "gpt-3.5-turbo":  {"input": 0.50,  "output": 1.50},
}


def get_price_per_million(model: str, config_pricing: dict) -> dict:
    """Return input/output price per 1M tokens for a given model."""
    # Try config first, then fallback, then unknown
    pricing = config_pricing or {}
    try:
        if model in pricing:
            return {"input": float(pricing[model]["input"]), "output": float(pricing[model]["output"]), "unknown": False}
        if model in FALLBACK_PRICING:
            return {**FALLBACK_PRICING[model], "unknown": False}
        # Unknown model — return 0 but flag it
        return {"input": 0.0, "output": 0.0, "unknown": True}
    except (KeyError, ValueError, TypeError) as e:
        # Fallback if config pricing is malformed
        return {"input": 0.0, "output": 0.0, "unknown": True}


def calculate_cost(prompt_tokens: int, completion_tokens: int, model: str, config_pricing: dict) -> dict:
    """
    Returns a dict with:
      prompt_tokens, completion_tokens, total_tokens,
      input_cost_usd, output_cost_usd, total_cost_usd,
      model, price_known
    """
    prices = get_price_per_million(model, config_pricing)
    price_known = not prices.get("unknown", False)

    input_cost  = (prompt_tokens     / 1_000_000) * prices["input"]
    output_cost = (completion_tokens / 1_000_000) * prices["output"]

    return {
        "prompt_tokens":     prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens":      prompt_tokens + completion_tokens,
        "input_cost_usd":    round(input_cost,  6),
        "output_cost_usd":   round(output_cost, 6),
        "total_cost_usd":    round(input_cost + output_cost, 6),
        "model":             model,
        "price_known":       price_known,
    }


def format_cost_report(usage_by_evaluator: dict, model: str, config_pricing: dict) -> str:
    """
    Accepts:
      usage_by_evaluator = {
        "quality": {"prompt_tokens": N, "completion_tokens": N, "calls": N},
        ...
      }
    Returns a formatted string for terminal output.
    """
    lines = ["\n💰 Token Usage & Cost Estimate", "─" * 62]
    lines.append(f"  {'Evaluator':<18} {'Calls':>5}  {'Prompt':>8}  {'Completion':>10}  {'Cost (USD)':>12}")
    lines.append("  " + "─" * 58)

    grand_prompt     = 0
    grand_completion = 0
    grand_cost       = 0.0
    price_warning    = False

    for name, usage in usage_by_evaluator.items():
        p  = usage.get("prompt_tokens", 0)
        c  = usage.get("completion_tokens", 0)
        calls = usage.get("calls", 0)
        cost = calculate_cost(p, c, model, config_pricing)
        if not cost["price_known"]:
            price_warning = True
        grand_prompt     += p
        grand_completion += c
        grand_cost       += cost["total_cost_usd"]
        lines.append(
            f"  {name:<18} {calls:>5}  {p:>8,}  {c:>10,}  ${cost['total_cost_usd']:>11.6f}"
        )

    lines.append("  " + "─" * 58)
    grand_total_cost = calculate_cost(grand_prompt, grand_completion, model, config_pricing)
    lines.append(
        f"  {'TOTAL':<18} {'':>5}  {grand_prompt:>8,}  {grand_completion:>10,}  ${grand_total_cost['total_cost_usd']:>11.6f}"
    )
    lines.append(f"\n  Model: {model}")
    if price_warning:
        lines.append("  ⚠️  Model not in pricing table — cost shown as $0. Update config.yaml pricing section.")
    else:
        lines.append("  ℹ️  Prices are estimates. Verify against your OpenAI usage dashboard.")
    lines.append("")
    return "\n".join(lines)
