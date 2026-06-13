#!/usr/bin/env python3
"""
fetch_news.py — Global News Digest fetcher
Fetches all 12 RSS feeds, grabs article summaries, translates headlines
to Spanish, and embeds everything into index.html.
Run manually: python fetch_news.py
GitHub Actions runs this automatically every morning.
"""

import feedparser
import json
import re
import sys
import time
import urllib.request
import urllib.parse
from datetime import datetime, timezone

SOURCES = [
    "https://feeds.npr.org/1004/rss.xml",
    "https://feeds.bbci.co.uk/news/world/rss.xml",
    "https://feeds.feedburner.com/euronews/en/news/",
    "https://www.france24.com/en/rss",
    "https://www.theguardian.com/world/rss",
    "https://www.aljazeera.com/xml/rss/all.xml",
    "https://batimes.com.ar/feed",
    "https://en.mercopress.com/rss",
    "https://www.channelnewsasia.com/rssfeeds/8395986",
    "https://www.thehindu.com/feeder/default.rss",
    "https://www.rnz.co.nz/rss/world.xml",
    "https://allafrica.com/tools/headlines/rdf/latest/headlines.rdf",
]

MAX_ITEMS  = 5
USER_AGENT = "Mozilla/5.0 (compatible; GlobalNewsBot/2.0)"


def strip_html(text):
    text = re.sub(r'<[^>]+>', '', text)
    text = text.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>') \
               .replace('&quot;', '"').replace('&#39;', "'").replace('&nbsp;', ' ')
    return re.sub(r'\s+', ' ', text).strip()


def get_og_description(url):
    try:
        req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
        with urllib.request.urlopen(req, timeout=8) as resp:
            html = resp.read(8192).decode('utf-8', errors='ignore')
        patterns = [
            r'<meta[^>]+property=["\']og:description["\'][^>]+content=["\'](.*?)["\']',
            r'<meta[^>]+content=["\'](.*?)["\'][^>]+property=["\']og:description["\']',
            r'<meta[^>]+name=["\']description["\'][^>]+content=["\'](.*?)["\']',
            r'<meta[^>]+content=["\'](.*?)["\'][^>]+name=["\']description["\']',
        ]
        for pat in patterns:
            m = re.search(pat, html, re.IGNORECASE | re.DOTALL)
            if m:
                desc = strip_html(m.group(1))
                if len(desc) > 25:
                    return desc
    except Exception:
        pass
    return ""


def translate_to_spanish(text):
    try:
        params = urllib.parse.urlencode({'q': text, 'langpair': 'en|es'})
        url = f'https://api.mymemory.translated.net/get?{params}'
        req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
        with urllib.request.urlopen(req, timeout=6) as resp:
            data = json.loads(resp.read().decode())
        translated = data['responseData']['translatedText']
        if translated and not translated.upper().startswith('MYMEMORY WARNING'):
            return translated
    except Exception:
        pass
    return ""


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
            pub  = entry.get("published") or entry.get("updated") or ""
            rss_desc = strip_html(entry.get("summary") or entry.get("description") or "")
            desc = rss_desc if len(rss_desc) > 40 else ""
            items.append({"title": title, "link": link, "pub": pub, "desc": desc})
        return {"ok": True, "items": items}
    except Exception:
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

    print("\nFetching article summaries (og:description)...")
    for url, feed_data in feeds.items():
        for item in feed_data["items"]:
            if not item["desc"] and item["link"]:
                item["desc"] = get_og_description(item["link"])
                if item["desc"]:
                    print(f"  ✓  {item['title'][:55]}...")
                time.sleep(0.2)

    print("\nTranslating headlines to Spanish...")
    total = sum(len(v["items"]) for v in feeds.values())
    done  = 0
    for url, feed_data in feeds.items():
        for item in feed_data["items"]:
            item["title_es"] = translate_to_spanish(item["title"])
            done += 1
            print(f"  [{done}/{total}] {item['title'][:55]}...")
            time.sleep(0.3)

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
