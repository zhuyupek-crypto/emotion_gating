import importlib
import os
import sys

import pandas as pd


ROOT = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.join(ROOT, "rebuild_from_archive")
sys.path.insert(0, WORK)
sys.path.insert(1, ROOT)
sys.path.insert(2, r"D:\work space\hdata")
sys.modules["jqdata"] = importlib.import_module("jqdata_compat")

from engine.data_api import DataAPI


api = DataAPI()
code = "002192.XSHE"
prev = pd.Timestamp("2020-07-15")

bb = api.get_billboard_list(stock_list=None, end_date=prev, count=1)
print("billboard rows", len(bb), "contains", code in set(bb.get("code", [])))
if not bb.empty:
    print(bb[bb["code"] == code].to_string(index=False))

secs = api.get_all_securities(["stock"], date=prev)
print("in securities", code in secs.index)
if code in secs.index:
    print(secs.loc[[code]].to_string())

df_hl = api.get_price(
    [code],
    end_date=prev,
    frequency="daily",
    fields=["close", "high", "high_limit"],
    count=1,
    panel=False,
    fill_paused=False,
)
print("hl")
print(df_hl.to_string(index=False))

df_t = api.get_price(
    [code],
    end_date=prev,
    frequency="1d",
    fields=["close", "low", "volume"],
    count=11,
    panel=False,
)
print("tail")
print(df_t.tail(12).to_string(index=False))
if "time" not in df_t.columns:
    df_t = df_t.reset_index()
g = df_t.groupby("code")
ma10 = g["close"].transform(lambda x: x.rolling(10).mean())
prev_low = g["low"].shift(1)
prev_vol = g["volume"].shift(1)
cond = (
    (df_t["close"] > prev_low)
    & (df_t["close"] > ma10)
    & (df_t["volume"] > prev_vol)
    & (df_t["volume"] < 10 * prev_vol)
    & (df_t["close"] > 1)
)
latest = df_t[df_t["time"] == prev]
print("latest")
print(latest.assign(ma10=ma10.loc[latest.index], prev_low=prev_low.loc[latest.index], prev_vol=prev_vol.loc[latest.index], cond=cond.loc[latest.index]).to_string(index=False))
