#!/usr/bin/env python3
"""
fetch_news.py — Global News Digest fetcher
Fetches all RSS feeds, grabs article summaries, translates English headlines
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

# lang="es" sources skip MyMemory translation (headlines already in Spanish)
SOURCES = [
    {"url": "https://feeds.npr.org/1004/rss.xml",                              "lang": "en"},
    {"url": "https://feeds.bbci.co.uk/news/world/rss.xml",                     "lang": "en"},
    {"url": "https://www.emol.com/rss/mundo.xml",                              "lang": "es"},
    {"url": "https://feeds.feedburner.com/euronews/en/news/",                  "lang": "en"},
    {"url": "https://www.france24.com/en/rss",                                 "lang": "en"},
    {"url": "https://www.theguardian.com/world/rss",                           "lang": "en"},
    {"url": "https://www.aljazeera.com/xml/rss/all.xml",                       "lang": "en"},
    {"url": "https://batimes.com.ar/feed",                                     "lang": "en"},
    {"url": "https://en.mercopress.com/rss/",                                  "lang": "en"},
    {"url": "https://www.emol.com/rss/nacional.xml",                           "lang": "es"},
    {"url": "https://www.channelnewsasia.com/rssfeeds/8395986",                "lang": "en"},
    {"url": "https://www.thehindu.com/feeder/default.rss",                     "lang": "en"},
    {"url": "https://www.rnz.co.nz/rss/world.xml",                             "lang": "en"},
    {"url": "https://allafrica.com/tools/headlines/rdf/latest/headlines.rdf",  "lang": "en"},
]

MAX_ITEMS  = 5
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
FEED_HEADERS = {
    'User-Agent':      USER_AGENT,
    'Accept':          'application/rss+xml, application/xml, text/xml, */*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
}


def strip_html(text):
    """Remove HTML tags and decode common entities."""
    text = re.sub(r'<[^>]+>', '', text)
    text = text.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>') \
               .replace('&quot;', '"').replace('&#39;', "'").replace('&nbsp;', ' ')
    return re.sub(r'\s+', ' ', text).strip()


def get_og_description(url):
    """
    Fetch the article page and extract og:description or meta description.
    Only reads the first 8 KB — enough for the <head> section.
    Returns empty string on any failure.
    """
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
    """Translate text to Spanish using MyMemory free API (no key required)."""
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
    return ""  # JS falls back to English title


def fetch_feed(url):
    try:
        req = urllib.request.Request(url, headers=FEED_HEADERS)
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read()
        # Pass raw bytes so feedparser handles encoding; avoids bot-detection on URL fetch
        feed = feedparser.parse(raw)
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

    # Step 1 — fetch RSS
    for source in SOURCES:
        url = source["url"]
        result = fetch_feed(url)
        feeds[url] = result
        status = f"✓  ({len(result['items'])} headlines)" if result["ok"] else "✗  (failed)"
        print(f"  {status}  {url}")
        if result["ok"]:
            ok_count += 1

    # Step 2 — fill missing descriptions via og:description
    print("\nFetching article summaries (og:description)...")
    for source in SOURCES:
        url = source["url"]
        for item in feeds[url]["items"]:
            if not item["desc"] and item["link"]:
                item["desc"] = get_og_description(item["link"])
                if item["desc"]:
                    print(f"  ✓  {item['title'][:55]}...")
                time.sleep(0.2)

    # Step 3 — translate titles to Spanish
    # Skip MyMemory for lang="es" sources — headlines already in Spanish.
    # Passing Spanish through EN→ES would garble them.
    print("\nTranslating headlines to Spanish...")
    total = sum(len(feeds[s["url"]]["items"]) for s in SOURCES)
    done  = 0
    for source in SOURCES:
        url        = source["url"]
        is_spanish = source["lang"] == "es"
        for item in feeds[url]["items"]:
            done += 1
            if is_spanish:
                item["title_es"] = item["title"]  # already Spanish
                print(f"  [{done}/{total}] (es→skip) {item['title'][:55]}...")
            else:
                item["title_es"] = translate_to_spanish(item["title"])
                print(f"  [{done}/{total}] {item['title'][:55]}...")
                time.sleep(0.3)

    # Build final data blob
    data = {
        "generated": datetime.now(timezone.utc).isoformat(),
        "feeds": feeds,
    }
    json_str = json.dumps(data, ensure_ascii=False, separators=(",", ":"))

    # Read index.html
    try:
        with open("index.html", "r", encoding="utf-8") as f:
            html = f.read()
    except FileNotFoundError:
        print("\nERROR: index.html not found.", file=sys.stderr)
        sys.exit(1)

    # Inject JSON using string split (immune to < or > in content)
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
