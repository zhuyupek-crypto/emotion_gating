# v227 YJJ Baseline Record

Created: 2026-05-18

This note freezes the current local hdata-native baseline for the mother
strategy's v227 "一进二" leg before adding the rest of pure v227 logic
such as 天蝎座, 龙头保护, and fuller holding state.

## Scope

Included:

- v227 一进二 candidate chain
- market mode / fb_pct / first-board performance gate
- first-board daily filters: ST, IPO age, circulating market cap, money,
  bull money cap, average price strength
- v122 volume-blowoff filter
- v130 first-limit-time tail seal filter
- low-price tilt / bull left-pressure scoring where implemented
- 09:26 buy simulation
- v227 scheduled sell approximation:
  - 11:25 profit sell
  - 13:01 <= -2% sell
  - intraday <= -5% stop
  - 14:50 non-limit close

Not yet included:

- v227 天蝎座 bear-mode low-open branch
- v227 龙头保护 full state
- exact JoinQuant minute-bar/cost alignment
- rzq / zb / auction_yiqian modules
- real order book / liquidity / slippage model beyond current simple fill

## Data And Script

Data source:

- `D:\work space\hdata\data\processed`
- 1d stock, 1m stock, stock_indicator, ST list, stock_basic
- local `idx_000852.parquet`

Script:

- `scripts/v227_yjj_probe.py`

Important switch:

- `--sell-time-shift 0`

The `--sell-time-shift` switch was tested with `-1`, `0`, and `+1` on the
March 2024 JoinQuant audit sample. `0` was closest overall, so no global
1-minute offset is applied.

## Commands

```powershell
python scripts\v227_yjj_probe.py --start 20240101 --end 20241231 --warmup 20231001 --sell-time-shift 0 --trades-out out_v227_hdata_2024_trades.csv --equity-out out_v227_hdata_2024_equity.csv
python scripts\v227_yjj_probe.py --start 20250101 --end 20251231 --warmup 20241001 --sell-time-shift 0 --trades-out out_v227_hdata_2025_trades.csv --equity-out out_v227_hdata_2025_equity.csv
python scripts\v227_yjj_probe.py --start 20260101 --end 20260515 --warmup 20251001 --sell-time-shift 0 --trades-out out_v227_hdata_2026_trades.csv --equity-out out_v227_hdata_2026_equity.csv
```

## Result Summary

| Period | Trading days | Sells | Return | Max drawdown | Win rate | Avg trade | Median trade | Best trade | Worst trade |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 2024 | 242 | 80 | 49.68% | -30.03% | 55.00% | 1.52% | 0.88% | 29.11% | -20.48% |
| 2025 | 243 | 142 | 113.04% | -21.26% | 55.63% | 1.34% | 0.52% | 45.67% | -14.62% |
| 2026-01-01 to 2026-05-15 | 80 | 57 | 44.71% | -13.79% | 54.39% | 1.61% | 0.43% | 44.09% | -12.48% |

## Monthly Equity Returns

| Month | Return |
| --- | ---: |
| 202401 | 0.00% |
| 202402 | 0.00% |
| 202403 | 25.38% |
| 202404 | 21.06% |
| 202405 | -4.14% |
| 202406 | -0.77% |
| 202407 | 0.00% |
| 202408 | 0.00% |
| 202409 | 5.28% |
| 202410 | 24.35% |
| 202411 | -7.08% |
| 202412 | -18.64% |
| 202501 | 0.00% |
| 202502 | 12.64% |
| 202503 | 9.81% |
| 202504 | -0.97% |
| 202505 | 0.00% |
| 202506 | 5.61% |
| 202507 | 7.84% |
| 202508 | 50.52% |
| 202509 | -0.59% |
| 202510 | -7.44% |
| 202511 | 0.75% |
| 202512 | 25.29% |
| 202601 | 3.40% |
| 202602 | 2.29% |
| 202603 | 25.29% |
| 202604 | -7.81% |
| 202605 | 9.76% |

## Output Files

- `out_v227_hdata_2024_trades.csv`
- `out_v227_hdata_2024_equity.csv`
- `out_v227_hdata_2025_trades.csv`
- `out_v227_hdata_2025_equity.csv`
- `out_v227_hdata_2026_trades.csv`
- `out_v227_hdata_2026_equity.csv`

## JoinQuant Alignment Notes

The local candidate chain matches the JoinQuant March 2024 samples well.
The remaining observed differences are mostly sell-side minute data and
execution-cost details.

Examples:

- `300347.XSHE` on 2024-03-18:
  - JoinQuant 13:01 close was 51.950, above the 51.940 midday threshold.
  - hdata 13:01 close was 51.920, below the threshold.
  - This changes the exit from 14:50 `eod_clear` to 13:01 `midday_loss`.
- `002130.XSHE` on 2024-03-25:
  - JoinQuant 14:50 close was 10.990, still limit-like.
  - hdata raw/processed 14:50 close was 10.910.
  - hdata exits one day earlier; JoinQuant carries to 2024-03-26.

Raw hdata 1m zip and processed hdata were checked and matched. Therefore
these are upstream minute-bar differences, not local build errors.

## Current Interpretation

This baseline does not collapse under local hdata. The signal remains
positive across 2024, 2025, and early 2026, but it is not low-risk:

- 2024 max drawdown reached about -30%.
- Return is month-concentrated in several windows.
- Median trade return is modest, so large winners matter.
- Minute-bar differences can materially alter individual trade paths.

Next research step: implement pure v227 full logic, especially 天蝎座 and
龙头保护, while keeping this file as the one-in-two baseline.

## Pure v227 Extension Check

Update: 2026-05-18

`scripts/v227_yjj_probe.py` now has optional switches for the first pure
v227 extension:

- `--include-scorpion`: include bear-mode 天蝎座 low-open branch.
- `--leader-protect`: include v227 leader protection state.

Default behavior remains the original one-in-two baseline. The extension
must be explicitly enabled.

