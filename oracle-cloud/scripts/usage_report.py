#!/usr/bin/env python3
"""
Generate daily usage report from OpenTelemetry trace file.
"""

import os, sys, json, datetime, pathlib, argparse
from collections import defaultdict

DATA_DIR = pathlib.Path.home() / "otel" / "data"
REPORTS_DIR = pathlib.Path.home() / "reports" / "usage"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

# Simple cost estimates (USD per 1M tokens or per token?). We'll use per token fraction.
# Provide rates per 1K tokens.
COST_TABLE_1K = {
    # model -> (input_per_1k, output_per_1k)
    "openai/gpt-4o": (0.005, 0.015),
    "openai/gpt-4-turbo": (0.01, 0.03),
    "openai/gpt-3.5-turbo": (0.0005, 0.0015),
    "anthropic/claude-3-opus": (0.015, 0.075),
    "anthropic/claude-3-sonnet": (0.003, 0.015),
    "meta-llama/llama-3.1-70b-instruct": (0.0007, 0.0007),
    "google/gemini-2.0-flash-001": (0.000075, 0.00030),
    "default": (0.001, 0.002),
}

def get_cost(model, input_tokens, output_tokens):
    rates = COST_TABLE_1K.get(model, COST_TABLE_1K["default"])
    return (input_tokens / 1000) * rates[0] + (output_tokens / 1000) * rates[1]

def ns_to_datetime(ns):
    # ns string to datetime in Chicago timezone
    sec = int(ns) / 1e9
    utc_dt = datetime.datetime.fromtimestamp(sec, tz=datetime.timezone.utc)
    # Convert to America/Chicago (assuming system has zoneinfo; if not, use pytz or use offset)
    try:
        import zoneinfo
        chicago = zoneinfo.ZoneInfo("America/Chicago")
        return utc_dt.astimezone(chicago)
    except Exception:
        # Fallback: use fixed offset if zoneinfo not available (Python 3.9+ has it)
        offset = -5  # CST; approximate, ignore DST
        return utc_dt + datetime.timedelta(hours=offset)

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", help="Report date (YYYY-MM-DD), default is today (America/Chicago)")
    parser.add_argument("--output-dir", default=str(REPORTS_DIR))
    args = parser.parse_args()
    if args.date:
        target_date = datetime.date.fromisoformat(args.date)
    else:
        # Get today in Chicago
        now = datetime.datetime.now(datetime.timezone.utc)
        try:
            import zoneinfo
            chicago = zoneinfo.ZoneInfo("America/Chicago")
            now_chicago = now.astimezone(chicago)
        except Exception:
            now_chicago = now - datetime.timedelta(hours=5)
        target_date = now_chicago.date()
    return target_date, args.output_dir

