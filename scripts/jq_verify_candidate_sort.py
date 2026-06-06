"""
一进二候选排序逐只对比
输出 2024-03-12 完整候选清单（按成交额排序）
用于对比两地的候选排序差异
"""
from jqdata import *
import pandas as pd
import numpy as np
from datetime import datetime, date

TODAY_STR = "2024-03-12"
CIRC_MIN, CIRC_MAX = 30.0, 500.0
MONEY_MIN = 6e8
IPO_DAYS = 250
LIMIT_TOL = 0.02


def get_prev(date_str):
    all_days = list(get_all_trade_days())
    parts = date_str.split("-")
    dt = date(int(parts[0]), int(parts[1]), int(parts[2]))
    try:
        idx = all_days.index(dt)
        if idx > 0:
            d = all_days[idx - 1]
            return f"{d.year}-{d.month:02d}-{d.day:02d}"
    except:
        pass
    for i in range(len(all_days)-1, -1, -1):
        if all_days[i] < dt:
            d = all_days[i]
            return f"{d.year}-{d.month:02d}-{d.day:02d}"
    return None


def fetch_d1(codes, end_date):
    if not codes:
        return {}
    df = get_price(codes, end_date=end_date, count=1, frequency='daily',
                   fields=['open', 'close', 'pre_close', 'high', 'low',
                           'high_limit', 'money', 'volume'],
                   panel=False, fill_paused=False, skip_paused=False)
    if df.empty:
        return {}
    result = {}
    for _, row in df.iterrows():
        c = row['code']
        result[c] = {k: (float(row[k]) if k in row and not pd.isna(row[k]) else 0)
                     for k in ['open', 'close', 'pre_close', 'high', 'low',
                                'high_limit', 'money', 'volume']}
    return result


today = datetime.strptime(TODAY_STR, "%Y-%m-%d").date()
prev_str = get_prev(TODAY_STR)
prev = datetime.strptime(prev_str, "%Y-%m-%d").date()
prev2_str = get_prev(prev_str)

print(f"T日={TODAY_STR}  T-1={prev_str}  T-2={prev2_str}\n")

# Step 0: 全市场
secs = get_all_securities(['stock'], date=prev)
codes_all = [s for s in secs.index if not s.startswith('688') and not s.startswith('8')]
print(f"【0】全市场（排除688/8开头）: {len(codes_all)}")

# Step 1: 首板（T-1涨停 T-2未涨停）
d1 = fetch_d1(codes_all, prev_str)
d2 = fetch_d1(codes_all, prev2_str) if prev2_str else {}

first_boards = []
for s in codes_all:
    r1 = d1.get(s)
    if not r1 or r1['high_limit'] <= 0 or abs(r1['close'] - r1['high_limit']) > LIMIT_TOL:
        continue
    r2 = d2.get(s)
    if r2 and r2['high_limit'] > 0 and abs(r2['close'] - r2['high_limit']) <= LIMIT_TOL:
        continue
    first_boards.append(s)

print(f"【1】首板宽集: {len(first_boards)}")

# Step 2: ST/IPO/市值
q = query(valuation.code, valuation.circulating_market_cap)
df_val = get_fundamentals(q, date=prev)
val_map = dict(zip(df_val['code'], df_val['circulating_market_cap'])) if not df_val.empty else {}

step2 = []
for s in first_boards:
    if s not in secs.index:
        continue
    name = secs.loc[s, 'display_name']
    if 'ST' in name or 'st' in name or '*' in name:
        continue
    if (today - secs.loc[s, 'start_date']).days < IPO_DAYS:
        continue
    if s not in val_map:
        continue
    circ = float(val_map[s])
    if circ < CIRC_MIN or circ > CIRC_MAX:
        continue
    step2.append((s, circ))

print(f"【2】ST/IPO/市值过滤: {len(step2)}")

# Step 3: 成交额 + avg_chg
d_t1 = fetch_d1([s for s, _ in step2], prev_str)
step3 = []
for s, circ in step2:
    r = d_t1.get(s)
    if not r:
        continue
    m = r['money']
    v = r['volume']
    c = r['close']
    if m < MONEY_MIN:
        continue
    if v > 0 and c > 0:
        avg_chg = m / v / c * 1.1 - 1
        if avg_chg < 0.07:
            continue
    step3.append((s, circ, m))

print(f"【3】成交额+avg_chg: {len(step3)}")

# Step 4: 开盘涨幅
d_today = fetch_d1([s for s, _, _ in step3], TODAY_STR)
step4 = []
for s, circ, money in step3:
    r = d_today.get(s)
    if not r:
        continue
    t_open = r['open']
    hl_today = r['high_limit']
    yclose = d_t1.get(s, {}).get('close', 0)
    if yclose <= 0 or t_open <= 0:
        continue
    if t_open >= hl_today * 0.999:
        continue
    open_pct = t_open / yclose - 1
    if open_pct < 0 or open_pct > 0.095:
        continue
    step4.append((s, circ, money, open_pct))

# 按成交额降序（前2只是最终买入候选）
step4.sort(key=lambda x: -(x[2] if x[2] > 0 else 0))

print(f"【4】开盘涨幅过滤: {len(step4)}")
print(f"\n{'='*70}")
print(f"{'排序':<4s} {'代码':<16s} {'流通市值(亿)':<14s} {'成交额(亿)':<12s} {'开盘涨幅':<10s} {'T-1涨停':<8s} {'T日开盘':<8s}")
print("=" * 70)

for idx, (s, circ, money, op) in enumerate(step4):
    r1 = d1.get(s, {})
    r_t = d_today.get(s, {})
    yc = r1.get('close', 0)
    t_open = r_t.get('open', 0)
    ms = f"{money/1e8:.2f}" if money > 0 else "0"
    print(f"{idx+1:<4d} {s:<16s} {circ:<14.1f} {ms:<12s} {op*100:<10.2f}% {yc:<8.2f} {t_open:<8.2f}")

print("\n验证结束")
