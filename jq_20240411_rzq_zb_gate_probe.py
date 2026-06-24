from jqdata import *
import json
import pandas as pd


BUY_DAY = "2024-04-11"
PREV_DAY = "2024-04-10"


def calc_money(row, prefix):
    total = 0.0
    if row is None:
        return None
    for i in range(1, 6):
        total += float(row.get("%s%d_p" % (prefix, i), 0) or 0) * float(row.get("%s%d_v" % (prefix, i), 0) or 0)
    return total


def as_float(x):
    try:
        if pd.isnull(x):
            return None
        return float(x)
    except Exception:
        return None


def clean_rows(rows):
    out = []
    for row in rows:
        clean = {}
        for k, v in row.items():
            if isinstance(v, (bool, str)) or v is None:
                clean[k] = v
            elif isinstance(v, int):
                clean[k] = int(v)
            else:
                clean[k] = as_float(v)
        out.append(clean)
    return out


def build_rzq_prepare():
    bb = get_billboard_list(stock_list=None, end_date=PREV_DAY, count=1)
    pool = bb["code"].unique().tolist() if bb is not None and not bb.empty else []

    secs = get_all_securities(["stock"], date=PREV_DAY)
    pool2 = []
    dropped = []
    for s in pool:
        reason = []
        if not isinstance(s, str) or "." not in s:
            reason.append("bad_code")
        elif not (s.startswith("60") or s.startswith("00")):
            reason.append("not_main_board_prefix")
        elif s.startswith("30") or s.startswith("68") or s.startswith("8") or s.startswith("4"):
            reason.append("excluded_market")
        elif s not in secs.index:
            reason.append("missing_security")
        else:
            name = secs.loc[s, "display_name"]
            if "ST" in name or "st" in name or "*" in name or "退" in name:
                reason.append("st_name=%s" % name)
            if (pd.Timestamp(BUY_DAY).date() - secs.loc[s, "start_date"]).days < 375:
                reason.append("ipo_lt_375")
        if reason:
            dropped.append({"code": s, "reason": "|".join(reason)})
        else:
            pool2.append(s)

    df_hl = get_price(
        pool2,
        end_date=PREV_DAY,
        frequency="daily",
        fields=["close", "high", "high_limit"],
        count=1,
        panel=False,
        fill_paused=False,
    )
    if df_hl is None or df_hl.empty:
        return [], {}, dropped
    df_hl = df_hl.dropna().copy()
    df_hl = df_hl[(df_hl["high"] == df_hl["high_limit"]) & (df_hl["close"] != df_hl["high_limit"])].copy()
    pool3 = df_hl["code"].tolist()

    df_t = get_price(
        pool3,
        end_date=PREV_DAY,
        frequency="1d",
        fields=["close", "low", "volume"],
        count=11,
        panel=False,
    )
    if df_t is None or df_t.empty:
        return [], {}, dropped
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
    latest = df_t[df_t["time"] == pd.Timestamp(PREV_DAY)]
    valid_codes = latest[cond.loc[latest.index]]["code"].unique().tolist()
    yclose = df_hl[df_hl["code"].isin(valid_codes)].set_index("code")["close"].to_dict()
    return valid_codes, yclose, dropped


def build_zb_prepare():
    secs = get_all_securities(["stock"], date=PREV_DAY)
    all_codes = []
    for s in secs.index:
        if not (s.startswith("60") or s.startswith("00")):
            continue
        if s.startswith("30") or s.startswith("68") or s.startswith("8") or s.startswith("4"):
            continue
        name = secs.loc[s, "display_name"]
        if "ST" in name or "st" in name or "*" in name or "退" in name:
            continue
        if (pd.Timestamp(BUY_DAY).date() - secs.loc[s, "start_date"]).days < 375:
            continue
        all_codes.append(s)

    df_hl = get_price(
        all_codes,
        end_date=PREV_DAY,
        frequency="daily",
        fields=["close", "high", "high_limit"],
        count=1,
        panel=False,
        fill_paused=False,
    )
    if df_hl is None or df_hl.empty:
        return [], {}
    df_hl = df_hl.dropna().copy()
    df_hl = df_hl[(df_hl["high"] == df_hl["high_limit"]) & (df_hl["close"] < df_hl["high_limit"])].copy()
    bomb_codes = df_hl["code"].tolist()

    q = query(valuation.code, income.operating_revenue).filter(
        valuation.code.in_(bomb_codes),
        income.operating_revenue > 1e8,
    )
    df_gjt = get_fundamentals(q, date=PREV_DAY)
    gjt_codes = list(df_gjt["code"]) if df_gjt is not None and not df_gjt.empty else []

    df_t = get_price(
        gjt_codes,
        end_date=PREV_DAY,
        frequency="1d",
        fields=["close", "low", "volume"],
        count=3,
        panel=False,
    )
    if df_t is None or df_t.empty:
        return [], {}
    if "time" not in df_t.columns:
        df_t = df_t.reset_index()
    grouped = df_t.groupby("code")
    ma3 = grouped["close"].transform(lambda x: x.rolling(3).mean())
    prev_low = grouped["low"].shift(1)
    prev_vol = grouped["volume"].shift(1)
    cond = (
        (df_t["close"] > prev_low)
        & (df_t["close"] > ma3)
        & (df_t["volume"] > prev_vol)
        & (df_t["volume"] < 15 * prev_vol)
        & (df_t["close"] > 1)
    )
    latest = df_t[df_t["time"] == pd.Timestamp(PREV_DAY)]
    valid_codes = latest[cond.loc[latest.index]]["code"].unique().tolist()

    q_mv = query(valuation.code, valuation.circulating_market_cap).filter(
        valuation.code.in_(valid_codes),
        valuation.circulating_market_cap > 10,
        valuation.circulating_market_cap < 2000,
    )
    df_mv = get_fundamentals(q_mv, date=PREV_DAY)
    final_codes = list(df_mv["code"]) if df_mv is not None and not df_mv.empty else []
    yclose = df_hl[df_hl["code"].isin(final_codes)].set_index("code")["close"].to_dict()
    return final_codes, yclose


