from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
ACC = ROOT / "coordination" / "attribution"


def sha_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


def sha_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def stable_hash(df: pd.DataFrame, cols: list[str]) -> str:
    x = df.copy()
    for col in cols:
        if col not in x.columns:
            x[col] = ""
    return sha_text(x[cols].astype(str).sort_values(cols).to_csv(index=False))


def source_mode_hash(raw: pd.DataFrame) -> str:
    if raw.empty:
        return stable_hash(raw, ["prepared_signal_id", "source_mode"])
    x = raw.copy()
    if "prepared_signal_id" not in x.columns:
        x["prepared_signal_id"] = ""
    x = x[x["prepared_signal_id"].notna()].drop_duplicates(["prepared_signal_id", "source_mode"])
    return stable_hash(x, ["prepared_signal_id", "source_mode"])


def row_count(path: Path) -> int | None:
    try:
        if path.suffix.lower() == ".parquet":
            return int(len(pd.read_parquet(path)))
        if path.suffix.lower() == ".csv":
            return int(len(pd.read_csv(path)))
    except Exception:
        return None
    return None


def resolve_source(source_root: Path) -> tuple[Path, Path]:
    candidates = [
        (source_root / "full_year" / "I1_FULL_YEAR_A_facts", source_root / "full_year" / "I1_FULL_YEAR_A_v1_observer"),
        (source_root / "I1_FULL_YEAR_A_facts", source_root / "I1_FULL_YEAR_A_v1_observer"),
        (source_root, source_root.parent / "I1_FULL_YEAR_A_v1_observer"),
    ]
    for facts, observer in candidates:
        if (facts / "SIGNAL_EVENT.parquet").exists() and (observer / "trades.csv").exists():
            return facts.resolve(), observer.resolve()
    raise SystemExit(f"Cannot locate Phase 1E A facts and observer csvs under {source_root}")


def compute_hashes(facts_dir: Path) -> dict[str, str]:
    sig = pd.read_parquet(facts_dir / "SIGNAL_EVENT.parquet")
    raw = pd.read_parquet(facts_dir / "RAW_PATTERN_EVENT.parquet")
    scan = pd.read_parquet(facts_dir / "SCAN_RUN_EVENT.parquet")
    orders = pd.read_parquet(facts_dir / "ORDER_INTENT.parquet")
    trades = pd.read_parquet(facts_dir / "TRADE_OUTCOME.parquet")
    return {
        "signal_key_sha256": stable_hash(sig, ["trade_date", "branch", "code", "signal_variant"]),
        "terminal_state_sha256": stable_hash(sig, ["trade_date", "branch", "code", "signal_variant", "terminal_state"]),
        "source_mode_sha256": source_mode_hash(raw),
        "raw_pattern_identity_sha256": stable_hash(raw, ["pattern_id", "prepared_signal_id", "source_mode", "scan_terminal_state"]),
        "scan_run_identity_sha256": stable_hash(scan, ["scan_run_id", "branch", "scan_status", "source_mode", "prepared_candidate_count", "raw_pattern_count"]),
        "order_lineage_sha256": stable_hash(orders, ["signal_id", "branch", "code", "side", "order_id", "order_status"]),
        "trade_lineage_sha256": stable_hash(trades, ["signal_id", "order_id", "entry_time", "entry_price", "entry_amount", "fill_status"]),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-fact-root", required=True)
    parser.add_argument("--output-fact-root", required=True)
    args = parser.parse_args()

    facts_src, observer_src = resolve_source(Path(args.source_fact_root))
    out_root = Path(args.output_fact_root).resolve()
    facts_out = out_root / "facts"
    observer_out = out_root / "observer"
    facts_out.mkdir(parents=True, exist_ok=True)
    observer_out.mkdir(parents=True, exist_ok=True)

    copied: list[dict[str, Any]] = []
    for src_dir, dst_dir in [(facts_src, facts_out), (observer_src, observer_out)]:
        for src in sorted(src_dir.iterdir()):
            if src.suffix.lower() not in {".parquet", ".csv"}:
                continue
            dst = dst_dir / src.name
            shutil.copy2(src, dst)
            copied.append(
                {
                    "relative_path": str(dst.relative_to(out_root)).replace("\\", "/"),
                    "source_absolute_path": str(src.resolve()),
                    "target_absolute_path": str(dst.resolve()),
                    "row_count": row_count(dst),
                    "size_bytes": dst.stat().st_size,
                    "sha256": sha_file(dst),
                }
            )

    hashes = compute_hashes(facts_out)
    canonical = json.loads((ACC / "CANONICAL_2023_BASELINE.json").read_text(encoding="utf-8"))
    required = [
        "signal_key_sha256",
        "terminal_state_sha256",
        "source_mode_sha256",
        "raw_pattern_identity_sha256",
        "scan_run_identity_sha256",
        "order_lineage_sha256",
        "trade_lineage_sha256",
    ]
    mismatches = {k: {"snapshot": hashes.get(k), "canonical": canonical.get(k)} for k in required if hashes.get(k) != canonical.get(k)}
    if mismatches:
        raise SystemExit(f"Snapshot hash mismatch: {json.dumps(mismatches, ensure_ascii=False, indent=2)}")

    observer_manifest = json.loads((ACC / "OBSERVER_V1_MANIFEST.json").read_text(encoding="utf-8"))
    manifest = {
        "snapshot_type": "MASTER_ACTUAL_PHASE2_INPUT",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_fact_root_absolute_path": str(Path(args.source_fact_root).resolve()),
        "resolved_source_facts_absolute_path": str(facts_src),
        "resolved_source_observer_absolute_path": str(observer_src),
        "target_absolute_path": str(out_root),
        "observer_contract_version": observer_manifest.get("observer_contract_version"),
        "canonical_2023_stable_business_hashes": hashes,
        "files": copied,
    }
    phase2_dir = out_root.parent
    phase2_dir.mkdir(parents=True, exist_ok=True)
    text = json.dumps(manifest, ensure_ascii=False, indent=2)
    (phase2_dir / "INPUT_SNAPSHOT_MANIFEST.json").write_text(text, encoding="utf-8")
    (out_root / "INPUT_SNAPSHOT_MANIFEST.json").write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
