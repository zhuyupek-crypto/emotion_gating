from __future__ import annotations

import argparse
import sys
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd


PROJECT = Path(__file__).resolve().parents[1]
HDATA_PROJECT = Path(r"D:\work space\hdata")
sys.path.insert(0, str(HDATA_PROJECT))

from scripts.core import local_jq as jq  # type: ignore  # noqa: E402


WIN_WINDOW = 60
FB_WINDOW = 60
FB_MIN_HIST = 10


@dataclass
class G:
    ipo_days: int = 250
    idx_code: str = "000852.XSHG"
    yjj_candidates: list[str] = field(default_factory=list)
    bear_candidates: list[str] = field(default_factory=list)
    yjj_yclose: dict[str, float] = field(default_factory=dict)
    market_mode: str = "bear"
    raw_market_mode: str = "bear"
    bull_sticky: int = 0
    prev_first_boards: list[str] = field(default_factory=list)
    first_board_perf: float = 0.0
    fb_pct: float = 0.5
    fb_perf_history: deque = field(default_factory=lambda: deque(maxlen=FB_WINDOW))
    board_heights: list[int] = field(default_factory=list)
    leader_candidates_for_tag: list[tuple[str, int]] = field(default_factory=list)
    stoploss_cooldown: int = 0
    bull_cooldown: int = 0
    bull_consec_loss: int = 0
    bull_release_confirm_pending: bool = False
    bull_release_guard: bool = False
    bull_release_confirm_pct: float = 0.60
    v227_shock_cooldown: int = 0
    v227_shock_cooldown_enabled: bool = True
    prev_portfolio_value: float | None = None
    branch_test: str = "force_v227"
    active: str = "v227"
    route_active: str = "v227"
    enable_v227: bool = True
    enable_rzq: bool = False
    enable_zb: bool = False
    v227_slots: int = 2
    rzq_slots: int = 0
    zb_slots: int = 0
    recent_trades: deque = field(default_factory=lambda: deque(maxlen=WIN_WINDOW))


g = G()


def code_set(text: object) -> set[str]:
    if pd.isna(text):
        return set()
    return {p.strip() for p in str(text).replace("|", ",").split(",") if p.strip() and not p.startswith("...")}


def calc_fb_perf() -> float:
    if not g.prev_first_boards:
        return 0.0
    closes = jq.history(2, field="close", security_list=g.prev_first_boards, df=False, fq=None)
    rets = []
    for s in g.prev_first_boards:
        c = closes.get(s)
        if c is not None and len(c) == 2 and c[0] > 0:
            rets.append(c[1] / c[0] - 1)
    return float(np.mean(rets)) if rets else 0.0


def calc_fb_pct() -> float:
    buf = list(g.fb_perf_history)
    if len(buf) < FB_MIN_HIST:
        return 0.5
    rank = sum(1 for v in buf if v < g.first_board_perf)
    return rank / len(buf)


def win_rate() -> float:
    if len(g.recent_trades) < WIN_WINDOW:
        return 0.5
    return float(sum(g.recent_trades)) / len(g.recent_trades)


def low_price_tilt_active() -> bool:
    if g.market_mode not in ("bear", "cautious"):
        return False
    if g.fb_pct >= 0.6:
        return False
    if g.market_mode == "cautious" and g.fb_pct < 0.4:
        return False
    if g.first_board_perf < 0 and g.fb_pct < 0.5:
        return False
    return win_rate() >= 0.45


def apply_low_price_tilt(candidates: list[str], price_map: dict[str, float]) -> list[str]:
    if not candidates or not low_price_tilt_active():
        return candidates
    ranked = []
    for idx, code in enumerate(candidates):
        price = float(price_map.get(code, 0) or 0)
        bonus = max(0.0, min(1.0, 20.0 / price - 1.0)) if price > 0 else 0.0
        ranked.append((code, 1.0 + 0.15 * bonus, idx))
    ranked.sort(key=lambda x: (-x[1], x[2]))
    return [c for c, _, _ in ranked]