Commands:

```powershell
python scripts\v227_yjj_probe.py --start 20240101 --end 20241231 --warmup 20231001 --sell-time-shift 0 --include-scorpion --leader-protect --trades-out out_v227_full_hdata_2024_trades.csv --equity-out out_v227_full_hdata_2024_equity.csv
python scripts\v227_yjj_probe.py --start 20250101 --end 20251231 --warmup 20241001 --sell-time-shift 0 --include-scorpion --leader-protect --trades-out out_v227_full_hdata_2025_trades.csv --equity-out out_v227_full_hdata_2025_equity.csv
python scripts\v227_yjj_probe.py --start 20260101 --end 20260515 --warmup 20251001 --sell-time-shift 0 --include-scorpion --leader-protect --trades-out out_v227_full_hdata_2026_trades.csv --equity-out out_v227_full_hdata_2026_equity.csv
```

Comparison:

| Version | Period | Sells | Return | Max drawdown | Win rate | Avg trade | Median trade |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| YJJ only | 2024 | 80 | 49.68% | -30.03% | 55.00% | 1.52% | 0.88% |
| Pure v227 extension | 2024 | 96 | 83.76% | -31.94% | 56.25% | 1.75% | 1.03% |
| YJJ only | 2025 | 142 | 113.04% | -21.26% | 55.63% | 1.34% | 0.52% |
| Pure v227 extension | 2025 | 148 | 201.41% | -21.53% | 58.11% | 1.77% | 0.75% |
| YJJ only | 2026-01-01 to 2026-05-15 | 57 | 44.71% | -13.79% | 54.39% | 1.61% | 0.43% |
| Pure v227 extension | 2026-01-01 to 2026-05-15 | 57 | 46.19% | -12.91% | 54.39% | 1.65% | 0.43% |

Reason counts in the pure v227 extension:

| Reason | 2024 | 2025 | 2026 |
| --- | ---: | ---: | ---: |
| `v227_yjj` buys | 81 | 143 | 57 |
| `v227_scorpion` buys | 17 | 5 | 0 |
| `morning_profit` sells | 48 | 79 | 29 |
| `midday_loss` sells | 27 | 43 | 22 |
| `eod_clear` sells | 19 | 18 | 4 |
| `leader_exit` sells | 0 | 3 | 1 |
| `stop_loss` sells | 2 | 5 | 1 |

Interpretation:

- 天蝎座 materially improves 2024 and adds a smaller but still positive
  contribution in 2025.
- 龙头保护 is rare but directionally positive in this sample.
- 2024 return improves sharply, but max drawdown also worsens slightly.
- 2026 is almost unchanged because no scorpion trades are selected in the
  tested window.

## Performance Note

Update: 2026-05-18

`scripts/v227_yjj_probe.py` was optimized without changing strategy logic:

- vectorized first-board identification;
- vectorized board-count calculation for leader tagging;
- changed 1m parquet reads to use `date` filters instead of loading a full
  stock-year file before slicing one day.

Regression:

- March 2024 pure v227 extension trade output matched the pre-optimization
  output line by line.

Observed runtime on this machine:

| Run | Before | After |
| --- | ---: | ---: |
| 2024-03 pure v227 extension | about 61s | about 8.4s |
| 2024 full-year pure v227 extension | about 410s | about 44s |
| 2025 full-year pure v227 extension | about 428s | about 50s |
| 2026-01-01 to 2026-05-15 pure v227 extension | about 172s | about 24s |

## 2022 Force V227 Parity Pass

Update: 2026-05-18

After comparing with the JoinQuant `force_v227` single-year transaction log
for 2022-01-01 to 2022-12-31, the local probe was adjusted for three mother
strategy details:

- bull-mode one-in-two candidates are sorted by `_score_with_left_pressure`
  instead of raw stock-code order.
- `bull_sticky` is modeled, so a raw `cautious` day can still trade as `bull`
  for up to two sessions after a bull day.
- JoinQuant daily-backtest v227 stop behavior is modeled as an opening
  09:30 check, followed by 11:25 / 13:01 / 14:50 scheduled exits, rather than
  scanning the whole 1m tape for a -5% stop.

Current local force-v227 2022 command:

```powershell
python scripts\v227_yjj_probe.py --start 20220101 --end 20221231 --warmup 20211001 --sell-time-shift 0 --include-scorpion --leader-protect --trades-out tmp_v227_full_2022_force_v227_parity_trades.csv --equity-out tmp_v227_full_2022_force_v227_parity_equity.csv
```

Current local result:

| Scope | Buys | Sells | Return | Max DD | Win Rate | YJJ Buys | Scorpion Buys |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 2022 force_v227 parity pass | 121 | 121 | -4.84% | -20.17% | 51.2% | 92 | 29 |

Known remaining parity gaps:

- 2022 January YJJ path now matches the provided JoinQuant log closely:
  `600566/603368`, `000546`, `000810`, `002191/002589`,
  `600718/603466`, `000426/002432`.
- Scorpion branch still has stock-pool mismatches. JoinQuant trades multiple
  historical ST names in February/March, while local hdata ST filtering removes
  many of them. Conversely local hdata currently allows some very low-price /
  delisting-tail names such as `600145` and `000687`, which are not in the
  provided JoinQuant transaction log.
- Therefore current local force-v227 annual PnL is not yet a clean substitute
  for JoinQuant until the historical tradable-universe/ST/delisting rules are
  aligned.

## 2022 Force V227 ST Limit Pass

Update: 2026-05-19

The hdata `st_list` semantics were rechecked. It is a daily ST record table,
not a pure delisting table. For JoinQuant mother-strategy parity the local
probe now separates two roles:

- `st_list` is used for 5% ST limit-price calculation.
- `st_list` is not used as a stock-exclusion filter unless
  `--use-st-list-filter` is explicitly supplied.
- delisted names are excluded only near the delisting tail by `delist_date`
  with `--delist-tail-days` defaulting to 30.
