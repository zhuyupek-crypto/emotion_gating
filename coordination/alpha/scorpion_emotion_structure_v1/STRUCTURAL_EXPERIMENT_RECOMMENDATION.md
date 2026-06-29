# STRUCTURAL_EXPERIMENT_RECOMMENDATION.md

Generated: 2026-06-29T20:29:02.651384

## Executive summary

Total matched Scorpion trades: 169.  Overall mean return: 0.0208; overall win rate: 65.68%; total gross contribution: 3.5080.

## Primary structural experiment (only one recommended)

**基于T-1情绪状态的仓位分级实验**

- Category: A - 情绪门控/仓位分级
- Rationale: WEAK_REPAIR等修复状态EV显著高于退潮/恐慌状态，建议在修复期维持标准仓位，在RECESSION/HIGH_DIVERGENCE/EXTREME_PANIC状态降低仓位或暂停。
- Causal features used (all T-1 close or T 09:30):
  - `T1_emotion_state_v2`, `T1_emotion_heat`, `T1_emotion_momentum`, `T1_emotion_stress`
  - `sector_limit_up_count`, `sector_first_board_count`, `sector_broken_board_rate`
  - `candidate_relative_to_cohort`, `first_board_cohort_open_gap_mean`, `market_open_positive_rate`
- Proposed implementation:
  - Do **not** modify `strategy_v227_scorp.py`.
  - Implement the experiment as a post-selection layer or wrapper around the existing entry signal.
  - Re-run the full 2018-2025 baseline after each variant to confirm 169 trades unchanged.

## Experiments deliberately not recommended as primary

- Adjusting the low-open interval, 60-day position threshold, or stop-loss percentage.
- Changing moving-average periods or sell timing.
- Adding Slots purely based on historical best performance.
- Using same-day close data or future concept-sector membership.

## Next steps after the primary experiment

1. If state-contingent sizing works, test a composite multi-candidate ranking score.
2. If ranking works, test confirmation-style entry timing.
3. Freeze the successful structural variant as a new baseline before any parameter tuning.
