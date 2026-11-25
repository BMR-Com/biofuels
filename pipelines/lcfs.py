"""Clean-fuel credit prices: California LCFS (CARB monthly credit transfer PDF + weekly snapshot page),
Oregon Clean Fuels Program (monthly XLSX), Washington Clean Fuel Standard (monthly XLSX).
Output data/credits/lcfs.json: {ca_monthly: [[YYYY-MM, $/t, credits]], ca_weekly: {...}, or_monthly, wa_monthly}.
Each source is merged into the stored history, so a blocked site only means no new point this run."""
import io, re, sys, datetime as dt
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import DATA, get, links, save_raw, write_json, read_json, run  # noqa: E402

OUT = DATA / "credits" / "lcfs.json"
CA_PAGE = "https://ww2.arb.ca.gov/resources/documents/monthly-lcfs-credit-transfer-activity-reports"
CA_PAGE2 = "https://ww2.arb.ca.gov/fuels/lcfs/credit/lrtcreditreports.htm"
CA_WEEKLY = "https://ww2.arb.ca.gov/resources/documents/weekly-lcfs-credit-transfer-activity-reports"
OR_XLSX = "https://www.oregon.gov/deq/ghgp/Documents/CFPCreditTransferActivityReport.xlsx"
WA_URL = "https://www.ezview.wa.gov/Portals/_1962/Documents/clean-fuel-data/CFSCreditTransferActivityReport_{}{}.xlsx"
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
MABBR = {m[:3].lower(): i + 1 for i, m in enumerate(MONTHS)}


def merge(old, new):
    d = {r[0]: r for r in (old or [])}
    for r in new:
        d[r[0]] = r
    return [d[k] for k in sorted(d)]


def parse_ca_pdf(b):
    import pdfplumber
    rows = []
    with pdfplumber.open(io.BytesIO(b)) as pdf:
        text = "\n".join(p.extract_text() or "" for p in pdf.pages)
    for m in re.finditer(r"\b([A-Z][a-z]{2})-(\d{2})\s+([\d,]+)\s+([\d,]+)\s+\$\s?([\d,.]+)", text):
        mon, yy, _n, vol, px = m.groups()
        if mon.lower() in MABBR:
            rows.append([f"20{yy}-{MABBR[mon.lower()]:02d}", float(px.replace(",", "")), int(vol.replace(",", ""))])
    return rows


def ca_monthly(state):
    pdfs = []
    for page in (CA_PAGE2, CA_PAGE):
        try:
            html = get(page, tries=2)
            pdfs += links(html, page, r"Credit%20Transfer%20Activity\.pdf$|Credit Transfer Activity\.pdf$")
        except Exception as e:
            print("CARB page", e)
    if not pdfs:   # fall back to CARB's posting pattern for the last few months
        t = dt.date.today()
        for k in range(1, 4):
            y, m = (t.year, t.month - k) if t.month - k > 0 else (t.year - 1, t.month - k + 12)
            py, pm = (y, m + 1) if m < 12 else (y + 1, 1)
            pdfs.append(f"https://ww2.arb.ca.gov/sites/default/files/{py}-{pm:02d}/{MONTHS[m - 1]}%20{y}%20-%20Monthly%20LCFS%20Credit%20Transfer%20Activity.pdf")
    rows, used = [], []
    for u in pdfs[:4]:
        try:
            b = get(u, binary=True, tries=2)
            r = parse_ca_pdf(b)
            if r:
                rows += r; used.append(u)
                save_raw("carb", u.rsplit("/", 1)[-1].replace("%20", "_"), b)
                break
        except Exception as e:
            print("CARB pdf", u[-60:], e)
    if not rows:
        raise RuntimeError("no CARB monthly rows")
    state["ca_monthly"] = merge(state.get("ca_monthly"), rows)
    return state["ca_monthly"][-1][0]


