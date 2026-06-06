import importlib
import os
import sys
import time
import traceback


ROOT = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.join(ROOT, "rebuild_from_archive")
STRATEGY = os.path.join(ROOT, "母版-20260506-Clone.py")

sys.path.insert(0, WORK)
sys.path.insert(1, ROOT)
sys.path.insert(2, r"D:\work space\hdata")
sys.modules["jqdata"] = importlib.import_module("jqdata_compat")

from scripts.core import hdata_reader
from engine.core import Engine


def main():
    year = int(sys.argv[1]) if len(sys.argv) > 1 else 2021
    warm_start_year = int(sys.argv[2]) if len(sys.argv) > 2 else 2020
    start_date = f"{warm_start_year}-01-01"
    end_date = f"{year}-12-31"
    out_dir = os.path.join(ROOT, f"rebuild_{year}_warm{warm_start_year}_v16")
    os.makedirs(out_dir, exist_ok=True)

    with open(STRATEGY, "r", encoding="utf-8") as f:
        strategy_code = f.read()

    preload_years = set(range(warm_start_year - 2, year + 1))
    print(f"Preloading hdata pivot cache for {sorted(preload_years)}...", flush=True)
    hdata_reader._update_pivot_cache(preload_years)
    print("Preload finished.", flush=True)

    start = time.time()
    engine = Engine(strategy_code, start_date, end_date, 1000000)
    equity, trades, logs, metrics = engine.run()
    elapsed = time.time() - start

    trades_year = trades[trades["time"].astype(str).str.startswith(str(year))].copy() if not trades.empty else trades
    equity_year = equity[equity["date"].astype(str).str.startswith(str(year))].copy() if not equity.empty else equity

    equity.to_csv(os.path.join(out_dir, f"local_equity_{warm_start_year}_to_{year}.csv"), index=False)
    trades.to_csv(os.path.join(out_dir, f"local_trades_{warm_start_year}_to_{year}.csv"), index=False)
    equity_year.to_csv(os.path.join(out_dir, f"local_equity_{year}.csv"), index=False)
    trades_year.to_csv(os.path.join(out_dir, f"local_trades_{year}.csv"), index=False)
    if getattr(engine, "daily_portfolio_stats", None):
        import pandas as pd
        stats = pd.DataFrame(engine.daily_portfolio_stats)
        stats.to_csv(
            os.path.join(out_dir, f"local_portfolio_stats_{warm_start_year}_to_{year}.csv"),
            index=False,
        )
        stats_year = stats[stats["date"].astype(str).str.startswith(str(year))].copy()
        stats_year.to_csv(
            os.path.join(out_dir, f"local_portfolio_stats_{year}.csv"),
            index=False,
        )
    if getattr(engine, "daily_state_snapshots", None):
        import pandas as pd
        states = pd.DataFrame(engine.daily_state_snapshots)
        states.to_csv(
            os.path.join(out_dir, f"local_state_{warm_start_year}_to_{year}.csv"),
            index=False,
        )
        states_year = states[states["date"].astype(str).str.startswith(str(year))].copy()
        states_year.to_csv(
            os.path.join(out_dir, f"local_state_{year}.csv"),
            index=False,
        )
    if getattr(engine, "profile_daily", None):
        import pandas as pd
        pd.DataFrame(engine.profile_daily).to_csv(
            os.path.join(out_dir, f"local_profile_{warm_start_year}_to_{year}.csv"),
            index=False,
        )
        if getattr(engine, "profile_handlers", None):
            pd.DataFrame(engine.profile_handlers).to_csv(
                os.path.join(out_dir, f"local_profile_handlers_{warm_start_year}_to_{year}.csv"),
                index=False,
            )
    with open(os.path.join(out_dir, f"local_run_{warm_start_year}_to_{year}.log"), "w", encoding="utf-8") as f:
        for line in logs:
            f.write(line + "\n")

    print(f"Completed in {elapsed:.2f}s", flush=True)
    print(f"Final portfolio value: {equity['value'].iloc[-1]:.2f}", flush=True)
    print(f"Total trades executed: {len(trades)} all, {len(trades_year)} in {year}", flush=True)
    print(f"Metrics: {metrics}", flush=True)
    print(f"Results saved to {out_dir}", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        raise
