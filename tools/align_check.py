import argparse
import csv
import re
import subprocess
from collections import defaultdict
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_JQ_TRADES = ROOT / "母版2020-2026日志" / "交易记录2020-2021.txt"
DEFAULT_LOCAL_DIR = ROOT / "rebuild_2021_warm2020_v16"
DEFAULT_OUT_DIR = ROOT / "alignment_reports"

CODE_RE = re.compile(r"\((\d{6}\.XS(?:HE|HG))\)")


def norm_time(value):
    value = (value or "").strip().replace(" every_bar", " 09:30:00").replace(" 9:", " 09:")
    if len(value) == 16:
        value += ":00"
    return value


def money_to_float(value):
    text = (value or "").strip().replace(",", "")
    if not text:
        return 0.0
    return float(text)


def parse_date(value):
    return datetime.strptime(value[:10], "%Y-%m-%d").date()


def in_range(time_value, start, end):
    day = parse_date(time_value)
    return start <= day <= end


def parse_jq_trades(path, start, end):
    rows = []
    with path.open("r", encoding="utf-8-sig", errors="ignore") as f:
        for line in f:
            parts = [p.strip() for p in line.rstrip("\n").split("\t")]
            if len(parts) < 9 or not re.match(r"^\d{4}-\d{2}-\d{2}$", parts[0]):
                continue
            match = CODE_RE.search(parts[2])
            if not match:
                continue
            time_value = norm_time(parts[0] + " " + parts[1])
            if not in_range(time_value, start, end):
                continue
            amount = int(float(parts[5].replace("股", "").replace(",", "")))
            action = "buy" if parts[3] == "买" else "sell"
            rows.append(
                {
                    "seq": len(rows) + 1,
                    "time": time_value,
                    "date": time_value[:10],
                    "code": match.group(1),
                    "action": action,
                    "amount": amount,
                    "abs_amount": abs(amount),
                    "price": float(parts[6]),
                    "value": money_to_float(parts[7]),
                    "pnl": money_to_float(parts[8]),
                    "fee": money_to_float(parts[9] if len(parts) > 9 else ""),
                    "source": "jq",
                }
            )
    return rows


def parse_local_trades(local_dir, start, end):
    paths = [
        local_dir / "local_trades_2020_to_2021.csv",
        local_dir / "local_trades_2021.csv",
        local_dir / "local_trades_2020.csv",
    ]
    path = next((p for p in paths if p.exists()), None)
    if path is None:
        raise FileNotFoundError(f"No local trades csv found in {local_dir}")

    rows = []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            time_value = norm_time(row["time"])
            if not in_range(time_value, start, end):
                continue
            amount = int(float(row["amount"]))
            action = "buy" if amount > 0 else "sell"
            rows.append(
                {
                    "seq": len(rows) + 1,
                    "time": time_value,
                    "date": time_value[:10],
                    "code": row["code"],
                    "action": action,
                    "amount": amount,
                    "abs_amount": abs(amount),
                    "price": float(row["price"]),
                    "fee": float(row.get("commission", 0) or 0) + float(row.get("tax", 0) or 0),
                    "source": "local",
                }
            )
    return rows, path


def key(row):
    return row["date"], row["code"], row["action"]


