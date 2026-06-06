# JoinQuant research script: probe bear-scorpion candidate chain for mismatch days.
# Paste into JQ research and run. It only prints a few dates/codes.

from jqdata import *
import pandas as pd

CASES = {
    '2022-03-18': ['002422.XSHE', '600257.XSHG'],
    '2022-04-06': ['600146.XSHG', '601919.XSHG'],
    '2022-05-10': ['002688.XSHE', '002952.XSHE', '600822.XSHG', '603900.XSHG'],
    '2022-12-20': ['000983.XSHE', '000546.XSHE', '002427.XSHE'],
}


def _prev_trade_day(day):
    ds = list(get_trade_days(end_date=day, count=3))
    ds = [str(x) for x in ds]
    return ds[-2] if ds[-1] == day else ds[-1]


def _one_day(today):
    prev = _prev_trade_day(today)
    secs = get_all_securities(['stock'], date=prev)
    stocks = [s for s in secs.index if not s.startswith('688') and not s.startswith('8')]
    px3 = get_price(stocks, end_date=prev, count=3, frequency='daily',
                    fields=['close', 'high_limit'], panel=False, fq=None)
    op1 = get_price(stocks, start_date=today, end_date=today, frequency='daily',
                    fields=['open'], panel=False, fq=None)
    fb, bear_pool = [], []
    for s in stocks:
        d = px3[px3['code'] == s]
        if len(d) < 3:
            continue
        cr = list(d['close'])
        hl = list(d['high_limit'])
        if hl[-1] > 0 and abs(cr[-1] - hl[-1]) <= 0.01:
            boards = 1
            if hl[-2] > 0 and abs(cr[-2] - hl[-2]) <= 0.01:
                boards = 2
            if boards == 1:
                fb.append(s)
                if s.startswith('30'):
                    continue
                if s in secs.index:
                    name = secs.loc[s, 'display_name']
                    if 'ST' in name or 'st' in name:
                        continue
                    if (pd.Timestamp(today).date() - secs.loc[s, 'start_date']).days < 250:
                        continue
                bear_pool.append(s)
    c60 = get_price(bear_pool, end_date=prev, count=60, frequency='daily',
                    fields=['close'], panel=False, fq='pre') if bear_pool else None
    bear = []
    for s in bear_pool:
        arr = list(c60[c60['code'] == s]['close']) if c60 is not None else []
        if len(arr) < 20:
            continue
        h60, l60 = max(arr), min(arr)
        pos = (arr[-1] - l60) / (h60 - l60) if h60 > l60 else 999
        if pos <= 0.5:
            bear.append(s)
    print('DAY,%s,prev=%s,fb=%d,bear_pool=%d,bear=%d' % (today, prev, len(fb), len(bear_pool), len(bear)))
    print('BEAR_FIRST80=' + '|'.join(bear[:80]))
    for s in CASES[today]:
        name = secs.loc[s, 'display_name'] if s in secs.index else 'NOSEC'
        sd = secs.loc[s, 'start_date'] if s in secs.index else ''
        d = px3[px3['code'] == s]
        cr = list(d['close']) if len(d) else []
        hl = list(d['high_limit']) if len(d) else []
        od = op1[op1['code'] == s]
        op = float(od.iloc[0]['open']) if len(od) else None
        yclose = cr[-1] if cr else None
        open_pct = op / yclose - 1 if op and yclose else None
        arr = list(c60[c60['code'] == s]['close']) if c60 is not None and s in bear_pool else []
        pos = None
        if len(arr) >= 20 and max(arr) > min(arr):
            pos = (arr[-1] - min(arr)) / (max(arr) - min(arr))
        print('DETAIL,%s,name=%s,start=%s,in_fb=%s,in_pool=%s,in_bear=%s,cr=%s,hl=%s,op=%s,open_pct=%s,pos60=%s' %
              (s, name, sd, s in fb, s in bear_pool, s in bear, cr, hl, op, open_pct, pos))


for day in CASES:
    _one_day(day)
