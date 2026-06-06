from __future__ import annotations

import argparse
import csv
import importlib
import os
import sys
import time
import traceback
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / "rebuild_from_archive"
STRATEGY = ROOT / "母版-20260506-Clone-分支净化回测.py"
OUT_DIR = Path(__file__).resolve().parent / "branch_runs"
STRATEGY_DIR = Path(__file__).resolve().parent / "branch_strategies"

DEFAULT_MODES = [
    "force_v227",
    "force_rzq",
    "force_zb",
    "force_rzq_zb",
    "force_auction",
]


def load_engine():
    sys.path.insert(0, str(WORK))
    sys.path.insert(1, str(ROOT))
    sys.path.insert(2, r"D:\work space\hdata")
    sys.modules["jqdata"] = importlib.import_module("jqdata_compat")

    from scripts.core import hdata_reader  # type: ignore
    from engine.core import Engine  # type: ignore

    return hdata_reader, Engine


def strategy_path_for_mode(mode: str) -> Path:
    path = STRATEGY_DIR / f"mother_branch_{mode}.py"
    if path.exists():
        return path
    if mode == "normal" and STRATEGY.exists():
        return STRATEGY
    raise FileNotFoundError(
        f"Missing strategy copy for mode={mode}: {path}. "
        "Run codex_strategy_dissection\\make_branch_strategy_copies.py first."
    )


def max_drawdown(values: list[float]) -> float:
    peak = None
    worst = 0.0
    for value in values:
        if peak is None or value > peak:
            peak = value
        if peak and peak > 0:
            worst = min(worst, value / peak - 1.0)
    return worst


def summarize_trades(trades) -> dict[str, object]:
    if trades is None or trades.empty:
        return {
            "trade_rows": 0,
            "buy_rows": 0,
            "sell_rows": 0,
            "round_trips": 0,
            "win_rate": "",
            "avg_ret_pct": "",
            "median_ret_pct": "",
            "profit_factor": "",
        }

    buy_rows = trades[trades["amount"] > 0].copy()
    sell_rows = trades[trades["amount"] < 0].copy()
    open_lots: dict[str, list[dict[str, float]]] = {}
    returns: list[float] = []

    for _, row in trades.sort_values("time").iterrows():
        code = str(row["code"])
        amount = float(row["amount"])
        price = float(row["price"])
        commission = float(row.get("commission", 0.0))
        tax = float(row.get("tax", 0.0))
        if amount > 0:
            open_lots.setdefault(code, []).append(
                {
                    "amount": amount,
                    "cost": amount * price + commission + tax,
                }
            )
            continue
        remaining = -amount
        lots = open_lots.get(code, [])
        while remaining > 0 and lots:
            lot = lots[0]
            matched = min(remaining, lot["amount"])
            buy_cost = lot["cost"] * matched / lot["amount"]
            sell_value = matched * price
            sell_fee = (commission + tax) * matched / (-amount)
            ret = (sell_value - sell_fee) / buy_cost - 1.0 if buy_cost > 0 else 0.0
            returns.append(ret)
            lot["amount"] -= matched
            lot["cost"] -= buy_cost
            remaining -= matched
            if lot["amount"] <= 0:
                lots.pop(0)

    if not returns:
        win_rate = avg_ret = median_ret = profit_factor = ""
    else:
        returns_sorted = sorted(returns)
        mid = len(returns_sorted) // 2
        if len(returns_sorted) % 2:
            median = returns_sorted[mid]
        else:
            median = (returns_sorted[mid - 1] + returns_sorted[mid]) / 2
        gains = sum(r for r in returns if r > 0)
        losses = -sum(r for r in returns if r < 0)
        win_rate = sum(1 for r in returns if r > 0) / len(returns)
        avg_ret = sum(returns) / len(returns)
        median_ret = median
        profit_factor = gains / losses if losses > 0 else ""

    return {
        "trade_rows": len(trades),
        "buy_rows": len(buy_rows),
        "sell_rows": len(sell_rows),
        "round_trips": len(returns),
        "win_rate": win_rate,
        "avg_ret_pct": avg_ret * 100 if returns else "",
        "median_ret_pct": median_ret * 100 if returns else "",
        "profit_factor": profit_factor,
    }


def run_mode(mode: str, start_date: str, end_date: str, initial_cash: float) -> dict[str, object]:
    hdata_reader, Engine = load_engine()

    strategy_path = strategy_path_for_mode(mode)
    strategy_code = strategy_path.read_text(encoding="utf-8")

    start_year = int(start_date[:4])
    end_year = int(end_date[:4])
    preload_years = set(range(start_year - 2, end_year + 1))
    print(f"[{mode}] preloading hdata years {sorted(preload_years)}", flush=True)
    hdata_reader._update_pivot_cache(preload_years)

    started = time.time()
    engine = Engine(strategy_code, start_date, end_date, initial_cash)
    equity, trades, logs, metrics = engine.run()
    elapsed = time.time() - started

    tag = f"{mode}_{start_date.replace('-', '')}_{end_date.replace('-', '')}"
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    equity_path = OUT_DIR / f"local_equity_{tag}.csv"
    trades_path = OUT_DIR / f"local_trades_{tag}.csv"
    log_path = OUT_DIR / f"local_run_{tag}.log"

    equity.to_csv(equity_path, index=False)
    trades.to_csv(trades_path, index=False)
    log_path.write_text("\n".join(logs) + ("\n" if logs else ""), encoding="utf-8")

    values = [float(v) for v in equity["value"].tolist()] if not equity.empty else []
    final_value = values[-1] if values else initial_cash
    trade_stats = summarize_trades(trades)

    row = {
        "mode": mode,
        "start_date": start_date,
        "end_date": end_date,
        "initial_cash": initial_cash,
        "final_value": final_value,
        "total_return_pct": (final_value / initial_cash - 1.0) * 100,
        "max_drawdown_pct": max_drawdown(values) * 100 if values else "",
        "elapsed_sec": round(elapsed, 2),
        "metrics": repr(metrics),
        "strategy_path": str(strategy_path),
        "equity_path": str(equity_path),
        "trades_path": str(trades_path),
        "log_path": str(log_path),
    }
    row.update(trade_stats)
    print(
        f"[{mode}] final={final_value:.2f} return={row['total_return_pct']:.2f}% "
        f"round_trips={row['round_trips']} elapsed={elapsed:.2f}s",
        flush=True,
    )
    return row


def write_summary(rows: list[dict[str, object]]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / "naked_branch_summary.csv"
    fields = [
        "mode",
        "start_date",
        "end_date",
        "initial_cash",
        "final_value",
        "total_return_pct",
        "max_drawdown_pct",
        "trade_rows",
        "buy_rows",
        "sell_rows",
        "round_trips",
        "win_rate",
        "avg_ret_pct",
        "median_ret_pct",
        "profit_factor",
        "elapsed_sec",
        "metrics",
        "strategy_path",
        "equity_path",
        "trades_path",
        "log_path",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    print(f"summary={path}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", default="2020-01-01")
    parser.add_argument("--end", default="2020-12-31")
    parser.add_argument("--initial-cash", type=float, default=1_000_000)
    parser.add_argument("--modes", nargs="+", default=DEFAULT_MODES)
    args = parser.parse_args()

    rows = []
    for mode in args.modes:
        rows.append(run_mode(mode, args.start, args.end, args.initial_cash))
        write_summary(rows)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        raise
