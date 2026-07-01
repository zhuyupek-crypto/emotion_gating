"""Static inventory helper for motherboard attribution Phase 0.

This script only reads files, computes hashes, and extracts simple static
metadata. It must not import or execute strategy modules.
"""

from __future__ import annotations

import ast
import hashlib
import json
import re
import subprocess
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "coordination" / "attribution" / "master_phase1"

EXTERNAL_HDATA_READER = Path(r"D:\work space\hdata\scripts\core\hdata_reader.py")

CORE_FILES = [
    "母版-20260506-Clone.py",
    "母版-一进二纯版.py",
    "母版-20260506-Clone-分支净化回测.py",
    "codex_strategy_dissection/branch_strategies/mother_branch_force_v227.py",
    "codex_strategy_dissection/branch_strategies/mother_branch_force_rzq.py",
    "codex_strategy_dissection/branch_strategies/mother_branch_force_zb.py",
    "codex_strategy_dissection/branch_strategies/mother_branch_force_rzq_zb.py",
    "codex_strategy_dissection/branch_strategies/mother_branch_force_auction.py",
    "scorp_optimize/strategies/strategy_v227_scorp.py",
    "rebuild_from_archive/engine/core.py",
    "rebuild_from_archive/engine/context.py",
    "rebuild_from_archive/engine/order.py",
    "rebuild_from_archive/engine/data_api.py",
    "rebuild_from_archive/project_compat.py",
    "rebuild_from_archive/jqdata_compat.py",
    "rebuild_from_archive/compat/call_auction.py",
    "rebuild_from_archive/compat/market_data.py",
    "rebuild_from_archive/compat/security_metadata.py",
    "coordination/local_native_l2/runs/FINAL_ACCEPTANCE_REPORT.json",
    "coordination/optimization/motherboard_performance/REPORT.md",
    "codex_strategy_dissection/naked_branch_backtest_findings.md",
]


def git(*args: str) -> str | None:
    try:
        return subprocess.check_output(
            ["git", *args], cwd=ROOT, text=True, encoding="utf-8", errors="replace"
        ).strip()
    except Exception:
        return None


