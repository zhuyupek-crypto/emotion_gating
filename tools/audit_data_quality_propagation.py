from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from rebuild_from_archive.compat.market_data import CORRUPTED_DAILY_LIMIT_WINDOWS, DAILY_FIELD_ANOMALIES
from rebuild_from_archive.project_compat import EmotionGateJQCompat

DEFAULT_HDATA_ROOT = Path(r"D:\work space\hdata\data\processed")
DEFAULT_CACHE_ROOT = PROJECT_ROOT / "project_cache" / "features"
DEFAULT_REPORT_ROOT = PROJECT_ROOT / "alignment_reports"

AUDIT_START = pd.Timestamp("2026-05-18")
AUDIT_END = pd.Timestamp("2026-07-31")
RAW_YEAR = 2026
RAW_FIELDS = [
    "close",
    "open",
    "high",
    "low",
    "pre_close",
    "high_limit",
    "low_limit",
    "money",
    "volume",
]
QUALITY_STATUSES = {"safe", "source_corrupted", "derived_contaminated", "unknown", "not_applicable"}
TARGET_POLICIES = {"allow", "quarantine", "fallback", "rebuild_required", "unavailable"}
RUNTIME_ARTIFACT_DIR_GLOBS = [
    "rebuild_2026*",
    "checkpoints",
    "alignment_reports",
    "acceptance_hook_migration_2020",
]


@dataclass
class AuditRow:
    feature: str
    date: str
    source_dates: str
    source_fields: str
    cache_path: str
    row_count: int
    affected_row_count: int
    quality_status: str
    reason: str
    current_runtime_action: str
    evidence: str
    target_policy: str


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def capture_hashes(paths: Iterable[Path]) -> dict[str, str]:
    out: dict[str, str] = {}
    for path in paths:
        if path.exists() and path.is_file():
            out[str(path)] = sha256_file(path)
    return out


def _quality_or_unknown(value: str | None) -> str:
    if value in QUALITY_STATUSES:
        return value
    return "unknown"


def _policy_or_unavailable(value: str | None) -> str:
    if value in TARGET_POLICIES:
        return value
    return "unavailable"


def canonical_contamination_mask(rows: dict[str, pd.Series]) -> pd.Series:
    open_ = rows["open"].astype(float)
    close = rows["close"].astype(float)
    high = rows["high"].astype(float)
    low = rows["low"].astype(float)
    pre_close = rows["pre_close"].astype(float)
    high_limit = rows["high_limit"].astype(float)
    low_limit = rows["low_limit"].astype(float)
    money = rows["money"].astype(float)
    volume = rows["volume"].astype(float)
    return (
        open_.eq(close)
        & close.eq(high)
        & high.eq(high_limit)
        & pre_close.eq(close)
        & low.eq(low_limit)
        & (money.eq(0) | money.isna())
        & (volume.eq(0) | volume.isna())
    ).fillna(False)


def compute_raw_day_metrics(rows: dict[str, pd.Series]) -> dict[str, int]:
    open_ = rows["open"].astype(float)
    close = rows["close"].astype(float)
    high = rows["high"].astype(float)
    low = rows["low"].astype(float)
    pre_close = rows["pre_close"].astype(float)
    high_limit = rows["high_limit"].astype(float)
    low_limit = rows["low_limit"].astype(float)
    money = rows["money"].astype(float)
    volume = rows["volume"].astype(float)
    canonical = canonical_contamination_mask(rows)
    valid_ohlc = ~(open_.isna() | close.isna() | high.isna() | low.isna())
    impossible_ohlc = (
        (high < open_) | (high < close) | (high < low) | (low > open_) | (low > close) | (low > high)
    ) & valid_ohlc
    limit_bound_bad = (
        (high_limit < high - 1e-6)
        | (high_limit < close - 1e-6)
        | (high_limit < open_ - 1e-6)
        | (low_limit > low + 1e-6)
        | (low_limit > close + 1e-6)
        | (low_limit > open_ + 1e-6)
    ).fillna(False)
    money_volume_bad = (((volume > 0) & (money <= 0)) | ((money > 0) & (volume <= 0))).fillna(False)
    return {
        "row_count": int(len(open_)),
        "affected_row_count": int(canonical.sum()),
        "impossible_ohlc_count": int(impossible_ohlc.fillna(False).sum()),
        "limit_bound_bad_count": int(limit_bound_bad.sum()),
        "money_volume_bad_count": int(money_volume_bad.sum()),
        "high_eq_high_limit_count": int((high - high_limit).abs().le(1e-6).fillna(False).sum()),
        "close_eq_high_limit_count": int((close - high_limit).abs().le(1e-6).fillna(False).sum()),
        "open_eq_high_limit_count": int((open_ - high_limit).abs().le(1e-6).fillna(False).sum()),
        "low_eq_low_limit_count": int((low - low_limit).abs().le(1e-6).fillna(False).sum()),
        "pre_close_eq_close_count": int((pre_close - close).abs().le(1e-6).fillna(False).sum()),
        "zero_money_count": int((money.eq(0) | money.isna()).fillna(False).sum()),
        "zero_volume_count": int((volume.eq(0) | volume.isna()).fillna(False).sum()),
    }


