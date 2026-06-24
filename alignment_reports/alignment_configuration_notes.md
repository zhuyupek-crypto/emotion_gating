# 对齐相关配置项说明

更新时间：2026-06-24

本文说明本次 JoinQuant 母版对齐工作里最重要的配置项、兼容开关和运行边界，方便后续在远端仓库中快速理解“哪些是工程能力，哪些是母版复刻例外”。

## 1. 原则

所有配置项都遵循同一个原则：

- 原始 `hdata` 不改
- 原始 `local_quant` 不改
- 项目特定的母版复刻行为，尽量集中在工作区 compat 层
- 通用引擎只提供“可注入、可回退、可选启用”的能力

## 2. `project_compat.py`

核心文件：

- [project_compat.py](D:\Work Space\他山之石\情绪门控\rebuild_from_archive\project_compat.py)

这是整个对齐工程最重要的项目级配置入口，主要承载以下几类配置。

### 2.1 `non_st_name_windows`

作用：

- 复刻 JoinQuant `get_all_securities(date=...)` 在特定日期的名称 / ST 展示口径

使用场景：

- 本地干净 ST 历史与母版当时可买口径不一致
- 未来 ST / 退市名称从静态元数据提前泄漏

特点：

- 只做窄窗口修复
- 只在有母版交易或 JQ 探针证据时增加

### 2.2 `minute_price_anomalies`

作用：

- 修正极少数分钟级价格点，用于复刻母版卖点 / 触发边界

使用场景：

- 一分钱差异或分钟快照差异导致卖点提前/延后

特点：

- 日期 + 时间 + 代码级精确修复
- 不做全局分钟价替换

### 2.3 `daily_price_anomalies`

作用：

- 修正极少数日线字段，例如 `high_limit`、`high`

使用场景：

- 母版严格依赖 `high == high_limit`
- 本地 float 尾差或平台口径差异导致候选被误过滤

特点：

- 日期 + 代码 + 字段级精确修复
- 不做全局 epsilon 容差

### 2.4 `execution_price_anomalies`

作用：

- 复刻 JoinQuant 在极少数买点的实际成交价

使用场景：

- `MarketOrderStyle(day_open)` 在母版中的成交价与本地推断值不同
- 一分钱差异会改变第二天止盈止损边界

特点：

- 只修精确的日期 + 时间 + 代码 + 买卖方向
- 不推广成通用撮合规则

### 2.5 `tail_seal_anomalies`

作用：

- 修正首板/尾板时间

使用场景：

- v130 / v122 / 一进二等路径对封板时间高度敏感

特点：

- 只修确认证据闭环的单点

### 2.6 `corrupted_daily_limit_windows`

作用：

- 标记某些时间窗内的日线快路径数据不能信任

当前已知窗口：

- `2026-05-25` 到 `2026-06-12`

用途：

- 通知引擎不要继续使用 fast path
- 强制回退到更慢但正确的通用 `get_price` 路径

### 2.7 `should_bypass_history_fastpath(...)`

作用：

- 给引擎层一个统一查询接口，判断当前字段/窗口是否必须绕过快路径

意义：

- 把“数据污染窗口”的判断留在项目 compat
- 通用引擎只负责执行回退，不负责理解母版项目特例

## 3. 引擎层配置能力

核心文件：

- [core.py](D:\Work Space\他山之石\情绪门控\rebuild_from_archive\engine\core.py)
- [data_api.py](D:\Work Space\他山之石\情绪门控\rebuild_from_archive\engine\data_api.py)

这些文件不直接存放项目特定例外，而是提供下面几类能力。

### 3.1 `_get_daily_snapshot_fast(fields)`

作用：

- 使用更快的方式批量获得日线快照字段

优点：

- 对大年份回放提速非常明显

风险：

- 一旦底层快照窗口污染，会把错误放大成整段分叉

当前处理方式：

- 默认可用
- compat 可要求按窗口回退

### 3.2 `get_price(... panel=False)` 回退路径

作用：

- 在 compat 认为 fast path 不可靠时，提供慢但正确的兜底路径

