"""
Generate JoinQuant Research CHECKS for v227 sell-price verification.

Input:  trades_v227_yjj_probe.csv from scripts/v227_yjj_probe.py
Output: jq_price_checks.txt containing chunks that can be pasted into
        scripts/jq_v227_price_probe_short.py.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
TRADES = ROOT / "trades_v227_yjj_probe.csv"
OUT = ROOT / "jq_price_checks.txt"
CHUNK_SIZE = 20


def main() -> None:
    tr = pd.read_csv(TRADES, dtype={"date": str, "entry_date": str})
    sells = tr[tr["side"] == "sell"].copy()
    rows = []
    for _, r in sells.iterrows():
        day = pd.to_datetime(r["date"]).strftime("%Y-%m-%d")
        rows.append((r["code"], day, float(r["entry"])))

    lines = []
    for i in range(0, len(rows), CHUNK_SIZE):
        chunk = rows[i:i + CHUNK_SIZE]
        lines.append(f"# chunk {i // CHUNK_SIZE + 1}: {len(chunk)} checks")
        lines.append("CHECKS = [")
        for code, day, entry in chunk:
            lines.append(f'    ("{code}", "{day}", {entry:.3f}),')
        lines.append("]\n")

    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {OUT} ({len(rows)} checks, {max(1, (len(rows)+CHUNK_SIZE-1)//CHUNK_SIZE)} chunks)")


if __name__ == "__main__":
    main()
