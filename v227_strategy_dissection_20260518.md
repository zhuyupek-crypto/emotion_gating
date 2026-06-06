# v227 Strategy Dissection Baseline

Created: 2026-05-18

This is the working baseline for dissecting the v227 strategy. The goal is
not to prove the strategy good yet, but to separate signal, regime filter,
position logic, exit logic, and data-source sensitivity.

## Current Research Object

Primary object:

- Pure v227 local hdata version.

Currently included:

- 一进二
- 天蝎座
- 龙头保护
- v227 scheduled exits
- local hdata-native minute bars

Currently excluded:

- rzq
- zb
- auction_yiqian
- JoinQuant exact minute/cost alignment
- order-book liquidity model

Main script:

- `scripts/v227_yjj_probe.py`

Main record:

- `v227_yjj_baseline_20260518.md`

## Reproducible Baselines

Training sample:

- 2020-01-01 to 2023-12-31
- warmup starts 2019-10-01
- Used for dissection and tuning.

Validation sample:

- 2024-01-01 onward
- Not to be optimized on.

YJJ only:

```powershell
python scripts\v227_yjj_probe.py --start 20200101 --end 20231231 --warmup 20191001 --sell-time-shift 0 --trades-out out_v227_train_2020_2023_yjj_trades.csv --equity-out out_v227_train_2020_2023_yjj_equity.csv
python scripts\v227_yjj_probe.py --start 20240101 --end 20241231 --warmup 20231001 --sell-time-shift 0 --trades-out out_v227_hdata_2024_trades.csv --equity-out out_v227_hdata_2024_equity.csv
python scripts\v227_yjj_probe.py --start 20250101 --end 20251231 --warmup 20241001 --sell-time-shift 0 --trades-out out_v227_hdata_2025_trades.csv --equity-out out_v227_hdata_2025_equity.csv
python scripts\v227_yjj_probe.py --start 20260101 --end 20260515 --warmup 20251001 --sell-time-shift 0 --trades-out out_v227_hdata_2026_trades.csv --equity-out out_v227_hdata_2026_equity.csv
```

Pure v227 extension:

```powershell
python scripts\v227_yjj_probe.py --start 20200101 --end 20231231 --warmup 20191001 --sell-time-shift 0 --include-scorpion --leader-protect --trades-out out_v227_train_2020_2023_full_trades.csv --equity-out out_v227_train_2020_2023_full_equity.csv
python scripts\v227_yjj_probe.py --start 20240101 --end 20241231 --warmup 20231001 --sell-time-shift 0 --include-scorpion --leader-protect --trades-out out_v227_full_hdata_2024_trades.csv --equity-out out_v227_full_hdata_2024_equity.csv
python scripts\v227_yjj_probe.py --start 20250101 --end 20251231 --warmup 20241001 --sell-time-shift 0 --include-scorpion --leader-protect --trades-out out_v227_full_hdata_2025_trades.csv --equity-out out_v227_full_hdata_2025_equity.csv
python scripts\v227_yjj_probe.py --start 20260101 --end 20260515 --warmup 20251001 --sell-time-shift 0 --include-scorpion --leader-protect --trades-out out_v227_full_hdata_2026_trades.csv --equity-out out_v227_full_hdata_2026_equity.csv
```

## Baseline Results

| Sample | Version | Period | Sells | Return | Max drawdown | Win rate | Avg trade | Median trade | Best | Worst |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Train | YJJ only | 2020-2023 | 413 | -32.00% | -58.88% | 50.61% | 0.13% | 0.16% | 28.93% | -21.35% |
| Train | Pure v227 | 2020-2023 | 467 | -22.43% | -65.04% | 53.53% | 0.49% | 0.62% | 28.93% | -21.35% |
| Validation | YJJ only | 2024 | 80 | 49.68% | -30.03% | 55.00% | 1.52% | 0.88% | 29.11% | -20.48% |
| Validation | YJJ only | 2025 | 142 | 113.04% | -21.26% | 55.63% | 1.34% | 0.52% | 45.67% | -14.62% |
| Validation | YJJ only | 2026-01-01 to 2026-05-15 | 57 | 44.71% | -13.79% | 54.39% | 1.61% | 0.43% | 44.09% | -12.48% |
| Validation | Pure v227 | 2024 | 96 | 83.76% | -31.94% | 56.25% | 1.75% | 1.03% | 29.11% | -20.48% |
| Validation | Pure v227 | 2025 | 148 | 201.41% | -21.53% | 58.11% | 1.77% | 0.75% | 46.06% | -14.62% |
| Validation | Pure v227 | 2026-01-01 to 2026-05-15 | 57 | 46.19% | -12.91% | 54.39% | 1.65% | 0.43% | 46.45% | -12.48% |

## Training Sample Breakdown

Yearly training results:

| Version | Year | Sells | Return | Max drawdown | Win rate |
| --- | --- | ---: | ---: | ---: | ---: |
| YJJ only | 2020 | 103 | 3.43% | -35.08% | 52.43% |
| YJJ only | 2021 | 147 | 23.06% | -34.72% | 51.02% |
| YJJ only | 2022 | 94 | -27.66% | -33.32% | 47.87% |
| YJJ only | 2023 | 69 | -26.86% | -37.53% | 50.72% |
| Pure v227 | 2020 | 110 | -10.95% | -36.40% | 52.73% |
| Pure v227 | 2021 | 156 | -11.54% | -53.80% | 54.49% |
| Pure v227 | 2022 | 122 | 4.05% | -24.80% | 53.28% |
| Pure v227 | 2023 | 79 | -8.83% | -22.13% | 53.16% |