def sha256_file(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def line_count(path: Path) -> int | None:
    if not path.exists() or not path.is_file():
        return None
    with path.open("rb") as f:
        return sum(1 for _ in f)


def rel_or_abs(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(path.resolve())


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def extract_functions(path: Path) -> list[dict]:
    if not path.exists() or path.suffix != ".py":
        return []
    try:
        tree = ast.parse(read_text(path), filename=str(path))
    except SyntaxError:
        return []
    funcs = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            funcs.append(
                {
                    "name": node.name,
                    "lineno": node.lineno,
                    "end_lineno": getattr(node, "end_lineno", None),
                }
            )
    return sorted(funcs, key=lambda x: (x["lineno"], x["name"]))


def extract_run_daily(path: Path) -> list[dict]:
    if not path.exists():
        return []
    out = []
    pattern = re.compile(r"run_daily\(([^,\)]+),\s*['\"]([^'\"]+)['\"]\)")
    for lineno, line in enumerate(read_text(path).splitlines(), start=1):
        m = pattern.search(line)
        if m:
            out.append(
                {
                    "lineno": lineno,
                    "handler": m.group(1).strip(),
                    "time": m.group(2).strip(),
                    "line": line.strip(),
                }
            )
    return out


def extract_g_assignments(path: Path) -> list[dict]:
    if not path.exists():
        return []
    out = []
    pattern = re.compile(r"\bg\.([A-Za-z_][A-Za-z0-9_]*)\s*=")
    for lineno, line in enumerate(read_text(path).splitlines(), start=1):
        m = pattern.search(line)
        if m:
            out.append({"name": m.group(1), "lineno": lineno, "line": line.strip()})
    return out


def file_record(path: Path) -> dict:
    exists = path.exists()
    return {
        "path": rel_or_abs(path),
        "absolute_path": str(path.resolve()),
        "exists": exists,
        "size_bytes": path.stat().st_size if exists and path.is_file() else None,
        "line_count": line_count(path),
        "sha256": sha256_file(path),
        "git_status": git("status", "--short", "--", rel_or_abs(path)) if path.is_relative_to(ROOT) else "external",
    }


def branch_entry(name: str, path: Path, status: str, notes: list[str]) -> dict:
    return {
        "path": rel_or_abs(path),
        "commit": git("rev-parse", "HEAD"),
        "sha256": sha256_file(path),
        "purity_status": status,
        "baseline_period": None,
        "baseline_artifacts": [],
        "functions": [f["name"] for f in extract_functions(path)],
        "notes": notes,
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    paths = [ROOT / p for p in CORE_FILES]
    paths.append(EXTERNAL_HDATA_READER)
    file_hashes = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "root": str(ROOT),
        "git_head": git("rev-parse", "HEAD"),
        "git_branch": git("branch", "--show-current"),
        "files": [file_record(p) for p in paths],
    }

    motherboard = ROOT / "母版-20260506-Clone.py"
    manifest = {
        "generated_at": file_hashes["generated_at"],
        "root": str(ROOT),
        "motherboard": {
            "path": rel_or_abs(motherboard),
            "commit": git("rev-parse", "HEAD"),
            "sha256": sha256_file(motherboard),
            "baseline_tag": "motherboard-performance-baseline-v1",
            "baseline_artifacts": [
                "coordination/local_native_l2/runs/FINAL_ACCEPTANCE_REPORT.json",
                "coordination/optimization/motherboard_performance/REPORT.md",
            ],
            "functions": [f["name"] for f in extract_functions(motherboard)],
            "run_daily": extract_run_daily(motherboard),
            "g_assignments": extract_g_assignments(motherboard),
        },
        "branches": {
            "YJJ": branch_entry(
                "YJJ",
                ROOT / "codex_strategy_dissection/branch_strategies/mother_branch_force_v227.py",
                "PURE_UNCERTAIN",
                ["force_v227 contains both YJJ and Scorpion; YJJ is not proven pure."],
            ),
            "Scorpion": branch_entry(
                "Scorpion",
                ROOT / "scorp_optimize/strategies/strategy_v227_scorp.py",
                "PURE_PASS",
                ["Dedicated Scorpion research strategy exists; previous notes cite formal pure-bear consistency checks."],
            ),
            "RZQ": branch_entry(
                "RZQ",
                ROOT / "codex_strategy_dissection/branch_strategies/mother_branch_force_rzq.py",
                "NOT_AUDITED",
                ["force_rzq copy exists, but Phase 0 found no formal purity evidence."],
            ),
            "ZB": branch_entry(
                "ZB",
                ROOT / "codex_strategy_dissection/branch_strategies/mother_branch_force_zb.py",
                "NOT_AUDITED",
                ["force_zb copy exists, but Phase 0 found no formal purity evidence."],
            ),
            "Auction": branch_entry(
                "Auction",
                ROOT / "codex_strategy_dissection/branch_strategies/mother_branch_force_auction.py",
                "NOT_AUDITED",
                ["force_auction copy exists; auction data timing and purity remain unaudited."],
            ),
        },
        "engine": {
            "core": file_record(ROOT / "rebuild_from_archive/engine/core.py"),
            "context": file_record(ROOT / "rebuild_from_archive/engine/context.py"),
            "order": file_record(ROOT / "rebuild_from_archive/engine/order.py"),
            "data_api": file_record(ROOT / "rebuild_from_archive/engine/data_api.py"),
            "project_compat": file_record(ROOT / "rebuild_from_archive/project_compat.py"),
            "jqdata_compat": file_record(ROOT / "rebuild_from_archive/jqdata_compat.py"),
        },
        "data_readers": {
            "hdata_reader": file_record(EXTERNAL_HDATA_READER),
        },
    }

    static = {
        "motherboard_functions": extract_functions(motherboard),
        "motherboard_run_daily": extract_run_daily(motherboard),
        "motherboard_g_assignments": extract_g_assignments(motherboard),
        "engine_core_functions": extract_functions(ROOT / "rebuild_from_archive/engine/core.py"),
        "order_functions": extract_functions(ROOT / "rebuild_from_archive/engine/order.py"),
        "context_functions": extract_functions(ROOT / "rebuild_from_archive/engine/context.py"),
    }

    (OUT_DIR / "FILE_HASHES.json").write_text(
        json.dumps(file_hashes, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (OUT_DIR / "BRANCH_BASELINE_MANIFEST.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (OUT_DIR / "STATIC_INVENTORY.json").write_text(
        json.dumps(static, ensure_ascii=False, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
