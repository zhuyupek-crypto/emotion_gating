"""
Targeted alignment diagnostic for v227 JQ parity work.

Runs the full probe logic from a given warmup start, accumulates state
properly, then prints detailed per-day diagnostics for specific focus dates.

Usage:
  python scripts/diagnose_alignment.py --focus 20220616,20220705,20220706,20220707
"""

from __future__ import annotations

import argparse
from collections import deque
from pathlib import Path

import numpy as np
import pandas as pd

# Reuse all helpers from the probe module
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))

import importlib.util
_spec = importlib.util.spec_from_file_location("probe", Path(__file__).resolve().parent / "v227_yjj_probe.py")
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

# Pull helpers
ROOT = _mod.ROOT
load_daily = _mod.load_daily
load_indicator = _mod.load_indicator
load_st = _mod.load_st
load_basic = _mod.load_basic
load_index = _mod.load_index
identify_first_boards = _mod.identify_first_boards
board_counts = _mod.board_counts
compute_raw_mode = _mod.compute_raw_mode
filter_base = _mod.filter_base
apply_v122_blast_filter = _mod.apply_v122_blast_filter
apply_v130 = _mod.apply_v130
score_with_left_pressure = _mod.score_with_left_pressure
apply_low_price_tilt = _mod.apply_low_price_tilt
scan_bear_scorpion = _mod.scan_bear_scorpion
low_price_tilt_active = _mod.low_price_tilt_active
jq_code = _mod.jq_code

