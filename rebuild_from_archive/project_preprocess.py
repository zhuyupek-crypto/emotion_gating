from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_HDATA_ROOT = Path(r"D:\work space\hdata\data\processed")
DEFAULT_CACHE_ROOT = PROJECT_ROOT / "project_cache" / "features"


def _jq_code(code: str) -> str:
    if code.endswith(".SZ"):
        return code[:-3] + ".XSHE"
    if code.endswith(".SH"):
        return code[:-3] + ".XSHG"
    if code.endswith(".BJ"):
        return code[:-3] + ".XBSE"
    return code


def _load_pivot(hdata_root: Path, year: int, field: str) -> pd.DataFrame:
    path = hdata_root / "pivot_cache" / str(year) / f"{field}.parquet"
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_parquet(path)


def _load_pivot_with_prev(hdata_root: Path, year: int, field: str, prev_tail: int = 110) -> pd.DataFrame:
    frames = []
    prev_path = hdata_root / "pivot_cache" / str(year - 1) / f"{field}.parquet"
    if prev_path.exists():
        frames.append(pd.read_parquet(prev_path).tail(prev_tail))
    frames.append(_load_pivot(hdata_root, year, field))
    return pd.concat(frames).sort_index()


def build_board_snapshot(year: int, hdata_root: Path = DEFAULT_HDATA_ROOT, cache_root: Path = DEFAULT_CACHE_ROOT) -> Path:
    hdata_root = Path(hdata_root)
    cache_root = Path(cache_root)
    fields = {}
    for field in ["close", "high_limit", "open", "high", "low", "money", "volume"]:
        frames = []
        prev_path = hdata_root / "pivot_cache" / str(year - 1) / f"{field}.parquet"
        if prev_path.exists():
            frames.append(pd.read_parquet(prev_path).tail(3))
        frames.append(_load_pivot(hdata_root, year, field))
        fields[field] = pd.concat(frames).sort_index()

    close = fields["close"]
    high_limit = fields["high_limit"]
    open_ = fields["open"]
    high = fields["high"]
    low = fields["low"]
    money = fields["money"]
    volume = fields["volume"]

    close_cmp = close.astype(float).round(4)
    high_limit_cmp = high_limit.astype(float).round(4)
    limit_up = (close_cmp - high_limit_cmp).abs().le(0.02) & high_limit_cmp.gt(0)
    run_arr = np.zeros(limit_up.shape[1], dtype=np.int16)
    board_rows = []
    for idx in close.index:
        cur = limit_up.loc[idx].fillna(False).to_numpy(dtype=bool)
        run_arr = np.where(cur, np.minimum(run_arr + 1, 3), 0).astype(np.int16)
        board_rows.append(run_arr.copy())
    board_count = pd.DataFrame(board_rows, index=close.index, columns=close.columns, dtype=np.int16)
    first_board = board_count.eq(1)
    max_board = board_count.max(axis=1).astype(np.int16)

    rows = []
    target_dates = [idx for idx in close.index if int(str(idx)[:4]) == year]
    for dt in target_dates:
        mask = limit_up.loc[dt].fillna(False)
        if not mask.any():
            continue
        codes = mask[mask].index.tolist()
        out = pd.DataFrame(
            {
                "date": int(dt),
                "code": [_jq_code(c) for c in codes],
                "is_limit_up_close": True,
                "board_count": board_count.loc[dt, codes].astype(np.int16).to_numpy(),
                "is_first_board": first_board.loc[dt, codes].astype(bool).to_numpy(),
                "max_board_count_market": int(max_board.loc[dt]),
                "prev_close": (close.loc[dt, codes] / 1.1).astype(float).to_numpy(),
                "open": open_.loc[dt, codes].astype(float).to_numpy(),
                "close": close.loc[dt, codes].astype(float).to_numpy(),
                "high": high.loc[dt, codes].astype(float).to_numpy(),
                "low": low.loc[dt, codes].astype(float).to_numpy(),
                "money": money.loc[dt, codes].astype(float).to_numpy(),
                "volume": volume.loc[dt, codes].astype(float).to_numpy(),
            }
        )
        out["avg_chg"] = np.where(
            (out["volume"] > 0) & (out["close"] > 0),
            out["money"] / out["volume"] / out["close"] * 1.1 - 1,
            np.nan,
        )
        rows.append(out)

    result = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()
    out_dir = cache_root / "board_snapshot"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{year}.parquet"
    result.to_parquet(out_path, index=False)
    return out_path


