import math
from types import SimpleNamespace

import pandas as pd

from rebuild_from_archive.project_compat import EmotionGateJQCompat


def test_minute_and_execution_overrides():
    compat = EmotionGateJQCompat(r"D:\Work Space\他山之石\情绪门控")
    assert compat.get_minute_price_override("20200114", "11:25", "002056.XSHE") == 10.90
    assert compat.get_execution_price_override("20230323", "09:30", "600518.XSHG", "buy") == 2.16


def test_order_amount_sequence_config_and_fill_override():
    compat = EmotionGateJQCompat(r"D:\Work Space\他山之石\情绪门控")
    assert compat.get_order_amount_override("20200518", "09:26", "000987.XSHE") == [38600, 33800]
    assert compat.get_fill_amount_override("20200416", "09:30", "002041.XSHE") == 39300


def test_call_auction_overrides_apply():
    compat = EmotionGateJQCompat(r"D:\Work Space\他山之石\情绪门控")
    frame = pd.DataFrame(
        [
            {"code": "002897.XSHE", "_date_int": 20200304, "a1_v": 1.0},
            {"code": "002635.XSHE", "_date_int": 20200903, "a1_v": 100.0},
            {"code": "000833.XSHE", "_date_int": 20210818, "a1_v": 10.0},
            {"code": "603908.XSHG", "_date_int": 20210818, "a1_v": 11.0},
        ]
    )
    out = compat.apply_call_auction_overrides(frame)
    assert "002897.XSHE" not in set(out["code"])
    assert "603908.XSHG" not in set(out["code"])
    assert set(out[out["_date_int"] == 20210818]["code"]) == {"000833.XSHE"}
    patched = out[(out["code"] == "002635.XSHE") & (out["_date_int"] == 20200903)]
    assert float(patched.iloc[0]["a1_v"]) == 2000.0


def test_strategy_state_override_and_instrument_fallback():
    compat = EmotionGateJQCompat(r"D:\Work Space\他山之石\情绪门控")
    state = SimpleNamespace(first_board_perf=1.0, fb_pct=0.8, fb_perf_history=[1.0], v227_shock_cooldown=0)
    context = SimpleNamespace(current_dt=pd.Timestamp("2020-08-05"))
    compat.apply_strategy_state_override("after_fb_state", context, state)
    assert math.isnan(state.first_board_perf)
    assert state.fb_pct == 0.0
    assert math.isnan(state.fb_perf_history[-1])

    context2 = SimpleNamespace(current_dt=pd.Timestamp("2023-02-17"))
    compat.apply_strategy_state_override("after_v227_shock", context2, state)
    assert state.v227_shock_cooldown == 1

    fallback = compat.get_instrument_price_fallback("511880.XSHG", end_date="2024-01-02")
    assert float(fallback["close"].iloc[0]) == 100.094
    assert compat.has_zero_fee_override("511880.XSHG") is True
