# Observability Gap

## Current Directly Available

From `Engine.daily_state_snapshots`:

```text
date
market_mode
raw_market_mode
active
FB
fb_pct
bull_sticky
bull_cooldown
bull_release_pending
bull_release_guard
stoploss_cooldown
rzq_cooldown
v227_shock_cooldown
enable_v227
enable_rzq
enable_zb
enable_auction
slot_v227
slot_rzq
slot_zb
slot_auction
cand_yjj
cand_bear
cand_rzq
cand_zb
cand_auction
auction_daily_value
recent_wr
core_wr
available_cash
locked_cash
positions_count
positions
owners
```

From `Engine.trades`:

```text
time
code
amount
price
commission
tax
trade_id
order_id
```

From `Engine.orders` / `Order`:

```text
order_id
security
amount
filled
price
avg_cost
style
side
status
add_time
commission
```

From compatibility telemetry:

```text
pre-open order presence events
pre-open cash-floor rejection hooks
pre-open duplicate-order anomaly hooks
```

## Available Through Read-Only Snapshots

The observer can capture these without changing behavior:

```text
handler name and scheduled time
available_cash before and after handler
locked_cash before and after handler
positions before and after handler
pending orders before and after handler
branch slots before and after handler
candidate list lengths
candidate code lists after prepare functions
owner map before and after handler
```

## Must Be Emitted at Strategy Execution Site

These cannot be reliably reconstructed from final trades:

| Branch | Function | Event | Why final logs are insufficient |
| --- | --- | --- | --- |
| all | `prepare_all` and branch prepare functions | raw pattern and branch eligibility | A missing final trade may mean no signal, filtered signal, or route/resource block. |
| all | buy handlers | environment/route gate decision | `enable_*` values are daily, but signal-level block reasons need execution order. |
| all | buy handlers | rank and selected_for_order | Candidate ordering can be branch-specific and partially transformed. |
| all | buy handlers | slot remaining before each candidate | Final positions do not prove which candidate exhausted the slot. |
| all | buy handlers | cash before each order intent | Cash is path-dependent across 9:26/9:27/9:28/9:30 handlers. |
| all | buy handlers | `signal_id -> order_id` | Owner and buy time are not enough for branch identity. |
| all | sell handlers | exit reason and original `signal_id` | Current trades know order_id but not branch-native exit reason. |
| engine | `_create_order` | order rejection reason | Some rejections return `None`, some create rejected orders. |
| engine | `_execute_trade` | fill mapping | Trade rows have order_id but not signal_id unless order map exists. |

## Behavior Change Risk

Low-risk observer points:

```text
before/after handler resource snapshots
after prepare function candidate list snapshots
after route decision daily state snapshot
after order return mapping
after trade append mapping
```

Higher-risk observer points:

```text
inside tight candidate loops if emit logic allocates heavily
around exception paths if observer accidentally catches strategy exceptions
inside order matching if observer mutates order objects
```

Phase 1 should implement the smallest useful observer and verify observer-on/off identity before adding counterfactual machinery.

## Minimum Phase 1 Scope

```text
Motherboard only
2023-01-01 to 2023-03-31
MASTER_ACTUAL only
actual buy trades 100% mapped to branch and signal_id
orders 100% mapped to initiating handler
unfilled candidates distinguish route, rank, slot, cash, order failure when observable
observer-on and observer-off trades/net value/state snapshots identical
```
