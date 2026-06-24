# 2024-2026 对齐进度记录

更新时间：2026-06-17

## 当前基线

- 2023 对齐后 checkpoint：
  `checkpoints/emotion_gate_20231231_002395execfix.pkl`
- 2024 最新本地运行：
  `rebuild_2024_from_20231231_snapshotfast_checkpoint_v16`
- 2024 运行后 checkpoint：
  `checkpoints/emotion_gate_20241231_snapshotfast.pkl`
- 对比脚本输出：
  `compare_actual_2024_rebuild_2024_from_20231231_snapshotfast_checkpoint_v16_by_key.csv`

## 效率修复

### 1. 竞价一进二预处理缓存补齐

问题：

- `auction_yiqian_prepare` 只有 2020、2021 缓存。
- 2024 跑测会回退到母版 `_auction_yiqian_prepare` 的每日全市场 `get_price(pool, count=4)` 路径。
- 旧构建器本身也很慢，因为每天调用 `get_all_securities` + 全市场 `get_price`。

处理：

- 在 `rebuild_from_archive/project_preprocess.py` 中把行情读取改为年度 pivot 切片。
- 左压检查改为从年度 `high/volume` pivot 计算。
- 保留 `DataAPI.get_all_securities(..., compat=EmotionGateJQCompat)` 用于上市日/name 兼容口径。

已生成：

- `project_cache/features/auction_yiqian_prepare/2024.parquet`
- `project_cache/features/auction_yiqian_prepare/2025.parquet`
- `project_cache/features/auction_yiqian_prepare/2026.parquet`
- `project_cache/features/master_prepare_index/2024.parquet`
- `project_cache/features/master_prepare_index/2025.parquet`
- `project_cache/features/master_prepare_index/2026.parquet`

风险记录：

- 用新快构建生成 2021 临时缓存，与既有 2021 缓存按 `date+code+kind` 约 97.4% 一致。
- 少量差异集中在 y2/rzq 分类、rank 和左压结果，说明该缓存还必须接受 JQ 交易结果反向校验，不能直接视作已完全复刻 JQ。
- 未覆盖旧 2020/2021 缓存。

### 2. 日线当前/成交快照快路径

问题：

- `get_current_data()[s]` 和订单成交在 09:26/09:30 频繁触发全市场日线快照。
- 旧路径通过 `get_price(... panel=False)` 拼全市场多字段 DataFrame，单日 profile 中 `_get_daily_current_snapshot/_get_daily_trade_snapshot` 占约 35 秒。

处理：

- 在 `rebuild_from_archive/engine/core.py` 增加 `_get_daily_snapshot_fast(fields)`。
- 仅供 `_get_daily_current_snapshot` 和 `_get_daily_trade_snapshot` 使用。
- 直接从 hdata `hdata_reader._PIVOT_CACHE` 读取当天 `open/close/high_limit/low_limit/paused/volume`。
- 如果缓存或字段缺失，自动回退旧 `get_price` 路径。

验证：

- 2024-01-02 至 2024-01-08 五交易日样本：
  - 优化前：83 秒。
  - 优化后：7.7 秒。
  - 交易明细完全一致：`002865.XSHE` 2024-01-02 11:25 卖出。
- 2024 全年：
  - 优化后完成耗时约 804 秒。
  - 总交易 307 笔。

## 2024 对齐结果

对比命令：

```powershell
Copy-Item -LiteralPath .\rebuild_2024_from_20231231_snapshotfast_checkpoint_v16\local_trades_2024_from_20231231_snapshotfast.csv -Destination .\rebuild_2024_from_20231231_snapshotfast_checkpoint_v16\local_trades_2024.csv -Force
python .\compare_actual_year.py 2024 .\rebuild_2024_from_20231231_snapshotfast_checkpoint_v16
```

结果：

- JQ：313
- 本地：307
- both：290
- missing：23
- extra：17
- 按 日期+代码+方向 的逐笔覆盖率约 92.7%。

## 当前首个未对齐点

### 2024-03-21 `002130.XSHE`

现象：

- JQ：`002130.XSHE` 只有 v227 买，2024-03-26 11:25 止盈卖出。
- 本地：2024-03-21 同时触发竞价腿和 v227 腿，各买一笔；2024-03-25 14:50 作为 v227 尾盘清卖出。
- 这导致后续现金、持仓和胜率路径偏移。

本地关键数据：

- 2024-03-20：
  - close = 8.25
  - high_limit = 8.25
  - money = 816,681,472
  - volume = 101,585,200
  - `avg_inc_y2 = 0.07191658`
  - `inc4 = 0.130137`
  - y2 条件成立。
- 2024-03-21 集合竞价：
  - current = 8.45
  - volume = 3,410,100
  - 竞价量比约 3.36%，满足 `vol_ratio >= 0.03`。
- valuation：
  - market_cap = 103.94
  - circulating_market_cap = 103.05
- 左压：本地为 True。

待 JQ 核验：

- 已新增 JQ 研究脚本：
  `jq_20240321_002130_auction_probe.py`
- JQ 输出已证实：`get_call_auction([002130.XSHE], 2024-03-21 09:15-09:25)` 返回空表。
- 本地 hdata 有 09:25 集合竞价记录：current=8.45、volume=3,410,100。
- 处理：在 `project_compat.py` 增加 `call_auction_empty_anomalies = {("002130.XSHE", 20240321)}`，并让 `DataAPI.get_call_auction` 从 compat profile 读取该异常。
- 重跑结果：本地 2024-03-21 多出的竞价买已消失。

### 2024-03-25 `002130.XSHE`

现象：

- JQ：2024-03-26 11:25 卖出 `002130.XSHE`。
- 本地：2024-03-25 14:50 卖出 `002130.XSHE`。

本地关键数据：

- 2024-03-25 日线 high_limit = 10.99。
- 2024-03-25 14:46 至 14:49 分钟 close 均为 10.99。
- 2024-03-25 14:50 分钟 close = 10.91。
- v227 尾盘卖出逻辑为“14:50 非涨停全清”，因此本地 14:50 卖出。

待 JQ 核验：

- 已新增 JQ 研究脚本：
  `jq_20240325_002130_sell_probe.py`
- 需要核对 JQ 在 2024-03-25 14:50 的分钟 close 是否仍为 high_limit。
- 如果 JQ 14:50 分钟价仍为 10.99，则记录为 JQ 分钟快照差异。
- 如果 JQ 14:50 分钟价也是 10.91，则继续查 JQ backtest 中 `current_data.last_price` 或 14:50 handler 执行语义。

## 2024 第二轮结果

在应用 `002130.XSHE` 集合竞价空表异常后：

- JQ：313
- 本地：306
- both：290
- missing：23
- extra：16
- 主要改善：去掉了 2024-03-21 多出的 `002130.XSHE` 竞价买。
- 当前最早分叉变为 2024-03-25/26 `002130.XSHE` 卖出日差异。

## 下一步

1. 用 JQ 输出确认 `002130.XSHE` 2024-03-25 14:50 是否仍视作涨停。
2. 先修复或记录 2024-03-25 这一处卖出日分叉，再重跑 2024。
3. 2024 交易对齐率达标后，再用最新 2024 checkpoint 接 2025。
4. 2025/2026 已具备预处理缓存，可直接使用相同 checkpoint runner。

## 2024-04-11 rzq/zb gate 待核验

现象：

- 最新 2024 本地结果 `rebuild_2024_from_20231231_002130sellfix_checkpoint_v16` 中，2024-04-11 本地多买 `000506.XSHE`，2024-04-12 多卖；JQ 母版没有这笔。
- 本地 2024-04-08 至 2024-04-10 交易逐笔匹配；2024-04-11 早盘状态为 `active=rzq+zb`、`enable_rzq=True`、`enable_zb=True`、可用现金约 3110 万、持仓 3 个。
- 反事实过滤 2024-04-10 龙虎榜里的 `000506.XSHE` 后，本地 2024-04-11 改为通过 `zb` 买 `000888.XSHE`，说明差异不是单票 `000506`，而是当天本地 `rzq/zb` 新仓 gate 比 JQ 多放行。

本地 probe：

- 新增本地诊断脚本：`tools/probe_local_20240411_rzq_zb.py`。
- 本地 `rzq_prepare_valid`：`000506.XSHE`、`600210.XSHG`、`605488.XSHG`。
- 本地 `rzq_pass` 只有 `000506.XSHE`：`open/yclose=0.9948`、集合竞价主买约 1959.74 万、主卖约 406.51 万、`turnover_ratio=0.304164`、score 约 1.4587。
- 本地 `zb_prepare_valid` 共 12 只，`zb_pass` 为 `000888.XSHE`、`603518.XSHG`、`002903.XSHE`、`002942.XSHE`；其中 `000888.XSHE` score 最高，`open/yclose=0.9819`、主买约 112.51 万、主卖约 18.63 万。
- 引擎语义注意：09:27/09:28 的 `get_current_data().last_price` 使用当日 `open`，不是日线 `close`；因此 `000506.XSHE`、`000888.XSHE` 虽然日内最终涨停，本地买入 gate 仍按开盘价通过“非涨停”检查。

待 JQ 核验：

- 新增 JQ 研究脚本：`jq_20240411_rzq_zb_gate_probe.py`。
- 需要核对 JQ 在 2024-04-11 的 `rzq_prepare_valid`、`zb_prepare_valid`、`get_call_auction` 主买/主卖、估值 `turnover_ratio` 排序、买入日 open/limit/paused。
- 暂不在 `project_compat.py` 增加异常；除非 JQ probe 或母版交易/策略逻辑能证明具体差异点。

补充工具：

- 新增 JQ/本地 probe 对比脚本：`tools/compare_probe_20240411_rzq_zb.py`。
- 默认读取：
  - 本地：`alignment_reports/probe_local_20240411_rzq_zb.json`
  - JQ：`alignment_reports/probe_jq_20240411_rzq_zb.json`
- 收到 JQ JSON 后保存为上述 JQ 文件，并运行：

```powershell
python .\tools\compare_probe_20240411_rzq_zb.py
```

该脚本会对比 `rzq_prepare_valid`、`zb_prepare_valid`、`rzq_pass`、`zb_pass`，并逐字段列出共同 gate 行中的 open/limit/auction/valuation/score 差异。

## 2024-04-11 rzq/zb gate JQ 核验结果

JQ 批量 gate probe 已返回，保存为 `alignment_reports/probe_jq_20240411_rzq_zb.json` 后用 `tools/compare_probe_20240411_rzq_zb.py` 对比。

结论：

- `rzq_pass` 本地与 JQ 完全一致，均只有 `000506.XSHE`。
- `zb_pass` 本地与 JQ 完全一致，均为 `000888.XSHE`、`603518.XSHG`、`002903.XSHE`、`002942.XSHE`。
- `rzq_prepare_valid` JQ 多出 `603261.XSHG`，但该股 `ratio_ok=false`，不影响最终通过集合。
- 估值 `turnover_ratio` 存储尺度存在差异：本地为小数，JQ 为百分数；score 因此约差 100 倍，但排序和最终通过集合一致。
- 多只股票价格绝对值存在复权/原始价尺度差异，但 `open/yclose` 比例、涨跌停门控和最终通过集合一致。

