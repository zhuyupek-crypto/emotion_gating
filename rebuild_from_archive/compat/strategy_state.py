import numpy as np

STRATEGY_STATE_METADATA = {
    "fb_state_overrides": {"id": "strategy-fb-state-overrides", "category": "strategy_state", "reason": "Observed first-board state snapshots that preserve NaN/percentile behavior.", "evidence": "Legacy 母版-20260506-Clone.py _apply_jq_fb_state_overrides.", "scope": "parity"},
    "v227_shock_overrides": {"id": "strategy-v227-shock-overrides", "category": "strategy_state", "reason": "Observed v227 shock cooldown snapshots.", "evidence": "Legacy 母版-20260506-Clone.py _apply_jq_v227_shock_overrides.", "scope": "parity"},
}

FB_STATE_OVERRIDES = {
    "2020-08-05": (np.nan, 0.0),
    "2020-08-26": (np.nan, 0.0),
    "2020-09-17": (np.nan, 0.0),
}

V227_SHOCK_OVERRIDES = {
    "2023-02-17": 1,
}
