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
python scripts/validate_scan_all_board_fastpath.py 2021-01-04 2021-01-05 2021-04-23 2020-07-15 2020-08-27 2020-12-18
```

Current check: 2020 and 2021 both validate cleanly against `board_snapshot` for 243 days each.
The `_scan_all` board-cache fast path validates cleanly on the sampled dates above.

## Guardrails

- Do not hardcode individual trades to improve speed or alignment.
- Do not replace JQ compatibility quirks with clean hdata behavior unless a local-vs-JQ harness proves parity.
- Keep engine/JQ-compatibility changes separate from strategy optimization changes.
- Do not modify `母版-20260506-原始版.py`.
- Do not modify the RZQ fast/reference strategies while using them as examples.

## Next Steps

1. Build or verify `master_prepare_index` for 2020 and 2021. 2020 and 2021 have been generated and validated.
2. Add a read API in `DataAPI`, for example `get_project_master_prepare_index(date)`. Done in current workspace.
3. Add an opt-in fast path for mother `_scan_all` / `_scan_boards_for_prev` that consumes the daily index and falls back to the current logic when missing. The current `母版-20260506-Clone.py` checkpoint uses `board_snapshot` inside `_scan_all` for market-wide limit-up and board-count facts, with fallback to the old full-market `history` scan if the cache is missing.
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

## 2026-06-11 Efficiency Checkpoint

Effective commits on the mother alignment path:

- `f59b64b Cache pre-open marks and harden hdata imports`
  - Restored hdata imports after the local `scripts/__init__.py` namespace appeared.
  - Cached repeated pre-open portfolio marks.
  - 2021 warm-to-2021-02-28 probe stayed identical: final value `1048896.80`, trades `38`.
- `0440e01 Skip income merge for valuation-only queries`
  - `get_valuation(fields=[...])` and valuation-only `get_fundamentals(query(...valuation...))` skip the expensive income merge.
  - 10-day probe: `prepare_all` dropped from about `9.80s` to `8.77s`; `_scan_all` from about `2.43s` to `1.12s`; trades unchanged.
- `290a1c2 Skip idle minutes in engine loop`
  - Minute loop now skips minutes with no scheduled handler, no `handle_data`, and no pending orders.
  - 10-day probe stayed identical and engine time dropped from about `24.93s` to `15.08s`.
  - 35-day probe stayed identical and engine time dropped from about `57.67s` to `54.61s`.

Tested but not kept:

- A daily high/low limit cache inside `get_price(frequency='1m')`.
  - 10-day probe stayed identical but only improved about `0.35s`.
  - 35-day probe was slower (`61.52s`), so the change was reverted before commit.

Current 35-day profile after the effective commits:

- `refresh_sec`: about `26.15s`
- `scheduled_sec`: about `26.83s`
- top handlers:
  - `prepare_all`: about `13.89s`
  - `buy_auction_yiqian`: about `10.25s`
  - `buy_v227_天蝎座`: about `1.70s`

Most promising next preprocessing target:

- Build a project-local daily `auction_yiqian_prepare` cache.
- It should mirror `_auction_yiqian_prepare` facts for each trade date:
  - ordered candidates capped by `g.auction_yiqian_candidate_cap`
  - `kind`
  - previous `close`, `money`, `volume`
  - `avg_inc`, `inc4`
  - `left_ok`
- Validate first with a comparison script against the live strategy function over 2020 and 2021 before wiring it into `母版-20260506-Clone.py`.
- Keep the fallback path to the current calculation whenever cache is absent or validation finds a mismatch.

Status update:

- `rebuild_from_archive/project_preprocess.py --only auction-yq YEAR` now generates `project_cache/features/auction_yiqian_prepare/YEAR.parquet`.
- The builder intentionally uses `DataAPI.get_price(..., fq='pre')` for the 4-day candidate window and the 101-day left-pressure window.  Do not replace this with raw pivot arithmetic without a new validation run; raw pivot arithmetic failed on adjusted-price and threshold-boundary cases such as `000733.XSHE` on 2021-07-19.
- Validation helper:

```powershell
python scripts/validate_auction_yiqian_prepare_cache.py 2020
python scripts/validate_auction_yiqian_prepare_cache.py 2021
```

- Current validation:
  - 2020: `OK checked=243 year=2020`
  - 2021: `OK checked=243 year=2021`
- The cache is now wired into `母版-20260506-Clone.py` with fallback to the old calculation when the cache file is missing.
- 2021 warm-to-2021-01-15 probe stayed identical after wiring: final value `983184.66`, trades `7`; `prepare_all` was about `3.72s` over 10 days.
- 2021 warm-to-2021-02-28 probe stayed identical after wiring: final value `1048896.80`, trades `38`; one run showed `prepare_all` about `9.78s` over 35 days, though total wall/engine time still needs more repeat measurements because refresh and buy-auction timings were noisy.
