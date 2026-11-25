"""USDA WASDE (monthly, 12:00 ET): US soybean oil supply & use, incl. the Biofuel line, from the text file.
Output data/usda/wasde_soyoil.json: {reports: {YYYY-MM: {columns: [...], rows: {label: [values]}}}}; history
builds release by release (the desk keeps every month so revisions can be shown)."""
import re, sys, datetime as dt
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import DATA, get, save_raw, write_json, read_json, run  # noqa: E402

OUT = DATA / "usda" / "wasde_soyoil.json"
URL = "https://www.usda.gov/oce/commodity/wasde/wasde{:02d}{:02d}.txt"
ROWS = ["Beginning Stocks", "Production", "Imports", "Supply, Total", "Domestic Disappearance", "Biofuel",
        "Food, Feed & other Industrial", "Exports", "Use, Total", "Ending stocks", "Avg. Price"]


def parse(txt):
    i = txt.find("SOYBEAN OIL")
    while i >= 0 and "Million Pounds" not in txt[i:i + 400] and "Beginning Stocks" not in txt[i:i + 800]:
        i = txt.find("SOYBEAN OIL", i + 10)
    if i < 0:
        raise RuntimeError("soybean oil block not found")
    block = txt[i:txt.find("SOYBEAN MEAL", i) if txt.find("SOYBEAN MEAL", i) > 0 else i + 3000]
    rows = {}
    for line in block.splitlines():
        lab = line.strip()
        for r in ROWS:
            if lab.lower().startswith(r.lower().split(",")[0].lower()) and r not in rows:
                vals = re.findall(r"(?<![\d/])(\d[\d,]*\.?\d*)(?![\d/])", lab[len(r.split(",")[0]):])
                vals = [float(v.replace(",", "")) for v in vals if not re.fullmatch(r"\d/", v)]
                if r == "Biofuel" and vals and vals[0] < 10:   # footnote marker like "3/"
                    vals = vals[1:]
                if vals:
                    rows[r] = vals
    hdr = re.findall(r"20\d\d/\d\d(?:\s*(?:Est\.|Proj\.))?", block[:600])
    return {"columns": hdr, "rows": rows}


def main():
    state = read_json(OUT, {"reports": {}}) or {"reports": {}}
    t = dt.date.today()
    for k in range(0, 3):
        y, m = (t.year, t.month - k) if t.month - k > 0 else (t.year - 1, t.month - k + 12)
        key = f"{y}-{m:02d}"
        if key in state["reports"] and k > 0:
            break
        try:
            txt = get(URL.format(m, y % 100), tries=2)
        except Exception as e:
            print("WASDE", key, e)
            continue
        save_raw("wasde", f"wasde{m:02d}{y % 100:02d}.txt", txt)
        state["reports"][key] = parse(txt)
        print(key, state["reports"][key]["rows"].get("Biofuel"))
        break
    if not state["reports"]:
        raise RuntimeError("no WASDE parsed")
    write_json(OUT, state)
    return max(state["reports"])


if __name__ == "__main__":
    sys.exit(0 if run("wasde", main) else 1)