- the mother-rule `bull + fb_pct < 0.2` v227 buy block was added.

Current command:

```powershell
python scripts\v227_yjj_probe.py --start 20220101 --end 20221231 --warmup 20211001 --sell-time-shift 0 --include-scorpion --leader-protect --trades-out tmp_v227_full_2022_force_v227_finalrules_trades.csv --equity-out tmp_v227_full_2022_force_v227_finalrules_equity.csv
```

Current result:

| Scope | Buys | Sells | Return | Max DD | Win Rate | YJJ Buys | Scorpion Buys |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 2022 force_v227 final-rules pass | 120 | 120 | -0.84% | -26.72% | 51.7% | 88 | 32 |

Important alignment changes:

- ST scorpion entries now reappear, including `600191`, `600093`,
  `002086`, `600146`, `600856`, and `002684`.
- The prior local-only delisting-tail trades in `600145` and `000687` are
  removed.
- January no longer has the local-only `600315` buy because the
  `bull_pct_lt_020` block is now modeled.

## 2022 Force V227 Execution Parity Pass

Update: 2026-05-19

The copied JoinQuant 2022 transaction history was saved as
`jq_force_v227_2022_raw.txt` and compared mechanically with
`scripts/compare_jq_force_v227_trades.py`.

One data-interface risk and two execution-level issues were fixed/confirmed in
the local probe:

- hdata daily candidates are selected as `000001.SZ` / `600000.SH`, and the
  corresponding hdata minute files are present and readable. The added
  `minute_bars()` symbol mapping is defensive for JoinQuant-format symbols in
  outputs/comparison, not the root cause of the 2022-01-24 split.
- v227 scheduled sells now respect low-limit non-fill behavior. This fixed the
  first true path split: local previously sold `002432.XSHE` on 2022-01-24 at
  the low limit `62.90`; JoinQuant carried it and sold on 2022-01-25 around
  `58.79`.
- Local buy sizing now follows the mother `order_value` behavior more closely:
  v227 one-in-two uses `pos_pct = 1.00` in bull and `0.75` otherwise, recomputes
  from remaining available cash per slot, and backs off by 100-share lots when
  fees would make the order exceed available cash. This restored the 2022-01-13
  second buy from local-only `002537.XSHE` back to JoinQuant's `002589.XSHE`.

Current command:

```powershell
python scripts\v227_yjj_probe.py --start 20220101 --end 20221231 --warmup 20211001 --sell-time-shift 0 --include-scorpion --leader-protect --trades-out tmp_v227_full_2022_force_v227_affordable_trades.csv --equity-out tmp_v227_full_2022_force_v227_affordable_equity.csv
python scripts\compare_jq_force_v227_trades.py --jq-raw jq_force_v227_2022_raw.txt --local tmp_v227_full_2022_force_v227_affordable_trades.csv --out-prefix compare_v227_2022_affordable
```

Current result:

| Scope | Local Rows | JQ Rows | JQ Only | Local Only | Matched Price/Size Diffs | Local Return | Win Rate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 2022 force_v227 execution parity | 244 | 220 | 34 | 58 | 184 | 0.10% | 51.6% |

Remaining structural gaps:

- The first remaining unmatched groups begin in April 2022, mostly in the
  v227 bear/scorpion low-open branch.
- Material price gaps are now a short list of scheduled sell bars, mostly
  one-minute/bar-source differences; the larger research blocker is still
  unmatched candidate selection, not price slippage.

Follow-up correction:

- hdata minute data was explicitly checked for `002432.SZ` and `600091.SH`;
  both have full 241-bar trading days in the examined sessions. The 2022-01-24
  `002432` split was execution logic, not missing local minute data.
- The limit-detection tolerance was changed from the local approximation
  `0.02` back to the mother-code value `0.01`. This removed a false low-price
  ST/retiring-name first-board classification in `600146.SH` on 2022-04-01.
- Bear/scorpion candidate order now preserves the mother scan order instead of
  forcing a local low-price sort. This aligned the 2022-04-28 pair from local
  `002596/002797` to JoinQuant's `002060/002596`.

Latest command/result after these corrections:

```powershell
python scripts\v227_yjj_probe.py --start 20220101 --end 20221231 --warmup 20211001 --sell-time-shift 0 --include-scorpion --leader-protect --trades-out tmp_v227_full_2022_force_v227_bearorder_trades.csv --equity-out tmp_v227_full_2022_force_v227_bearorder_equity.csv
python scripts\compare_jq_force_v227_trades.py --jq-raw jq_force_v227_2022_raw.txt --local tmp_v227_full_2022_force_v227_bearorder_trades.csv --out-prefix compare_v227_2022_bearorder
```

| Scope | Local Rows | JQ Rows | JQ Only | Local Only | Matched Price/Size Diffs | Local Return | Win Rate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 2022 force_v227 tolerance/order pass | 236 | 220 | 34 | 50 | 176 | 5.64% | 50.0% |

## 2022 Force V227 Low-Price Tilt Pass

Update: 2026-05-19 evening

Additional mother-code behavior added to `scripts/v227_yjj_probe.py`:

- Low-price tilt for non-bull v227 candidates, gated by market mode,
  `fb_pct`, retreat-phase detection, and recent realized win rate.
- The low-price multiplier is intentionally small, matching the mother
  direction rather than forcing an unconditional low-price sort.

Current command:

```powershell
python scripts\v227_yjj_probe.py --start 20220101 --end 20221231 --warmup 20211001 --sell-time-shift 0 --include-scorpion --leader-protect --trades-out tmp_v227_full_2022_force_v227_lowtilt_trades.csv --equity-out tmp_v227_full_2022_force_v227_lowtilt_equity.csv
python scripts\compare_jq_force_v227_trades.py --jq-raw jq_force_v227_2022_raw.txt --local tmp_v227_full_2022_force_v227_lowtilt_trades.csv --out-prefix compare_v227_2022_lowtilt
```

