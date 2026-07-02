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

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "coordination" / "attribution" / "master_phase1e"
FULL_RUN = OUT / "full_year_run"
ACC = ROOT / "coordination" / "attribution"
V1 = ROOT / "research" / "instrumented_strategies" / "motherboard_attribution_v1.py"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from research import run_motherboard_phase1c as phase1c
from research import run_motherboard_phase1d_closure as phase1d

FEATURE_DIRS = ["auction_yiqian_prepare", "board_snapshot", "master_prepare_index", "first_seal_time", "call_auction_by_date"]
PROTECTED = [
    "母版-20260506-Clone.py",
    "rebuild_from_archive/engine/core.py",
    "rebuild_from_archive/engine/data_api.py",
    "rebuild_from_archive/project_compat.py",
    "rebuild_from_archive/jqdata_compat.py",
]
EXPECTED = {
    "signal_event_count": 531,
    "signal_key_sha256": "60cb1a92bcf14da9b9409a635ef3e29ba552de3133bdc588218c2126d979ebf5",
    "terminal_state_sha256": "a24157da4db8a0c03afeff1d3021355ad9a38aeb5c3ff64f8ffed1bc8e4b9a9f",
    "source_mode_sha256": "5e5d3d5f86856e82890f8e4238652b1177928b8a14cee14454a8ac6791ecca54",
    "final_value": 1053321.5800000005,
    "trade_count": 87,
    "order_count": 87,
    "branch_counts": {"Auction": 270, "ZB": 166, "YJJ": 45, "Scorpion": 30, "RZQ": 20},
}


def sha_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


