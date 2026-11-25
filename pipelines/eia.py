"""EIA public files (no API key): biofuel feedstock consumption (dnav, monthly), operable biofuel capacity,
Monthly Energy Review tables 10.3/10.4a/10.4b/10.4c (ethanol, biodiesel, renewable diesel, other biofuels incl. SAF)
and spot ULSD prices (NY Harbor, US Gulf Coast, LA CARB).

Outputs data/eia/feedstocks.json, capacity.json, mer.json, spot.json.
"""
import io, sys
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import DATA, get, save_raw, write_json, run  # noqa: E402

OUT = DATA / "eia"
FEED = "https://www.eia.gov/dnav/pet/xls/PET_PNP_FEEDBIOFUEL_DCU_NUS_M.xls"
CAP = "https://www.eia.gov/dnav/pet/xls/PET_PNP_CAPBIO_DCU_NUS_M.xls"
MER = "https://www.eia.gov/totalenergy/data/browser/csv.php?tbl={}"
SPOT = "https://www.eia.gov/dnav/pet/hist_xls/{}d.xls"
SPOT_IDS = {"nyh_ulsd": "EER_EPD2DXL0_PF4_Y35NY_DPG", "usgc_ulsd": "EER_EPD2DXL0_PF4_RGC_DPG",
            "la_carb_ulsd": "EER_EPD2DC_PF4_Y05LA_DPG", "usgc_jet": "EER_EPJK_PF4_RGC_DPG"}
# feedstock series id fragment -> desk label (million lb per month)
FEEDS = {"EPOOBDSO_": "Soybean oil", "EPOOBDCNO_": "Corn oil (DCO)", "EPOOBDCO_": "Canola oil",
         "EPOOBDFSTL_": "Tallow", "EPOOBDFSYG_": "Yellow grease (incl. UCO)", "EPOOBDFSWG_": "White grease",
         "EPOOBDFSPT_": "Poultry fat", "EPOOBDVOO_": "Other vegetable oils", "EPOOBDAFO_": "Other waste oils/fats",
         "EPOOBDSOD_": "Soybean oil - biodiesel plants", "EPOOBDSOR_": "Soybean oil - renewable diesel plants"}


def dnav_xls(url, name):
    b = get(url, binary=True)
    save_raw("eia", name, b)
    xl = pd.ExcelFile(io.BytesIO(b))
    frames = []
    for sh in xl.sheet_names:
        if not sh.lower().startswith("data"):
            continue
        raw = xl.parse(sh, header=None)
        ids, names = raw.iloc[1], raw.iloc[2]       # row 2: sourcekeys, row 3: descriptions
        d = raw.iloc[3:].copy()
        d.columns = ["date"] + [f"{ids[i]}|{names[i]}" for i in range(1, raw.shape[1])]
        d["date"] = pd.to_datetime(d["date"], errors="coerce")
        frames.append(d.dropna(subset=["date"]).set_index("date"))
    df = pd.concat(frames, axis=1)
    return df.apply(pd.to_numeric, errors="coerce")


def feedstocks():
    df = dnav_xls(FEED, "feedbiofuel.xls")
    out = {}
    for frag, label in FEEDS.items():
        col = next((c for c in df.columns if frag in c.split("|")[0]), None)
        if col is None:
            continue
        s = df[col].dropna()
        out[label] = [[d.strftime("%Y-%m"), round(float(v), 1)] for d, v in s.items()]
    if "Soybean oil" not in out:
        raise RuntimeError("soybean oil series not found")
    last = out["Soybean oil"][-1][0]
    write_json(OUT / "feedstocks.json", {"asof": last, "unit": "million lb", "series": out})
    return last


def capacity():
    df = dnav_xls(CAP, "capbio.xls")
    out = {c.split("|")[1].strip(): [[d.strftime("%Y-%m"), float(v)] for d, v in df[c].dropna().items()] for c in df.columns}
    last = max(v[-1][0] for v in out.values() if v)
    write_json(OUT / "capacity.json", {"asof": last, "unit": "million gal/yr", "series": out})
    return last


def mer():
    out, last = {}, None
    for tbl in ("T10.03", "T10.04A", "T10.04B", "T10.04C"):
        txt = get(MER.format(tbl))
        save_raw("eia", f"mer_{tbl}.csv", txt)
        d = pd.read_csv(io.StringIO(txt))
        d = d[d["YYYYMM"] % 100 <= 12]
        d["Value"] = pd.to_numeric(d["Value"], errors="coerce")
        for (msn, desc, unit), g in d.groupby(["MSN", "Description", "Unit"]):
            g = g.dropna(subset=["Value"]).sort_values("YYYYMM")
            g = g[g["YYYYMM"] >= 201001]
            if g.empty:
                continue
            out[msn] = {"table": tbl, "desc": desc, "unit": unit,
                        "data": [[f"{int(y) // 100}-{int(y) % 100:02d}", round(float(v), 3)] for y, v in zip(g.YYYYMM, g.Value)]}
            last = max(last or "", out[msn]["data"][-1][0])
    write_json(OUT / "mer.json", {"asof": last, "series": out})
    return last


def spot():
    out = {}
    for k, sid in SPOT_IDS.items():
        try:
            b = get(SPOT.format(sid), binary=True)
            raw = pd.read_excel(io.BytesIO(b), sheet_name="Data 1", skiprows=2)
            raw.columns = ["date", "v"] + list(raw.columns[2:])
            s = raw.dropna(subset=["v"])
            s = s[pd.to_datetime(s["date"]) >= "2018-01-01"]
            out[k] = [[pd.Timestamp(d).strftime("%Y-%m-%d"), round(float(v), 4)] for d, v in zip(s["date"], s["v"])]
        except Exception as e:
            print("spot", k, e)
    if not out:
        raise RuntimeError("no spot series")
    last = max(v[-1][0] for v in out.values())
    write_json(OUT / "spot.json", {"asof": last, "unit": "$/gal", "series": out})
    return last


if __name__ == "__main__":
    which = sys.argv[1:] or ["feedstocks", "capacity", "mer", "spot"]
    res = [run(f"eia_{w}", globals()[w]) for w in which]
    sys.exit(0 if all(res) else 1)
