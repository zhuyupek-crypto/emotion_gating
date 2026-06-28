# Motherboard Shared Backtest Performance Optimization
**Task**: TASK-MOTHERBOARD-PERFORMANCE-001
**Branch**: `codex/motherboard-performance-v1`
**Baseline commit**: `e61c75b1ddb32f30ed20462f4059144122914b65`
**Strategy**: `母版-20260506-Clone.py` (full motherboard, profile `local_native_l2`)

## 基准年份和快速区间

- 基准年度: **2025** (分支覆盖最丰富: v227=130天, rzq+zb=113天, 531笔交易)
- 快速区间: **2025-03-01 至 2025-05-31** (61交易日, v227=40天, rzq+zb=21天, 86笔交易, 含3种market_mode切换)

## 优化前耗时

| 区间 | 耗时(秒) | history调用 | 交易数 | 最终净值 | 最大回撤 |
|------|---------|------------|--------|----------|---------|
| 快速区间 | 1157.291 | 3238 | 92 | 1291597.37 | 6.8527% |
| 全年 | 5328.463 | 15137 | 531 | 2513109.47 | 24.3692% |

## 优化后耗时

| 区间 | 耗时(秒) | history调用 | 交易数 | 最终净值 | 最大回撤 | 加速倍数 |
|------|---------|------------|--------|----------|---------|---------|
| 快速区间 | 261.217 | 3238 | 92 | 1291597.37 | 6.8527% | 4.43x |
| 全年 | 975.787 | 15137 | 531 | 2513109.47 | 24.3692% | 5.461x |

## 加速倍数

- 快速区间: **4.43x**
- 全年: **5.461x** (≥1.5x 阈值)

## 主要瓶颈

`hdata_reader.history()` 是主要瓶颈, 占运行时间约80%.

根因: `history()` 通过 `pd.DataFrame(np.nan, ...)` 创建结果, 然后用 `df[stock_codes] = sub_df.values[:, indexer]`, `df.loc[:, c] = ...`, `df[c] = ...` 等 `DataFrame.__setitem__` 操作逐列填充. 一次回测触发 1.6M+ 次内部 `iset` / `_iset_split_block` / `delete` 调用, 是 pandas DataFrame 列存块管理的开销.

cProfile 关键数据 (快速区间, 21天 profile):
- `hdata_reader.history`: 累计耗时最高 (约 80%)
- `DataFrame.__setitem__` 系列: 1.6M+ 调用
- `_iset_split_block` / `iset` / `delete`: 内部块管理热点

## 实际修改

### 1. `hdata_reader.history()` 结果构造改用 numpy 数组一次成型

**文件**: `D:\\work space\\hdata\\scripts\\core\\hdata_reader.py`

**位置**: `history()` 函数内构造 `sliced_dfs` 的循环 (原 ~883-942 行)

**修改前**: 对每个字段 `f`, 先 `pd.DataFrame(np.nan, index=target_dates, columns=hd_codes)`, 然后用三次 `__setitem__` 分别填 Stocks / Indices / ETFs:
```python
df_field = pd.DataFrame(np.nan, index=target_dates, columns=hd_codes)
if stock_codes:
    df_field[stock_codes] = sub_df.values[:, indexer]
for c in index_codes:
    df_field.loc[:, c] = ...
for c in etf_codes:
    df_field[c] = ...
```

**修改后**: 先用 `np.full()` 创建 float64 数组, 通过整数列位置一次写入所有数据, 最后只构造一次 DataFrame:
```python
col_idx_map = {c: i for i, c in enumerate(hd_codes)}
for f in all_fields_to_load:
    arr = np.full((len(target_dates), len(hd_codes)), np.nan, dtype=np.float64)
    # Stocks: arr[:, stock_col_positions] = sub_df.values[:, indexer]
    # Indices: arr[:, ci] = df_idx[h_col].reindex(target_dates).values
    # ETFs: arr[:, etf_col_positions] = etf_reindexed.values
    df_field = pd.DataFrame(arr, index=target_dates, columns=hd_codes)
```

### 2. ETF 数据改为 pivot 一次成型

原代码对 ETF 逐代码 `reindex` 后逐列 `__setitem__`; 修改后用 `etf_df_all.pivot(index='date_int', columns='code', values=h_col)` 一次构造宽表, 再 `reindex(index=target_dates, columns=etf_codes)` 对齐, 一次写入 numpy 数组.

### 修改范围声明

- 仅修改 `hdata_reader.history()` 内部结果构造逻辑
- 未修改任何策略源码、分支开关、active 路由、market_mode 计算、候选筛选、买卖条件、仓位/Slots、事件调度、撮合规则、成交价格、手续费、停牌/涨跌停判断、数据内容
- 未跳过任何交易日, 未使用近似计算, 未屏蔽任何分支, 未加入并行执行