def build_first_seal_time(year: int, hdata_root: Path = DEFAULT_HDATA_ROOT, cache_root: Path = DEFAULT_CACHE_ROOT, compat=None) -> Path:
    hdata_root = Path(hdata_root)
    cache_root = Path(cache_root)
    board_path = cache_root / "board_snapshot" / f"{year}.parquet"
    if not board_path.exists():
        build_board_snapshot(year, hdata_root, cache_root)
    boards = pd.read_parquet(board_path)
    first_boards = boards[boards["is_first_board"]].copy()
    if first_boards.empty:
        result = pd.DataFrame(columns=["date", "code", "first_limit_hit_time", "seal_bucket", "is_tail_seal"])
    else:
        high_limit = _load_pivot(hdata_root, year, "high_limit")
        rows = []
        for row in first_boards.itertuples(index=False):
            code = row.code
            local = code.replace(".XSHE", ".SZ").replace(".XSHG", ".SH").replace(".XBSE", ".BJ")
            date_int = int(row.date)
            limit_price = float(high_limit.loc[date_int, local]) if local in high_limit.columns else np.nan
            hit_time = None
            if compat is None:
                from rebuild_from_archive.project_compat import EmotionGateJQCompat
                compat = EmotionGateJQCompat(PROJECT_ROOT)
            override = (
                compat.get_tail_seal_override(f"{date_int:08d}", code)
                if compat is not None and hasattr(compat, "get_tail_seal_override")
                else None
            )
            if override is not None:
                hit_time = str(override)
            elif np.isfinite(limit_price) and limit_price > 0:
                min_path = hdata_root / "1m_stock" / local / f"{year}.parquet"
                if min_path.exists():
                    try:
                        df = pd.read_parquet(min_path, columns=["date", "trade_time", "close"], filters=[("date", "=", str(date_int))])
                    except Exception:
                        df = pd.read_parquet(min_path, columns=["date", "trade_time", "close"])
                        df = df[df["date"].astype(str) == str(date_int)]
                    if not df.empty:
                        hit = df[df["close"].astype(float) >= limit_price - 1e-6]
                        if not hit.empty:
                            hit_time = str(hit.iloc[0]["trade_time"])
            if hit_time is None:
                bucket = "none"
                is_tail = False
            else:
                ts = pd.to_datetime(hit_time)
                if ts.hour < 10:
                    bucket = "early"
                elif ts.hour < 14:
                    bucket = "mid"
                else:
                    bucket = "tail"
                is_tail = ts.hour >= 14
            rows.append(
                {
                    "date": date_int,
                    "code": code,
                    "first_limit_hit_time": hit_time,
                    "seal_bucket": bucket,
                    "is_tail_seal": is_tail,
                }
            )
        result = pd.DataFrame(rows)

    out_dir = cache_root / "first_seal_time"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{year}.parquet"
    result.to_parquet(out_path, index=False)
    return out_path


def build_call_auction_by_date(year: int, hdata_root: Path = DEFAULT_HDATA_ROOT, cache_root: Path = DEFAULT_CACHE_ROOT) -> Path:
    hdata_root = Path(hdata_root)
    cache_root = Path(cache_root)
    src_path = hdata_root / "1d_feature" / "call_auction" / f"{year}.parquet"
    out_dir = cache_root / "call_auction_by_date" / str(year)
    out_dir.mkdir(parents=True, exist_ok=True)
    if not src_path.exists():
        return out_dir

    df = pd.read_parquet(src_path)
    if df.empty or "date" not in df.columns:
        return out_dir
    if "code" in df.columns:
        df = df.copy()
        df["code"] = df["code"].astype(str).map(_jq_code)
    df["_date_key"] = df["date"].astype(str).str.replace("-", "", regex=False).str[:8]
    for date_key, sub in df.groupby("_date_key", sort=True):
        if not date_key:
            continue
        out = sub.drop(columns=["_date_key"]).reset_index(drop=True)
        out.to_parquet(out_dir / f"{date_key}.parquet", index=False)
    return out_dir


