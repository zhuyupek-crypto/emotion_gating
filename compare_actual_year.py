import csv
import sys
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def norm_time(value):
    value = (value or "").strip().replace(" every_bar", " 09:30:00").replace(" 9:", " 09:")
    if len(value) == 16:
        value += ":00"
    return value


def load_jq(year):
    rows = []
    path = ROOT / "jq_trades_actual.csv"
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            code = r["stock"]
            entry_time = norm_time(r["entry_time"])
            exit_time = norm_time(r["exit_time"])
            if entry_time[:4] == str(year):
                rows.append({"time": entry_time, "code": code, "action": "buy", "branch": r.get("branch", "")})
            if exit_time[:4] == str(year):
                rows.append({"time": exit_time, "code": code, "action": "sell", "branch": r.get("sell_tag", "")})
    rows.sort(key=lambda r: (r["time"], r["code"], r["action"]))
    return rows


def load_local(year):
    rows = []
    out_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / f"rebuild_{year}_v16"
    if not out_dir.is_absolute():
        out_dir = ROOT / out_dir
    path = out_dir / f"local_trades_{year}.csv"
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            amount = int(float(r["amount"]))
            rows.append(
                {
                    "time": norm_time(r["time"]),
                    "code": r["code"],
                    "action": "buy" if amount > 0 else "sell",
                    "amount": abs(amount),
                    "price": float(r["price"]),
                }
            )
    rows.sort(key=lambda r: (r["time"], r["code"], r["action"]))
    return rows


def key(row):
    return (row["time"][:10], row["code"], row["action"])


def main():
    year = int(sys.argv[1]) if len(sys.argv) > 1 else 2021
    jq = load_jq(year)
    local = load_local(year)
    jb = defaultdict(list)
    lb = defaultdict(list)
    for r in jq:
        jb[key(r)].append(r)
    for r in local:
        lb[key(r)].append(r)

    rows = []
    for k in sorted(set(jb) | set(lb)):
        n = max(len(jb.get(k, [])), len(lb.get(k, [])))
        for i in range(n):
            j = jb.get(k, [])[i] if i < len(jb.get(k, [])) else None
            l = lb.get(k, [])[i] if i < len(lb.get(k, [])) else None
            side = "both" if j and l else ("missing" if j else "extra")
            rows.append(
                {
                    "date": k[0],
                    "code": k[1],
                    "action": k[2],
                    "side": side,
                    "jq_time": j.get("time", "") if j else "",
                    "local_time": l.get("time", "") if l else "",
                    "jq_branch": j.get("branch", "") if j else "",
                    "local_amount": l.get("amount", "") if l else "",
                    "local_price": l.get("price", "") if l else "",
                }
            )

    suffix = Path(sys.argv[2]).name if len(sys.argv) > 2 else "v16"
    out_path = ROOT / f"compare_actual_{year}_{suffix}_by_key.csv"
    with out_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "date",
                "code",
                "action",
                "side",
                "jq_time",
                "local_time",
                "jq_branch",
                "local_amount",
                "local_price",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)

    missing = [r for r in rows if r["side"] == "missing"]
    extra = [r for r in rows if r["side"] == "extra"]
    both = [r for r in rows if r["side"] == "both"]
    print(f"YEAR={year} jq={len(jq)} local={len(local)} both={len(both)} missing={len(missing)} extra={len(extra)}")
    print(f"compare_csv={out_path}")
    print("missing:")
    for r in missing[:80]:
        print(r)
    if len(missing) > 80:
        print(f"... {len(missing) - 80} more")
    print("extra:")
    for r in extra[:80]:
        print(r)
    if len(extra) > 80:
        print(f"... {len(extra) - 80} more")


if __name__ == "__main__":
    main()
