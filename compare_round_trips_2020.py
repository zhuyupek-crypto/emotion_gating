import csv
from collections import defaultdict, deque
from pathlib import Path


ROOT = Path(r"D:\Work Space\他山之石\情绪门控")
LOCAL_TRADES = Path(r"D:\work space\local_quant\results\local_trades_2020.csv")
JQ_ROUND_TRIPS = ROOT / "jq_trades_actual.csv"
OUT = ROOT / "compare_round_trips_2020.csv"


def norm_dt(value):
    value = (value or "").strip()
    value = value.replace(" 9:", " 09:")
    value = value.replace(" every_bar", " 09:30:00")
    if len(value) == 16:
        value += ":00"
    return value


def load_local_round_trips():
    open_lots = defaultdict(deque)
    rows = []
    with LOCAL_TRADES.open("r", encoding="utf-8-sig", newline="") as f:
        for t in csv.DictReader(f):
            code = t["code"]
            amount = int(float(t["amount"]))
            dt = norm_dt(t["time"])
            action = t["action"]
            if action == "buy" or amount > 0:
                open_lots[code].append(
                    {
                        "stock": code,
                        "entry": dt[:10],
                        "entry_time": dt,
                        "entry_price": float(t["price"]),
                        "entry_amount": amount,
                    }
                )
                continue
            if not open_lots[code]:
                rows.append(
                    {
                        "stock": code,
                        "entry": "",
                        "exit": dt[:10],
                        "entry_time": "",
                        "exit_time": dt,
                        "local_status": "sell_without_buy",
                    }
                )
                continue
            lot = open_lots[code].popleft()
            lot.update(
                {
                    "exit": dt[:10],
                    "exit_time": dt,
                    "exit_price": float(t["price"]),
                    "exit_amount": amount,
                    "local_status": "closed",
                }
            )
            rows.append(lot)

    for code, q in open_lots.items():
        for lot in q:
            lot.update({"exit": "", "exit_time": "", "local_status": "open"})
            rows.append(lot)
    return rows


def load_jq_round_trips():
    rows = []
    with JQ_ROUND_TRIPS.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            if not row.get("entry", "").startswith("2020"):
                continue
            rows.append(
                {
                    "stock": row["stock"],
                    "entry": row["entry"],
                    "exit": row["exit"],
                    "entry_time": norm_dt(row["entry_time"]),
                    "exit_time": norm_dt(row["exit_time"]),
                    "branch": row.get("branch", ""),
                    "sell_tag": row.get("sell_tag", ""),
                }
            )
    return rows


def key(row):
    return (row.get("stock", ""), row.get("entry", ""), row.get("exit", ""))


def main():
    local = load_local_round_trips()
    jq = load_jq_round_trips()

    local_by_key = defaultdict(deque)
    jq_by_key = defaultdict(deque)
    for row in local:
        local_by_key[key(row)].append(row)
    for row in jq:
        jq_by_key[key(row)].append(row)

    all_keys = sorted(set(local_by_key) | set(jq_by_key))
    out_rows = []
    for k in all_keys:
        lq = local_by_key.get(k, deque())
        jq_q = jq_by_key.get(k, deque())
        n = max(len(lq), len(jq_q))
        for _ in range(n):
            l = lq.popleft() if lq else {}
            j = jq_q.popleft() if jq_q else {}
            out_rows.append(
                {
                    "stock": k[0],
                    "entry": k[1],
                    "exit": k[2],
                    "match": bool(l and j),
                    "jq_entry_time": j.get("entry_time", ""),
                    "local_entry_time": l.get("entry_time", ""),
                    "jq_exit_time": j.get("exit_time", ""),
                    "local_exit_time": l.get("exit_time", ""),
                    "entry_time_match": j.get("entry_time", "") == l.get("entry_time", ""),
                    "exit_time_match": j.get("exit_time", "") == l.get("exit_time", ""),
                    "branch": j.get("branch", ""),
                    "sell_tag": j.get("sell_tag", ""),
                    "local_entry_price": l.get("entry_price", ""),
                    "local_exit_price": l.get("exit_price", ""),
                    "local_entry_amount": l.get("entry_amount", ""),
                    "local_exit_amount": l.get("exit_amount", ""),
                    "local_status": l.get("local_status", ""),
                    "side": "both" if l and j else ("local_only" if l else "jq_only"),
                }
            )

    fields = [
        "stock",
        "entry",
        "exit",
        "match",
        "jq_entry_time",
        "local_entry_time",
        "jq_exit_time",
        "local_exit_time",
        "entry_time_match",
        "exit_time_match",
        "branch",
        "sell_tag",
        "local_entry_price",
        "local_exit_price",
        "local_entry_amount",
        "local_exit_amount",
        "local_status",
        "side",
    ]
    with OUT.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(out_rows)

    both = [r for r in out_rows if r["side"] == "both"]
    local_only = [r for r in out_rows if r["side"] == "local_only"]
    jq_only = [r for r in out_rows if r["side"] == "jq_only"]
    entry_time_bad = [r for r in both if not r["entry_time_match"]]
    exit_time_bad = [r for r in both if not r["exit_time_match"]]
    print(f"jq_round_trips={len(jq)} local_round_trips={len(local)} matched={len(both)}")
    print(f"local_only={len(local_only)} jq_only={len(jq_only)}")
    print(f"entry_time_mismatch={len(entry_time_bad)} exit_time_mismatch={len(exit_time_bad)}")
    print(f"wrote {OUT}")
    for row in (local_only + jq_only + entry_time_bad + exit_time_bad)[:25]:
        print(row)


if __name__ == "__main__":
    main()
