import importlib
import json
import os
import sys

import pandas as pd


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORK = os.path.join(ROOT, "rebuild_from_archive")
HDATA_SCRIPTS = r"D:\work space\hdata\scripts"

sys.path.insert(0, WORK)
sys.path.insert(1, HDATA_SCRIPTS)
sys.path.insert(2, r"D:\work space\hdata")
sys.path.insert(3, ROOT)
sys.modules["jqdata"] = importlib.import_module("jqdata_compat")

from engine.data_api import DataAPI
from project_compat import EmotionGateJQCompat


BUY_DAY = pd.Timestamp("2024-04-11")
PREV_DAY = pd.Timestamp("2024-04-10")


def calc_money(row, prefix):
    total = 0.0
    for i in range(1, 6):
        p = float(row.get(f"{prefix}{i}_p", 0) or 0)
        v = float(row.get(f"{prefix}{i}_v", 0) or 0)
        total += p * v
    return total


def safe_float(x):
    try:
        return float(x)
    except Exception:
        return None


def build_rzq_prepare(api):
    bb = api.get_billboard_list(stock_list=None, end_date=PREV_DAY, count=1)
    pool = bb["code"].unique().tolist() if bb is not None and not bb.empty else []

    secs = api.get_all_securities(["stock"], date=PREV_DAY)
    pool2 = []
    for s in pool:
        if not isinstance(s, str) or "." not in s:
            continue
        if not (s.startswith("60") or s.startswith("00")):
            continue
        if s.startswith("30") or s.startswith("68") or s.startswith("8") or s.startswith("4"):
            continue
        if s in secs.index:
            name = secs.loc[s, "display_name"]
            if "ST" in name or "st" in name or "*" in name or "退" in name:
                continue
            if (BUY_DAY.date() - secs.loc[s, "start_date"]).days < 375:
                continue
        pool2.append(s)

    df_hl = api.get_price(
        pool2,
        end_date=PREV_DAY,
        frequency="daily",
        fields=["close", "high", "high_limit"],
        count=1,
        panel=False,
        fill_paused=False,
    )
    df_hl = pd.DataFrame() if df_hl is None else df_hl.dropna().copy()
    if not df_hl.empty:
        df_hl = df_hl[(df_hl["high"] == df_hl["high_limit"]) & (df_hl["close"] != df_hl["high_limit"])].copy()
    pool3 = df_hl["code"].tolist() if not df_hl.empty else []

    df_t = api.get_price(
        pool3,
        end_date=PREV_DAY,
        frequency="1d",
        fields=["close", "low", "volume"],
        count=11,
        panel=False,
    )
    df_t = pd.DataFrame() if df_t is None else df_t.copy()
    if not df_t.empty and "time" not in df_t.columns:
        df_t = df_t.reset_index()
    valid_codes = []
    if not df_t.empty:
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
        latest = df_t[df_t["time"] == PREV_DAY]
        valid_codes = latest[cond.loc[latest.index]]["code"].unique().tolist()

    return {
        "billboard_rows": bb,
        "secs": secs,
        "pool": pool,
        "pool2": pool2,
        "df_hl": df_hl,
        "df_t": df_t,
        "valid_codes": valid_codes,
        "yclose_map": df_hl[df_hl["code"].isin(valid_codes)].set_index("code")["close"].to_dict() if not df_hl.empty else {},
    }


def build_zb_prepare(api):
    secs = api.get_all_securities(["stock"], date=PREV_DAY)
    all_codes = []
    for s in secs.index:
        if not (s.startswith("60") or s.startswith("00")):
            continue
        if s.startswith("30") or s.startswith("68") or s.startswith("8") or s.startswith("4"):
            continue
        name = secs.loc[s, "display_name"]
        if "ST" in name or "st" in name or "*" in name or "退" in name:
            continue
        if (BUY_DAY.date() - secs.loc[s, "start_date"]).days < 375:
            continue
        all_codes.append(s)

    df_hl = api.get_price(
        all_codes,
        end_date=PREV_DAY,
        frequency="daily",
        fields=["close", "high", "high_limit"],
        count=1,
        panel=False,
        fill_paused=False,
    )
    df_hl = pd.DataFrame() if df_hl is None else df_hl.dropna().copy()
    if not df_hl.empty:
        df_hl = df_hl[(df_hl["high"] == df_hl["high_limit"]) & (df_hl["close"] < df_hl["high_limit"])].copy()
    bomb_codes = df_hl["code"].tolist() if not df_hl.empty else []

    df_gjt = api.get_fundamentals(None, date=PREV_DAY)
    df_gjt = pd.DataFrame() if df_gjt is None else df_gjt.copy()
    if not df_gjt.empty:
        df_gjt = df_gjt[df_gjt["code"].isin(bomb_codes)].copy()
        if "operating_revenue" in df_gjt.columns:
            df_gjt = df_gjt[df_gjt["operating_revenue"] > 1e8].copy()
    gjt_codes = list(df_gjt["code"]) if not df_gjt.empty else []

    df_t = api.get_price(
        gjt_codes,
        end_date=PREV_DAY,
        frequency="1d",
        fields=["close", "low", "volume"],
        count=3,
        panel=False,
    )
    df_t = pd.DataFrame() if df_t is None else df_t.copy()
    if not df_t.empty and "time" not in df_t.columns:
        df_t = df_t.reset_index()
    valid_codes = []
    if not df_t.empty:
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
        latest = df_t[df_t["time"] == PREV_DAY]
        valid_codes = latest[cond.loc[latest.index]]["code"].unique().tolist()

    df_mv = api.get_fundamentals(None, date=PREV_DAY)
    df_mv = pd.DataFrame() if df_mv is None else df_mv.copy()
    if not df_mv.empty:
        df_mv = df_mv[df_mv["code"].isin(valid_codes)].copy()
        if "circulating_market_cap" in df_mv.columns:
            df_mv = df_mv[
                (df_mv["circulating_market_cap"] > 10)
                & (df_mv["circulating_market_cap"] < 2000)
            ].copy()
    final_codes = list(df_mv["code"]) if not df_mv.empty else []

    return {
        "secs": secs,
        "all_codes": all_codes,
        "df_hl": df_hl,
        "bomb_codes": bomb_codes,
        "df_gjt": df_gjt,
        "gjt_codes": gjt_codes,
        "df_t": df_t,
        "valid_codes_before_mv": valid_codes,
        "df_mv": df_mv,
        "valid_codes": final_codes,
        "yclose_map": df_hl[df_hl["code"].isin(final_codes)].set_index("code")["close"].to_dict() if not df_hl.empty else {},
    }


