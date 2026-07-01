# Phase 1A Report

Conclusion: PARTIAL

## Scope

```text
start: 2023-01-01
end: 2023-03-31
schema_version: 0.2
formal_strategy_sha256: 621a9c968473d73dfa1699be0a16714790e4f93ab950957c0a3f88f4f34bcc8e
instrumented_strategy_sha256: 16a22f329f2169490fb92e08f9985019a453df190cedc75cfdcf1b709cf4c3df
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
  "decision_events": 954,
  "trade_outcomes": 45,
  "handler_snapshots": 2242,
  "mapped_buy_trades": 45,
  "unmapped_buy_trades": 0,
  "mapped_sell_allocations": 43,
  "unmapped_sell_trades": 0,
  "terminal_states": {
    "FILLED": 45,
    "ROUTED_OUT": 131,
    "UNRESOLVED": 733
  },
  "buy_trade_mapping_rate": 1.0,
  "sell_trace_unmapped_count": 0,
  "order_to_handler_mapped": 87,
  "engine_order_count": 87,
  "order_to_handler_mapping_rate": 1.0
}
```

## Instrumentation Diff

`json
{
  "formal_strategy": "D:\\Work Space\\他山之石\\情绪门控\\worktrees\\motherboard-attribution-phase1a-v1\\母版-20260506-Clone.py",
  "instrumented_strategy": "D:\\Work Space\\他山之石\\情绪门控\\worktrees\\motherboard-attribution-phase1a-v1\\research\\instrumented_strategies\\motherboard_phase1a_observed.py",
  "formal_sha256": "621a9c968473d73dfa1699be0a16714790e4f93ab950957c0a3f88f4f34bcc8e",
  "instrumented_sha256": "16a22f329f2169490fb92e08f9985019a453df190cedc75cfdcf1b709cf4c3df",
  "prelude_removed_matches_formal": true,
  "allowed_difference": "single attribution prelude inserted after `from jqdata import *`"
}
`

## Notes

Phase 1A observes `PREPARED_CANDIDATE` events only. It does not claim true `RAW_PATTERN` coverage and does not compute counterfactual EV or Alpha Matrix outputs.
