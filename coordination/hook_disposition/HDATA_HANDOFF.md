# HData Handoff

Hooks below should move into HData or data-quality metadata because they represent source-content truth rather than strategy logic.

## `market_data.corrupted_daily_limit_windows`
- symbol: `CORRUPTED_DAILY_LIMIT_WINDOWS`
- semantic_type / disposition: `data_correction` / `move_to_hdata`
- affects: selection=yes, state=yes, order=no, fill=no, nav=yes
- reason: The 2026 corruption window is a source-data quality problem and should be expressed in data lineage, not in project compat forever.
- evidence: alignment_reports/data_quality_propagation_2026.md proves raw pivot corruption from 2026-05-25 forward and shows current runtime guards are only partial.
- runtime call sites: `rebuild_from_archive/project_compat.py:212:    def should_bypass_history_fastpath(self, unit, fields, end_dt):; rebuild_from_archive/engine\data_api.py:143:    def _should_bypass_history_fastpath(self, unit, fields, end_dt):; rebuild_from_archive/engine\data_api.py:149:                return bool(compat.should_bypass_history_fastpath(unit, fields, end_dt)); rebuild_from_archive/engine\data_api.py:438:                if self._should_bypass_history_fastpath(unit, fields_to_get, end_dt):; rebuild_from_archive/project_compat.py:224:    def load_first_seal_year(self, year):; rebuild_from_archive/engine\data_api.py:820:            return self.compat.load_first_seal_year(year); 母版-20260506-Clone.py:564:        board_df = get_project_board_snapshot(context.previous_date); 母版-20260506-Clone.py:666:        board_df = get_project_board_snapshot(context.previous_date); rebuild_from_archive/project_compat.py:67:                engine.data_api.get_project_board_snapshot(*a, **kw); rebuild_from_archive/project_compat.py:247:    def get_project_board_snapshot(self, date):; rebuild_from_archive/engine\data_api.py:823:    def get_project_board_snapshot(self, date):; rebuild_from_archive/engine\data_api.py:825:            return self.compat.get_project_board_snapshot(date)`
- handoff requirement: HData or upstream cache metadata must publish corruption windows and field-level quarantine signals.
- disable requirement: Disable only after raw-data quality flags propagate through cache build and runtime readers.
- delete requirement: Delete after HData versioned quality metadata replaces project-specific date guards and all dependent caches respect the same rule.

## `security_metadata.start_date_overrides`
- symbol: `SECURITY_START_DATE_OVERRIDES`
- semantic_type / disposition: `data_correction` / `move_to_hdata`
- affects: selection=yes, state=no, order=no, fill=no, nav=no
- reason: Listing-date truth belongs to the data layer, not to a strategy-specific compat profile.
- evidence: engine/data_api.py applies get_security_start_date_override while building _stock_basic for get_all_securities().
- runtime call sites: `rebuild_from_archive/project_compat.py:118:    def get_security_start_date_override(self, security):; rebuild_from_archive/engine\data_api.py:992:                    start_date = self.compat.get_security_start_date_override(code)`
- handoff requirement: HData needs a corrected listing-date source or overlay for these securities.
- disable requirement: Disable only after stock_basic or its replacement publishes correct PIT listing dates.
- delete requirement: Delete after HData ships corrected listing dates and all IPO-age filters read them directly.

## `security_metadata.non_st_name_windows`
- symbol: `NON_ST_NAME_WINDOWS`
- semantic_type / disposition: `data_correction` / `move_to_hdata`
- affects: selection=yes, state=no, order=no, fill=no, nav=no
- reason: Historical security-name state is source metadata, not project logic.
- evidence: project_compat.apply_security_name_overrides applies NON_ST_NAME_WINDOWS after reading daily ST state and before strategy filters consume display_name.
- runtime call sites: `rebuild_from_archive/project_compat.py:310:    def apply_security_name_overrides(self, api, out, date):; rebuild_from_archive/engine\data_api.py:107:            return self.compat.apply_security_name_overrides(self, out, date)`
- handoff requirement: HData needs PIT name history or equivalent metadata to eliminate these date-window strips.
- disable requirement: Disable only after display_name is PIT-correct for affected windows.
- delete requirement: Delete after PIT name history is available and strategy filters no longer need compat name surgery.

## `security_metadata.adjust_extras_is_st`
- symbol: `EmotionGateJQCompat.adjust_extras_is_st`
- semantic_type / disposition: `data_correction` / `move_to_hdata`
- affects: selection=yes, state=no, order=no, fill=no, nav=no
- reason: ST state and delisting-state truth should come from source metadata instead of project-side postprocessing.
- evidence: engine/data_api.py calls compat.adjust_extras_is_st from get_extras('is_st', ...), and project_compat.py embeds date windows and name/end_date heuristics.
- runtime call sites: `rebuild_from_archive/project_compat.py:354:    def adjust_extras_is_st(self, api, security, date, is_st):; rebuild_from_archive/engine\data_api.py:1031:                is_st = self.compat.adjust_extras_is_st(self, s, ds_dt, is_st)`
- handoff requirement: HData needs PIT ST status and delisting-state history that match the project’s required query dates.
- disable requirement: Disable only after get_extras('is_st') reads corrected PIT ST state directly.
- delete requirement: Delete after ST state is natively correct and the project no longer patches it post-query.

## `instrument_fallbacks.price_fallbacks`
- symbol: `INSTRUMENT_PRICE_FALLBACKS`
- semantic_type / disposition: `data_correction` / `move_to_hdata`
- affects: selection=yes, state=no, order=yes, fill=no, nav=yes
- reason: Instrument price history should come from the data layer; synthetic prices are a stopgap for missing upstream content.
- evidence: engine/data_api.py short-circuits get_price via compat.get_instrument_price_fallback before touching local price tables.
- runtime call sites: `rebuild_from_archive/project_compat.py:121:    def get_instrument_price_fallback(self, security, start_date=None, end_date=None):; rebuild_from_archive/engine\data_api.py:400:            fallback = self.compat.get_instrument_price_fallback(`
- handoff requirement: HData needs complete and trustworthy history for the fallback instruments or an explicit supported-source overlay.
- disable requirement: Disable only after local data can serve these instruments directly without synthetic rows.
- delete requirement: Delete after HData publishes native coverage and no call path reaches get_instrument_price_fallback.
