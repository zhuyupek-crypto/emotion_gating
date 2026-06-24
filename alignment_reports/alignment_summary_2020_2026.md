# 2020-2026 JoinQuant 母版对齐工作总览

更新时间：2026-06-24

本文是 2020-2026 情绪门控 JoinQuant 母版对齐工作的总总结文档，用于交接、回顾和后续继续推进。它聚焦四类内容：

- 最终对齐状态：每年的交易键覆盖情况、当前已知剩余问题。
- 根因总结：跨年份反复出现的偏差类型，以及每类问题的验证方式。
- 修改清单：为了逼近母版行为，在工作区副本中做过的兼容修复、引擎修复和运行链路优化。
- 方法论与效率：哪些做法有效，哪些修复被明确拒绝，后续继续推进时应遵守什么边界。

## 1. 范围与边界

本轮对齐始终遵守以下边界：

- 只改工作区副本，不改原始 `D:\work space\local_quant`。
- 不改原始 `D:\work space\hdata`。
- 不碰 `strategies/rzq`。
- 凡声称是 “JQ 异常” 或 “母版行为差异”，都必须至少满足以下证据之一：
  - JQ 研究环境探针结果；
  - 母版交易日志；
  - 策略逻辑推导且能被母版交易路径印证。
- 不硬凑数据，不把局部偶然现象扩写成全局规则。

当前工作区内与本项目最相关的文件：

- [alignment_issues_solutions_2020_2023.md](D:/Work%20Space/%E4%BB%96%E5%B1%B1%E4%B9%8B%E7%9F%B3/%E6%83%85%E7%BB%AA%E9%97%A8%E6%8E%A7/alignment_reports/alignment_issues_solutions_2020_2023.md)
- [alignment_progress_2024_2026.md](D:/Work%20Space/%E4%BB%96%E5%B1%B1%E4%B9%8B%E7%9F%B3/%E6%83%85%E7%BB%AA%E9%97%A8%E6%8E%A7/alignment_reports/alignment_progress_2024_2026.md)
- [project_compat.py](D:/Work%20Space/%E4%BB%96%E5%B1%B1%E4%B9%8B%E7%9F%B3/%E6%83%85%E7%BB%AA%E9%97%A8%E6%8E%A7/rebuild_from_archive/project_compat.py)
- [data_api.py](D:/Work%20Space/%E4%BB%96%E5%B1%B1%E4%B9%8B%E7%9F%B3/%E6%83%85%E7%BB%AA%E9%97%A8%E6%8E%A7/rebuild_from_archive/engine/data_api.py)
- [core.py](D:/Work%20Space/%E4%BB%96%E5%B1%B1%E4%B9%8B%E7%9F%B3/%E6%83%85%E7%BB%AA%E9%97%A8%E6%8E%A7/rebuild_from_archive/engine/core.py)
- [run_rebuild_year_checkpoint_v16.py](D:/Work%20Space/%E4%BB%96%E5%B1%B1%E4%B9%8B%E7%9F%B3/%E6%83%85%E7%BB%AA%E9%97%A8%E6%8E%A7/run_rebuild_year_checkpoint_v16.py)
- [compare_actual_year.py](D:/Work%20Space/%E4%BB%96%E5%B1%B1%E4%B9%8B%E7%9F%B3/%E6%83%85%E7%BB%AA%E9%97%A8%E6%8E%A7/compare_actual_year.py)
- [compare_actual_year_mother_log.py](D:/Work%20Space/%E4%BB%96%E5%B1%B1%E4%B9%8B%E7%9F%B3/%E6%83%85%E7%BB%AA%E9%97%A8%E6%8E%A7/tools/compare_actual_year_mother_log.py)

## 2. 当前总体状态

截至 2026-06-24，可交接的整体结论如下：