Current result:

| Scope | Local Rows | JQ Rows | JQ Only | Local Only | Matched Price/Size Diffs | Local Return | Win Rate |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 2022 force_v227 low-price tilt pass | 236 | 220 | 32 | 48 | 186 | 10.05% | 50.8% |

Remaining unmatched distribution:

| Side | 202203 | 202206 | 202207 | 202208 | 202209 | 202211 | 202212 | Total |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| JQ only rows | 0 | 0 | 16 | 2 | 4 | 4 | 6 | 32 |
| Local only rows | 2 | 4 | 22 | 14 | 0 | 0 | 6 | 48 |

High-signal findings from the remaining gaps:

- `002432.XSHE` proved the local hdata minute files are present; the old split
  was low-limit non-fill logic, not missing local minute data.
- The 2022-06-16 local-only `000025.XSHE` / `000987.XSHE` pair sits exactly on
  a state-boundary gate: full-year local context gives `fb_pct=0.38` and allows
  cautious v227, while a reset run around the same dates lands in the
  `[0.4,0.6)` cautious poison band and blocks. This should be treated as a
  strategy-state parity issue until JoinQuant audit values for that date are
  available.
- The 2022-07 cluster starts with local-only 2022-07-05
  `600477.XSHG` / `603127.XSHG`. A simple bull-route block does not explain the
  JoinQuant path, because JoinQuant later buys v227 on 2022-07-06 and
  2022-07-07 while the local `fb_pct` is still in the same mid-bull range. This
  points to candidate/filter/state parity, not a broad route switch.
- The 2022-12 cluster contains an execution-order mismatch: JoinQuant sells
  `603538.XSHG` at 09:30 and buys `000983.XSHE` at 09:30 on 2022-12-20. The
  local probe currently uses a simplified order where new buys are decided
  before same-morning exits free slots, so this is not an hdata price issue.

Current research stance:

- Local hdata is still usable for strategy dissection. The confirmed large
  splits so far are mostly execution/state reproduction issues.
- The local 2022 annual PnL should not yet be used as a clean replacement for
  JoinQuant force-v227 PnL, because a few early path splits cascade into many
  later unmatched trades.

## State-Machine Parity Framework

Update: 2026-05-23

The comparison workflow was changed from result-backtracking to state-machine
parity. The goal is to align pre-trade state first, then move down to
candidate and execution layers.

New local output:

```powershell
python scripts\v227_yjj_probe.py --start 20220101 --end 20220831 --warmup 20211001 --sell-time-shift 0 --include-scorpion --leader-protect --state-out local_state_2022_to_aug.csv --trades-out tmp_state_probe_trades.csv --equity-out tmp_state_probe_equity.csv
```

New comparison script:

```powershell
python scripts\compare_state_machine.py --jq-diag jq_diag_full.txt --local-state local_state_2022_to_aug.csv --out compare_state_2022_to_aug.csv --jq-state-out jq_state_2022.csv
```

Files:

- `local_state_2022_to_aug.csv`: local pre-trade state by day.
- `jq_state_2022.csv`: parsed JoinQuant `[DIAG-STATE]` rows.
- `compare_state_2022_to_aug.csv`: joined state comparison with difference
  tags.
- `scripts/compare_state_machine.py`: parser and state-machine diff tool.

Current state comparison result for the available JoinQuant DIAG window:

| Scope | Compared Dates | Both Sides | Rows With Diff | Mode Match | Active Match | fb_pct <= 0.02 | Max fb_pct Diff |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 2022-06 to 2022-08 DIAG window | 161 | 65 | 64 | 65/65 | 63/65 | 39/65 | 0.800000 |

High-signal findings:

- `market_mode` is fully aligned in the DIAG window (`65/65`). The first major
  splits are not raw-mode or bull-sticky problems.
- The active-route splits occur on `20220629` and `20220714`. Both are caused
  by `fb_pct` crossing the `0.8` route threshold locally while JoinQuant remains
  in `rzq+zb`.
- The 2022-07-05 local-only `600477.XSHG` / `603127.XSHG` issue is now
  explained at the state layer: JoinQuant has those YJJ candidates, but blocks
  them with `reason=not_enabled active=rzq+zb`. This is an active-route gate,
  not a candidate-selection issue.
- The 2022-06-29 `first_board_perf` split is a JoinQuant NaN propagation case.
  JoinQuant's 2022-06-28 PFB includes suspended/missing-price names such as
  `000502.XSHE`, `002447.XSHE`, `002464.XSHE`, and `300064.XSHE`; the mother
  `calc_fb_perf()` appends NaN and `np.mean(rets)` returns NaN. Local currently
  skips missing hdata rows, so it produces a valid `fb_perf` and crosses the
  `0.8` route gate. This is a state-machine reproduction issue, not an hdata
  price error.

Next state-machine tasks:

- Decide whether local parity mode should intentionally reproduce JoinQuant
  NaN propagation in `fb_perf`, while keeping the cleaner hdata-native mode for
  research.
- Implement `enable_v227`/`active` as a real buy gate in parity runs after the
  state layer is accepted.
- Add YJJ/BEAR candidate-list comparison only after L3-L6 state parity is
  either aligned or each residual difference is explicitly labeled.

Follow-up attempt:

- Added an experimental `--jq-na-propagation` switch to
  `scripts/v227_yjj_probe.py`. It is intentionally off by default.
- A first broad implementation degraded state parity: `market_mode` fell from
  `65/65` aligned to `59/65`, and `active` from `63/65` to `58/65`.
- Interpretation: NaN propagation is real for JoinQuant on dates such as
  `20220629`, but applying it directly to the current local PFB list over-fires
  because L2 PFB is not yet perfectly equivalent. This switch should remain
  diagnostic-only until the offending PFB residual names are labeled or a
  controlled JQ-state replay mode is added.

Important run-mode correction:

- `jq_diag_full.txt` / `母版-20260506-Clone-DIAG.py` are normal-route mother
  diagnostics, not the same run mode as the copied `force_v227` transaction
  history.
- This explains why DIAG can show `active=rzq+zb` and
  `enable_v227=False` on dates where the `force_v227` transaction history has
  v227 buys. The state log and transaction log were not from the same branch
  mode.
- A new generator was added:

```powershell
python scripts\make_diag_force_v227.py
```

It writes:

```text
母版-20260506-Clone-force-v227-DIAG.py
```

This file is based on `母版-20260506-Clone-强制单分支回测.py`, sets
`g.branch_test = 'v227'`, and appends the same DIAG hooks. Use this script in
JoinQuant for the next force-v227 state-machine log before comparing
cooldowns, recent-trade windows, slots, blocks, or buy decisions.

## 2022 Force V227 Deep Investigation Pass

Update: 2026-05-19 (session 2)

Current baseline: **32 JQ-only / 48 local-only / 186 matched** (same numbers as end of low-tilt pass).

This session focused on understanding the root cause of the remaining gaps
rather than adding new fixes. Each remaining unmatched cluster was inspected
in detail.

### Diagnostic Tool Created

A new script `scripts/diagnose_alignment.py` was created. It runs the full
probe logic from a warmup start (correctly accumulating `fb_hist` across all
warmup days), then prints detailed per-day diagnostics for specified focus
dates:

```powershell
python scripts\diagnose_alignment.py --focus 20220318,20220616,20220705,20220706,20220707
```

Key output includes: `market_mode`, `raw_mode`, `bull_sticky`, `fb_perf`,
`fb_pct`, `fb_hist` percentile distribution, `buy_block`, `low_tilt`, and
per-candidate open prices on the signal day.

**Important**: earlier ad-hoc runs that started from mid-year produced wrong
`fb_pct` values (e.g., showing 0.50 instead of the correct 0.38) because
`fb_hist` was not accumulated across the warmup period. This script fixes
that by always running from `--warmup 20211001` with only an `i<2` guard.

### Root Cause Analysis Per Cluster

**2022-03-18 (local-only 002422)**

Two local-only sell rows for `002422.XSHE` (scorpion entry). Probable
cause: data-level difference in 002422's open or prev-close price between
JoinQuant and hdata on or around 2022-03-17. JoinQuant may not have
selected 002422 as a valid scorpion candidate (wrong open range or filter).
Cannot reproduce without JQ's exact price data.

**2022-06-16 (local-only 000025 + 000987)**

Full-year probe gives `fb_pct = 0.3833` on 2022-06-16 (cautious mode, not
in the `[0.4, 0.6)` block → local allows the trade). JoinQuant's `fb_pct`
for the same day is presumably ≥ 0.40, which would fall inside the cautious
poison band and block trading.

Root cause is `fb_hist` state divergence: JoinQuant's first-board universe
differs from local (different ST exclusion, different tradable universe),
producing different `fb_perf` values for many days in Q1–Q2, which shifts
the percentile distribution. This is a structural, unfixable mismatch unless
the exact JoinQuant daily first-board membership can be replicated.

**2022-07-05 (local-only 600477 + 603127, cascades to 22 rows total)**

Confirmed facts (ruled out as causes):
- 涨停 detection: 600477 (hl=5.14, close=5.14) and 603127
  (hl=126.61, close=126.61) are valid 涨停 on 2022-07-04. Detection is NOT
  the issue.
- Market mode: unambiguously bull on 07-05 (CSI-1000=7076, MA60=6353,
  days_above_ma20=24/30=80%). Mode is NOT the issue.
- bull_sticky: local is already in bull mode, not a bull→cautious downgrade
  day, so bull_sticky is NOT the issue.

Observed pattern:
- Local 07-05 candidates avg_chg: 600477 7.01%, 603127 7.86%
- JQ 07-06 candidates avg_chg: 600030 8.19%, 000816 8.79%
- This suggests JQ may use a higher `avg_chg` threshold (e.g., ~8%) for
  some leg, or have a platform-level avg_chg computation difference.

Raising avg_chg threshold from 7% to 8% was NOT applied because it would
break some January matched trades (e.g., threshold-marginal stocks at
7.02%). Root cause remains unresolved at current information.

**2022-12-20 (JQ-only 6 rows, execution cascade)**

JoinQuant sells `603538.XSHG` at 09:30 and buys `000983.XSHE` at 09:30 on
2022-12-20. In JoinQuant, the 09:30 stop-loss frees a slot before the
09:26-queued buy decides whether to fill. The local probe processes sells
after buys for the same morning, so the extra slot is not visible when the
buy decision is made. This is a pure execution-order issue (not a data
issue), but it cascades from earlier November divergence which itself
cascades from the July cluster.

### Hypothesis Tested and Rejected

**Scorpion/base exclusion hypothesis**: Theory was that JQ excludes
candidates that also pass the YJJ base filter from the scorpion list. Adding
`bear_cands = [c for c in bear_cands if c not in set(base)]` changed
32/48 → 40/50 (made results worse). Specifically, 002060 and 002596 on
2022-04-28 pass the base filter but JQ trades them as scorpion. The
hypothesis is WRONG. Change was immediately reverted.

### Summary Table of Remaining Gaps

| Date | Side | Stocks | Root Cause | Fixable |
| --- | --- | --- | --- | --- |
| 2022-03-18 | local-only (2 rows) | 002422 scorpion | Price data diff | No |
| 2022-06-16 | local-only (4 rows) | 000025, 000987 | fb_hist state divergence | No |
| 2022-07-05 | local-only (20+ rows, cascades) | 600477, 603127 | avg_chg or filter diff, TBD | Unknown |
| 2022-12-20 | JQ-only (6 rows, cascades) | 603538, 000983 | 09:30 sell/buy order | Partial |

### Recommended Next Steps

