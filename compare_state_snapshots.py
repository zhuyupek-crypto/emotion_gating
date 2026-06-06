import argparse
import re
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parent


def find_mother_log() -> Path:
    for path in ROOT.iterdir():
        if path.is_dir() and "2020-2026" in path.name:
            log_path = path / "log.txt"
            if log_path.exists():
                return log_path
    raise FileNotFoundError("mother log directory containing 2020-2026/log.txt not found")


def parse_bool(value):
    text = str(value).strip()
    if text in ("True", "true", "1"):
        return True
    if text in ("False", "false", "0"):
        return False
    return pd.NA


def parse_jq_state(path: Path) -> pd.DataFrame:
    rows = []
    pat = re.compile(r"\[STATE\] date=(\d{4}-\d{2}-\d{2}) \| (.*)$")
    for line in path.read_text(encoding="utf-8-sig", errors="ignore").splitlines():
        m = pat.search(line)
        if not m:
            continue
        row = {"date": m.group(1)}
        for part in m.group(2).split(" | "):
            if "=" not in part:
                continue
            key, value = part.split("=", 1)
            key = key.strip()
            value = value.strip()
            if key == "slots":
                sm = re.search(r"v227:(\d+),rzq:(\d+),zb:(\d+),auction:(\d+)", value)
                if sm:
                    row["slot_v227"], row["slot_rzq"], row["slot_zb"], row["slot_auction"] = map(int, sm.groups())
            elif key == "cands":
                cm = re.search(r"yjj:(\d+),bear:(\d+),rzq:(\d+),zb:(\d+),auction:(\d+)", value)
                if cm:
                    row["cand_yjj"], row["cand_bear"], row["cand_rzq"], row["cand_zb"], row["cand_auction"] = map(
                        int, cm.groups()
                    )
            else:
                row[key] = value
        rows.append(row)
    df = pd.DataFrame(rows)
    numeric_cols = [
        "FB",
        "fb_pct",
        "recent_wr",
        "core_wr",
        "bull_sticky",
        "bull_cooldown",
        "stoploss_cooldown",
        "rzq_cooldown",
        "v227_shock_cooldown",
        "slot_v227",
        "slot_rzq",
        "slot_zb",
        "slot_auction",
        "cand_yjj",
        "cand_bear",
        "cand_rzq",
        "cand_zb",
        "cand_auction",
    ]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    for col in ["bull_release_pending", "bull_release_guard", "enable_v227", "enable_rzq", "enable_zb", "enable_auction"]:
        if col in df.columns:
            df[col] = df[col].map(parse_bool)
    return df


def load_local_state(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, encoding="utf-8-sig")
    for col in ["bull_release_pending", "bull_release_guard", "enable_v227", "enable_rzq", "enable_zb", "enable_auction"]:
        if col in df.columns:
            df[col] = df[col].map(parse_bool)
    return df


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("local_state_csv")
    parser.add_argument("--start", default="")
    parser.add_argument("--end", default="")
    parser.add_argument("--out", default="")
    args = parser.parse_args()

    local_path = Path(args.local_state_csv)
    if not local_path.is_absolute():
        local_path = ROOT / local_path
    jq = parse_jq_state(find_mother_log())
    local = load_local_state(local_path)
    if args.start:
        jq = jq[jq["date"] >= args.start]
        local = local[local["date"] >= args.start]
    if args.end:
        jq = jq[jq["date"] <= args.end]
        local = local[local["date"] <= args.end]

    compare_cols = [
        "market_mode",
        "raw_market_mode",
        "active",
        "FB",
        "fb_pct",
        "bull_sticky",
        "bull_cooldown",
        "bull_release_pending",
        "bull_release_guard",
        "stoploss_cooldown",
        "rzq_cooldown",
        "v227_shock_cooldown",
        "enable_v227",
        "enable_rzq",
        "enable_zb",
        "enable_auction",
        "slot_v227",
        "slot_rzq",
        "slot_zb",
        "slot_auction",
        "cand_yjj",
        "cand_bear",
        "cand_rzq",
        "cand_zb",
        "cand_auction",
        "recent_wr",
        "core_wr",
    ]
    keep = ["date"] + [c for c in compare_cols if c in jq.columns and c in local.columns]
    merged = jq[keep].merge(local[keep], on="date", how="outer", suffixes=("_jq", "_local"), indicator=True)

    tol = {
        "FB": 0.0011,
        "fb_pct": 0.011,
        "recent_wr": 0.011,
        "core_wr": 0.011,
    }
    diff_cols = []
    for col in keep[1:]:
        a = merged[f"{col}_jq"]
        b = merged[f"{col}_local"]
        if col in tol:
            diff = (pd.to_numeric(a, errors="coerce") - pd.to_numeric(b, errors="coerce")).abs() > tol[col]
        else:
            diff = a.astype(str) != b.astype(str)
        diff = diff & (merged["_merge"] == "both")
        merged[f"{col}_diff"] = diff
        diff_cols.append(f"{col}_diff")
    merged["diff_count"] = merged[diff_cols].sum(axis=1) if diff_cols else 0

    out_path = Path(args.out) if args.out else ROOT / f"compare_state_{local_path.stem}.csv"
    if not out_path.is_absolute():
        out_path = ROOT / out_path
    merged.sort_values("date").to_csv(out_path, index=False, encoding="utf-8-sig")

    overlap = merged[merged["_merge"] == "both"]
    print(f"jq_days={len(jq)} local_days={len(local)} overlap={len(overlap)}")
    print(f"diff_days={(overlap['diff_count'] > 0).sum()}")
    for col in keep[1:]:
        n = int(overlap[f"{col}_diff"].sum())
        if n:
            print(f"{col}: {n}")
    print("first diff rows:")
    cols = ["date", "diff_count"]
    for col in keep[1:]:
        if int(overlap[f"{col}_diff"].sum()):
            cols.extend([f"{col}_jq", f"{col}_local"])
            if len(cols) > 12:
                break
    print(overlap[overlap["diff_count"] > 0][cols].head(20).to_string(index=False))
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
