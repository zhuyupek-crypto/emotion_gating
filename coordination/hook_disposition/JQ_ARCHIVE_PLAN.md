# JQ Archive Plan

These hooks exist to replay archived JoinQuant behavior and should not be carried into a future local-native baseline.

## First-wave disable candidates

- `market_data.minute_price_anomalies`: disable first when local-native mode is allowed to drift only in price/size/fill/NAV.
- `execution.preopen_reject_cash_below`: disable first when local-native mode is allowed to drift only in price/size/fill/NAV.
- `execution.preopen_reject_orders`: disable first when local-native mode is allowed to drift only in price/size/fill/NAV.
- `execution.preopen_drop_first_duplicate`: disable first when local-native mode is allowed to drift only in price/size/fill/NAV.
- `execution.execution_price_anomalies`: disable first when local-native mode is allowed to drift only in price/size/fill/NAV.
- `execution.order_amount_anomalies`: disable first when local-native mode is allowed to drift only in price/size/fill/NAV.
- `execution.fill_amount_anomalies`: disable first when local-native mode is allowed to drift only in price/size/fill/NAV.
- `legacy.temporary_fallbacks_shim`: disable first when local-native mode is allowed to drift only in price/size/fill/NAV.

## Remaining archive-only hooks

## `market_data.minute_price_anomalies`
- reason: These are point answers for historical JoinQuant parity and do not describe a reusable market rule.
- affects selection/state/order/fill/nav: no/no/no/yes/yes
- disable requirement: Safe first-wave disable candidate for local-native mode if some trade price and NAV drift is acceptable.
- delete requirement: Delete once the project formally stops supporting JoinQuant minute-fill parity.

## `market_data.daily_ipo_close_anomalies`
- reason: This behavior exists to mimic the historical JoinQuant return shape, not to express a stable local market-data rule.
- affects selection/state/order/fill/nav: yes/yes/no/no/no
- disable requirement: Can be disabled in local-native mode once IPO handling is expected to follow local data directly.
- delete requirement: Delete after the project drops JoinQuant daily-history shape parity.

## `execution.preopen_reject_cash_below`
- reason: This is a recorded JoinQuant answer for one historical event, not a general exchange rule.
- affects selection/state/order/fill/nav: no/no/yes/no/yes
- disable requirement: Safe early-disable candidate when leaving JQ parity, with the expectation that only order acceptance and downstream NAV change.
- delete requirement: Delete when JQ pre-open rejection replay is no longer a supported mode.

## `execution.preopen_reject_orders`
- reason: This is only meaningful for replaying specific historical JoinQuant refusals.
- affects selection/state/order/fill/nav: no/no/yes/no/no
- disable requirement: Can be disabled with JQ parity hooks; impacts order presence but not upstream candidate logic.
- delete requirement: Delete after dropping archived JoinQuant pre-open order replay support.

## `execution.preopen_drop_first_duplicate`
- reason: This duplicates a platform queue quirk, not a stable project rule.
- affects selection/state/order/fill/nav: no/no/yes/no/no
- disable requirement: Can be disabled with only order-path effects once JQ parity is no longer required.
- delete requirement: Delete after archived JoinQuant duplicate-order replay is retired.

## `execution.execution_price_anomalies`
- reason: These are historical fill answers, not a general-purpose matcher rule.
- affects selection/state/order/fill/nav: no/no/no/yes/yes
- disable requirement: Good first-wave disable candidate for local-native if fill-price drift is acceptable.
- delete requirement: Delete after JoinQuant execution-price parity is no longer maintained.

## `execution.order_amount_anomalies`
- reason: These are historical mother-path answers, not reusable sizing logic.
- affects selection/state/order/fill/nav: no/no/yes/yes/yes
- disable requirement: Can be disabled in local-native mode; expect trade-size and NAV drift but not upstream candidate changes.
- delete requirement: Delete when the project stops preserving mother-path quantity parity.

## `execution.fill_amount_anomalies`
- reason: This is fill-answer replay, not a generic exchange or broker rule.
- affects selection/state/order/fill/nav: no/no/no/yes/yes
- disable requirement: Can be disabled with only fill and NAV consequences once parity mode is not required.
- delete requirement: Delete after archived fill-size parity support is retired.

## `strategy_state.fb_state_overrides`
- reason: These dates preserve historical JoinQuant state answers and do not represent a reusable project rule.
- affects selection/state/order/fill/nav: yes/yes/yes/no/no
- disable requirement: Do not disable until local-native mode explicitly accepts candidate/state divergence on these dates.
- delete requirement: Delete after the project stops supporting JoinQuant state-snapshot replay.

## `strategy_state.v227_shock_overrides`
- reason: This is a historical parity answer for one state transition, not a general strategy definition.
- affects selection/state/order/fill/nav: yes/yes/yes/no/no
- disable requirement: Do not disable until the project accepts branch-trigger drift for the affected date in local-native mode.
- delete requirement: Delete after JQ shock-state replay is retired.

## `legacy.temporary_fallbacks_shim`
- reason: This module exists only to absorb deprecated imports from the old JQ parity path.
- affects selection/state/order/fill/nav: no/no/no/no/no
- disable requirement: Can be removed once import-path audit confirms there are no remaining users.
- delete requirement: Delete after repo and external workflow scans prove the shim is unused.
