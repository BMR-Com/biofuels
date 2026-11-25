"""Shared helpers for every fetcher: HTTP with a browser User-Agent and retries, raw-file archive,
and the run log (logs/runs.jsonl, kept in the repo, never published) plus data/status.json (as-of dates, published)."""
import json, re, time, hashlib, datetime as dt
from pathlib import Path
import requests

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
RAW = DATA / "raw"
LOGS = ROOT / "logs"
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
      "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8", "Accept-Language": "en-US,en;q=0.9"}


def get(url, tries=4, timeout=60, binary=False, **kw):
    last = None
    for i in range(tries):
        try:
            r = requests.get(url, headers=UA, timeout=timeout, **kw)
            if r.status_code == 200 and r.content:
                return r.content if binary else r.text
            last = f"HTTP {r.status_code}"
        except Exception as e:  # network errors, timeouts
            last = str(e)[:120]
        time.sleep(3 * (i + 1))
    raise RuntimeError(f"{url} -> {last}")


def links(html, base, pattern):
    """All hrefs in html matching regex pattern, made absolute, in page order, de-duplicated."""
    from urllib.parse import urljoin
    out = []
    for h in re.findall(r'href=["\']([^"\']+)["\']', html, flags=re.I):
        u = urljoin(base, h.replace("&amp;", "&"))
        if re.search(pattern, u, flags=re.I) and u not in out:
            out.append(u)
    return out


def save_raw(source, name, content):
    p = RAW / source / name
    p.parent.mkdir(parents=True, exist_ok=True)
    (p.write_bytes if isinstance(content, bytes) else p.write_text)(content)
    return p


def sha(b):
    return hashlib.sha256(b if isinstance(b, bytes) else b.encode()).hexdigest()[:16]


def write_json(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=1, default=str, allow_nan=False))


def read_json(path, default=None):
    try:
        return json.loads(Path(path).read_text())
    except Exception:
        return default


def now():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def log_run(source, ok, asof=None, detail=""):
    """One file per source so parallel workflows never overwrite each other's state:
    logs/<source>.jsonl (history, repo only) and data/status/<source>.json (newest state; not published)."""
    LOGS.mkdir(exist_ok=True)
    rec = {"t": now(), "source": source, "ok": bool(ok), "asof": asof, "detail": str(detail)[:300]}
    with open(LOGS / f"{source}.jsonl", "a") as f:
        f.write(json.dumps(rec) + "\n")
    sp = DATA / "status" / f"{source}.json"
    prev = read_json(sp, {}) or {}
    write_json(sp, {"checked": rec["t"], "ok": rec["ok"],
                    "asof": asof if asof else prev.get("asof"),
                    "last_ok": rec["t"] if ok else prev.get("last_ok"),
                    "detail": "" if ok else rec["detail"][:160]})


def status():
    """All sources' newest state, {source: {...}}."""
    return {f.stem: read_json(f, {}) for f in sorted((DATA / "status").glob("*.json"))}

def run(source, fn):
    """Call fn() -> asof string; log success/failure; never raise (so one source can't stop the others)."""
    try:
        asof = fn()
        log_run(source, True, asof)
        return True
    except Exception as e:
        import traceback; traceback.print_exc()
        log_run(source, False, None, f"{type(e).__name__}: {e}")
        return False
