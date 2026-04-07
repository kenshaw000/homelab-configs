#!/usr/bin/env python3
"""
Dale Cooper Agent - LinkedIn Job Search
Mission: Find the jobs. Filter the noise. Deliver the signal.
"""

import sys
import os
import json
import time
import logging
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional
import urllib.parse
import urllib.request

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Base directory is the workspace root
BASE_DIR = Path(__file__).parent.parent
CONFIG_PATH = BASE_DIR / "configs" / "cooper_criteria.json"
DATA_DIR = BASE_DIR / "data"
TRACKER_PATH = DATA_DIR / "job_tracker.json"
LOG_PATH = DATA_DIR / "cooper_search_log.jsonl"

# Ensure data directory exists
DATA_DIR.mkdir(parents=True, exist_ok=True)

class ConfigError(Exception):
    pass

def load_config() -> Dict[str, Any]:
    """Load JSON configuration. Fails fast if missing or malformed."""
    if not CONFIG_PATH.exists():
        raise ConfigError(f"Config file not found: {CONFIG_PATH}")

    try:
        with open(CONFIG_PATH) as f:
            config = json.load(f)
    except json.JSONDecodeError as e:
        raise ConfigError(f"Invalid JSON in config: {e}")

    # Validate essential keys
    required = ['search', 'max_results_per_query']
    for key in required:
        if key not in config:
            raise ConfigError(f"Missing required config key: {key}")

    return config

def load_tracker() -> List[Dict[str, Any]]:
    """Load existing job tracker or initialize empty list."""
    if TRACKER_PATH.exists():
        try:
            with open(TRACKER_PATH) as f:
                data = json.load(f)
                # Support both formats: simple list OR dict with 'active' array
                if isinstance(data, dict):
                    active = data.get('active', [])
                    # Also include 'expired' for deduplication window
                    expired = data.get('expired', [])
                    return active + expired
                elif isinstance(data, list):
                    return data
                else:
                    return []
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Failed to load tracker: {e}. Starting fresh.")
    return []

def save_tracker(tracker: List[Dict[str, Any]]) -> None:
    """Save tracker atomically. Maintains active/expired structure based on 'active' flag."""
    # Load existing to preserve expired section
    existing = {"active": [], "expired": [], "last_checked": datetime.utcnow().isoformat() + 'Z', "total_original": len(tracker)}
    if TRACKER_PATH.exists():
        try:
            with open(TRACKER_PATH) as f:
                existing = json.load(f)
        except Exception:
            pass

    # Filter current tracker into active/expired
    active = []
    expired = []
    for job in tracker:
        if job.get('active', True) is False:
            expired.append(job)
        else:
            active.append(job)

    # Build new structure
    new_data = {
        "active": active,
        "expired": existing.get("expired", []),  # keep historical expired
        "last_checked": datetime.utcnow().isoformat() + 'Z',
        "total_original": len(tracker)
    }

    # Save atomically
    temp_path = TRACKER_PATH.with_suffix('.tmp')
    with open(temp_path, 'w') as f:
        json.dump(new_data, f, indent=2)
    temp_path.replace(TRACKER_PATH)

def log_entry(entry: Dict[str, Any]) -> None:
    """Append a log line for debugging."""
    entry['_ts'] = datetime.utcnow().isoformat() + 'Z'
    with open(LOG_PATH, 'a') as f:
        f.write(json.dumps(entry) + '\n')

def normalize_text(s: str) -> str:
    """Collapse whitespace and strip."""
    return re.sub(r'\s+', ' ', s).strip() if s else ""

def build_query_string(titles: List[str], location: str) -> str:
    """Build LinkedIn guest API query (no login required)."""
    base = 'https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search/'
    params = {
        'keywords': ' '.join(titles),
        'location': location
    }
    return f"{base}?{urllib.parse.urlencode(params)}"

