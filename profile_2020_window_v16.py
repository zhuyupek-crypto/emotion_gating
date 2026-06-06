import importlib
import os
import sys
import time
import traceback
from collections import defaultdict


ROOT = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.join(ROOT, "rebuild_from_archive")
STRATEGY = os.path.join(ROOT, "母版-20260506-Clone.py")

sys.path.insert(0, WORK)
sys.path.insert(1, ROOT)
sys.path.insert(2, r"D:\work space\hdata")
sys.modules["jqdata"] = importlib.import_module("jqdata_compat")

from scripts.core import hdata_reader
from engine.core import Engine


class TimerStats:
    def __init__(self):
        self.rows = defaultdict(lambda: [0, 0.0])

    def wrap(self, name, func):
        def wrapped(*args, **kwargs):
            start = time.perf_counter()
            try:
                return func(*args, **kwargs)
            finally:
                elapsed = time.perf_counter() - start
                row = self.rows[name]
                row[0] += 1
                row[1] += elapsed
        return wrapped

    def print_top(self, n=40):
        print("PROFILE_TOP")
        for name, (count, total) in sorted(self.rows.items(), key=lambda kv: kv[1][1], reverse=True)[:n]:
            avg = total / count if count else 0.0
            print(f"{name:34s} calls={count:7d} total={total:10.3f}s avg={avg:9.5f}s")


def main():
    start_date = sys.argv[1] if len(sys.argv) > 1 else "2020-01-01"
    end_date = sys.argv[2] if len(sys.argv) > 2 else "2020-02-14"
    with open(STRATEGY, "r", encoding="utf-8") as f:
        strategy_code = f.read()

    preload_years = {2018, 2019, 2020}
    print(f"Preloading hdata pivot cache for {sorted(preload_years)}...", flush=True)
    hdata_reader._update_pivot_cache(preload_years)
    print("Preload finished.", flush=True)

    stats = TimerStats()
    engine = Engine(strategy_code, start_date, end_date, 1000000)

    api = engine.data_api
    for name in [
        "get_price",
        "_history_cached",
        "get_call_auction",
        "_load_call_auction_year",
        "get_batch_sealing_points",
        "_load_minute_data",
        "get_valuation",
        "get_all_securities",
        "get_extras",
        "get_billboard_list",
    ]:
        if hasattr(api, name):
            setattr(api, name, stats.wrap(f"DataAPI.{name}", getattr(api, name)))

    engine.wrapped_get_fundamentals = stats.wrap("Engine.get_fundamentals", engine.wrapped_get_fundamentals)
    engine.wrapped_history = stats.wrap("Engine.history", engine.wrapped_history)
    engine.wrapped_attribute_history = stats.wrap("Engine.attribute_history", engine.wrapped_attribute_history)
    engine._wrapped_get_bars = stats.wrap("Engine.get_bars", engine._wrapped_get_bars)
    engine._get_trade_price = stats.wrap("Engine._get_trade_price", engine._get_trade_price)
    engine._refresh_portfolio_prices = stats.wrap("Engine._refresh_portfolio_prices", engine._refresh_portfolio_prices)
    engine._match_pending_orders = stats.wrap("Engine._match_pending_orders", engine._match_pending_orders)

    # The namespace is built in __init__, so replace function entries after wrapping methods.
    engine.namespace["history"] = engine.wrapped_history
    engine.namespace["attribute_history"] = engine.wrapped_attribute_history
    engine.namespace["get_bars"] = engine._wrapped_get_bars
    engine.namespace["get_fundamentals"] = engine.wrapped_get_fundamentals

    start = time.time()
    equity, trades, logs, metrics = engine.run()
    elapsed = time.time() - start
    print(f"Completed in {elapsed:.2f}s")
    print(f"trades={len(trades)} equity_rows={len(equity)} logs={len(logs)}")
    print(f"metrics={metrics}")
    stats.print_top()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        raise
