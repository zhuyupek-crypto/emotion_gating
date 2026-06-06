import csv
import re
import sys
from pathlib import Path


ROOT = Path(r"D:\Work Space\他山之石\情绪门控")
JQ_TXT = Path(r"D:\work space\local_quant\results\jq_trades_2020_real.txt")
LOCAL_CSV = Path(r"D:\work space\local_quant\results\local_trades_2020.csv")
JQ_PARSED = ROOT / "jq_trades_2020_real_parsed_from_txt.csv"
OUT_SEQ = ROOT / "compare_real_trades_2020_by_sequence.csv"
OUT_KEY = ROOT / "compare_real_trades_2020_by_key.csv"


CODE_RE = re.compile(r"\((\d{6}\.XS(?:HE|HG))\)")


def money_to_float(text):
    text = (text or "").strip().replace(",", "")
    if text == "":
        return 0.0
    return float(text)


def norm_time(value):
    value = (value or "").strip()
    value = value.replace(" every_bar", " 09:30:00")
    value = value.replace(" 9:", " 09:")
    if len(value) == 16:
        value += ":00"
    return value


def parse_jq_txt():
    rows = []
    with JQ_TXT.open("r", encoding="utf-8-sig", errors="ignore") as f:
        for line in f:
            parts = [p.strip() for p in line.rstrip("\n").split("\t")]
            if len(parts) < 10:
                continue
            if not re.match(r"^2020-\d{2}-\d{2}$", parts[0]):
                continue
            m = CODE_RE.search(parts[2])
            if not m:
                continue
            amount_text = parts[5].replace("股", "").replace(",", "")
            amount = int(float(amount_text))
            action = "buy" if parts[3] == "买" else "sell"
            rows.append(
                {
                    "seq": len(rows) + 1,
                    "time": norm_time(parts[0] + " " + parts[1]),
                    "code": m.group(1),
                    "action": action,
                    "amount": amount,
                    "price": float(parts[6]),
                    "value": money_to_float(parts[7]),
                    "pnl": money_to_float(parts[8]),
                    "fee": money_to_float(parts[9]),
                }
            )
    return rows


def parse_local_csv(path=LOCAL_CSV):
    rows = []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            amount = int(float(row["amount"]))
            action = row.get("action") or ("buy" if amount > 0 else "sell")
            rows.append(
                {
                    "seq": len(rows) + 1,
                    "time": norm_time(row["time"]),
                    "code": row["code"],
                    "action": action,
                    "amount": amount,
                    "price": float(row["price"]),
                    "fee": float(row.get("commission", 0) or 0) + float(row.get("tax", 0) or 0),
                }
            )
    return rows


def key(row):
    return (row["time"][:10], row["code"], row["action"])


