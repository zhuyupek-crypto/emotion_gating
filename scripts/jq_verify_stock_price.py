"""
聚宽单股验证 —— 价格差异诊断
"""
from jqdata import *
import pandas as pd

# 2024-02-29 (T-1)
# 验证 JQ 认为涨停、本地认为不涨停的股票
stock_jq = "600584.XSHG"
# 验证 JQ 不认为涨停、本地认为涨停的股票
stock_local = "002281.XSHE"

print("=== 单股验证 ===\n")

for s in [stock_jq, stock_local]:
    print(f"--- {s} ---")
    
    # 取不复权数据
    df = get_price(s, start_date="2024-02-26", end_date="2024-03-01",
                   frequency="daily", fields=["open", "close", "high", "low", "pre_close", "high_limit", "low_limit"],
                   skip_paused=True, fq=None, panel=False)
    
    if df is not None and not df.empty:
        for _, row in df.iterrows():
            dt = row["time"] if "time" in row else row.name
            c = row["close"]
            pc = row["pre_close"]
            hl = row["high_limit"]
            calc_hl = round(float(pc) * 1.10, 2) if pc > 0 else 0
            is_limit = abs(c - hl) <= 0.02 if hl > 0 else False
            print(f"  {dt}: pre_close={pc:.2f}, close={c:.2f}, high_limit={hl:.2f}, calc_hl={calc_hl:.2f}, is_limit={is_limit}")
    
    print()
