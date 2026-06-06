import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
HDATA_ROOT = Path(r"D:\work space\hdata")
sys.path.insert(0, str(HDATA_ROOT))

from scripts.core import local_jq as jq  # noqa: E402


def parse_codes(text):
    if pd.isna(text) or text == "":
        return set()
    return {x for x in str(text).split("|") if x}


def prev_trade_day(day):
    ds = [str(x) for x in jq.get_trade_days(end_date=day, count=3)]
    return ds[-2] if ds[-1] == day else ds[-1]


def scan_local(day, prev, tol):
    all_stocks = list(jq.get_all_securities(["stock"], date=prev).index)
    all_stocks = [s for s in all_stocks if not s.startswith("688") and not s.startswith("8")]
    high_limits = jq.history(3, field="high_limit", security_list=all_stocks, df=False, fq=None, end_date=prev)
    closes_raw = jq.history(3, field="close", security_list=all_stocks, df=False, fq=None, end_date=prev)
    lt = []
    pfb = []
    for s in all_stocks:
        hl = high_limits.get(s)
        cr = closes_raw.get(s)
        if hl is None or cr is None or len(hl) < 3 or len(cr) < 3:
            continue
        try:
            h0, c0 = float(hl[-1]), float(cr[-1])
            h1, c1 = float(hl[-2]), float(cr[-2])
        except Exception:
            continue
        if not (np.isfinite(h0) and np.isfinite(c0)):
            continue
        is_limit = h0 > 0 and abs(c0 - h0) <= tol
        if not is_limit:
            continue
        lt.append(s)
        prev_limit = np.isfinite(h1) and np.isfinite(c1) and h1 > 0 and abs(c1 - h1) <= tol
        if not prev_limit:
            pfb.append(s)
    return {"LT": set(lt), "PFB": set(pfb)}


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
    ap.add_argument("--jq-csv", default=str(ROOT / "jq_lt_pfb_master_consistent.csv"))
    ap.add_argument("--out", default=str(ROOT / "compare_jq_local_lt_pfb.csv"))
    ap.add_argument("--start", default=None)
    ap.add_argument("--end", default=None)
    ap.add_argument("--tol", type=float, default=None)
    ap.add_argument("--no-preload", action="store_true")
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

    if not args.no_preload:
        years = sorted({int(str(x)[:4]) for x in jq_df["date"]} | {int(str(x)[:4]) for x in jq_df["prev_date"]})
        jq.preload_years(years, fields=["close", "high_limit"])

    by_key = {}
    for row in jq_df.itertuples(index=False):
        by_key[(row.date, row.prev_date, float(row.tol), row.kind)] = parse_codes(row.codes)

    rows = []
    day_tol_pairs = sorted({(r.date, r.prev_date, float(r.tol)) for r in jq_df.itertuples(index=False)})
    for i, (day, prev, tol) in enumerate(day_tol_pairs, 1):
        local_sets = scan_local(day, prev, tol)
        for kind in ("LT", "PFB"):
            jq_set = by_key.get((day, prev, tol, kind), set())
            d = summarize_diff(jq_set, local_sets[kind])
            d.update({"date": day, "prev_date": prev, "tol": tol, "kind": kind})
            rows.append(d)
        if i % 50 == 0:
            print(f"progress {i}/{len(day_tol_pairs)} {day} tol={tol}")

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
