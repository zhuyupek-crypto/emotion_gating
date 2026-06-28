# Scorpion Purity Audit v1 — Non-bear Trade Source Analysis

**Task**: TASK-SCORPION-PURITY-AUDIT-001
**Base commit**: `7708e2e5`
**Strategy SHA256 (before fix)**: `55e96b2225d14c6d94052ff3dad03079094b3f7a66b46c76e6b6409d7618c2b0`
**Strategy SHA256 (after fix)**: `d34af30fd8805300403df6af7e5943aba4acb01f429018c1ac0c60cd79307fda`
**hdata_reader SHA256**: `bbd4671ea342fcf206dfec5f4ada6da85dbcaf3df3a5bb7c3b1b1010f6d9e361`

## Root Cause Analysis

`_scan_boards_for_prev()` has two data paths:

1. **board_snapshot path** (line 531): `if bear_pool and g.market_mode == 'bear':`
   - Has market_mode check → only populates bear_candidates in bear mode
2. **history_fallback path** (line 576): `if bear_pool:`
   - **Missing market_mode check** → populates bear_candidates in ALL modes (bug)

### Critical Finding: board_snapshot path NEVER executes

When Scorpion runs without compat profile (compat=None), `data_api.get_project_board_snapshot()`
returns an empty DataFrame (verified by direct test). This means:

- The board_snapshot path's `if board_df is not None and not board_df.empty:` check (line 512)
  always evaluates to False
- **ALL** trades come from the history_fallback path (line 576)
- The missing `g.market_mode == 'bear'` check in history_fallback is the **sole cause** of
  the 62 non-bear trades

## Trade Source Summary

| market_mode | candidate_source | count |
|-------------|------------------|-------|
| bear | history_fallback | 169 |
| bull | history_fallback | 28 |
| cautious | history_fallback | 34 |

**Total**: 231 trades | **Bear**: 169 | **Non-bear**: 62

## Answers to Audit Questions

1. **62笔非 bear 交易是否全部来自 history_fallback**: 是 (history_fallback=62, board_snapshot=0)
2. **非 bear 模式下 board_snapshot 路径是否始终为0笔**: 是 (board_snapshot 路径在 compat=None 时从不执行)
3. **history_fallback 缺少 market_mode 判断是否为唯一原因**: 是 (board_snapshot 路径有检查但因 compat=None 从不执行)
4. **bear 模式下交易来源**: 全部来自 history_fallback (board_snapshot 路径不执行)

## Minimal Fix (Formally Applied)

```python
# history_fallback path (line 576)
# Before:
if bear_pool:
# After:
if bear_pool and g.market_mode == 'bear':
```

Only this single condition was modified. No other strategy logic, parameters,
exit rules, stops, costs, or sorting were touched.

## Before/After Comparison

| Metric | Before (no fix) | After (minimal fix) |
|--------|-----------------|---------------------|
| completed_trades | 231 | 169 |
| total_return | 274.3372% | 365.3283% |
| annualized_return | 17.9391% | 21.1909% |
| max_drawdown | 13.2913% | 13.2933% |
| win_rate | 59.7403% | 65.6805% |
| EV | 1.3884% | 2.0757% |
| final_value | 3743371.56 | 4653282.83 |

### Yearly Comparison

| Year | Before Trades | After Trades | Before EV | After EV |
|------|---------------|--------------|-----------|----------|
| 2018 | 35 | 31 | 1.0579% | 1.2950% |
| 2019 | 35 | 31 | 2.2504% | 2.3874% |
| 2020 | 36 | 18 | 0.8601% | 1.5018% |
| 2021 | 30 | 15 | 1.2377% | 2.7500% |
| 2022 | 39 | 35 | 0.8100% | 1.1665% |
| 2023 | 14 | 11 | 1.5130% | 2.3076% |
| 2024 | 29 | 23 | 2.1618% | 3.4444% |
| 2025 | 13 | 5 | 1.6435% | 4.5860% |

After the fix, every year's EV improves — confirming non-bear trades were a net drag.

## Bear Parity Check (169 bear trades)

### Verdict: PASS

```text
审计结论：PASS
逻辑选择一致性：PASS
组合份额一致性：不适用
```

删除62笔非bear交易会改变现金和复利路径，因此后续shares变化属于预期组合状态效应，
不属于信号或交易逻辑差异。

### Field-by-field parity

| Field | Parity | 备注 |
|-------|--------|------|
| code (股票代码) | ✅ identical | 信号选择一致 |
| entry_date (买入时间) | ✅ identical | 执行一致 |
| buy_price (买入价格) | ✅ identical | 执行一致 |
| exit_date (卖出时间) | ✅ identical | 退出一致 |
| sell_price (卖出价格) | ✅ identical | 退出一致 |
| shares (数量) | 不适用 | 组合状态差异 |

### Root Cause of shares Difference — Cash Flow Effect (Expected)

The shares difference is an **expected and unavoidable consequence** of the fix:

1. The fix removes 62 non-bear trades (28 bull + 34 cautious)
2. These trades previously consumed capital (~negative EV: bull=-0.27%, cautious=-0.66%)
3. Removing them frees up cash that compounds over the 8-year backtest
4. Bear trades now have **more available cash** → larger position sizes per slot

**Evidence**:
- Rows 0-4 (first 5 bear trades): **identical shares** — no non-bear trades happened yet
- Rows 5-30: after_fix shares are consistently **larger** (e.g., 26800 vs 27300)
- Rows 93-168: differences compound significantly over the 8-year backtest

This is a **portfolio-state effect**, not a signal or logic change:
- Bear trade SELECTION is identical (same stocks, same dates, same prices)
- Only position SIZE differs (strategy sizes by available cash / slot value)
- The fix does not alter any sizing formula, slot count, or bear-mode candidate generation

## Defensive Buy Guard Check

- Status: **PASS**
- Applied `if g.market_mode != 'bear': return` at `buy_v227_天蝎座()` entry (in-memory only)
- Result: **IDENTICAL** to candidate fix
  - candidate: 338 execution_rows, final=4,653,282.83
  - buy_guard: 338 execution_rows, final=4,653,282.83
- **Not retained** in final code — only the candidate fix is kept to avoid duplicate logic

## Overall Conclusion

### Audit Objectives — all met

| Objective | Status |
|-----------|--------|
| 62笔非bear交易来源被完整解释 | ✅ PASS — all from history_fallback |
| 最小修复后非bear交易为0 | ✅ PASS — 169 trades, all bear |
| 没有修改其他策略条件 | ✅ PASS — only `if bear_pool:` → `if bear_pool and g.market_mode == 'bear':` |
| 169笔bear交易逻辑选择一致 | ✅ PASS — code/dates/prices identical |
| 防御性买入检查与候选修复一致 | ✅ PASS — identical results |

### Verdict

**审计结论：PASS**

- Root cause identified and confirmed
- Fix eliminates non-bear trades without altering bear trade selection logic
- shares差异属于预期组合状态效应（资金释放+复利路径改变），不属于信号或交易逻辑差异
