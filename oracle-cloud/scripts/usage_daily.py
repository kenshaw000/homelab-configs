#!/usr/bin/env python3
"""
Aggregate OpenTelemetry traces into daily usage metrics and report.
Reads from ~/otel/data/traces.jsonl (JSON Lines)
Writes to ~/reports/usage/YYYY-MM-DD.md
Also updates a master summary: ~/reports/usage/CUMULATIVE.md
"""

import os, sys, json, datetime, pathlib, re
from collections import defaultdict

WORKSPACE = pathlib.Path.home() / ".openclaw" / "workspace"
TRACES_FILE = pathlib.Path.home() / "otel" / "data" / "traces.jsonl"
REPORTS_DIR = pathlib.Path.home() / "reports" / "usage"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

# Simple cost table (USD per 1K tokens). Extend as needed.
COST_TABLE = {
    # OpenRouter models (approximate, update as needed)
    "openai/gpt-4o": {"prompt": 0.005, "completion": 0.015},
    "openai/gpt-4-turbo": {"prompt": 0.01, "completion": 0.03},
    "openai/gpt-3.5-turbo": {"prompt": 0.0005, "completion": 0.0015},
    "anthropic/claude-3-opus": {"prompt": 0.015, "completion": 0.075},
    "anthropic/claude-3-sonnet": {"prompt": 0.003, "completion": 0.015},
    "meta-llama/llama-3.1-70b-instruct": {"prompt": 0.0007, "completion": 0.0007},
    "google/gemini-2.0-flash-001": {"prompt": 0.000075, "completion": 0.00030},
    # default fallback if model not found
    "default": {"prompt": 0.001, "completion": 0.002},
}

def get_cost(model, prompt_tokens, completion_tokens):
    rates = COST_TABLE.get(model, COST_TABLE["default"])
    return (prompt_tokens / 1000) * rates["prompt"] + (completion_tokens / 1000) * rates["completion"]

def main():
    today = datetime.date.today().isoformat()
    entries = []
    # Read today's traces (filter by date in span start time if available)
    if TRACES_FILE.exists():
        for line in TRACES_FILE.read_text().splitlines():
            try:
                data = json.loads(line)
                # Collect ResourceSpans -> ScopeSpans -> Spans
                for rs in data.get("resourceSpans", []):
                    for ss in rs.get("scopeSpans", []):
                        for span in ss.get("spans", []):
                            # Extract timestamp; if none or old, skip if not today?
                            # For simplicity, include all; later we could filter.
                            attrs = {a["key"]: a["value"].get("stringValue") or a["value"].get("intValue") for a in span.get("attributes", [])}
                            # Basic required fields
                            model = attrs.get("gen_ai.model", attrs.get("model", "unknown"))
                            prompt_tokens = int(attrs.get("gen_ai.prompt_tokens", attrs.get("prompt_tokens", 0)))
                            completion_tokens = int(attrs.get("gen_ai.completion_tokens", attrs.get("completion_tokens", 0)))
                            total_tokens = prompt_tokens + completion_tokens
                            # Cost estimate
                            cost = get_cost(model, prompt_tokens, completion_tokens)
                            entries.append({
                                "model": model,
                                "prompt_tokens": prompt_tokens,
                                "completion_tokens": completion_tokens,
                                "total_tokens": total_tokens,
                                "cost": cost,
                            })
            except Exception as e:
                continue  # skip malformed lines

    # Aggregate
    totals = defaultdict(lambda: {"requests": 0, "prompt": 0, "completion": 0, "total": 0, "cost": 0.0})
    grand = {"requests": 0, "prompt": 0, "completion": 0, "total": 0, "cost": 0.0}
    for e in entries:
        m = e["model"]
        totals[m]["requests"] += 1
        totals[m]["prompt"] += e["prompt_tokens"]
        totals[m]["completion"] += e["completion_tokens"]
        totals[m]["total"] += e["total_tokens"]
        totals[m]["cost"] += e["cost"]
        grand["requests"] += 1
        grand["prompt"] += e["prompt_tokens"]
        grand["completion"] += e["completion_tokens"]
        grand["total"] += e["total_tokens"]
        grand["cost"] += e["cost"]

    # Build report
    lines = []
    lines.append(f"# Usage Report — {today}")
    lines.append("")
    lines.append("## Summary")
    lines.append(f"- Total requests: {grand['requests']}")
    lines.append(f"- Total prompt tokens: {grand['prompt']:,}")
    lines.append(f"- Total completion tokens: {grand['completion']:,}")
    lines.append(f"- Total tokens: {grand['total']:,}")
    lines.append(f"- Estimated cost: ${grand['cost']:.4f}")
    lines.append("")
    lines.append("## By Model")
    lines.append("")
    lines.append("| Model | Requests | Prompt | Completion | Total | Est. Cost |")
    lines.append("|-------|----------|--------|------------|-------|-----------|")
    for model, stats in sorted(totals.items(), key=lambda kv: kv[1]["cost"], reverse=True):
        lines.append(f"| {model} | {stats['requests']} | {stats['prompt']:,} | {stats['completion']:,} | {stats['total']:,} | ${stats['cost']:.4f} |")
    lines.append("")
    lines.append("*Note: Cost estimates use rough rates; actual OpenRouter pricing may vary.*")

    report_file = REPORTS_DIR / f"{today}.md"
    report_file.write_text("\n".join(lines))

    # Update cumulative summary (append or rewrite)
    cum_file = REPORTS_DIR / "CUMULATIVE.md"
    cum_lines = []
    if cum_file.exists():
        cum_lines = cum_file.read_text().splitlines()
    # Prepend today's summary section
    cum_lines.insert(0, f"## {today}")
    cum_lines.insert(1, "")
    cum_lines.insert(2, f"- Requests: {grand['requests']}")
    cum_lines.insert(3, f"- Tokens: {grand['total']:,}")
    cum_lines.insert(4, f"- Cost: ${grand['cost']:.4f}")
    cum_lines.insert(5, "")
    cum_file.write_text("\n".join(cum_lines))

    print(f"Report written to {report_file}")
    print(f"Cumulative updated: {cum_file}")

if __name__ == "__main__":
    main()