| 年份 | 当前状态 | 说明 |
|---|---|---|
| 2020 | 已对齐 | JQ `395` / local `395` / both `395` / missing `0` / extra `0`。 |
| 2021 | 已对齐 | JQ `455` / local `455` / both `455` / missing `0` / extra `0`。 |
| 2022 | JQ 侧已覆盖 | JQ `427` / local `429` / both `427` / missing `0` / extra `2`；剩余是母版日志 / 派生表口径问题。 |
| 2023 | JQ 侧已覆盖 | JQ `277` / local `284` / both `277` / missing `0` / extra `7`；剩余是母版日志重复单/派生表歧义。 |
| 2024 | 基本对齐 | 当前最好结果：JQ `322` / local `320` / both `320` / missing `2` / extra `0`。 |
| 2025 | 已对齐 | JQ `533` / local `533` / both `533` / missing `0` / extra `0`。 |
| 2026 | 截至 `2026-06-12` 母版可见交易已对齐 | JQ `191` / local `194` / both `191` / missing `0` / extra `3`；3 笔为 `2026-05-29 09:30` 的本地 `bull强清` 卖出，母版源日志缺失。 |

这里的 “已对齐” 指的是按 `日期 + 代码 + 买卖方向 + 分支键` 的交易键已经一致，或母版侧所有可见交易键已被本地覆盖。它不自动等价于金额、成交价、份额、现金曲线逐笔完全一致。

## 3. 年度结论

### 3.1 2020-2023：基础兼容层建立期

2020-2023 的问题与解决方案已经在单独文档中系统沉淀：

- [alignment_issues_solutions_2020_2023.md](D:/Work%20Space/%E4%BB%96%E5%B1%B1%E4%B9%8B%E7%9F%B3/%E6%83%85%E7%BB%AA%E9%97%A8%E6%8E%A7/alignment_reports/alignment_issues_solutions_2020_2023.md)

这一阶段最重要的成果不是“修掉了多少点”，而是建立了后续几年都在复用的方法和边界：

- 明确区分 “干净市场数据” 与 “JQ 历史行为复刻”。
- 兼容逻辑尽量收敛到 `EmotionGateJQCompat`，而不是把母版项目特性散落到引擎公共层。
- 只接受带证据的窄修复，不接受看起来能提高匹配率但缺乏依据的全局放宽。

这一阶段确认的主根因有五类：

- JQ 的 `get_all_securities(date=...)` 名称/ST 口径与本地干净 ST 历史不完全相同。
- 一分钱成交差异或分钟快照差异可能改变卖点触发，从而改变后续持仓路径。
- 封板时间、尾板时间、首板缓存的细节会影响 v130 / v122 / 二板选择。
- 同一分钟预开盘重复下单的可见性和母版派生表口径不稳定。
- 没有 checkpoint 和特征缓存时，全量回放成本过高，不利于逐点定位最早分叉。

从当前结果看，2020 和 2021 已达到完整交易键对齐；2022 和 2023 的 remaining extra 并不是新的 JQ-side 缺口，而是母版日志与派生交易表之间的表达歧义。

### 3.2 2024：从“可运行”推进到“基本对齐”

2024 是从 2023 checkpoint 向后推进的第一年，也是效率优化开始真正发挥作用的一年。

早期状态并不理想：

- `rebuild_2024_from_20231231_snapshotfast_checkpoint_v16` 的初始全年结果为：
  - JQ `313`
  - 本地 `307`
  - both `290`
  - missing `23`
  - extra `17`

后续通过多轮局部定位和兼容修复，逐步把最早分叉向后推。过程中处理过的典型问题包括：

- `002130.XSHE` 相关竞价/卖出分叉；
- `000584` 名称/ST 口径问题；
- `002141` 浮点/状态问题；
- `002265` 涨停价判定问题；

当前保存下来的最好结果来自：

- `compare_actual_2024_fullmother_002265limitfix_stateful.csv`

对应统计为：

- JQ `322`
- local `320`
- both `320`
- missing `2`
- extra `0`

剩余两笔未覆盖为：

- `2024-12-09 002114.XSHE buy zb`
- `2024-12-10 002114.XSHE sell zb卖`

因此，2024 当前应定义为“基本对齐，但仍有一个明确的尾部未闭合点”。它不是完全 finished，但已经不是大面积分叉状态。

