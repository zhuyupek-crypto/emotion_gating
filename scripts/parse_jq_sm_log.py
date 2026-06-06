"""Parse JoinQuant [SM-*] observer logs into CSV files."""

from __future__ import annotations

import argparse
import html
import json
import re
from pathlib import Path

import pandas as pd


STATE_RE = re.compile(r"\[SM-STATE\]\s+({.*})")
CANDS_RE = re.compile(r"\[SM-CANDS\]\s+(\d{8}\s+\d{2}:\d{2}:\d{2})\s+(\w+)\s+n=(\d+)\s+list=(.*)")
CAND_RE = re.compile(
    r"\[SM-CAND\]\s+(\d{8}\s+\d{2}:\d{2}:\d{2})\s+(\w+)\s+stock=(\S+)\s+"
    r"yc=([\d.\-]+)\s+open=([\d.\-]+)\s+(?:hl|high_limit)=([\d.\-]+)\s+"
    r"(?:(?:low_limit)=([\d.\-]+)\s+)?opct=([\d.\-]+)\s+paused=(\S+)\s+held=(\S+)"
)
ACTION_RE = re.compile(r"\[SM-ACTION\]\s+(\d{8}\s+\d{2}:\d{2}:\d{2})\s+(\S+)\s+before=(.*?)\s+after=(.*)")
PFB_RE = re.compile(r"\[SM-PFB\]\s+(\d{8}\s+\d{2}:\d{2}:\d{2})\s+n=(\d+)\s+list=(.*)")


def parse(path: Path) -> dict[str, pd.DataFrame]:
    rows = {"state": [], "cands": [], "cand": [], "action": [], "pfb": []}
    for line in path.read_text(encoding="utf-8-sig", errors="ignore").splitlines():
        m = STATE_RE.search(line)
        if m:
            try:
                rows["state"].append(json.loads(html.unescape(m.group(1))))
            except json.JSONDecodeError:
                pass
            continue
        m = CANDS_RE.search(line)
        if m:
            dt, label, n, codes = m.groups()
            rows["cands"].append({"dt": dt, "label": label, "n": int(n), "codes": codes})
            continue
        m = CAND_RE.search(line)
        if m:
            dt, label, stock, yc, op, hl, ll, opct, paused, held = m.groups()
            rows["cand"].append({
                "dt": dt,
                "label": label,
                "stock": stock,
                "yclose": float(yc),
                "open": float(op),
                "high_limit": float(hl),
                "low_limit": float(ll) if ll is not None else None,
                "open_pct": float(opct),
                "paused": paused == "True",
                "held": held == "True",
            })
            continue
        m = ACTION_RE.search(line)
        if m:
            dt, label, before, after = m.groups()
            rows["action"].append({"dt": dt, "label": label, "before": before, "after": after})
            continue
        m = PFB_RE.search(line)
        if m:
            dt, n, codes = m.groups()
            rows["pfb"].append({"dt": dt, "n": int(n), "codes": codes})
            continue
    return {k: pd.DataFrame(v) for k, v in rows.items()}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("log", type=Path)
    parser.add_argument("--out-prefix", default="jq_sm_2022")
    args = parser.parse_args()

    frames = parse(args.log)
    for name, df in frames.items():
        out = Path(f"{args.out_prefix}_{name}.csv")
        df.to_csv(out, index=False, encoding="utf-8-sig")
        print(f"{name}: {len(df)} -> {out}")


if __name__ == "__main__":
    main()
