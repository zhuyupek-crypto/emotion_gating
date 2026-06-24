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

For the 2021 ST/name cases, strip the ST prefix only on the observed previous-day filter date: `002147.XSHE` on `2021-01-14`, `600702.XSHG` on `2021-04-21`, `601020.XSHG` on `2021-09-10`, and `000980.XSHE` on `2021-12-10`.

User-provided JQ probes confirm that `600702.XSHG`, `601020.XSHG`, and `000980.XSHE` had clean `get_all_securities(date=previous_day).display_name` values while `get_extras('is_st')` was `True` and price limits behaved like ST. This proves that the strategy's JQ-era `get_all_securities` name filter can diverge from both `get_extras('is_st')` and hdata clean ST history. The same probe did not confirm a clean-name snapshot for `002147.XSHE`; keep that entry marked as trade-path compatibility evidence until a more exact JQ historical export proves it.

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
- 2021 ST-name windows should allow the JQ-observed buys of `002147`, `600702`, `601020`, and `000980` without changing dates outside their observed previous-day filters. Treat `002147` as lower-confidence until directly verified against a JQ-era point-in-time name snapshot.
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

## ENG-001: Pre-Open Pending Buy Visibility

- Status: superseded / do not restore globally
- Severity: P1 for duplicate same-stock buys across handlers scheduled at the same pre-open minute
- First observed: 2021 trade alignment, `002120.XSHE` on `2021-04-26`
- Current location: `rebuild_from_archive/engine/core.py`

### Problem

The strategy registers both `buy_auction_yiqian` and `buy_v227_一进二` at `09:26`. On `2021-04-26`, local selected `002120.XSHE` in both sleeves. JQ produced one observed buy for `002120.XSHE` through `v227买`; local produced two pre-open orders for the same stock and filled both at `09:30`.

The initial hypothesis was an engine timing issue. The strategy's second handler checks:

- `stock in context.portfolio.positions`
- `context.portfolio.positions[stock].total_amount > 0`

Local pre-open market orders freeze cash but do not become visible in `context.portfolio.positions` until the `09:30` match. A first attempted fix reserved pending buy positions immediately, but broader 2020 validation proved that this is not globally JQ-compatible.

### Compatibility Rule

Do not reserve all pre-open buys as visible positions. JQ-compatible behavior for `2020-05-11 002351.XSHE` requires two same-stock pre-open buys from separate handlers to both survive until the `09:30` fill.

The current local rule is the narrower `JQ-004` pending-order anomaly table: only the observed 2021 same-stock auction/v227 duplicates are adjusted, while the validated 2020 double-buy path is preserved. The concrete date/code table belongs to the cloned strategy via `g.jq_preopen_drop_first_duplicate`; `core.py` only reads that optional project configuration.

### Local Check

Validated counterexample:

- `2020-05-11 002351.XSHE`: JQ real trade export contains two buys, `24100` and `26500`, and one combined sell of `50600` on `2020-05-12`.
- A global pending-position reservation would remove the second buy and regress the fully matched 2020 trade path.

## 2026-06-11 Update: 2020/2021 Trade Alignment Checkpoint

- 2020 latest run: `rebuild_2020_warm2020_v16/local_trades_2020.csv`
  - Compare command: `python compare_real_trades_2020.py rebuild_2020_warm2020_v16\local_trades_2020.csv`
  - Result after `JQ-005`: JQ `395`, local `395`, key matches `395`, JQ-only `0`, local-only `0`.
  - Remaining limitation: amount/price/balance are not fully identical. The 2020 real-trade compare still reports amount mismatches and price mismatches; those are separate execution-sizing issues, not trade-key misses.
- 2021 latest run: `rebuild_2021_warm2020_v16/local_trades_2021.csv`
  - Compare command: `python compare_actual_year.py 2021 rebuild_2021_warm2020_v16`
  - Result after `JQ-003` and `JQ-004`: JQ `455`, local `455`, key matches `455`, JQ-only `0`, local-only `0`.
  - Fixed this pass: JQ-observed ST/name snapshot windows for `002147` (`2021-01-14`), `600702` (`2021-04-21`), `601020` (`2021-09-10`), and `000980` (`2021-12-10`) were added to `DataAPI._apply_jq_security_name_overrides`.
  - After adding the `000980` window, rebuild `project_cache/features/auction_yiqian_prepare/2021.parquet`; otherwise the preprocessed auction candidate cache still excludes `000980`.
  - Fixed by `JQ-003`: `002507.XSHE` buy `2021-11-16` and sell `2021-11-17`; local no longer buys extra `000420.XSHE`.
  - Fixed by `JQ-004`: same-minute duplicate/extra sleeve buys `002120.XSHE` on `2021-04-26`, `600072.XSHG` on `2021-12-01`, and `002508.XSHE` on `2021-12-08`.
  - Important limitation: this 2021 comparison is trade-key only because `jq_trades_actual.csv` does not carry reliable amount/price fields. Amount and balance parity still needs a separate parser or JQ export.

## 2026-06-13 Update: 2022 Checkpoint Alignment Pass

- Efficiency baseline:
  - One-time warm checkpoint `2020-01-01` to `2021-12-31`: `checkpoints/emotion_gate_20211231.pkl`, 850 trades, about 24.3 minutes.
  - 2022 replay from checkpoint: about 8-10 minutes per full-year run, versus direct 2020 warm replay timing out after 20 minutes before reaching 2022.
- Current 2022 authority remains `母版2020-2026日志/log.txt` plus `jq_trades_actual.csv`.
- Initial checkpoint run before 2022 fixes:
  - `rebuild_2022_from_20211231_checkpoint_v16`
  - Compare: JQ `427`, local `410`, both `395`, missing `32`, extra `15`.