### 3.3 2025：从年初热身到全年完全对齐

2025 的推进路径比较清晰：

- 先从 2024 年末 checkpoint 起跑。
- 逐步修到 `2025-10-09` 前全匹配。
- 继续做全年回放和 mother-log 对比。

这一年中比较关键的修复包括：

- `000987` 分钟线异常修复；
- `002426` 分钟线异常修复；
- `2025-03-19` 现金下限 / pre-open 行为确认；
- `600711` 名称/ST 口径修复；
- `603031` 尾封时间修复；
- `002121.XSHE` `2025-09-29` 前一日 `high_limit` 精确值修复。

其中 `002121` 是 2025 全年收口的关键点之一：

- 母版在 `2025-09-30 09:28` 有 `[zb买] 002121.XSHE op/yc=0.984`。
- 本地 hdata 对 `2025-09-29` 给出 `high=9.41`、`high_limit=9.40`。
- 母版逻辑使用严格 `high == high_limit`，导致本地把它排除，进而去买了别的票。
- 修复方式不是放宽全局等号，而是在 `project_compat.py` 增加精确异常点：
  - `("002121.XSHE", 20250929, "high_limit"): 9.41`

全年最终结果来自：

- `rebuild_2025_full_auctionleftapi_checkpoint_v16`
- `compare_actual_2025_rebuild_2025_full_auctionleftapi_checkpoint_v16_mother_log_by_key.csv`

最终统计：

- JQ `533`
- local `533`
- both `533`
- missing `0`
- extra `0`

2025 是目前 2024-2026 段中完成度最高的一年，已经达到全年逐笔交易键完整一致。

### 3.4 2026：补齐到 06-12，剩余问题收敛为母版源缺失

2026 是目前最新、也最复杂的一段。它的主要难点不在单个股票异常，而在于 5 月下旬到 6 月中旬出现了一整段 “日线快路径污染”。

这一年已确认并修复的关键点如下。

#### 3.4.1 `002310.XSHE` 分钟异常

在 `project_compat.py` 中增加：

- `("20260119", "14:50", "002310.XSHE"): 2.36`

用于复刻母版在该分钟点位上的卖出触发路径。

#### 3.4.2 `603268.XSHG` 未来 ST 名称泄漏

发现本地静态名称/状态口径把后续 ST 信息提前泄漏回 `2026-02-12`，影响母版前一日过滤。

修复方式：

- 在 `project_compat.py` 中加入：
  - `non_st_name_windows['603268.XSHG'] = ('2026-02-12', '2026-02-12')`

作用：

- 将 2026 的最早分叉从 `2026-02-13` 推迟到 5 月底，为后续集中处理真实大问题创造了条件。

#### 3.4.3 `2026-05-25` 到 `2026-06-12` 的 daily fast path 污染

这是 2026 最核心、最重要的发现。

现象：

- 一板/连板快照突然出现极不合理结果，例如首板数异常大然后归零；
- `get_current_data()` 看到的 `high_limit/low_limit/paused` 与逐日正确值不一致；
- `history(1d, money/volume)` 在问题窗口出现 0 值，导致候选扫描直接被清空；
- 同一天通过修正后的 `get_price(... panel=False)` 能拿到合理值，但引擎内部快路径仍读到错误快照。

结论：

- 外部 hdata pivot fast path 在这一时间窗内不能继续被无条件信任。
- 不是单个代码问题，而是一个时间窗级别的底层读数污染。

因此做了三层修复。

第一层：`project_compat.py`

- 新增 `corrupted_daily_limit_windows`，当前记录为：
  - `2026-05-25` 到 `2026-06-12`
- 新增 `should_bypass_history_fastpath(unit, fields, end_dt)`。
- `load_first_seal_year()` 在污染窗口跳过对应快缓存。
- `get_project_board_snapshot()` 在污染窗口直接返回空 `DataFrame()`，避免使用脏首板快照。

第二层：`data_api.py`

