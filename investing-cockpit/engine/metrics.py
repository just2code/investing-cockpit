import numpy as np, pandas as pd


def ew_index(close, members):
    """Equal-weighted basket: daily mean of member returns, compounded, base 100."""
    r = close[members].pct_change().mean(axis=1).fillna(0)
    return (1 + r).cumprod() * 100


def pct(s, k):
    return (s.iloc[-1] / s.iloc[-1 - k] - 1) * 100


def supertrend(h, l, c, n=10, m=3.0):
    """Returns (direction[+1/-1], line, bars since last flip)."""
    h, l, c = (np.asarray(x, float) for x in (h, l, c))
    prev = np.r_[c[0], c[:-1]]
    tr = np.maximum.reduce([h - l, abs(h - prev), abs(l - prev)])
    atr = pd.Series(tr).ewm(alpha=1 / n, adjust=False).mean().to_numpy()
    mid = (h + l) / 2
    ub, lb = mid + m * atr, mid - m * atr
    fub, flb = ub.copy(), lb.copy()
    d, st = np.ones(len(c)), np.zeros(len(c))
    st[0] = flb[0]
    for i in range(1, len(c)):
        fub[i] = ub[i] if (ub[i] < fub[i - 1] or c[i - 1] > fub[i - 1]) else fub[i - 1]
        flb[i] = lb[i] if (lb[i] > flb[i - 1] or c[i - 1] < flb[i - 1]) else flb[i - 1]
        d[i] = d[i - 1]
        if d[i - 1] == -1 and c[i] > fub[i]:
            d[i] = 1
        elif d[i - 1] == 1 and c[i] < flb[i]:
            d[i] = -1
        st[i] = flb[i] if d[i] == 1 else fub[i]
    flips = np.flatnonzero(np.diff(d) != 0)
    days = len(d) - 1 - (flips[-1] + 1) if len(flips) else len(d) - 1
    return d, st, days


def stock_metrics(close, high, low, vol):
    rows = []
    for s in close.columns:
        d = pd.DataFrame({"c": close[s], "h": high[s], "l": low[s], "v": vol[s]}).dropna()
        if len(d) < 210:
            continue
        dirn, st, days = supertrend(d.h, d.l, d.c)
        c = d.c.iloc[-1]
        rows.append(dict(
            symbol=s, close=c,
            ret_1m=(c / d.c.iloc[-22] - 1) * 100, ret_3m=(c / d.c.iloc[-64] - 1) * 100,
            trend="Long" if dirn[-1] == 1 else "Short", days_in_trend=int(days),
            trail_stop=st[-1], risk_pct=(c - st[-1]) / c * 100,
            from_52w_high=(c / d.c.tail(252).max() - 1) * 100,
            vol_ratio=d.v.tail(20).mean() / max(d.v.tail(50).mean(), 1)))
    return pd.DataFrame(rows).round(2)