def build_buy_gate(name, codes, yclose_map, lower, upper):
    if not codes:
        return []
    snap = get_price(
        codes,
        end_date=BUY_DAY,
        frequency="daily",
        fields=["open", "close", "high_limit", "low_limit", "paused"],
        count=1,
        panel=False,
        fill_paused=False,
    )
    if snap is None or snap.empty:
        return []
    au = get_call_auction(codes, start_date=BUY_DAY, end_date=BUY_DAY)
    val = get_valuation(
        codes,
        start_date=PREV_DAY,
        end_date=PREV_DAY,
        fields=["turnover_ratio", "market_cap", "circulating_market_cap"],
    )
    val_map = val.set_index("code").to_dict("index") if val is not None and not val.empty else {}
    au_map = {}
    if au is not None and not au.empty:
        for _, row in au.iterrows():
            au_map[row["code"]] = row

    rows = []
    for _, row in snap.iterrows():
        code = row["code"]
        yc = as_float(yclose_map.get(code))
        op = as_float(row.get("open"))
        ratio = op / yc if yc and op else None
        last_price = op
        high_limit = as_float(row.get("high_limit"))
        low_limit = as_float(row.get("low_limit"))
        au_row = au_map.get(code)
        buy_m = calc_money(au_row, "b")
        sell_m = calc_money(au_row, "a")
        turn = (val_map.get(code) or {}).get("turnover_ratio")
        market_cap = (val_map.get(code) or {}).get("market_cap")
        circ_cap = (val_map.get(code) or {}).get("circulating_market_cap")
        auction_ok = buy_m is not None and sell_m is not None and sell_m > 0 and (buy_m - sell_m) / sell_m > 0
        score = (turn or 0) * (ratio or 0) * ((buy_m / sell_m) if buy_m and sell_m else 0)
        rows.append(
            {
                "code": code,
                "leg": name,
                "yclose": yc,
                "open": op,
                "ratio": ratio,
                "paused": bool(row.get("paused")),
                "last_price": last_price,
                "high_limit": high_limit,
                "low_limit": low_limit,
                "ratio_ok": ratio is not None and lower < ratio < upper,
                "not_limit": (
                    last_price is not None
                    and high_limit is not None
                    and low_limit is not None
                    and not (last_price >= high_limit * 0.999 or last_price <= low_limit * 1.001)
                ),
                "auction_rows": 0 if au_row is None else 1,
                "buy_m": buy_m,
                "sell_m": sell_m,
                "auction_ok": auction_ok,
                "turnover_ratio": turn,
                "market_cap": market_cap,
                "circulating_market_cap": circ_cap,
                "score": score,
            }
        )
    rows = sorted(rows, key=lambda x: (-float(x.get("score") or 0), x["code"]))
    return clean_rows(rows)


def probe():
    rzq_codes, rzq_yclose, rzq_dropped = build_rzq_prepare()
    zb_codes, zb_yclose = build_zb_prepare()
    rzq_gate = build_buy_gate("rzq", rzq_codes, rzq_yclose, 0.96, 1.01)
    zb_gate = build_buy_gate("zb", zb_codes, zb_yclose, 0.97, 1.075)
    out = {
        "buy_day": BUY_DAY,
        "prev_day": PREV_DAY,
        "rzq_prepare_valid": rzq_codes,
        "rzq_security_filter_dropped": rzq_dropped,
        "zb_prepare_valid": zb_codes,
        "rzq_gate": rzq_gate,
        "zb_gate": zb_gate,
        "rzq_pass": [r for r in rzq_gate if r["ratio_ok"] and r["not_limit"] and r["auction_ok"]],
        "zb_pass": [r for r in zb_gate if r["ratio_ok"] and r["not_limit"] and r["auction_ok"]],
    }
    print(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True))


probe()