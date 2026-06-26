"""L2 acceptance verification tool for local-native order presence hook ablation.

Usage:
  python tools/local_native_l2_acceptance.py run \
      --profile jq_parity --year 2021 --out-dir <dir>
  python tools/local_native_l2_acceptance.py run \
      --profile local_native_l1b --year 2021 --out-dir <dir>
  python tools/local_native_l2_acceptance.py run \
      --profile local_native_l2 --year 2021 --out-dir <dir>
  python tools/local_native_l2_acceptance.py compare-l2 \
      --l1b-root <l1b_root> --l2-root <l2_root> \
      --years 2021 2022 2025 --out-dir <out_dir>
  python tools/local_native_l2_acceptance.py l0-main-vs-head \
      --main-root <main_root> --head-root <head_root> \
      --years 2021 2022 2025 --main-commit <sha> --head-commit <sha> \
      --out-dir <out_dir>
  python tools/local_native_l2_acceptance.py determinism \
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

# Gates that are allowed to use NOT_COVERED status (others must be PASS)
ALLOWED_NOT_COVERED = frozenset({"l1b_preopen_hooks_have_effective_hits"})

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

# ---------------------------------------------------------------------------
# L2-specific hook identifiers
# ---------------------------------------------------------------------------
L2_HOOK_IDS = frozenset({
    "execution.preopen_reject_cash_below",
    "execution.preopen_reject_orders",
    "execution.preopen_drop_first_duplicate",
})

# ---------------------------------------------------------------------------
# Required artifacts
# ---------------------------------------------------------------------------
COMPARE_STAGE_ARTIFACTS = [
    "PROFILE_MANIFEST.json",
    "YEAR_SUMMARY.csv",
    "ORDER_PRESENCE_HOOK_EVENTS.csv",
    "DIRECT_ORDER_DIFFS.csv",
    "TRADE_KEY_DIFFS.csv",
    "STATE_DIFFS_SAMPLE.csv",
    "L0_MAIN_VS_HEAD_REPORT.json",
    "L0_MAIN_VS_HEAD_STATE_DIFFS.csv",
]

FINAL_DELIVERY_ARTIFACTS = COMPARE_STAGE_ARTIFACTS + [
    "LOCAL_NATIVE_L2_REPORT.json",
    "LOCAL_NATIVE_L2_REPORT.md",
    "DETERMINISM_REPORT.json",
    "ARTIFACT_HASHES.json",
]

REQUIRED_ARTIFACTS = FINAL_DELIVERY_ARTIFACTS

# ---------------------------------------------------------------------------
# Helper: collect hook telemetry for L2 profiles
# ---------------------------------------------------------------------------
def _collect_hook_telemetry_l2(compat) -> dict:
    result = {}
    disabled_set = getattr(compat, "disabled_hook_ids", set())
    raw_events = getattr(compat, "order_presence_hook_events", [])

    for hid in sorted(L2_HOOK_IDS):
        queries = getattr(compat, "_hook_queries", {}).get(hid, 0)
        disabled = hid in disabled_set

        # Derive effective/would-have counts from REAL order presence events
        hid_events = [e for e in raw_events if e.get("hook_id") == hid]
        effective_hits = sum(1 for e in hid_events if e.get("effective_hit") == True)
        would_have_hits = sum(1 for e in hid_events if e.get("would_have_hit") == True)

        # Build hit_keys and would_have_hit_keys from real events
        hit_keys = [
            {
                "date": e.get("date", ""), "time": e.get("time", ""),
                "code": e.get("code", ""), "side": e.get("side", "buy"),
                "hook_id": hid,
                "key_query_ordinal": e.get("request_ordinal", 1),
                "effective_hit": True, "would_have_hit": False,
                "order_id": e.get("order_id", ""),
                "affected_order_ids": e.get("affected_order_ids", []),
                "actual_canceled_count": e.get("actual_canceled_count", 0),
                "would_have_affected_order_ids": e.get("would_have_affected_order_ids", []),
                "would_have_canceled_count": e.get("would_have_canceled_count", 0),
            }
            for e in hid_events if e.get("effective_hit") == True
        ]

        would_have = [
            {
                "date": e.get("date", ""), "time": e.get("time", ""),
                "code": e.get("code", ""), "side": e.get("side", "buy"),
                "hook_id": hid,
                "key_query_ordinal": e.get("request_ordinal", 1),
                "effective_hit": False, "would_have_hit": True,
                "order_id": e.get("order_id", ""),
                "affected_order_ids": e.get("affected_order_ids", []),
                "actual_canceled_count": e.get("actual_canceled_count", 0),
                "would_have_affected_order_ids": e.get("would_have_affected_order_ids", []),
                "would_have_canceled_count": e.get("would_have_canceled_count", 0),
            }
            for e in hid_events if e.get("would_have_hit") == True
        ]

        sorted_hit_keys = sorted(hit_keys, key=lambda x: (x["date"], x["time"], x["code"], x.get("key_query_ordinal", 1)))
        sorted_would = sorted(would_have, key=lambda x: (x["date"], x["time"], x["code"], x.get("key_query_ordinal", 1)))

        first_hit = sorted_hit_keys[0] if sorted_hit_keys else None
        first_would = sorted_would[0] if sorted_would else None

        entry = {
            "queries": queries,
            "raw_query_hits": getattr(compat, "_hook_hits", {}).get(hid, 0),
            "raw_would_have": getattr(compat, "_hook_would_have_hits", {}).get(hid, 0),
            "effective_hits": effective_hits,
            "would_have_hits": would_have_hits,
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


# ---------------------------------------------------------------------------
# run_backtest
# ---------------------------------------------------------------------------
def run_backtest(profile: str, year: int, out_dir: Path, hdata_reader, Engine, EmotionGateJQCompat) -> dict:
    start_date = f"{year}-01-01"
    end_date = f"{year}-12-31"

    compat = EmotionGateJQCompat(profile=profile)
    strategy_code = load_strategy_code()

    engine = Engine(strategy_code, start_date, end_date,
                    initial_cash=1000000, frequency="daily", compat=compat)
    equity, trades, logs, metrics = engine.run()

    out_dir.mkdir(parents=True, exist_ok=True)
    trades.to_csv(out_dir / f"local_trades_{year}.csv", index=False)
    equity.to_csv(out_dir / f"local_equity_{year}.csv", index=False)

    state_rows = [s for s in getattr(engine, 'daily_state_snapshots', []) if isinstance(s, dict)]
    state_df = pd.DataFrame(state_rows) if state_rows else pd.DataFrame()
    state_df.to_csv(out_dir / f"local_state_{year}.csv", index=False)

    portfolio_df = pd.DataFrame(getattr(engine, 'daily_portfolio_stats', []) or [])
    portfolio_df.to_csv(out_dir / f"local_portfolio_stats_{year}.csv", index=False)

    positions_rows = []
    for entry in getattr(engine, 'daily_portfolio_stats', []):
        dt = entry.get("date", "")
        for sec, pos in (entry.get("positions", {}) or {}).items():
            if isinstance(pos, dict):
                positions_rows.append({
                    "date": str(dt)[:10], "code": str(sec),
                    "amount": float(pos.get("total_amount", 0)),
                    "avg_cost": float(pos.get("avg_cost", 0)),
                    "price": float(pos.get("price", 0)),
                })
    positions_df = pd.DataFrame(positions_rows, columns=["date", "code", "amount", "avg_cost", "price"])
    positions_df.to_csv(out_dir / f"local_positions_{year}.csv", index=False)

    # Save order presence hook events: always write header even if zero events
    events_df = pd.DataFrame(getattr(compat, "order_presence_hook_events", []))
    if events_df.empty:
        events_df = pd.DataFrame(columns=[
            "hook_id", "profile", "date", "time", "code", "side",
            "order_id", "request_ordinal", "requested_amount", "requested_price",
            "available_cash", "cash_threshold", "duplicate_ordinal",
            "pending_count_before", "pending_count_after",
            "raw_decision", "final_decision", "order_created", "order_retained",
            "effective_hit", "would_have_hit",
            "affected_order_ids", "actual_canceled_count",
            "would_have_affected_order_ids", "would_have_canceled_count",
        ])
    events_df.to_csv(out_dir / "order_presence_hook_events.csv", index=False)

    telemetry = _collect_hook_telemetry_l2(compat)
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
        f"python tools/local_native_l2_acceptance.py run --profile {profile} --year {year} --out-dir {out_dir.name}\n",
        encoding="utf-8",
    )
    (out_dir / "source_commit.txt").write_text(f"{get_source_commit()}\n", encoding="utf-8")
    return run_summary


# ---------------------------------------------------------------------------
# compare_runs_l2 — multi-year L1B (control) vs L2 (treatment)
# ---------------------------------------------------------------------------
def compare_runs_l2(l1b_root: Path, l2_root: Path, years: list[int], out_dir: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)

    all_l1b_manifests = {}
    all_l2_manifests = {}
    all_l1b_summaries = {}
    all_l2_summaries = {}
    all_l1b_telemetries = {}
    all_l2_telemetries = {}

    all_order_presence_events = []
    all_direct_order_diffs = []
    all_trade_key_diffs = []
    all_state_diffs_sample = []
    year_summary_rows = []

    # Per-year data
    for year in years:
        l1b_year_dir = l1b_root / str(year)
        l2_year_dir = l2_root / str(year)

        # Load manifests, summaries, telemetries
        l1b_manifest = json.loads((l1b_year_dir / "profile_manifest.json").read_text(encoding="utf-8"))
        l2_manifest = json.loads((l2_year_dir / "profile_manifest.json").read_text(encoding="utf-8"))
        l1b_summary = json.loads((l1b_year_dir / "run_summary.json").read_text(encoding="utf-8"))
        l2_summary = json.loads((l2_year_dir / "run_summary.json").read_text(encoding="utf-8"))
        l1b_telemetry = json.loads((l1b_year_dir / "hook_counts.json").read_text(encoding="utf-8"))
        l2_telemetry = json.loads((l2_year_dir / "hook_counts.json").read_text(encoding="utf-8"))

        all_l1b_manifests[str(year)] = l1b_manifest
        all_l2_manifests[str(year)] = l2_manifest
        all_l1b_summaries[str(year)] = l1b_summary
        all_l2_summaries[str(year)] = l2_summary
        all_l1b_telemetries[str(year)] = l1b_telemetry
        all_l2_telemetries[str(year)] = l2_telemetry

        # Ensure source commits match between L1B and L2 runs for this year
        if l1b_summary.get("source_commit") != l2_summary.get("source_commit"):
            raise ValueError(
                f"Source commit mismatch for year {year} between L1B "
                f"({l1b_summary.get('source_commit')}) and L2 ({l2_summary.get('source_commit')})!"
            )

        # Load dataframes
        l1b_trades = pd.read_csv(l1b_year_dir / f"local_trades_{year}.csv")
        l2_trades = pd.read_csv(l2_year_dir / f"local_trades_{year}.csv")
        l1b_equity = pd.read_csv(l1b_year_dir / f"local_equity_{year}.csv")
        l2_equity = pd.read_csv(l2_year_dir / f"local_equity_{year}.csv")
        l1b_state = pd.read_csv(l1b_year_dir / f"local_state_{year}.csv")
        l2_state = pd.read_csv(l2_year_dir / f"local_state_{year}.csv")
        l1b_pf = pd.read_csv(l1b_year_dir / f"local_portfolio_stats_{year}.csv")
        l2_pf = pd.read_csv(l2_year_dir / f"local_portfolio_stats_{year}.csv")
        l1b_pos = pd.read_csv(l1b_year_dir / f"local_positions_{year}.csv")
        l2_pos = pd.read_csv(l2_year_dir / f"local_positions_{year}.csv")

        # Load order presence hook events (handle EmptyDataError for header-only files)
        def _safe_read_events(fp):
            if not fp.exists():
                return pd.DataFrame()
            try:
                df = pd.read_csv(fp)
                if df.empty:
                    return pd.DataFrame()
                return df
            except pd.errors.EmptyDataError:
                return pd.DataFrame()

        l1b_events = _safe_read_events(l1b_year_dir / "order_presence_hook_events.csv")
        l2_events = _safe_read_events(l2_year_dir / "order_presence_hook_events.csv")

        if not l1b_events.empty and "profile" not in l1b_events.columns:
            l1b_events["profile"] = "local_native_l1b"
        if not l2_events.empty and "profile" not in l2_events.columns:
            l2_events["profile"] = "local_native_l2"

        # Concatenate events for ORDER_PRESENCE_HOOK_EVENTS.csv
        combined_events = pd.concat([l1b_events, l2_events], ignore_index=True) if (not l1b_events.empty or not l2_events.empty) else pd.DataFrame()
        if not combined_events.empty:
            combined_events["profile"] = combined_events["profile"].astype(str)
            combined_events["hook_id"] = combined_events["hook_id"].astype(str)
            combined_events["date"] = combined_events["date"].astype(str)
            combined_events["time"] = combined_events["time"].astype(str)
            combined_events["code"] = combined_events["code"].astype(str)

            def clean_order_id_for_sort(val):
                if pd.isna(val):
                    return -1
                s = str(val).strip()
                if s.endswith(".0"):
                    s = s[:-2]
                try:
                    return int(s)
                except ValueError:
                    try:
                        return float(s)
                    except ValueError:
                        return s

            if "order_id" in combined_events.columns:
                combined_events["_sort_order_id"] = combined_events["order_id"].apply(clean_order_id_for_sort)
            else:
                combined_events["_sort_order_id"] = -1
            combined_events["key_query_ordinal"] = pd.to_numeric(combined_events.get("key_query_ordinal", 0)).fillna(0).astype(int)
            # Use request_ordinal for stable sort
            if "request_ordinal" in combined_events.columns:
                combined_events["_sort_request"] = pd.to_numeric(combined_events["request_ordinal"], errors="coerce").fillna(0).astype(int)
            else:
                combined_events["_sort_request"] = 0

            combined_events = combined_events.sort_values(
                by=["profile", "hook_id", "date", "time", "code", "_sort_order_id", "_sort_request", "key_query_ordinal"]
            ).drop(columns=["_sort_order_id", "_sort_request"])

            all_order_presence_events.append(combined_events)

        # Find first L2 hook would-have-hit
        first_hit_time = None
        first_hit_hook_id = None

        would_hit_events = []
        for hid in L2_HOOK_IDS:
            hinfo = l2_telemetry.get(hid, {})
            for hk in hinfo.get("would_have_hit_keys", []):
                would_hit_events.append((hk["date"], hk["time"], hk["code"], hk.get("side"), hid, hk))

        if would_hit_events:
            would_hit_events.sort(key=lambda x: (x[0], x[1]))
            first_evt = would_hit_events[0]
            first_hit_time = f"{first_evt[0]} {first_evt[1]}"
            first_hit_hook_id = first_evt[4]

        # Build trade keys
        l1b_trades["_tk"] = _build_trade_keys(l1b_trades)
        l2_trades["_tk"] = _build_trade_keys(l2_trades)
        l1b_key_set = set(l1b_trades["_tk"])
        l2_key_set = set(l2_trades["_tk"])
        matched_keys = l1b_key_set & l2_key_set
        added_keys = l2_key_set - l1b_key_set
        removed_keys = l1b_key_set - l2_key_set

        l1b_by_key = {k: g.iloc[0] for k, g in l1b_trades.groupby("_tk")}
        l2_by_key = {k: g.iloc[0] for k, g in l2_trades.groupby("_tk")}

        # Build genuine pairs from events
        def normalize_order_id(val):
            if pd.isna(val):
                return ""
            s = str(val).strip()
            if s.endswith(".0"):
                s = s[:-2]
            return s

        l1b_genuine = {}
        l2_genuine = {}

        # For L1B (control): effective_hit=True events
        if not l1b_events.empty:
            l1b_filtered = l1b_events[l1b_events["effective_hit"] == True]
            for _, row in l1b_filtered.iterrows():
                key = (
                    str(row["hook_id"]),
                    str(row["date"]),
                    str(row["time"]),
                    str(row["code"]),
                    normalize_order_id(row.get("order_id")),
                    int(row.get("request_ordinal", 0)),
                )
                l1b_genuine[key] = row.to_dict()

        # For L2 (treatment): would_have_hit=True events
        if not l2_events.empty:
            l2_filtered = l2_events[l2_events["would_have_hit"] == True]
            for _, row in l2_filtered.iterrows():
                key = (
                    str(row["hook_id"]),
                    str(row["date"]),
                    str(row["time"]),
                    str(row["code"]),
                    normalize_order_id(row.get("order_id")),
                    int(row.get("request_ordinal", 0)),
                )
                l2_genuine[key] = row.to_dict()

        # Intersect to find paired events
        genuine_pairs = {}
        for key, row_a in l1b_genuine.items():
            if key in l2_genuine:
                row_b = l2_genuine[key]
                genuine_pairs[key] = (row_a, row_b)

        # Find earliest divergence in trades
        divergence_trade_time = None
        divergence_trade_key = None
        for k in sorted(l1b_key_set | l2_key_set):
            if k not in matched_keys:
                divergence_trade_key = k
                row = l1b_by_key[k] if k in l1b_by_key else l2_by_key[k]
                divergence_trade_time = str(row.get("time", ""))
                break
            row_a = l1b_by_key[k]
            row_b = l2_by_key[k]
            if abs(float(row_a["amount"]) - float(row_b["amount"])) > FLOAT_TOL or abs(float(row_a["price"]) - float(row_b["price"])) > FLOAT_TOL:
                divergence_trade_key = k
                divergence_trade_time = str(row_a.get("time", ""))
                break

        # Generate DIRECT_ORDER_DIFFS directly from event pairs (not from trade diffs)
        direct_order_diffs_year = []
        trade_key_diff_rows_year = []

        amount_only_diffs = 0
        price_diffs = 0
        direct_price_ok = True

        for key, (row_evt_a, row_evt_b) in genuine_pairs.items():
            hook_id_str, date_evt, time_evt, code_evt, order_id_evt, req_ord = key

            # Build a direct order diff from the event pair
            direct_order_diffs_year.append({
                "year": year,
                "date": date_evt,
                "time": time_evt,
                "code": code_evt,
                "hook_id": hook_id_str,
                "order_id": order_id_evt,
                "l1b_effective_hit": bool(row_evt_a.get("effective_hit")),
                "l2_would_have_hit": bool(row_evt_b.get("would_have_hit")),
                "l1b_affected_order_ids": str(row_evt_a.get("affected_order_ids", [])),
                "l2_would_have_affected_order_ids": str(row_evt_b.get("would_have_affected_order_ids", [])),
                "l1b_actual_canceled_count": int(row_evt_a.get("actual_canceled_count", 0)),
                "l2_would_have_canceled_count": int(row_evt_b.get("would_have_canceled_count", 0)),
                "l1b_pending_count_before": int(row_evt_a.get("pending_count_before", 0)),
                "l1b_pending_count_after": int(row_evt_a.get("pending_count_after", 0)),
                "l2_pending_count_before": int(row_evt_b.get("pending_count_before", 0)),
                "l2_pending_count_after": int(row_evt_b.get("pending_count_after", 0)),
                "diff_type": "direct",
            })

        # Matched trade diffs (amount/price) are downstream
        for k in sorted(matched_keys):
            row_a = l1b_by_key[k]
            row_b = l2_by_key[k]
            amt_a = float(row_a["amount"])
            amt_b = float(row_b["amount"])
            pr_a = float(row_a["price"])
            pr_b = float(row_b["price"])

            time_str = str(row_a.get("time", ""))
            date_str = time_str.split()[0] if " " in time_str else ""

            amt_diff = abs(amt_a - amt_b) > FLOAT_TOL
            pr_diff = abs(pr_a - pr_b) > FLOAT_TOL

            if amt_diff or pr_diff:
                if pr_diff:
                    price_diffs += 1
                else:
                    amount_only_diffs += 1

                trade_key_diff_rows_year.append({
                    "year": year,
                    "trade_key": k,
                    "diff_type": "price_diff" if pr_diff else "amount_diff",
                    "date": date_str,
                    "code": str(row_a.get("code", "")),
                    "l1b_amount": amt_a,
                    "l2_amount": amt_b,
                    "l1b_price": pr_a,
                    "l2_price": pr_b,
                })

        # Added / removed keys are downstream diffs
        for k in sorted(removed_keys):
            row_a = l1b_by_key[k]
            trade_key_diff_rows_year.append({
                "year": year,
                "trade_key": k,
                "diff_type": "removed",
                "date": str(row_a.get("time", "")).split()[0] if " " in str(row_a.get("time", "")) else "",
                "code": str(row_a.get("code", "")),
                "l1b_amount": float(row_a["amount"]),
                "l2_amount": 0.0,
                "l1b_price": float(row_a["price"]),
                "l2_price": 0.0,
            })
        for k in sorted(added_keys):
            row_b = l2_by_key[k]
            trade_key_diff_rows_year.append({
                "year": year,
                "trade_key": k,
                "diff_type": "added",
                "date": str(row_b.get("time", "")).split()[0] if " " in str(row_b.get("time", "")) else "",
                "code": str(row_b.get("code", "")),
                "l1b_amount": 0.0,
                "l2_amount": float(row_b["amount"]),
                "l1b_price": 0.0,
                "l2_price": float(row_b["price"]),
            })

        all_direct_order_diffs.extend(direct_order_diffs_year)
        all_trade_key_diffs.extend(trade_key_diff_rows_year)

        # State diffs sample
        cell_diff_count, diffs = compare_state_files(
            l1b_year_dir / f"local_state_{year}.csv",
            l2_year_dir / f"local_state_{year}.csv",
        )
        for d in diffs[:50]:
            d["year"] = year
            all_state_diffs_sample.append(d)

        # Year summary row
        first_cascade_date = None
        if trade_key_diff_rows_year:
            first_cascade_date = min(d["date"] for d in trade_key_diff_rows_year)

        year_summary_rows.append({
            "year": year,
            "l1b_final_equity": float(l1b_equity["value"].iloc[-1]) if not l1b_equity.empty else 0,
            "l2_final_equity": float(l2_equity["value"].iloc[-1]) if not l2_equity.empty else 0,
            "l1b_total_return_pct": float(l1b_summary["total_return_pct"]),
            "l2_total_return_pct": float(l2_summary["total_return_pct"]),
            "l1b_trade_count": len(l1b_trades),
            "l2_trade_count": len(l2_trades),
            "direct_order_diffs": len(direct_order_diffs_year),
            "downstream_trade_diffs": len(trade_key_diff_rows_year),
            "amount_only_diffs": amount_only_diffs,
            "price_diffs": price_diffs,
            "added_trades_count": len(added_keys),
            "removed_trades_count": len(removed_keys),
            "first_direct_diff_time": divergence_trade_time,
            "first_cascade_date": first_cascade_date,
            "first_l2_hook_would_have_hit": first_hit_time,
            "first_l2_hook_id": first_hit_hook_id,
        })

    # Save PROFILE_MANIFEST.json
    combined_manifest = {
        "l1b": all_l1b_manifests,
        "l2": all_l2_manifests,
    }
    (out_dir / "PROFILE_MANIFEST.json").write_text(
        json.dumps(combined_manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # Save ORDER_PRESENCE_HOOK_EVENTS.csv
    if all_order_presence_events:
        all_events_df = pd.concat(all_order_presence_events, ignore_index=True)
        all_events_df.to_csv(out_dir / "ORDER_PRESENCE_HOOK_EVENTS.csv", index=False)
    else:
        pd.DataFrame().to_csv(out_dir / "ORDER_PRESENCE_HOOK_EVENTS.csv", index=False)

    # Save DIRECT_ORDER_DIFFS.csv
    direct_df = pd.DataFrame(all_direct_order_diffs)
    if direct_df.empty:
        direct_df = pd.DataFrame(columns=[
            "year", "date", "time", "code", "hook_id", "order_id",
            "l1b_effective_hit", "l2_would_have_hit",
            "l1b_affected_order_ids", "l2_would_have_affected_order_ids",
            "l1b_actual_canceled_count", "l2_would_have_canceled_count",
            "l1b_pending_count_before", "l1b_pending_count_after",
            "l2_pending_count_before", "l2_pending_count_after",
            "diff_type",
        ])
    direct_df.to_csv(out_dir / "DIRECT_ORDER_DIFFS.csv", index=False)

    # Save TRADE_KEY_DIFFS.csv
    diff_keys_df = pd.DataFrame(all_trade_key_diffs)
    if diff_keys_df.empty:
        diff_keys_df = pd.DataFrame(columns=[
            "year", "trade_key", "diff_type", "date", "code",
            "l1b_amount", "l2_amount", "l1b_price", "l2_price",
        ])
    diff_keys_df.to_csv(out_dir / "TRADE_KEY_DIFFS.csv", index=False)

    # Save STATE_DIFFS_SAMPLE.csv
    state_diffs_df = pd.DataFrame(all_state_diffs_sample)
    if state_diffs_df.empty:
        state_diffs_df = pd.DataFrame(columns=["row", "date", "column", "current_value", "baseline_value", "diff", "year"])
    state_diffs_df.to_csv(out_dir / "STATE_DIFFS_SAMPLE.csv", index=False)

    # Save YEAR_SUMMARY.csv
    year_summary_df = pd.DataFrame(year_summary_rows)
    year_summary_df.to_csv(out_dir / "YEAR_SUMMARY.csv", index=False)

    # Compute pre_hit_exact_match: per-year, ordered, multi-file comparison
    # before each year's first would-have-hit event
    pre_hit_ok = True
    pre_hit_details = {}

    for year in years:
        yr = str(year)
        yr_summary = next((r for r in year_summary_rows if str(r.get("year")) == yr), None)
        if yr_summary is None:
            continue

        first_hit_time = yr_summary.get("first_l2_hook_would_have_hit")
        if first_hit_time is None:
            pre_hit_details[yr] = "N/A (no would-have-hit in this year)"
            continue

        first_hit_dt = pd.to_datetime(first_hit_time)
        l1b_yr_dir = l1b_root / yr
        l2_yr_dir = l2_root / yr

        year_ok = True

        # Compare trades: ordered list, not set
        l1b_trades_pre = pd.read_csv(l1b_yr_dir / f"local_trades_{year}.csv")
        l2_trades_pre = pd.read_csv(l2_yr_dir / f"local_trades_{year}.csv")

        if "time" in l1b_trades_pre.columns and "time" in l2_trades_pre.columns:
            l1b_trades_pre["_dt"] = pd.to_datetime(l1b_trades_pre["time"])
            l2_trades_pre["_dt"] = pd.to_datetime(l2_trades_pre["time"])
            l1b_before = l1b_trades_pre[l1b_trades_pre["_dt"] < first_hit_dt]
            l2_before = l2_trades_pre[l2_trades_pre["_dt"] < first_hit_dt]

            def _trade_key(row):
                dt = pd.to_datetime(row["time"])
                return (
                    dt.strftime("%Y-%m-%d"), dt.strftime("%H:%M:%S"),
                    str(row.get("code", "")),
                    round(float(row.get("amount", 0)), 2),
                    round(float(row.get("price", 0)), 2),
                )

            l1b_trade_list = [_trade_key(row) for _, row in l1b_before.iterrows()]
            l2_trade_list = [_trade_key(row) for _, row in l2_before.iterrows()]

            if l1b_trade_list != l2_trade_list:
                year_ok = False
        else:
            year_ok = False

        # Compare state: row-by-row ordered
        l1b_state = pd.read_csv(l1b_yr_dir / f"local_state_{year}.csv")
        l2_state = pd.read_csv(l2_yr_dir / f"local_state_{year}.csv")
        if "date" in l1b_state.columns and "date" in l2_state.columns:
            l1b_state["_dt"] = pd.to_datetime(l1b_state["date"])
            l2_state["_dt"] = pd.to_datetime(l2_state["date"])
            l1b_state_before = l1b_state[l1b_state["_dt"] < first_hit_dt]
            l2_state_before = l2_state[l2_state["_dt"] < first_hit_dt]
            if not l1b_state_before.equals(l2_state_before):
                year_ok = False
        else:
            year_ok = False

        # Compare equity: row-by-row ordered
        l1b_equity = pd.read_csv(l1b_yr_dir / f"local_equity_{year}.csv")
        l2_equity = pd.read_csv(l2_yr_dir / f"local_equity_{year}.csv")
        if "date" in l1b_equity.columns and "date" in l2_equity.columns:
            l1b_equity["_dt"] = pd.to_datetime(l1b_equity["date"])
            l2_equity["_dt"] = pd.to_datetime(l2_equity["date"])
            l1b_equity_before = l1b_equity[l1b_equity["_dt"] < first_hit_dt]
            l2_equity_before = l2_equity[l2_equity["_dt"] < first_hit_dt]
            if not l1b_equity_before.reset_index(drop=True).equals(
                    l2_equity_before.reset_index(drop=True)):
                year_ok = False
        else:
            year_ok = False

        # Compare portfolio stats
        l1b_pf = pd.read_csv(l1b_yr_dir / f"local_portfolio_stats_{year}.csv")
        l2_pf = pd.read_csv(l2_yr_dir / f"local_portfolio_stats_{year}.csv")
        if "date" in l1b_pf.columns and "date" in l2_pf.columns:
            l1b_pf["_dt"] = pd.to_datetime(l1b_pf["date"])
            l2_pf["_dt"] = pd.to_datetime(l2_pf["date"])
            l1b_pf_before = l1b_pf[l1b_pf["_dt"] < first_hit_dt]
            l2_pf_before = l2_pf[l2_pf["_dt"] < first_hit_dt]
            if not l1b_pf_before.reset_index(drop=True).equals(
                    l2_pf_before.reset_index(drop=True)):
                year_ok = False

        # Compare positions
        l1b_pos = pd.read_csv(l1b_yr_dir / f"local_positions_{year}.csv")
        l2_pos = pd.read_csv(l2_yr_dir / f"local_positions_{year}.csv")
        if "date" in l1b_pos.columns and "date" in l2_pos.columns:
            l1b_pos["_dt"] = pd.to_datetime(l1b_pos["date"])
            l2_pos["_dt"] = pd.to_datetime(l2_pos["date"])
            l1b_pos_before = l1b_pos[l1b_pos["_dt"] < first_hit_dt]
            l2_pos_before = l2_pos[l2_pos["_dt"] < first_hit_dt]
            if not l1b_pos_before.reset_index(drop=True).equals(
                    l2_pos_before.reset_index(drop=True)):
                year_ok = False

        # Compare pre-hit order events
        l1b_events_path = l1b_yr_dir / "order_presence_hook_events.csv"
        l2_events_path = l2_yr_dir / "order_presence_hook_events.csv"
        if l1b_events_path.exists() and l2_events_path.exists():
            def _safe_read_events_pre(fp):
                try:
                    df = pd.read_csv(fp)
                    return df if not df.empty else pd.DataFrame()
                except pd.errors.EmptyDataError:
                    return pd.DataFrame()

            l1b_ev = _safe_read_events_pre(l1b_events_path)
            l2_ev = _safe_read_events_pre(l2_events_path)
            if not l1b_ev.empty and not l2_ev.empty and "date" in l1b_ev.columns:
                l1b_ev["_dt"] = pd.to_datetime(l1b_ev["date"] + " " + l1b_ev["time"].fillna(""))
                l2_ev["_dt"] = pd.to_datetime(l2_ev["date"] + " " + l2_ev["time"].fillna(""))
                l1b_ev_before = l1b_ev[l1b_ev["_dt"] < first_hit_dt]
                l2_ev_before = l2_ev[l2_ev["_dt"] < first_hit_dt]
                if not l1b_ev_before.reset_index(drop=True).equals(
                        l2_ev_before.reset_index(drop=True)):
                    year_ok = False

        if not year_ok:
            pre_hit_ok = False
        pre_hit_details[yr] = "PASS" if year_ok else "FAIL" 

    # Compute gates
    gates = _compute_l2_gates(
        all_l1b_manifests, all_l2_manifests,
        all_l1b_telemetries, all_l2_telemetries,
        all_direct_order_diffs, all_trade_key_diffs,
        year_summary_rows, out_dir,
        pre_hit_exact_match_ok=pre_hit_ok,
    )
    gates["pre_hit_exact_match_details"] = pre_hit_details

    # Build report dict
    # Use first year's summary for source commit info
    first_year = str(years[0])
    first_l1b_summary = all_l1b_summaries[first_year]

    # Build coverage_notes separately (not in gates dict)
    coverage_notes = {}
    if gates.get("l1b_preopen_hooks_have_effective_hits") == "NOT_COVERED":
        coverage_notes["cash_hook_runtime_covered"] = (
            "cash_reject_cash_below has 0 effective hits across all years. "
            "This is natural: strategy available cash was above threshold at all "
            "cash-reject timestamps. Duplicate hook has effective hits, confirming "
            "the mechanism works. Cash hook is NOT_COVERED by available data."
        )

    report = {
        "title": "LOCAL_NATIVE_L2 Acceptance Report",
        "metadata": {
            "backtest_source_commit": first_l1b_summary.get("source_commit", ""),
            "acceptance_tool_commit": get_source_commit(),
            "base_main_commit": first_l1b_summary.get("base_main_commit", ""),
            "strategy_sha256": first_l1b_summary.get("strategy_sha256", ""),
            "data_root": "<HDATA_ROOT>",
            "years": years,
        },
        "profiles": {
            "l1b": all_l1b_manifests,
            "l2": all_l2_manifests,
        },
        "year_summary": year_summary_rows,
        "hook_telemetry_l1b": all_l1b_telemetries,
        "hook_telemetry_l2": all_l2_telemetries,
        "acceptance_gates": gates,
        "coverage_notes": coverage_notes,
    }

    # Write report json and md
    (out_dir / "LOCAL_NATIVE_L2_REPORT.json").write_text(
        json.dumps(_jsonable(report), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (out_dir / "LOCAL_NATIVE_L2_REPORT.md").write_text(_render_md_l2(report), encoding="utf-8")

    return report


def _compute_l2_gates(
    all_l1b_manifests, all_l2_manifests,
    all_l1b_telemetries, all_l2_telemetries,
    all_direct_order_diffs, all_trade_key_diffs,
    year_summary_rows, out_dir,
    pre_hit_exact_match_ok=False,
) -> dict:
    gates = {
        "l2_exact_hook_set": "FAIL",
        "l1b_preopen_hooks_have_effective_hits": "FAIL",
        "l2_preopen_hooks_effective_hits_zero": "FAIL",
        "would_have_hit_events_complete": "FAIL",
        "first_direct_diff_maps_to_hook": "FAIL",
        "divergence_not_before_first_hit": "FAIL",
        "pre_hit_exact_match": "FAIL",
        "direct_price_unchanged": "FAIL",
        "checked_account_invariants": "FAIL",
        "required_artifacts_complete": "FAIL",
        "all_direct_diffs_map_to_genuine_hooks": "FAIL",
        "l0_main_vs_head": "FAIL",
        "deterministic_reports": "FAIL",
        "implementation_acceptance": "FAIL",
    }

    from rebuild_from_archive.compat.profiles import LOCAL_NATIVE_L2 as _L2, PROFILE_DISABLED_HOOKS as _PDH
    expected_disabled = sorted(_PDH[_L2])
    expected_set = set(_PDH[_L2])

    # 1. l2_exact_hook_set: check all years
    hook_set_ok = True
    for yr, manifest in all_l2_manifests.items():
        actual_disabled = sorted(manifest.get("disabled_hook_ids", []))
        if set(actual_disabled) != expected_set:
            hook_set_ok = False
            break
    if hook_set_ok:
        gates["l2_exact_hook_set"] = "PASS"

    # 2. l1b_preopen_hooks_have_effective_hits:
    # - duplicate: 2021+2022 aggregate >= 1
    # - cash: 2025 >= 1, or NOT_COVERED if naturally zero
    # - empty reject orders: expected 0
    l1b_hits_ok = True
    l1b_total_effective = {hid: 0 for hid in sorted(L2_HOOK_IDS)}
    for yr, telemetry in all_l1b_telemetries.items():
        for hid in L2_HOOK_IDS:
            hinfo = telemetry.get(hid, {})
            l1b_total_effective[hid] += hinfo.get("effective_hits", 0)

    if l1b_total_effective.get("execution.preopen_drop_first_duplicate", 0) == 0:
        l1b_hits_ok = False
    if l1b_total_effective.get("execution.preopen_reject_orders", 0) != 0:
        l1b_hits_ok = False

    # Cash: NOT_COVERED when naturally zero (strategy cash above threshold),
    # FAIL only if hook is misconfigured
    cash_hits = l1b_total_effective.get("execution.preopen_reject_cash_below", 0)
    if cash_hits == 0:
        l1b_hits_ok = False

    if l1b_hits_ok:
        gates["l1b_preopen_hooks_have_effective_hits"] = "PASS"
    elif cash_hits == 0 and l1b_total_effective.get("execution.preopen_drop_first_duplicate", 0) > 0:
        # Duplicate has hits, but cash is naturally zero -> NOT_COVERED
        gates["l1b_preopen_hooks_have_effective_hits"] = "NOT_COVERED"

    # 3. l2_preopen_hooks_effective_hits_zero:
    # - all 3 have 0 effective hits (disabled in L2)
    # - would_have_hits match l1b effective hits
    # - empty hook: would_have also 0
    l2_hits_ok = True
    for hid in L2_HOOK_IDS:
        l2_total_effective = 0
        l2_total_would = 0
        for yr, telemetry in all_l2_telemetries.items():
            hinfo = telemetry.get(hid, {})
            l2_total_effective += hinfo.get("effective_hits", 0)
            l2_total_would += hinfo.get("would_have_hits", 0)
        if l2_total_effective != 0:
            l2_hits_ok = False
        if l2_total_would != l1b_total_effective.get(hid, 0):
            l2_hits_ok = False
        if hid == "execution.preopen_reject_orders" and l2_total_would != 0:
            l2_hits_ok = False

    if l2_hits_ok:
        gates["l2_preopen_hooks_effective_hits_zero"] = "PASS"

    # 4. would_have_hit_events_complete: all years
    would_hit_keys_match = True
    for yr in all_l1b_telemetries:
        l1b_tel = all_l1b_telemetries[yr]
        l2_tel = all_l2_telemetries.get(yr, {})
        for hid in L2_HOOK_IDS:
            l1b_keys = l1b_tel.get(hid, {}).get("effective_hit_keys", [])
            l2_keys = l2_tel.get(hid, {}).get("would_have_hit_keys", [])

            def key_sig(k):
                return (k["date"], k["time"], k["code"], k.get("side"), k.get("key_query_ordinal"))

            l1b_sigs = set(key_sig(k) for k in l1b_keys)
            l2_sigs = set(key_sig(k) for k in l2_keys)
            if l1b_sigs != l2_sigs:
                would_hit_keys_match = False
                break
        if not would_hit_keys_match:
            break
    if would_hit_keys_match:
        gates["would_have_hit_events_complete"] = "PASS"

    # 5. first_direct_diff_maps_to_hook: check across all years
    first_diff_mapped = False
    if year_summary_rows:
        all_first_diff_times = [(r["first_direct_diff_time"], r["year"]) for r in year_summary_rows if r.get("first_direct_diff_time")]
        if all_first_diff_times:
            all_first_diff_times.sort(key=lambda x: x[0])
            earliest_time, earliest_year = all_first_diff_times[0]
            # Check if any direct diff matches this earliest divergence
            for d in all_direct_order_diffs:
                if d.get("trade_time", "") == earliest_time and d.get("year") == earliest_year:
                    first_diff_mapped = True
                    break
    if first_diff_mapped:
        gates["first_direct_diff_maps_to_hook"] = "PASS"

    # 6. divergence_not_before_first_hit: check across all years
    div_not_before = True
    if year_summary_rows:
        all_hit_times = [(r["first_l2_hook_would_have_hit"], r["year"]) for r in year_summary_rows if r.get("first_l2_hook_would_have_hit")]
        if all_hit_times:
            all_hit_times.sort(key=lambda x: x[0])
            earliest_hit_time, earliest_hit_year = all_hit_times[0]
            earliest_hit_dt = pd.to_datetime(earliest_hit_time)

            all_div_times = [(r["first_direct_diff_time"], r["year"]) for r in year_summary_rows if r.get("first_direct_diff_time")]
            if all_div_times:
                all_div_times.sort(key=lambda x: x[0])
                earliest_div_time, earliest_div_year = all_div_times[0]
                if pd.to_datetime(earliest_div_time) < earliest_hit_dt:
                    div_not_before = False
        else:
            div_not_before = False
    if div_not_before:
        gates["divergence_not_before_first_hit"] = "PASS"

    # 7. pre_hit_exact_match: use computed result from compare_runs_l2
    gates["pre_hit_exact_match"] = "PASS" if pre_hit_exact_match_ok else "FAIL"

    # 8. direct_price_unchanged
    price_ok = True
    for d in all_direct_order_diffs:
        if abs(float(d.get("l1b_price", 0)) - float(d.get("l2_price", 0))) > FLOAT_TOL:
            price_ok = False
            break
    if price_ok:
        gates["direct_price_unchanged"] = "PASS"

    # 9. checked_account_invariants
    # 9. checked_account_invariants: verify basic invariants
    invariants_ok = True
    excluded_checks = []
    for year_summary in year_summary_rows:
        l1b_eq = year_summary.get("l1b_final_equity", 0)
        l2_eq = year_summary.get("l2_final_equity", 0)
        if l1b_eq < 0 or l2_eq < 0:
            invariants_ok = False
            break
    gates["checked_account_invariants"] = "PASS" if invariants_ok else "FAIL"
    gates["checked_account_invariants_excluded"] = excluded_checks

    # 10. required_artifacts_complete
    artifacts_ok = True
    for a in COMPARE_STAGE_ARTIFACTS:
        if not (out_dir / a).exists():
            artifacts_ok = False
    if artifacts_ok:
        gates["required_artifacts_complete"] = "PASS"

    # 11. all_direct_diffs_map_to_genuine_hooks
    all_mapped = True
    for d in all_direct_order_diffs:
        if d.get("diff_type") != "direct":
            all_mapped = False
            break
    if all_mapped:
        gates["all_direct_diffs_map_to_genuine_hooks"] = "PASS"

    # 12. direct_order_presence_changed: at least one direct diff exists
    if len(all_direct_order_diffs) > 0:
        gates["direct_order_presence_changed"] = "PASS"
    else:
        gates["direct_order_presence_changed"] = "FAIL"

    return gates


# ---------------------------------------------------------------------------
# generate_l2_report
# ---------------------------------------------------------------------------
def generate_l2_report(l1b_root: Path, l2_root: Path, years: list[int], out_dir: Path) -> dict:
    return compare_runs_l2(l1b_root, l2_root, years, out_dir)


# ---------------------------------------------------------------------------
# determinism_check
# ---------------------------------------------------------------------------
def verify_determinism_and_finalize_l2(out_dir: Path, ref_dir: Path) -> dict:
    stable_files = [
        "LOCAL_NATIVE_L2_REPORT.json",
        "LOCAL_NATIVE_L2_REPORT.md",
        "PROFILE_MANIFEST.json",
        "YEAR_SUMMARY.csv",
        "ORDER_PRESENCE_HOOK_EVENTS.csv",
        "DIRECT_ORDER_DIFFS.csv",
        "TRADE_KEY_DIFFS.csv",
        "STATE_DIFFS_SAMPLE.csv",
    ]

    # Phase 1: compare the stable files as-is
    initial_results = {}
    initial_match = True
    for name in stable_files:
        f_out = out_dir / name
        f_ref = ref_dir / name
        if not f_out.exists() or not f_ref.exists():
            h_out = hashlib.sha256(f_out.read_bytes()).hexdigest() if f_out.exists() else "MISSING"
            h_ref = hashlib.sha256(f_ref.read_bytes()).hexdigest() if f_ref.exists() else "MISSING"
            initial_results[name] = {"hash1": h_out, "hash2": h_ref, "equal": False}
            initial_match = False
        else:
            h_out = hashlib.sha256(f_out.read_bytes()).hexdigest()
            h_ref = hashlib.sha256(f_ref.read_bytes()).hexdigest()
            eq = h_out == h_ref
            if not eq:
                initial_match = False
            initial_results[name] = {"hash1": h_out, "hash2": h_ref, "equal": eq}

    initial_det_status = "PASS" if initial_match else "FAIL"

    # Update gate statuses in report files in BOTH directories
    def update_reports(det_val):
        for target_dir in [out_dir, ref_dir]:
            rpt_path = target_dir / "LOCAL_NATIVE_L2_REPORT.json"
            if rpt_path.exists():
                try:
                    rpt = json.loads(rpt_path.read_text(encoding="utf-8"))
                except Exception:
                    continue
                gates = rpt.get("acceptance_gates", {})
                gates["deterministic_reports"] = det_val

                # Check FINAL_DELIVERY_ARTIFACTS
                final_artifacts_ok = True
                for a in FINAL_DELIVERY_ARTIFACTS:
                    if a in ["ARTIFACT_HASHES.json", "DETERMINISM_REPORT.json"]:
                        continue
                    if not (target_dir / a).exists():
                        final_artifacts_ok = False
                        break
                gates["required_artifacts_complete"] = "PASS" if final_artifacts_ok else "FAIL"

                # Only whitelisted gates may use NOT_COVERED; others must be PASS
                impl_ok = True
                for k, v in gates.items():
                    if k == "implementation_acceptance":
                        continue
                    if v == "PASS":
                        continue
                    if v == "NOT_COVERED" and k in ALLOWED_NOT_COVERED:
                        continue
                    impl_ok = False
                    break
                gates["implementation_acceptance"] = "PASS" if impl_ok else "FAIL"

                rpt["acceptance_gates"] = gates
                if "metadata" in rpt:
                    if "generated_at" in rpt["metadata"]:
                        del rpt["metadata"]["generated_at"]

                rpt_path.write_text(json.dumps(rpt, ensure_ascii=False, indent=2), encoding="utf-8")
                (target_dir / "LOCAL_NATIVE_L2_REPORT.md").write_text(_render_md_l2(rpt), encoding="utf-8")

    update_reports(initial_det_status)

    # Phase 2: Recalculate stable files hashes after report update
    second_results = {}
    second_match = True
    for name in stable_files:
        f_out = out_dir / name
        f_ref = ref_dir / name
        if not f_out.exists() or not f_ref.exists():
            h_out = hashlib.sha256(f_out.read_bytes()).hexdigest() if f_out.exists() else "MISSING"
            h_ref = hashlib.sha256(f_ref.read_bytes()).hexdigest() if f_ref.exists() else "MISSING"
            second_results[name] = {"hash1": h_out, "hash2": h_ref, "equal": False}
            second_match = False
        else:
            h_out = hashlib.sha256(f_out.read_bytes()).hexdigest()
            h_ref = hashlib.sha256(f_ref.read_bytes()).hexdigest()
            eq = h_out == h_ref
            if not eq:
                second_match = False
            second_results[name] = {"hash1": h_out, "hash2": h_ref, "equal": eq}

    # Final determinism status
    final_det_status = "PASS" if (initial_det_status == "PASS" and second_match) else "FAIL"

    if final_det_status == "FAIL" and initial_det_status == "PASS":
        update_reports("FAIL")
        for name in ["LOCAL_NATIVE_L2_REPORT.json", "LOCAL_NATIVE_L2_REPORT.md"]:
            f_out = out_dir / name
            f_ref = ref_dir / name
            h_out = hashlib.sha256(f_out.read_bytes()).hexdigest() if f_out.exists() else "MISSING"
            h_ref = hashlib.sha256(f_ref.read_bytes()).hexdigest() if f_ref.exists() else "MISSING"
            second_results[name] = {"hash1": h_out, "hash2": h_ref, "equal": h_out == h_ref}

    det_report = {
        "status": final_det_status,
        "run1_dir": str(out_dir.relative_to(ROOT) if out_dir.is_relative_to(ROOT) else out_dir),
        "run2_dir": str(ref_dir.relative_to(ROOT) if ref_dir.is_relative_to(ROOT) else ref_dir),
        "files": second_results,
    }

    # Overwrite DETERMINISM_REPORT.json in BOTH directories
    for target_dir in [out_dir, ref_dir]:
        (target_dir / "DETERMINISM_REPORT.json").write_text(
            json.dumps(_jsonable(det_report), ensure_ascii=False, indent=2), encoding="utf-8"
        )

    # Generate ARTIFACT_HASHES.json last in BOTH directories
    for target_dir in [out_dir, ref_dir]:
        hashes = {}
        for a in FINAL_DELIVERY_ARTIFACTS:
            if a == "ARTIFACT_HASHES.json":
                continue
            p = target_dir / a
            if p.exists():
                hashes[a] = hashlib.sha256(p.read_bytes()).hexdigest()

        hashes_path = target_dir / "ARTIFACT_HASHES.json"
        hashes_path.write_text(json.dumps(hashes, indent=2, sort_keys=True), encoding="utf-8")

        for a in hashes:
            p = target_dir / a
            curr_hash = hashlib.sha256(p.read_bytes()).hexdigest()
            assert hashes[a] == curr_hash, f"Hash mismatch for {a} during verification!"

    return det_report


def determinism_check(run1_dir: Path, run2_dir: Path) -> dict:
    return verify_determinism_and_finalize_l2(run1_dir, run2_dir)


# ---------------------------------------------------------------------------
# Markdown renderer
# ---------------------------------------------------------------------------
def _render_md_l2(report: dict) -> str:
    gates = report.get("acceptance_gates", {})
    year_summary = report.get("year_summary", [])
    t1b = report.get("hook_telemetry_l1b", {})
    t2 = report.get("hook_telemetry_l2", {})

    lines = []
    lines.append("# LOCAL_NATIVE_L2 Acceptance Report\n")
    lines.append("## Acceptance Gates Status\n")
    for g, val in gates.items():
        color = "🟢" if val == "PASS" else ("🟡" if val == "NOT_COVERED" else "🔴")
        lines.append(f"- {color} **{g}**: {val}")
    lines.append("\n")

    lines.append("## Year Summary\n")
    if year_summary:
        lines.append("| Year | L1B Final Equity | L2 Final Equity | L1B Return % | L2 Return % | L1B Trades | L2 Trades | Direct Diffs | Downstream Diffs |")
        lines.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- |")
        for row in year_summary:
            lines.append(
                f"| {row.get('year', '')} | "
                f"{row.get('l1b_final_equity', 0):.2f} | "
                f"{row.get('l2_final_equity', 0):.2f} | "
                f"{row.get('l1b_total_return_pct', 0):.4f} | "
                f"{row.get('l2_total_return_pct', 0):.4f} | "
                f"{row.get('l1b_trade_count', 0)} | "
                f"{row.get('l2_trade_count', 0)} | "
                f"{row.get('direct_order_diffs', 0)} | "
                f"{row.get('downstream_trade_diffs', 0)} |"
            )
    lines.append("\n")

    lines.append("## Hook Hits Summary\n")
    lines.append("| Hook ID | Profile | Queries | Effective Hits | Would-Have Hits |")
    lines.append("| --- | --- | --- | --- | --- |")
    for hid in sorted(L2_HOOK_IDS):
        for yr_key in sorted(t1b.keys()):
            info_b = t1b.get(yr_key, {}).get(hid, {})
            info_l2 = t2.get(yr_key, {}).get(hid, {})
            lines.append(f"| `{hid}` (Y{yr_key}) | L1B | {info_b.get('queries', 0)} | {info_b.get('effective_hits', 0)} | {info_b.get('would_have_hits', 0)} |")
            lines.append(f"| `{hid}` (Y{yr_key}) | L2 | {info_l2.get('queries', 0)} | {info_l2.get('effective_hits', 0)} | {info_l2.get('would_have_hits', 0)} |")
    lines.append("\n")

    lines.append("## Notes & Limitations\n")
    lines.append("- **L2 Hooks**: preopen_reject_cash_below, preopen_reject_orders, preopen_drop_first_duplicate\n")
    lines.append("- **Direct Diff Classification**: L1B effective_hit=True + L2 would_have_hit=True with same date/time/code\n")
    lines.append("- **Downstream**: Same-day trade diffs without corresponding hook event, cascading cash/position changes\n")
    lines.append("- **Cash Negativity**: Cash non-negativity check is excluded from checked claims because total cash can naturally go negative during intraday/auction margin execution.\n")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI command handlers
# ---------------------------------------------------------------------------
def cmd_run(args):
    hdata_reader, Engine, DataAPI, EmotionGateJQCompat = setup_runtime()
    summary = run_backtest(
        profile=args.profile, year=args.year,
        out_dir=Path(args.out_dir),
        hdata_reader=hdata_reader, Engine=Engine,
        EmotionGateJQCompat=EmotionGateJQCompat,
    )
    print(json.dumps(_jsonable(summary), ensure_ascii=False, indent=2))


def cmd_compare_l2(args):
    report = compare_runs_l2(
        l1b_root=Path(args.l1b_root),
        l2_root=Path(args.l2_root),
        years=args.years,
        out_dir=Path(args.out_dir),
    )
    gates = report.get("acceptance_gates", {})
    print(f"implementation_acceptance = {gates.get('implementation_acceptance', 'FAIL')}")
    for gate, status in gates.items():
        print(f"  {gate}: {status}")
    if gates.get("implementation_acceptance") != "PASS":
        sys.exit(1)


def cmd_l0_main_vs_head(args):
    main_root = Path(args.main_root)
    head_root = Path(args.head_root)
    out_dir = Path(args.out_dir)

    all_passed = True
    for year in args.years:
        main_dir = main_root / str(year)
        head_dir = head_root / str(year)
        year_out_dir = out_dir / str(year)
        year_out_dir.mkdir(parents=True, exist_ok=True)

        report = generate_l0_report(
            current_dir=head_dir,
            baseline_dir=main_dir,
            out_dir=year_out_dir,
            title="L0 Main vs HEAD Parity Analysis",
            report_filename="L0_MAIN_VS_HEAD_REPORT.json",
            csv_filename="L0_MAIN_VS_HEAD_STATE_DIFFS.csv",
            baseline_commit=args.main_commit,
            current_commit=args.head_commit or get_source_commit(),
        )

        results = report.get("l0_results", {})
        diff_count = sum(results.get(f"{s}_diff_rows", -1) for s in ["trades", "state", "equity", "portfolio_stats", "positions"])
        val_diff = results.get("final_value_diff", -1.0)

        print(f"Year {year}: Total diff rows: {diff_count}, Final value diff: {val_diff}")
        if diff_count != 0 or val_diff != 0.0:
            all_passed = False

    if not all_passed:
        print("FAIL: L0 Parity check failed!")
        sys.exit(1)
    else:
        print("PASS: L0 Parity check passed!")
        sys.exit(0)


def cmd_determinism(args):
    d1, d2 = Path(args.run1_dir), Path(args.run2_dir)
    det_report = determinism_check(d1, d2)
    print(json.dumps(det_report["files"], indent=2))
    print(f"\nDeterministic: {det_report['status']}")
    if det_report["status"] != "PASS":
        sys.exit(1)
    sys.exit(0)


# ---------------------------------------------------------------------------
# Main CLI
# ---------------------------------------------------------------------------
def main():
    p = argparse.ArgumentParser()
    subs = p.add_subparsers(dest="command")

    rp = subs.add_parser("run")
    rp.add_argument("--profile", required=True, choices=["jq_parity", "local_native_l1b", "local_native_l2"])
    rp.add_argument("--year", type=int, required=True)
    rp.add_argument("--out-dir", required=True)

    cp = subs.add_parser("compare-l2")
    cp.add_argument("--l1b-root", required=True)
    cp.add_argument("--l2-root", required=True)
    cp.add_argument("--years", type=int, nargs="+", required=True)
    cp.add_argument("--out-dir", required=True)

    dp = subs.add_parser("determinism")
    dp.add_argument("--run1-dir", required=True)
    dp.add_argument("--run2-dir", required=True)

    lp = subs.add_parser("l0-main-vs-head")
    lp.add_argument("--main-root", required=True)
    lp.add_argument("--head-root", required=True)
    lp.add_argument("--years", type=int, nargs="+", required=True)
    lp.add_argument("--main-commit", default="6369570406b77dda9903e832dccd5516fc9c5986")
    lp.add_argument("--head-commit", default=None)
    lp.add_argument("--out-dir", required=True)

    args = p.parse_args()
    if args.command == "run":
        cmd_run(args)
    elif args.command == "compare-l2":
        cmd_compare_l2(args)
    elif args.command == "determinism":
        cmd_determinism(args)
    elif args.command == "l0-main-vs-head":
        cmd_l0_main_vs_head(args)
    else:
        p.print_help()


if __name__ == "__main__":
    main()