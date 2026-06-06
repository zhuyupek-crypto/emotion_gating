"""
JoinQuant research script: audit the v227 "一进二" candidate chain.

Paste this file into a JoinQuant research notebook/script and run it.  It does
not place orders.  It reproduces the 9:05 preparation path that feeds
buy_v227_一进二, then prints a CSV table for local hdata comparison.

Usage:
  1. Edit CHECK_DATES, or set START_DATE/END_DATE and leave CHECK_DATES empty.
  2. Run in JoinQuant Research.
  3. Copy the CSV block printed at the end.

Important:
  This is a candidate/state audit, not a full strategy backtest.  Trade-derived
  states such as recent win rate, stop-loss cooldown, and bull cooldown are
  initialized to neutral unless you manually seed STATE_BY_DATE.
"""

from collections import deque
from datetime import date, datetime

import numpy as np
import pandas as pd
from jqdata import *


# ---------------------------------------------------------------------------
# Date selection
# ---------------------------------------------------------------------------

CHECK_DATES = [
    "2024-03-12",
    "2024-03-13",
    "2024-03-15",
]

START_DATE = "2024-01-01"
END_DATE = "2024-12-31"


# Optional manual state override for exact strategy-backtest comparison.
# Example:
# STATE_BY_DATE = {
#     "2024-03-12": {"stoploss_cooldown": 0, "bull_cooldown": 0,
#                    "v227_shock_cooldown": 0, "recent_win_rate": 0.50},
# }
STATE_BY_DATE = {}


# ---------------------------------------------------------------------------
# Mother-version constants
# ---------------------------------------------------------------------------

FB_WINDOW = 60
FB_MIN_HIST = 10
WIN_WINDOW = 60

IPO_DAYS = 250
IDX_CODE = "000852.XSHG"
LIMIT_TOL = 0.02

CIRC_MIN = 30.0
CIRC_MAX = 500.0
MONEY_MIN = 6e8
MONEY_MAX_BULL = 20e8

LOW_PRICE_FACTOR_ENABLED = True
LOW_PRICE_REF = 20.0
LOW_PRICE_WEIGHT = 0.15
LOW_PRICE_MIN_WIN_RATE = 0.45

BULL_RELEASE_CONFIRM_PCT = 0.60


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def _to_date(s):
    if isinstance(s, date):
        return s
    return pd.to_datetime(s).date()


def _fmt_date(d):
    return d.strftime("%Y-%m-%d")


def _jq_code_order(codes):
    # JoinQuant get_all_securities index order is the strategy's natural order.
    return list(codes)


def _get_trade_dates():
    if CHECK_DATES:
        return [_to_date(x) for x in CHECK_DATES]
    days = [pd.to_datetime(x).date() for x in list(get_all_trade_days())]
    start = _to_date(START_DATE)
    end = _to_date(END_DATE)
    return [d for d in days if start <= d <= end]


def _prev_trade_day(day):
    days = [pd.to_datetime(x).date() for x in list(get_all_trade_days())]
    idx = days.index(day)
    return days[idx - 1] if idx > 0 else None


def _is_pass_month(day):
    # Same as mother v218: Jan/Apr/Dec after day 15, plus 15 days before Spring Festival.
    if day.month in (1, 4, 12) and day.day >= 15:
        return True
    spring_festival_dates = {
        2015: "2015-02-19", 2016: "2016-02-08", 2017: "2017-01-28",
        2018: "2018-02-16", 2019: "2019-02-05", 2020: "2020-01-25",
        2021: "2021-02-12", 2022: "2022-02-01", 2023: "2023-01-22",
        2024: "2024-02-10", 2025: "2025-01-29", 2026: "2026-02-17",
        2027: "2027-02-06", 2028: "2028-01-26", 2029: "2029-02-13",
        2030: "2030-02-03",
    }
    sf = spring_festival_dates.get(day.year)
    if not sf:
        return False
    sf_date = pd.to_datetime(sf).date()
    return (sf_date - pd.Timedelta(days=15)) <= day < sf_date


def _as_map(df, field):
    if df is None or len(df) == 0:
        return {}
    if isinstance(df, pd.DataFrame) and "code" in df.columns:
        return df.set_index("code")[field].to_dict()
    return {}