def calc_chip_stats(
    close_arr: np.ndarray,
    high_arr: np.ndarray,
    low_arr: np.ndarray,
    volume_arr: np.ndarray,
    circulating_shares: float,
    bins: int = 30,
) -> tuple[float, float]:
    n = len(close_arr)
    if n < 20 or circulating_shares <= 0:
        return 0.0, 0.0
    highs = np.asarray(high_arr, dtype=float)
    lows = np.asarray(low_arr, dtype=float)
    closes = np.asarray(close_arr, dtype=float)
    vols = np.asarray(volume_arr, dtype=float)
    price_min = lows.min() * 0.95
    price_max = highs.max() * 1.05
    if price_max <= price_min:
        return 0.0, 0.0
    prices = np.linspace(price_min, price_max, bins)
    span = highs - lows
    avg_p = (highs + lows + closes) / 3.0
    valid = (vols > 0) & (span > 0)
    safe_span = np.where(valid, span, 1.0)
    mask = (prices[None, :] >= lows[:, None]) & (prices[None, :] <= highs[:, None])
    raw_w = np.maximum(1.0 - np.abs(prices[None, :] - avg_p[:, None]) / safe_span[:, None], 0.0)
    raw_w = np.where(mask, raw_w, 0.0)
    ws = raw_w.sum(axis=1, keepdims=True)
    new_dist = np.where(ws > 0, raw_w / np.where(ws > 0, ws, 1.0), 0.0)
    t = np.where(valid, np.minimum(vols / circulating_shares, 1.0), 0.0)
    keep = 1.0 - t
    suffix_keep = np.empty(n)
    suffix_keep[-1] = 1.0
    if n > 1:
        suffix_keep[:-1] = np.cumprod(keep[:0:-1])[::-1]
    weights = t * suffix_keep
    chips0 = np.ones(bins) / bins
    chips = chips0 * keep.prod() + (new_dist * weights[:, None]).sum(axis=0)
    total = chips.sum()
    if total <= 0:
        return 0.0, 0.0
    chips /= total
    winner_rate = float(chips[prices <= closes[-1]].sum())
    return 0.0, winner_rate


def score_with_left_pressure(context, candidates: list[str]) -> list[str]:
    closes_100 = jq.history(100, field="close", security_list=candidates, df=False, fq="pre")
    volumes_100 = jq.history(100, field="volume", security_list=candidates, df=False, fq="pre")
    highs_60 = jq.history(60, field="high", security_list=candidates, df=False, fq="pre")
    lows_60 = jq.history(60, field="low", security_list=candidates, df=False, fq="pre")
    q = jq.query(jq.valuation.code, jq.valuation.circulating_market_cap).filter(
        jq.valuation.code.in_(candidates)
    )
    cap_df = jq.get_fundamentals(q, date=context.previous_date)
    circ_caps = dict(zip(cap_df["code"], cap_df["circulating_market_cap"])) if not cap_df.empty else {}
    scored: list[tuple[str, float]] = []
    for s in candidates:
        c = closes_100.get(s)
        v = volumes_100.get(s)
        if c is None or v is None or len(c) < 60:
            continue
        c = np.asarray(c, dtype=float)
        v = np.asarray(v, dtype=float)
        if not np.isfinite(c).all() or not np.isfinite(v).all():
            continue
        prev_highs = c[:-1]
        prev_vols = v[:-1]
        max_idx = int(np.argmax(prev_highs))
        is_break = c[-1] >= prev_highs[max_idx] * 0.99
        vol_ok = v[-1] >= prev_vols[max_idx] * 0.9 if prev_vols[max_idx] > 0 else False
        lp_score = 1.0 if (is_break and vol_ok) else 0.5 if is_break else 0.0
        circ_cap = float(circ_caps.get(s, 0) or 0)
        wr = 0.0
        if circ_cap > 0 and c[-1] > 0:
            cs = circ_cap * 1e8 / c[-1]
            n = min(len(c), 60)
            h_arr = highs_60.get(s)
            l_arr = lows_60.get(s)
            if h_arr is not None and l_arr is not None:
                _, wr = calc_chip_stats(c[-n:], np.asarray(h_arr)[-n:], np.asarray(l_arr)[-n:], v[-n:], cs)
        score = lp_score * 0.5 + wr * 0.5
        scored.append((s, score))
    scored.sort(key=lambda x: -x[1])
    return [s for s, _ in scored]


