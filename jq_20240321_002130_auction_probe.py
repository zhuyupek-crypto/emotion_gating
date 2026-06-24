from jqdata import *
import pandas as pd


def _left_pressure_ok(stock, prev_date):
    try:
        df = get_price(
            [stock],
            count=101,
            end_date=prev_date,
            frequency="daily",
            fields=["high", "volume"],
            panel=False,
            fill_paused=False,
        )
    except Exception as exc:
        return False, "ERR %r" % exc
    if df is None or df.empty:
        return False, "EMPTY"
    if "time" not in df.columns:
        df = df.reset_index()
    sub = df[df["code"] == stock].sort_values("time").dropna(subset=["high", "volume"])
    if len(sub) < 20:
        return False, "LEN %d" % len(sub)
    highs = list(sub["high"].iloc[-101:])
    vols_all = list(sub["volume"].iloc[-101:])
    prev_high = highs[-1]
    zyts_0 = 100
    for offset, high in enumerate(reversed(highs[:-2]), 2):
        if high >= prev_high:
            zyts_0 = offset - 1
            break
    zyts = zyts_0 + 5
    vols = vols_all[-zyts:]
    ok = bool(len(vols) >= 2 and vols[-1] > max(vols[:-1]) * 0.9)
    return ok, "zyts=%s last_vol=%s max_prev=%s" % (
        zyts,
        vols[-1] if vols else None,
        max(vols[:-1]) if len(vols) >= 2 else None,
    )


def probe():
    day = "2024-03-21"
    prev_date = "2024-03-20"
    stock = "002130.XSHE"
    start = day + " 09:15:00"
    end = day + " 09:25:00"

    secs = get_all_securities(["stock"], date=prev_date)
    sec = secs.loc[[stock]] if stock in secs.index else pd.DataFrame()
    print("=== security ===")
    print(sec.to_string())

    df = get_price(
        [stock],
        count=4,
        end_date=prev_date,
        frequency="daily",
        fields=["open", "close", "high", "high_limit", "money", "volume"],
        panel=False,
        fill_paused=False,
    )
    print("\n=== prev 4d daily ===")
    print(df.to_string(index=False))

    wide = get_price(
        [stock],
        count=4,
        end_date=prev_date,
        frequency="daily",
        fields=["open", "close", "high", "high_limit", "money", "volume"],
        panel=True,
        fill_paused=False,
    )
    open1 = wide["open"].iloc[-1][stock]
    close1 = wide["close"].iloc[-1][stock]
    high1 = wide["high"].iloc[-1][stock]
    high_limit1 = wide["high_limit"].iloc[-1][stock]
    money1 = wide["money"].iloc[-1][stock]
    volume1 = wide["volume"].iloc[-1][stock]
    close2 = wide["close"].iloc[-2][stock]
    high2 = wide["high"].iloc[-2][stock]
    high_limit2 = wide["high_limit"].iloc[-2][stock]
    high3 = wide["high"].iloc[-3][stock]
    high_limit3 = wide["high_limit"].iloc[-3][stock]
    close4 = wide["close"].iloc[-4][stock]

    avg_raw = money1 / volume1 / close1
    inc4 = (close1 - close4) / close4
    y_limit = abs(close1 - high_limit1) <= 0.02
    prev2_ever_limit = abs(high2 - high_limit2) <= 0.02
    prev3_ever_limit = abs(high3 - high_limit3) <= 0.02
    avg_inc_y2 = avg_raw * 1.1 - 1
    mask_y2 = (
        y_limit
        and (not prev2_ever_limit)
        and (not prev3_ever_limit)
        and avg_inc_y2 >= 0.07
        and money1 >= 5e8
        and money1 <= 20e8
        and inc4 <= 0.25
    )
    print("\n=== y2 formula ===")
    print(
        dict(
            open1=open1,
            close1=close1,
            high1=high1,
            high_limit1=high_limit1,
            money1=money1,
            volume1=volume1,
            close4=close4,
            avg_inc_y2=avg_inc_y2,
            inc4=inc4,
            y_limit=y_limit,
            prev2_ever_limit=prev2_ever_limit,
            prev3_ever_limit=prev3_ever_limit,
            mask_y2=mask_y2,
        )
    )

    left_ok, left_detail = _left_pressure_ok(stock, prev_date)
    print("\n=== left pressure ===")
    print(left_ok, left_detail)

    au = get_call_auction([stock], start_date=start, end_date=end, fields=["time", "volume", "current"])
    print("\n=== auction ===")
    print(au.get(stock, pd.DataFrame()).to_string(index=False))

    val = get_valuation(
        [stock],
        start_date=prev_date,
        end_date=prev_date,
        fields=["market_cap", "circulating_market_cap"],
    )
    print("\n=== valuation ===")
    print(val.to_string(index=False))

    price = get_price(
        [stock],
        count=1,
        end_date=day,
        frequency="daily",
        fields=["open", "high_limit", "low_limit", "paused"],
        panel=False,
        fill_paused=False,
    )
    print("\n=== buy-day daily snapshot ===")
    print(price.to_string(index=False))


probe()