- 为 `get_price()` 增加 fast path bypass 能力。
- 在兼容层要求绕过时，主动抛出 `RuntimeError('history fastpath bypass requested by compat')`，转入慢但正确的回退路径。
- `get_batch_sealing_points()` 改为使用 `get_price(... fields=['high_limit'], panel=False)`，避免直接依赖 `_history_cached(...)` 旧路径。

第三层：`core.py`

- `_get_daily_snapshot_fast(fields)` 增加 compat 咨询。
- 当 `compat.should_bypass_history_fastpath('daily', fields, day)` 返回 true 时，不再继续快取，直接回退到旧路径。

这组修复直接解决了多类实质性分叉：

- `2026-05-25` 的缺失卖出：
  - `000700.XSHE [zb卖]`
  - `000417.XSHE [zb卖]`
  - `603206.XSHG [rzq卖]`
- `2026-05-26` 缺失的 v227 买入：
  - `002645.XSHE`
  - `603730.XSHG`

其中 `2026-05-26` 的根因非常关键：

- 不是策略逻辑错了，而是 `history(1d, money/volume)` 在污染窗口内返回了 0；
- `_scan_all()` 因为成交额/成交量条件不成立，直接把候选集清空；
- 这说明快路径优化如果没有兼容兜底，确实可能把正确策略行为压成“无票可选”。

#### 3.4.4 `2026-05-28` rzq 浮点尾差

母版在 `2026-05-28` 的 rzq 路径应买：

- `603773.XSHG`
- `002185.XSHE`
- `002552.XSHE`

本地曾错误地买成：

- `002552.XSHE`
- `002886.XSHE`

根因已明确：

- `_rzq_prepare()` 对前一日炸板判断依赖严格条件：
  - `high == high_limit`
  - `close != high_limit`
- 本地 `2026-05-27` 相关行存在 float 尾差：
  - `002185.XSHE high=20.540001 high_limit=20.54`
  - `603773.XSHG high=100.690002 high_limit=100.69`
- 这两个票因此在本地被提前剔除。

修复方式同样是精确点修，而非全局容差：

- `("002185.XSHE", 20260527, "high"): 20.540000915527344`
- `("002185.XSHE", 20260527, "high_limit"): 20.540000915527344`
- `("603773.XSHG", 20260527, "high"): 100.69000244140625`
- `("603773.XSHG", 20260527, "high_limit"): 100.69000244140625`

修复后本地探针能看到：

- 两票都满足严格 `high - high_limit == 0`
- 都能正确通过 rzq 的前日炸板筛选

该修复将 2026 的对比推到目前最优状态。

#### 3.4.5 2026 当前最终状态

当前最好结果来自：

- `rebuild_2026_to0612_rzqfloatfix_v7_checkpoint_v16`
- `compare_actual_2026_rebuild_2026_to0612_rzqfloatfix_v7_checkpoint_v16_mother_log_by_key.csv`

统计为：

- JQ `191`
- local `194`
- both `191`
- missing `0`
- extra `3`

三笔 extra 全部是：

- `2026-05-29 09:30 002185.XSHE sell bull强清`
- `2026-05-29 09:30 002552.XSHE sell bull强清`
- `2026-05-29 09:30 603773.XSHG sell bull强清`

这里最重要的判断不是 “本地多了 3 笔”，而是 “母版源缺失”：

- 解析 `母版2020-2026日志/log.txt` 时，`2026-05-29` 没有对应行；
- 直接文本扫描也找不到 `2026-05-29`；
- `jq_trades_actual.csv` 也没有这三笔；
- 因此当前 2026 的剩余问题，不是已经证实的本地逻辑偏差，而是母版侧源日志缺失导致无法进一步归责。

所以到 `2026-06-12` 的结论应写成：

- 所有母版可见交易键已经被本地覆盖；
- 剩余 3 笔是本地存在、母版源不可见的 `bull强清` 卖出，属于母版源缺口，不宜强行判定为本地错误。

## 4. 跨年份根因总结

回看 2020-2026，真正高频、值得长期保留的根因类型主要有以下几类。

### 4.1 名称 / ST 口径不是一个数据问题，而是一个平台行为问题

