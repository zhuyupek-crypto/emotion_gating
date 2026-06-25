# Hook Disposition Inventory

## Summary

- Hook total: `33`
- By semantic_type: `{"data_correction": 10, "jq_platform_behavior": 10, "market_rule": 2, "project_infrastructure": 7, "unknown": 4}`
- By disposition: `{"archive_jq_only": 10, "investigate": 15, "move_to_local_quant": 2, "retain_in_project": 6}`
- By status: `{"archive_candidate": 10, "handoff_pending": 2, "investigation_pending": 15, "retain": 6}`
- By wave: `{"L1A": 2, "L1B": 2, "L2": 3, "L3": 2, "L4": 1, "cleanup-only": 1}`
- By target_owner: `{"emotion_gating_project": 9, "hdata_candidate": 5, "investigation": 7, "jq_archive": 10, "local_quant": 2}`
- By year: `{"1900": 1, "2020": 14, "2021": 8, "2022": 7, "2023": 4, "2024": 5, "2025": 5, "2026": 3}`
- Hooks touching selection: `22`
- Hooks touching state: `13`
- Hooks touching order: `9`
- Hooks touching fill: `6`
- Hooks affecting NAV only: `4`
- Hooks with no active runtime call site: `2`
- Hooks still requiring investigation: `15`
- Empty config entries: `1`
- Zero-consumer entries: `5`
- HData confirmed issues: `0`
- HData verification queue: `12`
- project_logic: `0`
- project_infrastructure: `7`

## Key Findings

1. **project_logic hooks**: 0 — Current compat inventory contains **no true strategy alpha hooks**.
2. **project_infrastructure hooks**: 7 — These are project cache access, namespace wiring, and checkpoint infrastructure.
3. **HData confirmed**: 0 — No hook has sufficient in-branch evidence to be classified as a confirmed HData error.
4. **HData verification queue**: 12 — These need HData investigation before ownership assignment.
5. **zero-consumer entries**: 5 — 无直接消费者的条目（consumer_count仅表示对该hook入口的直接消费，不代表不存在通过DataAPI转发产生的间接业务影响）。真正可视为清理候选的条目需逐个审查。
6. **empty_config entries**: 1 — Interface registrations with empty data that should not count as active behavior.

## Questions

### 1. 哪些钩子属于通用市场规则？
- `engine.immediate_sell_cash_release`
- `instrument_fallbacks.zero_fee_overrides`

### 2a. 哪些钩子是HData主要候选（高嫌疑）？
- `instrument_fallbacks.price_fallbacks`
- `market_data.corrupted_daily_limit_windows`
- `security_metadata.adjust_extras_is_st`
- `security_metadata.non_st_name_windows`
- `security_metadata.start_date_overrides`

### 2b. 哪些钩子需HData参与核实队列？
- `call_auction.allow_only`
- `call_auction.depth_overrides`
- `call_auction.empty_anomalies`
- `instrument_fallbacks.price_fallbacks`
- `market_data.corrupted_daily_limit_windows`
- `market_data.daily_field_anomalies`
- `market_data.tail_seal_anomalies`
- `security_metadata.adjust_extras_is_st`
- `security_metadata.billboard_row_filters`
- `security_metadata.non_st_name_windows`
- `security_metadata.special_display_name_rules`
- `security_metadata.start_date_overrides`

### 3. 哪些钩子只是聚宽历史复刻？
- `execution.execution_price_anomalies`
- `execution.fill_amount_anomalies`
- `execution.order_amount_anomalies`
- `execution.preopen_drop_first_duplicate`
- `execution.preopen_reject_cash_below`
- `execution.preopen_reject_orders`
- `market_data.daily_ipo_close_anomalies`
- `market_data.minute_price_anomalies`
- `strategy_state.fb_state_overrides`
- `strategy_state.v227_shock_overrides`

### 4. 哪些钩子真正属于项目策略逻辑？
- none

### 5. 哪些钩子是项目基础设施？
- `engine.checkpoint_resume_hook`
- `project_feature.auction_yiqian_prepare_accessor`
- `project_feature.board_snapshot_accessor`
- `project_feature.call_auction_day_loader`
- `project_feature.first_seal_loader`
- `project_feature.master_prepare_index_accessor`
- `project_feature.strategy_namespace_bridge`

### 6. 哪些钩子仍无法判断？
- `legacy.public_data_api_shim`
- `legacy.temporary_fallbacks_shim`
- `market_data.tail_seal_anomalies`
- `project_feature.master_prepare_index_accessor`
- `security_metadata.special_display_name_rules`

### 7. L1A（价格类）：可第一批关闭？
- `execution.execution_price_anomalies`
- `market_data.minute_price_anomalies`

### 8. L1B（数量类）：应第二批关闭？
- `execution.fill_amount_anomalies`
- `execution.order_amount_anomalies`

### 9. L2（订单存在性类）：应第三批关闭？
- `execution.preopen_drop_first_duplicate`
- `execution.preopen_reject_cash_below`
- `execution.preopen_reject_orders`

### 10. L3（状态历史答案类）：应第四批关闭？
- `strategy_state.fb_state_overrides`
- `strategy_state.v227_shock_overrides`

### 11. L4（JQ数据形态类）：需本地数据确认后关闭？
- `market_data.daily_ipo_close_anomalies`

### 12. 哪些不是消融项，只是遗留清理？
- `legacy.temporary_fallbacks_shim`

### 13. 哪些没有真实消费者？
- `legacy.public_data_api_shim`
- `legacy.temporary_fallbacks_shim`
- `project_feature.master_prepare_index_accessor`
- `security_metadata.non_st_name_windows`
- `security_metadata.special_display_name_rules`

### 14. 哪些配置为空？
- `execution.preopen_reject_orders`

### 15. 哪些引用了外部未合并分支证据？
- `market_data.corrupted_daily_limit_windows`
- `market_data.daily_field_anomalies`

### 16. 哪些必须等待local_quant？
- `engine.immediate_sell_cash_release`
- `instrument_fallbacks.zero_fee_overrides`

## Hook Table

| hook_id | semantic_type | disposition | status | wave | years | codes | runtime call sites | consumer_count | target_owner |
| --- | --- | --- | --- | --- | --- | --- | ---: | ---: | --- |
| `engine.immediate_sell_cash_release` | `market_rule` | `move_to_local_quant` | `handoff_pending` | `—` | `` | `` | `2` | `2` | `local_quant` |
| `market_data.corrupted_daily_limit_windows` | `data_correction` | `investigate` | `investigation_pending` | `—` | `` | `` | `12` | `4` | `hdata_candidate` |
| `market_data.tail_seal_anomalies` | `unknown` | `investigate` | `investigation_pending` | `—` | `2020,2021,2022,2025` | `000420.XSHE,002487.XSHE,300118.XSHE,600711.XSHG,603031.XSHG` | `3` | `2` | `investigation` |
| `market_data.minute_price_anomalies` | `jq_platform_behavior` | `archive_jq_only` | `archive_candidate` | `L1A` | `2020,2021,2022,2023,2024,2025,2026` | `000592.XSHE,000987.XSHE,002056.XSHE,002130.XSHE,002176.XSHE,002229.XSHE` | `2` | `1` | `jq_archive` |
| `market_data.daily_ipo_close_anomalies` | `jq_platform_behavior` | `archive_jq_only` | `archive_candidate` | `L4` | `2020` | `605123.XSHG,605255.XSHG,605369.XSHG,605399.XSHG` | `3` | `2` | `jq_archive` |
| `market_data.daily_field_anomalies` | `data_correction` | `investigate` | `investigation_pending` | `—` | `2020,2021,2022,2024,2025,2026` | `000420.XSHE,002121.XSHE,002141.XSHE,002185.XSHE,002256.XSHE,002265.XSHE` | `4` | `3` | `investigation` |
| `execution.preopen_reject_cash_below` | `jq_platform_behavior` | `archive_jq_only` | `archive_candidate` | `L2` | `2025` | `` | `2` | `1` | `jq_archive` |
| `execution.preopen_reject_orders` | `jq_platform_behavior` | `archive_jq_only` | `archive_candidate` | `L2` | `` | `` | `2` | `1` | `jq_archive` |
| `execution.preopen_drop_first_duplicate` | `jq_platform_behavior` | `archive_jq_only` | `archive_candidate` | `L2` | `2021,2022` | `000547.XSHE,000600.XSHE,002120.XSHE,002508.XSHE,600072.XSHG,603589.XSHG` | `2` | `1` | `jq_archive` |
| `execution.execution_price_anomalies` | `jq_platform_behavior` | `archive_jq_only` | `archive_candidate` | `L1A` | `2020,2023` | `000034.XSHE,000049.XSHE,000505.XSHE,000592.XSHE,000650.XSHE,000700.XSHE` | `2` | `1` | `jq_archive` |
| `execution.order_amount_anomalies` | `jq_platform_behavior` | `archive_jq_only` | `archive_candidate` | `L1B` | `2020` | `000592.XSHE,000700.XSHE,000800.XSHE,000859.XSHE,000987.XSHE,002022.XSHE` | `2` | `1` | `jq_archive` |
| `execution.fill_amount_anomalies` | `jq_platform_behavior` | `archive_jq_only` | `archive_candidate` | `L1B` | `2020` | `002041.XSHE,600086.XSHG` | `2` | `1` | `jq_archive` |
| `call_auction.empty_anomalies` | `data_correction` | `investigate` | `investigation_pending` | `—` | `2020,2021` | `002897.XSHE,600804.XSHG,600982.XSHG,603908.XSHG` | `2` | `1` | `investigation` |
| `call_auction.allow_only` | `data_correction` | `investigate` | `investigation_pending` | `—` | `2021` | `000833.XSHE` | `2` | `1` | `investigation` |
| `call_auction.depth_overrides` | `data_correction` | `investigate` | `investigation_pending` | `—` | `2020,2021` | `000038.XSHE,002635.XSHE` | `2` | `1` | `investigation` |
| `security_metadata.start_date_overrides` | `data_correction` | `investigate` | `investigation_pending` | `—` | `` | `605123.XSHG,605255.XSHG,605369.XSHG,605399.XSHG` | `2` | `1` | `hdata_candidate` |
| `security_metadata.non_st_name_windows` | `data_correction` | `investigate` | `investigation_pending` | `—` | `1900,2020,2021,2022,2023,2024,2025,2026` | `000506.XSHE,000584.XSHE,000585.XSHE,000673.XSHE,000839.XSHE,000980.XSHE` | `2` | `0` | `hdata_candidate` |
| `security_metadata.special_display_name_rules` | `unknown` | `investigate` | `investigation_pending` | `—` | `2020,2022` | `001270.XSHE,600856.XSHG` | `2` | `0` | `investigation` |
| `security_metadata.adjust_extras_is_st` | `data_correction` | `investigate` | `investigation_pending` | `—` | `2020,2024` | `600856.XSHG` | `2` | `1` | `hdata_candidate` |
| `security_metadata.billboard_row_filters` | `data_correction` | `investigate` | `investigation_pending` | `—` | `2020,2022` | `600146.XSHG,603721.XSHG` | `2` | `1` | `investigation` |
| `instrument_fallbacks.price_fallbacks` | `data_correction` | `investigate` | `investigation_pending` | `—` | `2024` | `511880.XSHG` | `2` | `1` | `hdata_candidate` |
| `instrument_fallbacks.zero_fee_overrides` | `market_rule` | `move_to_local_quant` | `handoff_pending` | `—` | `` | `511880.XSHG` | `8` | `6` | `local_quant` |
| `strategy_state.fb_state_overrides` | `jq_platform_behavior` | `archive_jq_only` | `archive_candidate` | `L3` | `2020` | `` | `4` | `3` | `jq_archive` |
| `strategy_state.v227_shock_overrides` | `jq_platform_behavior` | `archive_jq_only` | `archive_candidate` | `L3` | `2023` | `` | `4` | `3` | `jq_archive` |
| `project_feature.first_seal_loader` | `project_infrastructure` | `retain_in_project` | `retain` | `—` | `` | `` | `4` | `1` | `emotion_gating_project` |
| `project_feature.board_snapshot_accessor` | `project_infrastructure` | `retain_in_project` | `retain` | `—` | `` | `` | `6` | `2` | `emotion_gating_project` |
| `project_feature.master_prepare_index_accessor` | `project_infrastructure` | `investigate` | `investigation_pending` | `—` | `` | `` | `4` | `0` | `emotion_gating_project` |
| `project_feature.auction_yiqian_prepare_accessor` | `project_infrastructure` | `retain_in_project` | `retain` | `—` | `` | `` | `5` | `1` | `emotion_gating_project` |
| `project_feature.call_auction_day_loader` | `project_infrastructure` | `retain_in_project` | `retain` | `—` | `` | `` | `2` | `1` | `emotion_gating_project` |
| `project_feature.strategy_namespace_bridge` | `project_infrastructure` | `retain_in_project` | `retain` | `—` | `` | `` | `4` | `3` | `emotion_gating_project` |
| `engine.checkpoint_resume_hook` | `project_infrastructure` | `retain_in_project` | `retain` | `—` | `` | `` | `6` | `4` | `emotion_gating_project` |
| `legacy.public_data_api_shim` | `unknown` | `investigate` | `investigation_pending` | `—` | `` | `` | `0` | `0` | `emotion_gating_project` |
| `legacy.temporary_fallbacks_shim` | `unknown` | `investigate` | `investigation_pending` | `cleanup-only` | `` | `` | `0` | `0` | `emotion_gating_project` |

