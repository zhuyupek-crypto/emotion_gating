from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
import sys

WORK = ROOT / "rebuild_from_archive"
sys.path.insert(0, str(WORK))
sys.path.insert(1, str(ROOT))
sys.path.insert(2, r"D:\work space\hdata")

from engine.data_api import DataAPI


def excluded_market_code(code: str) -> bool:
    return code.startswith(("688", "8", "4", "9")) or code.endswith((".BJ", ".XBSE"))


def raw_boards(api: DataAPI, date: str) -> dict[str, int]:
    day = pd.to_datetime(date)
    secs = api.get_all_securities(["stock"], date=day)
    all_stocks = [s for s in secs.index if not excluded_market_code(s)]
    high_limits = api.get_price(
        all_stocks,
        end_date=day,
        frequency="daily",
        fields=["high_limit"],
        count=3,
        panel=True,
        fq=None,
    )
    closes = api.get_price(
        all_stocks,
        end_date=day,
        frequency="daily",
        fields=["close"],
        count=3,
        panel=True,
        fq=None,
    )
    high_limits = high_limits["high_limit"] if isinstance(high_limits.columns, pd.MultiIndex) else high_limits
    closes = closes["close"] if isinstance(closes.columns, pd.MultiIndex) else closes
    out = {}
    for code in all_stocks:
        if code not in high_limits.columns or code not in closes.columns:
            continue
        hl = high_limits[code].to_numpy()
        cr = closes[code].to_numpy()
        if len(hl) < 3 or len(cr) < 3:
            continue
        if pd.isna(hl[-1]) or pd.isna(cr[-1]) or hl[-1] <= 0 or abs(cr[-1] - hl[-1]) > 0.02:
            continue
        boards = 1
        if hl[-2] > 0 and abs(cr[-2] - hl[-2]) <= 0.02:
            boards = 2
            if hl[-3] > 0 and abs(cr[-3] - hl[-3]) <= 0.02:
                boards = 3
        out[code] = boards
    return out


def cached_boards(api: DataAPI, date: str) -> dict[str, int]:
    day = pd.to_datetime(date)
    secs = api.get_all_securities(["stock"], date=day)
    all_stocks = [s for s in secs.index if not excluded_market_code(s)]
    board_df = api.get_project_board_snapshot(day)
    if board_df.empty:
        return {}
    board_df = board_df[
        (~board_df["code"].astype(str).map(excluded_market_code)) &
        (board_df["code"].isin(all_stocks))
    ].copy()
    by_code = {row.code: int(row.board_count) for row in board_df.itertuples(index=False)}
    return {code: by_code[code] for code in all_stocks if code in by_code}


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate mother _scan_all board cache fast path.")
    parser.add_argument("dates", nargs="+", help="Previous-date inputs, e.g. 2021-01-04")
    args = parser.parse_args()

    api = DataAPI()
    rows = []
    for date in args.dates:
        raw = raw_boards(api, date)
        cached = cached_boards(api, date)
        diffs = []
        if set(raw) != set(cached):
            diffs.append(f"codes raw_only={sorted(set(raw)-set(cached))[:10]} cached_only={sorted(set(cached)-set(raw))[:10]}")
        board_diff = [(code, raw[code], cached[code]) for code in sorted(set(raw) & set(cached)) if raw[code] != cached[code]]
        if board_diff:
            diffs.append(f"board_count={board_diff[:10]}")
        rows.append({"date": date, "raw_n": len(raw), "cached_n": len(cached), "status": "ok" if not diffs else " ; ".join(diffs)})

    out = pd.DataFrame(rows)
    print(out.to_string(index=False))
    if (out["status"] != "ok").any():
        raise SystemExit(1)


if __name__ == "__main__":
    main()
