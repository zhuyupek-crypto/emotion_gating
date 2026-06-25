# HData Handoff

## Confirmed HData Issues

当前没有足够证据把任何钩子直接认定为HData已确认错误。

所有疑似数据问题均需进一步调查才能确定归属。

## HData Verification Queue

以下项目需要HData核实后才能确定最终归属。每一行说明观察到什么、为什么怀疑HData、还有其他可能解释、需要什么证据。

### `call_auction.allow_only`
- **观察到什么**: Restrict a day's auction dataset to an allow-list of codes before ranking.
- **当前证据**: project_compat.apply_call_auction_overrides enforces CALL_AUCTION_ALLOW_ONLY before candidate ranking reads the frame.
- **为什么怀疑HData**: The allow-list may reflect source contamination or a JQ extract quirk; ownership is not yet proven.
- **其他可能解释**: 
  - 聚宽历史数据形态差异
  - 本地数据缺失
  - 平台数据同步时间差异
- **需要什么证据**: 
  - 逐笔对比聚宽与本地同一时间截面的原始数据
  - 确认差异来源（口径 vs 错误）
- **确认后如何修复**: HData修复数据源或发布字段级质量标记
- **确认前项目如何处理**: 保持当前compat钩子，标记为investigation_pending

### `call_auction.depth_overrides`
- **观察到什么**: Patch specific call-auction depth fields before candidate ranking.
- **当前证据**: project_compat.apply_call_auction_overrides patches the requested columns, and tests assert the 2020-09-03 override.
- **为什么怀疑HData**: These look like source-field corrections, but current evidence is not strong enough to assign them permanently to HData.
- **其他可能解释**: 
  - 聚宽历史数据形态差异
  - 本地数据缺失
  - 平台数据同步时间差异
- **需要什么证据**: 
  - 逐笔对比聚宽与本地同一时间截面的原始数据
  - 确认差异来源（口径 vs 错误）
- **确认后如何修复**: HData修复数据源或发布字段级质量标记
- **确认前项目如何处理**: 保持当前compat钩子，标记为investigation_pending

### `call_auction.empty_anomalies`
- **观察到什么**: Remove specific call-auction rows entirely before candidate logic consumes them.
- **当前证据**: project_compat.apply_call_auction_overrides removes rows keyed by CALL_AUCTION_EMPTY_ANOMALIES and engine/data_api.py calls it in get_call_auction.
- **为什么怀疑HData**: The current evidence shows row suppression but does not yet prove whether the source is wrong or JoinQuant-only.
- **其他可能解释**: 
  - 聚宽历史数据形态差异
  - 本地数据缺失
  - 平台数据同步时间差异
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

### `market_data.daily_field_anomalies`
- **观察到什么**: Patch specific daily field values before selection/state logic consumes them.
- **当前证据**: engine/data_api.py and engine/core.py both query get_daily_field_override. Some entries overlap the 2026 window reported in an external, unmerged branch.
- **为什么怀疑HData**: Some rows overlap the externally reported 2026 anomaly window, but that external audit has not been accepted or merged. Others are isolated point answers whose root cause is not yet assigned.
- **其他可能解释**: 
  - 聚宽历史数据形态差异
  - 本地数据缺失
  - 平台数据同步时间差异
- **需要什么证据**: 
  - 逐笔对比聚宽与本地同一时间截面的原始数据
  - 确认差异来源（口径 vs 错误）
- **确认后如何修复**: HData修复数据源或发布字段级质量标记
- **确认前项目如何处理**: 保持当前compat钩子，标记为investigation_pending

### `market_data.tail_seal_anomalies`
- **观察到什么**: Inject observed first-seal timestamps when minute-derived first hit times diverge from archived reference runs.
- **当前证据**: rebuild_from_archive/project_preprocess.py and engine/data_api.py both honor get_tail_seal_override for the same keyed timestamps.
- **为什么怀疑HData**: These point fixes may reflect minute-data issues or JoinQuant snapshot behavior; current evidence does not prove the owner.
- **其他可能解释**: 
  - 聚宽历史数据形态差异
  - 本地数据缺失
  - 平台数据同步时间差异
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

### `security_metadata.billboard_row_filters`
- **观察到什么**: Drop specific billboard rows before strategy-side candidate logic reads them.
- **当前证据**: engine/data_api.py calls compat.filter_billboard_rows in get_billboard_list, and project_compat.filter_billboard_rows keys off BILLBOARD_ROW_FILTERS.
- **为什么怀疑HData**: This looks like data cleanup, but the current evidence does not yet prove whether the underlying billboard source or JoinQuant export is wrong.
- **其他可能解释**: 
  - 聚宽历史数据形态差异
  - 本地数据缺失
  - 平台数据同步时间差异
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

### `security_metadata.special_display_name_rules`
- **观察到什么**: Apply extra security-name compatibility rules beyond the window table, including explicit special-code branches.
- **当前证据**: project_compat.apply_security_name_overrides contains special handling for 001270.XSHE and 600856.XSHG outside NON_ST_NAME_WINDOWS.
- **为什么怀疑HData**: The special-case branches mix PIT naming concerns with hardcoded stock-specific logic and need decomposition before ownership can be assigned.
- **其他可能解释**: 
  - 名称/ST/退市状态口径差异
  - 聚宽与本地复权口径差异
  - 平台数据同步时间
- **需要什么证据**: 
  - 逐笔对比聚宽与本地同一时间截面的原始数据
  - 确认差异来源（口径 vs 错误）
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