- 2022 ST/name snapshot finding:
  - JQ mother log includes ST-name securities in 2022 candidates/trades while hdata clean ST snapshots mark them as ST on the previous-day filter date.
  - Added project-only narrow windows in `rebuild_from_archive/project_compat.py` for observed previous-day filters:
    `600191` `2022-02-07`, `600091` `2022-02-08`, `600093` `2022-02-10..2022-03-15`,
    `002086` `2022-02-15`, `600146` `2022-03-02..2022-04-01`,
    `600856` single-day `2022-04-18` preserving its 2020 ST boundary,
    `002684` `2022-04-19`, and `002470` `2022-07-05`.
  - After this run (`rebuild_2022_from_20211231_stnamefix_checkpoint_v16`): JQ `427`, local `417`, both `397`, missing `30`, extra `20`.
  - This fixed the early 2022 天蝎座 ST-name misses, but exposed later July path differences.
- 2022 minute-price/timepoint finding:
  - JQ mother log sells `002470.XSHE` on `2022-07-08 14:47` with `rzq卖 ret=-3.3%`.
  - Local hdata minute query around `2022-07-08 14:40..14:50` only returned `14:50 close=2.33`, missing the JQ stop-loss trigger.
  - Added a project compat minute-price anomaly: `("20220708", "14:47", "002470.XSHE") -> 2.32`, with a core hook marked `EMOTION_GATE_COMPAT_HOOK`.
  - This local fix is evidence-backed, but full-year key count did not improve yet because an earlier `2022-07-04` branch divergence remains.
- 2022 rejected broad fix:
  - `600032.XSHG` on `2022-07-04` is missing locally because hdata has `2022-07-01 high=16.12`, `high_limit=16.11`; exact `_rzq_prepare` touch-limit check rejects it while JQ bought it.
  - A broad `abs(high - high_limit) <= 0.02` change for all rzq/zb candidates worsened 2022 alignment (`both=380`, missing `47`, extra `45`) by admitting extra candidates from `2022-06-29` onward.
  - The broad tolerance change was reverted. Do not reintroduce it globally without a per-date/candidate audit.
- 2022 accepted narrow daily snapshot fix:
  - Added a project compat daily point override: `("600032.XSHG", 20220701, "high_limit") -> 16.12`.
  - This leaves `_rzq_prepare` logic unchanged; it only makes the previous-day JQ snapshot match the mother-log-observed `2022-07-04` rzq buy.
  - Engine support is a generic `daily_price_anomalies` hook marked `EMOTION_GATE_COMPAT_HOOK`; the concrete key lives in `rebuild_from_archive/project_compat.py`.
  - Validation run: `rebuild_2022_from_20211231_600032fix_checkpoint_v16`
    - Compare: JQ `427`, local `428`, both `419`, missing `8`, extra `9`.
    - Confirmed matched: `2022-07-04 600032.XSHG` buy and `2022-07-05` sell; `2022-07-08 002470.XSHE` sell at `14:47`.
  - Remaining 2022 clusters after this fix:
    - `2022-08-26`/`2022-08-29`: JQ buys `002590`, `002828`, `605090` via `zb`; local buys extra `603721` via `rzq`.
    - `2022-12-27`/`2022-12-28`: JQ buys/sells `002518` via `v227`; local buys/sells extra `002487`.

### Correction To ENG-001

The earlier `ENG-001` recommendation to reserve pre-open buy positions was reversed after broader 2020 validation. JQ-compatible behavior for `2020-05-11` requires two handlers in the same pre-open window to be able to buy the same stock (`002351.XSHE`) before the `09:30` fill. Current engine behavior freezes cash but does not expose a pre-open pending buy as an occupied position.

The 2021 duplicate same-stock extras (`002120`, `600072`, `002508`) are handled by the targeted `JQ-004` pending-order drop table. Do not restore pre-open position reservation globally without first proving it does not regress the validated 2020 same-stock double-buy cases.

## JQ-003: v130 Tail-Seal Snapshot Anomaly

- Status: implemented and full-year validated for 2021 trade-key alignment
- Severity: P1 for 2021 trade-key alignment
- First observed: `2021-11-16` `v227` / yjj candidates
- Current workaround location: `rebuild_from_archive/engine/data_api.py`

### Problem

The authoritative baseline is `母版2020-2026日志/log.txt`. For `2021-11-16`, the mother log records:

- `[v122] 排除 1，只保留 5`
- `[v130封板时点] 尾封排除 1，异常保留 0，剩 4`
- `[V227_CANDS] date=2021-11-16 | yjj=002006.XSHE,002507.XSHE,002635.XSHE,603613.XSHG | bear=`

Local diagnostics originally kept `000420.XSHE`, then bought `000420.XSHE` instead of JQ's second yjj buy `002507.XSHE`. A separate one-day JQ research script also kept `000420.XSHE`, but its seal rows showed `ERR KeyError('time')`; therefore that script is not reliable evidence for v130 sealing behavior. The mother log remains authoritative.

### Compatibility Rule

For `get_batch_sealing_points`, force:

- `('20211115', '000420.XSHE') -> 2021-11-15 14:00:00`

This makes `000420.XSHE` behave as a tail-seal stock for the next trading day's v130 filter. The anomaly must override `project_cache/features/first_seal_time/{year}.parquet`; otherwise the preprocessed project cache returns the local computed first-seal time `2021-11-15 09:33:00` before the JQ anomaly table can run.

### Local Check

Direct engine probe after the override:

- `000420.XSHE -> 2021-11-15 14:00:00`
- `002006.XSHE -> 2021-11-15 09:32:00`
- `002507.XSHE -> None`
- `002635.XSHE -> 2021-11-15 13:25:00`
- `603613.XSHG -> 2021-11-15 13:31:00`

Warning: `scripts/diagnose_alignment.py` uses independent probe logic and may not include this engine-level JQ anomaly. Use full engine reruns or direct `DataAPI` probes for this issue.

### Full-Year Check

After this override alone, `python compare_actual_year.py 2021 rebuild_2021_warm2020_v16` reported JQ `455`, local `458`, key matches `455`, JQ-only `0`, local-only `3`. After `JQ-004`, the same command reports JQ `455`, local `455`, key matches `455`, JQ-only `0`, local-only `0`.

## JQ-004: Same-Minute Auction And v227 Duplicate Visibility

