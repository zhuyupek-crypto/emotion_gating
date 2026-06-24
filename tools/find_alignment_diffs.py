import argparse
import csv
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_JQ_FUNDS = ROOT / "母版2020-2026日志" / "资金记录2020-2021.txt"
DEFAULT_JQ_TRADES = ROOT / "母版2020-2026日志" / "交易记录2020-2021.txt"
DEFAULT_LOCAL_DIR = ROOT / "rebuild_2021_warm2020_v16"
DEFAULT_OUT_DIR = ROOT / "alignment_reports"

CODE_RE = re.compile(r"\((\d{6}\.XS(?:HE|HG))\)")


def money_to_float(value):
    text = (value or "").strip().replace(",", "")
    if not text:
        return 0.0
    return float(text)


def norm_time(value):
    value = (value or "").strip().replace(" every_bar", " 09:30:00").replace(" 9:", " 09:")
    if len(value) == 16:
        value += ":00"
    return value


def parse_date(value):
    return datetime.strptime(value[:10], "%Y-%m-%d").date()


def in_range(date_text, start, end):
    day = parse_date(date_text)
    return start <= day <= end


def parse_jq_funds(path, start, end):
    rows = {}
    positions = defaultdict(dict)
    current_date = None
    with path.open("r", encoding="utf-8-sig", errors="ignore") as f:
        for raw in f:
            line = raw.strip("\n")
            if re.match(r"^\d{4}-\d{2}-\d{2}$", line.strip()):
                current_date = line.strip()
                if in_range(current_date, start, end):
                    rows.setdefault(
                        current_date,
                        {
                            "date": current_date,
                            "cash": 0.0,
                            "positions_value": 0.0,
                            "total_value": 0.0,
                            "has_cash": False,
                            "has_total": False,
                        },
                    )
                continue
            if current_date is None or not in_range(current_date, start, end):
                continue
            parts = [p.strip() for p in line.split("\t")]
            if not parts or all(not p for p in parts):
                continue
            if parts[0] == "Cash":
                rows[current_date]["cash"] = money_to_float(parts[3] if len(parts) > 3 else "")
                rows[current_date]["has_cash"] = True
                continue
            if "总共:" in line:
                for part in parts:
                    if "总共:" in part:
                        rows[current_date]["total_value"] = money_to_float(part.split("总共:", 1)[1])
                        rows[current_date]["has_total"] = True
                rows[current_date]["positions_value"] = rows[current_date]["total_value"] - rows[current_date]["cash"]
                continue
            match = CODE_RE.search(parts[0])
            if match and len(parts) >= 4:
                amount = int(float(parts[1].replace("股", "").replace(",", "")))
                price = money_to_float(parts[2])
                value = money_to_float(parts[3])
                positions[current_date][match.group(1)] = {
                    "amount": amount,
                    "price": price,
                    "value": value,
                }
    return rows, positions


def local_stats_path(local_dir):
    candidates = [
        local_dir / "local_portfolio_stats_2020_to_2021.csv",
        local_dir / "local_portfolio_stats_2021.csv",
        local_dir / "local_portfolio_stats_2020.csv",
    ]
    return next((p for p in candidates if p.exists()), None)


def local_trades_path(local_dir):
    candidates = [
        local_dir / "local_trades_2020_to_2021.csv",
        local_dir / "local_trades_2021.csv",
        local_dir / "local_trades_2020.csv",
    ]
    return next((p for p in candidates if p.exists()), None)


def parse_local_stats(path, start, end):
    rows = {}
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            date = row["date"][:10]
            if not in_range(date, start, end):
                continue
            rows[date] = {
                "date": date,
                "cash": float(row["available_cash"]),
                "positions_value": float(row["positions_value"]),
                "total_value": float(row["total_value"]),
            }
    return rows


