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


def _print_security(day, stock):
    prev_trade = get_trade_days(end_date=pd.to_datetime(day) - pd.Timedelta(days=1), count=1)[0]
    prev_date = pd.Timestamp(prev_trade).strftime("%Y-%m-%d")
    start = day + " 09:15:00"
    end = day + " 09:25:00"

    print("\n" + "=" * 90)
    print("DAY=%s STOCK=%s PREV=%s" % (day, stock, prev_date))

    secs = get_all_securities(["stock"], date=prev_date)
    sec = secs.loc[[stock]] if stock in secs.index else pd.DataFrame()
    print("\n=== security ===")
    print(sec.to_string())

    df = get_price(
        [stock],
        count=4,
        end_date=prev_date,
        frequency="daily",
        fields=["open", "close", "high", "high_limit", "low_limit", "money", "volume"],
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
        fields=["open", "close", "high", "high_limit", "low_limit", "money", "volume"],
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

    avg_raw = money1 / volume1 / close1 if volume1 else 0
    inc4 = (close1 - close4) / close4 if close4 else 0
    y_limit = abs(close1 - high_limit1) <= 0.02
    y_ever_limit = abs(high1 - high_limit1) <= 0.02
    prev2_limit = abs(close2 - high_limit2) <= 0.02
    prev2_ever_limit = abs(high2 - high_limit2) <= 0.02
    prev3_ever_limit = abs(high3 - high_limit3) <= 0.02
    avg_inc_y2 = avg_raw * 1.1 - 1
    avg_inc_rzq = avg_raw - 1
    oc_ratio = (close1 - open1) / open1 if open1 else 0
    y_bomb = y_ever_limit and (close1 < high_limit1 * 0.999)

    print("\n=== candidate formulas ===")
    print(
        dict(
            avg_inc_y2=avg_inc_y2,
            avg_inc_rzq=avg_inc_rzq,
            inc4=inc4,
            y_limit=y_limit,
            y_bomb=y_bomb,
            prev2_limit=prev2_limit,
            prev2_ever_limit=prev2_ever_limit,
            prev3_ever_limit=prev3_ever_limit,
            oc_ratio=oc_ratio,
            mask_y2=(
                y_limit
                and (not prev2_ever_limit)
                and (not prev3_ever_limit)
                and avg_inc_y2 >= 0.07
                and money1 >= 5e8
                and money1 <= 20e8
                and inc4 <= 0.25
            ),
            mask_rzq=(
                y_bomb
                and (not prev2_limit)
                and avg_inc_rzq >= -0.04
                and money1 >= 3e8
                and money1 <= 19e8
                and oc_ratio >= -0.05
                and inc4 <= 0.18
            ),
        )
    )

    left_ok, left_detail = _left_pressure_ok(stock, prev_date)
    print("\n=== left pressure ===")
    print(left_ok, left_detail)

    au = get_call_auction([stock], start_date=start, end_date=end, fields=["time", "volume", "current"])
    print("\n=== get_call_auction(time, volume, current) ===")
    print(au.get(stock, pd.DataFrame()).to_string(index=False))

    au_full = get_call_auction(stock, start_date=day, end_date=day)
    print("\n=== get_call_auction(full depth) ===")
    print(au_full.to_string(index=False))

    try:
        row = au_full.iloc[0]
        buy_m = sum(row.get("b%d_p" % i, 0) * row.get("b%d_v" % i, 0) for i in range(1, 6))
        sell_m = sum(row.get("a%d_p" % i, 0) * row.get("a%d_v" % i, 0) for i in range(1, 6))
        print("\n=== auction depth imbalance ===")
        print(
            dict(
                buy_money=buy_m,
                sell_money=sell_m,
                net_ratio=((buy_m - sell_m) / sell_m) if sell_m else None,
            )
        )
    except Exception as exc:
        print("\n=== auction depth imbalance ===")
        print("ERR %r" % exc)

    val = get_valuation(
        [stock],
        start_date=prev_date,
        end_date=prev_date,
        fields=["market_cap", "circulating_market_cap", "turnover_ratio"],
    )
    print("\n=== valuation ===")
    print(val.to_string(index=False))

    price = get_price(
        [stock],
        count=1,
        end_date=day,
        frequency="daily",
        fields=["open", "close", "high_limit", "low_limit", "paused"],
        panel=False,
        fill_paused=False,
    )
    print("\n=== buy-day daily snapshot ===")
    print(price.to_string(index=False))

    print("\n=== current_data ===")
    try:
        cd = get_current_data()
        d = cd[stock]
        print(
            dict(
                paused=getattr(d, "paused", None),
                day_open=getattr(d, "day_open", None),
                last_price=getattr(d, "last_price", None),
                high_limit=getattr(d, "high_limit", None),
                low_limit=getattr(d, "low_limit", None),
                name=getattr(d, "name", None),
            )
        )
    except Exception as exc:
        print("UNAVAILABLE %r" % exc)


def probe():
    _print_security("2025-11-07", "002170.XSHE")
    _print_security("2025-11-10", "002544.XSHE")
    _print_security("2025-11-10", "002513.XSHE")


probe()