Reason counts in training sample:

| Reason | YJJ only | Pure v227 |
| --- | ---: | ---: |
| `v227_yjj` buys | 413 | 409 |
| `v227_scorpion` buys | 0 | 59 |
| `morning_profit` sells | 192 | 232 |
| `midday_loss` sells | 148 | 156 |
| `eod_clear` sells | 61 | 67 |
| `leader_exit` sells | 0 | 1 |
| `stop_loss` sells | 12 | 11 |

Training interpretation:

- 2020-2023 is a hard sample: both current variants lose money overall.
- Pure v227 improves average trade and win rate, but does not solve drawdown.
- 天蝎座 helps 2022/2023 relative to YJJ, but hurts 2020/2021 in this form.
- This sample is suitable for dissection because it is not flattering.

## Initial Interpretation

The strategy does not collapse under local hdata. That matters because the
JoinQuant and hdata minute bars differ at some key sell timestamps.

At the same time, this is not a clean, low-volatility edge:

- returns are concentrated in several strong windows;
- drawdown is large, especially 2024;
- median trade is modest, so a few large winners matter;
- minute-bar differences can flip individual trade outcomes;
- the current local version still lacks some mother-strategy portfolio state.

Working stance:

- worth dissecting further;
- not yet suitable for acceptance as a robust deployable strategy.

## 2026-05-25 Baseline Reset

We stopped the earlier "chase every residual 2022 mismatch" thread and
reset the research baseline around an explicit local hdata force-v227
object.

Important command convention:

- `--no-scorpion` means 一进二 only.
- `--include-scorpion --force-v227-route` means the current force-v227
  research object.
- JoinQuant fb override files are for alignment diagnostics only and are
  not used in this research baseline.

The script default currently includes scorpion, so research commands should
always pass the branch switch explicitly.

Current training run is yearly independent, not one continuous compounded
2020-2023 path. This was chosen because the 4-year single run is still slow
and because yearly runs give enough signal for first-pass dissection.

Commands used:

```powershell
python scripts\v227_yjj_probe.py --start 20200101 --end 20201231 --warmup 20191001 --sell-time-shift 0 --force-v227-route --include-scorpion --trades-out research_train_2020_force_v227_trades.csv --equity-out research_train_2020_force_v227_equity.csv --state-out research_train_2020_force_v227_state.csv
python scripts\v227_yjj_probe.py --start 20210101 --end 20211231 --warmup 20201001 --sell-time-shift 0 --force-v227-route --include-scorpion --trades-out research_train_2021_force_v227_trades.csv --equity-out research_train_2021_force_v227_equity.csv --state-out research_train_2021_force_v227_state.csv
python scripts\v227_yjj_probe.py --start 20220101 --end 20221231 --warmup 20211001 --sell-time-shift 0 --force-v227-route --include-scorpion --trades-out research_train_2022_force_v227_trades.csv --equity-out research_train_2022_force_v227_equity.csv --state-out research_train_2022_force_v227_state.csv
python scripts\v227_yjj_probe.py --start 20230101 --end 20231231 --warmup 20221001 --sell-time-shift 0 --force-v227-route --include-scorpion --trades-out research_train_2023_force_v227_trades.csv --equity-out research_train_2023_force_v227_equity.csv --state-out research_train_2023_force_v227_state.csv
python scripts\summarize_research_baseline.py
```

Generated files:

- `research_train_2020_2023_force_v227_summary.md`
- `research_train_2020_2023_force_v227_sells_enriched.csv`
- `research_train_2020_2023_force_v227_yearly.csv`
- `research_train_2020_2023_force_v227_by_branch.csv`
- `research_train_2020_2023_force_v227_by_exit.csv`
- `research_train_2020_2023_force_v227_by_mode.csv`
- `research_train_2020_2023_force_v227_by_fbpct.csv`
- `research_train_2020_2023_force_v227_monthly.csv`

Updated training summary:

| Year | Sells | Return | Max drawdown | Win rate | Avg trade | Median trade |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 2020 | 97 | -19.67% | -40.25% | 44.33% | -0.13% | -1.28% |
| 2021 | 143 | 90.50% | -17.08% | 52.45% | 1.10% | 0.50% |
| 2022 | 121 | 23.24% | -22.49% | 52.07% | 0.59% | 0.63% |
| 2023 | 71 | -25.20% | -32.42% | 56.34% | -0.67% | 0.89% |
| Annual-reset aggregate | 432 | 41.05% | n/a | 51.16% | 0.39% | 0.25% |

Branch quality:

| Entry branch | Sells | Win rate | Avg trade | Median trade | Best | Worst |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `v227_yjj` | 365 | 48.22% | 0.06% | -0.73% | 46.70% | -24.29% |
| `v227_scorpion` | 67 | 67.16% | 2.18% | 1.90% | 21.25% | -10.28% |

Exit quality:

| Exit reason | Sells | Win rate | Avg trade | Median trade |
| --- | ---: | ---: | ---: | ---: |
| `morning_profit` | 204 | 100.00% | 5.87% | 4.43% |
| `midday_loss` | 107 | 0.00% | -4.86% | -4.54% |
| `eod_clear` | 66 | 25.76% | -0.77% | -0.99% |
| `stop_loss` | 55 | 0.00% | -8.32% | -7.22% |

Initial reading:

- 天蝎座 is the cleaner branch in 2020-2023.
- 一进二 has large right-tail winners but poor median trade; it needs
  further filtering or position throttling.
- `cautious` entries are weak in aggregate; `bear` entries are strong
  because they are basically the 天蝎座 set.