def _daily_frame(codes, end_date, count=1, fields=None):
    if not codes:
        return pd.DataFrame()
    if fields is None:
        fields = ["open", "close", "high", "low", "high_limit", "money", "volume"]
    try:
        df = get_price(
            codes,
            end_date=end_date,
            count=count,
            frequency="daily",
            fields=fields,
            panel=False,
            fill_paused=False,
            skip_paused=False,
            fq=None,
        )
    except Exception:
        return pd.DataFrame()
    if df is None or len(df) == 0:
        return pd.DataFrame()
    if "time" not in df.columns:
        df = df.reset_index()
    return df


def _one_day_map(codes, end_date, fields=None):
    df = _daily_frame(codes, end_date, count=1, fields=fields)
    if df.empty:
        return {}
    return {row["code"]: row for _, row in df.iterrows()}


def _calc_fb_perf(prev_first_boards, prev_date):
    if not prev_first_boards:
        return 0.0
    df = _daily_frame(prev_first_boards, prev_date, count=2, fields=["close"])
    if df.empty:
        return 0.0
    rets = []
    for code, sub in df.groupby("code"):
        sub = sub.sort_values("time")
        if len(sub) == 2 and float(sub.iloc[0]["close"]) > 0:
            rets.append(float(sub.iloc[1]["close"]) / float(sub.iloc[0]["close"]) - 1)
    return float(np.mean(rets)) if rets else 0.0


def _calc_fb_pct(fb_hist, fb_perf):
    buf = list(fb_hist)
    if len(buf) < FB_MIN_HIST:
        return 0.5
    rank = sum(1 for v in buf if v < fb_perf)
    return rank / len(buf)


def _compute_raw_mode(prev_date, fb_perf):
    # Research scripts do not have strategy context, so use get_price with an
    # explicit end_date instead of attribute_history.
    try:
        df = get_price(IDX_CODE, end_date=prev_date, count=65, frequency="daily",
                       fields=["close"], panel=False, fq=None)
        idx = df["close"] if df is not None and len(df) else []
    except Exception:
        idx = []

    if len(idx) < 20:
        return "bear"
    arr = np.asarray(idx, dtype=float)
    high_20 = arr[-20:].max()
    if high_20 > 0 and (arr[-1] - high_20) / high_20 <= -0.12:
        return "bear"
    if len(arr) < 60:
        return "bear"

    ma20 = arr[-20:].mean()
    ma60 = arr[-60:].mean()
    price = arr[-1]
    recent_30 = arr[-30:]
    days_above = int((recent_30 > ma60).sum())

    if price <= ma60 and ma20 <= ma60:
        return "bear"
    if price <= ma60 and ma20 > ma60:
        return "cautious" if fb_perf > 0 else "bear"
    if days_above >= len(recent_30) * 0.66:
        return "bull"
    return "cautious" if fb_perf > -0.02 else "bear"


def _scan_first_boards(day, prev_date, prev2_date):
    secs = get_all_securities(["stock"], date=prev_date)
    codes = [s for s in secs.index if not s.startswith("688") and not s.startswith("8")]
    d3 = _daily_frame(codes, prev_date, count=3, fields=["close", "high_limit"])
    if d3.empty:
        return [], 0, secs, codes

    first_boards = []
    max_boards = 0
    for code, sub in d3.groupby("code"):
        sub = sub.sort_values("time")
        if len(sub) < 3:
            continue
        r3 = sub.iloc[-3:]
        hl = list(r3["high_limit"].astype(float))
        cl = list(r3["close"].astype(float))
        if hl[-1] <= 0 or abs(cl[-1] - hl[-1]) > LIMIT_TOL:
            continue
        boards = 1
        if hl[-2] > 0 and abs(cl[-2] - hl[-2]) <= LIMIT_TOL:
            boards = 2
            if hl[-3] > 0 and abs(cl[-3] - hl[-3]) <= LIMIT_TOL:
                boards = 3
        max_boards = max(max_boards, boards)
        if boards == 1:
            first_boards.append(code)
    return first_boards, max_boards, secs, codes