def update_board_heights() -> None:
    g.board_heights.append(getattr(g, "_today_max_boards", 0))
    if len(g.board_heights) > 20:
        g.board_heights = g.board_heights[-20:]


def scan_boards_for_prev(context) -> None:
    all_stocks = list(jq.get_all_securities(["stock"], date=context.previous_date).index)
    all_stocks = [s for s in all_stocks if not s.startswith("688") and not s.startswith("8")]
    high_limits = jq.history(3, field="high_limit", security_list=all_stocks, df=False, fq=None)
    closes_raw = jq.history(3, field="close", security_list=all_stocks, df=False, fq=None)
    secs = jq.get_all_securities(["stock"], date=context.previous_date)
    fb: list[str] = []
    bear_pool: list[str] = []
    max_b = 0
    for s in all_stocks:
        hl = high_limits.get(s)
        cr = closes_raw.get(s)
        if hl is None or cr is None or len(hl) < 3 or len(cr) < 3:
            continue
        if not (np.isfinite(hl[-1]) and np.isfinite(cr[-1])):
            continue
        if hl[-1] > 0 and abs(cr[-1] - hl[-1]) <= 0.01:
            boards = 1
            if np.isfinite(hl[-2]) and np.isfinite(cr[-2]) and hl[-2] > 0 and abs(cr[-2] - hl[-2]) <= 0.01:
                boards = 2
                if np.isfinite(hl[-3]) and np.isfinite(cr[-3]) and hl[-3] > 0 and abs(cr[-3] - hl[-3]) <= 0.01:
                    boards = 3
            max_b = max(max_b, boards)
            if boards == 1:
                fb.append(s)
                if s.startswith("30"):
                    continue
                if s in secs.index:
                    name = secs.loc[s, "display_name"]
                    if "ST" in name or "st" in name:
                        continue
                    if (context.current_dt.date() - secs.loc[s, "start_date"]).days < g.ipo_days:
                        continue
                g.yjj_yclose[s] = float(cr[-1])
                bear_pool.append(s)
    g.prev_first_boards = fb
    g._today_max_boards = max_b
    if bear_pool and g.market_mode == "bear":
        closes_60 = jq.history(60, field="close", security_list=bear_pool, df=False, fq="pre")
        for s in bear_pool:
            c60 = closes_60.get(s)
            if c60 is None or len(c60) < 20:
                continue
            h60, l60 = max(c60), min(c60)
            if h60 > l60 and (c60[-1] - l60) / (h60 - l60) <= 0.5:
                g.bear_candidates.append(s)
        g.bear_candidates = apply_low_price_tilt(g.bear_candidates, g.yjj_yclose)