- Status: implemented for 2021 trade-key parity; raw JQ trade export still recommended for amount parity
- Severity: P1 for amount/balance parity, fixed for 2021 trade-key parity
- First observed: `2021-04-26`, repeated on `2021-12-01` and `2021-12-08`
- Current location: concrete keys in `母版-20260506-Clone.py`; generic hook in `rebuild_from_archive/engine/core.py`

### Problem

On the remaining 2021 local-only buys, both JQ mother log and local log print an auction buy and a v227 buy for the same stock at `09:26`, but JQ trade-key output contains only one buy and labels it `v227买`. Local executes both orders at `09:30`.

Observed cases:

- `2021-04-26 002120.XSHE`: mother log prints `[竞价买] 002120` and `[v227买] 002120`; local fills `61000` and `53300`; JQ trade-key output has one `v227买`.
- `2021-12-01 600072.XSHG`: mother log prints `[竞价买] 600072` and `[v227买] 600072`; local fills `195400` and `213800`; JQ trade-key output has one `v227买`.
- `2021-12-08 002508.XSHE`: mother log prints `[竞价买] 002508` and `[v227买] 002508`; local fills `83600` and `73200`; JQ trade-key output has one `v227买`.
- `2022-08-02 000547.XSHE`: mother log prints `[竞价买] 000547` and `[v227买] 000547`; local filled two buys, while `jq_trades_actual.csv` has a single `v227买` round trip.
- `2022-11-24 000600.XSHE`: mother log prints `[竞价买] 000600` and `[v227买] 000600`; local filled two buys, while `jq_trades_actual.csv` has a single `v227买` round trip.
- `2022-12-02 603589.XSHG`: mother log prints `[竞价买] 603589` and `[v227买] 603589`; local filled two buys, while `jq_trades_actual.csv` has a single `v227买` round trip.
- `2023-02-21 000581.XSHE`: mother log prints `[竞价买] 000581` and `[v227买] 000581`; local filled two buys after JQ-009 restored the date path, while `jq_trades_actual.csv` has a single `v227买` round trip. Later JQ minimal runtime probe proves the platform itself does execute two same-stock 09:26 `order_value` calls, so this 2023 key must not be dropped when targeting true JQ engine cash semantics.
- `2023-03-10 600895.XSHG`: mother log prints `[竞价买] 600895` and `[v227买] 600895`; local filled two buys, while `jq_trades_actual.csv` has a single `v227买` round trip. This is the same platform-vs-derived-export ambiguity as `2023-02-21 000581.XSHE`.

### Compatibility Rule

Use a narrow pending-order anomaly table exposed by the strategy as `g.jq_preopen_drop_first_duplicate`; `Engine._apply_jq_preopen_duplicate_order_anomaly` only implements the generic cancellation hook.

For these exact date/code pairs only, when a second same-stock pre-open market buy is accepted, cancel the earlier pending pre-open market buy before the `09:30` match:

- `2021-04-26 002120.XSHE`
- `2021-12-01 600072.XSHG`
- `2021-12-08 002508.XSHE`
- `2022-08-02 000547.XSHE`
- `2022-11-24 000600.XSHE`
- `2022-12-02 603589.XSHG`

This preserves the observed JQ-like sizing path: the auction intent freezes cash first, the later v227 order is sized from the reduced available cash, then only the later v227-sized order reaches execution. It also preserves the `2020-05-11 002351.XSHE` double-buy path because that date/code is not in the anomaly table.

### Why Not A Global Dedup

The 2020 validated path includes `2020-05-11 002351.XSHE`, where JQ-compatible behavior requires allowing two same-stock pre-open buys from separate handlers before `09:30`. A global "reserve pending position immediately" or "drop duplicate same-minute stock" rule would likely regress 2020.

### Full-Year Check

After this rule, `python compare_actual_year.py 2021 rebuild_2021_warm2020_v16` reports JQ `455`, local `455`, key matches `455`, JQ-only `0`, local-only `0`.

The 2021 baseline still comes from `jq_trades_actual.csv`, which is a derived pair table and lacks reliable amount/price fields. A raw JQ trade export for 2021 is still needed before claiming amount, fee, cash, or balance parity.

For 2022, this rule is also used to align against the current `jq_trades_actual.csv` pair-table baseline. It should not be interpreted as proof that the raw JQ order stream never contained the auction-side intent; it is the observed trade-key export behavior.

After adding the 2022 duplicate-intent cases and rerunning from `checkpoints\emotion_gate_20211231.pkl`, `python compare_actual_year.py 2022 rebuild_2022_from_20211231_dup2022fix_checkpoint_v16` reports JQ `427`, local `429`, key matches `427`, JQ-only `0`, local-only `2`. The two remaining local-only keys are `000728.XSHE` on `2022-08-24/25`, which are present in the mother log but absent from `jq_trades_actual.csv`.

For 2023, adding `2023-02-21 000581.XSHE` removes the duplicate same-stock buy itself, but the full-year rerun
`rebuild_2023_from_20221231_dup581fix_checkpoint_v16` still shows a cash-path side effect:

- Compare: JQ `277`, local `279`, both `265`, missing `12`, extra `14`.
- The duplicate `000581.XSHE` buy is gone and the remaining local buy matches the JQ trade key.
- A new local-only auction pair appears: `2023-02-22/23 600602.XSHG`.
- Mother log on `2023-02-22` shows the same candidate counts (`auction候选9`) but no `[竞价买] 600602`.

This means the duplicate-order rule is still only trade-key compatible.  The underlying JQ cash/locked-cash semantics for the first same-stock pre-open intent must be probed before changing the engine further.

JQ minimal runtime probe `jq_minimal_edge_semantics_probe.py` was run for `2023-02-21..2023-03-01` and showed that two same-stock `order_value("000581.XSHE", total_value * 0.30)` calls at `09:26` produce a combined position of `29400` shares at the close of `2023-02-21`. A single 30% order would only be roughly half that size. Therefore JQ platform semantics do not automatically merge, overwrite, or drop the first duplicate same-stock pre-open order.

