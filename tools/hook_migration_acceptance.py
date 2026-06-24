from __future__ import annotations

import argparse
import importlib
import json
import math
import os
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / "rebuild_from_archive"
STRATEGY = ROOT / "母版-20260506-Clone.py"
BASELINE_2020_DIR = ROOT / "rebuild_2020_warm2020_v16"
DEFAULT_OUT_DIR = ROOT / "acceptance_hook_migration_2020"
HDATA_ROOT = Path(r"D:\work space\hdata")
HDATA_SCRIPTS = HDATA_ROOT / "scripts"
FLOAT_TOL = 1e-9


def setup_runtime():
    if str(WORK) not in sys.path:
        sys.path.insert(0, str(WORK))
    if str(HDATA_SCRIPTS) not in sys.path:
        sys.path.insert(1, str(HDATA_SCRIPTS))
    if str(HDATA_ROOT) not in sys.path:
        sys.path.insert(2, str(HDATA_ROOT))
    if str(ROOT) not in sys.path:
        sys.path.insert(3, str(ROOT))
    sys.modules["jqdata"] = importlib.import_module("jqdata_compat")
    from core import hdata_reader
    from rebuild_from_archive.engine.core import Engine
    from rebuild_from_archive.engine.data_api import DataAPI
    from rebuild_from_archive.project_compat import EmotionGateJQCompat

    return hdata_reader, Engine, DataAPI, EmotionGateJQCompat


def _jsonable(value):
    if isinstance(value, (pd.Timestamp, pd.Timedelta)):
        return str(value)
    if isinstance(value, (np.floating, float)):
        if math.isnan(float(value)):
            return "NaN"
        return float(value)
    if isinstance(value, (np.integer, int)):
        return int(value)
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(v) for v in value]
    return value


