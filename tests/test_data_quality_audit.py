from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import pandas as pd

from tools.audit_data_quality_propagation import (
    AUDIT_END,
    AUDIT_START,
    audit_data_quality,
    canonical_contamination_mask,
    infer_window_quality,
    propagate_board_quality,
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def _make_row(value: float, size: int = 3) -> pd.Series:
    return pd.Series([value] * size, index=[f"{i:06d}.SZ" for i in range(size)])


def _write_minimal_hdata(root: Path) -> None:
    pivot_root = root / "pivot_cache" / "2026"
    pivot_root.mkdir(parents=True, exist_ok=True)
    dates = [20260522, 20260523, 20260525, 20260526]
    cols = ["000001.SZ", "000002.SZ", "000003.SZ"]
    clean = {
        "open": [10, 10, None, None],
        "close": [11, 11, None, None],
        "high": [11, 11, None, None],
        "low": [9, 9, None, None],
        "pre_close": [10, 10, None, None],
        "high_limit": [11, 11, None, None],
        "low_limit": [9, 9, None, None],
        "money": [100, 100, None, None],
        "volume": [10, 10, None, None],
    }
    for field, values in clean.items():
        rows = []
        for value in values:
            if value is None:
                if field in {"money", "volume"}:
                    rows.append([0.0, 0.0, 0.0])
                elif field in {"low", "low_limit"}:
                    rows.append([9.0, 9.0, 9.0])
                else:
                    rows.append([11.0, 11.0, 11.0])
            else:
                rows.append([float(value)] * len(cols))
        frame = pd.DataFrame(rows, index=dates, columns=cols)
        frame.to_parquet(pivot_root / f"{field}.parquet")
    call_auction_root = root / "1d_feature" / "call_auction"
    call_auction_root.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"date": ["2026-05-22"], "code": ["000001.SZ"], "value": [1]}).to_parquet(call_auction_root / "2026.parquet")


def _write_minimal_cache(root: Path) -> None:
    (root / "board_snapshot").mkdir(parents=True, exist_ok=True)
    (root / "first_seal_time").mkdir(parents=True, exist_ok=True)
    (root / "master_prepare_index").mkdir(parents=True, exist_ok=True)
    (root / "auction_yiqian_prepare").mkdir(parents=True, exist_ok=True)
    (root / "call_auction_by_date" / "2026").mkdir(parents=True, exist_ok=True)

    pd.DataFrame(
        [
            {"date": 20260522, "code": "000001.XSHE", "is_limit_up_close": True, "board_count": 1, "is_first_board": True, "max_board_count_market": 1, "prev_close": 10.0, "open": 10.0, "close": 11.0, "high": 11.0, "low": 9.0, "money": 100.0, "volume": 10.0},
            {"date": 20260525, "code": "000001.XSHE", "is_limit_up_close": True, "board_count": 1, "is_first_board": True, "max_board_count_market": 3, "prev_close": 11.0, "open": 11.0, "close": 11.0, "high": 11.0, "low": 9.0, "money": 0.0, "volume": 0.0},
            {"date": 20260526, "code": "000001.XSHE", "is_limit_up_close": True, "board_count": 2, "is_first_board": False, "max_board_count_market": 3, "prev_close": 11.0, "open": 11.0, "close": 11.0, "high": 11.0, "low": 9.0, "money": 0.0, "volume": 0.0},
        ]
    ).to_parquet(root / "board_snapshot" / "2026.parquet", index=False)

    pd.DataFrame(
        [
            {"date": 20260522, "code": "000001.XSHE", "first_limit_hit_time": "2026-05-22 09:35:00", "seal_bucket": "early", "is_tail_seal": False},
            {"date": 20260525, "code": "000001.XSHE", "first_limit_hit_time": "2026-05-25 09:31:00", "seal_bucket": "early", "is_tail_seal": False},
        ]
    ).to_parquet(root / "first_seal_time" / "2026.parquet", index=False)

    pd.DataFrame(
        [
            {"date": 20260522, "limit_up_close_n": 1, "first_board_n": 1, "max_board_count_market": 1, "first_board_codes": "000001.XSHE", "leader_codes": ""},
            {"date": 20260525, "limit_up_close_n": 1, "first_board_n": 1, "max_board_count_market": 3, "first_board_codes": "000001.XSHE", "leader_codes": "000001.XSHE:3"},
            {"date": 20260526, "limit_up_close_n": 1, "first_board_n": 0, "max_board_count_market": 3, "first_board_codes": "", "leader_codes": "000001.XSHE:3"},
        ]
    ).to_parquet(root / "master_prepare_index" / "2026.parquet", index=False)

    pd.DataFrame(
        [
            {"date": 20260522, "previous_date": 20260521, "rank": 1, "code": "000001.XSHE", "kind": "y2", "prev_money": 100.0, "prev_close": 11.0, "prev_volume": 10.0, "avg_inc": 0.1, "inc4": 0.1, "left_ok": True},
            {"date": 20260525, "previous_date": 20260522, "rank": 1, "code": "000001.XSHE", "kind": "y2", "prev_money": 100.0, "prev_close": 11.0, "prev_volume": 10.0, "avg_inc": 0.1, "inc4": 0.1, "left_ok": True},
        ]
    ).to_parquet(root / "auction_yiqian_prepare" / "2026.parquet", index=False)

    pd.DataFrame({"date": ["2026-05-22"], "code": ["000001.XSHE"], "value": [1]}).to_parquet(
        root / "call_auction_by_date" / "2026" / "20260522.parquet",
        index=False,
    )