- The biggest bad months are 2020-08, 2022-01, 2020-02, 2023-11, and
  2023-12. These are now the first risk-case months for dissection.

Follow-up YJJ decomposition:

- Added entry-gap buckets using entry price vs previous daily close.
- Added YJJ-specific yearly/mode/fb_pct/entry-gap/monthly tables.
- Added simple trade-level filter cases in
  `research_train_2020_2023_force_v227_yjj_filter_cases.csv`.

YJJ entry-gap result:

| Entry gap | Sells | Win rate | Avg trade | Median trade |
| --- | ---: | ---: | ---: | ---: |
| `0~2%` | 180 | 51.11% | 0.21% | 0.38% |
| `2~4%` | 101 | 37.62% | -0.77% | -2.63% |
| `4~6%` | 39 | 61.54% | 1.89% | 1.16% |
| `>6%` | 13 | 46.15% | -1.29% | -3.91% |
| `-2~0%` | 32 | 50.00% | 0.20% | -0.86% |

Trade-level filter cases:

| Case | Sells | Win rate | Avg trade | Median trade |
| --- | ---: | ---: | ---: | ---: |
| all_yjj | 365 | 48.22% | 0.06% | -0.73% |
| drop_gap_2_4 | 264 | 52.27% | 0.38% | 0.48% |
| drop_gap_2_4_gt6 | 251 | 52.59% | 0.47% | 0.51% |
| drop_cautious | 239 | 48.54% | 0.35% | -0.87% |
| drop_cautious_and_bad_gap | 156 | 53.21% | 0.87% | 0.54% |
| keep_fb_20_40_or_gap_4_6 | 122 | 56.56% | 1.68% | 1.41% |

Interpretation:

- The YJJ drag is not simply "high open is bad"; `4~6%` is strong while
  `2~4%` and `>6%` are weak.
- The `2~4%` gap looks like the first concrete suspect: enough trades,
  poor win rate, and poor median.
- `keep_fb_20_40_or_gap_4_6` is too selective to accept as a rule, but it
  suggests that moderate first-board sentiment plus stronger auction
  confirmation may be the cleaner part of YJJ.
- These are trade-level diagnostics, not yet portfolio-level rule tests.

Portfolio-level diagnostic:

- Added `--yjj-exclude-open-ranges` to `scripts/v227_yjj_probe.py`.
- Tested skipping YJJ entry gaps `0.02:0.04,0.06:1` while keeping
  scorpion unchanged.
- 2020 result worsened from -19.67% to -59.06%.

This rejects the naive "drop weak entry-gap buckets" rule for now. The
trade-level table was useful for locating a suspect, but the portfolio path
depends heavily on large winners, cash timing, and slot cascades. Any
entry-gap rule must be tested as a full path, not as a static sell-sample
filter.

## 2026-05-25 JoinQuant Force-v227 Gap

User ran `母版-20260506-Clone-强制单分支回测.py` on JoinQuant:

| Year | JoinQuant return | JoinQuant max drawdown | Local force-v227 return | Local max drawdown |
| --- | ---: | ---: | ---: | ---: |
| 2020 | 68.16% | 20.39% | -19.67% | -40.25% |
| 2021 | 81.96% | 32.59% | 90.50% | -17.08% |
| 2022 | 19.55% | 24.17% | 23.24% | -22.49% |
| 2023 | -19.06% | 31.67% | -25.20% | -32.42% |

This changes the confidence label. The local version is not yet a complete
replica of the mother force-v227 branch. It is a hdata-native approximation
that is directionally close in 2021-2023 but badly wrong in 2020.

Tested a more mother-like local 2020 run:

```powershell
python scripts\v227_yjj_probe.py --start 20200101 --end 20201231 --warmup 20191001 --sell-time-shift 0 --force-v227-route --include-scorpion --leader-protect --simulate-cooldowns --trades-out research_jq_like_2020_force_v227_trades.csv --equity-out research_jq_like_2020_force_v227_equity.csv --state-out research_jq_like_2020_force_v227_state.csv
```

Result: -49.63%, worse than the bare local force-v227. Therefore the 2020
gap is not solved by simply enabling cooldown and leader protection. Next
alignment step should go back to JoinQuant 2020 transaction history and
compare trades from the top down.

Correction after review:

The next alignment step should not start from trade history. Trade history is
too path-dependent and mixes candidate state, execution, holding slots, exits,
and data differences. The proper order is state-machine alignment first.

State-machine alignment artifacts:

- `scripts/make_force_v227_state_observer.py`
- `母版-20260506-Clone-强制单分支回测-状态机观察.py`
- `scripts/parse_jq_sm_log.py`
- `scripts/compare_state_machine_alignment.py`

The observer is generated from `母版-20260506-Clone-强制单分支回测.py`, not the
normal mother file. It logs `SM-STATE`, `SM-PFB`, `SM-CANDS`, `SM-CAND`, and
`SM-ACTION` without changing strategy logic.

Alignment order:

1. Compare `prepare_all:after` only:
   raw/actual market mode, active route, slots, cooldowns, fb_perf, fb_pct,
   prev_first/yjj/bear counts.
2. Compare candidate sets:
   PFB, YJJ, scorpion.
3. Compare pre-buy blocking state:
   held count, slots, cooldowns, open limits and paused flags.
4. Only after these match, compare trade records and PnL.

2020 state-machine log received:

- Source zip: `20200101-20201231状态机日志.zip`
- Parsed files:
  - `jq_sm_force_v227_2020_state.csv`
  - `jq_sm_force_v227_2020_pfb.csv`
  - `jq_sm_force_v227_2020_cands.csv`
  - `jq_sm_force_v227_2020_cand.csv`
  - `jq_sm_force_v227_2020_action.csv`

