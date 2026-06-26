# LOCAL_NATIVE_L1B Acceptance Report

## Acceptance Gates Status

- 🟢 **l1b_exact_hook_set**: PASS
- 🟢 **l1a_size_hooks_have_effective_hits**: PASS
- 🟢 **l1b_size_hooks_effective_hits_zero**: PASS
- 🟢 **would_have_hit_events_complete**: PASS
- 🟢 **first_direct_diff_maps_to_hook**: PASS
- 🟢 **divergence_not_before_first_hit**: PASS
- 🟢 **pre_hit_exact_match**: PASS
- 🟢 **direct_price_unchanged**: PASS
- 🟢 **account_invariants**: PASS
- 🟢 **required_artifacts_complete**: PASS
- 🟢 **deterministic_reports**: PASS
- 🟢 **implementation_acceptance**: PASS


## Hook Hits Summary

| Hook ID | Profile | Queries | Effective Hits | Would-Have Hits |
| --- | --- | --- | --- | --- |
| `execution.execution_price_anomalies` | L1A | 395 | 0 | 107 |
| `execution.execution_price_anomalies` | L1B | 395 | 0 | 107 |
| `execution.fill_amount_anomalies` | L1A | 199 | 2 | 0 |
| `execution.fill_amount_anomalies` | L1B | 199 | 0 | 2 |
| `execution.order_amount_anomalies` | L1A | 199 | 27 | 0 |
| `execution.order_amount_anomalies` | L1B | 199 | 0 | 27 |
| `market_data.minute_price_anomalies` | L1A | 3448 | 0 | 1 |
| `market_data.minute_price_anomalies` | L1B | 3448 | 0 | 1 |


## Performance Comparison

| Metric | L1A (Control) | L1B (Experiment) |
| --- | --- | --- |
| Final Equity | 2533999.15 | 2531205.38 |
| Total Return | 153.3999% | 153.1205% |
| Trade Count | 395 | 395 |


## Trade Differences Breakdown

- **Amount-only differences**: 171
- **Price differences**: 0
- **Added trades (L1B only)**: 0
- **Removed trades (L1A only)**: 0
- **First direct difference time**: `2020-02-10 9:30`
- **First direct difference key**: `2020-02-10|2020-02-10 9:30|600400.XSHG|buy#1`
- **First cascading trade date**: `2020-02-11`
- **Earliest size hook would-have-hit**: `20200210 09:27` (`execution.order_amount_anomalies`)

