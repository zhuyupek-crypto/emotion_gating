from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / "rebuild_from_archive"
HDATA_ROOT = Path(r"D:\work space\hdata")
HDATA_SCRIPTS = HDATA_ROOT / "scripts"
FORMAL_STRATEGY = ROOT / "母版-20260506-Clone.py"
INSTRUMENTED_STRATEGY = ROOT / "research" / "instrumented_strategies" / "motherboard_phase1a_observed.py"
DEFAULT_OUT = ROOT / "coordination" / "attribution" / "master_phase1a"


def setup_runtime():
    for p in [WORK, HDATA_SCRIPTS, HDATA_ROOT, ROOT]:
        sp = str(p)
        if sp not in sys.path:
            sys.path.insert(0, sp)
    sys.modules["jqdata"] = importlib.import_module("jqdata_compat")
    from core import hdata_reader
    from rebuild_from_archive.engine.core import Engine
    from rebuild_from_archive.project_compat import EmotionGateJQCompat
    from rebuild_from_archive.attribution.observer import AttributionObserver, NullAttributionObserver, set_current_observer
    from rebuild_from_archive.attribution.writer import write_json, write_table, sha256_file
    return hdata_reader, Engine, EmotionGateJQCompat, AttributionObserver, NullAttributionObserver, set_current_observer, write_json, write_table, sha256_file


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def git(*args: str) -> str:
    try:
        return subprocess.check_output(["git", *args], cwd=ROOT, text=True, encoding="utf-8", errors="replace").strip()
    except Exception:
        return "unknown"


def _jsonable(value):
    if isinstance(value, pd.Timestamp):
        return str(value)
    if isinstance(value, float):
        return value
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_jsonable(v) for v in value]
    return value


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
        out[col] = out[col].map(lambda x: str(x) if isinstance(x, (pd.Timestamp,)) else x)
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
    orders_to_df(engine).to_csv(case_dir / "orders.csv", index=False)
    pd.DataFrame(getattr(engine, "daily_state_snapshots", []) or []).to_csv(case_dir / "state_snapshots.csv", index=False)
    pd.DataFrame(getattr(engine, "profile_handlers", []) or []).to_csv(case_dir / "handler_profile.csv", index=False)
    (case_dir / "run.log").write_text("\n".join(logs), encoding="utf-8")
    return {
        "label": label,
        "engine": engine,
        "equity": equity,
        "trades": trades,
        "orders": orders_to_df(engine),
        "state": pd.DataFrame(getattr(engine, "daily_state_snapshots", []) or []),
        "handlers": pd.DataFrame(getattr(engine, "profile_handlers", []) or []),
        "metrics": metrics,
        "elapsed_sec": elapsed,
        "final_value": float(equity["value"].iloc[-1]) if not equity.empty else None,
        "trade_count": int(len(trades)),
        "order_count": int(len(getattr(engine, "orders", {}) or {})),
    }


def parity_report(b0, i0, i1) -> dict:
    def compare_case(ref, other):
        return {
            "trades_equal": frames_equal(ref["trades"], other["trades"]),
            "orders_equal": frames_equal(ref["orders"], other["orders"]),
            "equity_equal": frames_equal(ref["equity"], other["equity"]),
            "state_equal": frames_equal(ref["state"], other["state"]),
            "handler_profile_equal": frames_equal(ref["handlers"][[c for c in ["date", "time", "handler"] if c in ref["handlers"].columns]], other["handlers"][[c for c in ["date", "time", "handler"] if c in other["handlers"].columns]]),
            "final_value_ref": ref["final_value"],
            "final_value_other": other["final_value"],
            "trade_count_ref": ref["trade_count"],
            "trade_count_other": other["trade_count"],
            "order_count_ref": ref["order_count"],
            "order_count_other": other["order_count"],
        }
    return {
        "B0_vs_I0": compare_case(b0, i0),
        "B0_vs_I1": compare_case(b0, i1),
    }


def terminal_summary_rows(signal_events: list[dict]) -> list[dict]:
    counts = {}
    for row in signal_events:
        st = row.get("terminal_state") or "UNRESOLVED"
        counts[st] = counts.get(st, 0) + 1
    return [{"terminal_state": k, "count": v} for k, v in sorted(counts.items())]


def build_atomic_sample(observer, limit=200) -> list[dict]:
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
    for sig in observer.signal_events[:limit]:
        sid = sig.get("signal_id")
        intent = order_by_signal.get(sid, {})
        out = outcome_by_signal.get(sid, {})
        rows.append({
            "schema_version": sig.get("schema_version"),
            "trade_date": sig.get("trade_date"),
            "code": sig.get("code"),
            "branch": sig.get("branch"),
            "observation_level": sig.get("observation_level"),
            "prepared_candidate": sig.get("prepared_candidate"),
            "handler_eligible": sig.get("handler_eligible"),
            "terminal_state": sig.get("terminal_state"),
            "fill_status": out.get("fill_status"),
            "order_id": intent.get("order_id"),
            "entry_price": out.get("entry_price"),
            "entry_amount": out.get("entry_amount"),
        })
    return rows


