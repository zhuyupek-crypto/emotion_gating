"""
中证1000指数数据 + 市场模式判断验证脚本
=========================================
对比本地 idx_000852.parquet 与聚宽官方数据
并输出 daily_raw_mode 用于验证模式判断差异
"""
from jqdata import *
import pandas as pd
import numpy as np
from datetime import datetime, date

IDX_CODE = "000852.XSHG"
START = "2023-11-01"
END = "2024-02-29"

print("=== 中证1000指数对比验证 ===")

# 取聚宽指数数据（不复权）
df = get_price(IDX_CODE, start_date=START, end_date=END,
               frequency="daily", fields=["close"],
               fq=None, panel=False, skip_paused=False)

if df is None or df.empty:
    print("数据获取失败")
else:
    # JQ的get_price: index为日期
    df = df.copy()
    df["date"] = df.index.strftime("%Y%m%d")
    df = df.reset_index(drop=True)
    df = df.sort_values("date").reset_index(drop=True)
    
    print(f"\n数据量: {len(df)} 条")
    print(f"日期范围: {df['date'].iloc[0]} ~ {df['date'].iloc[-1]}")
    
    # 输出 2024-01 全月数据
    print("\n=== 2024年1月 中证1000收盘价 ===")
    jan = df[(df["date"] >= "20240101") & (df["date"] <= "20240131")]
    
    # 构建 idx_map 并计算每日 raw_mode
    idx_map = dict(zip(df["date"], df["close"].astype(float)))
    all_dates = sorted(idx_map.keys())
    
    def compute_raw_mode(t_idx):
        hist = [idx_map[all_dates[i]]
                for i in range(max(0, t_idx - 64), t_idx + 1)
                if all_dates[i] in idx_map]
        if len(hist) < 20:
            return "bear"
        arr = np.array(hist, dtype=float)
        high_20 = arr[-20:].max()
        if high_20 > 0 and (arr[-1] - high_20) / high_20 <= -0.12:
            return "bear"
        if len(arr) < 60:
            return "bear"
        ma20 = arr[-20:].mean()
        ma60 = arr[-60:].mean()
        price = arr[-1]
        days_above = int((arr[-30:] > ma60).sum())
        if price <= ma60 and ma20 <= ma60:
            return "bear"
        if price <= ma60 and ma20 > ma60:
            return "cautious" if False else "bear"
        if days_above >= len(arr[-30:]) * 0.66:
            return "bull"
        return "cautious"
    
    print(f"{'日期':<12s} {'收盘价':<10s} {'MA20':<10s} {'MA60':<10s} {'20d回撤':<10s} {'Mode':<10s}")
    print("-" * 62)
    
    for _, row in jan.iterrows():
        d = row["date"]
        c = float(row["close"])
        t_idx = all_dates.index(d) if d in all_dates else -1
        if t_idx >= 0:
            mode = compute_raw_mode(t_idx)
            # Also get MA values
            hist = [idx_map[all_dates[i]] for i in range(max(0, t_idx - 64), t_idx + 1) if all_dates[i] in idx_map]
            arr = np.array(hist, dtype=float)
            ma20 = arr[-20:].mean() if len(arr) >= 20 else 0
            ma60 = arr[-60:].mean() if len(arr) >= 60 else 0
            dd20 = (arr[-1] - arr[-20:].max()) / arr[-20:].max() if len(arr) >= 20 else 0
            print(f"{d:<12s} {c:<10.2f} {ma20:<10.2f} {ma60:<10.2f} {dd20*100:<10.2f}% {mode:<10s}")
    
    # 输出完整数据供本地对比
    print("\n=== 完整数据（复制到本地对比） ===")
    print("date,close_jq")
    for _, row in jan.iterrows():
        print(f"{row['date']},{row['close']:.2f}")

print("\n验证结束")
