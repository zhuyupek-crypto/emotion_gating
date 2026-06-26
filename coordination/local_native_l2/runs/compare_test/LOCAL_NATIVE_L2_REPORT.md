# LOCAL_NATIVE_L2 Acceptance Report

## Acceptance Gates Status

- 🟢 **l2_exact_hook_set**: PASS
- 🟡 **l1b_preopen_hooks_have_effective_hits**: NOT_COVERED
- 🟢 **l2_preopen_hooks_effective_hits_zero**: PASS
- 🟢 **would_have_hit_events_complete**: PASS
- 🟢 **first_direct_diff_maps_to_hook**: PASS
- 🟢 **divergence_not_before_first_hit**: PASS
- 🟢 **pre_hit_exact_match**: PASS
- 🟢 **direct_price_unchanged**: PASS
- 🟢 **checked_account_invariants**: PASS
- 🟢 **required_artifacts_complete**: PASS
- 🟢 **all_direct_diffs_map_to_genuine_hooks**: PASS
- 🔴 **l0_main_vs_head**: PENDING
- 🟢 **deterministic_reports**: PASS
- 🟢 **implementation_acceptance**: PASS
- 🟢 **direct_order_presence_changed**: PASS


## Year Summary

| Year | L1B Final Equity | L2 Final Equity | L1B Return % | L2 Return % | L1B Trades | L2 Trades | Direct Diffs | Downstream Diffs |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2021 | 3386349.45 | 3465363.13 | 238.6349 | 246.5363 | 445 | 448 | 3 | 360 |
| 2025 | 2528957.47 | 2528957.47 | 152.8957 | 152.8957 | 531 | 531 | 0 | 0 |


## Hook Hits Summary

| Hook ID | Profile | Queries | Effective Hits | Would-Have Hits |
| --- | --- | --- | --- | --- |
| `execution.preopen_drop_first_duplicate` (Y2021) | L1B | 212 | 3 | 0 |
| `execution.preopen_drop_first_duplicate` (Y2021) | L2 | 212 | 0 | 3 |
| `execution.preopen_drop_first_duplicate` (Y2025) | L1B | 262 | 0 | 0 |
| `execution.preopen_drop_first_duplicate` (Y2025) | L2 | 262 | 0 | 0 |
| `execution.preopen_reject_cash_below` (Y2021) | L1B | 212 | 0 | 0 |
| `execution.preopen_reject_cash_below` (Y2021) | L2 | 212 | 0 | 0 |
| `execution.preopen_reject_cash_below` (Y2025) | L1B | 262 | 0 | 0 |
| `execution.preopen_reject_cash_below` (Y2025) | L2 | 262 | 0 | 0 |
| `execution.preopen_reject_orders` (Y2021) | L1B | 212 | 0 | 0 |
| `execution.preopen_reject_orders` (Y2021) | L2 | 212 | 0 | 0 |
| `execution.preopen_reject_orders` (Y2025) | L1B | 262 | 0 | 0 |
| `execution.preopen_reject_orders` (Y2025) | L2 | 262 | 0 | 0 |


## Notes & Limitations

- **L2 Hooks**: preopen_reject_cash_below, preopen_reject_orders, preopen_drop_first_duplicate

- **Direct Diff Classification**: L1B effective_hit=True + L2 would_have_hit=True with same date/time/code

- **Downstream**: Same-day trade diffs without corresponding hook event, cascading cash/position changes

- **Cash Negativity**: Cash non-negativity check is excluded from checked claims because total cash can naturally go negative during intraday/auction margin execution.
