"""Common utilities and pure functions for emotion-gate acceptance testing.

Shared between L1A and L1B acceptance tools.
"""

from __future__ import annotations

import hashlib
import importlib
import json
import math
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / "rebuild_from_archive"
STRATEGY = ROOT / "母版-20260506-Clone.py"
HDATA_ROOT = Path(r"D:\work space\hdata")
HDATA_SCRIPTS = HDATA_ROOT / "scripts"
FLOAT_TOL = 1e-9


def setup_runtime():
    if str(WORK) not in sys.path:
        sys.path.insert(0, str(WORK))
    if str(HDATA_SCRIPTS) not in sys.path:
        sys.path.insert(1, str(HDATA_SCRIPTS))
    if str(HDATA_ROOT) not in sys.path:
        sys.path.insert(2, str(HDATA_ROOT))
    if str(ROOT) not in sys.path:
        sys.path.insert(3, str(ROOT))
    sys.modules["jqdata"] = importlib.import_module("jqdata_compat")
    from core import hdata_reader
    from rebuild_from_archive.engine.core import Engine
    from rebuild_from_archive.engine.data_api import DataAPI
    from rebuild_from_archive.project_compat import EmotionGateJQCompat
    return hdata_reader, Engine, DataAPI, EmotionGateJQCompat


def _jsonable(value):
    if isinstance(value, (pd.Timestamp, pd.Timedelta)):
        return str(value)
    if isinstance(value, (np.floating, float)):
        if math.isnan(float(value)):
            return "NaN"
        return float(value)
    if isinstance(value, (np.integer, int)):
        return int(value)
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    return value


def get_source_commit() -> str:
    try:
        r = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                           capture_output=True, text=True, check=False)
        return r.stdout.strip() if r.returncode == 0 else "unknown"
    except Exception:
        return "unknown"


def get_main_commit() -> str:
    try:
        r = subprocess.run(
            ["git", "merge-base", "HEAD", "origin/main"],
            cwd=ROOT, capture_output=True, text=True, check=False,
        )
        return r.stdout.strip() if r.returncode == 0 else "unknown"
    except Exception:
        return "unknown"


def strategy_sha256() -> str:
    h = hashlib.sha256()
    h.update(STRATEGY.read_bytes())
    return h.hexdigest()


def load_strategy_code() -> str:
    return STRATEGY.read_text(encoding="utf-8")


def _nd(d):
    """Normalize date string for comparison: '20200114' -> '2020-01-14', '2020-01-14' -> '2020-01-14'."""
    if d is None:
        return ""
    raw = str(d).strip().split()[0] if " " in str(d) else str(d).strip()
    if len(raw) == 8 and raw.isdigit():
        return f"{raw[:4]}-{raw[4:6]}-{raw[6:]}"
    return raw


def _build_trade_keys(df: pd.DataFrame) -> list[str]:
    """Build stable trade keys from date+time+code+side+occurrence index."""
    keys = []
    counter = {}
    for _, row in df.iterrows():
        date = str(row.get("time", "")).split()[0] if "time" in row else str(row.get("date", ""))
        time_val = str(row.get("time", ""))
        code = str(row.get("code", ""))
        amount = float(row.get("amount", 0))
        side = "buy" if amount > 0 else "sell"
        base = f"{date}|{time_val}|{code}|{side}"
        counter[base] = counter.get(base, 0) + 1
        keys.append(f"{base}#{counter[base]}")
    return keys


def compare_baseline_file(
    run_path: Path, baseline_path: Path, suffix: str,
    key_col: str | list[str] | None = None,
) -> dict:
    """Compare a single baseline file for structural equality."""
    result = {
        "file_exists_current": run_path.exists() and run_path.stat().st_size > 2,
        "file_exists_baseline": baseline_path.exists() and baseline_path.stat().st_size > 2,
        "row_count_current": 0, "row_count_baseline": 0,
        "row_count_equal": False, "column_set_equal": False,
        "key_set_equal": False, "cell_diff_count": 0,
        "diff_rows": 0,
    }
    if not result["file_exists_current"] or not result["file_exists_baseline"]:
        result["diff_rows"] = -1
        return result
    rdf = pd.read_csv(run_path)
    bdf = pd.read_csv(baseline_path)
    result["row_count_current"] = len(rdf)
    result["row_count_baseline"] = len(bdf)
    result["row_count_equal"] = len(rdf) == len(bdf)
    run_cols = set(rdf.columns)
    base_cols = set(bdf.columns)
    result["column_set_equal"] = run_cols == base_cols

    if key_col is not None:
        kcols = [key_col] if isinstance(key_col, str) else list(key_col)
        if all(c in rdf.columns for c in kcols) and all(c in bdf.columns for c in kcols):
            run_keys = set(tuple(str(rdf[c].iloc[i]) for c in kcols) for i in range(len(rdf)))
            base_keys = set(tuple(str(bdf[c].iloc[i]) for c in kcols) for i in range(len(bdf)))
            result["key_set_equal"] = run_keys == base_keys

    diff_rows = 0
    common_cols = run_cols & base_cols
    if common_cols and len(rdf) == len(bdf):
        for i in range(len(rdf)):
            for col in sorted(common_cols):
                try:
                    v1 = float(rdf[col].iloc[i]) if pd.notna(rdf[col].iloc[i]) else float('nan')
                    v2 = float(bdf[col].iloc[i]) if pd.notna(bdf[col].iloc[i]) else float('nan')
                    if abs(v1 - v2) > FLOAT_TOL and not (pd.isna(v1) and pd.isna(v2)):
                        diff_rows += 1
                        break
                except (ValueError, TypeError):
                    if str(rdf[col].iloc[i]) != str(bdf[col].iloc[i]):
                        diff_rows += 1
                        break

    if not result["row_count_equal"]:
        diff_rows = max(diff_rows, abs(len(rdf) - len(bdf)))
    if not result["column_set_equal"]:
        diff_rows = max(diff_rows, len(run_cols ^ base_cols))
    if not result["key_set_equal"] and key_col is not None:
        diff_rows = max(diff_rows, 1)

    result["cell_diff_count"] = diff_rows
    result["diff_rows"] = diff_rows
    return result


def compare_state_files(current_path: Path, baseline_path: Path) -> tuple[int, list[dict]]:
    """Compare state files cell-by-cell and return diff count and diff rows list."""
    if not current_path.exists() or not baseline_path.exists():
        return -1, []
    rdf = pd.read_csv(current_path)
    bdf = pd.read_csv(baseline_path)
    
    diffs = []
    common_cols = sorted(list(set(rdf.columns) & set(bdf.columns)))
    for i in range(min(len(rdf), len(bdf))):
        row_date = str(rdf.loc[i, "date"])
        for col in common_cols:
            if col == "date":
                continue
            v1 = rdf.loc[i, col]
            v2 = bdf.loc[i, col]
            
            is_diff = False
            try:
                f1 = float(v1) if pd.notna(v1) else float('nan')
                f2 = float(v2) if pd.notna(v2) else float('nan')
                if abs(f1 - f2) > FLOAT_TOL and not (pd.isna(f1) and pd.isna(f2)):
                    is_diff = True
                    diff_val = f1 - f2
                else:
                    diff_val = 0.0
            except (ValueError, TypeError):
                if str(v1) != str(v2):
                    is_diff = True
                    diff_val = 1.0
            
            if is_diff:
                diffs.append({
                    "row": i,
                    "date": row_date,
                    "column": col,
                    "current_value": _jsonable(v1),
                    "baseline_value": _jsonable(v2),
                    "diff": _jsonable(diff_val)
                })
    return len(diffs), diffs