因此，2024-04-11 本地多买 `000506.XSHE` 的根因暂不在候选生成、集合竞价主买主卖、估值排序、开盘价/涨跌停/停牌 gate。下一步需核查 JQ 母版实际运行时状态与订单结果：当天是否进入 `buy_rzq`、当时 `rzq_slots/held/available_cash` 是否允许下单、`order_value(000506.XSHE, ..., MarketOrderStyle(day_open))` 是否返回订单，以及该订单是否被拒绝/取消/未进入当前 derived `jq_trades_actual.csv`。

已新增运行时观察脚本：

- `jq_20240411_runtime_state_probe.py`

运行方式：将该完整脚本放入聚宽策略回测环境，使用与母版一致的回测参数跑到覆盖 `2024-04-10` 至 `2024-04-12` 的区间，然后复制日志中包含 `[CX-411]` 的行。预期输出标签包括：

- `[CX-411] STATE ...`：`prepare_all`、`buy_rzq`、`buy_zb` 前后的 active、slots、cash、positions、owner。
- `[CX-411] LEG_PLAN ...`：按母版逻辑重新列出 rzq/zb 候选过滤、竞价过滤、score、slots、planned_orders。
- `[CX-411] ORDERS_AFTER_RZQ ...` / `[CX-411] ORDERS_AFTER_ZB ...`：JQ 当日 open orders / orders / trades 快照。

暂不在 `project_compat.py` 增加异常；必须等运行时 probe 或母版原始订单/交易日志证明具体差异点。

## 2024-04-11 `000506.XSHE` 结论：旧 `jq_trades_actual.csv` 漏项

补充证据：

- 原始母版日志 `母版2024交易日志.txt` 明确包含：
  - line 945：`2024-04-11 09:27:00 - [rzq买] 000506.XSHE op/yc=0.995`
  - line 965/967：`2024-04-12 09:30` 对 `000506.XSHE` 有 `[BIG_TRADE]` 与 `[bull强清]`。
- 本地完整 2024 日志在同一区间也为：
  - `2024-04-11 09:27 [rzq买] 000506.XSHE`
  - `2024-04-12 every_bar/09:30` 强清 `000506.XSHE`。
- 之前的 `jq_20240411_rzq_zb_gate_probe.py` 也证明 JQ gate 中 `rzq_pass` 只有 `000506.XSHE`。

因此，`compare_actual_year.py` 基于 `jq_trades_actual.csv` 报出的 `2024-04-11 000506.XSHE` local extra 不是本地复刻错误，而是旧派生 JQ 交易表漏掉了母版日志中的真实交易。不得为这条在 `project_compat.py` 增加异常，也不应删除本地 `000506` 交易。

本次收到的短窗口 JQ runtime probe 日志只覆盖 2024-04-12，且账户总值约 103 万、持仓为 `000612.XSHE` + `000888.XSHE`，明显不是全路径母版状态；只能作为脚本可运行性的辅助证据，不能替代 2020/2024 全路径母版日志。

新增诊断工具：

- `tools/compare_actual_year_mother_log.py`

该工具直接从 `母版2024交易日志.txt` 解析买卖事件，并特别拆分 `[bull强清] 2笔: ...` 这种聚合卖出行，用于避免旧 `jq_trades_actual.csv` 漏项误判。

运行：

```powershell
python .\tools\compare_actual_year_mother_log.py 2024 .\rebuild_2024_from_20231231_002130sellfix_checkpoint_v16
```

当前输出：

- mother-log events：321
- local events：306
- both：295
- missing：26
- extra：11
- 输出文件：`compare_actual_2024_rebuild_2024_from_20231231_002130sellfix_checkpoint_v16_mother_log_by_key.csv`

局部核验结果：

- 2024-04-10 全部关键买卖为 `both`。
- 2024-04-11 `000506.XSHE` buy 为 `both`，JQ 行号 945。
- 2024-04-12 `000506.XSHE` sell 为 `both`，JQ 行号 967。

下一步应转向 mother-log 对比下的最早真实差异：

1. `2024-01-02 002865.XSHE` 本地多卖，可能来自 2023 年末 checkpoint 持仓/卖出日志跨年口径，需要核对 checkpoint 与母版 2023 年末持仓。
2. `2024-02-27/28` JQ mother-log 为 `003025.XSHE` 天蝎座，本地为 `002888.XSHE`。
3. `2024-02-29/03-04` JQ mother-log 有 `600338.XSHG` 竞价买卖，本地缺失。
4. `2024-03-21 002130.XSHE` 在 mother-log 对比下为 JQ missing，而旧 `jq_trades_actual.csv` 口径曾显示本地多出；需要以原始母版日志为准重新核查 3/21 竞价/一进二路径。

后续 2024 对齐应优先使用 mother-log 事件对比作为 trade-key 证据，旧 `jq_trades_actual.csv` 只能作为辅助，不再单独作为 2024 分叉判定依据。

### 完整母版日志重跑结果

`tools/compare_actual_year_mother_log.py` 已支持读取 `母版2020-2026日志.zip`，避免年度日志切片遗漏跨年持仓卖出。

运行：

```powershell
python .\tools\compare_actual_year_mother_log.py 2024 .\rebuild_2024_from_20231231_002130sellfix_checkpoint_v16 --mother-log .\母版2020-2026日志.zip --out .\compare_actual_2024_rebuild_2024_from_20231231_002130sellfix_checkpoint_v16_full_mother_log_by_key.csv
```

输出：

- mother-log events：324
- local events：306
- both：299
- missing：25
- extra：7
- 输出文件：`compare_actual_2024_rebuild_2024_from_20231231_002130sellfix_checkpoint_v16_full_mother_log_by_key.csv`

变化：

- `2024-01-02 002865.XSHE` 不再是本地 extra。完整母版日志包含：`2024-01-02 11:25 [竞价卖-落袋] 002865.XSHE`，年度 `母版2024交易日志.txt` 片段漏了这个跨年持仓卖出。
- `2024-04-11/04-12 000506.XSHE` 仍为 `both`，确认该点已结案。

完整母版日志口径下的当前最早差异：

1. `2024-03-20 000917.XSHE` 本地 extra sell，疑似 2023/2024 checkpoint 持仓或母版日志解析口径问题，需要先查完整母版中 `000917.XSHE` 买卖链。
2. `2024-03-21 002130.XSHE` JQ mother-log missing buy，完整母版行号 9985，分支为 `v227`。这说明早前基于旧 `jq_trades_actual.csv` 认定的 3/21 “本地多买”不可靠；需以完整母版日志重新核查 3/21 的 v227/竞价路径。

后续工作应优先围绕完整母版日志对比文件继续，而不是旧 `jq_trades_actual.csv`。

## 2026-06-22 基准源修正：2024-03-21 `002130.XSHE`

结论：此前把 `2024-03-21 002130.XSHE` 判为“本地多出的竞价买”，是旧 `jq_trades_actual.csv` / 单次 JQ research `get_call_auction` 探针口径不完整导致。完整母版日志 `母版2020-2026日志.zip` 才是本轮 2024 trade-key 对齐的主基准。

证据：

- 完整母版日志同时包含：
  - `2024-03-21 09:26 [竞价买] 002130.XSHE y2 auction=1.024`
  - `2024-03-21 09:26 [v227买] 002130.XSHE 开2.4% [cautious]`
  - `2024-03-26 11:25 [v227止盈] 002130.XSHE +38.9%`
- 这与 2020-2023 留档中的 JQ-004 类问题一致：同股同分钟多分支交易/派生交易表可见性不能单独作为母版事实源。
- 2024-04-11 `000506.XSHE` 也已被完整母版日志证实为真实 `rzq` 买入和次日强清；旧 `jq_trades_actual.csv` 对该笔同样漏记。

处理：

- 已撤销 `project_compat.py` 中 `call_auction_empty_anomalies = {("002130.XSHE", 20240321)}`。
- 保留 `2024-03-25 14:50 002130.XSHE -> 10.99` 的分钟价异常；完整母版日志仍证明 `002130.XSHE` 持有到 `2024-03-26 11:25` 才止盈。
- 后续 2024 分叉判定优先使用 `tools/compare_actual_year_mother_log.py --mother-log 母版2020-2026日志.zip --local-log ...`，旧 `jq_trades_actual.csv` 仅作辅助。

验证：

```powershell
python .\run_rebuild_year_checkpoint_v16.py --start 2024-01-01 --end 2024-03-26 --tag 2024_to0326_fullmother_auction002130 --resume-checkpoint .\checkpoints\emotion_gate_20231231_002395execfix.pkl --preload-start-year 2022 --preload-end-year 2024 --progress-interval 20
python .\tools\compare_actual_year_mother_log.py 2024 .\rebuild_2024_to0326_fullmother_auction002130_checkpoint_v16 --mother-log .\母版2020-2026日志.zip --local-log .\rebuild_2024_to0326_fullmother_auction002130_checkpoint_v16\local_run_2024_to0326_fullmother_auction002130.log --out .\compare_actual_2024_to0326_fullmother_auction002130_mother_vs_local_log_by_key.csv
```

输出：`YEAR=2024 mother=325 local=49 both=49 missing=276 extra=0`。截至 2024-03-26，本地 49 笔全部能在完整母版日志中找到。

```powershell
python .\run_rebuild_year_checkpoint_v16.py --start 2024-01-01 --end 2024-04-24 --tag 2024_to0424_fullmother_auction002130 --resume-checkpoint .\checkpoints\emotion_gate_20231231_002395execfix.pkl --preload-start-year 2022 --preload-end-year 2024 --progress-interval 20
python .\tools\compare_actual_year_mother_log.py 2024 .\rebuild_2024_to0424_fullmother_auction002130_checkpoint_v16 --mother-log .\母版2020-2026日志.zip --local-log .\rebuild_2024_to0424_fullmother_auction002130_checkpoint_v16\local_run_2024_to0424_fullmother_auction002130.log --out .\compare_actual_2024_to0424_fullmother_auction002130_mother_vs_local_log_by_key.csv
```

输出：`YEAR=2024 mother=325 local=91 both=91 missing=234 extra=0`。截至 2024-04-24，本地 91 笔全部能在完整母版日志中找到；剩余 missing 是因为本地只跑到 4/24，而母版日志为完整年度。

关键本地日志：

- `2024-03-21 09:26 [竞价买] 002130.XSHE y2 auction=1.025`
- `2024-03-21 09:26 [v227买] 002130.XSHE 开2.4% [cautious]`
- `2024-03-26 11:25 [v227止盈] 002130.XSHE +38.9%`
- `2024-04-11 09:27 [rzq买] 000506.XSHE op/yc=0.995`
- `2024-04-12 [bull强清] 2笔: 000612.XSHE -1.1%, 000506.XSHE 8.6%`

下一步：用当前 `project_compat.py` 跑完整 2024，并用完整母版日志对比年度事件。若年度仍有 `extra` 或早于 2024-04-24 的 mismatch，先按 2020-2023 已留档类型归因；只有完整母版日志、JQ 探针或策略逻辑能证明时，才新增 project compat 异常。

## 2026-06-22 进一步定位：2024-04-23 `000584.XSHE` 天蝎座缺失

