"""Compare JoinQuant DIAG-STATE rows with local v227 state output.

This is the state-machine parity layer. It intentionally compares pre-trade
state before trying to explain final fills or PnL.
"""

from __future__ import annotations

import argparse
import html
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd


STATE_RE = re.compile(r"\[DIAG-STATE\]\s+({.*})")

NUMERIC_FIELDS = [
    "first_board_perf",
    "fb_pct",
    "fb_hist_len",
    "v227_slots",
    "bull_cooldown",
    "bull_consec_loss",
    "bull_sticky",
    "stoploss_cooldown",
    "v227_shock_cooldown",
    "recent_trades_len",
    "recent_trades_win",
]

BOOL_FIELDS = [
    "enable_v227",
    "bull_release_guard",
    "bull_release_confirm_pending",
]

TEXT_FIELDS = [
    "market_mode",
    "raw_market_mode",
    "active",
]

GATE_LEVELS = [0.2, 0.4, 0.6, 0.8]


def parse_jq_state(path: Path) -> pd.DataFrame:
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8-sig", errors="ignore").splitlines():
        m = STATE_RE.search(html.unescape(line))
        if not m:
            continue
        try:
            row = json.loads(m.group(1))
        except json.JSONDecodeError:
            continue
        row["date"] = str(row["date"]).replace("-", "")
        rows.append(row)
    if not rows:
        return pd.DataFrame(columns=["date"])
    return pd.DataFrame(rows).sort_values("date").reset_index(drop=True)


def load_local_state(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, dtype={"date": str})
    return df.sort_values("date").reset_index(drop=True)


def pct_bucket(value: float) -> str:
    if pd.isna(value):
        return "nan"
    if value < 0.2:
        return "<0.2"
    if value < 0.4:
        return "0.2-0.4"
    if value < 0.6:
        return "0.4-0.6"
    if value < 0.8:
        return "0.6-0.8"
    return ">=0.8"


def crossed_gate(jq_value: float, local_value: float) -> bool:
    if pd.isna(jq_value) or pd.isna(local_value):
        return False
    return any((jq_value < gate <= local_value) or (local_value < gate <= jq_value) for gate in GATE_LEVELS)


def add_diff_tags(df: pd.DataFrame) -> pd.DataFrame:
    tags_all: list[str] = []
    for _, row in df.iterrows():
        tags: list[str] = []
        if row.get("_merge") != "both":
            tags.append(str(row.get("_merge")))
            tags_all.append("|".join(tags))
            continue

        jq_fb = row.get("first_board_perf_jq")
        local_fb = row.get("first_board_perf_local")
        if pd.notna(jq_fb) and pd.notna(local_fb) and abs(float(local_fb) - float(jq_fb)) > 0.0005:
            tags.append("FB_PERF_DIFF")

        jq_pct = row.get("fb_pct_jq")
        local_pct = row.get("fb_pct_local")
        if pd.notna(jq_pct) and pd.notna(local_pct):
            if abs(float(local_pct) - float(jq_pct)) > 0.001:
                tags.append("FB_PCT_DIFF")
            if crossed_gate(float(jq_pct), float(local_pct)):
                tags.append("FB_PCT_GATE_DIFF")
            if pct_bucket(float(jq_pct)) != pct_bucket(float(local_pct)):
                tags.append("FB_PCT_BUCKET_DIFF")

        for field in TEXT_FIELDS:
            if row.get(f"{field}_jq") != row.get(f"{field}_local"):
                tags.append(f"{field.upper()}_DIFF")

        for field in BOOL_FIELDS:
            jq_val = row.get(f"{field}_jq")
            local_val = row.get(f"{field}_local")
            if pd.notna(jq_val) and pd.notna(local_val) and bool(jq_val) != bool(local_val):
                tags.append(f"{field.upper()}_DIFF")

        for field in [
            "v227_slots",
            "bull_sticky",
            "bull_cooldown",
            "bull_consec_loss",
            "stoploss_cooldown",
            "v227_shock_cooldown",
            "recent_trades_len",
            "recent_trades_win",
        ]:
            jq_val = row.get(f"{field}_jq")
            local_val = row.get(f"{field}_local")
            if pd.notna(jq_val) and pd.notna(local_val) and int(local_val) != int(jq_val):
                tags.append(f"{field.upper()}_DIFF")

        tags_all.append("|".join(tags))
    out = df.copy()
    out["diff_tags"] = tags_all
    out["has_diff"] = out["diff_tags"].ne("")
    return out


