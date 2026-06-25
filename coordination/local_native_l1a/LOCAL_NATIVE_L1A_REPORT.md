# LOCAL_NATIVE_L1A Acceptance Report

## Profile Definitions

- **jq_parity**: disabled_hook_ids = []
- **local_native_l1a**: disabled_hook_ids = ['execution.execution_price_anomalies', 'market_data.minute_price_anomalies']

## L0 Baseline Regression

- No baseline comparison performed.

## L1A Trade Comparison

- jq_trade_count: 395
- l1a_trade_count: 395
- matched_trade_key_count: 394
- trade_key_overlap_ratio: 0.994949
- price_only_diff_count: 108
- amount_diff_count: 239
- added_trade_count: 1
- removed_trade_count: 1

## L1A Performance

### jq_parity
- final_value: 2507117.2900000024
- total_return_pct: 150.71172900000022
- max_drawdown: -0.163735
- trade_count: 395
- win_rate: 0.446281
### local_native_l1a
- final_value: 2533999.15
- total_return_pct: 153.39991500000002
- max_drawdown: -0.16176
- trade_count: 395
- win_rate: 0.442149

## Causal Timing

- earliest_disabled_hook_hit: 2020-01-02
- earliest_trade_divergence: 2020-01-14 11:25
- earliest_state_divergence: 2020-01-15
- earliest_equity_divergence: 2020-01-14
- earliest_position_divergence: 2020-01-14

## Hook Hits (jq_parity)

### minute_price
- queries: 3470
- effective_hits: 1
- profile_disabled: 0
### execution_price
- queries: 395
- effective_hits: 107
- profile_disabled: 0

## Hook Hits (local_native_l1a)

### minute_price
- queries: 3448
- effective_hits: 0
- profile_disabled: 1
### execution_price
- queries: 395
- effective_hits: 0
- profile_disabled: 1

## Acceptance Gates

- l0_baseline_regression: **NOT_APPLICABLE**
- l1a_exact_hook_set: **PASS**
- l1a_hooks_disabled: **PASS**
- completed_successfully: **PASS**
- no_data_quality_issues: **PASS**
- implementation_acceptance: **PASS**