def _filter_scan_all(day, prev_date, market_mode, first_boards, secs):
    if not first_boards:
        return [], {}, {"first": 0}

    ymap = _one_day_map(first_boards, prev_date,
                        fields=["close", "high_limit", "money", "volume"])
    q = query(valuation.code, valuation.circulating_market_cap).filter(
        valuation.circulating_market_cap > CIRC_MIN,
        valuation.circulating_market_cap < CIRC_MAX,
    )
    val_df = get_fundamentals(q, date=prev_date)
    valid_caps = set(val_df["code"].tolist()) if val_df is not None and not val_df.empty else set()

    yclose = {}
    kept = []
    counts = {
        "first": len(first_boards),
        "drop_st": 0,
        "drop_ipo": 0,
        "drop_cap": 0,
        "drop_money": 0,
        "drop_bull_money": 0,
        "drop_avg": 0,
    }
    for code in _jq_code_order(first_boards):
        if code in secs.index:
            name = secs.loc[code, "display_name"]
            if "ST" in name or "st" in name:
                counts["drop_st"] += 1
                continue
            if (day - secs.loc[code, "start_date"]).days < IPO_DAYS:
                counts["drop_ipo"] += 1
                continue
        if code not in valid_caps:
            counts["drop_cap"] += 1
            continue
        row = ymap.get(code)
        if row is None:
            counts["drop_money"] += 1
            continue
        money = float(row["money"])
        vol = float(row["volume"])
        close = float(row["close"])
        if money < MONEY_MIN:
            counts["drop_money"] += 1
            continue
        if market_mode == "bull" and money > MONEY_MAX_BULL:
            counts["drop_bull_money"] += 1
            continue
        if vol > 0 and close > 0:
            avg_chg = money / vol / close * 1.1 - 1
            if avg_chg < 0.07:
                counts["drop_avg"] += 1
                continue
        yclose[code] = close
        kept.append(code)
    counts["after_base"] = len(kept)
    return kept, yclose, counts


def _apply_v122(candidates, prev_date):
    if not candidates:
        return [], 0
    df = _daily_frame(candidates, prev_date, count=31,
                      fields=["volume", "high", "close"])
    if df.empty:
        return candidates, 0
    kept = []
    removed = 0
    for code in candidates:
        sub = df[df["code"] == code].sort_values("time")
        if len(sub) < 31:
            kept.append(code)
            continue
        v = sub["volume"].astype(float).values
        h = sub["high"].astype(float).values
        c = sub["close"].astype(float).values
        prev_vols = v[-6:-1]
        if len(prev_vols) == 5 and prev_vols.min() > 0:
            is_blast = (v[-1] > prev_vols.mean() * 8) or (v[-1] > prev_vols.min() * 12)
            is_new_high = c[-1] > np.max(h[-31:-1])
            if is_blast and is_new_high:
                removed += 1
                continue
        kept.append(code)
    return kept, removed


def _apply_v130(candidates, prev_date):
    if not candidates:
        return [], 0, 0
    kept = []
    removed_tail = 0
    removed_err = 0
    start_dt = "%s 09:30:00" % _fmt_date(prev_date)
    end_dt = "%s 15:00:00" % _fmt_date(prev_date)
    for code in candidates:
        try:
            df_m = get_price(code, start_date=start_dt, end_date=end_dt,
                             frequency="1m", fields=["close", "high_limit"],
                             skip_paused=True, panel=False)
            if df_m is None or len(df_m) == 0:
                kept.append(code)
                continue
            if "time" in df_m.columns:
                df_m = df_m.set_index("time")
            hit_mask = df_m["close"] >= (df_m["high_limit"] - 0.001)
            if not hit_mask.any():
                kept.append(code)
                continue
            first_hit_ts = df_m.index[hit_mask][0]
            t_hit = pd.to_datetime(first_hit_ts).time()
            if t_hit.hour >= 14:
                removed_tail += 1
                continue
            kept.append(code)
        except Exception:
            kept.append(code)
            removed_err += 1
    return kept, removed_tail, removed_err