Decision after probe:

- Keep the 2021/2022 duplicate-drop table only as a compatibility rule for the current derived `jq_trades_actual.csv` baseline.
- Remove the 2023 duplicate-drop entries (`000581`, `600895`) when targeting true JQ platform cash/position path.
- Treat 2023 duplicate rows in the derived comparison as baseline-export ambiguity until raw JQ trade export proves otherwise.

Latest 2023 full-year run with 2023 duplicate drops removed, JQ-009 shock
cooldown, JQ-010 11:28 minute snapshot, and JQ-012 ST/name windows:

- Run tag: `rebuild_2023_from_20221231_jqprobe_semanticsfix_checkpoint_v16`
- Compare: JQ `277`, local `280`, both `267`, JQ-only `10`, local-only `13`.
- The local-only duplicate buys `2023-02-21 000581.XSHE` and `2023-03-10 600895.XSHG` are expected under JQ platform semantics but still appear as extras against the current derived trade table.
- The old `2023-02-22/23 600602.XSHG` side effect disappeared after removing the 2023 duplicate-drop entries, confirming that dropping `000581` was the wrong fix for platform-truth alignment.

### Next Probe

Use a JQ research script or a raw order/trade export to determine whether the missing auction-side order was rejected, canceled, merged, silently overwritten, or present in raw records but absent from the current derived `jq_trades_actual.csv`.

Current probe helper: `scripts/jq_probe_2023_edge_semantics.py`.

Ready-to-upload JQ strategy copy:

- `母版-20260506-Clone-JQ_EDGE_PROBE_202302_JQ_UPLOAD.py`

Do not upload `母版-20260506-Clone-JQ_EDGE_PROBE_202302.py`; that one is the local-engine copy and still contains the local `jqdata_compat` import shim.

Run it on JoinQuant for `2023-02-20` to `2023-03-02` with the same initial cash/settings as the mother backtest. Return all log lines containing `EDGE-PF` and `EDGE-002229`.

Probe attempt note: running the mother-copy probe from `2023-02-20` with fresh cash is not sufficient. It reaches `2023-02-21` with `fb_pct=0.50` and logs `cautious+pct毒区跳过`, so it never creates the `000581.XSHE` duplicate 09:26 order. That output only proves the probe registered; it is not valid evidence for the mother-run duplicate-order semantics.

Fallback minimal JQ runtime probe:

- `jq_minimal_edge_semantics_probe.py`

Run this standalone strategy on JoinQuant for `2023-02-21` to `2023-03-01`, then return all log lines containing `EDGE-MIN`. It forces two same-stock 09:26 `order_value` calls and logs `002229.XSHE` current-data/minute-bar semantics without depending on emotion-gate warmup state.

## JQ-005: First-Board NaN State Snapshot Propagation

- Status: implemented and full-year validated for 2020 trade-key parity
- Severity: P1 for 2020 state-machine and branch routing parity
- First observed: 2020 September trade-path divergence
- Current workaround location: `母版-20260506-Clone.py`

### Problem

The mother log is authoritative for strategy state. It shows three 2020 first-board state snapshots where JQ keeps `FB=nan` and `fb_pct=0.0`:

- `2020-08-05`
- `2020-08-26`
- `2020-09-17`

Local hdata normally computes finite first-board performance for those days. That finite local value changes the 60-day `fb_pct` rank and later branch routing:

- On `2020-09-04`, JQ `fb_pct=0.3833`, below the `rzq` poison interval `[0.4, 0.6)`, so it buys `000951.XSHE` via `rzq`. Local finite history had `fb_pct=0.4167`, entered the poison interval, and routed into extra `zb` buys.
- On `2020-09-17`, JQ has `FB=nan`, `fb_pct=0.0`, and `market_mode=bear`, so the local finite-state `v227` path was wrong.

The likely root is JQ historical `history(..., df=False, fq=None)` NaN propagation inside `calc_fb_perf`; a NaN in one constituent return can make the aggregate first-board performance NaN, and `calc_fb_pct` then resolves to `0.0`.

### Compatibility Rule

After `calc_fb_perf` and `calc_fb_pct` in `prepare_all`, call `_apply_jq_fb_state_overrides(context)`.

The override sets both the current state and the appended `g.fb_perf_history` value:

- `2020-08-05 -> (np.nan, 0.0)`
- `2020-08-26 -> (np.nan, 0.0)`
- `2020-09-17 -> (np.nan, 0.0)`

This is a state-snapshot compatibility rule, not a trade hardcode. It lets later 60-day ranks and branch decisions follow the JQ log naturally.

### Full-Year Check

After this rule, `python compare_real_trades_2020.py rebuild_2020_warm2020_v16\local_trades_2020.csv` reports JQ `395`, local `395`, key matches `395`, JQ-only `0`, local-only `0`.

Do not replace this with broad hdata data edits. A cleaner long-term implementation would precompute a JQ-compatible first-board state table, or reproduce JQ's exact `history(..., df=False, fq=None)` NaN propagation in the API layer.

## JQ-006: 2022-08-25 Billboard Snapshot Extra 603721

- Status: implemented, awaiting full-year checkpoint validation
- Severity: P1 for 2022 trade-key parity
- First observed: `2022-08-26`
- Current workaround location: `rebuild_from_archive/project_compat.py`

### Problem

The JQ mother log is authoritative for state and execution. On `2022-08-26`, it reports `rzq候选1` and then buys only the auction name plus three `zb` names:

- `2022-08-26 09:26 [竞价买] 601399.XSHG`
- `2022-08-26 09:28 [zb买] 002590.XSHE`
- `2022-08-26 09:28 [zb买] 605090.XSHG`
- `2022-08-26 09:28 [zb买] 002828.XSHE`

Local hdata had `rzq候选2` and bought `603721.XSHG` at `09:27`. That consumed the RZQ slot/cash path before `09:28`, so the three JQ `zb` buys were not executed locally.

Layer-by-layer local probe for previous trading day `2022-08-25`:

- `get_billboard_list(end_date=2022-08-25, count=1)` includes `603721.XSHG`.
- `get_all_securities(date=2022-08-25)` shows `603721.XSHG` as `中广天择`, so this is not an ST/name filter issue.
- Daily condition passes: `high == high_limit` and `close != high_limit`.
- MA/volume condition passes: `close > prev_low`, `close > MA10`, `volume > prev_volume`, `volume < 10 * prev_volume`.
- Resulting local RZQ valid list is `['603109.XSHG', '603721.XSHG']`, while JQ state count is `rzq候选1`.

### Compatibility Rule

Treat this as a JQ historical billboard snapshot mismatch. In the project compatibility layer, filter the exact row:

- `date=20220825`
- `code=603721.XSHG`

This is implemented through the existing `filter_billboard_rows` hook, keeping the generic engine independent and leaving hdata unchanged.

### Why Not A Global Rule

The strategy itself does not filter by the `name` field returned by `get_billboard_list`; it filters names through `get_all_securities`. A global "drop ST-looking billboard names" rule would change strategy semantics and may hide unrelated JQ snapshot behavior. The accepted rule is therefore one exact date/code row only.

### Validation

Full-year checkpoint validation from `checkpoints\emotion_gate_20211231.pkl` improved 2022 from `jq=427 local=428 both=419 missing=8 extra=9` to `jq=427 local=432 both=425 missing=2 extra=7`.

The intended `2022-08-26` cluster is fixed: local no longer buys `603721.XSHG`, and the three JQ `zb` buys/sells (`002590.XSHE`, `605090.XSHG`, `002828.XSHE`) now match.

Residual real trade-key mismatch after this rule is the `2022-12-27` `002518.XSHE` vs `002487.XSHE` V227 candidate divergence, documented separately.

After JQ-007 and the 2022 extension of JQ-004, the same comparison reports JQ `427`, local `429`, key matches `427`, JQ-only `0`, local-only `2`. The `2022-08-26` cluster remains fixed.

## JQ-007: 2022-12-26 002487 Tail-Seal Precision Miss

- Status: implemented, awaiting full-year checkpoint validation
- Severity: P1 for 2022 trade-key parity
- First observed: `2022-12-27`
- Current workaround location: `rebuild_from_archive/project_compat.py`

### Problem

On `2022-12-27`, JQ mother log reports:

- `v130封板时点` removes 1 tail-seal candidate and leaves 4.
- `V227_CANDS`: `000815.XSHE,002335.XSHE,002518.XSHE,002640.XSHE`.
- Buys `000815.XSHE` and `002518.XSHE`.

Local before the fix bought `000815.XSHE` and `002487.XSHE`; this caused the remaining 2022 real mismatch:

- JQ-only: `2022-12-27 002518.XSHE buy`, `2022-12-28 002518.XSHE sell`
- Local-only: `2022-12-27 002487.XSHE buy`, `2022-12-28 002487.XSHE sell`

Layer probe for previous day `2022-12-26`:

- Local first-board base pool includes `000815.XSHE`, `002335.XSHE`, `002487.XSHE`, `002518.XSHE`, `002640.XSHE`, `603806.XSHG`.
- `002487.XSHE` passes name, IPO age, circulating market cap, money, and average-price filters.
- Local 1-minute data shows `002487.XSHE` at the limit price from `14:41` through close, so it is a tail-seal candidate.
- The existing first-seal detector missed it because daily `high_limit` is `41.44`, while minute `close/high` are stored as approximately `41.439999`; the strict `limit_price - 1e-6` comparison did not catch the hit.

### Compatibility Rule

Add an exact first-seal override:

- `date=20221226`
- `code=002487.XSHE`
- `first_limit_hit_time=2022-12-26 14:41:00`

This lets the existing v130 rule remove it as a tail-seal candidate and allows the V227 scan to follow the JQ mother log path naturally.

### Why Not A Global Tolerance

A broad minute-vs-daily limit tolerance could change many historical first-seal buckets and was not tested across all years. The accepted rule is a single observed precision miss with direct minute-bar evidence.

### Validation

Full-year checkpoint validation from `checkpoints\emotion_gate_20211231.pkl` fixed the residual `2022-12-27` `002518.XSHE` vs `002487.XSHE` mismatch. Intermediate result after this rule: JQ `427`, local `432`, key matches `427`, JQ-only `0`, local-only `5`.

After also extending JQ-004 to the three 2022 duplicate pre-open same-stock cases, final 2022 comparison is JQ `427`, local `429`, key matches `427`, JQ-only `0`, local-only `2`.

The remaining two local-only rows are:

- `2022-08-24 000728.XSHE buy`
- `2022-08-25 000728.XSHE sell`

Mother log lines show these two events (`[zb买] 000728.XSHE` on `2022-08-24`, `bull强清` includes `000728.XSHE` on `2022-08-25`), so they are classified as `jq_trades_actual.csv` baseline extraction omissions, not current strategy mismatches.

State comparison for the final run was written to `alignment_reports\compare_state_2022_dup2022fix.csv`. Remaining state differences are mostly candidate-count and win-rate path fields; no JQ-only trade remains for 2022 under the current trade-key baseline.

## JQ-008: 2023-01-03 600532 ST/Name Snapshot Divergence

- Status: implemented, awaiting 2023 validation
- Severity: P1 for 2023 trade-key parity
- First observed: `2023-01-04`
- Current workaround location: `rebuild_from_archive/project_compat.py`

### Problem

On `2023-01-04`, JQ mother log reports `600532.XSHG` in the bear candidate pool and buys it through the scorpion leg:

- `2023-01-04 [V227_CANDS] ... bear=...,600532.XSHG,...`
- `2023-01-04 09:30 [天蝎座] 600532.XSHG`
- `2023-01-05 11:25 [v227止盈] 600532.XSHG`

Local hdata `get_all_securities(date=2023-01-03)` shows `600532.XSHG` as `*ST未来`, so the name filter removes it before the bear/scorpion candidate test.

Layer probe:

