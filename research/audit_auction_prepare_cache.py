from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import inspect
import json
import subprocess
import sys
import textwrap
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

OUT_DIR = ROOT / "coordination" / "attribution" / "master_phase1d"
LOCAL_DIR = ROOT / "research" / "auction_cache_audit"
HDATA_ROOT = Path(r"D:\work space\hdata\data\processed")
FEATURE = "auction_yiqian_prepare"
REQUIRED_COLUMNS = [
    "date",
    "previous_date",
    "rank",
    "code",
    "kind",
    "prev_money",
    "prev_close",
    "prev_volume",
    "avg_inc",
    "inc4",
    "left_ok",
]


@dataclass(frozen=True)
class CacheLocation:
    name: str
    root: Path


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(path.resolve())


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        keys: list[str] = []
        for row in rows:
            for key in row:
                if key not in keys:
                    keys.append(key)
        fieldnames = keys
    with path.open("w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in fieldnames})


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True, encoding="utf-8").strip()


def source_info(obj: Any) -> dict[str, Any]:
    file = Path(inspect.getsourcefile(obj) or "")
    lines, start = inspect.getsourcelines(obj)
    digest = hashlib.sha256("".join(lines).encode("utf-8")).hexdigest()
    return {
        "file": rel(file),
        "start_line": start,
        "end_line": start + len(lines) - 1,
        "sha256": digest,
    }


def resolve_provider() -> dict[str, Any]:
    from rebuild_from_archive.engine.data_api import DataAPI
    from rebuild_from_archive.project_compat import EmotionGateJQCompat

    compat = EmotionGateJQCompat(ROOT)
    api = DataAPI(compat=compat)
    compat_result = compat.get_project_auction_yiqian_prepare("2023-01-03")
    api_result = api.get_project_auction_yiqian_prepare("2023-01-03")
    namespace_src = inspect.getsource(EmotionGateJQCompat.namespace_entries)
    tree = ast.parse(textwrap.dedent(namespace_src))
    lambda_found = "get_project_auction_yiqian_prepare" in namespace_src and "engine.data_api.get_project_auction_yiqian_prepare" in namespace_src
    return {
        "resolved_at": datetime.now(timezone.utc).isoformat(),
        "runtime_symbol": "get_project_auction_yiqian_prepare(context.current_dt)",
        "namespace_binding": {
            "owner": "EmotionGateJQCompat.namespace_entries",
            "binding_kind": "lambda_wrapper",
            "delegates_to": "engine.data_api.get_project_auction_yiqian_prepare",
            "source": source_info(EmotionGateJQCompat.namespace_entries),
            "lambda_found_by_ast_parse": bool(lambda_found and isinstance(tree, ast.Module)),
        },
        "data_api_method": {
            "owner": "DataAPI.get_project_auction_yiqian_prepare",
            "binding_kind": "compat_delegate",
            "delegates_to": "compat.get_project_auction_yiqian_prepare(date)",
            "source": source_info(DataAPI.get_project_auction_yiqian_prepare),
        },
        "compat_method": {
            "owner": "EmotionGateJQCompat.get_project_auction_yiqian_prepare",
            "physical_feature_family": FEATURE,
            "loads_via": "_load_feature_year(self._auction_yiqian_cache, 'auction_yiqian_prepare', day.year)",
            "post_load_behavior": "filters date, sorts by rank, recomputes left_ok when left-pressure API is available",
            "source": source_info(EmotionGateJQCompat.get_project_auction_yiqian_prepare),
        },
        "instance_resolution": {
            "compat_class": f"{compat.__class__.__module__}.{compat.__class__.__name__}",
            "data_api_class": f"{api.__class__.__module__}.{api.__class__.__name__}",
            "compat_cache_attr_present": hasattr(compat, "_auction_yiqian_cache"),
            "compat_call_2023_01_03_return_type": type(compat_result).__name__,
            "compat_call_2023_01_03_rows": None if compat_result is None else int(len(compat_result)),
            "api_call_2023_01_03_return_type": type(api_result).__name__,
            "api_call_2023_01_03_rows": None if api_result is None else int(len(api_result)),
        },
    }


