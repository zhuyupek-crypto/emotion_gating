# 2020-2023 JoinQuant Alignment Issues And Solutions

Last updated: 2026-06-16

This document consolidates the JoinQuant alignment findings for the emotion-gate
rebuild from 2020 through 2023. It summarizes what was discovered, what was
changed, what was intentionally not generalized, and how each year currently
validates.

The original data roots remain read-only:

- `D:\work space\local_quant`
- `D:\work space\hdata`

All project-specific fixes live in the workspace copy, primarily in:

- `rebuild_from_archive/project_compat.py`
- selected application-run scripts and the cloned mother strategy
- generic hooks in `rebuild_from_archive/engine/` only where an optional
  `compat` profile is injected

Do not treat these compatibility rules as clean market data corrections. They
are narrow reproductions of historical JoinQuant behavior observed in the
mother log, JQ probes, or exported trade records.

## Current Alignment Status

| Year | Latest trade-key status | Remaining caveat |
|---|---:|---|
| 2020 | JQ `395`, local `395`, matched `395`, JQ-only `0`, local-only `0` | Trade keys align; amount/price/balance still have small execution/cash drift. |
| 2021 | JQ `455`, local `455`, matched `455`, JQ-only `0`, local-only `0` | Trade keys align; current baseline lacks reliable raw amount/price/order-id detail. |
| 2022 | JQ `427`, local `429`, matched `427`, JQ-only `0`, local-only `2` | Two local-only keys are present in the mother log but omitted by `jq_trades_actual.csv`. |
| 2023 | JQ `277`, local `284`, matched `277`, JQ-only `0`, local-only `7` | Seven local-only keys are mother-log duplicate/omission ambiguities in the derived trade table. |

The practical status is: 2020-2023 JQ-side trade keys are covered. 2022 and
2023 still need a raw JQ trade export if amount, price, order-id, and duplicate
same-minute order semantics must be audited beyond the current derived
`jq_trades_actual.csv` baseline.

## Cross-Year Root Causes

### 1. JQ-Compatible ST/Name Snapshots Differ From Clean hdata ST History

The strategy often filters by `get_all_securities(date=previous_day)` display
name rather than by `get_extras('is_st')`. hdata's clean ST snapshots can be
correct as market history while still differing from historical JQ
`get_all_securities` snapshots.

Observed behavior:

- Some names looked ST in hdata but passed JQ's name filter and were bought.
- Some final/delisting names leaked backward from static metadata and had to be
  prevented.
- `get_extras('is_st')`, price-limit behavior, and `get_all_securities`
  display names can disagree inside JoinQuant itself.

Solution:

- Keep hdata unchanged.
- Add narrow project-only `non_st_name_windows` for observed previous-day
  filter dates in `EmotionGateJQCompat`.
- Keep `600856.XSHG` special: allow the 2020-04-30 buy and 2020-05-06 sell,
  then treat ST from 2020-05-07 onward.

Important examples:

- 2020: `600666`, `600654`, `002192`, `600255`, `002256`, `600145`,
  `002638`, `600687`, `000673`, `600146`, `000585`, `600856`.
- 2021: `002147`, `600702`, `601020`, `000980`.
- 2022: `600191`, `600091`, `600093`, `002086`, `600146`, `002684`,
  `002470`.
- 2023: `600532`, `600518`, `000839`, `600242`, `603030`, `603880`.

Do not replace these with a wholesale `st_list` join. A future cleaner approach
is a project-local, point-in-time JQ-compatible name table:

```text
project_cache/features/jq_security_name_history.parquet
fields: code, display_name, start_date, end_date, is_st_jq_compat, source, evidence
```

### 2. One-Tick Execution Price Or Minute Snapshot Differences Can Change Path

Most one-cent differences only affect cash and later share counts, but some
cross a sell threshold and change trade keys.

Solution:

- Keep exact observed price exceptions in `EmotionGateJQCompat`.
- Do not turn them into a global execution rule.

Accepted examples:

- `2023-02-27 002229` buy: JQ fills `15.60`, local had `15.61`.
- `2023-02-28 002229` minute last/close anomalies: JQ has `11:28=15.18`,
  `14:47=15.14`; local hdata had lower values that triggered early stop.
- `2023-03-23 600518` buy: JQ fills `2.16`, local had `2.17`.
- `2023-12-12 002395` buy: JQ fills `13.60`, local had `13.61`.
- `2022-07-08 002470` minute snapshot: JQ mother log requires `14:47=2.32`.
- `2020-08-20 600027` buy: JQ execution and sizing require `4.30` and
  `164300` shares.

### 3. Tail-Seal And First-Seal Timing Need Exact Historical Exceptions

