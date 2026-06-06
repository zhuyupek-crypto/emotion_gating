# 项目内预处理库路线图：情绪门控回测加速

背景：2020 已按 DCA 口径对齐，`jq=395 local=395 both=395 jq_only=0 local_only=0`。当前 v16 全年耗时约 21-22 分钟，profile 显示主要时间消耗在运行时重复构造日截面候选特征，而不是撮合。

数据管理员判断这些特征过于项目个性化，因此后续优先在本项目内维护预处理库：`project_cache/features/...`。hdata 原始数据继续只读使用，不在 `D:\work space\hdata` 内写入项目专用特征。

## 1. 每日涨停/连板截面

当前项目路径：`project_cache/features/board_snapshot/{year}.parquet`

建议字段：
- `date`, `code`
- `is_limit_up_close`: 收盘是否涨停，需使用现有 `limit_status` 的精确涨停价，不允许用 `pre_close * 1.1/1.2` 临时估算
- `board_count`: 当日连续涨停板数，至少支持 1/2/3+
- `is_first_board`: 当日首板
- `max_board_count_market`: 当日全市场最高连板高度，可按日重复写入或单独做日表
- `prev_close`, `open`, `close`, `money`, `volume`, `high`, `low`
- `avg_chg`: 当前策略里的 `money / volume / close * 1.1 - 1`

用途：替代 `_scan_all` / `_scan_boards_for_prev` 中每天 3 日全市场 `high_limit/close/open/money/volume` 多次 history 查询和 Python 循环。

## 2. 首板封板时间截面

当前项目路径：`project_cache/features/first_seal_time/{year}.parquet`

建议字段：
- `date`, `code`
- `first_limit_hit_time`: 首次触及涨停时间，分钟粒度即可
- `seal_bucket`: `early` / `mid` / `tail` / `none`
- `is_tail_seal`: 是否 14:00 及以后首次触及

语义要求：
- 判断价格用 1m `close` 对齐当前 JQ 兼容口径。
- 涨停价必须来自精确 `limit_status` / pivot `high_limit`。
- 保留无封板记录或明确 `none`，避免运行时读取 240 根分钟线逐票扫描。

用途：替代 `get_batch_sealing_points` 的候选逐日分钟线读取。

## 3. 左压/突破截面

建议项目路径：`project_cache/features/left_pressure/{year}.parquet`

建议字段：
- `date`, `code`
- `close_100_available`, `volume_100_available`
- `prev_100_high_close`, `prev_100_high_idx`
- `is_break_099`: `close >= prev_high * 0.99`
- `vol_ok_09`: 当前量是否达到前高点对应量的 90%
- `lp_score_base`: 现策略 `_score_with_left_pressure` 的基础分值
- `auction_left_ok`: 当前 `_auction_yiqian_batch_left_pressure` 的布尔结果

用途：替代每天候选池上的 `close_100/volume_100/highs_60/lows_60` 查询和逐票循环。

## 4. 竞价快照索引

现有路径：`1d_feature/call_auction/{year}.parquet`

建议改进：
- 不改 hdata 年文件；项目内可建立 `project_cache/features/call_auction_by_date/{year}/{date}.parquet`。
- 按策略每日访问模式缓存当天或少量股票查询结果。

用途：当前年文件 2020 有约 94.6 万行，首次加载约 12 秒；后续过滤仍有一定成本。按日分区更符合策略每天 09:15-09:25 的访问模式。

状态：已在项目内实现并接入 `DataAPI.get_call_auction` 的同日查询路径；缓存缺失时回退 hdata 年文件。已生成 2020、2021 缓存。

## 5. 日点快查截面

建议项目路径：`project_cache/features/daily_point/{year}.parquet` 或继续强化运行时 pivot 读取

建议字段：
- `date`, `code`, `open`, `close`, `high`, `low`, `money`, `volume`
- `high_limit`, `low_limit`, `paused`
- `adj_factor`

语义要求：
- `high_limit/low_limit/paused` 必须与现有 pivot/history 输出一致。
- 不要在策略侧用规则估算涨跌停价；实测会破坏 2020 对齐。

用途：供 `get_current_data` / 撮合估值 / 单日点查使用，避免大量单票 `count=1` history。

## 优先级

1. `board_snapshot` + `first_seal_time`
2. `left_pressure`
3. `call_auction` 按日分区
4. `daily_point` 快查

第一优先级预计收益最大，因为它直接覆盖每日 09:05 全市场扫描和 v130 封板时点过滤。

## 验证纪律

涉及候选池、ST/name、集合竞价、涨停封板时间的预处理变更，必须先过短窗口和目标风险窗口，再跑全年。不要用全年回归作为第一道探测。
