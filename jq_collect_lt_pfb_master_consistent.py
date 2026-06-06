# JoinQuant research script: collect daily limit-up and first-board sets.
# Master-consistent core:
# - universe: get_all_securities(['stock'], date=prev), excluding 688* and 8*
# - prices: get_price(..., end_date=prev, count=3, fq=None)
# - limit hit: high_limit > 0 and abs(close - high_limit) <= tol
# - first board: today limit hit and previous day not limit hit
#
# Usage in JQ research:
# 1) Set START/END below.
# 2) Run this cell/script.
# Important:
# In JQ backtests, the mother template uses history(), which is anchored to
# context.current_dt. In JQ research, history() is not anchored to our loop day,
# so this script uses get_price(end_date=prev, count=3) to reproduce the same
# three daily bars explicitly.

from jqdata import *
import pandas as pd


START = '2020-01-01'
END = '2020-12-31'
TOLS = (0.01, 0.02)
OUT_FILE = 'jq_lt_pfb_master_consistent_v2_2020.csv'


def _code(x):
    return str(x)


def _codes(xs):
    return '|'.join([_code(x) for x in xs])


def _emit(rows, kind, day, prev, tol, codes):
    codes = sorted([_code(x) for x in codes])
    rows.append({
        'date': day,
        'prev_date': prev,
        'tol': tol,
        'kind': kind,
        'n': len(codes),
        'codes': _codes(codes),
    })


def _daily_3_maps(all_stocks, prev):
    df = get_price(
        all_stocks,
        end_date=prev,
        count=3,
        frequency='daily',
        fields=['close', 'high_limit'],
        skip_paused=False,
        fq=None,
        panel=False,
    )
    close_map = {}
    high_limit_map = {}
    if df is None or len(df) == 0:
        return close_map, high_limit_map

    # Common JQ panel=False shape for multiple securities:
    # columns include code/time/close/high_limit.
    if 'code' in df.columns:
        for code, sub in df.groupby('code'):
            sub = sub.sort_index()
            if 'time' in sub.columns:
                sub = sub.sort_values('time')
            close_map[code] = list(sub['close'].values)
            high_limit_map[code] = list(sub['high_limit'].values)
        return close_map, high_limit_map

    # Some environments return MultiIndex rows: (time, code) or (code, time).
    if hasattr(df.index, 'nlevels') and df.index.nlevels >= 2:
        names = list(df.index.names)
        code_level = 1
        for i, name in enumerate(names):
            if name in ('code', 'security'):
                code_level = i
        for code, sub in df.groupby(level=code_level):
            sub = sub.sort_index()
            close_map[str(code)] = list(sub['close'].values)
            high_limit_map[str(code)] = list(sub['high_limit'].values)
        return close_map, high_limit_map

    raise Exception('Unsupported get_price shape: columns=%s index=%s' % (list(df.columns), df.index))


def _prev_trade_day(day):
    ds = list(get_trade_days(end_date=day, count=3))
    ds = [str(x) for x in ds]
    if ds[-1] == day:
        return ds[-2]
    return ds[-1]


def _scan_prev(rows, day):
    prev = _prev_trade_day(day)
    all_stocks = list(get_all_securities(['stock'], date=prev).index)
    all_stocks = [s for s in all_stocks if not s.startswith('688') and not s.startswith('8')]
    closes_raw, high_limits = _daily_3_maps(all_stocks, prev)

    for tol in TOLS:
        lt = []
        pfb = []
        for s in all_stocks:
            hl = high_limits.get(s)
            cr = closes_raw.get(s)
            if hl is None or cr is None or len(hl) < 3 or len(cr) < 3:
                continue
            is_limit = hl[-1] > 0 and abs(cr[-1] - hl[-1]) <= tol
            if not is_limit:
                continue
            lt.append(s)
            prev_limit = hl[-2] > 0 and abs(cr[-2] - hl[-2]) <= tol
            if not prev_limit:
                pfb.append(s)
        _emit(rows, 'LT', day, prev, tol, lt)
        _emit(rows, 'PFB', day, prev, tol, pfb)


def main():
    days = [str(x) for x in get_trade_days(start_date=START, end_date=END)]
    rows = []
    print('LT_PFB_START,%s,%s,days=%d,tols=%s,out=%s' % (
        START, END, len(days), '|'.join(['%.2f' % x for x in TOLS]), OUT_FILE
    ))
    for i, day in enumerate(days):
        _scan_prev(rows, day)
        if i % 20 == 0:
            print('LT_PFB_PROGRESS,%s,%d/%d' % (day, i + 1, len(days)))
    df = pd.DataFrame(rows, columns=['date', 'prev_date', 'tol', 'kind', 'n', 'codes'])
    df.to_csv(OUT_FILE, index=False, encoding='utf-8-sig')
    print('LT_PFB_DONE,%s,%s,days=%d,rows=%d,out=%s' % (
        START, END, len(days), len(df), OUT_FILE
    ))


main()