## Detailed Hooks

### `engine.immediate_sell_cash_release`
- Module: `rebuild_from_archive.project_compat`
- Symbol: `EmotionGateJQCompat.immediate_sell_cash_release`
- Behavior: Release sell proceeds immediately after fill instead of waiting until end-of-day rollover.
- semantic_type / disposition / status: `market_rule` / `move_to_local_quant` / `handoff_pending`
- Wave: `—`
- Affected fields: `available_cash, locked_cash, positions_value`
- Trigger dates: ``
- Trigger codes: ``
- Effects: selection=no, state=no, order=yes, fill=yes, nav=yes
- direct_effect_scope: `['cash_settlement']`
- downstream_risk: `cash_path`
- empty_config: `no`
- Reason: This is account and cash-settlement semantics, not project alpha logic.
- Evidence: rebuild_from_archive/project_compat.py sets immediate_sell_cash_release=True and engine/core.py consumes it in the sell-fill cash path.
- Runtime call sites: `rebuild_from_archive/engine\core.py:872:            if getattr(self.compat, "immediate_sell_cash_release", False):; rebuild_from_archive/project_compat.py:35:    immediate_sell_cash_release = True`
- Secondary references: `alignment_reports\align_worktree_diff_2020-01-02_2021-12-31.patch:302:+            if getattr(self.compat, "immediate_sell_cash_release", False):; tools\audit_hook_disposition.py:309:        hook_id="engine.immediate_sell_cash_release",; tools\audit_hook_disposition.py:311:        symbol="EmotionGateJQCompat.immediate_sell_cash_release",; tools\audit_hook_disposition.py:312:        data_obj={"immediate_sell_cash_release": True},; tools\audit_hook_disposition.py:318:        evidence="rebuild_from_archive/project_compat.py sets immediate_sell_cash_release=True and engine/core.py consumes it in the sell-fill cash path.",; tools\audit_hook_disposition.py:330:        delete_requirement="Delete when engine/core.py no longer checks compat.immediate_sell_cash_release and the policy lives in local_quant.",; tools\audit_hook_disposition.py:331:        acceptance_test="Inventory-only: verify engine/core.py still references immediate_sell_cash_release and classify it as local_quant-owned.",; tools\audit_hook_disposition.py:333:        call_site_patterns=["immediate_sell_cash_release"],`
- target_owner: `local_quant`
- handoff_requirement: local_quant needs a first-class switch for sell-cash release timing so project code stops carrying the behavior flag.
- disable_requirement: Disable only after local_quant can reproduce the intended cash-release policy in native mode.
- delete_requirement: Delete when engine/core.py no longer checks compat.immediate_sell_cash_release and the policy lives in local_quant.
- acceptance_test: Inventory-only: verify engine/core.py still references immediate_sell_cash_release and classify it as local_quant-owned.

### `market_data.corrupted_daily_limit_windows`
- Module: `rebuild_from_archive.compat.market_data`
- Symbol: `CORRUPTED_DAILY_LIMIT_WINDOWS`
- Behavior: Quarantine a known daily-data corruption window by bypassing fast-path history and suppressing selected cached features.
- semantic_type / disposition / status: `data_correction` / `investigate` / `investigation_pending`
- Wave: `—`
- Affected fields: `pre_close, high_limit, low_limit, money, volume, board_snapshot, first_seal_time`
- Trigger dates: ``
- Trigger codes: ``
- Effects: selection=yes, state=yes, order=no, fill=no, nav=yes
- direct_effect_scope: `['data_shape']`
- downstream_risk: `strategy_path`
- empty_config: `no`
- Reason: The 2026 corruption window is a source-data quality concern, but the full root cause and impact scope have not yet been independently verified. JQ vs local data difference possible.
- Evidence: Project currently has an explicit data isolation window used at runtime to bypass fast-path and caching. The root cause and full impact range still need HData audit confirmation.
- External evidence ref: `codex/data-quality-propagation-audit branch, commit b951d3885f09fcc6d455675799a295c569af5439`
- External evidence status: `unreviewed`
- Runtime call sites: `rebuild_from_archive/engine\data_api.py:143:    def _should_bypass_history_fastpath(self, unit, fields, end_dt):; rebuild_from_archive/engine\data_api.py:149:                return bool(compat.should_bypass_history_fastpath(unit, fields, end_dt)); rebuild_from_archive/engine\data_api.py:438:                if self._should_bypass_history_fastpath(unit, fields_to_get, end_dt):; rebuild_from_archive/engine\data_api.py:820:            return self.compat.load_first_seal_year(year); rebuild_from_archive/engine\data_api.py:823:    def get_project_board_snapshot(self, date):; rebuild_from_archive/engine\data_api.py:825:            return self.compat.get_project_board_snapshot(date); rebuild_from_archive/project_compat.py:212:    def should_bypass_history_fastpath(self, unit, fields, end_dt):; rebuild_from_archive/project_compat.py:224:    def load_first_seal_year(self, year):; rebuild_from_archive/project_compat.py:247:    def get_project_board_snapshot(self, date):; rebuild_from_archive/project_compat.py:67:                engine.data_api.get_project_board_snapshot(*a, **kw); 母版-20260506-Clone.py:564:        board_df = get_project_board_snapshot(context.previous_date); 母版-20260506-Clone.py:666:        board_df = get_project_board_snapshot(context.previous_date)`
- Secondary references: `alignment_reports\align_worktree_diff_2020-01-02_2021-12-31.patch:232:-            'get_project_board_snapshot': lambda *a, **kw: self._wrap_pandas(self.data_api.get_project_board_snapshot(*a, **kw)),; alignment_reports\align_worktree_diff_2020-01-02_2021-12-31.patch:462:+            return self.compat.load_first_seal_year(year); alignment_reports\align_worktree_diff_2020-01-02_2021-12-31.patch:465:     def get_project_board_snapshot(self, date):; alignment_reports\align_worktree_diff_2020-01-02_2021-12-31.patch:481:+            return self.compat.get_project_board_snapshot(date); alignment_reports\alignment_configuration_notes.md:116:### 2.7 `should_bypass_history_fastpath(...)`; alignment_reports\alignment_final_report_2020_2026.md:190:  - 提供 `should_bypass_history_fastpath(...)`; alignment_reports\alignment_summary_2020_2026.md:204:- 新增 `should_bypass_history_fastpath(unit, fields, end_dt)`。; alignment_reports\alignment_summary_2020_2026.md:205:- `load_first_seal_year()` 在污染窗口跳过对应快缓存。; alignment_reports\alignment_summary_2020_2026.md:206:- `get_project_board_snapshot()` 在污染窗口直接返回空 `DataFrame()`，避免使用脏首板快照。; alignment_reports\alignment_summary_2020_2026.md:217:- 当 `compat.should_bypass_history_fastpath('daily', fields, day)` 返回 true 时，不再继续快取，直接回退到旧路径。; tools\audit_hook_disposition.py:1005:        evidence="母版-20260506-Clone.py reads get_project_board_snapshot(context.previous_date) for board scans; engine/data_api.py delegates through compat.",; tools\audit_hook_disposition.py:1020:        call_site_patterns=["get_project_board_snapshot("],; tools\audit_hook_disposition.py:360:        call_site_patterns=["should_bypass_history_fastpath(", "load_first_seal_year(", "get_project_board_snapshot("],; tools\audit_hook_disposition.py:992:        call_site_patterns=["load_first_seal_year(", "get_batch_sealing_points("],; tools\hook_migration_acceptance.py:166:    def should_bypass_history_fastpath(self, unit, fields, end_dt):; tools\hook_migration_acceptance.py:167:        value = self._base.should_bypass_history_fastpath(unit, fields, end_dt); tools\hook_migration_acceptance.py:561:    bypass_2026 = compat.should_bypass_history_fastpath("1d", ["high", "high_limit"], pd.Timestamp("2026-05-27"))`
- target_owner: `hdata_candidate`
- handoff_requirement: HData or upstream cache metadata must publish corruption windows and field-level quarantine signals.
- disable_requirement: Disable only after raw-data quality flags propagate through cache build and runtime readers.
- delete_requirement: Delete after HData versioned quality metadata replaces project-specific date guards and all dependent caches respect the same rule.
- acceptance_test: External investigation branch codex/data-quality-propagation-audit at commit b951d3885f09fcc6d455675799a295c569af5439 (not accepted/not merged); requires verification via hdata_candidate queue

### `market_data.tail_seal_anomalies`
- Module: `rebuild_from_archive.compat.market_data`
- Symbol: `TAIL_SEAL_ANOMALIES`
- Behavior: Inject observed first-seal timestamps when minute-derived first hit times diverge from archived reference runs.
- semantic_type / disposition / status: `unknown` / `investigate` / `investigation_pending`
- Wave: `—`
- Affected fields: `first_limit_hit_time, seal_bucket, is_tail_seal`
- Trigger dates: `2020-07-13; 2021-11-15; 2022-12-26; 2025-08-13`
- Trigger codes: `000420.XSHE; 002487.XSHE; 300118.XSHE; 600711.XSHG; 603031.XSHG`
- Effects: selection=yes, state=no, order=no, fill=no, nav=no
- direct_effect_scope: `['data_shape']`
- downstream_risk: `strategy_path`
- empty_config: `no`
- Reason: These point fixes may reflect minute-data issues or JoinQuant snapshot behavior; current evidence does not prove the owner.
- Evidence: rebuild_from_archive/project_preprocess.py and engine/data_api.py both honor get_tail_seal_override for the same keyed timestamps.
- Runtime call sites: `rebuild_from_archive/engine\data_api.py:851:                self.compat.get_tail_seal_override(day_key, sec); rebuild_from_archive/project_compat.py:114:    def get_tail_seal_override(self, date_key, security):; rebuild_from_archive/project_preprocess.py:137:                compat.get_tail_seal_override(f"{date_int:08d}", code)`
- Secondary references: `tools\audit_hook_disposition.py:389:        call_site_patterns=["get_tail_seal_override("],; tools\hook_migration_acceptance.py:161:    def get_tail_seal_override(self, date_key, security):; tools\hook_migration_acceptance.py:162:        value = self._base.get_tail_seal_override(date_key, security)`
- target_owner: `investigation`
- handoff_requirement: Need side-by-side evidence from minute source, derived first-seal cache, and mother reference to decide HData vs JQ archive ownership.
- disable_requirement: In local-native mode this group can be disabled only after first-seal behavior is proven acceptable without parity timestamps.
- delete_requirement: Delete after either HData is fixed and caches are rebuilt, or the project explicitly archives JoinQuant-only seal answers.
- acceptance_test: tests/test_compat_entrypoints.py::test_call_auction_overrides_apply does not cover this hook; add targeted first-seal evidence before retirement.

### `market_data.minute_price_anomalies`
- Module: `rebuild_from_archive.compat.market_data`
- Symbol: `MINUTE_PRICE_ANOMALIES`
- Behavior: Override minute-bar trade prices at specific timestamps to reproduce archived buy/sell boundary fills.
- semantic_type / disposition / status: `jq_platform_behavior` / `archive_jq_only` / `archive_candidate`
- Wave: `L1A`
- Affected fields: `close, trade_price`
- Trigger dates: `2020-01-14; 2021-05-19; 2021-08-09; 2022-07-08; 2023-02-28; 2024-03-25; 2025-06-13; 2025-07-11; 2026-01-19`
- Trigger codes: `000592.XSHE; 000987.XSHE; 002056.XSHE; 002130.XSHE; 002176.XSHE; 002229.XSHE; 002310.XSHE; 002426.XSHE; 002470.XSHE`
- Effects: selection=no, state=no, order=no, fill=yes, nav=yes
- direct_effect_scope: `['price']`
- downstream_risk: `cash_path`
- empty_config: `no`
- Reason: These are point answers for historical JoinQuant parity and do not describe a reusable market rule.
- Evidence: rebuild_from_archive/engine/core.py applies get_minute_price_override inside _apply_jq_minute_price_anomaly before returning trade prices.
- Runtime call sites: `rebuild_from_archive/engine\core.py:1119:                override = self.compat.get_minute_price_override(day_key, norm_time, security); rebuild_from_archive/project_compat.py:82:    def get_minute_price_override(self, date_key, time_key, security):`
- Secondary references: `tests\test_compat_entrypoints.py:11:    assert compat.get_minute_price_override("20200114", "11:25", "002056.XSHE") == 10.90; tools\audit_hook_disposition.py:416:        call_site_patterns=["get_minute_price_override("],; tools\hook_migration_acceptance.py:100:    def get_minute_price_override(self, date_key, time_key, security):; tools\hook_migration_acceptance.py:101:        value = self._base.get_minute_price_override(date_key, time_key, security)`
- target_owner: `jq_archive`
- handoff_requirement: Keep only in the JoinQuant replay profile; do not move into local-native market data behavior.
- disable_requirement: Safe first-wave disable candidate for local-native mode if some trade price and NAV drift is acceptable.
- delete_requirement: Delete once the project formally stops supporting JoinQuant minute-fill parity.
- acceptance_test: tests/test_compat_entrypoints.py::test_minute_and_execution_overrides

