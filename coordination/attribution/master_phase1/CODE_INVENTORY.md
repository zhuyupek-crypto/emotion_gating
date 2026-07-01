# Code Inventory

Generated for Phase 0 on branch `codex/motherboard-attribution-phase0-v1`.

Baseline:

```text
commit: cf542415191e952aa328250a3ee86bb15346a6b8
tag: motherboard-performance-baseline-v1
```

Static machine-readable outputs:

```text
FILE_HASHES.json
BRANCH_BASELINE_MANIFEST.json
STATIC_INVENTORY.json
```

## Motherboard

Primary file:

```text
母版-20260506-Clone.py
sha256: 621a9c968473d73dfa1699be0a16714790e4f93ab950957c0a3f88f4f34bcc8e
line_count: 2226
```

Key entries:

```text
initialize: 母版-20260506-Clone.py:88
prepare_all: 母版-20260506-Clone.py:220
market mode and scan: _v227_mode_and_scan at 母版-20260506-Clone.py:492
YJJ/Scorpion shared scan: _scan_boards_for_prev at 母版-20260506-Clone.py:554, _scan_all at 母版-20260506-Clone.py:650
RZQ prepare: _rzq_prepare at 母版-20260506-Clone.py:869
ZB prepare: _zb_prepare at 母版-20260506-Clone.py:938
Auction prepare: _auction_yiqian_prepare at 母版-20260506-Clone.py:1055
```

Buy handlers:

```text
buy_auction_yiqian: 母版-20260506-Clone.py:1302
buy_v227_一进二: 母版-20260506-Clone.py:1471
buy_v227_天蝎座: 母版-20260506-Clone.py:1544
buy_rzq: 母版-20260506-Clone.py:1586
buy_zb: 母版-20260506-Clone.py:1692
```

Sell and risk handlers:

```text
sell_auction_yiqian: 母版-20260506-Clone.py:1421
sell_v227_morning: 母版-20260506-Clone.py:1795
sell_rzq_slots: 母版-20260506-Clone.py:1816
sell_zb_slots: 母版-20260506-Clone.py:1856
check_stop_all: 母版-20260506-Clone.py:1902
sell_v227_midday: 母版-20260506-Clone.py:2031
sell_v227_afternoon: 母版-20260506-Clone.py:2057
tag_leaders: 母版-20260506-Clone.py:2105
```

Owner and cleanup:

```text
g.owner initialized: 母版-20260506-Clone.py:160
sold-owner cleanup in prepare_all: 母版-20260506-Clone.py:238
owner write auction: 母版-20260506-Clone.py:1408
owner write YJJ: 母版-20260506-Clone.py:1538
owner write Scorpion: 母版-20260506-Clone.py:1580
owner write RZQ: 母版-20260506-Clone.py:1686
owner write ZB: 母版-20260506-Clone.py:1785
clear helpers: 母版-20260506-Clone.py:2120 and 母版-20260506-Clone.py:2128
```

Cooldown and win tracking:

```text
stoploss_cooldown initialized: 母版-20260506-Clone.py:115
rzq_cooldown initialized: 母版-20260506-Clone.py:123
bull_cooldown initialized: 母版-20260506-Clone.py:165
v227_shock_cooldown initialized: 母版-20260506-Clone.py:184
cooldown decrement: 母版-20260506-Clone.py:250
shock update: 母版-20260506-Clone.py:409
win helpers: _win_rate at 母版-20260506-Clone.py:2152, _core_win_rate at 母版-20260506-Clone.py:2159, _win_scale at 母版-20260506-Clone.py:2166
trade tracker: _record_trade at 母版-20260506-Clone.py:2191
```

## Schedule

| Time | Handler | Branch / purpose | Can consume cash | Can occupy position |
| --- | --- | --- | --- | --- |
| 9:05 | `prepare_all` | state, scan, route, slots | no | no |
| 9:26 | `buy_auction_yiqian` | Auction | yes | yes |
| 9:26 | `buy_v227_一进二` | YJJ | yes | yes |
| 9:27 | `buy_rzq` | RZQ | yes | yes |
| 9:28 | `buy_zb` | ZB | yes | yes |
| 9:30 | `buy_v227_天蝎座` | Scorpion | yes | yes |
| 11:25 | `sell_v227_morning` | YJJ/Scorpion v227 exits | no | reduces |
| 11:25 | `sell_auction_yiqian` | Auction exits | no | reduces |
| 11:28 | `sell_rzq_slots` | RZQ exits | no | reduces |
| 11:30 | `sell_zb_slots` | ZB exits | no | reduces |
| every_bar | `check_stop_all` | global/branch stop handling | no | reduces |
| 13:01 | `sell_v227_midday` | v227 exits | no | reduces |
| 14:47 | `sell_rzq_slots` | RZQ exits | no | reduces |
| 14:48 | `sell_zb_slots` | ZB exits | no | reduces |
| 14:50 | `sell_v227_afternoon` | v227 exits | no | reduces |
| 14:50 | `sell_auction_yiqian` | Auction exits | no | reduces |
| 14:50 | `sell_rzq_slots` | RZQ exits | no | reduces |
| 14:52 | `sell_zb_slots` | ZB exits | no | reduces |
| 14:55 | `tag_leaders` | leader tagging | no | no |

## Route Chain

`prepare_all` resets candidates and transient maps, cleans owner state, decrements cooldowns, calculates first-board performance, and appends `fb_pct`.

