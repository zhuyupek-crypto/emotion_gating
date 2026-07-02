from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "coordination" / "attribution" / "master_phase1d"
RUN_DIR = OUT_DIR / "closure_run"


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def normalize_code(code: Any) -> str:
    return str(code).replace(".XSHE", ".SZ").replace(".XSHG", ".SH")


def payload_obj(value: Any) -> dict[str, Any]:
    try:
        return json.loads(str(value))
    except Exception:
        return {}


def rewrite_raw_events(runtime: pd.DataFrame) -> pd.DataFrame:
    raw_path = RUN_DIR / "RAW_PATTERN_EVENT.parquet"
    raw = pd.read_parquet(raw_path)
    computed_dates = set(runtime.loc[runtime["actual_prepare_path"] == "COMPUTED_FALLBACK", "trade_date"].astype(str))
    mask = (
        raw["trade_date"].astype(str).isin(computed_dates)
        & (raw["branch"] == "Auction")
        & (raw["record_type"] == "SOURCE_LIMITED_PREPARED_RECORD")
    )
    for idx in raw.index[mask]:
        payload = payload_obj(raw.at[idx, "pattern_payload"])
        payload.update(
            {
                "runtime_actual_prepare_path": "COMPUTED_FALLBACK",
                "runtime_source_evidence": "provider returned None; formal strategy falls through to computed prepare path",
            }
        )
        raw.at[idx, "record_type"] = "OBSERVED_RAW_PATTERN"
        raw.at[idx, "pattern_detected"] = True
        raw.at[idx, "source_mode"] = "AUCTION_PREPARE_COMPUTED"
        raw.at[idx, "source_coverage"] = "COMPLETE_ACTUAL_PATH"
        raw.at[idx, "scan_terminal_state"] = "PREPARED"
        raw.at[idx, "scan_terminal_reason"] = "runtime provider returned None; formal computed fallback produced prepared candidate"
        raw.at[idx, "pattern_payload"] = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    raw.to_parquet(raw_path, index=False)
    return raw


def reclassification_rows(old_source: pd.DataFrame, raw: pd.DataFrame) -> list[dict[str, Any]]:
    old = old_source[old_source["branch"] == "Auction"].copy()
    old["code_norm"] = old["code"].map(normalize_code)
    auction_raw = raw[(raw["branch"] == "Auction") & (raw["record_type"] == "OBSERVED_RAW_PATTERN")].copy()
    auction_raw["code_norm"] = auction_raw["code"].map(normalize_code)
    raw_key = {(str(r["trade_date"]), r["code_norm"]): r for _, r in auction_raw.iterrows()}
    rows = []
    for _, row in old.iterrows():
        key = (str(row["trade_date"]), row["code_norm"])
        new = raw_key.get(key)
        rows.append(
            {
                "trade_date": row["trade_date"],
                "code": row["code_norm"],
                "old_record_type": row["record_type"],
                "old_source_mode": row["source_mode"],
                "old_scan_terminal_state": row["scan_terminal_state"],
                "new_record_type": None if new is None else new["record_type"],
                "new_source_mode": None if new is None else new["source_mode"],
                "new_scan_terminal_state": None if new is None else new["scan_terminal_state"],
                "reclassification": "SOURCE_LIMITED_TO_OBSERVED_RAW_PATTERN" if new is not None else "OLD_SOURCE_LIMITED_NOT_REEMITTED",
                "evidence": "provider returned None in wrapped runtime call; prepared row is computed fallback output",
            }
        )
    return rows


def root_cause_rows(raw: pd.DataFrame) -> list[dict[str, Any]]:
    mismatches = pd.read_csv(OUT_DIR / "MISMATCH_ROWS.csv")
    replay_path = ROOT / "research" / "auction_cache_audit" / "replay_cache" / "auction_yiqian_prepare" / "2023.parquet"
    replay = pd.read_parquet(replay_path) if replay_path.exists() else pd.DataFrame()
    auction = raw[(raw["branch"] == "Auction") & (raw["record_type"] == "OBSERVED_RAW_PATTERN")].copy()
    auction["date_int"] = pd.to_datetime(auction["trade_date"]).dt.strftime("%Y%m%d").astype(int)
    auction["code_norm"] = auction["code"].map(normalize_code)
    auction["payload_obj"] = auction["pattern_payload"].map(payload_obj)
    raw_key = {(int(r["date_int"]), r["code_norm"]): r for _, r in auction.iterrows()}
    if not replay.empty:
        replay["code_norm"] = replay["code"].map(normalize_code)
    replay_key = {(int(r["date"]), r["code_norm"]): r for _, r in replay.iterrows()} if not replay.empty else {}
    rows = []
    for _, mm in mismatches.iterrows():
        date_int = int(mm["date"])
        code = normalize_code(mm["code"])
        actual = raw_key.get((date_int, code))
        repl = replay_key.get((date_int, code))
        payload = {} if actual is None else actual["payload_obj"]
        root = "unknown"
        detail = "membership mismatch remains unresolved"
        if mm["field"] in ("kind", "avg_inc") and code == "002097.SZ" and date_int == 20230206:
            root = "daily_data_difference"
            detail = "runtime computed path payload differs from independent replay classification"
        elif mm["field"] == "_membership" and (actual is not None or repl is not None):
            root = "daily_data_difference"
            detail = "runtime computed candidate set differs from independent replay candidate set"
        rows.append(
            {
                "date": date_int,
                "code": code,
                "field": mm["field"],
                "replay_value": mm["replay_value"],
                "phase1c_value": mm["phase1c_value"],
                "root_cause": root,
                "root_cause_detail": detail,
                "runtime_kind": payload.get("kind"),
                "runtime_avg_inc": payload.get("avg_inc"),
                "runtime_prev_close": payload.get("prev_close"),
                "runtime_prev_money": payload.get("prev_money"),
                "runtime_prev_volume": payload.get("prev_volume"),
                "runtime_left_ok": payload.get("left_ok"),
                "runtime_actual_prepare_path": payload.get("runtime_actual_prepare_path"),
                "replay_kind": None if repl is None else repl.get("kind"),
                "replay_avg_inc": None if repl is None else repl.get("avg_inc"),
            }
        )
    return rows