def fetch_with_retry(url: str, config: Dict[str, Any]) -> Optional[str]:
    """HTTP GET with retry logic and rate limiting using urllib."""
    headers = {
        'User-Agent': config.get('user_agent', 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
    }
    delay = config.get('request_delay_seconds', 2)
    max_attempts = config.get('retry_attempts', 3)
    backoff = config.get('retry_backoff_factor', 2)
    timeout = config.get('timeout_seconds', 10)

    req = urllib.request.Request(url, headers=headers)

    for attempt in range(1, max_attempts + 1):
        try:
            logger.info(f"Fetching: {url} (attempt {attempt})")
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                if resp.status == 200:
                    time.sleep(delay)  # Be polite
                    return resp.read().decode('utf-8', errors='replace')
                elif resp.status == 429:
                    logger.warning("Rate limited (429). Backing off.")
                    time.sleep(delay * (backoff ** attempt))
                else:
                    logger.warning(f"HTTP {resp.status} for {url}")
                    time.sleep(delay)
        except urllib.error.HTTPError as e:
            if e.code == 429:
                logger.warning("Rate limited (429). Backing off.")
                time.sleep(delay * (backoff ** attempt))
            else:
                logger.error(f"HTTP error {e.code}: {e.reason}")
                time.sleep(delay)
        except urllib.error.URLError as e:
            logger.error(f"URL error: {e.reason}")
            time.sleep(delay * (backoff ** attempt))
        except Exception as e:
            logger.error(f"Request failed: {e}")
            time.sleep(delay * (backoff ** attempt))

    return None

def parse_linkedin_html(html: str, config: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Parse LinkedIn guest API HTML using regex (no external libraries)."""
    jobs = []

    # Extract each <li> block that contains a job card
    li_blocks = re.findall(r'<li[^>]*>(.*?)</li>', html, re.DOTALL)
    logger.info(f"Found {len(li_blocks)} <li> blocks")

    for block in li_blocks:
        # Quick filter: must contain 'job-search-card' or 'base-search-card'
        if 'job-search-card' not in block and 'base-search-card' not in block:
            continue

        # Title: inside <h3 class="base-search-card__title"> ... </h3>
        title_match = re.search(r'<h3[^>]*class="[^"]*base-search-card__title[^"]*"[^>]*>(.*?)</h3>', block, re.DOTALL)
        if not title_match:
            continue
        title = normalize_text(re.sub(r'<[^>]+>', '', title_match.group(1)))
        if not title:
            continue

        # Company: <h4 class="base-search-card__subtitle"><a ...>(.*?)</a>
        company = "Unknown"
        comp_match = re.search(r'<h4[^>]*class="[^"]*base-search-card__subtitle[^"]*"[^>]*>.*?<a[^>]*>(.*?)</a>', block, re.DOTALL)
        if comp_match:
            company = normalize_text(re.sub(r'<[^>]+>', '', comp_match.group(1)))

        # Location: <span class="job-search-card__location">(.*?)</span>
        location = "Unknown"
        loc_match = re.search(r'<span[^>]*class="[^"]*job-search-card__location[^"]*"[^>]*>(.*?)</span>', block, re.DOTALL)
        if loc_match:
            location = normalize_text(re.sub(r'<[^>]+>', '', loc_match.group(1)))

        # URL: <a class="base-card__full-link" href="...">
        url = None
        url_match = re.search(r'<a[^>]*class="[^"]*base-card__full-link[^"]*"[^>]*href="([^"]+)"', block, re.DOTALL)
        if url_match:
            href = url_match.group(1)
            if href.startswith('/'):
                url = f"https://www.linkedin.com{href}"
            else:
                url = href.split('?')[0]

        job = {
            'title': title,
            'company': company,
            'location': location,
            'salary': None,
            'url': url,
            'source': 'linkedin_direct',
            'fetched_at': datetime.utcnow().isoformat() + 'Z'
        }
        jobs.append(job)

    # Deduplicate by title+company within this batch
    seen = set()
    unique = []
    for job in jobs:
        key = (job['title'].lower(), job['company'].lower())
        if key not in seen:
            seen.add(key)
            unique.append(job)

    logger.info(f"Parsed {len(unique)} unique jobs from HTML")
    return unique

def google_site_search_fallback(query: str, config: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Use Google to search LinkedIn jobs; parse with regex."""
    google_url = f"https://www.google.com/search?q={urllib.parse.quote(query)}&num=20&tbs=qdr:d"  # past 24h
    html = fetch_with_retry(google_url, config)
    if not html:
        return []

    results = []

    # Find result blocks: anchor with href to linkedin.com/jobs/view/ and an h3
    pattern = r'<a\s+href="([^"]*linkedin\.com/jobs/view/[^"]*)"[^>]*>.*?<h3[^>]*>(.*?)</h3>'
    matches = re.findall(pattern, html, re.DOTALL | re.IGNORECASE)

    for href, title_html in matches:
        # Clean title
        title = normalize_text(re.sub(r'<[^>]+>', '', title_html))
        if not title:
            title = "LinkedIn Job"

        # Snippet extraction (optional)
        snippet = ""
        snippet_match = re.search(r'<a[^>]*href="' + re.escape(href) + r'"[^>]*>.*?(<div class="[^"]*(?:VwiC3b|s3v9rd)[^"]*">.*?)</div>', html, re.DOTALL | re.IGNORECASE)
        if snippet_match:
            snippet = normalize_text(re.sub(r'<[^>]+>', '', snippet_match.group(1)))
        else:
            after = html[html.find(href):]
            snippet_match2 = re.search(r'<div[^>]*>([^<]*?•[^<]*•[^<]*)</div>', after)
            if snippet_match2:
                snippet = normalize_text(snippet_match2.group(1))

        parts = snippet.split('•') if snippet else []
        company = "Unknown"
        location = "Unknown"
        if len(parts) >= 2:
            company = normalize_text(parts[0])
            location = normalize_text(parts[1])
        elif len(parts) == 1:
            location = normalize_text(parts[0])

        results.append({
            'title': title,
            'company': company,
            'location': location,
            'salary': None,
            'url': href.split('?')[0],
            'source': 'google_fallback',
            'fetched_at': datetime.utcnow().isoformat() + 'Z'
        })

    logger.info(f"Google fallback returned {len(results)} jobs")
    return results

def matches_criteria(job: Dict[str, Any], config: Dict[str, Any]) -> bool:
    """Filter job against criteria."""
    search_cfg = config['search']
    title_lower = job['title'].lower()

    # Must contain 'internal audit' (broad catch)
    if 'internal audit' not in title_lower:
        return False

    # Must contain a seniority indicator
    seniority_terms = ['head', 'chief', 'director', 'vp', 'vice president', 'svp', 'senior vice president', 'president', 'executive']
    if not any(term in title_lower for term in seniority_terms):
        return False

    # Salary check (if present)
    salary = job.get('salary')
    if salary:
        nums = re.findall(r'[\d,]+', str(salary))
        if nums:
            try:
                sal_val = int(nums[0].replace(',', ''))
                if sal_val < search_cfg.get('salary_min', 0):
                    return False
            except ValueError:
                pass

    # Location check using source_query_type when available
    loc = job['location'].lower()
    loc_ok = False
    qtype = job.get('source_query_type')
    for loc_type in search_cfg['locations']:
        typ = loc_type['type']
        q = loc_type['query'].lower()
        if typ in ('remote', 'hybrid'):
            # If we know the query type, trust it; otherwise check string
            if qtype == typ:
                loc_ok = True
                break
            if q in loc:
                loc_ok = True
                break
        elif typ in ('chicago_radius', 'tinley_park_25mi'):
            if 'chicago' in loc or '606' in loc or '605' in loc or '604' in loc:
                loc_ok = True
                break
    if not loc_ok:
        return False

    return True

def deduplicate_jobs(new_jobs: List[Dict[str, Any]], tracker: List[Dict[str, Any]], config: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Remove jobs already in tracker (by URL + title match within dedupe window)."""
    dedup_window = timedelta(days=config.get('deduplicate_window_days', 7))
    seen = set()
    for old in tracker:
        try:
            fetched = datetime.fromisoformat(old['fetched_at'].rstrip('Z'))
            if datetime.utcnow() - fetched < dedup_window:
                key = (old.get('url'), old.get('title'))
                if key[0]:
                    seen.add(key)
        except Exception:
            continue

    unique = []
    for job in new_jobs:
        key = (job.get('url'), job.get('title'))
        if key[0] and key in seen:
            continue
        unique.append(job)

    return unique

def format_brief(jobs: List[Dict[str, Any]], is_morning: bool, config: Dict[str, Any]) -> str:
    """Format WhatsApp brief."""
    now = datetime.now()
    time_str = now.strftime("%I:%M %p")
    date_str = now.strftime("%Y-%m-%d")

    header = f"*Dale Cooper Brief* — {date_str} {time_str}\n"
    if is_morning:
        header += "_Morning intel_\n"
    else:
        header += "_Evening update_\n"
    header += f"Criteria: {', '.join(config['search']['titles'][:3])}…\n\n"

    if not jobs:
        body = "No new job matches found."
    else:
        lines = []
        for job in jobs[:config.get('brief_max_items', 10)]:
            salary_part = f", {job['salary']}" if job.get('salary') else ""
            line = f"• {job['title']} — {job['company']} ({job['location']}{salary_part})"
            if job.get('url'):
                line += f"\n  {job['url']}"
            lines.append(line)
        body = "\n".join(lines)

    footer = f"\n\nTotal new: {len(jobs)}"
    full = header + body + footer
    if len(full) > config.get('max_message_length', 2000):
        full = full[:1997] + "..."
    return full

def search_linkedin_direct(config: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Perform direct LinkedIn searches using guest API."""
    all_jobs = []
    search_cfg = config['search']
    titles = search_cfg['titles']
    max_pages = config.get('pages_per_query', 3)

    # Build queries for each location type
    queries = []
    for loc_type in search_cfg['locations']:
        queries.append((loc_type['type'], build_query_string(titles, loc_type['query'])))

    # Execute each query
    for qtype, base_url in queries:
        for page in range(0, max_pages):
            page_url = f"{base_url}&start={page * 25}"
            html = fetch_with_retry(page_url, config)
            if not html:
                continue
            jobs = parse_linkedin_html(html, config)
            # Annotate each job with the source query type for context-aware filtering
            for job in jobs:
                job['source_query_type'] = qtype
            all_jobs.extend(jobs)
            if len(jobs) < 10:  # Last page or fewer results
                break

    logger.info(f"Direct LinkedIn search returned {len(all_jobs)} raw jobs")
    return all_jobs

def run_search(is_morning: bool) -> Dict[str, Any]:
    """
    Main entry point:
    1. Load config and tracker
    2. Search LinkedIn (direct + Google fallback)
    3. Filter, dedupe, update tracker
    4. Format and return brief
    """
    try:
        config = load_config()
        tracker = load_tracker()
    except ConfigError as e:
        logger.error(f"Configuration error: {e}")
        return {"error": str(e), "brief": "Configuration error – check logs."}

    # Search
    jobs = search_linkedin_direct(config)
    if len(jobs) < 5:  # If direct gave few results, try Google fallback
        logger.info("Direct search yielded few results; trying Google fallback...")
        fallback_query = f"site:linkedin.com/jobs {' OR '.join(config['search']['titles'][:5])} remote OR hybrid OR Chicago"
        fallback_jobs = google_site_search_fallback(fallback_query, config)
        jobs.extend(fallback_jobs)

    # Filter
    filtered = [j for j in jobs if matches_criteria(j, config)]
    logger.info(f"Filtered to {len(filtered)} jobs matching criteria")

    # Deduplicate against existing tracker
    new_jobs = deduplicate_jobs(filtered, tracker, config)

    # Deduplicate within this batch by URL (same job may appear from multiple location queries)
    unique_by_url = {}
    for job in new_jobs:
        if job.get('url'):
            unique_by_url[job['url']] = job
    new_jobs = list(unique_by_url.values())

    # Update tracker with new jobs
    for job in new_jobs:
        tracker.append(job)
    save_tracker(tracker)

    # Log
    log_entry({
        'run_type': 'morning' if is_morning else 'evening',
        'total_fetched': len(jobs),
        'total_filtered': len(filtered),
        'new_jobs': len(new_jobs)
    })

    # Format output
    brief = format_brief(new_jobs, is_morning, config)
    return {
        'brief': brief,
        'new_count': len(new_jobs),
        'total_in_tracker': len(tracker)
    }

def main():
    """CLI: Determine run type from arguments."""
    import argparse
    parser = argparse.ArgumentParser(description="Dale Cooper Job Search Agent")
    parser.add_argument('--morning', action='store_true', help='Generate morning brief')
    parser.add_argument('--evening', action='store_true', help='Generate evening brief')
    args = parser.parse_args()

    if not (args.morning or args.evening):
        logger.error("Specify either --morning or --evening")
        sys.exit(2)

    result = run_search(args.morning)
    if 'error' in result:
        print(f"ERROR: {result['error']}")
        sys.exit(1)
    print(result['brief'])
    sys.exit(0)

if __name__ == '__main__':
    main()