The strategy's v130/v122 path is sensitive to first-seal time. Small differences
in minute precision or missing historical seal timing can change the selected
second-board candidate.

Solution:

- Add exact tail/first-seal exceptions only for observed date/code pairs.
- Do not add broad tolerance unless a full multi-year audit proves it safe.

Accepted examples:

- `2020-07-13 300118`, `2020-07-13 600711`: historical tail-seal behavior.
- `2021-11-15 000420`: force tail-seal at `14:00` so v130 excludes it on
  `2021-11-16`.
- `2022-12-26 002487`: force first limit hit at `14:41` so v130 removes it.

### 4. Same-Minute Duplicate Pre-Open Orders Are Baseline-Dependent

Early investigation tried making pending pre-open buys visible immediately.
That was rejected because 2020 has a validated case where two same-stock
pre-open buys must both survive.

Current rule:

- The engine freezes cash for pre-open orders but does not globally reserve a
  visible position before 09:30.
- A narrow duplicate-drop table is kept only for older derived trade-key
  baselines.
- For 2023, JQ minimal runtime probes proved the platform can execute two
  same-stock `09:26` `order_value` calls, so 2023 duplicate local keys are
  treated as derived-baseline ambiguities when the mother log shows both
  intents.

Observed duplicate-drop table currently includes:

- `2021-04-26 002120`
- `2021-12-01 600072`
- `2021-12-08 002508`
- `2022-08-02 000547`
- `2022-11-24 000600`
- `2022-12-02 603589`

Do not restore global pre-open pending-position visibility without retesting
the 2020 double-buy counterexample `2020-05-11 002351`.

### 5. Preprocessed Project Features Were Needed For Efficiency

Full warm replay from 2020 became too slow. Checkpoints and project feature
caches were introduced:

- 2020-2021 warm checkpoint: `checkpoints/emotion_gate_20211231.pkl`.
- Year replays from checkpoint reduced later-year runs to roughly 8-13 minutes
  instead of repeatedly replaying 2020 onward.
- Project-specific feature caches live under `project_cache/features` and are
  accessed via the compat profile, not by hardcoding emotion-gate logic into
  the reusable engine.

## 2020 Findings And Solutions

### 2020-02 / 2020-03: ST/Name Snapshot Affected State Machine

Problem:

- hdata marked `600666` and `600654` as ST on `2020-02-28`.
- JQ bought them on `2020-03-02`.
- Filtering them locally changed later PnL, bull cooldown, and active-state
  around `2020-03-17` / `2020-03-18`.

Solution:

- Add narrow non-ST name windows for `600666.XSHG` and `600654.XSHG` on
  `2020-02-28`.

### 2020-04 / 2020-05: `600856` ST Effective Window

Problem:

- hdata clean ST history marked `600856` too early for JQ reproduction.
- JQ-compatible path must keep the `2020-04-30` buy and `2020-05-06` sell.

Solution:

- Treat `600856.XSHG` as non-ST through `2020-05-06`.
- Apply ST behavior from `2020-05-07`.

### 2020-07 / 2020-12: Additional ST/Name Previous-Day Windows

Problem:

- Several JQ-observed buys were filtered locally because the previous-day
  `get_all_securities` display name looked ST or delisting-like in hdata/static
  metadata.

Solution:

- Add exact previous-day non-ST display-name windows:
  `002192`, `600255`, `002256`, `600145`, `002638`, `600687`, `000673`,
  `600146`, `000585`.

### 2020 First-Board NaN Propagation

Problem:

- JQ mother log kept `FB=nan` and `fb_pct=0.0` on `2020-08-05`,
  `2020-08-26`, and `2020-09-17`.
- Local finite values changed the 60-day rank and branch routing.

Solution:

- Add `_apply_jq_fb_state_overrides` in the cloned application strategy.
- Override both current `FB/fb_pct` and appended history values for those exact
  dates.

Validation:

- Latest 2020 compare: JQ `395`, local `395`, matched `395`,
  JQ-only `0`, local-only `0`.

Remaining limitation:

- 2020 amount/price/balance are not perfectly identical. The first material
  amount divergence is traced to small price/cash drift around
  `2020-07-15/16`, not to missing trade keys.

## 2021 Findings And Solutions

### 2021 ST/Name Snapshot Divergence

Problem:

- JQ bought stocks that hdata clean ST history would filter locally.
- User JQ probes showed `600702`, `601020`, and `000980` could have clean
  `get_all_securities` display names while `get_extras('is_st')` was `True`
  and limits behaved like ST.

Solution:

- Add exact previous-day windows:
  `002147` on `2021-01-14`, `600702` on `2021-04-21`,
  `601020` on `2021-09-10`, `000980` on `2021-12-10`.
