# Framework Separation Notes

## Boundary

- `rebuild_from_archive/engine/` is the local JoinQuant-like execution framework.
  It should expose generic backtest APIs (`get_price`, `order_value`,
  `get_all_securities`, `get_extras`, etc.) and must not know emotion-gate
  project cache paths or strategy-specific observed exceptions.
- `rebuild_from_archive/project_compat.py` is the emotion-gate compatibility
  profile.  It contains archived JoinQuant parity rules that are specific to
  this reproduction project:
  - ST/name snapshot overrides used by `get_all_securities` and `get_extras`.
  - Project preprocessed feature cache readers under `project_cache/features`.
  - Observed tail-seal and billboard parity exceptions.
  - Optional pre-open duplicate-order rule for older derived alignment logs.
- Run scripts for this application must pass
  `compat=EmotionGateJQCompat(ROOT)` when constructing `Engine`.

## Current Status

The framework is now configured by injection:

```python
from engine.core import Engine
from project_compat import EmotionGateJQCompat

engine = Engine(strategy_code, start_date, end_date, 1000000,
                compat=EmotionGateJQCompat(ROOT))
```

Without `compat`, `engine` still runs as a generic local JQ-style framework, but
project-only namespace helpers such as `get_project_board_snapshot` are not
injected into strategy globals.

The generic framework path is validated with the unmodified LocalQuant sample:

```powershell
python tools\verify_sample_strategy_alignment.py --start 2024-01-01 --end 2024-03-31
```

This reads `D:\work space\local_quant\strategies\sample_strategy.py` without
editing it, runs it once on this workspace framework and once on the original
read-only `D:\work space\local_quant` framework, and writes comparison artifacts
under `alignment_reports/sample_strategy_alignment/`.

## Do Not Touch

- Do not edit original `D:\work space\local_quant`.
- Do not edit original `D:\work space\hdata`.
- Keep strategy/application experiments separate from reusable framework code.
- Do not put new emotion-gate parity hacks directly in `engine/`; add them to
  `project_compat.py` or a future application profile.

## Remaining Cleanup

Some documented JQ historical data quirks still live inside `engine/data_api.py`
and `engine/core.py` because they model JoinQuant compatibility rather than the
emotion-gate strategy itself.  If a second application needs a clean framework,
promote those quirks into a separate generic `JQHistoricalQuirkProfile` and pass
it through the same `compat` mechanism.
