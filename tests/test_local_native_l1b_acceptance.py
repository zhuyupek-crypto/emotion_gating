"""Unit tests for the L1B compatibility layer and acceptance verification gates.
"""

from __future__ import annotations

import json
import pytest
import pandas as pd
from pathlib import Path

from rebuild_from_archive.compat.profiles import (
    JQ_PARITY,
    LOCAL_NATIVE_L1A,
    LOCAL_NATIVE_L1B,
    PROFILE_DISABLED_HOOKS,
)
from rebuild_from_archive.project_compat import EmotionGateJQCompat
from tools.local_native_l1b_acceptance import compare_runs_l1b


class TestL1BProfilePrecise:
    """Verify that L1B profile precisely disables exactly the 4 hooks."""

    def test_l1b_profile_disabled_hooks(self):
        c = EmotionGateJQCompat(profile=LOCAL_NATIVE_L1B)
        assert c.disabled_hook_ids == frozenset({
            "market_data.minute_price_anomalies",
            "execution.execution_price_anomalies",
            "execution.order_amount_anomalies",
            "execution.fill_amount_anomalies",
        })


class TestL1BSequentialOverrideSemantics:
    """Verify that list-type overrides follow sequential consumption and index-tracking."""

    def test_order_amount_list_sequential_consumption(self):
        # ("20200518", "09:26", "000987.XSHE"): [38600, 33800]
        # Test under JQ_PARITY (enabled)
        c = EmotionGateJQCompat(profile=JQ_PARITY)
        
        # 1st query
        r1 = c.get_order_amount_override("20200518", "09:26", "000987.XSHE")
        assert r1 == [38600, 33800]
        assert c._order_query_counts[("20200518", "09:26", "000987.XSHE")] == 1
        
        # 2nd query
        r2 = c.get_order_amount_override("20200518", "09:26", "000987.XSHE")
        assert r2 == [38600, 33800]
        assert c._order_query_counts[("20200518", "09:26", "000987.XSHE")] == 2
        
        # 3rd query
        r3 = c.get_order_amount_override("20200518", "09:26", "000987.XSHE")
        assert r3 == [38600, 33800]
        assert c._order_query_counts[("20200518", "09:26", "000987.XSHE")] == 3

        # Verify telemetry
        t = c.profile_manifest()
        events = c._hook_hit_keys
        assert len(events) == 2
        assert events[0]["override_value"] == 38600
        assert events[0]["key_query_ordinal"] == 1
        assert events[0]["sequence_index"] == 0
        assert events[0]["effective_hit"] is True
        assert events[0]["would_have_hit"] is False
        
        assert events[1]["override_value"] == 33800
        assert events[1]["key_query_ordinal"] == 2
        assert events[1]["sequence_index"] == 1
        assert events[1]["effective_hit"] is True
        assert events[1]["would_have_hit"] is False

    def test_order_amount_list_sequential_would_have_hits(self):
        # Test under LOCAL_NATIVE_L1B (disabled)
        c = EmotionGateJQCompat(profile=LOCAL_NATIVE_L1B)
        
        # 1st query
        r1 = c.get_order_amount_override("20200518", "09:26", "000987.XSHE")
        assert r1 is None
        
        # 2nd query
        r2 = c.get_order_amount_override("20200518", "09:26", "000987.XSHE")
        assert r2 is None
        
        # 3rd query
        r3 = c.get_order_amount_override("20200518", "09:26", "000987.XSHE")
        assert r3 is None

        # Verify telemetry
        events = c._hook_would_have_hit_keys
        assert len(events) == 2
        assert events[0]["override_value"] == 38600
        assert events[0]["key_query_ordinal"] == 1
        assert events[0]["sequence_index"] == 0
        assert events[0]["effective_hit"] is False
        assert events[0]["would_have_hit"] is True
        
        assert events[1]["override_value"] == 33800
        assert events[1]["key_query_ordinal"] == 2
        assert events[1]["sequence_index"] == 1
        assert events[1]["effective_hit"] is False
        assert events[1]["would_have_hit"] is True


class TestCompatControlGroupUnchanged:
    """Verify that JQ_PARITY and LOCAL_NATIVE_L1A profiles behave exactly as before."""

    def test_jq_parity_and_l1a_behavior(self):
        jq = EmotionGateJQCompat(profile=JQ_PARITY)
        l1a = EmotionGateJQCompat(profile=LOCAL_NATIVE_L1A)
        
        # Order amount overrides should be identical and enabled
        r_jq = jq.get_order_amount_override("20200210", "09:27", "600400.XSHG")
        r_l1a = l1a.get_order_amount_override("20200210", "09:27", "600400.XSHG")
        assert r_jq == 146300
        assert r_l1a == 146300
        
        # Fill amount overrides should be identical and enabled
        rf_jq = jq.get_fill_amount_override("20200402", "09:30", "600086.XSHG")
        rf_l1a = l1a.get_fill_amount_override("20200402", "09:30", "600086.XSHG")
        assert rf_jq == 146000
        assert rf_l1a == 146000