## 一致性结果

### 快速区间 (2025-03-01 至 2025-05-31)

- 状态: **PASS**
- Trades 差异: 0
- Equity 最大差异: 0.0
- Positions 差异: 0
- Portfolio 差异: 0
- 路由差异: 0

### 全年 (2025-01-01 至 2025-12-31)

- 状态: **PASS**
- Trades 差异: 0 (before=531, after=531)
- Orders 差异: 通过 trade_id/order_id 列隐含在 Trades 校验中 (本基准保存 TRADES, 含 order_id 列)
- Equity 最大差异: 0.0
- Positions 差异: 0
- Portfolio 差异: 0
- 路由差异: 0
- 候选状态差异: 已包含在 STATE 路由字段校验 (cand_yjj / cand_bear / cand_rzq / cand_zb / cand_auction) 中

## 剩余瓶颈

1. `hdata_reader.history()` 本身仍是累计耗时最高的函数, 但内部瓶颈已从 `__setitem__` 转为实际 parquet 读取与 `_PIVOT_CACHE` 加载. 进一步提速需在数据源层做按日期/股票预建索引或内存常驻.
2. 策略内部扫描 (`_scan_boards_for_prev`, `_rzq_prepare`, `_zb_prepare`, `auction_prepare`) 是策略逻辑, 本任务不修改.
3. `DataAPI._history_cached()` 的 DataFrame copy 可考虑后续优化, 但收益小于本次 history() 重构.

## 是否可以冻结为公共性能版本

**可以** 冻结为公共性能版本.

判定依据:
- 完整母版结果一致: True
- 母版路由一致: True
- 候选状态一致: True
- 全年速度提升 ≥1.5x: True (5.461x)

## 交付物

- `BEFORE.json` — 优化前基准 (快速区间 + 全年)
- `AFTER.json` — 优化后基准 (含加速倍数)
- `PARITY.json` — 全年一致性校验
- `REPORT.md` — 本报告
- `hdata_reader_performance.patch` — 标准 unified diff 补丁 (可应用到 baseline hdata_reader.py)
- `HDATA_READER_VERSION.json` — 文件身份记录 (baseline/optimized/patch SHA256)
- `tools/apply_hdata_reader_performance_patch.py` — 极简应用与校验脚本
- 公共代码修改: `hdata_reader.py` 中 `history()` 函数结果构造逻辑 (外部 HDATA 目录, 通过 patch 固化)

## 外部代码版本固化

实际性能代码位于外部 HDATA 目录 (`D:\work space\hdata`), 该目录不是 git 仓库. 仓库通过以下方式对该修改进行版本固化:

1. **标准 patch**: `hdata_reader_performance.patch` 是标准 unified diff, 可直接应用到优化前 `hdata_reader.py` (通过 `git apply --no-index -p1` 或 `patch -p1`).
2. **基线 SHA**: `HDATA_READER_VERSION.json` 记录 `baseline_sha256` = `33050a95d18b0e48ead37bcc0b710cc4b14527b396f83710570849c68cf28818`
3. **优化后 SHA**: `HDATA_READER_VERSION.json` 记录 `optimized_sha256` = `bbd4671ea342fcf206dfec5f4ada6da85dbcaf3df3a5bb7c3b1b1010f6d9e361`
4. **patch SHA**: `HDATA_READER_VERSION.json` 记录 `patch_sha256` = `cce3ad31adbcec324a1178d41ed8de5f3c9d1a497c5c568085346512b343dcd5`
5. **应用工具**: `tools/apply_hdata_reader_performance_patch.py` 提供安全的 apply/check 流程:
   - 定位 HDATA 根目录 (`$LOCALQUANT_HDATA_ROOT` 或默认 `D:\work space\hdata`)
   - 校验当前 `hdata_reader.py` SHA256
   - 已是 optimized: 报告 already applied, 正常退出
   - 是 baseline: 应用 patch, 然后重新校验 SHA256 必须等于 optimized
   - 既不是 baseline 也不是 optimized: 拒绝修改并报告冲突
   - `--check` 模式只校验不修改

**重要**: 母版性能标签同时依赖 `emotion_gating` commit 和 optimized `hdata_reader` SHA256. 仅有仓库 commit 不够, 还需确认外部 HDATA 文件的 SHA256 匹配 `bbd4671ea342fcf206dfec5f4ada6da85dbcaf3df3a5bb7c3b1b1010f6d9e361`. 校验命令:

```bash
python tools/apply_hdata_reader_performance_patch.py --check
```
