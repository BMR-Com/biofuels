"""USDA FAS PSD world vegetable-oil balances (monthly with WASDE): palm, soybean, rapeseed, sunflower oil for the
main producers/consumers. Output data/usda/psd_vegoil.json: {commodity: {country: {year: {attribute: 1000 t}}}}."""
import io, sys, zipfile
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import DATA, get, write_json, run  # noqa: E402

URL = "https://apps.fas.usda.gov/psdonline/downloads/psd_oilseeds_csv.zip"
COMM = {"Oil, Palm": "Palm oil", "Oil, Soybean": "Soybean oil", "Oil, Rapeseed": "Rapeseed oil", "Oil, Sunflowerseed": "Sunflower oil"}
COUNTRIES = ["Indonesia", "Malaysia", "United States", "Brazil", "Argentina", "China", "India", "European Union", "Canada", "World"]
ATTR = ["Production", "Imports", "Exports", "Industrial Dom. Cons.", "Food Use Dom. Cons.", "Domestic Consumption", "Ending Stocks"]


def main():
    b = get(URL, binary=True, timeout=120)
    z = zipfile.ZipFile(io.BytesIO(b))
    d = pd.read_csv(z.open(z.namelist()[0]))
    d = d[d.Commodity_Description.isin(COMM) & d.Attribute_Description.isin(ATTR) & (d.Market_Year >= 2015)]
    out = {}
    for r in d.itertuples():
        c = r.Country_Name if r.Country_Name in COUNTRIES else None
        if c is None:
            continue
        out.setdefault(COMM[r.Commodity_Description], {}).setdefault(c, {}).setdefault(str(r.Market_Year), {})[r.Attribute_Description] = float(r.Value)
    # world totals
    w = d.groupby(["Commodity_Description", "Market_Year", "Attribute_Description"]).Value.sum()
    for (cm, y, a), v in w.items():
        out.setdefault(COMM[cm], {}).setdefault("World", {}).setdefault(str(y), {})[a] = float(v)
    write_json(DATA / "usda" / "psd_vegoil.json", {"unit": "1000 t", "data": out})
    return str(int(d.Market_Year.max()))


if __name__ == "__main__":
    sys.exit(0 if run("psd", main) else 1)