### `market_data.daily_ipo_close_anomalies`
- Module: `rebuild_from_archive.compat.market_data`
- Symbol: `DAILY_IPO_CLOSE_ANOMALIES`
- Behavior: Patch IPO sync-delay rows where the parity path expects prior close plus trailing NaN behavior.
- semantic_type / disposition / status: `jq_platform_behavior` / `archive_jq_only` / `archive_candidate`
- Wave: `L4`
- Affected fields: `close, high_limit, low_limit, pre_close`
- Trigger dates: `2020-08-04; 2020-08-25; 2020-09-16`
- Trigger codes: `605123.XSHG; 605255.XSHG; 605369.XSHG; 605399.XSHG`
- Effects: selection=yes, state=yes, order=no, fill=no, nav=no
- direct_effect_scope: `['data_shape']`
- downstream_risk: `strategy_path`
- empty_config: `no`
- Reason: This behavior exists to mimic the historical JoinQuant return shape, not to express a stable local market-data rule.
- Evidence: engine/data_api.py applies get_daily_ipo_close_override in both panel and long-form daily-history anomaly patchers.
- Runtime call sites: `rebuild_from_archive/engine\data_api.py:181:                self.compat.get_daily_ipo_close_override(sec, end_int); rebuild_from_archive/engine\data_api.py:229:                    self.compat.get_daily_ipo_close_override(sec, end_int); rebuild_from_archive/project_compat.py:86:    def get_daily_ipo_close_override(self, security, date_int):`
- Secondary references: `tools\audit_hook_disposition.py:443:        call_site_patterns=["get_daily_ipo_close_override("],; tools\hook_migration_acceptance.py:110:    def get_daily_ipo_close_override(self, security, date_int):; tools\hook_migration_acceptance.py:111:        value = self._base.get_daily_ipo_close_override(security, date_int); tools\hook_migration_acceptance.py:507:        close_override = compat.get_daily_ipo_close_override(case["code"], case["trade_date"])`
- target_owner: `jq_archive`
- handoff_requirement: Retain only under a JoinQuant parity profile or archived replay mode.
- disable_requirement: Can be disabled in local-native mode once IPO handling is expected to follow local data directly.
- delete_requirement: Delete after the project drops JoinQuant daily-history shape parity.
- acceptance_test: tools/hook_migration_acceptance.py targeted 2020 IPO override checks

### `market_data.daily_field_anomalies`
- Module: `rebuild_from_archive.compat.market_data`
- Symbol: `DAILY_FIELD_ANOMALIES`
- Behavior: Patch specific daily field values before selection/state logic consumes them.
- semantic_type / disposition / status: `data_correction` / `investigate` / `investigation_pending`
- Wave: `—`
- Affected fields: `open, high, high_limit, money`
- Trigger dates: `2020-08-28; 2021-09-10; 2021-11-15; 2022-07-01; 2024-07-16; 2024-12-03; 2024-12-09; 2025-09-29; 2026-05-27`
- Trigger codes: `000420.XSHE; 002121.XSHE; 002141.XSHE; 002185.XSHE; 002256.XSHE; 002265.XSHE; 600032.XSHG; 603393.XSHG; 603569.XSHG; 603773.XSHG`
- Effects: selection=yes, state=yes, order=no, fill=no, nav=yes
- direct_effect_scope: `['data_shape']`
- downstream_risk: `strategy_path`
- empty_config: `no`
- Reason: Some rows overlap the externally reported 2026 anomaly window, but that external audit has not been accepted or merged. Others are isolated point answers whose root cause is not yet assigned.
- Evidence: engine/data_api.py and engine/core.py both query get_daily_field_override. Some entries overlap the 2026 window reported in an external, unmerged branch.
- External evidence ref: `codex/data-quality-propagation-audit branch, commit b951d3885f09fcc6d455675799a295c569af5439`
- External evidence status: `unreviewed`
- Runtime call sites: `rebuild_from_archive/engine\core.py:1211:                        self.compat.get_daily_field_override(code, day_int, field); rebuild_from_archive/engine\data_api.py:167:                self.compat.get_daily_field_override(sec, end_int, field); rebuild_from_archive/engine\data_api.py:222:                    self.compat.get_daily_field_override(sec, end_int, field); rebuild_from_archive/project_compat.py:90:    def get_daily_field_override(self, security, date_int, field):`
- Secondary references: `tools\audit_hook_disposition.py:470:        call_site_patterns=["get_daily_field_override("],; tools\hook_migration_acceptance.py:105:    def get_daily_field_override(self, security, date_int, field):; tools\hook_migration_acceptance.py:106:        value = self._base.get_daily_field_override(security, date_int, field)`
- target_owner: `investigation`
- handoff_requirement: Split the group into true source-data defects vs JoinQuant-only answers before moving ownership.
- disable_requirement: Disable only after each remaining point is either archived as JQ-only or repaired upstream.
- delete_requirement: Delete only after the mixed bundle is decomposed and each member has a final owner.
- acceptance_test: tools/hook_migration_acceptance.py targeted 2026 corrupted daily fastpath check

### `execution.preopen_reject_cash_below`
- Module: `rebuild_from_archive.compat.execution`
- Symbol: `PREOPEN_REJECT_CASH_BELOW`
- Behavior: Reject pre-open orders below a recorded cash threshold at a specific timestamp.
- semantic_type / disposition / status: `jq_platform_behavior` / `archive_jq_only` / `archive_candidate`
- Wave: `L2`
- Affected fields: `available_cash, preopen_order_acceptance`
- Trigger dates: `2025-03-19`
- Trigger codes: ``
- Effects: selection=no, state=no, order=yes, fill=no, nav=yes
- direct_effect_scope: `['order_presence']`
- downstream_risk: `strategy_path`
- empty_config: `no`
- Reason: This is a recorded JoinQuant answer for one historical event, not a general exchange rule.
- Evidence: engine/core.py calls compat.should_reject_preopen_cash inside _should_reject_jq_preopen_order.
- Runtime call sites: `rebuild_from_archive/engine\core.py:471:            should_reject, cash_threshold = self.compat.should_reject_preopen_cash(; rebuild_from_archive/project_compat.py:104:    def should_reject_preopen_cash(self, date_key, time_key, available_cash):`
- Secondary references: `tools\audit_hook_disposition.py:499:        call_site_patterns=["should_reject_preopen_cash("],; tools\hook_migration_acceptance.py:130:    def should_reject_preopen_cash(self, date_key, time_key, available_cash):; tools\hook_migration_acceptance.py:131:        reject, threshold = self._base.should_reject_preopen_cash(date_key, time_key, available_cash); tools\hook_migration_acceptance.py:558:    reject_2025, threshold_2025 = compat.should_reject_preopen_cash("2025-03-19", "09:28", 19999.99)`
- target_owner: `jq_archive`
- handoff_requirement: Keep under JQ replay only; local-native mode should not inherit date-specific cash floors.
- disable_requirement: Safe early-disable candidate when leaving JQ parity, with the expectation that only order acceptance and downstream NAV change.
- delete_requirement: Delete when JQ pre-open rejection replay is no longer a supported mode.
- acceptance_test: tools/hook_migration_acceptance.py targeted 2025 preopen cash floor check

### `execution.preopen_reject_orders`
- Module: `rebuild_from_archive.compat.execution`
- Symbol: `PREOPEN_REJECT_ORDERS`
- Behavior: Reject whole pre-open orders for explicit date/code pairs.
- semantic_type / disposition / status: `jq_platform_behavior` / `archive_jq_only` / `archive_candidate`
- Wave: `L2`
- Affected fields: `preopen_order_acceptance`
- Trigger dates: ``
- Trigger codes: ``
- Effects: selection=no, state=no, order=yes, fill=no, nav=no
- direct_effect_scope: `['order_presence']`
- downstream_risk: `strategy_path`
- empty_config: `yes`
- Reason: This is only meaningful for replaying specific historical JoinQuant refusals.
- Evidence: engine/core.py calls compat.should_reject_preopen_order inside _should_reject_jq_preopen_order.
- Runtime call sites: `rebuild_from_archive/engine\core.py:487:            and self.compat.should_reject_preopen_order(date_key, security); rebuild_from_archive/project_compat.py:108:    def should_reject_preopen_order(self, date_key, security):`
- Secondary references: `tools\audit_hook_disposition.py:527:        call_site_patterns=["should_reject_preopen_order("],; tools\hook_migration_acceptance.py:135:    def should_reject_preopen_order(self, date_key, security):; tools\hook_migration_acceptance.py:136:        reject = self._base.should_reject_preopen_order(date_key, security)`
- target_owner: `jq_archive`
- handoff_requirement: Keep only with the archived JQ execution profile.
- disable_requirement: Can be disabled with JQ parity hooks; impacts order presence but not upstream candidate logic.
- delete_requirement: Delete after dropping archived JoinQuant pre-open order replay support.
- acceptance_test: Inventory scan only; current set is empty so retirement risk is low.

### `execution.preopen_drop_first_duplicate`
- Module: `rebuild_from_archive.compat.execution`
- Symbol: `PREOPEN_DROP_FIRST_DUPLICATE`
- Behavior: Drop the first duplicate pre-open pending order on recorded dates to match JoinQuant queue behavior.
- semantic_type / disposition / status: `jq_platform_behavior` / `archive_jq_only` / `archive_candidate`
- Wave: `L2`
- Affected fields: `pending_orders`
- Trigger dates: `2021-04-26; 2021-12-01; 2021-12-08; 2022-08-02; 2022-11-24; 2022-12-02`
- Trigger codes: `000547.XSHE; 000600.XSHE; 002120.XSHE; 002508.XSHE; 600072.XSHG; 603589.XSHG`
- Effects: selection=no, state=no, order=yes, fill=no, nav=no
- direct_effect_scope: `['order_presence']`
- downstream_risk: `strategy_path`
- empty_config: `no`
- Reason: This duplicates a platform queue quirk, not a stable project rule.
- Evidence: engine/core.py calls compat.should_drop_first_preopen_duplicate inside _apply_jq_preopen_duplicate_order_anomaly.
- Runtime call sites: `rebuild_from_archive/engine\core.py:505:            or not self.compat.should_drop_first_preopen_duplicate(date_key, order.security); rebuild_from_archive/project_compat.py:111:    def should_drop_first_preopen_duplicate(self, date_key, security):`
- Secondary references: `tools\audit_hook_disposition.py:554:        call_site_patterns=["should_drop_first_preopen_duplicate("],; tools\hook_migration_acceptance.py:140:    def should_drop_first_preopen_duplicate(self, date_key, security):; tools\hook_migration_acceptance.py:141:        drop = self._base.should_drop_first_preopen_duplicate(date_key, security); tools\hook_migration_acceptance.py:536:    dup = compat.should_drop_first_preopen_duplicate("2021-12-01", "600072.XSHG")`
- target_owner: `jq_archive`
- handoff_requirement: Keep only in the JQ replay profile; local-native should use native duplicate-order handling.
- disable_requirement: Can be disabled with only order-path effects once JQ parity is no longer required.
- delete_requirement: Delete after archived JoinQuant duplicate-order replay is retired.
- acceptance_test: tools/hook_migration_acceptance.py targeted 2021 preopen duplicate check

