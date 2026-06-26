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


class TestL1BAcceptanceAdditionalGates:
    """Verify negative and positive test cases for all new L1B gates and constraints."""

    def _setup_mock_run(self, l1a_dir, l1b_dir, out_dir):
        # Create directories
        for d in (l1a_dir, l1b_dir, out_dir):
            d.mkdir(parents=True, exist_ok=True)
        # Write summaries
        for d, prof in [(l1a_dir, "local_native_l1a"), (l1b_dir, "local_native_l1b")]:
            (d / "profile_manifest.json").write_text(json.dumps({
                "profile": prof,
                "disabled_hook_ids": sorted(list(PROFILE_DISABLED_HOOKS[prof]))
            }))
            (d / "run_summary.json").write_text(json.dumps({
                "profile": prof,
                "total_return_pct": 5.0,
                "source_commit": "test-commit-123",
                "base_main_commit": "main-commit",
                "strategy_sha256": "strategy-sha",
            }))
            (d / "hook_counts.json").write_text(json.dumps({
                "execution.order_amount_anomalies": {"effective_hits": 0, "would_have_hits": 0, "effective_hit_keys": [], "would_have_hit_keys": []},
                "execution.fill_amount_anomalies": {"effective_hits": 0, "would_have_hits": 0, "effective_hit_keys": [], "would_have_hit_keys": []}
            }))
            pd.DataFrame(columns=["hook_id", "date", "time", "code", "side", "order_id", "query_ordinal", "key_query_ordinal", "sequence_index", "computed_amount_before_override", "override_amount", "final_order_amount", "final_fill_amount", "profile", "effective_hit", "would_have_hit"]).to_csv(d / "size_hook_events.csv", index=False)
            pd.DataFrame(columns=["time", "code", "amount", "price", "commission", "tax", "trade_id", "order_id"]).to_csv(d / "local_trades_2020.csv", index=False)
            pd.DataFrame([{"date": "2020-01-01", "value": 1000000.0}]).to_csv(d / "local_equity_2020.csv", index=False)
            pd.DataFrame([{"date": "2020-01-01", "available_cash": 1000000.0, "total_value": 1000000.0}]).to_csv(d / "local_portfolio_stats_2020.csv", index=False)
            pd.DataFrame(columns=["date", "code", "amount", "avg_cost", "price"]).to_csv(d / "local_positions_2020.csv", index=False)
            pd.DataFrame([{"date": "2020-01-01", "available_cash": 1000000.0}]).to_csv(d / "local_state_2020.csv", index=False)

    def test_ordinary_event_not_direct(self, tmp_path):
        l1a_dir = tmp_path / "l1a"
        l1b_dir = tmp_path / "l1b"
        out_dir = tmp_path / "out"
        self._setup_mock_run(l1a_dir, l1b_dir, out_dir)

        # Write ordinary events (effective_hit=False, would_have_hit=False, override_amount=NaN)
        pd.DataFrame([{
            "hook_id": "execution.order_amount_anomalies", "date": "20200518", "time": "09:26", "code": "000987.XSHE",
            "side": "buy", "order_id": "1", "key_query_ordinal": 1, "sequence_index": 0,
            "computed_amount_before_override": 10000, "override_amount": None, "final_order_amount": 10000,
            "effective_hit": False, "would_have_hit": False
        }]).to_csv(l1a_dir / "size_hook_events.csv", index=False)

        pd.DataFrame([{
            "hook_id": "execution.order_amount_anomalies", "date": "20200518", "time": "09:26", "code": "000987.XSHE",
            "side": "buy", "order_id": "1", "key_query_ordinal": 1, "sequence_index": 0,
            "computed_amount_before_override": 10000, "override_amount": None, "final_order_amount": 10000,
            "effective_hit": False, "would_have_hit": False
        }]).to_csv(l1b_dir / "size_hook_events.csv", index=False)

        # Write trade differences
        pd.DataFrame([{"time": "2020-05-18 09:26:00", "code": "000987.XSHE", "amount": 38600, "price": 10.0}]).to_csv(l1a_dir / "local_trades_2020.csv", index=False)
        pd.DataFrame([{"time": "2020-05-18 09:26:00", "code": "000987.XSHE", "amount": 10000, "price": 10.0}]).to_csv(l1b_dir / "local_trades_2020.csv", index=False)

        pd.DataFrame().to_csv(out_dir / "L0_MAIN_VS_HEAD_STATE_DIFFS.csv", index=False)
        (out_dir / "L0_MAIN_VS_HEAD_REPORT.json").write_text(json.dumps({
            "baseline_commit": "6369570406b77dda9903e832dccd5516fc9c5986",
            "current_commit": "test-commit-123",
            "l0_results": {"trades_diff_rows": 0, "state_diff_rows": 0, "equity_diff_rows": 0, "portfolio_stats_diff_rows": 0, "positions_diff_rows": 0, "final_value_diff": 0.0}
        }))

        # Generate SIZE_HOOK_EVENTS.csv in compare runs
        r = compare_runs_l1b(l1a_dir, l1b_dir, out_dir)
        direct_df = pd.read_csv(out_dir / "DIRECT_SIZE_DIFFS.csv")
        trade_key_df = pd.read_csv(out_dir / "TRADE_KEY_DIFFS.csv")

        # Because it was an ordinary event (not effective/would_have hit and no override), it must NOT be direct!
        assert len(direct_df) == 0
        assert len(trade_key_df) == 1

    def test_genuine_hook_event_is_direct(self, tmp_path):
        l1a_dir = tmp_path / "l1a"
        l1b_dir = tmp_path / "l1b"
        out_dir = tmp_path / "out"
        self._setup_mock_run(l1a_dir, l1b_dir, out_dir)

        # Write genuine hook event pair (L1A has effective_hit=True, L1B has would_have_hit=True, override matches)
        pd.DataFrame([{
            "hook_id": "execution.order_amount_anomalies", "date": "20200518", "time": "09:26", "code": "000987.XSHE",
            "side": "buy", "order_id": "1", "key_query_ordinal": 1, "sequence_index": 0,
            "computed_amount_before_override": 10000, "override_amount": 38600, "final_order_amount": 38600,
            "effective_hit": True, "would_have_hit": False
        }]).to_csv(l1a_dir / "size_hook_events.csv", index=False)

        pd.DataFrame([{
            "hook_id": "execution.order_amount_anomalies", "date": "20200518", "time": "09:26", "code": "000987.XSHE",
            "side": "buy", "order_id": "1", "key_query_ordinal": 1, "sequence_index": 0,
            "computed_amount_before_override": 10000, "override_amount": 38600, "final_order_amount": 10000,
            "effective_hit": False, "would_have_hit": True
        }]).to_csv(l1b_dir / "size_hook_events.csv", index=False)

        # Write trade differences
        pd.DataFrame([{"time": "2020-05-18 09:26:00", "code": "000987.XSHE", "amount": 38600, "price": 10.0}]).to_csv(l1a_dir / "local_trades_2020.csv", index=False)
        pd.DataFrame([{"time": "2020-05-18 09:26:00", "code": "000987.XSHE", "amount": 10000, "price": 10.0}]).to_csv(l1b_dir / "local_trades_2020.csv", index=False)

        pd.DataFrame().to_csv(out_dir / "L0_MAIN_VS_HEAD_STATE_DIFFS.csv", index=False)
        (out_dir / "L0_MAIN_VS_HEAD_REPORT.json").write_text(json.dumps({
            "baseline_commit": "6369570406b77dda9903e832dccd5516fc9c5986",
            "current_commit": "test-commit-123",
            "l0_results": {"trades_diff_rows": 0, "state_diff_rows": 0, "equity_diff_rows": 0, "portfolio_stats_diff_rows": 0, "positions_diff_rows": 0, "final_value_diff": 0.0}
        }))

        # Mock the hook counts so l1a hits aren't 0 (required for l1a_size_hooks_have_effective_hits gate check)
        (l1a_dir / "hook_counts.json").write_text(json.dumps({
            "execution.order_amount_anomalies": {"effective_hits": 1, "would_have_hits": 0, "effective_hit_keys": [{"date": "20200518", "time": "09:26", "code": "000987.XSHE", "side": "buy", "key_query_ordinal": 1}]},
            "execution.fill_amount_anomalies": {"effective_hits": 1, "would_have_hits": 0, "effective_hit_keys": [{"date": "20200518", "time": "09:26", "code": "000987.XSHE", "side": "buy", "key_query_ordinal": 1}]}
        }))
        (l1b_dir / "hook_counts.json").write_text(json.dumps({
            "execution.order_amount_anomalies": {"effective_hits": 0, "would_have_hits": 1, "would_have_hit_keys": [{"date": "20200518", "time": "09:26", "code": "000987.XSHE", "side": "buy", "key_query_ordinal": 1}]},
            "execution.fill_amount_anomalies": {"effective_hits": 0, "would_have_hits": 1, "would_have_hit_keys": [{"date": "20200518", "time": "09:26", "code": "000987.XSHE", "side": "buy", "key_query_ordinal": 1}]}
        }))

        r = compare_runs_l1b(l1a_dir, l1b_dir, out_dir)
        direct_df = pd.read_csv(out_dir / "DIRECT_SIZE_DIFFS.csv")
        assert len(direct_df) == 1
        assert direct_df.iloc[0]["trade_key"] == "2020-05-18|2020-05-18 09:26:00|000987.XSHE|buy#1"
        assert r["acceptance_gates"]["all_direct_diffs_map_to_genuine_hooks"] == "PASS"

    def test_l0_gate_missing_report(self, tmp_path):
        l1a_dir = tmp_path / "l1a"
        l1b_dir = tmp_path / "l1b"
        out_dir = tmp_path / "out"
        self._setup_mock_run(l1a_dir, l1b_dir, out_dir)
        
        # Missing L0_MAIN_VS_HEAD_REPORT.json
        r = compare_runs_l1b(l1a_dir, l1b_dir, out_dir)
        assert r["acceptance_gates"]["l0_main_vs_head"] == "FAIL"

    def test_l0_gate_nonzero(self, tmp_path):
        l1a_dir = tmp_path / "l1a"
        l1b_dir = tmp_path / "l1b"
        out_dir = tmp_path / "out"
        self._setup_mock_run(l1a_dir, l1b_dir, out_dir)
        
        pd.DataFrame().to_csv(out_dir / "L0_MAIN_VS_HEAD_STATE_DIFFS.csv", index=False)
        # Non-zero diff rows
        (out_dir / "L0_MAIN_VS_HEAD_REPORT.json").write_text(json.dumps({
            "baseline_commit": "6369570406b77dda9903e832dccd5516fc9c5986",
            "current_commit": "test-commit-123",
            "l0_results": {"trades_diff_rows": 5, "state_diff_rows": 0, "equity_diff_rows": 0, "portfolio_stats_diff_rows": 0, "positions_diff_rows": 0, "final_value_diff": 0.0}
        }))
        r = compare_runs_l1b(l1a_dir, l1b_dir, out_dir)
        assert r["acceptance_gates"]["l0_main_vs_head"] == "FAIL"

    def test_l0_gate_zero(self, tmp_path):
        l1a_dir = tmp_path / "l1a"
        l1b_dir = tmp_path / "l1b"
        out_dir = tmp_path / "out"
        self._setup_mock_run(l1a_dir, l1b_dir, out_dir)
        
        pd.DataFrame().to_csv(out_dir / "L0_MAIN_VS_HEAD_STATE_DIFFS.csv", index=False)
        (out_dir / "L0_MAIN_VS_HEAD_REPORT.json").write_text(json.dumps({
            "baseline_commit": "6369570406b77dda9903e832dccd5516fc9c5986",
            "current_commit": "test-commit-123",
            "l0_results": {"trades_diff_rows": 0, "state_diff_rows": 0, "equity_diff_rows": 0, "portfolio_stats_diff_rows": 0, "positions_diff_rows": 0, "final_value_diff": 0.0}
        }))
        r = compare_runs_l1b(l1a_dir, l1b_dir, out_dir)
        assert r["acceptance_gates"]["l0_main_vs_head"] == "PASS"

    def test_required_state_diffs(self, tmp_path):
        l1a_dir = tmp_path / "l1a"
        l1b_dir = tmp_path / "l1b"
        out_dir = tmp_path / "out"
        self._setup_mock_run(l1a_dir, l1b_dir, out_dir)
        
        pd.DataFrame().to_csv(out_dir / "L0_MAIN_VS_HEAD_STATE_DIFFS.csv", index=False)
        (out_dir / "L0_MAIN_VS_HEAD_REPORT.json").write_text(json.dumps({
            "baseline_commit": "6369570406b77dda9903e832dccd5516fc9c5986",
            "current_commit": "test-commit-123",
            "l0_results": {"trades_diff_rows": 0, "state_diff_rows": 0, "equity_diff_rows": 0, "portfolio_stats_diff_rows": 0, "positions_diff_rows": 0, "final_value_diff": 0.0}
        }))

        # Run comparison, it generates all compare stage files.
        r = compare_runs_l1b(l1a_dir, l1b_dir, out_dir)
        assert r["acceptance_gates"]["required_artifacts_complete"] == "PASS"

        # If we remove L0_MAIN_VS_HEAD_STATE_DIFFS.csv
        (out_dir / "L0_MAIN_VS_HEAD_STATE_DIFFS.csv").unlink()
        r = compare_runs_l1b(l1a_dir, l1b_dir, out_dir)
        assert r["acceptance_gates"]["required_artifacts_complete"] == "FAIL"

    def test_required_l0_report(self, tmp_path):
        l1a_dir = tmp_path / "l1a"
        l1b_dir = tmp_path / "l1b"
        out_dir = tmp_path / "out"
        self._setup_mock_run(l1a_dir, l1b_dir, out_dir)
        
        # L0 report not generated in out_dir
        r = compare_runs_l1b(l1a_dir, l1b_dir, out_dir)
        assert r["acceptance_gates"]["required_artifacts_complete"] == "FAIL"

    def test_account_ordinary_event_no_exemption(self, tmp_path):
        l1a_dir = tmp_path / "l1a"
        l1b_dir = tmp_path / "l1b"
        out_dir = tmp_path / "out"
        self._setup_mock_run(l1a_dir, l1b_dir, out_dir)

        # Non-standard lot size (e.g. 150 shares for stock)
        pd.DataFrame([{"time": "2020-05-18 09:26:00", "code": "000987.XSHE", "amount": 150, "price": 10.0, "order_id": 1}]).to_csv(l1a_dir / "local_trades_2020.csv", index=False)
        pd.DataFrame([{"time": "2020-05-18 09:26:00", "code": "000987.XSHE", "amount": 150, "price": 10.0, "order_id": 1}]).to_csv(l1b_dir / "local_trades_2020.csv", index=False)

        # Write ordinary event
        pd.DataFrame([{
            "hook_id": "execution.order_amount_anomalies", "date": "20200518", "time": "09:26", "code": "000987.XSHE",
            "side": "buy", "order_id": "1", "key_query_ordinal": 1, "sequence_index": 0,
            "computed_amount_before_override": 100, "override_amount": None, "final_order_amount": 100,
            "effective_hit": False, "would_have_hit": False
        }]).to_csv(l1a_dir / "size_hook_events.csv", index=False)

        pd.DataFrame().to_csv(out_dir / "L0_MAIN_VS_HEAD_STATE_DIFFS.csv", index=False)
        (out_dir / "L0_MAIN_VS_HEAD_REPORT.json").write_text(json.dumps({
            "baseline_commit": "6369570406b77dda9903e832dccd5516fc9c5986",
            "current_commit": "test-commit-123",
            "l0_results": {"trades_diff_rows": 0, "state_diff_rows": 0, "equity_diff_rows": 0, "portfolio_stats_diff_rows": 0, "positions_diff_rows": 0, "final_value_diff": 0.0}
        }))

        r = compare_runs_l1b(l1a_dir, l1b_dir, out_dir)
        # Should fail account invariants because 150 is not a multiple of 100, and it is a buy trade (so not sell-all)
        # and it's not exempt since the event is not an effective hit
        assert r["acceptance_gates"]["account_invariants"] == "FAIL"

    def test_account_effective_hit_exemption(self, tmp_path):
        l1a_dir = tmp_path / "l1a"
        l1b_dir = tmp_path / "l1b"
        out_dir = tmp_path / "out"
        self._setup_mock_run(l1a_dir, l1b_dir, out_dir)

        # L1A has trade with 150 shares (non-standard), but JQ override was 150 shares
        pd.DataFrame([{"time": "2020-05-18 09:26:00", "code": "000987.XSHE", "amount": 150, "price": 10.0, "order_id": 1}]).to_csv(l1a_dir / "local_trades_2020.csv", index=False)
        # L1B must have standard lot size because its override is disabled
        pd.DataFrame([{"time": "2020-05-18 09:26:00", "code": "000987.XSHE", "amount": 100, "price": 10.0, "order_id": 1}]).to_csv(l1b_dir / "local_trades_2020.csv", index=False)

        # L1A effective hit
        pd.DataFrame([{
            "hook_id": "execution.order_amount_anomalies", "date": "20200518", "time": "09:26", "code": "000987.XSHE",
            "side": "buy", "order_id": "1", "key_query_ordinal": 1, "sequence_index": 0,
            "computed_amount_before_override": 100, "override_amount": 150, "final_order_amount": 150,
            "effective_hit": True, "would_have_hit": False
        }]).to_csv(l1a_dir / "size_hook_events.csv", index=False)

        pd.DataFrame().to_csv(out_dir / "L0_MAIN_VS_HEAD_STATE_DIFFS.csv", index=False)
        (out_dir / "L0_MAIN_VS_HEAD_REPORT.json").write_text(json.dumps({
            "baseline_commit": "6369570406b77dda9903e832dccd5516fc9c5986",
            "current_commit": "test-commit-123",
            "l0_results": {"trades_diff_rows": 0, "state_diff_rows": 0, "equity_diff_rows": 0, "portfolio_stats_diff_rows": 0, "positions_diff_rows": 0, "final_value_diff": 0.0}
        }))

        r = compare_runs_l1b(l1a_dir, l1b_dir, out_dir)
        # Should pass account invariants because JQ override is 150 and effective_hit is True in JQ parity/L1A
        assert r["acceptance_gates"]["account_invariants"] == "PASS"

    def test_determinism_report_roundtrip_fail(self, tmp_path):
        from tools.local_native_l1b_acceptance import verify_determinism_and_finalize_l1b
        run1_dir = tmp_path / "run1"
        run2_dir = tmp_path / "run2"
        for d in (run1_dir, run2_dir):
            d.mkdir(parents=True, exist_ok=True)
            
        # Write same stable files initially
        stable_files = [
            "PROFILE_MANIFEST.json", "DIRECT_SIZE_DIFFS.csv",
            "TRADE_KEY_DIFFS.csv", "STATE_DIFFS_SAMPLE.csv"
        ]
        for name in stable_files:
            (run1_dir / name).write_text("content", encoding="utf-8")
            (run2_dir / name).write_text("content", encoding="utf-8")
            
        # Create reports
        report_data = {
            "title": "Report",
            "acceptance_gates": {
                "l1b_exact_hook_set": "PASS",
                "l1a_size_hooks_have_effective_hits": "PASS",
                "l1b_size_hooks_effective_hits_zero": "PASS",
                "would_have_hit_events_complete": "PASS",
                "first_direct_diff_maps_to_hook": "PASS",
                "divergence_not_before_first_hit": "PASS",
                "pre_hit_exact_match": "PASS",
                "direct_price_unchanged": "PASS",
                "account_invariants": "PASS",
                "required_artifacts_complete": "PASS",
                "all_direct_diffs_map_to_genuine_hooks": "PASS",
                "l0_main_vs_head": "PASS",
                "deterministic_reports": "FAIL",
                "implementation_acceptance": "FAIL"
            }
        }
        
        # Initially let reports match
        (run1_dir / "LOCAL_NATIVE_L1B_REPORT.json").write_text(json.dumps(report_data, indent=2), encoding="utf-8")
        (run2_dir / "LOCAL_NATIVE_L1B_REPORT.json").write_text(json.dumps(report_data, indent=2), encoding="utf-8")
        (run1_dir / "LOCAL_NATIVE_L1B_REPORT.md").write_text("initial md", encoding="utf-8")
        (run2_dir / "LOCAL_NATIVE_L1B_REPORT.md").write_text("initial md", encoding="utf-8")

        # Set up final delivery artifacts
        # We need mock L0_MAIN_VS_HEAD_REPORT.json and L0_MAIN_VS_HEAD_STATE_DIFFS.csv and SIZE_HOOK_EVENTS.csv in both directories
        # to ensure final_artifacts_ok checks pass
        for d in (run1_dir, run2_dir):
            (d / "L0_MAIN_VS_HEAD_REPORT.json").write_text("L0 report", encoding="utf-8")
            (d / "L0_MAIN_VS_HEAD_STATE_DIFFS.csv").write_text("L0 state diffs", encoding="utf-8")
            (d / "SIZE_HOOK_EVENTS.csv").write_text("Size hook events", encoding="utf-8")

        # verify_determinism should succeed first
        det = verify_determinism_and_finalize_l1b(run1_dir, run2_dir)
        assert det["status"] == "PASS"

        # Now, if we manually corrupt run2's report md after writing it or make them mismatch
        (run2_dir / "TRADE_KEY_DIFFS.csv").write_text("changed content", encoding="utf-8")
        
        # When we re-run, determinism must fail and report gates must roll back to FAIL
        det2 = verify_determinism_and_finalize_l1b(run1_dir, run2_dir)
        assert det2["status"] == "FAIL"
        
        # Read run1 report json and verify implementation_acceptance became FAIL
        updated_rpt = json.loads((run1_dir / "LOCAL_NATIVE_L1B_REPORT.json").read_text(encoding="utf-8"))
        assert updated_rpt["acceptance_gates"]["deterministic_reports"] == "FAIL"
        assert updated_rpt["acceptance_gates"]["implementation_acceptance"] == "FAIL"