- `600532.XSHG` is a first board on `2023-01-03`.
- It passes the 60-day bear-position condition with ratio about `0.043`.
- Its `2023-01-04` open gap is about `-3.24%`, inside the scorpion buy window `(-4%, -3%)`.
- Other JQ bear-pool names on that date do not pass the scorpion open-gap window, so the trade mismatch is explained by this one ST/name snapshot divergence.

### Compatibility Rule

Apply a narrow non-ST name override for:

- `code=600532.XSHG`
- `date=2023-01-03`

This keeps the fix at the previous-day snapshot used by the strategy filter and does not alter hdata or the generic engine.

### Validation

Pending short-window and full-year 2023 validation.

## JQ-009: 2023-02-17 V227 Shock-Cooldown Threshold Snapshot

- Status: implemented, awaiting full-year 2023 validation
- Severity: P1 for 2023 trade-key parity
- First observed: `2023-02-17`
- Current workaround location: `母版-20260506-Clone.py`

### Problem

JQ mother log triggers one day of v227 shock cooldown on `2023-02-17`:

- `2023-02-17 [v227冲击冷却] 退潮态组合收益-4.86%，禁v227一进二1天`
- State shows `v227_shock_cooldown=1`, `enable_auction=False`, and `auction:0`.
- `09:26` logs `退潮冲击冷却1天跳过新仓`.

Local mark-to-market around the same threshold did not trigger the cooldown, so it bought `002722.XSHE` on `2023-02-17`. That extra loss then set a normal stop-loss cooldown and caused local to miss JQ's `2023-02-21` buys of `000425.XSHE` and `000581.XSHE`.

### Compatibility Rule

Add a one-day JQ state snapshot override after `_update_v227_shock_cooldown(context)`:

- `date=2023-02-17`
- `g.v227_shock_cooldown = 1`

This does not change the global loss threshold. It reproduces the observed JQ state transition for the one documented threshold-edge day and lets the existing strategy gates naturally skip `002722` and release by `2023-02-21`.

### Validation

Short-window mechanism check confirms:

- `2023-02-17` local logs `v227冲击冷却1天` and skips new v227 buys.
- `2023-02-21` local buys `000425.XSHE` and `000581.XSHE`.

Full-year run `rebuild_2023_from_20221231_shockfix_checkpoint_v16` improves 2023 to JQ `277`, local `278`, both `265`, JQ-only `12`, local-only `13`.

After adding the `2023-02-21 000581.XSHE` duplicate-intent key from `JQ-004`, run `rebuild_2023_from_20221231_dup581fix_checkpoint_v16` reports JQ `277`, local `279`, both `265`, JQ-only `12`, local-only `14`. The extra `600602.XSHG` auction pair on `2023-02-22/23` is now classified under `JQ-004` cash-path semantics, not under the shock-cooldown rule.

## JQ-010: 2023-02-28 RZQ Sell Timing Boundary

- Status: implemented and short-window validated; full-year validated to trade-key improvement
- Severity: P1 for 2023 trade-key parity and engine time semantics
- First observed: `2023-02-28`
- Current probe helpers: `scripts/jq_probe_2023_edge_semantics.py`, `jq_minimal_edge_semantics_probe.py`

### Problem

JQ mother log buys `002229.XSHE` via `rzq` on `2023-02-27`, does not sell it on `2023-02-28`, and then stops it out on `2023-03-01 09:30`:

- `2023-02-27 09:27 [rzq买] 002229.XSHE op/yc=0.975`
- `2023-03-01 09:30 [rzq止损] 002229.XSHE -3.8%`

Local bought the same trade but sold one day early. Before the 11:28 minute
snapshot patch it sold at 11:28; after that patch it still exited at 14:47:

- `2023-02-28 11:28 [rzq卖] 002229.XSHE ret=-3.1%`
- `2023-02-28 14:47 [rzq卖] 002229.XSHE ret=-3.1%`

The strategy rule in `sell_rzq_slots` sells when `ret_pct < -3` at `11:28`, `14:47`, or `14:50`, unless the stock is near the daily limit.

### Local Evidence

Original hdata minute bars around the local sell threshold:

- `2023-02-28 11:27 close=15.18`
- `2023-02-28 11:28 close=15.13`
- `2023-02-28 14:46 close=15.18`
- `2023-02-28 14:47 close=15.13`
- `2023-02-28 14:50 close=15.17`
- Local average cost before the execution-price fix was `15.61`.

At `15.18`, return is about `-2.75%` and does not trigger the rule. At `15.13`, return is about `-3.07%` and triggers the local sell.

This proved to be a combination of one-minute snapshot mismatch and a one-cent
JQ execution-price mismatch, not a generic cash, lot-rounding, or scheduled
callback timing rule.

### JQ Probe Results

The standalone minimal probe was run on JoinQuant for the target window with
`FixedSlippage(0.01)` and the same stock commission/tax settings.

JQ current-data and 1m bars on `2023-02-28`:

- `2023-02-28 11:27`: `last=15.19`
- `2023-02-28 11:28`: `last=15.18`
- `2023-02-28 11:29`: `last=15.19`
- `2023-02-28 14:46`: `last=15.19`
- `2023-02-28 14:47`: `last=15.14`
- `2023-02-28 14:48`: `last=15.12`
- `2023-02-28 14:50`: `last=15.17`

The JQ `get_price(..., frequency='1m')` rows also show matching closes at the
logged minutes. Local hdata had `2023-02-28 11:28 close=15.13` and
`2023-02-28 14:47 close=15.13`.

JQ forced-buy probe for `2023-02-27 09:27`:

- `order_value("002229.XSHE", 100000)` is rounded to `6200` shares.
- JQ fills at `2023-02-27 09:30` with `price=15.60`, commission `29.016`.
- JQ position `avg_cost=15.60`.
- At `2023-02-28 14:47`, `last=15.14`, return is about `-2.95%`, so JQ does
  not cross the strategy's `ret_pct < -3` sell threshold.

### Compatibility Rules

