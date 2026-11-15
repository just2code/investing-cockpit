"""Nightly pipeline: python -m engine.run"""
import json, datetime as dt
import pandas as pd, yfinance as yf
from engine.universe import load_groups, ROOT
from engine import metrics as M

MIN_TURNOVER = 2e7   # Rs 2 crore average daily traded value (20d)
MIN_MEMBERS = 4
OUT = ROOT / "data"


def download(symbols, period="2y", chunk=100):
    parts = []
    for i in range(0, len(symbols), chunk):
        t = [s + ".NS" for s in symbols[i:i + chunk]]
        df = yf.download(t, period=period, auto_adjust=True, progress=False, threads=True)
        if not df.empty:
            parts.append(df)
    full = pd.concat(parts, axis=1)
    full.columns = pd.MultiIndex.from_tuples([(f, s.replace(".NS", "")) for f, s in full.columns])
    return [full[f].sort_index().ffill(limit=3) for f in ("Close", "High", "Low", "Volume")]


def main():
    groups, n5 = load_groups()
    names = dict(zip(n5.symbol, n5["name"]))
    close, high, low, vol = download(sorted(groups.symbol.unique()))
    turnover = (close * vol).tail(20).mean()
    ok = [s for s in close.columns if close[s].count() >= 210 and turnover.get(s, 0) >= MIN_TURNOVER]
    close, high, low, vol = (x[ok] for x in (close, high, low, vol))

    bench = M.ew_index(close, ok)
    ma50, ma200 = close.rolling(50).mean().iloc[-1], close.rolling(200).mean().iloc[-1]
    hi252 = close.rolling(252, min_periods=200).max().iloc[-1]
    last = close.iloc[-1]

    rows, ew_all = [], {}
    for sec, g in groups.groupby("sector"):
        mem = [s for s in g.symbol if s in close.columns]
        if len(mem) < MIN_MEMBERS:
            continue
        ew = M.ew_index(close, mem)
        ew_all[sec] = ew
        rows.append(dict(
            sector=sec, members=len(mem),
            ret_1m=M.pct(ew, 21), ret_3m=M.pct(ew, 63), ret_6m=M.pct(ew, 126),
            rs_3m=M.pct(ew, 63) - M.pct(bench, 63),
            above50=(last[mem] > ma50[mem]).mean() * 100,
            above200=(last[mem] > ma200[mem]).mean() * 100,
            near_high=(last[mem] >= 0.9 * hi252[mem]).mean() * 100,
            ew_above_50dma=bool(ew.iloc[-1] > ew.rolling(50).mean().iloc[-1]),
            custom=not sec.startswith("NSE:"), updated=g.updated.min()))
    sec = pd.DataFrame(rows)
    r = lambda c: sec[c].rank(pct=True)
    sec["score"] = (0.4 * r("rs_3m") + 0.3 * r("ret_1m") + 0.3 * r("above50")) * 100
    sec["strong"] = sec.ew_above_50dma & (sec.above50 >= 60) & (sec.rs_3m > 0)
    sec["stale"] = (pd.Timestamp.today() - pd.to_datetime(sec.updated)).dt.days > 90
    sec = sec.sort_values("score", ascending=False).round(1)

    sm = M.stock_metrics(close, high, low, vol)
    stk = (groups.merge(sm, on="symbol")
           .merge(sec[["sector", "ret_3m"]].rename(columns={"ret_3m": "sector_ret_3m"}), on="sector"))
    stk["rs_sector_3m"] = (stk.ret_3m - stk.sector_ret_3m).round(1)
    stk["name"] = stk.symbol.map(names).fillna(stk.symbol)

    OUT.mkdir(exist_ok=True)
    sec.to_csv(OUT / "sector_table.csv", index=False)
    stk.drop(columns=["updated"]).to_csv(OUT / "stock_table.csv", index=False)
    pd.DataFrame(ew_all).tail(252).round(2).to_csv(OUT / "ew_index.csv")
    (OUT / "meta.json").write_text(json.dumps({"asof": str(close.index[-1].date()),
                                               "run": dt.datetime.utcnow().isoformat(),
                                               "stocks": len(ok), "sectors": len(sec)}))
    print(f"done: {len(sec)} sectors, {len(ok)} stocks, as of {close.index[-1].date()}")


if __name__ == "__main__":
    main()
