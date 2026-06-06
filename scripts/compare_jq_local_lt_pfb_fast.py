import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
HDATA_ROOT = Path(r"D:\work space\hdata")
sys.path.insert(0, str(HDATA_ROOT))

from scripts.core import hdata_reader  # noqa: E402


def parse_codes(text):
    if pd.isna(text) or text == "":
        return set()
    return {x for x in str(text).split("|") if x}


def date_int(x):
    return int(str(x).replace("-", "")[:8])


def jq_code(hd_code):
    return hdata_reader.hdata_to_jq_code(hd_code)


def valid_universe_by_prev(stock_basic, prev):
    prev_i = date_int(prev)
    df = stock_basic
    list_i = pd.to_numeric(df["list_date"], errors="coerce").fillna(19000101).astype(int)
    delist_i = pd.to_numeric(df["delist_date"], errors="coerce").fillna(22000101).astype(int)
    mask = (list_i <= prev_i) & (delist_i > prev_i)
    codes = df.loc[mask, "code"].tolist()
    out = []
    for c in codes:
        j = jq_code(c)
        if j.startswith("688") or j.startswith("8"):
            continue
        out.append(c)
    return out


def summarize_diff(jq_set, local_set):
    both = jq_set & local_set
    jq_only = sorted(jq_set - local_set)
    local_only = sorted(local_set - jq_set)
    union_n = len(jq_set | local_set)
    return {
        "jq_n": len(jq_set),
        "local_n": len(local_set),
        "both_n": len(both),
        "jq_only_n": len(jq_only),
        "local_only_n": len(local_only),
        "jaccard": len(both) / union_n if union_n else 1.0,
        "jq_only": "|".join(jq_only),
        "local_only": "|".join(local_only),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--jq-csv", default=str(ROOT / "jq_lt_pfb_master_consistent_v2_2020.csv"))
    ap.add_argument("--out", default=str(ROOT / "compare_jq_local_lt_pfb_v2_2020_fast.csv"))
    ap.add_argument("--start", default=None)
    ap.add_argument("--end", default=None)
    ap.add_argument("--tol", type=float, default=None)
    args = ap.parse_args()

    jq_df = pd.read_csv(args.jq_csv, dtype={"date": str, "prev_date": str, "kind": str})
    jq_df["tol"] = jq_df["tol"].astype(float).round(2)
    if args.start:
        jq_df = jq_df[jq_df["date"] >= args.start]
    if args.end:
        jq_df = jq_df[jq_df["date"] <= args.end]
    if args.tol is not None:
        jq_df = jq_df[jq_df["tol"] == round(args.tol, 2)]
    if jq_df.empty:
        raise SystemExit("No rows after filters")

    years = sorted({date_int(x) // 10000 for x in jq_df["date"]} | {date_int(x) // 10000 for x in jq_df["prev_date"]})
    hdata_reader._update_pivot_cache(set(years), fields_needed={"close", "high_limit"})
    close = hdata_reader._PIVOT_CACHE["close"].sort_index()
    high_limit = hdata_reader._PIVOT_CACHE["high_limit"].sort_index()
    stock_basic = hdata_reader.load_stock_basic().copy()

    by_key = {}
    for row in jq_df.itertuples(index=False):
        by_key[(row.date, row.prev_date, float(row.tol), row.kind)] = parse_codes(row.codes)

    rows = []
    cache = {}
    keys = sorted({(r.date, r.prev_date, float(r.tol)) for r in jq_df.itertuples(index=False)})
    all_dates = close.index.tolist()
    date_pos = {int(d): i for i, d in enumerate(all_dates)}

    for idx, (day, prev, tol) in enumerate(keys, 1):
        prev_i = date_int(prev)
        ck = (prev_i, tol)
        if ck not in cache:
            if prev_i not in date_pos or date_pos[prev_i] < 1:
                lt_set, pfb_set = set(), set()
            else:
                universe_hd = valid_universe_by_prev(stock_basic, prev)
                c0 = close.loc[prev_i, universe_hd]
                h0 = high_limit.loc[prev_i, universe_hd]
                prev2_i = int(all_dates[date_pos[prev_i] - 1])
                c1 = close.loc[prev2_i, universe_hd]
                h1 = high_limit.loc[prev2_i, universe_hd]

                is_limit = (h0 > 0) & np.isfinite(h0) & np.isfinite(c0) & ((c0 - h0).abs() <= tol)
                prev_limit = (h1 > 0) & np.isfinite(h1) & np.isfinite(c1) & ((c1 - h1).abs() <= tol)
                lt_hd = list(is_limit[is_limit].index)
                pfb_hd = list((is_limit & ~prev_limit)[is_limit & ~prev_limit].index)
                lt_set = {jq_code(c) for c in lt_hd}
                pfb_set = {jq_code(c) for c in pfb_hd}
            cache[ck] = {"LT": lt_set, "PFB": pfb_set}

        for kind in ("LT", "PFB"):
            jq_set = by_key.get((day, prev, tol, kind), set())
            local_set = cache[ck][kind]
            d = summarize_diff(jq_set, local_set)
            d.update({"date": day, "prev_date": prev, "tol": tol, "kind": kind})
            rows.append(d)
        if idx % 100 == 0:
            print(f"progress {idx}/{len(keys)} {day} tol={tol}")

    out_df = pd.DataFrame(rows)
    cols = [
        "date", "prev_date", "tol", "kind",
        "jq_n", "local_n", "both_n", "jq_only_n", "local_only_n", "jaccard",
        "jq_only", "local_only",
    ]
    out_df = out_df[cols]
    out_df.to_csv(args.out, index=False, encoding="utf-8-sig")

    print("saved", args.out)
    print(out_df.groupby(["tol", "kind"])[["jq_only_n", "local_only_n", "jaccard"]].agg(["mean", "max", "min"]).to_string())
    worst = out_df.sort_values(["jq_only_n", "local_only_n"], ascending=False).head(20)
    print("worst")
    print(worst[["date", "prev_date", "tol", "kind", "jq_n", "local_n", "jq_only_n", "local_only_n", "jaccard"]].to_string(index=False))


if __name__ == "__main__":
    main()