def build_master_prepare_index(year: int, hdata_root: Path = DEFAULT_HDATA_ROOT, cache_root: Path = DEFAULT_CACHE_ROOT) -> Path:
    """Build a compact daily index for the mother strategy prepare phase.

    This is intentionally narrower than a full strategy feature table.  It
    caches the market-wide board facts that `_scan_all` and
    `_scan_boards_for_prev` recompute every morning, while leaving candidate
    ranking and JQ compatibility behavior in the strategy/engine until parity
    checks prove a wider replacement is safe.
    """
    cache_root = Path(cache_root)
    board_path = cache_root / "board_snapshot" / f"{year}.parquet"
    if not board_path.exists():
        build_board_snapshot(year, hdata_root, cache_root)

    boards = pd.read_parquet(board_path)
    if boards.empty:
        result = pd.DataFrame(
            columns=[
                "date",
                "limit_up_close_n",
                "first_board_n",
                "max_board_count_market",
                "first_board_codes",
                "leader_codes",
            ]
        )
    else:
        rows = []
        for date_int, sub in boards.groupby("date", sort=True):
            first = sub[sub["is_first_board"]].copy()
            leaders = sub[sub["board_count"].astype(int) >= 3].copy()
            first_codes = "|".join(first["code"].astype(str).sort_values().tolist())
            leader_parts = []
            for row in leaders.sort_values(["board_count", "code"], ascending=[False, True]).itertuples(index=False):
                leader_parts.append(f"{row.code}:{int(row.board_count)}")
            rows.append(
                {
                    "date": int(date_int),
                    "limit_up_close_n": int(len(sub)),
                    "first_board_n": int(len(first)),
                    "max_board_count_market": int(sub["max_board_count_market"].max()),
                    "first_board_codes": first_codes,
                    "leader_codes": "|".join(leader_parts),
                }
            )
        result = pd.DataFrame(rows)

    out_dir = cache_root / "master_prepare_index"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{year}.parquet"
    result.to_parquet(out_path, index=False)
    return out_path


def _auction_yiqian_batch_left_pressure_api(api, candidates: list[str], previous_date: pd.Timestamp) -> dict[str, bool]:
    result = {}
    if not candidates:
        return result
    try:
        df = api.get_price(
            candidates,
            count=101,
            end_date=previous_date,
            frequency="daily",
            fields=["high", "volume"],
            panel=False,
            fill_paused=False,
        )
    except Exception:
        return result
    if df is None or df.empty:
        return result
    if "time" not in df.columns:
        df = df.reset_index()
    for code, sub in df.groupby("code"):
        sub = sub.sort_values("time").dropna(subset=["high", "volume"])
        if len(sub) < 20:
            result[code] = False
            continue
        highs = list(sub["high"].iloc[-101:])
        vols_all = list(sub["volume"].iloc[-101:])
        prev_high = highs[-1]
        zyts_0 = 100
        for offset, high in enumerate(reversed(highs[:-2]), 2):
            if high >= prev_high:
                zyts_0 = offset - 1
                break
        zyts = zyts_0 + 5
        vols = vols_all[-zyts:]
        if len(vols) < 2:
            result[code] = False
            continue
        result[code] = bool(vols[-1] > max(vols[:-1]) * 0.9)
    return result


def _auction_yiqian_batch_left_pressure_pivots(
    high: pd.DataFrame,
    volume: pd.DataFrame,
    date_pos: dict[int, int],
    previous_date_int: int,
    candidates: list[str],
) -> dict[str, bool]:
    result = {}
    if not candidates or previous_date_int not in date_pos:
        return result
    prev_pos = date_pos[previous_date_int]
    start_pos = max(0, prev_pos - 100)
    for code in candidates:
        if code not in high.columns or code not in volume.columns:
            result[code] = False
            continue
        sub = pd.DataFrame(
            {
                "high": high[code].iloc[start_pos : prev_pos + 1],
                "volume": volume[code].iloc[start_pos : prev_pos + 1],
            }
        ).dropna()
        if len(sub) < 20:
            result[code] = False
            continue
        highs = list(sub["high"].astype(float).iloc[-101:])
        vols_all = list(sub["volume"].astype(float).iloc[-101:])
        prev_high = highs[-1]
        zyts_0 = 100
        for offset, high_val in enumerate(reversed(highs[:-2]), 2):
            if high_val >= prev_high:
                zyts_0 = offset - 1
                break
        zyts = zyts_0 + 5
        vols = vols_all[-zyts:]
        if len(vols) < 2:
            result[code] = False
            continue
        result[code] = bool(vols[-1] > max(vols[:-1]) * 0.9)
    return result