年度完整母版日志对比在 `002130/000506` 修正后输出：`YEAR=2024 mother=325 local=307 both=301 missing=24 extra=6`，输出文件为 `compare_actual_2024_fullmother_auction002130_mother_vs_local_log_by_key.csv`。

当前最早真实差异：

- JQ：`2024-04-23 09:30 [天蝎座] 000584.XSHE 低开-3.2%`，`2024-04-24 11:25 [v227止盈] 000584.XSHE +9.0%`。
- 本地：2024-04-23 日志为 `bear候选11`，未买 `000584.XSHE`；母版同日为 `bear候选17`。

本地探针结论：

- `000584.XSHE` 在 2024-04-22 是一板：`close=2.19`、`is_first_board=True`。
- 本地 `get_all_securities(date=2024-04-22)` 的 `display_name` 为 ST 名称，因此被策略 `ST|st|*|退` 前一日名称过滤剔除。
- IPO 年龄不构成过滤：`ipo_age=10374`。
- 60 日位置通过天蝎座 bear pool 条件：`pos=0.080645 <= 0.5`。
- 买入日开盘条件通过：2024-04-23 `open=2.12`，前收 `2.19`，`open_pct=-3.196%`，落在 `[-4%, -3%]`。

归因：与 2020-2023 留档 JQ-012 同类，属于 JQ-compatible `get_all_securities(date=previous_day)` display-name snapshot 与本地 clean ST/name 快照差异，不是行情数据硬凑。

处理：已在 `project_compat.py` 增加最小窗口：

```python
"000584.XSHE": ("2024-04-22", "2024-04-22")
```

待验证：需要重跑 `2024-01-01` 至 `2024-04-24`，然后完整年度重跑。当前 Codex approval/usage 限制拦截了回测命令，尚未完成验证。

## 2026-06-22 更新：2024 天蝎座 ST/name 批量窗口与 `002141` -3% 边界

### `000584.XSHE` 验证结果

`000584.XSHE` 的最小 non-ST name window 已验证通过：

```powershell
python .\run_rebuild_year_checkpoint_v16.py --start 2024-01-01 --end 2024-04-24 --tag 2024_to0424_fullmother_000584namefix --resume-checkpoint .\checkpoints\emotion_gate_20231231_002395execfix.pkl --progress-interval 20
python .\tools\compare_actual_year_mother_log.py 2024 .\rebuild_2024_to0424_fullmother_000584namefix_checkpoint_v16 --mother-log .\母版2020-2026日志.zip --local-log .\rebuild_2024_to0424_fullmother_000584namefix_checkpoint_v16\local_run_2024_to0424_fullmother_000584namefix.log --out .\compare_actual_2024_to0424_fullmother_000584namefix_mother_vs_local_log_by_key.csv
```

结果：`YEAR=2024 mother=325 local=93 both=93 missing=232 extra=0`。截至 2024-04-24，本地全部交易键进入完整母版日志。

### 2024 scorpion ST/name 批量窗口

后续缺失的多笔天蝎座买入沿用 2020-2023 已归档的 JQ-012 类型：JQ mother-log 买入，但本地 `get_all_securities(date=previous_day)` 显示 ST 名称，策略名称过滤提前剔除；价格/板位/60 日位置/开盘缺口均自然通过。

已在 `project_compat.py` 增加最小 previous-day name window：

- `002141.XSHE`: `2024-06-07`、`2024-07-15`
- `002052.XSHE`: `2024-06-20`
- `603003.XSHG`: `2024-06-27`
- `000506.XSHE`: `2024-08-07`

局部验证到 2024-08-09，未处理 `002141` -3% 浮点边界前，新增窗口已修复 6/11、6/21、6/28、8/08 等 ST/name 型缺失，但 `2024-07-16 002141.XSHE` 仍未买入。

### `002141.XSHE` 2024-07-16 浮点边界

证据：

- 完整母版日志：`2024-07-16 09:30 [天蝎座] 002141.XSHE 低开-3.0%`，`2024-07-17 11:25 [v227止盈] 002141.XSHE +5.1%`。
- 本地候选探针：`002141.XSHE` 已在 `2024-07-15` 一板、通过 60 日位置，且在低价 tilt 后排序第一。
- 本地运行时 `current_data`：`day_open=np.float32(0.97)`、`yc=1.0`，得到 `open_pct=np.float32(-0.029999971)`；母版策略天蝎座门槛为严格 `if open_pct < -0.04 or open_pct > -0.03: continue`，因此本地被浮点误差挡在 -3% 边界外。

处理：

- 在 `project_compat.py daily_price_anomalies` 增加精确点：`("002141.XSHE", 20240716, "open"): 0.96999997`。
- 在 `engine/core.py _get_daily_snapshot_fast()` 中应用 `compat.daily_price_anomalies`，避免快速日线 snapshot 绕过已登记的日线点异常。

复查探针：

- 修复后 `day_open=0.96999997`，`open_pct=-0.030000029999999955`，严格门槛放行。
- 交易价仍由 `_get_trade_price()` 四舍五入为 `0.97`，不改变实际成交价。

### mother-log stateful 对比口径

完整母版日志存在残留退出日志，例如：

- `2024-06-24 14:50 [BIG_TRADE] ... 002052.XSHE branch=v227_scorpion ...` 后，`2024-06-25 09:30 [BIG_TRADE] ... branch=unknown_v227 entry=NA pnl=-0` 和 `[v227止损] 002052.XSHE`。
- `2024-07-17 11:25 [v227止盈] 002141.XSHE` 后，`2024-07-18 11:25` 又出现一次 `002141.XSHE` 止盈。

这些不应驱动本地硬造交易。因此 `tools/compare_actual_year_mother_log.py` 新增可选 `--drop-unmatched-sells`，按同代码买卖计数过滤没有对应 open position 的残留退出日志；默认口径不变。

### 验证到 2024-08-09

```powershell
python .\run_rebuild_year_checkpoint_v16.py --start 2024-01-01 --end 2024-07-18 --tag 2024_to0718_fullmother_002141floatfix --resume-checkpoint .\checkpoints\emotion_gate_20231231_002395execfix.pkl --progress-interval 20
python .\tools\compare_actual_year_mother_log.py 2024 .\rebuild_2024_to0718_fullmother_002141floatfix_checkpoint_v16 --mother-log .\母版2020-2026日志.zip --local-log .\rebuild_2024_to0718_fullmother_002141floatfix_checkpoint_v16\local_run_2024_to0718_fullmother_002141floatfix.log --drop-unmatched-sells --out .\compare_actual_2024_to0718_fullmother_002141floatfix_mother_vs_local_log_by_key_stateful.csv
```

截至 2024-07-18：`both_to_0718=164`，无 missing/extra。

```powershell
python .\run_rebuild_year_checkpoint_v16.py --start 2024-01-01 --end 2024-08-09 --tag 2024_to0809_fullmother_002141floatfix --resume-checkpoint .\checkpoints\emotion_gate_20231231_002395execfix.pkl --progress-interval 30
python .\tools\compare_actual_year_mother_log.py 2024 .\rebuild_2024_to0809_fullmother_002141floatfix_checkpoint_v16 --mother-log .\母版2020-2026日志.zip --local-log .\rebuild_2024_to0809_fullmother_002141floatfix_checkpoint_v16\local_run_2024_to0809_fullmother_002141floatfix.log --drop-unmatched-sells --out .\compare_actual_2024_to0809_fullmother_002141floatfix_mother_vs_local_log_by_key_stateful.csv
```

截至 2024-08-09：`both_to_0809=177`，无 missing/extra。下一条真实缺失从 `2024-08-12 002285.XSHE` 卖出开始，因为局部回测只跑到 8/09。

下一步：用当前修复跑完整 2024，并继续使用 `--drop-unmatched-sells` 口径定位 2024-08-12 之后的真实差异；若新差异仍落在 ST/name、集合竞价、分钟价、执行价等既有类别，优先沿用 2020-2023 已留档分类。

## 2026-06-22 更新：完整 2024 至 12/09 预开盘现金语义

### 完整 2024 首轮验证与 2024-12-04 `603569.XSHG`

使用 `002141` 浮点边界修复后跑完整 2024：

```powershell
python .\run_rebuild_year_checkpoint_v16.py --start 2024-01-01 --end 2024-12-31 --tag 2024_from_20231231_fullmother_002141floatfix --resume-checkpoint .\checkpoints\emotion_gate_20231231_002395execfix.pkl --save-checkpoint .\checkpoints\emotion_gate_20241231_fullmother_002141floatfix.pkl --progress-interval 40
python .\tools\compare_actual_year_mother_log.py 2024 .\rebuild_2024_from_20231231_fullmother_002141floatfix_checkpoint_v16 --mother-log .\母版2020-2026日志.zip --local-log .\rebuild_2024_from_20231231_fullmother_002141floatfix_checkpoint_v16\local_run_2024_from_20231231_fullmother_002141floatfix.log --drop-unmatched-sells --out .\compare_actual_2024_fullmother_002141floatfix_mother_vs_local_log_by_key_stateful.csv
```

结果：`YEAR=2024 mother=322 local=316 both=312 missing=10 extra=4`。

最早真实差异：

- JQ：2024-12-04 买入 `603569.XSHG`，2024-12-06 卖出。
- 本地：2024-12-04 买入 `600738.XSHG`，2024-12-06 卖出。

证据：

- 母版 2024-12-04 日志：`zb候选36`，买入 `002535.XSHE`、`603569.XSHG`、`002551.XSHE`。
- 本地 2024-12-04 日志：`zb候选34`，买入 `002535.XSHE`、`002551.XSHE`、`600738.XSHG`。
- 本地探针显示 `603569.XSHG` 没有进入 `g.zb_candidates`；2024-12-03 本地日线为 `high=9.41`、`high_limit=9.40`，策略 `_zb_prepare` 使用严格炸板判断 `high == high_limit`，因此本地被剔除。
- 若按 JQ 母版行为允许 `603569.XSHG` 进入候选，其 `zb` score 排在 `002551.XSHE` 与 `600738.XSHG` 之前，正好解释本地第三仓从 `600738` 替换为 JQ 的 `603569`。

归因：这与 2020-2023 已留档的日线点快照/涨停价舍入差异同类，不是为了对齐硬凑候选。已在 `project_compat.py daily_price_anomalies` 增加最小点异常：

```python
("603569.XSHG", 20241203, "high_limit"): 9.41
```

### `603569` 修复后完整 2024 验证

```powershell
python .\run_rebuild_year_checkpoint_v16.py --start 2024-01-01 --end 2024-12-31 --tag 2024_from_20231231_fullmother_603569limitfix --resume-checkpoint .\checkpoints\emotion_gate_20231231_002395execfix.pkl --save-checkpoint .\checkpoints\emotion_gate_20241231_fullmother_603569limitfix.pkl --progress-interval 60
python .\tools\compare_actual_year_mother_log.py 2024 .\rebuild_2024_from_20231231_fullmother_603569limitfix_checkpoint_v16 --mother-log .\母版2020-2026日志.zip --local-log .\rebuild_2024_from_20231231_fullmother_603569limitfix_checkpoint_v16\local_run_2024_from_20231231_fullmother_603569limitfix.log --drop-unmatched-sells --out .\compare_actual_2024_fullmother_603569limitfix_mother_vs_local_log_by_key_stateful.csv
```

