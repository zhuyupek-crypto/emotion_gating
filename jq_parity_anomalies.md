# JQ Parity Anomalies

This file records project-local compatibility rules that intentionally reproduce observed JoinQuant behavior. Treat these as guarded alignment rules, not generic hdata data fixes.

## Current 2020 Baseline

- Command: `python run_rebuild_year_v16.py 2020`
- Compare: `python compare_real_trades_2020.py rebuild_2020_v16/local_trades_2020.csv`
- DCA result: `jq_trades=395 local_trades=395`, `key match both=395 jq_only=0 local_only=0`
- Last known full-year runtime: about 13 minutes after v16 batching/cache work.

## Red Rules

These rules can break 2020 alignment if replaced by cleaner-looking raw hdata logic.

### Daily History Anomalies

Location: `rebuild_from_archive/engine/data_api.py`

- IPO sync-delay snapshots:
  - `605399.XSHG` on `2020-08-04`: `13.16`
  - `605123.XSHG` on `2020-08-25`: `30.33`
  - `605255.XSHG` on `2020-08-25`: `12.66`
  - `605369.XSHG` on `2020-09-16`: `31.65`
- Point value anomaly:
  - `002256.XSHE` on `2020-08-28`, field `open`: `1.24`
  - `603393.XSHG` on `2021-09-10`, field `high`: `40.42`
  - `000420.XSHE` on `2021-11-15`, field `money`: `965000000.0`

These preserve observed JQ daily-history quirks. They are applied to both wide and long-form `get_price` results.

### Call Auction Anomalies

Location: `rebuild_from_archive/engine/data_api.py`

- Empty local auction for JQ parity:
  - `002897.XSHE` on `2020-03-04`
  - `600804.XSHG` on `2021-09-01`
- Date-level visibility guard:
  - `2021-08-18`: keep only `000833.XSHE` visible to call-auction queries.
  - `2021-12-02`: keep no securities visible to call-auction queries.
- Depth patch:
  - `002635.XSHE` on `2020-09-03`, `a1_v=2000.0`
  - `000038.XSHE` on `2021-06-04`, `a1_v=40000.0`

These affect auction ranking and should only change with a targeted candidate-ranking check.

### First-Seal Time Anomalies

Locations:

- `rebuild_from_archive/engine/data_api.py`
- `rebuild_from_archive/project_preprocess.py`

Rules:

- `300118.XSHE` on `2020-07-13`: first limit hit `2020-07-13 14:00:00`
- `600711.XSHG` on `2020-07-13`: first limit hit `2020-07-13 14:00:00`

Keep the runtime and preprocessed cache paths consistent.

### Minute Price Anomalies

Location: `rebuild_from_archive/engine/core.py`

- `000592.XSHE` on `2021-05-19 11:28`: use `3.17` instead of local minute close `3.16`.
- `002176.XSHE` on `2021-08-09 14:52`: use `24.84` instead of local minute close `24.82`.

This preserves the observed 2021 JQ `rzq` exit timing: local close `3.16` triggers `ret < -3%` on `2021-05-19 11:28`, while JQ keeps the position and exits at the `2021-05-20` open.
It also preserves the observed 2021 JQ `zb` profit exit timing for `002176.XSHE`: local close `24.82` is below the `24.83` entry average, while the JQ-compatible tick triggers the `2021-08-09 14:52` sell.

The anomaly must be applied to both `_get_trade_price` and the batched position-price refresh path, because `get_current_data()[s].last_price` can hit the refreshed trade-price cache before `_get_trade_price` is called directly.

### Security Metadata And ST Semantics

Location: `rebuild_from_archive/engine/data_api.py`

- IPO listing-date overrides:
  - `605399.XSHG`: `2020-08-03`
  - `605123.XSHG`: `2020-08-21`
  - `605255.XSHG`: `2020-08-21`
  - `605369.XSHG`: `2020-09-14`
- Point-in-time display-name guard strips future delisting markers from active securities.
- `600856.XSHG` must become `*ST中天` only from `2020-05-07`.
- `get_extras('is_st')` must keep the same `600856` window.
- The hdata `1d_feature/st_list/{year}.parquet` files are complete ST audit data, but they are not a drop-in replacement for JQ-compatible strategy filtering.

### Billboard Anomaly

Location: `rebuild_from_archive/engine/data_api.py`

- Remove `600146.XSHG` on `2020-02-26` from local billboard results.

This mirrors the observed 2020 JQ strategy log, where that local three-day deviation record did not drive a `2020-02-27` buy.

### 2024 ETF Temporary Fallback

Location: `rebuild_from_archive/engine/temporary_fallbacks.py` and `rebuild_from_archive/engine/data_api.py`

- `511880.XSHG` has temporary official price injection and zero-fee handling for 2024.
- This does not affect 2020 stock DCA, but it is a red rule for later-year alignment until replaced by a proper ETF data adapter.

## Yellow Rules

These are performance caches or project-local preprocessed features. They may be optimized, but each change needs a small regression before any full-year run.

- `get_current_data` daily snapshot cache in `rebuild_from_archive/engine/core.py`
- `_get_trade_price` daily early/late snapshot fast path in `rebuild_from_archive/engine/core.py`
- `get_call_auction` query cache in `rebuild_from_archive/engine/data_api.py`
- `project_cache/features/board_snapshot/{year}.parquet`
- `project_cache/features/first_seal_time/{year}.parquet`

## Validation Discipline

For any change touching red or yellow rules:

1. Run a direct sample check for the affected stock/date.
2. Run a short profile or target-window rebuild.
3. Run a known risk window if the change touches candidate ranking or ST/name semantics.
4. Run the full-year 2020 rebuild only after the shorter checks pass.
5. Compare with `compare_real_trades_2020.py` and require `jq_only=0 local_only=0`.

Avoid using the full 2020 run as the first detector for localized data-semantics changes.
