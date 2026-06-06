from jqdata import *
import pandas as pd, numpy as np
CHECK_DATES = ["2024-03-12", "2024-03-13", "2024-03-15"]
IDX_CODE, IPO_DAYS, LIMIT_TOL = "000852.XSHG", 250, 0.02
CIRC_MIN, CIRC_MAX, MONEY_MIN, MONEY_MAX_BULL = 30.0, 500.0, 6e8, 20e8
def td(s): return pd.to_datetime(s).date()
def ds(d): return pd.to_datetime(d).strftime("%Y-%m-%d")
def prev_day(d):
    days = [pd.to_datetime(x).date() for x in get_all_trade_days()]
    i = days.index(td(d) if isinstance(d, str) else d)
    return days[i - 1] if i > 0 else None
def is_pass_month(d):
    d = td(d) if isinstance(d, str) else d
    if d.month in (1, 4, 12) and d.day >= 15: return True
    sf = {2024:"2024-02-10",2025:"2025-01-29",2026:"2026-02-17"}.get(d.year)
    return bool(sf and (pd.to_datetime(sf).date() - pd.Timedelta(days=15)) <= d < pd.to_datetime(sf).date())
def gp(codes, end, count=1, fields=None):
    if not codes: return pd.DataFrame()
    fields = fields or ["open","close","high","high_limit","money","volume"]
    df = get_price(codes, end_date=end, count=count, frequency="daily",
                   fields=fields, panel=False, fill_paused=False, skip_paused=False, fq=None)
    if df is None or len(df) == 0: return pd.DataFrame()
    return df.reset_index() if "time" not in df.columns else df
def one_map(codes, end, fields=None):
    df = gp(codes, end, 1, fields)
    return {} if df.empty else {r["code"]: r for _, r in df.iterrows()}
def raw_mode(prev, fb_perf=0):
    df = get_price(IDX_CODE, end_date=prev, count=65, frequency="daily",
                   fields=["close"], panel=False, fq=None)
    a = np.asarray(df["close"], float) if df is not None and len(df) else np.array([])
    if len(a) < 20: return "bear"
    if (a[-1] - a[-20:].max()) / a[-20:].max() <= -0.12: return "bear"
    if len(a) < 60: return "bear"
    ma20, ma60, price = a[-20:].mean(), a[-60:].mean(), a[-1]
    days_above = int((a[-30:] > ma60).sum())
    if price <= ma60 and ma20 <= ma60: return "bear"
    if price <= ma60 and ma20 > ma60: return "cautious" if fb_perf > 0 else "bear"
    if days_above >= 30 * 0.66: return "bull"
    return "cautious" if fb_perf > -0.02 else "bear"
def first_boards(day):
    prev = prev_day(day); secs = get_all_securities(["stock"], date=prev)
    codes = [s for s in secs.index if not s.startswith("688") and not s.startswith("8")]
    df = gp(codes, prev, 3, ["close","high_limit"])
    out, maxb = [], 0
    for c, sub in df.groupby("code"):
        sub = sub.sort_values("time")
        if len(sub) < 3: continue
        cl, hl = list(sub["close"].astype(float))[-3:], list(sub["high_limit"].astype(float))[-3:]
        if hl[-1] <= 0 or abs(cl[-1] - hl[-1]) > LIMIT_TOL: continue
        b = 1
        if hl[-2] > 0 and abs(cl[-2] - hl[-2]) <= LIMIT_TOL:
            b = 2
            if hl[-3] > 0 and abs(cl[-3] - hl[-3]) <= LIMIT_TOL: b = 3
        maxb = max(maxb, b)
        if b == 1: out.append(c)
    return out, secs, maxb
def v130(cands, prev):
    keep, tail, err = [], 0, 0
    for c in cands:
        try:
            m = get_price(c, start_date=ds(prev)+" 09:30:00", end_date=ds(prev)+" 15:00:00",
                          frequency="1m", fields=["close","high_limit"], panel=False)
            if m is None or len(m) == 0: keep.append(c); continue
            if "time" in m.columns: m = m.set_index("time")
            hit = m["close"] >= m["high_limit"] - 0.001
            if not hit.any(): keep.append(c); continue
            if pd.to_datetime(m.index[hit][0]).time().hour >= 14: tail += 1; continue
            keep.append(c)
        except Exception:
            keep.append(c); err += 1
    return keep, tail, err
def audit(day):
    day, prev = td(day), prev_day(day)
    mode = raw_mode(prev, 0.0)
    active = "v227" if (mode in ("bear","cautious") or is_pass_month(day)) else "rzq+zb"
    fb, secs, maxb = first_boards(day)
    q = query(valuation.code, valuation.circulating_market_cap).filter(
        valuation.circulating_market_cap > CIRC_MIN, valuation.circulating_market_cap < CIRC_MAX)
    vdf = get_fundamentals(q, date=prev); caps = set(vdf["code"]) if vdf is not None and not vdf.empty else set()
    ym = one_map(fb, prev, ["close","high_limit","money","volume"])
    base, drop = [], dict(st=0, ipo=0, cap=0, money=0, bullmoney=0, avg=0)
    for c in fb:
        if c in secs.index:
            name = secs.loc[c, "display_name"]
            if "ST" in name or "st" in name: drop["st"] += 1; continue
            if (day - secs.loc[c, "start_date"]).days < IPO_DAYS: drop["ipo"] += 1; continue
        if c not in caps: drop["cap"] += 1; continue
        r = ym.get(c)
        if r is None or float(r["money"]) < MONEY_MIN: drop["money"] += 1; continue
        if mode == "bull" and float(r["money"]) > MONEY_MAX_BULL: drop["bullmoney"] += 1; continue
        avg = float(r["money"]) / float(r["volume"]) / float(r["close"]) * 1.1 - 1 if float(r["volume"]) > 0 and float(r["close"]) > 0 else 0
        if avg < 0.07: drop["avg"] += 1; continue
        base.append(c)
    after130, tail, err = v130(base, prev)
    print("%s prev=%s mode=%s active=%s first=%d base=%d v130=%d tail=%d err=%d drop=%s" %
          (ds(day), ds(prev), mode, active, len(fb), len(base), len(after130), tail, err, drop))
    print("CODES=" + "|".join(after130))
for d in CHECK_DATES: audit(d)