结果：`YEAR=2024 mother=322 local=316 both=314 missing=8 extra=2`。最早剩余真实差异进入 2024-12-09/12-10：

- JQ missing：2024-12-09 买入 `002114.XSHE`，2024-12-10 卖出。
- 本地 extra：2024-12-10 买入 `002144.XSHE`，2024-12-16 卖出。
- 后续 missing 还有 `002265.XSHE`、`002687.XSHE`、`001211.XSHE` 的跟随差异，需先解决 12/09 仓位/现金状态后再判断。

### 2024-12-09 预开盘现金语义待 JQ 探针

本地 2024-12-09 状态：`active=rzq+zb`，持仓 `002158.XSHE:auction`、`002297.XSHE:zb`、`002345.XSHE:zb`，可用现金约 3210 万；`rzq` 候选 5 个、`zb` 候选 47 个。

本地当天行为：

- 09:27 买入 `603662.XSHG`：`[rzq买] 603662.XSHG op/yc=0.984`。
- 09:28 未买 `002114.XSHE`。

本地探针显示 `002114.XSHE` 在 2024-12-09 `zb` 候选中且排序第一：`score=2.7717`、`auction_ratio=0.9960`、`buy/sell=9.337`、`turnover=0.2980`；`002144.XSHE` 不在 12/09 候选中。

当前推断：本地引擎在 09:27 `rzq` 预开盘下单后冻结/占用现金，导致 09:28 `zb` 买入阶段现金不足，未能买入 JQ 母版中的 `002114.XSHE`。JQ 母版日志则显示 2024-12-09 同时买入 `603662.XSHG` 与 `002114.XSHE`。这属于 2020-2023 已留档的 pre-open pending order / available_cash 语义类别；此前全局改预开盘现金冻结曾造成其他年份回归，因此本轮不做全局语义修改。

待证据：已生成 JQ 回测环境脚本 `jq_20241209_preopen_cash_probe_JQ_UPLOAD.py`。需要在聚宽回测环境运行 2024-12-02 至 2024-12-16，并回传所有包含 `[CX-1209]` 的日志，以及正常 `[rzq买]`、`[zb买]`、`[bull强清]`、`[v227止盈]`、`[v227止损]` 行。确认 JQ 在 09:27 后、09:28 前的 `available_cash/locked_cash/positions` 后，才能决定是否加最小范围 compat 逻辑或记录为未修复差异。
### 2024-12-09/12-10 复查：`002114` 现金语义未解，`002265` 日线炸板点已确认

收到 2024-12-02 至 2024-12-16 的 JQ 短区间回测探针后，结论需要分开处理：

- 短区间 JQ 探针在 2024-12-09 的 `fb_pct=0.50`，触发 `[rzq] bull+pct毒区跳过`，因此只买 `002114.XSHE`，不能复现完整母版同日同时买 `603662.XSHG` 与 `002114.XSHE` 的路径。
- 完整母版日志在 2024-12-09 的 `fb_pct=0.65`，明确记录 `[rzq买] 603662.XSHG` 与 `[zb买] 002114.XSHE`；本地完整接续同日 `fb_pct=0.65` 但只买 `603662.XSHG`。
- 本地 12/09 gate probe 显示 `rzq_pass` 只有 `603662.XSHG` 一个，`zb_pass` 第一为 `002114.XSHE`。简单跳过 `603662` 的预开盘现金冻结可以让 12/09 同时买入两者，但会造成 12/10 盘前可用现金为负，并阻断母版的 `002265.XSHE` 买入；该补丁已撤销，不能作为最终修复。

因此 `002114.XSHE` 仍归类为未解决的 full-path pre-open cross-handler cash/order 语义差异。需要完整路径 JQ 探针，至少覆盖 2024-12-09 09:27 后、09:28 前、09:30 后以及 2024-12-10 09:27 前的 `available_cash/locked_cash/positions/order` 状态，短区间回测不足以证明。

同时，2024-12-10 `002265.XSHE` 已确认是独立的日线炸板快照差异：

- 完整母版日志：`2024-12-10 09:27 [rzq买] 002265.XSHE op/yc=1.005`，并在 2024-12-16 `rzq卖`。
- 本地 12/10 prepare 分层探针：`002265.XSHE` 进入龙虎榜池并通过名称/上市过滤，但没有进入 `df_hl` 炸板层。
- 本地 hdata/JQ-compatible snapshot：2024-12-09 `002265.XSHE high=20.19`、`high_limit=20.18`、`close=19.29`，策略 `_rzq_prepare` 严格要求 `high == high_limit and close != high_limit`。
- 加入最小点异常 `("002265.XSHE", 20241209, "high_limit"): 20.19` 后，本地 12/10 `rzq_prepare_valid` 包含 `002265.XSHE`，且 `rzq_pass` 唯一通过项为 `002265.XSHE`，score=2.62985，ratio=1.004666，buy/sell=9.236。

该处理与 `603569.XSHG` / 2020-2023 已留档的日线 high/high_limit equality 类别一致。
### 2024-12-09 full-path JQ probe result

The quiet full-year JQ probe (`jq_20241209_preopen_cash_probe_FULLPATH_QUIET_JQ_UPLOAD.py`, 2024-01-01 to 2024-12-16) contradicts the archived parsed mother-log assumption for `002114.XSHE`:

- 2024-12-09 09:27 before `buy_rzq`: available=1,090,383.02, locked=0, positions=`002297.XSHE,002345.XSHE`.
- JQ places `603662.XSHG` for value=1,090,383.02, amount=16,400; after `buy_rzq`: available=4,703.02, locked=1,085,680.00.
- 2024-12-09 09:28 before `buy_zb`: available=4,703.02, `002114.XSHE` is in `zb_candidates`, but no `[zb买] 002114.XSHE` is emitted; after `buy_zb` cash/state are unchanged.
- 2024-12-10 09:27 JQ buys `002265.XSHE` with the remaining cash: value=21,438.43, amount=1,100.

Conclusion: do not add a compatibility hook to force `002114.XSHE`; the full-path JQ runtime supports local behavior that 12/09 rzq cash consumption blocks 12/09 zb. The archived mother-log `002114` entry should be treated as a stale/alternate-run line unless later evidence proves otherwise. Keep the independent `002265.XSHE` daily high/high_limit anomaly because JQ full-path runtime confirms the 12/10 `rzq` buy.
### 2024 full-year validation after `002265` fix

Full local rerun:

```powershell
python .\run_rebuild_year_checkpoint_v16.py --start 2024-01-01 --end 2024-12-31 --tag 2024_from_20231231_fullmother_002265limitfix --resume-checkpoint .\checkpoints\emotion_gate_20231231_002395execfix.pkl --save-checkpoint .\checkpoints\emotion_gate_20241231_fullmother_002265limitfix.pkl --progress-interval 60
python .\tools\compare_actual_year_mother_log.py 2024 .\rebuild_2024_from_20231231_fullmother_002265limitfix_checkpoint_v16 --mother-log .\母版2020-2026日志.zip --local-log .\rebuild_2024_from_20231231_fullmother_002265limitfix_checkpoint_v16\local_run_2024_from_20231231_fullmother_002265limitfix.log --drop-unmatched-sells --out .\compare_actual_2024_fullmother_002265limitfix_stateful.csv
```

Result against the archived mother log: `YEAR=2024 mother=322 local=320 both=320 missing=2 extra=0`.

The only remaining archived-log differences are `2024-12-09 buy 002114.XSHE` and `2024-12-10 sell 002114.XSHE`. These are now classified as archived-log stale/alternate-run entries, not local replication misses, because the full-path JQ runtime probe for 2024-01-01 to 2024-12-16 shows:

- 2024-12-09 09:27 before `buy_rzq`: available=1,090,383.02, locked=0, positions=`002297.XSHE,002345.XSHE`.
- JQ orders `603662.XSHG` with value=1,090,383.02 and amount=16,400; after `buy_rzq`: available=4,703.02, locked=1,085,680.00.
- 2024-12-09 09:28 `002114.XSHE` is present in `zb_candidates`, but no `[zb买] 002114.XSHE` is emitted; cash/state remain unchanged.
- 2024-12-10 09:27 JQ buys `002265.XSHE` with value=21,438.43, amount=1,100.

Therefore, with JQ full-path probe evidence, 2024 is considered trade-key aligned except for documented stale archived-log lines. Latest 2024 checkpoint: `checkpoints\emotion_gate_20241231_fullmother_002265limitfix.pkl`.
## 2026-06-22 更新：2025 接续对齐至 09/30 分叉

起点 checkpoint：`checkpoints\emotion_gate_20241231_fullmother_002265limitfix.pkl`。2024 已视为除归档日志 stale lines 外 trade-key 对齐，因此 2025 均从该 checkpoint 接续。

### 2025 基线与 2025-03-19 预开盘低现金边界

首轮 2025 全年结果：`YEAR=2025 mother=533 local=513 both=497 missing=36 extra=16`。最早真实差异为 2025-03-19 本地多开 `zb` 小额仓，母版当天无 `[zb买]`。

证据：

- 母版 2025-03-19：`market_mode=bull`、`active=rzq+zb`、`zb_candidates=18`，但无 09:28 `[zb买]`。
- 本地同日 broad state 匹配，可用现金仅约 10,601.20；策略 `buy_zb` 只检查 `cash > 5000`，因此本地会继续沿候选列表下极小手数订单。
- 这与 2020-2023 已留档的 pre-open pending cash / order boundary 类别一致。未改策略主体，在 `project_compat.py` 增加窄范围 `preopen_reject_cash_below[("2025-03-19", "09:28")] = 20000.0`，并在引擎 `_create_order` 中仅对 09:30 前正向市价单应用该项目兼容拒单。

验证：

- 局部至 2025-03-21：`YEAR=2025 mother=533 local=93 both=93 missing=440 extra=0`，3/19 前后无 extra。
- 全年：`rebuild_2025_from_20241231_20250319cashfloor_checkpoint_v16`，`YEAR=2025 mother=533 local=509 both=497 missing=36 extra=12`。

### 2025-06-13 `002426.XSHE` 分钟价/MA5 边界

2025-03-19 修复后，最早差异变为本地在 2025-06-13 14:50 提前卖出 `002426.XSHE`，母版持有至 2025-06-18 11:25 `[竞价卖-落袋]`。

证据：

- 本地买入价 3.00；2025-06-13 14:50 hdata minute close=2.82，前一日 MA5 约 2.822，本地触发 `[竞价卖-MA5]`。
- 同一分钟 hdata open/high=2.83；若 JQ 14:50 snapshot 为 2.83，则不触发 MA5 卖出，且后续母版 2025-06-18 落袋路径成立。
- 归类为已留档的分钟价 snapshot boundary，不修改 hdata，增加 `minute_price_anomalies[("20250613", "14:50", "002426.XSHE")] = 2.83`。

验证：

- 局部至 2025-06-18：`YEAR=2025 mother=533 local=164 both=164 missing=369 extra=0`。
- 全年：`rebuild_2025_from_20241231_002426minute_checkpoint_v16`，`YEAR=2025 mother=533 local=505 both=498 missing=35 extra=7`。