FB_WIN = _mod.FB_WIN
FB_MIN_HIST = _mod.FB_MIN_HIST
WIN_WINDOW = _mod.WIN_WINDOW
SLOTS = _mod.SLOTS


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--warmup", default="20211001")
    parser.add_argument("--end", default="20221231")
    parser.add_argument("--focus", default="20220616,20220705,20220706,20220707,20220318")
    args = parser.parse_args()

    focus_dates = set(args.focus.split(","))
    warmup = args.warmup
    end = args.end

    years = list(range(int(warmup[:4]), int(end[:4]) + 1))
    daily = load_daily(years)
    ind = load_indicator(years)
    st = load_st(years)
    list_date, name_map, list_status, delist_date = load_basic()
    idx_map = load_index()

    trade_dates = sorted(d for d in daily if warmup <= d <= end)

    fb_hist: deque[float] = deque(maxlen=FB_WIN)
    prev_first_boards: list[str] = []
    recent_trades: deque[int] = deque(maxlen=WIN_WINDOW)
    board_heights: deque[int] = deque(maxlen=20)
    bull_sticky = 0

    for i, today in enumerate(trade_dates):
        if i < 2:
            continue

        prev, prev2 = trade_dates[i - 1], trade_dates[i - 2]
        prev3 = trade_dates[i - 3] if i >= 3 else prev2
        df_prev, df_prev2, df_prev3 = daily[prev], daily[prev2], daily[prev3]
        st_prev = st.get(prev, set())
        st_prev2 = st.get(prev2, set())
        st_prev3 = st.get(prev3, set())

        if prev_first_boards:
            rets = []
            for code in prev_first_boards:
                if code in df_prev.index and code in df_prev2.index:
                    base = float(df_prev2.loc[code, "close"])
                    if base > 0:
                        rets.append(float(df_prev.loc[code, "close"]) / base - 1)
            fb_perf = float(np.mean(rets)) if rets else 0.0
        else:
            fb_perf = 0.0
        fb_hist.append(fb_perf)
        fb_pct = sum(1 for x in fb_hist if x < fb_perf) / len(fb_hist) if len(fb_hist) >= FB_MIN_HIST else 0.5

        raw_mode = compute_raw_mode(trade_dates, i, idx_map, fb_perf)
        if raw_mode == "bull":
            bull_sticky = 2
            market_mode = "bull"
        elif bull_sticky > 0 and raw_mode == "cautious":
            bull_sticky -= 1
            market_mode = "bull"
        else:
            bull_sticky = 0
            market_mode = raw_mode

        first_boards = identify_first_boards(df_prev, df_prev2, st_prev, st_prev2)
        prev_board_counts = board_counts(df_prev, df_prev2, df_prev3, st_prev, st_prev2, st_prev3)
        board_heights.append(max(prev_board_counts.values()) if prev_board_counts else 0)

        prev_first_boards = first_boards

        low_tilt = low_price_tilt_active(market_mode, fb_pct, fb_perf, board_heights, recent_trades)

        base, drops = filter_base(
            first_boards, df_prev, ind.get(prev, pd.Series(dtype=float)),
            st_prev, list_date, name_map, list_status, delist_date,
            today, market_mode, False, 30,
        )
        base, blast = apply_v122_blast_filter(base, prev, trade_dates[:i], daily)
        cands, tail, err = apply_v130(base, prev, df_prev, st_prev)

        if cands and market_mode == "bull":
            ranked = score_with_left_pressure(cands, prev, trade_dates[:i], daily, ind.get(prev, pd.Series(dtype=float)))
        else:
            ranked = apply_low_price_tilt(cands, df_prev["close"], low_tilt)

        scorpion_cands = []
        if market_mode == "bear":
            scorpion_cands = scan_bear_scorpion(
                first_boards, df_prev, trade_dates[:i], daily, st_prev,
                list_date, name_map, list_status, delist_date, today, False, 30,
            )
            scorpion_cands = apply_low_price_tilt(scorpion_cands, df_prev["close"], low_tilt)

        buy_block = ""
        if market_mode == "bear":
            buy_block = "bear_mode"
        elif market_mode == "bull" and fb_pct < 0.2:
            buy_block = "bull_pct_lt_020"
        elif market_mode == "cautious" and 0.4 <= fb_pct < 0.6:
            buy_block = "cautious_pct_040_060"

        if today in focus_dates:
            print(f"\n{'='*70}")
            print(f"FOCUS DATE: {today}")
            print(f"  market_mode={market_mode}  raw_mode={raw_mode}  bull_sticky={bull_sticky}")
            print(f"  fb_perf={fb_perf*100:.3f}%  fb_pct={fb_pct:.4f}  fb_hist_len={len(fb_hist)}")
            print(f"  buy_block={buy_block or '-'}  low_tilt={low_tilt}")
            print(f"  first_boards={len(first_boards)}")

            # fb_hist percentile context
            if len(fb_hist) >= FB_MIN_HIST:
                sorted_hist = sorted(fb_hist)
                p25 = sorted_hist[len(sorted_hist)//4]
                p50 = sorted_hist[len(sorted_hist)//2]
                p75 = sorted_hist[3*len(sorted_hist)//4]
                print(f"  fb_hist: p25={p25*100:.3f}% p50={p50*100:.3f}% p75={p75*100:.3f}% today={fb_perf*100:.3f}%")
                # How many entries are below/above key thresholds for the current fb_perf
                pct_below = sum(1 for x in fb_hist if x < fb_perf) / len(fb_hist)
                print(f"  fb_pct={pct_below:.4f} (block if 0.40<=pct<0.60 in cautious)")

            print(f"  drops={drops}  blast={blast}  tail={tail}")
            print(f"  base candidates ({len(base)}): {[jq_code(c) for c in base]}")
            print(f"  v130 candidates ({len(cands)}): {[jq_code(c) for c in cands]}")
            print(f"  ranked ({len(ranked)}): {[jq_code(c) for c in ranked]}")
            print(f"  scorpion ({len(scorpion_cands)}): {[jq_code(c) for c in scorpion_cands]}")

            # Candidate open prices for context
            today_df = daily.get(today, pd.DataFrame())
            for code in (ranked + scorpion_cands)[:8]:
                hcode = code  # already hdata format
                if hcode not in today_df.index:
                    print(f"    {jq_code(code)}: NOT IN TODAY DF")
                    continue
                row = today_df.loc[hcode]
                yclose = float(df_prev.loc[hcode, "close"]) if hcode in df_prev.index else 0
                op = float(row["open"])
                opct = op / yclose - 1 if yclose > 0 else float("nan")
                print(f"    {jq_code(code)}: open={op:.2f} yclose={yclose:.2f} opct={opct*100:.2f}%")


if __name__ == "__main__":
    main()