本地 hdata 的 ST 历史可以是“市场上更干净”的版本，但母版依赖的是 JoinQuant 当年当日 `get_all_securities(date=...)` 的展示口径。两者不一致时，不能直接说 hdata 错了，也不能粗暴把整个项目改成 “凡是本地 ST 就过滤”。

因此对齐策略应是：

- hdata 保持不动；
- 在 compat 中记录窄窗口的 JQ-compatible name/ST 例外；
- 只对被母版交易证实过的日期+代码生效。

### 4.2 严格等号判定对浮点尾差极其敏感

母版里多个分支都依赖严格比较：

- `high == high_limit`
- `close == high_limit`
- 某分钟价是否碰到阈值

如果直接把本地浮点尾差当作正常数值使用，可能只差一个极小尾数，但策略路径已经分叉。所以正确做法不是全局 `round()` 或 `abs(a-b) < eps`，而是：

- 先证明母版该点确实需要严格通过；
- 再把兼容修复收敛到日期+代码+字段级别。

### 4.3 快路径优化必须允许“按窗口回退”

2026 的教训很明确：

- 快路径能带来巨大的效率收益；
- 但如果底层缓存或 pivot 某个时间窗有污染，快路径会把错误放大成整段年份分叉；
- 因此优化不能是单向的，只允许更快，不允许更稳。

最终建立的原则是：

- 快路径默认开启；
- compat 可以在特定时间窗按字段要求 bypass；
- 一旦 bypass，就回退到更慢但可验证的通用 `get_price` 路径。

这是整个对齐工程里非常重要的一次工程化升级。

### 4.4 比较口径必须逐步升级到 mother-log

单靠派生的 `jq_trades_actual.csv` 不够：

- 它会漏掉部分母版日志可见交易；
- 它对重复单、同分钟多次意图、强清等分支的表达不够稳定；
- 它无法解释为什么某笔交易发生，只能给出派生后的结果。

因此后期把对齐主比较器升级为：

- 优先解析母版日志；
- 必要时再结合 `jq_trades_actual.csv`；
- 本地日志保留 branch key，以便比较器按 “日期 + 代码 + 方向 + 分支” 落键。

这也是 [compare_actual_year_mother_log.py](D:/Work%20Space/%E4%BB%96%E5%B1%B1%E4%B9%8B%E7%9F%B3/%E6%83%85%E7%BB%AA%E9%97%A8%E6%8E%A7/tools/compare_actual_year_mother_log.py) 存在的意义。

## 5. 修改清单

### 5.1 兼容层修改

绝大多数“为了复刻母版”而产生的业务差异修复，最终都收敛到了：

- [project_compat.py](D:/Work%20Space/%E4%BB%96%E5%B1%B1%E4%B9%8B%E7%9F%B3/%E6%83%85%E7%BB%AA%E9%97%A8%E6%8E%A7/rebuild_from_archive/project_compat.py)

该文件承载了几类兼容能力：

- 非 ST 名称窗口；
- 分钟级精确价格异常点；
- 日线字段精确异常点；
- 首板 / 封板 / 板块快照兼容；
- 指定时间窗 fast path bypass 决策；
- 项目级缓存/特征载入辅助。

它的意义不只是“放一堆例外表”，更重要的是把所有非通用、非市场通用的复刻逻辑集中在一个地方，降低污染面。

### 5.2 引擎公共层修改

对引擎的改动是克制的，只在需要注入 compat、或需要给 compat 一个安全回退口时才做。

主要涉及：

- [core.py](D:/Work%20Space/%E4%BB%96%E5%B1%B1%E4%B9%8B%E7%9F%B3/%E6%83%85%E7%BB%AA%E9%97%A8%E6%8E%A7/rebuild_from_archive/engine/core.py)
- [data_api.py](D:/Work%20Space/%E4%BB%96%E5%B1%B1%E4%B9%8B%E7%9F%B3/%E6%83%85%E7%BB%AA%E9%97%A8%E6%8E%A7/rebuild_from_archive/engine/data_api.py)

关键工程点：

