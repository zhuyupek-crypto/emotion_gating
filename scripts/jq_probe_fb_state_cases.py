# JoinQuant research script: probe fb_perf/fb_pct around remaining mismatches.

from jqdata import *
import pandas as pd
import numpy as np

CASES = ['2022-11-22', '2022-12-20', '2022-12-23', '2022-12-27']
FB_WIN = 60


def _d(x):
    return pd.Timestamp(x).strftime('%Y-%m-%d')


def _prev_day(day):
    ds = [_d(x) for x in get_trade_days(end_date=day, count=3)]
    return ds[-2] if ds[-1] == day else ds[-1]


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
        return 0.0
    px = get_price(prev_boards, end_date=today, count=2, frequency='daily',
                   fields=['close'], panel=False, fq=None)
    vals = []
    for s in prev_boards:
        d = px[px['code'] == s]
        if len(d) < 2:
            vals.append(np.nan)
        else:
            c = list(d['close'])
            vals.append(c[-1] / c[-2] - 1 if c[-2] else np.nan)
    return float(np.mean(vals))


hist = []
days = [_d(x) for x in get_trade_days(start_date='2022-08-15', end_date='2022-12-30')]
prev_fb = []
print('PROBE_START,days=%d,first=%s,last=%s' % (len(days), days[0], days[-1]))
for day in days:
    perf = _fb_perf(day, prev_fb)
    hist.append(perf)
    if len(hist) > FB_WIN:
        hist = hist[-FB_WIN:]
    pct = 0.0 if np.isnan(perf) else (sum(1 for x in hist if (not np.isnan(x)) and x < perf) / len(hist) if len(hist) >= 10 else 0.5)
    if day in CASES:
        print('STATE,%s,prev=%s,fb_perf=%s,fb_pct=%.6f,hist_len=%d,prev_fb_n=%d' %
              (day, _prev_day(day), perf, pct, len(hist), len(prev_fb)))
        print('PFB=' + '|'.join(prev_fb[:120]))
    prev_fb = _first_boards(day)
