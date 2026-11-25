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
# item key -> (report, regex for the line label)
ITEMS = {
    "sbo_crude_il":   ("roundup", r"(?:Crude )?Soybean Oil.*(?:Illinois|IL\b|Central)"),
    "sbo_crude_ia":   ("roundup", r"(?:Crude )?Soybean Oil.*(?:Iowa|IA\b)"),
    "tallow_bft":     ("roundup", r"(?:Bleachable|BFT|Packer Bleachable).*Tallow|Tallow.*Bleachable"),
    "tallow_edible":  ("roundup", r"Edible Tallow|Tallow.*Edible"),
    "cwg_rt":         ("roundup", r"Choice White Grease"),
    "yg_rt":          ("roundup", r"Yellow Grease"),
    "ethanol_ia":     ("roundup", r"Ethanol.*Iowa|Iowa.*Ethanol"),
    "dco_ia":         ("ethanol", r"(?:Distillers Corn Oil|Corn Oil).*"),
    "yg_mn":          ("byproduct", r"Yellow Grease.*(?:Minn|MN)"),
    "yg_ca":          ("byproduct", r"Yellow Grease.*(?:San Joaquin|California|CA)"),
    "cwg_central":    ("byproduct", r"Choice White Grease.*(?:Central|Trade)"),
}
NUM = r"(\d{1,3}(?:\.\d{1,4})?)"


def pdf_text(b):
    import pdfplumber
    with pdfplumber.open(io.BytesIO(b)) as pdf:
        return "\n".join(p.extract_text() or "" for p in pdf.pages)


def report_date(text):
    m = re.search(r"(\d{1,2})/(\d{1,2})/(20\d{2})", text) or re.search(r"([A-Z][a-z]+ \d{1,2}, 20\d{2})", text)
    if not m:
        return str(dt.date.today())
    if len(m.groups()) == 3:
        return f"{m.group(3)}-{int(m.group(1)):02d}-{int(m.group(2)):02d}"
    return dt.datetime.strptime(m.group(1).replace(",", ""), "%B %d %Y").date().isoformat()


def first_price(line):
    """Midpoint of the first 'lo-hi' range (or first number) after the label; ignores dates and basis like -100Z."""
    body = re.sub(r"\d{1,2}/\d{1,2}/\d{2,4}", " ", line)
    m = re.search(NUM + r"\s*-\s*" + NUM, body)
    if m:
        lo, hi = float(m.group(1)), float(m.group(2))
        if 0 < lo <= hi < 400:
            return round((lo + hi) / 2, 3), f"{lo}-{hi}"
    for x in re.findall(r"(?<![\w.-])" + NUM + r"(?![\w.])", body):
        v = float(x)
        if 5 < v < 400:
            return v, x
    return None, None


def main():
    state = read_json(OUT, {"rows": []}) or {"rows": []}
    texts, got = {}, 0
    for k, u in REPORTS.items():
        try:
            t = pdf_text(get(u, binary=True))
            texts[k] = t
            save_raw("ams", f"{k}.txt", t)
        except Exception as e:
            print("AMS", k, e)
    if not texts:
        raise RuntimeError("no AMS report downloaded")
    for key, (rep, pat) in ITEMS.items():
        t = texts.get(rep)
        if not t:
            continue
        for line in t.splitlines():
            if re.search(pat, line, flags=re.I):
                v, raw = first_price(line)
                if v is None:
                    continue
                row = {"date": report_date(t), "item": key, "value": v, "raw": raw, "line": line.strip()[:140], "report": rep}
                state["rows"] = [r for r in state["rows"] if not (r["date"] == row["date"] and r["item"] == key)] + [row]
                got += 1
                break
    state["updated"] = str(dt.date.today())
    write_json(OUT, state)
    if not got:
        raise RuntimeError("downloaded but no price lines matched (check data/raw/ams/*.txt)")
    return max(r["date"] for r in state["rows"])


if __name__ == "__main__":
    sys.exit(0 if run("ams_cash", main) else 1)
