from jqdata import *
import numpy as np
import pandas as pd


TODAY = '2020-07-14'
WATCH = '600711.XSHG'
IPO_DAYS = 250


def _d(x):
    return pd.Timestamp(x).strftime('%Y-%m-%d')


def _prev_day(day):
    return _d(list(get_trade_days(end_date=day, count=2))[0])


def _hist_field(codes, count, field, end_date, fq='pre'):
    """Research-safe replacement for backtest history(...): explicit end_date."""
    df = get_price(
        codes,
        end_date=end_date,
        count=count,
        frequency='daily',
        fields=[field],
        panel=False,
        fq=fq,
    )
    out = {}
    if df is None or len(df) == 0:
        return {c: np.array([]) for c in codes}
    for c in codes:
        sub = df[df['code'] == c].sort_values('time')
        out[c] = np.asarray(sub[field].values)
    return out


def _contains(name, arr):
    print('HAS,%s,%s,n=%d' % (name, WATCH in arr, len(arr)))


today = TODAY
prev = _prev_day(today)
print('FULL_CHAIN_V2_START,today=%s,prev=%s,watch=%s' % (today, prev, WATCH))

secs = get_all_securities(['stock'], date=prev)
stocks = [s for s in secs.index if not s.startswith('688') and not s.startswith('8')]
px3 = get_price(
    stocks,
    end_date=prev,
    count=3,
    frequency='daily',
    fields=['open', 'close', 'high', 'high_limit', 'money', 'volume'],
    panel=False,
    fq=None,
)
q = query(valuation.code, valuation.circulating_market_cap).filter(
    valuation.circulating_market_cap > 30,
    valuation.circulating_market_cap < 500,
)
val = get_fundamentals(q, date=prev)
valid_caps = set(val['code'].tolist()) if not val.empty else set()

first_boards = []
base = []
for s in stocks:
    d = px3[px3['code'] == s]
    if len(d) < 3:
        continue
    cr = list(d['close'])
    hl = list(d['high_limit'])
    if not (hl[-1] > 0 and abs(cr[-1] - hl[-1]) <= 0.02):
        continue
    boards = 1
    if hl[-2] > 0 and abs(cr[-2] - hl[-2]) <= 0.02:
        boards = 2
        if hl[-3] > 0 and abs(cr[-3] - hl[-3]) <= 0.02:
            boards = 3
    if boards == 1:
        first_boards.append(s)
    else:
        continue
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
    avg_chg = m / v / close * 1.1 - 1 if v > 0 and close > 0 else -999
    if avg_chg < 0.07:
        continue
    base.append(s)

_contains('first_boards', first_boards)
_contains('base', base)

v31 = _hist_field(base, 31, 'volume', prev, fq='pre')
h31 = _hist_field(base, 31, 'high', prev, fq='pre')
c31 = _hist_field(base, 31, 'close', prev, fq='pre')
after_v122 = []
removed_v122 = []
for s in base:
    v = v31.get(s)
    h = h31.get(s)
    c = c31.get(s)
    if v is None or h is None or c is None or len(v) < 31:
        after_v122.append(s)
        continue
    prev_vols = v[-6:-1]
    remove = False
    if len(prev_vols) == 5 and np.nanmin(prev_vols) > 0:
        is_blast = (v[-1] > float(np.nanmean(prev_vols)) * 8) or (v[-1] > float(np.nanmin(prev_vols)) * 12)
        is_new_high = c[-1] > float(np.nanmax(h[-31:-1]))
        remove = bool(is_blast and is_new_high)
    if remove:
        removed_v122.append(s)
    else:
        after_v122.append(s)

_contains('after_v122', after_v122)
print('V122_REMOVED,n=%d,list=%s,watch_removed=%s' %
      (len(removed_v122), '|'.join(removed_v122), WATCH in removed_v122))
if WATCH in base:
    s = WATCH
    v = v31.get(s)
    h = h31.get(s)
    c = c31.get(s)
    pv = v[-6:-1] if v is not None and len(v) >= 6 else []
    print('WATCH_V122_DETAIL,len=%s,today_vol=%s,avg5=%s,min5=%s,close=%s,prev_high_max=%s' %
          (len(v) if v is not None else -1,
           v[-1] if v is not None and len(v) else None,
           float(np.nanmean(pv)) if len(pv) else None,
           float(np.nanmin(pv)) if len(pv) else None,
           c[-1] if c is not None and len(c) else None,
           float(np.nanmax(h[-31:-1])) if h is not None and len(h) >= 31 else None))

start_dt = '%s 09:30:00' % prev
end_dt = '%s 15:00:00' % prev
after_v130 = []
removed_tail = []
for s in after_v122:
    mdf = get_price(s, start_date=start_dt, end_date=end_dt, frequency='1m',
                    fields=['close', 'high_limit'], skip_paused=True, panel=False, fq=None)
    if mdf is None or len(mdf) == 0:
        after_v130.append(s)
        continue
    if 'time' in mdf.columns:
        mdf = mdf.set_index('time')
    hit = mdf[mdf['close'] >= mdf['high_limit'] - 0.001]
    if hit.empty:
        after_v130.append(s)
        continue
    ft = pd.Timestamp(hit.index[0])
    if ft.time().hour >= 14:
        removed_tail.append(s)
    else:
        after_v130.append(s)

_contains('after_v130', after_v130)
print('V130_REMOVED,n=%d,list=%s,watch_removed=%s' %
      (len(removed_tail), '|'.join(removed_tail), WATCH in removed_tail))

closes_100 = _hist_field(after_v130, 100, 'close', prev, fq='pre')
volumes_100 = _hist_field(after_v130, 100, 'volume', prev, fq='pre')
scored = []
dropped = []
for s in after_v130:
    c = closes_100.get(s)
    v = volumes_100.get(s)
    if c is None or v is None or len(c) < 60:
        dropped.append(s)
        continue
    prev_highs = c[:-1]
    prev_vols = v[:-1]
    max_idx = np.argmax(prev_highs)
    is_break = c[-1] >= prev_highs[max_idx] * 0.99
    vol_ok = v[-1] >= prev_vols[max_idx] * 0.9 if prev_vols[max_idx] > 0 else False
    lp_score = 1.0 if (is_break and vol_ok) else 0.5 if is_break else 0.0
    scored.append((s, lp_score))
scored.sort(key=lambda x: -x[1])
final_codes = [x[0] for x in scored]
_contains('after_left', final_codes)
print('LEFT_DROPPED,n=%d,list=%s,watch_dropped=%s' % (len(dropped), '|'.join(dropped), WATCH in dropped))
if WATCH in final_codes:
    print('WATCH_FINAL_RANK,%d' % (final_codes.index(WATCH) + 1))
else:
    print('WATCH_FINAL_RANK,NONE')