def parse_trades(path, start, end, source):
    rows = []
    if source == "jq":
        with path.open("r", encoding="utf-8-sig", errors="ignore") as f:
            for raw in f:
                parts = [p.strip() for p in raw.rstrip("\n").split("\t")]
                if len(parts) < 9 or not re.match(r"^\d{4}-\d{2}-\d{2}$", parts[0]):
                    continue
                time = norm_time(parts[0] + " " + parts[1])
                if not in_range(time[:10], start, end):
                    continue
                match = CODE_RE.search(parts[2])
                if not match:
                    continue
                amount = int(float(parts[5].replace("股", "").replace(",", "")))
                rows.append(
                    {
                        "date": time[:10],
                        "time": time,
                        "code": match.group(1),
                        "amount": amount,
                        "action": "buy" if amount > 0 else "sell",
                        "price": float(parts[6]),
                    }
                )
    else:
        with path.open("r", encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                time = norm_time(row["time"])
                if not in_range(time[:10], start, end):
                    continue
                amount = int(float(row["amount"]))
                rows.append(
                    {
                        "date": time[:10],
                        "time": time,
                        "code": row["code"],
                        "amount": amount,
                        "action": "buy" if amount > 0 else "sell",
                        "price": float(row["price"]),
                    }
                )
    rows.sort(key=lambda r: (r["time"], r["code"], r["amount"]))
    return rows


def reconstruct_positions(trades, dates):
    positions_by_day = {}
    positions = defaultdict(int)
    trades_by_day = defaultdict(list)
    for row in trades:
        trades_by_day[row["date"]].append(row)
    for date in sorted(dates):
        for trade in trades_by_day.get(date, []):
            positions[trade["code"]] += trade["amount"]
            if positions[trade["code"]] == 0:
                del positions[trade["code"]]
        positions_by_day[date] = dict(positions)
    return positions_by_day


def compare_daily(jq_funds, local_stats):
    dates = sorted(set(jq_funds) & set(local_stats))
    rows = []
    for date in dates:
        jq = jq_funds[date]
        local = local_stats[date]
        rows.append(
            {
                "date": date,
                "jq_total": jq["total_value"],
                "local_total": local["total_value"],
                "total_diff": local["total_value"] - jq["total_value"],
                "total_diff_pct": (local["total_value"] - jq["total_value"]) / jq["total_value"] if jq["total_value"] else 0.0,
                "jq_cash": jq["cash"],
                "local_cash": local["cash"],
                "cash_diff": local["cash"] - jq["cash"],
                "jq_positions_value": jq["positions_value"],
                "local_positions_value": local["positions_value"],
                "positions_value_diff": local["positions_value"] - jq["positions_value"],
            }
        )
    return rows


def compare_positions(jq_positions, local_positions):
    dates = sorted(set(jq_positions) | set(local_positions))
    rows = []
    for date in dates:
        jq = jq_positions.get(date, {})
        local = local_positions.get(date, {})
        for code in sorted(set(jq) | set(local)):
            jq_amount = jq.get(code, {}).get("amount", 0) if isinstance(jq.get(code), dict) else jq.get(code, 0)
            local_amount = local.get(code, 0)
            if jq_amount == local_amount:
                continue
            rows.append(
                {
                    "date": date,
                    "code": code,
                    "jq_amount": jq_amount,
                    "local_amount": local_amount,
                    "amount_diff": local_amount - jq_amount,
                    "category": "position_amount_diff",
                }
            )
    return rows


def compare_position_maps(left_positions, right_positions, left_name, right_name):
    dates = sorted(set(left_positions) | set(right_positions))
    rows = []
    for date in dates:
        left = left_positions.get(date, {})
        right = right_positions.get(date, {})
        for code in sorted(set(left) | set(right)):
            left_value = left.get(code, {})
            right_value = right.get(code, {})
            left_amount = left_value.get("amount", 0) if isinstance(left_value, dict) else left_value
            right_amount = right_value.get("amount", 0) if isinstance(right_value, dict) else right_value
            if left_amount == right_amount:
                continue
            rows.append(
                {
                    "date": date,
                    "code": code,
                    f"{left_name}_amount": left_amount,
                    f"{right_name}_amount": right_amount,
                    "amount_diff": right_amount - left_amount,
                    "category": f"{left_name}_vs_{right_name}_position_diff",
                }
            )
    return rows


def write_csv(path, rows, fields):
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def nearby_trades(trades, center_date, window_days=1):
    center = parse_date(center_date)
    out = []
    for row in trades:
        day = parse_date(row["date"])
        if abs((day - center).days) <= window_days:
            out.append(row)
    return out


def main():
    parser = argparse.ArgumentParser(description="Locate JQ/local alignment differences without repairing them.")
    parser.add_argument("--jq-funds", default=str(DEFAULT_JQ_FUNDS))
    parser.add_argument("--jq-trades", default=str(DEFAULT_JQ_TRADES))
    parser.add_argument("--local-dir", default=str(DEFAULT_LOCAL_DIR))
    parser.add_argument("--start", default="2020-01-02")
    parser.add_argument("--end", default="2021-12-31")
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    args = parser.parse_args()

    start = parse_date(args.start)
    end = parse_date(args.end)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    jq_funds, jq_fund_positions = parse_jq_funds(Path(args.jq_funds), start, end)
    local_stats = parse_local_stats(local_stats_path(Path(args.local_dir)), start, end)
    daily_rows = compare_daily(jq_funds, local_stats)

    jq_trades = parse_trades(Path(args.jq_trades), start, end, "jq")
    local_trades = parse_trades(local_trades_path(Path(args.local_dir)), start, end, "local")
    all_dates = sorted(set(jq_funds) | set(local_stats))
    jq_trade_positions = reconstruct_positions(jq_trades, all_dates)
    local_positions = reconstruct_positions(local_trades, all_dates)
    position_rows = compare_positions(jq_fund_positions, local_positions)
    jq_fund_quality_rows = compare_position_maps(jq_fund_positions, jq_trade_positions, "jq_fund", "jq_trade")
    jq_missing_cash_rows = [
        {
            "date": date,
            "issue": "missing_cash_row",
            "total_value": row["total_value"],
            "cash": row["cash"],
        }
        for date, row in sorted(jq_funds.items())
        if not row.get("has_cash")
    ]

    first_value_diff = next((r for r in daily_rows if abs(r["total_diff"]) > 0.01), None)
    first_cash_diff = next((r for r in daily_rows if abs(r["cash_diff"]) > 0.01), None)
    first_position_diff = position_rows[0] if position_rows else None

    daily_path = out_dir / f"alignment_daily_value_diffs_{args.start}_{args.end}.csv"
    write_csv(
        daily_path,
        daily_rows,
        [
            "date",
            "jq_total",
            "local_total",
            "total_diff",
            "total_diff_pct",
            "jq_cash",
            "local_cash",
            "cash_diff",
            "jq_positions_value",
            "local_positions_value",
            "positions_value_diff",
        ],
    )

    pos_path = out_dir / f"alignment_position_diffs_{args.start}_{args.end}.csv"
    write_csv(pos_path, position_rows, ["date", "code", "jq_amount", "local_amount", "amount_diff", "category"])

    jq_quality_path = out_dir / f"jq_fund_quality_issues_{args.start}_{args.end}.csv"
    write_csv(
        jq_quality_path,
        jq_fund_quality_rows,
        ["date", "code", "jq_fund_amount", "jq_trade_amount", "amount_diff", "category"],
    )

    jq_missing_cash_path = out_dir / f"jq_fund_missing_cash_{args.start}_{args.end}.csv"
    write_csv(jq_missing_cash_path, jq_missing_cash_rows, ["date", "issue", "total_value", "cash"])

    report_path = out_dir / f"alignment_diff_investigation_{args.start}_{args.end}.md"
    with report_path.open("w", encoding="utf-8") as f:
        f.write(f"# Alignment Difference Investigation {args.start} to {args.end}\n\n")
        f.write("This report locates differences only. It does not attempt any repair.\n\n")
        f.write("## First Divergences\n\n")
        last_jq_fund_date = max(jq_funds) if jq_funds else ""
        last_jq_trade_date = max((row["date"] for row in jq_trades), default="")
        f.write(f"- Last JQ fund date: `{last_jq_fund_date}`\n")
        f.write(f"- Last JQ trade date: `{last_jq_trade_date}`\n")
        if last_jq_fund_date and last_jq_trade_date and last_jq_fund_date < last_jq_trade_date:
            f.write("- JQ fund record is truncated before the last JQ trade date.\n")
        if jq_missing_cash_rows:
            f.write(f"- JQ fund dates missing Cash row: {len(jq_missing_cash_rows)}; first `{jq_missing_cash_rows[0]['date']}`\n")
        if jq_fund_quality_rows:
            first_quality = jq_fund_quality_rows[0]
            f.write(
                "- First JQ fund-vs-trade position mismatch: `{date}` `{code}` fund={jq_fund_amount} trade={jq_trade_amount} diff={amount_diff}\n".format(
                    **first_quality
                )
            )
        if first_value_diff:
            f.write(
                "- First total value diff: `{date}` local-jq={total_diff:.2f} ({total_diff_pct:.4%}); "
                "cash_diff={cash_diff:.2f}; positions_value_diff={positions_value_diff:.2f}\n".format(**first_value_diff)
            )
        else:
            f.write("- First total value diff: none above 0.01\n")
        if first_cash_diff:
            f.write("- First cash diff: `{date}` local-jq={cash_diff:.2f}\n".format(**first_cash_diff))
        else:
            f.write("- First cash diff: none above 0.01\n")
        if first_position_diff:
            f.write(
                "- First position amount diff: `{date}` `{code}` jq={jq_amount} local={local_amount} diff={amount_diff}\n".format(
                    **first_position_diff
                )
            )
        else:
            f.write("- First position amount diff: none\n")

        f.write("\n## Largest Total Value Differences\n\n")
        if jq_missing_cash_rows or jq_fund_quality_rows:
            f.write("Warning: some large total-value differences may be caused by JQ fund export quality issues listed above.\n\n")
        top_value = sorted(daily_rows, key=lambda r: abs(r["total_diff"]), reverse=True)[:20]
        f.write("| date | jq_total | local_total | local-jq | diff_pct | cash_diff | position_value_diff |\n")
        f.write("|---|---:|---:|---:|---:|---:|---:|\n")
        for row in top_value:
            f.write(
                "| {date} | {jq_total:.2f} | {local_total:.2f} | {total_diff:.2f} | {total_diff_pct:.4%} | {cash_diff:.2f} | {positions_value_diff:.2f} |\n".format(
                    **row
                )
            )

        f.write("\n## First Position Differences\n\n")
        f.write("| date | code | jq_amount | local_amount | amount_diff |\n")
        f.write("|---|---|---:|---:|---:|\n")
        for row in position_rows[:50]:
            f.write(
                "| {date} | {code} | {jq_amount} | {local_amount} | {amount_diff} |\n".format(**row)
            )

        if first_value_diff:
            center = first_value_diff["date"]
            f.write(f"\n## Trades Near First Total Value Diff ({center})\n\n")
            f.write("### JQ\n\n")
            f.write("| time | code | action | amount | price |\n|---|---|---|---:|---:|\n")
            for row in nearby_trades(jq_trades, center):
                f.write("| {time} | {code} | {action} | {amount} | {price:.2f} |\n".format(**row))
            f.write("\n### Local\n\n")
            f.write("| time | code | action | amount | price |\n|---|---|---|---:|---:|\n")
            for row in nearby_trades(local_trades, center):
                f.write("| {time} | {code} | {action} | {amount} | {price:.2f} |\n".format(**row))

        f.write("\n## Artifacts\n\n")
        f.write(f"- Daily value diffs: `{daily_path}`\n")
        f.write(f"- Position diffs: `{pos_path}`\n")
        f.write(f"- JQ fund-vs-trade quality issues: `{jq_quality_path}`\n")
        f.write(f"- JQ fund missing Cash rows: `{jq_missing_cash_path}`\n")

    print(f"report={report_path}")
    print(f"daily_diffs={daily_path}")
    print(f"position_diffs={pos_path}")
    if first_value_diff:
        print(
            "first_value_diff={date} total_diff={total_diff:.2f} cash_diff={cash_diff:.2f} positions_value_diff={positions_value_diff:.2f}".format(
                **first_value_diff
            )
        )
    if first_position_diff:
        print(
            "first_position_diff={date} {code} jq={jq_amount} local={local_amount} diff={amount_diff}".format(
                **first_position_diff
            )
        )
    print(f"jq_fund_quality_issues={len(jq_fund_quality_rows)} missing_cash_dates={len(jq_missing_cash_rows)}")


if __name__ == "__main__":
    main()
