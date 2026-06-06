# 2020 Real Trade Alignment Findings

Scope: read-only comparison against
`D:\work space\local_quant\results\jq_trades_2020_real.txt`.

## Inputs

- JQ baseline: `D:\work space\local_quant\results\jq_trades_2020_real.txt`
- Local trades: `D:\work space\local_quant\results\local_trades_2020.csv`

Generated in the current workspace:

- `D:\Work Space\他山之石\情绪门控\jq_trades_2020_real_parsed_from_txt.csv`
- `D:\Work Space\他山之石\情绪门控\compare_real_trades_2020_by_sequence.csv`
- `D:\Work Space\他山之石\情绪门控\compare_real_trades_2020_by_key.csv`

## Summary

- JQ baseline parsed trades: 395
- Local trades: 388
- Sequence-level exact matches: 0
- Sequence-level same date/code/action: 15
- Date/code/action key matches: 249
- JQ-only keys: 146
- Local-only keys: 139

This is not yet a small one-lot residual. The largest visible issue starts at
the first trading day: local buy prices are often lower than JQ buy prices,
which inflates local share counts and then cascades into later cash/position
differences.

## Primary Pattern

For early buy orders, JQ appears to execute the pre-open scheduled market order
at the current day's open/auction price, while local execution is using a
previous-day-visible price for many 09:26/09:27/09:28 orders.

Examples:

| seq | date time | code | JQ price | local price | JQ amount | local amount |
|---:|---|---|---:|---:|---:|---:|
| 1 | 2020-01-02 09:26 | 002041.XSHE | 9.96 | 9.63 | 31100 | 31100 |
| 3 | 2020-01-13 09:26 | 002056.XSHE | 10.08 | 9.18 | 52900 | 58100 |
| 4 | 2020-01-13 09:26 | 002235.XSHE | 10.66 | 9.65 | 51100 | 55200 |
| 6 | 2020-01-15 09:26 | 300448.XSHE | 10.01 | 9.14 | 55700 | 69200 |
| 9 | 2020-01-17 09:26 | 000818.XSHE | 23.70 | 22.72 | 26100 | 31100 |

Direct hdata checks show the JQ prices above match current-day raw daily open
values, not a data-source problem.

## Likely Cause

`engine/order.py::get_trade_price()` intends `09:30-09:35` to use daily open.
But it calls `DataAPI.get_price(... end_date=current_dt, frequency='daily')`.
Inside engine context, `DataAPI.get_price()` shifts daily requests before 09:30
back to the previous trading day to avoid lookahead for `history`.

That anti-lookahead rule is correct for historical data access, but it appears
too strict for actual order matching at scheduled buy times such as 09:26. JQ's
transaction log shows those market orders are filled at the day's open/auction
execution price.

## Suggested Fix Direction

Keep this in the API/engine compatibility layer:

- For order matching (`get_trade_price`), bypass the before-09:30 daily
  anti-lookahead shift and fetch today's open directly, similar to how
  `get_current_data()` already uses `_get_price_raw()` for today's open/limits.
- Preserve the anti-lookahead shift for strategy `history/get_price` calls,
  because that was important for state-machine alignment.
- Re-run 2020 and compare `jq_trades_2020_real.txt` against
  `local_trades_2020.csv` after this change.
