"""
诊断脚本：对比验证本地实现与原版的关键差异
"""
import warnings
import pandas as pd
import numpy as np
from pathlib import Path
warnings.filterwarnings('ignore')

HDATA   = Path(r'D:\work space\hdata')
DAILY_D = HDATA / '1d_stock'
M1_D    = HDATA / '1m_stock'
IND_D   = HDATA / '1d_feature' / 'stock_indicator'
BASIC_F = HDATA / 'stock_basic.parquet'

# ============================
# 1. 加载数据
# ============================
def load_daily_sample():
    """加载 2024–2025 日线"""
    frames = []
    for yr in (2024, 2025):
        f = DAILY_D / f'{yr}.parquet'
        if f.exists():
            frames.append(pd.read_parquet(f))
    df = pd.concat(frames, ignore_index=True)
    df['date'] = df['date'].astype(str)
    # 排除 688/8/30
    c = df['code']
    mask = (~c.str.startswith('688')) & (~c.str.startswith('8')) & (~c.str.startswith('30'))
    df = df[mask].copy()
    return df

df = load_daily_sample()
print(f"总行数: {len(df):,}, 股票数: {df['code'].nunique():,}")

# ============================
# 2. 验证 pre_close 正确性
# ============================
print("\n=== 验证 pre_close 连续性 ===")
codes = df['code'].unique()[:50]
issues = 0
total = 0
for code in codes:
    sub = df[df['code'] == code].sort_values('date')
    for i in range(1, len(sub)):
        prev_close = float(sub.iloc[i-1]['close'])
        curr_pc = float(sub.iloc[i]['pre_close'])
        if prev_close > 0 and curr_pc > 0:
            total += 1
            diff = abs(curr_pc - prev_close) / prev_close
            if diff > 0.01:  # pre_close 应与前一日 close 一致（1%误差内）
                issues += 1
                if issues <= 3:
                    print(f"  {code}: {sub.iloc[i-1]['date']} close={prev_close:.2f} → "
                          f"{sub.iloc[i]['date']} pre_close={curr_pc:.2f} (diff={diff*100:.2f}%)")
print(f"  pre_close 异常比例: {issues}/{total} = {issues/total*100:.2f}%")

# ============================
# 3. 验证涨停阈值选择
# ============================
print("\n=== 首板识别: 1.095 vs 0.02绝对价差 ===")
codes_good = df[df['close'] > 5]['code'].unique()[:200]
sub = df[df['code'].isin(codes_good)].copy()
sub['pc'] = sub['pre_close'].astype(float)
sub['cl'] = sub['close'].astype(float)
sub['hl'] = sub['pc'] * 1.10
sub['hl_round'] = sub['hl'].round(2)
sub['abs_diff'] = (sub['cl'] - sub['hl_round']).abs()
sub['pct_chk'] = sub['cl'] / sub['pc']

# 原版_scan_all 判断涨停: abs_diff <= 0.02
sub['orig_limit'] = sub['abs_diff'] <= 0.02
# 本地使用 1.095
sub['local_limit'] = sub['pct_chk'] >= 1.095

# 两者不一致的情况
mismatch = sub[sub['orig_limit'] != sub['local_limit']]
print(f"  orig±0.02 判定涨停: {sub['orig_limit'].sum()}")
print(f"  local≥1.095 判定涨停: {sub['local_limit'].sum()}")
print(f"  不一致行数: {len(mismatch)}")
if len(mismatch):
    print(f"  其中orig认可但local否定的: {len(mismatch[~mismatch['local_limit'] & mismatch['orig_limit']])}")
    print(f"  其中local认可但orig否定的: {len(mismatch[mismatch['local_limit'] & ~mismatch['orig_limit']])}")
    # 抽样显示
    samp = mismatch.sample(min(10, len(mismatch)))
    for _, r in samp.iterrows():
        print(f"    {r['code']} {r['date']}: close={r['cl']:.2f}, hl={r['hl_round']:.2f}, "
              f"abs_diff={r['abs_diff']:.3f}, pct_chk={r['pct_chk']:.4f}")

# ============================
# 4. 检查 vol/amount 单位
# ============================
print("\n=== 检查 vol/amount 单位一致性 ===")
for code in codes[:5]:
    sub = df[df['code'] == code].sort_values('date').tail(5)
    print(f"\n  {code}:")
    for _, r in sub.iterrows():
        amt = float(r['amount'])
        vol = float(r['vol'])
        close = float(r['close'])
        vwap = amt / vol if vol > 0 else 0
        ratio = vwap / close if close > 0 else 0
        print(f"    {r['date']}: amt={amt:.0f}, vol={vol:.0f}, vwap={vwap:.2f}, "
              f"close={close:.2f}, vwap/close={ratio:.4f}")

# ============================
# 5. 验证一些首板样本
# ============================
print("\n=== 首板样本 check ===")
# 取一个具体交易日
test_date = '20241202'
prev_date = '20241129'
prev2_date = '20241128'
for d in [prev2_date, prev_date, test_date]:
    exists = d in set(df['date'])
    print(f"  {d}: {'✓' if exists else '✗'}")

df_t1 = df[df['date'] == prev_date].set_index('code')
df_t2 = df[df['date'] == prev2_date].set_index('code')

