# Event Schema v0.2

Phase 1A uses this schema for the first runnable motherboard observer. It is deliberately honest about the first observation level: Phase 1A starts from prepared candidate lists, not true raw pattern hits inside the scanner.

All fact tables must include:

```text
schema_version = 0.2
```

## Identity

`signal_id` format:

```text
{branch}|{trade_date}|{code}|{signal_variant}
```

The same stock on the same date can be recognized by multiple branches and must not be merged.

## Observation Levels

Allowed `observation_level` values:

```text
PREPARED_CANDIDATE
RAW_PATTERN
BRANCH_FILTER_INPUT
```

Phase 1A only emits:

```text
observation_level = PREPARED_CANDIDATE
raw_pattern_hit = null
prepared_candidate = true
```

Do not describe Phase 1A prepared candidates as full raw signals. True `RAW_PATTERN` events are reserved for later instrumentation inside scan/filter functions.

## SIGNAL_EVENT

One row per observed `trade_date x code x branch x signal_variant`.

Every row that enters `SIGNAL_EVENT` must close into exactly one `terminal_state`.

Required fields:

```text
schema_version
signal_id
trade_date
signal_time
code
branch
signal_variant
strategy_commit
strategy_sha256
observation_level
raw_pattern_hit
prepared_candidate
handler_eligible
branch_eligible
raw_candidate_rank
final_candidate_rank
branch_candidate_count
terminal_state
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

Field semantics:

```text
prepared_candidate: true when the candidate was present in a post-prepare branch list.
handler_eligible: true only after the buy handler actually reaches the candidate and evaluates handler-local conditions.
branch_eligible: branch-defined eligibility state; not a prerequisite for entering SIGNAL_EVENT.
raw_pattern_hit: null in Phase 1A unless later RAW_PATTERN instrumentation exists.
terminal_state: unique final state for this SIGNAL_EVENT row.
```

`branch_payload` is a branch-specific JSON object. The schema intentionally does not force YJJ, Scorpion, RZQ, ZB, and Auction to share the same shape features.

## DECISION_EVENT

One signal can have multiple decision rows.

Required fields:

```text
schema_version
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
LOOP_CONTROL
```

## TRADE_OUTCOME

Phase 1A implements `MASTER_ACTUAL`. Other outcome types are reserved.

Required fields:

```text
schema_version
signal_id
outcome_type
actual_traded
order_id
trade_ids
entry_time
entry_price
entry_amount
entry_value
requested_amount
filled_amount
unfilled_amount
fill_status
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

Allowed `fill_status` values:

```text
NONE
FULL
PARTIAL
```

Partial fills are represented as:

```text
terminal_state = FILLED
fill_status = PARTIAL
```

They are not a separate terminal state.

## HANDLER_RESOURCE_SNAPSHOT

Phase 1A records handler-level before/after snapshots.

Required fields:

```text
schema_version
date
time
handler
stage
available_cash
locked_cash
portfolio_total_value
positions_count
positions
owners
pending_order_count
pending_order_ids
slot_v227
slot_rzq
slot_zb
slot_auction
candidate_counts
candidate_codes
```

## ATOMIC_EVENT_WIDE

The wide table is an analysis view, not the source of truth.

Source mapping:

```text
identity and signal context: SIGNAL_EVENT
primary block reason: first failed DECISION_EVENT in execution order
all block reasons: all failed DECISION_EVENT rows for the signal
resource occupation fields: DECISION_EVENT GLOBAL_RESOURCE / BRANCH_SLOT rows
order and fill fields: TRADE_OUTCOME MASTER_ACTUAL
fill status: TRADE_OUTCOME.fill_status
terminal state: SIGNAL_EVENT.terminal_state
```

Core wide fields:

```text
schema_version
trade_date
code
branch
observation_level
prepared_candidate
handler_eligible
raw_signal
raw_pattern_hit
branch_eligible
master_allowed
master_traded
terminal_state
fill_status
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
requested_amount
filled_amount
unfilled_amount
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

Every `SIGNAL_EVENT` row must close into one terminal state:

```text
FILLED
FILTERED
ROUTED_OUT
RANKED_OUT
SLOT_BLOCKED
CASH_BLOCKED
ORDER_NOT_CREATED
ORDER_REJECTED
DATA_INVALID
UNRESOLVED
```

Strict definitions:

```text
FILLED: at least one buy trade filled and mapped to the signal. Use fill_status to distinguish FULL and PARTIAL.
FILTERED: observed before branch eligibility and failed branch-native non-route filter. Phase 1A should rarely use this because it starts at PREPARED_CANDIDATE.
ROUTED_OUT: branch was disabled by motherboard active route or enable flag.
RANKED_OUT: signal was allowed but rank exceeded the branch order selection limit.
SLOT_BLOCKED: signal was allowed but branch slots were exhausted.
CASH_BLOCKED: signal was allowed and selected or intended, but available cash was insufficient.
ORDER_NOT_CREATED: buy handler chose not to call an order function after selection or candidate evaluation.
ORDER_REJECTED: order function returned None due to rejection logic or returned a rejected Order.
DATA_INVALID: required price, auction, limit, metadata, or history data was missing or invalid.
UNRESOLVED: observer could not assign a unique terminal state, including candidates not evaluated after original loop stop.
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
ORDER_RETURNED_NONE
ORDER_REJECTED
ORDER_PARTIAL_FILL
NOT_EVALUATED_AFTER_LOOP_STOP
EXIT_REASON_UNRESOLVED
UNKNOWN
```

Phase 1 may append new enum values, but must document the semantic change.
