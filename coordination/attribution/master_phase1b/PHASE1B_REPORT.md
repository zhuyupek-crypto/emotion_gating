# Phase 1B Report

Conclusion: PASS

## Scope

```text
start: 2023-01-01
end: 2023-03-31
schema_version: 0.3
outcome_scope: MASTER_ACTUAL
formal_strategy_sha256: 621a9c968473d73dfa1699be0a16714790e4f93ab950957c0a3f88f4f34bcc8e
instrumented_strategy_sha256: 369b5598d3c225b84c4472ce639ac5478d18a999c77334d639322e474beb3193
```

## Closure

```json
{
  "signal_events": 909,
  "closed_events": 909,
  "unresolved_events": 0,
  "unresolved_rate": 0.0,
  "duplicate_signal_keys": [],
  "duplicate_signal_key_count": 0,
  "all_have_terminal_state": true,
  "all_have_v03_key": true
}
```

## Behavior Parity

```json
{
  "B0_vs_I0": {
    "trades_equal": true,
    "orders_equal": true,
    "equity_equal": true,
    "state_equal": true,
    "handler_profile_equal": true,
    "final_value_ref": 1053321.5800000005,
    "final_value_other": 1053321.5800000005,
    "trade_count_ref": 87,
    "trade_count_other": 87,
    "order_count_ref": 87,
    "order_count_other": 87
  },
  "B0_vs_I1": {
    "trades_equal": true,
    "orders_equal": true,
    "equity_equal": true,
    "state_equal": true,
    "handler_profile_equal": true,
    "final_value_ref": 1053321.5800000005,
    "final_value_other": 1053321.5800000005,
    "trade_count_ref": 87,
    "trade_count_other": 87,
    "order_count_ref": 87,
    "order_count_other": 87
  }
}
```

## Mapping Audit

```json
{
  "signal_events": 909,
  "decision_events": 1687,
  "trade_outcomes": 45,
  "handler_snapshots": 2242,
  "mapped_buy_trades": 45,
  "unmapped_buy_trades": 0,
  "mapped_sell_allocations": 43,
  "unmapped_sell_trades": 0,
  "terminal_states": {
    "BRANCH_FILTERED": 362,
    "CASH_BLOCKED": 23,
    "FILLED": 45,
    "MOTHERBOARD_GATED_OUT": 143,
    "POSITION_BLOCKED": 1,
    "ROUTED_OUT": 131,
    "SLOT_BLOCKED": 204
  },
  "closure_rate": 1.0,
  "unresolved": 0,
  "buy_trade_mapping_rate": 1.0,
  "sell_trace_unmapped_count": 0,
  "order_to_handler_mapped": 87,
  "engine_order_count": 87,
  "order_to_handler_mapping_rate": 1.0
}
```

## Phase 1A / Phase 1B Alignment

```json
{
  "phase1a_dir": "D:\\Work Space\\他山之石\\情绪门控\\worktrees\\motherboard-attribution-phase1a-v1\\coordination\\attribution\\master_phase1a",
  "available": true,
  "trades_equal": true,
  "orders_equal": true,
  "signal_set_source": "full",
  "signal_keys_equal": true,
  "phase1a_signal_keys": 909,
  "phase1b_signal_keys": 909,
  "phase1a_minus_phase1b_sample": [],
  "phase1b_minus_phase1a_sample": []
}
```

## Instrumentation Diff

```json
{
  "formal_strategy": "D:\\Work Space\\他山之石\\情绪门控\\worktrees\\motherboard-attribution-phase1b-v1\\母版-20260506-Clone.py",
  "instrumented_strategy": "D:\\Work Space\\他山之石\\情绪门控\\worktrees\\motherboard-attribution-phase1b-v1\\research\\instrumented_strategies\\motherboard_phase1b_observed.py",
  "formal_sha256": "621a9c968473d73dfa1699be0a16714790e4f93ab950957c0a3f88f4f34bcc8e",
  "instrumented_sha256": "369b5598d3c225b84c4472ce639ac5478d18a999c77334d639322e474beb3193",
  "prelude_and_overrides_removed_match_formal": true,
  "allowed_difference": "attribution prelude plus end-of-file buy-handler overrides only"
}
```

## Notes

Phase 1B keeps the observation level at `PREPARED_CANDIDATE`. It closes actual execution lineage only and does not introduce counterfactual EV, Alpha Matrix, auction-truth audit, or strategy-parameter changes.
