# REVIEW_CORRECTIONS.md

Generated: 2026-06-30T02:26:08.703069
Git HEAD: 151f337e4bd8112f29486b99c908196c8e2e6869

## 审查目的

修正 TASK-SCORPION-EMOTION-STRUCTURE-001 报告中互相矛盾或证据不足的结论，确认板块共振字段可靠性，并完成正式基线行为验证。

## 情绪状态结论修正

- 可形成结论：WEAK_REPAIR、ACCELERATION、RECESSION、EXTREME_PANIC（小样本）。
- 不可形成结论：ICE_POINT、ICE_REPAIR、HIGH_DIVERGENCE（样本<20）。
- WEAK_REPAIR 是收益增强状态，但 ACCELERATION、RECESSION、EXTREME_PANIC 仍具有正 EV，当前证据不支持情绪状态硬过滤或直接暂停交易。

## 板块共振结论修正

- 不再声称“板块共振具有显著解释力”。
- 板块涨停数量与候选股开盘至收盘代理收益存在弱正相关，但对 169 笔真实交易没有发现显著正向效果。
- 板块共振排序仅作为待验证结构实验，需满足字段审计 PASS、历史行业映射 PASS、多候选代理方向稳定、至少 3 个两年区间方向一致、效应非单一来源等条件。

## H4 真实交易分组（Bootstrap 2000 次，seed=42）

| test                                      |   high_n |   low_n |   high_ev |   low_ev |    diff |   ci_low |   ci_high |   pvalue | interpretation                |
|:------------------------------------------|---------:|--------:|----------:|---------:|--------:|---------:|----------:|---------:|:------------------------------|
| H4_real_trade_high_vs_low_sector_limit_up |       45 | 53.0000 |    0.0114 |   0.0215 | -0.0101 |  -0.0321 |    0.0123 |   0.3820 | 真实交易高/低板块涨停组EV差异 |


## H6 候选代理相关（Bootstrap 2000 次，seed=42）

| test                                                  |   high_n |   low_n |   high_ev |   low_ev |   diff |   ci_low |   ci_high |   pvalue | interpretation                              |
|:------------------------------------------------------|---------:|--------:|----------:|---------:|-------:|---------:|----------:|---------:|:--------------------------------------------|
| H6_candidate_proxy_sector_limit_up_vs_return_to_close |     5978 |     nan |    0.1008 |      nan | 0.1008 |   0.0748 |    0.1254 |   0.0000 | 多候选代理相关（candidate_return_to_close） |


说明：candidate_return_to_close 是开盘至收盘代理收益，不是天蝎正式交易 EV；大样本导致的小 p 值不等于强解释力。

## Sector 字段审计

| panel                 |   identical_rows |   total_rows |   identical_ratio |   dates_with_difference |   dates_total |   sectors_with_different_samples |   different_samples_by_sector_total |
|:----------------------|-----------------:|-------------:|------------------:|------------------------:|--------------:|---------------------------------:|------------------------------------:|
| trade_panel           |               79 |          136 |            0.5809 |                      55 |           127 |                               15 |                                  57 |
| multi_candidate_panel |             3049 |         5978 |            0.5100 |                     379 |           447 |                               31 |                                2929 |


人工抽样核对结果：见 SECTOR_COUNT_AUDIT.csv。

## 基线验证

- 默认命令保持快速 checkpoint 模式，防止误触发完整回测导致 CPU 满载。
- 正式完整基线仅由 `--baseline` 显式触发，结果见 FULL_BASELINE_VERIFICATION.json。

## 推荐实验修正

- 正式推荐：A 类 — 基于 T-1 情绪状态的仓位分级实验。
- 板块共振排序：暂不推荐实施，仅保留为待验证实验。
