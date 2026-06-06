"""
验证 300347 在 2024-03-14/15 的涨停状态
"""
from jqdata import *
import pandas as pd

code = "300347.XSHE"
for ds in ["2024-03-13", "2024-03-14", "2024-03-15"]:
    df = get_price(code, end_date=ds, count=1, frequency="daily",
                   fields=["open","close","pre_close","high_limit","money","volume"],
                   panel=False, fill_paused=False, skip_paused=False)
    if not df.empty:
        r = df.iloc[0]
        hl = r["high_limit"]
        c = r["close"]
        print(f"{ds}: pre_close={r['pre_close']:.2f}, open={r['open']:.2f}, close={c:.2f}, high_limit={hl:.2f}, is_limit={abs(c-hl)<=0.02 if hl > 0 else False}, money={r['money']/1e8:.1f}亿")
