# Event Schema v0.1

Phase 0 only designs the schema. It does not implement an observer.

## Identity

`signal_id` format:

```text
{branch}|{trade_date}|{code}|{signal_variant}
```

The same stock on the same date can be recognized by multiple branches and must not be merged.

## SIGNAL_EVENT

One row per `trade_date x code x branch x signal_variant`.

Required fields:

```text
signal_id
trade_date
signal_time
code
branch
signal_variant
strategy_commit
strategy_sha256
raw_pattern_hit
branch_eligible
raw_candidate_rank
final_candidate_rank
branch_candidate_count
market_mode
raw_market_mode
active_route
emotion_state
emotion_heat
emotion_momentum
emotion_stress
source_function
source_path
source_line
branch_payload
```

`branch_payload` is a branch-specific JSON object. Phase 0 intentionally does not force YJJ, Scorpion, RZQ, ZB, and Auction to share the same shape features.

## DECISION_EVENT

One signal can have multiple decision rows.

Required fields:

```text
signal_id
decision_seq
decision_time
decision_stage
decision_name
decision_value
rule_description
passed
reason_code
reason_detail
market_mode
active_route
branch_enabled
branch_slots_total
branch_slots_used
branch_slots_remaining
available_cash
locked_cash
positions_count
pending_order_count
candidate_rank
selected_for_order
blocking_signal_id
blocking_branch
blocking_code
blocking_order_id
```

Allowed `decision_stage` values:

```text
BRANCH_FILTER
ENVIRONMENT_GATE
ROUTE_GATE
COOLDOWN_GATE
RANKING
BRANCH_SLOT
GLOBAL_RESOURCE
ORDER_CREATION
MARKET_EXECUTION
EXIT
```

## TRADE_OUTCOME

Phase 0 freezes `MASTER_ACTUAL`. Other outcome types are reserved.

Required fields:

```text
signal_id
outcome_type
actual_traded
order_id
trade_ids
entry_time
entry_price
entry_amount
entry_value
exit_time
exit_price
exit_reason
holding_days
gross_return
net_return
commission
tax
slippage
order_status
order_reject_reason
is_limit_up_entry
is_limit_down_exit
```

Allowed `outcome_type` values:

```text
MASTER_ACTUAL
STANDALONE_ACTUAL
INDEPENDENT_COUNTERFACTUAL
```

`STANDALONE_ACTUAL` and `INDEPENDENT_COUNTERFACTUAL` are not Phase 0 implementation targets.

## ATOMIC_EVENT_WIDE

The wide table is an analysis view, not the source of truth.

Source mapping:

```text
identity and signal context: SIGNAL_EVENT
primary block reason: first failed DECISION_EVENT in execution order
all block reasons: all failed DECISION_EVENT rows for the signal
resource occupation fields: DECISION_EVENT GLOBAL_RESOURCE / BRANCH_SLOT rows
order and fill fields: TRADE_OUTCOME MASTER_ACTUAL
```

Core wide fields:

```text
trade_date
code
branch
raw_signal
branch_eligible
master_allowed
master_traded
blocked_stage
blocked_reason_primary
all_block_reasons
occupied_by_branch
occupied_by_code
occupied_by_signal_id
emotion_state
emotion_score
emotion_heat
emotion_momentum
emotion_stress
market_mode
raw_market_mode
active_route
candidate_rank
branch_candidate_count
slots_total
slots_remaining_before
available_cash_before
requested_value
entry_price
exit_price
exit_reason
holding_days
gross_ret
net_ret
ret_after_30bp
ret_after_100bp
is_limit_up_entry
is_limit_down_exit
counterfactual_available
counterfactual_source
```

## Terminal States

Every `branch_eligible` signal must close into one terminal state:

```text
FILLED
FILTERED
ROUTED_OUT
RANKED_OUT
SLOT_BLOCKED
CASH_BLOCKED
ORDER_NOT_CREATED
ORDER_REJECTED
PARTIAL_FILL
DATA_INVALID
UNRESOLVED
```

Strict definitions:

```text
FILLED: at least one buy trade filled and mapped to the signal.
FILTERED: failed branch-native non-route filter after raw pattern hit.
ROUTED_OUT: branch was disabled by motherboard active route or enable flag.
RANKED_OUT: eligible and allowed, but rank exceeded the branch order selection limit.
SLOT_BLOCKED: eligible and allowed, but branch slots were exhausted.
CASH_BLOCKED: eligible and allowed, selected or intended, but available cash was insufficient.
ORDER_NOT_CREATED: buy handler chose not to call an order function after selection.
ORDER_REJECTED: engine created or attempted an order that became rejected or returned None due to rejection logic.
PARTIAL_FILL: order filled partially and retained unfilled quantity.
DATA_INVALID: required price, auction, limit, metadata, or history data was missing or invalid.
UNRESOLVED: Phase 1 observer could not assign a unique terminal state.
```

## Block Reason Enum

```text
BRANCH_FILTER_FAILED
ROUTE_DISABLED
MARKET_MODE_BLOCK
FB_PCT_BLOCK
MONTH_BLOCK
BULL_RELEASE_GUARD
STOPLOSS_COOLDOWN
RZQ_COOLDOWN
BULL_COOLDOWN
SHOCK_COOLDOWN
WIN_RATE_SCALE_ZERO
RANK_OUT
BRANCH_SLOT_FULL
GLOBAL_CASH_INSUFFICIENT
DUPLICATE_POSITION
DUPLICATE_PENDING_ORDER
PAUSED
OPEN_PRICE_INVALID
LIMIT_UP_UNBUYABLE
LIMIT_DOWN_UNSELLABLE
DATA_MISSING
ORDER_NOT_CREATED
ORDER_REJECTED
ORDER_PARTIAL_FILL
UNKNOWN
```

Phase 1 may append new enum values, but must document the semantic change.
