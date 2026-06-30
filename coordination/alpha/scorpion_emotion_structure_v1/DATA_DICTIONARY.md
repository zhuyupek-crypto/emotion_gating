# DATA_DICTIONARY.md

Generated: 2026-06-30T02:26:08.467907

## CSV deliverables

| File | Description |
|------|-------------|
| EMOTION_DAILY_PANEL.csv | Daily causal emotion features and assigned state. One row per trading day. |
| TRADE_EMOTION_PANEL.csv | Each Scorpion trade joined with T-1 emotion panel and T open context. |
| EMOTION_STATE_SUMMARY.csv | Return statistics grouped by T-1 emotion state (primary v2). |
| EMOTION_STATE_SUMMARY_V1.csv | Return statistics grouped by T-1 emotion state (sensitivity v1). |
| PERIOD_STABILITY_V2.csv | Per-state EV/win-rate across four 2-year periods (primary v2). |
| PERIOD_STABILITY_V1.csv | Per-state EV/win-rate across four 2-year periods (sensitivity v1). |
| SECTOR_RESONANCE_SUMMARY.csv | Return statistics grouped by T-1 L1 sector. |
| OPEN_CONTEXT_SUMMARY.csv | Return statistics by open-gap / market-open quintiles. |
| MULTI_CANDIDATE_RANKING_ANALYSIS.csv | Per-candidate features and ranks on days with >1 candidate. |
| HYPOTHESIS_TEST_RESULTS.csv | Tidy table of H1-H6 test results. |

## Key column semantics

- `T1_*`: value from the emotion panel on the trading day **before** the entry date.
- `open_gap`: (T open - T pre_close) / T pre_close; visible at 09:30.
- `candidate_relative_to_cohort`: candidate open gap minus mean open gap of T-1 first-board cohort.
- `candidate_relative_to_market`: candidate open gap minus median market open gap.
- `sector_limit_up_count`: number of limit-up stocks in the candidate's T-1 L1 sector.
- `sector_first_board_count`: number of first boards in the candidate's T-1 L1 sector.
- `candidate_return_to_close`: same-day (close - open) / open; used only as a post-hoc ranking outcome.

## Local parquet cache

All local files live under `d:\workspace\他山之石\情绪门控\_emotion_structure_local` and are recorded in `local_manifest.json`.