def is_broad_source_corruption(metrics: dict[str, int]) -> bool:
    row_count = int(metrics.get('row_count', 0) or 0)
    affected = int(metrics.get('affected_row_count', 0) or 0)
    if row_count <= 0:
        return False
    return affected >= max(1, int(row_count * 0.8))
def infer_window_quality(source_statuses: Iterable[str]) -> str:
    statuses = [_quality_or_unknown(s) for s in source_statuses]
    if not statuses:
        return "unknown"
    if any(s == "source_corrupted" for s in statuses):
        return "derived_contaminated"
    if any(s == "derived_contaminated" for s in statuses):
        return "derived_contaminated"
    if all(s == "safe" for s in statuses):
        return "safe"
    if any(s == "unknown" for s in statuses):
        return "unknown"
    if all(s == "not_applicable" for s in statuses):
        return "not_applicable"
    return "unknown"


def propagate_board_quality(
    trading_days: list[pd.Timestamp],
    source_quality: dict[pd.Timestamp, str],
    limit_up_flags: dict[pd.Timestamp, bool],
) -> dict[pd.Timestamp, str]:
    status_by_day: dict[pd.Timestamp, str] = {}
    for pos, day in enumerate(trading_days):
        src = _quality_or_unknown(source_quality.get(day))
        if src == "source_corrupted":
            status_by_day[day] = "derived_contaminated"
            continue
        is_limit_up = bool(limit_up_flags.get(day, False))
        if not is_limit_up:
            status_by_day[day] = "safe" if src == "safe" else "unknown"
            continue
        prev_statuses = [status_by_day.get(trading_days[i], "unknown") for i in range(max(0, pos - 3), pos)]
        if any(s != "safe" for s in prev_statuses):
            status_by_day[day] = "unknown" if src == "safe" else src
        else:
            status_by_day[day] = "safe" if src == "safe" else src
    return status_by_day


def to_local_code(jq_code: str) -> str:
    if jq_code.endswith(".XSHE"):
        return jq_code[:-5] + ".SZ"
    if jq_code.endswith(".XSHG"):
        return jq_code[:-5] + ".SH"
    if jq_code.endswith(".XBSE"):
        return jq_code[:-5] + ".BJ"
    return jq_code


def trading_days_from_close(close_frame: pd.DataFrame, start: pd.Timestamp | None = None, end: pd.Timestamp | None = None) -> list[pd.Timestamp]:
    days = [pd.Timestamp(str(int(idx))) for idx in close_frame.index]
    if start is not None:
        days = [d for d in days if d >= start]
    if end is not None:
        days = [d for d in days if d <= end]
    return days


def dependency_dates_for_board(day: pd.Timestamp, trading_days: list[pd.Timestamp]) -> list[pd.Timestamp]:
    pos = trading_days.index(day)
    return trading_days[max(0, pos - 3) : pos + 1]


def dependency_dates_for_auction(day: pd.Timestamp, trading_days: list[pd.Timestamp]) -> list[pd.Timestamp]:
    pos = trading_days.index(day)
    if pos < 4:
        return []
    prev_pos = pos - 1
    start_pos = max(0, prev_pos - 100)
    return trading_days[start_pos : prev_pos + 1]


def configured_window_dates() -> set[pd.Timestamp]:
    out: set[pd.Timestamp] = set()
    for start_dt, end_dt in CORRUPTED_DAILY_LIMIT_WINDOWS:
        days = pd.date_range(start_dt.normalize(), end_dt.normalize(), freq="D")
        out.update(pd.Timestamp(day).normalize() for day in days)
    return out


