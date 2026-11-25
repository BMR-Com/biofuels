"""Policy tracker: (1) Federal Register documents on the RFS, biofuels and the 45Z credit (public JSON API);
(2) change detection on the EPA / Treasury / CARB policy pages (a page whose text changes is flagged with the date).
Output data/policy/fedreg.json and data/policy/watch.json."""
import re, sys, datetime as dt
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import DATA, get, sha, write_json, read_json, run  # noqa: E402
import requests

FR = "https://www.federalregister.gov/api/v1/documents.json"
QUERIES = {
    "RFS / RVO / SRE (EPA)": {"conditions[term]": '"renewable fuel standard" OR "renewable fuel" OR "small refinery"',
                              "conditions[agencies][]": "environmental-protection-agency"},
    "45Z clean fuel credit (Treasury/IRS)": {"conditions[term]": '"45Z" OR "clean fuel production credit"'},
    "Biofuel trade (Commerce/ITC/USTR)": {"conditions[term]": '"biodiesel" OR "renewable diesel" OR "used cooking oil" OR "tallow"'},
}
PAGES = {
    "EPA RFS announcements": "https://www.epa.gov/renewable-fuel-standard/news-notices-and-announcements-renewable-fuel-standard",
    "EPA small refinery exemptions": "https://www.epa.gov/fuels-registration-reporting-and-compliance-help/rfs-small-refinery-exemptions",
    "EPA RFS annual standards": "https://www.epa.gov/renewable-fuel-standard/renewable-fuel-annual-standards",
    "IRS 45Z clean fuel production credit": "https://www.irs.gov/credits-deductions/clean-fuel-production-credit",
    "CARB LCFS main page": "https://ww2.arb.ca.gov/our-work/programs/low-carbon-fuel-standard",
}


def fedreg():
    out = {}
    since = (dt.date.today() - dt.timedelta(days=540)).isoformat()
    for name, q in QUERIES.items():
        p = {"per_page": 25, "order": "newest", "conditions[publication_date][gte]": since,
             "fields[]": ["title", "type", "publication_date", "html_url", "agencies", "abstract", "document_number"]}
        p.update(q)
        r = requests.get(FR, params=p, timeout=60, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        docs = r.json().get("results", [])
        out[name] = [{"date": d["publication_date"], "type": d.get("type"), "title": d["title"], "url": d["html_url"],
                      "agency": ", ".join(a.get("name", "") for a in d.get("agencies", [])[:2]),
                      "abstract": (d.get("abstract") or "")[:400]} for d in docs]
    write_json(DATA / "policy" / "fedreg.json", {"updated": str(dt.date.today()), "groups": out})
    return max((d["date"] for v in out.values() for d in v), default=str(dt.date.today()))


def watch():
    st = read_json(DATA / "policy" / "watch.json", {}) or {}
    ok = 0
    for name, url in PAGES.items():
        try:
            html = get(url, tries=2)
        except Exception as e:
            st.setdefault(name, {"url": url})["error"] = str(e)[:100]
            continue
        body = re.sub(r"(?s)<(script|style|header|footer|nav).*?</\1>", " ", html)
        text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", body))
        text = re.sub(r"Last updated on [A-Za-z]+ \d+, \d{4}", "", text)
        h = sha(text)
        rec = st.setdefault(name, {"url": url})
        rec.pop("error", None)
        if rec.get("hash") != h:
            if rec.get("hash"):
                rec["changed"] = str(dt.date.today())
            rec["hash"] = h
        rec["checked"] = str(dt.date.today())
        ok += 1
    write_json(DATA / "policy" / "watch.json", st)
    if not ok:
        raise RuntimeError("no policy page reachable")
    return str(dt.date.today())


if __name__ == "__main__":
    a = run("policy_fedreg", fedreg)
    b = run("policy_watch", watch)
    sys.exit(0 if a or b else 1)