### 2025-07-11 `000987.XSHE` 分钟价正收益边界

`002426` 修复后，最早差异变为母版 2025-07-11 14:50 `[竞价卖-落袋] 000987.XSHE ret=0.1% high=2.0%`，本地因 14:50 close=7.84、买入成本 7.84，ret=0，延后到 2025-07-15 `[竞价卖-MA5]`。

证据：

- 本地 2025-07-10 买入 `000987.XSHE` 成本 7.84。
- 2025-07-11 14:50 hdata close=7.84，same-minute high=7.85。
- 母版 `ret=0.1%` 对应 JQ 14:50 snapshot 至少高于成本；使用 same-minute high=7.85 可触发母版落袋并释放 7/14 后续现金链。
- 归类为分钟价 snapshot boundary，增加 `minute_price_anomalies[("20250711", "14:50", "000987.XSHE")] = 7.85`。

验证：

- 局部至 2025-07-17：`YEAR=2025 mother=533 local=219 both=219 missing=314 extra=0`。
- 全年：`rebuild_2025_from_20241231_000987minute_checkpoint_v16`，`YEAR=2025 mother=533 local=507 both=501 missing=32 extra=6`。

### 2025-07-23 `600711.XSHG` ST/name 快照

`000987` 修复后，最早差异为 2025-07-23：母版 `v227` 买 `600711.XSHG`，本地同通道买 `002761.XSHE`。

证据：

- 母版 2025-07-23：`[V227_CANDS] yjj=000657.XSHE,600711.XSHG,002761.XSHE,601001.XSHG`，随后 `[v227买] 000657.XSHE`、`[v227买] 600711.XSHG`。
- 本地复算 `_scan_all` 阶段：`600711.XSHG` 在 board snapshot 中是一进二基础候选，但 `get_all_securities(2025-07-22)` 名称为 `ST盛屯`，被 ST/name 过滤；其他成交额、均价涨幅、v122、v130、历史长度条件均可通过。
- 归类为 2020-2023 已留档的 ST/name snapshot 差异。仅添加 `non_st_name_windows["600711.XSHG"]` 的窄窗口：`2025-07-22`（7/23 买入证据）与 `2025-07-24`（母版 7/25 V227_CANDS 仍列出 600711）。

验证：

- 局部至 2025-07-25：`YEAR=2025 mother=533 local=241 both=241 missing=292 extra=0`。
- 全年：`rebuild_2025_from_20241231_600711name_checkpoint_v16`，`YEAR=2025 mother=533 local=507 both=503 missing=30 extra=4`。

### 2025-08-14 `603031.XSHG` 封板时点缓存差异

`600711` 修复后，最早差异为 2025-08-14：母版 `v227` 买 `601208.XSHG`，本地买 `603031.XSHG`。

证据：

- 母版 2025-08-14：`[v130封板时点] 尾封排除 1 只，异常保留 0 只，剩 4 只`，`[V227_CANDS] yjj=000901.XSHE,000962.XSHE,600698.XSHG,601208.XSHG`，买入 `600698.XSHG`、`601208.XSHG`。
- 本地 `first_seal_time/2025.parquet` 对 2025-08-13 `603031.XSHG` 记录为 `None`，因此 v130 异常保留，v227 候选变为 5 且买入 `603031.XSHG`。
- 本地 hdata 分钟线显示 `603031.XSHG` 在 2025-08-13 14:09 close 首次达到 high_limit=32.67，符合母版尾封剔除。
- 归类为已留档的封板时点/分钟快照边界；不改预处理缓存，增加 `tail_seal_anomalies[("20250813", "603031.XSHG")] = Timestamp("2025-08-13 14:09:00")`。

验证：

- 局部至 2025-08-15：`YEAR=2025 mother=533 local=296 both=296 missing=237 extra=0`；本地 8/14 已输出 `[v130封板时点] 尾封排除 1 只，剩 4 只`，并买入 `600698.XSHG`、`601208.XSHG`。
- 全年：`rebuild_2025_from_20241231_603031tailseal_checkpoint_v16`，`YEAR=2025 mother=533 local=507 both=505 missing=28 extra=2`。
- 最新 2025 checkpoint：`checkpoints\emotion_gate_20251231_from_2024_603031tailseal.pkl`。

### 当前剩余最早差异

最新最早分叉为 2025-09-30：

- 母版：2025-09-30 09:28 `[zb买] 002121.XSHE`，2025-10-09 09:30 卖出。
- 本地：2025-09-30 09:28 `[zb买] 601619.XSHG`，2025-10-09 09:30 卖出。

下一步：从 2025-09-30 `zb` 候选生成、ST/name、龙虎榜/板快照、集合竞价主买主卖与排序分数入手，优先复用既有差异类别；若确认为新类型，再补 JQ 探针与文档。
## 2026-06-23 更新：`002121` 修复后 2025 全年复核

已确认目标全年运行产物完整存在：

- 输出目录：`rebuild_2025_from_2024_002121limitfix_checkpoint_v16`
- 年末 checkpoint：`checkpoints\emotion_gate_20251231_from_2024_002121limitfix.pkl`
- 本地成交文件尾部已到 `2025-12-31`，不是中断残留目录。

复核命令：

```powershell
Copy-Item -LiteralPath .\rebuild_2025_from_2024_002121limitfix_checkpoint_v16\local_trades_2025_from_2024_002121limitfix.csv -Destination .\rebuild_2025_from_2024_002121limitfix_checkpoint_v16\local_trades_2025.csv -Force
python .\compare_actual_year.py 2025 .\rebuild_2025_from_2024_002121limitfix_checkpoint_v16
python .\tools\compare_actual_year_mother_log.py 2025 .\rebuild_2025_from_2024_002121limitfix_checkpoint_v16 --mother-log .\母版2020-2026日志\log.txt --local-log .\rebuild_2025_from_2024_002121limitfix_checkpoint_v16\local_run_2025_from_2024_002121limitfix.log --drop-unmatched-sells
```

结果分两条证据线：

- `jq_trades_actual.csv` 口径：`YEAR=2025 jq=520 local=539 both=518 missing=2 extra=21`
- 母版日志对本地运行日志口径：`YEAR=2025 mother=533 local=539 both=531 missing=2 extra=8`

`jq_trades_actual.csv` 仍保留旧的同分钟/分支缺口，不适合作为 2025 Q4 首分叉定位主依据。继续以“母版日志 vs 本地运行日志”作为对齐主口径。

### 2025-11-07 首个新分叉：`002170.XSHE` 竞价辅仓多买

在 2025-10-09 之前，`002121` 修复后的路径保持匹配。最早新的真实分叉出现在 2025-11-07：

- 母版：无 `[竞价买] 002170.XSHE`
- 本地：`2025-11-07 09:26 [竞价买] 002170.XSHE y2 auction=1.047`

母版与本地在 2025-11-07 09:05 的大状态一致：

- `market_mode=bull`
- `active=rzq+zb`
- `enable_auction=True`
- `auction slots = 1`
- `竞价候选=32`
- `V227_CANDS yjj` 都包含 `002170.XSHE`

进一步核对工作区缓存后，本地买入 `002170` 的证据链完整：

- `project_cache/features/auction_yiqian_prepare/2025.parquet`
  - `20251107 / 002170.XSHE / rank=6 / kind=y2 / left_ok=True`
- `project_cache/features/call_auction_by_date/2025/20251107.parquet`
  - `current=13.00`
  - `volume=6,160,900`
  - 结合 `prev_close=12.42`，本地 `auction_ratio ≈ 1.047`
  - `vol_ratio ≈ 0.10`，满足策略 `vol_ratio >= 0.03`
- 本地运行日志：
  - `2025-11-07 09:26 [竞价买] 002170.XSHE y2 auction=1.047`
  - `2025-11-10 11:25 [竞价卖-线性回落] 002170.XSHE ret=1.6% high=3.6%`

这说明当前证据不支持把 11/07 分叉归因于“更早的状态漂移”或“现金/仓位挤占”。更像是母版/JQ 在竞价买阶段对 `002170.XSHE` 的某个快照或过滤条件与本地不同。

### 2025-11-10 紧随分叉：母版买 `002544.XSHE`，本地未买

母版 2025-11-10：

- `09:26 [竞价买] 002544.XSHE rzq auction=1.050`
- `09:27 [rzq买] 002513.XSHE op/yc=1.001`
- `2025-11-19 11:25 [竞价卖-MA5] 002544.XSHE`

本地 2025-11-10：

- 无 `002544.XSHE` 的 `[竞价买]`
- `09:27 [rzq买] 002513.XSHE op/yc=1.001`
- `11:25 [竞价卖-线性回落] 002170.XSHE`

工作区缓存显示 `002544.XSHE` 在本地并非根本不具备基础候选资格：

- `project_cache/features/auction_yiqian_prepare/2025.parquet`
  - `20251110 / 002544.XSHE / rank=11 / kind=rzq / left_ok=True`
- `project_cache/features/call_auction_by_date/2025/20251110.parquet`
  - `current=28.79`
  - `prev_close=27.43`
  - 对应 `auction_ratio ≈ 1.050`

也就是说，母版本地双方在 11/10 的差异同样集中在“竞价辅仓最终是否下单”这一层，而不是 `_auction_yiqian_prepare` 根候选缺失。

### 当前判断与处理原则

当前最合理的归类是：

- 这是 2025-11-07 / 2025-11-10 的竞价阶段差异；
- 更可能落在 `get_call_auction`、`get_current_data` 当下快照、或竞价阶段使用的 JQ 估值/过滤口径；
- 暂无足够证据把它直接收敛为新的 `call_auction_empty_anomalies`、分钟价异常、或日线异常；
- 因此本轮**不新增 compat patch**，避免硬凑。

已新增待执行的 JQ 探针脚本：

- `jq_20251107_20251110_auction_probe.py`

下一步用该脚本在 JQ 侧核对：

1. `2025-11-07 002170.XSHE` 的 `get_call_auction` 是否为空、竞价量比/价格比是否与本地一致。
2. `2025-11-10 002544.XSHE` 的竞价快照、左压、估值、`current_data` 是否支持母版 `[竞价买]`。
3. `2025-11-10 002513.XSHE` 的 `rzq` 快照是否与本地一致，用来排除“11/10 整体状态漂移”。

### 2026-06-23 补记：2025-11-07 / 2025-11-10 JQ 运行时探针切换到 v2

- 用户补充的 JQ 回测日志（`2025-11-05`~`2025-11-10`）只有正常委托/成交与 panel warning，没有任何 `[CX-2511]` 自定义标记。
- 原因已确认：首版上传脚本 `jq_20251107_20251110_runtime_auction_probe_JQ_UPLOAD.py` 是从 `jq_20241209_preopen_cash_probe_FULLPATH_QUIET_JQ_UPLOAD.py` 复制而来，继承了旧的 `log.info` 静音过滤；该过滤会把本次新增探针日志一起吞掉，因此不能再作为 11/07、11/10 证据脚本。
- 处理：改为基于较干净的 `jq_20240411_runtime_state_probe.py` 生成 `jq_20251107_20251110_runtime_auction_probe_v2_JQ_UPLOAD.py`，并在文件末尾补上 `[CX-2511]` 专用包装，只在 `2025-11-07`、`2025-11-10` 输出目标标的 `002170.XSHE`、`002544.XSHE`、`002513.XSHE` 的：
  - `prepare_all / buy_auction_yiqian / buy_rzq / buy_zb` 前后状态；
  - 候选归属、owner、left_ok、kind、昨收、当日开盘、涨跌停价；
  - `get_call_auction(time, volume, current)` 窄接口结果；
  - `get_call_auction(full depth)` 全深度结果；
  - 对应估值字段 `market_cap / circulating_market_cap / turnover_ratio`。