def _low_price_tilt_active(market_mode, fb_pct, fb_perf, board_heights, recent_win_rate,
                           stoploss_cooldown, bull_cooldown, bull_force_clear=False):
    if not LOW_PRICE_FACTOR_ENABLED:
        return False
    if market_mode not in ("bear", "cautious"):
        return False
    if fb_pct >= 0.6:
        return False
    if stoploss_cooldown > 0 or bull_cooldown > 0 or bull_force_clear:
        return False
    if recent_win_rate < LOW_PRICE_MIN_WIN_RATE:
        return False
    if market_mode == "cautious" and fb_pct < 0.4:
        return False
    if fb_perf < 0 and fb_pct < 0.5:
        return False
    if len(board_heights) >= 10:
        recent = float(np.mean(list(board_heights)[-3:]))
        prior = float(np.mean(list(board_heights)[-10:]))
        if recent < prior and recent <= 3:
            return False
    return True


def _apply_low_price_tilt(candidates, yclose, active):
    if not candidates or not active:
        return candidates
    ranked = []
    for idx, code in enumerate(candidates):
        price = float(yclose.get(code, 0) or 0)
        bonus = 0.0
        if price > 0:
            bonus = max(0.0, min(1.0, LOW_PRICE_REF / price - 1.0))
        score = 1.0 + LOW_PRICE_WEIGHT * bonus
        ranked.append((code, score, idx))
    ranked.sort(key=lambda x: (-x[1], x[2]))
    return [x[0] for x in ranked]


def _score_with_left_pressure(candidates, prev_date):
    # Mother v218 currently reduces this to a binary 60-day breakout score.
    if not candidates:
        return candidates
    df = _daily_frame(candidates, prev_date, count=60, fields=["close", "high", "low", "volume"])
    if df.empty:
        return candidates
    scored = []
    for idx, code in enumerate(candidates):
        sub = df[df["code"] == code].sort_values("time")
        if len(sub) < 20:
            scored.append((code, 0.5, idx))
            continue
        closes = sub["close"].astype(float).values
        curr = closes[-1]
        prev_high_max = closes[:-1].max()
        is_break = curr >= prev_high_max * 0.99 if prev_high_max > 0 else False
        scored.append((code, 1.0 if is_break else 0.0, idx))
    scored.sort(key=lambda x: (-x[1], x[2]))
    return [x[0] for x in scored]


