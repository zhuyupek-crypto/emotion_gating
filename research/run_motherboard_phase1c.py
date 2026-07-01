from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Iterable

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / "rebuild_from_archive"
HDATA_ROOT = Path(r"D:\work space\hdata")
HDATA_SCRIPTS = HDATA_ROOT / "scripts"
FORMAL_STRATEGY = ROOT / "母版-20260506-Clone.py"
INSTRUMENTED_STRATEGY = ROOT / "research" / "instrumented_strategies" / "motherboard_phase1c_observed.py"
DEFAULT_OUT = ROOT / "coordination" / "attribution" / "master_phase1c"
PHASE1B_OUT_CANDIDATES = [
    ROOT.parent / "motherboard-attribution-phase1b-v1" / "coordination" / "attribution" / "master_phase1b",
    ROOT / "coordination" / "attribution" / "master_phase1b",
]


def setup_runtime():
    for p in [WORK, HDATA_SCRIPTS, HDATA_ROOT, ROOT]:
        sp = str(p)
        if sp not in sys.path:
            sys.path.insert(0, sp)
    sys.modules["jqdata"] = __import__("jqdata_compat")
    from core import hdata_reader
    from rebuild_from_archive.engine.core import Engine
    from rebuild_from_archive.project_compat import EmotionGateJQCompat
    from rebuild_from_archive.attribution.observer import AttributionObserver, NullAttributionObserver, set_current_observer
    from rebuild_from_archive.attribution.writer import write_json, write_table, sha256_file
    from rebuild_from_archive.attribution.schema import SCHEMA_VERSION
    return hdata_reader, Engine, EmotionGateJQCompat, AttributionObserver, NullAttributionObserver, set_current_observer, write_json, write_table, sha256_file, SCHEMA_VERSION


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def git(*args: str) -> str:
    try:
        return subprocess.check_output(["git", *args], cwd=ROOT, text=True, encoding="utf-8", errors="replace").strip()
    except Exception:
        return "unknown"


def orders_to_df(engine) -> pd.DataFrame:
    rows = []
    for oid, order in sorted(getattr(engine, "orders", {}).items(), key=lambda x: int(x[0]) if str(x[0]).isdigit() else str(x[0])):
        status = getattr(order, "status", None)
        rows.append({
            "order_id": str(oid),
            "security": getattr(order, "security", None),
            "amount": getattr(order, "amount", None),
            "filled": getattr(order, "filled", None),
            "price": getattr(order, "price", None),
            "side": getattr(order, "side", None),
            "status": getattr(status, "name", status),
            "commission": getattr(order, "commission", None),
        })
    return pd.DataFrame(rows)


