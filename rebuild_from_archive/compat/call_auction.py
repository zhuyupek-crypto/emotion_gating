CALL_AUCTION_METADATA = {
    "empty_anomalies": {"id": "call-auction-empty-anomalies", "category": "market_snapshot", "reason": "Observed call-auction records that should be removed.", "evidence": "Legacy engine/data_api.py anomaly_empty and project_compat.py call_auction_empty_anomalies.", "scope": "parity"},
    "allow_only": {"id": "call-auction-allow-only", "category": "market_snapshot", "reason": "Observed days where only a subset of auction rows should remain.", "evidence": "Legacy engine/data_api.py allow_only.", "scope": "parity"},
    "depth_overrides": {"id": "call-auction-depth-overrides", "category": "market_snapshot", "reason": "Observed auction depth overrides used by candidate ranking.", "evidence": "Legacy engine/data_api.py anomaly_depth.", "scope": "parity"},
}

CALL_AUCTION_EMPTY_ANOMALIES = {
    ("002897.XSHE", 20200304),
    ("600804.XSHG", 20210901),
    ("600982.XSHG", 20210818),
    ("603908.XSHG", 20210818),
}

CALL_AUCTION_ALLOW_ONLY = {
    20210818: {"000833.XSHE"},
    20211202: set(),
}

CALL_AUCTION_DEPTH_OVERRIDES = {
    ("000038.XSHE", 20210604): {"a1_v": 40000.0},
    ("002635.XSHE", 20200903): {"a1_v": 2000.0},
}
