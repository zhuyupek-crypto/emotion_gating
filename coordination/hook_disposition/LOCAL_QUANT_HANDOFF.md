# Local Quant Handoff

以下钩子描述的是通用市场、账户或费用行为，应迁移到 local_quant 作为平台通用能力。
local_quant 不应为 emotion_gating 项目提供专用 boolean 开关，而应采用统一的账户结算政策、费用模型和证券类型分类。

## `engine.immediate_sell_cash_release`
- symbol: `EmotionGateJQCompat.immediate_sell_cash_release`
- semantic_type / disposition: `market_rule` / `move_to_local_quant`
- affects: selection=no, state=no, order=yes, fill=yes, nav=yes
- direct_effect_scope: `['cash_settlement']`
- downstream_risk: `cash_path`
- reason: This is account and cash-settlement semantics, not project alpha logic.
- evidence: rebuild_from_archive/project_compat.py sets immediate_sell_cash_release=True and engine/core.py consumes it in the sell-fill cash path.
- runtime call sites: `rebuild_from_archive/engine\core.py:872:            if getattr(self.compat, "immediate_sell_cash_release", False):; rebuild_from_archive/project_compat.py:35:    immediate_sell_cash_release = True`
- **handoff requirement**: local_quant 应提供统一账户结算政策（卖出成交后的资金何时重新计入可用现金），而不是 emotion_gating 专用 boolean 开关。
- disable requirement: Disable only after local_quant can reproduce the intended cash-release policy in native mode.
- delete requirement: Delete when engine/core.py no longer checks compat.immediate_sell_cash_release and the policy lives in local_quant.

## `instrument_fallbacks.zero_fee_overrides`
- symbol: `ZERO_FEE_OVERRIDES`
- semantic_type / disposition: `market_rule` / `move_to_local_quant`
- affects: selection=no, state=no, order=no, fill=yes, nav=yes
- direct_effect_scope: `['fee']`
- downstream_risk: `nav_only`
- reason: Fee classification belongs in the generic instrument/fee model, not in project compat constants.
- evidence: engine/core.py calls compat.has_zero_fee_override from buy/sell fee estimation and realized fee logic.
- runtime call sites: `rebuild_from_archive/engine\core.py:403:                    if self._has_zero_fee_override(security):; rebuild_from_archive/engine\core.py:426:                if self._has_zero_fee_override(security):; rebuild_from_archive/engine\core.py:451:    def _has_zero_fee_override(self, security):; rebuild_from_archive/engine\core.py:455:            and self.compat.has_zero_fee_override(security); rebuild_from_archive/engine\core.py:797:            if self._has_zero_fee_override(security):; rebuild_from_archive/engine\core.py:811:                if self._has_zero_fee_override(security):; rebuild_from_archive/engine\core.py:830:        if self._has_zero_fee_override(security):; rebuild_from_archive/project_compat.py:146:    def has_zero_fee_override(self, security):`
- **handoff requirement**: local_quant 应按证券类型、交易品种和账户费用模型统一计算费用，而不是为 511880 单独保留项目 override。
- disable requirement: Disable only after fee policy is modeled in local_quant by instrument type or explicit configuration.
- delete requirement: Delete after engine/core.py no longer checks compat.has_zero_fee_override and fee policy is generic.
