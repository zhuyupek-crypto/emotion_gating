# Versioning And Project Boundaries

This repository is for the workspace copy only. Do not edit or commit files from:

- `D:\work space\local_quant`
- `D:\work space\hdata`

## Layers

### Backtest Engine / JQ Compatibility Layer

Current location:

- `rebuild_from_archive/engine/`
- `rebuild_from_archive/jqdata_compat.py`
- `rebuild_from_archive/project_preprocess.py`

This layer contains local JoinQuant compatibility behavior, hdata adapters, execution semantics, and documented JQ anomaly handling. Treat it as a baseline layer. Future work may split it into a separate repository/package.

### Application / Strategy Layer

Current key files:

- `母版-20260506-Clone.py`
- `母版-20260506-原始版.py`
- `run_rebuild_*.py`
- `compare_*.py`
- strategy analysis helpers such as `codex_strategy_dissection/`

Strategy optimization, branch naked runs, and parameter analysis should happen in new analysis copies or directories. Avoid changing the baseline strategy and engine together unless the change is explicitly part of JQ parity work.

## Baseline Notes

- `母版-20260506-原始版.py` is the preserved original strategy copy. Do not modify it for optimization work.
- `母版-20260506-Clone.py` is the current workspace clone used by the local rebuild harness.
- `alignment_open_issues.md` records JQ compatibility findings and should be updated when compatibility behavior changes.

## Git Practice

- Do not use `git add .` in this repository; many generated result files are intentionally ignored.
- Commit engine compatibility changes separately from strategy/application changes.
- Commit analysis outputs only when they are concise reports. Large run directories, CSV outputs, caches, and archives should remain untracked.
