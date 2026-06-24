from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
LOCAL_QUANT_ROOT = Path(r"D:\work space\local_quant")
SAMPLE_STRATEGY = LOCAL_QUANT_ROOT / "strategies" / "sample_strategy.py"
OUT_DIR = ROOT / "alignment_reports" / "sample_strategy_alignment"


RUNNER = r"""
import importlib
import json
import os
import sys
import types
from pathlib import Path

import pandas as pd

engine_root = Path(r"{engine_root}")
strategy_path = Path(r"{strategy_path}")
out_path = Path(r"{out_path}")
start_date = "{start_date}"
end_date = "{end_date}"
initial_cash = {initial_cash}

sys.path.insert(0, str(engine_root))
sys.path.insert(1, r"D:\work space\hdata")
scripts_pkg = types.ModuleType("scripts")
scripts_pkg.__path__ = [r"D:\work space\hdata\scripts"]
sys.modules["scripts"] = scripts_pkg
sys.modules["jqdata"] = importlib.import_module("jqdata_compat")

from engine.core import Engine

strategy_code = strategy_path.read_text(encoding="utf-8")
engine = Engine(strategy_code, start_date, end_date, initial_cash)
equity, trades, logs, metrics = engine.run()

out_path.parent.mkdir(parents=True, exist_ok=True)
trades.to_csv(out_path.with_suffix(".trades.csv"), index=False)
equity.to_csv(out_path.with_suffix(".equity.csv"), index=False)
summary = {{
    "label": "{label}",
    "engine_root": str(engine_root),
    "strategy_path": str(strategy_path),
    "start_date": start_date,
    "end_date": end_date,
    "final_value": None if equity.empty else float(equity["value"].iloc[-1]),
    "trade_count": int(len(trades)),
    "metrics": metrics,
}}
out_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(summary, ensure_ascii=False))
"""


def _run(label: str, engine_root: Path, start_date: str, end_date: str, initial_cash: float) -> dict:
    out_path = OUT_DIR / f"{label}_{start_date.replace('-', '')}_{end_date.replace('-', '')}.json"
    code = RUNNER.format(
        label=label,
        engine_root=str(engine_root),
        strategy_path=str(SAMPLE_STRATEGY),
        out_path=str(out_path),
        start_date=start_date,
        end_date=end_date,
        initial_cash=initial_cash,
    )
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env.setdefault("LOCALQUANT_DATA_ROOT", r"D:\work space\hdata\data\processed")
    completed = subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(ROOT),
        env=env,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"{label} failed with exit code {completed.returncode}\n"
            f"STDOUT:\n{completed.stdout}\nSTDERR:\n{completed.stderr}"
        )
    return json.loads(completed.stdout.strip().splitlines()[-1])


def _trade_keys(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    if df.empty:
        return pd.DataFrame(columns=["date", "code", "side", "amount", "price"])
    out = pd.DataFrame()
    out["date"] = pd.to_datetime(df["time"]).dt.strftime("%Y-%m-%d")
    out["code"] = df["code"].astype(str)
    out["side"] = df["amount"].astype(float).map(lambda x: "buy" if x > 0 else "sell")
    out["amount"] = df["amount"].astype(float)
    out["price"] = df["price"].astype(float)
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", default="2024-01-01")
    parser.add_argument("--end", default="2024-03-31")
    parser.add_argument("--initial-cash", type=float, default=1_000_000)
    args = parser.parse_args()

    if not SAMPLE_STRATEGY.exists():
        raise FileNotFoundError(SAMPLE_STRATEGY)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    workspace_engine = ROOT / "rebuild_from_archive"
    local_engine = LOCAL_QUANT_ROOT

    ws = _run("workspace_engine", workspace_engine, args.start, args.end, args.initial_cash)
    lq = _run("local_quant_engine", local_engine, args.start, args.end, args.initial_cash)

    tag = f"{args.start.replace('-', '')}_{args.end.replace('-', '')}"
    ws_trades = _trade_keys(OUT_DIR / f"workspace_engine_{tag}.trades.csv")
    lq_trades = _trade_keys(OUT_DIR / f"local_quant_engine_{tag}.trades.csv")

    key_cols = ["date", "code", "side"]
    merged = ws_trades.merge(lq_trades, on=key_cols, how="outer", indicator=True, suffixes=("_workspace", "_local"))
    unmatched = merged[merged["_merge"] != "both"].copy()
    matched = merged[merged["_merge"] == "both"].copy()
    matched_rate = 1.0 if max(len(ws_trades), len(lq_trades)) == 0 else len(matched) / max(len(ws_trades), len(lq_trades))

    report = {
        "sample_strategy": str(SAMPLE_STRATEGY),
        "workspace_summary": ws,
        "local_quant_summary": lq,
        "trade_count_diff": int(ws["trade_count"] - lq["trade_count"]),
        "final_value_diff": None
        if ws["final_value"] is None or lq["final_value"] is None
        else float(ws["final_value"] - lq["final_value"]),
        "trade_key_match_rate": matched_rate,
        "unmatched_count": int(len(unmatched)),
    }
    report_path = OUT_DIR / f"sample_strategy_alignment_{tag}.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    unmatched.to_csv(OUT_DIR / f"sample_strategy_unmatched_{tag}.csv", index=False)

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
