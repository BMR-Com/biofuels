"""USDA AMS Market News weekly PDFs (no key): Ag Energy Round-Up (crude soybean oil, tallow, choice white grease,
yellow grease, biodiesel/ethanol), National Ethanol Report 3616 (distillers corn oil), Animal By-Product 3510
(yellow grease, choice white grease), Processor Feedstuff 3511 (crude soybean oil cash basis).

Each run appends one dated row per item to data/ams/cash.json (history builds over time) and keeps the raw text
of every PDF in data/raw/ams/ so parsing can be checked. Prices are stored in cents/lb ($/cwt is divided by 1)."""
import io, re, sys, datetime as dt
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import DATA, get, save_raw, write_json, read_json, run  # noqa: E402

OUT = DATA / "ams" / "cash.json"
REPORTS = {"roundup": "https://www.ams.usda.gov/mnreports/lswagenergy.pdf",
           "ethanol": "https://www.ams.usda.gov/mnreports/ams_3616.pdf",
           "byproduct": "https://www.ams.usda.gov/mnreports/ams_3510.pdf",
           "processor": "https://www.ams.usda.gov/mnreports/ams_3511.pdf"}
# item key -> (report, section title regex, region regex). Rows look like
#   "<Region> <Ask|Trade|Bid> [basis] [basis change] <price lo-hi | price> <change> <average> [year ago] <freight>"
ITEMS = {
    "sbo_crude_il": ("processor", r"^Soybean Oil$", r"^Illinois\b"),
    "sbo_crude_ia": ("processor", r"^Soybean Oil$", r"^Iowa\b"),
    "dco_ia":       ("ethanol", r"^Distillers Corn Oil", r"^Iowa"),
    "dco_il":       ("ethanol", r"^Distillers Corn Oil", r"^Illinois\b"),
    "yg_mn":        ("byproduct", r"^Yellow Grease$", r"^Minnesota\b"),
    "yg_ca":        ("byproduct", r"^Yellow Grease$", r"^CA-South\b"),
    "cwg_mn":       ("byproduct", r"^Choice White Grease$", r"^Minnesota\b"),
    "tallow_bft":   ("byproduct", r"^(?:Packer )?Bleachable(?: Fancy)? Tallow|^Tallow.*Bleachable", r"^(?:Central|Chicago|Minnesota|Texas)"),
    "tallow_edible": ("byproduct", r"^Edible Tallow", r"^(?:Central|Chicago|Minnesota)"),
}
# Ag Energy Round-Up (2026 | 2025 | 5-yr columns; first value is this week, "unq" = unquoted): label line, then region line
ROUNDUP = {"tallow_bft": (r"Bleachable Tallow|ble Tallow \(\$/cwt\)", r"^Chicago\b"),
           "tallow_edible": (r"^Edible Tallow", r"^Chicago\b"),
           "cwg_rt": (r"^Choice White Grease \(", r"^(?:Central U\.S\.|Minneapolis)\b"),
           "yg_rt": (r"^Yellow Grease \(", r"^(?:Central U\.S\.|Minneapolis)\b")}
SALE = re.compile(r"\b(Ask|Trade|Bid|Offer)\b")
NUM = r"(\d{1,3}(?:\.\d{1,4})?)"


def pdf_text(b):
    import pdfplumber
    with pdfplumber.open(io.BytesIO(b)) as pdf:
        return "\n".join(p.extract_text() or "" for p in pdf.pages)


def report_date(text):
    m = re.search(r"Report for \d{1,2}/\d{1,2}/20\d{2}\s*-\s*(\d{1,2})/(\d{1,2})/(20\d{2})", text) or re.search(r"(\d{1,2})/(\d{1,2})/(20\d{2})", text)
    if m:
        return f"{m.group(3)}-{int(m.group(1)):02d}-{int(m.group(2)):02d}"
    m = re.search(r"([A-Z][a-z]+)\.? (\d{1,2}), (20\d{2})", text)
    if m:
        for f in ("%B %d %Y", "%b %d %Y"):
            try:
                return dt.datetime.strptime(f"{m.group(1)} {m.group(2)} {m.group(3)}", f).date().isoformat()
            except ValueError:
                pass
    return str(dt.date.today())