def sha_file(path: Path) -> str | None:
    if not path.exists():
        return None
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def git(*args: str) -> str:
    try:
        return subprocess.check_output(["git", *args], cwd=ROOT, text=True, encoding="utf-8", errors="replace").strip()
    except Exception:
        return "unknown"


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def write_csv(path: Path, rows: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df = rows if isinstance(rows, pd.DataFrame) else pd.DataFrame(list(rows or []))
    df.to_csv(path, index=False, encoding="utf-8-sig")


def _stable_cell(value: Any) -> Any:
    if value is None or pd.isna(value) if not isinstance(value, (list, dict, tuple, set)) else False:
        return None
    if isinstance(value, (dict, list, tuple, set)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    return str(value)


def write_table(path: Path, rows: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df = rows if isinstance(rows, pd.DataFrame) else pd.DataFrame(list(rows or []))
    if path.suffix.lower() == ".parquet":
        for col in df.columns:
            if df[col].dtype == "object":
                df[col] = df[col].map(_stable_cell)
        df.to_parquet(path, index=False)
    else:
        df.to_csv(path, index=False, encoding="utf-8-sig")


def hash_df(df: pd.DataFrame, cols: list[str]) -> str:
    x = df.copy()
    for c in cols:
        if c not in x.columns:
            x[c] = ""
    return sha_text(x[cols].astype(str).sort_values(cols).to_csv(index=False))


def source_mode_hash(raw: pd.DataFrame) -> str:
    if raw.empty:
        return hash_df(raw, ["prepared_signal_id", "source_mode"])
    x = raw.copy()
    if "prepared_signal_id" not in x.columns:
        x["prepared_signal_id"] = ""
    x = x[x["prepared_signal_id"].notna()].drop_duplicates(["prepared_signal_id", "source_mode"])
    return hash_df(x, ["prepared_signal_id", "source_mode"])


def protected_hashes() -> dict[str, str | None]:
    out = {p: sha_file(ROOT / p) for p in PROTECTED}
    hdata_reader = Path(r"D:\work space\hdata\scripts\core\hdata_reader.py")
    out[str(hdata_reader)] = sha_file(hdata_reader)
    return out


def cache_precheck() -> dict[str, Any]:
    base = ROOT / "project_cache" / "features"
    rows, files = [], []
    for name in FEATURE_DIRS:
        d = base / name
        found = sorted([p for p in d.rglob("*") if p.is_file()]) if d.exists() else []
        rows.append({"feature": name, "path": str(d), "exists": d.exists(), "file_count": len(found)})
        files += [str(p) for p in found]
    return {"passed": len(files) == 0, "checked": rows, "project_cache_files": files}


def strip_blocks(text: str) -> str:
    out = text.replace("\r\n", "\n")
    markers = [
        ("\n# === PHASE1B_ATTRIBUTION_PRELUDE_BEGIN ===", "# === PHASE1B_ATTRIBUTION_PRELUDE_END ===\n"),
        ("\n# === PHASE1B_ATTRIBUTION_BUY_OVERRIDES_BEGIN ===", "# === PHASE1B_ATTRIBUTION_BUY_OVERRIDES_END ===\n"),
        ("\n# === PHASE1C_SCAN_SOURCE_OVERRIDES_BEGIN ===", "# === PHASE1C_SCAN_SOURCE_OVERRIDES_END ===\n"),
        ("\n# === PHASE1D_CLOSURE_RUNTIME_SOURCE_BEGIN ===", "# === PHASE1D_CLOSURE_RUNTIME_SOURCE_END ===\n"),
    ]
    for b, e in markers:
        if b in out and e in out:
            pre, rest = out.split(b, 1)
            _, post = rest.split(e, 1)
            out = pre + "\n" + post
    return out.replace("import time\nimport hashlib\nfrom pathlib import Path\n", "import time\n")


def materialize_v1() -> dict[str, Any]:
    OUT.mkdir(parents=True, exist_ok=True)
    code = phase1d.closure_strategy_code()
    V1.parent.mkdir(parents=True, exist_ok=True)
    V1.write_text(code, encoding="utf-8")
    formal = phase1c.FORMAL_STRATEGY.read_text(encoding="utf-8-sig").replace("\r\n", "\n")
    diff = {
        "observer_contract_version": "1.0",
        "strategy_path": str(V1),
        "strategy_sha256": sha_file(V1),
        "formal_strategy_sha256": sha_file(phase1c.FORMAL_STRATEGY),
        "normalized_formal_match_after_removing_observer_blocks": strip_blocks(code).rstrip() == formal.rstrip(),
        "source": "research.run_motherboard_phase1d_closure.closure_strategy_code()",
    }
    (OUT / "INSTRUMENTATION_DIFF_V1.md").write_text(
        "# Instrumentation Diff V1\n\n"
        f"observer_contract_version: `{diff['observer_contract_version']}`\n"
        f"strategy_sha256: `{diff['strategy_sha256']}`\n"
        f"formal_strategy_sha256: `{diff['formal_strategy_sha256']}`\n"
        f"normalized_match_after_removing_observer_blocks: `{diff['normalized_formal_match_after_removing_observer_blocks']}`\n\n"
        "The v1 strategy is materialized from the Phase 1D canonical closure generator. Permitted differences are observer and runtime-source evidence blocks only.\n",
        encoding="utf-8",
    )
    return diff


def runtime_manifest(hdata_reader: Any, schema_version: str) -> dict[str, Any]:
    return {
        "runtime_environment": "CODE_NATIVE_COMPUTED_ENVIRONMENT",
        "observer_contract_version": "1.0",
        "downstream_schema_version": schema_version,
        "upstream_schema_version": "0.4",
        "worktree_root": str(ROOT.resolve()),
        "branch": git("branch", "--show-current"),
        "commit": git("rev-parse", "HEAD"),
        "data_root": "D:/work space/hdata/data/processed",
        "hdata_reader_file": getattr(hdata_reader, "__file__", None),
        "python_version": sys.version,
        "platform": platform.platform(),
        "pandas_version": pd.__version__,
        "env_LOCALQUANT_DATA_ROOT": os.environ.get("LOCALQUANT_DATA_ROOT"),
        "env_LOCALQUANT_HDATA_ROOT": os.environ.get("LOCALQUANT_HDATA_ROOT"),
        "protected_sha_before": protected_hashes(),
        "cache_precheck": cache_precheck(),
    }


def run_case(label: str, code: str, observer: Any, start: str, end: str, out_dir: Path, Engine: Any, Compat: Any, set_obs: Any) -> dict[str, Any]:
    return phase1d.run_case_code(label, code, observer, start, end, out_dir, Engine, Compat, set_obs)


def new_observer(Cls: Any, commit: str, strategy_sha: str, formal_sha: str) -> Any:
    obs = Cls(strategy_commit=commit, strategy_sha256=strategy_sha, formal_strategy_commit=commit, formal_strategy_sha256=formal_sha, observer_commit=commit)
    obs.observer_contract_version = "1.0"
    return obs



def canonicalize_phase1d_source(obs: Any) -> None:
    """Apply the Phase 1D canonical runtime-source rewrite before hashing/persisting."""
    computed_dates = {str(e.get("trade_date")) for e in (getattr(obs, "auction_runtime_source_events", []) or []) if e.get("actual_prepare_path") == "COMPUTED_FALLBACK"}
    if not computed_dates:
        return
    for row in getattr(obs, "raw_pattern_events", []) or []:
        if str(row.get("trade_date")) in computed_dates and row.get("branch") == "Auction" and row.get("record_type") == "SOURCE_LIMITED_PREPARED_RECORD":
            payload = {}
            try:
                payload = json.loads(row.get("pattern_payload") or "{}")
            except Exception:
                payload = {}
            payload.update({"runtime_actual_prepare_path": "COMPUTED_FALLBACK", "runtime_source_evidence": "provider returned None; formal strategy falls through to computed prepare path"})
            row["record_type"] = "OBSERVED_RAW_PATTERN"
            row["pattern_detected"] = True
            row["source_mode"] = "AUCTION_PREPARE_COMPUTED"
            row["source_coverage"] = "COMPLETE_ACTUAL_PATH"
            row["scan_terminal_state"] = "PREPARED"
            row["scan_terminal_reason"] = "runtime provider returned None; formal computed fallback produced prepared candidate"
            row["pattern_payload"] = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
def persist(obs: Any, out_dir: Path) -> None:
    tables = {
        "SIGNAL_EVENT": obs.signal_events,
        "DECISION_EVENT": obs.decision_events,
        "TRADE_OUTCOME": obs.trade_outcomes,
        "HANDLER_RESOURCE_SNAPSHOT": obs.handler_snapshots,
        "ORDER_INTENT": obs.order_intents,
        "LOOP_STOP_EVENT": obs.loop_stop_events,
        "POSITION_BLOCK_AUDIT": obs.position_block_events,
        "ORDER_NONE_AUDIT": obs.order_none_events,
        "SCAN_RUN_EVENT": getattr(obs, "scan_run_events", []),
        "RAW_PATTERN_EVENT": getattr(obs, "raw_pattern_events", []),
        "SCAN_DECISION_EVENT": getattr(obs, "scan_decision_events", []),
        "PATTERN_PREPARED_ALIGNMENT": getattr(obs, "pattern_prepared_alignment", []),
        "AUCTION_RUNTIME_SOURCE_BY_DATE": getattr(obs, "auction_runtime_source_events", []),
        "AUCTION_COMPUTED_PREPARE_ROWS": getattr(obs, "auction_computed_prepare_rows", []),
    }
    for name, rows in tables.items():
        write_table(out_dir / f"{name}.parquet", rows)


def parity_all(parity: dict[str, Any]) -> bool:
    return all(v for case in parity.values() if isinstance(case, dict) for k, v in case.items() if k.endswith("_equal"))


def q1_payload(i1: dict[str, Any], obs: Any, behavior: dict[str, Any]) -> dict[str, Any]:
    sig = pd.DataFrame(obs.signal_events)
    raw = pd.DataFrame(getattr(obs, "raw_pattern_events", []) or [])
    got = {
        "q1_gate_passed": False,
        "runtime_environment": "CODE_NATIVE_COMPUTED_ENVIRONMENT",
        "observer_contract_version": "1.0",
        "final_value": i1["final_value"],
        "trade_count": i1["trade_count"],
        "order_count": i1["order_count"],
        "signal_event_count": int(len(sig)),
        "branch_counts": dict(Counter(sig.get("branch", pd.Series(dtype=str)))),
        "signal_key_sha256": hash_df(sig, ["trade_date", "branch", "code", "signal_variant"]),
        "terminal_state_sha256": hash_df(sig, ["trade_date", "branch", "code", "signal_variant", "terminal_state"]),
        "source_mode_sha256": source_mode_hash(raw),
        "behavior_parity": behavior,
        "expected": EXPECTED,
    }
    checks = {
        "behavior_parity": parity_all(behavior),
        "final_value": abs(float(got["final_value"]) - EXPECTED["final_value"]) < 1e-6,
        "trade_count": got["trade_count"] == EXPECTED["trade_count"],
        "order_count": got["order_count"] == EXPECTED["order_count"],
        "signal_event_count": got["signal_event_count"] == EXPECTED["signal_event_count"],
        "branch_counts": got["branch_counts"] == EXPECTED["branch_counts"],
        "signal_key_sha256": got["signal_key_sha256"] == EXPECTED["signal_key_sha256"],
        "terminal_state_sha256": got["terminal_state_sha256"] == EXPECTED["terminal_state_sha256"],
        "source_mode_sha256": got["source_mode_sha256"] == EXPECTED["source_mode_sha256"],
    }
    got["checks"] = checks
    got["q1_gate_passed"] = all(checks.values())
    return got


def summary(case: dict[str, Any]) -> dict[str, Any]:
    return {"label": case["label"], "final_value": case["final_value"], "trade_count": case["trade_count"], "order_count": case["order_count"], "elapsed_sec": case["elapsed_sec"]}


def write_hash_spec() -> None:
    (OUT / "HASH_SPEC.md").write_text(
        "# Hash Spec\n\nAll hashes are SHA256 over UTF-8 CSV text from pandas `to_csv(index=False)` after selecting columns, coercing to string, and sorting by those columns.\n\n"
        "- signal_key_sha256: `trade_date, branch, code, signal_variant`\n"
        "- terminal_state_sha256: `trade_date, branch, code, signal_variant, terminal_state`\n"
        "- source_mode_sha256: distinct `prepared_signal_id, source_mode` from RAW_PATTERN_EVENT\n"
        "- raw_pattern_identity_sha256: `pattern_id, prepared_signal_id, source_mode, scan_terminal_state`\n"
        "- scan_run_identity_sha256: `scan_run_id, branch, scan_status, source_mode, prepared_candidate_count, raw_pattern_count`\n"
        "- order_lineage_sha256: `signal_id, branch, code, side, order_id, order_status`\n"
        "- trade_lineage_sha256: `signal_id, order_id, entry_time, entry_price, entry_amount, fill_status`\n",
        encoding="utf-8",
    )


def summarize_tables(obs: Any, out_dir: Path, engine: Any | None) -> dict[str, Any]:
    sig = pd.DataFrame(obs.signal_events)
    raw = pd.DataFrame(getattr(obs, "raw_pattern_events", []) or [])
    scan = pd.DataFrame(getattr(obs, "scan_run_events", []) or [])
    trade = pd.DataFrame(obs.trade_outcomes)
    orders = pd.DataFrame(obs.order_intents)
    handlers = pd.DataFrame(obs.handler_snapshots)
    unresolved = sig[sig.get("terminal_state") == "UNRESOLVED"] if not sig.empty else sig
    dup = sig[sig.duplicated(["trade_date", "branch", "code", "signal_variant"], keep=False)] if not sig.empty else sig
    unmapped = list(getattr(obs, "unmapped_buy_trades", []) or []) + list(getattr(obs, "unmapped_sell_trades", []) or [])
    group = lambda df, cols: df.groupby(cols, dropna=False).size().reset_index(name="count") if not df.empty else []
    write_csv(out_dir / "SIGNAL_TYPE_AUDIT.csv", group(sig, ["branch", "signal_variant"]))
    write_csv(out_dir / "NULL_ELIGIBILITY_AUDIT.csv", [{"column": c, "null_count": int(sig[c].isna().sum()) if c in sig else None} for c in ["handler_eligible", "branch_eligible"]])
    write_csv(out_dir / "EVIDENCE_SCOPE_MATRIX.csv", [
        {"evidence": "actual_2023_observer_v1", "phase2_use": "allowed", "scope": "actual control flow"},
        {"evidence": "old_phase1c_909", "phase2_use": "forbidden", "scope": "SUPERSEDED_FOR_ATTRIBUTION"},
    ])
    write_csv(out_dir / "MARKET_STATE_COVERAGE.csv", group(sig, ["market_mode", "raw_market_mode"]))
    write_csv(out_dir / "CONTROL_FLOW_COVERAGE.csv", group(scan, ["branch", "scan_status"]))
    write_csv(out_dir / "HANDLER_COVERAGE.csv", group(handlers, ["handler", "stage"]))
    write_csv(out_dir / "TERMINAL_STATE_SUMMARY.csv", group(sig, ["terminal_state"]))
    write_csv(out_dir / "TERMINAL_STATE_BY_BRANCH.csv", group(sig, ["branch", "terminal_state"]))
    write_csv(out_dir / "BLOCK_REASON_SUMMARY.csv", group(sig, ["terminal_state", "terminal_reason_code"]))
    write_csv(out_dir / "BRANCH_DECISION_FUNNEL.csv", phase1c.branch_funnel_rows(obs.signal_events))
    write_csv(out_dir / "SOURCE_MODE_SUMMARY.csv", group(raw, ["branch", "source_mode"]))
    write_csv(out_dir / "SCAN_STATUS_SUMMARY.csv", group(scan, ["branch", "scan_status"]))
    write_csv(out_dir / "UNMAPPED_TRADE_AUDIT.csv", unmapped)
    write_csv(out_dir / "DUPLICATE_LINEAGE_AUDIT.csv", dup)
    write_csv(out_dir / "UNRESOLVED_EVENTS.csv", unresolved)
    positions = []
    if engine is not None:
        for code, pos in sorted((getattr(engine.context.portfolio, "positions", {}) or {}).items()):
            if getattr(pos, "total_amount", 0):
                positions.append({"code": code, "total_amount": getattr(pos, "total_amount", 0), "closeable_amount": getattr(pos, "closeable_amount", None)})
    write_csv(out_dir / "YEAR_END_OPEN_POSITION_LINEAGE.csv", positions)
    vol = {"signal_events": int(len(sig)), "raw_pattern_events": int(len(raw)), "scan_run_events": int(len(scan)), "decision_events": int(len(obs.decision_events)), "order_intents": int(len(orders)), "trade_outcomes": int(len(trade)), "unresolved_events": int(len(unresolved)), "duplicate_signal_key_rows": int(len(dup)), "unmapped_trade_rows": int(len(unmapped))}
    write_csv(out_dir / "EVENT_VOLUME_SUMMARY.csv", [vol])
    write_json(out_dir / "EVENT_VOLUME_SUMMARY.json", vol)
    closure = {"signal_events": vol["signal_events"], "closed_events": vol["signal_events"] - vol["unresolved_events"], "unresolved_events": vol["unresolved_events"], "duplicate_signal_key_rows": vol["duplicate_signal_key_rows"], "unmapped_trade_rows": vol["unmapped_trade_rows"], "trade_lineage_mapping_rate": 1.0 if vol["unmapped_trade_rows"] == 0 else None}
    write_json(out_dir / "FULL_YEAR_EVENT_CLOSURE.json", closure)
    return {"event_volume": vol, "closure": closure}


def repeatability(a: Any, b: Any) -> dict[str, Any]:
    sig_a, sig_b = pd.DataFrame(a.signal_events), pd.DataFrame(b.signal_events)
    raw_a, raw_b = pd.DataFrame(getattr(a, "raw_pattern_events", []) or []), pd.DataFrame(getattr(b, "raw_pattern_events", []) or [])
    scan_a, scan_b = pd.DataFrame(getattr(a, "scan_run_events", []) or []), pd.DataFrame(getattr(b, "scan_run_events", []) or [])
    ord_a, ord_b = pd.DataFrame(a.order_intents), pd.DataFrame(b.order_intents)
    tr_a, tr_b = pd.DataFrame(a.trade_outcomes), pd.DataFrame(b.trade_outcomes)
    out = {
        "signal_key_sha256_a": hash_df(sig_a, ["trade_date", "branch", "code", "signal_variant"]),
        "signal_key_sha256_b": hash_df(sig_b, ["trade_date", "branch", "code", "signal_variant"]),
        "terminal_state_sha256_a": hash_df(sig_a, ["trade_date", "branch", "code", "signal_variant", "terminal_state"]),
        "terminal_state_sha256_b": hash_df(sig_b, ["trade_date", "branch", "code", "signal_variant", "terminal_state"]),
        "source_mode_sha256_a": source_mode_hash(raw_a), "source_mode_sha256_b": source_mode_hash(raw_b),
        "raw_pattern_identity_sha256_a": hash_df(raw_a, ["pattern_id", "prepared_signal_id", "source_mode", "scan_terminal_state"]),
        "raw_pattern_identity_sha256_b": hash_df(raw_b, ["pattern_id", "prepared_signal_id", "source_mode", "scan_terminal_state"]),
        "scan_run_identity_sha256_a": hash_df(scan_a, ["scan_run_id", "branch", "scan_status", "source_mode", "prepared_candidate_count", "raw_pattern_count"]),
        "scan_run_identity_sha256_b": hash_df(scan_b, ["scan_run_id", "branch", "scan_status", "source_mode", "prepared_candidate_count", "raw_pattern_count"]),
        "order_lineage_sha256_a": hash_df(ord_a, ["signal_id", "branch", "code", "side", "order_id", "order_status"]),
        "order_lineage_sha256_b": hash_df(ord_b, ["signal_id", "branch", "code", "side", "order_id", "order_status"]),
        "trade_lineage_sha256_a": hash_df(tr_a, ["signal_id", "order_id", "entry_time", "entry_price", "entry_amount", "fill_status"]),
        "trade_lineage_sha256_b": hash_df(tr_b, ["signal_id", "order_id", "entry_time", "entry_price", "entry_amount", "fill_status"]),
    }
    out["repeatable"] = all(out[k[:-2] + "_a"] == out[k[:-2] + "_b"] for k in list(out) if k.endswith("_b"))
    return out


def write_reports(status: str, q1: dict[str, Any], full: dict[str, Any] | None, rep: dict[str, Any] | None, closure: dict[str, Any] | None, canon: dict[str, Any] | None) -> None:
    (OUT / "PHASE1E_REPORT.md").write_text(
        "# Phase 1E Report\n\n"
        f"Conclusion: `{status}`\n\nQ1 canonical gate passed: `{q1.get('q1_gate_passed')}`\n"
        f"Q1 signal events: `{q1.get('signal_event_count')}`\nQ1 signal key SHA256: `{q1.get('signal_key_sha256')}`\n"
        f"Q1 terminal state SHA256: `{q1.get('terminal_state_sha256')}`\nQ1 source mode SHA256: `{q1.get('source_mode_sha256')}`\n\n"
        f"Full-year behavior parity: `{None if full is None else full.get('all_behavior_equal')}`\n"
        f"Full-year repeatability: `{None if rep is None else rep.get('repeatable')}`\nUnresolved events: `{None if closure is None else closure.get('unresolved_events')}`\n\n"
        "No alpha, EV, branch gate matrix, optimization, or counterfactual analysis is included in Phase 1E.\n",
        encoding="utf-8",
    )
    (ACC / "PHASE1_ACCEPTANCE_REPORT.md").write_text(f"# Phase 1 Acceptance Report\n\nStatus: `{status}`\n\nQ1 canonical gate: `{q1.get('q1_gate_passed')}`\nFull-year behavior parity: `{None if full is None else full.get('all_behavior_equal')}`\nFull-year repeatability: `{None if rep is None else rep.get('repeatable')}`\n", encoding="utf-8")
    (ACC / "ATTRIBUTION_CONTRACT_V1.md").write_text("# Attribution Contract V1\n\nObserver contract version: `1.0`. Downstream fact schema remains `0.3`; upstream scan/source schema remains `0.4`. Phase 2 may use only actual observed 2023 computed-environment facts.\n", encoding="utf-8")
    write_json(ACC / "OBSERVER_V1_MANIFEST.json", {"observer_contract_version": "1.0", "status": status, "strategy_path": str(V1), "strategy_sha256": sha_file(V1), "schema_versions": {"downstream": "0.3", "upstream": "0.4"}})
    write_json(ACC / "CANONICAL_2023_BASELINE.json", canon or {"status": status, "available": False})
    (ACC / "KNOWN_LIMITATIONS.md").write_text("# Known Limitations\n\n- The old Phase 1C 909-signal Q1 artifact is `SUPERSEDED_FOR_ATTRIBUTION`.\n- Phase 1 records actual observed control flow only; it does not contain counterfactual branch universes or EV labels.\n", encoding="utf-8")
    (ACC / "PHASE2_INPUT_CONTRACT.md").write_text("# Phase 2 Input Contract\n\nAllowed input: `coordination/attribution/master_phase1e/` summaries and local full-year fact parquet under `coordination/attribution/master_phase1e/full_year_run/`. Forbidden input: archived Phase 1C 909-signal ledger, optimization outputs, and online replacements for local hdata.\n", encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2023-01-01")
    ap.add_argument("--q1-end", default="2023-03-31")
    ap.add_argument("--end", default="2023-12-31")
    ap.add_argument("--q1-only", action="store_true")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    FULL_RUN.mkdir(parents=True, exist_ok=True)
    write_hash_spec()
    hdata_reader, Engine, Compat, AttrObs, NullObs, set_obs, _, _, _, schema_version = phase1c.setup_runtime()
    years = {pd.Timestamp(args.start).year - 2, pd.Timestamp(args.start).year - 1, pd.Timestamp(args.start).year}
    if hasattr(hdata_reader, "_update_pivot_cache"):
        hdata_reader._update_pivot_cache(years)
    env = runtime_manifest(hdata_reader, schema_version)
    if not env["cache_precheck"]["passed"]:
        write_json(OUT / "RUNTIME_ENVIRONMENT_MANIFEST.json", env)
        raise SystemExit("E0 failed: project cache feature files exist")
    env["instrumentation_diff"] = materialize_v1()
    write_json(OUT / "RUNTIME_ENVIRONMENT_MANIFEST.json", env)
    commit = git("rev-parse", "HEAD")
    formal_code = phase1c.FORMAL_STRATEGY.read_text(encoding="utf-8-sig")
    v1_code = V1.read_text(encoding="utf-8")
    formal_sha, v1_sha = sha_file(phase1c.FORMAL_STRATEGY), sha_file(V1)
    q1_dir = FULL_RUN / "q1_canonical_gate"
    b0 = run_case("B0_Q1_formal_null", formal_code, NullObs(), args.start, args.q1_end, q1_dir, Engine, Compat, set_obs)
    i0 = run_case("I0_Q1_v1_null", v1_code, NullObs(), args.start, args.q1_end, q1_dir, Engine, Compat, set_obs)
    obs_q1 = new_observer(AttrObs, commit, v1_sha, formal_sha)
    i1 = run_case("I1_Q1_v1_observer", v1_code, obs_q1, args.start, args.q1_end, q1_dir, Engine, Compat, set_obs)
    canonicalize_phase1d_source(obs_q1)
    persist(obs_q1, q1_dir / "facts")
    q1_behavior = phase1c.parity_report(b0, i0, i1)
    q1_behavior["all_behavior_equal"] = parity_all(q1_behavior)
    q1 = q1_payload(i1, obs_q1, q1_behavior)
    write_json(OUT / "Q1_CANONICAL_REGRESSION.json", q1)
    if (not q1["q1_gate_passed"]) or args.q1_only:
        status = "Q1_GATE_PASS" if q1["q1_gate_passed"] else "FAIL_Q1_GATE"
        env["protected_sha_after"] = protected_hashes()
        write_json(OUT / "RUNTIME_ENVIRONMENT_MANIFEST.json", env)
        write_reports(status, q1, None, None, None, None)
        write_json(OUT / "RUN_MANIFEST.json", {"status": status, "q1": q1, "runtime_environment": env})
        print(json.dumps({"status": status, "q1": q1}, ensure_ascii=False, indent=2))
        return
    full_dir = FULL_RUN / "full_year"
    b0f = run_case("B0_FULL_YEAR_formal_null", formal_code, NullObs(), args.start, args.end, full_dir, Engine, Compat, set_obs)
    i0f = run_case("I0_FULL_YEAR_v1_null", v1_code, NullObs(), args.start, args.end, full_dir, Engine, Compat, set_obs)
    obs_a = new_observer(AttrObs, commit, v1_sha, formal_sha)
    i1a = run_case("I1_FULL_YEAR_A_v1_observer", v1_code, obs_a, args.start, args.end, full_dir, Engine, Compat, set_obs)
    canonicalize_phase1d_source(obs_a)
    persist(obs_a, full_dir / "I1_FULL_YEAR_A_facts")
    obs_b = new_observer(AttrObs, commit, v1_sha, formal_sha)
    i1b = run_case("I1_FULL_YEAR_B_v1_observer", v1_code, obs_b, args.start, args.end, full_dir, Engine, Compat, set_obs)
    canonicalize_phase1d_source(obs_b)
    persist(obs_b, full_dir / "I1_FULL_YEAR_B_facts")
    full = phase1c.parity_report(b0f, i0f, i1a)
    full["all_behavior_equal"] = parity_all(full)
    write_json(OUT / "FULL_YEAR_BEHAVIOR_PARITY.json", {"cases": [summary(x) for x in [b0f, i0f, i1a]], "behavior_parity": full, "all_behavior_equal": full["all_behavior_equal"]})
    rep = repeatability(obs_a, obs_b)
    write_json(OUT / "FULL_YEAR_REPEATABILITY.json", rep)
    tables = summarize_tables(obs_a, OUT, i1a["engine"])
    closure = tables["closure"]
    write_json(OUT / "PERFORMANCE_AND_CAPACITY.json", {"q1_cases": [summary(x) for x in [b0, i0, i1]], "full_year_cases": [summary(x) for x in [b0f, i0f, i1a, i1b]], "event_volume": tables["event_volume"]})
    env["protected_sha_after"] = protected_hashes()
    protected_ok = env["protected_sha_before"] == env["protected_sha_after"]
    status = "PASS_AND_FREEZE" if full["all_behavior_equal"] and rep["repeatable"] and closure["unresolved_events"] == 0 and closure["duplicate_signal_key_rows"] == 0 and closure["unmapped_trade_rows"] == 0 and protected_ok else "PARTIAL"
    canon = {"status": status, "observer_contract_version": "1.0", "runtime_environment": "CODE_NATIVE_COMPUTED_ENVIRONMENT", "start": args.start, "end": args.end, "strategy_sha256": v1_sha, "formal_strategy_sha256": formal_sha, "signal_event_count": tables["event_volume"]["signal_events"], "signal_key_sha256": rep["signal_key_sha256_a"], "terminal_state_sha256": rep["terminal_state_sha256_a"], "source_mode_sha256": rep["source_mode_sha256_a"], "protected_files_unchanged": protected_ok}
    write_json(OUT / "RUNTIME_ENVIRONMENT_MANIFEST.json", env)
    write_reports(status, q1, full, rep, closure, canon)
    write_json(OUT / "RUN_MANIFEST.json", {"status": status, "generated_at": pd.Timestamp.now().isoformat(), "q1": q1, "full_year_behavior_parity": full, "full_year_repeatability": rep, "closure": closure, "canonical_2023_baseline": canon, "runtime_environment": env})
    print(json.dumps({"status": status, "q1_gate_passed": q1["q1_gate_passed"], "full_year_behavior_equal": full["all_behavior_equal"], "repeatable": rep["repeatable"], "closure": closure}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()