class TestL1BClassification:
    """Verify the classification logic separating direct_size_diffs and downstream_diffs."""

    def test_classification_logic(self, tmp_path):
        l1a_dir = tmp_path / "l1a"
        l1b_dir = tmp_path / "l1b"
        out_dir = tmp_path / "out"
        for d in (l1a_dir, l1b_dir, out_dir):
            d.mkdir(parents=True, exist_ok=True)
            
        # Write dummy profiles and summaries
        for d, prof in [(l1a_dir, "local_native_l1a"), (l1b_dir, "local_native_l1b")]:
            (d / "profile_manifest.json").write_text(json.dumps({
                "profile": prof,
                "disabled_hook_ids": sorted(list(PROFILE_DISABLED_HOOKS[prof]))
            }))
            (d / "run_summary.json").write_text(json.dumps({
                "profile": prof,
                "total_return_pct": 5.0,
            }))
            
        # Dummy hook counts
        # L1A has effective hits
        (l1a_dir / "hook_counts.json").write_text(json.dumps({
            "execution.order_amount_anomalies": {
                "effective_hits": 1,
                "effective_hit_keys": [{"date": "20200518", "time": "09:26", "code": "000987.XSHE", "side": "buy", "key_query_ordinal": 1}]
            },
            "execution.fill_amount_anomalies": {
                "effective_hits": 0,
                "effective_hit_keys": []
            }
        }))
        # L1B has would-have-hits
        (l1b_dir / "hook_counts.json").write_text(json.dumps({
            "execution.order_amount_anomalies": {
                "effective_hits": 0,
                "would_have_hits": 1,
                "would_have_hit_keys": [{"date": "20200518", "time": "09:26", "code": "000987.XSHE", "side": "buy", "key_query_ordinal": 1}]
            },
            "execution.fill_amount_anomalies": {
                "effective_hits": 0,
                "would_have_hits": 0,
                "would_have_hit_keys": []
            }
        }))

        # Dummy size hook events
        # L1A has override active
        pd.DataFrame([{
            "hook_id": "execution.order_amount_anomalies",
            "date": "20200518",
            "time": "09:26",
            "code": "000987.XSHE",
            "side": "buy",
            "order_id": "1",
            "key_query_ordinal": 1,
            "sequence_index": 0,
            "computed_amount_before_override": 10000,
            "override_amount": 38600,
            "final_order_amount": 38600,
            "effective_hit": True,
            "would_have_hit": False
        }]).to_csv(l1a_dir / "size_hook_events.csv", index=False)

        # L1B has override disabled
        pd.DataFrame([{
            "hook_id": "execution.order_amount_anomalies",
            "date": "20200518",
            "time": "09:26",
            "code": "000987.XSHE",
            "side": "buy",
            "order_id": "1",
            "key_query_ordinal": 1,
            "sequence_index": 0,
            "computed_amount_before_override": 10000,
            "override_amount": 38600,
            "final_order_amount": 10000,
            "effective_hit": False,
            "would_have_hit": True
        }]).to_csv(l1b_dir / "size_hook_events.csv", index=False)

        # Write dummy trades
        # L1A has trade with override amount 38600
        pd.DataFrame([{
            "time": "2020-05-18 09:26:00",
            "code": "000987.XSHE",
            "amount": 38600,
            "price": 10.0,
        }, {
            # Downstream cascading diff
            "time": "2020-05-19 10:00:00",
            "code": "000001.XSHE",
            "amount": 5000,
            "price": 12.0,
        }]).to_csv(l1a_dir / "local_trades_2020.csv", index=False)

        # L1B has trade with computed amount 10000
        pd.DataFrame([{
            "time": "2020-05-18 09:26:00",
            "code": "000987.XSHE",
            "amount": 10000,
            "price": 10.0,
        }, {
            # Downstream cascading diff (changed amount)
            "time": "2020-05-19 10:00:00",
            "code": "000001.XSHE",
            "amount": 2000,
            "price": 12.0,
        }]).to_csv(l1b_dir / "local_trades_2020.csv", index=False)

        # Write dummy equity, state, portfolio, positions
        for d in (l1a_dir, l1b_dir):
            pd.DataFrame([{"date": "2020-05-17", "value": 1000000.0}]).to_csv(d / "local_equity_2020.csv", index=False)
            pd.DataFrame([{"date": "2020-05-17", "available_cash": 1000000.0, "total_value": 1000000.0}]).to_csv(d / "local_portfolio_stats_2020.csv", index=False)
            pd.DataFrame([{"date": "2020-05-17", "code": "000987.XSHE", "amount": 0, "avg_cost": 0.0, "price": 10.0}]).to_csv(d / "local_positions_2020.csv", index=False)
            pd.DataFrame([{"date": "2020-05-17", "available_cash": 1000000.0}]).to_csv(d / "local_state_2020.csv", index=False)

        # Run comparison
        r = compare_runs_l1b(l1a_dir, l1b_dir, out_dir)
        
        # Verify classification
        direct_diffs = pd.read_csv(out_dir / "DIRECT_SIZE_DIFFS.csv")
        assert len(direct_diffs) == 1
        assert direct_diffs.iloc[0]["trade_key"] == "2020-05-18|2020-05-18 09:26:00|000987.XSHE|buy#1"
        assert direct_diffs.iloc[0]["l1a_amount"] == 38600
        assert direct_diffs.iloc[0]["l1b_amount"] == 10000
        assert direct_diffs.iloc[0]["override_value"] == 38600
        
        downstream_diffs = pd.read_csv(out_dir / "TRADE_KEY_DIFFS.csv")
        assert len(downstream_diffs) == 1
        assert downstream_diffs.iloc[0]["trade_key"] == "2020-05-19|2020-05-19 10:00:00|000001.XSHE|buy#1"
        assert downstream_diffs.iloc[0]["diff_type"] == "amount_diff"