### `execution.execution_price_anomalies`
- Module: `rebuild_from_archive.compat.execution`
- Symbol: `EXECUTION_PRICE_ANOMALIES`
- Behavior: Force execution prices for specific date/time/code/side combinations on the parity path.
- semantic_type / disposition / status: `jq_platform_behavior` / `archive_jq_only` / `archive_candidate`
- Wave: `L1A`
- Affected fields: `trade_price`
- Trigger dates: `2020-01-16; 2020-01-20; 2020-01-21; 2020-01-22; 2020-02-06; 2020-02-10; 2020-02-11; 2020-02-12; 2020-02-14; 2020-02-18; 2020-02-19; 2020-02-20; 2020-02-24; 2020-02-25; 2020-02-26; 2020-02-27; 2020-03-02; 2020-03-04; 2020-03-05; 2020-03-11; 2020-03-12; 2020-03-13; 2020-03-17; 2020-03-18; 2020-03-19; 2020-03-25; 2020-03-27; 2020-03-30; 2020-03-31; 2020-04-02; 2020-04-03; 2020-04-08; 2020-04-14; 2020-04-15; 2020-04-16; 2020-04-17; 2020-04-22; 2020-04-27; 2020-05-12; 2020-05-14; 2020-05-15; 2020-05-18; 2020-05-19; 2020-05-20; 2020-06-02; 2020-06-03; 2020-06-04; 2020-06-05; 2020-06-08; 2020-06-09; 2020-06-10; 2020-06-11; 2020-06-12; 2020-06-16; 2020-06-17; 2020-06-18; 2020-06-19; 2020-06-22; 2020-06-23; 2020-06-24; 2020-06-29; 2020-06-30; 2020-07-01; 2020-07-03; 2020-07-06; 2020-07-07; 2020-07-08; 2020-07-09; 2020-08-20; 2023-02-27; 2023-03-23; 2023-12-12`
- Trigger codes: `000034.XSHE; 000049.XSHE; 000505.XSHE; 000592.XSHE; 000650.XSHE; 000700.XSHE; 000800.XSHE; 000818.XSHE; 000987.XSHE; 002041.XSHE; 002063.XSHE; 002075.XSHE; 002079.XSHE; 002137.XSHE; 002156.XSHE; 002183.XSHE; 002184.XSHE; 002185.XSHE; 002208.XSHE; 002221.XSHE; 002229.XSHE; 002279.XSHE; 002340.XSHE; 002351.XSHE; 002365.XSHE; 002371.XSHE; 002395.XSHE; 002402.XSHE; 002409.XSHE; 002413.XSHE; 002428.XSHE; 002444.XSHE; 002466.XSHE; 002470.XSHE; 002532.XSHE; 002596.XSHE; 002603.XSHE; 002605.XSHE; 002612.XSHE; 002686.XSHE; 002873.XSHE; 002891.XSHE; 002915.XSHE; 002930.XSHE; 002935.XSHE; 300037.XSHE; 300448.XSHE; 300463.XSHE; 300677.XSHE; 600027.XSHG; 600095.XSHG; 600126.XSHG; 600143.XSHG; 600198.XSHG; 600221.XSHG; 600223.XSHG; 600241.XSHG; 600268.XSHG; 600315.XSHG; 600318.XSHG; 600469.XSHG; 600515.XSHG; 600518.XSHG; 600550.XSHG; 600654.XSHG; 600812.XSHG; 600831.XSHG; 600859.XSHG; 600884.XSHG; 600966.XSHG; 600973.XSHG; 600988.XSHG; 601330.XSHG; 601788.XSHG; 601908.XSHG; 601999.XSHG; 603083.XSHG; 603101.XSHG; 603185.XSHG; 603186.XSHG; 603608.XSHG; 603626.XSHG; 603788.XSHG; 603912.XSHG`
- Effects: selection=no, state=no, order=no, fill=yes, nav=yes
- direct_effect_scope: `['price']`
- downstream_risk: `cash_path`
- empty_config: `no`
- Reason: These are historical fill answers, not a general-purpose matcher rule.
- Evidence: engine/core.py queries get_execution_price_override inside _apply_jq_execution_price_anomaly during order matching.
- Runtime call sites: `rebuild_from_archive/engine\core.py:1133:                override = self.compat.get_execution_price_override(day_key, norm_time, security, side); rebuild_from_archive/project_compat.py:94:    def get_execution_price_override(self, date_key, time_key, security, side):`
- Secondary references: `tests\test_compat_entrypoints.py:12:    assert compat.get_execution_price_override("20230323", "09:30", "600518.XSHG", "buy") == 2.16; tools\audit_hook_disposition.py:581:        call_site_patterns=["get_execution_price_override("],; tools\hook_migration_acceptance.py:115:    def get_execution_price_override(self, date_key, time_key, security, side):; tools\hook_migration_acceptance.py:116:        value = self._base.get_execution_price_override(date_key, time_key, security, side)`
- target_owner: `jq_archive`
- handoff_requirement: Archive with the JQ replay execution profile; do not upstream to local-native matching.
- disable_requirement: Good first-wave disable candidate for local-native if fill-price drift is acceptable.
- delete_requirement: Delete after JoinQuant execution-price parity is no longer maintained.
- acceptance_test: tests/test_compat_entrypoints.py::test_minute_and_execution_overrides

### `execution.order_amount_anomalies`
- Module: `rebuild_from_archive.compat.execution`
- Symbol: `ORDER_AMOUNT_ANOMALIES`
- Behavior: Force order quantities for specific pre-open or open events on the mother replay path.
- semantic_type / disposition / status: `jq_platform_behavior` / `archive_jq_only` / `archive_candidate`
- Wave: `L1B`
- Affected fields: `order_amount`
- Trigger dates: `2020-02-10; 2020-03-02; 2020-03-04; 2020-03-09; 2020-03-10; 2020-03-11; 2020-03-12; 2020-03-16; 2020-03-18; 2020-03-27; 2020-03-30; 2020-04-02; 2020-04-13; 2020-04-14; 2020-04-21; 2020-04-24; 2020-04-27; 2020-04-30; 2020-05-18; 2020-06-15; 2020-06-30; 2020-07-02; 2020-07-06; 2020-07-14; 2020-08-20`
- Trigger codes: `000592.XSHE; 000700.XSHE; 000800.XSHE; 000859.XSHE; 000987.XSHE; 002022.XSHE; 002063.XSHE; 002075.XSHE; 002221.XSHE; 002365.XSHE; 002444.XSHE; 002596.XSHE; 002612.XSHE; 002661.XSHE; 600027.XSHG; 600086.XSHG; 600095.XSHG; 600126.XSHG; 600241.XSHG; 600400.XSHG; 600654.XSHG; 600856.XSHG; 600966.XSHG; 601975.XSHG; 603912.XSHG`
- Effects: selection=no, state=no, order=yes, fill=yes, nav=yes
- direct_effect_scope: `['size']`
- downstream_risk: `position_path`
- empty_config: `no`
- Reason: These are historical mother-path answers, not reusable sizing logic.
- Evidence: engine/core.py applies get_order_amount_override inside _apply_jq_order_amount_anomaly before creating orders.
- Runtime call sites: `rebuild_from_archive/engine\core.py:1147:                override = self.compat.get_order_amount_override(day_key, norm_time, security); rebuild_from_archive/project_compat.py:98:    def get_order_amount_override(self, date_key, time_key, security):`
- Secondary references: `tests\test_compat_entrypoints.py:17:    assert compat.get_order_amount_override("20200518", "09:26", "000987.XSHE") == [38600, 33800]; tools\audit_hook_disposition.py:608:        call_site_patterns=["get_order_amount_override("],; tools\hook_migration_acceptance.py:120:    def get_order_amount_override(self, date_key, time_key, security):; tools\hook_migration_acceptance.py:121:        value = self._base.get_order_amount_override(date_key, time_key, security)`
- target_owner: `jq_archive`
- handoff_requirement: Keep only with the archived mother/JQ parity profile.
- disable_requirement: Can be disabled in local-native mode; expect trade-size and NAV drift but not upstream candidate changes.
- delete_requirement: Delete when the project stops preserving mother-path quantity parity.
- acceptance_test: tests/test_compat_entrypoints.py::test_order_amount_sequence_config_and_fill_override

### `execution.fill_amount_anomalies`
- Module: `rebuild_from_archive.compat.execution`
- Symbol: `FILL_AMOUNT_ANOMALIES`
- Behavior: Force fill share counts for specific orders when replaying archived fills.
- semantic_type / disposition / status: `jq_platform_behavior` / `archive_jq_only` / `archive_candidate`
- Wave: `L1B`
- Affected fields: `fill_amount`
- Trigger dates: `2020-04-02; 2020-04-16`
- Trigger codes: `002041.XSHE; 600086.XSHG`
- Effects: selection=no, state=no, order=no, fill=yes, nav=yes
- direct_effect_scope: `['size']`
- downstream_risk: `position_path`
- empty_config: `no`
- Reason: This is fill-answer replay, not a generic exchange or broker rule.
- Evidence: engine/core.py applies get_fill_amount_override inside _apply_jq_fill_amount_anomaly during matching.
- Runtime call sites: `rebuild_from_archive/engine\core.py:1174:                override = self.compat.get_fill_amount_override(day_key, norm_time, security); rebuild_from_archive/project_compat.py:101:    def get_fill_amount_override(self, date_key, time_key, security):`
- Secondary references: `tests\test_compat_entrypoints.py:18:    assert compat.get_fill_amount_override("20200416", "09:30", "002041.XSHE") == 39300; tools\audit_hook_disposition.py:635:        call_site_patterns=["get_fill_amount_override("],; tools\hook_migration_acceptance.py:125:    def get_fill_amount_override(self, date_key, time_key, security):; tools\hook_migration_acceptance.py:126:        value = self._base.get_fill_amount_override(date_key, time_key, security)`
- target_owner: `jq_archive`
- handoff_requirement: Archive with other JQ-only fill answer hooks.
- disable_requirement: Can be disabled with only fill and NAV consequences once parity mode is not required.
- delete_requirement: Delete after archived fill-size parity support is retired.
- acceptance_test: tests/test_compat_entrypoints.py::test_order_amount_sequence_config_and_fill_override

### `call_auction.empty_anomalies`
- Module: `rebuild_from_archive.compat.call_auction`
- Symbol: `CALL_AUCTION_EMPTY_ANOMALIES`
- Behavior: Remove specific call-auction rows entirely before candidate logic consumes them.
- semantic_type / disposition / status: `data_correction` / `investigate` / `investigation_pending`
- Wave: `—`
- Affected fields: `call_auction_rows`
- Trigger dates: `2020-03-04; 2021-08-18; 2021-09-01`
- Trigger codes: `002897.XSHE; 600804.XSHG; 600982.XSHG; 603908.XSHG`
- Effects: selection=yes, state=yes, order=no, fill=no, nav=no
- direct_effect_scope: `['data_shape']`
- downstream_risk: `strategy_path`
- empty_config: `no`
- Reason: The current evidence shows row suppression but does not yet prove whether the source is wrong or JoinQuant-only.
- Evidence: project_compat.apply_call_auction_overrides removes rows keyed by CALL_AUCTION_EMPTY_ANOMALIES and engine/data_api.py calls it in get_call_auction.
- Runtime call sites: `rebuild_from_archive/engine\data_api.py:759:            df = self.compat.apply_call_auction_overrides(df); rebuild_from_archive/project_compat.py:149:    def apply_call_auction_overrides(self, frame):`
- Secondary references: `tests\test_compat_entrypoints.py:31:    out = compat.apply_call_auction_overrides(frame); tools\audit_hook_disposition.py:662:        call_site_patterns=["apply_call_auction_overrides("],; tools\audit_hook_disposition.py:689:        call_site_patterns=["apply_call_auction_overrides("],; tools\audit_hook_disposition.py:716:        call_site_patterns=["apply_call_auction_overrides("],; tools\hook_migration_acceptance.py:176:    def apply_call_auction_overrides(self, frame):; tools\hook_migration_acceptance.py:178:        out = self._base.apply_call_auction_overrides(frame)`
- target_owner: `investigation`
- handoff_requirement: Need source-vs-reference row-level evidence before assigning to HData or JQ archive.
- disable_requirement: Disable only after call-auction candidate behavior is accepted without these row deletions.
- delete_requirement: Delete once the source owner is assigned and either repaired upstream or archived as JQ-only.
- acceptance_test: tests/test_compat_entrypoints.py::test_call_auction_overrides_apply

### `call_auction.allow_only`
- Module: `rebuild_from_archive.compat.call_auction`
- Symbol: `CALL_AUCTION_ALLOW_ONLY`
- Behavior: Restrict a day's auction dataset to an allow-list of codes before ranking.
- semantic_type / disposition / status: `data_correction` / `investigate` / `investigation_pending`
- Wave: `—`
- Affected fields: `call_auction_rows`
- Trigger dates: `2021-08-18; 2021-12-02`
- Trigger codes: `000833.XSHE`
- Effects: selection=yes, state=yes, order=no, fill=no, nav=no
- direct_effect_scope: `['data_shape']`
- downstream_risk: `strategy_path`
- empty_config: `no`
- Reason: The allow-list may reflect source contamination or a JQ extract quirk; ownership is not yet proven.
- Evidence: project_compat.apply_call_auction_overrides enforces CALL_AUCTION_ALLOW_ONLY before candidate ranking reads the frame.
- Runtime call sites: `rebuild_from_archive/engine\data_api.py:759:            df = self.compat.apply_call_auction_overrides(df); rebuild_from_archive/project_compat.py:149:    def apply_call_auction_overrides(self, frame):`
- Secondary references: `tests\test_compat_entrypoints.py:31:    out = compat.apply_call_auction_overrides(frame); tools\audit_hook_disposition.py:662:        call_site_patterns=["apply_call_auction_overrides("],; tools\audit_hook_disposition.py:689:        call_site_patterns=["apply_call_auction_overrides("],; tools\audit_hook_disposition.py:716:        call_site_patterns=["apply_call_auction_overrides("],; tools\hook_migration_acceptance.py:176:    def apply_call_auction_overrides(self, frame):; tools\hook_migration_acceptance.py:178:        out = self._base.apply_call_auction_overrides(frame)`
- target_owner: `investigation`
- handoff_requirement: Need per-day upstream data evidence to decide whether this belongs in HData or the JQ archive bucket.
- disable_requirement: Disable only after accepting candidate drift for the affected dates in non-parity mode.
- delete_requirement: Delete after root-cause assignment and either source repair or archival.
- acceptance_test: tests/test_compat_entrypoints.py::test_call_auction_overrides_apply

