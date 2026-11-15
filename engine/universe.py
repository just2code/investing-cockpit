import io, datetime as dt
from pathlib import Path
import pandas as pd, requests

ROOT = Path(__file__).resolve().parent.parent
URLS = ["https://www.niftyindices.com/IndexConstituent/ind_nifty500list.csv",
        "https://nsearchives.nseindia.com/content/indices/ind_nifty500list.csv"]
LOCAL = ROOT / "data" / "nifty500list.csv"


def load_nifty500():
    """Nifty 500 list (name, industry, symbol). Falls back to the last saved copy if NSE blocks us."""
    df = None
    for u in URLS:
        try:
            r = requests.get(u, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
            r.raise_for_status()
            df = pd.read_csv(io.StringIO(r.text))
            df.to_csv(LOCAL, index=False)
            break
        except Exception as e:
            print("download failed:", u, e)
    if df is None:
        df = pd.read_csv(LOCAL)
    df = df.rename(columns={"Company Name": "name", "Industry": "industry", "Symbol": "symbol"})
    return df[["name", "industry", "symbol"]]


def load_groups():
    """Base layer = NSE industry. Overlay = sectors.csv (TJI / custom). Returns (groups, nifty500)."""
    n5 = load_nifty500()
    base = pd.DataFrame({"sector": "NSE: " + n5.industry, "symbol": n5.symbol,
                         "updated": dt.date.today().isoformat()})
    f = ROOT / "sectors.csv"
    custom = pd.read_csv(f, comment="#") if f.exists() else base.iloc[0:0]
    groups = pd.concat([base, custom], ignore_index=True)
    groups["symbol"] = groups.symbol.astype(str).str.upper().str.strip()
    return groups.drop_duplicates(["sector", "symbol"]), n5