def compare_trades(jq_rows, local_rows, amount_tolerance=0, price_tolerance=0.005):
    jq_by_key = defaultdict(list)
    local_by_key = defaultdict(list)
    for row in jq_rows:
        jq_by_key[key(row)].append(row)
    for row in local_rows:
        local_by_key[key(row)].append(row)

    detail = []
    for item_key in sorted(set(jq_by_key) | set(local_by_key)):
        jq_list = jq_by_key.get(item_key, [])
        local_list = local_by_key.get(item_key, [])
        count = max(len(jq_list), len(local_list))
        for idx in range(count):
            jq = jq_list[idx] if idx < len(jq_list) else None
            local = local_list[idx] if idx < len(local_list) else None
            if jq and local:
                amount_diff = jq["abs_amount"] - local["abs_amount"]
                price_diff = jq["price"] - local["price"]
                if amount_diff != 0:
                    category = "data_diff_amount"
                elif abs(price_diff) > price_tolerance:
                    category = "data_diff_price"
                else:
                    category = "matched"
                side = "both"
            elif jq:
                amount_diff = ""
                price_diff = ""
                category = "blocked_missing_local"
                side = "jq_only"
            else:
                amount_diff = ""
                price_diff = ""
                category = "blocked_extra_local"
                side = "local_only"

            detail.append(
                {
                    "date": item_key[0],
                    "code": item_key[1],
                    "action": item_key[2],
                    "side": side,
                    "category": category,
                    "jq_time": jq["time"] if jq else "",
                    "local_time": local["time"] if local else "",
                    "jq_amount": jq["abs_amount"] if jq else "",
                    "local_amount": local["abs_amount"] if local else "",
                    "amount_diff": amount_diff,
                    "jq_price": jq["price"] if jq else "",
                    "local_price": local["price"] if local else "",
                    "price_diff": price_diff,
                    "jq_fee": jq["fee"] if jq else "",
                    "local_fee": local["fee"] if local else "",
                }
            )

    matched = sum(1 for row in detail if row["side"] == "both")
    jq_count = len(jq_rows)
    local_count = len(local_rows)
    alignment_rate = matched / jq_count if jq_count else 0.0
    trade_count_diff_rate = abs(local_count - jq_count) / jq_count if jq_count else 0.0
    return detail, alignment_rate, trade_count_diff_rate


def load_equity(path, start, end):
    if path is None:
        return None
    path = Path(path)
    if not path.exists():
        return None
    rows = []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        fields = reader.fieldnames or []
        value_field = "value" if "value" in fields else ("portfolio_value" if "portfolio_value" in fields else None)
        if value_field is None:
            raise ValueError(f"Cannot find equity value column in {path}")
        for row in reader:
            date_value = row.get("date") or row.get("time", "")[:10]
            if not date_value:
                continue
            day = parse_date(date_value)
            if start <= day <= end:
                rows.append({"date": date_value[:10], "value": float(row[value_field])})
    return rows


def local_equity_path(local_dir):
    candidates = [
        local_dir / "local_equity_2020_to_2021.csv",
        local_dir / "local_equity_2021.csv",
        local_dir / "local_equity_2020.csv",
    ]
    return next((p for p in candidates if p.exists()), None)


def return_from_equity(rows):
    if not rows:
        return None
    first = rows[0]["value"]
    last = rows[-1]["value"]
    return last / first - 1 if first else None


