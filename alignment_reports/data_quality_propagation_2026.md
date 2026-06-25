# 2026 Data Quality Propagation Audit

- Audit range: `2026-05-18` to `2026-07-31`
- Configured corrupted window: `2026-05-25` to `2026-06-12`
- Observed raw corruption span in 2026 pivot data: `2026-05-25` to `2026-12-31`

## Dependency Graph

```text
raw_pivot
  |- board_snapshot
  |    |- first_seal_time
  |    `- master_prepare_index
  |- auction_yiqian_prepare
  `- call_auction_by_date (separate source tree; lineage not proven clean)
```

## Raw Source Findings

### `close`
- Observed anomaly span: `2026-05-25` to `2026-12-31`
- Configured compat point overrides in 2026: `0`
- Interpretation: the few point overrides are not enough; the broad-market canonical contamination pattern means these rows are not trustworthy as source data.

### `open`
- Observed anomaly span: `2026-05-25` to `2026-12-31`
- Configured compat point overrides in 2026: `0`
- Interpretation: the few point overrides are not enough; the broad-market canonical contamination pattern means these rows are not trustworthy as source data.

### `high`
- Observed anomaly span: `2026-05-25` to `2026-12-31`
- Configured compat point overrides in 2026: `2`
- Interpretation: the few point overrides are not enough; the broad-market canonical contamination pattern means these rows are not trustworthy as source data.

### `low`
- Observed anomaly span: `2026-05-25` to `2026-12-31`
- Configured compat point overrides in 2026: `0`
- Interpretation: the few point overrides are not enough; the broad-market canonical contamination pattern means these rows are not trustworthy as source data.

### `pre_close`
- Observed anomaly span: `2026-05-25` to `2026-12-31`
- Configured compat point overrides in 2026: `0`
- Interpretation: the few point overrides are not enough; the broad-market canonical contamination pattern means these rows are not trustworthy as source data.

### `high_limit`
- Observed anomaly span: `2026-05-25` to `2026-12-31`
- Configured compat point overrides in 2026: `2`
- Interpretation: the few point overrides are not enough; the broad-market canonical contamination pattern means these rows are not trustworthy as source data.

### `low_limit`
- Observed anomaly span: `2026-05-25` to `2026-12-31`
- Configured compat point overrides in 2026: `0`
- Interpretation: the few point overrides are not enough; the broad-market canonical contamination pattern means these rows are not trustworthy as source data.

### `money`
- Observed anomaly span: `2026-05-25` to `2026-12-31`
- Configured compat point overrides in 2026: `0`
- Interpretation: the few point overrides are not enough; the broad-market canonical contamination pattern means these rows are not trustworthy as source data.

### `volume`
- Observed anomaly span: `2026-05-25` to `2026-12-31`
- Configured compat point overrides in 2026: `0`
- Interpretation: the few point overrides are not enough; the broad-market canonical contamination pattern means these rows are not trustworthy as source data.

## Derived Cache Findings

- `board_snapshot/2026.parquet`: contains rows for the configured window and remains contaminated through at least `2026-12-31`; runtime only blocks reads from `2026-05-25` to `2026-06-12`.
- `first_seal_time/2026.parquet`: contains `5047` rows on `2026-05-25`, then stops. This proves the first-board identity pollution entered the derived cache before the cache went silent.
- `master_prepare_index/2026.parquet`: inherits `board_snapshot` contamination and keeps returning one row per trading day with inflated counts through at least `2026-12-31`.
- `auction_yiqian_prepare/2026.parquet`: disk rows stop at `2026-05-25`, but the feature's t-1/t-4 and 101-day dependencies mean later dates are still unsafe; the current runtime treats empty cache as 'do nothing', not as 'safe'.
- `call_auction_by_date/2026/`: uses a separate source tree, so this audit cannot prove it is contaminated by the pivot issue, but it also cannot certify the upstream lineage as safe.

## Runtime Protection Gaps

- `should_bypass_history_fastpath` does not cover `open`, `close`, `high`, or `low`, even though the raw contamination pattern affects those fields too.
- A `history(..., field='high')` call can still bypass the configured guard.
- `get_project_master_prepare_index` has no quarantine behavior.
- `get_project_board_snapshot` only quarantines the configured date window; it exposes contaminated post-window rows directly.
- `get_project_auction_yiqian_prepare` returns an empty cached DataFrame for later dates, which suppresses strategy logic without proving data safety.

## Proven vs Not Proven

### Proven
- Raw pivot corruption starts on `2026-05-25` and is still present at least through `2026-07-31` (and observed through `2026-12-31`).
- `board_snapshot` and `master_prepare_index` both contain and expose contaminated derived rows.
- `first_seal_time` contains contaminated rows on `2026-05-25`.
- `auction_yiqian_prepare` is not safe after `2026-05-25` just because later cache rows are missing.
- 2026 checkpoints and state outputs exist inside the contaminated window and should be treated as downstream products.

### Not Proven
- A first confirmed safe post-window date for `board_snapshot`, `first_seal_time`, `master_prepare_index`, or `auction_yiqian_prepare`.
- That `call_auction_by_date` is isolated from the same upstream data-quality issue.
- That any 2026 downstream alignment artifact can be used as a clean reference.

## Next-Stage Isolation Recommendations

- Add source-quality flags at the raw-pivot layer instead of relying on date checks embedded in runtime readers.
- Prevent cache builders from materializing rows when any required source date/field is already marked corrupted or unknown.
- Attach source lineage and quality metadata to each cache year so runtime can distinguish `allow`, `quarantine`, `fallback`, `rebuild_required`, and `unavailable`.
- Apply the same quality policy to preprocess and runtime; do not let post-window cache rows bypass protection once the source remains dirty.
