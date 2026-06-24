import pandas as pd

SECURITY_METADATA = {
    "start_date_overrides": {"id": "security-start-date-overrides", "category": "security_metadata", "reason": "Observed JQ listing-date overrides.", "evidence": "Legacy engine/data_api.py ipo_overrides.", "scope": "parity"},
    "non_st_name_windows": {"id": "security-non-st-name-windows", "category": "security_metadata", "reason": "Observed PIT name snapshots that should not carry future ST labels.", "evidence": "Legacy project_compat.py non_st_name_windows.", "scope": "parity"},
    "billboard_row_filters": {"id": "security-billboard-row-filters", "category": "security_metadata", "reason": "Observed billboard rows that should be filtered for parity.", "evidence": "Legacy project_compat.py filter_billboard_rows hardcoded anomalies.", "scope": "parity"},
}

SECURITY_START_DATE_OVERRIDES = {
    "605123.XSHG": pd.Timestamp("2020-08-21"),
    "605255.XSHG": pd.Timestamp("2020-08-21"),
    "605369.XSHG": pd.Timestamp("2020-09-14"),
    "605399.XSHG": pd.Timestamp("2020-08-03"),
}

NON_ST_NAME_WINDOWS = {
    "600666.XSHG": ("2020-02-28", "2020-02-28"),
    "600654.XSHG": ("2020-02-28", "2020-02-28"),
    "002192.XSHE": ("2020-07-15", "2020-07-15"),
    "600255.XSHG": ("2020-08-25", "2020-08-25"),
    "002256.XSHE": ("2020-08-27", "2020-08-27"),
    "600145.XSHG": ("2020-09-09", "2020-09-09"),
    "002638.XSHE": ("2020-10-23", "2020-10-23"),
    "600687.XSHG": ("2020-11-23", "2020-11-23"),
    "000673.XSHE": ("2020-11-30", "2020-11-30"),
    "600146.XSHG": [("2020-12-14", "2020-12-14"), ("2022-03-02", "2022-04-01")],
    "000585.XSHE": ("2020-12-18", "2020-12-18"),
    "002147.XSHE": ("2021-01-14", "2021-01-14"),
    "600702.XSHG": ("2021-04-21", "2021-04-21"),
    "601020.XSHG": ("2021-09-10", "2021-09-10"),
    "000980.XSHE": ("2021-12-10", "2021-12-10"),
    "600191.XSHG": ("2022-02-07", "2022-02-07"),
    "603268.XSHG": ("2026-02-12", "2026-02-12"),
    "600091.XSHG": ("2022-02-08", "2022-02-08"),
    "600093.XSHG": ("2022-02-10", "2022-03-15"),
    "002086.XSHE": ("2022-02-15", "2022-02-15"),
    "002684.XSHE": ("2022-04-19", "2022-04-19"),
    "002470.XSHE": ("2022-07-05", "2022-07-05"),
    "600532.XSHG": [("2023-01-03", "2023-01-03"), ("2023-06-01", "2023-06-01")],
    "000839.XSHE": ("2023-06-01", "2023-06-01"),
    "600242.XSHG": ("2023-06-01", "2023-06-01"),
    "603030.XSHG": ("2023-06-01", "2023-06-01"),
    "603880.XSHG": ("2023-06-01", "2023-06-01"),
    "600518.XSHG": [("2023-03-22", "2023-03-22"), ("2023-04-10", "2023-04-10")],
    "600856.XSHG": ("1900-01-01", "2020-05-06"),
    "000584.XSHE": ("2024-04-22", "2024-04-22"),
    "002141.XSHE": [("2024-06-07", "2024-06-07"), ("2024-07-15", "2024-07-15")],
    "002052.XSHE": ("2024-06-20", "2024-06-20"),
    "603003.XSHG": ("2024-06-27", "2024-06-27"),
    "000506.XSHE": ("2024-08-07", "2024-08-07"),
    "600711.XSHG": [("2025-07-22", "2025-07-22"), ("2025-07-24", "2025-07-24")],
}

BILLBOARD_ROW_FILTERS = [
    ("600146.XSHG", "20200226"),
    ("603721.XSHG", "20220825"),
]

