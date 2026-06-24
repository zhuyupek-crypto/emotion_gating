import importlib
import os
import sys
import time


ROOT = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.join(ROOT, "rebuild_from_archive")
OUT = os.path.join(ROOT, "rebuild_2020_to_0904_v16_probe")
STRATEGY = os.path.join(ROOT, "母版-20260506-Clone.py")

sys.path.insert(0, WORK)
sys.path.insert(1, ROOT)
sys.path.insert(2, r"D:\work space\hdata")
sys.modules["jqdata"] = importlib.import_module("jqdata_compat")

from scripts.core import hdata_reader
from engine.core import Engine
from project_compat import EmotionGateJQCompat


def main():
    os.makedirs(OUT, exist_ok=True)
    with open(STRATEGY, "r", encoding="utf-8") as f:
        strategy_code = f.read()

    print("Preloading hdata pivot cache for 2018-2020...", flush=True)
    hdata_reader._update_pivot_cache({2018, 2019, 2020})
    print("Preload finished.", flush=True)

    start = time.time()
    engine = Engine(strategy_code, "2020-01-01", "2020-09-04", 1000000, compat=EmotionGateJQCompat(ROOT))
    equity, trades, logs, metrics = engine.run()
    elapsed = time.time() - start

    equity.to_csv(os.path.join(OUT, "local_equity_2020_to_0904.csv"), index=False)
    trades.to_csv(os.path.join(OUT, "local_trades_2020_to_0904.csv"), index=False)
    with open(os.path.join(OUT, "local_run_2020_to_0904.log"), "w", encoding="utf-8") as f:
        for line in logs:
            f.write(line + "\n")

    print(f"Completed in {elapsed:.2f}s", flush=True)
    print(f"Final portfolio value: {equity['value'].iloc[-1]:.2f}", flush=True)
    print(f"Total trades executed: {len(trades)}", flush=True)
    print(f"Metrics: {metrics}", flush=True)
    print(f"Results saved to {OUT}", flush=True)


if __name__ == "__main__":
    main()