def ca_weekly(state):
    html = get(CA_WEEKLY, tries=2)
    tabs = pd.read_html(io.StringIO(html))
    for t in tabs:
        flat = t.astype(str).apply(lambda r: " | ".join(r), axis=1).str.cat(sep="\n")
        m = re.search(r"Average Price[^|]*\|\s*\$?\s*([\d,.]+)", flat)
        if m:
            wk = re.search(r"(?:week|through|to)\s+(?:of\s+)?([A-Z][a-z]+ \d{1,2},? \d{4})", html)
            state["ca_weekly"] = {"avg_price": float(m.group(1).replace(",", "")), "week": wk.group(1) if wk else None,
                                  "checked": str(dt.date.today())}
            return state["ca_weekly"]["week"] or str(dt.date.today())
    raise RuntimeError("weekly table not found")


def xlsx_month_price(b):
    """Find a table with a month column and an average price column; return [[YYYY-MM, price, volume]]."""
    xl = pd.ExcelFile(io.BytesIO(b))
    best = []
    for sh in xl.sheet_names:
        raw = xl.parse(sh, header=None)
        for i in range(min(40, len(raw))):
            hdr = [str(x).lower() for x in raw.iloc[i]]
            pc = next((j for j, h in enumerate(hdr) if "price" in h and ("average" in h or "avg" in h or "weighted" in h)), None)
            if pc is None:
                continue
            vc = next((j for j, h in enumerate(hdr) if ("credit" in h or "volume" in h) and j != pc and "price" not in h), None)
            rows = []
            for _, r in raw.iloc[i + 1:].iterrows():
                d = pd.to_datetime(str(r.iloc[0]), errors="coerce")
                if pd.isna(d):
                    mm = re.match(r"([A-Za-z]{3})[a-z]*[-\s']+(\d{2,4})", str(r.iloc[0]))
                    if not mm or mm.group(1).lower() not in MABBR:
                        continue
                    y = int(mm.group(2)); y = y + 2000 if y < 100 else y
                    d = pd.Timestamp(y, MABBR[mm.group(1).lower()], 1)
                p = pd.to_numeric(str(r.iloc[pc]).replace("$", "").replace(",", ""), errors="coerce")
                v = pd.to_numeric(str(r.iloc[vc]).replace(",", ""), errors="coerce") if vc is not None else None
                if pd.notna(p) and 0 < p < 1000:
                    rows.append([d.strftime("%Y-%m"), float(p), float(v) if v is not None and pd.notna(v) else None])
            if len(rows) > len(best):
                best = rows
    return best


def oregon(state):
    b = get(OR_XLSX, binary=True)
    save_raw("oregon", "CFPCreditTransferActivityReport.xlsx", b)
    rows = xlsx_month_price(b)
    if not rows:
        raise RuntimeError("no Oregon rows parsed")
    state["or_monthly"] = merge(state.get("or_monthly"), rows)
    return state["or_monthly"][-1][0]


def washington(state):
    t = dt.date.today()
    for k in range(0, 4):
        y, m = (t.year, t.month - k) if t.month - k > 0 else (t.year - 1, t.month - k + 12)
        try:
            b = get(WA_URL.format(MONTHS[m - 1], y), binary=True, tries=1)
        except Exception:
            continue
        save_raw("washington", f"CFS_{y}{m:02d}.xlsx", b)
        rows = xlsx_month_price(b)
        if rows:
            state["wa_monthly"] = merge(state.get("wa_monthly"), rows)
            return state["wa_monthly"][-1][0]
    raise RuntimeError("no Washington file found")


if __name__ == "__main__":
    state = read_json(OUT, {}) or {}
    res = [run(f"lcfs_{n}", lambda f=f: f(state)) for n, f in
           (("ca_monthly", ca_monthly), ("ca_weekly", ca_weekly), ("oregon", oregon), ("washington", washington))]
    state["updated"] = str(dt.date.today())
    write_json(OUT, state)
    sys.exit(0 if res[0] else 1)
