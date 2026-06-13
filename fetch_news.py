#!/usr/bin/env python3
"""
fetch_news.py — Global News Digest fetcher
Fetches all 12 RSS feeds and embeds data into index.html.
Run manually: python fetch_news.py
GitHub Actions runs this automatically every morning.
"""

import feedparser
import json
import sys
from datetime import datetime, timezone

SOURCES = [
    "https://rsshub.app/apnews/topics/world-news",
    "https://feeds.bbci.co.uk/news/world/rss.xml",
    "https://feeds.feedburner.com/euronews/en/news/",
    "https://www.france24.com/en/rss",
    "https://www.theguardian.com/world/rss",
    "https://www.aljazeera.com/xml/rss/all.xml",
    "https://www.infobae.com/feeds/rss/",
    "https://en.mercopress.com/rss",
    "https://www.channelnewsasia.com/rssfeeds/8395986",
    "https://www.thehindu.com/feeder/default.rss",
    "https://www.rnz.co.nz/rss/world.xml",
    "https://allafrica.com/tools/headlines/rdf/latest/headlines.rdf",
]

MAX_ITEMS = 5
USER_AGENT = "Mozilla/5.0 (compatible; GlobalNewsBot/2.0)"

def fetch_feed(url):
    try:
        feed = feedparser.parse(url, agent=USER_AGENT)
        if feed.bozo and not feed.entries:
            raise Exception("Feed parse failed")
        items = []
        for entry in feed.entries[:MAX_ITEMS]:
            title = (entry.get("title") or "").strip()
            if not title:
                continue
            link = entry.get("link") or ""
            pub  = (entry.get("published") or entry.get("updated") or "")
            items.append({"title": title, "link": link, "pub": pub})
        return {"ok": True, "items": items}
    except Exception as e:
        return {"ok": False, "items": []}

def main():
    print(f"Fetching {len(SOURCES)} feeds...\n")
    feeds = {}
    ok_count = 0
    for url in SOURCES:
        result = fetch_feed(url)
        feeds[url] = result
        status = f"✓  ({len(result['items'])} headlines)" if result["ok"] else "✗  (failed)"
        print(f"  {status}  {url}")
        if result["ok"]:
            ok_count += 1

    data = {
        "generated": datetime.now(timezone.utc).isoformat(),
        "feeds": feeds,
    }
    json_str = json.dumps(data, ensure_ascii=False, separators=(",", ":"))

    try:
        with open("index.html", "r", encoding="utf-8") as f:
            html = f.read()
    except FileNotFoundError:
        print("\nERROR: index.html not found.", file=sys.stderr)
        sys.exit(1)

    START = '<script id="news-data" type="application/json">'
    END   = '</script>'
    start_idx = html.find(START)
    if start_idx == -1:
        print('\nERROR: Could not find <script id="news-data"> in index.html.', file=sys.stderr)
        sys.exit(1)
    content_start = start_idx + len(START)
    end_idx = html.find(END, content_start)
    if end_idx == -1:
        print('\nERROR: Could not find closing </script> tag.', file=sys.stderr)
        sys.exit(1)

    new_html = html[:content_start] + json_str + html[end_idx:]

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(new_html)

    print(f"\n✓ index.html updated — {ok_count}/{len(SOURCES)} feeds OK")
    print(f"  Timestamp: {data['generated']}")

if __name__ == "__main__":
    main()
