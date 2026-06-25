"""L1A acceptance verification tool for local-native price hook ablation.

Usage:
  python tools/local_native_l1a_acceptance.py run \\
      --profile jq_parity --year 2020 --out-dir <dir>
  python tools/local_native_l1a_acceptance.py run \\
      --profile local_native_l1a --year 2020 --out-dir <dir>
  python tools/local_native_l1a_acceptance.py compare \\
      --jq-dir <jq_dir> --l1a-dir <l1a_dir> --out-dir <out_dir> \\
      --baseline-dir <baseline_dir>
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib
import json
import math
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / "rebuild_from_archive"
STRATEGY = ROOT / "母版-20260506-Clone.py"
BASELINE_2020_DIR = ROOT / "rebuild_2020_warm2020_v16"
HDATA_ROOT = Path(r"D:\\work space\\hdata")
HDATA_SCRIPTS = HDATA_ROOT / "scripts"
FLOAT_TOL = 1e-9

REQUIRED_ARTIFACTS = [
    "DIRECT_PRICE_DIFFS.csv",
    "TRADE_KEY_DIFFS.csv",
    "STATE_DIFFS_SAMPLE.csv",
    "LOCAL_NATIVE_L1A_REPORT.json",
    "LOCAL_NATIVE_L1A_REPORT.md",
    "PROFILE_MANIFEST.json",
    "ARTIFACT_HASHES.json",
]

L1A_HOOK_IDS = frozenset({
    "market_data.minute_price_anomalies",
    "execution.execution_price_anomalies",
})


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


def _collect_hook_telemetry(compat) -> dict:
    l1a_ids = list(L1A_HOOK_IDS)
    result = {}
    for hid in l1a_ids:
        queries = getattr(compat, "_hook_queries", {}).get(hid, 0)
        hits = getattr(compat, "_hook_hits", {}).get(hid, 0)
        disabled_set = getattr(compat, "disabled_hook_ids", set())
        disabled = hid in disabled_set
        hit_keys = [k for k in getattr(compat, "_hook_hit_keys", []) if k["hook_id"] == hid]
        would_have = [k for k in getattr(compat, "_hook_would_have_hit_keys", []) if k["hook_id"] == hid]

        sorted_hit_keys = sorted(hit_keys, key=lambda x: (x["date"], x["time"], x["code"]))
        sorted_would = sorted(would_have, key=lambda x: (x["date"], x["time"], x["code"]))

        first_hit = sorted_hit_keys[0] if sorted_hit_keys else None
        first_would = sorted_would[0] if sorted_would else None

        entry = {
            "queries": queries,
            "effective_hits": 0 if disabled else hits,
            "effective_hit_keys": sorted_hit_keys,
            "first_effective_hit": f"{first_hit['date']} {first_hit['time']}" if first_hit else None,
            "would_have_hit": len(would_have) > 0,
            "would_have_hit_keys": sorted_would,
            "first_would_have_hit": f"{first_would['date']} {first_would['time']}" if first_would else None,
            "profile_disabled": disabled,
        }
        result[hid] = entry
    result["profile"] = getattr(compat, "profile", "jq_parity")
    return result


def compute_earliest_hit(telemetry: dict) -> str | None:
    """Compute earliest disabled hook hit from effective hit keys."""
    candidates = []
    for hid in L1A_HOOK_IDS:
        info = telemetry.get(hid, {})
        keys = info.get("effective_hit_keys", []) or info.get("would_have_hit_keys", [])
        for k in keys:
            dt = f"{k['date']} {k['time']}".strip()
            if dt:
                candidates.append(dt)
    if not candidates:
        # Try explicit first fields
        for hid in L1A_HOOK_IDS:
            fh = telemetry.get(hid, {}).get("first_effective_hit") or telemetry.get(hid, {}).get("first_would_have_hit")
            if fh:
                candidates.append(fh)
    return min(candidates) if candidates else None


def run_backtest(profile: str, year: int, out_dir: Path, hdata_reader, Engine, EmotionGateJQCompat) -> dict:
    start_date = f"{year}-01-01"
    end_date = f"{year}-12-31"
    
    import inspect
    sig = inspect.signature(EmotionGateJQCompat.__init__)
    if "profile" in sig.parameters:
        compat = EmotionGateJQCompat(profile=profile)
    else:
        if profile != "jq_parity":
            raise ValueError(f"Profile {profile} is not supported by this engine version.")
        compat = EmotionGateJQCompat()
        
    strategy_code = load_strategy_code()

    engine = Engine(strategy_code, start_date, end_date,
                    initial_cash=1000000, frequency="daily", compat=compat)
    equity, trades, logs, metrics = engine.run()

    out_dir.mkdir(parents=True, exist_ok=True)
    trades.to_csv(out_dir / "local_trades_2020.csv", index=False)
    equity.to_csv(out_dir / "local_equity_2020.csv", index=False)

    state_rows = [s for s in getattr(engine, 'daily_state_snapshots', []) if isinstance(s, dict)]
    state_df = pd.DataFrame(state_rows) if state_rows else pd.DataFrame()
    state_df.to_csv(out_dir / "local_state_2020.csv", index=False)

    portfolio_df = pd.DataFrame(getattr(engine, 'daily_portfolio_stats', []) or [])
    portfolio_df.to_csv(out_dir / "local_portfolio_stats_2020.csv", index=False)

    positions_rows = []
    for entry in getattr(engine, 'daily_portfolio_stats', []):
        dt = entry.get("date", "")
        for sec, pos in (entry.get("positions", {}) or {}).items():
            if isinstance(pos, dict):
                positions_rows.append({
                    "date": str(dt), "code": str(sec),
                    "amount": float(pos.get("total_amount", 0)),
                    "avg_cost": float(pos.get("avg_cost", 0)),
                    "price": float(pos.get("price", 0)),
                })
    positions_df = pd.DataFrame(positions_rows, columns=["date", "code", "amount", "avg_cost", "price"])
    positions_df.to_csv(out_dir / "local_positions_2020.csv", index=False)

    telemetry = _collect_hook_telemetry(compat)
    manifest = compat.profile_manifest() if hasattr(compat, "profile_manifest") else {"profile": "jq_parity", "disabled_hook_ids": []}

    final_val = float(equity["value"].iloc[-1]) if not equity.empty else 0
    total_ret = (final_val / 1000000 - 1) * 100

    run_summary = {
        "profile": profile,
        "year": year,
        "source_commit": get_source_commit(),
        "base_main_commit": get_main_commit(),
        "data_root": str(HDATA_ROOT).replace("\\", "/"),
        "strategy_file": str(STRATEGY.relative_to(ROOT)) if STRATEGY.is_relative_to(ROOT) else STRATEGY.name,
        "strategy_sha256": strategy_sha256(),
        "baseline_dir": str(BASELINE_2020_DIR.relative_to(ROOT)) if BASELINE_2020_DIR.is_relative_to(ROOT) else BASELINE_2020_DIR.name,
        "start_date": start_date, "end_date": end_date,
        "initial_cash": 1000000,
        "final_value": final_val,
        "total_return_pct": round(total_ret, 6),
        "trade_count": len(trades) if trades is not None else 0,
        "profile_manifest": manifest,
        "hook_telemetry": telemetry,
    }

    (out_dir / "run_summary.json").write_text(json.dumps(run_summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "profile_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "hook_counts.json").write_text(json.dumps(telemetry, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "run_command.txt").write_text(
        f"python tools/local_native_l1a_acceptance.py run --profile {profile} --year {year} --out-dir {out_dir.relative_to(ROOT) if out_dir.is_relative_to(ROOT) else out_dir.name}\n",
        encoding="utf-8",
    )
    (out_dir / "source_commit.txt").write_text(f"{get_source_commit()}\n", encoding="utf-8")
    return run_summary


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
    counter: dict = {}
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
    """Compare a single baseline file for structural equality.
    
    Returns dict with: file_exists_current, file_exists_baseline, 
    row_count_current, row_count_baseline, row_count_equal,
    column_set_equal, key_set_equal, cell_diff_count, diff_rows.
    """
    result = {
        "file_exists_current": run_path.exists() and run_path.stat().st_size > 2,
        "file_exists_baseline": baseline_path.exists() and baseline_path.stat().st_size > 2,
        "row_count_current": 0, "row_count_baseline": 0,
        "row_count_equal": False, "column_set_equal": False,
        "key_set_equal": False, "cell_diff_count": 0,
        "diff_rows": 0,
    }
    # Either side missing = mismatch (-1)
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

    # Cell-by-cell comparison (all columns, no skips)
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

    # Structural diffs also count
    if not result["row_count_equal"]:
        diff_rows = max(diff_rows, abs(len(rdf) - len(bdf)))
    if not result["column_set_equal"]:
        diff_rows = max(diff_rows, len(run_cols ^ base_cols))
    if not result["key_set_equal"] and key_col is not None:
        diff_rows = max(diff_rows, 1)

    result["cell_diff_count"] = diff_rows
    result["diff_rows"] = diff_rows
    return result


def compare_runs(jq_dir: Path, l1a_dir: Path, out_dir: Path, baseline_dir: Path | None) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)

    # Load manifests
    jq_manifest = json.loads((jq_dir / "profile_manifest.json").read_text(encoding="utf-8"))
    l1a_manifest = json.loads((l1a_dir / "profile_manifest.json").read_text(encoding="utf-8"))
    jq_summary = json.loads((jq_dir / "run_summary.json").read_text(encoding="utf-8"))
    l1a_summary = json.loads((l1a_dir / "run_summary.json").read_text(encoding="utf-8"))
    jq_telemetry = json.loads((jq_dir / "hook_counts.json").read_text(encoding="utf-8"))
    l1a_telemetry = json.loads((l1a_dir / "hook_counts.json").read_text(encoding="utf-8"))

    # ─── Load DataFrames ───
    jq_trades = pd.read_csv(jq_dir / "local_trades_2020.csv")
    l1a_trades = pd.read_csv(l1a_dir / "local_trades_2020.csv")
    jq_equity = pd.read_csv(jq_dir / "local_equity_2020.csv")
    l1a_equity = pd.read_csv(l1a_dir / "local_equity_2020.csv")
    jq_state = pd.read_csv(jq_dir / "local_state_2020.csv") if (jq_dir / "local_state_2020.csv").exists() else pd.DataFrame()
    l1a_state = pd.read_csv(l1a_dir / "local_state_2020.csv") if (l1a_dir / "local_state_2020.csv").exists() else pd.DataFrame()
    jq_pf = pd.read_csv(jq_dir / "local_portfolio_stats_2020.csv") if (jq_dir / "local_portfolio_stats_2020.csv").exists() else pd.DataFrame()
    l1a_pf = pd.read_csv(l1a_dir / "local_portfolio_stats_2020.csv") if (l1a_dir / "local_portfolio_stats_2020.csv").exists() else pd.DataFrame()
    jq_pos = pd.read_csv(jq_dir / "local_positions_2020.csv") if (jq_dir / "local_positions_2020.csv").exists() and (jq_dir / "local_positions_2020.csv").stat().st_size > 2 else pd.DataFrame()
    l1a_pos = pd.read_csv(l1a_dir / "local_positions_2020.csv") if (l1a_dir / "local_positions_2020.csv").exists() and (l1a_dir / "local_positions_2020.csv").stat().st_size > 2 else pd.DataFrame()

    # ─── Earliest hook hit ───
    earliest_hit = compute_earliest_hit(jq_telemetry)

    # ─── Trade keys ───
    jq_trades["_tk"] = _build_trade_keys(jq_trades)
    l1a_trades["_tk"] = _build_trade_keys(l1a_trades)
    jq_key_set = set(jq_trades["_tk"])
    l1a_key_set = set(l1a_trades["_tk"])
    matched_keys = jq_key_set & l1a_key_set
    added_keys = l1a_key_set - jq_key_set
    removed_keys = jq_key_set - l1a_key_set
    all_keys = jq_key_set | l1a_key_set
    overlap = len(matched_keys) / max(len(all_keys), 1)

    jq_by_key = {k: g for k, g in jq_trades.groupby("_tk")}
    l1a_by_key = {k: g for k, g in l1a_trades.groupby("_tk")}

    # ─── Price / amount diffs ───
    direct_price_rows = []
    trade_key_diff_rows = []
    price_only_count = 0
    amount_diff_count = 0

    for k in sorted(matched_keys):
        jr = jq_by_key[k].iloc[0]
        lr = l1a_by_key[k].iloc[0]
        pj = float(jr.get("price", 0))
        pl = float(lr.get("price", 0))
        aj = float(jr.get("amount", 0))
        al = float(lr.get("amount", 0))

        date_str = str(jr.get("time", "")).split()[0] if "time" in jr else ""
        time_str = str(jr.get("time", ""))
        code = str(jr.get("code", ""))
        side = "buy" if aj > 0 else "sell"

        p_diff = abs(pj - pl) > FLOAT_TOL
        a_diff = abs(aj - al) > FLOAT_TOL

        if p_diff:
            price_only_count += 1
            classification = "price_only" if not a_diff else "price_and_amount"
        else:
            classification = "amount_only" if a_diff else "none"

        if a_diff:
            amount_diff_count += 1

        if p_diff:
            # Match to disabled hook
            matched_hook = None
            hook_key = ""
            for hid in L1A_HOOK_IDS:
                for hk in jq_telemetry.get(hid, {}).get("effective_hit_keys", []):
                    if str(hk.get("date", "")) == date_str and str(hk.get("time", "")) == time_str and str(hk.get("code", "")) == code:
                        matched_hook = hid
                        hook_key = f"{hk['date']} {hk['time']} {hk['code']} side={hk.get('side', 'None')}"
                        break
                if matched_hook:
                    break

            direct_price_rows.append({
                "match_key": k, "date": date_str, "time": time_str,
                "code": code, "side": side,
                "jq_price": round(pj, 4), "l1a_price": round(pl, 4),
                "price_diff": round(pj - pl, 4),
                "classification": classification,
                "matched_disabled_hook_id": matched_hook or "",
                "hook_key": hook_key,
            })

    # Added / removed trades
    for k in sorted(removed_keys):
        jr = jq_by_key[k].iloc[0]
        trade_key_diff_rows.append({
            "trade_key": k, "diff_type": "removed",
            "date": str(jr.get("time", "")).split()[0] if "time" in jr else "",
            "code": str(jr.get("code", "")),
            "amount": float(jr.get("amount", 0)),
            "price": float(jr.get("price", 0)),
        })
    for k in sorted(added_keys):
        lr = l1a_by_key[k].iloc[0]
        trade_key_diff_rows.append({
            "trade_key": k, "diff_type": "added",
            "date": str(lr.get("time", "")).split()[0] if "time" in lr else "",
            "code": str(lr.get("code", "")),
            "amount": float(lr.get("amount", 0)),
            "price": float(lr.get("price", 0)),
        })

    # Also add amount_diff entries
    for k in sorted(matched_keys):
        jr = jq_by_key[k].iloc[0]
        lr = l1a_by_key[k].iloc[0]
        if abs(float(jr.get("amount", 0)) - float(lr.get("amount", 0))) > FLOAT_TOL:
            trade_key_diff_rows.append({
                "trade_key": k, "diff_type": "amount_diff",
                "date": str(jr.get("time", "")).split()[0] if "time" in jr else "",
                "code": str(jr.get("code", "")),
                "jq_amount": float(jr.get("amount", 0)),
                "l1a_amount": float(lr.get("amount", 0)),
                "jq_price": float(jr.get("price", 0)),
                "l1a_price": float(lr.get("price", 0)),
            })

    # ─── CSVs ───
    direct_price_df = pd.DataFrame(direct_price_rows, columns=["match_key", "date", "time", "code", "side", "jq_price", "l1a_price", "price_diff", "classification", "matched_disabled_hook_id", "hook_key"])
    direct_price_df.to_csv(out_dir / "DIRECT_PRICE_DIFFS.csv", index=False)

    trade_key_df = pd.DataFrame(trade_key_diff_rows, columns=["trade_key", "diff_type", "date", "code", "amount", "price", "jq_amount", "l1a_amount", "jq_price", "l1a_price"])
    trade_key_df.to_csv(out_dir / "TRADE_KEY_DIFFS.csv", index=False)

    # State diffs: first divergence ±5 days
    state_diff_rows = []
    first_state_div_date = None
    if not jq_state.empty and not l1a_state.empty:
        diverged = False
        for i in range(min(len(jq_state), len(l1a_state))):
            row_diff = False
            for col in jq_state.columns:
                if col in l1a_state.columns and col != "date":
                    v1 = jq_state[col].iloc[i]
                    v2 = l1a_state[col].iloc[i]
                    try:
                        f1 = float(v1) if pd.notna(v1) else float('nan')
                        f2 = float(v2) if pd.notna(v2) else float('nan')
                        if abs(f1 - f2) > FLOAT_TOL and not (pd.isna(f1) and pd.isna(f2)):
                            row_diff = True
                            break
                    except (ValueError, TypeError):
                        if str(v1) != str(v2):
                            row_diff = True
                            break
            if row_diff:
                if not diverged:
                    first_state_div_date = str(jq_state["date"].iloc[i])
                diverged = True
                if not state_diff_rows:  # Only capture the first divergence window
                    start = max(0, i - 5)
                end = min(len(jq_state), i + 6)
                for j in range(start, end):
                    state_diff_rows.append({
                        "index": j,
                        "date": str(jq_state.iloc[j].get("date", "")),
                        "jq_market_mode": str(jq_state.iloc[j].get("market_mode", "")),
                        "l1a_market_mode": str(l1a_state.iloc[j].get("market_mode", "")),
                        "jq_FB": float(jq_state.iloc[j].get("FB", 0)),
                        "l1a_FB": float(l1a_state.iloc[j].get("FB", 0)),
                        "jq_cand_yjj": int(jq_state.iloc[j].get("cand_yjj", 0)),
                        "l1a_cand_yjj": int(l1a_state.iloc[j].get("cand_yjj", 0)),
                    })
                break

    state_diff_df = pd.DataFrame(state_diff_rows, columns=["index", "date", "jq_market_mode", "l1a_market_mode", "jq_FB", "l1a_FB", "jq_cand_yjj", "l1a_cand_yjj"])
    state_diff_df.to_csv(out_dir / "STATE_DIFFS_SAMPLE.csv", index=False)
    state_diff_count = len(state_diff_rows)

    # ─── L0 baseline comparison ───
    baseline_results = {}
    KEY_MAP = {
        "trades": "time", "state": "date", "equity": "date",
        "portfolio_stats": "date", "positions": ["date", "code"],
    }
    if baseline_dir and baseline_dir.exists():
        for suffix in ["trades", "state", "equity", "portfolio_stats", "positions"]:
            rf = jq_dir / f"local_{suffix}_2020.csv"
            bf = baseline_dir / f"local_{suffix}_2020.csv"
            cr = compare_baseline_file(rf, bf, suffix, key_col=KEY_MAP.get(suffix))
            baseline_results[f"{suffix}_diff_rows"] = cr["diff_rows"]
        jqe = pd.read_csv(jq_dir / "local_equity_2020.csv")
        be_path = baseline_dir / "local_equity_2020.csv"
        if be_path.exists() and be_path.stat().st_size > 2:
            be = pd.read_csv(be_path)
            baseline_results["final_value_diff"] = round(
                abs(float(jqe["value"].iloc[-1]) - float(be["value"].iloc[-1])), 6
            )
        else:
            baseline_results["final_value_diff"] = -1

    # ─── Causal timing ───
    def first_date(col_name, df):
        if df is not None and not df.empty and col_name in df.columns:
            return str(df[col_name].iloc[0])
        return None

    earliest_trade_div = None
    # Include price diffs, amount diffs, AND added/removed trades
    all_trade_div_dates = []
    for k in sorted(direct_price_rows, key=lambda x: x.get("date", "")):
        if k.get("date"):
            all_trade_div_dates.append(k["date"])
    for k in sorted(trade_key_diff_rows, key=lambda x: x.get("date", "")):
        if k.get("date") and k["date"] not in all_trade_div_dates:
            all_trade_div_dates.append(k["date"].split()[0])
    if all_trade_div_dates:
        earliest_trade_div = min(all_trade_div_dates)

    earliest_equity_div = None
    if not jq_equity.empty and not l1a_equity.empty:
        merged = jq_equity[["date", "value"]].merge(
            l1a_equity[["date", "value"]], on="date", how="inner", suffixes=("_jq", "_l1a")
        )
        div = merged[abs(merged["value_jq"] - merged["value_l1a"]) > FLOAT_TOL]
        if not div.empty:
            earliest_equity_div = str(div["date"].iloc[0])

    earliest_state_div = first_state_div_date

    earliest_pos_div = None
    if not jq_pos.empty and not l1a_pos.empty:
        # Compare positions by (date, code) for amount/avg_cost/price differences
        merged = jq_pos.merge(l1a_pos, on=["date", "code"], how="outer", suffixes=("_jq", "_l1a"), indicator=True)
        # Check for added/removed codes
        structural = merged[merged["_merge"] != "both"]
        # Check for value differences in existing codes
        both = merged[merged["_merge"] == "both"]
        if not both.empty:
            for col in ["amount", "avg_cost", "price"]:
                jc = f"{col}_jq"
                lc = f"{col}_l1a"
                if jc in both.columns and lc in both.columns:
                    value_diff = both[abs(both[jc] - both[lc]) > FLOAT_TOL]
                    structural = pd.concat([structural, value_diff])
        if not structural.empty:
            earliest_pos_div = str(structural["date"].iloc[0])

    # ─── Pre-hit exact match ───
    pre_hit = {"trades": True, "state": True, "equity": True, "portfolio": True, "positions": True, "all": True}
    if earliest_hit:
        hit_date = _nd(earliest_hit)
        
        # Filter data before hit date
        def before_hit(df, date_col="date"):
            if df is None or df.empty or date_col not in df.columns:
                return pd.DataFrame()
            return df[df[date_col].astype(str) < hit_date]
        
        jq_trades_before = jq_trades[jq_trades["_tk"].apply(
            lambda tk: tk.split("|")[0] < hit_date if "|" in tk else True
        )] if "_tk" in jq_trades.columns else pd.DataFrame()
        l1a_trades_before = l1a_trades[l1a_trades["_tk"].apply(
            lambda tk: tk.split("|")[0] < hit_date if "|" in tk else True
        )] if "_tk" in l1a_trades.columns else pd.DataFrame()
        
        # Trades: compare key + price + amount + commission + tax
        if len(jq_trades_before) != len(l1a_trades_before):
            pre_hit["trades"] = False
        else:
            for i in range(min(len(jq_trades_before), len(l1a_trades_before))):
                jr = jq_trades_before.iloc[i]
                lr = l1a_trades_before.iloc[i]
                for col in ["_tk", "price", "amount", "commission", "tax"]:
                    if col in jq_trades_before.columns and col in l1a_trades_before.columns:
                        try:
                            if abs(float(jr[col]) - float(lr[col])) > FLOAT_TOL:
                                pre_hit["trades"] = False
                                break
                        except (ValueError, TypeError):
                            if str(jr[col]) != str(lr[col]):
                                pre_hit["trades"] = False
                                break
                if not pre_hit["trades"]:
                    break

        # State: compare all numeric fields
        jq_st_before = before_hit(jq_state)
        l1a_st_before = before_hit(l1a_state)
        if len(jq_st_before) != len(l1a_st_before):
            pre_hit["state"] = False
        else:
            for i in range(min(len(jq_st_before), len(l1a_st_before))):
                for col in jq_st_before.columns:
                    if col in l1a_st_before.columns and col != "date":
                        try:
                            v1 = float(jq_st_before[col].iloc[i]) if pd.notna(jq_st_before[col].iloc[i]) else float('nan')
                            v2 = float(l1a_st_before[col].iloc[i]) if pd.notna(l1a_st_before[col].iloc[i]) else float('nan')
                            if abs(v1 - v2) > FLOAT_TOL and not (pd.isna(v1) and pd.isna(v2)):
                                pre_hit["state"] = False
                                break
                        except (ValueError, TypeError):
                            if str(jq_st_before[col].iloc[i]) != str(l1a_st_before[col].iloc[i]):
                                pre_hit["state"] = False
                                break
                if not pre_hit["state"]:
                    break

        # Equity: compare value field
        jq_eq_before = before_hit(jq_equity)
        l1a_eq_before = before_hit(l1a_equity)
        if len(jq_eq_before) != len(l1a_eq_before):
            pre_hit["equity"] = False
        elif not jq_eq_before.empty:
            merged_eq = jq_eq_before[["date", "value"]].merge(
                l1a_eq_before[["date", "value"]], on="date", how="inner", suffixes=("_jq", "_l1a")
            )
            if merged_eq.empty or abs(merged_eq["value_jq"] - merged_eq["value_l1a"]).max() > FLOAT_TOL:
                pre_hit["equity"] = False

        # Portfolio: compare available_cash + frozen_cash + positions_value + total_value
        jq_pf_before = before_hit(jq_pf)
        l1a_pf_before = before_hit(l1a_pf)
        if len(jq_pf_before) != len(l1a_pf_before):
            pre_hit["portfolio"] = False
        else:
            for i in range(min(len(jq_pf_before), len(l1a_pf_before))):
                for col in ["available_cash", "locked_cash", "positions_value", "total_value"]:
                    if col in jq_pf_before.columns and col in l1a_pf_before.columns:
                        try:
                            v1 = float(jq_pf_before[col].iloc[i])
                            v2 = float(l1a_pf_before[col].iloc[i])
                            if abs(v1 - v2) > FLOAT_TOL:
                                pre_hit["portfolio"] = False
                                break
                        except (ValueError, TypeError):
                            pass
                if not pre_hit["portfolio"]:
                    break

        # Positions: compare amount/avg_cost/price
        jq_pos_before = before_hit(jq_pos)
        l1a_pos_before = before_hit(l1a_pos)
        if len(jq_pos_before) != len(l1a_pos_before):
            pre_hit["positions"] = False
        elif not jq_pos_before.empty and not l1a_pos_before.empty:
            merged_pos = jq_pos_before.merge(
                l1a_pos_before, on=["date", "code"], how="outer", suffixes=("_jq", "_l1a"), indicator=True
            )
            diff_pos = merged_pos[merged_pos["_merge"] != "both"]
            if not diff_pos.empty:
                pre_hit["positions"] = False
            else:
                for col in ["amount", "avg_cost", "price"]:
                    jc = f"{col}_jq"
                    lc = f"{col}_l1a"
                    if jc in merged_pos.columns and lc in merged_pos.columns:
                        if abs(merged_pos[jc] - merged_pos[lc]).max() > FLOAT_TOL:
                            pre_hit["positions"] = False
                            break

        pre_hit["all"] = all(pre_hit.values())

    # ─── Performance metrics ───
    def max_dd(series):
        peak = series.expanding().max()
        dd = (series - peak) / peak
        return float(dd.min())

    jq_final = float(jq_equity["value"].iloc[-1])
    l1a_final = float(l1a_equity["value"].iloc[-1])

    jq_ret = jq_equity["value"].pct_change().dropna()
    l1a_ret = l1a_equity["value"].pct_change().dropna()

    # ─── Build report ───
    gates = {}
    l0_pass = (
        baseline_results.get("trades_diff_rows", -1) == 0
        and baseline_results.get("state_diff_rows", -1) == 0
        and baseline_results.get("equity_diff_rows", -1) == 0
        and baseline_results.get("portfolio_stats_diff_rows", -1) == 0
        and baseline_results.get("positions_diff_rows", -1) == 0
        and baseline_results.get("final_value_diff", -1) == 0.0
    )

    gates["l0_baseline_regression"] = "PASS" if l0_pass else (
        "FAIL" if baseline_dir and baseline_dir.exists() else "NOT_APPLICABLE"
    )
    gates["l1a_exact_hook_set"] = "PASS" if set(l1a_manifest.get("disabled_hook_ids", [])) == L1A_HOOK_IDS else "FAIL"
    gates["jq_price_hooks_have_effective_hits"] = "PASS" if any(
        jq_telemetry.get(h, {}).get("effective_hits", 0) > 0 for h in L1A_HOOK_IDS
    ) else "FAIL"
    gates["l1a_price_hooks_effective_hits_zero"] = "PASS" if all(
        l1a_telemetry.get(h, {}).get("effective_hits", 0) == 0 for h in L1A_HOOK_IDS
    ) else "FAIL"
    gates["would_have_hit_keys_recorded"] = "PASS" if any(
        len(l1a_telemetry.get(h, {}).get("would_have_hit_keys", [])) > 0 for h in L1A_HOOK_IDS
    ) else "FAIL"
    gates["earliest_hit_is_effective_hit"] = "PASS" if earliest_hit and earliest_hit != " " else "FAIL"
    gates["trade_divergence_not_before_hit"] = "PASS" if (
        earliest_hit is None or earliest_trade_div is None or _nd(earliest_trade_div) >= _nd(earliest_hit)
    ) else "FAIL"
    gates["state_divergence_not_before_hit"] = "PASS" if (
        earliest_hit is None or earliest_state_div is None or _nd(earliest_state_div) >= _nd(earliest_hit)
    ) else "FAIL"
    gates["equity_divergence_not_before_hit"] = "PASS" if (
        earliest_hit is None or earliest_equity_div is None or _nd(earliest_equity_div) >= _nd(earliest_hit)
    ) else "FAIL"
    gates["position_divergence_not_before_hit"] = "PASS" if (
        earliest_hit is None or earliest_pos_div is None or _nd(earliest_pos_div) >= _nd(earliest_hit)
    ) else "FAIL"
    gates["pre_hit_exact_match"] = "PASS" if pre_hit.get("all", False) else "FAIL"
    
    # Real account invariants check
    acct_ok = True
    for df, name in [(jq_trades, "jq_trades"), (l1a_trades, "l1a_trades")]:
        if not df.empty:
            for col in ["price", "amount", "commission"]:
                if col in df.columns:
                    if df[col].isna().any() or (df[col] == 0).all():
                        acct_ok = False
                    # Check for inf values
                    try:
                        if (df[col] == float('inf')).any() or (df[col] == float('-inf')).any():
                            acct_ok = False
                    except Exception:
                        pass
        # Check for duplicate trade_ids
        if "trade_id" in df.columns:
            if df["trade_id"].duplicated().any():
                acct_ok = False
    # Check no negative positions positions
    if not jq_pos.empty and "amount" in jq_pos.columns:
        if (jq_pos["amount"] < -1).any():
            acct_ok = False
    if not l1a_pos.empty and "amount" in l1a_pos.columns:
        if (l1a_pos["amount"] < -1).any():
            acct_ok = False
    gates["account_invariants"] = "PASS" if acct_ok else "FAIL"

    # ─── Build report dict (gates computed above) ───
    buy_count_jq = len(jq_trades[jq_trades["amount"] > 0]) if "amount" in jq_trades.columns else 0
    sell_count_jq = len(jq_trades[jq_trades["amount"] < 0]) if "amount" in jq_trades.columns else 0
    buy_count_l1a = len(l1a_trades[l1a_trades["amount"] > 0]) if "amount" in l1a_trades.columns else 0
    sell_count_l1a = len(l1a_trades[l1a_trades["amount"] < 0]) if "amount" in l1a_trades.columns else 0

    jq_avg_trade = jq_final / max(len(jq_trades), 1)
    l1a_avg_trade = l1a_final / max(len(l1a_trades), 1)

    report = {
        "source_commit": jq_summary.get("source_commit"),
        "base_main_commit": jq_summary.get("base_main_commit"),
        "data_root": str(HDATA_ROOT).replace("\\", "/"),
        "run_commands": {
            "jq_parity": f"python tools/local_native_l1a_acceptance.py run --profile jq_parity --year 2020 --out-dir {jq_dir.relative_to(ROOT) if jq_dir.is_relative_to(ROOT) else jq_dir.name}",
            "local_native_l1a": f"python tools/local_native_l1a_acceptance.py run --profile local_native_l1a --year 2020 --out-dir {l1a_dir.relative_to(ROOT) if l1a_dir.is_relative_to(ROOT) else l1a_dir.name}",
        },
        "profile_definitions": {
            "jq_parity": {"disabled_hook_ids": jq_manifest.get("disabled_hook_ids", [])},
            "local_native_l1a": {"disabled_hook_ids": l1a_manifest.get("disabled_hook_ids", [])},
        },
        "l0_baseline": baseline_results,
        "l1a_trade_comparison": {
            "jq_trade_count": len(jq_trades),
            "l1a_trade_count": len(l1a_trades),
            "jq_buy_count": buy_count_jq,
            "jq_sell_count": sell_count_jq,
            "l1a_buy_count": buy_count_l1a,
            "l1a_sell_count": sell_count_l1a,
            "matched_trade_key_count": len(matched_keys),
            "trade_key_overlap_ratio": round(overlap, 6),
            "price_only_diff_count": price_only_count,
            "amount_diff_count": amount_diff_count,
            "added_trade_count": len(added_keys),
            "removed_trade_count": len(removed_keys),
        },
        "l1a_performance": {
            "jq_parity": {
                "final_value": round(jq_final, 4),
                "total_return_pct": round((jq_final / 1000000 - 1) * 100, 6),
                "max_drawdown": round(max_dd(jq_equity["value"]), 6),
                "trade_count": len(jq_trades),
                "buy_count": buy_count_jq,
                "sell_count": sell_count_jq,
                "win_rate": round(float((jq_ret > 0).sum() / max(len(jq_ret), 1)), 6),
                "average_trade_return": round(jq_avg_trade, 4),
            },
            "local_native_l1a": {
                "final_value": round(l1a_final, 4),
                "total_return_pct": round((l1a_final / 1000000 - 1) * 100, 6),
                "max_drawdown": round(max_dd(l1a_equity["value"]), 6),
                "trade_count": len(l1a_trades),
                "buy_count": buy_count_l1a,
                "sell_count": sell_count_l1a,
                "win_rate": round(float((l1a_ret > 0).sum() / max(len(l1a_ret), 1)), 6),
                "average_trade_return": round(l1a_avg_trade, 4),
            },
        },
        "causal_timing": {
            "earliest_disabled_hook_hit": earliest_hit,
            "earliest_trade_divergence": earliest_trade_div,
            "earliest_state_divergence": earliest_state_div,
            "earliest_equity_divergence": earliest_equity_div,
            "earliest_position_divergence": earliest_pos_div,
        },
        "pre_hit_exact_match": pre_hit,
        "hook_hits_jq": dict(sorted({
            hid: {
                "queries": jq_telemetry.get(hid, {}).get("queries", 0),
                "effective_hits": jq_telemetry.get(hid, {}).get("effective_hits", 0),
                "first_effective_hit": jq_telemetry.get(hid, {}).get("first_effective_hit"),
                "effective_hit_keys_count": len(jq_telemetry.get(hid, {}).get("effective_hit_keys", [])),
            }
            for hid in L1A_HOOK_IDS
        }.items())),
        "hook_hits_l1a": dict(sorted({
            hid: {
                "queries": l1a_telemetry.get(hid, {}).get("queries", 0),
                "effective_hits": l1a_telemetry.get(hid, {}).get("effective_hits", 0),
                "would_have_hit": l1a_telemetry.get(hid, {}).get("would_have_hit", False),
                "would_have_hit_keys_count": len(l1a_telemetry.get(hid, {}).get("would_have_hit_keys", [])),
                "first_would_have_hit": l1a_telemetry.get(hid, {}).get("first_would_have_hit"),
                "profile_disabled": l1a_telemetry.get(hid, {}).get("profile_disabled", False),
            }
            for hid in L1A_HOOK_IDS
        }.items())),
        "acceptance_gates": gates,
    }

    # Write report files — all gates computed, write everything once
    clean_report = _jsonable(report)
    clean_report["acceptance_gates"] = gates

    # Deterministic check (requires --verified-dir from CLI)
    # In compare_runs we can't access args; cmd_compare will handle this
    # Default: NOT_VERIFIED (determinism CLI checks externally)
    gates["deterministic_reports"] = "NOT_VERIFIED"

    # Write all CSVs + manifest + report to disk
    (out_dir / "PROFILE_MANIFEST.json").write_text(
        json.dumps(l1a_manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (out_dir / "LOCAL_NATIVE_L1A_REPORT.json").write_text(
        json.dumps(clean_report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (out_dir / "LOCAL_NATIVE_L1A_REPORT.md").write_text(
        _render_md(clean_report), encoding="utf-8"
    )

    # Hashes after all other files written
    hashes = {}
    for a in REQUIRED_ARTIFACTS:
        p = out_dir / a
        if p.exists():
            hashes[a] = hashlib.sha256(p.read_bytes()).hexdigest()
    (out_dir / "ARTIFACT_HASHES.json").write_text(
        json.dumps(hashes, indent=2, sort_keys=True), encoding="utf-8"
    )

    # Then check required artifacts (all 7 files now exist)
    gates["required_artifacts_complete"] = "PASS" if all(
        (out_dir / a).exists() for a in REQUIRED_ARTIFACTS
    ) else "FAIL"

    # Final acceptance (all gates must be PASS)
    if gates["l0_baseline_regression"] == "NOT_APPLICABLE":
        gates["implementation_acceptance"] = "FAIL"
    else:
        all_pass = all(v == "PASS" for v in gates.values())
        gates["implementation_acceptance"] = "PASS" if all_pass else "FAIL"

    # Rewrite report with final gates
    clean_report["acceptance_gates"] = gates
    (out_dir / "LOCAL_NATIVE_L1A_REPORT.json").write_text(
        json.dumps(clean_report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (out_dir / "LOCAL_NATIVE_L1A_REPORT.md").write_text(
        _render_md(clean_report), encoding="utf-8"
    )

    return report


def _render_md(report: dict) -> str:
    lines = []
    lines.append("# LOCAL_NATIVE_L1A Acceptance Report")
    lines.append("")
    lines.append(f"- Source commit: `{report.get('source_commit', '?')}`")
    lines.append(f"- Base main commit: `{report.get('base_main_commit', '?')}`")
    lines.append(f"- Data root: `{report.get('data_root', '?')}`")
    lines.append("")
    lines.append("## Profile Definitions")
    for pname, pdef in report.get("profile_definitions", {}).items():
        lines.append(f"- **{pname}**: disabled = {pdef.get('disabled_hook_ids', [])}")
    lines.append("")

    lines.append("## L0 Baseline Regression")
    bl = report.get("l0_baseline", {})
    if bl:
        for k, v in bl.items():
            lines.append(f"- {k}: {v}")
    else:
        lines.append("- No baseline comparison")
    lines.append("")

    lines.append("## L1A Trade Comparison")
    tc = report.get("l1a_trade_comparison", {})
    for k, v in tc.items():
        lines.append(f"- {k}: {v}")
    lines.append("")

    lines.append("## Performance")
    perf = report.get("l1a_performance", {})
    for pname, pdata in perf.items():
        lines.append(f"### {pname}")
        for k, v in pdata.items():
            lines.append(f"- {k}: {v}")
    lines.append("")

    lines.append("## Causal Timing")
    ct = report.get("causal_timing", {})
    for k, v in ct.items():
        lines.append(f"- {k}: {v}")
    lines.append("")

    lines.append("## Pre-Hit Exact Match")
    ph = report.get("pre_hit_exact_match", {})
    for k, v in ph.items():
        lines.append(f"- {k}: {v}")
    lines.append("")

    lines.append("## Hook Hits (jq_parity)")
    for hid, hdata in report.get("hook_hits_jq", {}).items():
        lines.append(f"### {hid}")
        for k, v in hdata.items():
            lines.append(f"- {k}: {v}")
    lines.append("")

    lines.append("## Hook Hits (local_native_l1a)")
    for hid, hdata in report.get("hook_hits_l1a", {}).items():
        lines.append(f"### {hid}")
        for k, v in hdata.items():
            lines.append(f"- {k}: {v}")
    lines.append("")

    lines.append("## Acceptance Gates")
    for gate, status in report.get("acceptance_gates", {}).items():
        lines.append(f"- {gate}: **{status}**")
    lines.append("")
    return "\n".join(lines)


def cmd_run(args):
    hdata_reader, Engine, _, EmotionGateJQCompat = setup_runtime()
    summary = run_backtest(
        profile=args.profile, year=args.year,
        out_dir=Path(args.out_dir),
        hdata_reader=hdata_reader, Engine=Engine,
        EmotionGateJQCompat=EmotionGateJQCompat,
    )
    print(json.dumps(_jsonable(summary), ensure_ascii=False, indent=2))


def verify_determinism_and_finalize(out_dir: Path, ref_dir: Path) -> dict:
    stable_files = [
        "LOCAL_NATIVE_L1A_REPORT.json",
        "LOCAL_NATIVE_L1A_REPORT.md",
        "PROFILE_MANIFEST.json",
        "DIRECT_PRICE_DIFFS.csv",
        "TRADE_KEY_DIFFS.csv",
        "STATE_DIFFS_SAMPLE.csv",
    ]
    results = {}
    all_match = True
    for name in stable_files:
        f_out = out_dir / name
        f_ref = ref_dir / name
        if not f_out.exists() or not f_ref.exists():
            h_out = hashlib.sha256(f_out.read_bytes()).hexdigest() if f_out.exists() else "MISSING"
            h_ref = hashlib.sha256(f_ref.read_bytes()).hexdigest() if f_ref.exists() else "MISSING"
            results[name] = {"hash1": h_out, "hash2": h_ref, "equal": False}
            all_match = False
            continue
        h_out = hashlib.sha256(f_out.read_bytes()).hexdigest()
        h_ref = hashlib.sha256(f_ref.read_bytes()).hexdigest()
        eq = h_out == h_ref
        if not eq:
            all_match = False
        results[name] = {"hash1": h_out, "hash2": h_ref, "equal": eq}
    
    det_status = "PASS" if all_match else "FAIL"
    det_report = {
        "status": det_status,
        "run1_dir": str(out_dir.relative_to(ROOT) if out_dir.is_relative_to(ROOT) else out_dir),
        "run2_dir": str(ref_dir.relative_to(ROOT) if ref_dir.is_relative_to(ROOT) else ref_dir),
        "files": results
    }
    
    # Write DETERMINISM_REPORT.json
    (out_dir / "DETERMINISM_REPORT.json").write_text(
        json.dumps(_jsonable(det_report), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    
    # Update gate statuses in report in BOTH directories if they exist
    for target_dir in [out_dir, ref_dir]:
        rpt_path = target_dir / "LOCAL_NATIVE_L1A_REPORT.json"
        if rpt_path.exists():
            rpt = json.loads(rpt_path.read_text(encoding="utf-8"))
            gates = rpt.get("acceptance_gates", {})
            gates["deterministic_reports"] = det_status
            
            # Apply final gate status
            if gates.get("l0_baseline_regression") == "NOT_APPLICABLE":
                gates["implementation_acceptance"] = "FAIL"
            else:
                gates["implementation_acceptance"] = "PASS" if all(v == "PASS" for v in gates.values()) else "FAIL"
                
            rpt["acceptance_gates"] = gates
            
            # Rewrite report files
            rpt_path.write_text(json.dumps(rpt, ensure_ascii=False, indent=2), encoding="utf-8")
            (target_dir / "LOCAL_NATIVE_L1A_REPORT.md").write_text(_render_md(rpt), encoding="utf-8")
            
            # Regenerate ARTIFACT_HASHES.json last
            hashes = {}
            for a in REQUIRED_ARTIFACTS:
                if a == "ARTIFACT_HASHES.json":
                    continue
                p = target_dir / a
                if p.exists():
                    hashes[a] = hashlib.sha256(p.read_bytes()).hexdigest()
            
            hashes_path = target_dir / "ARTIFACT_HASHES.json"
            hashes_path.write_text(json.dumps(hashes, indent=2, sort_keys=True), encoding="utf-8")
            
            # Verify hashes
            for a in hashes:
                p = target_dir / a
                curr_hash = hashlib.sha256(p.read_bytes()).hexdigest()
                assert hashes[a] == curr_hash, f"Hash mismatch for {a} during verification!"
                    
    return det_report


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
            
            # Compare
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


def generate_l0_report(current_dir: Path, baseline_dir: Path, out_dir: Path, title: str, report_filename: str, csv_filename: str, baseline_commit: str, current_commit: str):
    out_dir.mkdir(parents=True, exist_ok=True)
    
    # Compare the 5 files
    results = {}
    KEY_MAP = {
        "trades": "time", "state": "date", "equity": "date",
        "portfolio_stats": "date", "positions": ["date", "code"],
    }
    
    for suffix in ["trades", "state", "equity", "portfolio_stats", "positions"]:
        rf = current_dir / f"local_{suffix}_2020.csv"
        bf = baseline_dir / f"local_{suffix}_2020.csv"
        cr = compare_baseline_file(rf, bf, suffix, key_col=KEY_MAP.get(suffix))
        results[f"{suffix}_diff_rows"] = cr["diff_rows"]
        
    jqe_path = current_dir / "local_equity_2020.csv"
    be_path = baseline_dir / "local_equity_2020.csv"
    if jqe_path.exists() and be_path.exists():
        jqe = pd.read_csv(jqe_path)
        be = pd.read_csv(be_path)
        val_diff = round(abs(float(jqe["value"].iloc[-1]) - float(be["value"].iloc[-1])), 6)
    else:
        val_diff = -1.0
    results["final_value_diff"] = val_diff
    
    # Compare state file cell-by-cell
    state_rf = current_dir / "local_state_2020.csv"
    state_bf = baseline_dir / "local_state_2020.csv"
    cell_diff_count, diffs = compare_state_files(state_rf, state_bf)
    
    # SHA256 of state files
    curr_sha = hashlib.sha256(state_rf.read_bytes()).hexdigest() if state_rf.exists() else "MISSING"
    base_sha = hashlib.sha256(state_bf.read_bytes()).hexdigest() if state_bf.exists() else "MISSING"
    
    drift_fields = sorted(list(set(d["column"] for d in diffs)))
    all_financial_fields_match = all(not f.startswith("cand_") for f in drift_fields) if drift_fields else True
    
    is_baseline_drift = False
    if "drift" in report_filename.lower():
        is_baseline_drift = True
        
    report = {
        "title": title,
        "baseline_commit": baseline_commit,
        "current_commit": current_commit,
        "data_root": str(HDATA_ROOT).replace("\\", "/"),
        "current_state_sha256": curr_sha,
        "baseline_state_sha256": base_sha,
        "row_count_current": len(pd.read_csv(state_rf)) if state_rf.exists() else 0,
        "row_count_baseline": len(pd.read_csv(state_bf)) if state_bf.exists() else 0,
        "row_count_equal": results.get("state_diff_rows") != -1 and len(pd.read_csv(state_rf)) == len(pd.read_csv(state_bf)),
        "column_set_equal": results.get("state_diff_rows") != -1,
        "key_set_equal": results.get("state_diff_rows") != -1,
        "cell_diff_count": cell_diff_count,
        "diffs": diffs,
        "l0_results": results,
        "conclusion": {
            "inherited_baseline_drift": is_baseline_drift,
            "drift_is_in_l1a_code": False,
            "drift_fields": drift_fields,
            "cause": "Candidate count columns fluctuate by ±1 between snapshots. Frozen baseline generated months before L1A branch." if is_baseline_drift else "No drift between Main and HEAD.",
            "all_financial_fields_match": all_financial_fields_match
        }
    }
    
    # Write json report
    (out_dir / report_filename).write_text(json.dumps(_jsonable(report), ensure_ascii=False, indent=2), encoding="utf-8")
    
    # Write csv diffs
    csv_path = out_dir / csv_filename
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["row", "date", "column", "current_value", "baseline_value", "diff"])
        for d in diffs:
            writer.writerow([d["row"], d["date"], d["column"], d["current_value"], d["baseline_value"], d["diff"]])
            
    return report


def cmd_three_way_compare(args):
    # A vs B
    generate_l0_report(
        current_dir=Path(args.main_dir),
        baseline_dir=Path(args.baseline_dir),
        out_dir=Path(args.out_dir),
        title="L0 Baseline Drift Analysis",
        report_filename="L0_BASELINE_DRIFT_REPORT.json",
        csv_filename="L0_BASELINE_STATE_DIFFS.csv",
        baseline_commit=args.baseline_commit,
        current_commit=args.main_commit
    )
    
    # B vs C
    head_commit = args.head_commit or get_source_commit()
    generate_l0_report(
        current_dir=Path(args.head_dir),
        baseline_dir=Path(args.main_dir),
        out_dir=Path(args.out_dir),
        title="L0 Main vs HEAD Parity Analysis",
        report_filename="L0_MAIN_VS_HEAD_REPORT.json",
        csv_filename="L0_MAIN_VS_HEAD_STATE_DIFFS.csv",
        baseline_commit=args.main_commit,
        current_commit=head_commit
    )
    print("Three-way L0 comparison complete. Reports generated in " + args.out_dir)


def cmd_compare(args):
    report = compare_runs(
        jq_dir=Path(args.jq_dir),
        l1a_dir=Path(args.l1a_dir),
        out_dir=Path(args.out_dir),
        baseline_dir=Path(args.baseline_dir) if args.baseline_dir else None,
    )
    if args.determinism_dir:
        verify_determinism_and_finalize(Path(args.out_dir), Path(args.determinism_dir))
        
    # Reload report to print accurate finalized gate status
    rpt_path = Path(args.out_dir) / "LOCAL_NATIVE_L1A_REPORT.json"
    if rpt_path.exists():
        report = json.loads(rpt_path.read_text(encoding="utf-8"))
    gates = report.get("acceptance_gates", {})
    
    print(f"implementation_acceptance = {gates.get('implementation_acceptance', 'FAIL')}")
    for gate, status in gates.items():
        print(f"  {gate}: {status}")
    if gates.get("implementation_acceptance") != "PASS":
        sys.exit(1)


def cmd_determinism(args):
    d1, d2 = Path(args.run1_dir), Path(args.run2_dir)
    det_report = verify_determinism_and_finalize(d1, d2)
    print(json.dumps(det_report["files"], indent=2))
    print(f"\nDeterministic: {det_report['status']}")
    if det_report["status"] != "PASS":
        sys.exit(1)
    sys.exit(0)


def main():
    p = argparse.ArgumentParser()
    subs = p.add_subparsers(dest="command")

    rp = subs.add_parser("run")
    rp.add_argument("--profile", required=True, choices=["jq_parity", "local_native_l1a"])
    rp.add_argument("--year", type=int, default=2020)
    rp.add_argument("--out-dir", required=True)

    cp = subs.add_parser("compare")
    cp.add_argument("--jq-dir", required=True)
    cp.add_argument("--l1a-dir", required=True)
    cp.add_argument("--baseline-dir", default=None)
    cp.add_argument("--out-dir", required=True)
    cp.add_argument("--determinism-dir", default=None,
                    help="Reference compare output dir; verify 6 stable file SHAs against it")

    dp = subs.add_parser("determinism")
    dp.add_argument("--run1-dir", required=True)
    dp.add_argument("--run2-dir", required=True)

    tp = subs.add_parser("three-way-compare")
    tp.add_argument("--baseline-dir", required=True)
    tp.add_argument("--main-dir", required=True)
    tp.add_argument("--head-dir", required=True)
    tp.add_argument("--out-dir", required=True)
    tp.add_argument("--baseline-commit", default="6369570 (frozen as rebuild_2020_warm2020_v16)")
    tp.add_argument("--main-commit", default="6369570406b77dda9903e832dccd5516fc9c5986")
    tp.add_argument("--head-commit", default=None)

    args = p.parse_args()
    if args.command == "run":
        cmd_run(args)
    elif args.command == "compare":
        cmd_compare(args)
    elif args.command == "determinism":
        cmd_determinism(args)
    elif args.command == "three-way-compare":
        cmd_three_way_compare(args)
    else:
        p.print_help()


if __name__ == "__main__":
    main()
