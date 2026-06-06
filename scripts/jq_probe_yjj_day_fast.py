# JoinQuant research script: fast yjj chain for one buy day.

from jqdata import *
import pandas as pd

TARGET_DATE = '2022-12-26'
WATCH = ['000029.XSHE', '002093.XSHE', '600779.XSHG']
IPO_DAYS = 250


def _d(x):
    return pd.Timestamp(x).strftime('%Y-%m-%d')


def _prev_days(day):
    ds = [_d(x) for x in get_trade_days(end_date=day, count=4)]
    if ds[-1] == day:
        return ds[-2], ds[-3]
    return ds[-1], ds[-2]


today = TARGET_DATE
prev, prev2 = _prev_days(today)
secs = get_all_securities(['stock'], date=prev)
stocks = [s for s in secs.index if not s.startswith('688') and not s.startswith('8')]
print('YJJ_START,today=%s,prev=%s,prev2=%s,stocks=%d' % (today, prev, prev2, len(stocks)))

px3 = get_price(stocks, end_date=prev, count=3, frequency='daily',
                fields=['open', 'close', 'high_limit', 'money', 'volume'], panel=False, fq=None)
q = query(valuation.code, valuation.circulating_market_cap).filter(
    valuation.circulating_market_cap > 30,
    valuation.circulating_market_cap < 500
)
val = get_fundamentals(q, date=prev)
valid_caps = set(val['code'].tolist()) if not val.empty else set()

fb = []
base = []
for s in stocks:
    d = px3[px3['code'] == s]
    if len(d) < 3:
        continue
    cr, hl = list(d['close']), list(d['high_limit'])
    if not (hl[-1] > 0 and abs(cr[-1] - hl[-1]) <= 0.02):
        continue
    if hl[-2] > 0 and abs(cr[-2] - hl[-2]) <= 0.02:
        continue
    fb.append(s)
    name = secs.loc[s, 'display_name'] if s in secs.index else ''
    if 'ST' in name or 'st' in name:
        continue
    if s in secs.index and (pd.Timestamp(today).date() - secs.loc[s, 'start_date']).days < IPO_DAYS:
        continue
    if s not in valid_caps:
        continue
    m = float(d.iloc[-1]['money'])
    v = float(d.iloc[-1]['volume'])
    close = float(d.iloc[-1]['close'])
    if m < 6e8:
        continue
    avg_chg = m / v / close * 1.1 - 1 if v > 0 and close > 0 else 0
    if avg_chg < 0.07:
        continue
    base.append(s)

print('FB_N=%d,BASE_N=%d' % (len(fb), len(base)))
print('BASE=' + '|'.join(base[:120]))

# Avoid a slow all-candidate 1m scan in research. Only inspect WATCH names.
v130 = list(base)
print('V130_SKIPPED_FULL_SCAN,BASE_AS_V130=' + '|'.join(v130[:120]))

today_px = get_price(WATCH, start_date=today, end_date=today, frequency='daily',
                     fields=['open', 'high_limit'], panel=False, fq=None)
for s in WATCH:
    dday = px3[px3['code'] == s]
    yclose = float(dday.iloc[-1]['close']) if len(dday) else None
    watch_tail = None
    try:
        mdf = get_price(s, start_date=prev, end_date=prev, frequency='1m',
                        fields=['close'], panel=False, fq=None)
        hl_prev = float(dday.iloc[-1]['high_limit']) if len(dday) else 0
        hit = mdf[mdf['close'] >= hl_prev - 0.001] if hl_prev > 0 and len(mdf) else mdf.iloc[0:0]
        if len(hit):
            tcol = 'time' if 'time' in hit.columns else None
            ft = hit.iloc[0][tcol] if tcol else hit.index[0]
            watch_tail = pd.Timestamp(ft).strftime('%H:%M')
        else:
            watch_tail = 'NO_HIT'
    except Exception as e:
        watch_tail = 'ERR:%s' % e
    trow = today_px[today_px['code'] == s] if len(today_px) else today_px
    op = float(trow.iloc[0]['open']) if len(trow) else None
    hl = float(trow.iloc[0]['high_limit']) if len(trow) else None
    paused = 'NA_IN_RESEARCH'
    opct = op / yclose - 1 if op and yclose else None
    print('DETAIL,%s,in_fb=%s,in_base=%s,first_hit_prev=%s,yclose=%s,open=%s,hl=%s,opct=%s,paused=%s,name=%s' %
          (s, s in fb, s in base, watch_tail, yclose, op, hl, opct, paused,
           secs.loc[s, 'display_name'] if s in secs.index else 'NOSEC'))
