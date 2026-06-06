# JoinQuant research script: batch-compute fb_perf/fb_pct for mother timing.
#
# TARGET_PERF_DATE is the date whose previous-day first boards are evaluated.
# Mother state on the next trading day uses this value.
# Example: TARGET_PERF_DATE='2022-11-21' corresponds to mother state 2022-11-22.

from jqdata import *
import pandas as pd
import numpy as np

TARGET_PERF_DATE = '2022-12-22'
COUNT = 90
FB_WIN = 60


def _d(x):
    return pd.Timestamp(x).strftime('%Y-%m-%d')


dates = [_d(x) for x in get_trade_days(end_date=TARGET_PERF_DATE, count=COUNT)]
stocks = list(get_all_securities(['stock'], date=TARGET_PERF_DATE).index)
stocks = [s for s in stocks if not s.startswith('688') and not s.startswith('8')]
print('BATCH_START,target_perf=%s,dates=%d,stocks=%d,first=%s,last=%s' %
      (TARGET_PERF_DATE, len(dates), len(stocks), dates[0], dates[-1]))

px = get_price(stocks, start_date=dates[0], end_date=dates[-1], frequency='daily',
               fields=['close', 'high_limit'], panel=False, fq=None)
if 'time' in px.columns:
    px['day'] = px['time'].apply(_d)
elif 'date' in px.columns:
    px['day'] = px['date'].apply(_d)
else:
    raise Exception('no date/time column: %s' % list(px.columns))

by_day = {d: g.set_index('code') for d, g in px.groupby('day')}
perfs = []
pfb_map = {}
for i in range(2, len(dates)):
    d2, d1, day = dates[i - 2], dates[i - 1], dates[i]
    if d1 not in by_day or d2 not in by_day or day not in by_day:
        continue
    a = by_day[d1]
    b = by_day[d2]
    common = a.index.intersection(b.index)
    c1 = a.loc[common, 'close'].astype(float)
    h1 = a.loc[common, 'high_limit'].astype(float)
    c2 = b.loc[common, 'close'].astype(float)
    h2 = b.loc[common, 'high_limit'].astype(float)
    lim1 = (h1 > 0) & ((c1 - h1).abs() <= 0.02)
    lim2 = (h2 > 0) & ((c2 - h2).abs() <= 0.02)
    pfb = list(common[lim1 & ~lim2])
    pfb_map[day] = pfb
    rets = []
    t = by_day[day]
    for s in pfb:
        if s in t.index and s in a.index:
            y = float(a.loc[s, 'close'])
            z = float(t.loc[s, 'close'])
            rets.append(z / y - 1 if y else np.nan)
        else:
            rets.append(np.nan)
    perf = float(np.mean(rets)) if rets else 0.0
    perfs.append((day, perf, len(pfb), sum(1 for x in rets if np.isnan(x))))

hist = []
target_row = None
for day, perf, n, miss in perfs:
    hist.append(perf)
    if len(hist) > FB_WIN:
        hist = hist[-FB_WIN:]
    if np.isnan(perf):
        pct = 0.0
    elif len(hist) >= 10:
        pct = sum(1 for x in hist if (not np.isnan(x)) and x < perf) / len(hist)
    else:
        pct = 0.5
    if day == TARGET_PERF_DATE:
        target_row = (day, perf, pct, len(hist), n, miss)
    if day >= TARGET_PERF_DATE:
        break

if target_row:
    day, perf, pct, hist_len, n, miss = target_row
    print('TARGET,perf_date=%s,fb_perf=%s,fb_pct=%.6f,hist_len=%d,pfb_n=%d,missing_n=%d' %
          (day, perf, pct, hist_len, n, miss))
    print('PFB=' + '|'.join(pfb_map.get(day, [])[:160]))
else:
    print('TARGET_NOT_FOUND')
