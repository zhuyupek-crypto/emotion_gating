# 裸分支回放状态说明

状态：

未完成。这里专门纠正前面的口径：母版已成交日志归因，不等于裸分支收益。

## 已完成的是什么

前面的产物完成的是母版日志归因：

- 已成交交易收益
- 日级状态快照
- 路由机会计数
- 冷却机会计数
- 仓位状态切片
- 退出标签切片

这些都很有用，但它们都以“母版允许成交”为前提。

## 裸分支需要什么

每个分支都需要单独回放，让它能交易母版原本会挡掉的机会。

最低需要：

- `force_v227`
- `force_rzq`
- `force_zb`
- `force_rzq_zb`
- `force_auction`

更严格的裸信号层，还要继续关闭分支内部的 `market_mode`、`fb_pct`、冷却和动态仓位。

## 当前可靠证据

项目里已有可靠证据目前只覆盖 `force_v227` 的 2020-2023：

- `../research_train_2020_2023_force_v227_summary.md`
- `../research_train_2020_2023_force_v227_yearly.csv`
- `../research_train_2020_2023_force_v227_by_branch.csv`

关键结果：

| 范围 | 卖出数 | 胜率 | 平均交易 | 中位交易 | 最好 | 最差 |
|---|---:|---:|---:|---:|---:|---:|
| `force_v227`，2020-2023 年度重置 | 432 | 51.16% | 0.39% | 0.25% | 46.70% | -24.29% |
| `force_v227` 内的 YJJ | 365 | 48.22% | 0.06% | -0.73% | 46.70% | -24.29% |
| `force_v227` 内的 scorpion | 67 | 67.16% | 2.18% | 1.90% | 21.25% | -10.28% |

年度结果：

| 年份 | 收益 | 最大回撤 | 卖出数 | 胜率 | 平均交易 | 中位交易 |
|---|---:|---:|---:|---:|---:|---:|
| 2020 | -19.67% | -40.25% | 97 | 44.33% | -0.13% | -1.28% |
| 2021 | 90.50% | -17.08% | 143 | 52.45% | 1.10% | 0.50% |
| 2022 | 23.24% | -22.49% | 121 | 52.07% | 0.59% | 0.63% |
| 2023 | -25.20% | -32.42% | 71 | 56.34% | -0.67% | 0.89% |

解读：

- scorpion 在强制 V227 里仍然是最干净的子 alpha。
- YJJ 裸看偏弱：平均接近 0，中位数为负，并且有明显坏年份。
- `force_v227` 整体不能盲目扩张，需要先做分支内过滤。

## 本地 runner 状态

已新增：

- `make_branch_strategy_copies.py`
- `branch_strategies/mother_branch_force_*.py`
- `run_naked_branch_backtests.py`
- `naked_branch_backtest_protocol.md`

现在不再只做内存替换，而是在 `branch_strategies/` 下生成独立策略副本。每个副本里都可以直接确认：

- `mother_branch_force_v227.py` 写死 `g.branch_test = 'force_v227'`
- `mother_branch_force_rzq.py` 写死 `g.branch_test = 'force_rzq'`
- `mother_branch_force_auction.py` 写死 `g.branch_test = 'force_auction'`

短窗口冒烟：

- 命令：`python codex_strategy_dissection\run_naked_branch_backtests.py --start 2020-01-01 --end 2020-01-31 --modes force_v227`
- 输出：`branch_runs/naked_branch_summary.csv`
- 结果：runner 可以执行，但该窗口产生 0 笔交易。

诊断：

- 强制路由生效，日志显示 `活跃=force_v227`。
- 但本地分支净化策略在 2020 年 1 月把 V227 候选过滤到 0，主要发生在 v130 尾封过滤。
- 这和同窗口已有母版/本地日志不一致，因此当前 runner 不能直接当裸收益证据。

## 下一步

1. 先让 `branch_strategies/` 中的分支副本与当前本地引擎/数据口径对齐。
2. 只有当它能复现已知 `force_v227` 或母版样本后，才跑完整分支。
3. 完整生成 2020-2026：
   `force_v227`、`force_rzq`、`force_zb`、`force_rzq_zb`、`force_auction`。
4. 再做更纯的裸信号层，关闭分支内部门控。

在此之前，只有已有的 `force_v227` 2020-2023 研究基线可以被当作裸分支证据。
