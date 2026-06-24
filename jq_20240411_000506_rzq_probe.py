from jqdata import *
import pandas as pd


def probe():
    stock = "000506.XSHE"
    buy_day = "2024-04-11"
    prev_day = "2024-04-10"

    print("=== billboard ===")
    try:
        bb = get_billboard_list(stock_list=None, end_date=prev_day, count=1)
        print("rows", 0 if bb is None else len(bb))
        if bb is not None and not bb.empty:
            print(bb[bb["code"] == stock].to_string(index=False))
            print("contains", stock in set(bb["code"].astype(str)))
    except Exception as exc:
        print("ERR", repr(exc))

    print("\n=== security ===")
    secs = get_all_securities(["stock"], date=prev_day)
    print(secs.loc[[stock]].to_string() if stock in secs.index else "missing")

    print("\n=== prev daily hit/bomb ===")
    df_hl = get_price(
        [stock],
        end_date=prev_day,
        frequency="daily",
        fields=["close", "high", "high_limit"],
        count=1,
        panel=False,
        fill_paused=False,
    )
    print(df_hl.to_string(index=False))
    if df_hl is not None and not df_hl.empty:
        r = df_hl.iloc[-1]
        print(
            dict(
                high_eq_limit=bool(r["high"] == r["high_limit"]),
                close_ne_limit=bool(r["close"] != r["high_limit"]),
            )
        )

    print("\n=== ma10 volume condition ===")
    df_t = get_price(
        [stock],
        end_date=prev_day,
        frequency="1d",
        fields=["close", "low", "volume"],
        count=11,
        panel=False,
    )
    print(df_t.to_string(index=False))
    if df_t is not None and not df_t.empty:
        if "time" not in df_t.columns:
            df_t = df_t.reset_index()
        grouped = df_t.groupby("code")
        ma10 = grouped["close"].transform(lambda x: x.rolling(10).mean())
        prev_low = grouped["low"].shift(1)
        prev_vol = grouped["volume"].shift(1)
        cond = (
            (df_t["close"] > prev_low)
            & (df_t["close"] > ma10)
            & (df_t["volume"] > prev_vol)
            & (df_t["volume"] < 10 * prev_vol)
            & (df_t["close"] > 1)
        )
        out = df_t.copy()
        out["ma10"] = ma10
        out["prev_low"] = prev_low
        out["prev_vol"] = prev_vol
        out["cond"] = cond
        print("\n--- condition table ---")
        print(out.to_string(index=False))

    print("\n=== buy day snapshot ===")
    snap = get_price(
        [stock],
        count=1,
        end_date=buy_day,
        frequency="daily",
        fields=["open", "close", "high_limit", "low_limit", "paused"],
        panel=False,
        fill_paused=False,
    )
    print(snap.to_string(index=False))


probe()