def build_buy_gate(api, codes, yclose_map, leg):
    snap = api.get_price(
        codes,
        end_date=BUY_DAY,
        frequency="daily",
        fields=["open", "close", "high_limit", "low_limit", "paused"],
        count=1,
        panel=False,
        fill_paused=False,
    )
    snap = pd.DataFrame() if snap is None else snap.copy()
    if snap.empty:
        return []

    au = api.get_call_auction(codes, start_date=BUY_DAY.strftime("%Y-%m-%d"), end_date=BUY_DAY.strftime("%Y-%m-%d"))
    val = api.get_valuation(codes, start_date=PREV_DAY, end_date=PREV_DAY, fields=["turnover_ratio", "market_cap", "circulating_market_cap"])
    val = pd.DataFrame() if val is None else val.copy()
    if not val.empty and "code" in val.columns:
        val = val[val["code"].isin(codes)].copy()
    val_map = val.set_index("code").to_dict("index") if not val.empty else {}

    au_map = {}
    if isinstance(au, dict):
        for code, sub in au.items():
            if sub is not None and not sub.empty:
                au_map[code] = sub.iloc[0]
    else:
        au = pd.DataFrame() if au is None else au.copy()
        if not au.empty and "code" in au.columns:
            for _, row in au.iterrows():
                au_map[row["code"]] = row

    rows = []
    for _, row in snap.iterrows():
        code = row["code"]
        yc = safe_float(yclose_map.get(code))
        op = safe_float(row.get("open"))
        hl = safe_float(row.get("high_limit"))
        ll = safe_float(row.get("low_limit"))
        # At 09:27/09:28 the local engine current_data.last_price uses the daily open.
        last_price = op
        paused = bool(row.get("paused"))
        ratio = (op / yc) if yc and op else None
        if leg == "rzq":
            ratio_ok = ratio is not None and 0.96 < ratio < 1.01
        else:
            ratio_ok = ratio is not None and 0.97 < ratio < 1.075
        not_limit = (
            last_price is not None
            and hl is not None
            and ll is not None
            and not (last_price >= hl * 0.999 or last_price <= ll * 1.001)
        )
        au_row = au_map.get(code)
        buy_m = calc_money(au_row, "b") if au_row is not None else None
        sell_m = calc_money(au_row, "a") if au_row is not None else None
        auction_ok = buy_m is not None and sell_m is not None and sell_m > 0 and (buy_m - sell_m) / sell_m > 0
        turn = safe_float((val_map.get(code) or {}).get("turnover_ratio"))
        market_cap = safe_float((val_map.get(code) or {}).get("market_cap"))
        circ_cap = safe_float((val_map.get(code) or {}).get("circulating_market_cap"))
        score = (turn or 0.0) * (ratio or 0.0) * ((buy_m / sell_m) if buy_m and sell_m else 0.0)
        rows.append(
            {
                "code": code,
                "leg": leg,
                "yclose": yc,
                "open": op,
                "ratio": ratio,
                "paused": paused,
                "last_price": last_price,
                "high_limit": hl,
                "low_limit": ll,
                "ratio_ok": ratio_ok,
                "not_limit": not_limit,
                "auction_ok": auction_ok,
                "buy_m": buy_m,
                "sell_m": sell_m,
                "turnover_ratio": turn,
                "market_cap": market_cap,
                "circulating_market_cap": circ_cap,
                "score": score,
            }
        )
    return sorted(rows, key=lambda x: (-x["score"], x["code"]))


def main():
    api = DataAPI(data_root=r"D:\work space\hdata", compat=EmotionGateJQCompat(ROOT))

    rzq = build_rzq_prepare(api)
    zb = build_zb_prepare(api)

    rzq_gate = build_buy_gate(api, rzq["valid_codes"], rzq["yclose_map"], "rzq")
    zb_gate = build_buy_gate(api, zb["valid_codes"], zb["yclose_map"], "zb")

    out = {
        "buy_day": BUY_DAY.strftime("%Y-%m-%d"),
        "prev_day": PREV_DAY.strftime("%Y-%m-%d"),
        "rzq_prepare_valid": rzq["valid_codes"],
        "zb_prepare_valid": zb["valid_codes"],
        "rzq_gate": rzq_gate,
        "zb_gate": zb_gate,
        "rzq_pass": [r for r in rzq_gate if r["ratio_ok"] and r["not_limit"] and r["auction_ok"]],
        "zb_pass": [r for r in zb_gate if r["ratio_ok"] and r["not_limit"] and r["auction_ok"]],
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