`_v227_mode_and_scan` calculates `raw_market_mode`, applies bull stickiness to `market_mode`, and scans either `_scan_boards_for_prev` or `_scan_all`.

`prepare_all` then scans RZQ when `_is_pass_month(context)` is false. ZB is scanned only when pass-month is false and `market_mode == 'bull'`.

Route decision:

```text
bear -> active v227
cautious -> active v227
fb_pct >= 0.8 -> active v227
bull_release_guard -> active v227
otherwise bull and not pass month -> active rzq+zb
else -> active v227
```

Enable and slots:

```text
active v227: enable_v227 true, v227/rzq/zb slots = 2/0/0
active rzq+zb: enable_rzq and enable_zb true, slots = 0/3/3
auction: independent sleeve; daily value decides enable_auction_yiqian and one slot
```

## Branch Signal Chains

### YJJ

```text
base universe -> previous first-board detection -> invalid code/ST/listing-age filter -> yjj_candidates -> v227 route -> YJJ buy gate -> open-gap/position/cash/order -> v227 exits
```

Phase 0 status: `PURE_UNCERTAIN`. `force_v227` contains both YJJ and Scorpion and is not a pure YJJ branch.

### Scorpion

```text
base universe -> previous first-board weak/bear pool -> bear_candidates -> bear market route -> Scorpion buy gate -> low-open repair entry -> v227 exits/stop
```

Phase 0 status: `PURE_PASS` based on existing Scorpion-specific research artifact path, but Phase 1 should still revalidate mapping in the current observer.

### RZQ

```text
RZQ prepare -> internal filters and scoring -> active rzq+zb -> RZQ buy gates/cooldown -> slot/rank/cash/order -> RZQ exits/stop
```

Phase 0 status: `NOT_AUDITED`.

### ZB

```text
ZB prepare -> previous broken-limit-board pattern -> filters and scoring -> active rzq+zb -> ZB buy gates -> slot/rank/cash/order -> ZB exits/stop
```

Phase 0 status: `NOT_AUDITED`.

### Auction

```text
auction prepare -> first-board and weak-turn-strong auction variants -> left-pressure checks -> independent auction sleeve enable/value -> rank/cap/slot/cash/order -> auction trailing/MA exits
```

Phase 0 status: `NOT_AUDITED`; data timing risk is explicitly `UNKNOWN/RISK` until sample playback proves availability.

## Engine and Infrastructure

Core files:

```text
Engine: rebuild_from_archive/engine/core.py
Context/Portfolio/Position: rebuild_from_archive/engine/context.py
Order/Trade/Slippage/Cost: rebuild_from_archive/engine/order.py
DataAPI: rebuild_from_archive/engine/data_api.py
project_compat: rebuild_from_archive/project_compat.py
jqdata_compat: rebuild_from_archive/jqdata_compat.py
hdata_reader.py: D:\work space\hdata\scripts\core\hdata_reader.py
```

Current directly recorded fields:

```text
Engine.trades: time, code, amount, price, commission, tax, trade_id, order_id
Engine.orders: order object keyed by order_id with security, amount, filled, price, style, side, status, add_time, commission
Engine.daily_state_snapshots: date, market_mode, raw_market_mode, active, FB, fb_pct, cooldowns, enable flags, slots, candidate counts, cash, locked cash, positions, owners
Portfolio: available_cash, locked_cash, positions
Position: security, avg_cost, total_amount, closeable_amount, price
```

Current missing fields:

```text
signal_id
branch-specific raw_pattern_hit rows
per-filter pass/fail reasons
candidate list and rank transitions
order_intent before order function call
order_id -> signal_id
trade_id -> original signal_id
exit reason -> original entry signal_id
resource blocker identity for occupied_by
```

## Data Source Risk List

| Data | Source / reader | Phase 0 risk | Note |
| --- | --- | --- | --- |
| daily price | hdata via engine DataAPI | CLEAR | hdata is the required local source; timing still depends on call date. |
| minute price | hdata via engine DataAPI | CLEAR | Used by intraday matching. |
| open price | daily price / order reference price | CLEAR | Needs Phase 1 fill mapping. |
| call auction | compat/call_auction and strategy auction calls | UNKNOWN/RISK | Must audit actual available time and fields. |
| high_limit / low_limit | daily/minute price fields | CLEAR | Needs limit-entry/exit flags. |
| board snapshot / first board | project market data helpers | UNKNOWN | Must confirm physical source and timestamp. |
| ST and listing date | security metadata | CLEAR/UNKNOWN | Source exists; exact effective-date semantics need audit. |
| industry mapping | metadata/fundamental files if used | UNKNOWN | No Phase 0 proof yet. |
| valuation/fundamental | hdata feature/fundamental files if used | UNKNOWN | Must align by available date, especially announcements. |

## Phase 1 Sensor Positions

Minimum recommended emit locations:

```text
prepare_all after candidate reset and before scans: handler resource snapshot
after each branch prepare/scan: SIGNAL_EVENT candidate list with source function
after route decision: ROUTE_GATE DECISION_EVENT for each eligible signal
before each buy handler: resource snapshot
inside each buy handler before early return: gate/slot/cash/rank decisions
immediately before order call: order_intent with signal_id
after order function returns: order_submitted/order_rejected with order_id
after Engine trade append: trade outcome mapping via order_id
inside sell handlers before order call: exit decision with original signal_id
```
