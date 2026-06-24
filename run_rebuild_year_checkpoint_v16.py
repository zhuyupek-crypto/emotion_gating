import argparse
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
from project_checkpoint import load_engine_checkpoint, save_engine_checkpoint
from project_compat import EmotionGateJQCompat


def run_engine(strategy_code, start_date, end_date, resume_checkpoint=None, progress_interval=50):
    engine = Engine(strategy_code, start_date, end_date, 1000000, compat=EmotionGateJQCompat(ROOT))
    engine.progress_interval = progress_interval
    if resume_checkpoint:
        engine.set_resume_state(load_engine_checkpoint(resume_checkpoint))
    return engine, *engine.run()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--resume-checkpoint", default="")
    parser.add_argument("--save-checkpoint", default="")
    parser.add_argument("--preload-start-year", type=int, default=2018)
    parser.add_argument("--preload-end-year", type=int, default=0)
    parser.add_argument("--progress-interval", type=int, default=50)
    args = parser.parse_args()

    out_dir = os.path.join(ROOT, f"rebuild_{args.tag}_checkpoint_v16")
    os.makedirs(out_dir, exist_ok=True)

    with open(STRATEGY, "r", encoding="utf-8") as f:
        strategy_code = f.read()

    end_year = int(args.end[:4])
    preload_end = args.preload_end_year or end_year
    preload_years = set(range(args.preload_start_year, preload_end + 1))
    print(f"Preloading hdata pivot cache for {sorted(preload_years)}...", flush=True)
    hdata_reader._update_pivot_cache(preload_years)
    print("Preload finished.", flush=True)

    start = time.time()
    engine, equity, trades, logs, metrics = run_engine(
        strategy_code,
        args.start,
        args.end,
        resume_checkpoint=args.resume_checkpoint or None,
        progress_interval=args.progress_interval,
    )
    elapsed = time.time() - start

    tag = args.tag
    equity.to_csv(os.path.join(out_dir, f"local_equity_{tag}.csv"), index=False)
    trades.to_csv(os.path.join(out_dir, f"local_trades_{tag}.csv"), index=False)
    if getattr(engine, "daily_portfolio_stats", None):
        import pandas as pd
        pd.DataFrame(engine.daily_portfolio_stats).to_csv(
            os.path.join(out_dir, f"local_portfolio_stats_{tag}.csv"),
            index=False,
        )
    if getattr(engine, "daily_state_snapshots", None):
        import pandas as pd
        pd.DataFrame(engine.daily_state_snapshots).to_csv(
            os.path.join(out_dir, f"local_state_{tag}.csv"),
            index=False,
        )
    if getattr(engine, "profile_daily", None):
        import pandas as pd
        pd.DataFrame(engine.profile_daily).to_csv(
            os.path.join(out_dir, f"local_profile_{tag}.csv"),
            index=False,
        )
        if getattr(engine, "profile_handlers", None):
            pd.DataFrame(engine.profile_handlers).to_csv(
                os.path.join(out_dir, f"local_profile_handlers_{tag}.csv"),
                index=False,
            )
    with open(os.path.join(out_dir, f"local_run_{tag}.log"), "w", encoding="utf-8") as f:
        for line in logs:
            f.write(line + "\n")

    if args.save_checkpoint:
        save_engine_checkpoint(engine, args.save_checkpoint, args.end)
        print(f"Saved checkpoint: {args.save_checkpoint}", flush=True)

    print(f"Completed in {elapsed:.2f}s", flush=True)
    if equity.empty:
        print("Final portfolio value: EMPTY", flush=True)
    else:
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