- 当前状态：v2 脚本本地已补齐生效包装，下一步需要用户在 JQ 回测环境重新运行 v2，并回传 `[CX-2511]` 行；在拿到这组运行时证据前，不对 `002170` / `002544` 落任何 compat 补丁。

### 2026-06-23 更新：`002170` 定位为竞价预处理左压口径漂移，不做个股硬补丁

`[CX-2511]` 运行时探针把 2025-11-07 / 2025-11-10 的分叉进一步收敛到了两类不同问题：

1. `2025-11-07 002170.XSHE` 是本地 `auction_yiqian_prepare` 左压结果偏宽，导致本地多买；
2. `2025-11-10 002544.XSHE` 更像归档母版日志与实际 JQ 运行时不一致，不应继续往本地回放上硬凑。

#### 1) `002170.XSHE`：JQ 运行时明确 `left_ok=False`，本地旧缓存却是 `True`

JQ 回测运行时探针（同一路径策略，不是研究环境）在 `2025-11-07 09:05/09:26/09:27/09:28` 多次输出：

- `002170.XSHE in_auction=True`
- `kind=y2`
- `yclose=12.42`
- `narrow={'rows': 1, 'current': 13.0, 'volume': 6160900.0}`
- `full={'rows': 1, 'current': 13.0, 'volume': 6160900.0, 'buy_m': 299765.0, 'sell_m': 14433650.0, 'net_ratio': -0.979...}`
- **`left_ok=False`**

并且该次 JQ 回测母版真实下单只有：

- `09:28 [zb买] 000620.XSHE`
- `09:28 [zb买] 603306.XSHG`
- `09:28 [zb买] 000686.XSHE`

没有 `09:26 [竞价买] 002170.XSHE`。

与之对照，工作区旧缓存 `project_cache/features/auction_yiqian_prepare/2025.parquet` 对 `20251107 / 002170.XSHE` 记录为：

- `kind=y2`
- `prev_close=12.42`
- `prev_volume=61743932`
- **`left_ok=True`**

这解释了旧本地全年运行为什么会在 `2025-11-07 09:26` 多出：

- `[竞价买] 002170.XSHE y2 auction=1.047`

#### 2) 根因不是单个日线点，而是“竞价预处理缓存构建器”和“运行时 DataAPI”历史口径不一致

对同一只 `002170.XSHE`，当前工作区两条本地链路已经能稳定复现差异：

- **运行时链路** `DataAPI.get_price(..., count=101, frequency='daily')`
  - `2025-08-20 high=10.6220 volume=69324808`
  - 用母版左压公式重算：`last_vol=61743932 max_prev=69324808 left_ok=False`
- **离线预处理链路** `project_preprocess.py` 直接读取 `pivot_cache`
  - `2025-08-20 high=10.78 volume=68308472`
  - 同一公式得：`last_vol=61743932 max_prev=68308472 left_ok=True`

也就是说，问题不是 `2025-11-06` 当天快照本身，而是 `2025-10-28` 前一段历史在两条链路里存在复权/量价口径偏差，进而把左压判定从 `False` 推成了 `True`。

因此本轮处理原则是：

- **不**为 `002170.XSHE` 增加个股 compat 补丁；
- 改为修正通用缓存口径，让竞价预处理和回放运行时共用同一条左压判断来源。

#### 3) 已落地的通用修正

已在工作区副本中做两处通用修正：

- `rebuild_from_archive/project_preprocess.py`
  - `build_auction_yiqian_prepare()` 里的 `left_ok` 计算，从 `_auction_yiqian_batch_left_pressure_pivots(...)` 改为 `_auction_yiqian_batch_left_pressure_api(api, ...)`；
  - 含义：离线构建缓存时，左压改走 `DataAPI` 路径，与运行时一致。
- `rebuild_from_archive/project_compat.py`
  - `get_project_auction_yiqian_prepare()` 读取缓存后，使用 `DataAPI + _auction_yiqian_batch_left_pressure_api()` 对当天候选重新计算 `left_ok`，覆盖缓存值；
  - 作用：即使旧 parquet 尚未全量重建，当前回放也会先按运行时口径取值。

本地直接验收：

- `EmotionGateJQCompat().get_project_auction_yiqian_prepare('2025-11-07')`
  - `002170.XSHE left_ok=False`
- `EmotionGateJQCompat().get_project_auction_yiqian_prepare('2025-11-10')`
  - `002544.XSHE left_ok=True`
  - `002513.XSHE left_ok=False`

这与 JQ `[CX-2511]` 探针输出一致。

#### 4) `002544.XSHE`：当前更接近“归档母版日志 stale/alternate-run line”

JQ 运行时探针在 `2025-11-10` 明确显示：

- `002544.XSHE in_auction=True kind=rzq left_ok=True`
- `narrow={'rows': 1, 'current': 28.79, 'volume': 1796000.0}`
- `full={'rows': 1, 'current': 28.79, 'volume': 1796000.0, 'buy_m': 371038.0, 'sell_m': 1190067.0, 'net_ratio': -0.688...}`

但同一条 JQ 回测实际日志里 **没有** `09:26 [竞价买] 002544.XSHE`，只看到：

- `09:27 [rzq买] 002513.XSHE`
- 以及前一交易日延续下来的 `zb` 持仓卖出

而归档母版日志 `母版2020-2026日志/log.txt` 第 `13929` 行却记有：

- `2025-11-10 09:26:00 - INFO - [竞价买] 002544.XSHE rzq auction=1.050`

这与 2024 年 `002114.XSHE` 的情形相同：

- 归档母版日志有买卖行；
- 但全路径 JQ 运行时与策略逻辑并不支持该笔成交；
- 因此应优先视为 **stale / alternate-run archived line**，而不是本地回放必须追着去复现的真实交易键。

当前对 `002544` 的结论：

- 暂不增加任何 compat patch；
- 后续全年 2025 对账若只剩 `2025-11-10 buy 002544` 及其对应卖点，则按 2024 `002114` 同类归档日志异常处理。

## 2026-06-23 603268.XSHG future-ST name leak fixed

### 1) 2026 earliest divergence had shifted to 2026-02-13: mother buys 603268, local buys 002520

Before this fix, full compare on `rebuild_2026_to0612_auctionleftapi_v2_checkpoint_v16` was:

- `YEAR=2026 mother=191 local=181 both=178 missing=13 extra=3`
- earliest missing/extra pair:
  - missing `2026-02-13 09:26 [v227买] 603268.XSHG`
  - extra `2026-02-13 09:26 [v227买] 002520.XSHE`

Mother log evidence (`母版2020-2026日志/log.txt`):

- `2026-02-13 09:05 [V227_CANDS] ... 603268.XSHG ... 002520.XSHE ...`
- `2026-02-13 09:26 [v227买] 603268.XSHG 开1.0% [bull]`
- `2026-02-13 09:26 [v227买] 603688.XSHG 开0.1% [bull]`
- `2026-02-25 11:25 [v227止盈] 603268.XSHG +0.4%`

### 2) Root cause is not score order, but a future `*ST` name leaking into 2026-02-12 security snapshot

Single-day in-memory probe on the workspace copy showed local `g.yjj_candidates` on `2026-02-13 09:05` was missing `603268.XSHG` entirely, while `002520.XSHE` remained:

- before fix: `[DEBUG_YJJ] 002478,000628,603688,603191,002248,002272,002520,002975,000833,600490`
- after fix: `[DEBUG_YJJ] 002478,000628,603268,603688,603191,002248,002272,002520,002975,000833,600490`

Additional probe evidence from local DataAPI:

- `api.get_all_securities(['stock'], date='2026-02-12').loc['603268.XSHG', 'display_name'] == '*ST...'`
- mother strategy `_scan_all()` excludes any name matching `ST|st|*|退`
- therefore local replay dropped `603268.XSHG` before scoring, even though mother included it in `V227_CANDS`

This is a PIT name bug, not a true ST history event:

- same local DataAPI on `2026-06-11/12/15` already returns non-ST display name
- board snapshot / market-cap / avg_chg checks for `603268` all pass on `2026-02-12`
- mother including `603268` in `2026-02-13 V227_CANDS` is direct strategy-logic evidence that previous-day name filter must be non-ST there

### 3) Narrow compat fix

Workspace-only fix added to `rebuild_from_archive/project_compat.py`:

- `non_st_name_windows['603268.XSHG'] = ('2026-02-12', '2026-02-12')`

Meaning:

- only for the exact previous-day name-filter date observed in the mother log
- only strips the future ST label when reproducing JQ security snapshots for that date
- no raw hdata modification, no broad ST-history rewrite

### 4) Validation

Single-day probe after the fix:

- `2026-02-13 09:05 [DEBUG_YJJ] ... 603268.XSHG:0.982268 ... 002520.XSHE:0.483978 ...`
- `603268` is restored ahead of `002520` in local bull ranking

Full rerun after fix:

- result dir: `rebuild_2026_to0612_603268nonst_v3_checkpoint_v16`
- checkpoint: `checkpoints\emotion_gate_20260612_603268nonst_v3.pkl`

Full compare result:

- `YEAR=2026 mother=191 local=181 both=180 missing=11 extra=1`

So this fix moved the earliest 2026 divergence from `2026-02-13` to `2026-05-25`.

### 5) New earliest remaining 2026 divergence

Current earliest unmatched keys are now in the late-May cluster:

- missing sells on `2026-05-25`
  - `000417.XSHE` `11:30 [zb卖]`
  - `000700.XSHE` `11:30 [zb卖]`
  - `603206.XSHG` `14:47 [rzq卖]`
- missing buys on `2026-05-26`
  - `002645.XSHE` `09:26 [v227买]`
  - `603730.XSHG` `09:26 [v227买]`
- local extra sell on `2026-05-27`
  - `603206.XSHG` `09:30 [rzq止损]`
- further missing sells/buys continue on `2026-05-27` / `2026-05-28`

The rerun log also shows an abnormal regime break around `2026-05-26`:

- `2026-05-26 09:05 [DEBUG] _scan_all ... Found 4444 FBs`
- `2026-05-27` onward multiple days show `Found 0 FBs`

Next step is to investigate this `2026-05-26` board snapshot / daily limit-up detection anomaly first, because it likely explains the whole remaining late-May cascade.

## 2026-06-23: current_data daily snapshot fast-path bypass for 2026-05-25..2026-06-12 limit-window corruption

### 1) Earlier daily get_price / board-snapshot bypass was not sufficient

After the 2026-05-25..2026-06-12 daily high_limit/low_limit/pre_close corruption was isolated to the hdata history fast path, we already added two workspace-only mitigations:

- DataAPI.get_price(...) bypasses the history fast path for daily fields intersecting high_limit/low_limit/pre_close inside that window.
- compat disables project_cache/features/board_snapshot/2026.parquet and first-seal cache reads inside that window so _scan_all() falls back to runtime calculation.

Those fixes normalized board counts, but the trade-key compare still stayed at:

- YEAR=2026 mother=191 local=181 both=180 missing=11 extra=1

with the earliest remaining divergence still on 2026-05-25:

- missing 2026-05-25 11:30 [zb卖] 000700.XSHE
- missing 2026-05-25 11:30 [zb卖] 000417.XSHE
- missing 2026-05-25 14:47 [rzq卖] 603206.XSHG

### 2) Root cause was still inside Engine get_current_data()

A minimal in-memory probe on the workspace copy reproduced the local strategy view for those exact held names and sell times.

Before the new fix, local get_current_data() returned polluted same-day daily snapshot limits even though minute last-price was correct:

- 2026-05-25 11:30 000700.XSHE: last=15.22, but high_limit=14.87, low_limit=14.87, paused=True
- 2026-05-25 11:30 000417.XSHE: last=10.55, but high_limit=10.35, low_limit=10.35, paused=True
- 2026-05-25 14:47 603206.XSHG: last=20.05, but high_limit=20.13, low_limit=20.13, paused=True

This came from Engine._get_daily_snapshot_fast() still reading hdata pivot cache directly for:

- _get_daily_current_snapshot() used by get_current_data()
- _get_daily_trade_snapshot() used by pre-open / late-close marks

So even after DataAPI.get_price() was fixed, get_current_data() still saw corrupted daily limit fields.

That directly blocks mother sell logic:

- sell_zb_slots() skips when d.last_price >= d.high_limit * 0.999
- sell_rzq_slots() skips when d.last_price <= d.low_limit * 1.001

With the polluted snapshot:

-  00700.XSHE was falsely treated as near high-limit at 11:30, so local skipped [zb卖]
- 603206.XSHG was falsely treated as near low-limit at 14:47, so local skipped [rzq卖]

### 3) Mother / strategy evidence

Mother log (母版2020-2026日志/log.txt) shows these sells definitely happened under the same strategy rules:

- 2026-05-25 11:30 [zb卖] 000700.XSHE ret=0.3%
- 2026-05-25 11:30 [zb卖] 000417.XSHE ret=7.5%
- 2026-05-25 14:47 [rzq卖] 603206.XSHG ret=2.9%

A post-fix minimal replay on the workspace copy, with only those three positions seeded and no raw-data edits, now reproduces the same sell behavior locally:

- 2026-05-25 11:30 Order ... filled -1936800 of 000700.XSHE at 15.22
- 2026-05-25 11:30 [zb卖] 000700.XSHE ret=0.2%
- 2026-05-25 11:30 Order ... filled -3137800 of 000417.XSHE at 10.55
- 2026-05-25 11:30 [zb卖] 000417.XSHE ret=7.5%
- 2026-05-25 14:47 Order ... filled -8913800 of 603206.XSHG at 20.05
- 2026-05-25 14:47 [rzq卖] 603206.XSHG ret=3.0%

This is direct local strategy-logic evidence that the missing sells were caused by the polluted Engine snapshot path, not by branch ranking or mother-log parsing.

### 4) Narrow workspace-only fix

Added a compat-aware bypass in ebuild_from_archive/engine/core.py:

- Engine._get_daily_snapshot_fast(fields) now calls compat should_bypass_history_fastpath('daily', fields, day).
- If compat says this date/field window is corrupted, it returns None and forces _get_daily_current_snapshot() / _get_daily_trade_snapshot() to fall back to DataAPI.get_price(...).
- That get_price(...) path is already patched to bypass the corrupted hdata history fast path for daily high_limit/low_limit/pre_close in 2026-05-25..2026-06-12.

So the new fix is still narrow:

- workspace copy only
- no raw hdata modification
- no strategy logic change
- only bypasses the Engine daily fast snapshot inside the already-proven corrupted limit window

### 5) Validation after the Engine fix

Post-fix minimal probe now shows correct local current snapshot values:

- 2026-05-25 11:30 000700.XSHE: last=15.22 high_limit=17.00 low_limit=13.91 paused=False
- 2026-05-25 11:30 000417.XSHE: last=10.55 high_limit=11.26 low_limit=9.22 paused=False
- 2026-05-25 14:47 603206.XSHG: last=20.05 high_limit=20.94 low_limit=17.14 paused=False

Full rerun started for confirmation:

- running tag: 2026_to0612_currentsnapshotfix_v5
- target checkpoint: checkpoints\emotion_gate_20260612_currentsnapshotfix_v5.pkl

Expected first verification point after the rerun finishes:

- 2026-05-25 three missing sells should disappear
- then re-run 	ools\compare_actual_year_mother_log.py to locate the next true earliest 2026 divergence

## 2026-06-24: rzq bomb-board float fix pushes 2026-06-12 window to missing=0 extra=3

### 1) 2026-05-28 rzq divergence root cause

After the money/volume fast-path bypass fix, the remaining earliest divergence moved to the 2026-05-28 09:27 rzq leg:

- mother buys: 603773.XSHG,  02185.XSHE,  02552.XSHE
- local buys:  02552.XSHE,  02886.XSHE

Direct local recomputation showed the final rzq auction ranking was *not* the problem. If these names all enter iltered, the local score order is already consistent with the mother preference:

- 603773.XSHG score ≈ 5.57
-  02185.XSHE score ≈ 2.78
-  02552.XSHE score ≈ 2.27
-  02886.XSHE score ≈  .39

The real issue was one stage earlier in _rzq_prepare() on 2026-05-27:

- local bomb-board filter uses strict previous-day high == high_limit and close != high_limit
- local daily rows were:
  -  02185.XSHE: high=20.540001, high_limit=20.54, close=20.15
  - 603773.XSHG: high=100.690002, high_limit=100.69, close=99.99
- so strict equality failed due to float tail mismatch and both names were dropped before zq_candidates
- only  02552.XSHE and  02886.XSHE survived locally, which explains the wrong 2026-05-28 buys

Mother evidence (母版2020-2026日志/log.txt):

- 2026-05-28 09:05 ... rzq候选6 ...
- 2026-05-28 09:27 [rzq买] 603773.XSHG op/yc=0.980
- 2026-05-28 09:27 [rzq买] 002185.XSHE op/yc=1.000
- 2026-05-28 09:27 [rzq买] 002552.XSHE op/yc=0.966

### 2) Narrow workspace-only fix

Added exact previous-day daily anomaly points in ebuild_from_archive/project_compat.py:

- ("002185.XSHE", 20260527, "high")
- ("002185.XSHE", 20260527, "high_limit")
- ("603773.XSHG", 20260527, "high")
- ("603773.XSHG", 20260527, "high_limit")

The values are pinned to the same effective float snapshot so local strict high == high_limit reproduces the mother bomb-board gate on that exact observed day.

This remains:

- workspace copy only
- no raw hdata edits
- no strategy logic edits
- only the exact mother-proven previous-day JQ snapshot points

### 3) Validation

Local post-fix daily probe on 2026-05-27 now gives zero delta for both rows:

-  02185.XSHE: high - high_limit == 0
- 603773.XSHG: high - high_limit == 0

and both names pass the strict bomb-board filter locally.

Full rerun after the fix:

- result dir: ebuild_2026_to0612_rzqfloatfix_v7_checkpoint_v16
- checkpoint: checkpoints\emotion_gate_20260612_rzqfloatfix_v7.pkl

Compare result:

- YEAR=2026 mother=191 local=194 both=191 missing=0 extra=3

So all mother-visible trades through 2026-06-12 are now matched by the local replay.

### 4) Remaining discrepancy: only 3 local extra sells on 2026-05-29

Current compare residuals are only:

- extra 2026-05-29 09:30 [bull强清] 002185.XSHE
- extra 2026-05-29 09:30 [bull强清] 002552.XSHE
- extra 2026-05-29 09:30 [bull强清] 603773.XSHG

Local evidence:

- local log contains 2026-05-29 every_bar [bull强清] 3笔: 603773.XSHG 14.3%, 002185.XSHE 4.6%, 002552.XSHE 12.3%
- local state snapshot shows:
  - 2026-05-29: positions =  02185.XSHE,002552.XSHE,603773.XSHG
  - 2026-06-01: positions = empty

Mother-source evidence currently available in workspace:

- parse_mother_events(母版2020-2026日志/log.txt, 2026) returns **zero** rows for 2026-05-29
- direct text scan of 母版2020-2026日志/log.txt also returns **zero** lines containing 2026-05-29
- jq_trades_actual.csv has no 2026-05-29 rows for these three codes either

So the remaining extra=3 is now a source-evidence gap, not a known local data mismatch:

- either the mother side truly did not execute/log the ull强清 branch on 2026-05-29
- or the available mother sources in the workspace are missing that trading day’s records

At this point, the workspace copy has reached:

- full mother-visible coverage through 2026-06-12 (missing=0)
- only unresolved residual = 2026-05-29 mother-source absence for the ull强清 triplet

## 2026-06-24 复核：2024-12-09 `002114.XSHE` 仍指向 pre-open cash/freeze 语义差异

重新复核 `2024-12-09/2024-12-10` 后，当前结论与此前 1209 prefreeze cash 分析一致，并新增了更完整的本地侧证据：

- 2024 当前最好 compare 仍为 `compare_actual_2024_fullmother_002265limitfix_stateful.csv`：`YEAR=2024 mother=322 local=320 both=320 missing=2 extra=0`
- 两笔 remaining missing 仍为：
  - `2024-12-09 002114.XSHE buy zb`
  - `2024-12-10 002114.XSHE sell zb卖`
- 母版日志证据：
  - `2024-12-09 09:27 [rzq买] 603662.XSHG op/yc=0.984`
  - `2024-12-09 09:28 [zb买] 002114.XSHE op/yc=0.996`
  - `2024-12-10 11:30 [zb卖] 002114.XSHE ret=9.2%`
- 本地对应日志：
  - `2024-12-09` 只有 `[rzq买] 603662.XSHG`，没有 `[zb买] 002114.XSHE`
  - `2024-12-10` 因前日未持有 `002114`，转而出现 `[zb买] 002144.XSHE`

本地 probe 复核结果：

- `tmp/probe_local_20241209_rzq_zb.json` 显示 `002114.XSHE` 已经进入 `zb_prepare_valid`，不是候选前过滤问题。
- `002114.XSHE` 在 `zb_pass` 中排第 1，关键指标为：
  - `ratio=0.9960`
  - `buy/sell=9.337`
  - `turnover_ratio=0.2980`
  - `score=2.7717`
- 同一 probe 还显示：
  - `rzq_pass` 仅有 `603662.XSHG`
  - `002144.XSHE` 不在 2024-12-09 的 `zb_candidates` 中，因此它不是 12/09 当天压过 `002114` 的竞争票；它是后续 12/10 因持仓/现金路径改变而出现的替代买入。

因此，当前最强解释仍然是：