- Rebuild affected preprocessed auction candidate cache after adding `000980`.

### 2021 v130 Tail-Seal Snapshot: `000420`

Problem:

- On `2021-11-16`, JQ v130 excluded one tail-seal candidate and bought
  `002507`; local kept `000420` and bought the wrong stock.

Solution:

- Force `000420.XSHE` first/tail seal time on `2021-11-15` to `14:00`.

### 2021 Same-Minute Auction/v227 Duplicates

Problem:

- `002120`, `600072`, and `002508` appeared as same-stock `竞价买` and
  `v227买` intents in the same pre-open minute.
- The current derived 2021 baseline kept only one trade key.

Solution:

- Use the narrow duplicate-drop table for those exact 2021 date/code pairs.
- Do not globalize this behavior.

Validation:

- Latest 2021 compare: JQ `455`, local `455`, matched `455`,
  JQ-only `0`, local-only `0`.

Remaining limitation:

- 2021 baseline is trade-key oriented. Reliable amount/price/order-id parity
  requires raw JQ trade export.

## 2022 Findings And Solutions

### 2022 ST/Name Snapshot Divergence

Problem:

- JQ mother log included ST-name securities in candidate pools where hdata clean
  snapshots filtered them.

Solution:

- Add narrow previous-day windows for observed cases:
  `600191`, `600091`, `600093`, `002086`, `600146`, `002684`, `002470`.

### 2022-07-04 `600032` Daily High-Limit Snapshot

Problem:

- `_rzq_prepare` requires previous-day high to equal high_limit.
- hdata had `2022-07-01 high=16.12`, `high_limit=16.11`.
- JQ bought `600032` on `2022-07-04`.

Rejected solution:

- A broad `abs(high - high_limit) <= 0.02` tolerance worsened alignment badly.

Accepted solution:

- Add one daily price anomaly:
  `("600032.XSHG", 20220701, "high_limit") -> 16.12`.

### 2022-07-08 `002470` Minute Sell Snapshot

Problem:

- JQ sold `002470` at `2022-07-08 14:47` with `ret=-3.3%`.
- Local minute snapshot did not trigger the scheduled RZQ stop.

Solution:

- Add one minute price anomaly:
  `("20220708", "14:47", "002470.XSHE") -> 2.32`.

### 2022-08-26 `603721` Billboard Snapshot

Problem:

- Local billboard data admitted `603721` into RZQ; JQ did not.
- This consumed slot/cash and blocked three JQ `zb` buys.

Solution:

- Filter exact billboard row `20220825 603721.XSHG` in the project compat
  layer.

### 2022-12-27 `002487` Tail-Seal Precision Miss

Problem:

- Local first-seal detector missed `002487` because minute price was stored as
  approximately `41.439999` while daily high_limit was `41.44`.
- JQ v130 treated it as a tail-seal exclusion and bought `002518` instead.

Solution:

- Add exact seal override:
  `("20221226", "002487.XSHE") -> 2022-12-26 14:41:00`.

### 2022 Same-Minute Duplicate Baseline Cases

Problem:

- Derived 2022 trade table kept only one leg of several same-minute duplicate
  intents.

Solution:

- Extend duplicate-drop table for the current derived baseline:
  `000547`, `000600`, `603589`.

Validation:

- Latest 2022 compare: JQ `427`, local `429`, matched `427`,
  JQ-only `0`, local-only `2`.
- The two local-only rows are `2022-08-24/25 000728`, which are visible in the
  mother log and classified as `jq_trades_actual.csv` extraction omissions.

## 2023 Findings And Solutions

### 2023-01-04 `600532` ST/Name Snapshot

Problem:

- hdata showed `600532` as `*ST未来` on `2023-01-03`.
- JQ bear/scorpion pool included it and bought it on `2023-01-04`.

Solution:

- Add non-ST window for `600532.XSHG` on `2023-01-03`.

### 2023-02-17 V227 Shock Cooldown

Problem:

- JQ mother log triggered one-day v227 shock cooldown on `2023-02-17`.
- Local mark-to-market missed the threshold and bought `002722`, causing a
  downstream path miss.

Solution:

- Add exact state override after cooldown calculation:
  `2023-02-17 -> g.v227_shock_cooldown = 1`.

### 2023-02-27/28 `002229` RZQ Stop Boundary

Problem:

- Local sold `002229` on `2023-02-28`; JQ held until `2023-03-01`.
- JQ probes showed both minute snapshot and execution-price differences.

Solution:

- Add minute anomalies:
  `("20230228", "11:28", "002229.XSHE") -> 15.18`
  and `("20230228", "14:47", "002229.XSHE") -> 15.14`.
