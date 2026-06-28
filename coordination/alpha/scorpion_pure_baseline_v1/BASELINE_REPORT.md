# Scorpion Pure-Bear Baseline v1 — Full Period (2018-2025)

**Task**: TASK-SCORPION-PURE-BASELINE-001
**Strategy**: `scorp_optimize/strategies/strategy_v227_scorp.py`
**Strategy SHA256**: `d34af30fd8805300403df6af7e5943aba4acb01f429018c1ac0c60cd79307fda`
**Emotion_gating commit**: `3e75774556e1aa8e85451f8558c9536161ade278`
**hdata_reader SHA256**: `bbd4671ea342fcf206dfec5f4ada6da85dbcaf3df3a5bb7c3b1b1010f6d9e361`
**Period**: 2018-01-01 to 2025-12-31
**Slots**: 2 | **Initial cash**: 1,000,000
**Elapsed**: 3160.997s

## Formal Fix Applied

```python
# history_fallback path (line 576)
# Before:
if bear_pool:
# After:
if bear_pool and g.market_mode == 'bear':
```

This one-line fix makes the history_fallback path consistent with the board_snapshot
path (line 531). No other strategy logic, parameters, exit rules, stops, costs,
or sorting were modified. No monkey patching — the fix is committed to the
strategy file directly.

## Overall Metrics

| Metric | Value |
|--------| 2018 | 31 | 61.2903% | 1.2950% | 0.4015 | 8.9600% |
| 2019 | 31 | 70.9677% | 2.3874% | 0.7401 | 3.5453% |
| 2020 | 18 | 61.1111% | 1.5018% | 0.2703 | 4.2809% |
| 2021 | 15 | 60.0000% | 2.7500% | 0.4125 | 13.2933% |
| 2022 | 35 | 60.0000% | 1.1665% | 0.4083 | 6.5853% |
| 2023 | 11 | 72.7273% | 2.3076% | 0.2538 | 4.4614% |
| 2024 | 23 | 73.9130% | 3.4444% | 0.7922 | 6.5135% |
| 2025 | 5 | 80.0000% | 4.5860% | 0.2293 | 3.1062% |

## Market Mode Breakdown (at buy time)

| Mode | Trades | Win rate | EV | Profit contribution |
|------|--------|----------|-----|---------------------|
| bear | 169 | 65.6805% | 2.0757% | 3.5080 |
| bull | 0 | - | - | - |
| cautious | 0 | - | - | - |

**All trades are bear mode.** Primary market mode: **bear**.

## Yearly Metrics

> **Note**: profit_contribution 字段表示各交易收益率之和，不代表组合资金利润占比。

| Year | Trades | Win rate | EV | Profit contribution | Max drawdown |
|------|--------|----------|-----|---------------------|---------------|
| 2018 | 31 | 61.2903% | 1.2950% | 0.4015 | 0.0000% |
| 2019 | 31 | 70.9677% | 2.3874% | 0.7401 | 0.0000% |
| 2020 | 18 | 61.1111% | 1.5018% | 0.2703 | 0.0000% |
| 2021 | 15 | 60.0000% | 2.7500% | 0.4125 | 0.0000% |
| 2022 | 35 | 60.0000% | 1.1665% | 0.4083 | 0.0000% |
| 2023 | 11 | 72.7273% | 2.3076% | 0.2538 | 0.0000% |
| 2024 | 23 | 73.9130% | 3.4444% | 0.7922 | 0.0000% |
| 2025 | 5 | 80.0000% | 4.5860% | 0.2293 | 0.0000% |

## Concentration

- Best year: 2025
- Worst year: 2022
- Best year profit ratio: 6.5365%
- Top 5 profit ratio: 32.6326%
- Top 10 profit ratio: 50.2423%
- Max gain trade: 002143.XSHE ret=33.3333%
- Max loss trade: 000760.XSHE ret=-8.2857%

## Comparison with Original Baseline (231 trades)

The original baseline (`coordination/alpha/scorpion_baseline_v1/`) contains 231
trades: 169 bear + 28 bull + 34 cautious. This pure-bear baseline contains only
the 169 bear trades, because the fix prevents `bear_candidates` from being
populated in bull/cautious modes.

### Signal & Execution Consistency (must match)

| Field | Status | Differences |
|-------|--------|-------------|
| code | ✅ identical | 0 |
| entry_date | ✅ identical | 0 |
| buy_price | ✅ identical | 0 |
| exit_date | ✅ identical | 0 |
| sell_price | ✅ identical | 0 |

**Overall signal/execution consistency: PASS**

### Portfolio State (allowed to differ)

| Field | Status | Differences |
|-------|--------|-------------|
| shares | 不适用 (portfolio-state effect) | 145 |

删除62笔非bear交易会改变现金和复利路径，因此后续shares变化属于预期组合状态效应，不属于信号或交易逻辑差异。

### Additional Comparison

| Field | Status | Differences |
|-------|--------|-------------|
| 单笔未加权收益率 (ret) | ✅ identical | 0 |
| 持股天数 (holding_days) | ✅ identical | 0 |

### Yearly Trade Count Comparison

| Year | Original bear | Pure bear |
|------|---------------|-----------|
| 2018 | 31 | 31 |
| 2019 | 31 | 31 |
| 2020 | 18 | 18 |
| 2021 | 15 | 15 |
| 2022 | 35 | 35 |
| 2023 | 11 | 11 |
| 2024 | 23 | 23 |
| 2025 | 5 | 5 |

## Verification

- Strategy SHA256 verified: `d34af30fd8805300403df6af7e5943aba4acb01f429018c1ac0c60cd79307fda`
- hdata_reader SHA256 verified: `bbd4671ea342fcf206dfec5f4ada6da85dbcaf3df3a5bb7c3b1b1010f6d9e361`
- No monkey patching: strategy file read as-is from disk
- All trades are bear mode (169 bear, 0 bull, 0 cautious)
- No defensive buy guard in `buy_v227_天蝎座()` (only candidate fix retained)

## Run Provenance

- Git HEAD at run: `3e75774556e1aa8e85451f8558c9536161ade278`
- Git clean at snapshot: False
- Run timestamp: 2026-06-29T07:43:40.029584
- Elapsed: 3160.997s
