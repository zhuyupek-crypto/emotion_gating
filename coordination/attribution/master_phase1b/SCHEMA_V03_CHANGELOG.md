# Schema v0.3 Changelog

Phase 1B upgrades the observer/event model from v0.2 to v0.3 without changing the formal strategy, engine, compatibility layer, or strategy parameters.

## Corrections

- `SIGNAL_EVENT` closure applies to every signal row, not only rows with `branch_eligible = true`.
- Phase 1B remains honest about coverage: `observation_level = PREPARED_CANDIDATE`; true raw-pattern events are not claimed.
- Signal identity is `(trade_date, branch, code, signal_variant)`.
- `PARTIAL_FILL` is not a terminal state. Partial executions use `terminal_state = FILLED` and `fill_status = PARTIAL`.
- `emotion_state`, `emotion_heat`, `emotion_momentum`, and `emotion_stress` are reserved/null. Actual motherboard state is stored in `fb_pct` and `first_board_perf`.

## New Fields

`SIGNAL_EVENT` adds path flags and terminal provenance:

```text
handler_reached
candidate_loop_reached
handler_eligible
branch_eligible
qualified_for_ranking
participated_in_ranking
selected_for_order
loop_stop_reason
terminal_reason_code
terminal_decision_seq
```

Source-version fields are written on every signal row:

```text
formal_strategy_commit
formal_strategy_sha256
instrumented_strategy_commit
instrumented_strategy_sha256
observer_commit
schema_version
```

## Terminal State Set

```text
FILLED
BRANCH_FILTERED
MOTHERBOARD_GATED_OUT
ROUTED_OUT
RANKED_OUT
SLOT_BLOCKED
CASH_BLOCKED
POSITION_BLOCKED
ORDER_NOT_CREATED
ORDER_REJECTED
DATA_INVALID
NOT_EVALUATED_AFTER_STOP
UNRESOLVED
```

`UNRESOLVED` is reserved for observer defects and is measured against the Phase 1B acceptance threshold.
