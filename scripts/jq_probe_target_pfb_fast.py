# JoinQuant research script: fast previous-first-board probe for one target.
#
# Note on mother-state timing:
# prepare_all calculates fb_perf before scanning the latest previous day.
# Therefore the mother state used on 2022-11-22 corresponds to this probe's
# TARGET_DATE='2022-11-21' (11/18 first boards -> 11/21 performance).

from jqdata import *
import pandas as pd
import numpy as np

# This target corresponds to the mother state used on 2022-11-22 09:05.
TARGET_DATE = '2022-11-21'


def _d(x):
    return pd.Timestamp(x).strftime('%Y-%m-%d')


def _prev_day(day):
    ds = [_d(x) for x in get_trade_days(end_date=day, count=3)]
    return ds[-2] if ds[-1] == day else ds[-1]


today = TARGET_DATE
prev = _prev_day(today)
stocks = list(get_all_securities(['stock'], date=prev).index)
stocks = [s for s in stocks if not s.startswith('688') and not s.startswith('8')]
print('FAST_START,target=%s,prev=%s,stocks=%d' % (today, prev, len(stocks)))

px3 = get_price(stocks, end_date=prev, count=3, frequency='daily',
                fields=['close', 'high_limit'], panel=False, fq=None)
fb = []
for s in stocks:
    d = px3[px3['code'] == s]
    if len(d) < 3:
        continue
    cr, hl = list(d['close']), list(d['high_limit'])
    if hl[-1] > 0 and abs(cr[-1] - hl[-1]) <= 0.02:
        if not (hl[-2] > 0 and abs(cr[-2] - hl[-2]) <= 0.02):
            fb.append(s)
print('PFB_N=%d' % len(fb))
print('PFB=' + '|'.join(fb[:160]))

px2 = get_price(fb, end_date=today, count=2, frequency='daily',
                fields=['close'], panel=False, fq=None) if fb else None
rets = []
missing = []
for s in fb:
    d = px2[px2['code'] == s]
    if len(d) < 2:
        missing.append(s)
        rets.append(np.nan)
    else:
        c = list(d['close'])
        rets.append(c[-1] / c[-2] - 1 if c[-2] else np.nan)
perf = float(np.mean(rets)) if rets else 0.0
print('FB_PERF=%s,MISSING_N=%d' % (perf, len(missing)))
if missing:
    print('MISSING=' + '|'.join(missing[:120]))