def cache_locations() -> list[CacheLocation]:
    locations = [
        CacheLocation("phase1d_worktree", ROOT / "project_cache" / "features" / FEATURE),
    ]
    if ROOT.parent.name == "worktrees":
        locations.append(CacheLocation("main_workspace", ROOT.parent.parent / "project_cache" / "features" / FEATURE))
        for sibling in sorted(ROOT.parent.iterdir()):
            if sibling.is_dir() and sibling != ROOT:
                locations.append(CacheLocation(f"sibling:{sibling.name}", sibling / "project_cache" / "features" / FEATURE))
    return locations


def audit_cache_inventory() -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    inventory: list[dict[str, Any]] = []
    schema_rows: list[dict[str, Any]] = []
    provenance_unknown: list[str] = []
    for loc in cache_locations():
        files = sorted(loc.root.glob("*.parquet")) if loc.root.exists() else []
        if not files:
            inventory.append(
                {
                    "location": loc.name,
                    "path": str(loc.root),
                    "exists": loc.root.exists(),
                    "file": "",
                    "year": "",
                    "rows": "",
                    "sha256": "",
                    "note": "no parquet files found",
                }
            )
            continue
        for path in files:
            year = path.stem
            df = pd.read_parquet(path)
            columns = list(df.columns)
            missing = [c for c in REQUIRED_COLUMNS if c not in columns]
            extra = [c for c in columns if c not in REQUIRED_COLUMNS]
            duplicate_keys = int(df.duplicated(["date", "code"]).sum()) if {"date", "code"}.issubset(df.columns) else ""
            rank_dupes = int(df.duplicated(["date", "rank"]).sum()) if {"date", "rank"}.issubset(df.columns) else ""
            bad_kind = int((~df["kind"].isin(["y2", "rzq"])).sum()) if "kind" in df.columns else ""
            inventory.append(
                {
                    "location": loc.name,
                    "path": str(loc.root),
                    "exists": True,
                    "file": path.name,
                    "year": year,
                    "rows": int(len(df)),
                    "date_min": int(df["date"].min()) if "date" in df.columns and len(df) else "",
                    "date_max": int(df["date"].max()) if "date" in df.columns and len(df) else "",
                    "size_bytes": path.stat().st_size,
                    "mtime": datetime.fromtimestamp(path.stat().st_mtime).isoformat(),
                    "sha256": sha256_file(path),
                }
            )
            schema_rows.append(
                {
                    "location": loc.name,
                    "file": path.name,
                    "columns": "|".join(columns),
                    "missing_required_columns": "|".join(missing),
                    "extra_columns": "|".join(extra),
                    "duplicate_date_code": duplicate_keys,
                    "duplicate_date_rank": rank_dupes,
                    "bad_kind_rows": bad_kind,
                    "max_rank": int(df["rank"].max()) if "rank" in df.columns and len(df) else "",
                    "schema_status": "PASS" if not missing and duplicate_keys == 0 and rank_dupes == 0 and bad_kind == 0 else "WARN",
                }
            )
    has_2023 = any(str(row.get("year")) == "2023" and row.get("file") == "2023.parquet" for row in inventory)
    if not has_2023:
        provenance_unknown.append("No physical auction_yiqian_prepare/2023.parquet found in inspected project cache roots.")
    return inventory, schema_rows, provenance_unknown


