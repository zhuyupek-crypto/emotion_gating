import importlib
import os
import sys
import time
import traceback

import pandas as pd


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORK = os.path.join(ROOT, "rebuild_from_archive")
STRATEGY = os.path.join(ROOT, "母版-20260506-Clone.py")
HDATA_SCRIPTS = r"D:\work space\hdata\scripts"
CHECKPOINT = os.path.join(ROOT, "checkpoints", "emotion_gate_20231231_002395execfix.pkl")

sys.path.insert(0, WORK)
sys.path.insert(1, HDATA_SCRIPTS)
sys.path.insert(2, r"D:\work space\hdata")
sys.path.insert(3, ROOT)
sys.modules["jqdata"] = importlib.import_module("jqdata_compat")

from core import hdata_reader
from engine.core import Engine
from project_checkpoint import load_engine_checkpoint
from project_compat import EmotionGateJQCompat


class CounterfactualCompat(EmotionGateJQCompat):
    def filter_billboard_rows(self, frame):
        frame = super().filter_billboard_rows(frame)
        if frame is None or frame.empty or "date" not in frame.columns or "code" not in frame.columns:
            return frame
        date_int = frame["date"].astype(str)
        anomaly = (frame["code"] == "000506.XSHE") & (date_int == "20240410")
        return frame[~anomaly].copy() if anomaly.any() else frame


def main():
    tag = "2024_to0424_counterfactual_no_000506_billboard"
    out_dir = os.path.join(ROOT, f"rebuild_{tag}_checkpoint_v16")
    os.makedirs(out_dir, exist_ok=True)

    with open(STRATEGY, "r", encoding="utf-8") as f:
        strategy_code = f.read()

    print("Preloading hdata pivot cache for 2018-2024...", flush=True)
    hdata_reader._update_pivot_cache(set(range(2018, 2025)))
    print("Preload finished.", flush=True)

    start = time.time()
    engine = Engine(strategy_code, "2024-01-01", "2024-04-24", 1000000, compat=CounterfactualCompat(ROOT))
    engine.progress_interval = 25
    engine.set_resume_state(load_engine_checkpoint(CHECKPOINT))
    equity, trades, logs, metrics = engine.run()
    elapsed = time.time() - start

    trades.to_csv(os.path.join(out_dir, f"local_trades_{tag}.csv"), index=False)
    trades.to_csv(os.path.join(out_dir, "local_trades_2024.csv"), index=False)
    equity.to_csv(os.path.join(out_dir, f"local_equity_{tag}.csv"), index=False)
    if getattr(engine, "daily_state_snapshots", None):
        pd.DataFrame(engine.daily_state_snapshots).to_csv(
            os.path.join(out_dir, f"local_state_{tag}.csv"),
            index=False,
        )
    with open(os.path.join(out_dir, f"local_run_{tag}.log"), "w", encoding="utf-8") as f:
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
