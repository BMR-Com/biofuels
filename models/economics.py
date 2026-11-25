"""Biofuel input/output economics: for each pathway (feedstock -> BD / RD / SAF), the per-gallon stack
   revenue  = ULSD (or jet) + RINs x EV + LCFS credit (California only) + 45Z + co-products
   cost     = feedstock (c/lb x lb/gal) + opex
   margin   = revenue - cost;  breakeven D4 = (cost - other revenue) / EV
plus the BOHO spread and its history. Writes data/model/margins.json (outputs and the variables used only)."""
import json, sys, datetime as dt
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
sys.path.insert(0, str(ROOT / "pipelines"))
from common import write_json, read_json, run  # noqa: E402

A = json.loads((DATA / "manual" / "assumptions.json").read_text())


def px(latest, k):
    v = latest.get(k)
    return v["close"] if v and not v.get("stale") else None


def ams_latest(item, max_age=45):
    rows = (read_json(DATA / "ams" / "cash.json", {}) or {}).get("rows", [])
    r = sorted([x for x in rows if x["item"] == item], key=lambda x: x["date"])
    if r and (dt.date.today() - dt.date.fromisoformat(r[-1]["date"])).days <= max_age:
        return r[-1]["value"], r[-1]["date"]
    return None, None


def lcfs_price(latest):
    lc = read_json(DATA / "credits" / "lcfs.json", {}) or {}
    fut = latest.get("LCS")
    if fut and not fut.get("stale"):
        return fut["close"], f"OPIS LCFS futures {fut['date']}"
    if lc.get("ca_weekly", {}).get("avg_price"):
        w = lc["ca_weekly"]
        return w["avg_price"], f"CARB weekly average {w.get('week') or w.get('checked')}"
    if lc.get("ca_monthly"):
        m = lc["ca_monthly"][-1]
        return m[1], f"CARB monthly average {m[0]}"
    return None, None


def feed_prices(latest):
    zl = px(latest, "ZL")
    fb = A["feedstock_fallback_vs_zl_c_lb"]
    out = {"soybean": (zl, "CBOT soybean oil front month")}
    for k, item, lab in (("dco", "dco_ia", "USDA AMS distillers corn oil"), ("tallow", "tallow_bft", "USDA AMS bleachable tallow")):
        v, d = ams_latest(item)
        out[k] = (v, f"{lab} {d}") if v is not None else ((zl + fb[k]) if zl else None, f"CBOT soybean oil {fb[k]:+.0f}c/lb (desk spread; cash quote missing)")
    out["uco"] = ((zl + fb["uco"]) if zl else None, f"CBOT soybean oil {fb['uco']:+.0f}c/lb (desk spread to Midwest UCO)")
    v, d = ams_latest("yg_mn")
    if v is None:
        v, d = ams_latest("yg_rt")
    if v is not None:
        out["yellow_grease"] = (v, f"USDA AMS yellow grease {d} (reference only)")
    out["canola"] = ((zl + fb["canola"]) if zl else None, f"CBOT soybean oil {fb['canola']:+.0f}c/lb (no free US canola oil cash price)")
    fc, fx = px(latest, "FCPO"), px(latest, "USDMYR")
    out["palm"] = ((fc / fx / 22.0462) if fc and fx else None, "Bursa FCPO converted at USD/MYR (not RFS-eligible; comparison only)")
    fu = px(latest, "FUCO")
    out["uco_asia"] = ((fu / 22.0462) if fu else None, "Bursa UCO futures (FOB Asia, thin)")
    return out


def stack(p, feeds, ulsd, jet, d4, lcfs, year=2026):
    fuel = p["fuel"]
    lbg = A["lb_per_gal"][fuel]
    ev = A["ev"]["BD"] if fuel == "BD" else A["ev"][f"{fuel}_{min(year, 2027) if year >= 2027 else 2026}"]
    f_c, f_src = feeds[p["feed"]]
    if f_c is None or ulsd is None or d4 is None:
        return None
    feed = f_c * lbg / 100
    z = A["z45"]
    z45 = 0.0
    if p["na_feed"] and year <= 2029:
        z45 = max(0.0, z["max_per_gal"] * z["inflation_factor"] * (z["threshold"] - p["ci_45z"]) / z["threshold"])
    lc = 0.0
    if lcfs is not None:
        mt = (A["lcfs"]["diesel_ci_std_2026"] - p["ci_carb"]) * A["energy_mj_per_gal"][fuel] * A["lcfs"]["eer"] / 1e6
        lc = max(0.0, mt * lcfs)
    fuel_px = jet if (fuel == "SAF" and jet) else ulsd
    rin = d4 * ev
    co = A["coproduct_per_gal"][fuel]
    opex = A["opex_per_gal"][fuel]
    base = fuel_px + rin + z45 + co - feed - opex
    return {"id": p["id"], "label": p["label"], "fuel": fuel, "feed_c_lb": round(f_c, 2), "feed_src": f_src,
            "feed_per_gal": round(feed, 3), "opex": opex, "fuel_px": round(fuel_px, 4), "ev": ev, "rin_per_gal": round(rin, 3),
            "z45_per_gal": round(z45, 3), "lcfs_per_gal": round(lc, 3), "coproduct": co,
            "margin_ex_ca": round(base, 3), "margin_ca": round(base + lc, 3),
            "breakeven_d4_ex_ca": round((feed + opex - fuel_px - z45 - co) / ev, 3),
            "ci_carb": p["ci_carb"], "ci_45z": p["ci_45z"]}


