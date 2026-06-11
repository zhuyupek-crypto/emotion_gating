from __future__ import annotations

import argparse
import importlib
import os
import sys
from pathlib import Path

import pandas as pd
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / "rebuild_from_archive"
STRATEGY = ROOT / "母版-20260506-Clone.py"
HDATA_SCRIPTS = Path(r"D:\work space\hdata\scripts")

sys.path.insert(0, str(WORK))
sys.path.insert(1, str(HDATA_SCRIPTS))
sys.path.insert(2, r"D:\work space\hdata")
sys.path.insert(3, str(ROOT))
sys.modules["jqdata"] = importlib.import_module("jqdata_compat")

from core import hdata_reader
from engine.core import Engine


def _reset_auction_state(g):
    g.auction_yiqian_candidates = []
    g.auction_yiqian_yclose = {}
    g.auction_yiqian_kind = {}
    g.auction_yiqian_prev_money = {}
    g.auction_yiqian_prev_volume = {}
    g.auction_yiqian_avg_inc = {}
    g.auction_yiqian_inc4 = {}
    g.auction_yiqian_left_ok = {}


def _live_rows(engine: Engine, day: pd.Timestamp, previous_day: pd.Timestamp) -> pd.DataFrame:
    g = engine.namespace["g"]
    _reset_auction_state(g)
    engine.current_time = "09:05"
    engine.context.current_dt = day.replace(hour=9, minute=5)
    engine.context.previous_date = previous_day
    engine.namespace["_auction_yiqian_prepare"](engine.context)
    rows = []
    for rank, code in enumerate(getattr(g, "auction_yiqian_candidates", []) or [], 1):
        rows.append(
            {
                "date": int(day.strftime("%Y%m%d")),
                "rank": rank,
                "code": code,
                "kind": g.auction_yiqian_kind.get(code),
                "prev_money": float(g.auction_yiqian_prev_money.get(code, 0)),
                "prev_close": float(g.auction_yiqian_yclose.get(code, 0)),
                "prev_volume": float(g.auction_yiqian_prev_volume.get(code, 0)),
                "avg_inc": float(g.auction_yiqian_avg_inc.get(code, 0)),
                "inc4": float(g.auction_yiqian_inc4.get(code, 0)),
                "left_ok": bool(g.auction_yiqian_left_ok.get(code, False)),
            }
        )
    return pd.DataFrame(rows)


def _norm(df: pd.DataFrame) -> pd.DataFrame:
    cols = ["date", "rank", "code", "kind", "prev_money", "prev_close", "prev_volume", "avg_inc", "inc4", "left_ok"]
    if df.empty:
        return pd.DataFrame(columns=cols)
    out = df[cols].copy()
    return out.sort_values(["date", "rank"]).reset_index(drop=True)


def _same(live: pd.DataFrame, cached: pd.DataFrame) -> bool:
    live = _norm(live)
    cached = _norm(cached)
    exact_cols = ["date", "rank", "code", "kind", "left_ok"]
    if list(live[exact_cols].itertuples(index=False, name=None)) != list(cached[exact_cols].itertuples(index=False, name=None)):
        return False
    # Runtime buy logic only consumes kind, prev_volume, and left_ok from this
    # prepare block.  Other numeric columns are kept for audit/debug and may
    # differ slightly because the offline cache starts from pivot parquet.
    numeric_cols = ["prev_volume"]
    for col in numeric_cols:
        if not np.allclose(live[col].astype(float), cached[col].astype(float), rtol=1e-6, atol=1e-3, equal_nan=True):
            return False
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate auction_yiqian_prepare cache against live mother strategy logic.")
    parser.add_argument("year", type=int)
    parser.add_argument("--max-days", type=int, default=0, help="Limit validation days for quick probes.")
    args = parser.parse_args()

    cache_path = ROOT / "project_cache" / "features" / "auction_yiqian_prepare" / f"{args.year}.parquet"
    if not cache_path.exists():
        raise FileNotFoundError(cache_path)
    cached = pd.read_parquet(cache_path)

    years = {args.year - 1, args.year}
    hdata_reader._update_pivot_cache(years)

    with STRATEGY.open("r", encoding="utf-8") as f:
        strategy_code = f.read()
    engine = Engine(strategy_code, f"{args.year}-01-01", f"{args.year}-12-31", 1000000)
    exec(strategy_code, engine.namespace)
    engine.namespace["initialize"](engine.context)

    trade_days = [pd.Timestamp(d) for d in engine.data_api.get_trade_days(f"{args.year - 1}-12-01", f"{args.year}-12-31")]
    target_days = [d for d in trade_days if d.year == args.year]
    if args.max_days:
        target_days = target_days[: args.max_days]

    mismatches = []
    checked = 0
    for day in target_days:
        idx = trade_days.index(day)
        if idx == 0:
            continue
        previous_day = trade_days[idx - 1]
        live = _norm(_live_rows(engine, day, previous_day))
        day_key = int(day.strftime("%Y%m%d"))
        cached_day = _norm(cached[cached["date"].astype(int) == day_key])
        if not _same(live, cached_day):
            mismatches.append((day_key, live, cached_day))
            if len(mismatches) >= 10:
                break
        checked += 1

    if mismatches:
        print(f"FAIL checked={checked} mismatches={len(mismatches)}")
        for day_key, live, cached_day in mismatches[:3]:
            print(f"\nDATE {day_key}")
            print("live:")
            print(live.head(20).to_string(index=False))
            print("cached:")
            print(cached_day.head(20).to_string(index=False))
        return 1

    print(f"OK checked={checked} year={args.year}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