def instrumentation_diff() -> dict:
    formal = FORMAL_STRATEGY.read_text(encoding="utf-8-sig").replace(chr(13) + chr(10), chr(10))
    inst = INSTRUMENTED_STRATEGY.read_text(encoding="utf-8-sig").replace(chr(13) + chr(10), chr(10))
    begin = "\n# === PHASE1A_ATTRIBUTION_PRELUDE_BEGIN ==="
    end = "# === PHASE1A_ATTRIBUTION_PRELUDE_END ===\n"
    stripped = inst
    if begin in stripped and end in stripped:
        prefix, rest = stripped.split(begin, 1)
        _, suffix = rest.split(end, 1)
        stripped = prefix + chr(10) + suffix
    return {
        "formal_strategy": str(FORMAL_STRATEGY),
        "instrumented_strategy": str(INSTRUMENTED_STRATEGY),
        "formal_sha256": sha256(FORMAL_STRATEGY),
        "instrumented_sha256": sha256(INSTRUMENTED_STRATEGY),
        "prelude_removed_matches_formal": stripped.rstrip() == formal.rstrip(),
        "allowed_difference": "single attribution prelude inserted after `from jqdata import *`",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", default="2023-01-01")
    parser.add_argument("--end", default="2023-03-31")
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT))
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    hdata_reader, Engine, EmotionGateJQCompat, AttributionObserver, NullAttributionObserver, set_current_observer, write_json, write_table, sha256_file = setup_runtime()

    years = {pd.Timestamp(args.start).year - 2, pd.Timestamp(args.start).year - 1, pd.Timestamp(args.start).year}
    if hasattr(hdata_reader, "_update_pivot_cache"):
        hdata_reader._update_pivot_cache(years)

    commit = git("rev-parse", "HEAD")
    inst_sha = sha256(INSTRUMENTED_STRATEGY)

    b0 = run_case("B0_formal", FORMAL_STRATEGY, NullAttributionObserver(), args.start, args.end, out_dir, Engine, EmotionGateJQCompat, set_current_observer)
    i0 = run_case("I0_null", INSTRUMENTED_STRATEGY, NullAttributionObserver(), args.start, args.end, out_dir, Engine, EmotionGateJQCompat, set_current_observer)
    obs = AttributionObserver(strategy_commit=commit, strategy_sha256=inst_sha)
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

    artifacts = {}
    artifacts["SIGNAL_EVENT"] = write_table(obs.signal_events, out_dir / "SIGNAL_EVENT.parquet")
    artifacts["DECISION_EVENT"] = write_table(obs.decision_events, out_dir / "DECISION_EVENT.parquet")
    artifacts["TRADE_OUTCOME"] = write_table(obs.trade_outcomes, out_dir / "TRADE_OUTCOME.parquet")
    artifacts["HANDLER_RESOURCE_SNAPSHOT"] = write_table(obs.handler_snapshots, out_dir / "HANDLER_RESOURCE_SNAPSHOT.parquet")
    artifacts["ATOMIC_EVENT_WIDE"] = write_table(build_atomic_sample(obs, limit=len(obs.signal_events)), out_dir / "ATOMIC_EVENT_WIDE.parquet")

    write_table(obs.signal_events[:200], out_dir / "SIGNAL_EVENT_SAMPLE.csv")
    write_table(obs.decision_events[:200], out_dir / "DECISION_EVENT_SAMPLE.csv")
    write_table(obs.trade_outcomes[:200], out_dir / "TRADE_OUTCOME_SAMPLE.csv")
    write_table(obs.handler_snapshots[:200], out_dir / "HANDLER_RESOURCE_SNAPSHOT_SAMPLE.csv")
    write_table(build_atomic_sample(obs, 200), out_dir / "ATOMIC_EVENT_WIDE_SAMPLE.csv")
    write_table(terminal_summary_rows(obs.signal_events), out_dir / "TERMINAL_STATE_SUMMARY.csv")
    write_table([r for r in obs.signal_events if r.get("terminal_state") == "UNRESOLVED"], out_dir / "UNRESOLVED_EVENTS.csv")

    inst_diff = instrumentation_diff()
    write_json(parity, out_dir / "BEHAVIOR_PARITY.json")
    write_json(mapping, out_dir / "MAPPING_AUDIT.json")
    write_json(inst_diff, out_dir / "INSTRUMENTATION_DIFF.json")

    manifest = {
        "generated_at": pd.Timestamp.now().isoformat(),
        "start": args.start,
        "end": args.end,
        "branch": git("branch", "--show-current"),
        "commit": commit,
        "formal_strategy_sha256": sha256(FORMAL_STRATEGY),
        "instrumented_strategy_sha256": inst_sha,
        "schema_version": "0.2",
        "artifacts": artifacts,
        "command": "python research/run_motherboard_phase1a.py --start %s --end %s" % (args.start, args.end),
    }
    write_json(manifest, out_dir / "RUN_MANIFEST.json")

    status = "PASS"
    if not all(parity[k][field] for k in parity for field in ["trades_equal", "orders_equal", "equity_equal", "state_equal", "handler_profile_equal"]):
        status = "FAIL"
    elif mapping["unmapped_buy_trades"] or mapping["unmapped_sell_trades"]:
        status = "FAIL"
    elif mapping["terminal_states"].get("UNRESOLVED", 0):
        status = "PARTIAL"

    report = f"""# Phase 1A Report

Conclusion: {status}

## Scope

```text
start: {args.start}
end: {args.end}
schema_version: 0.2
formal_strategy_sha256: {sha256(FORMAL_STRATEGY)}
instrumented_strategy_sha256: {inst_sha}
```

## Behavior Parity

```json
{json.dumps(parity, ensure_ascii=False, indent=2)}
```

## Mapping Audit

```json
{json.dumps(mapping, ensure_ascii=False, indent=2)}
```

## Instrumentation Diff

```json
{json.dumps(inst_diff, ensure_ascii=False, indent=2)}
```

## Notes

Phase 1A observes `PREPARED_CANDIDATE` events only. It does not claim true `RAW_PATTERN` coverage and does not compute counterfactual EV or Alpha Matrix outputs.
"""
    (out_dir / "PHASE1A_REPORT.md").write_text(report, encoding="utf-8")

    print(json.dumps({"status": status, "parity": parity, "mapping": mapping}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()






