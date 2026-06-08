from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
FEATURE_ROOT = ROOT / "project_cache" / "features"


def split_codes(value: object) -> set[str]:
    if pd.isna(value) or value == "":
        return set()
    return {part for part in str(value).split("|") if part}


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate master_prepare_index against board_snapshot.")
    parser.add_argument("year", type=int)
    parser.add_argument("--feature-root", type=Path, default=FEATURE_ROOT)
    args = parser.parse_args()

    board_path = args.feature_root / "board_snapshot" / f"{args.year}.parquet"
    index_path = args.feature_root / "master_prepare_index" / f"{args.year}.parquet"
    boards = pd.read_parquet(board_path)
    idx = pd.read_parquet(index_path)

    rows = []
    for date_int, sub in boards.groupby("date", sort=True):
        idx_day = idx[idx["date"].astype(int) == int(date_int)]
        if idx_day.empty:
            rows.append({"date": int(date_int), "status": "missing_index"})
            continue
        row = idx_day.iloc[0]
        first = sub[sub["is_first_board"]]
        expected_first = set(first["code"].astype(str))
        actual_first = split_codes(row.get("first_board_codes", ""))
        expected_leaders = {
            f"{r.code}:{int(r.board_count)}"
            for r in sub[sub["board_count"].astype(int) >= 3].itertuples(index=False)
        }
        actual_leaders = split_codes(row.get("leader_codes", ""))
        diffs = []
        if int(row["limit_up_close_n"]) != len(sub):
            diffs.append("limit_up_close_n")
        if int(row["first_board_n"]) != len(first):
            diffs.append("first_board_n")
        if int(row["max_board_count_market"]) != int(sub["max_board_count_market"].max()):
            diffs.append("max_board_count_market")
        if actual_first != expected_first:
            diffs.append("first_board_codes")
        if actual_leaders != expected_leaders:
            diffs.append("leader_codes")
        rows.append({"date": int(date_int), "status": "ok" if not diffs else ",".join(diffs)})

    out = pd.DataFrame(rows)
    counts = out["status"].value_counts(dropna=False)
    print(counts.to_string())
    bad = out[out["status"] != "ok"]
    if not bad.empty:
        print(bad.head(20).to_string(index=False))
        raise SystemExit(1)
    print(f"validated {args.year}: {len(out)} days")


if __name__ == "__main__":
    main()
