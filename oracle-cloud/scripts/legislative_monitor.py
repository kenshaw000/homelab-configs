#!/usr/bin/env python3
"""
Comprehensive monitor for Illinois political and legal activity:
- Legislative news for Sen. Michael Hastings and Rep. Bob Rita.
- Case tracking: Hastings v. Wadley et al. and related legal news.
Uses Google News RSS only; no API keys required.
"""

import os, sys, datetime, json, re, urllib.request, urllib.parse
from pathlib import Path

WORKSPACE = Path.home() / ".openclaw" / "workspace"
CACHE_FILE = WORKSPACE / "data" / "news_watch_cache.json"
MAX_PER_QUERY = 5

# Sources: Google News RSS queries
NEWS_QUERIES = {
    "Legislative – Hastings": "Michael Hastings Illinois",
    "Legislative – Rita": "Bob Rita Illinois",
    "Legal – Hastings Case": "Hastings v. Wadley",
    "Legal – Michael Hastings lawsuit": "Michael Hastings lawsuit",
    "Legal – Big Tent Coalition": "Big Tent Coalition Illinois"
}

def ensure_dirs():
    (WORKSPACE / "data").mkdir(parents=True, exist_ok=True)

def load_cache():
    if CACHE_FILE.exists():
        with open(CACHE_FILE) as f:
            return json.load(f)
    return {"seen_guids": [], "last_run": None}

def save_cache(cache):
    with open(CACHE_FILE, "w") as f:
        json.dump(cache, f, indent=2)

def fetch_news(query):
    url = f"https://news.google.com/rss/search?q={urllib.parse.quote(query)}&hl=en-US&gl=US&ceid=US:en"
    headlines = []
    guids = []
    try:
        with urllib.request.urlopen(url, timeout=15) as r:
            content = r.read().decode("utf-8", errors="replace")
            for m in re.finditer(r"<item[^>]*>(.*?)</item>", content, re.DOTALL):
                item = m.group(1)
                tmatch = re.search(r"<title[^>]*>([^<]+)</title>", item)
                gmatch = re.search(r"<guid[^>]*>([^<]+)</guid>", item)
                if tmatch:
                    title = tmatch.group(1).strip()
                    guid = (gmatch.group(1) if gmatch else title)[:200]
                    if title and " - " not in title and guid not in guids:
                        headlines.append(title)
                        guids.append(guid)
                if len(headlines) >= MAX_PER_QUERY:
                    break
    except Exception as e:
        print(f"Error fetching news for '{query}': {e}", file=sys.stderr)
    return headlines, guids

def main():
    ensure_dirs()
    cache = load_cache()
    seen_guids = set(cache.get("seen_guids", []))
    summary_lines = []
    all_new = []
    for section, query in NEWS_QUERIES.items():
        headlines, guids = fetch_news(query)
        new_titles = []
        for title, guid in zip(headlines, guids):
            if guid not in seen_guids:
                seen_guids.add(guid)
                new_titles.append(title)
                all_new.append((section, title))
        if new_titles:
            summary_lines.append(f"\n{section}:")
            for t in new_titles:
                summary_lines.append(f"- {t}")
        else:
            summary_lines.append(f"\n{section}: No new headlines.")
    # Update cache (keep recent only)
    cache["seen_guids"] = list(seen_guids)[-2000:]
    cache["last_run"] = datetime.date.today().isoformat()
    save_cache(cache)
    if not all_new:
        summary_lines.append("\nNo new headlines across monitored topics.")
    print("\n".join(summary_lines))

if __name__ == "__main__":
    main()
