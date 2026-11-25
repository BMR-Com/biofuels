"""Market-moving biofuel and vegetable-oil headlines from Reuters, Bloomberg and WSJ (Google News RSS, public).
Only headlines that name a price/production driver are kept (RINs, RVO, SRE, 45Z, LCFS, biodiesel, renewable
diesel, SAF, soybean oil/crush, palm oil, canola, UCO, tallow, feedstock tariffs). Output data/news/news.json."""
import re, sys, datetime as dt, html as H
from pathlib import Path
from email.utils import parsedate_to_datetime

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import DATA, get, write_json, read_json, run  # noqa: E402

FEED = "https://news.google.com/rss/search?q={}&hl=en-US&gl=US&ceid=US:en"
SITES = "(site:reuters.com OR site:bloomberg.com OR site:wsj.com)"
TOPICS = ['"renewable fuel standard" OR RINs OR "biomass-based diesel"', '"soybean oil" OR soyoil OR "soybean crush"',
          '"renewable diesel" OR biodiesel OR "sustainable aviation fuel"', '"palm oil" OR "used cooking oil" OR tallow OR "canola oil"',
          '45Z OR "small refinery exemptions" OR "low carbon fuel standard"']
KEEP = re.compile(r"\b(RINs?|RFS|renewable fuel|biofuel|biodiesel|renewable diesel|SAF|aviation fuel|45Z|small refiner|SRE|"
                  r"low carbon fuel|LCFS|soy(?:bean)? ?oil|soyoil|crush|palm oil|CPO|canola|rapeseed|cooking oil|UCO|tallow|"
                  r"B40|B50|mandate|blending|feedstock)\b", re.I)
DROP = re.compile(r"\b(recipe|stock to buy|dividend|shares? (?:rise|fall|jump)|earnings call transcript)\b", re.I)


def main():
    old = read_json(DATA / "news" / "news.json", {"items": []}) or {"items": []}
    seen = {i["title"]: i for i in old["items"]}
    for t in TOPICS:
        q = (t + " " + SITES).replace(" ", "+").replace('"', "%22")
        try:
            xml = get(FEED.format(q), tries=2)
        except Exception as e:
            print("news", e)
            continue
        for it in re.findall(r"(?s)<item>(.*?)</item>", xml):
            title = H.unescape(re.sub(r"<.*?>", "", re.search(r"<title>(.*?)</title>", it, re.S).group(1))).strip()
            link = re.search(r"<link>(.*?)</link>", it, re.S).group(1).strip()
            src = re.search(r"<source[^>]*>(.*?)</source>", it, re.S)
            pub = re.search(r"<pubDate>(.*?)</pubDate>", it, re.S)
            date = parsedate_to_datetime(pub.group(1)).date().isoformat() if pub else str(dt.date.today())
            if not KEEP.search(title) or DROP.search(title):
                continue
            title = re.sub(r"\s+-\s+(Reuters|Bloomberg(?:\.com)?|WSJ|The Wall Street Journal)$", "", title)
            seen.setdefault(title, {"title": title, "url": link, "source": src.group(1) if src else "", "date": date})
    cut = (dt.date.today() - dt.timedelta(days=45)).isoformat()
    items = sorted([i for i in seen.values() if i["date"] >= cut], key=lambda i: i["date"], reverse=True)[:80]
    write_json(DATA / "news" / "news.json", {"updated": str(dt.date.today()), "items": items})
    if not items:
        raise RuntimeError("no headlines")
    return items[0]["date"]


if __name__ == "__main__":
    sys.exit(0 if run("news", main) else 1)
