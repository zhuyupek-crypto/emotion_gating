from jqdata import *
import pandas as pd

CHECKS = [
    ("300347.XSHE", "2024-03-18", 53.00),
    ("002611.XSHE", "2024-03-20", 8.81),
    ("002130.XSHE", "2024-03-25", 8.46),
    ("002130.XSHE", "2024-03-26", 8.46),
    ("000801.XSHE", "2024-03-21", 14.12),
    ("603688.XSHG", "2024-03-27", 92.98),
]

TIMES = ["11:24", "11:25", "11:26", "13:00", "13:01", "13:02", "14:49", "14:50", "14:51"]

def norm_time(x):
    return pd.to_datetime(x).strftime("%H:%M")

def fetch_day(code, day):
    df = get_price(
        code,
        start_date=day + " 09:30:00",
        end_date=day + " 15:00:00",
        frequency="1m",
        fields=["open", "high", "low", "close", "high_limit", "low_limit"],
        panel=False,
        skip_paused=False,
        fq=None,
    )
    if df is None or len(df) == 0:
        return pd.DataFrame()
    if "time" in df.columns:
        df = df.set_index("time")
    df = df.copy()
    df["hhmm"] = [norm_time(x) for x in df.index]
    return df

def probe_one(code, day, entry):
    df = fetch_day(code, day)
    print("\n=== %s %s entry=%.3f mid_thr=%.3f stop_thr=%.3f ===" %
          (code, day, entry, entry * 0.98, entry * 0.95))
    if df.empty:
        print("NO_DATA")
        return
    for t in TIMES:
        sub = df[df["hhmm"] == t]
        if sub.empty:
            print("%s MISSING" % t)
            continue
        r = sub.iloc[0]
        print("%s open=%.3f high=%.3f low=%.3f close=%.3f high_limit=%.3f low_limit=%.3f ret=%.5f" % (
            t, r["open"], r["high"], r["low"], r["close"],
            r["high_limit"], r["low_limit"], r["close"] / entry - 1
        ))
    m1 = df[(df["hhmm"] >= "11:25") & (df["close"] <= entry * 0.98)]
    if len(m1):
        r = m1.iloc[0]
        print("FIRST_CLOSE_LE_MID after1125: %s close=%.3f ret=%.5f" %
              (norm_time(m1.index[0]), r["close"], r["close"] / entry - 1))
    else:
        print("FIRST_CLOSE_LE_MID after1125: NONE")
    m2 = df[df["close"] >= df["high_limit"] * 0.999]
    if len(m2):
        r = m2.iloc[0]
        print("FIRST_AT_LIMIT: %s close=%.3f high_limit=%.3f" %
              (norm_time(m2.index[0]), r["close"], r["high_limit"]))
    else:
        print("FIRST_AT_LIMIT: NONE")

for code, day, entry in CHECKS:
    probe_one(code, day, entry)