### `call_auction.depth_overrides`
- Module: `rebuild_from_archive.compat.call_auction`
- Symbol: `CALL_AUCTION_DEPTH_OVERRIDES`
- Behavior: Patch specific call-auction depth fields before candidate ranking.
- semantic_type / disposition / status: `data_correction` / `investigate` / `investigation_pending`
- Wave: `—`
- Affected fields: `a1_v`
- Trigger dates: `2020-09-03; 2021-06-04`
- Trigger codes: `000038.XSHE; 002635.XSHE`
- Effects: selection=yes, state=yes, order=no, fill=no, nav=no
- direct_effect_scope: `['data_shape']`
- downstream_risk: `strategy_path`
- empty_config: `no`
- Reason: These look like source-field corrections, but current evidence is not strong enough to assign them permanently to HData.
- Evidence: project_compat.apply_call_auction_overrides patches the requested columns, and tests assert the 2020-09-03 override.
- Runtime call sites: `rebuild_from_archive/engine\data_api.py:759:            df = self.compat.apply_call_auction_overrides(df); rebuild_from_archive/project_compat.py:149:    def apply_call_auction_overrides(self, frame):`
- Secondary references: `tests\test_compat_entrypoints.py:31:    out = compat.apply_call_auction_overrides(frame); tools\audit_hook_disposition.py:662:        call_site_patterns=["apply_call_auction_overrides("],; tools\audit_hook_disposition.py:689:        call_site_patterns=["apply_call_auction_overrides("],; tools\audit_hook_disposition.py:716:        call_site_patterns=["apply_call_auction_overrides("],; tools\hook_migration_acceptance.py:176:    def apply_call_auction_overrides(self, frame):; tools\hook_migration_acceptance.py:178:        out = self._base.apply_call_auction_overrides(frame)`
- target_owner: `investigation`
- handoff_requirement: Need raw call-auction depth evidence and a source owner before handoff.
- disable_requirement: Disable only after proving candidate ranking is acceptable without the patched depth values.
- delete_requirement: Delete after source ownership is resolved and the patch is either repaired upstream or archived.
- acceptance_test: tests/test_compat_entrypoints.py::test_call_auction_overrides_apply

### `security_metadata.start_date_overrides`
- Module: `rebuild_from_archive.compat.security_metadata`
- Symbol: `SECURITY_START_DATE_OVERRIDES`
- Behavior: Replace listing dates for specific securities before IPO-age filters run.
- semantic_type / disposition / status: `data_correction` / `investigate` / `investigation_pending`
- Wave: `—`
- Affected fields: `start_date`
- Trigger dates: ``
- Trigger codes: `605123.XSHG; 605255.XSHG; 605369.XSHG; 605399.XSHG`
- Effects: selection=yes, state=no, order=no, fill=no, nav=no
- direct_effect_scope: `['data_shape']`
- downstream_risk: `strategy_path`
- empty_config: `no`
- Reason: Listing-date truth belongs to the data layer, but the discrepancy may reflect JoinQuant listing-date conventions rather than HData errors. Pending independent verification.
- Evidence: engine/data_api.py applies get_security_start_date_override while building _stock_basic for get_all_securities().
- Runtime call sites: `rebuild_from_archive/engine\data_api.py:992:                    start_date = self.compat.get_security_start_date_override(code); rebuild_from_archive/project_compat.py:118:    def get_security_start_date_override(self, security):`
- Secondary references: `tools\audit_hook_disposition.py:743:        call_site_patterns=["get_security_start_date_override("],; tools\hook_migration_acceptance.py:171:    def get_security_start_date_override(self, security):; tools\hook_migration_acceptance.py:172:        value = self._base.get_security_start_date_override(security); tools\hook_migration_acceptance.py:506:        start_override = compat.get_security_start_date_override(case["code"])`
- target_owner: `hdata_candidate`
- handoff_requirement: HData needs a corrected listing-date source or overlay for these securities.
- disable_requirement: Disable only after stock_basic or its replacement publishes correct PIT listing dates.
- delete_requirement: Delete after HData ships corrected listing dates and all IPO-age filters read them directly.
- acceptance_test: tools/hook_migration_acceptance.py targeted 2020 IPO override checks

### `security_metadata.non_st_name_windows`
- Module: `rebuild_from_archive.compat.security_metadata`
- Symbol: `NON_ST_NAME_WINDOWS`
- Behavior: Strip future ST or delisting markers from PIT display names inside explicit date windows.
- semantic_type / disposition / status: `data_correction` / `investigate` / `investigation_pending`
- Wave: `—`
- Affected fields: `display_name`
- Trigger dates: `1900-01-01; 2020-02-28; 2020-05-06; 2020-07-15; 2020-08-25; 2020-08-27; 2020-09-09; 2020-10-23; 2020-11-23; 2020-11-30; 2020-12-14; 2020-12-18; 2021-01-14; 2021-04-21; 2021-09-10; 2021-12-10; 2022-02-07; 2022-02-08; 2022-02-10; 2022-02-15; 2022-03-02; 2022-03-15; 2022-04-01; 2022-04-19; 2022-07-05; 2023-01-03; 2023-03-22; 2023-04-10; 2023-06-01; 2024-04-22; 2024-06-07; 2024-06-20; 2024-06-27; 2024-07-15; 2024-08-07; 2025-07-22; 2025-07-24; 2026-02-12`
- Trigger codes: `000506.XSHE; 000584.XSHE; 000585.XSHE; 000673.XSHE; 000839.XSHE; 000980.XSHE; 002052.XSHE; 002086.XSHE; 002141.XSHE; 002147.XSHE; 002192.XSHE; 002256.XSHE; 002470.XSHE; 002638.XSHE; 002684.XSHE; 600091.XSHG; 600093.XSHG; 600145.XSHG; 600146.XSHG; 600191.XSHG; 600242.XSHG; 600255.XSHG; 600518.XSHG; 600532.XSHG; 600654.XSHG; 600666.XSHG; 600687.XSHG; 600702.XSHG; 600711.XSHG; 600856.XSHG; 601020.XSHG; 603003.XSHG; 603030.XSHG; 603268.XSHG; 603880.XSHG`
- Effects: selection=yes, state=no, order=no, fill=no, nav=no
- direct_effect_scope: `['data_shape']`
- downstream_risk: `strategy_path`
- empty_config: `no`
- Reason: Historical security-name state is source metadata, but the divergence may stem from JoinQuant name-history conventions vs local data PIT snapshots. Pending independent verification.
- Evidence: project_compat.apply_security_name_overrides applies NON_ST_NAME_WINDOWS after reading daily ST state and before strategy filters consume display_name.
- Runtime call sites: `rebuild_from_archive/engine\data_api.py:107:            return self.compat.apply_security_name_overrides(self, out, date); rebuild_from_archive/project_compat.py:310:    def apply_security_name_overrides(self, api, out, date):`
- Secondary references: `alignment_reports\align_worktree_diff_2020-01-02_2021-12-31.patch:394:+            return self.compat.apply_security_name_overrides(self, out, date); tools\audit_hook_disposition.py:770:        call_site_patterns=["apply_security_name_overrides("],; tools\audit_hook_disposition.py:797:        call_site_patterns=["apply_security_name_overrides("],; tools\hook_migration_acceptance.py:188:    def apply_security_name_overrides(self, api, out, date):; tools\hook_migration_acceptance.py:190:        result = self._base.apply_security_name_overrides(api, out, date)`
- target_owner: `hdata_candidate`
- handoff_requirement: HData needs PIT name history or equivalent metadata to eliminate these date-window strips.
- disable_requirement: Disable only after display_name is PIT-correct for affected windows.
- delete_requirement: Delete after PIT name history is available and strategy filters no longer need compat name surgery.
- acceptance_test: tools/hook_migration_acceptance.py targeted 2021 ST name window check

### `security_metadata.special_display_name_rules`
- Module: `rebuild_from_archive.project_compat`
- Symbol: `EmotionGateJQCompat.apply_security_name_overrides`
- Behavior: Apply extra security-name compatibility rules beyond the window table, including explicit special-code branches.
- semantic_type / disposition / status: `unknown` / `investigate` / `investigation_pending`
- Wave: `—`
- Affected fields: `display_name`
- Trigger dates: `2020-05-07; 2022-04-18`
- Trigger codes: `001270.XSHE; 600856.XSHG`
- Effects: selection=yes, state=no, order=no, fill=no, nav=no
- direct_effect_scope: `['data_shape']`
- downstream_risk: `strategy_path`
- empty_config: `no`
- Reason: The special-case branches mix PIT naming concerns with hardcoded stock-specific logic and need decomposition before ownership can be assigned.
- Evidence: project_compat.apply_security_name_overrides contains special handling for 001270.XSHE and 600856.XSHG outside NON_ST_NAME_WINDOWS.
- Runtime call sites: `rebuild_from_archive/engine\data_api.py:107:            return self.compat.apply_security_name_overrides(self, out, date); rebuild_from_archive/project_compat.py:310:    def apply_security_name_overrides(self, api, out, date):`
- Secondary references: `alignment_reports\align_worktree_diff_2020-01-02_2021-12-31.patch:394:+            return self.compat.apply_security_name_overrides(self, out, date); tools\audit_hook_disposition.py:770:        call_site_patterns=["apply_security_name_overrides("],; tools\audit_hook_disposition.py:797:        call_site_patterns=["apply_security_name_overrides("],; tools\hook_migration_acceptance.py:188:    def apply_security_name_overrides(self, api, out, date):; tools\hook_migration_acceptance.py:190:        result = self._base.apply_security_name_overrides(api, out, date)`
- target_owner: `investigation`
- handoff_requirement: Split general PIT name logic from single-stock legacy rules and re-evaluate ownership.
- disable_requirement: Disable only after each remaining special-case is either absorbed by PIT metadata or explicitly archived as JQ-only.
- delete_requirement: Delete after the method no longer needs stock-specific name branches.
- acceptance_test: Inventory scan and manual review of project_compat.apply_security_name_overrides branches

### `security_metadata.adjust_extras_is_st`
- Module: `rebuild_from_archive.project_compat`
- Symbol: `EmotionGateJQCompat.adjust_extras_is_st`
- Behavior: Override is_st results using PIT name and end-date heuristics for specific windows and codes.
- semantic_type / disposition / status: `data_correction` / `investigate` / `investigation_pending`
- Wave: `—`
- Affected fields: `is_st, display_name, end_date`
- Trigger dates: `2020-05-07; 2024-05-01; 2024-06-03`
- Trigger codes: `600856.XSHG`
- Effects: selection=yes, state=no, order=no, fill=no, nav=no
- direct_effect_scope: `['data_shape']`
- downstream_risk: `strategy_path`
- empty_config: `no`
- Reason: ST state and delisting-state truth should come from source metadata, but the divergence may reflect JoinQuant ST classification conventions rather than HData errors. Pending verification.
- Evidence: engine/data_api.py calls compat.adjust_extras_is_st from get_extras('is_st', ...), and project_compat.py embeds date windows and name/end_date heuristics.
- Runtime call sites: `rebuild_from_archive/engine\data_api.py:1031:                is_st = self.compat.adjust_extras_is_st(self, s, ds_dt, is_st); rebuild_from_archive/project_compat.py:354:    def adjust_extras_is_st(self, api, security, date, is_st):`
- Secondary references: `alignment_reports\align_worktree_diff_2020-01-02_2021-12-31.patch:633:+                is_st = self.compat.adjust_extras_is_st(self, s, ds_dt, is_st); tools\audit_hook_disposition.py:827:        call_site_patterns=["adjust_extras_is_st("],; tools\hook_migration_acceptance.py:199:    def adjust_extras_is_st(self, api, security, date, is_st):; tools\hook_migration_acceptance.py:200:        value = self._base.adjust_extras_is_st(api, security, date, is_st)`
- target_owner: `hdata_candidate`
- handoff_requirement: HData needs PIT ST status and delisting-state history that match the project's required query dates.
- disable_requirement: Disable only after get_extras('is_st') reads corrected PIT ST state directly.
- delete_requirement: Delete after ST state is natively correct and the project no longer patches it post-query.
- acceptance_test: tools/hook_migration_acceptance.py targeted 2024 ST rule check

### `security_metadata.billboard_row_filters`
- Module: `rebuild_from_archive.compat.security_metadata`
- Symbol: `BILLBOARD_ROW_FILTERS`
- Behavior: Drop specific billboard rows before strategy-side candidate logic reads them.
- semantic_type / disposition / status: `data_correction` / `investigate` / `investigation_pending`
- Wave: `—`
- Affected fields: `billboard_rows`
- Trigger dates: `2020-02-26; 2022-08-25`
- Trigger codes: `600146.XSHG; 603721.XSHG`
- Effects: selection=yes, state=no, order=no, fill=no, nav=no
- direct_effect_scope: `['data_shape']`
- downstream_risk: `strategy_path`
- empty_config: `no`
- Reason: This looks like data cleanup, but the current evidence does not yet prove whether the underlying billboard source or JoinQuant export is wrong.
- Evidence: engine/data_api.py calls compat.filter_billboard_rows in get_billboard_list, and project_compat.filter_billboard_rows keys off BILLBOARD_ROW_FILTERS.
- Runtime call sites: `rebuild_from_archive/engine\data_api.py:1073:                df = self.compat.filter_billboard_rows(df); rebuild_from_archive/project_compat.py:369:    def filter_billboard_rows(self, frame):`
- Secondary references: `alignment_reports\align_worktree_diff_2020-01-02_2021-12-31.patch:649:+                df = self.compat.filter_billboard_rows(df); tools\audit_hook_disposition.py:857:        call_site_patterns=["filter_billboard_rows("],; tools\hook_migration_acceptance.py:204:    def filter_billboard_rows(self, frame):; tools\hook_migration_acceptance.py:205:        out = self._base.filter_billboard_rows(frame); tools\run_counterfactual_2024_000506_billboard_filter.py:29:    def filter_billboard_rows(self, frame):; tools\run_counterfactual_2024_000506_billboard_filter.py:30:        frame = super().filter_billboard_rows(frame)`
- target_owner: `investigation`
- handoff_requirement: Need row-level upstream billboard evidence before assigning to HData or archive-only replay.
- disable_requirement: Disable only after validating candidate behavior on affected dates without the row drop.
- delete_requirement: Delete after root cause is assigned and addressed by the right owner.
- acceptance_test: tools/run_counterfactual_2024_000506_billboard_filter.py demonstrates nearby workflow but not full retirement criteria.

