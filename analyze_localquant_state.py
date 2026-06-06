import re
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parent
MOTHER_LOG = ROOT / "母版2020-2026日志" / "log.txt"
LQ_RESULTS = Path(r"D:\work space\local_quant\results")
LOCAL_LOG = LQ_RESULTS / "local_run_2020.log"


def parse_mother_state(path: Path) -> pd.DataFrame:
    pat = re.compile(r"\[STATE\] date=(\d{4}-\d{2}-\d{2}) \| (.*)$")
    rows = []
    for line in path.read_text(encoding="utf-8-sig", errors="ignore").splitlines():
        m = pat.search(line)
        if not m:
            continue
        row = {"date": m.group(1)}
        for part in m.group(2).split(" | "):
            if "=" not in part:
                continue
            key, value = part.split("=", 1)
            row[key.strip()] = value.strip()
        rows.append(row)
    return pd.DataFrame(rows)


def parse_local_state(path: Path) -> pd.DataFrame:
    rows = []
    # local_quant logs are mojibake in the saved file, but the ascii state values
    # and numeric fields remain parseable.
    line_re = re.compile(r"^\[(\d{4}-\d{2}-\d{2})\s+9:05\].*FB([+-]?(?:\d+\.\d+|nan))%.*pct=(\d+\.\d+).*?=([a-z0-9+_]+)")
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if "FB" not in line or "pct=" not in line:
            continue
        m = line_re.search(line)
        if not m:
            continue
        date, fb_pct_text, pct_text, active = m.groups()
        mode_match = re.search(r"=([a-z]+)\s+\| FB", line)
        rows.append(
            {
                "date": date,
                "market_mode": mode_match.group(1) if mode_match else "",
                "FB_pct_text": float(fb_pct_text),
                "FB": float(fb_pct_text) / 100.0,
                "fb_pct": float(pct_text),
                "active": active,
            }
        )
    return pd.DataFrame(rows).drop_duplicates("date", keep="last")


def main() -> None:
    jq = parse_mother_state(MOTHER_LOG)
    loc = parse_local_state(LOCAL_LOG)
    jq2020 = jq[(jq["date"] >= "2020-01-01") & (jq["date"] <= "2020-12-31")].copy()
    keep = ["date", "market_mode", "raw_market_mode", "active", "FB", "fb_pct"]
    jq2020 = jq2020[keep].copy()
    for col in ["FB", "fb_pct"]:
        jq2020[col] = pd.to_numeric(jq2020[col], errors="coerce")

    both = jq2020.merge(loc, on="date", suffixes=("_jq", "_local"), how="outer", indicator=True)
    both["fb_diff"] = both["FB_jq"] - both["FB_local"]
    both["pct_diff"] = both["fb_pct_jq"] - both["fb_pct_local"]
    both["mode_match"] = both["market_mode_jq"] == both["market_mode_local"]
    both["active_match"] = both["active_jq"] == both["active_local"]

    out = both.sort_values("date")
    out_path = ROOT / "compare_localquant_state_2020.csv"
    out.to_csv(out_path, index=False, encoding="utf-8-sig")

    overlap = out[out["_merge"] == "both"].copy()
    print(f"mother_days={len(jq2020)} local_days={len(loc)} overlap={len(overlap)}")
    print(f"mode mismatches: {(~overlap['mode_match']).sum()}")
    print(f"active mismatches: {(~overlap['active_match']).sum()}")
    print(f"fb_pct abs diff > 0.01: {(overlap['pct_diff'].abs() > 0.01).sum()}")
    print(f"fb_pct abs diff > 0.05: {(overlap['pct_diff'].abs() > 0.05).sum()}")
    print(f"FB abs diff > 0.001: {(overlap['fb_diff'].abs() > 0.001).sum()}")
    cols = [
        "date",
        "market_mode_jq",
        "market_mode_local",
        "active_jq",
        "active_local",
        "FB_jq",
        "FB_local",
        "fb_diff",
        "fb_pct_jq",
        "fb_pct_local",
        "pct_diff",
    ]
    print("\nfirst important mismatches")
    important = overlap[
        (~overlap["mode_match"])
        | (~overlap["active_match"])
        | (overlap["pct_diff"].abs() > 0.01)
        | (overlap["fb_diff"].abs() > 0.001)
    ]
    print(important[cols].head(40).to_string(index=False))
    print(f"\nwrote {out_path}")


if __name__ == "__main__":
    main()