def run_audit():
    dates = _get_trade_dates()
    _emit("v227 audit start: %d dates, first=%s" % (
        len(dates), _fmt_date(dates[0]) if dates else "None"
    ))
    rows = []

    fb_hist = deque(maxlen=FB_WINDOW)
    prev_first_boards = []
    board_heights = []
    bull_sticky = 0
    bull_release_confirm_pending = False

    for day in dates:
        _emit("processing %s" % _fmt_date(day))
        prev_date = _prev_trade_day(day)
        if prev_date is None:
            continue

        ds = _fmt_date(day)
        state = STATE_BY_DATE.get(ds, {})
        stoploss_cooldown = int(state.get("stoploss_cooldown", 0))
        bull_cooldown = int(state.get("bull_cooldown", 0))
        v227_shock_cooldown = int(state.get("v227_shock_cooldown", 0))
        recent_win_rate = float(state.get("recent_win_rate", 0.50))

        fb_perf = _calc_fb_perf(prev_first_boards, prev_date)
        fb_hist.append(fb_perf)
        fb_pct = _calc_fb_pct(fb_hist, fb_perf)

        raw_mode = _compute_raw_mode(prev_date, fb_perf)
        if raw_mode == "bull":
            bull_sticky = 2
            market_mode = "bull"
        elif bull_sticky > 0 and raw_mode == "cautious":
            bull_sticky -= 1
            market_mode = "bull"
        else:
            bull_sticky = 0
            market_mode = raw_mode

        bull_release_guard = False
        if bull_release_confirm_pending and bull_cooldown <= 0:
            if market_mode == "bull":
                if raw_mode != "bull" and fb_pct < BULL_RELEASE_CONFIRM_PCT:
                    bull_release_guard = True
                else:
                    bull_release_confirm_pending = False
            else:
                bull_release_confirm_pending = False

        pass_month = _is_pass_month(day)
        if market_mode == "bear":
            active = "v227"
        elif market_mode == "cautious":
            active = "v227"
        elif fb_pct >= 0.8:
            active = "v227"
        elif bull_release_guard:
            active = "v227"
        elif not pass_month:
            active = "rzq+zb"
        else:
            active = "v227"
        enable_v227 = active == "v227"

        first_boards, max_boards, secs, _codes = _scan_first_boards(day, prev_date, None)
        prev_first_boards = first_boards
        board_heights.append(max_boards)
        if len(board_heights) > 20:
            board_heights = board_heights[-20:]

        if market_mode == "bear":
            raw_candidates = []
            yclose = {}
            counts = {"first": len(first_boards), "after_base": 0}
        else:
            raw_candidates, yclose, counts = _filter_scan_all(day, prev_date, market_mode, first_boards, secs)

        after_v122, v122_removed = _apply_v122(raw_candidates, prev_date)
        after_v130, v130_tail, v130_err = _apply_v130(after_v122, prev_date)

        low_tilt_active = _low_price_tilt_active(
            market_mode, fb_pct, fb_perf, board_heights, recent_win_rate,
            stoploss_cooldown, bull_cooldown,
        )
        if after_v130 and market_mode == "bull":
            final_order = _score_with_left_pressure(after_v130, prev_date)
            sort_mode = "left_pressure"
        else:
            final_order = _apply_low_price_tilt(after_v130, yclose, low_tilt_active)
            sort_mode = "low_price_tilt" if low_tilt_active else "jq_order"

        # buy_v227_一进二 skip gates.  This says whether the final_order would
        # actually be considered by that buy function before open filters.
        buy_skip = False
        skip_reason = ""
        if not enable_v227:
            buy_skip, skip_reason = True, "disabled"
        elif market_mode == "cautious" and 0.4 <= fb_pct < 0.6:
            buy_skip, skip_reason = True, "cautious_pct_040_060"
        elif market_mode == "bull" and fb_pct < 0.2:
            buy_skip, skip_reason = True, "bull_pct_lt_020"
        elif market_mode == "bull" and bull_cooldown > 0:
            buy_skip, skip_reason = True, "bull_cooldown"
        elif market_mode == "bear":
            buy_skip, skip_reason = True, "bear_mode"
        elif stoploss_cooldown > 0 and market_mode != "bull":
            buy_skip, skip_reason = True, "stoploss_cooldown"
        elif v227_shock_cooldown > 0:
            buy_skip, skip_reason = True, "v227_shock_cooldown"
        elif not final_order:
            buy_skip, skip_reason = True, "no_candidate"

        rows.append({
            "date": ds,
            "prev_date": _fmt_date(prev_date),
            "raw_mode": raw_mode,
            "market_mode": market_mode,
            "fb_perf": round(fb_perf, 6),
            "fb_pct": round(fb_pct, 4),
            "pass_month": int(pass_month),
            "active": active,
            "enable_v227": int(enable_v227),
            "buy_skip": int(buy_skip),
            "skip_reason": skip_reason,
            "sort_mode": sort_mode,
            "low_tilt": int(low_tilt_active),
            "n_first": counts.get("first", len(first_boards)),
            "drop_st": counts.get("drop_st", 0),
            "drop_ipo": counts.get("drop_ipo", 0),
            "drop_cap": counts.get("drop_cap", 0),
            "drop_money": counts.get("drop_money", 0),
            "drop_bull_money": counts.get("drop_bull_money", 0),
            "drop_avg": counts.get("drop_avg", 0),
            "n_after_base": counts.get("after_base", len(raw_candidates)),
            "v122_removed": v122_removed,
            "n_after_v122": len(after_v122),
            "v130_tail": v130_tail,
            "v130_err": v130_err,
            "n_after_v130": len(after_v130),
            "final_codes": "|".join(final_order),
            "buy_probe_top2": "|".join(final_order[:2]) if not buy_skip else "",
        })

    out = pd.DataFrame(rows)
    print("\n=== v227_yjj_audit preview ===")
    print(out.head(20).to_string(index=False))
    print("\n=== CSV_START ===")
    print(out.to_csv(index=False))
    print("=== CSV_END ===")
    return out


def _emit(msg):
    print(msg)
    logger = globals().get("log")
    if logger is not None:
        try:
            logger.info(msg)
        except Exception:
            pass


try:
    _emit("jq_v227_yjj_audit loaded")
    audit_df = run_audit()
    _emit("jq_v227_yjj_audit done")
except Exception as e:
    import traceback
    _emit("jq_v227_yjj_audit ERROR: %s" % repr(e))
    _emit(traceback.format_exc())
