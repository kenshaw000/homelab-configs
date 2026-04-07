#!/usr/bin/env python3
"""
Job Tracker Validation Script
Checks LinkedIn job URLs to determine active/expired status.
Updates job_tracker.json with active flags and moves expired jobs to separate section.
"""

import json
import re
import time
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

# Configuration
WORKSPACE = Path("/home/ubuntu/.openclaw/workspace")
DATA_DIR = WORKSPACE / "data"
JOB_FILE = DATA_DIR / "job_tracker.json"

# Expiration indicators (case-insensitive)
EXPIRED_PHRASES = [
    "no longer accepting applications",
    "this job is no longer available",
    "job not found",
    "the job you are looking for is no longer available",
    "this position has been filled",
    "this job has been filled",
    "we're sorry, but this job is no longer available",
    "the job is closed",
    "this job has expired",
]

# Posting date patterns (common LinkedIn patterns)
POSTED_DATE_PATTERNS = [
    r"Posted\s+(\d+)\s+(hour|day|week|month|year)s?\s+ago",
    r"Posted\s+on\s+([A-Za-z]+ \d{1,2}, \d{4})",
    r"Posted\s+(\d{1,2})\s+([A-Za-z]{3})\s+(\d{4})",
    r"Posted\s+([A-Za-z]+ \d{1,2})(?:, \d{4})?",
]

def load_jobs():
    with open(JOB_FILE, 'r') as f:
        data = json.load(f)
    # Support both flat list (old format) and segmented format (new)
    if isinstance(data, list):
        return data
    elif isinstance(data, dict):
        jobs = []
        if "active" in data and isinstance(data["active"], list):
            jobs.extend(data["active"])
        if "expired" in data and isinstance(data["expired"], list):
            jobs.extend(data["expired"])
        return jobs
    else:
        raise ValueError("Invalid job_tracker.json format")

def save_jobs(data):
    with open(JOB_FILE, 'w') as f:
        json.dump(data, f, indent=2)

def fetch_url(url, timeout=10):
    """Fetch URL with a simple GET request using urllib."""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        req = Request(url, headers=headers)
        with urlopen(req, timeout=timeout) as response:
            content = response.read().decode('utf-8', errors='ignore')
            # Build a simple response-like object
            class SimpleResponse:
                def __init__(self, content, status=200):
                    self.text = content
                    self.status_code = status
            return SimpleResponse(content)
    except HTTPError as e:
        # HTTPError has a code attribute
        class SimpleResponse:
            def __init__(self, code):
                self.text = ""
                self.status_code = code
        return SimpleResponse(e.code)
    except URLError as e:
        print(f"Error fetching {url}: {e}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"Unexpected error fetching {url}: {e}", file=sys.stderr)
        return None

def is_expired(content, title=""):
    """Check if job page indicates expiration."""
    content_lower = content.lower()
    for phrase in EXPIRED_PHRASES:
        if phrase in content_lower:
            return True
    # Removed broad "sign in" check because LinkedIn job pages always contain sign-in links.
    return False

def extract_posted_date(content):
    """Try to extract the posting date from the page content."""
    for pattern in POSTED_DATE_PATTERNS:
        match = re.search(pattern, content, re.IGNORECASE)
        if match:
            return match.group(0)
    return None

def infer_work_type(location, source_type):
    """Infer work type from location string."""
    location_lower = location.lower()
    if "remote" in location_lower or "remote" in source_type.lower():
        return "Remote"
    elif "hybrid" in location_lower or "hybrid" in source_type.lower():
        return "Hybrid"
    elif "on-site" in location_lower or "on site" in location_lower or "onsite" in location_lower:
        return "On-site"
    else:
        # Default to on-site if location is a city
        if location and location != "Remote" and "metropolitan area" not in location_lower:
            return "On-site (assumed)"
        return "Unknown"

def validate_jobs():
    jobs = load_jobs()
    active_jobs = []
    expired_jobs = []

    print(f"Validating {len(jobs)} job listings...")

    for idx, job in enumerate(jobs):
        url = job.get("url")
        title = job.get("title", "Unknown")
        print(f"[{idx+1}/{len(jobs)}] Checking: {title}")

        response = fetch_url(url)
        if response is None:
            print(f"  -> Could not fetch")
            job["active"] = False
            job["checked_at"] = datetime.now(timezone.utc).isoformat()
            expired_jobs.append(job)
            time.sleep(2)
            continue

        if response.status_code != 200:
            print(f"  -> Status {response.status_code} - likely expired")
            job["active"] = False
            job["checked_at"] = datetime.now(timezone.utc).isoformat()
            expired_jobs.append(job)
            time.sleep(2)
            continue

        content = response.text
        if is_expired(content, title):
            print(f"  -> Expired (page indicates closed)")
            job["active"] = False
        else:
            print(f"  -> Active")
            job["active"] = True
            # Try to extract posting date if not already present
            if not job.get("date_posted"):
                posted = extract_posted_date(content)
                if posted:
                    job["date_posted"] = posted
                    print(f"     Found posted date: {posted}")

        job["checked_at"] = datetime.now(timezone.utc).isoformat()
        if job.get("active"):
            active_jobs.append(job)
        else:
            expired_jobs.append(job)

        time.sleep(2)  # Rate limiting

    # Build new structure
    new_data = {
        "active": active_jobs,
        "expired": expired_jobs,
        "last_checked": datetime.now(timezone.utc).isoformat(),
        "total_original": len(jobs)
    }

    save_jobs(new_data)
    print(f"\nValidation complete. Active: {len(active_jobs)}, Expired: {len(expired_jobs)}")
    print(f"Updated {JOB_FILE}")

    # Also print a summary of active jobs
    print("\n=== Active Job Listings ===")
    for job in active_jobs:
        work_type = infer_work_type(job.get("location", ""), job.get("source_query_type", ""))
        date_posted = job.get("date_posted", "Not available")
        print(f"- {job['title']} at {job['company']}")
        print(f"  Location: {job['location']} | Type: {work_type}")
        print(f"  Posted: {date_posted}")
        print(f"  URL: {job['url']}")
        print()

if __name__ == "__main__":
    validate_jobs()