def test_known_window_is_detected_by_canonical_pattern():
    rows = {
        "open": _make_row(11),
        "close": _make_row(11),
        "high": _make_row(11),
        "low": _make_row(9),
        "pre_close": _make_row(11),
        "high_limit": _make_row(11),
        "low_limit": _make_row(9),
        "money": _make_row(0),
        "volume": _make_row(0),
    }
    mask = canonical_contamination_mask(rows)
    assert mask.all()


def test_propagation_detects_board_count_and_downstream_inheritance():
    days = [pd.Timestamp("2026-05-25"), pd.Timestamp("2026-05-26"), pd.Timestamp("2026-05-27")]
    source_quality = {
        days[0]: "source_corrupted",
        days[1]: "safe",
        days[2]: "safe",
    }
    limit_up_flags = {days[0]: True, days[1]: True, days[2]: False}
    board_quality = propagate_board_quality(days, source_quality, limit_up_flags)
    assert board_quality[days[0]] == "derived_contaminated"
    assert board_quality[days[1]] == "unknown"
    assert board_quality[days[2]] == "safe"
    assert infer_window_quality([board_quality[days[0]]]) == "derived_contaminated"
    assert infer_window_quality([board_quality[days[1]]]) == "unknown"


def test_conservative_unknown_when_evidence_is_missing():
    assert infer_window_quality([]) == "unknown"
    assert infer_window_quality(["safe", "unknown"]) == "unknown"


def test_audit_is_read_only_for_existing_parquet_files(tmp_path: Path):
    hdata_root = tmp_path / "hdata"
    cache_root = tmp_path / "cache"
    report_root = tmp_path / "reports"
    _write_minimal_hdata(hdata_root)
    _write_minimal_cache(cache_root)

    target = hdata_root / "pivot_cache" / "2026" / "close.parquet"
    before = _sha256(target)

    report = audit_data_quality(
        project_root=tmp_path,
        hdata_root=hdata_root,
        cache_root=cache_root,
        report_root=report_root,
        audit_start=pd.Timestamp("2026-05-22"),
        audit_end=pd.Timestamp("2026-05-26"),
    )

    after = _sha256(target)
    assert before == after
    assert (report_root / "data_quality_propagation_2026.json").exists()
    assert (report_root / "data_quality_propagation_2026.md").exists()
    assert (report_root / "data_quality_propagation_2026_by_date.csv").exists()
    assert report["observed_raw_corruption_span_2026"]["first"] == "2026-05-25"