Fixes found from state alignment:

1. GEM limit rule was wrong before 2020-08-24.
   Local code applied 20% to all `30xxx`; JoinQuant uses 10% before the
   2020-08-24 reform. This caused the first large 2020 PFB mismatch.
2. Local ST table has isolated missing trading days, e.g. 2020-01-02.
   Treating missing days as no ST broke high-limit reconstruction. Added
   forward fill across trading days.
3. IPO first-day +44% must count as a limit day when deciding whether the
   next day is "first board". This removed local-only IPO second-day false
   first boards such as `603109`.
4. The delist-transition map incorrectly marked future delisted stocks as
   being in transition when the run window ended before their delist date.
   Fixed by ignoring delist dates outside the loaded trade-date range.
5. The first observer limited PFB lists to 80 names; this is insufficient for
   set-level comparison. Updated `SM_CAND_LIMIT` to 1000 for future runs.

Important correction:

- Earlier `missing_prev_daily` was described too broadly as local data
  missing. That was wrong for many cases.
- In JoinQuant, `history(count=...)` may use the stock's recent effective bars
  rather than requiring a row on the global previous trading day. Local hdata
  has no row on suspended days, so a calendar-slice implementation falsely
  classifies those names as missing.
- A naive local implementation that always skips suspended days is also not
  sufficient: it over-includes long-suspended or already-delisted stale bars
  such as `002680` and `600610`, and can change consecutive-board judgement
  across suspended days.
- Therefore the remaining task is not simply "fill missing daily rows"; it is
  to reproduce JoinQuant's exact `history`/pause semantics for scan inputs.
  This must be solved at the state-machine layer before accepting trade PnL.

Current 2020 local run after the state fixes:

```powershell
python scripts\v227_yjj_probe.py --start 20200101 --end 20201231 --warmup 20191001 --sell-time-shift 0 --force-v227-route --include-scorpion --trades-out research_train_2020_force_v227_statefix_trades.csv --equity-out research_train_2020_force_v227_statefix_equity.csv --state-out research_train_2020_force_v227_statefix_state.csv
```

Result: -43.39%, still not close to JoinQuant PnL. This is expected because
we are still aligning the state machine, not trading PnL.

State alignment after fixes:

- 2020-01-02 PFB count improved from local 29 to local 39 vs JoinQuant 40.
- Remaining 2020-01-02 difference is `603799.XSHG`, caused by missing local
  daily data on 2019-12-31.
- 2020-01-03 PFB count improved from local 44 to local 75 vs JoinQuant 78.
- Across 2020, market_mode differs on 2 days, raw_market_mode on 12 days,
  PFB count on 202 days, with mean absolute PFB count difference about 2.2.

Next state task:

- Rerun JoinQuant observer with the updated `SM_CAND_LIMIT=1000` only if
  full set comparison is needed.
- Before rerunning, continue with count-level and early untruncated dates:
  isolate whether remaining differences are hdata daily missing rows, index
  history differences, or state feedback from buys/sells.

## Strategy Anatomy

### 1. Universe And Exclusions

Current rules:

- exclude STAR board `688`;
- exclude Beijing board / `8` prefix;
- filter ST / name contains ST / `*`;
- IPO age filter;
- market cap filter for YJJ;
- different board restrictions for 天蝎座.

Questions:

- How much return comes from excluding recent IPOs?
- Is market cap range doing real work or just curve fitting?
- Does excluding `300` in 天蝎座 matter?

### 2. Regime Filter

Main components:

- 中证1000 trend state;
- 20-day drawdown bear override;
- MA20 / MA60 relation;
- days above MA60;
- first-board performance;
- fb_pct rank;
- bull sticky state.

Questions:

- Is the regime filter adding return or mainly reducing drawdown?
- Which part matters: index trend, first-board performance, or fb_pct?
- Does bull sticky help or add delayed risk?

### 3. Entry Signal: 一进二

Main components:

- yesterday first board;
- yesterday money threshold;
- average-price strength filter;
- bull-mode high money cap;
- v122 blast-volume/new-high filter;
- v130 tail-seal filter;
- next-day open gap range;
- low-price tilt / bull left-pressure score.

Questions:

- Which filter removes the most losers?
- Which filter removes the most winners?
- Does v130 tail-seal filter survive hdata minute source?
- Is open gap range robust to small perturbations?

### 4. Entry Signal: 天蝎座

Main components:

- only bear mode;
- yesterday main-board first board;
- 60-day position <= 0.5;
- next-day open between -4% and -3%;
- low-price ordering.

Questions:

- Is 天蝎座 a genuine separate edge or just bear-market rebound beta?
- Why does it help 2024/2025 but not 2026 so far?
- Is the -4% to -3% low-open window too narrow?

### 5. Exit Logic

Main components:

- 11:25 profit sell unless still limit or leader;
- 13:01 <= -2% sell unless leader;
- intraday <= -5% stop;
- 14:50 clear unless still limit;
-跌停 wait-until-open state is only approximated so far;
- leader exits only when limit breaks near close.

Questions:

- Is 11:25 profit taking doing work, or cutting winners?
- Is 13:01 -2% protective or harmful?
- How sensitive is the strategy to 14:50 vs 14:45 vs 14:55?
- Does leader protection improve risk-adjusted return or only headline return?

### 6. Position And Portfolio State

Current local assumptions:

- initial cash 1,000,000;
- two v227 slots;
- simple market-order fill at selected bar/open price;
- fees and stamp tax approximated;
- no order-book impact model.

