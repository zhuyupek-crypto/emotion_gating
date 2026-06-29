# STRUCTURAL_EXPERIMENT_RECOMMENDATION.md

Generated: 2026-06-30T02:26:08.468877

## Executive summary

Total matched Scorpion trades: 169.  Overall mean return: 0.0208; overall win rate: 65.68%; total gross contribution: 3.5080.

## Primary structural experiment (only one recommended)

**基于T-1情绪状态的仓位分级实验**

- Category: A - 情绪门控/仓位分级
- Rationale: WEAK_REPAIR 是表现最强且跨周期方向一致的阶段（EV 3.35%，45笔），但 ACCELERATION、RECESSION 和 EXTREME_PANIC 仍具有正 EV，因此当前证据不支持情绪状态硬过滤或直接暂停交易。建议先验证在 WEAK_REPAIR 维持标准仓位、其余状态降低仓位的分级方案。
- Causal features used (all T-1 close or T 09:30):
  - `T1_emotion_state_v2`, `T1_emotion_heat`, `T1_emotion_momentum`, `T1_emotion_stress`
- Proposed implementation:
  - Do **not** modify `strategy_v227_scorp.py`.
  - Implement the experiment as a post-selection layer or wrapper around the existing entry signal.
  - Re-run the full 2018-2025 baseline after each variant to confirm 169 trades unchanged.

## Sector resonance sorting (currently unverified)

板块涨停数量与候选股开盘至收盘代理收益存在弱正相关，但对 169 笔真实交易没有发现显著正向效果。
推荐仅作为后续待验证实验，需同时满足：

1. 板块字段审计 PASS（SECTOR_COUNT_AUDIT.csv）
2. 历史行业映射 PASS
3. 多候选代理相关方向稳定且至少 3 个两年区间方向一致
4. 效应不是由单一时期或单一行业贡献

在未通过上述检查前，不得声称板块共振已被证明有效。

## Experiments deliberately not recommended as primary

- Adjusting the low-open interval, 60-day position threshold, or stop-loss percentage.
- Changing moving-average periods or sell timing.
- Adding Slots purely based on historical best performance.
- Using same-day close data or future concept-sector membership.
- Hard filtering by emotion state based on small-sample states (ICE_POINT, ICE_REPAIR, HIGH_DIVERGENCE).

## Next steps after the primary experiment

1. If state-contingent sizing works, test a composite multi-candidate ranking score.
2. If ranking works, test confirmation-style entry timing.
3. Freeze the successful structural variant as a new baseline before any parameter tuning.