def build_auction_yiqian_prepare(
    year: int,
    hdata_root: Path = DEFAULT_HDATA_ROOT,
    cache_root: Path = DEFAULT_CACHE_ROOT,
    ipo_days: int = 250,
    candidate_cap: int = 40,
) -> Path:
    """Build daily cache for mother `_auction_yiqian_prepare`.

    The cache is not consumed by the strategy yet.  It is a validation target:
    compare it against the live prepare function before enabling any fast path.
    """
    hdata_root = Path(hdata_root)
    cache_root = Path(cache_root)

    engine_root = PROJECT_ROOT / "rebuild_from_archive"
    if str(engine_root) not in sys.path:
        sys.path.insert(0, str(engine_root))
    from engine.data_api import DataAPI

    try:
        from project_compat import EmotionGateJQCompat
        compat = EmotionGateJQCompat(PROJECT_ROOT)
    except Exception:
        compat = None
    api = DataAPI(str(hdata_root), compat=compat)
    fields = {
        field: _load_pivot_with_prev(hdata_root, year, field, prev_tail=110)
        for field in ["open", "close", "high", "high_limit", "money", "volume"]
    }
    for frame in fields.values():
        frame.columns = [_jq_code(str(c)) for c in frame.columns]
    open_ = fields["open"]
    close = fields["close"]
    high = fields["high"]
    high_limit = fields["high_limit"]
    money = fields["money"]
    volume = fields["volume"]
    dates = list(close.index)
    date_pos = {int(d): i for i, d in enumerate(dates)}
    target_dates = [int(d) for d in dates if int(str(d)[:4]) == year]

    rows = []
    for date_int in target_dates:
        pos = date_pos[date_int]
        if pos < 4:
            continue
        prev_date_int = int(dates[pos - 1])
        curr_date = pd.to_datetime(str(date_int))
        prev_date = pd.to_datetime(str(prev_date_int))

        secs = api.get_all_securities(["stock"], date=prev_date)
        if secs is None or secs.empty:
            continue
        codes = secs.index.astype(str)
        mask_code = codes.str.startswith("60") | codes.str.startswith("00")
        mask_name = ~secs["display_name"].astype(str).str.contains(r"ST|st|\*|退", regex=True, na=True)
        start_dates = pd.to_datetime(secs["start_date"], errors="coerce")
        mask_ipo = (curr_date - start_dates).dt.days >= ipo_days
        pool_jq = list(secs[mask_code & mask_name & mask_ipo].index.astype(str))
        if not pool_jq:
            continue

        pool_jq = [code for code in pool_jq if code in close.columns]
        if not pool_jq:
            continue
        open1 = open_.iloc[pos - 1][pool_jq]
        close1 = close.iloc[pos - 1][pool_jq]
        high1 = high.iloc[pos - 1][pool_jq]
        high_limit1 = high_limit.iloc[pos - 1][pool_jq]
        money1 = money.iloc[pos - 1][pool_jq]
        volume1 = volume.iloc[pos - 1][pool_jq]
        close2 = close.iloc[pos - 2][pool_jq]
        high2 = high.iloc[pos - 2][pool_jq]
        high_limit2 = high_limit.iloc[pos - 2][pool_jq]
        high3 = high.iloc[pos - 3][pool_jq]
        high_limit3 = high_limit.iloc[pos - 3][pool_jq]
        close4 = close.iloc[pos - 4][pool_jq]

        valid_mask = (
            (high_limit1 > 0) & (close1 > 0) & (open1 > 0) &
            (volume1 > 0) & (close4 > 0) &
            high_limit1.notna() & close1.notna() & open1.notna() &
            volume1.notna() & close4.notna() &
            close2.notna() & high2.notna() & high_limit2.notna() &
            high3.notna() & high_limit3.notna()
        )
        valid_codes = list(valid_mask[valid_mask].index)
        if not valid_codes:
            continue

        open1 = open1[valid_codes]
        close1 = close1[valid_codes]
        high1 = high1[valid_codes]
        high_limit1 = high_limit1[valid_codes]
        money1 = money1[valid_codes]
        volume1 = volume1[valid_codes]
        close2 = close2[valid_codes]
        high2 = high2[valid_codes]
        high_limit2 = high_limit2[valid_codes]
        high3 = high3[valid_codes]
        high_limit3 = high_limit3[valid_codes]
        close4 = close4[valid_codes]

        avg_raw = money1 / volume1 / close1
        inc4 = (close1 - close4) / close4
        y_limit = (close1 - high_limit1).abs() <= 0.02
        y_ever_limit = (high1 - high_limit1).abs() <= 0.02
        y_bomb = y_ever_limit & (close1 < high_limit1 * 0.999)
        prev2_limit = (close2 - high_limit2).abs() <= 0.02
        prev2_ever_limit = (high2 - high_limit2).abs() <= 0.02
        prev3_ever_limit = (high3 - high_limit3).abs() <= 0.02

        avg_inc_y2 = avg_raw * 1.1 - 1
        mask_y2 = (
            y_limit & (~prev2_ever_limit) & (~prev3_ever_limit) &
            (avg_inc_y2 >= 0.07) & (money1 >= 5e8) & (money1 <= 20e8) & (inc4 <= 0.25)
        )
        avg_inc_rzq = avg_raw - 1
        oc_ratio = (close1 - open1) / open1
        mask_rzq = (
            y_bomb & (~prev2_limit) & (~mask_y2) &
            (avg_inc_rzq >= -0.04) & (money1 >= 3e8) & (money1 <= 19e8) &
            (oc_ratio >= -0.05) & (inc4 <= 0.18)
        )

        day_rows = []
        for code in list(mask_y2[mask_y2].index):
            day_rows.append((code, float(money1[code]), "y2", float(close1[code]), float(volume1[code]), float(avg_inc_y2[code]), float(inc4[code])))
        for code in list(mask_rzq[mask_rzq].index):
            day_rows.append((code, float(money1[code]), "rzq", float(close1[code]), float(volume1[code]), float(avg_inc_rzq[code]), float(inc4[code])))
        if not day_rows:
            continue
        day_rows.sort(key=lambda x: (0 if x[2] == "y2" else 1, -x[1]))
        day_rows = day_rows[:candidate_cap]
        day_candidates = [code for code, *_ in day_rows]
        left_ok = _auction_yiqian_batch_left_pressure_api(
            api, day_candidates, prev_date
        )
        for rank, (code, money_val, kind, close_val, volume_val, avg_inc, inc4_val) in enumerate(day_rows, 1):
            rows.append(
                {
                    "date": date_int,
                    "previous_date": prev_date_int,
                    "rank": rank,
                    "code": code,
                    "kind": kind,
                    "prev_money": money_val,
                    "prev_close": close_val,
                    "prev_volume": volume_val,
                    "avg_inc": avg_inc,
                    "inc4": inc4_val,
                    "left_ok": bool(left_ok.get(code, False)),
                }
            )

    result = pd.DataFrame(rows)
    out_dir = cache_root / "auction_yiqian_prepare"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{year}.parquet"
    result.to_parquet(out_path, index=False)
    return out_path


