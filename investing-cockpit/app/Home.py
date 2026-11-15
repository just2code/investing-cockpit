import json
from pathlib import Path
import pandas as pd
import streamlit as st

D = Path(__file__).resolve().parent.parent / "data"
st.set_page_config(page_title="Strong Sectors & Stocks", layout="wide")

if not (D / "sector_table.csv").exists():
    st.error("No data yet. Run `python -m engine.run` or wait for the nightly job.")
    st.stop()


@st.cache_data(ttl=3600)
def load():
    return (pd.read_csv(D / "sector_table.csv"), pd.read_csv(D / "stock_table.csv"),
            pd.read_csv(D / "ew_index.csv", index_col=0, parse_dates=True),
            json.loads((D / "meta.json").read_text()))


sectors, stocks, ew, meta = load()
st.title("Strong sectors & stocks")
st.caption(f"EOD data as of {meta['asof']} · {meta['sectors']} sectors · {meta['stocks']} liquid stocks · "
           "equal-weighted baskets · screening aid, not advice")

with st.sidebar:
    src = st.radio("Sector source", ["All", "NSE industries", "Custom / TJI"])
    min_m = st.slider("Min stocks in sector", 4, 30, 6)
    only_strong = st.checkbox("Only strong sectors", value=False)

view = sectors[sectors.members >= min_m]
if src == "NSE industries":
    view = view[~view.custom]
elif src == "Custom / TJI":
    view = view[view.custom]
if only_strong:
    view = view[view.strong]

st.subheader("1. Sector leaderboard")
st.dataframe(
    view[["sector", "members", "score", "ret_1m", "ret_3m", "ret_6m", "rs_3m",
          "above50", "above200", "near_high", "strong", "stale"]],
    hide_index=True, use_container_width=True,
    column_config={
        "above50": st.column_config.ProgressColumn("% > 50DMA", min_value=0, max_value=100, format="%.0f%%"),
        "above200": st.column_config.ProgressColumn("% > 200DMA", min_value=0, max_value=100, format="%.0f%%"),
        "near_high": st.column_config.ProgressColumn("% near 52w high", min_value=0, max_value=100, format="%.0f%%"),
        "score": st.column_config.NumberColumn("Score", format="%.0f"),
        "rs_3m": "RS 3M (pp)", "ret_1m": "1M %", "ret_3m": "3M %", "ret_6m": "6M %"})
st.caption("Strong = basket above its 50DMA, 60%+ of stocks above 50DMA, and 3M outperformance vs the "
           "equal-weighted universe. Stale = custom list not refreshed for 90+ days.")

st.subheader("2. Equal-weighted baskets (rebased, last 6M)")
sel = st.multiselect("Sectors", view.sector.tolist(), default=view.sector.head(5).tolist())
if sel:
    t = ew[[s for s in sel if s in ew.columns]].tail(126)
    st.line_chart(t / t.iloc[0] * 100)

st.subheader("3. Strongest stocks in a sector")
sec = st.selectbox("Sector", view.sector.tolist())
long_only = st.checkbox("Supertrend long only", value=True)
t = stocks[stocks.sector == sec]
if long_only:
    t = t[t.trend == "Long"]
t = t.sort_values("rs_sector_3m", ascending=False)
t = t.assign(fresh=(t.trend == "Long") & (t.days_in_trend <= 10))
st.dataframe(
    t[["symbol", "name", "close", "ret_1m", "ret_3m", "rs_sector_3m", "trend", "days_in_trend", "fresh",
       "trail_stop", "risk_pct", "from_52w_high", "vol_ratio"]],
    hide_index=True, use_container_width=True,
    column_config={"rs_sector_3m": "RS vs sector 3M (pp)", "risk_pct": "Risk to trail %",
                   "fresh": "Fresh flip (≤10d)", "vol_ratio": "Vol 20d/50d"})
st.caption("Trail stop = Supertrend(10, 3) line. Trail it rather than setting a fixed target.")

st.subheader("4. Diversification check")
picks = st.multiselect("Shortlist", sorted(stocks.symbol.unique()))
if picks:
    prim = stocks.sort_values("sector", key=lambda s: ~s.str.startswith("NSE:")).drop_duplicates("symbol")
    cnt = prim[prim.symbol.isin(picks)].sector.value_counts()
    st.bar_chart(cnt)
    if len(picks) >= 3 and cnt.iloc[0] / len(picks) > 0.4:
        st.warning(f"{cnt.iloc[0]} of {len(picks)} picks are in {cnt.index[0]}. Consider spreading across sectors.")
