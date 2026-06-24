import pandas as pd


MARKET_DATA_METADATA = {
    "corrupted_daily_limit_windows": {
        "id": "market-data-corrupted-daily-limit-windows",
        "category": "market_snapshot",
        "reason": "Corrupted daily limit windows that must bypass the fast history path.",
        "evidence": "Existing project_compat.corrupted_daily_limit_windows behavior.",
        "scope": "parity",
    },
    "tail_seal_anomalies": {
        "id": "market-data-tail-seal-anomalies",
        "category": "market_snapshot",
        "reason": "Observed first-seal timestamps used by preprocess and runtime sealing logic.",
        "evidence": "Legacy project_preprocess.py and project_compat.py hardcoded overrides.",
        "scope": "parity",
    },
    "minute_price_anomalies": {
        "id": "market-data-minute-price-anomalies",
        "category": "market_snapshot",
        "reason": "Observed JoinQuant minute snapshot differences affecting sell/buy boundaries.",
        "evidence": "Legacy engine/core.py and project_compat.py parity overrides.",
        "scope": "parity",
    },
    "daily_ipo_close_anomalies": {
        "id": "market-data-daily-ipo-close-anomalies",
        "category": "market_snapshot",
        "reason": "IPO sync-delay daily rows where JQ returns prior close plus trailing NaN.",
        "evidence": "Legacy engine/data_api.py hardcoded IPO anomalies.",
        "scope": "parity",
    },
    "daily_field_anomalies": {
        "id": "market-data-daily-field-anomalies",
        "category": "market_snapshot",
        "reason": "Observed point-in-time daily field overrides used by strategy selection and state logic.",
        "evidence": "Legacy engine/data_api.py and project_compat.py hardcoded field overrides.",
        "scope": "parity",
    },
}


CORRUPTED_DAILY_LIMIT_WINDOWS = [
    (pd.Timestamp("2026-05-25"), pd.Timestamp("2026-06-12")),
]


TAIL_SEAL_ANOMALIES = {
    ("20200713", "300118.XSHE"): pd.Timestamp("2020-07-13 14:00:00"),
    ("20200713", "600711.XSHG"): pd.Timestamp("2020-07-13 14:00:00"),
    ("20211115", "000420.XSHE"): pd.Timestamp("2021-11-15 14:00:00"),
    ("20221226", "002487.XSHE"): pd.Timestamp("2022-12-26 14:41:00"),
    ("20250813", "603031.XSHG"): pd.Timestamp("2025-08-13 14:09:00"),
}


MINUTE_PRICE_ANOMALIES = {
    ("20200114", "11:25", "002056.XSHE"): 10.90,
    ("20210519", "11:28", "000592.XSHE"): 3.17,
    ("20210809", "14:52", "002176.XSHE"): 24.84,
    ("20220708", "14:47", "002470.XSHE"): 2.32,
    ("20230228", "11:28", "002229.XSHE"): 15.18,
    ("20230228", "14:47", "002229.XSHE"): 15.14,
    ("20240325", "14:50", "002130.XSHE"): 10.99,
    ("20250613", "14:50", "002426.XSHE"): 2.83,
    ("20250711", "14:50", "000987.XSHE"): 7.85,
    ("20260119", "14:50", "002310.XSHE"): 2.36,
}


DAILY_IPO_CLOSE_ANOMALIES = {
    ("605399.XSHG", 20200804): 13.16,
    ("605123.XSHG", 20200825): 30.33,
    ("605255.XSHG", 20200825): 12.66,
    ("605369.XSHG", 20200916): 31.65,
}


DAILY_FIELD_ANOMALIES = {
    ("002256.XSHE", 20200828, "open"): 1.24,
    ("603393.XSHG", 20210910, "high"): 40.42,
    ("000420.XSHE", 20211115, "money"): 965000000.0,
    ("600032.XSHG", 20220701, "high_limit"): 16.12,
    ("002141.XSHE", 20240716, "open"): 0.96999997,
    ("603569.XSHG", 20241203, "high_limit"): 9.41,
    ("002265.XSHE", 20241209, "high_limit"): 20.19,
    ("002121.XSHE", 20250929, "high_limit"): 9.41,
    ("002185.XSHE", 20260527, "high"): 20.540000915527344,
    ("002185.XSHE", 20260527, "high_limit"): 20.540000915527344,
    ("603773.XSHG", 20260527, "high"): 100.69000244140625,
    ("603773.XSHG", 20260527, "high_limit"): 100.69000244140625,
}

