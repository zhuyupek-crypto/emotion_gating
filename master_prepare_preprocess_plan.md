# Master Prepare Preprocessing Plan

Date: 2026-06-08

Scope: workspace copy only. Do not edit `D:\work space\local_quant` or `D:\work space\hdata`.

## Why This Exists

Mother-strategy alignment and later optimization are bottlenecked by `prepare_all`.

The latest profile evidence from `rebuild_2025_warm2024_v16` shows:

- `prepare_all`: about 960 seconds across 2024-2025
- `buy_auction_yiqian`: about 194 seconds
- `refresh_sec`: about 458 seconds

So the first high-value target is project-local preprocessing for the market-wide daily facts that `prepare_all` recomputes every morning.

## Existing Read-Only Reference

The `bare_runs_analysis/strategies/rzq/` work has already started this pattern:

- `bare_runs_analysis/feature_extractor.py`
- `bare_runs_analysis/features/rzq_features_YYYY.parquet`
- `bare_runs_analysis/strategies/rzq/strategy_rzq_fast.py`

Use it as a reference only. Do not modify files under `bare_runs_analysis/strategies/rzq/` while doing mother-strategy parity work.

## Existing Project Cache

`rebuild_from_archive/project_preprocess.py` already supports:

- `project_cache/features/board_snapshot/YYYY.parquet`
- `project_cache/features/first_seal_time/YYYY.parquet`
- `project_cache/features/call_auction_by_date/YYYY/YYYYMMDD.parquet`

`rebuild_from_archive/engine/data_api.py` already reads those caches through:

- `get_project_board_snapshot(date)`
- `get_project_master_prepare_index(date)`
- `_load_project_first_seal_year(year)`
- `_load_project_call_auction_day(day)`

The generated cache directory is ignored by Git. Commit source code and concise docs only, not generated parquet outputs.

## New In This Checkpoint

`rebuild_from_archive/project_preprocess.py` now also has:

- `build_master_prepare_index(year, ...)`
- `build_year_bundle(year, ...)`
- CLI entry point:

```powershell
python rebuild_from_archive/project_preprocess.py --only index 2020 2021
```

Use `--only index` for the current lightweight path. The default bundle also rebuilds first-seal and call-auction caches; first-seal can be slow because it may scan minute bars.

The new `master_prepare_index/YYYY.parquet` is intentionally narrow:

- `date`
- `limit_up_close_n`
- `first_board_n`
- `max_board_count_market`
- `first_board_codes`
- `leader_codes`

It is a daily index for `_scan_all` / `_scan_boards_for_prev`, not a full candidate replacement yet.

Validation helper:

```powershell
python scripts/validate_master_prepare_index.py 2021
```

Current check: 2020 and 2021 both validate cleanly against `board_snapshot` for 243 days each.

## Guardrails

- Do not hardcode individual trades to improve speed or alignment.
- Do not replace JQ compatibility quirks with clean hdata behavior unless a local-vs-JQ harness proves parity.
- Keep engine/JQ-compatibility changes separate from strategy optimization changes.
- Do not modify `母版-20260506-原始版.py`.
- Do not modify the RZQ fast/reference strategies while using them as examples.

## Next Steps

1. Build or verify `master_prepare_index` for 2020 and 2021. 2020 and 2021 have been generated and validated.
2. Add a read API in `DataAPI`, for example `get_project_master_prepare_index(date)`. Done in current workspace.
3. Add an opt-in fast path for mother `_scan_all` / `_scan_boards_for_prev` that consumes the daily index and falls back to the current logic when missing.
4. Validate the fast path against current logic for 2020:
   - `prev_first_boards`
   - `_today_max_boards`
   - `leader_candidates_for_tag`
   - `first_board_perf`
   - `fb_pct`
5. Only after those are equal, extend preprocessing to:
   - `auction_yiqian_candidates`
   - `rzq_candidates`
   - `zb_candidates`
   - left-pressure facts

## Current Alignment Context

- 2020 trade keys were previously aligned exactly: 395 local / 395 JQ / 0 missing / 0 extra.
- Amount, price, and cash are not exact parity.
- 2021 first known trade-key mismatch was local duplicate pre-open buying of `002120.XSHE` on 2021-04-26.
- Commit `58689bc` fixed the underlying engine issue: pre-open pending buys now reserve visible, non-closeable position amount and do not double-count portfolio value.

## Current Git Notes

There may be unrelated uncommitted changes in:

- `bare_runs_analysis/run_backtests.py`
- `bare_runs_analysis/strategies/strategy_v227_scorp.py`

Those belong to naked-run/optimization work. Do not mix them into mother alignment commits.
