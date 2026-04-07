#!/usr/bin/env python3
"""
Tinley Park News Test - One-off cron job
Fetches recent local news for Tinley Park, IL via Google News RSS
and outputs a concise summary with links for WhatsApp.
"""

import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime

def fetch_news():
    query = "Tinley Park IL local news"
    url = f"https://news.google.com/rss/search?q={urllib.parse.quote(query)}&hl=en-US&gl=US&ceid=US:en"

    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/rss+xml, application/xml, text/xml',
    }
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status != 200:
                return f"ERROR: HTTP {resp.status} from news source."
            data = resp.read()
    except Exception as e:
        return f"ERROR: Failed to fetch news - {e}"

    # Parse RSS XML
    try:
        root = ET.fromstring(data)
        # Items can be under <item> or in Atom <entry>
        items = root.findall('.//item')
        if not items:
            # Try Atom namespace
            ns = {'atom': 'http://www.w3.org/2005/Atom'}
            items = root.findall('.//atom:entry', ns) or root.findall('.//entry')
    except ET.ParseError as e:
        return f"ERROR: Failed to parse news feed - {e}"

    if not items:
        return "No recent news found for Tinley Park, IL."

    stories = []
    for item in items[:7]:
        # Title
        title_elem = item.find('title')
        title = title_elem.text.strip() if title_elem is not None and title_elem.text else "No title"
        # Link: RSS <link href=""> or text; Atom <link href="">
        link = ""
        link_elem = item.find('link')
        if link_elem is not None:
            link = link_elem.get('href') or link_elem.text or ""
        if not link:
            # Try <guid> or <id>
            guid = item.find('guid') or item.find('id')
            if guid is not None and guid.text:
                link = guid.text
        stories.append((title, link))

    # Format output
    now = datetime.now().strftime("%Y-%m-%d %I:%M %p CT")
    lines = [f"*Tinley Park News Test* — {now}\n"]
    for idx, (title, url) in enumerate(stories, 1):
        lines.append(f"{idx}. {title}")
        if url:
            lines.append(f"   {url}")
        lines.append("")  # blank line
    output = "\n".join(lines).strip()
    if len(output) > 2000:
        output = output[:1997] + "..."
    return output

if __name__ == "__main__":
    result = fetch_news()
    print(result)
    sys.exit(0)
