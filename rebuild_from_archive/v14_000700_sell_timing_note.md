# v14 000700 Sell Timing Note

## Finding

The first remaining 2020 trade-alignment divergence was `000700.XSHE`:

- Local v13 bought on `2020-07-02 09:30` and sold on `2020-07-03 14:48`.
- JoinQuant bought on `2020-07-02 09:28` and sold on `2020-07-06 11:30`.

The local `2020-07-03 14:48` sell came from strategy log `[zb卖] 000700.XSHE ret=0.0%`.

For `zb` holdings, the sell rule is:

- sell if `ret > 0`
- sell if current price is below MA5
- sell if previous-day close equals previous-day high limit

On `2020-07-03 14:48`, hdata minute close is stored as `8.010000228881836`, while the position average cost is effectively `8.01` after `FixedSlippage(0.01)`. The unrounded float32 minute price made `ret > 0` true, even though the logged return rounded to `0.0%`.

MA5 and previous-day high-limit checks were not the cause:

- MA5 through `2020-07-02`: `7.666`
- `2020-07-02` close/high_limit: `7.88 / 8.88`

## Change

`engine/order.py` now rounds trade price and daily limit prices to 2 decimals at the `get_trade_price` boundary.

This keeps A-share current prices from leaking hdata float32 noise into strategy comparisons and order execution.

## Targeted Check

After the change:

- `2020-07-03 14:48`: `price=8.01`, `avg=8.01`, `ret=0.0`, `cond_gain=False`, `cond_ma=False`
- `2020-07-06 11:30`: `price=8.39`, `avg=8.01`, `ret=4.744%`, `cond_gain=True`

So the 7/3 premature sell should be removed, and the position should survive to the next scheduled `zb` sell on 7/6.

## Verification Status

A full `run_rebuild_2020_v14.py` run was started, but it was too slow for the current tool timeout and did not complete. No v14 CSV outputs were written yet.

