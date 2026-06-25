# HData Handoff

## Confirmed HData Issues

当前没有足够证据把任何钩子直接认定为HData已确认错误。

所有疑似数据问题均需进一步调查才能确定归属。

## HData Verification Queue

以下项目需要HData核实后才能确定最终归属。每一行说明观察到什么、为什么怀疑HData、还有其他可能解释、需要什么证据。

### `market_data.corrupted_daily_limit_windows`
- **观察到什么**: Quarantine a known daily-data corruption window by bypassing fast-path history and suppressing selected cached features.
- **当前证据**: Project currently has an explicit data isolation window used at runtime to bypass fast-path and caching. The root cause and full impact range still need HData audit confirmation.
- **为什么怀疑HData**: The 2026 corruption window is a source-data quality concern, but the full root cause and impact scope have not yet been independently verified. JQ vs local data difference possible.
- **其他可能解释**: 
  - 聚宽历史数据形态差异
  - 本地数据缺失
  - 平台数据同步时间差异
- **需要什么证据**: 
  - 确认2026-05-25起数据污染根因是HData上游问题
  - 当前分支的外部线索（codex/data-quality-propagation-audit 未验收）不能作为已确认依据
- **确认后如何修复**: HData修复数据源或发布字段级质量标记
- **确认前项目如何处理**: 保持当前compat钩子，标记为investigation_pending

### `security_metadata.start_date_overrides`
- **观察到什么**: Replace listing dates for specific securities before IPO-age filters run.
- **当前证据**: engine/data_api.py applies get_security_start_date_override while building _stock_basic for get_all_securities().
- **为什么怀疑HData**: Listing-date truth belongs to the data layer, but the discrepancy may reflect JoinQuant listing-date conventions rather than HData errors. Pending independent verification.
- **其他可能解释**: 
  - 聚宽历史截面口径差异
  - 公告日与生效日差异
- **需要什么证据**: 
  - 逐笔对比聚宽与本地同一时间截面的原始数据
  - 确认差异来源（口径 vs 错误）
- **确认后如何修复**: HData修复数据源或发布字段级质量标记
- **确认前项目如何处理**: 保持当前compat钩子，标记为investigation_pending

### `security_metadata.non_st_name_windows`
- **观察到什么**: Strip future ST or delisting markers from PIT display names inside explicit date windows.
- **当前证据**: project_compat.apply_security_name_overrides applies NON_ST_NAME_WINDOWS after reading daily ST state and before strategy filters consume display_name.
- **为什么怀疑HData**: Historical security-name state is source metadata, but the divergence may stem from JoinQuant name-history conventions vs local data PIT snapshots. Pending independent verification.
- **其他可能解释**: 
  - 名称/ST/退市状态口径差异
  - 聚宽与本地复权口径差异
  - 平台数据同步时间
- **需要什么证据**: 
  - 逐笔对比聚宽与本地同一时间截面的原始数据
  - 确认差异来源（口径 vs 错误）
- **确认后如何修复**: HData修复数据源或发布字段级质量标记
- **确认前项目如何处理**: 保持当前compat钩子，标记为investigation_pending

### `security_metadata.adjust_extras_is_st`
- **观察到什么**: Override is_st results using PIT name and end-date heuristics for specific windows and codes.
- **当前证据**: engine/data_api.py calls compat.adjust_extras_is_st from get_extras('is_st', ...), and project_compat.py embeds date windows and name/end_date heuristics.
- **为什么怀疑HData**: ST state and delisting-state truth should come from source metadata, but the divergence may reflect JoinQuant ST classification conventions rather than HData errors. Pending verification.
- **其他可能解释**: 
  - 名称/ST/退市状态口径差异
  - 聚宽与本地复权口径差异
  - 平台数据同步时间
- **需要什么证据**: 
  - 逐笔对比聚宽与本地同一时间截面的原始数据
  - 确认差异来源（口径 vs 错误）
- **确认后如何修复**: HData修复数据源或发布字段级质量标记
- **确认前项目如何处理**: 保持当前compat钩子，标记为investigation_pending

### `instrument_fallbacks.price_fallbacks`
- **观察到什么**: Serve synthetic daily prices for instruments missing or unusable in the local data path.
- **当前证据**: engine/data_api.py short-circuits get_price via compat.get_instrument_price_fallback before touching local price tables.
- **为什么怀疑HData**: Instrument price history should come from the data layer, but the absence may reflect data-coverage gaps rather than HData errors. Pending verification.
- **其他可能解释**: 
  - 名称/ST/退市状态口径差异
  - 聚宽与本地复权口径差异
  - 平台数据同步时间
- **需要什么证据**: 
  - 逐笔对比聚宽与本地同一时间截面的原始数据
  - 确认差异来源（口径 vs 错误）
- **确认后如何修复**: HData修复数据源或发布字段级质量标记
- **确认前项目如何处理**: 保持当前compat钩子，标记为investigation_pending
