"""EPA EMTS public RFS data (monthly, third Thursday): RIN generation by D-code and month, generation by fuel type,
domestic/import split, available (unretired) RINs. Each EPA file is a full-history snapshot, so only the newest is read.

Outputs data/rfs/emts.json:
  monthly: {D3|D4|D5|D6|D7: [[YYYY-MM, RINs, gallons], ...]}
  by_fuel: {year: [{d, fuel, ev, rins, gal}]}
  origin:  {year: {D4: {domestic, importer, foreign, total}}}
  available: {year: {D4: {separated_unlocked, ...}}}
"""
import io, re, sys
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import DATA, get, links, save_raw, write_json, run  # noqa: E402

BASE = "https://www.epa.gov/fuels-registration-reporting-and-compliance-help/"
PAGES = {
    "rindata": BASE + "spreadsheet-rin-generation-and-renewable-fuel",
    "fuelproduction": BASE + "spreadsheet-rin-generation-and-renewable-fuel-0",
    "generationbreakout": BASE + "spreadsheet-rin-generation-data-renewable-fuel",
    "availablerins": BASE + "spreadsheet-available-rins-date-renewable-fuel",
}
MON = {m: i + 1 for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"])}


def newest_csv(prefix):
    html = get(PAGES[prefix])
    cands = links(html, PAGES[prefix], rf"/{prefix}[_-]?[a-z]+\d{{4}}(_\d+)?\.csv$")
    if not cands:
        cands = links(html, PAGES[prefix], r"\.csv$")
    if not cands:
        raise RuntimeError(f"no csv link on {prefix} page")

    def key(u):
        m = re.search(r"([a-z]+)(\d{4})(?:_\d+)?\.csv$", u.lower())
        if not m:
            return (0, 0)
        return (int(m.group(2)), MON.get(m.group(1)[:3], 0))
    u = max(cands, key=key)
    txt = get(u)
    save_raw("epa", u.rsplit("/", 1)[-1], txt)
    return u, pd.read_csv(io.StringIO(txt), thousands=",")


def num(s):
    return pd.to_numeric(s.astype(str).str.replace(",", "").str.strip(), errors="coerce")


def main():
    out = {}
    u, d = newest_csv("rindata")
    d.columns = [c.strip().upper().replace(" ", "_") for c in d.columns]
    d["RIN_QUANTITY"], d["BATCH_VOLUME"] = num(d["RIN_QUANTITY"]), num(d["BATCH_VOLUME"])
    d = d.groupby(["FUEL_CODE", "RIN_YEAR", "PRODUCTION_MONTH"], as_index=False)[["RIN_QUANTITY", "BATCH_VOLUME"]].sum()
    monthly = {}
    for code, g in d.groupby("FUEL_CODE"):
        g = g.sort_values(["RIN_YEAR", "PRODUCTION_MONTH"])
        monthly[f"D{int(code)}"] = [[f"{int(r.RIN_YEAR)}-{int(r.PRODUCTION_MONTH):02d}", int(r.RIN_QUANTITY), int(r.BATCH_VOLUME)]
                                    for r in g.itertuples()]
    out["monthly"] = monthly
    last = max(v[-1][0] for v in monthly.values())
    out["source_file"] = {"rindata": u}

    try:
        u2, f = newest_csv("fuelproduction")
        f.columns = [c.strip() for c in f.columns]
        f["RIN Quantity"], f["Batch Volume"] = num(f["RIN Quantity"]), num(f["Batch Volume"])
        by = {}
        for r in f.itertuples(index=False):
            yr, fuel, code, cat = int(r[0]), r[1], int(r[2]), str(r[3])
            ev = re.search(r"EV\s*([\d.]+)", cat)
            by.setdefault(str(yr), []).append({"d": f"D{code}", "fuel": cat, "ev": float(ev.group(1)) if ev else None,
                                              "rins": int(r[5]) if pd.notna(r[5]) else 0, "gal": int(r[6]) if pd.notna(r[6]) else 0})
        out["by_fuel"] = {y: by[y] for y in sorted(by)[-6:]}
        out["source_file"]["fuelproduction"] = u2
    except Exception as e:
        print("fuelproduction failed", e)

    try:
        u3, g = newest_csv("generationbreakout")
        g.columns = [c.strip() for c in g.columns]
        o = {}
        for r in g.itertuples(index=False):
            o.setdefault(str(int(r[0])), {})[f"D{int(r[1])}"] = {"domestic": float(num(pd.Series([r[2]]))[0]),
                                                               "importer": float(num(pd.Series([r[3]]))[0]),
                                                               "foreign": float(num(pd.Series([r[4]]))[0]),
                                                               "total": float(num(pd.Series([r[5]]))[0])}
        out["origin"] = {y: o[y] for y in sorted(o)[-8:]}
        out["source_file"]["generationbreakout"] = u3
    except Exception as e:
        print("generationbreakout failed", e)

    try:
        u4, a = newest_csv("availablerins")
        a.columns = [c.strip() for c in a.columns]
        av = {}
        for r in a.itertuples(index=False):
            yr = str(int(r[0])); dcode = re.search(r"\((D\d)\)", str(r[1]))
            if not dcode:
                continue
            k = av.setdefault(yr, {}).setdefault(dcode.group(1), {})
            tag = str(r[2]).strip().lower()
            for nm, val in zip(["generated", "retired", "locked", "unlocked"], r[3:7]):
                k[f"{tag}_{nm}"] = float(num(pd.Series([val]))[0])
        out["available"] = {y: av[y] for y in sorted(av)[-4:]}
        out["source_file"]["availablerins"] = u4
    except Exception as e:
        print("availablerins failed", e)

    out["asof"] = last
    write_json(DATA / "rfs" / "emts.json", out)
    return last


if __name__ == "__main__":
    sys.exit(0 if run("epa_emts", main) else 1)