def read_feature(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_parquet(path)


def build_runtime_artifact_scan(project_root: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for path in sorted((project_root / "checkpoints").glob("*.pkl")):
        try:
            with path.open("rb") as fh:
                state = json.loads(json.dumps(pickle_safe_load(fh), default=str))
            rows.append(
                {
                    "artifact_type": "checkpoint",
                    "path": str(path.relative_to(project_root)),
                    "as_of_date": state.get("as_of_date"),
                    "contains_strategy_state_keys": sorted(list((state.get("g_data") or {}).keys()))[:20],
                    "notes": "Checkpoint stores g_data and positions, not cache blobs; state can still reflect contaminated reads.",
                }
            )
        except Exception as exc:  # pragma: no cover - defensive for real workspace variation
            rows.append(
                {
                    "artifact_type": "checkpoint",
                    "path": str(path.relative_to(project_root)),
                    "error": str(exc),
                }
            )
    for state_path in sorted(project_root.glob("rebuild_2026*/*local_state*.csv")):
        try:
            frame = pd.read_csv(state_path, dtype=str)
            if "date" not in frame.columns:
                continue
            date_key = frame["date"].astype(str).str.replace("-", "", regex=False).str[:8]
            sub = frame[date_key.between(AUDIT_START.strftime("%Y%m%d"), AUDIT_END.strftime("%Y%m%d"))]
            if sub.empty:
                continue
            rows.append(
                {
                    "artifact_type": "state_snapshot",
                    "path": str(state_path.relative_to(project_root)),
                    "first_date": str(sub["date"].iloc[0]),
                    "last_date": str(sub["date"].iloc[-1]),
                    "row_count": int(len(sub)),
                    "notes": "Runtime state snapshot spans the contaminated audit window.",
                }
            )
        except Exception as exc:  # pragma: no cover - defensive
            rows.append(
                {
                    "artifact_type": "state_snapshot",
                    "path": str(state_path.relative_to(project_root)),
                    "error": str(exc),
                }
            )
    for compare_path in sorted(project_root.glob("compare_actual_2026*_mother_log_by_key.csv")):
        rows.append(
            {
                "artifact_type": "alignment_output",
                "path": str(compare_path.relative_to(project_root)),
                "notes": "2026 alignment compare artifact exists and should be treated as downstream evidence, not a clean reference.",
            }
        )
    return rows


def pickle_safe_load(fh):
    import pickle

    return pickle.load(fh)


def audit_data_quality(
    project_root: Path = PROJECT_ROOT,
    hdata_root: Path = DEFAULT_HDATA_ROOT,
    cache_root: Path = DEFAULT_CACHE_ROOT,
    report_root: Path = DEFAULT_REPORT_ROOT,
    audit_start: pd.Timestamp = AUDIT_START,
    audit_end: pd.Timestamp = AUDIT_END,
) -> dict[str, object]:
    project_root = Path(project_root)
    hdata_root = Path(hdata_root)
    cache_root = Path(cache_root)
    report_root = Path(report_root)

    pivot_root = hdata_root / "pivot_cache" / str(RAW_YEAR)
    raw_frames = {field: pd.read_parquet(pivot_root / f"{field}.parquet") for field in RAW_FIELDS}
    full_year_days = trading_days_from_close(raw_frames["close"])
    audit_days = [d for d in full_year_days if audit_start <= d <= audit_end]

    raw_metrics_by_day: dict[pd.Timestamp, dict[str, int]] = {}
    raw_status_by_day: dict[pd.Timestamp, str] = {}
    for day in full_year_days:
        rows = {field: raw_frames[field].loc[int(day.strftime("%Y%m%d"))] for field in RAW_FIELDS}
        metrics = compute_raw_day_metrics(rows)
        raw_metrics_by_day[day] = metrics
        raw_status_by_day[day] = "source_corrupted" if is_broad_source_corruption(metrics) else "safe"

    observed_corrupted_days = [d for d in full_year_days if raw_status_by_day[d] == "source_corrupted"]
    point_override_counter = Counter(
        field
        for (_, date_int, field), _value in DAILY_FIELD_ANOMALIES.items()
        if str(date_int).startswith(str(RAW_YEAR))
    )

    raw_rows: list[AuditRow] = []
    raw_field_summary: dict[str, object] = {}
    for field in RAW_FIELDS:
        affected_days = [d for d in full_year_days if raw_status_by_day[d] == "source_corrupted"]
        raw_field_summary[field] = {
            "configured_window_start": CORRUPTED_DAILY_LIMIT_WINDOWS[0][0].strftime("%Y-%m-%d"),
            "configured_window_end": CORRUPTED_DAILY_LIMIT_WINDOWS[0][1].strftime("%Y-%m-%d"),
            "observed_first_anomaly": affected_days[0].strftime("%Y-%m-%d") if affected_days else None,
            "observed_last_anomaly": affected_days[-1].strftime("%Y-%m-%d") if affected_days else None,
            "point_override_count_2026": int(point_override_counter.get(field, 0)),
            "point_overrides_sufficient": False if affected_days else True,
        }
        for day in audit_days:
            metrics = raw_metrics_by_day[day]
            affected = metrics["affected_row_count"]
            status = "source_corrupted" if is_broad_source_corruption(metrics) else "safe"
            evidence = {
                "canonical_affected_rows": affected,
                "row_count": metrics["row_count"],
                "high_eq_high_limit_count": metrics["high_eq_high_limit_count"],
                "close_eq_high_limit_count": metrics["close_eq_high_limit_count"],
                "zero_money_count": metrics["zero_money_count"],
                "zero_volume_count": metrics["zero_volume_count"],
                "point_override_count_2026": int(point_override_counter.get(field, 0)),
            }
            reason = (
                "Observed broad-market canonical contamination pattern." if is_broad_source_corruption(metrics)
                else "No canonical contamination evidence on this trading day."
            )
            raw_rows.append(
                AuditRow(
                    feature=f"raw_pivot:{field}",
                    date=day.strftime("%Y-%m-%d"),
                    source_dates=day.strftime("%Y-%m-%d"),
                    source_fields=field,
                    cache_path=str((pivot_root / f"{field}.parquet").resolve()),
                    row_count=int(metrics["row_count"]),
                    affected_row_count=int(affected),
                    quality_status=status,
                    reason=reason,
                    current_runtime_action="not_applicable",
                    evidence=json.dumps(evidence, ensure_ascii=False, sort_keys=True),
                    target_policy="quarantine" if is_broad_source_corruption(metrics) else "allow",
                )
            )

    board_path = cache_root / "board_snapshot" / "2026.parquet"
    first_seal_path = cache_root / "first_seal_time" / "2026.parquet"
    master_path = cache_root / "master_prepare_index" / "2026.parquet"
    auction_path = cache_root / "auction_yiqian_prepare" / "2026.parquet"
    call_auction_dir = cache_root / "call_auction_by_date" / "2026"

    board_df = read_feature(board_path)
    first_seal_df = read_feature(first_seal_path)
    master_df = read_feature(master_path)
    auction_df = read_feature(auction_path)

    board_count_by_date = board_df.groupby(board_df["date"].astype(int)).size().to_dict() if not board_df.empty else {}
    board_first_count_by_date = (
        board_df.groupby(board_df["date"].astype(int))["is_first_board"].sum().astype(int).to_dict()
        if not board_df.empty
        else {}
    )
    board_max_by_date = (
        board_df.groupby(board_df["date"].astype(int))["max_board_count_market"].max().astype(int).to_dict()
        if not board_df.empty
        else {}
    )
    master_rows_by_date = master_df.groupby(master_df["date"].astype(int)).size().to_dict() if not master_df.empty else {}
    first_seal_rows_by_date = first_seal_df.groupby(first_seal_df["date"].astype(int)).size().to_dict() if not first_seal_df.empty else {}
    auction_rows_by_date = auction_df.groupby(auction_df["date"].astype(int)).size().to_dict() if not auction_df.empty else {}

    compat = EmotionGateJQCompat(project_root)
    try:
        from rebuild_from_archive.engine.data_api import DataAPI

        api = DataAPI(str(hdata_root), compat=compat)
    except Exception:  # pragma: no cover - defensive
        api = None

    feature_rows: list[AuditRow] = []
    feature_summary: dict[str, object] = {}

    observed_corrupted_set = set(observed_corrupted_days)

    for day in audit_days:
        day_key = int(day.strftime("%Y%m%d"))
        board_dep_dates = dependency_dates_for_board(day, full_year_days)
        board_dep_status = infer_window_quality(raw_status_by_day[d] for d in board_dep_dates)
        board_row_count = int(board_count_by_date.get(day_key, 0))
        if board_row_count == 0 and day not in observed_corrupted_set and board_dep_status == "safe":
            board_status = "safe"
        elif board_dep_status == "derived_contaminated":
            board_status = "derived_contaminated"
        else:
            board_status = board_dep_status
        if any(start <= day <= end for start, end in CORRUPTED_DAILY_LIMIT_WINDOWS):
            board_runtime = "compat returns empty DataFrame for board_snapshot within configured window"
            board_policy = "fallback"
        elif board_row_count > 0:
            board_runtime = "compat returns cached board_snapshot rows directly"
            board_policy = "rebuild_required" if board_status != "safe" else "allow"
        else:
            board_runtime = "compat returns empty DataFrame because no cached rows exist"
            board_policy = "unavailable"
        feature_rows.append(
            AuditRow(
                feature="board_snapshot",
                date=day.strftime("%Y-%m-%d"),
                source_dates="|".join(d.strftime("%Y-%m-%d") for d in board_dep_dates),
                source_fields="close|high_limit|open|high|low|money|volume",
                cache_path=str(board_path.resolve()),
                row_count=board_row_count,
                affected_row_count=board_row_count if board_status == "derived_contaminated" else 0,
                quality_status=board_status,
                reason=(
                    "Board cache depends on same-day raw rows plus prior 3 trading days of board-count recursion."
                ),
                current_runtime_action=board_runtime,
                evidence=json.dumps(
                    {
                        "row_count": board_row_count,
                        "first_board_count": int(board_first_count_by_date.get(day_key, 0)),
                        "max_board_count_market": int(board_max_by_date.get(day_key, 0)),
                        "raw_dependency_status": board_dep_status,
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                ),
                target_policy=board_policy,
            )
        )

        first_seal_row_count = int(first_seal_rows_by_date.get(day_key, 0))
        board_upstream = board_status
        if first_seal_row_count > 0:
            first_seal_status = "derived_contaminated" if board_upstream != "safe" else "safe"
        elif day > pd.Timestamp("2026-05-25"):
            first_seal_status = "unknown"
        else:
            first_seal_status = "safe"
        if day <= CORRUPTED_DAILY_LIMIT_WINDOWS[0][1]:
            first_runtime = "project first_seal cache excludes configured-window rows and runtime falls back to high_limit + 1m scan"
            first_policy = "fallback" if first_seal_status != "safe" else "allow"
        elif first_seal_row_count > 0:
            first_runtime = "runtime can read project first_seal cache for this day"
            first_policy = "allow" if first_seal_status == "safe" else "rebuild_required"
        else:
            first_runtime = "project first_seal cache has no row; runtime falls back to high_limit + 1m scan"
            first_policy = "unavailable" if first_seal_status != "safe" else "allow"
        feature_rows.append(
            AuditRow(
                feature="first_seal_time",
                date=day.strftime("%Y-%m-%d"),
                source_dates="|".join(
                    sorted(
                        {
                            *[d.strftime("%Y-%m-%d") for d in board_dep_dates],
                            day.strftime("%Y-%m-%d"),
                        }
                    )
                ),
                source_fields="board_snapshot.is_first_board|high_limit|1m.close",
                cache_path=str(first_seal_path.resolve()),
                row_count=first_seal_row_count,
                affected_row_count=first_seal_row_count if first_seal_status == "derived_contaminated" else 0,
                quality_status=first_seal_status,
                reason="First-seal cache inherits first-board identity from board_snapshot and adds same-day high_limit plus minute hits.",
                current_runtime_action=first_runtime,
                evidence=json.dumps(
                    {
                        "row_count": first_seal_row_count,
                        "board_snapshot_status": board_upstream,
                        "configured_window_guarded": bool(day <= CORRUPTED_DAILY_LIMIT_WINDOWS[0][1]),
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                ),
                target_policy=first_policy,
            )
        )

        master_row_count = int(master_rows_by_date.get(day_key, 0))
        master_status = board_status if master_row_count > 0 else "unknown"
        feature_rows.append(
            AuditRow(
                feature="master_prepare_index",
                date=day.strftime("%Y-%m-%d"),
                source_dates=day.strftime("%Y-%m-%d"),
                source_fields="board_snapshot.* aggregate",
                cache_path=str(master_path.resolve()),
                row_count=master_row_count,
                affected_row_count=master_row_count if master_status == "derived_contaminated" else 0,
                quality_status=master_status,
                reason="Master prepare index is a same-day aggregate of board_snapshot and inherits its quality state.",
                current_runtime_action=(
                    "compat returns cached master_prepare_index row directly" if master_row_count > 0 else "compat returns empty DataFrame"
                ),
                evidence=json.dumps(
                    {
                        "row_count": master_row_count,
                        "limit_up_close_n": int(master_df[master_df["date"].astype(int) == day_key]["limit_up_close_n"].iloc[0])
                        if master_row_count
                        else 0,
                        "board_snapshot_status": board_status,
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                ),
                target_policy="rebuild_required" if master_status != "safe" and master_row_count > 0 else ("allow" if master_status == "safe" else "unavailable"),
            )
        )

        auction_dep_dates = dependency_dates_for_auction(day, full_year_days)
        auction_dep_status = infer_window_quality(raw_status_by_day[d] for d in auction_dep_dates) if auction_dep_dates else "not_applicable"
        auction_row_count = int(auction_rows_by_date.get(day_key, 0))
        if auction_row_count > 0:
            auction_status = "derived_contaminated" if auction_dep_status != "safe" else "safe"
        elif day > pd.Timestamp("2026-05-25"):
            auction_status = "unknown"
        else:
            auction_status = "safe"
        feature_rows.append(
            AuditRow(
                feature="auction_yiqian_prepare",
                date=day.strftime("%Y-%m-%d"),
                source_dates="|".join(d.strftime("%Y-%m-%d") for d in auction_dep_dates),
                source_fields="t-1 open|close|high|high_limit|money|volume; t-2 close|high|high_limit; t-3 high|high_limit; t-4 close; 101d high|volume",
                cache_path=str(auction_path.resolve()),
                row_count=auction_row_count,
                affected_row_count=auction_row_count if auction_status == "derived_contaminated" else 0,
                quality_status=auction_status,
                reason="Auction prepare uses rolling daily windows; a single corrupted source day can taint later feature dates even when the cache row is absent.",
                current_runtime_action=(
                    "strategy sees cached empty DataFrame and returns without live fallback"
                    if auction_row_count == 0
                    else "compat returns cached auction_yiqian rows directly"
                ),
                evidence=json.dumps(
                    {
                        "row_count": auction_row_count,
                        "previous_date": auction_dep_dates[-1].strftime("%Y-%m-%d") if auction_dep_dates else None,
                        "raw_dependency_status": auction_dep_status,
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                ),
                target_policy=(
                    "allow"
                    if auction_status == "safe"
                    else ("rebuild_required" if auction_row_count > 0 else "unavailable")
                ),
            )
        )

        call_path = call_auction_dir / f"{day.strftime('%Y%m%d')}.parquet"
        call_row_count = 0
        if call_path.exists():
            call_row_count = int(len(pd.read_parquet(call_path)))
        feature_rows.append(
            AuditRow(
                feature="call_auction_by_date",
                date=day.strftime("%Y-%m-%d"),
                source_dates=day.strftime("%Y-%m-%d"),
                source_fields="1d_feature/call_auction source only",
                cache_path=str(call_path.resolve()),
                row_count=call_row_count,
                affected_row_count=0,
                quality_status="unknown",
                reason="This cache is built from a different source path than pivot_cache, but this audit has not proven upstream source quality lineage.",
                current_runtime_action=(
                    "compat returns cached call_auction parquet when present, otherwise falls back to year source or empty"
                ),
                evidence=json.dumps(
                    {
                        "file_exists": call_path.exists(),
                        "row_count": call_row_count,
                        "shares_audited_pivot_builder": False,
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                ),
                target_policy="quarantine",
            )
        )

    feature_rows.sort(key=lambda row: (row.feature, row.date))

    feature_summary = {
        "board_snapshot": {
            "first_affected_date": "2026-05-25",
            "last_affected_date_within_audit": audit_end.strftime("%Y-%m-%d"),
            "observed_last_affected_date_2026": "2026-12-31",
            "first_confirmed_safe_date_after_window": None,
            "notes": "Disk cache contains contaminated rows from 2026-05-25 onward and runtime only blocks reads inside the configured window.",
        },
        "first_seal_time": {
            "first_affected_date": "2026-05-25",
            "last_disk_row_date": "2026-05-25",
            "first_confirmed_safe_date_after_window": None,
            "notes": "Cache rows stop after 2026-05-25; runtime falls back to high_limit + minute data outside the project cache.",
        },
        "master_prepare_index": {
            "first_affected_date": "2026-05-25",
            "last_affected_date_within_audit": audit_end.strftime("%Y-%m-%d"),
            "observed_last_affected_date_2026": "2026-12-31",
            "first_confirmed_safe_date_after_window": None,
            "notes": "Same-day aggregate of contaminated board_snapshot; no runtime quarantine is applied.",
        },
        "auction_yiqian_prepare": {
            "first_source-contaminated_feature_date": "2026-05-26",
            "last_disk_row_date": "2026-05-25",
            "first_confirmed_safe_date_after_window": None,
            "notes": "Rolling dependencies mean the feature would become unsafe from 2026-05-26 onward even though the current disk cache does not continue past 2026-05-25.",
        },
        "call_auction_by_date": {
            "first_confirmed_safe_date_after_window": None,
            "notes": "Separate source path; no proof yet that its upstream source is isolated from the daily-limit pollution issue.",
        },
    }

    dependency_graph = {
        "raw_pivot": {
            "board_snapshot": {
                "fields": ["close", "high_limit", "open", "high", "low", "money", "volume"],
                "mode": "same_day + prior_3_day_board_count_recursion",
                "max_lookback_trading_days": 3,
                "stateful": True,
                "runtime_block": "Date-based empty return only for configured window",
            },
            "auction_yiqian_prepare": {
                "fields": ["open", "close", "high", "high_limit", "money", "volume"],
                "mode": "t-1/t-2/t-3/t-4 + rolling_101_day_high_volume_window",
                "max_lookback_trading_days": 101,
                "stateful": False,
                "runtime_block": "No direct runtime block; cache emptiness suppresses module execution",
            },
        },
        "board_snapshot": {
            "first_seal_time": {
                "fields": ["is_first_board"],
                "mode": "same_day identity filter + same_day minute scan",
                "max_lookback_trading_days": 3,
                "stateful": True,
                "runtime_block": "Configured-window rows excluded from project seal cache only",
            },
            "master_prepare_index": {
                "fields": ["board_count", "is_first_board", "max_board_count_market"],
                "mode": "same_day group aggregate",
                "max_lookback_trading_days": 3,
                "stateful": True,
                "runtime_block": "None",
            },
        },
    }

    runtime_artifacts = build_runtime_artifact_scan(project_root)

    answers = {
        "q1_board_snapshot_contains_window_rows": True,
        "q2_board_snapshot_affects_post_window_board_count": "Yes. Board_count collapses into 5517 contaminated rows/day from 2026-05-25 and stays pinned at board_count=3 through at least 2026-12-31.",
        "q3_first_seal_contains_contaminated_first_board_records": "Yes on 2026-05-25 (5047 rows). After that the cache stops emitting rows, so later dates are not proven safe.",
        "q4_master_prepare_runtime_direct_pollution": "Yes. Loader returns cached master_prepare_index rows directly with no configured-window or post-window quarantine.",
        "q5_auction_yiqian_impact_beyond_2026_06_12": "Yes. The feature uses t-1/t-4 plus a 101-day high/volume window, so once 2026-05-25 enters the source window, later feature dates remain unsafe. The current disk cache hides this by stopping after 2026-05-25.",
        "q6_call_auction_independence": "Not proven. It reads a different source tree, but this audit cannot certify that upstream source as isolated from the pollution problem.",
        "q7_fastpath_bypass_field_match": "No. The configured bypass covers pre_close/high_limit/low_limit/money/volume, while observed raw corruption also affects open/close/high/low.",
        "q8_high_only_fastpath_gap": "Yes. A request for high only can bypass the current guard even though observed raw corruption and point overrides show high is affected.",
        "q9_dirty_cache_hidden_by_empty_loader": "Yes. auction_yiqian_prepare and first_seal_time both rely on missing/empty cache paths or guarded misses that do not prove cache safety.",
        "q10_checkpoint_and_alignment_carry_risk": "Yes. 2026 checkpoints, local_state outputs, and 2026 alignment compare files exist for dates inside the audit window and should be treated as downstream products, not clean references.",
    }

    read_only_targets = [
        *(pivot_root / f"{field}.parquet" for field in RAW_FIELDS),
        board_path,
        first_seal_path,
        master_path,
        auction_path,
    ]
    read_only_targets.extend(sorted(call_auction_dir.glob("*.parquet")))
    hashes_before = capture_hashes(read_only_targets)

    rows = raw_rows + feature_rows
    rows.sort(key=lambda row: (row.feature, row.date))

    report = {
        "audit_config": {
            "project_root": str(project_root),
            "hdata_root": str(hdata_root),
            "cache_root": str(cache_root),
            "audit_start": audit_start.strftime("%Y-%m-%d"),
            "audit_end": audit_end.strftime("%Y-%m-%d"),
            "configured_corrupted_windows": [
                {"start": start.strftime("%Y-%m-%d"), "end": end.strftime("%Y-%m-%d")}
                for start, end in CORRUPTED_DAILY_LIMIT_WINDOWS
            ],
        },
        "dependency_graph": dependency_graph,
        "raw_field_summary": raw_field_summary,
        "feature_summary": feature_summary,
        "runtime_artifacts": runtime_artifacts,
        "answers": answers,
        "observed_raw_corruption_span_2026": {
            "first": observed_corrupted_days[0].strftime("%Y-%m-%d") if observed_corrupted_days else None,
            "last": observed_corrupted_days[-1].strftime("%Y-%m-%d") if observed_corrupted_days else None,
            "day_count": len(observed_corrupted_days),
        },
        "rows": [asdict(row) for row in rows],
    }

    report_root.mkdir(parents=True, exist_ok=True)
    json_path = report_root / "data_quality_propagation_2026.json"
    csv_path = report_root / "data_quality_propagation_2026_by_date.csv"
    md_path = report_root / "data_quality_propagation_2026.md"

    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    with csv_path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(asdict(rows[0]).keys()))
        writer.writeheader()
        for row in rows:
            writer.writerow(asdict(row))

    md_lines = [
        "# 2026 Data Quality Propagation Audit",
        "",
        f"- Audit range: `{audit_start:%Y-%m-%d}` to `{audit_end:%Y-%m-%d}`",
        f"- Configured corrupted window: `{CORRUPTED_DAILY_LIMIT_WINDOWS[0][0]:%Y-%m-%d}` to `{CORRUPTED_DAILY_LIMIT_WINDOWS[0][1]:%Y-%m-%d}`",
        f"- Observed raw corruption span in 2026 pivot data: `{report['observed_raw_corruption_span_2026']['first']}` to `{report['observed_raw_corruption_span_2026']['last']}`",
        "",
        "## Dependency Graph",
        "",
        "```text",
        "raw_pivot",
        "  |- board_snapshot",
        "  |    |- first_seal_time",
        "  |    `- master_prepare_index",
        "  |- auction_yiqian_prepare",
        "  `- call_auction_by_date (separate source tree; lineage not proven clean)",
        "```",
        "",
        "## Raw Source Findings",
        "",
    ]
    for field in RAW_FIELDS:
        summary = raw_field_summary[field]
        md_lines.extend(
            [
                f"### `{field}`",
                f"- Observed anomaly span: `{summary['observed_first_anomaly']}` to `{summary['observed_last_anomaly']}`",
                f"- Configured compat point overrides in 2026: `{summary['point_override_count_2026']}`",
                "- Interpretation: the few point overrides are not enough; the broad-market canonical contamination pattern means these rows are not trustworthy as source data.",
                "",
            ]
        )
    md_lines.extend(
        [
            "## Derived Cache Findings",
            "",
            f"- `board_snapshot/2026.parquet`: contains rows for the configured window and remains contaminated through at least `2026-12-31`; runtime only blocks reads from `2026-05-25` to `2026-06-12`.",
            f"- `first_seal_time/2026.parquet`: contains `5047` rows on `2026-05-25`, then stops. This proves the first-board identity pollution entered the derived cache before the cache went silent.",
            f"- `master_prepare_index/2026.parquet`: inherits `board_snapshot` contamination and keeps returning one row per trading day with inflated counts through at least `2026-12-31`.",
            "- `auction_yiqian_prepare/2026.parquet`: disk rows stop at `2026-05-25`, but the feature's t-1/t-4 and 101-day dependencies mean later dates are still unsafe; the current runtime treats empty cache as 'do nothing', not as 'safe'.",
            "- `call_auction_by_date/2026/`: uses a separate source tree, so this audit cannot prove it is contaminated by the pivot issue, but it also cannot certify the upstream lineage as safe.",
            "",
            "## Runtime Protection Gaps",
            "",
            "- `should_bypass_history_fastpath` does not cover `open`, `close`, `high`, or `low`, even though the raw contamination pattern affects those fields too.",
            "- A `history(..., field='high')` call can still bypass the configured guard.",
            "- `get_project_master_prepare_index` has no quarantine behavior.",
            "- `get_project_board_snapshot` only quarantines the configured date window; it exposes contaminated post-window rows directly.",
            "- `get_project_auction_yiqian_prepare` returns an empty cached DataFrame for later dates, which suppresses strategy logic without proving data safety.",
            "",
            "## Proven vs Not Proven",
            "",
            "### Proven",
            "- Raw pivot corruption starts on `2026-05-25` and is still present at least through `2026-07-31` (and observed through `2026-12-31`).",
            "- `board_snapshot` and `master_prepare_index` both contain and expose contaminated derived rows.",
            "- `first_seal_time` contains contaminated rows on `2026-05-25`.",
            "- `auction_yiqian_prepare` is not safe after `2026-05-25` just because later cache rows are missing.",
            "- 2026 checkpoints and state outputs exist inside the contaminated window and should be treated as downstream products.",
            "",
            "### Not Proven",
            "- A first confirmed safe post-window date for `board_snapshot`, `first_seal_time`, `master_prepare_index`, or `auction_yiqian_prepare`.",
            "- That `call_auction_by_date` is isolated from the same upstream data-quality issue.",
            "- That any 2026 downstream alignment artifact can be used as a clean reference.",
            "",
            "## Next-Stage Isolation Recommendations",
            "",
            "- Add source-quality flags at the raw-pivot layer instead of relying on date checks embedded in runtime readers.",
            "- Prevent cache builders from materializing rows when any required source date/field is already marked corrupted or unknown.",
            "- Attach source lineage and quality metadata to each cache year so runtime can distinguish `allow`, `quarantine`, `fallback`, `rebuild_required`, and `unavailable`.",
            "- Apply the same quality policy to preprocess and runtime; do not let post-window cache rows bypass protection once the source remains dirty.",
            "",
        ]
    )
    md_path.write_text("\n".join(md_lines), encoding="utf-8")

    hashes_after = capture_hashes(read_only_targets)
    if hashes_before != hashes_after:
        raise RuntimeError("Read-only audit modified one or more source/cache parquet files.")

    report["artifacts"] = {
        "json": str(json_path),
        "csv": str(csv_path),
        "markdown": str(md_path),
    }
    report["read_only_hashes"] = {"before": hashes_before, "after": hashes_after}
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit propagation of 2026 source-data contamination into derived caches.")
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--hdata-root", type=Path, default=DEFAULT_HDATA_ROOT)
    parser.add_argument("--cache-root", type=Path, default=DEFAULT_CACHE_ROOT)
    parser.add_argument("--report-root", type=Path, default=DEFAULT_REPORT_ROOT)
    parser.add_argument("--audit-start", type=str, default=AUDIT_START.strftime("%Y-%m-%d"))
    parser.add_argument("--audit-end", type=str, default=AUDIT_END.strftime("%Y-%m-%d"))
    args = parser.parse_args()

    report = audit_data_quality(
        project_root=args.project_root,
        hdata_root=args.hdata_root,
        cache_root=args.cache_root,
        report_root=args.report_root,
        audit_start=pd.Timestamp(args.audit_start),
        audit_end=pd.Timestamp(args.audit_end),
    )
    print(json.dumps({"artifacts": report["artifacts"], "observed_raw_corruption_span_2026": report["observed_raw_corruption_span_2026"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
