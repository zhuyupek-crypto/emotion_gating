# 策略拆解工作台

这个目录是独立的策略归因和分支拆解工作台。

边界：

- 读取已有母版日志和研究输出。
- 只在本目录下写派生分析文件。
- 不修改母版策略、本地回测引擎、聚宽对齐脚本和已有对比 CSV。

当前主要来源：

- `../母版2020-2026日志.zip`

核心产物：

- `outputs/branch_state_attribution.csv`: closed-trade attribution parsed from
  母版日志解析出的一笔已结清交易一行归因表。
- `outputs/daily_state_snapshot.csv`: 从 `[STATE]` 解析出的日级状态快照。
- `outputs/summary_by_*.csv`: 分支、年份、模式、退出等切片统计。
- `outputs/run_summary.md`: 运行摘要。
- `work_plan.md`: 本工作台的阶段计划和当前进展。
- `phase3_initial_findings.md`、`phase4_route_gate_findings.md`、
  `phase4_cooldown_findings.md`、`phase4_sizing_findings.md`、
  `phase4_exit_findings.md`: 阶段性解释笔记。
- `optimization_candidates.md`: 优化候选和实验队列。
- `final_report.md`: 信号、路由、门控、仓位、退出的中文汇总报告。
- `make_branch_strategy_copies.py`: 在本目录生成可人工核验的单分支策略副本。
- `branch_strategies/`: 每个 `force_*` 模式一份独立策略副本，文件内写死
  `g.branch_test`。
- `naked_branch_backtest_protocol.md`: 单分支裸回放协议。
- `run_naked_branch_backtests.py`: 读取 `branch_strategies/` 中的策略副本并把
  回放结果写到 `branch_runs/`。
- `naked_branch_backtest_findings.md`: 裸分支证据状态和纠偏说明。

本工作台把当前母版日志视为分析来源，不把它当作环境对齐验证器。环境和聚宽对齐工作继续保持独立。
