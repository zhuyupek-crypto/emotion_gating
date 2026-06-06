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


def _contains(name, arr):
    print('HAS,%s,%s,n=%d' % (name, WATCH in arr, len(arr)))


today = TODAY
prev = _prev_day(today)
print('FULL_CHAIN_START,today=%s,prev=%s,watch=%s' % (today, prev, WATCH))

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
reasons = {}
for s in stocks:
    d = px3[px3['code'] == s]
    if len(d) < 3:
        reasons[s] = 'daily_len_%d' % len(d)
        continue
    cr = list(d['close'])
    hl = list(d['high_limit'])
    if not (hl[-1] > 0 and abs(cr[-1] - hl[-1]) <= 0.02):
        reasons[s] = 'not_limit'
        continue
    boards = 1
    if hl[-2] > 0 and abs(cr[-2] - hl[-2]) <= 0.02:
        boards = 2
        if hl[-3] > 0 and abs(cr[-3] - hl[-3]) <= 0.02:
            boards = 3
    if boards == 1:
        first_boards.append(s)
    if boards != 1:
        reasons[s] = 'not_first_%d' % boards
        continue
    name = secs.loc[s, 'display_name'] if s in secs.index else ''
    if 'ST' in name or 'st' in name:
        reasons[s] = 'st'
        continue
    if s in secs.index and (pd.Timestamp(today).date() - secs.loc[s, 'start_date']).days < IPO_DAYS:
        reasons[s] = 'ipo'
        continue
    if s not in valid_caps:
        reasons[s] = 'cap'
        continue
    m = float(d.iloc[-1]['money'])
    v = float(d.iloc[-1]['volume'])
    close = float(d.iloc[-1]['close'])
    if m < 6e8:
        reasons[s] = 'money'
        continue
    avg_chg = m / v / close * 1.1 - 1 if v > 0 and close > 0 else -999
    if avg_chg < 0.07:
        reasons[s] = 'avg'
        continue
    base.append(s)
    reasons[s] = 'base_ok'

_contains('first_boards', first_boards)
_contains('base', base)
print('WATCH_REASON_AFTER_BASE,%s' % reasons.get(WATCH))

v31 = history(31, '1d', 'volume', security_list=base, df=False, fq='pre')
h31 = history(31, '1d', 'high', security_list=base, df=False, fq='pre')
c31 = history(31, '1d', 'close', security_list=base, df=False, fq='pre')
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
    if len(prev_vols) == 5 and prev_vols.min() > 0:
        is_blast = (v[-1] > float(np.mean(prev_vols)) * 8) or (v[-1] > float(np.min(prev_vols)) * 12)
        is_new_high = c[-1] > float(np.max(h[-31:-1]))
        remove = is_blast and is_new_high
    if remove:
        removed_v122.append(s)
    else:
        after_v122.append(s)

_contains('after_v122', after_v122)
print('V122_REMOVED_N=%d,watch_removed=%s' % (len(removed_v122), WATCH in removed_v122))

start_dt = '%s 09:30:00' % prev
end_dt = '%s 15:00:00' % prev
after_v130 = []
removed_tail = []
err_keep = []
for s in after_v122:
    try:
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
            continue
        after_v130.append(s)
    except Exception:
        err_keep.append(s)
        after_v130.append(s)

_contains('after_v130', after_v130)
print('V130_REMOVED_N=%d,ERR_KEEP_N=%d,watch_removed=%s,watch_err_keep=%s' %
      (len(removed_tail), len(err_keep), WATCH in removed_tail, WATCH in err_keep))

# Mother bull scoring. Track all names dropped by score due insufficient data.
closes_100 = history(100, field='close', security_list=after_v130, df=False, fq='pre')
volumes_100 = history(100, field='volume', security_list=after_v130, df=False, fq='pre')
highs_60 = history(60, field='high', security_list=after_v130, df=False, fq='pre')
lows_60 = history(60, field='low', security_list=after_v130, df=False, fq='pre')
q2 = query(valuation.code, valuation.circulating_market_cap).filter(valuation.code.in_(after_v130))
cap_df = get_fundamentals(q2, date=prev)
circ_caps = dict(zip(cap_df['code'], cap_df['circulating_market_cap'])) if not cap_df.empty else {}
scored = []
dropped_score = []
for s in after_v130:
    c = closes_100.get(s)
    v = volumes_100.get(s)
    if c is None or v is None or len(c) < 60:
        dropped_score.append(s)
        continue
    prev_highs = c[:-1]
    prev_vols = v[:-1]
    max_idx = np.argmax(prev_highs)
    is_break = c[-1] >= prev_highs[max_idx] * 0.99
    vol_ok = v[-1] >= prev_vols[max_idx] * 0.9 if prev_vols[max_idx] > 0 else False
    lp_score = 1.0 if (is_break and vol_ok) else 0.5 if is_break else 0.0
    circ_cap = circ_caps.get(s, 0)
    score = lp_score * 0.5
    scored.append((s, score, lp_score, is_break, vol_ok, circ_cap))

scored.sort(key=lambda x: -x[1])
final_codes = [x[0] for x in scored]
_contains('after_left', final_codes)
print('LEFT_DROPPED_N=%d,watch_dropped=%s' % (len(dropped_score), WATCH in dropped_score))
for i, row in enumerate(scored[:40]):
    s, score, lp_score, is_break, vol_ok, circ_cap = row
    marker = '<WATCH>' if s == WATCH else ''
    print('LEFT_RANK,%d,%s,score=%.6f,lp=%.3f,break=%s,vol_ok=%s,cap=%s%s' %
          (i + 1, s, score, lp_score, is_break, vol_ok, circ_cap, marker))
if WATCH in final_codes:
    print('WATCH_FINAL_RANK,%d' % (final_codes.index(WATCH) + 1))
else:
    print('WATCH_FINAL_RANK,NONE')