Still missing or partial:

- stoploss cooldown;
- v227 shock cooldown;
- bull cooldown and force clear;
- exact closeable amount / T+1 behavior beyond simple same-day no-sell;
- exact JoinQuant order fill details.

Questions:

- Does cooldown improve future returns or merely reduce exposure?
- Does the strategy need dynamic sizing?
- What is capacity if fill slippage is added?

## Data Sensitivity Notes

Known JoinQuant vs hdata differences:

- `300347.XSHE` 2024-03-18 13:01:
  - JoinQuant close: 51.950;
  - hdata close: 51.920;
  - flips midday-loss decision.
- `002130.XSHE` 2024-03-25 14:50:
  - JoinQuant close: 10.990;
  - hdata close: 10.910;
  - flips carry vs exit path.

Conclusion:

- do not judge individual trades too literally;
- judge yearly and regime-level behavior;
- keep hdata-native and jq-aligned concepts separate.

## First Dissection Experiments

Priority 1: contribution by module.

- YJJ only
- YJJ + 天蝎座
- YJJ + 龙头保护
- YJJ + 天蝎座 + 龙头保护

Priority 2: entry filter ablation.

- remove v130 tail-seal filter
- remove v122 volume/new-high filter
- remove average-price strength filter
- relax/tighten money filter
- relax/tighten market-cap filter
- remove low-price tilt

Priority 3: exit robustness.

- 11:25 profit sell on/off
- 13:01 loss sell threshold: -1%, -2%, -3%
- stop loss: -4%, -5%, -6%
- 14:50 exit time: 14:45, 14:50, 14:55
- leader protection on/off

Priority 4: regime robustness.

- no market regime
- index-only regime
- fb_perf-only regime
- fb_pct poison zones on/off
- bull sticky on/off

Priority 5: execution realism.

- add 10/20/30 bps buy slippage;
- add 10/20/30 bps sell slippage;
- reject opens near limit;
- cap trade amount as percentage of previous day amount.

## Acceptance Bar

Continue researching if:

- hdata-native remains profitable after reasonable slippage;
- no single month or single stock explains most of the edge;
- filter ablations show understandable contribution;
- drawdown can be reduced without destroying return;
- 2024/2025/2026 behavior is directionally consistent.

Stop or demote if:

- small parameter moves destroy most returns;
- edge depends mainly on one or two months;
- hdata-native collapses after basic slippage;
- most gains come from bars known to differ from JoinQuant;
- key filters look like pure curve fitting with no stable mechanism.

## Next Step

Build an experiment runner that can produce a compact table for the module
and filter ablations. The first target is the module contribution table:

| Variant | YJJ | 天蝎座 | 龙头保护 | 2024 ret/mdd | 2025 ret/mdd | 2026 ret/mdd |
| --- | --- | --- | --- | --- | --- | --- |

## 2026-05-27 State-Machine Data Notes

New hdata `history` compatibility API was inspected:

- location: `D:\work space\hdata\scripts\core\hdata_reader.py`;
- `skip_paused=False` now reproduces the important JoinQuant behavior of
  calendar-aligned rows plus suspended-day forward-filled prices and zero
  volume/amount;
- `field='high_limit'` is still not supported by the API because the base
  daily parquet does not contain `high_limit`, and the compatibility layer does
  not derive it yet.

Measured against the 2020 JoinQuant state-machine log:

- after reparsing `jq_sm_force_v227_2020_unzip\log.txt`, the PFB observer has
  243 trading-day rows;
- using the new `history(skip_paused=False)` for close and an application-side
  derived high-limit panel, PFB count difference is within 5 stocks on 229/243
  days, and within 2 stocks on 167/243 days;
- the remaining worst count gaps cluster around 2020-04-29, 2020-04-30 and
  2020-05-06.

Important correction:

- earlier "missing prev daily" classifications were often suspended-day
  history semantics, not raw daily-data gaps;
- JoinQuant does not simply skip suspended days in this branch. The mother code
  calls `history(..., skip_paused=False)` by default, so suspended days remain
  in the 3-row panel with filled prices.

Data/API issue to report:

- JoinQuant mother code reads `history(3, field='high_limit', ..., fq=None)`.
  hdata `history` now supports `high_limit` and `low_limit` via
  `1d_feature/limit_status`.
- Residual issue: JoinQuant PFB includes suspended-day examples that are not
  explained by ffilled real limit prices. Example:
  `603799.XSHG` is in JoinQuant PFB on 2020-01-02. The mother code can only add
  it if `abs(close[-1] - high_limit[-1]) <= 0.02` for the previous bar. With
  hdata's current `history`, 2019-12-31 has `close=39.39` and
  `high_limit=42.73`, so it is not a limit-up bar. This implies either
  JoinQuant's suspended-day `high_limit` fill differs from hdata's current
  assumption, or the observer/PFB date context needs another direct check.
- Similar direct-check cases: `002552.XSHE`, `600215.XSHG`, `603960.XSHG` on
  the 2020-01-03 PFB row.

Follow-up from data layer:

- JoinQuant direct probe confirmed the real suspended-day rule:
  `close` is forward-filled, and `pre_close/open/high/low/vwap/high_limit/low_limit`
  are forced to that same `close` on suspended days.
- hdata `history` was updated accordingly. Rechecking the earlier examples:
  `603799.XSHG`, `002552.XSHE`, `600215.XSHG`, and `603960.XSHG` no longer
  explain the PFB residual.
- 2020 PFB count alignment after the suspended-limit fix:
  243 rows total; count difference <= 1 on 129 rows, <= 2 on 176 rows,
  <= 5 on 233 rows. The remaining largest count gaps are small in count terms
  but still have large list-set residuals on days where the JQ observer log
  abbreviates lists as `...(+N)`.
