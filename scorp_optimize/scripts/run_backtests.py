import os
import sys
import time
import importlib
import traceback
import gc

ROOT = r"D:\Work Space\他山之石\情绪门控"
WORK = os.path.join(ROOT, "rebuild_from_archive")

sys.path.insert(0, WORK)
sys.path.insert(1, ROOT)
sys.path.insert(2, r"D:\work space\hdata")
sys.modules["jqdata"] = importlib.import_module("jqdata_compat")

from scripts.core import hdata_reader
from engine.core import Engine

# Define runs
STRATEGIES = {
    "rzq_original": os.path.join(ROOT, "bare_runs_analysis", "strategies", "strategy_rzq_original.py"),
}

YEARS = [2020, 2021, 2022, 2023, 2024, 2025, 2026]

def main():
    out_base = os.path.join(ROOT, "bare_runs_analysis", "runs")
    os.makedirs(out_base, exist_ok=True)
    
    total_tasks = len(STRATEGIES) * len(YEARS)
    completed_tasks = 0
    
    for name, path in STRATEGIES.items():
        print(f"\n=================== Strategy: {name} ===================", flush=True)
        strategy_dir = os.path.join(out_base, name)
        os.makedirs(strategy_dir, exist_ok=True)
        
        with open(path, "r", encoding="utf-8") as f:
            strategy_code = f.read()
            
        for year in YEARS:
            start_date = f"{year}-01-01"
            end_date = f"{year}-12-31" if year < 2026 else "2026-06-06"
            
            equity_path = os.path.join(strategy_dir, f"{year}_equity.csv")
            trades_path = os.path.join(strategy_dir, f"{year}_trades.csv")
            log_path = os.path.join(strategy_dir, f"{year}_run.log")
            
            # Check if outputs already exist (skip if completed)
            if os.path.exists(equity_path) and os.path.exists(trades_path) and os.path.exists(log_path):
                if os.path.getsize(equity_path) > 0 and os.path.getsize(trades_path) > 0:
                    print(f"[{name} - {year}] Already completed, skipping.", flush=True)
                    completed_tasks += 1
                    continue
            
            # Clear cache and run GC to keep memory usage minimal
            hdata_reader.clear_cache()
            gc.collect()
            
            print(f"[{name} - {year}] Running {year} ({start_date} to {end_date})...", flush=True)
            
            # Preload only the required years for this single task
            preload_years = {year - 2, year - 1, year}
            hdata_reader._update_pivot_cache(preload_years)
            
            start = time.time()
            try:
                engine = Engine(strategy_code, start_date, end_date, 1000000)
                equity, trades, logs, metrics = engine.run()
                elapsed = time.time() - start
                
                # Save outputs
                equity.to_csv(equity_path, index=False)
                trades.to_csv(trades_path, index=False)
                with open(log_path, "w", encoding="utf-8") as lf:
                    for line in logs:
                        lf.write(line + "\n")
                
                print(f"[{name} - {year}] Completed in {elapsed:.2f}s | Trades: {len(trades)} | End Val: {equity['value'].iloc[-1]:.1f}", flush=True)
                completed_tasks += 1
            except Exception as e:
                print(f"[{name} - {year}] Failed!", flush=True)
                traceback.print_exc()

    print(f"\n=================== Summary: {completed_tasks}/{total_tasks} backtests finished ===================", flush=True)
    
    # Trigger results analysis automatically
    print("\n=================== All Backtests Finished. Starting Analysis... ===================", flush=True)
    try:
        from bare_runs_analysis import analyze_results
        analyze_results.main()
        print("All processes (backtest + analysis) completed successfully!", flush=True)
    except Exception as e:
        print("Analysis phase failed:", flush=True)
        traceback.print_exc()

if __name__ == "__main__":
    main()
