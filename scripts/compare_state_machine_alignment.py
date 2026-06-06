from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


KEY_COLS = [
    "raw_market_mode",
    "market_mode",
    "active",
    "enable_v227",
    "v227_slots",
    "held_v227",
    "bull_sticky",
    "bull_cooldown",
    "bull_consec_loss",
    "bull_release_guard",
    "bull_release_confirm_pending",
    "stoploss_cooldown",
    "v227_shock_cooldown",
    "recent_trades_len",
    "recent_trades_win",
]

NUM_COLS = [
    "first_board_perf",
    "fb_pct",
]

COUNT_COLS = [
    ("prev_first_n", "first_boards_n"),
    ("yjj_n", "v130_n"),
    ("bear_n", "bear_n"),
]


def normalize_date_from_dt(dt: object) -> str:
    text = str(dt)
    return text[:8]


def code_set(text: object) -> set[str]:
    if pd.isna(text):
        return set()
    out = set()
    for part in str(text).replace("|", ",").split(","):
        part = part.strip()
        if part and not part.startswith("..."):
            out.add(part)
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--jq-state", required=True, type=Path, help="Parsed JQ SM state csv.")
    parser.add_argument("--jq-pfb", type=Path, default=None, help="Parsed JQ SM pfb csv.")
    parser.add_argument("--jq-cands", type=Path, default=None, help="Parsed JQ SM cands csv.")
    parser.add_argument("--local-state", required=True, type=Path, help="Local state csv from v227_yjj_probe.")
    parser.add_argument("--out", default="state_machine_alignment.csv", type=Path)
    args = parser.parse_args()

    jq = pd.read_csv(args.jq_state)
    jq = jq[jq["stage"] == "prepare_all:after"].copy()
    jq["date"] = jq["dt"].map(normalize_date_from_dt)
    jq = jq.drop_duplicates("date", keep="last")

    local = pd.read_csv(args.local_state, dtype={"date": str})
    rows = []
    for _, j in jq.iterrows():
        date = j["date"]
        ldf = local[local["date"] == date]
        row = {"date": date}
        if ldf.empty:
            row["status"] = "missing_local"
            rows.append(row)
            continue
        l = ldf.iloc[0]
        diffs = []
        for col in KEY_COLS:
            if col in jq.columns and col in local.columns:
                jv = str(j.get(col))
                lv = str(l.get(col))
                if jv != lv:
                    diffs.append(f"{col}: jq={jv} local={lv}")
        for col in NUM_COLS:
            if col in jq.columns and col in local.columns:
                jv = float(j.get(col))
                lv = float(l.get(col))
                row[f"jq_{col}"] = jv
                row[f"local_{col}"] = lv
                row[f"diff_{col}"] = jv - lv
                if abs(jv - lv) > 1e-6:
                    diffs.append(f"{col}: jq={jv:.8f} local={lv:.8f}")
        for jq_col, local_col in COUNT_COLS:
            if jq_col in jq.columns and local_col in local.columns:
                jv = int(j.get(jq_col))
                lv = int(l.get(local_col))
                row[f"jq_{jq_col}"] = jv
                row[f"local_{local_col}"] = lv
                if jv != lv:
                    diffs.append(f"{jq_col}/{local_col}: jq={jv} local={lv}")
        row["status"] = "ok" if not diffs else "diff"
        row["diffs"] = " ; ".join(diffs[:20])
        rows.append(row)

    out = pd.DataFrame(rows)
    out.to_csv(args.out, index=False, encoding="utf-8-sig")
    print(out["status"].value_counts(dropna=False).to_string())
    first = out[out["status"] == "diff"].head(10)
    if not first.empty:
        print(first[["date", "diffs"]].to_string(index=False))
    print(f"WROTE {args.out}")


if __name__ == "__main__":
    main()
