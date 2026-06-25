# Local Quant Handoff

Hooks below should move into local_quant because they describe generic market, fee, or account behavior rather than project alpha rules.

## `engine.immediate_sell_cash_release`
- symbol: `EmotionGateJQCompat.immediate_sell_cash_release`
- semantic_type / disposition: `market_rule` / `move_to_local_quant`
- affects: selection=no, state=no, order=yes, fill=yes, nav=yes
- reason: This is account and cash-settlement semantics, not project alpha logic.
- evidence: rebuild_from_archive/project_compat.py sets immediate_sell_cash_release=True and engine/core.py consumes it in the sell-fill cash path.
- runtime call sites: `rebuild_from_archive/project_compat.py:35:    immediate_sell_cash_release = True; rebuild_from_archive/engine\core.py:872:            if getattr(self.compat, "immediate_sell_cash_release", False):`
- handoff requirement: local_quant needs a first-class switch for sell-cash release timing so project code stops carrying the behavior flag.
- disable requirement: Disable only after local_quant can reproduce the intended cash-release policy in native mode.
- delete requirement: Delete when engine/core.py no longer checks compat.immediate_sell_cash_release and the policy lives in local_quant.

## `instrument_fallbacks.zero_fee_overrides`
- symbol: `ZERO_FEE_OVERRIDES`
- semantic_type / disposition: `market_rule` / `move_to_local_quant`
- affects: selection=no, state=no, order=no, fill=yes, nav=yes
- reason: Fee classification belongs in the generic instrument/fee model, not in project compat constants.
- evidence: engine/core.py calls compat.has_zero_fee_override from buy/sell fee estimation and realized fee logic.
- runtime call sites: `rebuild_from_archive/project_compat.py:146:    def has_zero_fee_override(self, security):; rebuild_from_archive/engine\core.py:403:                    if self._has_zero_fee_override(security):; rebuild_from_archive/engine\core.py:426:                if self._has_zero_fee_override(security):; rebuild_from_archive/engine\core.py:451:    def _has_zero_fee_override(self, security):; rebuild_from_archive/engine\core.py:455:            and self.compat.has_zero_fee_override(security); rebuild_from_archive/engine\core.py:797:            if self._has_zero_fee_override(security):; rebuild_from_archive/engine\core.py:811:                if self._has_zero_fee_override(security):; rebuild_from_archive/engine\core.py:830:        if self._has_zero_fee_override(security):`
- handoff requirement: local_quant needs instrument-class-aware fee configuration that covers these cases natively.
- disable requirement: Disable only after fee policy is modeled in local_quant by instrument type or explicit configuration.
- delete requirement: Delete after engine/core.py no longer checks compat.has_zero_fee_override and fee policy is generic.