def write_csv(path, rows, fieldnames):
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_diff(path):
    try:
        result = subprocess.run(
            ["git", "diff", "--", "rebuild_from_archive", "母版-20260506-Clone.py", "alignment_open_issues.md", "tools"],
            cwd=ROOT,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            check=False,
        )
        path.write_text(result.stdout, encoding="utf-8")
    except Exception as exc:
        path.write_text(f"Failed to collect git diff: {exc}\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Check local/JQ alignment without attempting repairs.")
    parser.add_argument("--jq-trades", default=str(DEFAULT_JQ_TRADES))
    parser.add_argument("--jq-equity", default="")
    parser.add_argument("--local-dir", default=str(DEFAULT_LOCAL_DIR))
    parser.add_argument("--start", default="2020-01-02")
    parser.add_argument("--end", default="2021-12-31")
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    args = parser.parse_args()

    start = parse_date(args.start)
    end = parse_date(args.end)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    jq_trades = parse_jq_trades(Path(args.jq_trades), start, end)
    local_trades, local_trade_path = parse_local_trades(Path(args.local_dir), start, end)
    detail, alignment_rate, trade_count_diff_rate = compare_trades(jq_trades, local_trades)

    detail_path = out_dir / f"align_trade_detail_{args.start}_{args.end}.csv"
    write_csv(
        detail_path,
        detail,
        [
            "date", "code", "action", "side", "category", "jq_time", "local_time",
            "jq_amount", "local_amount", "amount_diff", "jq_price", "local_price",
            "price_diff", "jq_fee", "local_fee",
        ],
    )

    jq_equity = load_equity(args.jq_equity, start, end) if args.jq_equity else None
    local_equity = load_equity(local_equity_path(Path(args.local_dir)), start, end)
    jq_return = return_from_equity(jq_equity) if jq_equity else None
    local_return = return_from_equity(local_equity) if local_equity else None
    return_diff = abs(local_return - jq_return) if jq_return is not None and local_return is not None else None

    pass_return = return_diff is not None and return_diff < 0.02
    pass_count = trade_count_diff_rate < 0.05
    pass_alignment = alignment_rate > 0.95
    platform_trusted = pass_return and pass_count and pass_alignment

    diff_path = out_dir / f"align_worktree_diff_{args.start}_{args.end}.patch"
    write_diff(diff_path)

    category_counts = defaultdict(int)
    for row in detail:
        category_counts[row["category"]] += 1

    report_path = out_dir / f"align_report_{args.start}_{args.end}.md"
    with report_path.open("w", encoding="utf-8") as f:
        f.write(f"# Alignment Report {args.start} to {args.end}\n\n")
        f.write("## Verdict\n\n")
        if platform_trusted:
            f.write('Platform verdict: "平台可信"\n\n')
        else:
            f.write('Platform verdict: "未达平台可信验收或净值数据不足"\n\n')
        f.write("No repair attempts were made by this tool.\n\n")
        f.write("## Inputs\n\n")
        f.write(f"- JQ trades: `{args.jq_trades}`\n")
        f.write(f"- JQ equity: `{args.jq_equity or 'not provided'}`\n")
        f.write(f"- Local trades: `{local_trade_path}`\n")
        f.write(f"- Local equity: `{local_equity_path(Path(args.local_dir)) or 'not found'}`\n\n")
        f.write("## Metrics\n\n")
        f.write(f"- JQ trades: {len(jq_trades)}\n")
        f.write(f"- Local trades: {len(local_trades)}\n")
        f.write(f"- Trade count diff rate: {trade_count_diff_rate:.4%}\n")
        f.write(f"- Per-trade key alignment rate: {alignment_rate:.4%}\n")
        if return_diff is None:
            f.write("- Total return diff: unavailable because JQ equity was not provided\n")
        else:
            f.write(f"- JQ total return: {jq_return:.4%}\n")
            f.write(f"- Local total return: {local_return:.4%}\n")
            f.write(f"- Total return diff: {return_diff:.4%}\n")
        f.write("\n## Acceptance\n\n")
        f.write(f"- Total return diff < 2%: {'PASS' if pass_return else 'FAIL/UNAVAILABLE'}\n")
        f.write(f"- Trade count diff < 5%: {'PASS' if pass_count else 'FAIL'}\n")
        f.write(f"- Per-trade alignment > 95%: {'PASS' if pass_alignment else 'FAIL'}\n\n")
        f.write("## Difference Categories\n\n")
        for category in sorted(category_counts):
            f.write(f"- {category}: {category_counts[category]}\n")
        f.write("\n## Unmatched Trade List\n\n")
        unmatched = [row for row in detail if row["side"] != "both"]
        if not unmatched:
            f.write("No unmatched trades by date+code+action.\n")
        else:
            f.write("| date | code | action | side | category | jq_time | local_time | jq_amount | local_amount |\n")
            f.write("|---|---|---|---|---|---|---|---:|---:|\n")
            for row in unmatched:
                f.write(
                    "| {date} | {code} | {action} | {side} | {category} | {jq_time} | {local_time} | {jq_amount} | {local_amount} |\n".format(
                        **row
                    )
                )
        f.write("\n## Data Difference Summary\n\n")
        data_diffs = [row for row in detail if row["side"] == "both" and row["category"] != "matched"]
        f.write(f"- Matched keys with amount/price differences: {len(data_diffs)}\n")
        f.write("- Full amount/price details are in the trade detail CSV.\n")
        f.write("\n## Diff Scope\n\n")
        f.write("- Complete captured diff is attached below as an artifact.\n")
        f.write("- This script does not decide whether the diff is acceptable; that remains a review item for the total designer.\n")
        f.write("\n## Artifacts\n\n")
        f.write(f"- Trade detail CSV: `{detail_path}`\n")
        f.write(f"- Worktree diff: `{diff_path}`\n")

    print(f"report={report_path}")
    print(f"trade_detail={detail_path}")
    print(f"diff={diff_path}")
    print(f"jq_trades={len(jq_trades)} local_trades={len(local_trades)}")
    print(f"trade_count_diff_rate={trade_count_diff_rate:.4%}")
    print(f"alignment_rate={alignment_rate:.4%}")
    print("return_diff=UNAVAILABLE" if return_diff is None else f"return_diff={return_diff:.4%}")
    print('verdict="平台可信"' if platform_trusted else 'verdict="未达平台可信验收或净值数据不足"')


if __name__ == "__main__":
    main()
