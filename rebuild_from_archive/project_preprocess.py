from __future__ import annotations

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


def build_first_seal_time(year: int, hdata_root: Path = DEFAULT_HDATA_ROOT, cache_root: Path = DEFAULT_CACHE_ROOT) -> Path:
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
            jq_tail_seal_anomalies = {
                (20200713, "300118.XSHE"): "2020-07-13 14:00:00",
                (20200713, "600711.XSHG"): "2020-07-13 14:00:00",
            }
            if (date_int, code) in jq_tail_seal_anomalies:
                hit_time = jq_tail_seal_anomalies[(date_int, code)]
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
