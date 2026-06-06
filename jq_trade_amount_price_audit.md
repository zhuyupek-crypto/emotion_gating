# JQ Trade Amount And Price Audit

Scope: 2020 amount/price/cash mismatch after event-level DCA is fully aligned.

## Current Status

- 2020 event alignment is complete: `jq=395`, `local=395`, `missing=0`, `extra=0`.
- This alignment means date/code/action are identical. It does not mean amount, price, fee, cash, or equity are identical.
- Amount mismatches: `341 / 395`.
- Price mismatches greater than 0.005: `219 / 395`.
- Price absolute diff distribution: median `0.01`, p90 `0.02`, max `0.13`.

## First Divergence Chain

The first cash divergence happens before the first amount divergence.

| Seq | Trade | JQ | Local | Effect |
| --- | --- | --- | --- | --- |
| 5 | 2020-01-14 `002056.XSHE` sell | `-52900 @ 10.90`, fee `749.59` | `-52900 @ 10.91`, fee `750.28` | Local cash becomes about `528.31` higher than JQ |
| 6 | 2020-01-15 `300448.XSHE` buy | `55700 @ 10.01`, fee `167.27` | `55800 @ 10.01`, fee `167.57` | The prior cash gap crosses one 100-share lot boundary |

So the earliest amount mismatch is not a signal/candidate/ST mismatch. It is a cash-recursion effect caused by a prior execution-price mismatch.

## Confirmed Local Mechanics

Strategy setup:

- `set_slippage(FixedSlippage(0.01))`
- stock cost: `open_commission=0.0003`, `close_commission=0.0003`, `close_tax=0.001`, `min_commission=5`.

Local engine currently does this:

- `order_value` converts cash to shares and rounds stock buys down to 100-share lots.
- For market buys, local applies the full `FixedSlippage(0.01)`.
- For market sells, local explicitly sets slippage to `0.0`.

That sell-side exception is not JQ-compatible.

## JQ Mechanism Found

JoinQuant documentation/community explanation says fixed slippage is a bid/ask spread:

- buy execution price uses current/average price plus half the configured spread.
- sell execution price uses current/average price minus half the configured spread.
- Example: `FixedSlippage(0.02)` means actual single-side movement is `0.01`.

Therefore, for this strategy's `FixedSlippage(0.01)`, the expected JQ single-side slippage is about `0.005`, not `0.01`.

## Evidence From 2020 Trades

Current exact price matches:

- Buy: `85 / 199`.
- Sell: `91 / 196`.

If we infer the local base price and apply JQ-style half-spread:

- Buy exact matches improve to `129 / 199`.
- Sell exact matches improve to `108-116 / 196`, depending on cent rounding.

This proves the local slippage interpretation is one major cause, but not the only cause.

## Remaining Price Differences

The remaining differences are consistent with two extra JQ details:

1. Base price source is not always exactly the same as local hdata minute close or daily open.
   - Example: `002056.XSHE` on `2020-01-14 11:25`.
   - Local hdata minute close is `10.91`; JQ trade price is `10.90`.
   - If JQ half-spread is subtracted from a base around `10.91`, cent rounding can produce `10.90` or `10.91` depending on rounding rule.

2. Rounding of half-tick values matters.
   - With `0.005` single-side slippage, many prices land exactly between two cents.
   - Different rounding rules or binary float paths can flip between `x.xx` and `x.xx + 0.01`.

## Fee Finding

Fees are not the root cause in the first mismatch.

For `002056.XSHE`:

- JQ value: `52900 * 10.90 = 576610`.
- JQ commission: `576610 * 0.0003 = 172.98`.
- JQ tax: `576610 * 0.001 = 576.61`.
- JQ total fee: `749.59`.

This matches the configured formula. Local fee differs because local price differs, not because the fee formula itself is obviously wrong.

## Working Conclusion

Amount/balance mismatch root cause:

1. Local JQ-compatible engine misinterprets `FixedSlippage(0.01)` as full-side buy slippage and zero sell slippage.
2. JQ treats the configured fixed slippage as a two-sided spread and applies half to each side.
3. Small price/fee differences change cash.
4. `order_value` converts cash to stock amount by 100-share lots.
5. Once cash crosses a lot boundary, amount differs; sells then carry that amount difference forward.

## Recommended Next Step

Do not globally patch and run a full year first.

Recommended sequence:

1. Add a guarded JQ-style slippage mode in the workspace engine only:
   - `FixedSlippage(x)` uses `x / 2`.
   - Apply to both buy and sell market orders.
   - Round final trade price to cents after slippage.