关键点：

- 这是“正确性兜底”
- 不是“常态替代”

### 3.3 `get_batch_sealing_points()`

当前含义：

- 不再无条件依赖旧的 `_history_cached(...)` 结果
- 会转入可受 compat 控制的 `get_price` 路径

意义：

- 减少封板时间在污染窗口里被快路径误读的风险

## 4. 预处理与缓存配置

核心文件：

- [project_preprocess.py](D:\Work Space\他山之石\情绪门控\rebuild_from_archive\project_preprocess.py)

主要缓存：

- `project_cache/features/auction_yiqian_prepare/*.parquet`
- `project_cache/features/master_prepare_index/*.parquet`

作用：

- 避免 2024-2026 回放反复退回母版慢准备路径
- 减少全市场 `get_all_securities` / `get_price(count=4)` 型开销

注意：

- `project_cache/` 是运行缓存，不建议作为“结果物”提交
- 真正需要版本化的是“生成这些缓存所依赖的程序”，而不是缓存文件本身

## 5. checkpoint 配置

核心文件：

- [project_checkpoint.py](D:\Work Space\他山之石\情绪门控\rebuild_from_archive\project_checkpoint.py)
- [run_rebuild_year_checkpoint_v16.py](D:\Work Space\他山之石\情绪门控\run_rebuild_year_checkpoint_v16.py)

作用：

- 从最近一个可信年份状态起跑
- 避免每次都从 2020 全量回放

原则：

- `checkpoints/` 里的 `.pkl` 是运行产物
- 它们用于本地提速和定位分叉
- 不应作为核心源码资产长期依赖

## 6. 比较器配置

核心文件：

- [compare_actual_year.py](D:\Work Space\他山之石\情绪门控\compare_actual_year.py)
- [compare_actual_year_mother_log.py](D:\Work Space\他山之石\情绪门控\tools\compare_actual_year_mother_log.py)

当前推荐比较口径：

- 优先使用 mother-log
- 辅助参考 `jq_trades_actual.csv`
- 统一按“日期 + 代码 + 买卖方向 + 分支键”落键

原因：

- 派生交易表会漏掉部分母版可见交易
- 对重复单 / 双意图 / 强清表达不稳定

## 7. JQ 探针脚本

代表文件：

- `jq_20241209_preopen_cash_probe_JQ_UPLOAD.py`
- `jq_20241209_rzq_zb_focus_probe_JQ_UPLOAD.py`
- `jq_20241209_rzq_zb_ordertrace_probe_JQ_UPLOAD.py`
- 其他 `jq_*_probe*.py`

用途：

- 当本地推断不足以确认根因时，去 JQ 环境直接观察：
  - 候选池
  - 竞价数据
  - `available_cash / locked_cash`
  - `order_value()` 是否被调用

注意：

- 这些脚本属于“证据获取工具”
- 它们可以版本化保存
- 但运行日志、上传副本、临时输出不建议混入核心源码提交

## 8. 建议提交到远端的内容

建议版本化保存：

- `alignment_reports/*.md`
- `rebuild_from_archive/project_compat.py`
- `rebuild_from_archive/project_checkpoint.py`
- `rebuild_from_archive/project_preprocess.py`
- `rebuild_from_archive/engine/core.py`
- `rebuild_from_archive/engine/data_api.py`
- `run_rebuild_year_checkpoint_v16.py`
- `compare_actual_year.py`
- `tools/compare_actual_year_mother_log.py`
- 必要的 JQ 探针脚本

不建议作为核心提交内容长期保留：

- `checkpoints/`
- `tmp/`
- 大量运行生成的 `.csv` / `.log` / `.prof`
- 母版原始日志压缩包

## 9. 最重要的配置理解

如果只记住三点，记这三点就够了：

1. `project_compat.py` 负责“母版复刻例外”，不是修市场原始数据。
2. 快路径可以提速，但必须允许按窗口回退，正确性优先。
3. checkpoint、缓存、探针都是推进效率的工具，不是事实基线；真正的基线仍然是 mother-log 与可复核的 JQ 证据。

