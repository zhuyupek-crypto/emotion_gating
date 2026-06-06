from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd


PROJECT = Path(__file__).resolve().parents[1]
HDATA_PROJECT = Path(r"D:\work space\hdata")
sys.path.insert(0, str(PROJECT / "scripts"))
sys.path.insert(0, str(HDATA_PROJECT))

from scripts.core import hdata_reader  # type: ignore  # noqa: E402
import v227_yjj_probe as probe  # noqa: E402


def code_set(text: object) -> set[str]:
    if pd.isna(text):
        return set()
    return {p.strip() for p in str(text).replace("|", ",").split(",") if p.strip()}


def active_universe(prev: str, basic: pd.DataFrame) -> list[str]:
    df = basic.copy()
    df["list_date"] = df["list_date"].astype(str).str.replace("-", "", regex=False)
    delist = df["delist_date"].fillna("").astype(str).replace({"nan": "", "NaN": "", "NaT": "", "None": ""})
    delist = delist.str.replace("-", "", regex=False)
    mask = df["list_date"].le(prev) & ((delist == "") | delist.gt(prev))
    codes = df.loc[mask, "code"].astype(str)
    codes = codes[~codes.str.startswith("688") & ~codes.str.startswith("8") & ~codes.str.startswith("92")]
    return [hdata_reader.hdata_to_jq_code(c) for c in codes.tolist()]


def _row_frame(close: pd.DataFrame, pre_close: pd.DataFrame, row_idx: int) -> pd.DataFrame:
    date = str(close.index[row_idx])
    df = pd.DataFrame({
        "close": close.iloc[row_idx],
        "pre_close": pre_close.iloc[row_idx],
    })
    df = df.dropna(subset=["close", "pre_close"]).copy()
    df.index = [probe.local_code(c) for c in df.index]
    df["date"] = date
    return df


def high_limit_history_panel(prev: str, universe_jq: list[str], st_by_day: dict[str, set[str]], count: int = 3) -> pd.DataFrame:
    try:
        return hdata_reader.history(
            count, field="high_limit", security_list=universe_jq, df=True,
            skip_paused=False, fq=None, end_date=prev,
        )
    except Exception:
        pass

    cal = hdata_reader.load_calendar()["date"].astype(str).tolist()
    cal = sorted(cal)
    end_idx = cal.index(prev)
    start_idx = max(0, end_idx - count + 1)
    buffer_start_idx = max(0, start_idx - 40)
    full_dates = cal[buffer_start_idx:end_idx + 1]
    target_dates = cal[start_idx:end_idx + 1]
    hd_codes = [hdata_reader.clean_code_to_hdata(c) for c in universe_jq]
    raw = hdata_reader.load_1d(
        start=full_dates[0], end=prev, codes=hd_codes,
        columns=["code", "date", "pre_close"],
    )
    if raw.empty:
        return pd.DataFrame()
    raw["date"] = raw["date"].astype(str)
    parts = []
    for d, g in raw.groupby("date", sort=False):
        idx = g["code"].astype(str)
        pc = pd.Series(g["pre_close"].astype(float).to_numpy(), index=idx)
        hl = probe.high_limit_series(pc, st_by_day.get(d, set()), trade_date=d)
        parts.append(pd.DataFrame({"code": idx.to_numpy(), "date": d, "high_limit": hl.to_numpy()}))
    traded_hl = pd.concat(parts, ignore_index=True)
    grid = pd.DataFrame([(c, d) for c in hd_codes for d in full_dates], columns=["code", "date"])
    merged = grid.merge(traded_hl, on=["code", "date"], how="left")
    merged = merged.sort_values(["code", "date"])
    merged["high_limit"] = merged.groupby("code")["high_limit"].ffill().bfill()
    merged = merged[merged["date"].isin(target_dates)]
    merged["code"] = merged["code"].map(hdata_reader.hdata_to_jq_code)
    return merged.pivot(index="date", columns="code", values="high_limit")


