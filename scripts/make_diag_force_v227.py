"""Generate a JoinQuant DIAG script for the forced v227 branch.

The existing `母版-20260506-Clone-DIAG.py` is based on the normal-route mother
strategy. It is useful for route research, but it is not the same run mode as
the copied `force_v227` transaction history. This generator uses the forced
single-branch source and pins `g.branch_test = 'v227'` before appending the
same DIAG hooks.
"""

from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "母版-20260506-Clone-强制单分支回测.py"
DST = ROOT / "母版-20260506-Clone-force-v227-DIAG.py"
INJECT_AFTER_LINE_CONTAINS = "from jqdata import *"

sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_diag_master import DIAG_PATCH  # noqa: E402


LOUD_DIAG_PATCH = DIAG_PATCH.replace(
    "def _dlog(msg):\n"
    "    \"\"\"DIAG 行用 log.warning 输出，避免被 set_level('xxx','warning') 关掉。\"\"\"\n"
    "    log.warning(msg)\n",
    "def _dlog(msg):\n"
    "    \"\"\"DIAG 行用普通 info 输出。响亮版不静默日志，优先保证可见。\"\"\"\n"
    "    log.info(msg)\n",
)
LOUD_DIAG_PATCH = LOUD_DIAG_PATCH.replace("DIAG_START = '2022-06-01'", "DIAG_START = '2022-01-01'")
LOUD_DIAG_PATCH = LOUD_DIAG_PATCH.replace("DIAG_END   = '2022-08-31'", "DIAG_END   = '2022-12-31'")
LOUD_DIAG_PATCH = LOUD_DIAG_PATCH.replace(
    "_orig_prepare_all = prepare_all\n"
    "def prepare_all(context):\n"
    "    _install_diag_log_filter()  # 兜底：确保 monkey-patch 已生效（幂等）\n"
    "    _orig_prepare_all(context)\n"
    "    _diag_state(context)\n",
    "_orig_prepare_all = prepare_all\n"
    "def prepare_all(context):\n"
    "    _orig_prepare_all(context)\n"
    "    _diag_state(context)\n",
)

SMOKE_PATCH = r"""
# ===== force-v227 DIAG smoke hooks =====
try:
    _orig_initialize_for_diag = initialize
    def initialize(context):
        _orig_initialize_for_diag(context)
        log.info('[DIAG-BOOT] initialize reached')
except Exception as _e:
    pass

try:
    _orig_prepare_for_diag_smoke = prepare_all
    def prepare_all(context):
        log.info('[DIAG-BOOT] prepare_all entered')
        _orig_prepare_for_diag_smoke(context)
except Exception as _e:
    pass
# ===== end smoke hooks =====
"""


def main() -> None:
    src_text = SRC.read_text(encoding="utf-8")
    if "g.branch_test = 'normal'" not in src_text:
        raise SystemExit("Cannot find expected g.branch_test = 'normal' marker")

    src_text = src_text.replace("g.branch_test = 'normal'", "g.branch_test = 'v227'", 1)
    src_lines = src_text.split("\n")

    out_lines: list[str] = []
    injected = False
    for line in src_lines:
        out_lines.append(line)
        if (not injected) and INJECT_AFTER_LINE_CONTAINS in line:
            out_lines.append("# DIAG loud mode: no log.set_level monkey patch.\n")
            injected = True

    out_lines.append(LOUD_DIAG_PATCH)
    out_lines.append(SMOKE_PATCH)
    DST.write_text("\n".join(out_lines), encoding="utf-8")
    print(f"写入 {DST}")
    print(f"原文件 {len(src_lines)} 行 -> 副本 {len(out_lines)} 行")
    print(f"branch_test: v227")
    print(f"loud DIAG 注入: {injected}")


if __name__ == "__main__":
    main()
