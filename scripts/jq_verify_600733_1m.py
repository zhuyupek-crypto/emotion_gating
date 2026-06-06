"""
验证 600733.XSHG 2024-03-12 分钟数据
对比局宽 vs 本地 parquet 的分钟 OHLC
"""
from jqdata import *
import pandas as pd
import numpy as np

code = "600733.XSHG"
date = "2024-03-12"

print(f"=== {code} {date} 分钟数据 ===\n")

# 取分钟数据
df = get_price(code, start_date=date, end_date=date,
               frequency="1m", fields=["open", "high", "low", "close", "volume"],
               skip_paused=False, panel=False, fill_paused=False)

if df is None or df.empty:
    print("无分钟数据")
else:
    print(f"总条数: {len(df)}")
    print(f"日期列: {list(df.columns)}")
    
    # 统一处理
    if "time" in df.columns:
        df = df.rename(columns={"time": "datetime"})
    
    # 计算日OHLC
    open_p = float(df["open"].iloc[0])
    high_p = float(df["high"].max())
    low_p = float(df["low"].min())
    close_p = float(df["close"].iloc[-1])
    
    print(f"\n日OHLC: open={open_p:.2f}, high={high_p:.2f}, low={low_p:.2f}, close={close_p:.2f}")
    print(f"\n本地 parquet OHLC: open=7.08, high=7.29, low=6.65, close=7.03")
    print(f"\n差异分析:")
    print(f"  open: JQ={open_p:.2f}, local=7.08, diff={abs(open_p-7.08):.4f}")
    print(f"  high: JQ={high_p:.2f}, local=7.29, diff={abs(high_p-7.29):.4f}")
    print(f"  low:  JQ={low_p:.2f}, local=6.65, diff={abs(low_p-6.65):.4f}")
    print(f"  close:JQ={close_p:.2f}, local=7.03, diff={abs(close_p-7.03):.4f}")
    
    # 检查是否触发 -5% 止损
    entry = 7.08  # JQ 买入价
    stop = entry * 0.95
    print(f"\n止损验证:")
    print(f"  JQ买入价: {entry}")
    print(f"  -5%止损价: {stop:.2f}")
    print(f"  JQ最低价: {low_p}")
    print(f"  JQ触发止损: {low_p <= stop}")
    print(f"  本地触发止损: True (本地 low=6.65 <= {stop:.2f})")
    
    # 逐分钟检查前30分钟
    print(f"\n前30分钟逐笔:")
    df_head = df.head(30)
    for _, row in df_head.iterrows():
        t = row.get("datetime", row.get("time", ""))
        o = row["open"]
        h = row["high"]
        l = row["low"]
        c = row["close"]
        hit = "*** STOP ***" if l <= stop else ""
        print(f"  {t}: O={o:.2f} H={h:.2f} L={l:.2f} C={c:.2f} {hit}")

print("\n验证结束")
