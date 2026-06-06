from jqdata import *
import numpy as np
import pandas as pd


WINDOWS = [
    ('300118.XSHE', '2020-07-13', '13:50:00', '14:06:00'),
    ('000789.XSHE', '2020-07-20', '10:30:00', '10:40:00'),
    ('000789.XSHE', '2020-07-20', '14:08:00', '14:16:00'),
]

TARGET_DAY = '2020-07-14'
WATCH = ['600711.XSHG']
IPO_DAYS = 250


def _d(x):
    return pd.Timestamp(x).strftime('%Y-%m-%d')


def _prev_day(day):
    ds = [_d(x) for x in get_trade_days(end_date=day, count=2)]
    return ds[0]


def print_windows():
    for code, day, start_t, end_t in WINDOWS:
        print('WIN_START,%s,%s,%s,%s' % (code, day, start_t, end_t))
        df = get_price(
            code,
            start_date='%s %s' % (day, start_t),
            end_date='%s %s' % (day, end_t),
            frequency='1m',
            fields=['open', 'high', 'low', 'close', 'high_limit', 'volume', 'money'],
            skip_paused=True,
            panel=False,
            fq=None,
        )
        if df is None or len(df) == 0:
            print('WIN_NO_DATA,%s,%s' % (code, day))
            continue
        if 'time' in df.columns:
            df = df.set_index('time')
        hit = df[df['close'] >= df['high_limit'] - 0.001]
        first_hit = 'NONE' if hit.empty else pd.Timestamp(hit.index[0]).strftime('%H:%M:%S')
        print('WIN_HIT,%s,%s,first=%s,hit_n=%d' % (code, day, first_hit, len(hit)))
        for idx, r in df.iterrows():
            print(
                'BAR,%s,%s,open=%.4f,high=%.4f,low=%.4f,close=%.4f,hl=%.4f,vol=%.0f,money=%.2f,hit=%s'
                % (
                    code,
                    pd.Timestamp(idx).strftime('%H:%M:%S'),
                    float(r['open']),
                    float(r['high']),
                    float(r['low']),
                    float(r['close']),
                    float(r['high_limit']),
                    float(r['volume']),
                    float(r['money']),
                    bool(float(r['close']) >= float(r['high_limit']) - 0.001),
                )
            )


def print_600711_chain():
    today = TARGET_DAY
    prev = _prev_day(today)
    code = WATCH[0]
    print('CHAIN_START,today=%s,prev=%s,code=%s' % (today, prev, code))

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

    d = px3[px3['code'] == code]
    if len(d) < 3:
        print('CHAIN_NO_DAILY,len=%d' % len(d))
        return
    cr = list(d['close'])
    hl = list(d['high_limit'])
    is_limit = hl[-1] > 0 and abs(cr[-1] - hl[-1]) <= 0.02
    prev_limit = hl[-2] > 0 and abs(cr[-2] - hl[-2]) <= 0.02
    first = is_limit and not prev_limit
    name = secs.loc[code, 'display_name'] if code in secs.index else ''
    age = (pd.Timestamp(today).date() - secs.loc[code, 'start_date']).days if code in secs.index else -1
    m = float(d.iloc[-1]['money'])
    v = float(d.iloc[-1]['volume'])
    close = float(d.iloc[-1]['close'])
    avg_chg = m / v / close * 1.1 - 1 if v > 0 and close > 0 else -999
    print(
        'CHAIN_BASE,%s,is_limit=%s,prev_limit=%s,first=%s,name=%s,age=%d,cap_ok=%s,money=%.2f,volume=%.2f,close=%.4f,hl=%.4f,avg_chg=%.6f'
        % (code, is_limit, prev_limit, first, name, age, code in valid_caps, m, v, close, float(hl[-1]), avg_chg)
    )

    v31 = history(31, '1d', 'volume', security_list=WATCH, df=False, fq='pre')
    h31 = history(31, '1d', 'high', security_list=WATCH, df=False, fq='pre')
    c31 = history(31, '1d', 'close', security_list=WATCH, df=False, fq='pre')
    vv, hh, cc = v31.get(code), h31.get(code), c31.get(code)
    if vv is None or hh is None or cc is None or len(vv) < 31:
        print('CHAIN_V122,%s,NO_HISTORY' % code)
    else:
        prev_vols = vv[-6:-1]
        is_blast = (vv[-1] > float(np.mean(prev_vols)) * 8) or (vv[-1] > float(np.min(prev_vols)) * 12)
        is_new_high = cc[-1] > float(np.max(hh[-31:-1]))
        print(
            'CHAIN_V122,%s,today_vol=%.2f,avg5=%.2f,min5=%.2f,blast=%s,new_high=%s,remove=%s'
            % (code, vv[-1], float(np.mean(prev_vols)), float(np.min(prev_vols)), is_blast, is_new_high, is_blast and is_new_high)
        )

    start_dt = '%s 09:30:00' % prev
    end_dt = '%s 15:00:00' % prev
    mdf = get_price(code, start_date=start_dt, end_date=end_dt, frequency='1m',
                    fields=['close', 'high_limit'], skip_paused=True, panel=False, fq=None)
    if mdf is None or len(mdf) == 0:
        print('CHAIN_V130,%s,NO_MINUTE' % code)
    else:
        if 'time' in mdf.columns:
            mdf = mdf.set_index('time')
        hit = mdf[mdf['close'] >= mdf['high_limit'] - 0.001]
        if hit.empty:
            print('CHAIN_V130,%s,NO_HIT' % code)
        else:
            ft = pd.Timestamp(hit.index[0])
            print('CHAIN_V130,%s,first=%s,hit_n=%d,remove_tail=%s' %
                  (code, ft.strftime('%H:%M:%S'), len(hit), ft.time().hour >= 14))

    # Bull left-pressure stage: reproduce the mother's "drop if len(c)<60 or no score" behavior.
    closes_100 = history(100, field='close', security_list=WATCH, df=False, fq='pre')
    volumes_100 = history(100, field='volume', security_list=WATCH, df=False, fq='pre')
    highs_60 = history(60, field='high', security_list=WATCH, df=False, fq='pre')
    lows_60 = history(60, field='low', security_list=WATCH, df=False, fq='pre')
    q2 = query(valuation.code, valuation.circulating_market_cap).filter(valuation.code.in_(WATCH))
    cap_df = get_fundamentals(q2, date=prev)
    cap = dict(zip(cap_df['code'], cap_df['circulating_market_cap'])) if not cap_df.empty else {}
    c = closes_100.get(code)
    vv100 = volumes_100.get(code)
    h60 = highs_60.get(code)
    l60 = lows_60.get(code)
    print('CHAIN_LEFT_INPUT,%s,len_c=%s,len_v=%s,len_h=%s,len_l=%s,cap=%s,nan_c=%s,nan_v=%s' %
          (code,
           len(c) if c is not None else -1,
           len(vv100) if vv100 is not None else -1,
           len(h60) if h60 is not None else -1,
           len(l60) if l60 is not None else -1,
           cap.get(code, None),
           bool(pd.isna(c).any()) if c is not None else True,
           bool(pd.isna(vv100).any()) if vv100 is not None else True))


print_windows()
print_600711_chain()