class CountingCompat:
    def __init__(self, base_cls, project_root=None):
        self._base = base_cls(project_root)
        self._counts = {
            name: {"queries": 0, "hits": 0, "hit_keys": [], "miss_keys": []}
            for name in [
                "minute_price",
                "daily_field",
                "execution_price",
                "order_amount",
                "fill_amount",
                "call_auction",
                "security_metadata",
                "preopen_order",
                "strategy_state",
                "instrument_fallback",
                "tail_seal",
                "history_fastpath",
            ]
        }

    def __getattr__(self, name):
        return getattr(self._base, name)

    def namespace_entries(self, engine):
        entries = self._base.namespace_entries(engine) if hasattr(self._base, 'namespace_entries') else {}
        entries['apply_project_strategy_compat'] = lambda stage, context, state=None: self.apply_strategy_state_override(stage, context, state)
        return entries

    def _record(self, category, key, hit):
        bucket = self._counts[category]
        bucket["queries"] += 1
        target = bucket["hit_keys"] if hit else bucket["miss_keys"]
        if len(target) < 200:
            target.append(_jsonable(key))
        if hit:
            bucket["hits"] += 1

    def get_minute_price_override(self, date_key, time_key, security):
        value = self._base.get_minute_price_override(date_key, time_key, security)
        self._record("minute_price", (date_key, time_key, security), value is not None)
        return value

    def get_daily_field_override(self, security, date_int, field):
        value = self._base.get_daily_field_override(security, date_int, field)
        self._record("daily_field", (security, date_int, field, "field"), value is not None)
        return value

    def get_daily_ipo_close_override(self, security, date_int):
        value = self._base.get_daily_ipo_close_override(security, date_int)
        self._record("daily_field", (security, date_int, "ipo_close"), value is not None)
        return value

    def get_execution_price_override(self, date_key, time_key, security, side):
        value = self._base.get_execution_price_override(date_key, time_key, security, side)
        self._record("execution_price", (date_key, time_key, security, side), value is not None)
        return value

    def get_order_amount_override(self, date_key, time_key, security):
        value = self._base.get_order_amount_override(date_key, time_key, security)
        self._record("order_amount", (date_key, time_key, security), value is not None)
        return value

    def get_fill_amount_override(self, date_key, time_key, security):
        value = self._base.get_fill_amount_override(date_key, time_key, security)
        self._record("fill_amount", (date_key, time_key, security), value is not None)
        return value

    def should_reject_preopen_cash(self, date_key, time_key, available_cash):
        reject, threshold = self._base.should_reject_preopen_cash(date_key, time_key, available_cash)
        self._record("preopen_order", (date_key, time_key, "cash_floor", round(float(available_cash), 6)), reject)
        return reject, threshold

    def should_reject_preopen_order(self, date_key, security):
        reject = self._base.should_reject_preopen_order(date_key, security)
        self._record("preopen_order", (date_key, security, "skip"), reject)
        return reject

    def should_drop_first_preopen_duplicate(self, date_key, security):
        drop = self._base.should_drop_first_preopen_duplicate(date_key, security)
        self._record("preopen_order", (date_key, security, "drop_first_duplicate"), drop)
        return drop

    def apply_strategy_state_override(self, stage, context, state=None):
        value = self._base.apply_strategy_state_override(stage, context, state)
        date_key = getattr(getattr(context, "current_dt", None), "strftime", lambda *_: "")("%Y-%m-%d")
        self._record("strategy_state", (stage, date_key), value is not None)
        return value

    def get_instrument_price_fallback(self, security, start_date=None, end_date=None):
        value = self._base.get_instrument_price_fallback(security, start_date=start_date, end_date=end_date)
        self._record("instrument_fallback", ("price", security, str(start_date), str(end_date)), value is not None)
        return value

    def has_zero_fee_override(self, security):
        value = self._base.has_zero_fee_override(security)
        self._record("instrument_fallback", ("zero_fee", security), value)
        return value

    def get_tail_seal_override(self, date_key, security):
        value = self._base.get_tail_seal_override(date_key, security)
        self._record("tail_seal", (date_key, security), value is not None)
        return value

    def should_bypass_history_fastpath(self, unit, fields, end_dt):
        value = self._base.should_bypass_history_fastpath(unit, fields, end_dt)
        self._record("history_fastpath", (unit, tuple(fields) if isinstance(fields, (list, tuple, set)) else fields, str(end_dt)), value)
        return value

    def get_security_start_date_override(self, security):
        value = self._base.get_security_start_date_override(security)
        self._record("security_metadata", ("start_date", security), value is not None)
        return value

    def apply_call_auction_overrides(self, frame):
        before = None if frame is None else frame.copy()
        out = self._base.apply_call_auction_overrides(frame)
        hit = False
        if before is not None and out is not None:
            try:
                hit = not before.equals(out)
            except Exception:
                hit = len(before) != len(out)
        self._record("call_auction", ("frame", 0 if frame is None else len(frame)), hit)
        return out

    def apply_security_name_overrides(self, api, out, date):
        before = out[["display_name"]].copy() if out is not None and not out.empty and "display_name" in out.columns else None
        result = self._base.apply_security_name_overrides(api, out, date)
        ds = pd.to_datetime(date).strftime("%Y-%m-%d") if date is not None else ""
        if before is not None and result is not None and not result.empty and "display_name" in result.columns:
            for code in set(list(getattr(self._base, "non_st_name_windows", {}).keys()) + ["600856.XSHG", "001270.XSHE"]):
                if code in before.index and code in result.index:
                    if str(before.loc[code, "display_name"]) != str(result.loc[code, "display_name"]):
                        self._record("security_metadata", ("display_name", ds, code), True)
        return result

    def adjust_extras_is_st(self, api, security, date, is_st):
        value = self._base.adjust_extras_is_st(api, security, date, is_st)
        self._record("security_metadata", ("is_st", str(date), security, bool(is_st)), value != is_st)
        return value

    def filter_billboard_rows(self, frame):
        out = self._base.filter_billboard_rows(frame)
        hit = frame is not None and out is not None and len(frame) != len(out)
        self._record("security_metadata", ("billboard", 0 if frame is None else len(frame)), hit)
        return out

    def counts_summary(self):
        summary = {}
        for key, value in self._counts.items():
            summary[key] = {
                "queries": value["queries"],
                "hits": value["hits"],
                "hit_keys": value["hit_keys"],
                "miss_key_examples": value["miss_keys"][:20],
            }
        return summary