def main():
    target_date, output_dir = parse_args()
    date_str = target_date.isoformat()
    filename = DATA_DIR / f"traces-{date_str}.jsonl"
    # If file not found, fall back to traces-*.jsonl for that date? Actually we already used date. If not found, maybe no traces.
    if not filename.exists():
        # Also check if there is a traces.jsonl legacy file (process all)
        legacy = DATA_DIR / "traces.jsonl"
        if legacy.exists():
            print(f"Using legacy file {legacy} (no date match)")
            file_to_use = legacy
        else:
            print(f"No trace file for {date_str} at {filename}")
            # Create empty report
            report_path = pathlib.Path(output_dir) / f"{date_str}.md"
            report_path.write_text(f"# Usage Report — {date_str}\n\nNo data available.\n")
            return
    else:
        file_to_use = filename

    # Aggregation structures
    stats_by_model = defaultdict(lambda: {"requests": 0, "input": 0, "output": 0, "cost": 0.0})
    total_requests = 0
    total_input = 0
    total_output = 0
    total_cost = 0.0

    # Process each line
    with open(file_to_use) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue
            # Iterate spans
            for rs in data.get("resourceSpans", []):
                for ss in rs.get("scopeSpans", []):
                    for span in ss.get("spans", []):
                        # Determine the span's local date in Chicago
                        start_ns = span.get("startTimeUnixNano")
                        if not start_ns:
                            continue
                        try:
                            span_dt = ns_to_datetime(start_ns)
                        except Exception:
                            continue
                        # If span date != target_date, skip
                        if span_dt.date() != target_date:
                            continue

                        attrs = {a["key"]: a["value"] for a in span.get("attributes", [])}
                        # Extract model: try gen_ai.request.model
                        model = None
                        for key in ["gen_ai.request.model", "gen_ai.response.model", "model"]:
                            if key in attrs:
                                v = attrs[key]
                                if isinstance(v, dict):
                                    model = v.get("stringValue") or v.get("intValue") or str(v)
                                else:
                                    model = str(v)
                                break
                        if not model:
                            model = "unknown"

                        # Extract token counts
                        input_tokens = 0
                        output_tokens = 0
                        # Look for gen_ai.usage.input_tokens (int) and output
                        for input_key in ["gen_ai.usage.input_tokens", "gen_ai.prompt_tokens", "prompt_tokens"]:
                            if input_key in attrs:
                                v = attrs[input_key]
                                if isinstance(v, dict):
                                    input_tokens = int(v.get("intValue", 0))
                                else:
                                    input_tokens = int(v)
                                break
                        for output_key in ["gen_ai.usage.output_tokens", "gen_ai.completion_tokens", "completion_tokens"]:
                            if output_key in attrs:
                                v = attrs[output_key]
                                if isinstance(v, dict):
                                    output_tokens = int(v.get("intValue", 0))
                                else:
                                    output_tokens = int(v)
                                break
                        # If total available, we could use that but not needed
                        request_cost = get_cost(model, input_tokens, output_tokens)

                        # Accumulate
                        stats_by_model[model]["requests"] += 1
                        stats_by_model[model]["input"] += input_tokens
                        stats_by_model[model]["output"] += output_tokens
                        stats_by_model[model]["cost"] += request_cost

                        total_requests += 1
                        total_input += input_tokens
                        total_output += output_tokens
                        total_cost += request_cost

    # Generate report
    lines = []
    lines.append(f"# Usage Report — {date_str}")
    lines.append("")
    lines.append("## Summary")
    lines.append(f"- Total requests: {total_requests}")
    lines.append(f"- Total prompt/input tokens: {total_input:,}")
    lines.append(f"- Total completion/output tokens: {total_output:,}")
    lines.append(f"- Total tokens: {total_input + total_output:,}")
    lines.append(f"- Estimated cost: ${total_cost:.4f}")
    lines.append("")
    if stats_by_model:
        lines.append("## By Model")
        lines.append("")
        lines.append("| Model | Requests | Input | Output | Est. Cost |")
        lines.append("|-------|----------|--------|--------|-----------|")
        for model, stats in sorted(stats_by_model.items(), key=lambda kv: kv[1]["cost"], reverse=True):
            lines.append(f"| {model} | {stats['requests']} | {stats['input']:,} | {stats['output']:,} | ${stats['cost']:.4f} |")
        lines.append("")
    lines.append("*Note: Cost estimates are based on approximate public rates; actual OpenRouter pricing may vary.*")

    report_file = pathlib.Path(output_dir) / f"{date_str}.md"
    report_file.write_text("\n".join(lines))

    # Update cumulative summary
    cum_file = pathlib.Path(output_dir) / "CUMULATIVE.md"
    if cum_file.exists():
        cum_lines = cum_file.read_text().splitlines()
    else:
        cum_lines = ["# Cumulative Usage Summary", ""]
    # Insert today's summary after header if empty
    # Prepend today's block
    new_block = [f"## {date_str}", "",
                 f"- Requests: {total_requests}",
                 f"- Tokens: {total_input + total_output:,}",
                 f"- Cost: ${total_cost:.4f}", ""]
    # Insert after header lines (first two lines) if the file has data after header
    cum_lines = cum_lines[:2] + new_block + cum_lines[2:]
    cum_file.write_text("\n".join(cum_lines))

    print(f"Report written to {report_file}")
    print(f"Cumulative updated: {cum_file}")

if __name__ == "__main__":
    main()
