# Schema v0.4 Changelog

Phase 1C adds upstream scan/source attribution facts while preserving Phase 1B downstream event semantics.

## Version Strategy

- Upstream Phase 1C tables use `schema_version = 0.4`.
- Downstream Phase 1B tables keep `schema_version = 0.3`.
- `SIGNAL_EVENT`, `DECISION_EVENT`, `TRADE_OUTCOME`, `ATOMIC_EVENT_WIDE`, and `HANDLER_RESOURCE_SNAPSHOT` keep their Phase 1B field meanings, terminal states, and results.

## New Upstream Tables

- `SCAN_RUN_EVENT`: one main row per `trade_date x branch`, initialized from `prepare_all` before scanner control flow.
- `RAW_PATTERN_EVENT`: observed raw-pattern rows or source-limited prepared-source records.
- `SCAN_DECISION_EVENT`: preparation-stage decisions tied to a pattern/source record.
- `PATTERN_PREPARED_ALIGNMENT`: parent mapping from observed/source-limited records to Phase 1B prepared signals.

## Important Semantics

- Uncalled scanners use `scan_status = NOT_CALLED_BY_CONTROL_FLOW` and keep `raw_pattern_count = null`.
- `SOURCE_LIMITED` at `SCAN_RUN_EVENT.scan_status` describes run-level source coverage.
- `SOURCE_LIMITED` at `RAW_PATTERN_EVENT.scan_terminal_state` describes a single source-limited record.
- Auction cache records use `record_type = SOURCE_LIMITED_PREPARED_RECORD`, `pattern_detected = null`, and do not count as complete raw patterns.
- `raw_pattern_count` only counts `record_type = OBSERVED_RAW_PATTERN`.

## Phase 1C Result Note

The 2023Q1 run closes all 909 Phase 1B prepared candidates to upstream parents/source records: 408 observed raw-pattern parent records and 501 Auction source-limited prepared records. Auction cache prepared-candidate lineage is closed; Auction complete RAW_PATTERN and preparation-filter chain is not established in this phase.
