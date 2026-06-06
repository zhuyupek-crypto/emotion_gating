from __future__ import annotations

from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]


RUNS = [
    ("yjj", "out_v227_hdata"),
    ("pure_v227", "out_v227_full_hdata"),
]


def summarize(prefix: str, year: str) -> dict:
    eq_path = ROOT / f"{prefix}_{year}_equity.csv"
    tr_path = ROOT / f"{prefix}_{year}_trades.csv"
    eq = pd.read_csv(eq_path, dtype={"date": str})
    tr = pd.read_csv(tr_path, dtype={"date": str, "entry_date": str})
    eq["equity"] = eq["equity"].astype(float)
    eq["peak"] = eq["equity"].cummax()
    eq["dd"] = eq["equity"] / eq["peak"] - 1
    sells = tr[tr["side"] == "sell"].copy()
    sells["ret"] = sells["ret"].astype(float)
    return {
        "days": len(eq),
        "trades": len(tr),
        "sells": len(sells),
        "ret": eq["equity"].iloc[-1] / eq["equity"].iloc[0] - 1,
        "mdd": eq["dd"].min(),
        "win": (sells["ret"] > 0).mean() if len(sells) else float("nan"),
        "avg": sells["ret"].mean() if len(sells) else float("nan"),
        "median": sells["ret"].median() if len(sells) else float("nan"),
        "best": sells["ret"].max() if len(sells) else float("nan"),
        "worst": sells["ret"].min() if len(sells) else float("nan"),
    }


def main() -> None:
    rows = []
    for name, prefix in RUNS:
        for year in ["2024", "2025", "2026"]:
            row = {"version": name, "year": year}
            row.update(summarize(prefix, year))
            rows.append(row)
    out = pd.DataFrame(rows)
    pct_cols = ["ret", "mdd", "win", "avg", "median", "best", "worst"]
    printable = out.copy()
    for col in pct_cols:
        printable[col] = printable[col].map(lambda x: f"{x:.2%}")
    print(printable.to_string(index=False))


if __name__ == "__main__":
    main()