def normalize_df(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    out = df.copy()
    for col in out.columns:
        out[col] = out[col].map(lambda x: str(x) if isinstance(x, pd.Timestamp) else x)
    return out.reset_index(drop=True)


def frames_equal(a: pd.DataFrame, b: pd.DataFrame) -> bool:
    a = normalize_df(a)
    b = normalize_df(b)
    if list(a.columns) != list(b.columns) or len(a) != len(b):
        return False
    try:
        pd.testing.assert_frame_equal(a, b, check_dtype=False, check_exact=False, rtol=1e-10, atol=1e-8)
        return True
    except AssertionError:
        return False


def read_table(path: Path) -> pd.DataFrame:
    if path.exists():
        if path.suffix.lower() == ".parquet":
            return pd.read_parquet(path)
        return pd.read_csv(path)
    return pd.DataFrame()


def run_case(label: str, strategy_path: Path, observer, start: str, end: str, out_dir: Path, Engine, EmotionGateJQCompat, set_current_observer):
    set_current_observer(observer)
    strategy_code = strategy_path.read_text(encoding="utf-8-sig")
    compat = EmotionGateJQCompat(ROOT)
    engine = Engine(strategy_code, start, end, 1000000, compat=compat)
    if observer is not None:
        setattr(observer, "engine", engine)
    t0 = time.time()
    equity, trades, logs, metrics = engine.run()
    elapsed = time.time() - t0
    if getattr(observer, "enabled", False):
        observer.finalize(engine)
    case_dir = out_dir / label
    case_dir.mkdir(parents=True, exist_ok=True)
    equity.to_csv(case_dir / "equity.csv", index=False)
    trades.to_csv(case_dir / "trades.csv", index=False)
    orders = orders_to_df(engine)
    orders.to_csv(case_dir / "orders.csv", index=False)
    state = pd.DataFrame(getattr(engine, "daily_state_snapshots", []) or [])
    handlers = pd.DataFrame(getattr(engine, "profile_handlers", []) or [])
    state.to_csv(case_dir / "state_snapshots.csv", index=False)
    handlers.to_csv(case_dir / "handler_profile.csv", index=False)
    (case_dir / "run.log").write_text("\n".join(logs), encoding="utf-8")
    return {
        "label": label,
        "engine": engine,
        "equity": equity,
        "trades": trades,
        "orders": orders,
        "state": state,
        "handlers": handlers,
        "metrics": metrics,
        "elapsed_sec": elapsed,
        "final_value": float(equity["value"].iloc[-1]) if not equity.empty else None,
        "trade_count": int(len(trades)),
        "order_count": int(len(getattr(engine, "orders", {}) or {})),
    }


def handler_key_df(df: pd.DataFrame) -> pd.DataFrame:
    cols = [c for c in ["date", "time", "handler"] if c in df.columns]
    return df[cols] if cols else pd.DataFrame()


def parity_report(b0, i0, i1) -> dict:
    def compare_case(ref, other):
        return {
            "trades_equal": frames_equal(ref["trades"], other["trades"]),
            "orders_equal": frames_equal(ref["orders"], other["orders"]),
            "equity_equal": frames_equal(ref["equity"], other["equity"]),
            "state_equal": frames_equal(ref["state"], other["state"]),
            "handler_profile_equal": frames_equal(handler_key_df(ref["handlers"]), handler_key_df(other["handlers"])),
            "final_value_ref": ref["final_value"],
            "final_value_other": other["final_value"],
            "trade_count_ref": ref["trade_count"],
            "trade_count_other": other["trade_count"],
            "order_count_ref": ref["order_count"],
            "order_count_other": other["order_count"],
        }
    return {"B0_vs_I0": compare_case(b0, i0), "B0_vs_I1": compare_case(b0, i1)}


def terminal_summary_rows(signal_events: Iterable[dict]) -> list[dict]:
    rows = pd.DataFrame(list(signal_events))
    if rows.empty:
        return []
    group_cols = ["branch", "terminal_state"]
    return rows.groupby(group_cols, dropna=False).size().reset_index(name="count").sort_values(group_cols).to_dict("records")


def block_reason_rows(signal_events: Iterable[dict]) -> list[dict]:
    df = pd.DataFrame(list(signal_events))
    if df.empty:
        return []
    blocked = df[df["terminal_state"].isin(["BRANCH_FILTERED", "MOTHERBOARD_GATED_OUT", "ROUTED_OUT", "RANKED_OUT", "SLOT_BLOCKED", "CASH_BLOCKED", "POSITION_BLOCKED", "ORDER_NOT_CREATED", "ORDER_REJECTED", "DATA_INVALID", "NOT_EVALUATED_AFTER_STOP"])]
    if blocked.empty:
        return []
    return blocked.groupby(["branch", "terminal_state", "terminal_reason_code"], dropna=False).size().reset_index(name="count").sort_values(["branch", "terminal_state", "count"], ascending=[True, True, False]).to_dict("records")


def branch_funnel_rows(signal_events: Iterable[dict]) -> list[dict]:
    df = pd.DataFrame(list(signal_events))
    if df.empty:
        return []
    rows = []
    bool_cols = ["prepared_candidate", "handler_reached", "candidate_loop_reached", "handler_eligible", "branch_eligible", "qualified_for_ranking", "participated_in_ranking", "selected_for_order"]
    for branch, gdf in df.groupby("branch", dropna=False):
        row = {"branch": branch, "signal_events": int(len(gdf))}
        for col in bool_cols:
            row[col] = int(gdf[col].fillna(False).astype(bool).sum()) if col in gdf.columns else 0
        row["filled"] = int((gdf["terminal_state"] == "FILLED").sum())
        row["unresolved"] = int((gdf["terminal_state"] == "UNRESOLVED").sum())
        rows.append(row)
    return rows


def build_atomic_sample(observer, limit=None) -> list[dict]:
    order_by_signal = {}
    for intent in observer.order_intents:
        sid = intent.get("signal_id")
        if sid and sid not in order_by_signal:
            order_by_signal[sid] = intent
    outcome_by_signal = {}
    for out in observer.trade_outcomes:
        sid = out.get("signal_id")
        if sid and sid not in outcome_by_signal:
            outcome_by_signal[sid] = out
    rows = []
    source = observer.signal_events if limit is None else observer.signal_events[:limit]
    for sig in source:
        sid = sig.get("signal_id")
        intent = order_by_signal.get(sid, {})
        out = outcome_by_signal.get(sid, {})
        rows.append({
            "schema_version": sig.get("schema_version"),
            "trade_date": sig.get("trade_date"),
            "code": sig.get("code"),
            "branch": sig.get("branch"),
            "signal_variant": sig.get("signal_variant"),
            "observation_level": sig.get("observation_level"),
            "prepared_candidate": sig.get("prepared_candidate"),
            "handler_reached": sig.get("handler_reached"),
            "candidate_loop_reached": sig.get("candidate_loop_reached"),
            "handler_eligible": sig.get("handler_eligible"),
            "branch_eligible": sig.get("branch_eligible"),
            "qualified_for_ranking": sig.get("qualified_for_ranking"),
            "participated_in_ranking": sig.get("participated_in_ranking"),
            "selected_for_order": sig.get("selected_for_order"),
            "terminal_state": sig.get("terminal_state"),
            "terminal_reason_code": sig.get("terminal_reason_code"),
            "fill_status": out.get("fill_status"),
            "order_id": intent.get("order_id"),
            "order_status": intent.get("order_status"),
            "entry_price": out.get("entry_price"),
            "entry_amount": out.get("entry_amount"),
        })
    return rows


def strip_instrumentation(text: str) -> str:
    stripped = text
    markers = [
        ("\n# === PHASE1B_ATTRIBUTION_PRELUDE_BEGIN ===", "# === PHASE1B_ATTRIBUTION_PRELUDE_END ===\n"),
        ("\n# === PHASE1B_ATTRIBUTION_BUY_OVERRIDES_BEGIN ===", "# === PHASE1B_ATTRIBUTION_BUY_OVERRIDES_END ===\n"),
        ("\n# === PHASE1C_SCAN_SOURCE_OVERRIDES_BEGIN ===", "# === PHASE1C_SCAN_SOURCE_OVERRIDES_END ===\n"),
    ]
    for begin, end in markers:
        if begin in stripped and end in stripped:
            prefix, rest = stripped.split(begin, 1)
            _, suffix = rest.split(end, 1)
            stripped = prefix + "\n" + suffix
    return stripped


def instrumentation_diff() -> dict:
    formal = FORMAL_STRATEGY.read_text(encoding="utf-8-sig").replace("\r\n", "\n")
    inst = INSTRUMENTED_STRATEGY.read_text(encoding="utf-8-sig").replace("\r\n", "\n")
    stripped = strip_instrumentation(inst)
    return {
        "formal_strategy": str(FORMAL_STRATEGY),
        "instrumented_strategy": str(INSTRUMENTED_STRATEGY),
        "formal_sha256": sha256(FORMAL_STRATEGY),
        "instrumented_sha256": sha256(INSTRUMENTED_STRATEGY),
        "prelude_and_overrides_removed_match_formal": stripped.rstrip() == formal.rstrip(),
        "allowed_difference": "attribution prelude, end-of-file buy-handler overrides, and Phase 1C scan-source overrides only",
    }


def event_closure_audit(signal_events: list[dict]) -> dict:
    total = len(signal_events)
    unresolved = [r for r in signal_events if r.get("terminal_state") == "UNRESOLVED"]
    duplicate_keys = []
    seen = set()
    for r in signal_events:
        key = (r.get("trade_date"), r.get("branch"), r.get("code"), r.get("signal_variant"))
        if key in seen:
            duplicate_keys.append("|".join(str(x) for x in key))
        seen.add(key)
    return {
        "signal_events": total,
        "closed_events": total - len(unresolved),
        "unresolved_events": len(unresolved),
        "unresolved_rate": len(unresolved) / max(1, total),
        "duplicate_signal_keys": duplicate_keys[:50],
        "duplicate_signal_key_count": len(duplicate_keys),
        "all_have_terminal_state": all(bool(r.get("terminal_state")) for r in signal_events),
        "all_have_v03_key": all(r.get("trade_date") and r.get("branch") and r.get("code") and r.get("signal_variant") for r in signal_events),
    }


def phase1b_alignment(out_dir: Path, phase1c_cases: dict, signal_events: list[dict]) -> dict:
    phase1b_dir = next((p for p in PHASE1B_OUT_CANDIDATES if p.exists()), None)
    result = {"phase1b_dir": str(phase1b_dir) if phase1b_dir else None, "available": phase1b_dir is not None}
    if phase1b_dir is None:
        return result
    result["trades_equal"] = frames_equal(read_table(phase1b_dir / "B0_formal" / "trades.csv"), read_table(out_dir / "B0_formal" / "trades.csv"))
    result["orders_equal"] = frames_equal(read_table(phase1b_dir / "B0_formal" / "orders.csv"), read_table(out_dir / "B0_formal" / "orders.csv"))
    p1a_signal = read_table(phase1b_dir / "SIGNAL_EVENT.parquet")
    if p1a_signal.empty:
        p1a_signal = read_table(phase1b_dir / "SIGNAL_EVENT_SAMPLE.csv")
        result["signal_set_source"] = "sample"
    else:
        result["signal_set_source"] = "full"
    p1b_signal = pd.DataFrame(signal_events)
    key_cols = ["trade_date", "branch", "code", "signal_variant"]
    if all(c in p1a_signal.columns for c in key_cols) and all(c in p1b_signal.columns for c in key_cols):
        k1 = set(map(tuple, p1a_signal[key_cols].astype(str).itertuples(index=False, name=None)))
        k2 = set(map(tuple, p1b_signal[key_cols].astype(str).itertuples(index=False, name=None)))
        result.update({
            "signal_keys_equal": k1 == k2,
            "phase1b_signal_keys": len(k1),
            "phase1c_signal_keys": len(k2),
            "phase1b_minus_phase1c_sample": ["|".join(x) for x in sorted(k1 - k2)[:20]],
            "phase1c_minus_phase1b_sample": ["|".join(x) for x in sorted(k2 - k1)[:20]],
        })
    else:
        result["signal_keys_equal"] = None
        result["signal_key_note"] = "Phase 1B full SIGNAL_EVENT not found or lacks v0.3 key columns."
    return result


def _group_count(rows, cols):
    df = pd.DataFrame(rows)
    if df.empty:
        return []
    return df.groupby(cols, dropna=False).size().reset_index(name="count").sort_values(cols).to_dict("records")


def scan_run_summary_rows(rows):
    df = pd.DataFrame(rows)
    if df.empty:
        return []
    out = []
    for branch, gdf in df.groupby("branch", dropna=False):
        out.append({
            "branch": branch,
            "scan_days": int(len(gdf)),
            "not_run_days": int((gdf["scan_status"] == "NOT_CALLED_BY_CONTROL_FLOW").sum()),
            "source_error_days": int((gdf["scan_status"] == "SOURCE_ERROR").sum()),
            "source_limited_days": int((gdf["scan_status"] == "SOURCE_LIMITED").sum()),
            "source_universe_count": None if "source_universe_count" not in gdf else pd.to_numeric(gdf["source_universe_count"], errors="coerce").sum(skipna=True),
            "raw_pattern_count": pd.to_numeric(gdf.get("raw_pattern_count"), errors="coerce").sum(skipna=True),
            "source_limited_prepared_record_count": pd.to_numeric(gdf.get("source_limited_prepared_record_count"), errors="coerce").sum(skipna=True),
            "prepared_candidate_count": pd.to_numeric(gdf.get("prepared_candidate_count"), errors="coerce").sum(skipna=True),
        })
    return out


def raw_pattern_funnel_rows(raw_rows):
    df = pd.DataFrame(raw_rows)
    if df.empty:
        return []
    out = []
    for branch, gdf in df.groupby("branch", dropna=False):
        observed = gdf[gdf["record_type"] == "OBSERVED_RAW_PATTERN"]
        source_limited = gdf[gdf["record_type"] == "SOURCE_LIMITED_PREPARED_RECORD"]
        out.append({
            "branch": branch,
            "raw_pattern_event_rows": int(len(gdf)),
            "observed_raw_pattern_count": int(len(observed)),
            "source_limited_prepared_record_count": int(len(source_limited)),
            "prepared_count": int((gdf["scan_terminal_state"] == "PREPARED").sum()),
            "source_limited_count": int((gdf["scan_terminal_state"] == "SOURCE_LIMITED").sum()),
            "unresolved_count": int((gdf["scan_terminal_state"] == "UNRESOLVED").sum()),
            "observed_pattern_parent_mapping_rate": float(observed["prepared_signal_id"].notna().mean()) if len(observed) else None,
            "source_record_parent_mapping_rate": float(source_limited["prepared_signal_id"].notna().mean()) if len(source_limited) else None,
            "source_limited_ratio": float(len(source_limited) / max(1, len(gdf))),
        })
    return out


def static_api_audit() -> dict:
    observer_text = (ROOT / "rebuild_from_archive" / "attribution" / "observer.py").read_text(encoding="utf-8")
    forbidden = ["history(", "attribute_history(", "get_price(", "get_fundamentals(", "get_billboard_list(", "get_call_auction(", "get_project_board_snapshot(", "get_project_auction_yiqian_prepare("]
    hits = {name: observer_text.count(name) for name in forbidden}
    return {"observer_forbidden_data_api_call_count": sum(hits.values()), "hits": hits}

def status_from(parity: dict, mapping: dict, closure: dict) -> str:
    parity_ok = all(parity[k][field] for k in parity for field in ["trades_equal", "orders_equal", "equity_equal", "state_equal", "handler_profile_equal"])
    if not parity_ok or mapping["unmapped_buy_trades"] or mapping["unmapped_sell_trades"]:
        return "FAIL"
    rate = closure["unresolved_rate"]
    if rate < 0.005:
        return "PASS"
    if rate <= 0.02:
        return "PARTIAL"
    return "FAIL"


def write_report(path: Path, status: str, args, schema_version: str, parity: dict, mapping: dict, closure: dict, alignment: dict, inst_diff: dict, upstream: dict, api_audit: dict):
    report = f"""# Phase 1C Report

Conclusion: {status}

## Scope

```text
start: {args.start}
end: {args.end}
upstream_schema_version: 0.4
downstream_schema_version: {schema_version}
phase1b_downstream_semantics_changed: false
outcome_scope: MASTER_ACTUAL
formal_strategy_sha256: {sha256(FORMAL_STRATEGY)}
instrumented_strategy_sha256: {sha256(INSTRUMENTED_STRATEGY)}
```

## Schema Strategy

```text
upstream_tables: 0.4
downstream_tables: 0.3
phase1b_downstream_semantics_changed: false
```

## Upstream Scan Audit

```json
{json.dumps(upstream, ensure_ascii=False, indent=2)}
```

## Observer Data API Audit

```json
{json.dumps(api_audit, ensure_ascii=False, indent=2)}
```

## Closure

```json
{json.dumps(closure, ensure_ascii=False, indent=2)}
```

## Behavior Parity

```json
{json.dumps(parity, ensure_ascii=False, indent=2)}
```

## Mapping Audit

```json
{json.dumps(mapping, ensure_ascii=False, indent=2)}
```

## Phase 1B / Phase 1C Alignment

```json
{json.dumps(alignment, ensure_ascii=False, indent=2)}
```

## Instrumentation Diff

```json
{json.dumps(inst_diff, ensure_ascii=False, indent=2)}
```

## Notes

Phase 1C adds upstream scan/source facts with schema_version 0.4 while preserving Phase 1B downstream schema_version 0.3 semantics. It does not introduce shadow scans, additional observer data API calls, counterfactual EV, Alpha Matrix, or strategy-parameter changes.
"""
    path.write_text(report, encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", default="2023-01-01")
    parser.add_argument("--end", default="2023-03-31")
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT))
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    hdata_reader, Engine, EmotionGateJQCompat, AttributionObserver, NullAttributionObserver, set_current_observer, write_json, write_table, sha256_file, schema_version = setup_runtime()

    years = {pd.Timestamp(args.start).year - 2, pd.Timestamp(args.start).year - 1, pd.Timestamp(args.start).year}
    if hasattr(hdata_reader, "_update_pivot_cache"):
        hdata_reader._update_pivot_cache(years)

    commit = git("rev-parse", "HEAD")
    formal_sha = sha256(FORMAL_STRATEGY)
    inst_sha = sha256(INSTRUMENTED_STRATEGY)

    b0 = run_case("B0_formal", FORMAL_STRATEGY, NullAttributionObserver(), args.start, args.end, out_dir, Engine, EmotionGateJQCompat, set_current_observer)
    i0 = run_case("I0_null", INSTRUMENTED_STRATEGY, NullAttributionObserver(), args.start, args.end, out_dir, Engine, EmotionGateJQCompat, set_current_observer)
    obs = AttributionObserver(
        strategy_commit=commit,
        strategy_sha256=inst_sha,
        formal_strategy_commit=commit,
        formal_strategy_sha256=formal_sha,
        observer_commit=commit,
    )
    i1 = run_case("I1_observer", INSTRUMENTED_STRATEGY, obs, args.start, args.end, out_dir, Engine, EmotionGateJQCompat, set_current_observer)

    parity = parity_report(b0, i0, i1)
    mapping = obs.audit_summary()
    mapping.update({
        "buy_trade_mapping_rate": 1.0 if mapping["unmapped_buy_trades"] == 0 else mapping["mapped_buy_trades"] / max(1, mapping["mapped_buy_trades"] + mapping["unmapped_buy_trades"]),
        "sell_trace_unmapped_count": mapping["unmapped_sell_trades"],
        "order_to_handler_mapped": len(obs.order_to_handler),
        "engine_order_count": i1["order_count"],
        "order_to_handler_mapping_rate": len(obs.order_to_handler) / max(1, i1["order_count"]),
    })
    closure = event_closure_audit(obs.signal_events)
    inst_diff = instrumentation_diff()
    cases = {"B0_formal": b0, "I0_null": i0, "I1_observer": i1}
    alignment = phase1b_alignment(out_dir, cases, obs.signal_events)
    upstream = obs.upstream_audit()
    api_audit = static_api_audit()
    status = status_from(parity, mapping, closure)
    if upstream.get("unique_trade_date_branch") != 295 or api_audit.get("observer_forbidden_data_api_call_count") != 0:
        status = "FAIL"

    artifacts = {}
    artifacts["SIGNAL_EVENT"] = write_table(obs.signal_events, out_dir / "SIGNAL_EVENT.parquet")
    artifacts["DECISION_EVENT"] = write_table(obs.decision_events, out_dir / "DECISION_EVENT.parquet")
    artifacts["TRADE_OUTCOME"] = write_table(obs.trade_outcomes, out_dir / "TRADE_OUTCOME.parquet")
    artifacts["HANDLER_RESOURCE_SNAPSHOT"] = write_table(obs.handler_snapshots, out_dir / "HANDLER_RESOURCE_SNAPSHOT.parquet")
    artifacts["ORDER_INTENT"] = write_table(obs.order_intents, out_dir / "ORDER_INTENT.parquet")
    artifacts["LOOP_STOP_EVENT"] = write_table(obs.loop_stop_events, out_dir / "LOOP_STOP_EVENT.parquet")
    artifacts["POSITION_BLOCK_AUDIT"] = write_table(obs.position_block_events, out_dir / "POSITION_BLOCK_AUDIT.parquet")
    artifacts["ORDER_NONE_AUDIT"] = write_table(obs.order_none_events, out_dir / "ORDER_NONE_AUDIT.parquet")
    artifacts["ATOMIC_EVENT_WIDE"] = write_table(build_atomic_sample(obs), out_dir / "ATOMIC_EVENT_WIDE.parquet")
    artifacts["SCAN_RUN_EVENT"] = write_table(obs.scan_run_events, out_dir / "SCAN_RUN_EVENT.parquet")
    artifacts["RAW_PATTERN_EVENT"] = write_table(obs.raw_pattern_events, out_dir / "RAW_PATTERN_EVENT.parquet")
    artifacts["SCAN_DECISION_EVENT"] = write_table(obs.scan_decision_events, out_dir / "SCAN_DECISION_EVENT.parquet")
    artifacts["PATTERN_PREPARED_ALIGNMENT"] = write_table(obs.pattern_prepared_alignment, out_dir / "PATTERN_PREPARED_ALIGNMENT.parquet")

    write_table(obs.signal_events[:200], out_dir / "SIGNAL_EVENT_SAMPLE.csv")
    write_table(obs.decision_events[:200], out_dir / "DECISION_EVENT_SAMPLE.csv")
    write_table(obs.trade_outcomes[:200], out_dir / "TRADE_OUTCOME_SAMPLE.csv")
    write_table(obs.handler_snapshots[:200], out_dir / "HANDLER_RESOURCE_SNAPSHOT_SAMPLE.csv")
    write_table(obs.order_intents[:200], out_dir / "ORDER_INTENT_SAMPLE.csv")
    write_table(obs.loop_stop_events[:200], out_dir / "LOOP_STOP_EVENT_SAMPLE.csv")
    write_table(obs.position_block_events[:200], out_dir / "POSITION_BLOCK_AUDIT_SAMPLE.csv")
    write_table(obs.order_none_events[:200], out_dir / "ORDER_NONE_AUDIT_SAMPLE.csv")
    write_table(build_atomic_sample(obs, 200), out_dir / "ATOMIC_EVENT_WIDE_SAMPLE.csv")
    write_table(terminal_summary_rows(obs.signal_events), out_dir / "TERMINAL_STATE_BY_BRANCH.csv")
    write_table(block_reason_rows(obs.signal_events), out_dir / "BLOCK_REASON_SUMMARY.csv")
    write_table(branch_funnel_rows(obs.signal_events), out_dir / "BRANCH_DECISION_FUNNEL.csv")
    write_table([r for r in obs.signal_events if r.get("terminal_state") == "UNRESOLVED"], out_dir / "UNRESOLVED_EVENTS.csv")
    write_table(obs.scan_run_events[:200], out_dir / "SCAN_RUN_EVENT_SAMPLE.csv")
    write_table(obs.raw_pattern_events[:200], out_dir / "RAW_PATTERN_EVENT_SAMPLE.csv")
    write_table(obs.scan_decision_events[:200], out_dir / "SCAN_DECISION_EVENT_SAMPLE.csv")
    write_table(obs.pattern_prepared_alignment, out_dir / "PATTERN_PREPARED_ALIGNMENT.csv")
    write_table(scan_run_summary_rows(obs.scan_run_events), out_dir / "SCAN_RUN_SUMMARY.csv")
    write_table(_group_count(obs.scan_run_events, ["branch", "scan_status"]), out_dir / "SCAN_STATUS_BY_BRANCH.csv")
    write_table(_group_count(obs.scan_run_events, ["branch", "source_mode"]), out_dir / "SOURCE_MODE_SUMMARY.csv")
    write_table(raw_pattern_funnel_rows(obs.raw_pattern_events), out_dir / "RAW_PATTERN_FUNNEL_BY_BRANCH.csv")
    write_table(raw_pattern_funnel_rows(obs.raw_pattern_events), out_dir / "RAW_PATTERN_FUNNEL.csv")
    write_table(_group_count(obs.raw_pattern_events, ["branch", "scan_terminal_state", "scan_terminal_reason"]), out_dir / "SCAN_FILTER_REASON_SUMMARY.csv")
    write_table([r for r in obs.pattern_prepared_alignment if r.get("alignment_status") == "MISSING_PATTERN_PARENT"], out_dir / "PREPARED_WITHOUT_PATTERN_PARENT.csv")
    write_table([r for r in obs.pattern_prepared_alignment if r.get("alignment_status") == "DUPLICATE_PATTERN_PARENT"], out_dir / "DUPLICATE_PATTERN_PARENT.csv")
    write_table([r for r in obs.raw_pattern_events if r.get("scan_terminal_state") == "SOURCE_LIMITED"], out_dir / "SOURCE_LIMITED_AUDIT.csv")
    write_table([r for r in obs.raw_pattern_events if r.get("scan_terminal_state") == "UNRESOLVED"], out_dir / "UNRESOLVED_PATTERN_EVENTS.csv")

    write_json(parity, out_dir / "BEHAVIOR_PARITY.json")
    write_json(mapping, out_dir / "MAPPING_AUDIT.json")
    write_json(closure, out_dir / "EVENT_CLOSURE_AUDIT.json")
    write_json(alignment, out_dir / "PHASE1B_PHASE1C_ALIGNMENT.json")
    write_json(inst_diff, out_dir / "INSTRUMENTATION_DIFF.json")
    write_json(upstream, out_dir / "UPSTREAM_SCAN_AUDIT.json")
    write_json(api_audit, out_dir / "OBSERVER_DATA_API_AUDIT.json")

    manifest = {
        "generated_at": pd.Timestamp.now().isoformat(),
        "start": args.start,
        "end": args.end,
        "branch": git("branch", "--show-current"),
        "commit": commit,
        "formal_strategy_commit": commit,
        "formal_strategy_sha256": formal_sha,
        "instrumented_strategy_commit": commit,
        "instrumented_strategy_sha256": inst_sha,
        "observer_commit": commit,
        "downstream_schema_version": schema_version,
        "upstream_schema_version": "0.4",
        "status": status,
        "artifacts": artifacts,
        "command": "python research/run_motherboard_phase1c.py --start %s --end %s" % (args.start, args.end),
    }
    write_json(manifest, out_dir / "RUN_MANIFEST.json")
    write_report(out_dir / "PHASE1C_REPORT.md", status, args, schema_version, parity, mapping, closure, alignment, inst_diff, upstream, api_audit)

    print(json.dumps({"status": status, "closure": closure, "mapping": mapping, "upstream": upstream, "api_audit": api_audit, "parity": parity, "alignment": alignment}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()