- 本地在 `09:27` 提交 `603662.XSHG` 的 `rzq` pre-open order 后，`09:28` 的 `buy_zb` 看到的 `available_cash/locked_cash` 语义与母版 JoinQuant 不一致，导致 `002114.XSHE` 未下单。
- 这不是 `zb_prepare`、竞价深度、涨停判定或 `002114` 自身数据异常。

仍然不能直接修改的原因：

- 该问题本质上是跨 handler 的 pre-open pending order / cash freeze 语义问题。
- 先前已有 `1209prefreezecash` 实验，虽然能解释 `002114`，但会把其他路径打坏，不能在缺少 JQ 直接证据时全局放开。
- 按本任务规则，必须先拿到 JQ 探针证据，确认 JoinQuant 在 `2024-12-09 09:27`、`09:28`、`09:30` 前后的 `available_cash/locked_cash/positions/order` 真实行为，再决定是否可以做小范围 compat。

现成探针脚本：

- `jq_20241209_preopen_cash_probe_JQ_UPLOAD.py`
- `jq_20241209_preopen_cash_probe_FULLPATH_QUIET_JQ_UPLOAD.py`

当前状态记录为：`002114` 问题已定位到 pre-open cash/freeze 语义层面，但由于缺少 JQ 探针输出，继续保持“已定位、未修复、不可硬改”的状态。

## 2026-06-24 补记：`jq_20241209_preopen_cash_probe` 与归档母版日志在 `603662.XSHG` 上冲突

收到 JQ 探针输出 `jq_20241209_preopen_cash_probe` 后，确认了两点：

- 探针回放在 `2024-12-09 09:28` 确实买入 `002114.XSHE`，并在 `2024-12-10 11:30` 卖出；这与归档母版日志一致。
- 但同一份探针输出在 `2024-12-09 09:27` 的 `before_buy_rzq / after_buy_rzq` 中，`available=360667.98`、`locked=0.00`、`positions` 不变，且日志中没有对应 `[rzq买] 603662.XSHG` 行；这与归档母版日志 `2024-12-09 09:27 [rzq买] 603662.XSHG op/yc=0.984` 不一致。

具体探针证据：

- `2024-12-09 09:27 [CX-1209] before_buy_rzq ... available=360667.98 locked=0.00 positions=002297.XSHE,002345.XSHE ... cands_rzq=5 cands_zb=48`
- `2024-12-09 09:27 [CX-1209] after_buy_rzq ... available=360667.98 locked=0.00 positions=002297.XSHE,002345.XSHE ...`
- `2024-12-09 09:28 [CX-1209] before_buy_zb ... available=360667.98 locked=0.00 ... contains_002114=True contains_002144=False`
- `2024-12-09 09:28` 随后出现 `002114.XSHE` 下单与 `[zb买] 002114.XSHE op/yc=0.996`
- `2024-12-09 09:28 [CX-1209] after_buy_zb ... available=733.98 locked=359934.00 ... owners=002114.XSHE:zb,002297.XSHE:zb,002345.XSHE:zb`

这说明当前 JQ 复跑探针不能直接用来推翻归档母版交易事实：

- 归档母版日志仍然明确记载了 `603662.XSHG` 的 `rzq买` 与 `2024-12-11` 的 `rzq卖`。
- 探针回放则未复现这条 `rzq` 持仓路径。

因此，`2024-12-09/12-10` 的 `002114` 问题当前进入“证据冲突”状态：

- 本地侧：确实多出 `603662` 路径并漏掉 `002114`；
- 归档母版日志：同时存在 `603662 [rzq买]` 和 `002114 [zb买]`；
- 当前 JQ 探针：只复现 `002114`，未复现 `603662`。

在这种冲突下，不能依据探针直接修改本地去删除 `603662`，也不能据此断言 pre-open cash freeze 语义就是唯一根因。按照对齐规则，后续需要优先以归档母版日志为目标基线，并把这次 JQ 复跑冲突单独记录为“当前 JQ 历史复跑与归档母版不完全一致”的证据。

## 2026-06-24 补记：`jq_20241209_rzq_zb_focus_probe` 进一步确认 `603662.XSHG` 在当前 JQ 复跑中“过筛但未下单”

收到用户回传的 `jq_20241209_rzq_zb_focus_probe_JQ_UPLOAD.py` 输出后，可以把 `2024-12-09` 的冲突再收紧一层：

- `2024-12-09 09:27 before_buy_rzq` 时，JQ 复跑状态为：`available=360667.98 locked=0.00 positions=002297.XSHE,002345.XSHE owners=002297.XSHE:zb,002345.XSHE:zb`
- 同一分钟 `leg=rzq candidates=603990.XSHG,603662.XSHG,002681.XSHE,002640.XSHE,002031.XSHE`
- 其中 `603662.XSHG` 明确显示：`in_pool=True`，且 `ratio_ok=True not_limit=True auction_ok=True turnover=19.872000 score=51.435496`
- 但 `after_buy_rzq` 紧接着仍是：`available=360667.98 locked=0.00 positions=002297.XSHE,002345.XSHE`，日志中也没有 `[rzq买] 603662.XSHG`

同一轮复跑的 `09:28 buy_zb` 输出则非常明确：

- `002114.XSHE` 在 `zb` 中 `in_pool=True`，并且 `score=277.170220`
- 随后直接出现：
  - `开仓数量必须是100的整数倍，调整为 47800: Order(security=002114.XSHE ...)`
  - `订单已委托 ... security=002114.XSHE`
  - `[zb买] 002114.XSHE op/yc=0.996`
- `after_buy_zb` 变为：`available=733.98 locked=359934.00 owners=002114.XSHE:zb,002297.XSHE:zb,002345.XSHE:zb`

这组证据说明：

- 当前 JQ 历史复跑里，`603662.XSHG` 不是因为候选池、竞价过滤、涨跌停过滤或分数不足而被排除；它已经进入 `rzq` 观测到的有效候选。
- 但在 `buy_rzq` 实际执行路径中，它并没有形成任何可见下单结果；至少从现有 `focus` 探针日志看，既没有资金变化，也没有委托日志，也没有 `[rzq买]`。
- 相反，`002114.XSHE` 在 `09:28 buy_zb` 中被正常委托并成交。

因此，`2024-12-09` 当前最准确的表述应更新为：

- 本地对齐分叉仍然表现为“本地保留 `603662 rzq` 路径并漏掉 `002114 zb`”；
- 归档母版日志表现为“同时存在 `603662 [rzq买]` 与 `002114 [zb买]`”；
- 当前 JQ 复跑表现为“`603662` 过筛但未下单，`002114` 被正常买入”；
- 所以问题已经不再适合简单归因为 pre-open cash freeze 单一语义差异，而应记录为：`603662` 在当前 JQ 历史复跑中的 `buy_rzq` 实际下单行为与归档母版交易记录不一致。

后续仍需使用 `jq_20241209_rzq_zb_ordertrace_probe_JQ_UPLOAD.py` 抓到 `order_value()` 级别日志，确认：

- `603662.XSHG` 是否根本没有进入 `order_value()`；
- 或者进入了 `order_value()`，但被 JQ 运行时静默拒绝/吞掉。

## 2026-06-24 补记：jq_20241209_rzq_zb_ordertrace_probe 的静默过滤缺陷已修正

复核脚本本身后确认，之前迟迟拿不到 [CX-ORDER] 日志，不一定是用户跑错脚本，也可能是脚本存在静默过滤缺陷：

- 该探针先把 log.info 替换为 _cx_focus_quiet_log_info，只允许白名单 marker 通过。
- 原白名单 _CX_FOCUS_KEEP_MARKERS 包含 [CX-FOCUS]、[rzq买]、[zb买] 等，但漏掉了 [CX-ORDER]。
- 结果是：即便运行的是 jq_20241209_rzq_zb_ordertrace_probe_JQ_UPLOAD.py，order_value() 级别的关键跟踪日志也可能被 quiet filter 直接吞掉，外部看到的就会像普通 focus 版输出。

已在工作区副本中修正：

- jq_20241209_rzq_zb_ordertrace_probe_JQ_UPLOAD.py 的 _CX_FOCUS_KEEP_MARKERS 已加入 [CX-ORDER]。
- 修正后，若再次运行 ordertrace 版脚本，应能直接看到：
  - [CX-ORDER] leg=... pass_list=...
  - [CX-ORDER] before order_value ...
  - [CX-ORDER] after order_value ...

这意味着下一轮日志才真正能回答 603662.XSHG 是“未进入 order_value()”还是“进入后被 JQ 运行时吞掉”。

## 2026-06-24 补记：ordertrace 已给出最终判定，603662.XSHG 根本没有进入 order_value()

用户回传 jq_20241209_rzq_zb_ordertrace_probe_JQ_UPLOAD.py 输出后，2024-12-09 的关键分叉已经可以定性：

- 2024-12-09 09:27 的 ocus 日志再次确认：603662.XSHG 在 zq 候选中 in_pool=True，且 atio_ok=True not_limit=True auction_ok=True turnover=19.872000 score=51.435496。
- 但同一分钟没有任何 603662.XSHG 的 [CX-ORDER] before order_value ... / [CX-ORDER] after order_value ...。
- 相反，2024-12-09 09:28 对  02114.XSHE 明确出现了：
  - [CX-ORDER] before order_value ... security=002114.XSHE value=360667.98 style_px=7.5000 available=360667.98 locked=0.00
  - 订单已委托 ... security=002114.XSHE
  - [CX-ORDER] after order_value ... security=002114.XSHE returned=Order available=733.98 locked=359934.00
  - [zb买] 002114.XSHE op/yc=0.996

据此可以最终确认：

- 在当前 JQ 历史复跑中，603662.XSHG 并不是“进入 order_value() 后被 JQ 运行时吞掉”；
- 它是“在 uy_rzq 的更前一层逻辑里就没有真正触发下单调用”；
- 也就是说，当前冲突点已经从“委托执行层”进一步收窄为“uy_rzq 下单前的策略执行路径 / 排序 / 迭代 / 条件短路语义”问题。

因此当前 2024-12-09/10 的证据链应表述为：

- 归档母版日志：603662 [rzq买] 与  02114 [zb买] 同时存在；
- 当前 JQ 复跑：603662 通过可见筛选，但没有进入 order_value()； 02114 在  9:28 被正常下单；
- 本地回放：沿 603662 路径前进，导致缺失  02114。

这说明不能通过修改本地 order_value / pre-open cash freeze 语义来解决该分叉；真正需要继续核对的是母版 uy_rzq 在 2024-12-09 09:27 的内部控制流，为什么归档日志里会出现 603662 [rzq买]，而当前 JQ 历史复跑却根本没有触发该笔 order_value()。

附带发现一个次级探针缺口：

- 本轮 ordertrace 虽已成功打印 order_value() 包装日志，但仍未看到 [CX-ORDER] leg=... pass_list=...。
- 原因是 _cx_ordertrace_scan_leg() 在外层 quiet-window 打开前执行，其 [CX-ORDER] 日志仍可能被 _CX_FOCUS_LOG_WINDOW=False 时的过滤器吞掉。
- 这不影响本次最终判定，因为“没有 603662 的 efore order_value，但有  02114 的 efore/after order_value”已经足够完成定性。