def scan_all(context, run_v130: bool = True) -> None:
    all_stocks = list(jq.get_all_securities(["stock"], date=context.previous_date).index)
    all_stocks = [s for s in all_stocks if not s.startswith("688") and not s.startswith("8")]
    high_limits = jq.history(3, field="high_limit", security_list=all_stocks, df=False, fq=None)
    closes_raw = jq.history(3, field="close", security_list=all_stocks, df=False, fq=None)
    moneys = jq.history(1, field="money", security_list=all_stocks, df=False)
    volumes = jq.history(1, field="volume", security_list=all_stocks, df=False)
    secs = jq.get_all_securities(["stock"], date=context.previous_date)
    q = jq.query(jq.valuation.code, jq.valuation.circulating_market_cap).filter(
        jq.valuation.circulating_market_cap > 30,
        jq.valuation.circulating_market_cap < 500,
    )
    val_df = jq.get_fundamentals(q, date=context.previous_date)
    valid_caps = set(val_df["code"].tolist()) if not val_df.empty else set()
    first_boards: list[str] = []
    max_b = 0
    for s in all_stocks:
        hl = high_limits.get(s)
        cr = closes_raw.get(s)
        if hl is None or cr is None or len(hl) < 3 or len(cr) < 3:
            continue
        if not (np.isfinite(hl[-1]) and np.isfinite(cr[-1])):
            continue
        if hl[-1] <= 0 or abs(cr[-1] - hl[-1]) > 0.02:
            continue
        boards = 1
        if np.isfinite(hl[-2]) and np.isfinite(cr[-2]) and hl[-2] > 0 and abs(cr[-2] - hl[-2]) <= 0.02:
            boards = 2
            if np.isfinite(hl[-3]) and np.isfinite(cr[-3]) and hl[-3] > 0 and abs(cr[-3] - hl[-3]) <= 0.02:
                boards = 3
        max_b = max(max_b, boards)
        is_first = boards == 1
        if is_first:
            first_boards.append(s)
        if s in secs.index:
            name = secs.loc[s, "display_name"]
            if "ST" in name or "st" in name:
                continue
            if (context.current_dt.date() - secs.loc[s, "start_date"]).days < g.ipo_days:
                continue
        if s not in valid_caps:
            continue
        m = moneys.get(s)
        if m is None or len(m) == 0 or m[-1] < 6e8:
            continue
        if g.market_mode == "bull" and m[-1] > 20e8:
            continue
        if is_first:
            v_arr = volumes.get(s)
            if v_arr is not None and len(v_arr) > 0 and v_arr[-1] > 0 and cr[-1] > 0:
                avg_chg = m[-1] / v_arr[-1] / cr[-1] * 1.1 - 1
                if avg_chg < 0.07:
                    continue
        g.yjj_yclose[s] = float(cr[-1])
        if is_first:
            g.yjj_candidates.append(s)
    g.prev_first_boards = first_boards
    g._today_max_boards = max_b

    if g.yjj_candidates:
        v31 = jq.history(31, "1d", "volume", security_list=g.yjj_candidates, df=False, fq="pre")
        h31 = jq.history(31, "1d", "high", security_list=g.yjj_candidates, df=False, fq="pre")
        c31 = jq.history(31, "1d", "close", security_list=g.yjj_candidates, df=False, fq="pre")
        kept = []
        for s in g.yjj_candidates:
            v = v31.get(s)
            h = h31.get(s)
            c = c31.get(s)
            if v is None or h is None or c is None or len(v) < 31:
                kept.append(s)
                continue
            prev_vols = v[-6:-1]
            if len(prev_vols) == 5 and prev_vols.min() > 0:
                is_blast = (v[-1] > float(np.mean(prev_vols)) * 8) or (v[-1] > float(np.min(prev_vols)) * 12)
                is_new_high = c[-1] > float(np.max(h[-31:-1]))
                if is_blast and is_new_high:
                    continue
            kept.append(s)
        g.yjj_candidates = kept

    if run_v130 and g.yjj_candidates:
        yday = context.previous_date
        kept_t = []
        try:
            seal_times = jq.get_batch_sealing_points(g.yjj_candidates, yday)
        except Exception:
            seal_times = {}
        for s in g.yjj_candidates:
            hit = seal_times.get(s)
            if hit is None or pd.isna(hit):
                kept_t.append(s)
                continue
            t_hit = pd.to_datetime(hit).time()
            if t_hit.hour >= 14:
                continue
            kept_t.append(s)
        g.yjj_candidates = kept_t
    if g.yjj_candidates and g.market_mode == "bull":
        g.yjj_candidates = score_with_left_pressure(context, g.yjj_candidates)
    else:
        g.yjj_candidates = apply_low_price_tilt(g.yjj_candidates, g.yjj_yclose)


