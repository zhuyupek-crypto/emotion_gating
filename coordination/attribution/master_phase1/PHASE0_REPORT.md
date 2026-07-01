# Phase 0 Report

Conclusion: PASS for static Phase 0 preparation.

This phase created a dedicated worktree and branch from the frozen motherboard baseline, produced file hashes and baseline manifests, audited the main static call chain, froze event schema v0.1, and identified observer gaps. It did not modify formal strategy, engine, compatibility, or hdata reader behavior.

## Branch and Baseline

```text
worktree: D:\Work Space\他山之石\情绪门控\worktrees\motherboard-attribution-phase0-v1
branch: codex/motherboard-attribution-phase0-v1
commit: cf542415191e952aa328250a3ee86bb15346a6b8
tag at HEAD: motherboard-performance-baseline-v1
```

## Motherboard

```text
path: 母版-20260506-Clone.py
sha256: 621a9c968473d73dfa1699be0a16714790e4f93ab950957c0a3f88f4f34bcc8e
line_count: 2226
```

## Naked Branch Assets

| Branch | Path | Purity status | Note |
| --- | --- | --- | --- |
| YJJ | `codex_strategy_dissection/branch_strategies/mother_branch_force_v227.py` | PURE_UNCERTAIN | `force_v227` includes both YJJ and Scorpion. |
| Scorpion | `scorp_optimize/strategies/strategy_v227_scorp.py` | PURE_PASS | Dedicated Scorpion research strategy exists; still revalidate observer mapping in Phase 1. |
| RZQ | `codex_strategy_dissection/branch_strategies/mother_branch_force_rzq.py` | NOT_AUDITED | Force copy exists, no formal purity proof found in Phase 0. |
| ZB | `codex_strategy_dissection/branch_strategies/mother_branch_force_zb.py` | NOT_AUDITED | Force copy exists, no formal purity proof found in Phase 0. |
| Auction | `codex_strategy_dissection/branch_strategies/mother_branch_force_auction.py` | NOT_AUDITED | Force copy exists; data timing remains a major audit item. |

## Engine

Core paths:

```text
rebuild_from_archive/engine/core.py
rebuild_from_archive/engine/context.py
rebuild_from_archive/engine/order.py
rebuild_from_archive/engine/data_api.py
rebuild_from_archive/project_compat.py
rebuild_from_archive/jqdata_compat.py
```

Current trade fields:

```text
time, code, amount, price, commission, tax, trade_id, order_id
```

Current order fields:

```text
order_id, security, amount, filled, price, avg_cost, style, side, status, add_time, commission
```

Current state snapshot fields include market state, active route, enable flags, slots, candidate counts, cash, positions, and owner map.

## Confirmed Schedule

```text
9:05 prepare_all
9:26 buy_auction_yiqian
9:26 buy_v227_一进二
9:27 buy_rzq
9:28 buy_zb
9:30 buy_v227_天蝎座
11:25 sell_v227_morning
11:25 sell_auction_yiqian
11:28 sell_rzq_slots
11:30 sell_zb_slots
every_bar check_stop_all
13:01 sell_v227_midday
14:47 sell_rzq_slots
14:48 sell_zb_slots
14:50 sell_v227_afternoon
14:50 sell_auction_yiqian
14:50 sell_rzq_slots
14:52 sell_zb_slots
14:55 tag_leaders
```

## Current Directly Observable

```text
daily market state
raw market state
active route
FB and fb_pct
cooldowns
enable flags
slots
candidate counts
cash and locked cash
positions and owner map
orders
trades
compat order-presence events
```

## Must Add Observer

```text
raw_pattern_hit per branch/date/code
branch_eligible per branch/date/code
per-filter pass/fail reason
candidate ordering and rank-outs
slot/cash snapshots per candidate and per handler
order_intent before order call
signal_id -> order_id
order_id -> branch
trade_id -> original signal_id
exit reason -> original signal_id
occupied_by resource attribution
```

## Data Timing Risk

CLEAR:

```text
hdata daily price
hdata minute price
engine open/close reference fields, subject to call-date validation
high_limit/low_limit fields
```

RISK:

```text
call auction features
auction buy/sell pressure fields
pre-open order reference price behavior
```

UNKNOWN:

```text
board snapshot physical source and exact timestamp
industry mapping if used
fundamental or valuation data if used by future branches
effective-date semantics for some metadata fields
```

## Deliverables

```text
OVERALL_ATTRIBUTION_PLAN.md
CODE_INVENTORY.md
EVENT_SCHEMA.md
OBSERVABILITY_GAP.md
PHASE0_REPORT.md
FILE_HASHES.json
BRANCH_BASELINE_MANIFEST.json
STATIC_INVENTORY.json
research/attribution_phase0_inventory.py
```

## Phase 1 Recommendation

Start with the smallest motherboard observer:

```text
scope: motherboard only
window: 2023-01-01 to 2023-03-31
outcome_type: MASTER_ACTUAL only
goal: map actual buys to unique branch/signal_id and prove observer-on/off behavior identity
defer: branch-native counterfactuals, full alpha matrix, full eight-year run
```

## Open Issues

```text
YJJ is not isolated from Scorpion in force_v227 assets.
RZQ/ZB/Auction force copies are not purity-proven.
Auction data availability and timing remain unproven.
Observer design still needs exact emit placement inside each buy handler.
External hdata reader is recorded by hash but not committed.
```
