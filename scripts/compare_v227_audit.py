"""
Compare local v227_yjj_probe trades with JoinQuant AUDIT_V227 samples.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
LOCAL = ROOT / "trades_v227_yjj_probe.csv"
JQ = ROOT / "jq_v227_audit_202403_sample.csv"


def norm_local() -> pd.DataFrame:
    df = pd.read_csv(LOCAL, dtype={"date": str})
    df["event"] = df["side"].str.upper()
    df["day"] = df["date"].astype(str)
    return df[["event", "day", "code", "price", "reason"]].copy()


def norm_jq() -> pd.DataFrame:
    df = pd.read_csv(JQ)
    df["day"] = df["datetime"].str.slice(0, 8)
    return df[["event", "day", "code", "price", "reason", "datetime", "extra"]].copy()


def main() -> None:
    local = norm_local()
    jq = norm_jq()
    rows = []
    for _, r in jq.iterrows():
        cand = local[(local["event"] == r["event"]) & (local["code"] == r["code"])]
        exact = cand[cand["day"] == r["day"]]
        if not exact.empty:
            l = exact.iloc[0]
            status = "OK" if abs(float(l["price"]) - float(r["price"])) <= 0.011 and l["reason"] == r["reason"] else "DIFF"
            rows.append({
                "status": status,
                "event": r["event"],
                "code": r["code"],
                "jq_day": r["day"],
                "local_day": l["day"],
                "jq_price": r["price"],
                "local_price": l["price"],
                "jq_reason": r["reason"],
                "local_reason": l["reason"],
            })
        elif not cand.empty:
            l = cand.iloc[0]
            rows.append({
                "status": "DATE_MISMATCH",
                "event": r["event"],
                "code": r["code"],
                "jq_day": r["day"],
                "local_day": l["day"],
                "jq_price": r["price"],
                "local_price": l["price"],
                "jq_reason": r["reason"],
                "local_reason": l["reason"],
            })
        else:
            rows.append({
                "status": "MISSING_LOCAL",
                "event": r["event"],
                "code": r["code"],
                "jq_day": r["day"],
                "local_day": "",
                "jq_price": r["price"],
                "local_price": "",
                "jq_reason": r["reason"],
                "local_reason": "",
            })

    out = pd.DataFrame(rows)
    print(out.to_string(index=False))
    print("\ncounts:")
    print(out["status"].value_counts().to_string())


if __name__ == "__main__":
    main()