def mode_and_scan(context, run_v130: bool = True) -> None:
    idx = jq.attribute_history(g.idx_code, 65, "1d", ["close"])["close"]
    if len(idx) >= 20:
        high_20 = np.max(idx.iloc[-20:])
        now_price = idx.iloc[-1]
        if (now_price - high_20) / high_20 <= -0.12:
            g.market_mode = "bear"
            scan_boards_for_prev(context)
            update_board_heights()
            return
    if len(idx) >= 60:
        ma20 = np.mean(idx.iloc[-20:])
        ma60 = np.mean(idx.iloc[-60:])
        price = idx.iloc[-1]
        recent_30 = idx.iloc[-30:] if len(idx) >= 30 else idx.iloc[-10:]
        days_above = sum(1 for p in recent_30 if p > ma60)
        if price <= ma60 and ma20 <= ma60:
            new_mode = "bear"
        elif price <= ma60 and ma20 > ma60:
            new_mode = "cautious" if g.first_board_perf > 0 else "bear"
        elif days_above >= len(recent_30) * 0.66:
            new_mode = "bull"
        else:
            new_mode = "cautious" if g.first_board_perf > -0.02 else "bear"
    else:
        new_mode = "bear"
    g.raw_market_mode = new_mode
    if new_mode == "bull":
        g.bull_sticky = 2
        g.market_mode = "bull"
    elif g.bull_sticky > 0 and new_mode == "cautious":
        g.bull_sticky -= 1
        g.market_mode = "bull"
    else:
        g.bull_sticky = 0
        g.market_mode = new_mode
    if g.market_mode == "bear":
        scan_boards_for_prev(context)
    else:
        scan_all(context, run_v130=run_v130)
    update_board_heights()


def prepare_day(day: str, prev: str, run_v130: bool = True) -> dict[str, object]:
    g.yjj_candidates = []
    g.bear_candidates = []
    g.yjj_yclose = {}
    g.leader_candidates_for_tag = []
    current_dt = pd.Timestamp(day + " 09:05:00")
    # JoinQuant daily history at 09:05 is effectively cut off at
    # context.previous_date. Keep context.current_dt as today for IPO-age
    # checks, but set the local data clock to the previous trading day.
    jq.set_current_dt(pd.Timestamp(prev + " 15:00:00"))
    context = SimpleNamespace(
        current_dt=current_dt,
        previous_date=pd.Timestamp(prev).date(),
        portfolio=SimpleNamespace(total_value=1_000_000.0, available_cash=1_000_000.0, positions={}),
    )
    g.first_board_perf = calc_fb_perf()
    g.fb_perf_history.append(g.first_board_perf)
    g.fb_pct = calc_fb_pct()
    mode_and_scan(context, run_v130=run_v130)
    g.active = "v227"
    g.route_active = "v227"
    g.enable_v227 = True
    g.v227_slots = 2
    return {
        "date": day.replace("-", ""),
        "first_board_perf": g.first_board_perf,
        "fb_pct": g.fb_pct,
        "raw_market_mode": g.raw_market_mode,
        "market_mode": g.market_mode,
        "bull_sticky": g.bull_sticky,
        "prev_first_n": len(g.prev_first_boards),
        "yjj_n": len(g.yjj_candidates),
        "bear_n": len(g.bear_candidates),
        "prev_first_codes": "|".join(g.prev_first_boards),
        "yjj_codes": "|".join(g.yjj_candidates),
        "bear_codes": "|".join(g.bear_candidates),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2020-01-02")
    ap.add_argument("--end", default="2020-12-31")
    ap.add_argument("--out", type=Path, default=PROJECT / "local_jq_force_v227_state.csv")
    ap.add_argument("--no-v130", action="store_true")
    args = ap.parse_args()

    jq.auth("local", "local")
    preload_years = list(range(pd.Timestamp(args.start).year - 1, pd.Timestamp(args.end).year + 1))
    jq.preload_years(preload_years, fields=["close", "high_limit", "money", "volume", "high", "low"])
    tds = [d.strftime("%Y-%m-%d") for d in jq.get_trade_days(start_date=args.start, end_date=args.end)]
    all_tds = [d.strftime("%Y-%m-%d") for d in jq.get_trade_days(end_date=args.end, count=len(tds) + 80)]
    rows = []
    for i, day in enumerate(tds):
        prevs = [d for d in all_tds if d < day]
        if not prevs:
            continue
        row = prepare_day(day, prevs[-1], run_v130=not args.no_v130)
        rows.append(row)
        if (i + 1) % 20 == 0:
            print(f"PROGRESS {i+1}/{len(tds)} {day}")
    out = pd.DataFrame(rows)
    out.to_csv(args.out, index=False, encoding="utf-8-sig")
    print(f"WROTE {args.out} rows={len(out)}")


if __name__ == "__main__":
    main()
