#!/usr/bin/env python3
"""
fetch_news.py — Global News Digest fetcher
==========================================
Fetches all 12 RSS feeds server-side and embeds the data into index.html.
Run manually:   python fetch_news.py
Run via GitHub Actions: automatically on schedule

No CORS issues, no rate limits, no browser restrictions.
Works with both GitHub Pages (Option D) and local Cowork schedule (Option C).
"""

import feedparser
import json
import re
import sys
from datetime import datetime, timezone

# ── All 12 sources ───────────────────────────────────────
SOURCES = [
    # Wire Services
    "https://rsshub.app/apnews/topics/world-news",
    "https://feeds.bbci.co.uk/news/world/rss.xml",
    # Europe
    "https://feeds.feedburner.com/euronews/en/news/",
    "https://www.france24.com/en/rss",
    "https://www.theguardian.com/world/rss",
    # Middle East
    "https://www.aljazeera.com/xml/rss/all.xml",
    # Americas
    "https://www.infobae.com/feeds/rss/",
    "https://en.mercopress.com/rss",
    # Asia-Pacific
    "https://www.channelnewsasia.com/rssfeeds/8395986",
    "https://www.thehindu.com/feeder/default.rss",
    "https://www.rnz.co.nz/rss/world.xml",
    # Africa
    "https://allafrica.com/tools/headlines/rdf/latest/headlines.rdf",
]

MAX_ITEMS = 5
USER_AGENT = "Mozilla/5.0 (compatible; GlobalNewsBot/2.0; +https://github.com)"

def fetch_feed(url):
    """Fetch a single RSS feed. Returns dict with ok/items/error."""
    try:
        feed = feedparser.parse(url, agent=USER_AGENT)
        # bozo means parse warning, but entries may still be valid
        if feed.bozo and not feed.entries:
            raise Exception(f"Parse error: {feed.bozo_exception}")
        items = []
        for entry in feed.entries[:MAX_ITEMS]:
            title = (entry.get("title") or "").strip()
            if not title:
                continue
            link = entry.get("link") or ""
            pub = (entry.get("published")
                   or entry.get("updated")
                   or entry.get("dc_date")
                   or "")
            items.append({"title": title, "link": link, "pub": pub})
        return {"ok": True, "items": items}
    except Exception as e:
        return {"ok": False, "items": [], "error": str(e)}

def main():
    print(f"Fetching {len(SOURCES)} feeds…\n")
    feeds = {}
    ok_count = 0

    for url in SOURCES:
        result = fetch_feed(url)
        feeds[url] = result
        if result["ok"]:
            ok_count += 1
            print(f"  ✓  {url}  ({len(result['items'])} headlines)")
        else:
            print(f"  ✗  {url}  — {result.get('error', 'unknown error')}", file=sys.stderr)

    data = {
        "generated": datetime.now(timezone.utc).isoformat(),
        "feeds": feeds,
    }
    json_str = json.dumps(data, ensure_ascii=False, separators=(",", ":"))

    # ── Inject into index.html ────────────────────────────
    try:
        with open("index.html", "r", encoding="utf-8") as f:
            html = f.read()
    except FileNotFoundError:
        print("\nERROR: index.html not found in current directory.", file=sys.stderr)
        print("Run this script from the same folder as index.html.", file=sys.stderr)
        sys.exit(1)

    pattern = r'(<script id="news-data" type="application/json">)[^<]*(</script>)'
    
    def replacer(m):
        return m.group(1) + json_str + m.group(2)

    new_html, count = re.subn(pattern, replacer, html)

    if count == 0:
        print('\nERROR: Could not find <script id="news-data"> in index.html.', file=sys.stderr)
        sys.exit(1)

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(new_html)

    print(f"\n✓ index.html updated — {ok_count}/{len(SOURCES)} feeds OK")
    print(f"  Timestamp: {data['generated']}")

if __name__ == "__main__":
    main()
