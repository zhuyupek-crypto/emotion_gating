# Scorpion 本地回测性能优化报告

## 结论：PARTIAL

结果完全一致（Trades/EQUITY/STATE 零差异），但加速不足 2 倍。主要瓶颈在不可修改的数据源层 `hdata_reader.history()`。

---

## 测试区间

- **区间**：2025-01-01 至 2025-12-31（243 个交易日）
- **选择原因**：已有 before benchmark 产物覆盖该年；20 笔完整交易（≥10）；包含开仓和退出；未使用 2026
- **策略**：独立 Scorpion（strategy_v227_scorp.py，slots=2，market_gate=off）
- **Profile**：local_native_l2

## 耗时对比

| 指标 | 优化前 | 优化后 |
|------|--------|--------|
| 总耗时（秒） | 1825.774 | 1826.04 |
| 交易笔数 | 20 | 20 |
| 最终净值 | 1,109,839.15 | 1,109,839.15 |
| 最大回撤 | 4.99% | 4.99% |

**加速倍数**：0.9999x（无加速）

## 前三个性能瓶颈

基于 cProfile 对 2025 Q1（57 天）的分析（总耗时 595.65s）：

### 1. hdata_reader.history() — 363.87s（61%）
- 918 次调用，每次构建 DataFrame 时通过 `__setitem__` 逐字段填充
- 触发 843,727 次 `DataFrame.__setitem__`（累计 243.78s）和 841,972 次 `managers.iset`（tottime 50.84s）
- **不可修改**：数据源层代码，任务冻结条件禁止修改

### 2. _scan_boards_for_prev() — 302.22s（51%）
- 策略函数，57 次调用，内部调用 history/get_price 获取板块数据
- **不可修改**：策略代码，任务冻结条件禁止修改

### 3. _zb_prepare() — 172.29s（29%）
- 策略函数，17 次调用
- **不可修改**：策略代码

## 实际修改内容

仅修改 `rebuild_from_archive/engine/data_api.py`，减少冗余 `.copy()` 调用：

### 1. _history_cached() — 缓存存储路径
- **修改前**：缓存未命中时执行 2 次 `.copy()`（存储时复制 + 返回时复制）
- **修改后**：存储原始对象（新对象无外部引用），仅在返回时复制保护缓存 → 1 次 `.copy()`
- 影响：918 次缓存未命中，每次节省 1 次大 DataFrame 复制

### 2. get_all_securities() — 缓存命中返回路径
- **修改前**：缓存命中时执行 2 次 `.copy()`（`cached.copy()` + `return out.copy()`）
- **修改后**：`cached.copy()` 已创建防御性副本，`return out` 无需再复制 → 1 次 `.copy()`
- 影响：~131 次缓存命中，每次节省 1 次 5000+ 行 DataFrame 复制

### 未修改策略逻辑确认
- 策略参数：未修改 ✓
- 事件执行顺序：未修改 ✓
- 订单排序：未修改 ✓
- 成交价格口径：未修改 ✓
- 涨跌停/停牌判断：未修改 ✓
- 日期和时间口径：未修改 ✓
- 交易日未跳过 ✓
- 未使用近似计算 ✓

## 一致性检查结果

| 检查项 | 结果 |
|--------|------|
| Trades 差异 | 0（20 行 vs 20 行，逐列完全一致） |
| Equity 最大误差 | 0.0（243 行 vs 243 行，所有数值列差异为 0） |
| State 差异 | 0（date/positions/available_cash/positions_count 完全一致） |
| 最终净值 | 完全一致（1,109,839.15） |
| 最大回撤 | 完全一致（4.99%） |

## 尚未解决的主要瓶颈

**hdata_reader.history() 占总耗时 61%，是唯一需要优化的重大瓶颈，但无法在本任务范围内修改。**

该函数通过以下方式构建 DataFrame：
1. 创建 `pd.DataFrame(np.nan, index=target_dates, columns=hd_codes)` 全 NaN 空表
2. 逐字段 `df[field][stock_codes] = values` 填充（触发 843K 次 `__setitem__`）
3. 每次调用涉及大量 pandas 内部管理器操作（`iset`、`_iset_split_block`、`delete`）

可能的优化方向（超出本任务范围）：
- 在 hdata_reader 中使用 `pd.concat` 或 numpy 数组直接构建 DataFrame，避免逐字段 `__setitem__`
- 预构建 pivot 缓存（`_PIVOT_CACHE` 已存在但未覆盖所有查询路径）
- 批量加载并按日期索引，减少重复筛选

## 是否建议开始 2018—2025 全期基线

**暂不建议。**

当前 2025 全年耗时约 30 分钟。2018—2025 共 8 年，预计耗时 4 小时以上。在 hdata_reader 瓶颈解决前，全期基线耗时不支持快速迭代。建议先优化数据源层，再启动全期基线。
