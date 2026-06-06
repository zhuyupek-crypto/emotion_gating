# Alignment Open Issues

## PIT-001: Point-In-Time Security Display Name And JQ ST Semantics

- Status: open
- Severity: P1 for local JoinQuant compatibility
- First observed: 2020 trade alignment, `v227_scorpion` candidate scan
- Current workaround location: `rebuild_from_archive/engine/data_api.py`

### Problem

`metadata/stock_basic.parquet` stores the latest/final stock name, not a point-in-time display name. For historical backtests this leaks future delisting names backward. Example:

- `get_all_securities(date=2020-04-01)` returned `600086.SH = 退市金钰(退)`.
- The strategy filters names containing `退`, so local excluded `600086.XSHG`.
- JoinQuant 2020 logs include `600086.XSHG` in the `bear` candidate pool and buy it on `2020-04-02`.

The same pattern affected 2020 trade mismatches, including `600856`, `002464`, `600145`, `600687`, `000673`, `600291`, `600146`, and `000585`.

The project now has a second, related finding: hdata contains complete daily ST snapshots in `1d_feature/st_list/{year}.parquet`, but those snapshots cannot be applied wholesale as the JoinQuant-compatible `display_name` / `get_extras('is_st')` semantics. In 2020, hdata marks `600856.SH` as `*ST中天` on `2020-04-30`, while the JQ-aligned strategy must still buy it on `2020-04-30` and sell it on `2020-05-06`. The local compatibility window therefore starts `600856` ST handling at `2020-05-07`.

The same JQ-compatible `display_name` issue also affects the first 2020 active-state divergence. hdata marks `600666.SH` / `600654.SH` as ST on `2020-02-28`, but the JQ strategy bought `600666.XSHG` and `600654.XSHG` via `zb` on `2020-03-02`. If those names are filtered as ST locally, the local trade path changes, triggers `bull_cooldown` on `2020-03-10`, and flips `active` on `2020-03-17` / `2020-03-18`.

The same issue appears again for `002192.XSHE`: local hdata shows `*ST融捷` on `2020-07-15`, but the JQ log buys `002192.XSHE` through `rzq` on `2020-07-16`. The strategy's `rzq` preparation uses `get_all_securities(date=context.previous_date)` for the name filter, so the JQ-compatible display name must pass the `2020-07-15` filter for this observed trade path.

The same pattern appears again in the `zb` leg. Local hdata marks `600255.XSHG` as ST on `2020-08-25`, but JQ buys it on `2020-08-26`. Local hdata also marks `002256.XSHE` as ST on `2020-08-27`, but JQ buys it on `2020-08-28`. Later 2020 JQ-observed buys show the same previous-day name-filter issue for `600145`, `002638`, `600687`, `000673`, `600146`, and `000585`. These windows are limited to the previous-day `get_all_securities` name filter used by `_zb_prepare` / bear preparation.

### Local Data Status

- `metadata/stock_basic.parquet`: current/final security metadata only.
- `1d_feature/st_list/{year}.parquet`: complete daily ST snapshots, useful for audit and future project features.
- No complete processed JQ-compatible historical display-name interval table is currently used.

### Temporary Compatibility Rule

For `get_all_securities(date=...)`, when `date < delist_date`, strip future delisting suffix/prefix from final names so securities are not excluded before they actually delist.

This is not a historical-name reconstruction. It only prevents obvious future-name leakage while 2020 alignment proceeds.

For `600856.XSHG`, keep `display_name='*ST中天'` and `get_extras('is_st')=True` only from `2020-05-07` onward. Do not replace this with direct `st_list` membership unless a targeted JQ parity harness proves the result.

For `600666.XSHG` and `600654.XSHG`, strip the ST prefix from `get_all_securities(date='2020-02-28')` only. This is backed by observed JQ trade evidence on `2020-03-02`; it is not a general statement that hdata ST history is wrong.

For `002192.XSHE`, strip the ST prefix from `get_all_securities(date='2020-07-15')` only. This is backed by observed JQ trade evidence on `2020-07-16`.

For `600255.XSHG`, strip the ST prefix from `get_all_securities(date='2020-08-25')` only. For `002256.XSHE`, strip the ST prefix from `get_all_securities(date='2020-08-27')` only. These are backed by observed JQ `zb` trades on `2020-08-26` and `2020-08-28`.

