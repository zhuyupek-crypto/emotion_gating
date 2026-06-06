# JoinQuant research script: one target fb_perf/fb_pct probe.
# Change TARGET_DATE and run one target at a time.

from jqdata import *
import pandas as pd
import numpy as np

TARGET_DATE = '2022-11-22'
FB_WIN = 60


def _d(x):
    return pd.Timestamp(x).strftime('%Y-%m-%d')


def _first_boards(prev):
    stocks = list(get_all_securities(['stock'], date=prev).index)
    stocks = [s for s in stocks if not s.startswith('688') and not s.startswith('8')]
    px = get_price(stocks, end_date=prev, count=3, frequency='daily',
                   fields=['close', 'high_limit'], panel=False, fq=None)
    out = []
    for s in stocks:
        d = px[px['code'] == s]
        if len(d) < 3:
            continue
        cr, hl = list(d['close']), list(d['high_limit'])
        if hl[-1] > 0 and abs(cr[-1] - hl[-1]) <= 0.02:
            if not (hl[-2] > 0 and abs(cr[-2] - hl[-2]) <= 0.02):
                out.append(s)
    return out


def _fb_perf(today, prev_boards):
    if not prev_boards:
        return 0.0, []
    px = get_price(prev_boards, end_date=today, count=2, frequency='daily',
                   fields=['close'], panel=False, fq=None)
    vals = []
    missing = []
    for s in prev_boards:
        d = px[px['code'] == s]
        if len(d) < 2:
            vals.append(np.nan)
            missing.append(s)
        else:
            c = list(d['close'])
            vals.append(c[-1] / c[-2] - 1 if c[-2] else np.nan)
    return float(np.mean(vals)), missing


all_days = [_d(x) for x in get_trade_days(end_date=TARGET_DATE, count=75)]
print('PROBE_ONE_START,target=%s,days=%d,first=%s,last=%s' %
      (TARGET_DATE, len(all_days), all_days[0], all_days[-1]))

hist = []
prev_fb = []
last_state = None
for idx, day in enumerate(all_days):
    perf, missing = _fb_perf(day, prev_fb)
    hist.append(perf)
    if len(hist) > FB_WIN:
        hist = hist[-FB_WIN:]
    if np.isnan(perf):
        pct = 0.0
    elif len(hist) >= 10:
        pct = sum(1 for x in hist if (not np.isnan(x)) and x < perf) / len(hist)
    else:
        pct = 0.5
    last_state = (day, perf, pct, len(hist), len(prev_fb), missing)
    if idx % 5 == 0 or day == TARGET_DATE:
        print('PROGRESS,%s,idx=%d,fb_perf=%s,fb_pct=%.6f,prev_fb_n=%d,missing=%d' %
              (day, idx, perf, pct, len(prev_fb), len(missing)))
    if day == TARGET_DATE:
        break
    prev_fb = _first_boards(day)

day, perf, pct, hist_len, pfb_n, missing = last_state
print('STATE,%s,fb_perf=%s,fb_pct=%.6f,hist_len=%d,prev_fb_n=%d,missing_n=%d' %
      (day, perf, pct, hist_len, pfb_n, len(missing)))
if missing:
    print('MISSING=' + '|'.join(missing[:80]))
print('PFB=' + '|'.join(prev_fb[:120]))
