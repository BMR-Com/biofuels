"""Daily futures, swaps and FX closes for the desk, from TradingView (tvdatafeed, no login, ~10 min delayed;
daily bars = exchange settlements once the session has closed).

Writes, per desk key:
  data/prices/<key>.csv     date, close (front), close2 (second), plus contract columns where fetched
  data/prices/latest.json   newest close per key, its trade date, the contract it came from and a stale flag
Curves for soybean oil and ULSD (next 8 listed months) go to data/prices/curves.json (BOHO curve).

Thin markets (RIN, LCFS, BOHO swaps) sometimes leave the continuous 1! series on an old contract, so for those the
script also pulls named contracts around today and keeps whichever series has the newest bar.
"""
import sys, time, datetime as dt
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import DATA, write_json, run  # noqa: E402

OUT = DATA / "prices"
CODES = "FGHJKMNQUVXZ"
# key: (exchange, root, unit, description, thin)
SYMS = {
    "ZL":   ("CBOT", "ZL", "c/lb", "CBOT soybean oil", False),
    "ZS":   ("CBOT", "ZS", "c/bu", "CBOT soybeans", False),
    "ZM":   ("CBOT", "ZM", "$/st", "CBOT soybean meal", False),
    "ZC":   ("CBOT", "ZC", "c/bu", "CBOT corn", False),
    "OSF":  ("CBOT", "OSF", "%", "CBOT soybean oilshare", True),
    "HO":   ("NYMEX", "HO", "$/gal", "NYMEX NY Harbor ULSD", False),
    "RB":   ("NYMEX", "RB", "$/gal", "NYMEX RBOB gasoline", False),
    "CL":   ("NYMEX", "CL", "$/bbl", "NYMEX WTI crude", False),
    "CU":   ("NYMEX", "CU", "$/gal", "Chicago ethanol (Platts) swap", True),
    "RN4":  ("NYMEX", "RN4", "$/RIN", "D4 biomass-based diesel RIN (OPIS)", True),
    "RN6":  ("NYMEX", "RN6", "$/RIN", "D6 renewable fuel RIN (OPIS)", True),
    "RN3":  ("NYMEX", "RN3", "$/RIN", "D3 cellulosic RIN (OPIS)", True),
    "LCS":  ("NYMEX", "LCS", "$/t", "California LCFS credit (OPIS)", True),
    "BHO":  ("NYMEX", "BHO", "$/gal", "Soybean oil vs NYH ULSD spread swap", True),
    "FCPO": ("MYX", "FCPO", "MYR/t", "Bursa crude palm oil", False),
    "FUCO": ("MYX", "FUCO", "$/t", "Bursa used cooking oil", True),
    "RS":   ("ICEUS", "RS", "CAD/t", "ICE canola", False),
    "ECO":  ("EURONEXT", "ECO", "EUR/t", "Euronext rapeseed", False),
    "ULS":  ("ICEEUR", "ULS", "$/t", "ICE low sulphur gasoil", False),
    "FBD":  ("NYMEX", "FBD", "$/t", "FAME 0 biodiesel FOB Rdam (Argus)", True),
    "UCR":  ("NYMEX", "UCR", "$/t", "UCOME biodiesel FOB ARA (Argus)", True),
    "HVO":  ("NYMEX", "HVO", "$/t", "HVO Class II FOB ARA (Argus)", True),
}
FX = {"USDMYR": ("FX_IDC", "USDMYR"), "USDCAD": ("FX_IDC", "USDCAD"), "EURUSD": ("FX_IDC", "EURUSD")}
CURVES = {"ZL": "FHKNQUVZ", "HO": CODES}   # listed months used for the curve


def trade_dates(index):
    ts = pd.to_datetime(index)
    return (ts + pd.to_timedelta((ts.hour >= 18).astype(int), unit="D")).normalize()


class TV:
    def __init__(self):
        from tvDatafeed import TvDatafeed, Interval
        self.tv, self.I = TvDatafeed(), Interval

    def hist(self, sym, ex, n=4000):
        for a in range(3):
            try:
                d = self.tv.get_hist(symbol=sym, exchange=ex, interval=self.I.in_daily, n_bars=n)
                if d is not None and len(d):
                    d.index = trade_dates(d.index)
                    d = d[~d.index.duplicated(keep="last")]
                    return d
            except Exception as e:
                print(sym, ex, "err", str(e)[:80])
            time.sleep(2 + 2 * a)
        return None


