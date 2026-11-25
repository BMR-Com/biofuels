"""Mandate balance: D4 RINs required by the RVO vs RINs generated so far this year (EPA EMTS), the run-rate needed
for the rest of the year, the feedstock pounds that implies, soybean oil's share of biofuel feedstock (EIA) and the
WASDE soybean oil biofuel line vs the EIA run-rate. Writes data/model/balance.json."""
import sys, datetime as dt
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
sys.path.insert(0, str(ROOT / "pipelines"))
from common import write_json, read_json, run  # noqa: E402


def main():
    rvo = pd.read_csv(DATA / "manual" / "rvo.csv")
    em = read_json(DATA / "rfs" / "emts.json", {}) or {}
    out = {"years": {}}
    for yr in (2026, 2027):
        r = rvo[(rvo.year == yr) & (rvo.status == "final")].set_index("category")["total_bn_rins"]
        bbd, adv, tot, cel = (float(r.get(k, float("nan"))) for k in ("Biomass-based diesel", "Advanced", "Total renewable fuel", "Cellulosic"))
        y = {"rvo_bbd": bbd, "rvo_adv": adv, "rvo_total": tot, "rvo_cel": cel,
             "other_advanced_gap": round(adv - bbd - cel, 3), "conventional": round(tot - adv, 3),
             "bbd_gal_at_1_6": round(bbd / 1.6, 3), "feedstock_bn_lb_at_8": round(bbd / 1.6 * 8, 1)}
        m = em.get("monthly", {})
        for d in ("D4", "D5", "D6", "D3"):
            pts = [p for p in m.get(d, []) if p[0].startswith(str(yr))]
            if pts:
                y[f"{d}_ytd_bn"] = round(sum(p[1] for p in pts) / 1e9, 3)
                y[f"{d}_months"] = len(pts)
                y[f"{d}_last"] = pts[-1][0]
        if y.get("D4_months"):
            left = 12 - y["D4_months"]
            # D4 is nested: D4 surplus over the BBD line fills the advanced gap; compare D4+D5 to advanced-minus-cellulosic
            need = bbd - y["D4_ytd_bn"]
            y["D4_needed_per_month_rest_bn"] = round(need / left, 3) if left > 0 else None
            y["D4_avg_month_ytd_bn"] = round(y["D4_ytd_bn"] / y["D4_months"], 3)
            y["D4_pace_full_year_bn"] = round(y["D4_ytd_bn"] / y["D4_months"] * 12, 3)
            y["D4_pace_vs_rvo_bn"] = round(y["D4_pace_full_year_bn"] - bbd, 3)
            if y.get("D5_ytd_bn") is not None:
                y["adv_pace_vs_rvo_bn"] = round((y["D4_ytd_bn"] + y["D5_ytd_bn"] + y.get("D3_ytd_bn", 0)) / y["D4_months"] * 12 - adv, 3)
        out["years"][str(yr)] = y
    # monthly D4 generation chart (last 4 years)
    out["d4_monthly"] = [p for p in em.get("monthly", {}).get("D4", []) if p[0] >= "2022-01"]
    out["d6_monthly"] = [p for p in em.get("monthly", {}).get("D6", []) if p[0] >= "2022-01"]
    out["d5_monthly"] = [p for p in em.get("monthly", {}).get("D5", []) if p[0] >= "2022-01"]
    # feedstock shares (EIA)
    fs = (read_json(DATA / "eia" / "feedstocks.json", {}) or {}).get("series", {})
    main = ["Soybean oil", "Corn oil (DCO)", "Canola oil", "Tallow", "Yellow grease (incl. UCO)", "White grease", "Poultry fat", "Other vegetable oils", "Other waste oils/fats"]
    if fs.get("Soybean oil"):
        frame = pd.DataFrame({k: dict(map(tuple, fs[k])) for k in main if k in fs}).sort_index()
        frame = frame[frame.index >= "2021-01"]
        tot = frame.sum(axis=1, min_count=3)
        out["feed_share_soy"] = [[i, round(float(v), 4)] for i, v in (frame["Soybean oil"] / tot).dropna().items()]
        last12 = frame.tail(12)
        out["feed_mix_last12_mlb"] = {k: round(float(last12[k].sum()), 0) for k in frame.columns}
        out["eia_soy_12m_bn_lb"] = round(float(last12["Soybean oil"].sum()) / 1000, 2)
        out["eia_soy_last"] = frame.index[-1]
    w = (read_json(DATA / "usda" / "wasde_soyoil.json", {}) or {}).get("reports", {})
    if w:
        k = max(w)
        out["wasde"] = {"report": k, "columns": w[k].get("columns"), "biofuel": w[k]["rows"].get("Biofuel"),
                        "ending_stocks": w[k]["rows"].get("Ending stocks"), "price": w[k]["rows"].get("Avg. Price"),
                        "history": {m: w[m]["rows"].get("Biofuel") for m in sorted(w)}}
    out["asof"] = em.get("asof")
    write_json(DATA / "model" / "balance.json", out)
    return out["asof"] or str(dt.date.today())


if __name__ == "__main__":
    sys.exit(0 if run("model_balance", main) else 1)
