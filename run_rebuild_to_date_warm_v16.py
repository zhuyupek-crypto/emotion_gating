import importlib
import os
import sys
import time
import traceback


ROOT = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.join(ROOT, "rebuild_from_archive")
STRATEGY = os.path.join(ROOT, "母版-20260506-Clone.py")
HDATA_SCRIPTS = r"D:\work space\hdata\scripts"

sys.path.insert(0, WORK)
sys.path.insert(1, HDATA_SCRIPTS)
sys.path.insert(2, r"D:\work space\hdata")
sys.path.insert(3, ROOT)
sys.modules["jqdata"] = importlib.import_module("jqdata_compat")

from core import hdata_reader
from engine.core import Engine
from project_compat import EmotionGateJQCompat


def main():
    end_date = sys.argv[1] if len(sys.argv) > 1 else "2021-05-20"
    warm_start_year = int(sys.argv[2]) if len(sys.argv) > 2 else 2020
    end_year = int(end_date[:4])
    start_date = f"{warm_start_year}-01-01"
    out_dir = os.path.join(ROOT, f"rebuild_warm{warm_start_year}_to_{end_date.replace('-', '')}_v16_probe")
    os.makedirs(out_dir, exist_ok=True)

    with open(STRATEGY, "r", encoding="utf-8") as f:
        strategy_code = f.read()

    preload_years = set(range(warm_start_year - 2, end_year + 1))
    print(f"Preloading hdata pivot cache for {sorted(preload_years)}...", flush=True)
    hdata_reader._update_pivot_cache(preload_years)
    print("Preload finished.", flush=True)

    start = time.time()
    engine = Engine(strategy_code, start_date, end_date, 1000000, compat=EmotionGateJQCompat(ROOT))
    equity, trades, logs, metrics = engine.run()
    elapsed = time.time() - start

    trades.to_csv(os.path.join(out_dir, f"local_trades_{warm_start_year}_to_{end_date.replace('-', '')}.csv"), index=False)
    equity.to_csv(os.path.join(out_dir, f"local_equity_{warm_start_year}_to_{end_date.replace('-', '')}.csv"), index=False)
    if getattr(engine, "daily_portfolio_stats", None):
        import pandas as pd
        pd.DataFrame(engine.daily_portfolio_stats).to_csv(
            os.path.join(out_dir, f"local_portfolio_stats_{warm_start_year}_to_{end_date.replace('-', '')}.csv"),
            index=False,
        )
    if getattr(engine, "daily_state_snapshots", None):
        import pandas as pd
        pd.DataFrame(engine.daily_state_snapshots).to_csv(
            os.path.join(out_dir, f"local_state_{warm_start_year}_to_{end_date.replace('-', '')}.csv"),
            index=False,
        )
    if getattr(engine, "profile_daily", None):
        import pandas as pd
        pd.DataFrame(engine.profile_daily).to_csv(
            os.path.join(out_dir, f"local_profile_{warm_start_year}_to_{end_date.replace('-', '')}.csv"),
            index=False,
        )
        if getattr(engine, "profile_handlers", None):
            pd.DataFrame(engine.profile_handlers).to_csv(
                os.path.join(out_dir, f"local_profile_handlers_{warm_start_year}_to_{end_date.replace('-', '')}.csv"),
                index=False,
            )
    with open(os.path.join(out_dir, f"local_run_{warm_start_year}_to_{end_date.replace('-', '')}.log"), "w", encoding="utf-8") as f:
        for line in logs:
            f.write(line + "\n")

    print(f"Completed in {elapsed:.2f}s", flush=True)
    print(f"Final portfolio value: {equity['value'].iloc[-1]:.2f}", flush=True)
    print(f"Total trades executed: {len(trades)}", flush=True)
    print(f"Metrics: {metrics}", flush=True)
    print(f"Results saved to {out_dir}", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        raise