def compare(jq: pd.DataFrame, local: pd.DataFrame) -> pd.DataFrame:
    keep = ["date"] + TEXT_FIELDS + NUMERIC_FIELDS + BOOL_FIELDS
    jq_keep = jq[[c for c in keep if c in jq.columns]].copy()
    local_keep = local[[c for c in keep if c in local.columns]].copy()
    for field in NUMERIC_FIELDS:
        if field in jq_keep:
            jq_keep[field] = pd.to_numeric(jq_keep[field], errors="coerce")
        if field in local_keep:
            local_keep[field] = pd.to_numeric(local_keep[field], errors="coerce")
    merged = jq_keep.merge(local_keep, on="date", how="outer", suffixes=("_jq", "_local"), indicator=True)
    return add_diff_tags(merged.sort_values("date").reset_index(drop=True))


def print_summary(df: pd.DataFrame) -> None:
    both = df[df["_merge"].eq("both")]
    print(f"Compared dates: {len(df)}")
    print(f"Both sides: {len(both)}")
    print(f"Rows with diffs: {int(both['has_diff'].sum())}")
    if not both.empty:
        mode_match = (both["market_mode_jq"] == both["market_mode_local"]).sum() if "market_mode_jq" in both else 0
        active_match = (both["active_jq"] == both["active_local"]).sum() if "active_jq" in both else 0
        print(f"Mode match: {mode_match}/{len(both)}")
        print(f"Active match: {active_match}/{len(both)}")
        if "fb_pct_jq" in both and "fb_pct_local" in both:
            diff = (both["fb_pct_local"] - both["fb_pct_jq"]).abs()
            print(f"fb_pct <=0.02: {int((diff <= 0.02).sum())}/{len(both)}")
            print(f"fb_pct max diff: {diff.max():.6f}")

    first = both[both["has_diff"]].head(20)
    if not first.empty:
        cols = [
            "date",
            "market_mode_jq",
            "market_mode_local",
            "active_jq",
            "active_local",
            "first_board_perf_jq",
            "first_board_perf_local",
            "fb_pct_jq",
            "fb_pct_local",
            "diff_tags",
        ]
        cols = [c for c in cols if c in first.columns]
        print("\nFirst differing dates:")
        print(first[cols].to_string(index=False))

    tag_counts: dict[str, int] = {}
    for tags in both["diff_tags"]:
        for tag in str(tags).split("|"):
            if tag:
                tag_counts[tag] = tag_counts.get(tag, 0) + 1
    if tag_counts:
        print("\nDiff tag counts:")
        for tag, count in sorted(tag_counts.items(), key=lambda x: (-x[1], x[0])):
            print(f"{tag}: {count}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--jq-diag", type=Path, default=Path("jq_diag_full.txt"))
    parser.add_argument("--local-state", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=Path("compare_state_2022.csv"))
    parser.add_argument("--jq-state-out", type=Path, default=Path("jq_state_2022.csv"))
    args = parser.parse_args()

    jq = parse_jq_state(args.jq_diag)
    local = load_local_state(args.local_state)
    jq.to_csv(args.jq_state_out, index=False, encoding="utf-8-sig")
    out = compare(jq, local)
    out.to_csv(args.out, index=False, encoding="utf-8-sig")
    print(f"WROTE {args.jq_state_out}")
    print(f"WROTE {args.out}")
    print_summary(out)


if __name__ == "__main__":
    main()
