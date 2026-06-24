INSTRUMENT_FALLBACK_METADATA = {
    "price_fallbacks": {"id": "instrument-price-fallbacks", "category": "mother_path", "reason": "Observed project-scoped fallback prices for missing instruments.", "evidence": "Legacy engine/data_api.py and engine/temporary_fallbacks.py 511880 overrides.", "scope": "parity"},
    "zero_fee_overrides": {"id": "instrument-zero-fee-overrides", "category": "platform_execution", "reason": "Observed fee override for project fallback instruments.", "evidence": "Legacy engine/temporary_fallbacks.py has_zero_fee_fallback.", "scope": "parity"},
}

INSTRUMENT_PRICE_FALLBACKS = {
    "511880.XSHG": {
        "prices": {
            "20240102": 100.094, "20240103": 100.113, "20240104": 100.120, "20240105": 100.138,
            "20240108": 100.138, "20240109": 100.142, "20240110": 100.150, "20240111": 100.148,
            "20240112": 100.170, "20240115": 100.179, "20240116": 100.178, "20240117": 100.182,
            "20240118": 100.191, "20240119": 100.208, "20240122": 100.224, "20240123": 100.216,
            "20240124": 100.216, "20240125": 100.205, "20240126": 100.233, "20240129": 100.241,
            "20240130": 100.254, "20240131": 100.260, "20240201": 100.262,
            "20240401": 100.562, "20240506": 100.703,
        },
        "default_price": 100.50,
        "volume": 1000000,
        "money": 100000000,
    },
}

ZERO_FEE_OVERRIDES = {"511880.XSHG"}
