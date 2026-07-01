# Motherboard Attribution Event Schema

`schema_version = 0.3`

This schema describes actual-execution attribution for the motherboard strategy. Phase 1B remains at `observation_level = PREPARED_CANDIDATE`: rows are emitted from branch-prepared candidate lists, not from true raw pattern scanners. True `RAW_PATTERN` coverage is intentionally deferred.

## Identity

A `SIGNAL_EVENT` is uniquely keyed by:

```text
(trade_date, branch, code, signal_variant)
```

`signal_variant` is required because a branch can later split into multiple signal variants without collapsing same-day same-code lineage.

## Source Versions

Every signal row carries source version fields:

```text
formal_strategy_commit
formal_strategy_sha256
instrumented_strategy_commit
instrumented_strategy_sha256
observer_commit
schema_version
```

## SIGNAL_EVENT

Every row that enters `SIGNAL_EVENT` must close into exactly one terminal state. `branch_eligible` is only a path state and is not a table admission condition.

Required Phase 1B path fields:

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

Observation fields:

```text
observation_level = PREPARED_CANDIDATE
prepared_candidate = true/false
raw_pattern_hit = null
```

Emotion fields are reserved and currently null because Phase 1B does not materialize a true emotion-state vector:

```text
emotion_state = null
emotion_heat = null
emotion_momentum = null
emotion_stress = null
```

The strategy's actual motherboard state is stored separately:

```text
fb_pct
first_board_perf
market_mode
raw_market_mode
active_route
```

## Terminal States

Allowed terminal states:

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

Meanings:

- `FILLED`: at least one buy trade filled and mapped to this signal. Partial fills remain `terminal_state = FILLED` and use `fill_status = PARTIAL` in `TRADE_OUTCOME`.
- `BRANCH_FILTERED`: candidate reached branch-native checks and failed a branch rule.
- `MOTHERBOARD_GATED_OUT`: branch handler was reached but motherboard-level mode, cooldown, month, or scaling gate blocked the branch.
- `ROUTED_OUT`: branch was not enabled by the route gate after preparation.
- `RANKED_OUT`: candidate participated in ranking but was outside the executable selection set.
- `SLOT_BLOCKED`: branch/global slot capacity prevented evaluation or order creation.
- `CASH_BLOCKED`: available cash was insufficient for the strategy's minimum order threshold.
- `POSITION_BLOCKED`: an existing position in the same code blocked a new buy.
- `ORDER_NOT_CREATED`: an order function returned `None` before creating an engine order.
- `ORDER_REJECTED`: an engine order object was created but rejected.
- `DATA_INVALID`: required market, auction, or reference data was missing or invalid.
- `NOT_EVALUATED_AFTER_STOP`: original loop control stopped before this candidate was evaluated.
- `UNRESOLVED`: observer defect only. It should not be used for normal loop stops or resource blocks.

Terminal assignment is strict: a non-`UNRESOLVED` terminal cannot be overwritten by another terminal. `FILLED` is final and cannot be overwritten.

## DECISION_EVENT

`DECISION_EVENT` records direct layer evidence from route gates, motherboard gates, branch filters, ranking, resource checks, order creation, and loop control.

Important fields:

```text
signal_id
decision_seq
decision_stage
decision_name
decision_value
passed
reason_code
reason_detail
available_cash
locked_cash
positions_count
pending_order_count
candidate_rank
selected_for_order
```

## LOOP_STOP_EVENT

Loop stop rows record explicit original-loop stops such as slot/take completion. Affected signal ids are also closed to a resource terminal or `NOT_EVALUATED_AFTER_STOP`.

## TRADE_OUTCOME

`TRADE_OUTCOME` is actual execution only:

```text
outcome_type = MASTER_ACTUAL
actual_traded = true
terminal_state is represented on SIGNAL_EVENT
fill_status = FULL / PARTIAL
```

No counterfactual EV or Alpha Matrix fields are produced in Phase 1B.