- `_get_daily_snapshot_fast(fields)` 的引入和后续 compat 回退能力；
- `get_price()` fast path 可被 compat 主动要求绕过；
- `get_batch_sealing_points()` 从直接用底层缓存，改为走可控的 `get_price(... panel=False)`；
- 快路径只服务性能，不再被默认视为“永远正确的数据源”。

### 5.3 运行与比较脚本

运行和比对链路本身也做了不少工作：

- [run_rebuild_year_checkpoint_v16.py](D:/Work%20Space/%E4%BB%96%E5%B1%B1%E4%B9%8B%E7%9F%B3/%E6%83%85%E7%BB%AA%E9%97%A8%E6%8E%A7/run_rebuild_year_checkpoint_v16.py)
- [compare_actual_year.py](D:/Work%20Space/%E4%BB%96%E5%B1%B1%E4%B9%8B%E7%9F%B3/%E6%83%85%E7%BB%AA%E9%97%A8%E6%8E%A7/compare_actual_year.py)
- [compare_actual_year_mother_log.py](D:/Work%20Space/%E4%BB%96%E5%B1%B1%E4%B9%8B%E7%9F%B3/%E6%83%85%E7%BB%AA%E9%97%A8%E6%8E%A7/tools/compare_actual_year_mother_log.py)

这些脚本承担了几类工作：

- 从 checkpoint 快速起跑；
- 控制预加载年份，减少重复 IO；
- 产出本地交易、状态、profile、handler profile 等文件；
- 支持从 mother-log 解析真实交易事件；
- 按分支键比较，而不是只按简单买卖聚合。

## 6. 效率优化与工程收益

这轮工作不仅仅是“补差异”，还做了一批很关键的效率优化。没有这些优化，2024-2026 的逐点推进成本会明显更高。

### 6.1 checkpoint 化

这是最直接也最有效的优化。

核心思路：

- 先把已经验证通过的年份封成 checkpoint；
- 后续从最近一个可信 checkpoint 起跑，而不是每次都从 2020 全量 replay。

收益：

- 2020-2021 跑热只做一次；
- 后续年份重放缩短到大约 8-13 分钟量级；
- 最早分叉验证可以快速迭代，不必为一个 5 月末的问题反复重跑前面几年。

### 6.2 项目特征缓存

在 `project_cache/features` 下补齐或复用了多类缓存，例如：

- `auction_yiqian_prepare`
- `master_prepare_index`
- 首板/封板相关特征

它们的作用是把一些反复用到、但从原始数据实时重算很慢的中间结果提前固化下来。

### 6.3 2024 起补齐竞价一进二预处理缓存

2024 以前只存在 2020、2021 的相关缓存，导致 2024 回放时会退回母版慢路径：

- 每日全市场 `get_all_securities`
- 大范围 `get_price(pool, count=4)`

后续通过 `project_preprocess.py` 改成年级 pivot 切片和左压快算后，生成了：

- `project_cache/features/auction_yiqian_prepare/2024.parquet`
- `project_cache/features/auction_yiqian_prepare/2025.parquet`
- `project_cache/features/auction_yiqian_prepare/2026.parquet`
- `project_cache/features/master_prepare_index/2024.parquet`
- `project_cache/features/master_prepare_index/2025.parquet`
- `project_cache/features/master_prepare_index/2026.parquet`

这使得 2024-2026 的回放不再依赖母版原始慢准备路径。

### 6.4 日线快照快路径

在 `core.py` 中引入 `_get_daily_snapshot_fast(fields)` 后，2024 早段样本出现了数量级提升：

- 优化前约 `83s`
- 优化后约 `7.7s`

而且在样本窗口内交易明细保持一致。

这说明快路径本身是成功的；后续在 2026 出现问题，并不是快路径思路错误，而是快路径必须补上 “污染窗口回退” 机制。

### 6.5 profile 驱动优化

运行脚本会输出：

- `local_profile_*.csv`
- `local_profile_handlers_*.csv`

这使性能优化不再靠猜，而是可以看到哪些 handler、哪些快照函数最耗时，再决定是否值得引入快路径或缓存。