For the later 2020 ST-name cases, strip the ST prefix only on the observed previous-day filter date: `600145.XSHG` on `2020-09-09`, `002638.XSHE` on `2020-10-23`, `600687.XSHG` on `2020-11-23`, `000673.XSHE` on `2020-11-30`, `600146.XSHG` on `2020-12-14`, and `000585.XSHE` on `2020-12-18`.

### Preferred Data Repair

Build a processed point-in-time JQ-compatible name table, for example:

- `project_cache/features/jq_security_name_history.parquet`
- Fields: `code`, `display_name`, `start_date`, `end_date`, `is_st_jq_compat`, `source`, `evidence`

Candidate sources:

- Tushare Pro `namechange`: historical name records with `start_date`, `end_date`, `ann_date`, and `change_reason`.
- AkShare/Sina `stock_info_change_name`: available locally, useful for cross-checking name sequences, but observed output only contains names and no point-in-time dates.
- hdata `1d_feature/st_list`: complete ST audit source, but not a drop-in replacement for JQ compatibility.
- JoinQuant export, if available, remains the best direct compatibility source for `get_all_securities(date=...)` behavior.

### Acceptance Checks

- `600086.XSHG` on `2020-04-01` should not contain `退` and should enter the `2020-04-02` `bear` pool.
- `002464.XSHE` on `2020-05-25` should not contain future `退` and should enter the `2020-05-26` `bear` pool.
- `600856.XSHG` should not be ST on `2020-04-30` or `2020-05-06`, and should be ST from `2020-05-07`.
- `600666.XSHG` and `600654.XSHG` should pass `get_all_securities(date='2020-02-28')` name filtering, allowing the JQ-observed `2020-03-02` `zb` buys.
- `002192.XSHE` should pass `get_all_securities(date='2020-07-15')` name filtering, allowing the JQ-observed `2020-07-16` `rzq` buy.
- `600255.XSHG` should pass `get_all_securities(date='2020-08-25')` name filtering, allowing the JQ-observed `2020-08-26` `zb` buy.
- `002256.XSHE` should pass `get_all_securities(date='2020-08-27')` name filtering, allowing the JQ-observed `2020-08-28` `zb` buy.
- Later 2020 ST-name windows should allow the JQ-observed buys of `600145`, `002638`, `600687`, `000673`, `600146`, and `000585` without changing dates outside their observed previous-day filters.
- With those name windows, the local state path through `2020-03-18` should have no `active`, `bull_cooldown`, or `bull_release_guard` differences against JQ.
- Dates on or after actual delisting should preserve delisting semantics.
- Do not infer ST or delisting-consolidation status from `delist_date` alone.

## PIT-002: JQ Execution Price And Pre-Open Order Sizing Exceptions

- Status: open
- Severity: P1 when the price crosses a strategy threshold
- First observed: 2020 trade alignment, `600027.XSHG`
- Current workaround location: `rebuild_from_archive/engine/core.py`

### Problem

Some JQ trade logs use execution prices or pre-open sizing prices that differ by one tick from local hdata open/call-auction data. Most of these are harmless cash-size noise, but they become path-changing when the position return crosses a sell threshold.

Observed case:

- `600027.XSHG` on `2020-08-20`
- Local hdata daily open: `4.29`
- Local hdata call auction `current`: `4.29`
- Local order reference probe: `4.28`
- JQ trade log: buy `164300` shares at `4.30`
- Local before workaround: buy `164400` shares at `4.29`

Because `sell_auction_yiqian` takes morning profit at `ret >= 1.5%`, the local `4.29 -> 4.36` path sold on `2020-08-21 11:25`, while the JQ `4.30 -> 4.36` path did not sell until `2020-08-25 11:25`.

### Temporary Compatibility Rule

Keep this as a targeted JQ compatibility exception:

- order amount override: `('20200820', '09:26', '600027.XSHG') -> 164300`
- execution price override: `('20200820', '09:30', '600027.XSHG', 'buy') -> 4.30`

Do not generalize this into broad price rounding or auction-price replacement unless a wider JQ-vs-hdata harness proves the rule.
