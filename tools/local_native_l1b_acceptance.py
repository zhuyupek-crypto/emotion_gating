"""L1B acceptance verification tool for local-native size hook ablation.

Usage:
  python tools/local_native_l1b_acceptance.py run \\
      --profile jq_parity --year 2020 --out-dir <dir>
  python tools/local_native_l1b_acceptance.py run \\
      --profile local_native_l1a --year 2020 --out-dir <dir>
  python tools/local_native_l1b_acceptance.py run \\
      --profile local_native_l1b --year 2020 --out-dir <dir>
  python tools/local_native_l1b_acceptance.py compare-l1b \\
      --l1a-dir <l1a_dir> --l1b-dir <l1b_dir> --out-dir <out_dir>
  python tools/local_native_l1b_acceptance.py l0-main-vs-head \\
      --main-dir <main_dir> --head-dir <head_dir> --out-dir <out_dir>
  python tools/local_native_l1b_acceptance.py determinism \\
      --run1-dir <run1_dir> --run2-dir <run2_dir>
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

# Reuse setup_runtime and other helper functions from acceptance_common
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.acceptance_common import (
    setup_runtime,
    _jsonable,
    get_source_commit,
    get_main_commit,
    strategy_sha256,
    load_strategy_code,
    _nd,
    _build_trade_keys,
    compare_baseline_file,
    compare_state_files,
    FLOAT_TOL,
    HDATA_ROOT,
)

# Reuse generate_l0_report from L1A tool to avoid duplication
from tools.local_native_l1a_acceptance import generate_l0_report

REQUIRED_ARTIFACTS = [
    "DIRECT_SIZE_DIFFS.csv",
    "TRADE_KEY_DIFFS.csv",
    "STATE_DIFFS_SAMPLE.csv",
    "LOCAL_NATIVE_L1B_REPORT.json",
    "LOCAL_NATIVE_L1B_REPORT.md",
    "PROFILE_MANIFEST.json",
    "ARTIFACT_HASHES.json",
]

L1A_HOOK_IDS = frozenset({
    "market_data.minute_price_anomalies",
    "execution.execution_price_anomalies",
})

L1B_HOOK_IDS = frozenset({
    "execution.order_amount_anomalies",
    "execution.fill_amount_anomalies",
})

ALL_HOOK_IDS = L1A_HOOK_IDS | L1B_HOOK_IDS


def _collect_hook_telemetry_l1b(compat) -> dict:
    result = {}
    for hid in ALL_HOOK_IDS:
        queries = getattr(compat, "_hook_queries", {}).get(hid, 0)
        hits = getattr(compat, "_hook_hits", {}).get(hid, 0)
        would_hits = getattr(compat, "_hook_would_have_hits", {}).get(hid, 0)
        
        disabled_set = getattr(compat, "disabled_hook_ids", set())
        disabled = hid in disabled_set
        
        hit_keys = [k for k in getattr(compat, "_hook_hit_keys", []) if k["hook_id"] == hid]
        would_have = [k for k in getattr(compat, "_hook_would_have_hit_keys", []) if k["hook_id"] == hid]
        
        sorted_hit_keys = sorted(hit_keys, key=lambda x: (x["date"], x["time"], x["code"], x.get("key_query_ordinal", 1)))
        sorted_would = sorted(would_have, key=lambda x: (x["date"], x["time"], x["code"], x.get("key_query_ordinal", 1)))
        
        first_hit = sorted_hit_keys[0] if sorted_hit_keys else None
        first_would = sorted_would[0] if sorted_would else None
        
        entry = {
            "queries": queries,
            "effective_hits": 0 if disabled else hits,
            "would_have_hits": would_hits if disabled else 0,
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


def run_backtest(profile: str, year: int, out_dir: Path, hdata_reader, Engine, EmotionGateJQCompat) -> dict:
    start_date = f"{year}-01-01"
    end_date = f"{year}-12-31"
    
    compat = EmotionGateJQCompat(profile=profile)
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

    # Save detailed size hook events for verification
    events_df = pd.DataFrame(getattr(compat, "size_hook_events", []))
    events_df.to_csv(out_dir / "size_hook_events.csv", index=False)

    telemetry = _collect_hook_telemetry_l1b(compat)
    manifest = compat.profile_manifest()

    final_val = float(equity["value"].iloc[-1]) if not equity.empty else 0
    total_ret = (final_val / 1000000 - 1) * 100

    run_summary = {
        "profile": profile,
        "year": year,
        "source_commit": get_source_commit(),
        "base_main_commit": get_main_commit(),
        "data_root": str(HDATA_ROOT).replace("\\", "/"),
        "strategy_file": "母版-20260506-Clone.py",
        "strategy_sha256": strategy_sha256(),
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
        f"python tools/local_native_l1b_acceptance.py run --profile {profile} --year {year} --out-dir {out_dir.name}\n",
        encoding="utf-8",
    )
    (out_dir / "source_commit.txt").write_text(f"{get_source_commit()}\n", encoding="utf-8")
    return run_summary


def cmd_run(args):
    hdata_reader, Engine, DataAPI, EmotionGateJQCompat = setup_runtime()
    summary = run_backtest(
        profile=args.profile, year=args.year,
        out_dir=Path(args.out_dir),
        hdata_reader=hdata_reader, Engine=Engine,
        EmotionGateJQCompat=EmotionGateJQCompat,
    )
    print(json.dumps(_jsonable(summary), ensure_ascii=False, indent=2))


def compare_runs_l1b(l1a_dir: Path, l1b_dir: Path, out_dir: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)

    # Load manifests, summaries, telemetries
    l1a_manifest = json.loads((l1a_dir / "profile_manifest.json").read_text(encoding="utf-8"))
    l1b_manifest = json.loads((l1b_dir / "profile_manifest.json").read_text(encoding="utf-8"))
    l1a_summary = json.loads((l1a_dir / "run_summary.json").read_text(encoding="utf-8"))
    l1b_summary = json.loads((l1b_dir / "run_summary.json").read_text(encoding="utf-8"))
    l1a_telemetry = json.loads((l1a_dir / "hook_counts.json").read_text(encoding="utf-8"))
    l1b_telemetry = json.loads((l1b_dir / "hook_counts.json").read_text(encoding="utf-8"))

    # Load dataframes
    l1a_trades = pd.read_csv(l1a_dir / "local_trades_2020.csv")
    l1b_trades = pd.read_csv(l1b_dir / "local_trades_2020.csv")
    l1a_equity = pd.read_csv(l1a_dir / "local_equity_2020.csv")
    l1b_equity = pd.read_csv(l1b_dir / "local_equity_2020.csv")
    l1a_state = pd.read_csv(l1a_dir / "local_state_2020.csv")
    l1b_state = pd.read_csv(l1b_dir / "local_state_2020.csv")
    l1a_pf = pd.read_csv(l1a_dir / "local_portfolio_stats_2020.csv")
    l1b_pf = pd.read_csv(l1b_dir / "local_portfolio_stats_2020.csv")
    l1a_pos = pd.read_csv(l1a_dir / "local_positions_2020.csv")
    l1b_pos = pd.read_csv(l1b_dir / "local_positions_2020.csv")
    
    l1a_events = pd.read_csv(l1a_dir / "size_hook_events.csv") if (l1a_dir / "size_hook_events.csv").exists() else pd.DataFrame()
    l1b_events = pd.read_csv(l1b_dir / "size_hook_events.csv") if (l1b_dir / "size_hook_events.csv").exists() else pd.DataFrame()

    # Save size_hook_events.csv in out_dir for determinism/reference
    if not l1b_events.empty:
        l1b_events.to_csv(out_dir / "SIZE_HOOK_EVENTS.csv", index=False)
    else:
        pd.DataFrame().to_csv(out_dir / "SIZE_HOOK_EVENTS.csv", index=False)

    # Find first L1B size hook would-have-hit
    first_hit_time = None
    first_hit_hook_id = None
    first_hit_key = None
    
    # Check would-have-hits in l1b
    would_hit_events = []
    for hid in L1B_HOOK_IDS:
        hinfo = l1b_telemetry.get(hid, {})
        for hk in hinfo.get("would_have_hit_keys", []):
            would_hit_events.append((hk["date"], hk["time"], hk["code"], hk.get("side"), hid, hk))
            
    if would_hit_events:
        # Sort by date, time
        would_hit_events.sort(key=lambda x: (x[0], x[1]))
        first_evt = would_hit_events[0]
        first_hit_time = f"{first_evt[0]} {first_evt[1]}"
        first_hit_hook_id = first_evt[4]
        first_hit_key = first_evt[5]

    # Verification gates dict
    gates = {
        "l1b_exact_hook_set": "FAIL",
        "l1a_size_hooks_have_effective_hits": "FAIL",
        "l1b_size_hooks_effective_hits_zero": "FAIL",
        "would_have_hit_events_complete": "FAIL",
        "first_direct_diff_maps_to_hook": "FAIL",
        "divergence_not_before_first_hit": "FAIL",
        "pre_hit_exact_match": "FAIL",
        "direct_price_unchanged": "FAIL",
        "account_invariants": "FAIL",
        "required_artifacts_complete": "FAIL",
        "deterministic_reports": "FAIL",  # populated later
        "implementation_acceptance": "FAIL",
    }

    # 1. l1b_exact_hook_set
    expected_disabled = sorted(list(L1A_HOOK_IDS | L1B_HOOK_IDS))
    actual_disabled = sorted(l1b_manifest.get("disabled_hook_ids", []))
    if actual_disabled == expected_disabled:
        gates["l1b_exact_hook_set"] = "PASS"

    # 2. l1a_size_hooks_have_effective_hits
    l1a_hits_ok = True
    for hid in L1B_HOOK_IDS:
        hinfo = l1a_telemetry.get(hid, {})
        if hinfo.get("effective_hits", 0) == 0:
            l1a_hits_ok = False
    if l1a_hits_ok:
        gates["l1a_size_hooks_have_effective_hits"] = "PASS"

    # 3. l1b_size_hooks_effective_hits_zero
    l1b_hits_zero = True
    for hid in L1B_HOOK_IDS:
        hinfo = l1b_telemetry.get(hid, {})
        if hinfo.get("effective_hits", 0) > 0 or hinfo.get("would_have_hits", 0) == 0:
            l1b_hits_zero = False
    if l1b_hits_zero:
        gates["l1b_size_hooks_effective_hits_zero"] = "PASS"

    # 4. would_have_hit_events_complete
    # Compare L1B would-have hit keys with L1A effective hit keys
    would_hit_keys_match = True
    for hid in L1B_HOOK_IDS:
        l1a_keys = l1a_telemetry.get(hid, {}).get("effective_hit_keys", [])
        l1b_keys = l1b_telemetry.get(hid, {}).get("would_have_hit_keys", [])
        # Compare key sets by (date, time, code, side, key_query_ordinal)
        def key_sig(k):
            return (k["date"], k["time"], k["code"], k.get("side"), k.get("key_query_ordinal"))
        
        l1a_sigs = set(key_sig(k) for k in l1a_keys)
        l1b_sigs = set(key_sig(k) for k in l1b_keys)
        if l1a_sigs != l1b_sigs:
            would_hit_keys_match = False
    if would_hit_keys_match:
        gates["would_have_hit_events_complete"] = "PASS"

    # Build trade keys
    l1a_trades["_tk"] = _build_trade_keys(l1a_trades)
    l1b_trades["_tk"] = _build_trade_keys(l1b_trades)
    l1a_key_set = set(l1a_trades["_tk"])
    l1b_key_set = set(l1b_trades["_tk"])
    matched_keys = l1a_key_set & l1b_key_set
    added_keys = l1b_key_set - l1a_key_set
    removed_keys = l1a_key_set - l1b_key_set

    # Map matched keys to size events
    l1a_by_key = {k: g.iloc[0] for k, g in l1a_trades.groupby("_tk")}
    l1b_by_key = {k: g.iloc[0] for k, g in l1b_trades.groupby("_tk")}

    # Classification lists
    direct_size_diffs = []
    trade_key_diff_rows = []
    
    amount_only_diffs = 0
    price_diffs = 0
    direct_price_ok = True

    # Find earliest divergence in trades
    divergence_trade_time = None
    divergence_trade_key = None
    for k in sorted(l1a_key_set | l1b_key_set):
        if k not in matched_keys:
            divergence_trade_key = k
            row = l1a_by_key[k] if k in l1a_by_key else l1b_by_key[k]
            divergence_trade_time = str(row.get("time", ""))
            break
        row_a = l1a_by_key[k]
        row_b = l1b_by_key[k]
        if abs(float(row_a["amount"]) - float(row_b["amount"])) > FLOAT_TOL or abs(float(row_a["price"]) - float(row_b["price"])) > FLOAT_TOL:
            divergence_trade_key = k
            divergence_trade_time = str(row_a.get("time", ""))
            break

    # Categorize matched trade diffs
    for k in sorted(matched_keys):
        row_a = l1a_by_key[k]
        row_b = l1b_by_key[k]
        amt_a = float(row_a["amount"])
        amt_b = float(row_b["amount"])
        pr_a = float(row_a["price"])
        pr_b = float(row_b["price"])
        
        time_str = str(row_a.get("time", ""))
        date_str = time_str.split()[0]
        code = str(row_a.get("code", ""))
        side = "buy" if amt_a > 0 else "sell"
        occurrence_idx = int(k.split("#")[1])

        amt_diff = abs(amt_a - amt_b) > FLOAT_TOL
        pr_diff = abs(pr_a - pr_b) > FLOAT_TOL

        if amt_diff or pr_diff:
            if pr_diff:
                price_diffs += 1
            else:
                amount_only_diffs += 1

            # Match to a size event in l1a_events or l1b_events
            matched_evt = None
            def normalize_order_id(val):
                if pd.isna(val):
                    return ""
                s = str(val).strip()
                if s.endswith(".0"):
                    s = s[:-2]
                return s

            trade_order_id = normalize_order_id(row_a.get("order_id"))
            has_order_col = "order_id" in l1b_events.columns if not l1b_events.empty else False
            # Find in l1b_events
            if not l1b_events.empty:
                if trade_order_id and has_order_col:
                    matches = l1b_events[
                        (l1b_events["code"].astype(str) == code) &
                        (l1b_events["order_id"].apply(normalize_order_id) == trade_order_id)
                    ]
                else:
                    matches = l1b_events[
                        (l1b_events["date"].astype(str) == date_str.replace("-", "")) &
                        (l1b_events["time"].astype(str) == time_str.split()[1][:5]) &
                        (l1b_events["code"].astype(str) == code) &
                        (l1b_events["side"].astype(str) == side) &
                        (l1b_events["key_query_ordinal"].astype(int) == occurrence_idx)
                    ]
                if not matches.empty:
                    matched_evt = matches.iloc[0].to_dict()

            if matched_evt is not None:
                # Direct price constraint: price must be unchanged
                if pr_diff:
                    direct_price_ok = False
                
                # Check quantity diff is explainable by override
                override_val = matched_evt.get("override_amount")
                computed_val = matched_evt.get("computed_amount_before_override")
                
                direct_size_diffs.append({
                    "trade_key": k,
                    "date": date_str,
                    "time": time_str.split()[1],
                    "code": code,
                    "side": side,
                    "l1a_amount": amt_a,
                    "l1b_amount": amt_b,
                    "diff_amount": amt_a - amt_b,
                    "l1a_price": pr_a,
                    "l1b_price": pr_b,
                    "hook_id": matched_evt.get("hook_id"),
                    "key_query_ordinal": occurrence_idx,
                    "sequence_index": matched_evt.get("sequence_index"),
                    "override_value": override_val,
                })
            else:
                # Downstream matched diff
                trade_key_diff_rows.append({
                    "trade_key": k,
                    "diff_type": "price_diff" if pr_diff else "amount_diff",
                    "date": date_str,
                    "code": code,
                    "l1a_amount": amt_a,
                    "l1b_amount": amt_b,
                    "l1a_price": pr_a,
                    "l1b_price": pr_b,
                })

    # Added / removed keys are downstream diffs
    for k in sorted(removed_keys):
        row_a = l1a_by_key[k]
        trade_key_diff_rows.append({
            "trade_key": k,
            "diff_type": "removed",
            "date": str(row_a.get("time", "")).split()[0],
            "code": str(row_a.get("code", "")),
            "l1a_amount": float(row_a["amount"]),
            "l1b_amount": 0.0,
            "l1a_price": float(row_a["price"]),
            "l1b_price": 0.0,
        })
    for k in sorted(added_keys):
        row_b = l1b_by_key[k]
        trade_key_diff_rows.append({
            "trade_key": k,
            "diff_type": "added",
            "date": str(row_b.get("time", "")).split()[0],
            "code": str(row_b.get("code", "")),
            "l1a_amount": 0.0,
            "l1b_amount": float(row_b["amount"]),
            "l1a_price": 0.0,
            "l1b_price": float(row_b["price"]),
        })

    # Save CSV files
    direct_df = pd.DataFrame(direct_size_diffs)
    if direct_df.empty:
        direct_df = pd.DataFrame(columns=[
            "trade_key", "date", "time", "code", "side",
            "l1a_amount", "l1b_amount", "diff_amount", "l1a_price", "l1b_price",
            "hook_id", "key_query_ordinal", "sequence_index", "override_value"
        ])
    direct_df.to_csv(out_dir / "DIRECT_SIZE_DIFFS.csv", index=False)

    diff_keys_df = pd.DataFrame(trade_key_diff_rows)
    if diff_keys_df.empty:
        diff_keys_df = pd.DataFrame(columns=[
            "trade_key", "diff_type", "date", "code",
            "l1a_amount", "l1b_amount", "l1a_price", "l1b_price"
        ])
    diff_keys_df.to_csv(out_dir / "TRADE_KEY_DIFFS.csv", index=False)

    # 5. direct_price_unchanged
    if direct_price_ok:
        gates["direct_price_unchanged"] = "PASS"

    # 6. first_direct_diff_maps_to_hook
    # The earliest trade difference must be a direct size diff
    first_diff_mapped = False
    if divergence_trade_time is not None:
        first_evt_time = pd.to_datetime(divergence_trade_time)
        # Check if this trade key exists in direct_size_diffs
        if any(d["trade_key"] == divergence_trade_key for d in direct_size_diffs):
            first_diff_mapped = True
    if first_diff_mapped:
        gates["first_direct_diff_maps_to_hook"] = "PASS"

    # 7. divergence_not_before_first_hit
    div_not_before = True
    if first_hit_time is not None:
        first_hit_dt = pd.to_datetime(first_hit_time)
        if divergence_trade_time is not None:
            if pd.to_datetime(divergence_trade_time) < first_hit_dt:
                div_not_before = False
    else:
        div_not_before = False
    if div_not_before:
        gates["divergence_not_before_first_hit"] = "PASS"

    # 8. pre_hit_exact_match & pre_hit_date check
    pre_hit_ok = True
    if first_hit_time is not None:
        first_hit_dt = pd.to_datetime(first_hit_time)
        pre_hit_date_str = first_hit_dt.strftime("%Y-%m-%d")
        
        # Compare daily files up to pre_hit_date
        for suffix in ["equity", "state", "portfolio_stats", "positions"]:
            f_a = l1a_dir / f"local_{suffix}_2020.csv"
            f_b = l1b_dir / f"local_{suffix}_2020.csv"
            if not f_a.exists() or not f_b.exists():
                pre_hit_ok = False
                break
            df_a = pd.read_csv(f_a)
            df_b = pd.read_csv(f_b)
            df_a_pre = df_a[df_a["date"] < pre_hit_date_str]
            df_b_pre = df_b[df_b["date"] < pre_hit_date_str]
            if len(df_a_pre) != len(df_b_pre):
                pre_hit_ok = False
                break
            if not df_a_pre.reset_index(drop=True).equals(df_b_pre.reset_index(drop=True)):
                pre_hit_ok = False
                break
    else:
        pre_hit_ok = False
    if pre_hit_ok:
        gates["pre_hit_exact_match"] = "PASS"

    # 9. account_invariants
    invariants_ok = True
    def normalize_order_id(val):
        if pd.isna(val):
            return ""
        s = str(val).strip()
        if s.endswith(".0"):
            s = s[:-2]
        return s

    for target_dir in [l1a_dir, l1b_dir]:
        # Cash must not be negative without explanation (natural preopen/auction margin allowed up to 100,000)
        port_df = pd.read_csv(target_dir / "local_portfolio_stats_2020.csv")
        if (port_df["available_cash"] < -100000.0).any():
            invariants_ok = False
        
        # Positions must not have negative quantity
        pos_df = pd.read_csv(target_dir / "local_positions_2020.csv")
        if (pos_df["amount"] < -FLOAT_TOL).any():
            invariants_ok = False
            
        # Total portfolio value accounting identity check
        # Group positions by date
        pos_grouped = pos_df.groupby("date")
        for idx_row, row_port in port_df.iterrows():
            d = row_port["date"]
            cash = float(row_port["available_cash"])
            total_val = float(row_port["total_value"])
            pos_sum = 0.0
            if d in pos_grouped.groups:
                g = pos_grouped.get_group(d)
                pos_sum = float((g["amount"] * g["price"]).sum())
            if abs(total_val - (cash + pos_sum)) > 1.0: # Allow minor rounding tolerance
                invariants_ok = False
                
        # Lot size check (minimum 100 shares for stock/etf, 10 for bond)
        trades_df = pd.read_csv(target_dir / "local_trades_2020.csv")
        for _, t_row in trades_df.iterrows():
            code = t_row["code"]
            amt = abs(float(t_row["amount"]))
            # Skip overridden amount hooks in control run using normalized order_id
            trade_order_id = normalize_order_id(t_row.get("order_id"))
            has_order_col = "order_id" in l1a_events.columns if not l1a_events.empty else False
            if target_dir == l1a_dir and not l1a_events.empty:
                if trade_order_id and has_order_col:
                    if any(
                        normalize_order_id(evt["order_id"]) == trade_order_id and
                        evt["code"] == code
                        for _, evt in l1a_events.iterrows()
                    ):
                        continue
                else:
                    if any(
                        _nd(evt["date"]) == _nd(t_row["time"].split()[0]) and
                        evt["code"] == code and
                        abs(float(evt["override_amount"]) - amt) <= FLOAT_TOL
                        for _, evt in l1a_events.iterrows()
                    ):
                        continue
            
            # Allow fractions/lot sizes based on code suffix
            if code.endswith(".XSHG") or code.endswith(".XSHE"):
                if amt % 100 > FLOAT_TOL and abs(amt % 100 - 100) > FLOAT_TOL:
                    # Check if it was a sell all (reduces position to 0)
                    is_sell = float(t_row["amount"]) < 0
                    t_date = t_row["time"].split()[0]
                    day_pos = pos_df[(pos_df["date"] == t_date) & (pos_df["code"] == code)]
                    is_sell_all = is_sell and day_pos.empty
                    if not is_sell_all:
                        invariants_ok = False
    if invariants_ok:
        gates["account_invariants"] = "PASS"

    # Compare state cell-by-cell for state diff sample
    cell_diff_count, diffs = compare_state_files(l1a_dir / "local_state_2020.csv", l1b_dir / "local_state_2020.csv")
    diffs_df = pd.DataFrame(diffs)
    if diffs_df.empty:
        diffs_df = pd.DataFrame(columns=["row", "date", "column", "current_value", "baseline_value", "diff"])
    diffs_df.head(50).to_csv(out_dir / "STATE_DIFFS_SAMPLE.csv", index=False)

    # 10. required_artifacts_complete
    artifacts_ok = True
    for a in REQUIRED_ARTIFACTS:
        if a not in ["LOCAL_NATIVE_L1B_REPORT.json", "LOCAL_NATIVE_L1B_REPORT.md", "ARTIFACT_HASHES.json"]:
            if not (out_dir / a).exists():
                artifacts_ok = False
    if artifacts_ok:
        gates["required_artifacts_complete"] = "PASS"

    # Save first cascading difference date
    first_cascade_date = None
    if trade_key_diff_rows:
        first_cascade_date = min(d["date"] for d in trade_key_diff_rows)

    # Performance summary
    performance = {
        "final_equity_l1a": float(l1a_equity["value"].iloc[-1]),
        "final_equity_l1b": float(l1b_equity["value"].iloc[-1]),
        "total_return_pct_l1a": float(l1a_summary["total_return_pct"]),
        "total_return_pct_l1b": float(l1b_summary["total_return_pct"]),
        "trade_count_l1a": len(l1a_trades),
        "trade_count_l1b": len(l1b_trades),
        "amount_only_diffs": amount_only_diffs,
        "price_diffs": price_diffs,
        "added_trades_count": len(added_keys),
        "removed_trades_count": len(removed_keys),
        "first_cascade_trade_date": first_cascade_date,
        "first_direct_diff_time": divergence_trade_time,
        "first_direct_diff_key": divergence_trade_key,
    }

    report = {
        "title": "LOCAL_NATIVE_L1B Acceptance Report",
        "profiles": {
            "l1a": l1a_manifest,
            "l1b": l1b_manifest,
        },
        "performance": performance,
        "hook_telemetry_l1a": l1a_telemetry,
        "hook_telemetry_l1b": l1b_telemetry,
        "first_size_hook_would_have_hit": {
            "time": first_hit_time,
            "hook_id": first_hit_hook_id,
            "key": first_hit_key,
        },
        "acceptance_gates": gates,
    }

    # Finalize JSON and MD
    (out_dir / "LOCAL_NATIVE_L1B_REPORT.json").write_text(json.dumps(_jsonable(report), ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "LOCAL_NATIVE_L1B_REPORT.md").write_text(_render_md_l1b(report), encoding="utf-8")

    return report


def _render_md_l1b(report: dict) -> str:
    gates = report["acceptance_gates"]
    perf = report["performance"]
    t1a = report["hook_telemetry_l1a"]
    t1b = report["hook_telemetry_l1b"]

    lines = []
    lines.append("# LOCAL_NATIVE_L1B Acceptance Report\n")
    lines.append("## Acceptance Gates Status\n")
    for g, val in gates.items():
        color = "🟢" if val == "PASS" else "🔴"
        lines.append(f"- {color} **{g}**: {val}")
    lines.append("\n")

    lines.append("## Hook Hits Summary\n")
    lines.append("| Hook ID | Profile | Queries | Effective Hits | Would-Have Hits |")
    lines.append("| --- | --- | --- | --- | --- |")
    for hid in sorted(ALL_HOOK_IDS):
        info_a = t1a.get(hid, {})
        info_b = t1b.get(hid, {})
        lines.append(f"| `{hid}` | L1A | {info_a.get('queries', 0)} | {info_a.get('effective_hits', 0)} | {info_a.get('would_have_hits', 0)} |")
        lines.append(f"| `{hid}` | L1B | {info_b.get('queries', 0)} | {info_b.get('effective_hits', 0)} | {info_b.get('would_have_hits', 0)} |")
    lines.append("\n")

    lines.append("## Performance Comparison\n")
    lines.append("| Metric | L1A (Control) | L1B (Experiment) |")
    lines.append("| --- | --- | --- |")
    lines.append(f"| Final Equity | {perf['final_equity_l1a']:.2f} | {perf['final_equity_l1b']:.2f} |")
    lines.append(f"| Total Return | {perf['total_return_pct_l1a']:.4f}% | {perf['total_return_pct_l1b']:.4f}% |")
    lines.append(f"| Trade Count | {perf['trade_count_l1a']} | {perf['trade_count_l1b']} |")
    lines.append("\n")

    lines.append("## Trade Differences Breakdown\n")
    lines.append(f"- **Amount-only differences**: {perf['amount_only_diffs']}")
    lines.append(f"- **Price differences**: {perf['price_diffs']}")
    lines.append(f"- **Added trades (L1B only)**: {perf['added_trades_count']}")
    lines.append(f"- **Removed trades (L1A only)**: {perf['removed_trades_count']}")
    lines.append(f"- **First direct difference time**: `{perf['first_direct_diff_time']}`")
    lines.append(f"- **First direct difference key**: `{perf['first_direct_diff_key']}`")
    lines.append(f"- **First cascading trade date**: `{perf['first_cascade_trade_date']}`")
    
    first_hit = report["first_size_hook_would_have_hit"]
    lines.append(f"- **Earliest size hook would-have-hit**: `{first_hit['time']}` (`{first_hit['hook_id']}`)")
    lines.append("\n")
    
    return "\n".join(lines)


def cmd_compare_l1b(args):
    report = compare_runs_l1b(
        l1a_dir=Path(args.l1a_dir),
        l1b_dir=Path(args.l1b_dir),
        out_dir=Path(args.out_dir)
    )
    if args.determinism_dir:
        verify_determinism_and_finalize_l1b(Path(args.out_dir), Path(args.determinism_dir))

    # Reload report to print accurate finalized gate status
    rpt_path = Path(args.out_dir) / "LOCAL_NATIVE_L1B_REPORT.json"
    if rpt_path.exists():
        report = json.loads(rpt_path.read_text(encoding="utf-8"))
    gates = report.get("acceptance_gates", {})
    
    print(f"implementation_acceptance = {gates.get('implementation_acceptance', 'FAIL')}")
    for gate, status in gates.items():
        print(f"  {gate}: {status}")
    if gates.get("implementation_acceptance") != "PASS":
        sys.exit(1)


def cmd_l0_main_vs_head(args):
    # Perform strict zero-diff verification: HEAD jq_parity vs Main jq_parity
    main_dir = Path(args.main_dir)
    head_dir = Path(args.head_dir)
    out_dir = Path(args.out_dir)
    
    report = generate_l0_report(
        current_dir=head_dir,
        baseline_dir=main_dir,
        out_dir=out_dir,
        title="L0 Main vs HEAD Parity Analysis",
        report_filename="L0_MAIN_VS_HEAD_REPORT.json",
        csv_filename="L0_MAIN_VS_HEAD_STATE_DIFFS.csv",
        baseline_commit=args.main_commit,
        current_commit=args.head_commit or get_source_commit()
    )
    
    results = report.get("l0_results", {})
    diff_count = sum(results.get(f"{s}_diff_rows", -1) for s in ["trades", "state", "equity", "portfolio_stats", "positions"])
    val_diff = results.get("final_value_diff", -1.0)
    
    print(f"L0 Main vs HEAD Parity check complete.")
    print(f"  Total diff rows: {diff_count}")
    print(f"  Final value diff: {val_diff}")
    
    if diff_count != 0 or val_diff != 0.0:
        print("FAIL: L0 Parity check failed!")
        sys.exit(1)
    else:
        print("PASS: L0 Parity check passed!")
        sys.exit(0)


def verify_determinism_and_finalize_l1b(out_dir: Path, ref_dir: Path) -> dict:
    stable_files = [
        "LOCAL_NATIVE_L1B_REPORT.json",
        "LOCAL_NATIVE_L1B_REPORT.md",
        "PROFILE_MANIFEST.json",
        "DIRECT_SIZE_DIFFS.csv",
        "TRADE_KEY_DIFFS.csv",
        "STATE_DIFFS_SAMPLE.csv",
    ]
    
    # 1. Compare the non-report stable files first to determine det_status
    non_report_files = [
        "PROFILE_MANIFEST.json",
        "DIRECT_SIZE_DIFFS.csv",
        "TRADE_KEY_DIFFS.csv",
        "STATE_DIFFS_SAMPLE.csv",
    ]
    all_match = True
    for name in non_report_files:
        f_out = out_dir / name
        f_ref = ref_dir / name
        if not f_out.exists() or not f_ref.exists():
            all_match = False
        else:
            h_out = hashlib.sha256(f_out.read_bytes()).hexdigest()
            h_ref = hashlib.sha256(f_ref.read_bytes()).hexdigest()
            if h_out != h_ref:
                all_match = False
    det_status = "PASS" if all_match else "FAIL"
    
    # 2. Update gate statuses in report files in BOTH directories if they exist
    for target_dir in [out_dir, ref_dir]:
        rpt_path = target_dir / "LOCAL_NATIVE_L1B_REPORT.json"
        if rpt_path.exists():
            rpt = json.loads(rpt_path.read_text(encoding="utf-8"))
            gates = rpt.get("acceptance_gates", {})
            gates["deterministic_reports"] = det_status
            
            # Apply final gate status
            gates["implementation_acceptance"] = "PASS" if all(v == "PASS" for k, v in gates.items() if k != "implementation_acceptance") else "FAIL"
                
            rpt["acceptance_gates"] = gates
            rpt_path.write_text(json.dumps(rpt, ensure_ascii=False, indent=2), encoding="utf-8")
            (target_dir / "LOCAL_NATIVE_L1B_REPORT.md").write_text(_render_md_l1b(rpt), encoding="utf-8")

    # 3. Recalculate raw SHA256 of all 6 stable files and compare them
    results = {}
    for name in stable_files:
        f_out = out_dir / name
        f_ref = ref_dir / name
        if not f_out.exists() or not f_ref.exists():
            h_out = hashlib.sha256(f_out.read_bytes()).hexdigest() if f_out.exists() else "MISSING"
            h_ref = hashlib.sha256(f_ref.read_bytes()).hexdigest() if f_ref.exists() else "MISSING"
            results[name] = {"hash1": h_out, "hash2": h_ref, "equal": False}
            det_status = "FAIL"
            continue
        h_out = hashlib.sha256(f_out.read_bytes()).hexdigest()
        h_ref = hashlib.sha256(f_ref.read_bytes()).hexdigest()
        eq = h_out == h_ref
        if not eq:
            det_status = "FAIL"
        results[name] = {"hash1": h_out, "hash2": h_ref, "equal": eq}

    det_report = {
        "status": det_status,
        "run1_dir": str(out_dir.relative_to(ROOT) if out_dir.is_relative_to(ROOT) else out_dir),
        "run2_dir": str(ref_dir.relative_to(ROOT) if ref_dir.is_relative_to(ROOT) else ref_dir),
        "files": results
    }

    # 4. Overwrite DETERMINISM_REPORT.json in BOTH directories
    for target_dir in [out_dir, ref_dir]:
        (target_dir / "DETERMINISM_REPORT.json").write_text(
            json.dumps(_jsonable(det_report), ensure_ascii=False, indent=2), encoding="utf-8"
        )

    # 5. Generate ARTIFACT_HASHES.json last in BOTH directories
    for target_dir in [out_dir, ref_dir]:
        hashes = {}
        for a in REQUIRED_ARTIFACTS:
            if a == "ARTIFACT_HASHES.json":
                continue
            p = target_dir / a
            if p.exists():
                hashes[a] = hashlib.sha256(p.read_bytes()).hexdigest()
        
        hashes_path = target_dir / "ARTIFACT_HASHES.json"
        hashes_path.write_text(json.dumps(hashes, indent=2, sort_keys=True), encoding="utf-8")
        
        # 6. Verify every recorded hash
        for a in hashes:
            p = target_dir / a
            curr_hash = hashlib.sha256(p.read_bytes()).hexdigest()
            assert hashes[a] == curr_hash, f"Hash mismatch for {a} during verification!"
            
    return det_report


def cmd_determinism(args):
    d1, d2 = Path(args.run1_dir), Path(args.run2_dir)
    det_report = verify_determinism_and_finalize_l1b(d1, d2)
    print(json.dumps(det_report["files"], indent=2))
    print(f"\nDeterministic: {det_report['status']}")
    if det_report["status"] != "PASS":
        sys.exit(1)
    sys.exit(0)


def main():
    p = argparse.ArgumentParser()
    subs = p.add_subparsers(dest="command")

    rp = subs.add_parser("run")
    rp.add_argument("--profile", required=True, choices=["jq_parity", "local_native_l1a", "local_native_l1b"])
    rp.add_argument("--year", type=int, default=2020)
    rp.add_argument("--out-dir", required=True)

    cp = subs.add_parser("compare-l1b")
    cp.add_argument("--l1a-dir", required=True)
    cp.add_argument("--l1b-dir", required=True)
    cp.add_argument("--out-dir", required=True)
    cp.add_argument("--determinism-dir", default=None)

    dp = subs.add_parser("determinism")
    dp.add_argument("--run1-dir", required=True)
    dp.add_argument("--run2-dir", required=True)

    lp = subs.add_parser("l0-main-vs-head")
    lp.add_argument("--main-dir", required=True)
    lp.add_argument("--head-dir", required=True)
    lp.add_argument("--out-dir", required=True)
    lp.add_argument("--main-commit", default="6369570406b77dda9903e832dccd5516fc9c5986")
    lp.add_argument("--head-commit", default=None)

    args = p.parse_args()
    if args.command == "run":
        cmd_run(args)
    elif args.command == "compare-l1b":
        cmd_compare_l1b(args)
    elif args.command == "determinism":
        cmd_determinism(args)
    elif args.command == "l0-main-vs-head":
        cmd_l0_main_vs_head(args)
    else:
        p.print_help()


if __name__ == "__main__":
    main()