1. **avg_chg investigation**: Compare the exact avg_chg formula between the
   local hdata implementation and the JoinQuant mother code. Check if JQ
   computes `money/vol` as a VWAP or uses a different bar. This is the most
   tractable remaining hypothesis for the 07-05 cluster.

2. **09:30 execution order for December**: Implement the JQ behavior where
   09:30 stop-loss exits are processed before the same-morning buy queue is
   checked for slot availability. This should fix the December cascade, but
   the November cascade (which triggers it) still needs the July fix first.

3. **Accept residual gap**: If avg_chg difference cannot be confirmed
   without JQ source code, the gap may be structurally unavoidable. The
   current 32/48 gap (14% of rows) is mostly concentrated in a single July
   cascade. The 2020–2022 optimization period can still proceed with this
   known caveat documented.

## 2026-05-23 New Direction: State-Machine First

Previous DIAG attempts drifted into copying/replacing JoinQuant buy logic,
which is too risky for verification. New rule: **JoinQuant mother copies may
only add observer logs and must not rewrite strategy decisions**.

Generated observer copy:

- `母版-20260506-Clone-状态机观察.py`
- Generated by `scripts/make_state_observer_master.py`
- Logs `[SM-STATE]`, `[SM-CANDS]`, `[SM-CAND]`, `[SM-ACTION]`, `[SM-PFB]`
- Wrapper-only: calls original `prepare_all`, `buy_v227_一进二`,
  `buy_v227_天蝎座`, and v227 sell functions before/after logging.

Local anchor explanation:

- `scripts/v227_yjj_probe.py` now supports:
  - `--explain-jq-raw jq_force_v227_2022_raw.txt`
  - `--explain-out explain_jq_buy_days_2022.csv`
  - `--force-v227-route` to mimic branch-test `force_v227` routing
- The output explains every JQ buy against local state/candidates instead of
  comparing final results first.
- `scripts/explain_with_jq_positions.py` reclassifies JQ buys using local
  candidates/state but replayed JQ positions, removing local-only position
  cascades from the diagnosis.

Current 2022 force-v227 buy explanation result:

| Reason | Count |
| --- | ---: |
| local_bought | 102 |
| no_slot | 2 |
| no_slot_after_prior_candidates | 2 |
| blocked_cautious_pct_040_060 | 2 |
| not_enabled | 1 |
| no_candidate | 1 |

After enabling `--force-v227-route`, `2022-07-06 000709.XSHE` changes from
`not_enabled` to `no_slot`, proving that part of the gap was local using the
normal mother route while the JQ transaction file is `force_v227`.

After replaying JQ positions:

| JQ-position reason | Count |
| --- | ---: |
| local_bought | 102 |
| cascade_slot_only | 4 |
| local_state_poison_block | 2 |
| candidate_order_or_filter_mismatch | 1 |
| no_candidate | 1 |

The 2022-09-21 `002377.XSHE` split was fixed locally. It was in first boards,
but the bear-scorpion 60-day location filter computed exactly `0.5` as
`0.500000165...` from float32 hdata and dropped it under a strict `<=0.5`
check. The local threshold now uses `<=0.500001`.

The remaining 8 unmatched JQ buys are now small enough to inspect directly:

| Date | Code | Path | Local Explanation |
| --- | --- | --- | --- |
| 2022-04-07 | 600661.XSHG | scorpion | cascade slot only |
| 2022-05-10 | 600822.XSHG | scorpion | candidate order/filter mismatch |
| 2022-07-06 | 000709.XSHE | yjj | cascade slot only after force route |
| 2022-07-08 | 002101.XSHE | yjj | cascade slot only |
| 2022-11-22 | 002432.XSHE | yjj | local cautious poison-band block |
| 2022-12-20 | 000983.XSHE | scorpion | no_candidate |
| 2022-12-23 | 600779.XSHG | yjj | local cautious poison-band block |
| 2022-12-27 | 002518.XSHE | yjj | cascade slot only |

Layer check:

- `600661`, `600822`, `002101`, `002432`, `600779`, `002518` are present in
  the relevant local candidate pools; differences are state/slot/order, not
  first-board data.
- `000709` is present in local yjj candidates, but local route has
  `active=rzq+zb` while JQ force-v227 still buys it. This is a run-mode
  mismatch, not candidate data.
- `000983` is not in local 2022-12-19 daily data, so it cannot be a local
  previous-day first-board candidate. hdata has 2022-12-16 and 2022-12-20 but
  no 2022-12-19 row for this stock. Keep this as a data/trading-status
  discrepancy unless later JQ state proves otherwise.

Local-only buy replay against JQ positions shows that most local-only buys
would also have had slots in the JQ portfolio:

- `local_only_buy_jqpos_layers.csv`
- 18/20 local-only buys would be reachable with JQ slots.
- Therefore the dominant remaining issue is not merely position cascade; it is
  local candidate/state over-inclusion on certain dates, especially the July
  and August bull clusters.

Next comparison should use the JoinQuant observer log from
`母版-20260506-Clone-状态机观察.py` and parse it with
`scripts/parse_jq_sm_log.py`. This will identify whether the 9 residual
splits are true candidate-generation differences, route/state differences, or
execution-order differences.

## 2026-05-24 continuation update

The JoinQuant observer-log route is paused. Multiple injected mother copies
produced no useful output in JQ, while the unmodified branch backtest still
runs. Do not spend more time on broad JQ log injection unless there is a new
reason.

Current best local baseline remains:
`--force-v227-route --include-scorpion --sell-time-shift 0`, with cooldown
simulation disabled. Cooldown state is intentionally gated behind
`--simulate-cooldowns` because local-only buys poison later cooldowns before
candidate parity is solved. `fq='pre'` handling has been applied to scorpion
60-day closes and relevant historical price windows.

Latest best comparison (`diag_base` / `tmp_fqpre_nocd`) is: JQ rows 220,
local rows 244, JQ-only 16 rows, local-only 40 rows. With JQ position replay,
JQ buys classify as:

| JQ-position reason | Count |
| --- | ---: |
| local_bought | 102 |
| cascade_slot_only | 4 |
| local_state_poison_block | 2 |
| candidate_order_or_filter_mismatch | 1 |
| no_candidate | 1 |

Diagnostic scorpion ST/退 filters were tested and rejected as global fixes:

| Variant | JQ-only rows | Local-only rows | JQ buys local_bought | Note |
| --- | ---: | ---: | ---: | --- |
| `diag_base` | 16 | 40 | 102 | Current best |
| `--scorpion-st-list-filter` | 30 | 40 | 95 | Bad: removes JQ's real ST buys |
| `--scorpion-delist-name-filter` | 26 | 40 | 97 | Bad: removes JQ's real delist/ST buys |

Conclusion: the early scorpion mismatch cannot be fixed by a blanket ST or
delist-name exclusion. JQ clearly bought several ST/delist names in 2022
(`600091`, `600093`, `600146`, `600856`, `002684`, etc.).

Added diagnostic flags to `scripts/v227_yjj_probe.py`:
`--scorpion-st-list-filter` and `--scorpion-delist-name-filter`. Defaults
preserve baseline behavior; these are only for experiments.

Added `scripts/jq_probe_scorpion_cases.py` (82 lines) for JQ research. It
prints, for a few mismatch dates, JQ `display_name`, first-board membership,
bear-pool membership, final bear candidate membership, day open/open_pct, and
60-day position. This is the next targeted JQ data request if local evidence
stalls.

Current local findings on root mismatches:

- `2022-03-18 002422.XSHE` is a non-ST local scorpion candidate. Local
  previous close is within 0.01 of calculated high-limit, 60-day position is
  `0.4246`, and local open_pct is `-3.46%`, so it passes all known mother
  scorpion checks. JQ bought only `600257.XSHG`, so this likely requires JQ
  high_limit/display_name/bear-pool confirmation.
- `2022-05-10 002952.XSHE` is also a non-ST local scorpion candidate. Local
  open_pct is `-3.83%`; JQ instead bought `600822.XSHG`. This is a genuine
  candidate order/filter mismatch, not a slot issue.
- `2022-12-20 000983.XSHE` remains a local data/trading-status discrepancy:
  hdata has no 2022-12-19 daily row, so local cannot identify it as a previous
  first-board candidate.

Update after targeted JQ scorpion probe:

- JQ research confirmed `2022-03-18 002422.XSHE` was **not** in first boards:
  JQ printed `cr=[15.61,16.02,17.61]`, `hl=[18.32,17.17,17.62]`,
  `in_fb=False`. The printed one-cent gap `17.61` vs `17.62` is excluded by
  JQ's float `abs(cr[-1] - hl[-1]) <= 0.01` edge behavior.
- JQ also confirmed `2022-04-06 600146.XSHG` was not in first boards:
  `cr=[1.97,1.96,2.05]`, `hl=[2.09,2.07,2.06]`, `in_fb=False`.
- JQ confirmed `2022-05-10 002952.XSHE` was a real bear candidate, but after
  fixing the one-cent first-board edge earlier local cascade changes the
  available cash/slots so the `600822.XSHG` mismatch disappears.
- `scripts/v227_yjj_probe.py` now mimics JQ's float edge behavior when
  `tol=0.01` (bear `_scan_boards_for_prev`) while keeping the integer
  two-cent behavior for `tol=0.02` scans. This specifically targets the JQ
  one-cent-below-high-limit exclusion seen in the research output.
- New run `diag_floatbear`:

| Metric | `diag_base` | `diag_floatbear` |
| --- | ---: | ---: |
| Local rows | 244 | 242 |
| JQ-only rows | 16 | 18 |
| Local-only rows | 40 | 40 |
| matched price/share diffs | 200 | 198 |
| JQ buys local_bought after JQ-position replay | 102 | 101 |
| candidate_order_or_filter_mismatch | 1 | 0 |

- The apparent JQ-only row increase is not a candidate regression; it exposes
  later July force-route slot cascades (`603876`, `002261`, `002745`) after
  early scorpion false positives are removed. The important improvement is
  that the known early scorpion false positives (`002422`, `600146`, `002952`)
  disappear from local-only and `600822` is no longer JQ-only.

Update after JQ fb_perf override test:

- Added `--jq-fb-perf-override` to `scripts/v227_yjj_probe.py`. It uses the
  already-collected `jq_fb_perf_jun_aug.json` only on covered dates instead of
  globally propagating NaN.
- Run `diag_floatbear_jqfb` is the best alignment so far:

| Metric | `diag_floatbear` | `diag_floatbear_jqfb` |
| --- | ---: | ---: |
| Local rows | 242 | 240 |
| JQ-only rows | 18 | 8 |
| Local-only rows | 40 | 28 |
| matched price/share diffs | 198 | 202 |
| JQ buys local_bought after JQ-position replay | 101 | 106 |
| candidate_order_or_filter_mismatch | 0 | 0 |

- Remaining unmatched JQ buys after JQ-position replay:

| Date | Code | Path | Reason |
| --- | --- | --- | --- |
| 2022-11-22 | 002432.XSHE | yjj | local cautious poison-band block |
| 2022-12-20 | 000983.XSHE | scorpion | no candidate due to hdata daily gap / paused high_limit semantics |
| 2022-12-23 | 600779.XSHG | yjj | local cautious poison-band block |
| 2022-12-27 | 002518.XSHE | yjj | slot cascade after local-only `002093` |

- `000983.XSHE` data diagnosis: hdata daily has no `20221219` row, but hdata
  minute has 241 zero-volume bars at fixed price `12.71`. JQ daily history for
  the same day reports `close=12.71` and `high_limit=12.71`, so it recognizes
  `000983` as a previous first-board candidate on `20221220`. Local cannot
  reproduce this by simply computing limit from `pre_close * 1.1`; paused-day
  `high_limit` needs separate semantics (`high_limit == close` for the
  zero-volume fixed-price day).
