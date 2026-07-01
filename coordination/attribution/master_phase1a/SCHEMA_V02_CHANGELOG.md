# Schema v0.2 Changelog

This changelog records the mandatory corrections applied before Phase 1A observer implementation.

## 1. Terminal closure scope

Old wording:

```text
Every branch_eligible signal must close into one terminal state.
```

Corrected wording:

```text
Every SIGNAL_EVENT row must close into exactly one terminal_state.
```

Rationale: `branch_eligible` is a path state, not an event-table admission rule. A signal can enter `SIGNAL_EVENT` before branch eligibility is known.

## 2. Phase 1A observation level

Phase 1A starts from post-prepare candidate lists, not true raw scanner hits.

Added fields:

```text
observation_level
prepared_candidate
handler_eligible
```

Phase 1A emits:

```text
observation_level = PREPARED_CANDIDATE
prepared_candidate = true
raw_pattern_hit = null
```

Reserved values for later phases:

```text
RAW_PATTERN
BRANCH_FILTER_INPUT
```

Rationale: prepared candidates must not be mislabeled as complete raw pattern hits.

## 3. Partial fills

Old model:

```text
PARTIAL_FILL as a terminal_state peer of FILLED
```

Corrected model:

```text
terminal_state = FILLED
fill_status = FULL / PARTIAL
```

Added `TRADE_OUTCOME` fields:

```text
fill_status
requested_amount
filled_amount
unfilled_amount
```

Rationale: partial fill is a fill shape, not a mutually exclusive terminal state.

## 4. Schema version

All fact tables now carry:

```text
schema_version = 0.2
```

## 5. New reason enum values

Added:

```text
ORDER_RETURNED_NONE
NOT_EVALUATED_AFTER_LOOP_STOP
EXIT_REASON_UNRESOLVED
```