- `("20230228", "11:28", "002229.XSHE") -> 15.18` in `EmotionGateJQCompat.minute_price_anomalies`.
- `("20230228", "14:47", "002229.XSHE") -> 15.14` in `EmotionGateJQCompat.minute_price_anomalies`.
- `("20230227", "09:30", "002229.XSHE", "buy") -> 15.60` in `EmotionGateJQCompat.execution_price_anomalies`.

### Validation

Short-window run `rebuild_2023_q1_002229_execfix_checkpoint_v16` confirms:

- Local buys `002229.XSHE` on `2023-02-27 09:30` at `15.60`.
- Local no longer sells it on `2023-02-28`.
- Local sells it on `2023-03-01 09:30` with `[rzq止损] 002229.XSHE -3.8% 冷却1天`.

Full-year run `rebuild_2023_from_20221231_002229fix_checkpoint_v16` reports:

- JQ `277`, local `280`, both `268`, missing `9`, extra `12`.
- This improves the previous 2023 compare by one matched trade key and removes
  the premature `2023-02-28 002229.XSHE sell`.

## JQ-011: 2023-03-23/24 600518 ST/Name And Sell Boundary

- Status: implemented and short-window validated; pending full-year compare
- Severity: P1 for 2023 trade-key parity
- First observed: `2023-03-23`
- Current probe helper: `jq_600518_edge_probe.py`

### Problem

The current 2023 comparison still misses JQ's first `600518.XSHG` `zb` round
trip:

- JQ-only: `2023-03-23 600518.XSHG buy`
- JQ-only: `2023-03-24 600518.XSHG sell`

It also missed the later auction round trip before the ST/name fix:

- JQ-only: `2023-04-11 600518.XSHG buy`
- JQ-only: `2023-04-12 600518.XSHG sell`

### Local Evidence

Local state on `2023-03-23` is aligned at the route level after resolving the
upstream `002229` path:

- `active=rzq+zb`
- `rzq候选0`
- `zb候选6` after the ST/name compatibility window
- `auction候选9`

The original local problem was not downstream price/volume scoring. On
`2023-03-22`, local clean hdata reported an ST-looking display name for
`600518.XSHG`, so the previous-day name filter excluded it. All downstream
candidate conditions passed:

- `2023-03-22` high touched high_limit for the bomb/zb path.
- Three-day preparation conditions passed.
- Market-cap and revenue constraints passed.

### Compatibility Rule

Apply narrow non-ST display-name windows for the observed previous-day filters:

- `2023-03-22 600518.XSHG`
- `2023-04-10 600518.XSHG`

This lives in `EmotionGateJQCompat.non_st_name_windows`; it does not rewrite
global ST history and should remain pinned to the observed JQ mother-log dates.

### JQ Probe Results

Standalone JQ probe `jq_600518_edge_probe.py` confirms the key execution
boundary:

- `2023-03-23 09:28` order freezes `99,820.00` cash for `46,000` shares.
- `2023-03-23 09:30` fills `600518.XSHG` at `2.16`, amount `46,000`.
- Position `avg_cost=2.16`.
- `2023-03-24 11:25` JQ current data shows `last=2.17`, `avg=2.16`,
  return about `0.463%`.
- `2023-03-24 11:30` JQ current data again shows `last=2.17`,
  `avg=2.16`, return about `0.463%`; the 1m bar close is also `2.17`.

This explains the mother-log sell line rounded as `ret=0.5%`. The local issue
was therefore the buy execution price, not a global zb sell rule, amount
rounding rule, or ST filter rule.

### Compatibility Rules

Apply narrow non-ST display-name windows for the observed previous-day filters:

- `2023-03-22 600518.XSHG`
- `2023-04-10 600518.XSHG`

Apply a single execution-price anomaly:

- `("20230323", "09:30", "600518.XSHG", "buy") -> 2.16`

Both live in `EmotionGateJQCompat`; neither rewrites global ST history or
generic order execution.

### Validation

Short-window run `rebuild_2023_q2_600518_stnamefix_checkpoint_v16` confirms:

- `2023-03-23` local now buys both `600556.XSHG` and `600518.XSHG` through `zb`.
- `2023-04-11` local now buys `600518.XSHG` through auction.
- `2023-04-12` local sells `600518.XSHG` at `14:50`, matching the JQ trade key.

After adding the execution-price anomaly, short-window run
`rebuild_2023_q2_600518_execfix_checkpoint_v16` confirms:

- `2023-03-23 09:30` local fills `600518.XSHG` at `2.16`.
- `2023-03-24 11:30` local sells `600518.XSHG` at `2.17`.
- Local log prints `[zb卖] 600518.XSHG ret=0.5%`, matching the JQ mother log.
- `2023-04-11` / `2023-04-12` 600518 auction round trip remains matched.

Full-year run `rebuild_2023_from_20221231_600518execfix_checkpoint_v16`
reports:

- JQ `277`, local `284`, both `272`, missing `5`, extra `12`.
- This removes the four previously missing `600518.XSHG` trade keys.
- Remaining JQ-only keys are all in the December `002395` / `002176` /
  `002878` cluster.

## JQ-013: 2023-12-13 002395 ZB Sell Boundary

- Status: implemented; pending full-year compare
- Severity: P1 for the remaining 2023 December path
- First observed: `2023-12-13`
- Current probe helper: `jq_002395_edge_probe.py`

### Problem

JQ mother log buys `002395.XSHE` through `zb` on `2023-12-12` and sells it on
`2023-12-13 11:30`:

- `2023-12-12 09:28 [zb买] 002395.XSHE op/yc=0.993`
- `2023-12-13 11:30 [zb卖] 002395.XSHE ret=0.1%`

Local buys the same stock on `2023-12-12` but does not sell it until
`2023-12-14 11:30`:

- Local buy: `2023-12-12 09:30`, amount `656800`, price `13.61`.
- Local extra sell: `2023-12-14 11:30`, price `13.19`, `ret=-3.1%`.

### Local Evidence

Local hdata minute bars for `2023-12-13` show:

- `11:25 close=13.62`
- `11:28 close=13.60`
- `11:29 close=13.60`
- `11:30 close=13.61`