def build_year_bundle(year: int, hdata_root: Path = DEFAULT_HDATA_ROOT, cache_root: Path = DEFAULT_CACHE_ROOT) -> list[Path]:
    outputs = [
        build_board_snapshot(year, hdata_root, cache_root),
        build_first_seal_time(year, hdata_root, cache_root),
        build_master_prepare_index(year, hdata_root, cache_root),
    ]
    call_auction_dir = build_call_auction_by_date(year, hdata_root, cache_root)
    outputs.append(Path(call_auction_dir))
    return outputs


def main() -> None:
    parser = argparse.ArgumentParser(description="Build project-local preprocessing features.")
    parser.add_argument("years", nargs="+", type=int, help="Years to build, e.g. 2020 2021")
    parser.add_argument("--hdata-root", type=Path, default=DEFAULT_HDATA_ROOT)
    parser.add_argument("--cache-root", type=Path, default=DEFAULT_CACHE_ROOT)
    parser.add_argument(
        "--only",
        choices=["bundle", "board", "first-seal", "auction", "index", "auction-yq"],
        default="bundle",
        help="Build only one feature family. Use index for the lightweight mother prepare daily index.",
    )
    args = parser.parse_args()

    for year in args.years:
        print(f"BUILD year={year}")
        if args.only == "bundle":
            outputs = build_year_bundle(year, args.hdata_root, args.cache_root)
        elif args.only == "board":
            outputs = [build_board_snapshot(year, args.hdata_root, args.cache_root)]
        elif args.only == "first-seal":
            outputs = [build_first_seal_time(year, args.hdata_root, args.cache_root)]
        elif args.only == "auction":
            outputs = [Path(build_call_auction_by_date(year, args.hdata_root, args.cache_root))]
        elif args.only == "auction-yq":
            outputs = [build_auction_yiqian_prepare(year, args.hdata_root, args.cache_root)]
        else:
            outputs = [build_master_prepare_index(year, args.hdata_root, args.cache_root)]
        for path in outputs:
            print(f"  {path}")


if __name__ == "__main__":
    main()