- Performance improved materially with hdata pivot cache: full 2020 PFB
  diagnostic completed in about 90 seconds. This is acceptable for diagnostics
  but still too slow to call repeatedly from a full local state-machine replay;
  the probe should use cached annual panels directly or reuse the hdata pivot
  cache carefully.

## 2026-05-27 `local_jq` P0 Smoke Test

Test target:

- `D:\work space\hdata\scripts\core\local_jq.py`

Passed:

- `local_jq.history` daily `close/high_limit/low_limit/paused` works for
  suspended-day samples.
- `df=False` single-field output is `dict[code] -> ndarray`, matching mother
  code usage such as `high_limits.get(s)[-1]`.
- `get_all_securities(['stock'], date=...)` returns JQ codes with
  `display_name` and `start_date`.
- `get_fundamentals` simple market-cap range query works when the date is
  passed as `YYYYMMDD`.

Issues found:

- `get_price(... frequency='1m', start_date='YYYY-MM-DD HH:MM:SS',
  end_date='YYYY-MM-DD HH:MM:SS', fields=['close','high_limit'])` currently
  fails because the datetime string is passed through to `history` and parsed
  as an integer date. Mother v130 uses exactly this pattern.
- `get_price(... frequency='1m', end_date='YYYY-MM-DD', count=240, ...)`
  currently fails with `KeyError: 'time'`; local minute parquet uses
  `trade_time`, while the history/minute output path looks for `time`.
- `get_price` currently ignores `start_date` semantics and mainly delegates to
  `history(count=count or 1, end_date=end_date)`. For v130 it must return the
  actual intraday interval `09:30:00` to `15:00:00`, not just one tail bar.
- `get_current_data()` has no as-of/context date. It reads the latest available
  day in the whole data set, while mother code expects the current backtest
  timestamp. It also returned `high_limit/low_limit = NaN` for latest sample
  rows where `limit_status` had NaN. For state-machine replay it needs either
  a `set_current_dt(...)` mechanism or a context-bound as-of date.
- `attribute_history(...)` also has no as-of date and therefore uses latest data
  when called outside a context. Mother mode detection needs it as of
  `context.current_dt`.
- `get_fundamentals(..., date='YYYY-MM-DD')` and `date='YYYYMMDD'` behave
  differently. The date argument should be normalized before calling hdata
  loaders. In the smoke test, `date='2020-01-02'` and `date='20200102'`
  returned different candidate rows.

Recommendation:

- Add a tiny local runtime clock, e.g. `local_jq.set_current_dt(dt)` and derive
  `previous_date` from the trading calendar. Then make `history`,
  `attribute_history`, `get_current_data`, `get_fundamentals`, and `get_price`
  default to that clock when no explicit `end_date/date` is supplied.
- Fix minute `get_price` separately from `history`: parse full datetimes,
  filter by `trade_time`, merge/derive `high_limit/low_limit`, and return
  `panel=False` DataFrame with time index.

Follow-up after P0 fixes:

- `set_current_dt` exists and `history` defaults to that date when `end_date`
  is omitted.
- `get_price` 1m interval now supports full datetime strings. The v130 test
  `603799.XSHG`, `2020-01-03 09:30:00` to `15:00:00`, returned 241 rows with
  DatetimeIndex and detected first limit touch at `14:56`.
- `get_fundamentals` date normalization now gives the same result for
  `2020-01-02` and `20200102`.
- Remaining issues:
  - `get_current_data` still returns NaN prices/limits for suspended
    `002552.XSHE` on `2020-01-03`, while `history` returns the correct filled
    suspended-day close/high_limit/low_limit.
  - `attribute_history('000852.XSHG', ...)` fails with `KeyError:
    '000852.SH'` because it is routed through stock history; the mother
    strategy uses `g.idx_code='000852.XSHG'` for market-mode detection, so index
    support is still required.
  - `get_price(..., frequency='1m', count=240, end_date='20200103')` returns
    240 rows starting at 09:31. This may be acceptable for explicit `count`,
    but v130 uses explicit start/end and already returns 241 rows.

Final P0 verification:

- `get_current_data` suspended-day fill is fixed. On `2020-01-03 09:26`,
  `002552.XSHE` returns `paused=1`, `last_price=day_open=high_limit=low_limit=25.21`.
- `attribute_history` single-security field shape is fixed. Both
  `attribute_history('000852.XSHG', 5, '1d', ['close'])['close']` and
  `attribute_history('603799.XSHG', 5, '1d', ['close'])['close']` work for
  `skip_paused=True/False`.
- v130 minute interval remains good: `603799.XSHG` on `2020-01-03` returns
  241 rows from `09:30` to `15:00`, first touch at `14:56`.
- PFB suspended samples are now consistent with the JQ-style flattened
  suspended-day limit behavior for `603799.XSHG`, `002552.XSHE`,
  `600215.XSHG`, and `603960.XSHG`.

P0 is now green for the force-v227 state-machine API surface.

## 2026-05-27 `local_jq` State Replay

New probe:

- `scripts/local_jq_force_v227_state.py`

Important implementation detail:

- In JoinQuant backtest at `09:05`, daily `history()` is effectively cut off at
  `context.previous_date`, not the current trading date. The probe therefore
  keeps `context.current_dt` as today for IPO-age checks, but sets the
  `local_jq` data clock to the previous trading day during `prepare_all`.

2020 first-10-trading-day replay with v130 enabled:

- market mode: 10/10 exact;
- YJJ candidate count: 10/10 exact;
- PFB count: all 10 days within 2 stocks, 5/10 exact;
- Bear candidate count: 10/10 exact.

2020 full-year replay without v130 minute scan:

- rows: 243;
- PFB count exact: 63/243;
- PFB count within 1: 162/243;
- PFB count within 2: 212/243;
- PFB count within 5: 242/243;
- `market_mode` exact: 241/243;
- `raw_market_mode` exact: 241/243;
- `first_board_perf` mean absolute difference: 0.00188;
- `fb_pct` exact: 68/243; within 0.05: 170/243; within 0.10: 220/243;
- Bear candidate count exact: 209/243; within 2: 241/243.

Remaining market-mode mismatches:

- 2020-05-29: JQ `bear`, local `cautious`; caused by tiny fb_perf sign/level
  difference around the mode threshold.
- 2020-09-17: JQ `bear`, local `cautious`; JQ state has `first_board_perf=NaN`
  / `fb_pct=0`, matching the earlier known mother-data NaN behavior.

Artifacts:

- `local_jq_force_v227_state_jan_head.csv`
- `local_jq_force_v227_state_2020_no_v130.csv`
- `local_jq_vs_jq_state_2020_no_v130_compare.csv`

Diagnostic artifacts:

- `scripts/diagnose_history_pfb.py`
- `jq_sm_force_v227_2020_reparse_pfb.csv`
- `history_pfb_compare_2020_reparse.csv`

## 2026-05-27 Performance Cache And Revised State Baseline

Data-layer update verified:

- `local_jq.preload_years([2019, 2020], fields=[...])` works and is required
  for January `history(count=...)` calls that cross into the prior year.
- Preloading only `[2020]` is not sufficient for `2020-01-03` style windows:
  `history(3, ...)` needs `2019-12-31` and otherwise raises a cache index
  error.
- Warm full-market single-field `history(3, ...)` is about 0.7s after preload.
- `get_batch_sealing_points(..., 100 stocks)` is about 1.1s in the sampled
  2020-01-03 test.

Probe update:

- `scripts/local_jq_force_v227_state.py` now preloads the start year minus one
  through the end year.
- v130 scanning now uses `get_batch_sealing_points`.
- PFB detection now explicitly rejects non-finite close/high_limit values.
  Without this, `NaN` comparisons could allow pre-list or unavailable rows to
  slip into the local first-board set.

2020 full-year replay after these changes, without v130 minute scan:

- rows: 243;
- PFB count exact: 19/243;
- PFB count within 1: 63/243;
- PFB count within 2: 112/243;
- PFB count within 5: 201/243;
- max PFB count gap: 15; mean absolute PFB count gap: 3.276;
- `first_board_perf` mean absolute difference: 0.002386; max: 0.012058;
- `fb_pct` exact: 66/243; within 0.05: 162/243; within 0.10: 211/243;
- `raw_market_mode` exact: 241/243;
- `market_mode` exact: 241/243;
- YJJ candidate count exact: 206/243; within 1: 233/243; max gap: 4;
- Bear candidate count exact: 173/243; within 2: 222/243; max gap: 9.

Remaining market-mode mismatches are still:

- 2020-05-29: JQ `bear`, local `cautious`;
- 2020-09-17: JQ `bear`, local `cautious`.

Current interpretation:

- The high-level state machine is close enough to continue diagnosis:
  market regime is 241/243 exact and YJJ count is usually exact or off by one.
- PFB is not fully aligned. The remaining residual is too large to call the
  PFB layer closed.
- Early examples still point to IPO first-day high-limit behavior and
  delisted/ST/S-stock limit behavior as major PFB root causes. Some large-day
  PFB code lists from JQ logs are truncated with `...(+N)`, so count-level
  comparison is more reliable than set-level comparison on those days.

Artifacts:

- `local_jq_force_v227_state_2020_fast_no_v130_finite.csv`
- `compare_2020_fast_no_v130_finite.csv`

## 2026-05-27 P0 Edge-Case Data Rebuild Verification

The data layer was rebuilt for IPO first-day limits, ST/S/delisting limits, and
low-price cent rounding. Local replay was rerun with the same observer.

Important sampled fixes:

- `603109.XSHG` on `2019-12-31`: `high_limit=26.47`, matching first-day
  close, so it enters the `2020-01-02` PFB set.
- `300811.XSHE` on `2019-12-30/31`: first day has
  `close=high_limit=37.76`; second day is therefore not a first board for
  `2020-01-02`.
- `002089.XSHE`, `600856.XSHG`, `600891.XSHG`, `600247.XSHG` now use the
  expected 5% ST-style limit on the sampled dates.

2020 first 10 trading days after rebuild:

- PFB count exact: 7/10; within 2: 10/10.
- `2020-01-02` PFB set is exact against the parsed JQ PFB log.
- `market_mode` exact: 10/10.

2020 full-year replay after rebuild, without v130 minute scan:

- rows: 243;
- PFB count exact: 100/243;
- PFB count within 1: 180/243;
- PFB count within 2: 226/243;
- PFB count within 5: 242/243;
- max PFB count gap: 9; mean absolute PFB count gap: 0.947;
- `first_board_perf` mean absolute difference: 0.000757; max: 0.005143;
- `fb_pct` exact: 106/243; within 0.05: 212/243; within 0.10: 234/243;
- `raw_market_mode` exact: 242/243;
- `market_mode` exact: 242/243;
- YJJ candidate count exact: 207/243; within 1: 233/243; max gap: 4;
- Bear candidate count exact: 199/243; within 2: 242/243; max gap: 5.

