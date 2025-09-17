# pip install feedparser html2text rapidfuzz
import re, time, json, urllib.request
from datetime import datetime, timezone
import feedparser
from html2text import html2text
from rapidfuzz import fuzz

FEEDS = [
  # FCA news
  {"name": "FCA", "type": "rss", "url": "https://www.fca.org.uk/news/rss.xml"},
  # Finanstilsynet news
  {"name": "Finanstilsynet NO", "type": "rss", "url": "https://www.finanstilsynet.no/en/rss/"},
  # BaFin generic RSS hub feeds exist, choose the main all items feed in prod
  {"name": "BaFin", "type": "rss", "url": "https://www.bafin.de/EN/Service/TopNavigation/RSS/rss_node.html"},
]

HTML_SOURCES = [
  # DNB NL enforcement English
  {"name": "DNB NL", "url": "https://www.dnb.nl/en/general-news/enforcement-measures-2025/"},
  # FI SE sanctions landing in Swedish
  {"name": "FI SE", "url": "https://www.fi.se/sv/publicerat/sanktioner/finansiella-foretag/"},
]

KEYWORDS = [
  # English
  r"\baml\b", r"money laundering", r"financial crime", r"kyc", r"customer due diligence", r"transaction monitoring",
  # Norwegian
  r"hvitvask", r"overtredelsesgebyr", r"tilsynsrapport",
  # Swedish
  r"penningtvatt|penningtvätt", r"sanktionsavgift", r"sanktioner",
  # French
  r"\blcb\s*ft\b|\bblanchiment\b",
  # German
  r"geldw[äa]sche|\bbuss?geld|\bbußgeld",
]

def fetch(url):
  with urllib.request.urlopen(url, timeout=20) as r:
    return r.read().decode("utf-8", "ignore")

def score_text(txt):
  txt_l = txt.lower()
  for kw in KEYWORDS:
    if re.search(kw, txt_l):
      return True
  return False

def parse_rss(feed):
  out = []
  d = feedparser.parse(feed["url"])
  for e in d.entries:
    title = e.get("title", "")
    summary = re.sub(r"\s+", " ", e.get("summary", ""))
    text = f"{title} {summary}"
    if score_text(text):
      out.append({
        "regulator": feed["name"],
        "title": title.strip(),
        "link": e.get("link", ""),
        "published": e.get("published", e.get("updated", "")),
        "summary": summary[:400],
      })
  return out

def parse_html(src):
  out = []
  html = fetch(src["url"])
  text = html2text(html)
  # naive split by lines and pick lines that look like headlines with dates or amounts
  lines = [l.strip() for l in text.splitlines() if l.strip()]
  for i, line in enumerate(lines):
    if score_text(line):
      snippet = " ".join(lines[max(0, i-2): i+3])[:400]
      out.append({
        "regulator": src["name"],
        "title": line[:200],
        "link": src["url"],
        "published": None,
        "summary": snippet
      })
  return out

def dedupe(items):
  out, seen = [], []
  for it in items:
    key = f'{it["regulator"]}|{it["title"]}'
    keep = True
    for prev in seen:
      if fuzz.token_set_ratio(prev, key) > 90:
        keep = False
        break
    if keep:
      seen.append(key)
      out.append(it)
  return out

def run():
  items = []
  for f in FEEDS:
    try:
      items.extend(parse_rss(f))
    except Exception:
      pass
  for s in HTML_SOURCES:
    try:
      items.extend(parse_html(s))
    except Exception:
      pass
  items = dedupe(items)
  now = datetime.now(timezone.utc).isoformat()
  payload = {
    "generated_at": now,
    "count": len(items),
    "items": items
  }
  print(json.dumps(payload, ensure_ascii=False, indent=2))

if __name__ == "__main__":
  run()