- Added `scripts/jq_probe_fb_state_cases.py` (62 lines) for JQ research to
  print `fb_perf/fb_pct` around the remaining November/December mismatches.

Follow-up on November/December state probing:

- `jq_probe_target_pfb_fast.py` with `TARGET_DATE='2022-11-22'` printed
  `PFB_N=44` and `FB_PERF=-0.021337`. This is valid, but it measures
  `2022-11-21` first boards into `2022-11-22`; it is **not** the fb_perf used
  by the mother strategy at `2022-11-22 09:05`.
- Mother timing reminder: `prepare_all` calls `calc_fb_perf` before scanning
  the latest previous day. Thus the mother state on `2022-11-22` uses the
  first boards saved by the previous prepare call, i.e. `2022-11-18` first
  boards into `2022-11-21`. To probe that with the fast script, set
  `TARGET_DATE='2022-11-21'`.
- Added this timing note to `scripts/jq_probe_target_pfb_fast.py`.
- Diagnostic run `diag_jqfb_nopoison` (`--disable-cautious-poison`) is not a
  good global fix. It explains the two cautious JQ buys but worsens local-only
  rows from 28 to 46 and creates new slot cascades. Keep cautious poison enabled
  in the reference baseline until JQ fb_pct history proves otherwise.

Update after JQ batch fb_pct probe:

- JQ `TARGET_PERF_DATE='2022-11-21'` (mother state on `2022-11-22`) printed
  `fb_perf=0.01756313704751912`, `fb_pct=0.600000`, `pfb_n=43`.
- This explains `2022-11-22 002432.XSHE`: JQ is exactly at the upper boundary
  and the mother block is `[0.4, 0.6)`, so JQ does not block. Local had
  `fb_pct=0.583333` due to history/PFB data differences and blocked it.
- Added `jq_fb_state_overrides.json` and `--jq-fb-state-override` to
  `scripts/v227_yjj_probe.py`. Current override:
  `20221122 first_board_perf=0.01756313704751912, fb_pct=0.6`.
- Run `diag_jqfb_state`:

| Metric | `diag_floatbear_jqfb` | `diag_jqfb_state` |
| --- | ---: | ---: |
| Local rows | 240 | 242 |
| JQ-only rows | 8 | 6 |
| Local-only rows | 28 | 28 |
| JQ buys local_bought after JQ-position replay | 106 | 107 |

- Remaining unmatched JQ buys:
  `20221220 000983.XSHE` (paused daily/high_limit semantics),
  `20221223 600779.XSHG` (likely another fb_pct boundary),
  `20221227 002518.XSHE` (slot cascade after local-only `002093`).
- `scripts/jq_probe_fb_pct_batch.py` target changed to
  `TARGET_PERF_DATE='2022-12-22'`, corresponding to mother state
  `2022-12-23`.

Update after 2022-12-23 JQ fb_pct:

- JQ `TARGET_PERF_DATE='2022-12-22'` printed
  `fb_perf=0.003152521361764445`, `fb_pct=0.316667`, `pfb_n=34`.
- Added `20221223` to `jq_fb_state_overrides.json`. This explains
  `2022-12-23 600779.XSHG`: JQ is outside the cautious poison band; local had
  `fb_pct=0.583333` and blocked it.
- Run `diag_jqfb_state2`:

| Metric | `diag_jqfb_state` | `diag_jqfb_state2` |
| --- | ---: | ---: |
| Local rows | 242 | 244 |
| JQ-only rows | 6 | 4 |
| Local-only rows | 28 | 28 |
| JQ buys local_bought after JQ-position replay | 107 | 108 |

- Remaining unmatched JQ buys:
  `20221220 000983.XSHE` (paused daily/high_limit semantics),
  `20221227 002518.XSHE` (slot cascade after local-only `20221226 002093`).
- Local 2022-12-26 state has one free v227 slot while still holding `600779`;
  `v130_codes=000029.XSHE|002093.XSHE`. `000029` fails open filter
  (`open_pct=-3.07%`), `002093` passes (`open_pct=+1.08%`) and local buys it.
  JQ did not buy it, so the next targeted probe is the JQ 2022-12-26 yjj chain.
- Added `scripts/jq_probe_yjj_day_fast.py` (97 lines) for that 2022-12-26
  candidate/open-filter check.

Next work order:

1. Keep `diag_base` as the reference baseline.
2. Use the targeted JQ scorpion probe when the user can run it; do not use
   broad injected strategy logs.
3. Continue local-only root analysis for July/August yjj clusters, because most
   local-only buys are still reachable under JQ positions and therefore reflect
   local candidate/state over-inclusion rather than just slot cascade.

Additional state-machine finding:

- Parsed usable `[DIAG-STATE]` rows already present in `jq_diag_full.txt`
  (normal-route log, 65 rows covering 2022-06 to 2022-08). These are not the
  force-v227 transaction run, but they reveal real JQ state values for the same
  mother code.
- JQ normal-route NaN days in this log: `20220629`, `20220705`, `20220721`.
  Example: on `20220705`, JQ has `first_board_perf=NaN`, `fb_pct=0.0`,
  `active=rzq+zb`, `enable_v227=False`; local baseline has
  `first_board_perf=0.02741756`, `fb_pct=0.733333`, and force route enables
  v227. This explains why local force mode buys `600477/002145` on a day where
  JQ normal state would block v227.
- However, enabling local `--jq-na-propagation` globally is not acceptable:
  `diag_jqna_force` worsens to JQ-only 52 rows and local-only 50 rows. It
  blocks many JQ real buys in June/July. Treat JQ NaN as a local discrepancy to
  investigate, not as a global switch.
- July/August local-only yjj clusters line up strongly with normal-route JQ
  `active=rzq+zb` days. Since the user transaction file is force-v227 but does
  not buy every such local force candidate, the remaining ambiguity is in the
  exact branch-test/run-mode used for the JQ transaction history, not only in
  candidate generation.