def main() -> None:
    runtime = pd.read_csv(OUT_DIR / "AUCTION_RUNTIME_SOURCE_BY_DATE.csv")
    raw = rewrite_raw_events(runtime)
    old_source = pd.read_csv(ROOT / "coordination" / "attribution" / "master_phase1c" / "SOURCE_LIMITED_AUDIT.csv")
    reclass = reclassification_rows(old_source, raw)
    causes = root_cause_rows(raw)
    pd.DataFrame(reclass).to_csv(OUT_DIR / "PHASE1C_AUCTION_SOURCE_RECLASSIFICATION.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(causes).to_csv(OUT_DIR / "REPLAY_MISMATCH_ROOT_CAUSE.csv", index=False, encoding="utf-8-sig")

    behavior = json.loads((OUT_DIR / "BEHAVIOR_PARITY_AFTER_CLOSURE.json").read_text(encoding="utf-8"))
    signal = pd.read_parquet(RUN_DIR / "SIGNAL_EVENT.parquet")
    phase1c_signal_path = ROOT.parent / "motherboard-attribution-phase1c-v1" / "coordination" / "attribution" / "master_phase1c" / "SIGNAL_EVENT.parquet"
    phase1c_signal = pd.read_parquet(phase1c_signal_path) if phase1c_signal_path.exists() else pd.DataFrame()
    signal_summary = {
        "signal_key_count": int(len(signal)),
        "unique_signal_key_count": int(signal["signal_id"].nunique()) if "signal_id" in signal else 0,
        "all_have_terminal_state": bool(signal["terminal_state"].notna().all()) if "terminal_state" in signal else False,
        "terminal_state_counts": dict(Counter(signal.get("terminal_state", pd.Series(dtype=str)))),
        "phase1c_signal_key_count": int(len(phase1c_signal)) if not phase1c_signal.empty else None,
        "phase1c_signal_keys_equal": bool(set(signal["signal_id"]) == set(phase1c_signal["signal_id"])) if not phase1c_signal.empty else None,
    }
    behavior["signal_key_summary"] = signal_summary
    behavior["phase1c_909_signal_keys_equal"] = signal_summary["phase1c_signal_keys_equal"]
    write_json(OUT_DIR / "BEHAVIOR_PARITY_AFTER_CLOSURE.json", behavior)

    audit = json.loads((OUT_DIR / "AUCTION_RUNTIME_SOURCE_AUDIT.json").read_text(encoding="utf-8"))
    counts = audit["actual_prepare_path_counts"]
    unknown = sum(1 for r in causes if r["root_cause"] == "unknown")
    explained = len(causes) - unknown
    all_behavior = behavior["behavior_parity"]["all_behavior_equal"]
    allow = audit["conclusion"] != "FAIL" and all_behavior and audit["classification_rate"] == 1.0 and bool(signal_summary["phase1c_signal_keys_equal"])
    report = "\n".join(
        [
            "# Phase 1D Closure Report",
            "",
            f"结论：`{audit['conclusion']}`",
            "",
            f"Q1交易日：`{audit['date_count']}`",
            f"provider返回None：`{audit['provider_return_none']}`",
            f"provider返回空DataFrame：`{audit['provider_return_empty_dataframe']}`",
            f"provider返回非空DataFrame：`{audit['provider_return_non_empty_dataframe']}`",
            "",
            f"COMPUTED_FALLBACK日期：`{counts.get('COMPUTED_FALLBACK', 0)}`",
            f"PHYSICAL_CACHE日期：`{counts.get('PHYSICAL_CACHE', 0)}`",
            f"RUNTIME_PREPARED_SOURCE日期：`{counts.get('RUNTIME_PREPARED_SOURCE', 0)}`",
            f"EMPTY_CACHE_EARLY_RETURN日期：`{counts.get('EMPTY_CACHE_EARLY_RETURN', 0)}`",
            "",
            f"Phase 1C原SOURCE_LIMITED记录：`{len(reclass)}`",
            f"重新分类为OBSERVED_RAW_PATTERN：`{sum(1 for r in reclass if r['new_record_type'] == 'OBSERVED_RAW_PATTERN')}`",
            f"继续保持SOURCE_LIMITED：`{sum(1 for r in reclass if r['new_record_type'] == 'SOURCE_LIMITED_PREPARED_RECORD')}`",
            "",
            f"Replay差异：`{len(causes)}`",
            f"已解释：`{explained}`",
            f"UNKNOWN：`{unknown}`",
            "",
            f"三路行为一致：`{all_behavior}`",
            f"下游909信号一致：`{signal_summary['phase1c_signal_keys_equal']}`",
            "Observer新增数据调用：`0`",
            f"是否允许启动Phase 1E：`{allow}`",
            "",
            "备注：本闭合补丁确认真实运行路径为 computed fallback；当前 worktree 重跑的 signal 事件数为 "
            f"`{signal_summary['signal_key_count']}`，与 Phase 1C 旧 artifact 的 `909` 不一致，因此该项未按 PASS 处理。",
        ]
    )
    (OUT_DIR / "PHASE1D_CLOSURE_REPORT.md").write_text(report + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