def history():
    """Daily BOHO, D4 x 1.5 and the soy-biodiesel screen margin (ex-45Z, ex-LCFS) from the stored price files."""
    def s(k):
        f = DATA / "prices" / f"{k}.csv"
        if not f.exists():
            return None
        d = pd.read_csv(f, parse_dates=["date"]).set_index("date")["close"]
        return d[~d.index.duplicated()]
    zl, ho, d4 = s("ZL"), s("HO"), s("RN4")
    if zl is None or ho is None:
        return {}
    df = pd.concat({"zl": zl, "ho": ho, "d4": d4} if d4 is not None else {"zl": zl, "ho": ho}, axis=1).dropna(subset=["zl", "ho"])
    df = df[df.index >= "2016-01-01"]
    df["boho"] = df.zl * 0.075 - df.ho
    if "d4" in df:
        df["d4"] = df["d4"].ffill(limit=5)
        df["rin_bd"] = df.d4 * 1.5
        df["soy_bd_margin"] = df.ho + df.rin_bd + A["coproduct_per_gal"]["BD"] - df.zl * A["lb_per_gal"]["BD"] / 100 - A["opex_per_gal"]["BD"]
    df = df.round(4)
    return {c: [[d.strftime("%Y-%m-%d"), (None if pd.isna(v) else float(v))] for d, v in df[c].items()] for c in df.columns}


def series():
    """Daily closes for the charts (since 2019), palm converted to c/lb."""
    out = {}
    for k in ("ZL", "HO", "RN4", "RN6", "RN3", "LCS", "FCPO", "RS", "ECO", "ULS", "FUCO", "CU", "OSF", "ZS", "ZM"):
        f = DATA / "prices" / f"{k}.csv"
        if not f.exists():
            continue
        d = pd.read_csv(f, parse_dates=["date"]).set_index("date")["close"].dropna()
        d = d[~d.index.duplicated()]
        d = d[d.index >= "2019-01-01"]
        if k == "FCPO" and (DATA / "prices" / "USDMYR.csv").exists():
            fx = pd.read_csv(DATA / "prices" / "USDMYR.csv", parse_dates=["date"]).set_index("date")["close"]
            fx = fx[~fx.index.duplicated()].reindex(d.index).ffill()
            d = (d / fx / 22.0462).dropna()
            k = "PALM_c_lb"
        out[k] = [[i.strftime("%Y-%m-%d"), round(float(v), 4)] for i, v in d.items()]
    write_json(DATA / "model" / "series.json", out)