### `instrument_fallbacks.price_fallbacks`
- Module: `rebuild_from_archive.compat.instrument_fallbacks`
- Symbol: `INSTRUMENT_PRICE_FALLBACKS`
- Behavior: Serve synthetic daily prices for instruments missing or unusable in the local data path.
- semantic_type / disposition / status: `data_correction` / `investigate` / `investigation_pending`
- Wave: `—`
- Affected fields: `open, close, high, low, volume, money`
- Trigger dates: `2024-01-02; 2024-01-03; 2024-01-04; 2024-01-05; 2024-01-08; 2024-01-09; 2024-01-10; 2024-01-11; 2024-01-12; 2024-01-15; 2024-01-16; 2024-01-17; 2024-01-18; 2024-01-19; 2024-01-22; 2024-01-23; 2024-01-24; 2024-01-25; 2024-01-26; 2024-01-29; 2024-01-30; 2024-01-31; 2024-02-01; 2024-04-01; 2024-05-06`
- Trigger codes: `511880.XSHG`
- Effects: selection=yes, state=no, order=yes, fill=no, nav=yes
- direct_effect_scope: `['data_shape']`
- downstream_risk: `position_path`
- empty_config: `no`
- Reason: Instrument price history should come from the data layer, but the absence may reflect data-coverage gaps rather than HData errors. Pending verification.
- Evidence: engine/data_api.py short-circuits get_price via compat.get_instrument_price_fallback before touching local price tables.
- Runtime call sites: `rebuild_from_archive/engine\data_api.py:400:            fallback = self.compat.get_instrument_price_fallback(; rebuild_from_archive/project_compat.py:121:    def get_instrument_price_fallback(self, security, start_date=None, end_date=None):`
- Secondary references: `tests\test_compat_entrypoints.py:52:    fallback = compat.get_instrument_price_fallback("511880.XSHG", end_date="2024-01-02"); tools\audit_hook_disposition.py:884:        call_site_patterns=["get_instrument_price_fallback("],; tools\hook_migration_acceptance.py:151:    def get_instrument_price_fallback(self, security, start_date=None, end_date=None):; tools\hook_migration_acceptance.py:152:        value = self._base.get_instrument_price_fallback(security, start_date=start_date, end_date=end_date)`
- target_owner: `hdata_candidate`
- handoff_requirement: HData needs complete and trustworthy history for the fallback instruments or an explicit supported-source overlay.
- disable_requirement: Disable only after local data can serve these instruments directly without synthetic rows.
- delete_requirement: Delete after HData publishes native coverage and no call path reaches get_instrument_price_fallback.
- acceptance_test: tests/test_compat_entrypoints.py::test_strategy_state_override_and_instrument_fallback

### `instrument_fallbacks.zero_fee_overrides`
- Module: `rebuild_from_archive.compat.instrument_fallbacks`
- Symbol: `ZERO_FEE_OVERRIDES`
- Behavior: Treat specific instruments as zero-fee in the engine fee path.
- semantic_type / disposition / status: `market_rule` / `move_to_local_quant` / `handoff_pending`
- Wave: `—`
- Affected fields: `commission, tax`
- Trigger dates: ``
- Trigger codes: `511880.XSHG`
- Effects: selection=no, state=no, order=no, fill=yes, nav=yes
- direct_effect_scope: `['fee']`
- downstream_risk: `nav_only`
- empty_config: `no`
- Reason: Fee classification belongs in the generic instrument/fee model, not in project compat constants.
- Evidence: engine/core.py calls compat.has_zero_fee_override from buy/sell fee estimation and realized fee logic.
- Runtime call sites: `rebuild_from_archive/engine\core.py:403:                    if self._has_zero_fee_override(security):; rebuild_from_archive/engine\core.py:426:                if self._has_zero_fee_override(security):; rebuild_from_archive/engine\core.py:451:    def _has_zero_fee_override(self, security):; rebuild_from_archive/engine\core.py:455:            and self.compat.has_zero_fee_override(security); rebuild_from_archive/engine\core.py:797:            if self._has_zero_fee_override(security):; rebuild_from_archive/engine\core.py:811:                if self._has_zero_fee_override(security):; rebuild_from_archive/engine\core.py:830:        if self._has_zero_fee_override(security):; rebuild_from_archive/project_compat.py:146:    def has_zero_fee_override(self, security):`
- Secondary references: `tests\test_compat_entrypoints.py:54:    assert compat.has_zero_fee_override("511880.XSHG") is True; tools\audit_hook_disposition.py:911:        call_site_patterns=["has_zero_fee_override("],; tools\hook_migration_acceptance.py:156:    def has_zero_fee_override(self, security):; tools\hook_migration_acceptance.py:157:        value = self._base.has_zero_fee_override(security); tools\hook_migration_acceptance.py:546:    zero_fee = compat.has_zero_fee_override("511880.XSHG")`
- target_owner: `local_quant`
- handoff_requirement: local_quant needs instrument-class-aware fee configuration that covers these cases natively.
- disable_requirement: Disable only after fee policy is modeled in local_quant by instrument type or explicit configuration.
- delete_requirement: Delete after engine/core.py no longer checks compat.has_zero_fee_override and fee policy is generic.
- acceptance_test: tests/test_compat_entrypoints.py::test_strategy_state_override_and_instrument_fallback

### `strategy_state.fb_state_overrides`
- Module: `rebuild_from_archive.compat.strategy_state`
- Symbol: `FB_STATE_OVERRIDES`
- Behavior: Force first-board performance state snapshots on specific dates after fb-state computation.
- semantic_type / disposition / status: `jq_platform_behavior` / `archive_jq_only` / `archive_candidate`
- Wave: `L3`
- Affected fields: `first_board_perf, fb_pct, fb_perf_history`
- Trigger dates: `2020-08-05; 2020-08-26; 2020-09-17`
- Trigger codes: ``
- Effects: selection=yes, state=yes, order=yes, fill=no, nav=no
- direct_effect_scope: `['state']`
- downstream_risk: `strategy_path`
- empty_config: `no`
- Reason: These dates preserve historical JoinQuant state answers and do not represent a reusable project rule.
- Evidence: 母版-20260506-Clone.py calls apply_project_strategy_compat('after_fb_state', ...) and project_compat.apply_strategy_state_override applies FB_STATE_OVERRIDES.
- Runtime call sites: `rebuild_from_archive/project_compat.py:174:    def apply_strategy_state_override(self, stage, context, state=None):; rebuild_from_archive/project_compat.py:75:            "apply_project_strategy_compat": lambda stage, context, state=None: self.apply_strategy_state_override(; 母版-20260506-Clone.py:266:    apply_project_strategy_compat("after_fb_state", context, g); 母版-20260506-Clone.py:271:    apply_project_strategy_compat("after_v227_shock", context, g)`
- Secondary references: `alignment_reports\compat_hook_migration_report.md:11:- `母版-20260506-Clone.py` 的策略状态兼容已改为 `apply_project_strategy_compat(...)` 单入口；; alignment_reports\compat_hook_migration_report.md:54:当前运行时代码中，兼容事实应通过 `EmotionGateJQCompat` 或 `apply_project_strategy_compat(...)` 暴露，不再由调用点各自维护散落字典。; tests\test_compat_entrypoints.py:43:    compat.apply_strategy_state_override("after_fb_state", context, state); tests\test_compat_entrypoints.py:49:    compat.apply_strategy_state_override("after_v227_shock", context2, state); tools\audit_hook_disposition.py:1117:        evidence="Engine.__init__ merges compat.namespace_entries(self), and 母版-20260506-Clone.py calls apply_project_strategy_compat(...) at fixed stages.",; tools\audit_hook_disposition.py:1132:        call_site_patterns=["namespace_entries(", "apply_project_strategy_compat("],; tools\audit_hook_disposition.py:923:        evidence="母版-20260506-Clone.py calls apply_project_strategy_compat('after_fb_state', ...) and project_compat.apply_strategy_state_override applies FB_STATE_OVERRIDES.",; tools\audit_hook_disposition.py:938:        call_site_patterns=["apply_project_strategy_compat(", "apply_strategy_state_override("],; tools\audit_hook_disposition.py:950:        evidence="母版-20260506-Clone.py calls apply_project_strategy_compat('after_v227_shock', ...) and project_compat.apply_strategy_state_override applies V227_SHOCK_OVERRIDES.",; tools\audit_hook_disposition.py:965:        call_site_patterns=["apply_project_strategy_compat(", "apply_strategy_state_override("],; tools\hook_migration_acceptance.py:145:    def apply_strategy_state_override(self, stage, context, state=None):; tools\hook_migration_acceptance.py:146:        value = self._base.apply_strategy_state_override(stage, context, state); tools\hook_migration_acceptance.py:541:    override = compat.apply_strategy_state_override("after_v227_shock", context, state); tools\hook_migration_acceptance.py:88:        entries['apply_project_strategy_compat'] = lambda stage, context, state=None: self.apply_strategy_state_override(stage, context, state)`
- target_owner: `jq_archive`
- handoff_requirement: Keep only with the archived JQ replay profile; local-native state should derive from native computations.
- disable_requirement: Do not disable until local-native mode explicitly accepts candidate/state divergence on these dates.
- delete_requirement: Delete after the project stops supporting JoinQuant state-snapshot replay.
- acceptance_test: tests/test_compat_entrypoints.py::test_strategy_state_override_and_instrument_fallback

### `strategy_state.v227_shock_overrides`
- Module: `rebuild_from_archive.compat.strategy_state`
- Symbol: `V227_SHOCK_OVERRIDES`
- Behavior: Force v227 shock cooldown state on a recorded retreat day after the strategy computes shock state.
- semantic_type / disposition / status: `jq_platform_behavior` / `archive_jq_only` / `archive_candidate`
- Wave: `L3`
- Affected fields: `v227_shock_cooldown`
- Trigger dates: `2023-02-17`
- Trigger codes: ``
- Effects: selection=yes, state=yes, order=yes, fill=no, nav=no
- direct_effect_scope: `['state']`
- downstream_risk: `strategy_path`
- empty_config: `no`
- Reason: This is a historical parity answer for one state transition, not a general strategy definition.
- Evidence: 母版-20260506-Clone.py calls apply_project_strategy_compat('after_v227_shock', ...) and project_compat.apply_strategy_state_override applies V227_SHOCK_OVERRIDES.
- Runtime call sites: `rebuild_from_archive/project_compat.py:174:    def apply_strategy_state_override(self, stage, context, state=None):; rebuild_from_archive/project_compat.py:75:            "apply_project_strategy_compat": lambda stage, context, state=None: self.apply_strategy_state_override(; 母版-20260506-Clone.py:266:    apply_project_strategy_compat("after_fb_state", context, g); 母版-20260506-Clone.py:271:    apply_project_strategy_compat("after_v227_shock", context, g)`
- Secondary references: `alignment_reports\compat_hook_migration_report.md:11:- `母版-20260506-Clone.py` 的策略状态兼容已改为 `apply_project_strategy_compat(...)` 单入口；; alignment_reports\compat_hook_migration_report.md:54:当前运行时代码中，兼容事实应通过 `EmotionGateJQCompat` 或 `apply_project_strategy_compat(...)` 暴露，不再由调用点各自维护散落字典。; tests\test_compat_entrypoints.py:43:    compat.apply_strategy_state_override("after_fb_state", context, state); tests\test_compat_entrypoints.py:49:    compat.apply_strategy_state_override("after_v227_shock", context2, state); tools\audit_hook_disposition.py:1117:        evidence="Engine.__init__ merges compat.namespace_entries(self), and 母版-20260506-Clone.py calls apply_project_strategy_compat(...) at fixed stages.",; tools\audit_hook_disposition.py:1132:        call_site_patterns=["namespace_entries(", "apply_project_strategy_compat("],; tools\audit_hook_disposition.py:923:        evidence="母版-20260506-Clone.py calls apply_project_strategy_compat('after_fb_state', ...) and project_compat.apply_strategy_state_override applies FB_STATE_OVERRIDES.",; tools\audit_hook_disposition.py:938:        call_site_patterns=["apply_project_strategy_compat(", "apply_strategy_state_override("],; tools\audit_hook_disposition.py:950:        evidence="母版-20260506-Clone.py calls apply_project_strategy_compat('after_v227_shock', ...) and project_compat.apply_strategy_state_override applies V227_SHOCK_OVERRIDES.",; tools\audit_hook_disposition.py:965:        call_site_patterns=["apply_project_strategy_compat(", "apply_strategy_state_override("],; tools\hook_migration_acceptance.py:145:    def apply_strategy_state_override(self, stage, context, state=None):; tools\hook_migration_acceptance.py:146:        value = self._base.apply_strategy_state_override(stage, context, state); tools\hook_migration_acceptance.py:541:    override = compat.apply_strategy_state_override("after_v227_shock", context, state); tools\hook_migration_acceptance.py:88:        entries['apply_project_strategy_compat'] = lambda stage, context, state=None: self.apply_strategy_state_override(stage, context, state)`
- target_owner: `jq_archive`
- handoff_requirement: Keep only for archived JQ replay; local-native should use native state transitions.
- disable_requirement: Do not disable until the project accepts branch-trigger drift for the affected date in local-native mode.
- delete_requirement: Delete after JQ shock-state replay is retired.
- acceptance_test: tools/hook_migration_acceptance.py targeted 2023 v227 shock check

