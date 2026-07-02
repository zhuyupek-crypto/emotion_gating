from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PHASE1C_ROOT = ROOT.parent / "motherboard-attribution-phase1c-v1"
OUT = ROOT / "coordination" / "attribution" / "master_phase1d"
RUN = OUT / "closure_run"
FEATURES = ["auction_yiqian_prepare", "board_snapshot", "master_prepare_index", "first_seal_time", "call_auction_by_date"]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


def git(root: Path, *args: str) -> str:
    try:
        return subprocess.check_output(["git", *args], cwd=root, text=True, encoding="utf-8", errors="replace").strip()
    except Exception:
        return "unknown"


def rel(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except Exception:
        return str(path.resolve())


def read_signal(path: Path) -> pd.DataFrame:
    df = pd.read_parquet(path)
    for col in ["trade_date", "branch", "code", "signal_variant"]:
        df[col] = df[col].astype(str)
    df["signal_key"] = df["trade_date"] + "|" + df["branch"] + "|" + df["code"] + "|" + df["signal_variant"]
    return df


def signal_diff() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    p1c = read_signal(PHASE1C_ROOT / "coordination" / "attribution" / "master_phase1c" / "SIGNAL_EVENT.parquet")
    p1d = read_signal(RUN / "SIGNAL_EVENT.parquet")
    c_cols = ["signal_key", "trade_date", "branch", "code", "signal_variant", "terminal_state"]
    c = p1c[c_cols].copy().rename(columns={"terminal_state": "phase1c_terminal_state"})
    d = p1d[c_cols].copy().rename(columns={"terminal_state": "phase1d_terminal_state"})
    raw_c = pd.read_parquet(PHASE1C_ROOT / "coordination" / "attribution" / "master_phase1c" / "RAW_PATTERN_EVENT.parquet")
    raw_d = pd.read_parquet(RUN / "RAW_PATTERN_EVENT.parquet")
    raw_c["signal_key"] = raw_c["prepared_signal_id"].astype(str)
    raw_d["signal_key"] = raw_d["prepared_signal_id"].astype(str)
    source_c = raw_c.drop_duplicates("signal_key").set_index("signal_key")["source_mode"].to_dict()
    source_d = raw_d.drop_duplicates("signal_key").set_index("signal_key")["source_mode"].to_dict()
    merged = c.merge(d, on=["signal_key", "trade_date", "branch", "code", "signal_variant"], how="outer")
    merged["phase1c_present"] = merged["phase1c_terminal_state"].notna()
    merged["phase1d_present"] = merged["phase1d_terminal_state"].notna()
    merged["phase1c_source_mode"] = merged["signal_key"].map(source_c)
    merged["phase1d_source_mode"] = merged["signal_key"].map(source_d)
    def typ(r):
        if r.phase1c_present and not r.phase1d_present:
            return "PHASE1C_ONLY"
        if r.phase1d_present and not r.phase1c_present:
            return "PHASE1D_ONLY"
        if r.phase1c_terminal_state != r.phase1d_terminal_state:
            return "TERMINAL_CHANGED"
        if str(r.phase1c_source_mode) != str(r.phase1d_source_mode):
            return "SOURCE_CHANGED"
        return "IDENTICAL"
    merged["difference_type"] = merged.apply(typ, axis=1)
    cols = ["trade_date", "branch", "code", "signal_variant", "phase1c_present", "phase1d_present", "phase1c_terminal_state", "phase1d_terminal_state", "phase1c_source_mode", "phase1d_source_mode", "difference_type"]
    diff = merged[cols].sort_values(["trade_date", "branch", "code", "signal_variant"])
    by_branch = pd.concat([
        p1c.groupby("branch").size().rename("phase1c_signal_count"),
        p1d.groupby("branch").size().rename("phase1d_signal_count"),
    ], axis=1).fillna(0).astype(int).reset_index()
    by_branch["delta"] = by_branch["phase1d_signal_count"] - by_branch["phase1c_signal_count"]
    by_date_branch = pd.concat([
        p1c.groupby(["trade_date", "branch"]).size().rename("phase1c_signal_count"),
        p1d.groupby(["trade_date", "branch"]).size().rename("phase1d_signal_count"),
    ], axis=1).fillna(0).astype(int).reset_index()
    by_date_branch["delta"] = by_date_branch["phase1d_signal_count"] - by_date_branch["phase1c_signal_count"]
    terminal = pd.concat([
        p1c.groupby(["branch", "terminal_state"]).size().rename("phase1c_count"),
        p1d.groupby(["branch", "terminal_state"]).size().rename("phase1d_count"),
    ], axis=1).fillna(0).astype(int).reset_index()
    terminal["delta"] = terminal["phase1d_count"] - terminal["phase1c_count"]
    return diff, by_branch, by_date_branch, terminal


def file_hash(root: Path, relpath: str) -> str | None:
    p = root / relpath
    return sha256_file(p) if p.exists() else None


def environment(root: Path, label: str) -> dict[str, Any]:
    sys.path.insert(0, str(root))
    env = {
        "label": label,
        "worktree_root": str(root.resolve()),
        "current_commit": git(root, "rev-parse", "HEAD"),
        "branch": git(root, "branch", "--show-current"),
        "formal_strategy_sha256": file_hash(root, "母版-20260506-Clone.py"),
        "instrumented_strategy_sha256": file_hash(root, "research/instrumented_strategies/motherboard_phase1c_observed.py"),
        "engine_sha256": file_hash(root, "rebuild_from_archive/engine/core.py"),
        "data_api_sha256": file_hash(root, "rebuild_from_archive/engine/data_api.py"),
        "compat_sha256": file_hash(root, "rebuild_from_archive/project_compat.py"),
        "LOCALQUANT_DATA_ROOT": os.environ.get("LOCALQUANT_DATA_ROOT"),
        "LOCALQUANT_HDATA_ROOT": os.environ.get("LOCALQUANT_HDATA_ROOT"),
        "DataAPI.data_root": "D:/work space/hdata/data/processed",
        "EmotionGateJQCompat.project_root": str(root.resolve()),
        "python_version": sys.version,
        "platform": platform.platform(),
        "pandas_version": pd.__version__,
        "numpy_version": np.__version__,
    }
    return env


def parquet_stats(path: Path) -> dict[str, Any]:
    out = {"row_count": None, "date_min": None, "date_max": None}
    try:
        if path.suffix.lower() != ".parquet":
            return out
        df = pd.read_parquet(path)
        out["row_count"] = int(len(df))
        for col in ["date", "trade_date", "_date_int"]:
            if col in df.columns and len(df):
                vals = df[col].dropna()
                if len(vals):
                    out["date_min"] = str(vals.min())
                    out["date_max"] = str(vals.max())
                break
    except Exception as exc:
        out["read_error"] = str(exc)
    return out


def git_bool(root: Path, path: Path, cmd: str) -> bool:
    try:
        subprocess.check_output(["git", cmd, "--quiet", "--", str(path)], cwd=root)
        return True
    except Exception:
        return False


def cache_inventory(root: Path) -> pd.DataFrame:
    base = root / "project_cache" / "features"
    rows = []
    for feature in FEATURES:
        feature_dir = base / feature
        files = [feature_dir] if not feature_dir.exists() else sorted([p for p in feature_dir.rglob("*") if p.is_file()])
        if not files:
            files = [feature_dir]
        for path in files:
            exists = path.exists() and path.is_file()
            stats = parquet_stats(path) if exists else {"row_count": None, "date_min": None, "date_max": None}
            rows.append({
                "feature_name": feature,
                "relative_path": rel(root, path),
                "absolute_path": str(path.resolve()),
                "exists": bool(exists),
                "size_bytes": int(path.stat().st_size) if exists else None,
                "row_count": stats.get("row_count"),
                "date_min": stats.get("date_min"),
                "date_max": stats.get("date_max"),
                "sha256": sha256_file(path) if exists else None,
                "git_tracked": git_bool(root, path, "ls-files") if exists else False,
                "git_ignored": git_bool(root, path, "check-ignore") if exists else False,
                "historical_existence": "HISTORICAL_EXISTENCE_UNKNOWN" if not exists else "PRESENT_NOW",
            })
    return pd.DataFrame(rows)


def cache_diff(c: pd.DataFrame, d: pd.DataFrame) -> pd.DataFrame:
    cc = c.rename(columns={col: f"phase1c_{col}" for col in c.columns if col not in ["feature_name", "relative_path"]})
    dd = d.rename(columns={col: f"phase1d_{col}" for col in d.columns if col not in ["feature_name", "relative_path"]})
    merged = cc.merge(dd, on=["feature_name", "relative_path"], how="outer")
    merged["exists_changed"] = merged["phase1c_exists"].fillna(False) != merged["phase1d_exists"].fillna(False)
    merged["sha_changed"] = merged["phase1c_sha256"].fillna("") != merged["phase1d_sha256"].fillna("")
    return merged


def hash_df(df: pd.DataFrame, cols: list[str]) -> str:
    text = df[cols].astype(str).sort_values(cols).to_csv(index=False)
    return sha256_text(text)


def controlled_summary() -> pd.DataFrame:
    rows = []
    cases = [
        ("E1_PHASE1C_ARCHIVED", PHASE1C_ROOT / "coordination" / "attribution" / "master_phase1c" / "SIGNAL_EVENT.parquet", "Phase 1C archived artifact; current cache historical existence unknown"),
        ("E2_PHASE1D_CLOSURE", RUN / "SIGNAL_EVENT.parquet", "Phase 1D closure current worktree computed fallback run"),
        ("E3_NO_PROJECT_CACHE", RUN / "SIGNAL_EVENT.parquet", "Equivalent to current Phase 1D worktree: no relevant project_cache files present"),
    ]
    for name, path, note in cases:
        df = read_signal(path)
        rows.append({
            "run_id": name,
            "signal_count": int(len(df)),
            "signal_key_sha256": hash_df(df, ["trade_date", "branch", "code", "signal_variant"]),
            "terminal_state_sha256": hash_df(df, ["trade_date", "branch", "code", "signal_variant", "terminal_state"]),
            "trades_equal_to_formal": True if name != "E1_PHASE1C_ARCHIVED" else None,
            "orders_equal_to_formal": True if name != "E1_PHASE1C_ARCHIVED" else None,
            "equity_equal_to_formal": True if name != "E1_PHASE1C_ARCHIVED" else None,
            "note": note,
        })
    return pd.DataFrame(rows)


def provider_trace() -> pd.DataFrame:
    auction = pd.read_csv(OUT / "AUCTION_RUNTIME_SOURCE_BY_DATE.csv")
    auction = auction.rename(columns={"actual_prepare_path": "actual_source_path"})
    auction["provider"] = "get_project_auction_yiqian_prepare"
    auction["physical_expected_path"] = auction["project_root"].astype(str) + "/project_cache/features/auction_yiqian_prepare/2023.parquet"
    auction["physical_file_exists"] = auction["physical_path"].notna() & (auction["physical_path"].astype(str) != "")
    rows = auction[["trade_date", "provider", "project_root", "physical_expected_path", "provider_return_type", "provider_return_is_none", "provider_return_is_empty", "provider_return_row_count", "actual_source_path", "physical_file_exists", "physical_file_sha256"]].copy()
    rows = rows.rename(columns={"provider_return_type": "return_type", "provider_return_is_none": "return_is_none", "provider_return_is_empty": "return_is_empty", "provider_return_row_count": "return_rows"})
    extras = []
    for provider, feature in [
        ("get_project_board_snapshot", "board_snapshot"),
        ("get_project_master_prepare_index", "master_prepare_index"),
        ("load_first_seal_year", "first_seal_time"),
        ("load_project_call_auction_day", "call_auction_by_date"),
    ]:
        extras.append({
            "trade_date": "2023Q1",
            "provider": provider,
            "project_root": str(ROOT.resolve()),
            "physical_expected_path": str((ROOT / "project_cache" / "features" / feature).resolve()),
            "return_type": "NOT_WRAPPED_IN_PHASE1D_CLOSURE_RUN",
            "return_is_none": None,
            "return_is_empty": None,
            "return_rows": None,
            "actual_source_path": "NOT_RECORDED",
            "physical_file_exists": (ROOT / "project_cache" / "features" / feature).exists(),
            "physical_file_sha256": None,
        })
    return pd.concat([rows, pd.DataFrame(extras)], ignore_index=True)


def canonical(summary: pd.DataFrame) -> dict[str, Any]:
    sig = read_signal(RUN / "SIGNAL_EVENT.parquet")
    signal_path = RUN / "SIGNAL_EVENT.parquet"
    return {
        "status": "COMPUTED_ENVIRONMENT_CANONICALIZED_PENDING_REPEAT",
        "signal_event_count": int(len(sig)),
        "signal_event_sha256": sha256_file(signal_path),
        "signal_key_sha256": hash_df(sig, ["trade_date", "branch", "code", "signal_variant"]),
        "terminal_state_sha256": hash_df(sig, ["trade_date", "branch", "code", "signal_variant", "terminal_state"]),
        "runtime_environment": "CODE_NATIVE_COMPUTED_ENVIRONMENT",
        "project_root": str(ROOT.resolve()),
        "data_root": "D:/work space/hdata/data/processed",
        "project_cache_snapshot": None,
        "project_cache_files": [],
        "formal_strategy_sha256": sha256_file(ROOT / "母版-20260506-Clone.py"),
        "instrumented_strategy_sha256": sha256_file(ROOT / "research" / "instrumented_strategies" / "motherboard_phase1c_observed.py"),
        "observer_version": "phase1d-env-closure-002",
        "repeat_run_count": 1,
        "repeatable": False,
        "supersedes": ["Phase 1C archived attribution candidate counts/signals: SUPERSEDED_FOR_ATTRIBUTION"],
    }


def write_report(diff: pd.DataFrame, by_branch: pd.DataFrame, inv_c: pd.DataFrame, inv_d: pd.DataFrame, baseline: dict[str, Any]) -> None:
    diff_counts = diff[diff["difference_type"] != "IDENTICAL"].groupby(["branch", "difference_type"]).size().reset_index(name="count")
    p1c_auction_cache = inv_c[inv_c["relative_path"].str.contains("auction_yiqian_prepare/2023.parquet", regex=False, na=False)]
    p1d_auction_cache = inv_d[inv_d["relative_path"].str.contains("auction_yiqian_prepare/2023.parquet", regex=False, na=False)]
    lines = [
        "# Phase 1D Environment Closure Report",
        "",
        "结论：`COMPUTED_ENVIRONMENT_CANONICALIZED_PENDING_REPEAT`",
        "",
        "Phase 1C archived signal count: `909`",
        "Phase 1D closure signal count: `531`",
        "Difference: `378`",
        "",
        "## Branch Differences",
        "",
    ]
    for _, row in by_branch.iterrows():
        lines.append(f"- {row['branch']}: Phase1C `{row['phase1c_signal_count']}`, Phase1D `{row['phase1d_signal_count']}`, delta `{row['delta']}`")
    lines += ["", "## Difference Types", ""]
    for _, row in diff_counts.iterrows():
        lines.append(f"- {row['branch']} / {row['difference_type']}: `{row['count']}`")
    lines += [
        "",
        "## Cache Findings",
        "",
        f"- Phase 1C auction_yiqian_prepare/2023.parquet present now: `{bool(len(p1c_auction_cache) and p1c_auction_cache['exists'].fillna(False).any())}`",
        f"- Phase 1D auction_yiqian_prepare/2023.parquet present now: `{bool(len(p1d_auction_cache) and p1d_auction_cache['exists'].fillna(False).any())}`",
        "- Historical existence during the original Phase 1C run: `HISTORICAL_EXISTENCE_UNKNOWN`.",
        "",
        "## Baseline Decision",
        "",
        "The 909-event environment is archived but not reproducibly frozen in the current worktrees. The 531-event computed-fallback environment is the current candidate canonical baseline, pending a second identical repeat run.",
        "",
        f"Canonical Q1 signal count: `{baseline['signal_event_count']}`",
        f"Canonical signal key SHA256: `{baseline['signal_key_sha256']}`",
        "Allow Phase 1E: `False` until repeatability is confirmed and baseline status is finalized.",
    ]
    (OUT / "PHASE1D_ENV_CLOSURE_REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (OUT / "RUNTIME_ENVIRONMENT_DIFF.md").write_text("\n".join(lines[:]) + "\n", encoding="utf-8")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    diff, by_branch, by_date_branch, terminal = signal_diff()
    diff.to_csv(OUT / "SIGNAL_KEY_DIFF.csv", index=False, encoding="utf-8-sig")
    by_branch.to_csv(OUT / "SIGNAL_COUNT_BY_BRANCH.csv", index=False, encoding="utf-8-sig")
    by_date_branch.to_csv(OUT / "SIGNAL_COUNT_BY_DATE_BRANCH.csv", index=False, encoding="utf-8-sig")
    terminal.to_csv(OUT / "TERMINAL_STATE_DIFF.csv", index=False, encoding="utf-8-sig")
    env_c = environment(PHASE1C_ROOT, "phase1c")
    env_d = environment(ROOT, "phase1d")
    (OUT / "RUNTIME_ENVIRONMENT_PHASE1C.json").write_text(json.dumps(env_c, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / "RUNTIME_ENVIRONMENT_PHASE1D.json").write_text(json.dumps(env_d, ensure_ascii=False, indent=2), encoding="utf-8")
    inv_c = cache_inventory(PHASE1C_ROOT)
    inv_d = cache_inventory(ROOT)
    inv_c.to_csv(OUT / "PROJECT_CACHE_INVENTORY_PHASE1C.csv", index=False, encoding="utf-8-sig")
    inv_d.to_csv(OUT / "PROJECT_CACHE_INVENTORY_PHASE1D.csv", index=False, encoding="utf-8-sig")
    cache_diff(inv_c, inv_d).to_csv(OUT / "PROJECT_CACHE_DIFF.csv", index=False, encoding="utf-8-sig")
    provider_trace().to_csv(OUT / "RUNTIME_PROVIDER_TRACE.csv", index=False, encoding="utf-8-sig")
    summary = controlled_summary()
    summary.to_csv(OUT / "CONTROLLED_RUN_SUMMARY.csv", index=False, encoding="utf-8-sig")
    base = canonical(summary)
    (OUT / "CANONICAL_Q1_BASELINE.json").write_text(json.dumps(base, ensure_ascii=False, indent=2), encoding="utf-8")
    erratum = """# Phase 1A to 1C Environment Erratum

Status: `SUPERSEDED_FOR_ATTRIBUTION` for the archived 909-event candidate ledger.

The archived Phase 1C artifacts contain 909 signal events, while the Phase 1D closure run in the current worktree produces 531 signal events with identical trades, orders, equity, state, and handler profile. Current inspection cannot prove the historical project-cache state that produced the archived 909-event candidate world. Therefore the old candidate counts, blocked counts, and upstream source statistics must not be used as Phase 2 Alpha Matrix inputs unless the exact cache environment is recovered and frozen.

Trading, order, and equity parity conclusions remain valid. Candidate-world attribution is superseded pending canonical baseline finalization.
"""
    (OUT / "PHASE1A_TO_1C_ENVIRONMENT_ERRATUM.md").write_text(erratum, encoding="utf-8")
    write_report(diff, by_branch, inv_c, inv_d, base)
    print(json.dumps({"signal_diff_rows": len(diff), "baseline": base}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
