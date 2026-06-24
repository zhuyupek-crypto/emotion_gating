# Amount/Price Difference Root-Cause Notes

This is diagnostic only. No repair was attempted.

## Summary

- Matched trades with amount differences: 538
- Buy-side amount differences: 270
- Matched trades with price differences: 22
- First price mismatch: `2020-07-15` `600502.XSHG` `sell` JQ=4.66 local=4.67 diff=-0.009999999999999787
- First buy amount mismatch: `2020-07-16` `601216.XSHG` JQ=212800 local=212900 diff=-100; price JQ=3.48 local=3.48
- Same-day portfolio drift at first amount mismatch: total_diff=1537.86, cash_diff=1228.86, positions_value_diff=309.00

## Concrete First Chain

The first material share-count divergence is `2020-07-16 601216.XSHG`: JQ bought 212800 shares, local bought 212900 shares.

The immediate upstream cause is the previous day's `600502.XSHG` sell price: JQ sold at 4.66, local sold at 4.67. With 89700 shares, this creates about 897 yuan extra local proceeds before fees. At `601216.XSHG` price 3.48, one lot costs about 348 yuan, so this cash drift is sufficient to cross one 100-share lot boundary.

Relevant nearby rows:

| date | code | action | category | jq_amount | local_amount | amount_diff | jq_price | local_price | price_diff |
|---|---|---|---|---:|---:|---:|---:|---:|---:|
| 2020-07-15 | 600502.XSHG | sell | data_diff_price | 89700 | 89700 | 0 | 4.66 | 4.67 | -0.009999999999999787 |
| 2020-07-16 | 002626.XSHE | sell | data_diff_price | 34100 | 34100 | 0 | 41.08 | 41.1 | -0.020000000000003126 |
| 2020-07-16 | 600685.XSHG | buy | matched | 2300 | 2300 | 0 | 31.33 | 31.33 | 0.0 |
| 2020-07-16 | 601216.XSHG | buy | data_diff_amount | 212800 | 212900 | -100 | 3.48 | 3.48 | 0.0 |
| 2020-07-17 | 600685.XSHG | sell | data_diff_price | 2300 | 2300 | 0 | 33.21 | 33.22 | -0.00999999999999801 |
| 2020-07-17 | 601216.XSHG | sell | data_diff_amount | 212800 | 212900 | -100 | 3.1 | 3.1 | 0.0 |

## Pattern Classification

- Early share-count differences are mostly 100-share boundary effects after small cash/price drifts.
- A single 0.01 execution price difference on a large position can create enough cash drift to change the next buy by one or more lots.
- Once cash differs, later `order_value` sizing will keep producing amount differences even when signal, code, direction, and nominal price match.
- Larger late-2021 gaps are mixed with true key mismatches and incomplete JQ fund export, so they must be reviewed separately from early rounding drift.

## Monthly Concentration

| month | buy amount diffs | price diffs | max abs amount diff |
|---|---:|---:|---:|
| 2020-07 | 11 | 9 | 900 |
| 2020-08 | 17 | 3 | 7200 |
| 2020-09 | 11 | 0 | 3800 |
| 2020-10 | 4 | 0 | 7700 |
| 2020-11 | 6 | 0 | 11200 |
| 2020-12 | 10 | 0 | 9800 |
| 2021-01 | 17 | 0 | 16600 |
| 2021-02 | 6 | 0 | 29700 |
| 2021-03 | 10 | 0 | 5300 |
| 2021-04 | 14 | 0 | 113400 |
| 2021-05 | 20 | 1 | 38900 |
| 2021-06 | 21 | 2 | 700 |
| 2021-07 | 25 | 6 | 2400 |
| 2021-08 | 29 | 1 | 331300 |
| 2021-09 | 25 | 0 | 17400 |
| 2021-10 | 11 | 0 | 22600 |
| 2021-11 | 11 | 0 | 16800 |
| 2021-12 | 22 | 0 | 118900 |

## Prior Price Differences Before First Amount Mismatch

| date | code | action | jq_price | local_price | price_diff |
|---|---|---|---:|---:|---:|
| 2020-07-15 | 600502.XSHG | sell | 4.66 | 4.67 | -0.009999999999999787 |
| 2020-07-16 | 002626.XSHE | sell | 41.08 | 41.1 | -0.020000000000003126 |