def row_price(line):
    """Price from a region row: the first lo-hi range without a futures-month suffix (basis like 100.00Z is skipped);
    else the first plain number after the sale type, skipping a basis change such as 'UNCH-DN 50.00'."""
    m = SALE.search(line)
    body = line[m.end():] if m else line
    body = re.sub(r"-?\d[\d,]*\.\d+[A-Z](?:\s+to\s+-?\d[\d,]*\.\d+[A-Z])?", " ", body)   # basis
    r = re.search(r"(?<![\d.])(\d[\d,]*\.\d+)\s*-\s*(\d[\d,]*\.\d+)(?![\d.A-Z])", body)
    if r:
        lo, hi = (float(x.replace(",", "")) for x in r.groups())
        return round((lo + hi) / 2, 3), f"{lo}-{hi}"
    body = re.sub(r"^\s*(?:UNCH|UP|DN)(?:-(?:UNCH|UP|DN))?\s+(?:\d+\.\d+(?:-(?:UP|DN)\s+\d+\.\d+)?)?", " ", body)
    n = re.search(r"(?<![\w.])(\d[\d,]*\.\d+)(?![\w.])", body)
    return (float(n.group(1).replace(",", "")), n.group(1)) if n else (None, None)


def sections(text):
    """Yield (section title, region row) for every priced row."""
    cur = None
    for line in (l.strip() for l in text.splitlines()):
        if not line:
            continue
        if SALE.search(line) and cur:
            yield cur, line
        elif re.match(r"^(Region|State/Province|Ethanol Plant|Commodity)\b", line):
            continue
        else:
            cur = line


def roundup_rows(text):
    out, lines = {}, [l.strip() for l in text.splitlines()]
    for key, (lab, reg) in ROUNDUP.items():
        for i, l in enumerate(lines):
            if re.search(lab, l):
                for l2 in lines[i + 1:i + 12]:
                    if re.match(reg, l2):
                        tok = re.sub(reg, "", l2).split()
                        if tok and tok[0].lower() != "unq":
                            r = re.match(r"(\d+\.\d+)-?$", tok[0])
                            hi = tok[1] if len(tok) > 1 and re.match(r"\d+\.\d+$", tok[1]) and tok[0].endswith("-") else None
                            if r:
                                v = (float(r.group(1)) + float(hi)) / 2 if hi else float(r.group(1))
                                out[key] = (round(v, 3), l2[:140])
                        break
                break
    return out


def main():
    state = read_json(OUT, {"rows": []}) or {"rows": []}
    texts = {}
    got = 0
    for k, u in REPORTS.items():
        try:
            t = pdf_text(get(u, binary=True))
            texts[k] = t
            save_raw("ams", f"{k}.txt", t)
        except Exception as e:
            print("AMS", k, e)
    if not texts:
        raise RuntimeError("no AMS report downloaded")
    def add(key, v, raw, line, rep):
        nonlocal got
        row = {"date": report_date(texts[rep]), "item": key, "value": v, "raw": raw, "line": line[:140], "report": rep}
        state["rows"] = [r for r in state["rows"] if not (r["date"] == row["date"] and r["item"] == key)] + [row]
        got += 1
    for key, (rep, sec, reg) in ITEMS.items():
        if rep not in texts:
            continue
        for title, line in sections(texts[rep]):
            if re.search(sec, title, flags=re.I) and re.search(reg, line):
                v, raw = row_price(line)
                if v is not None and 5 < v < 300:
                    add(key, v, raw, line, rep)
                    break
    if "roundup" in texts:
        for key, (v, line) in roundup_rows(texts["roundup"]).items():
            if not any(r["item"] == key and r["date"] == report_date(texts["roundup"]) for r in state["rows"]):
                add(key, v, str(v), line, "roundup")
    state["updated"] = str(dt.date.today())
    write_json(OUT, state)
    if not got:
        raise RuntimeError("downloaded but no price lines matched (check data/raw/ams/*.txt)")
    return max(r["date"] for r in state["rows"])


if __name__ == "__main__":
    sys.exit(0 if run("ams_cash", main) else 1)
