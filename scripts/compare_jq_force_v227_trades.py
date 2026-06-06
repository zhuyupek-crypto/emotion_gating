"""Compare JoinQuant copied transaction history with local v227 trade CSV.

Usage:
  python scripts/compare_jq_force_v227_trades.py \
    --jq-raw jq_force_v227_2022_raw.txt \
    --local tmp_v227_full_2022_force_v227_finalrules_trades.csv \
    --out-prefix compare_v227_2022

The JoinQuant input can be the copied transaction-history text from the web UI,
including blank separator rows. Only buy/sell rows are parsed.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import pandas as pd


JQ_CODE_RE = re.compile(r"\((\d{6}\.XS(?:HG|HE))\)")
DATE_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})\s+(\d{2}):(\d{2}):(\d{2})")


def parse_jq_raw(path: Path) -> pd.DataFrame:
    rows: list[dict] = []
    for raw_line in path.read_text(encoding="utf-8-sig", errors="ignore").splitlines():
        line = raw_line.strip()
        if not line or "市价单" not in line:
            continue
        m_date = DATE_RE.match(line)
        m_code = JQ_CODE_RE.search(line)
        if not m_date or not m_code:
            continue

        parts = re.split(r"\s+", line)
        if len(parts) < 8:
            continue

        side = "buy" if "买" in parts else "sell" if "卖" in parts else ""
        if not side:
            continue

        shares = None
        price = None
        amount = None
        for token in parts:
            if token.endswith("股"):
                try:
                    shares = int(token[:-1].replace(",", ""))
                except ValueError:
                    pass
            elif price is None:
                try:
                    price = float(token.replace(",", ""))
                except ValueError:
                    pass

        # The first numeric token in a JQ row is sometimes not the price
        # depending on copy formatting, so locate the market-order token and
        # parse the two following numeric fields when possible.
        if "市价单" in parts:
            i = parts.index("市价单")
            if i + 2 < len(parts):
                try:
                    shares = int(parts[i + 1].rstrip("股").replace(",", ""))
                    price = float(parts[i + 2].replace(",", ""))
                except ValueError:
                    pass
            if i + 3 < len(parts):
                try:
                    amount = abs(float(parts[i + 3].replace(",", "")))
                except ValueError:
                    pass

        y, mo, d, hh, mm, ss = m_date.groups()
        rows.append(
            {
                "date": f"{y}{mo}{d}",
                "time": f"{hh}:{mm}:{ss}",
                "code": m_code.group(1),
                "side": side,
                "price": price,
                "shares": abs(shares) if shares is not None else None,
                "amount": amount,
                "raw": raw_line,
            }
        )

    df = pd.DataFrame(rows)
    if df.empty:
        return pd.DataFrame(columns=["date", "time", "code", "side", "price", "shares", "amount", "raw"])
    return df.sort_values(["date", "time", "side", "code"]).reset_index(drop=True)


def normalize_local(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, dtype={"date": str})
    df["time"] = ""
    df["price"] = df["price"].astype(float)
    df["shares"] = df["shares"].abs().astype(int)
    keep = ["date", "time", "code", "side", "price", "shares", "reason"]
    return df[keep].sort_values(["date", "side", "code"]).reset_index(drop=True)


def compare(jq: pd.DataFrame, local: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    key = ["date", "side", "code"]
    jq_keyed = jq.copy()
    local_keyed = local.copy()
    jq_keyed["_jq_n"] = jq_keyed.groupby(key).cumcount()
    local_keyed["_local_n"] = local_keyed.groupby(key).cumcount()
    full_key = key + ["_jq_n"]
    local_keyed = local_keyed.rename(columns={"_local_n": "_jq_n"})

    joined = jq_keyed.merge(local_keyed, on=full_key, how="outer", suffixes=("_jq", "_local"), indicator=True)
    jq_only = joined[joined["_merge"].eq("left_only")].copy()
    local_only = joined[joined["_merge"].eq("right_only")].copy()
    both = joined[joined["_merge"].eq("both")].copy()

    both["price_diff"] = both["price_local"] - both["price_jq"]
    both["price_diff_abs"] = both["price_diff"].abs()
    both["shares_diff"] = both["shares_local"] - both["shares_jq"]
    price_or_size_diff = both[(both["price_diff_abs"] > 0.011) | (both["shares_diff"].abs() > 0)].copy()
    return jq_only, local_only, price_or_size_diff


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--jq-raw", required=True, type=Path)
    parser.add_argument("--local", required=True, type=Path)
    parser.add_argument("--out-prefix", default="compare_v227")
    args = parser.parse_args()

    jq = parse_jq_raw(args.jq_raw)
    local = normalize_local(args.local)
    jq_csv = Path(f"{args.out_prefix}_jq_parsed.csv")
    jq.to_csv(jq_csv, index=False, encoding="utf-8-sig")

    jq_only, local_only, diffs = compare(jq, local)
    jq_only.to_csv(f"{args.out_prefix}_jq_only.csv", index=False, encoding="utf-8-sig")
    local_only.to_csv(f"{args.out_prefix}_local_only.csv", index=False, encoding="utf-8-sig")
    diffs.to_csv(f"{args.out_prefix}_price_or_size_diff.csv", index=False, encoding="utf-8-sig")

    print(f"JQ parsed rows: {len(jq)} -> {jq_csv}")
    print(f"Local rows: {len(local)}")
    print(f"JQ only: {len(jq_only)}")
    print(f"Local only: {len(local_only)}")
    print(f"Price/share diffs among matched keys: {len(diffs)}")
    if len(jq_only):
        print("\nJQ only head:")
        print(jq_only[["date", "side", "code", "time_jq", "price_jq", "shares_jq"]].head(30).to_string(index=False))
    if len(local_only):
        print("\nLocal only head:")
        print(local_only[["date", "side", "code", "price_local", "shares_local", "reason"]].head(30).to_string(index=False))
    if len(diffs):
        print("\nMatched key price/share diff head:")
        cols = ["date", "side", "code", "price_jq", "price_local", "price_diff", "shares_jq", "shares_local", "shares_diff", "reason"]
        print(diffs[cols].head(30).to_string(index=False))


if __name__ == "__main__":
    main()
