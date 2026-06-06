"""
一进二策略 — 本地候选池诊断脚本
===================================
与 jq_verify_candidates.py 输出相同格式，
直接粘贴对比两地候选池差异。
"""
import os, sys, pandas as pd, numpy as np
from pathlib import Path

sys.path.insert(0, r"D:\work space\hdata\local_quant")

# ============================================================
# 配置（与 backtest_yijin.py 一致）
# ============================================================
CHECK_DATES = [
    "2024-03-01",
    "2024-03-15",
    "2024-06-05",
    "2024-09-10",
    "2024-11-20",
    "2024-01-15",
    "2024-04-22",
    "2024-08-01",
]
CIRC_MIN = 30.0
CIRC_MAX = 500.0
MONEY_MIN = 6e8
IPO_DAYS = 250
LIMIT_TOL = 0.02

HDATA = Path(r"D:\work space\hdata")
DAILY_D = HDATA / '1d_stock'
IND_D = HDATA / '1d_feature' / 'stock_indicator'
BASIC_F = HDATA / 'stock_basic.parquet'

# data loading
print("Loading data...")
df = pd.concat([
    pd.read_parquet(DAILY_D / f'{y}.parquet', columns=["code","date","open","close","pre_close","high","low","vol","amount"])
    for y in [2023, 2024]
], ignore_index=True)
df["date"] = df["date"].astype(str)
df = df[~df["code"].str.startswith("688") & ~df["code"].str.startswith("8")]
daily_lkp = {d: g.set_index("code") for d, g in df.groupby("date", sort=False)}
all_dates = sorted(daily_lkp.keys())

df_ind = pd.read_parquet(IND_D / "2024.parquet", columns=["code","date","circ_mv"])
df_ind["date"] = df_ind["date"].astype(str)
df_ind["circ_mv_yi"] = df_ind["circ_mv"].astype(float) / 1e8
ind_lkp = {d: g.set_index("code")["circ_mv_yi"] for d, g in df_ind.groupby("date", sort=False)}

basic = pd.read_parquet(BASIC_F)
ipo_lkp = dict(zip(basic["code"], basic["list_date"].astype(str)))
print(f"Daily: {len(daily_lkp)} days, Indicator: {len(ind_lkp)} days, Basic: {len(ipo_lkp)} stocks")


def get_prev_date(date_str):
    idx = all_dates.index(date_str) if date_str in all_dates else -1
    return all_dates[idx - 1] if idx > 0 else None


def verify_one_day(today_str):
    today_yyyymmdd = today_str.replace("-", "")
    prev_str = get_prev_date(today_yyyymmdd)
    if prev_str is None:
        return f"{today_str}: no prev date"
    prev2_str = get_prev_date(prev_str)

    lines = []
    lines.append(f"\n{'='*60}")
    lines.append(f"T日 = {today_str}")
    lines.append("="*60)
    p1 = f"{prev_str[:4]}-{prev_str[4:6]}-{prev_str[6:]}"
    p2 = f"{prev2_str[:4]}-{prev2_str[4:6]}-{prev2_str[6:]}" if prev2_str else "None"
    lines.append(f"T-1 = {p1}  T-2 = {p2}")

    df1 = daily_lkp.get(prev_str)
    df2 = daily_lkp.get(prev2_str) if prev2_str else None
    if df1 is None or df2 is None:
        return "\n".join(lines) + "\n数据缺失"

    lines.append(f"\n【0】全市场（排除688/8开头）: {len(df1)} 只")

    common = df1.index.intersection(df2.index)
    pc1 = df1.loc[common, "pre_close"].astype(float)
    pc2 = df2.loc[common, "pre_close"].astype(float)
    c1 = df1.loc[common, "close"].astype(float)
    c2 = df2.loc[common, "close"].astype(float)
    hl1 = (pc1 * 1.10).round(2)
    hl2 = (pc2 * 1.10).round(2)
    up1 = (c1 - hl1).abs() <= LIMIT_TOL
    up2 = (c2 - hl2).abs() <= LIMIT_TOL
    first_boards = set(common[up1 & ~up2])
    lines.append(f"\n【1】首板宽集: {len(first_boards)} 只")
    if not first_boards:
        return "\n".join(lines)

    # IPO filter
    today_ts = pd.Timestamp(today_yyyymmdd)
    step2 = []
    for code in first_boards:
        ld = ipo_lkp.get(code, "")
        if len(ld) == 8 and (today_ts - pd.Timestamp(ld)).days < IPO_DAYS:
            continue
        step2.append(code)

    circ_s = ind_lkp.get(prev_str, pd.Series(dtype=float))
    circ = circ_s.reindex(step2).fillna(0.0)
    step2b = [c for c in step2 if CIRC_MIN <= circ.get(c, 0) <= CIRC_MAX]
    ipo_skipped = len(step2) - len(step2b)
    lines.append(f"  排除IPO={ipo_skipped}（无ST数据，流通市值过滤已含）")
    lines.append(f"  通过: {len(step2b)} 只")
    if not step2b:
        return "\n".join(lines)

    sub = df1.loc[step2b]
    amt = sub["amount"].astype(float)
    vol_s = sub["vol"].astype(float)
    cls = sub["close"].astype(float)
    avg_chg = np.where((vol_s > 0) & (cls > 0), amt / vol_s / cls * 1.1 - 1, 0.0)

    money_skip = int((amt < MONEY_MIN).sum())
    step3_mask = (amt >= MONEY_MIN) & (avg_chg >= 0.07)
    step3 = sub[step3_mask].index.tolist()
    avg_chg_skip = int((~step3_mask & (amt >= MONEY_MIN)).sum())
    lines.append(f"  排除money<6亿={money_skip}  avg_chg<7%={avg_chg_skip}")
    lines.append(f"  通过: {len(step3)} 只")
    if not step3:
        return "\n".join(lines)

    today_df = daily_lkp.get(today_yyyymmdd)
    step4 = []
    open_skip = 0
    for code in step3:
        if today_df is None or code not in today_df.index:
            open_skip += 1; continue
        row = today_df.loc[code]
        t_open = float(row["open"])
        pc = float(row["pre_close"])
        hl = round(pc * (1.20 if code.startswith("30") else 1.10), 2)
        if t_open <= 0 or pc <= 0:
            open_skip += 1; continue
        if t_open >= hl * 0.999:
            open_skip += 1; continue
        yclose = float(df1.loc[code, "close"]) if code in df1.index else 0
        if yclose <= 0:
            open_skip += 1; continue
        open_pct = t_open / yclose - 1
        if open_pct < 0 or open_pct > 0.095:
            open_skip += 1; continue
        step4.append((code, circ.get(code, 0), float(amt[code]), open_pct))

    lines.append(f"  排除开盘异常={open_skip}")
    lines.append(f"  通过: {len(step4)} 只")

    step4.sort(key=lambda x: -x[2])
    lines.append(f"\n最终候选（前10按成交额降序）:")
    lines.append(f"{'代码':<15s} {'流通市值(亿)':<12s} {'成交额(亿)':<12s} {'开盘涨幅':<10s}")
    lines.append("-" * 49)
    for s, circ_v, money, op in step4[:10]:
        lines.append(f"{s:<15s} {circ_v:<12.1f} {money/1e8:<12.1f} {op*100:<10.2f}%")
    lines.append(f"\nALL({len(step4)}): {','.join(s for s,_,_,_ in step4)}")
    return "\n".join(lines)


print("\n" + "="*60)
print("本地候选池诊断")
print("="*60)
for dt in CHECK_DATES:
    print(verify_one_day(dt))
print("\n诊断结束")