def next_contracts(months, n, today):
    out, y, m = [], today.year, today.month
    for k in range(0, 30):
        mm = (m - 1 + k) % 12 + 1
        yy = y + (m - 1 + k) // 12
        c = CODES[mm - 1]
        if c in months:
            out.append(f"{c}{yy}")
        if len(out) >= n:
            break
    return out


def settled(d):
    """Keep only bars for trade dates whose US settle (~14:30 CT) has passed: the evening session that opens at
    17:00 CT is stamped with the next trade date and must not be stored as a close."""
    now = pd.Timestamp.now(tz="America/Chicago")
    cut = now.date() if now.hour >= 15 else (now - pd.Timedelta(days=1)).date()
    return d[[x.date() <= cut for x in d.index]]


def fetch_all():
    OUT.mkdir(parents=True, exist_ok=True)
    tv = TV()
    today = dt.date.today()
    latest, curves = {}, {}
    for key, (ex, root, unit, desc, thin) in SYMS.items():
        series = {}
        for n in (1, 2):
            d = tv.hist(f"{root}{n}!", ex)
            if d is not None:
                series[f"c{n}"] = settled(d)
            time.sleep(1)
        if thin:   # named contracts: this month .. +3, and December of this and next year (RIN vintages)
            names = [f"{CODES[(today.month - 1 + k) % 12]}{today.year + (today.month - 1 + k) // 12}" for k in range(0, 4)]
            names += [f"Z{today.year}", f"Z{today.year + 1}"]
            for nm in dict.fromkeys(names):
                d = tv.hist(f"{root}{nm}", ex, n=400)
                if d is not None:
                    series[nm] = settled(d)
                time.sleep(1)
        if not series:
            print(key, "no data")
            continue
        df = pd.DataFrame({k: v["close"] for k, v in series.items()})
        df.index = pd.to_datetime(df.index).date
        df.index.name = "date"
        df = df.sort_index()
        # front = the series with the newest bar (ties: c1); for thin markets this skips a stuck 1!
        best = max(series, key=lambda k: (series[k].index[-1], k == "c1"))
        s = df[best].dropna()
        front = df[best] if best == "c1" or "c1" not in df else df[best].combine_first(df["c1"])
        df.insert(0, "close", front)
        df.to_csv(OUT / f"{key}.csv", float_format="%.6g")
        last_d = s.index[-1]
        latest[key] = {"close": float(s.iloc[-1]), "date": str(last_d), "contract": best, "unit": unit, "desc": desc,
                       "prev": float(s.iloc[-2]) if len(s) > 1 else None,
                       "stale": (today - last_d).days > 6}
        print(key, best, last_d, s.iloc[-1])
        if key in CURVES:
            pts = []
            for nm in next_contracts(CURVES[key], 8, today):
                d = tv.hist(f"{root}{nm}", ex, n=30)
                if d is not None and len(settled(d)):
                    dd = settled(d)
                    pts.append({"contract": nm, "close": float(dd["close"].iloc[-1]), "date": str(dd.index[-1].date())})
                time.sleep(1)
            curves[key] = pts
    for key, (ex, sym) in FX.items():
        d = tv.hist(sym, ex, n=4000)
        if d is None:
            continue
        s = d["close"]; s.index = pd.to_datetime(s.index).date
        s.rename("close").to_frame().rename_axis("date").to_csv(OUT / f"{key}.csv", float_format="%.6g")
        latest[key] = {"close": float(s.iloc[-1]), "date": str(s.index[-1]), "unit": "fx", "desc": key, "stale": False}
    if "ZL" not in latest or "HO" not in latest:
        raise RuntimeError("core prices (ZL/HO) missing")
    write_json(OUT / "latest.json", {"updated": str(dt.datetime.utcnow())[:16], "prices": latest})
    write_json(OUT / "curves.json", curves)
    stale = [k for k, v in latest.items() if v.get("stale")]
    if stale:
        print("stale:", stale)
    return latest["ZL"]["date"]


if __name__ == "__main__":
    ok = run("prices", fetch_all)
    sys.exit(0 if ok else 1)
