"""
验证 600733.XSHG 日线数据 2024-03-12
比较 JQ 日线 OHLC 与本地 parquet
"""
from jqdata import *
import pandas as pd

code = "600733.XSHG"

print(f"=== {code} 日线数据 ===\n")

# 取 3 月 10-14 日数据
df = get_price(code, start_date="2024-03-11", end_date="2024-03-15",
               frequency="daily", fields=["open","high","low","close","volume","money"],
               fq=None, panel=False, skip_paused=False)

if df is not None and not df.empty:
    if "time" in df.columns:
        df = df.rename(columns={"time": "date"})
    df["date"] = df.index.strftime("%Y%m%d")
    df = df.reset_index(drop=True)
    
    print(f"{'date':<10s} {'open':<8s} {'high':<8s} {'low':<8s} {'close':<8s} {'vol':<10s}")
    print("-" * 50)
    for _, row in df.iterrows():
        d = row["date"]
        o = row["open"]
        h = row["high"]
        l = row["low"]
        c = row["close"]
        v = row["volume"]
        print(f"{d:<10s} {o:<8.2f} {h:<8.2f} {l:<8.2f} {c:<8.2f} {v:<10.0f}")
else:
    print("无数据")

print("\n本地 parquet 数据:")
print("20240312: open=7.08, high=7.29, low=6.65, close=7.03, vol=139949075")
print("20240313: open=7.05, high=7.19, low=6.87, close=7.15")
print("20240314: open=7.16, high=7.80, low=7.10, close=7.72")
print("\n验证结束")