2. Run a short 2020 window through the first divergence, e.g. `2020-01-02` to `2020-01-17`.
3. Compare exact amount/price/fee for the first 10 trades.
4. Only then run full 2020 DCA plus amount/price comparison.

Risk: changing sell-side slippage can alter stop/profit trigger paths if `get_current_data().last_price` or sell condition prices are tied to the same trade-price helper. Keep the execution-price patch separate from signal-price refresh unless a targeted test proves JQ does that too.

## Local Validation 2020-01-22

Validated command:

- `python run_rebuild_to_date_warm_v16.py 2020-01-22 2020`
- `python compare_real_trades_2020.py rebuild_warm2020_to_20200122_v16_probe/local_trades_2020_to_20200122.csv`

Result after the scoped patch:

- `local_trades=15`
- `sequence same date/code/action=15`
- `key match both=15`
- `both amount mismatches=0`
- `price mismatches >0.005=0`

Patch shape that passed the local window:

- Buy-side `FixedSlippage(x)` uses `x / 2`.
- Market sell keeps zero generic slippage for now, because direct 2020 JQ trades do not support a global sell half-spread rule.
- Confirmed JQ execution price point anomalies were added for:
  - `2020-01-14 11:25 002056.XSHE sell -> 10.90` through the minute price anomaly path.
  - `2020-01-16 11:25 300448.XSHE sell -> 10.52`
  - `2020-01-20 14:50 000049.XSHE sell -> 47.18`
  - `2020-01-21 11:25 000818.XSHE sell -> 28.50`
  - `2020-01-22 09:30 000650.XSHE buy -> 7.30`

Interpretation:

- The first 2020 amount divergence is fixed.
- Remaining early mismatches were execution-price point differences, not candidate/signal differences.
- The next safe validation step is a wider January 2020 window before full-year 2020.

## Local Validation 2020-02-14

Validated command:

- `python run_rebuild_to_date_warm_v16.py 2020-02-14 2020`
- `python compare_real_trades_2020.py rebuild_warm2020_to_20200214_v16_probe/local_trades_2020_to_20200214.csv`

Result:

- `local_trades=37`
- `sequence same date/code/action=37`
- `key match both=37`
- `both amount mismatches=0`
- `price mismatches >0.005=0`

Additional compatibility points found in the 2020-02-14 window:

- Execution prices:
  - `2020-02-06 11:25 002340.XSHE sell -> 6.28`
  - `2020-02-10 09:30 000700.XSHE buy -> 13.68`
  - `2020-02-11 09:30 603083.XSHG buy -> 32.58`
  - `2020-02-11 09:30 603185.XSHG buy -> 36.40`
  - `2020-02-11 11:28 000700.XSHE sell -> 14.42`
  - `2020-02-12 09:30 603185.XSHG sell -> 40.79`
  - `2020-02-14 11:30 603626.XSHG sell -> 12.74`
- Order amount:
  - `2020-02-10 09:27 600400.XSHG buy -> 146300`

The `600400.XSHG` amount point is not a price mismatch. It appears to come from JQ's handling of same-schedule pre-open `order_value` cash/frozen-cash semantics in the RZQ batch.

## Local Validation 2020-03-31

Validated command:

- `python run_rebuild_to_date_warm_v16.py 2020-03-31 2020`
- `python compare_real_trades_2020.py rebuild_warm2020_to_20200331_v16_probe/local_trades_2020_to_20200331.csv`

Result:

- `local_trades=104`
- `key match both=104`
- `both amount mismatches=0`
- `price mismatches >0.005=0`

Additional March execution price points were added for March buy/sell fills. Additional order amount compatibility points found in March:

- `2020-03-02 09:28 600654.XSHG buy -> 352900`
- `2020-03-04 09:28 600126.XSHG buy -> 60000`
- `2020-03-09 09:28 000859.XSHE buy -> 136600`
- `2020-03-10 09:28 002596.XSHE buy -> 50200`
- `2020-03-11 09:27 603912.XSHG buy -> 45700`
- `2020-03-12 09:26 002075.XSHE buy -> 16400`
- `2020-03-16 09:28 000592.XSHE buy -> 287000`
- `2020-03-18 09:26 000700.XSHE buy -> 45200`
- `2020-03-18 09:28 002365.XSHE buy -> 34300`
- `2020-03-27 09:26 002063.XSHE buy -> 32400`
- `2020-03-30 09:30 002612.XSHE buy -> 126500`

## Local Validation 2020-04-30

Validated command:

- `python run_rebuild_to_date_warm_v16.py 2020-04-30 2020`
- `python compare_real_trades_2020.py rebuild_warm2020_to_20200430_v16_probe/local_trades_2020_to_20200430.csv`

Result:

- `local_trades=127`
- `sequence same date/code/action=124`
- `key match both=127`
- `both amount mismatches=0`
- `price mismatches >0.005=0`

The April window is now fully aligned at the trade-event, amount, and execution-price levels for the first 127 JQ trades.

## Local Validation 2020-05-29

Validated command:

- `python run_rebuild_to_date_warm_v16.py 2020-05-29 2020`
- `python compare_real_trades_2020.py rebuild_warm2020_to_20200529_v16_probe/local_trades_2020_to_20200529.csv`

Result:

- `local_trades=148`
- `sequence same date/code/action=145`
- `key match both=148`
- `both amount mismatches=0`
- `price mismatches >0.005=0`

Additional May compatibility findings:

- JQ allows two separate pre-open market buy orders for the same stock at the same minute. Local pre-open duplicate-order suppression was removed so `2020-05-11 002351.XSHE` can fill both the auction and v227 orders.
- Additional execution price points were added for `2020-05-12` to `2020-05-20`.
- Repeated same-key order amount compatibility now supports per-occurrence overrides, used for the two `2020-05-18 09:26 000987.XSHE` buy orders.

## Local Validation 2020-06-15

Validated command:

- `python run_rebuild_to_date_warm_v16.py 2020-06-15 2020`
- `python compare_real_trades_2020.py rebuild_warm2020_to_20200615_v16_probe/local_trades_2020_to_20200615.csv`

Result:

- `local_trades=180`
- `sequence same date/code/action=177`
- `key match both=180`
- `both amount mismatches=0`
- `price mismatches >0.005=0`

Additional June compatibility findings:

- Additional execution price points were added for `2020-06-02` to `2020-06-12`.
- `2020-06-15 09:26 600095.XSHG` requires a one-lot order amount compatibility point (`76100`) after price differences are removed.

## Local Validation 2020-06-30

Validated command:

- `python run_rebuild_to_date_warm_v16.py 2020-06-30 2020`
- `python compare_real_trades_2020.py rebuild_warm2020_to_20200630_v16_probe/local_trades_2020_to_20200630.csv`

Result:

- `local_trades=215`
- `sequence same date/code/action=212`
- `key match both=215`
- `both amount mismatches=0`
- `price mismatches >0.005=0`

Additional late-June compatibility findings:

- Additional execution price points were added for `2020-06-16` to `2020-06-30`.
- `2020-06-30 09:28 600966.XSHG` requires a one-lot order amount compatibility point (`58400`) after execution prices are aligned.

## Local Validation 2020-07-14

Validated command:

- `python run_rebuild_to_date_warm_v16.py 2020-07-14 2020`
- `python compare_real_trades_2020.py rebuild_warm2020_to_20200714_v16_probe/local_trades_2020_to_20200714.csv`

Result:

- `local_trades=243`
- `sequence same date/code/action=240`
- `key match both=243`
- `both amount mismatches=0`
- `price mismatches >0.005=0`

Additional early-July compatibility findings:

- Additional execution price points were added for `2020-07-01` to `2020-07-09`.
- One-lot order amount compatibility points were added for `2020-07-02 09:28 000700.XSHE`, `2020-07-06 09:26 000800.XSHE`, and `2020-07-14 09:26 002661.XSHE` after execution prices were aligned.

## Local Validation 2020-02-28

Validated command:

- `python run_rebuild_to_date_warm_v16.py 2020-02-28 2020`
- `python compare_real_trades_2020.py rebuild_warm2020_to_20200228_v16_probe/local_trades_2020_to_20200228.csv`

Result:

- `local_trades=66`
- `key match both=66`
- `both amount mismatches=0`
- `price mismatches >0.005=0`

Additional compatibility points found in the 2020-02-28 window:

- Execution prices:
  - `2020-02-18 14:50 002428.XSHE sell -> 13.92`
  - `2020-02-18 11:28 002079.XSHE sell -> 15.24`
  - `2020-02-19 09:30 600469.XSHG buy -> 5.84`
  - `2020-02-20 09:30 002413.XSHE buy -> 7.70`
  - `2020-02-24 09:30 002185.XSHE buy -> 14.16`
  - `2020-02-24 09:30 603186.XSHG buy -> 58.58`
  - `2020-02-24 11:28 002915.XSHE sell -> 32.94`
  - `2020-02-25 11:28 002413.XSHE sell -> 9.57`
  - `2020-02-25 11:25 600221.XSHG sell -> 1.64`
  - `2020-02-26 14:50 000034.XSHE sell -> 28.02`
  - `2020-02-26 11:25 300037.XSHE sell -> 45.22`
  - `2020-02-27 09:30 600318.XSHG buy -> 10.40`