Remaining mismatch:

- `2020-09-17`: JQ has `market_mode=bear`, local has `cautious`. The PFB set
  count and parsed set are exact for this day (`29/29`), but JQ state has
  `first_board_perf=NaN` and `fb_pct=0`, while local computes a valid
  `first_board_perf=0.003474` and `fb_pct=0.25`. This remains a mother-strategy
  NaN behavior rather than a PFB set mismatch.

Largest PFB count gap:

- `2020-07-21`: JQ state count is 167, local count is 176. The parsed JQ PFB
  code line is truncated with `...(+N)`, so code-set attribution is incomplete.

Artifacts:

- `local_jq_force_v227_state_2020_after_p0fix_no_v130.csv`
- `compare_2020_after_p0fix_no_v130.csv`

## 2026-05-28 Local Data Upgrade Recheck

The local data/interface layer was upgraded again on 2026-05-28. Rechecking
against the same 2020 JQ state logs produced the same full-year baseline as the
post-P0 rebuild:

- PFB count exact: 100/243;
- PFB count within 1: 180/243;
- PFB count within 2: 226/243;
- `raw_market_mode` exact: 242/243;
- `market_mode` exact: 242/243;
- YJJ candidate count exact: 207/243; within 1: 233/243;
- Bear candidate count exact: 199/243; within 2: 242/243;
- `first_board_perf` MAE: 0.000757.

The only market-mode mismatch remains `2020-09-17`, where the JQ mother state
has `first_board_perf=NaN` / `fb_pct=0`, while local computes valid values.

New observer finding:

- The local observer was missing the mother strategy's bull-mode
  `_score_with_left_pressure` step. This was added to
  `scripts/local_jq_force_v227_state.py`.
- The sampled large YJJ difference on `2020-07-21` was already fixed by
  running with v130; `2020-07-14` still has two local-only YJJ names after v130:
  `300118.XSHE` and `600711.XSHG`.
- For those two, local first-touch times are before 14:00, so they are not
  v130 tail-seal exclusions:
  - `300118.XSHE`: first touch `2020-07-13 13:56`;
  - `600711.XSHG`: first touch `2020-07-13 11:17`.
- Both pass the mother avg-price filter only narrowly:
  - `300118.XSHE`: `avg_chg=0.077596`;
  - `600711.XSHG`: `avg_chg=0.072688`.

Across the full 2020 no-v130 comparison, local-only YJJ names are mostly near
the mother filter threshold `avg_chg >= 0.07`:

- local-only YJJ samples: 50;
- 45/50 have local `avg_chg` in `[0.065, 0.08]`;
- min local `avg_chg`: 0.070227;
- median: 0.072670.

Interpretation:

- Remaining YJJ extras are very likely driven by small `money / volume / close`
 口径 differences around the 7% avg-price threshold, not by a broad state-machine
  route error.
- A targeted JQ probe should print `money`, `volume`, `close`, and computed
  `avg_chg` for local-only near-threshold names, especially `300118.XSHE` and
  `600711.XSHG` on `2020-07-13`.

Artifacts:

- `local_jq_force_v227_state_2020_after_upgrade_no_v130.csv`
- `compare_2020_after_upgrade_no_v130.csv`
- `local_jq_force_v227_state_20200714_21_after_leftpressure_v130.csv`

Follow-up JQ probes ruled out avg-price-filter mismatch for sampled local-only
YJJ names:

- JQ `money / volume / close * 1.1 - 1` matches local for the sampled names.
- Therefore the 7% avg-price threshold is not the source of those differences.

JQ v122/v130 probes then classified sampled names:

- Tail-seal exclusions in JQ:
  - `300118.XSHE` on `2020-07-13`: first hit `14:04`, remove by v130.
  - `300322.XSHE` on `2020-02-24`: first hit `15:00`, remove by v130.
  - `603456.XSHG` on `2020-02-24`: first hit `14:20`, remove by v130.
  - `603601.XSHG` on `2020-02-24`: first hit `14:02`, remove by v130.
  - `600316.XSHG` on `2020-07-20`: first hit `14:12`, remove by v130.
  - `600580.XSHG` on `2020-07-20`: first hit `14:13`, remove by v130.
  - `600879.XSHG` on `2020-07-20`: first hit `14:24`, remove by v130.
  - `000878.XSHE` on `2020-09-18`: first hit `14:10`, remove by v130.
  - `002216.XSHE` on `2020-09-18`: first hit `14:51`, remove by v130.
- Not explained by v122/v130:
  - `600711.XSHG` on `2020-07-13`: v122 keep, first hit `11:17`, v130 keep.
  - `000789.XSHE` on `2020-07-20`: JQ first hit `10:35`, v130 keep, but local
    minute data currently sees first hit `14:12`.

Minute-data discrepancies found:

- `300118.XSHE` `2020-07-13`: local first hit `13:56`, JQ first hit `14:04`.
  This can explain why local kept it while JQ removed it on `2020-07-14`.
- `000789.XSHE` `2020-07-20`: local first hit `14:12`, JQ first hit `10:35`.
  This is a local/JQ minute-line mismatch even if final YJJ alignment may be
  affected by later filters.

Remaining focused tasks:

- Ask data layer to compare local vs JQ 1m bars around `300118.XSHE`
  `2020-07-13 13:50-14:05` and `000789.XSHE` `2020-07-20 10:30-10:40/14:10-14:15`.
- Add a JQ stage probe for `600711.XSHG` on `2020-07-14` after v122, after
  v130, and after `_score_with_left_pressure`, because v122/v130 do not explain
  its absence from final JQ YJJ candidates.