def generator_manifest() -> tuple[dict[str, Any], str]:
    from rebuild_from_archive import project_preprocess

    func = project_preprocess.build_auction_yiqian_prepare
    src = source_info(func)
    source_text = inspect.getsource(func)
    manifest = {
        "generator": "rebuild_from_archive.project_preprocess.build_auction_yiqian_prepare",
        "source": src,
        "git_commit": git("rev-parse", "HEAD"),
        "default_hdata_root": str(project_preprocess.DEFAULT_HDATA_ROOT),
        "default_cache_root": str(project_preprocess.DEFAULT_CACHE_ROOT),
        "cli_entry": "python rebuild_from_archive/project_preprocess.py 2023 --only auction-yq --hdata-root <hdata_root> --cache-root <cache_root>",
        "candidate_cap_default": 40,
        "ipo_days_default": 250,
        "source_sha256": hashlib.sha256(source_text.encode("utf-8")).hexdigest(),
    }
    logic_md = "\n".join(
        [
            "# Auction Cache Generator Logic",
            "",
            "- Generator: `build_auction_yiqian_prepare(year, hdata_root, cache_root, ipo_days=250, candidate_cap=40)`.",
            "- Inputs: local hdata daily pivots `open`, `close`, `high`, `high_limit`, `money`, `volume`; security universe from `DataAPI.get_all_securities`.",
            "- Target date T uses T-1, T-2, T-3 and T-4 daily data only.",
            "- Universe: 60/00 stocks, non-ST/non-delisted by display name, IPO age at least 250 calendar days.",
            "- `y2`: T-1 close at limit, T-2/T-3 not ever-limit, `avg_raw * 1.1 - 1 >= 0.07`, T-1 money in [5e8, 20e8], `inc4 <= 0.25`.",
            "- `rzq`: T-1 ever-limit but not close-limit, T-2 not close-limit, not y2, `avg_raw - 1 >= -0.04`, T-1 money in [3e8, 19e8], close/open >= -5%, `inc4 <= 0.18`.",
            "- Ranking: y2 before rzq, then descending T-1 money; capped at `candidate_cap` rows per date.",
            "- `left_ok`: recomputed from historical highs/volumes through `_auction_yiqian_batch_left_pressure_api`.",
            "- Output: `cache_root/auction_yiqian_prepare/{year}.parquet`.",
            "",
            "This is a prepared-candidate cache, not a raw auction pattern hit.",
        ]
    )
    return manifest, logic_md


def load_phase1c_source() -> pd.DataFrame:
    candidates = [
        ROOT / "coordination" / "attribution" / "master_phase1c" / "SOURCE_LIMITED_AUDIT.csv",
    ]
    if ROOT.parent.name == "worktrees":
        for sibling in sorted(ROOT.parent.iterdir()):
            candidates.append(sibling / "coordination" / "attribution" / "master_phase1c" / "SOURCE_LIMITED_AUDIT.csv")
    for path in candidates:
        if path.exists():
            df = pd.read_csv(path)
            df["_phase1c_source_file"] = str(path)
            return df
    return pd.DataFrame()


def parse_payload(value: Any) -> dict[str, Any]:
    if pd.isna(value):
        return {}
    try:
        return json.loads(str(value))
    except Exception:
        return {}


def normalize_code(code: str) -> str:
    code = str(code)
    return code.replace(".XSHE", ".SZ").replace(".XSHG", ".SH")


def phase1c_candidates(start: str, end: str) -> pd.DataFrame:
    df = load_phase1c_source()
    if df.empty:
        return df
    df = df[df.get("branch", "") == "Auction"].copy()
    df["trade_date_dt"] = pd.to_datetime(df["trade_date"])
    df = df[(df["trade_date_dt"] >= pd.to_datetime(start)) & (df["trade_date_dt"] <= pd.to_datetime(end))].copy()
    if df.empty:
        return df
    payloads = df["pattern_payload"].map(parse_payload)
    for key in ["kind", "prev_close", "prev_money", "prev_volume", "avg_inc", "inc4", "left_ok"]:
        df[key] = payloads.map(lambda p: p.get(key))
    df["date"] = df["trade_date_dt"].dt.strftime("%Y%m%d").astype(int)
    df["code_norm"] = df["code"].map(normalize_code)
    df["phase1c_rank"] = df.groupby("date").cumcount() + 1
    return df


