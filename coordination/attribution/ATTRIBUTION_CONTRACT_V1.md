# Attribution Contract V1

Contract v1.0 is the combined contract of downstream schema `0.3` and upstream scan/source schema `0.4`. It freezes fact identity, null semantics, evidence scope, and lineage rules for Phase 2.

## Fact Tables

| Table | Primary Key / Stable Identity | Purpose |
| --- | --- | --- |
| SIGNAL_EVENT | `signal_id = branch|trade_date|code|signal_variant` | Prepared candidate and terminal lineage |
| DECISION_EVENT | `signal_id + decision_seq` | Downstream decision sequence |
| TRADE_OUTCOME | `signal_id + order_id + trade_ids` | MASTER_ACTUAL trade result allocation |
| ORDER_INTENT | `token` and `order_id` when bound | Order creation lineage |
| EXIT_INTENT | exit intent identity when present | Sell-side lineage extension |
| HANDLER_RESOURCE_SNAPSHOT | `date + time + handler + stage` | Cash/slot/position context |
| LOOP_STOP_EVENT | `date + handler + stop_type + candidate_index` | Loop-level stopping evidence |
| POSITION_BLOCK_AUDIT | `signal_id + reason_code` | Position-related terminal evidence |
| ORDER_NONE_AUDIT | `signal_id + reason_code` | Missing order return evidence |
| SCAN_RUN_EVENT | `scan_run_id = branch|trade_date|MAIN` | Upstream scan invocation/source status |
| RAW_PATTERN_EVENT | `pattern_id = branch|trade_date|code|pattern_variant` | Raw/prepared parent source evidence |
| SCAN_DECISION_EVENT | `pattern_id + decision_seq` | Upstream scan decision sequence when instrumented |
| PATTERN_PREPARED_ALIGNMENT | `pattern_id + prepared_signal_id` | Parent-to-prepared mapping |

## Legal Branches And Variants

- `Auction -> AUCTION_PREPARED`
- `Scorpion -> SCORPION_PREPARED`
- `ZB -> ZB_PREPARED`
- `YJJ -> YJJ_PREPARED`
- `RZQ -> RZQ_PREPARED`

## Legal Terminal States

`FILLED`, `BRANCH_FILTERED`, `MOTHERBOARD_GATED_OUT`, `ROUTED_OUT`, `RANKED_OUT`, `SLOT_BLOCKED`, `CASH_BLOCKED`, `POSITION_BLOCKED`, `ORDER_NOT_CREATED`, `ORDER_REJECTED`, `DATA_INVALID`, `NOT_EVALUATED_AFTER_STOP`, `UNRESOLVED`.

Phase 1E frozen baseline has `UNRESOLVED = 0`. A terminal state may be set only once; a later conflicting terminal state is invalid.

## Legal Scan Status And Source Mode

Scan status values: `EXECUTED`, `EXECUTED_EMPTY`, `NOT_CALLED_BY_CONTROL_FLOW`, `EARLY_RETURN_NO_SOURCE`, `SOURCE_ERROR`, `SOURCE_LIMITED`.

Source modes observed/frozen for 2023: `AUCTION_PREPARE_COMPUTED`, `PROJECT_AUCTION_PREPARE_CACHE`, `PROJECT_BOARD_SNAPSHOT`, `BILLBOARD_API`, `DAILY_PRICE_COMPUTED`, `NOT_APPLICABLE`.

`NOT_CALLED_BY_CONTROL_FLOW` means the branch scanner was not reached by the formal runtime path. `EXECUTED_EMPTY` means the scanner ran and produced no prepared/source parent rows.

## Evidence Scope

Legal evidence scopes: `EXHAUSTIVE_RAW_PATTERN`, `PREPARED_PARENT_ONLY`, `SOURCE_LIMITED`, `NOT_OBSERVED`.

`EXHAUSTIVE_RAW_PATTERN` means the branch directly emits the full raw universe and pre-prepared rejection decisions. `PREPARED_PARENT_ONLY` means the branch emits a parent/source record for prepared or reached candidates but cannot support full raw rejection EV. `SOURCE_LIMITED` means source identity is known but raw semantics are incomplete. `NOT_OBSERVED` means no usable upstream evidence exists.

## Null, False, And Not Evaluated

`null` means not evaluated or not applicable at that layer. It is valid only when explained by upstream control flow or an approved terminal state such as `ROUTED_OUT`, `MOTHERBOARD_GATED_OUT`, `SLOT_BLOCKED`, `NOT_EVALUATED_AFTER_STOP`, `BRANCH_FILTERED`, `DATA_INVALID`, or `POSITION_BLOCKED`.

`false` means evaluated and failed. It must not be collapsed into `null`.

`NOT_EVALUATED` semantics are represented by upstream terminal/loop states and must not be used as evidence of a rule failure.

## Outcome Scope

`MASTER_ACTUAL` is the actual formal strategy execution. `AUDIT_REPLAY` or future counterfactual outputs must not be mixed with `MASTER_ACTUAL` rows without explicit scope columns and manifest separation.

## Order, Trade, And Position Lineage

Buy order lineage maps `ORDER_INTENT -> order_id -> trade -> signal_id`. Sell trades are allocated to open lots by actual execution lineage. Year-end open positions remain valid lineage endpoints and are reported separately; they are not unresolved signals.

## Stable Hashes

Stable hashes are SHA256 over UTF-8 CSV text produced by selecting frozen business columns, coercing to string, sorting by the same columns, and writing `to_csv(index=False)`. See `master_phase1e/HASH_SPEC.md`.