### `project_feature.first_seal_loader`
- Module: `rebuild_from_archive.project_compat`
- Symbol: `EmotionGateJQCompat.load_first_seal_year`
- Behavior: Load and filter project first-seal cache rows before runtime sealing-point lookups use them.
- semantic_type / disposition / status: `project_infrastructure` / `retain_in_project` / `retain`
- Wave: `—`
- Affected fields: `first_limit_hit_time, project_cache/features/first_seal_time`
- Trigger dates: ``
- Trigger codes: ``
- Effects: selection=yes, state=no, order=no, fill=no, nav=no
- direct_effect_scope: `['infrastructure']`
- downstream_risk: `strategy_path`
- empty_config: `no`
- Reason: This is a project feature-cache integration point, not a generic market rule or external data fact.
- Evidence: engine/data_api.py delegates _load_project_first_seal_year to compat.load_first_seal_year and get_batch_sealing_points consumes the result.
- Runtime call sites: `rebuild_from_archive/engine\data_api.py:820:            return self.compat.load_first_seal_year(year); rebuild_from_archive/engine\data_api.py:838:    def get_batch_sealing_points(self, securities, date):; rebuild_from_archive/project_compat.py:224:    def load_first_seal_year(self, year):; 母版-20260506-Clone.py:798:            sealing_times = get_batch_sealing_points(g.yjj_candidates, yday)`
- Secondary references: `alignment_reports\align_worktree_diff_2020-01-02_2021-12-31.patch:462:+            return self.compat.load_first_seal_year(year); alignment_reports\align_worktree_diff_2020-01-02_2021-12-31.patch:525:     def get_batch_sealing_points(self, securities, date):; alignment_reports\alignment_configuration_notes.md:166:### 3.3 `get_batch_sealing_points()`; alignment_reports\alignment_final_report_2020_2026.md:193:  - `get_batch_sealing_points()` 改走 `get_price(... panel=False)`; alignment_reports\alignment_final_report_2020_2026.md:318:- `get_batch_sealing_points()` 改走可控路径; alignment_reports\alignment_summary_2020_2026.md:205:- `load_first_seal_year()` 在污染窗口跳过对应快缓存。; alignment_reports\alignment_summary_2020_2026.md:212:- `get_batch_sealing_points()` 改为使用 `get_price(... fields=['high_limit'], panel=False)`，避免直接依赖 `_history_cached(...)` 旧路径。; alignment_reports\alignment_summary_2020_2026.md:396:- `get_batch_sealing_points()` 从直接用底层缓存，改为走可控的 `get_price(... panel=False)`；; tools\audit_hook_disposition.py:360:        call_site_patterns=["should_bypass_history_fastpath(", "load_first_seal_year(", "get_project_board_snapshot("],; tools\audit_hook_disposition.py:992:        call_site_patterns=["load_first_seal_year(", "get_batch_sealing_points("],; tools\hook_migration_acceptance.py:529:    tail = api.get_batch_sealing_points(["000420.XSHE"], "2021-11-15").get("000420.XSHE")`
- target_owner: `emotion_gating_project`
- handoff_requirement: Retain while project-specific feature caches remain part of the strategy runtime.
- disable_requirement: Disable only if first-seal cache loading is removed or replaced by a different project feature pipeline.
- delete_requirement: Delete after the project no longer uses first_seal_time cache lookups in runtime or has moved them into a different project-owned service.
- acceptance_test: Inventory scan: verifies first_seal_time cache is loaded through compat integration point

### `project_feature.board_snapshot_accessor`
- Module: `rebuild_from_archive.project_compat`
- Symbol: `EmotionGateJQCompat.get_project_board_snapshot`
- Behavior: Expose project board-snapshot cache rows to strategy code as a project-specific fast path.
- semantic_type / disposition / status: `project_infrastructure` / `retain_in_project` / `retain`
- Wave: `—`
- Affected fields: `board_snapshot, board_count, is_first_board`
- Trigger dates: ``
- Trigger codes: ``
- Effects: selection=yes, state=yes, order=no, fill=no, nav=no
- direct_effect_scope: `['infrastructure']`
- downstream_risk: `strategy_path`
- empty_config: `no`
- Reason: Board snapshot is a project-derived feature accessor, not alpha logic. It belongs to the project infrastructure layer.
- Evidence: 母版-20260506-Clone.py reads get_project_board_snapshot(context.previous_date) for board scans; engine/data_api.py delegates through compat.
- Runtime call sites: `rebuild_from_archive/engine\data_api.py:823:    def get_project_board_snapshot(self, date):; rebuild_from_archive/engine\data_api.py:825:            return self.compat.get_project_board_snapshot(date); rebuild_from_archive/project_compat.py:247:    def get_project_board_snapshot(self, date):; rebuild_from_archive/project_compat.py:67:                engine.data_api.get_project_board_snapshot(*a, **kw); 母版-20260506-Clone.py:564:        board_df = get_project_board_snapshot(context.previous_date); 母版-20260506-Clone.py:666:        board_df = get_project_board_snapshot(context.previous_date)`
- Secondary references: `alignment_reports\align_worktree_diff_2020-01-02_2021-12-31.patch:232:-            'get_project_board_snapshot': lambda *a, **kw: self._wrap_pandas(self.data_api.get_project_board_snapshot(*a, **kw)),; alignment_reports\align_worktree_diff_2020-01-02_2021-12-31.patch:465:     def get_project_board_snapshot(self, date):; alignment_reports\align_worktree_diff_2020-01-02_2021-12-31.patch:481:+            return self.compat.get_project_board_snapshot(date); alignment_reports\alignment_summary_2020_2026.md:206:- `get_project_board_snapshot()` 在污染窗口直接返回空 `DataFrame()`，避免使用脏首板快照。; tools\audit_hook_disposition.py:1005:        evidence="母版-20260506-Clone.py reads get_project_board_snapshot(context.previous_date) for board scans; engine/data_api.py delegates through compat.",; tools\audit_hook_disposition.py:1020:        call_site_patterns=["get_project_board_snapshot("],; tools\audit_hook_disposition.py:360:        call_site_patterns=["should_bypass_history_fastpath(", "load_first_seal_year(", "get_project_board_snapshot("],`
- target_owner: `emotion_gating_project`
- handoff_requirement: Retain while the strategy depends on board_snapshot cache acceleration and project-specific data-quality policy.
- disable_requirement: Disable only if strategy switches to a different project-owned feature source or recomputes the logic natively.
- delete_requirement: Delete after project runtime no longer depends on board_snapshot compat exposure.
- acceptance_test: Inventory scan: verifies board_snapshot compat is used by strategy code on main path

### `project_feature.master_prepare_index_accessor`
- Module: `rebuild_from_archive.project_compat`
- Symbol: `EmotionGateJQCompat.get_project_master_prepare_index`
- Behavior: Expose the project's master_prepare_index cache to runtime callers through compat.
- semantic_type / disposition / status: `project_infrastructure` / `investigate` / `investigation_pending`
- Wave: `—`
- Affected fields: `master_prepare_index`
- Trigger dates: ``
- Trigger codes: ``
- Effects: selection=yes, state=yes, order=no, fill=no, nav=no
- direct_effect_scope: `['infrastructure']`
- downstream_risk: `strategy_path`
- empty_config: `no`
- Reason: Main path has no direct strategy consumer. If only definition and forwarding exist without strategy usage, it should enter unused cleanup candidate.
- Evidence: engine/data_api.py delegates get_project_master_prepare_index through compat; no direct strategy consumer is currently present on the main path.
- Runtime call sites: `rebuild_from_archive/engine\data_api.py:828:    def get_project_master_prepare_index(self, date):; rebuild_from_archive/engine\data_api.py:830:            return self.compat.get_project_master_prepare_index(date); rebuild_from_archive/project_compat.py:256:    def get_project_master_prepare_index(self, date):; rebuild_from_archive/project_compat.py:70:                engine.data_api.get_project_master_prepare_index(*a, **kw)`
- Secondary references: `alignment_reports\align_worktree_diff_2020-01-02_2021-12-31.patch:233:-            'get_project_master_prepare_index': lambda *a, **kw: self._wrap_pandas(self.data_api.get_project_master_prepare_index(*a, **kw)),; alignment_reports\align_worktree_diff_2020-01-02_2021-12-31.patch:484:     def get_project_master_prepare_index(self, date):; alignment_reports\align_worktree_diff_2020-01-02_2021-12-31.patch:500:+            return self.compat.get_project_master_prepare_index(date); tools\audit_hook_disposition.py:1048:        call_site_patterns=["get_project_master_prepare_index("],`
- target_owner: `emotion_gating_project`
- handoff_requirement: Confirm if there are real runtime consumers. If only definition and forwarding without strategy usage, enter unused cleanup candidate.
- disable_requirement: Disable only if the project removes this cache or rewires the consumer path.
- delete_requirement: Delete after there are no project callers and no fast-path cache exposure for master_prepare_index.
- acceptance_test: Inventory scan should flag that current direct runtime call sites are limited.

### `project_feature.auction_yiqian_prepare_accessor`
- Module: `rebuild_from_archive.project_compat`
- Symbol: `EmotionGateJQCompat.get_project_auction_yiqian_prepare`
- Behavior: Expose cached auction_yiqian_prepare rows to strategy code and patch left-pressure checks onto them.
- semantic_type / disposition / status: `project_infrastructure` / `retain_in_project` / `retain`
- Wave: `—`
- Affected fields: `auction_yiqian_prepare, left_ok`
- Trigger dates: ``
- Trigger codes: ``
- Effects: selection=yes, state=yes, order=no, fill=no, nav=no
- direct_effect_scope: `['infrastructure']`
- downstream_risk: `strategy_path`
- empty_config: `no`
- Reason: This accessor is specific to the project's derived candidate-preparation feature set, not strategy alpha logic.
- Evidence: 母版-20260506-Clone.py reads get_project_auction_yiqian_prepare(context.current_dt), and project_compat.get_project_auction_yiqian_prepare also runs project-specific left-pressure logic.
- Runtime call sites: `rebuild_from_archive/engine\data_api.py:833:    def get_project_auction_yiqian_prepare(self, date):; rebuild_from_archive/engine\data_api.py:835:            return self.compat.get_project_auction_yiqian_prepare(date); rebuild_from_archive/project_compat.py:263:    def get_project_auction_yiqian_prepare(self, date):; rebuild_from_archive/project_compat.py:73:                engine.data_api.get_project_auction_yiqian_prepare(*a, **kw); 母版-20260506-Clone.py:1058:        cached = get_project_auction_yiqian_prepare(context.current_dt)`
- Secondary references: `alignment_reports\align_worktree_diff_2020-01-02_2021-12-31.patch:234:-            'get_project_auction_yiqian_prepare': lambda *a, **kw: self._wrap_pandas(self.data_api.get_project_auction_yiqian_prepare(*a, **kw)),; alignment_reports\align_worktree_diff_2020-01-02_2021-12-31.patch:503:     def get_project_auction_yiqian_prepare(self, date):; alignment_reports\align_worktree_diff_2020-01-02_2021-12-31.patch:522:+            return self.compat.get_project_auction_yiqian_prepare(date); tools\audit_hook_disposition.py:1061:        evidence="母版-20260506-Clone.py reads get_project_auction_yiqian_prepare(context.current_dt), and project_compat.get_project_auction_yiqian_prepare also runs project-specific left-pressure logic.",; tools\audit_hook_disposition.py:1076:        call_site_patterns=["get_project_auction_yiqian_prepare("],`
- target_owner: `emotion_gating_project`
- handoff_requirement: Retain while auction_yiqian_prepare remains part of the project feature graph.
- disable_requirement: Disable only if the project removes this cache path or replaces it with a different project-owned feature service.
- delete_requirement: Delete after no runtime caller depends on auction_yiqian_prepare compat exposure.
- acceptance_test: Inventory scan: verifies auction_yiqian_prepare compat is consumed by strategy code

