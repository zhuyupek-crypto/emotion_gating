"""Tests for the L1A acceptance tool itself (not the full backtest)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "tools" / "local_native_l1a_acceptance.py"


class TestToolHelp:
    """Tool CLI responds to help and basic commands."""

    def test_help_does_not_crash(self):
        result = subprocess.run(
            [sys.executable, str(TOOL), "--help"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0
        assert "run" in result.stdout
        assert "compare" in result.stdout

    def test_run_help(self):
        result = subprocess.run(
            [sys.executable, str(TOOL), "run", "--help"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0

    def test_compare_help(self):
        result = subprocess.run(
            [sys.executable, str(TOOL), "compare", "--help"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0


class TestAcceptanceLogic:
    """Test acceptance logic functions directly."""

    def test_trade_key_generation(self):
        """_build_trade_keys produces consistent keys."""
        import pandas as pd
        from tools.local_native_l1a_acceptance import _build_trade_keys

        df = pd.DataFrame({
            "time": ["2020-01-02 09:30:00", "2020-01-02 09:30:00", "2020-01-03 14:50:00"],
            "code": ["000001.XSHE", "000001.XSHE", "000002.XSHE"],
            "amount": [1000, -500, 2000],
        })
        keys = _build_trade_keys(df)
        assert len(keys) == 3
        assert keys[0].startswith("2020-01-02|")
        # Different sides get different base keys even at same time
        assert "buy" in keys[0] or "sell" in keys[0]
        assert "buy" in keys[1] or "sell" in keys[1]

    def test_trade_key_deterministic(self):
        """Same data produces same keys."""
        import pandas as pd
        from tools.local_native_l1a_acceptance import _build_trade_keys

        df = pd.DataFrame({
            "time": ["2020-01-02 09:30", "2020-01-02 09:31"],
            "code": ["000001.XSHE", "000002.XSHE"],
            "amount": [1000, -500],
        })
        keys1 = _build_trade_keys(df)
        keys2 = _build_trade_keys(df)
        assert keys1 == keys2

    def test_jsonable_handles_nan(self):
        from tools.local_native_l1a_acceptance import _jsonable
        assert _jsonable(float("nan")) == "NaN"
        assert _jsonable(float("inf")) == float("inf")

    def test_jsonable_handles_timestamp(self):
        import pandas as pd
        from tools.local_native_l1a_acceptance import _jsonable
        ts = pd.Timestamp("2020-01-02")
        assert _jsonable(ts) == "2020-01-02 00:00:00"
