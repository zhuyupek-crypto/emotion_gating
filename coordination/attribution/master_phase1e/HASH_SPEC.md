# Hash Spec

All hashes are SHA256 over UTF-8 CSV text from pandas `to_csv(index=False)` after selecting columns, coercing to string, and sorting by those columns.

- signal_key_sha256: `trade_date, branch, code, signal_variant`
- terminal_state_sha256: `trade_date, branch, code, signal_variant, terminal_state`
- source_mode_sha256: distinct `prepared_signal_id, source_mode` from RAW_PATTERN_EVENT
- raw_pattern_identity_sha256: `pattern_id, prepared_signal_id, source_mode, scan_terminal_state`
- scan_run_identity_sha256: `scan_run_id, branch, scan_status, source_mode, prepared_candidate_count, raw_pattern_count`
- order_lineage_sha256: `signal_id, branch, code, side, order_id, order_status`
- trade_lineage_sha256: `signal_id, order_id, entry_time, entry_price, entry_amount, fill_status`