def _save_engine_outputs(out_dir: Path, engine, equity, trades, logs, metrics, year: int, warm_start_year: int):
    out_dir.mkdir(parents=True, exist_ok=True)
    trades_year = trades[trades["time"].astype(str).str.startswith(str(year))].copy() if not trades.empty else trades
    equity_year = equity[equity["date"].astype(str).str.startswith(str(year))].copy() if not equity.empty else equity
    equity.to_csv(out_dir / f"local_equity_{warm_start_year}_to_{year}.csv", index=False)
    trades.to_csv(out_dir / f"local_trades_{warm_start_year}_to_{year}.csv", index=False)
    equity_year.to_csv(out_dir / f"local_equity_{year}.csv", index=False)
    trades_year.to_csv(out_dir / f"local_trades_{year}.csv", index=False)
    if getattr(engine, "daily_portfolio_stats", None):
        stats = pd.DataFrame(engine.daily_portfolio_stats)
        stats.to_csv(out_dir / f"local_portfolio_stats_{warm_start_year}_to_{year}.csv", index=False)
        stats[stats["date"].astype(str).str.startswith(str(year))].copy().to_csv(out_dir / f"local_portfolio_stats_{year}.csv", index=False)
    if getattr(engine, "daily_state_snapshots", None):
        states = pd.DataFrame(engine.daily_state_snapshots)
        states.to_csv(out_dir / f"local_state_{warm_start_year}_to_{year}.csv", index=False)
        states[states["date"].astype(str).str.startswith(str(year))].copy().to_csv(out_dir / f"local_state_{year}.csv", index=False)
    if getattr(engine, "profile_daily", None):
        pd.DataFrame(engine.profile_daily).to_csv(out_dir / f"local_profile_{warm_start_year}_to_{year}.csv", index=False)
    if getattr(engine, "profile_handlers", None):
        pd.DataFrame(engine.profile_handlers).to_csv(out_dir / f"local_profile_handlers_{warm_start_year}_to_{year}.csv", index=False)
    with (out_dir / f"local_run_{warm_start_year}_to_{year}.log").open("w", encoding="utf-8") as f:
        for line in logs:
            f.write(line + "\n")
    summary = {
        "elapsed_seconds": None,
        "final_portfolio_value": float(equity["value"].iloc[-1]) if not equity.empty else None,
        "total_trades_all": int(len(trades)),
        "total_trades_year": int(len(trades_year)),
        "metrics": _jsonable(metrics),
    }
    return summary


