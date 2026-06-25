# JQ Archive Plan

These hooks exist to replay archived JoinQuant behavior and should not be carried into a future local-native baseline.

## Ablation Waves

### L1A — 价格类钩子（第一批关闭）

- `market_data.minute_price_anomalies`
  - direct: ['price'], downstream: cash_path
- `execution.execution_price_anomalies`
  - direct: ['price'], downstream: cash_path

### L1B — 数量类钩子（第二批关闭）

- `execution.order_amount_anomalies`
  - direct: ['size', 'order'], downstream: position_path
- `execution.fill_amount_anomalies`
  - direct: ['size', 'fill'], downstream: position_path

### L2 — 订单存在性类钩子（第三批关闭）

- `execution.preopen_reject_cash_below`
  - direct: ['order_presence'], downstream: strategy_path
- `execution.preopen_reject_orders`
  - direct: ['order_presence'], downstream: strategy_path
- `execution.preopen_drop_first_duplicate`
  - direct: ['order_presence'], downstream: strategy_path

### L3 — 状态历史答案类钩子（第四批关闭）

- `strategy_state.fb_state_overrides`
  - direct: ['state'], downstream: strategy_path
- `strategy_state.v227_shock_overrides`
  - direct: ['state'], downstream: strategy_path

### L4 — JQ数据形态类钩子

只有在本地原生模式明确接受本地数据形态后再关闭。

- `market_data.daily_ipo_close_anomalies`
  - direct: ['data_shape'], downstream: selection

## 非消融项（Legacy Cleanup）

以下不属于策略消融变量，只能在确认没有调用者后删除。

- `legacy.temporary_fallbacks_shim`: This module exists only to absorb deprecated imports from the old JQ parity path. It is a legacy cleanup item, not a strategy ablation variable.

## 所有 archive-only 钩子明细

### `market_data.minute_price_anomalies`
- 消融波次: `L1A`
- direct_effect_scope: `['price']`
- downstream_risk: `cash_path`
- reason: These are point answers for historical JoinQuant parity and do not describe a reusable market rule.
- affects selection/state/order/fill/nav: no/no/no/yes/yes
- empty_config: `no`
- disable requirement: Safe first-wave disable candidate for local-native mode if some trade price and NAV drift is acceptable.
- delete requirement: Delete once the project formally stops supporting JoinQuant minute-fill parity.

### `market_data.daily_ipo_close_anomalies`
- 消融波次: `L4`
- direct_effect_scope: `['data_shape']`
- downstream_risk: `selection`
- reason: This behavior exists to mimic the historical JoinQuant return shape, not to express a stable local market-data rule.
- affects selection/state/order/fill/nav: yes/yes/no/no/no
- empty_config: `no`
- disable requirement: Can be disabled in local-native mode once IPO handling is expected to follow local data directly.
- delete requirement: Delete after the project drops JoinQuant daily-history shape parity.

### `execution.preopen_reject_cash_below`
- 消融波次: `L2`
- direct_effect_scope: `['order_presence']`
- downstream_risk: `strategy_path`
- reason: This is a recorded JoinQuant answer for one historical event, not a general exchange rule.
- affects selection/state/order/fill/nav: no/no/yes/no/yes
- empty_config: `no`
- disable requirement: Safe early-disable candidate when leaving JQ parity, with the expectation that only order acceptance and downstream NAV change.
- delete requirement: Delete when JQ pre-open rejection replay is no longer a supported mode.

### `execution.preopen_reject_orders`
- 消融波次: `L2`
- direct_effect_scope: `['order_presence']`
- downstream_risk: `strategy_path`
- reason: This is only meaningful for replaying specific historical JoinQuant refusals.
- affects selection/state/order/fill/nav: no/no/yes/no/no
- empty_config: `yes`
- disable requirement: Can be disabled with JQ parity hooks; impacts order presence but not upstream candidate logic.
- delete requirement: Delete after dropping archived JoinQuant pre-open order replay support.

### `execution.preopen_drop_first_duplicate`
- 消融波次: `L2`
- direct_effect_scope: `['order_presence']`
- downstream_risk: `strategy_path`
- reason: This duplicates a platform queue quirk, not a stable project rule.
- affects selection/state/order/fill/nav: no/no/yes/no/no
- empty_config: `no`
- disable requirement: Can be disabled with only order-path effects once JQ parity is no longer required.
- delete requirement: Delete after archived JoinQuant duplicate-order replay is retired.

### `execution.execution_price_anomalies`
- 消融波次: `L1A`
- direct_effect_scope: `['price']`
- downstream_risk: `cash_path`
- reason: These are historical fill answers, not a general-purpose matcher rule.
- affects selection/state/order/fill/nav: no/no/no/yes/yes
- empty_config: `no`
- disable requirement: Good first-wave disable candidate for local-native if fill-price drift is acceptable.
- delete requirement: Delete after JoinQuant execution-price parity is no longer maintained.

### `execution.order_amount_anomalies`
- 消融波次: `L1B`
- direct_effect_scope: `['size', 'order']`
- downstream_risk: `position_path`
- reason: These are historical mother-path answers, not reusable sizing logic.
- affects selection/state/order/fill/nav: no/no/yes/yes/yes
- empty_config: `no`
- disable requirement: Can be disabled in local-native mode; expect trade-size and NAV drift but not upstream candidate changes.
- delete requirement: Delete when the project stops preserving mother-path quantity parity.

### `execution.fill_amount_anomalies`
- 消融波次: `L1B`
- direct_effect_scope: `['size', 'fill']`
- downstream_risk: `position_path`
- reason: This is fill-answer replay, not a generic exchange or broker rule.
- affects selection/state/order/fill/nav: no/no/no/yes/yes
- empty_config: `no`
- disable requirement: Can be disabled with only fill and NAV consequences once parity mode is not required.
- delete requirement: Delete after archived fill-size parity support is retired.

### `strategy_state.fb_state_overrides`
- 消融波次: `L3`
- direct_effect_scope: `['state']`
- downstream_risk: `strategy_path`
- reason: These dates preserve historical JoinQuant state answers and do not represent a reusable project rule.
- affects selection/state/order/fill/nav: yes/yes/yes/no/no
- empty_config: `no`
- disable requirement: Do not disable until local-native mode explicitly accepts candidate/state divergence on these dates.
- delete requirement: Delete after the project stops supporting JoinQuant state-snapshot replay.

### `strategy_state.v227_shock_overrides`
- 消融波次: `L3`
- direct_effect_scope: `['state']`
- downstream_risk: `strategy_path`
- reason: This is a historical parity answer for one state transition, not a general strategy definition.
- affects selection/state/order/fill/nav: yes/yes/yes/no/no
- empty_config: `no`
- disable requirement: Do not disable until the project accepts branch-trigger drift for the affected date in local-native mode.
- delete requirement: Delete after JQ shock-state replay is retired.