## 7. 过程中明确拒绝的修复方式

这部分同样重要，因为它定义了后续继续推进时不能走的捷径。

### 7.1 不做全局 ST 改写

不能因为几个票在 JQ 可买、本地被 ST 过滤，就把整个项目切换成另一套 ST 历史。这样会把真实市场数据和平台行为耦在一起，污染面过大。

### 7.2 不做全局浮点容差

不能为了让 `high == high_limit` 更容易通过，就把所有相关判断改成 epsilon 比较。这样确实可能短期提高匹配率，但会把未被证明的路径也一起改掉，后续很难追责。

### 7.3 不做全局重复单去重

2020 已经证实存在母版允许同股同分钟双买的反例，所以不能把 “同分钟重复下单” 全部视作噪声或脏单。

### 7.4 不为了局部匹配率去重写原始数据

原始 hdata 与原始 local_quant 保持只读，是整个工程可信的基础。所有例外都应该记录在工作区 compat 中，而不是直接改底层数据文件。

## 8. 现阶段仍然未完全闭合的点

### 8.1 2022 / 2023 的 local-only

这两年的 remaining extra 已知不是新发现的 JQ-side missing，而是：

- 母版日志与 `jq_trades_actual.csv` 的派生口径差异；
- 重复单、同分钟双意图、日志表达等问题导致的 trade table 歧义。

如果后续要继续追金额、成交价、份额、订单级别一致性，仍然需要更原始的 JQ 导出。

### 8.2 2024 的最后一个尾部未对齐点

当前最好结果里还剩：

- `2024-12-09 002114.XSHE buy zb`
- `2024-12-10 002114.XSHE sell zb卖`

这是 2024 仍未完全封口的明确待办。

### 8.3 2026-05-29 的三笔 `bull强清`

当前判断偏向：

- 本地这三笔是真实跑出来的；
- 母版源日志在该日缺失；
- 不能在没有额外母版证据的情况下，直接把它们算成已证实的本地 bug。

如果后续能拿到更完整的母版当天日志或更原始的 JQ 交易导出，这里仍可继续复核。

## 9. 最有效的工作方法

回顾整个 2020-2026，对齐推进效率最高的方法基本稳定为以下顺序：

1. 只看最早分叉，不同时追多个尾部问题。
2. 先用 mother-log 确认母版到底发生了什么。
3. 再做最小本地重放或 JQ 探针，确认是数据问题、平台行为差异，还是策略状态机差异。
4. 只有证据闭环后，才写 compat 修复。
5. 修完立即从最近 checkpoint 重跑到目标窗口，而不是先改很多点再一起验证。

这套方法的优势是：

- 每个修复都能解释“为什么要改”；
- 后续回看时，知道这条规则是在复刻什么历史现象；
- 不会因为追求短期匹配率，把项目变成一个无法维护的大杂烩。

## 10. 建议的后续推进顺序

如果继续做 2024-2026 的收尾，建议顺序如下：

1. 先闭合 2024 年尾 `002114.XSHE` 的最后两笔。
2. 继续沿 2026-06-12 之后推进，仍然坚持 “从最近 checkpoint 起跑 + mother-log 最早分叉定位”。
3. 若要清算 2022/2023 的 residual extra，前提应是拿到更原始的 JQ 订单/成交导出，而不是继续在派生表上猜。

## 11. 一句话结论

到目前为止，这项对齐工作已经完成了最难的部分：

- 2020、2021、2025 已完整对齐；
- 2022、2023 的 JQ-side 交易键已覆盖，剩余是基线表达歧义；
- 2024 已收敛到只剩 `002114` 一组尾部问题；
- 2026 已推进到 `2026-06-12`，所有母版可见交易键已匹配，剩余 3 笔属于母版源日志缺失背景下的 local-only 强清记录。

真正有价值的产出不只是这些数字本身，而是已经建立起一套可持续复用的对齐框架：窄 compat、可回退快路径、checkpoint 驱动重放、mother-log 优先比较，以及“没有证据就不扩写规则”的工作纪律。
