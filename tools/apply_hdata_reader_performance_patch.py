"""Apply (or check) the hdata_reader performance optimization patch.

The actual performance code lives in the external HDATA directory
(default: D:\\work space\\hdata), which is NOT a git repository. This tool
version-fixates that change inside the emotion_gating repo by:

1. Locating the HDATA root via LOCALQUANT_HDATA_ROOT env var (default
   D:\\work space\\hdata).
2. Reading the baseline / optimized / patch SHA256 from
   coordination/optimization/motherboard_performance/HDATA_READER_VERSION.json.
3. Computing the current SHA256 of scripts/core/hdata_reader.py.
4. Deciding what to do:
   - current == optimized  -> already applied, exit 0
   - current == baseline   -> apply the patch, then verify optimized SHA
   - otherwise             -> REFUSE to modify, report conflict (exit 2)
5. After applying, recompute SHA256; it MUST equal optimized_sha256.

Usage:
    python tools/apply_hdata_reader_performance_patch.py           # apply
    python tools/apply_hdata_reader_performance_patch.py --check     # check only

Exit codes:
    0  OK (already applied, or successfully applied, or check passes)
    1  Error (patch file missing / unreadable, git apply failed, etc.)
    2  Conflict (current SHA matches neither baseline nor optimized)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parents[1]
VERSION_JSON = (
    REPO_ROOT
    / "coordination"
    / "optimization"
    / "motherboard_performance"
    / "HDATA_READER_VERSION.json"
)


def _default_hdata_root() -> Path:
    env = os.environ.get("LOCALQUANT_HDATA_ROOT")
    if env:
        return Path(env)
    return Path(r"D:\work space\hdata")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def load_version_info() -> dict:
    if not VERSION_JSON.exists():
        print(f"ERROR: version info not found: {VERSION_JSON}", file=sys.stderr)
        sys.exit(1)
    info = json.loads(VERSION_JSON.read_text(encoding="utf-8"))
    for key in ("relative_path", "baseline_sha256", "optimized_sha256",
                "patch_sha256", "patch_file"):
        if key not in info:
            print(f"ERROR: version info missing key {key!r}: {VERSION_JSON}",
                  file=sys.stderr)
            sys.exit(1)
    return info


def locate_patch_file(info: dict) -> Path:
    # patch_file is relative to repo root
    patch_path = REPO_ROOT / info["patch_file"]
    if not patch_path.exists():
        print(f"ERROR: patch file not found: {patch_path}", file=sys.stderr)
        sys.exit(1)
    return patch_path


def verify_patch_sha(patch_path: Path, expected_sha: str) -> None:
    actual = sha256_file(patch_path)
    if actual != expected_sha:
        print(
            f"ERROR: patch SHA256 mismatch.\n"
            f"  expected: {expected_sha}\n"
            f"  actual:   {actual}\n"
            f"  patch:    {patch_path}",
            file=sys.stderr,
        )
        sys.exit(1)


def apply_patch(patch_path: Path, hdata_root: Path, rel_path: str) -> None:
    """Apply the unified diff patch using git apply --no-index -p1.

    git apply --no-index works outside a git repository. -p1 strips
    the a/ / b/ prefix from the patch paths. The working directory is
    set to hdata_root so the relative path resolves correctly.
    """
    cmd = [
        "git", "apply", "--no-index", "-p1",
        str(patch_path),
    ]
    try:
        result = subprocess.run(
            cmd,
            cwd=str(hdata_root),
            capture_output=True,
            text=True,
            timeout=60,
        )
    except FileNotFoundError:
        print("ERROR: git command not found. Install git or apply the patch "
              "manually with: patch -p1 < " + str(patch_path), file=sys.stderr)
        sys.exit(1)
    except subprocess.TimeoutExpired:
        print("ERROR: git apply timed out", file=sys.stderr)
        sys.exit(1)

    # git writes verbose/progress to stderr even on success
    if result.returncode != 0:
        print(
            f"ERROR: git apply failed (exit {result.returncode}).\n"
            f"  stdout: {result.stdout}\n"
            f"  stderr: {result.stderr}",
            file=sys.stderr,
        )
        sys.exit(1)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Apply or check the hdata_reader performance patch."
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Only check the current state; do not modify the file.",
    )
    parser.add_argument(
        "--hdata-root",
        type=str,
        default=None,
        help="Override HDATA root directory (default: $LOCALQUANT_HDATA_ROOT "
             "or D:\\work space\\hdata).",
    )
    args = parser.parse_args()

    hdata_root = Path(args.hdata_root) if args.hdata_root else _default_hdata_root()
    if not hdata_root.exists():
        print(f"ERROR: HDATA root does not exist: {hdata_root}", file=sys.stderr)
        return 1

    info = load_version_info()
    rel_path = info["relative_path"]
    target = hdata_root / rel_path
    if not target.exists():
        print(f"ERROR: target file not found: {target}", file=sys.stderr)
        return 1

    baseline_sha = info["baseline_sha256"]
    optimized_sha = info["optimized_sha256"]
    patch_sha = info["patch_sha256"]

    # Verify patch file integrity
    patch_path = locate_patch_file(info)
    verify_patch_sha(patch_path, patch_sha)

    # Compute current file SHA256
    current_sha = sha256_file(target)

    print(f"HDATA root:          {hdata_root}")
    print(f"Target file:         {target}")
    print(f"baseline_sha256:     {baseline_sha}")
    print(f"optimized_sha256:    {optimized_sha}")
    print(f"current_sha256:      {current_sha}")
    print(f"patch_sha256:        {patch_sha}  (verified)")
    print()

    if current_sha == optimized_sha:
        print("STATUS: already applied (current == optimized)")
        print("No action needed.")
        return 0

    if current_sha == baseline_sha:
        print("STATUS: at baseline (current == baseline)")
        if args.check:
            print("--check mode: not applying. Patch is ready to apply.")
            return 0
        print("Applying patch ...")
        apply_patch(patch_path, hdata_root, rel_path)
        # Verify result
        new_sha = sha256_file(target)
        print(f"post-apply_sha256:   {new_sha}")
        if new_sha != optimized_sha:
            print(
                f"ERROR: post-apply SHA256 does not match optimized!\n"
                f"  expected: {optimized_sha}\n"
                f"  actual:   {new_sha}",
                file=sys.stderr,
            )
            return 1
        print("STATUS: successfully applied (current == optimized)")
        return 0

    # Neither baseline nor optimized
    print(
        "CONFLICT: current SHA256 matches neither baseline nor optimized.\n"
        "  The file has been modified in an unexpected way. Refusing to apply.\n"
        "  To resolve: restore the original baseline hdata_reader.py, then re-run.",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