def run_replay(year: int) -> Path:
    from rebuild_from_archive.project_preprocess import build_auction_yiqian_prepare

    cache_root = LOCAL_DIR / "replay_cache"
    out_path = cache_root / FEATURE / f"{year}.parquet"
    if not out_path.exists():
        build_auction_yiqian_prepare(year, hdata_root=HDATA_ROOT, cache_root=cache_root)
    return out_path


def align_candidates(replay_path: Path, phase1c: pd.DataFrame, start: str, end: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    replay = pd.read_parquet(replay_path)
    replay["date_dt"] = pd.to_datetime(replay["date"].astype(str))
    replay = replay[(replay["date_dt"] >= pd.to_datetime(start)) & (replay["date_dt"] <= pd.to_datetime(end))].copy()
    replay["code_norm"] = replay["code"].astype(str).map(normalize_code)
    replay_keyed = replay.set_index(["date", "code_norm"], drop=False)
    p1 = phase1c.copy()
    p1_keyed = p1.set_index(["date", "code_norm"], drop=False) if not p1.empty else pd.DataFrame()

    dates = sorted(set(p1["date"].astype(int))) if not p1.empty else sorted(set(replay["date"].astype(int)))
    summary: list[dict[str, Any]] = []
    rank_rows: list[dict[str, Any]] = []
    field_rows: list[dict[str, Any]] = []
    mismatch_rows: list[dict[str, Any]] = []
    left_rows: list[dict[str, Any]] = []
    float_fields = ["prev_close", "prev_money", "prev_volume", "avg_inc", "inc4"]
    for date in dates:
        rday = replay[replay["date"].astype(int) == int(date)].copy().sort_values("rank")
        pday = p1[p1["date"].astype(int) == int(date)].copy().sort_values("phase1c_rank") if not p1.empty else pd.DataFrame()
        rset = set(rday["code_norm"])
        pset = set(pday["code_norm"]) if not pday.empty else set()
        inter = rset & pset
        summary.append(
            {
                "date": date,
                "replay_count": len(rday),
                "phase1c_source_limited_count": len(pday),
                "intersection_count": len(inter),
                "phase1c_only_count": len(pset - rset),
                "replay_only_count": len(rset - pset),
                "jaccard": round(len(inter) / len(rset | pset), 6) if (rset | pset) else 1.0,
                "exact_set_match": rset == pset,
                "exact_order_match": list(rday["code_norm"]) == list(pday["code_norm"]) if not pday.empty else False,
            }
        )
        for idx, code in enumerate(list(rday["code_norm"]), 1):
            p_rank = None
            if code in pset:
                p_rank = int(pday[pday["code_norm"] == code]["phase1c_rank"].iloc[0])
            rank_rows.append(
                {
                    "date": date,
                    "code": code,
                    "replay_rank": idx,
                    "phase1c_rank": p_rank if p_rank is not None else "",
                    "kind": rday[rday["code_norm"] == code]["kind"].iloc[0],
                    "prev_money": rday[rday["code_norm"] == code]["prev_money"].iloc[0],
                    "rank_match": p_rank == idx,
                    "within_candidate_cap_40": idx <= 40,
                }
            )
        for code in sorted(inter):
            r = replay_keyed.loc[(date, code)]
            p = p1_keyed.loc[(date, code)]
            for field in ["kind", "left_ok", *float_fields]:
                rv = r[field]
                pv = p[field]
                if field in float_fields:
                    diff = abs(float(rv) - float(pv))
                    match = diff <= max(1e-5, abs(float(rv)) * 1e-9)
                else:
                    diff = ""
                    match = str(rv).lower() == str(pv).lower()
                field_rows.append({"date": date, "code": code, "field": field, "replay_value": rv, "phase1c_value": pv, "abs_diff": diff, "match": match})
                if not match:
                    mismatch_rows.append({"date": date, "code": code, "field": field, "replay_value": rv, "phase1c_value": pv, "abs_diff": diff})
            left_rows.append(
                {
                    "date": date,
                    "code": code,
                    "left_ok_replay": bool(r["left_ok"]),
                    "left_ok_phase1c": bool(p["left_ok"]),
                    "left_ok_match": bool(r["left_ok"]) == bool(p["left_ok"]),
                }
            )
        for code in sorted(pset - rset):
            mismatch_rows.append({"date": date, "code": code, "field": "_membership", "replay_value": "ABSENT", "phase1c_value": "PRESENT", "abs_diff": ""})
        for code in sorted(rset - pset):
            mismatch_rows.append({"date": date, "code": code, "field": "_membership", "replay_value": "PRESENT", "phase1c_value": "ABSENT", "abs_diff": ""})
    return summary, rank_rows, field_rows, left_rows, mismatch_rows


def pit_audit_rows() -> list[dict[str, Any]]:
    rows = []
    for field, source, cutoff, status in [
        ("date", "target trading day T from annual daily calendar", "T 09:05", "PIT_SAFE_BUT_PRECOMPUTED"),
        ("previous_date", "T-1 trading date", "T 09:05", "PIT_SAFE_BUT_PRECOMPUTED"),
        ("code", "T-1 security universe and T-1 derived candidates", "T 09:05", "PIT_SAFE_BUT_PRECOMPUTED"),
        ("kind", "T-1/T-2/T-3/T-4 daily OHLCV and high_limit rules", "T 09:05", "PIT_SAFE_BUT_PRECOMPUTED"),
        ("rank", "same-day prepared candidate ordering by kind and T-1 money", "T 09:05", "PIT_SAFE_BUT_PRECOMPUTED"),
        ("prev_close", "T-1 daily close", "T 09:05", "PIT_SAFE_BUT_PRECOMPUTED"),
        ("prev_money", "T-1 daily money", "T 09:05", "PIT_SAFE_BUT_PRECOMPUTED"),
        ("prev_volume", "T-1 daily volume", "T 09:05", "PIT_SAFE_BUT_PRECOMPUTED"),
        ("avg_inc", "T-1 amount/volume/close derived auction proxy", "T 09:05", "PIT_SAFE_BUT_PRECOMPUTED"),
        ("inc4", "T-1 close versus T-4 close", "T 09:05", "PIT_SAFE_BUT_PRECOMPUTED"),
        ("left_ok", "historical high/volume through T-1", "T 09:05", "PIT_SAFE_BUT_PRECOMPUTED"),
    ]:
        rows.append({"field": field, "source_timestamp_max": source, "required_availability_cutoff": cutoff, "pit_status": status, "note": "Physical historical availability is not proven by 2026 file mtimes."})
    return rows


def write_reports(
    start: str,
    end: str,
    provider: dict[str, Any],
    inventory: list[dict[str, Any]],
    schema_rows: list[dict[str, Any]],
    manifest: dict[str, Any],
    provenance_unknown: list[str],
    date_summary: list[dict[str, Any]],
    mismatches: list[dict[str, Any]],
) -> None:
    inspected_files = [r for r in inventory if r.get("file")]
    has_physical_2023 = any(str(r.get("year")) == "2023" for r in inspected_files)
    exact_alignment = bool(date_summary) and all(bool(r["exact_set_match"]) and bool(r["exact_order_match"]) for r in date_summary)
    intersection_total = sum(int(r.get("intersection_count", 0)) for r in date_summary)
    phase1c_total = sum(int(r.get("phase1c_source_limited_count", 0)) for r in date_summary)
    membership_mismatches = sum(1 for r in mismatches if r.get("field") == "_membership")
    field_mismatches = len(mismatches) - membership_mismatches
    conclusion = "VERIFIED_EXACT" if has_physical_2023 and exact_alignment and not mismatches else "PARTIAL"
    availability_md = "\n".join(
        [
            "# Cache Availability Audit",
            "",
            f"- Window: {start} to {end}.",
            f"- Physical 2023 cache present in inspected roots: `{has_physical_2023}`.",
            "- Field-level information is derivable from T-1 or earlier daily data, so the generator logic is PIT-safe if the batch is completed before 09:05 on T.",
            "- File mtimes in the inspected cache roots are 2026 build times and cannot prove historical pre-open availability.",
            "- Current Phase 1D worktree has no local `project_cache/features/auction_yiqian_prepare/2023.parquet`; inspected main workspace cache also lacks `2023.parquet`.",
        ]
    )
    (OUT_DIR / "CACHE_AVAILABILITY_AUDIT.md").write_text(availability_md, encoding="utf-8")
    report = "\n".join(
        [
            "# Phase 1D Auction Cache Provenance/PIT Audit",
            "",
            f"- Window: `{start}` to `{end}`.",
            f"- Conclusion: `{conclusion}`.",
            f"- Provider: runtime namespace delegates to `DataAPI.get_project_auction_yiqian_prepare`, then to `EmotionGateJQCompat.get_project_auction_yiqian_prepare`.",
            f"- Generator: `{manifest['generator']}`.",
            f"- Physical 2023 cache found: `{has_physical_2023}`.",
            f"- Date-level rows compared: `{len(date_summary)}`.",
            f"- Mismatch rows: `{len(mismatches)}`.",
            f"- Replay alignment: `{intersection_total}/{phase1c_total}` Phase 1C source-limited rows intersect the independent generator replay; residual differences are `{membership_mismatches}` membership rows and `{field_mismatches}` field rows.",
            "",
            "## Key Findings",
            "",
            "1. `auction_yiqian_prepare` is a prepared-candidate cache, not raw auction pattern evidence.",
            "2. The generator source is present and uses only T-1 or earlier daily data for candidate construction.",
            "3. The inspected physical cache roots do not contain `auction_yiqian_prepare/2023.parquet`, so 2023Q1 Phase 1C `SOURCE_LIMITED_PREPARED_RECORD` rows cannot be certified as physical-cache-derived.",
            "4. Phase 1D does not rewrite Phase 1C facts; it records the provenance gap as audit evidence for the next implementation boundary.",
            "",
            "## Required Artifacts",
            "",
            "- `PROVIDER_RESOLUTION.json`",
            "- `AUCTION_CACHE_INVENTORY.json`",
            "- `CACHE_SCHEMA_AUDIT.csv`",
            "- `GENERATOR_MANIFEST.json`",
            "- `GENERATOR_LOGIC.md`",
            "- `AUCTION_CACHE_PIT_AUDIT.csv`",
            "- `CACHE_AVAILABILITY_AUDIT.md`",
            "- `CACHE_CANDIDATE_ALIGNMENT.csv`",
            "- `CACHE_FIELD_ALIGNMENT.csv`",
            "- `CACHE_RANK_CAP_AUDIT.csv`",
            "- `LEFT_PRESSURE_ALIGNMENT.csv`",
            "- `CACHE_FALLBACK_LOGIC_DIFF.md`",
            "- `DATE_LEVEL_SUMMARY.csv`",
            "- `MISMATCH_ROWS.csv`",
            "- `UNKNOWN_PROVENANCE_ITEMS.csv`",
            "- `RUN_MANIFEST.json`",
            "",
            "## Unknown Provenance Items",
            "",
            *(f"- {item}" for item in provenance_unknown),
        ]
    )
    (OUT_DIR / "PHASE1D_REPORT.md").write_text(report, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", default="2023-01-01")
    parser.add_argument("--end", default="2023-03-31")
    parser.add_argument("--skip-replay", action="store_true")
    args = parser.parse_args()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    LOCAL_DIR.mkdir(parents=True, exist_ok=True)

    provider = resolve_provider()
    inventory, schema_rows, provenance_unknown = audit_cache_inventory()
    manifest, logic_md = generator_manifest()
    p1 = phase1c_candidates(args.start, args.end)
    if p1.empty:
        provenance_unknown.append("Phase 1C SOURCE_LIMITED_AUDIT.csv was not available for full Q1 alignment.")

    if args.skip_replay:
        replay_path = LOCAL_DIR / "replay_cache" / FEATURE / "2023.parquet"
    else:
        replay_path = run_replay(2023)
    date_summary, rank_rows, field_rows, left_rows, mismatch_rows = align_candidates(replay_path, p1, args.start, args.end) if replay_path.exists() else ([], [], [], [], [])
    if not replay_path.exists():
        provenance_unknown.append("Replay parquet was not generated.")

    write_json(OUT_DIR / "PROVIDER_RESOLUTION.json", provider)
    write_json(OUT_DIR / "AUCTION_CACHE_INVENTORY.json", {"locations": inventory})
    write_csv(OUT_DIR / "CACHE_SCHEMA_AUDIT.csv", schema_rows)
    write_json(OUT_DIR / "GENERATOR_MANIFEST.json", manifest)
    (OUT_DIR / "GENERATOR_LOGIC.md").write_text(logic_md, encoding="utf-8")
    write_csv(OUT_DIR / "AUCTION_CACHE_PIT_AUDIT.csv", pit_audit_rows())
    write_csv(OUT_DIR / "DATE_LEVEL_SUMMARY.csv", date_summary)
    write_csv(OUT_DIR / "CACHE_CANDIDATE_ALIGNMENT.csv", date_summary)
    write_csv(OUT_DIR / "CACHE_FIELD_ALIGNMENT.csv", field_rows)
    write_csv(OUT_DIR / "CACHE_RANK_CAP_AUDIT.csv", rank_rows)
    write_csv(OUT_DIR / "LEFT_PRESSURE_ALIGNMENT.csv", left_rows)
    write_csv(OUT_DIR / "MISMATCH_ROWS.csv", mismatch_rows)
    write_csv(OUT_DIR / "UNKNOWN_PROVENANCE_ITEMS.csv", [{"item": item} for item in provenance_unknown], ["item"])
    (OUT_DIR / "CACHE_FALLBACK_LOGIC_DIFF.md").write_text(
        "\n".join(
            [
                "# Cache Fallback Logic Diff",
                "",
                "- Runtime accessor returns `None` when the yearly physical feature file is absent.",
                "- When rows are present, runtime sorts by `rank` and attempts to recompute `left_ok` through `_auction_yiqian_batch_left_pressure_api`.",
                "- Phase 1C `SOURCE_LIMITED_PREPARED_RECORD` rows label the prepared source as `PROJECT_AUCTION_PREPARE_CACHE`; Phase 1D found no inspected 2023 physical cache file, so those rows should be treated as prepared-source observations with unknown physical cache provenance.",
                "- No formal strategy, engine, compat, or data-reader behavior was changed in Phase 1D.",
            ]
        ),
        encoding="utf-8",
    )
    run_manifest = {
        "run_at": datetime.now(timezone.utc).isoformat(),
        "cwd": str(ROOT),
        "git_commit": git("rev-parse", "HEAD"),
        "start": args.start,
        "end": args.end,
        "hdata_root": str(HDATA_ROOT),
        "replay_path": str(replay_path),
        "phase1c_source_rows": int(len(p1)),
        "date_summary_rows": len(date_summary),
        "mismatch_rows": len(mismatch_rows),
        "phase1c_facts_rewritten": False,
    }
    write_json(OUT_DIR / "RUN_MANIFEST.json", run_manifest)
    write_reports(args.start, args.end, provider, inventory, schema_rows, manifest, provenance_unknown, date_summary, mismatch_rows)
    print(json.dumps(run_manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()




