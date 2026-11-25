"""Builds the public website in _site/: the page, assets and the published JSON only. Code (pipelines/, models/),
raw downloads, run logs, the model assumptions and the failure detail in status.json stay in the repo and are never
published. Primers (primers/primers.md) are rendered to data/primers.json. Also writes data/asof.json (as-of date
per input, no error text) for the page footers."""
import json, re, shutil, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "_site"
EXCLUDE_DIRS = {"raw", "status"}
EXCLUDE_FILES = {"status.json", "assumptions.json", "catchup.json"}


def primers():
    import markdown
    md = (ROOT / "primers" / "primers.md").read_text()
    parts = re.split(r"(?m)^## ", md)
    out = []
    for p in parts[1:]:
        title, _, body = p.partition("\n")
        title = re.sub(r"^\d+\.\s*", "", title.strip())
        if title.lower().startswith("sources"):
            out.append({"id": "sources", "title": "Sources", "html": markdown.markdown(body.strip(), extensions=["tables"])})
            continue
        slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:40]
        body = re.sub(r"\n---\s*$", "", body.strip())
        out.append({"id": slug, "title": title, "html": markdown.markdown(body, extensions=["tables"])})
    (ROOT / "data" / "primers.json").write_text(json.dumps(out))


def asof():
    st = {f.stem: json.loads(f.read_text()) for f in (ROOT / "data" / "status").glob("*.json")}
    (ROOT / "data" / "asof.json").write_text(json.dumps({k: v.get("asof") for k, v in st.items()}))


def main():
    primers()
    asof()
    if SITE.exists():
        shutil.rmtree(SITE)
    SITE.mkdir()
    shutil.copy(ROOT / "index.html", SITE / "index.html")
    shutil.copytree(ROOT / "assets", SITE / "assets")
    for f in (ROOT / "data").rglob("*"):
        rel = f.relative_to(ROOT / "data")
        if f.is_dir() or rel.parts[0] in EXCLUDE_DIRS or f.name in EXCLUDE_FILES or f.suffix not in (".json", ".csv"):
            continue
        if rel.parts[0] == "prices" and f.suffix == ".csv":   # chart data is in model/series.json
            continue
        dst = SITE / "data" / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(f, dst)
    (SITE / ".nojekyll").write_text("")
    n = sum(1 for _ in SITE.rglob("*") if _.is_file())
    print("site files:", n)


if __name__ == "__main__":
    sys.exit(main())
