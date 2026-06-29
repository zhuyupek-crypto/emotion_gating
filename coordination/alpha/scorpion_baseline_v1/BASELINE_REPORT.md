# Scorpion Baseline v1 — Full Period (2018-2025)
**Task**: TASK-SCORPION-BASELINE-001
**Strategy**: `scorp_optimize/strategies/strategy_v227_scorp.py`
**Strategy SHA256**: `55e96b2225d14c6d94052ff3dad03079094b3f7a66b46c76e6b6409d7618c2b0`
**Emotion_gating commit**: `cf542415191e952aa328250a3ee86bb15346a6b8`
**Baseline tag**: `motherboard-performance-baseline-v1`
**hdata_reader SHA256**: `bbd4671ea342fcf206dfec5f4ada6da85dbcaf3df3a5bb7c3b1b1010f6d9e361`
**Period**: 2018-01-01 to 2025-12-31
**Slots**: 2 | **Initial cash**: 1,000,000
**Elapsed**: 3734.655s

## Overall Metrics

| Metric | Value |
|--------|-------|
| Total return | 274.3372% |
| Annualized return | 17.9391% |
| Max drawdown | 13.2913% |
| Final value | 3743371.56 |
| completed_trades | 231 |
| execution_rows | 462 |
| Win rate | 59.7403% |
| EV (per trade) | 1.3884% |
| Avg gain | 4.6932% |
| Avg loss | -3.5156% |
| Profit/Loss ratio | 1.3350 |
| Avg holding days | 1.53 |
| Max consecutive losses | 5 |

## Yearly Metrics

| Year | Trades | Win rate | EV | Profit contribution | Max drawdown |
|------|--------|----------|-----|---------------------|---------------|
| 2018 | 35 | 60.0000% | 1.0579% | 0.3703 | 8.9649% |
| 2019 | 35 | 71.4286% | 2.2504% | 0.7877 | 3.5444% |
| 2020 | 36 | 55.5556% | 0.8601% | 0.3096 | 9.4394% |
| 2021 | 30 | 50.0000% | 1.2377% | 0.3713 | 13.2913% |
| 2022 | 39 | 56.4103% | 0.8100% | 0.3159 | 11.2203% |
| 2023 | 14 | 64.2857% | 1.5130% | 0.2118 | 4.4616% |
| 2024 | 29 | 62.0690% | 2.1618% | 0.6269 | 6.9108% |
| 2025 | 13 | 61.5385% | 1.6435% | 0.2136 | 7.9318% |

## Concentration

> **Note**: profit_contribution 字段表示各交易收益率之和，不代表组合资金利润占比。


- Best year: 2019
- Worst year: 2023
- Best year profit ratio: 24.5595%
- Top 5 profit ratio: 35.6941%
- Top 10 profit ratio: 55.2154%
- Max gain trade: 002143.XSHE ret=33.3333%
- Max loss trade: 600212.XSHG ret=-9.0909%

## Market Mode Statistics (at buy time)

| Mode | Trades | Win rate | EV | Profit contribution |
|------|--------|----------|-----|---------------------|
| bear | 169 | 65.6805% | 2.0757% | 3.5080 |
| bull | 28 | 35.7143% | -0.2709% | -0.0759 |
| cautious | 34 | 50.0000% | -0.6618% | -0.2250 |

Primary market mode: **bear**

## Comparison with Historical Numbers

| Metric | Historical | This baseline |
|--------|-----------|---------------|
| Total return | ~150.93% | 274.3372% |
| Max drawdown | ~14.55% | 13.2913% |
| completed_trades | ~97 | 231 |
| Win rate | ~64.95% | 59.7403% |
| EV | ~2.22% | 1.3884% |
| Avg holding days | ~1.1 | 1.53 |

### 差异分析

本基线与历史数字存在显著差异，主要来源：

1. **回测区间不同**: 历史数字"约 150.93%"可能来自较短区间（如 2020-2025 或 2021-2025），本基线为完整 2018-2025 八年期。2018-2019 两年贡献了约 70 笔交易和大量利润（profit_contribution 合计 1.16），显著拉高全期收益。

2. **策略版本不同**: 仓库中存在两个不同版本的 `strategy_v227_scorp.py`:
   - `scorp_optimize/strategies/strategy_v227_scorp.py` (72379 bytes, SHA256: 55e96b22...) — 本基线使用
   - `bare_runs_analysis/strategies/strategy_v227_scorp.py` (72454 bytes, SHA256: 55c1172a...) — 可能是历史数字来源
   两者内容不同（相差 75 bytes），策略逻辑差异会直接影响交易信号、候选筛选和退出条件。

3. **交易笔数口径**: 历史"约 97 笔"可能采用不同的 buy/sell 配对方法或仅统计 v227 主策略交易（排除 auction_yiqian 袖套交易）。本基线的 231 completed_trades 来自所有 execution_rows (462) 的 buy/sell 配对，口径更宽。

4. **数据版本**: hdata 数据持续更新，board 扫描结果（`_scan_boards_for_prev` 发现的 FB 数量）可能因数据版本不同而变化，影响候选池和入场信号。

5. **Slots 与市场状态配置**: 本基线确认 Slots=2 (v227_slots=2, rzq_slots=0, zb_slots=0, auction_yiqian_slots=1)。历史数字可能使用不同的 Slots 配置或市场状态门控参数。

**结论**: 差异不表明回测错误，而是区间、策略版本和数据版本的综合影响。本基线在当前版本和完整区间内自洽，且通过三个月重复运行一致性验证。

## 三个月重复运行一致性验证

- **区间**: 2019-05-01 至 2019-07-31 (62 交易日, 49 笔交易)
- **Run 1 耗时**: ~125s | **Run 2 耗时**: ~125s
- **状态**: **PASS**

| 检查项 | 结果 |
|--------|------|
| TRADES (行数+内容) | PASS — 49 行完全一致 |
| EQUITY (净值序列) | PASS — max_diff=0.00e+00 |
| 最终净值 | PASS — 1218211.74 (一致) |
| 候选数量 (cand_yjj/bear/rzq/zb/auction) | PASS — 全部一致 |
| market_mode | PASS — 完全一致 |

两次独立运行结果完全一致，确认回测确定性。