def write_csv(path, rows, fields):
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main():
    jq = parse_jq_txt()
    local_path = Path(sys.argv[1]) if len(sys.argv) > 1 else LOCAL_CSV
    if not local_path.is_absolute():
        local_path = ROOT / local_path
    local = parse_local_csv(local_path)
    write_csv(
        JQ_PARSED,
        jq,
        ["seq", "time", "code", "action", "amount", "price", "value", "pnl", "fee"],
    )

    seq_rows = []
    for i in range(max(len(jq), len(local))):
        j = jq[i] if i < len(jq) else {}
        l = local[i] if i < len(local) else {}
        seq_rows.append(
            {
                "seq": i + 1,
                "jq_time": j.get("time", ""),
                "local_time": l.get("time", ""),
                "jq_code": j.get("code", ""),
                "local_code": l.get("code", ""),
                "jq_action": j.get("action", ""),
                "local_action": l.get("action", ""),
                "jq_amount": j.get("amount", ""),
                "local_amount": l.get("amount", ""),
                "amount_diff": (j.get("amount", 0) - l.get("amount", 0)) if j and l else "",
                "jq_price": j.get("price", ""),
                "local_price": l.get("price", ""),
                "price_diff": (j.get("price", 0.0) - l.get("price", 0.0)) if j and l else "",
                "same_time": j.get("time", "") == l.get("time", ""),
                "same_code": j.get("code", "") == l.get("code", ""),
                "same_action": j.get("action", "") == l.get("action", ""),
                "same_side_key": key(j) == key(l) if j and l else False,
            }
        )

    fields_seq = [
        "seq",
        "jq_time",
        "local_time",
        "jq_code",
        "local_code",
        "jq_action",
        "local_action",
        "jq_amount",
        "local_amount",
        "amount_diff",
        "jq_price",
        "local_price",
        "price_diff",
        "same_time",
        "same_code",
        "same_action",
        "same_side_key",
    ]
    write_csv(OUT_SEQ, seq_rows, fields_seq)

    local_by_key = {}
    for l in local:
        local_by_key.setdefault(key(l), []).append(l)
    jq_by_key = {}
    for j in jq:
        jq_by_key.setdefault(key(j), []).append(j)

    key_rows = []
    for k in sorted(set(local_by_key) | set(jq_by_key)):
        lq = list(local_by_key.get(k, []))
        jq_q = list(jq_by_key.get(k, []))
        n = max(len(lq), len(jq_q))
        for idx in range(n):
            j = jq_q[idx] if idx < len(jq_q) else {}
            l = lq[idx] if idx < len(lq) else {}
            key_rows.append(
                {
                    "date": k[0],
                    "code": k[1],
                    "action": k[2],
                    "side": "both" if j and l else ("jq_only" if j else "local_only"),
                    "jq_time": j.get("time", ""),
                    "local_time": l.get("time", ""),
                    "jq_amount": j.get("amount", ""),
                    "local_amount": l.get("amount", ""),
                    "amount_diff": (j.get("amount", 0) - l.get("amount", 0)) if j and l else "",
                    "jq_price": j.get("price", ""),
                    "local_price": l.get("price", ""),
                    "price_diff": (j.get("price", 0.0) - l.get("price", 0.0)) if j and l else "",
                    "jq_fee": j.get("fee", ""),
                    "local_fee": l.get("fee", ""),
                    "fee_diff": (j.get("fee", 0.0) - l.get("fee", 0.0)) if j and l else "",
                }
            )
    fields_key = [
        "date",
        "code",
        "action",
        "side",
        "jq_time",
        "local_time",
        "jq_amount",
        "local_amount",
        "amount_diff",
        "jq_price",
        "local_price",
        "price_diff",
        "jq_fee",
        "local_fee",
        "fee_diff",
    ]
    write_csv(OUT_KEY, key_rows, fields_key)

    seq_same_key = sum(1 for r in seq_rows if r["same_side_key"])
    seq_same_all = sum(
        1
        for r in seq_rows
        if r["same_time"] and r["same_code"] and r["same_action"] and r["amount_diff"] == 0 and abs(float(r["price_diff"] or 0)) < 0.005
    )
    both = [r for r in key_rows if r["side"] == "both"]
    print(f"jq_trades={len(jq)} local_trades={len(local)}")
    print(f"sequence same date/code/action={seq_same_key}; exact seq rows={seq_same_all}")
    print(
        "key match both=%d jq_only=%d local_only=%d"
        % (
            len(both),
            sum(1 for r in key_rows if r["side"] == "jq_only"),
            sum(1 for r in key_rows if r["side"] == "local_only"),
        )
    )
    print(
        "both amount mismatches=%d price mismatches >0.005=%d"
        % (
            sum(1 for r in both if r["amount_diff"] != 0),
            sum(1 for r in both if abs(float(r["price_diff"])) > 0.005),
        )
    )
    print(f"wrote {JQ_PARSED}")
    print(f"wrote {OUT_SEQ}")
    print(f"wrote {OUT_KEY}")
    for row in seq_rows[:15]:
        print(row)


if __name__ == "__main__":
    main()