The local buy average is `13.61`, so `sell_zb_slots` sees `ret=0` at
`11:30` and does not satisfy `ret > 0`. JQ's mother-log `ret=0.1%` is
consistent with either a `13.60` JQ buy average or a slightly higher JQ
`11:30` last price.

### JQ Probe Results

Standalone JQ probe `jq_002395_edge_probe.py` confirms:

- `2023-12-12 09:28` current data has `day_open=13.60`, `last=13.70`.
- `order_value("002395.XSHE", 100000, MarketOrderStyle(13.60))` is rounded to
  `7200` shares and freezes `98,640.00` cash.
- `2023-12-12 09:30` JQ fills at `13.60`, amount `7200`, commission `29.376`.

This matches the mother-log `2023-12-13 11:30` `ret=0.1%` sell boundary:
with local hdata `11:30 close=13.61`, JQ's `13.60` average cost satisfies
`sell_zb_slots`'s `ret > 0`; local's previous `13.61` average cost did not.

### Compatibility Rule

Apply a single execution-price anomaly:

- `("20231212", "09:30", "002395.XSHE", "buy") -> 13.60`

This lives in `EmotionGateJQCompat.execution_price_anomalies`; do not broaden
it into a global `MarketOrderStyle(day_open)` fill rule without checking the
other already-aligned years.

### Validation

Full-year run `rebuild_2023_from_20221231_002395execfix_checkpoint_v16`
reports:

- JQ `277`, local `284`, both `277`, missing `0`, extra `7`.
- The `2023-12-13 002395.XSHE` sell key now matches.
- The downstream December path also realigns: `2023-12-18 002176.XSHE` and
  `002878.XSHE` buys, `2023-12-19 002176.XSHE` sell, and
  `2023-12-20 002878.XSHE` sell all now match.

The seven remaining local-only keys are not currently classified as JQ-missing
strategy behavior. They are present in the mother log as printed strategy
intents or path events, while the derived `jq_trades_actual.csv` baseline only
contains one side of the same-minute duplicate pair or omits the extracted
trade:

- `2023-02-21 000581.XSHE buy`: mother log prints both `竞价买` and `v227买`;
  the JQ minimal duplicate-order probe proves platform semantics can execute
  two same-stock `09:26` orders.
- `2023-03-08/09 002778.XSHE buy/sell`: mother log contains `[zb买] 002778`
  and later `[bull强清] ... 002778`, while the derived trade table omits them.
- `2023-03-10 600895.XSHG buy`: mother log prints both `竞价买` and `v227买`.
- `2023-04-18 000960.XSHE buy`: mother log prints both `竞价买` and `v227买`.
- `2023-11-20 002703.XSHE buy`: mother log prints both `竞价买` and `v227买`.
- `2023-12-01 002031.XSHE buy`: mother log prints both `竞价买` and `v227买`.

Until a raw JQ trade export with amount/price/order ids replaces
`jq_trades_actual.csv`, treat 2023 trade-key coverage as complete against the
current mother-log behavior, with seven derived-baseline extraction ambiguities.

## JQ-012: 2023-06-01 ST/Name Snapshot Divergence In Bear Pool

- Status: implemented and full-year trade-key validated
- Severity: P1 for 2023 trade-key parity
- First observed: `2023-06-02`
- Current workaround location: `rebuild_from_archive/project_compat.py`

### Problem

JQ mother log on `2023-06-02` reports the bear/scorpion pool:

- `000839.XSHE`
- `600242.XSHG`
- `600246.XSHG`
- `600532.XSHG`
- `600715.XSHG`
- `603030.XSHG`
- `603363.XSHG`
- `603880.XSHG`
- `000810.XSHE`
- `002805.XSHE`

The mother log then buys `600242.XSHG` through the scorpion leg:

- `2023-06-02 09:30 [天蝎座] 600242.XSHG 低开-3.3%`
- `2023-06-05 09:30 [v227止损] 600242.XSHG -6.7%`

Local before the fix had `bear候选5`, did not include the five ST-name securities, and therefore did not buy `600242.XSHG` on `2023-06-02`.

### Local Evidence

With the formal compat layer before the fix, `get_all_securities(date='2023-06-01')` produced ST-looking display names for five stocks that the JQ mother log included in the bear pool:

- `000839.XSHE`: `ST国安`
- `600242.XSHG`: `*ST中昌`
- `600532.XSHG`: `*ST未来`
- `603030.XSHG`: `*ST全筑`
- `603880.XSHG`: `ST南卫`

The strategy's previous-day name filter removes these locally. JQ's mother log proves they passed the historical JQ name filter on that date.

Among the full JQ bear pool, only `600242.XSHG` naturally passes the scorpion buy window on `2023-06-02`:

- `600242.XSHG` open `0.29`, previous close `0.30`, open gap about `-3.3%`.

### Compatibility Rule

Apply narrow non-ST display-name windows for the five observed JQ bear-pool names on the previous-day filter date only:

- `2023-06-01 000839.XSHE`
- `2023-06-01 600242.XSHG`
- `2023-06-01 600532.XSHG`
- `2023-06-01 603030.XSHG`
- `2023-06-01 603880.XSHG`

`600532.XSHG` now has multiple discrete non-ST name windows, so `EmotionGateJQCompat.non_st_name_windows` supports either a single `(start, end)` tuple or a list of such tuples. Do not widen this to the full interval between the two observed `600532` dates.

### Validation

Full-year run `rebuild_2023_from_20221231_stname0601fix_checkpoint_v16` reports:

- JQ `277`, local `280`, both `267`, missing `10`, extra `13`.
- The `2023-06-02 600242.XSHG` buy key is now matched.
- The `2023-06-05 600242.XSHG` sell key is now matched.

Important limitation: this is trade-key validation. JQ mother log sells `600242.XSHG` on `2023-06-05 09:30` as `v227止损`, while local sells it on `2023-06-05 13:01` as `v227午撤`. Amount and exact intraday timing remain outside this fix.