def desk_read(i, rows):
    """Plain-language bullets built from the numbers only (no forecasts)."""
    out = []
    b, cov, d4, d6 = i.get("boho"), i.get("boho_cover"), i.get("d4"), i.get("d6")
    if b is not None and cov is not None:
        out.append(f"BOHO is {b:+.2f} $/gal; D4 x 1.5 = {i['rin_bd_per_gal']:.2f}, so RINs {'cover' if cov >= 0 else 'fall short of'} the "
                   f"soybean oil premium to heating oil by {abs(cov):.2f} $/gal before 45Z and LCFS.")
    if d4 and d6:
        sp = d4 - d6
        out.append(f"D4 trades {sp:+.3f} over D6: " + ("a wide spread says biomass-based diesel, not ethanol, is the marginal RIN." if sp > 0.10
                   else "a tight spread says the D4 market is not paying much above the conventional (D6) clearing price, so BBD supply is ample against the nested mandate."))
    ex = [r for r in rows if r["fuel"] in ("BD", "RD")]
    if ex:
        best = max(ex, key=lambda r: r["margin_ca"]); worst = min(ex, key=lambda r: r["margin_ex_ca"])
        out.append(f"Best screen margin: {best['label']} at {best['margin_ca']:+.2f} $/gal into California; weakest: {worst['label']} at {worst['margin_ex_ca']:+.2f} $/gal outside it.")
        marg = max(ex, key=lambda r: r["breakeven_d4_ex_ca"])
        if d4:
            out.append(f"Highest breakeven D4 is {marg['label']} at {marg['breakeven_d4_ex_ca']:.2f} vs D4 at {d4:.2f}: "
                       + ("that capacity is under water and should be cutting runs." if marg["breakeven_d4_ex_ca"] > d4 else "even the marginal pathway runs at screen prices."))
    y = ((read_json(DATA / "model" / "balance.json", {}) or {}).get("years") or {}).get(str(dt.date.today().year), {})
    if y.get("D4_pace_vs_rvo_bn") is not None:
        gap = y["D4_pace_vs_rvo_bn"]
        out.append(f"Mandate: D4 generation through {y['D4_last']} runs at {y['D4_pace_full_year_bn']:.2f} bn RINs a year vs a {y['rvo_bbd']:.2f} bn "
                   f"biomass-based diesel obligation ({gap:+.2f} bn); the rest of the year needs {y['D4_needed_per_month_rest_bn']:.2f} bn a month vs "
                   f"{y['D4_avg_month_ytd_bn']:.2f} so far" + (", so the RIN has to keep paying for more gallons (or carryover RINs get drawn)." if gap < 0 else ", so the mandate is covered and RINs have room to soften."))
    soy = next((r for r in rows if r["id"] == "soy_bd"), None)
    if soy:
        out.append(f"Soybean oil biodiesel: {soy['margin_ex_ca']:+.2f} $/gal with 45Z of {soy['z45_per_gal']:.2f}; breakeven D4 {soy['breakeven_d4_ex_ca']:.2f}.")
    return out


def main():
    series()
    latest = (read_json(DATA / "prices" / "latest.json", {}) or {}).get("prices", {})
    if not latest:
        raise RuntimeError("no prices")
    ulsd, d4, d6, d3 = px(latest, "HO"), px(latest, "RN4"), px(latest, "RN6"), px(latest, "RN3")
    spot = (read_json(DATA / "eia" / "spot.json", {}) or {}).get("series", {})
    jet = spot.get("usgc_jet", [[None, None]])[-1][1] if spot.get("usgc_jet") else None
    jet = jet if jet else (ulsd + 0.05 if ulsd else None)
    lc, lc_src = lcfs_price(latest)
    feeds = feed_prices(latest)
    rows = [r for r in (stack(p, feeds, ulsd, jet, d4, lc) for p in A["pathways"]) if r]
    rows27 = [r for r in (stack(p, feeds, ulsd, jet, d4, lc, 2027) for p in A["pathways"]) if r]
    zl = px(latest, "ZL")
    boho = round(zl * 0.075 - ulsd, 4) if zl and ulsd else None
    out = {
        "asof": latest.get("ZL", {}).get("date"),
        "inputs": {"ulsd": ulsd, "jet": jet, "d4": d4, "d6": d6, "d3": d3, "lcfs": lc, "lcfs_src": lc_src,
                   "zl_c_lb": zl, "boho": boho, "d4_minus_d6": round(d4 - d6, 4) if d4 and d6 else None,
                   "rin_bd_per_gal": round(d4 * 1.5, 4) if d4 else None,
                   "boho_cover": round(d4 * 1.5 - boho, 4) if d4 and boho is not None else None,
                   "feeds": {k: {"c_lb": (round(v[0], 2) if v[0] is not None else None), "src": v[1]} for k, v in feeds.items()}},
        "pathways": rows, "pathways_2027": rows27,
        "variables": ["CBOT soybean oil", "NYMEX ULSD", "US Gulf jet (EIA)", "D4 RIN (OPIS futures)", "D6 RIN", "LCFS credit",
                      "USDA AMS tallow, yellow grease, distillers corn oil", "Bursa palm and UCO", "RIN equivalence values",
                      "CARB CI and energy density", "45Z emissions rate", "opex and co-product credits"],
        "history": history(),
    }
    out["read"] = desk_read(out["inputs"], rows)
    write_json(DATA / "model" / "margins.json", out)
    return out["asof"]


if __name__ == "__main__":
    sys.exit(0 if run("model_economics", main) else 1)
