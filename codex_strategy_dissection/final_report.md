# 策略拆解总报告

来源：

- `../母版2020-2026日志.zip:log.txt`

解析区间：

- 2020-01-02 至 2026-05-28

样本：

- 买入记录：1323
- 已结清交易：1249
- 日状态快照：1549
- 日志末尾仍未结清：79
- 未匹配卖出：5

边界：

所有新增和派生文件都在 `codex_strategy_dissection/` 下。本工作没有修改母版策略、本地引擎、hdata 或聚宽对齐文件。

重要口径修正：

本报告是“母版已成交日志归因”，不是“关掉门控后的裸分支回放”。裸分支回放进度单独记录在
`naked_branch_backtest_findings.md`。

## 可复用表

核心表：

- `outputs/branch_state_attribution.csv`：每笔已结清交易一行，包含买入时状态、分支、路由、冷却、胜率状态、候选信息、退出标签和收益。
- `outputs/daily_state_snapshot.csv`：每日一行，包含市场模式、active 路由、FB 状态、冷却、分支开关、仓位槽和候选数量。

派生切片：

- `outputs/summary_by_branch.csv`
- `outputs/summary_by_branch_market_mode.csv`
- `outputs/summary_by_branch_fb_pct_bucket.csv`
- `outputs/summary_by_branch_buy_signal_bucket.csv`
- `outputs/summary_by_branch_candidate_rank_bucket.csv`
- `outputs/summary_by_branch_exit_label.csv`
- `outputs/candidate_conversion_*.csv`
- `outputs/route_opportunity_*.csv`
- `outputs/cooldown_attribution_*.csv`
- `outputs/sizing_*.csv`

## 已成交分支质量

| 分支 | 已结清 | 胜率 | 平均收益 | 中位收益 | 盈亏比 |
|---|---:|---:|---:|---:|---:|
| `rzq` | 145 | 54.48% | 2.90% | 1.60% | 2.17 |
| `v227_scorpion` | 109 | 66.97% | 2.63% | 2.00% | 3.24 |
| `auction_rzq` | 58 | 62.07% | 2.45% | 1.30% | 2.01 |
| `auction_y2` | 238 | 64.71% | 1.88% | 1.60% | 1.86 |
| `zb` | 366 | 62.84% | 1.55% | 1.20% | 1.76 |
| `v227_yjj` | 328 | 52.13% | 1.03% | 0.35% | 1.44 |

解读：

- `v227_scorpion` 是已成交样本里最干净的 alpha：胜率、中位数、盈亏比都强，左尾也相对温和。
- `rzq` 平均收益最高，但状态敏感性更强。
- `v227_yjj` 是右尾驱动，平均数明显好于中位数，不能只看均值。

裸分支提醒：

- 上表只代表母版允许成交后的表现。
- 目前可靠的裸分支证据只覆盖已有研究输出里的 `force_v227` 2020-2023。

## 路由和门控

最大机会成本问题：

- `rzq` 非 bull 被挡：720 个候选日、1741 个候选被路由挡掉。
- bull 下 YJJ 被 `rzq+zb` 路由替代：392 个候选日、1906 个候选被挡。
- `v227_scorpion` 没有路由饥饿问题，瓶颈在执行漏斗，而不是 active 资格。

解读：

- RZQ 非 bull 禁用是一个很大的路由决策，必须回放。
- bull 下 YJJ 和 `rzq+zb` 是路线竞争，不是单纯调 YJJ 参数。
- 调其他分支时不要误伤 scorpion。

## 冷却

主要冷却机会成本：

- `bull_cooldown`：70 天，覆盖 RZQ、ZB、YJJ 的大量候选。
- `v227_shock_cooldown`：16 天，主要压制少量 YJJ 机会。
- `rzq_cooldown`：7 天，样本较少。
- `stoploss_cooldown`：本日志中解析到 0 个活跃日。

解读：

- `bull_cooldown` 是第一个值得回放验证的冷却。
- `v227_shock_cooldown` 当前看成本较低，先保留，等回放再判断。

## 仓位和胜率状态

`recent_wr` / `core_wr` 不是单调的全局加仓信号。

关键切片：

- `recent_wr 50-55%`：282 笔，胜率 67.73%，平均 2.29%，中位 1.60%，盈亏比 2.35。
- `recent_wr >=65%`：243 笔，胜率 53.09%，平均 1.19%，中位 0.50%，盈亏比 1.48。
- `v227_yjj` 在 `recent_wr >=65%`：50 笔，平均 -0.90%，中位 -1.75%。
- `rzq` 在 `core_wr >=65%`：20 笔，平均 6.12%，中位 3.85%。

解读：

- 不要把高近期胜率当作全局加仓理由。
- 胜率状态更像分支健康信号，而不是组合健康信号。
- 日志里的 slot 状态缺少分支内变化，不能单靠已成交归因判断扩仓或缩仓。

## 退出

强退出：

- `竞价卖-线性回落`：43 笔，平均 8.71%。
- `rzq卖`：93 笔，平均 7.38%。
- `竞价卖-落袋`：133 笔，平均 5.66%。
- `v227止盈`：248 笔，平均 5.57%。

主要亏损退出：

- `v227止损`：50 笔，平均 -7.57%。
- `竞价卖-MA5`：101 笔，平均 -6.43%。
- `rzq止损`：49 笔，平均 -5.77%。
- `v227午撤`：95 笔，平均 -4.53%。

解读：

- 退出标签是结果，不是买入前可用特征。
- 真正可行动的退出优化，必须回连到买入时或盘中可获得的信息。

## 当前实验顺序

1. 先完成强制单分支裸回放。
2. 回放 `bull_cooldown` 被挡窗口。
3. 回放非 bull 的 `rzq` 候选。
4. 比较 bull 下被挡 YJJ 和实际 `rzq+zb`。
5. 拆 `auction` 的 MA5 亏损。
6. 回放分支化的 `recent_wr/core_wr` 仓位规则。
7. 拆 scorpion 执行漏斗。
8. 最后再考虑参数和 slot 调整。

## 还不能证明的事

当前工作证明了日志层归因，并指出了回放目标；它不能证明被挡候选或未成交候选的反事实收益。

下一层必须先做强制单分支回放，而不是直接优化混合母版。
