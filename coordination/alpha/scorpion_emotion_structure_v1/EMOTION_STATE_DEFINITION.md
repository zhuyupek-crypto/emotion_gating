# EMOTION_STATE_DEFINITION.md

Generated: 2026-06-30T02:26:06.308190

## State philosophy

All emotion states are constructed from causal T-1 close or T 09:30 features.
The definitions below were frozen before inspecting Scorpion trade returns.

## Dimension scores

Each raw feature is converted to a 250-day rolling percentile rank, then averaged
within its dimension so every dimension lies on [0, 1].

| Dimension | Components |
|-----------|------------|
| breadth_score | limit_up_count, advance_decline_ratio, market_positive_rate |
| height_score | max_board_height, first_to_second_promotion_rate |
| profit_score | prev_first_board_next_day_mean_return, prev_limit_up_next_day_mean_return |
| stress_score | limit_down_count, broken_board_rate, return_below_minus5pct_count |
| liquidity_score | total_market_turnover |

## Aggregate indicators

- `emotion_heat` = (breadth + height + profit) / 3, range [0, 1]
- `emotion_momentum` = emotion_heat.diff(3)
- `emotion_stress` = stress_score

## State classification rules (primary v2)

| State | Rule |
|-------|------|
| EXTREME_PANIC | stress > 0.80 and heat < 0.35 |
| ICE_POINT | heat < 0.35 and momentum < 0 |
| ICE_REPAIR | heat < 0.35 and momentum >= 0 |
| WEAK_REPAIR | 0.35 <= heat < 0.65 and momentum >= 0 |
| RECESSION | 0.35 <= heat < 0.65 and momentum < 0 |
| HIGH_DIVERGENCE | heat >= 0.65, momentum < 0, stress > 0.45 |
| ACCELERATION | heat >= 0.65 and momentum >= 0 |

## State classification rules (sensitivity v1, retained for reference)

| State | Rule |
|-------|------|
| EXTREME_PANIC | stress > 0.80 and heat < 0.25 |
| ICE_POINT | heat < 0.30 and momentum < 0 |
| ICE_REPAIR | heat < 0.30 and momentum >= 0 |
| WEAK_REPAIR | 0.30 <= heat < 0.65 and momentum >= 0 |
| RECESSION | 0.30 <= heat < 0.65 and momentum < 0 |
| HIGH_DIVERGENCE | heat >= 0.65, momentum < 0, stress > 0.55 |
| ACCELERATION | heat >= 0.65 and momentum >= 0 |

## State distribution (2018-2025)

### v2 (primary)

| count           |   count |
|:----------------|--------:|
| ICE_POINT       |     127 |
| ICE_REPAIR      |      17 |
| WEAK_REPAIR     |     410 |
| ACCELERATION    |     534 |
| HIGH_DIVERGENCE |      36 |
| RECESSION       |     677 |
| EXTREME_PANIC   |     141 |


### v1 (sensitivity reference)

| count           |   count |
|:----------------|--------:|
| ICE_POINT       |     115 |
| ICE_REPAIR      |       6 |
| WEAK_REPAIR     |     424 |
| ACCELERATION    |     534 |
| HIGH_DIVERGENCE |      15 |
| RECESSION       |     797 |
| EXTREME_PANIC   |      51 |