def pfb_by_history(prev: str, universe_jq: list[str], st_by_day: dict[str, set[str]], tol: float) -> list[str]:
    close = hdata_reader.history(
        3, field="close", security_list=universe_jq, df=True,
        skip_paused=False, fq=None, end_date=prev,
    )
    high_limit = high_limit_history_panel(prev, universe_jq, st_by_day, count=3)
    if close.empty or len(close) < 2:
        return []
    common_cols = close.columns.intersection(high_limit.columns)
    close = close[common_cols]
    high_limit = high_limit[common_cols]
    common = pd.Index([probe.local_code(c) for c in common_cols])
    if len(common) == 0:
        return []
    valid = close.iloc[-1].notna() & close.iloc[-2].notna() & high_limit.iloc[-1].notna() & high_limit.iloc[-2].notna()
    close = close.loc[:, valid]
    high_limit = high_limit.loc[:, valid]
    common = pd.Index([probe.local_code(c) for c in close.columns])
    c1 = np.rint(close.iloc[-1].astype(float).to_numpy() * 100).astype(np.int64)
    c2 = np.rint(close.iloc[-2].astype(float).to_numpy() * 100).astype(np.int64)
    hl1 = np.rint(high_limit.iloc[-1].astype(float).to_numpy() * 100).astype(np.int64)
    hl2 = np.rint(high_limit.iloc[-2].astype(float).to_numpy() * 100).astype(np.int64)
    tol_cents = int(round(tol * 100))
    mask = (np.abs(c1 - hl1) <= tol_cents) & ~(np.abs(c2 - hl2) <= tol_cents)
    return [probe.jq_code(c) for c in common[mask]]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--jq-pfb", type=Path, default=PROJECT / "jq_sm_force_v227_2020_pfb.csv")
    ap.add_argument("--limit", type=int, default=20)
    ap.add_argument("--out", type=Path, default=PROJECT / "history_pfb_compare.csv")
    ap.add_argument("--tol", type=float, default=0.02)
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    jq = pd.read_csv(args.jq_pfb)
    jq["date"] = jq["dt"].astype(str).str.slice(0, 8)
    jq = jq.drop_duplicates("date", keep="last").head(args.limit)

    basic = hdata_reader.load_stock_basic()
    cal = hdata_reader.load_calendar()
    trade_dates = sorted(cal["date"].astype(str).tolist())
    years = sorted({int(str(d)[:4]) for d in trade_dates if "2019" <= str(d)[:4] <= "2020"})
    st = probe.fill_st_calendar(probe.load_st(years), trade_dates)

    rows = []
    for _, r in jq.iterrows():
        today = r["date"]
        prevs = [d for d in trade_dates if d < today]
        if not prevs:
            continue
        prev = prevs[-1]
        universe = active_universe(prev, basic)
        local = set(pfb_by_history(prev, universe, st, args.tol))
        jq_set = code_set(r["codes"])
        jq_n = int(r["n"])
        jq_only = sorted(jq_set - local)
        local_only = sorted(local - jq_set)
        rows.append({
            "date": today,
            "prev": prev,
            "jq_n": jq_n,
            "jq_listed_n": len(jq_set),
            "local_n": len(local),
            "jq_only_n": len(jq_only),
            "local_only_n": len(local_only),
            "jq_only": "|".join(jq_only[:80]),
            "local_only": "|".join(local_only[:80]),
        })
        if not args.quiet:
            print(f"{today} prev={prev} jq={jq_n} listed={len(jq_set)} local={len(local)} jq_only={len(jq_only)} local_only={len(local_only)}")
        if not args.quiet and (jq_only or local_only):
            print("  JQ_ONLY=" + "|".join(jq_only[:30]))
            print("  LOCAL_ONLY=" + "|".join(local_only[:30]))

    pd.DataFrame(rows).to_csv(args.out, index=False, encoding="utf-8-sig")
    print(f"WROTE {args.out}")


if __name__ == "__main__":
    main()