if not df_t1.empty and not df_t2.empty:
    common = df_t1.index.intersection(df_t2.index)
    pc1 = df_t1.loc[common, 'pre_close'].astype(float)
    pc2 = df_t2.loc[common, 'pre_close'].astype(float)
    c1 = df_t1.loc[common, 'close'].astype(float)
    c2 = df_t2.loc[common, 'close'].astype(float)

    hl_rounded = (pc1 * 1.10).round(2)
    orig_up1 = (pc1 > 0) & ((c1 - hl_rounded).abs() <= 0.02)
    local_up1 = (pc1 > 0) & (c1 / pc1 >= 1.095)

    hl2_rounded = (pc2 * 1.10).round(2)
    orig_up2 = (pc2 > 0) & ((c2 - hl2_rounded).abs() <= 0.02)
    local_up2 = (pc2 > 0) & (c2 / pc2 >= 1.095)

    # 原版一进二：T-1涨停、T-2未涨停
    fb_orig = set(common[orig_up1 & ~orig_up2])
    fb_local = set(common[local_up1 & ~local_up2])

    print(f"  原版识别首板: {len(fb_orig)}")
    print(f"  本地识别首板: {len(fb_local)}")
    diff = fb_orig - fb_local
    if diff:
        print(f"  原版有但本地无的 {len(diff)} 只:")
        for code in list(diff)[:5]:
            row = df_t1.loc[code]
            print(f"    {code}: close={row['close']:.2f}, pc={row['pre_close']:.2f}, "
                  f"ratio={float(row['close'])/float(row['pre_close']):.4f}, "
                  f"hl={float(row['pre_close'])*1.1:.2f}")
    diff2 = fb_local - fb_orig
    if diff2:
        print(f"  本地有但原版无的 {len(diff2)} 只:")
        for code in list(diff2)[:5]:
            row = df_t1.loc[code]
            hl_actual = (float(row['pre_close']) * 1.10).round(2)
            print(f"    {code}: close={row['close']:.2f}, pc={row['pre_close']:.2f}, "
                  f"ratio={float(row['close'])/float(row['pre_close']):.4f}, "
                  f"hl={hl_actual:.2f}, abs_diff={abs(float(row['close'])-hl_actual):.3f}")

# ============================
# 6. 检查 avg_chg 分布
# ============================
print("\n=== avg_chg 分布 ===")
# 取一个首板日的候选
if not df_t1.empty and not df_t2.empty:
    common = df_t1.index.intersection(df_t2.index)
    pc1 = df_t1.loc[common, 'pre_close'].astype(float)
    c1 = df_t1.loc[common, 'close'].astype(float)
    hl1 = (pc1 * 1.10).round(2)

    up_stocks = common[(pc1 > 0) & (pc2 > 0) & (c1 / pc1 >= 1.095) & (c2 / pc2 < 1.095)]

    if len(up_stocks):
        a = df_t1.loc[up_stocks, 'amount'].astype(float)
        v = df_t1.loc[up_stocks, 'vol'].astype(float)
        c = df_t1.loc[up_stocks, 'close'].astype(float)
        avg_chg = a / v / c * 1.1 - 1
        print(f"  avg_chg 统计: mean={avg_chg.mean()*100:.2f}%, "
              f"min={avg_chg.min()*100:.2f}%, max={avg_chg.max()*100:.2f}%")
        print(f"  avg_chg < 7% 比例: {(avg_chg < 0.07).mean()*100:.1f}%")
        # 显示几个异常的
        bad = avg_chg[(avg_chg < 0.05) | (avg_chg > 0.15)]
        if len(bad):
            print(f"  异常 avg_chg 样本 ({len(bad)} 只):")
            for code in bad.index[:5]:
                r = df_t1.loc[code]
                print(f"    {code}: close={float(r['close']):.2f}, amt={float(r['amount']):.0f}, "
                      f"vol={float(r['vol']):.0f}, avg_chg={float(avg_chg.loc[code])*100:.2f}%")

# ============================
# 7. 分钟数据检查
# ============================
print("\n=== 分钟数据样本 ===")
from functools import lru_cache

@lru_cache(maxsize=10)
def load_1m_year(code, year):
    f = M1_D / code / f'{year}.parquet'
    if not f.exists():
        return pd.DataFrame()
    try:
        df = pd.read_parquet(f, columns=['date', 'trade_time', 'high', 'low', 'close'])
        df['hhmm'] = (df['trade_time'].dt.hour * 100 + df['trade_time'].dt.minute).astype('int16')
        df['date'] = pd.Categorical(df['date'])
        return df
    except:
        return pd.DataFrame()

# 找一个有交易的一天
if len(up_stocks):
    sample_code = list(up_stocks)[0]
    print(f"  分钟数据: {sample_code}, prev_date={prev_date}")
    m1 = load_1m_year(sample_code, prev_date[:4])
    if not m1.empty:
        m1d = m1[m1['date'] == prev_date]
        print(f"  分钟条数: {len(m1d)}")
        if len(m1d):
            print(f"  时间范围: {m1d.iloc[0]['hhmm']} - {m1d.iloc[-1]['hhmm']}")
            print(f"  首5行:")
            for _, r in m1d.head(5).iterrows():
                print(f"    {r['hhmm']}: H={r['high']:.2f} L={r['low']:.2f} C={r['close']:.2f}")

print("\n=== 诊断完成 ===")
