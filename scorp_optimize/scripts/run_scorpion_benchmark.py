"""Scorpion performance benchmark - runs naked Scorpion strategy for a given year."""
import sys
import os
import json
import time
import importlib
from pathlib import Path

ROOT = Path(r"d:\workspace\他山之石\l2_exec")
WORK = ROOT / "rebuild_from_archive"
HDATA_ROOT = Path(r"D:\work space\hdata")
HDATA_SCRIPTS = HDATA_ROOT / "scripts"
STRATEGY_FILE = ROOT / "scorp_optimize" / "strategies" / "strategy_v227_scorp.py"

for p in [str(WORK), str(HDATA_SCRIPTS), str(HDATA_ROOT), str(ROOT)]:
    if p not in sys.path:
        sys.path.insert(0, p)

sys.modules["jqdata"] = importlib.import_module("jqdata_compat")

from core import hdata_reader
from rebuild_from_archive.engine.core import Engine
from rebuild_from_archive.engine.data_api import DataAPI
from rebuild_from_archive.project_compat import EmotionGateJQCompat
import pandas as pd


def run_benchmark(year, out_dir, profile="local_native_l2"):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    start_date = f"{year}-01-01"
    end_date = f"{year}-12-31"
    compat = EmotionGateJQCompat(profile=profile)
    strategy_code = STRATEGY_FILE.read_text(encoding="utf-8")
    engine = Engine(strategy_code, start_date, end_date,
                    initial_cash=1000000, frequency="daily", compat=compat)
    t0 = time.perf_counter()
    equity, trades, logs, metrics = engine.run()
    t1 = time.perf_counter()
    elapsed = round(t1 - t0, 3)
    trades.to_csv(out_dir / "TRADES.csv", index=False)
    equity.to_csv(out_dir / "EQUITY.csv", index=False)
    state_rows = [s for s in getattr(engine, "daily_state_snapshots", []) if isinstance(s, dict)]
    state_df = pd.DataFrame(state_rows) if state_rows else pd.DataFrame()
    state_df.to_csv(out_dir / "STATE.csv", index=False)
    eq = equity.copy()
    if not eq.empty and "value" in eq.columns:
        eq_vals = eq["value"].astype(float).values
        peak = eq_vals[0]
        max_dd = 0.0
        for v in eq_vals:
            if v > peak:
                peak = v
            dd = (peak - v) / peak if peak > 0 else 0
            if dd > max_dd:
                max_dd = dd
        max_dd_pct = round(max_dd * 100, 4)
    else:
        max_dd_pct = 0.0
    final_val = float(equity["value"].iloc[-1]) if not equity.empty else 0
    total_ret = (final_val / 1000000 - 1) * 100
    benchmark = {
        "test_year": year,
        "start_date": start_date,
        "end_date": end_date,
        "strategy_file": str(STRATEGY_FILE),
        "profile": profile,
        "initial_cash": 1000000,
        "start_time": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(t0)),
        "end_time": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(t1)),
        "elapsed_seconds": elapsed,
        "trade_count": len(trades) if trades is not None else 0,
        "final_value": round(final_val, 6),
        "total_return_pct": round(total_ret, 6),
        "max_drawdown_pct": max_dd_pct,
    }
    (out_dir / "benchmark.json").write_text(json.dumps(benchmark, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(benchmark, indent=2, ensure_ascii=False))
    return benchmark


if __name__ == "__main__":
    year = int(sys.argv[1]) if len(sys.argv) > 1 else 2025
    out = sys.argv[2] if len(sys.argv) > 2 else f"benchmark_{year}"
    prof = "local_native_l2"
    for i, arg in enumerate(sys.argv):
        if arg == "--profile" and i + 1 < len(sys.argv):
            prof = sys.argv[i + 1]
    run_benchmark(year, out, prof)
