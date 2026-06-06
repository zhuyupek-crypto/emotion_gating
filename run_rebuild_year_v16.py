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
    start_date = f"{year}-01-01"
    end_date = f"{year}-12-31"
    out_dir = os.path.join(ROOT, f"rebuild_{year}_v16")
    os.makedirs(out_dir, exist_ok=True)

    with open(STRATEGY, "r", encoding="utf-8") as f:
        strategy_code = f.read()

    preload_years = {year - 2, year - 1, year}
    print(f"Preloading hdata pivot cache for {sorted(preload_years)}...", flush=True)
    hdata_reader._update_pivot_cache(preload_years)
    print("Preload finished.", flush=True)

    start = time.time()
    engine = Engine(strategy_code, start_date, end_date, 1000000)
    equity, trades, logs, metrics = engine.run()
    elapsed = time.time() - start

    equity.to_csv(os.path.join(out_dir, f"local_equity_{year}.csv"), index=False)
    trades.to_csv(os.path.join(out_dir, f"local_trades_{year}.csv"), index=False)
    with open(os.path.join(out_dir, f"local_run_{year}.log"), "w", encoding="utf-8") as f:
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