### `project_feature.call_auction_day_loader`
- Module: `rebuild_from_archive.project_compat`
- Symbol: `EmotionGateJQCompat.load_project_call_auction_day`
- Behavior: Swap the generic call-auction year read for the project's by-date cache when available.
- semantic_type / disposition / status: `project_infrastructure` / `retain_in_project` / `retain`
- Wave: `—`
- Affected fields: `call_auction_by_date`
- Trigger dates: ``
- Trigger codes: ``
- Effects: selection=yes, state=no, order=no, fill=no, nav=no
- direct_effect_scope: `['infrastructure']`
- downstream_risk: `strategy_path`
- empty_config: `no`
- Reason: This is a project cache integration point for a derived feature layout, not strategy alpha logic.
- Evidence: engine/data_api.py calls compat.load_project_call_auction_day from _get_call_auction_day before falling back to raw 1d_feature/call_auction.
- Runtime call sites: `rebuild_from_archive/engine\data_api.py:806:            out = self.compat.load_project_call_auction_day(self, day); rebuild_from_archive/project_compat.py:288:    def load_project_call_auction_day(self, api, day):`
- Secondary references: `alignment_reports\align_worktree_diff_2020-01-02_2021-12-31.patch:404:-        out = self._load_project_call_auction_day(day); alignment_reports\align_worktree_diff_2020-01-02_2021-12-31.patch:407:+            out = self.compat.load_project_call_auction_day(self, day); alignment_reports\align_worktree_diff_2020-01-02_2021-12-31.patch:415:-    def _load_project_call_auction_day(self, day):; tools\audit_hook_disposition.py:1104:        call_site_patterns=["load_project_call_auction_day("],`
- target_owner: `emotion_gating_project`
- handoff_requirement: Retain while the project prefers its by-date call-auction cache layout.
- disable_requirement: Disable only if runtime stops consulting the project call_auction_by_date cache.
- delete_requirement: Delete after the project no longer needs this alternate loader path.
- acceptance_test: Inventory scan: verifies call_auction_by_date cache loader is consumed via compat

### `project_feature.strategy_namespace_bridge`
- Module: `rebuild_from_archive.project_compat`
- Symbol: `EmotionGateJQCompat.namespace_entries/apply_project_strategy_compat`
- Behavior: Inject project-owned compat entrypoints into the strategy namespace, including the strategy-state bridge.
- semantic_type / disposition / status: `project_infrastructure` / `retain_in_project` / `retain`
- Wave: `—`
- Affected fields: `strategy_state`
- Trigger dates: ``
- Trigger codes: ``
- Effects: selection=yes, state=yes, order=no, fill=no, nav=no
- direct_effect_scope: `['infrastructure']`
- downstream_risk: `strategy_path`
- empty_config: `no`
- Reason: Namespace wiring is project infrastructure that allows strategy code to call project-owned compatibility services. The bridge itself is infrastructure; JQ history overrides called through it are archive_jq_only.
- Evidence: Engine.__init__ merges compat.namespace_entries(self), and 母版-20260506-Clone.py calls apply_project_strategy_compat(...) at fixed stages.
- Runtime call sites: `rebuild_from_archive/engine\core.py:222:            self.namespace.update(self.compat.namespace_entries(self)); rebuild_from_archive/project_compat.py:64:    def namespace_entries(self, engine):; 母版-20260506-Clone.py:266:    apply_project_strategy_compat("after_fb_state", context, g); 母版-20260506-Clone.py:271:    apply_project_strategy_compat("after_v227_shock", context, g)`
- Secondary references: `alignment_reports\align_worktree_diff_2020-01-02_2021-12-31.patch:243:+            self.namespace.update(self.compat.namespace_entries(self)); alignment_reports\compat_hook_migration_report.md:11:- `母版-20260506-Clone.py` 的策略状态兼容已改为 `apply_project_strategy_compat(...)` 单入口；; alignment_reports\compat_hook_migration_report.md:54:当前运行时代码中，兼容事实应通过 `EmotionGateJQCompat` 或 `apply_project_strategy_compat(...)` 暴露，不再由调用点各自维护散落字典。; tests\test_hook_disposition_inventory.py:221:    """namespace_entries() exposed methods must each have an inventory owner."""; tests\test_hook_disposition_inventory.py:572:    """namespace_entries() returned keys must each map to a hook_id in inventory."""; tools\audit_hook_disposition.py:1117:        evidence="Engine.__init__ merges compat.namespace_entries(self), and 母版-20260506-Clone.py calls apply_project_strategy_compat(...) at fixed stages.",; tools\audit_hook_disposition.py:1132:        call_site_patterns=["namespace_entries(", "apply_project_strategy_compat("],; tools\audit_hook_disposition.py:923:        evidence="母版-20260506-Clone.py calls apply_project_strategy_compat('after_fb_state', ...) and project_compat.apply_strategy_state_override applies FB_STATE_OVERRIDES.",; tools\audit_hook_disposition.py:938:        call_site_patterns=["apply_project_strategy_compat(", "apply_strategy_state_override("],; tools\audit_hook_disposition.py:950:        evidence="母版-20260506-Clone.py calls apply_project_strategy_compat('after_v227_shock', ...) and project_compat.apply_strategy_state_override applies V227_SHOCK_OVERRIDES.",; tools\audit_hook_disposition.py:965:        call_site_patterns=["apply_project_strategy_compat(", "apply_strategy_state_override("],; tools\hook_migration_acceptance.py:86:    def namespace_entries(self, engine):; tools\hook_migration_acceptance.py:87:        entries = self._base.namespace_entries(engine) if hasattr(self._base, 'namespace_entries') else {}`
- target_owner: `emotion_gating_project`
- handoff_requirement: Retain until project-owned feature and state hooks are redesigned or removed.
- disable_requirement: Disable only after the strategy no longer expects these injected entrypoints.
- delete_requirement: Delete after project compat entrypoints are removed or replaced by a new project extension surface.
- acceptance_test: Inventory scan plus tests/test_compat_entrypoints.py state override checks

### `engine.checkpoint_resume_hook`
- Module: `rebuild_from_archive.engine.core`
- Symbol: `Engine.set_resume_state/_apply_resume_state`
- Behavior: Restore project checkpoint state into the engine before the run loop starts.
- semantic_type / disposition / status: `project_infrastructure` / `retain_in_project` / `retain`
- Wave: `—`
- Affected fields: `portfolio, g_data, order_id_counter`
- Trigger dates: ``
- Trigger codes: ``
- Effects: selection=yes, state=yes, order=yes, fill=no, nav=yes
- direct_effect_scope: `['infrastructure']`
- downstream_risk: `strategy_path`
- empty_config: `no`
- Reason: This is a project warm-start/checkpoint integration hook, not a JQ historical fact bundle or strategy alpha logic. May be migrated to shared engine extension API in the future.
- Evidence: engine/core.py marks the resume hook with EMOTION_GATE_COMPAT_HOOK comments and tools/run_counterfactual_2024_000506_billboard_filter.py uses engine.set_resume_state(...).
- Runtime call sites: `rebuild_from_archive/engine\core.py:133:        # EMOTION_GATE_COMPAT_HOOK:; rebuild_from_archive/engine\core.py:1573:        self._apply_resume_state(); rebuild_from_archive/engine\core.py:230:    def set_resume_state(self, state):; rebuild_from_archive/engine\core.py:231:        """EMOTION_GATE_COMPAT_HOOK: install an application checkpoint state."""; rebuild_from_archive/engine\core.py:234:    def _apply_resume_state(self):; rebuild_from_archive/engine\core.py:235:        """EMOTION_GATE_COMPAT_HOOK: restore portfolio and strategy globals."""`
- Secondary references: `tools\audit_hook_disposition.py:1145:        evidence="engine/core.py marks the resume hook with EMOTION_GATE_COMPAT_HOOK comments and tools/run_counterfactual_2024_000506_billboard_filter.py uses engine.set_resume_state(...).",; tools\audit_hook_disposition.py:1158:        acceptance_test="Inventory scan of EMOTION_GATE_COMPAT_HOOK sites and manual workflow reference in tools/run_counterfactual_2024_000506_billboard_filter.py",; tools\audit_hook_disposition.py:1160:        call_site_patterns=["set_resume_state(", "_apply_resume_state(", "EMOTION_GATE_COMPAT_HOOK"],; tools\run_counterfactual_2024_000506_billboard_filter.py:53:    engine.set_resume_state(load_engine_checkpoint(CHECKPOINT))`
- target_owner: `emotion_gating_project`
- handoff_requirement: Retain until checkpoint responsibilities are redesigned outside the generic engine or explicitly migrated to a shared extension API.
- disable_requirement: Disable only after all checkpoint-based workflows are removed or replaced.
- delete_requirement: Delete after no workflow uses set_resume_state and checkpoint restore is moved elsewhere.
- acceptance_test: Inventory scan of EMOTION_GATE_COMPAT_HOOK sites and manual workflow reference in tools/run_counterfactual_2024_000506_billboard_filter.py

### `legacy.public_data_api_shim`
- Module: `rebuild_from_archive.data_api`
- Symbol: `rebuild_from_archive.data_api.DataAPI`
- Behavior: Re-export the archived legacy DataAPI implementation from the old public import path.
- semantic_type / disposition / status: `unknown` / `investigate` / `investigation_pending`
- Wave: `—`
- Affected fields: `public_import_path`
- Trigger dates: ``
- Trigger codes: ``
- Effects: selection=no, state=no, order=no, fill=no, nav=no
- direct_effect_scope: `['infrastructure']`
- downstream_risk: `none`
- empty_config: `no`
- Reason: This is a compatibility entrypoint for legacy/manual callers, but its external dependency surface is not fully inventoried yet.
- Evidence: rebuild_from_archive/data_api.py dynamically loads rebuild_from_archive/legacy/data_api_legacy.py; legacy/README.md lists only the public shim as a known in-repo caller.
- Runtime call sites: ``
- Secondary references: `alignment_reports\compat_hook_migration_report.md:60:- `rebuild_from_archive/data_api.py` (shim); alignment_reports\compat_hook_migration_report.md:81:- 尚未清理 `rebuild_from_archive/data_api.py` (shim) 这份归档平行实现；; rebuild_from_archive/legacy\README.md:13:- `rebuild_from_archive/data_api.py` public shim.; rebuild_from_archive/legacy\README.md:19:- the `rebuild_from_archive/data_api.py` shim is deleted;; rebuild_from_archive/legacy\README.md:9:  re-exported by the public `rebuild_from_archive/data_api.py` shim.; tools\audit_hook_disposition.py:1167:        data_obj={"legacy_entrypoint": "rebuild_from_archive/data_api.py"},; tools\audit_hook_disposition.py:1173:        evidence="rebuild_from_archive/data_api.py dynamically loads rebuild_from_archive/legacy/data_api_legacy.py; legacy/README.md lists only the public shim as a known in-repo caller.",; tools\audit_hook_disposition.py:1189:            "from rebuild_from_archive.data_api",; tools\audit_hook_disposition.py:1190:            "import rebuild_from_archive.data_api",; tools\audit_hook_disposition.py:1191:            "rebuild_from_archive/data_api.py",; tools\audit_hook_disposition.py:57:    "rebuild_from_archive/data_api.py",; tools\audit_hook_disposition.py:69:    "rebuild_from_archive/data_api.py",; tools\hook_migration_acceptance.py:599:            "status": "Legacy public entry retained via rebuild_from_archive/data_api.py shim; current in-repo caller set is the shim itself, and no suspected_unused runtime dependency remains.",`
- target_owner: `emotion_gating_project`
- handoff_requirement: Need an explicit caller audit across manual workflows before deleting the public shim.
- disable_requirement: Disable only after external/manual callers are confirmed gone or migrated to engine/data_api.py.
- delete_requirement: Delete after the public import path is unused and legacy workflows have been redirected.
- acceptance_test: Inventory scan should mark this as having no active main-path runtime call sites inside the repo.

### `legacy.temporary_fallbacks_shim`
- Module: `rebuild_from_archive.engine.temporary_fallbacks`
- Symbol: `get_price_fallback/has_zero_fee_fallback`
- Behavior: Closed shim that intentionally returns no fallback so old imports do not introduce a second fact source.
- semantic_type / disposition / status: `unknown` / `investigate` / `investigation_pending`
- Wave: `cleanup-only`
- Affected fields: `fallback_import_path`
- Trigger dates: ``
- Trigger codes: ``
- Effects: selection=no, state=no, order=no, fill=no, nav=no
- direct_effect_scope: `['none']`
- downstream_risk: `none`
- empty_config: `no`
- Reason: This module exists only to absorb deprecated imports from the old JQ parity path. It is a legacy cleanup item, not a strategy ablation variable.
- Evidence: rebuild_from_archive/engine/temporary_fallbacks.py documents itself as a non-operative shim and current repo scan shows no active runtime caller.
- Runtime call sites: ``
- Secondary references: `tools\audit_hook_disposition.py:1221:            "from rebuild_from_archive.engine.temporary_fallbacks import",; tools\audit_hook_disposition.py:1222:            "import rebuild_from_archive.engine.temporary_fallbacks",`
- target_owner: `emotion_gating_project`
- handoff_requirement: Keep only until any remaining legacy imports are proven gone; do not add new callers.
- disable_requirement: Can be removed once import-path audit confirms there are no remaining users.
- delete_requirement: Delete after repo and external workflow scans prove the shim is unused.
- acceptance_test: Inventory scan should flag no active runtime call sites for temporary_fallbacks.
