# 策略拆解工作计划

目标：

在独立目录 `codex_strategy_dissection/` 中完成母版策略的信号、路由、门控、仓位和退出拆解，形成可复用归因表、切片统计和优化建议，并避免影响本地环境/聚宽对齐工作。

## 边界

- 只读来源：母版日志、已有研究 CSV、已有策略脚本。
- 写入范围：只写 `codex_strategy_dissection/`。
- 本工作台用于归因、裸分支回放准备和实验设计，不作为环境对齐验证器。

## 阶段状态

| 阶段 | 状态 | 主要产物 |
|---|---|---|
| 0. 工作台隔离 | 已完成 | `README.md`、`outputs/` |
| 1. 已结清交易归因 | 已完成 | `outputs/branch_state_attribution.csv` |
| 2. 日级状态快照 | 已完成 | `outputs/daily_state_snapshot.csv` |
| 3. 分支质量切片 | 已完成母版已成交口径 | `summary_by_*.csv`、`phase3_initial_findings.md` |
| 4. 路由/门控/冷却/仓位/退出归因 | 已完成日志层口径 | `phase4_*.md`、`candidate_conversion_*`、`route_opportunity_*`、`cooldown_*`、`sizing_*` |
| 5. 优化候选 | 第一版已完成 | `optimization_candidates.md`、`final_report.md` |
| 6. 裸分支回放 | 进行中 | `make_branch_strategy_copies.py`、`branch_strategies/`、`run_naked_branch_backtests.py` |

## 当前关键口径

- `final_report.md` 是母版已成交日志归因报告。
- 裸分支收益尚未完成，不能用母版已成交样本替代。
- 当前可靠裸分支证据只覆盖已有研究输出里的 `force_v227` 2020-2023。
- 新增的 `branch_strategies/` 每个 `force_*` 都是独立策略副本，文件内写死 `g.branch_test`，可人工核验。

## 当前 parser 运行

来源：

- `母版2020-2026日志.zip:log.txt`

解析区间：

- 2020-01-02 至 2026-05-28

解析数量：

- 买入：1323
- 已结清交易：1249
- 日状态：1549
- 日志末尾未结清：79
- 未匹配卖出：5

## 当前推荐实验顺序

1. 修正并完成强制单分支裸回放。
2. 回放 `bull_cooldown` 被挡窗口。
3. 回放非 bull 的 `rzq` 候选。
4. 比较 bull 下被挡 YJJ 和实际 `rzq+zb`。
5. 拆竞价 MA5 亏损。
6. 回放分支化 recent/core 胜率仓位。
7. 拆 scorpion 执行漏斗。
8. 最后再考虑参数或 slot 调整。

## 当前阻塞点

短窗口 `force_v227` 回放已经证明强制路由副本被读取：

- 策略副本：`branch_strategies/mother_branch_force_v227.py`
- 文件内：`g.branch_test = 'force_v227'`
- 回放 summary 记录了该策略路径。
- 日志显示：`活跃=force_v227`

但 2020-01 窗口产生 0 笔交易，原因是本地分支净化策略把 V227 候选过滤到 0，主要表现为 v130 尾封过滤。这和已有母版/本地日志不一致，因此下一步不是直接跑全区间，而是先对齐该分支副本的候选过滤口径。

## 报告语言

从本轮开始，归因报告和后续报告统一使用中文。