- Add execution anomaly:
  `("20230227", "09:30", "002229.XSHE", "buy") -> 15.60`.

### 2023-03 / 2023-04 `600518`

Problem:

- Local filtered `600518` due to ST-looking previous-day name.
- After name fix, local still failed the `2023-03-24 11:30` sell boundary
  because buy average was `2.17` instead of JQ `2.16`.

Solution:

- Add non-ST windows for `600518.XSHG` on `2023-03-22` and `2023-04-10`.
- Add execution anomaly:
  `("20230323", "09:30", "600518.XSHG", "buy") -> 2.16`.

Validation:

- JQ probe confirmed `2023-03-24 11:30 last=2.17`, `avg=2.16`,
  `ret=0.463%`, matching mother-log `ret=0.5%`.

### 2023-06-02 Bear Pool ST/Name Snapshot

Problem:

- JQ bear pool included several names that local hdata showed as ST on
  `2023-06-01`.
- Only `600242` naturally passed the scorpion open-gap buy window.

Solution:

- Add exact `2023-06-01` non-ST windows:
  `000839`, `600242`, `600532`, `603030`, `603880`.

### 2023-12-13 `002395` ZB Sell Boundary

Problem:

- Local bought `002395` at `13.61` and did not sell on `2023-12-13 11:30`.
- JQ mother log sold at `ret=0.1%`.

JQ probe result:

- `MarketOrderStyle(day_open=13.60)` filled at `13.60`.

Solution:

- Add execution anomaly:
  `("20231212", "09:30", "002395.XSHE", "buy") -> 13.60`.

Validation:

- Latest 2023 compare:
  JQ `277`, local `284`, matched `277`, JQ-only `0`, local-only `7`.
- The December path realigned:
  `002395` sell, `002176/002878` buys, and their later sells all match.

Remaining 2023 local-only rows:

- `2023-02-21 000581 buy`
- `2023-03-08/09 002778 buy/sell`
- `2023-03-10 600895 buy`
- `2023-04-18 000960 buy`
- `2023-11-20 002703 buy`
- `2023-12-01 002031 buy`

Classification:

- These are not JQ-only misses. The mother log contains the corresponding
  printed strategy intents or path events.
- Most are same-minute `竞价买 + v227买` duplicate-intent cases where the
  derived baseline kept only one buy key.
- `002778` is visible in the mother log as `[zb买]` and later `[bull强清]`,
  but omitted by the derived trade table.

## Rejected Or Non-Generalized Fixes

These were deliberately not accepted as broad rules:

- Global ST filtering from hdata `st_list`: rejected because JQ
  `get_all_securities` display names diverge from `get_extras('is_st')` and
  clean ST history.
- Global pre-open position reservation: rejected because it regresses validated
  2020 same-stock double-buy behavior.
- Broad high/high_limit tolerance: rejected because it worsened 2022 alignment.
- Global `MarketOrderStyle(day_open)` execution price rule: not accepted; only
  exact JQ-probed execution anomalies were added.
- Broad minute-price replacement from hdata to JQ: not accepted; only exact
  observed minute snapshots were patched.

## Implementation Map

Project-specific compatibility:

- `rebuild_from_archive/project_compat.py`
  - `non_st_name_windows`
  - `tail_seal_anomalies`
  - `minute_price_anomalies`
  - `daily_price_anomalies`
  - `execution_price_anomalies`
  - project feature cache readers

Framework hooks:

- `rebuild_from_archive/engine/core.py`
  - optional `compat` injection
  - execution/minute anomaly lookup
  - pre-open duplicate hook
  - checkpoint resume hook
- `rebuild_from_archive/engine/data_api.py`
  - JQ-compatible data surface and compat-filter hooks

Application strategy state overrides:

- `母版-20260506-Clone.py`
  - first-board NaN state overrides
  - v227 shock-cooldown date override
  - derived-baseline duplicate intent table

Documentation:

- `alignment_open_issues.md`
- `rebuild_from_archive/FRAMEWORK_SEPARATION.md`
- `alignment_reports/amount_diff_root_causes_2020-2021.md`
- this report

## Recommended Next Steps

1. Preserve the current compat layer as the 2020-2023 JQ reproduction profile.
2. Do not promote project quirks into the shared LocalQuant base until they are
   recast as optional profiles.
3. Request raw JQ trade exports with order ids, amount, price, commission, tax,
   and cash snapshots for 2021-2023 before claiming amount/balance parity.
4. Build a project-local JQ-compatible point-in-time display-name table to
   replace the growing manual `non_st_name_windows` map.
5. Keep using checkpoints and preprocessed feature caches for later-year
   alignment and optimization runs.