def run_2020(args):
    hdata_reader, Engine, DataAPI, EmotionGateJQCompat = setup_runtime()
    out_dir = Path(args.out_dir)
    with STRATEGY.open("r", encoding="utf-8") as f:
        strategy_code = f.read()
    preload_years = set(range(2018, 2021))
    hdata_reader._update_pivot_cache(preload_years)
    compat = CountingCompat(EmotionGateJQCompat, ROOT)
    started = time.time()
    engine = Engine(strategy_code, "2020-01-01", "2020-12-31", 1000000, compat=compat)
    equity, trades, logs, metrics = engine.run()
    elapsed = time.time() - started
    summary = _save_engine_outputs(out_dir, engine, equity, trades, logs, metrics, 2020, 2020)
    summary["elapsed_seconds"] = elapsed
    summary["suspected_unused_runtime_modules"] = sorted([m for m in sys.modules if "suspected_unused" in m])
    (out_dir / "run_summary.json").write_text(json.dumps(_jsonable(summary), ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "hook_counts_2020.json").write_text(json.dumps(_jsonable(compat.counts_summary()), ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def _norm_time(value: str) -> str:
    value = str(value or "").strip().replace(" every_bar", " 09:30:00").replace(" 9:", " 09:")
    if len(value) == 16:
        value += ":00"
    return value


def _float_equal(a, b, tol=FLOAT_TOL):
    if pd.isna(a) and pd.isna(b):
        return True
    if pd.isna(a) or pd.isna(b):
        return False
    return abs(float(a) - float(b)) <= tol


def _compare_scalar_frames(left: pd.DataFrame, right: pd.DataFrame, key_cols, field_specs):
    merged = left.merge(right, on=key_cols, how="outer", suffixes=("_baseline", "_current"), indicator=True)
    rows = []
    for rec in merged.to_dict("records"):
        if rec["_merge"] != "both":
            rows.append({k: rec.get(k) for k in key_cols} | {"field": "__row__", "baseline": rec["_merge"] == "left_only", "current": rec["_merge"] == "right_only", "reason": rec["_merge"]})
            continue
        for field, kind in field_specs.items():
            a = rec.get(f"{field}_baseline")
            b = rec.get(f"{field}_current")
            same = False
            if kind == "float":
                same = _float_equal(a, b)
            else:
                same = (str(a) == str(b)) or (pd.isna(a) and pd.isna(b))
            if not same:
                rows.append({k: rec.get(k) for k in key_cols} | {"field": field, "baseline": a, "current": b, "reason": "value_diff"})
    return pd.DataFrame(rows)


def _load_trades(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, encoding="utf-8-sig")
    df = df.copy()
    df["time"] = df["time"].map(_norm_time)
    df["trade_date"] = df["time"].str[:10]
    df["action"] = np.where(df["amount"].astype(float) > 0, "buy", "sell")
    df["abs_amount"] = df["amount"].astype(float).abs().astype(int)
    return df


def _reconstruct_positions(trades: pd.DataFrame, dates: list[str]) -> pd.DataFrame:
    pos = defaultdict(int)
    by_day = defaultdict(list)
    for row in trades.sort_values(["time", "code", "order_id", "trade_id"], na_position="last").to_dict("records"):
        by_day[row["trade_date"]].append(row)
    rows = []
    for date in sorted(dates):
        for row in by_day.get(date, []):
            pos[row["code"]] += int(float(row["amount"]))
            if pos[row["code"]] == 0:
                del pos[row["code"]]
        items = sorted((code, qty) for code, qty in pos.items() if qty != 0)
        rows.append({
            "date": date,
            "positions_qty": ",".join(f"{code}:{qty}" for code, qty in items),
        })
    return pd.DataFrame(rows)


def analyze_2020(args):
    out_dir = Path(args.out_dir)
    baseline_dir = Path(args.baseline_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    current_trades = _load_trades(out_dir / "local_trades_2020.csv")
    baseline_trades = _load_trades(baseline_dir / "local_trades_2020.csv")
    trade_fields = {
        "trade_date": "str",
        "time": "str",
        "code": "str",
        "action": "str",
        "price": "float",
        "abs_amount": "float",
        "commission": "float",
        "tax": "float",
    }
    trade_diffs = _compare_scalar_frames(
        baseline_trades.reset_index().rename(columns={"index": "seq"}),
        current_trades.reset_index().rename(columns={"index": "seq"}),
        ["seq"],
        trade_fields,
    )
    trade_diffs.to_csv(out_dir / "diff_trades_vs_baseline_2020.csv", index=False, encoding="utf-8-sig")

    baseline_state = pd.read_csv(baseline_dir / "local_state_2020.csv", encoding="utf-8-sig")
    current_state = pd.read_csv(out_dir / "local_state_2020.csv", encoding="utf-8-sig")
    state_fields = {
        "market_mode": "str",
        "raw_market_mode": "str",
        "FB": "float",
        "fb_pct": "float",
        "bull_cooldown": "float",
        "stoploss_cooldown": "float",
        "rzq_cooldown": "float",
        "v227_shock_cooldown": "float",
        "available_cash": "float",
        "locked_cash": "float",
        "owners": "str",
    }
    state_diffs = _compare_scalar_frames(baseline_state, current_state, ["date"], state_fields)
    state_diffs.to_csv(out_dir / "diff_state_vs_baseline_2020.csv", index=False, encoding="utf-8-sig")

    baseline_equity = pd.read_csv(baseline_dir / "local_equity_2020.csv", encoding="utf-8-sig")
    current_equity = pd.read_csv(out_dir / "local_equity_2020.csv", encoding="utf-8-sig")
    equity_diffs = _compare_scalar_frames(baseline_equity, current_equity, ["date"], {"value": "float"})
    equity_diffs.to_csv(out_dir / "diff_equity_vs_baseline_2020.csv", index=False, encoding="utf-8-sig")

    baseline_stats = pd.read_csv(baseline_dir / "local_portfolio_stats_2020.csv", encoding="utf-8-sig")
    current_stats = pd.read_csv(out_dir / "local_portfolio_stats_2020.csv", encoding="utf-8-sig")
    stats_diffs = _compare_scalar_frames(
        baseline_stats,
        current_stats,
        ["date"],
        {"available_cash": "float", "frozen_cash": "float", "positions_value": "float", "total_value": "float"},
    )
    stats_diffs.to_csv(out_dir / "diff_portfolio_stats_vs_baseline_2020.csv", index=False, encoding="utf-8-sig")

    all_dates = sorted(set(baseline_state["date"].astype(str)) | set(current_state["date"].astype(str)))
    baseline_positions = _reconstruct_positions(baseline_trades, all_dates)
    current_positions = _reconstruct_positions(current_trades, all_dates)
    position_diffs = _compare_scalar_frames(baseline_positions, current_positions, ["date"], {"positions_qty": "str"})
    position_diffs.to_csv(out_dir / "diff_positions_vs_baseline_2020.csv", index=False, encoding="utf-8-sig")

    mother_compare = subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools" / "compare_actual_year_mother_log.py"),
            "2020",
            str(out_dir),
            "--mother-log",
            str(ROOT / "母版2020-2026日志" / "log.txt"),
            "--local-log",
            str(out_dir / "local_run_2020_to_2020.log"),
            "--drop-unmatched-sells",
            "--out",
            str(out_dir / "compare_actual_2020_mother_log_from_local_log.csv"),
        ],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    (out_dir / "compare_actual_2020_mother_log_from_local_log.stdout.txt").write_text(mother_compare.stdout + "\nSTDERR\n" + mother_compare.stderr, encoding="utf-8")

    real_compare = subprocess.run(
        [sys.executable, str(ROOT / "compare_real_trades_2020.py"), str(out_dir / "local_trades_2020.csv")],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    (out_dir / "compare_real_trades_2020.stdout.txt").write_text(real_compare.stdout + "\nSTDERR\n" + real_compare.stderr, encoding="utf-8")

    state_vs_jq = subprocess.run(
        [
            sys.executable,
            str(ROOT / "compare_state_snapshots.py"),
            str(out_dir / "local_state_2020.csv"),
            "--start",
            "2020-01-02",
            "--end",
            "2020-12-31",
            "--out",
            str(out_dir / "compare_state_2020_vs_mother.csv"),
        ],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    (out_dir / "compare_state_2020_vs_mother.stdout.txt").write_text(state_vs_jq.stdout + "\nSTDERR\n" + state_vs_jq.stderr, encoding="utf-8")

    summary = {
        "trade_rows_baseline": int(len(baseline_trades)),
        "trade_rows_current": int(len(current_trades)),
        "trade_diff_rows": int(len(trade_diffs)),
        "state_diff_rows": int(len(state_diffs)),
        "equity_diff_rows": int(len(equity_diffs)),
        "portfolio_diff_rows": int(len(stats_diffs)),
        "position_diff_rows": int(len(position_diffs)),
        "baseline_final_value": float(baseline_equity["value"].iloc[-1]),
        "current_final_value": float(current_equity["value"].iloc[-1]),
        "final_value_diff": float(current_equity["value"].iloc[-1] - baseline_equity["value"].iloc[-1]),
        "mother_compare_stdout": mother_compare.stdout.strip().splitlines(),
        "real_compare_stdout": real_compare.stdout.strip().splitlines(),
        "state_vs_mother_stdout": state_vs_jq.stdout.strip().splitlines(),
    }
    (out_dir / "analysis_summary_2020.json").write_text(json.dumps(_jsonable(summary), ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def targeted_checks(args):
    hdata_reader, Engine, DataAPI, EmotionGateJQCompat = setup_runtime()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    compat = CountingCompat(EmotionGateJQCompat, ROOT)
    api = DataAPI(str(HDATA_ROOT), compat=compat)
    results = []

    def add_result(name, passed, details):
        results.append({"name": name, "passed": bool(passed), "details": _jsonable(details)})

    ipo_cases = [
        {"code": "605399.XSHG", "start_date": "2020-08-03", "trade_date": 20200804, "close": 13.16},
        {"code": "605123.XSHG", "start_date": "2020-08-21", "trade_date": 20200825, "close": 30.33},
        {"code": "605255.XSHG", "start_date": "2020-08-21", "trade_date": 20200825, "close": 12.66},
        {"code": "605369.XSHG", "start_date": "2020-09-14", "trade_date": 20200916, "close": 31.65},
    ]
    ipo_details = []
    ipo_pass = True
    for case in ipo_cases:
        start_dt = pd.Timestamp(case["start_date"])
        prev_dt = start_dt - pd.Timedelta(days=1)
        prev_secs = api.get_all_securities(["stock"], date=prev_dt)
        start_secs = api.get_all_securities(["stock"], date=start_dt)
        start_override = compat.get_security_start_date_override(case["code"])
        close_override = compat.get_daily_ipo_close_override(case["code"], case["trade_date"])
        row_ok = (
            case["code"] not in prev_secs.index
            and case["code"] in start_secs.index
            and str(start_secs.loc[case["code"], "start_date"]) == start_dt.date().isoformat()
            and pd.Timestamp(start_override) == start_dt
            and _float_equal(close_override, case["close"])
        )
        ipo_pass = ipo_pass and row_ok
        ipo_details.append({
            "code": case["code"],
            "previous_day_present": bool(case["code"] in prev_secs.index),
            "start_day_present": bool(case["code"] in start_secs.index),
            "start_date": str(start_secs.loc[case["code"], "start_date"]) if case["code"] in start_secs.index else None,
            "start_override": str(start_override),
            "trade_date": case["trade_date"],
            "close_override": close_override,
            "expected_close": case["close"],
            "passed": bool(row_ok),
        })
    add_result("2020_ipo_close_overrides", ipo_pass, {"rows": ipo_details})

    tail = api.get_batch_sealing_points(["000420.XSHE"], "2021-11-15").get("000420.XSHE")
    add_result("2021_tail_seal", str(tail) == "2021-11-15 14:00:00", {"tail": str(tail), "tail_hits": compat.counts_summary()["tail_seal"]})

    secs_2021 = api.get_all_securities(["stock"], date="2021-04-21")
    name_600702 = secs_2021.loc["600702.XSHG", "display_name"] if "600702.XSHG" in secs_2021.index else None
    add_result("2021_st_name_window", name_600702 is not None and "ST" not in str(name_600702), {"display_name": name_600702})

    dup = compat.should_drop_first_preopen_duplicate("2021-12-01", "600072.XSHG")
    add_result("2021_preopen_duplicate", dup is True, {"value": dup})

    state = SimpleNamespace(v227_shock_cooldown=0)
    context = SimpleNamespace(current_dt=pd.Timestamp("2023-02-17 09:30:00"))
    override = compat.apply_strategy_state_override("after_v227_shock", context, state)
    add_result("2023_v227_shock", override == 1 and state.v227_shock_cooldown == 1, {"override": override, "state": state.v227_shock_cooldown})

    df_511880 = api.get_price("511880.XSHG", end_date="2024-01-02", frequency="daily", fields=["close"], count=1)
    price_511880 = float(df_511880["close"].iloc[-1]) if not df_511880.empty else None
    zero_fee = compat.has_zero_fee_override("511880.XSHG")
    add_result("2024_511880_fallback", _float_equal(price_511880, 100.094) and zero_fee, {"price": price_511880, "zero_fee": zero_fee})

    june3 = api._st_codes_on("2024-06-03")
    may6 = api._st_codes_on("2024-05-06")
    candidate = next(iter(sorted(june3 - may6))) if june3 - may6 else None
    if candidate is not None:
        is_st_shifted = api.get_extras("is_st", candidate, start_date="2024-05-06", end_date="2024-05-06")[candidate][0]
        add_result("2024_st_rule", bool(is_st_shifted) is True, {"candidate": candidate, "is_st": bool(is_st_shifted)})
    else:
        add_result("2024_st_rule", False, {"candidate": None, "reason": "no candidate found"})

    reject_2025, threshold_2025 = compat.should_reject_preopen_cash("2025-03-19", "09:28", 19999.99)
    add_result("2025_preopen_cash_floor", reject_2025 is True and _float_equal(threshold_2025, 20000.0), {"reject": reject_2025, "threshold": threshold_2025})

    bypass_2026 = compat.should_bypass_history_fastpath("1d", ["high", "high_limit"], pd.Timestamp("2026-05-27"))
    df_2026 = api.get_price("002185.XSHE", end_date="2026-05-27", frequency="daily", fields=["high", "high_limit"], count=1)
    high_2026 = float(df_2026["high"].iloc[-1]) if not df_2026.empty else None
    high_limit_2026 = float(df_2026["high_limit"].iloc[-1]) if not df_2026.empty else None
    add_result("2026_corrupted_daily_fastpath", bypass_2026 and _float_equal(high_2026, 20.540000915527344) and _float_equal(high_limit_2026, 20.540000915527344), {"bypass": bypass_2026, "high": high_2026, "high_limit": high_limit_2026})

    main_path_scan = subprocess.run(
        [
            "rg",
            "-n",
            "suspected_unused",
            "rebuild_from_archive/engine",
            "rebuild_from_archive/project_compat.py",
            "rebuild_from_archive/project_preprocess.py",
            "母版-20260506-Clone.py",
        ],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    add_result("suspected_unused_static_main_path", main_path_scan.returncode == 1, {"stdout": main_path_scan.stdout.strip().splitlines()})

    legacy_inventory = [
        {
            "artifact": "rebuild_from_archive/suspected_unused/data_api_legacy.py",
            "years": [2020, 2024],
            "categories": ["security_metadata.start_date_overrides", "instrument_fallback.price_fallback", "security_metadata.adjust_extras_is_st"],
            "status": "2020 start_date path proven not required by runtime main path; 2024 fallback/ST logic retained until 2024 targeted checks complete",
        },
        {
            "artifact": "rebuild_from_archive/suspected_unused/core_diff_rebased.patch",
            "years": [2020, 2021, 2024],
            "categories": ["platform_execution.cash_freeze", "platform_execution.fill_and_fee", "instrument_fallback.zero_fee"],
            "status": "text archive only; no runtime import; retain until multi-year execution validation fully closes",
        },
        {
            "artifact": "rebuild_from_archive/suspected_unused/core_diff_rebased_git.patch",
            "years": [2020, 2021, 2024],
            "categories": ["platform_execution.cash_freeze", "platform_execution.fill_and_fee", "instrument_fallback.zero_fee"],
            "status": "text archive only; no runtime import; retain until multi-year execution validation fully closes",
        },
    ]

    report = {
        "results": results,
        "hook_counts_after_targeted": compat.counts_summary(),
        "legacy_inventory": legacy_inventory,
    }
    (out_dir / "targeted_checks_report.json").write_text(json.dumps(_jsonable(report), ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(_jsonable(report), ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_run = sub.add_parser("run-2020")
    p_run.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    p_run.set_defaults(func=run_2020)

    p_an = sub.add_parser("analyze-2020")
    p_an.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    p_an.add_argument("--baseline-dir", default=str(BASELINE_2020_DIR))
    p_an.set_defaults(func=analyze_2020)

    p_t = sub.add_parser("targeted")
    p_t.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    p_t.set_defaults(func=targeted_checks)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()


