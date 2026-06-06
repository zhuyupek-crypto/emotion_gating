# LocalQuant State Alignment Notes

Scope: read-only inspection of `D:\work space\local_quant` and `D:\work space\hdata`.

## Current State

- `local_quant` is ahead of the older local probe path and should be the primary runner.
- 2020 mother-log and local-run state rows both cover 243 trading days.
- State alignment is already close:
  - mode mismatches: 1 day
  - active-route mismatches: 1 day
  - `fb_pct` absolute diff greater than 0.05: 16 days
  - `FB` absolute diff greater than 0.001: 6 days
- JQ enhanced state-machine log confirms there are exactly 3 `first_board_perf=NaN`
  days in 2020.

The generated comparison table is:

`D:\Work Space\他山之石\情绪门控\compare_localquant_state_2020.csv`

The extracted JQ NaN-day tables are:

- `D:\Work Space\他山之石\情绪门控\jq_sm_nan_days_2020.csv`
- `D:\Work Space\他山之石\情绪门控\jq_sm_nan_local_mismatch_2020.csv`

## Important Remaining Pattern

The largest state differences are JQ `FB=nan` days:

| date | JQ mode | local mode | JQ active | local active | JQ FB | local FB | JQ fb_pct | local fb_pct |
|---|---|---|---|---|---:|---:|---:|---:|
| 2020-08-05 | bull | bull | rzq+zb | rzq+zb | nan | 0.010 | 0.0000 | 0.25 |
| 2020-08-26 | bull | bull | rzq+zb | rzq+zb | nan | 0.007 | 0.0000 | 0.25 |
| 2020-09-17 | bear | cautious | v227 | v227 | nan | 0.003 | 0.0000 | 0.27 |

These are not trade-derived differences. They occur at `prepare_all` before the day routes are used.

## Likely Cause

The mother code calculates:

```python
closes = history(2, field='close', security_list=g.prev_first_boards, df=False, fq=None)
rets.append(c[1] / c[0] - 1)
return float(np.mean(rets))
```

JQ preserves at least one NaN return in the `rets` list on the three dates above, so `np.mean(rets)` becomes NaN, and then `fb_pct` becomes 0.

LocalQuant currently returns a finite result on those same dates. That means its `history(..., df=False, fq=None)` path is likely filtering, filling, shifting, or otherwise not reproducing the JQ NaN propagation for those first-board samples.

The `FB` calculation runs before the daily scan refreshes `g.prev_first_boards`,
so the relevant pool for a given `FB` date is the previous trading day's
`[SM-PFB]` list, not the same-day list.

- 2020-08-05 uses 2020-08-04 PFB. The JQ log compresses this list as
  `n=194` with `...(+114)`, so the exact offending member is hidden in the
  available log text.
- 2020-08-26 uses 2020-08-25 PFB. Current hdata reproduces a NaN return for
  `300090.XSHE`: `c[0]=0.12`, `c[1]=NaN`.
- 2020-09-17 uses 2020-09-16 PFB. Current hdata reproduces a NaN return for
  `300216.XSHE`: `c[0]=0.19`, `c[1]=NaN`.

The result is a one-day hard state divergence on 2020-09-17 (`bear` vs
`cautious`) and many later `fb_pct` rank differences because NaN values stay
inside the 60-day `fb_perf_history` window and compare false in
`v < g.first_board_perf`.

After classifying by the 60-trading-day window after these JQ NaN events:

- 66 of 69 `fb_pct` differences greater than 0.01 are explained by the NaN
  window.
- 15 of 16 `fb_pct` differences greater than 0.05 are explained by the NaN
  window.
- The 2020-08-19 active-route mismatch is explained by the 2020-08-05 NaN:
  JQ `fb_pct=0.7833`, local `fb_pct=0.80`; the route threshold is `>=0.8`.

The first large pre-NaN discrepancy is 2020-06-23:

- JQ: `FB=0.0112`, `fb_pct=0.3667`
- local: `FB=0.0100`, `fb_pct=0.3000`
- mode and active route still match, so this is lower priority than the NaN
  propagation issue.

`D:\work space\local_quant\results\jq_pct_overrides.csv` already contains the
JQ `fb_pct` stream, including the 3 NaN days. However, the formal 2020 run path
`D:\work space\local_quant\run_mother_2020.py` loads
`D:\work space\他山之石\情绪门控\母版-20260506-Clone.py`, not
`D:\work space\local_quant\research\temp\strategy_aligned_2020.py`; the override
logic appears only in the research/temp strategy copy. That explains why
`results\local_run_2020.log` still shows finite local `FB` / `fb_pct` on the 3
NaN dates.

## Recommended Next Check

In `local_quant`, instrument only the `history(2, field='close', df=False, fq=None)` call used by `calc_fb_perf`, and print entries where:

- `len(c) == 2`
- `c[0] > 0`
- `c[1]` is NaN

Do this for 2020-08-05, 2020-08-26, and 2020-09-17. If no such entry appears locally, the missing behavior is in `DataAPI.get_price` / `wrapped_history`, not the strategy.

## Practical Fix Direction

Keep the fix inside the JoinQuant-compatible API layer, not the strategy:

- preserve JQ-like NaN values in `history(..., df=False, fq=None)` for daily multi-security close requests;
- avoid silently dropping securities from the returned dict if JQ would return a two-element array containing NaN;
- avoid filling missing daily bars in the raw `fq=None` path used by `calc_fb_perf`.
