import csv
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DETAIL = ROOT / "alignment_reports" / "align_trade_detail_2020-01-02_2021-12-31.csv"
DAILY = ROOT / "alignment_reports" / "alignment_daily_value_diffs_2020-01-02_2021-12-31.csv"
OUT = ROOT / "alignment_reports" / "amount_diff_root_causes_2020-2021.md"


def load_csv(path):
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def fnum(value):
    if value in ("", None):
        return 0.0
    return float(value)


def main():
    detail = load_csv(DETAIL)
    daily = {row["date"]: row for row in load_csv(DAILY)}
    diffs = [row for row in detail if row["category"] in ("data_diff_amount", "data_diff_price")]
    amount_buys = [row for row in diffs if row["category"] == "data_diff_amount" and row["action"] == "buy"]
    price_rows = [row for row in diffs if row["category"] == "data_diff_price"]

    by_month = defaultdict(lambda: {"amount_buy": 0, "price": 0, "max_abs_amount_diff": 0.0})
    for row in amount_buys:
        key = row["date"][:7]
        by_month[key]["amount_buy"] += 1
        by_month[key]["max_abs_amount_diff"] = max(by_month[key]["max_abs_amount_diff"], abs(fnum(row["amount_diff"])))
    for row in price_rows:
        by_month[row["date"][:7]]["price"] += 1

    first_amount = amount_buys[0] if amount_buys else None
    first_price = price_rows[0] if price_rows else None

    # Identify the preceding price/cash drift nearest to the first amount mismatch.
    prior_price = []
    if first_amount:
        first_date = first_amount["date"]
        prior_price = [row for row in price_rows if row["date"] <= first_date][-10:]

    with OUT.open("w", encoding="utf-8") as f:
        f.write("# Amount/Price Difference Root-Cause Notes\n\n")
        f.write("This is diagnostic only. No repair was attempted.\n\n")
        f.write("## Summary\n\n")
        f.write(f"- Matched trades with amount differences: {sum(1 for r in diffs if r['category'] == 'data_diff_amount')}\n")
        f.write(f"- Buy-side amount differences: {len(amount_buys)}\n")
        f.write(f"- Matched trades with price differences: {len(price_rows)}\n")
        if first_price:
            f.write(
                "- First price mismatch: `{date}` `{code}` `{action}` JQ={jq_price} local={local_price} diff={price_diff}\n".format(
                    **first_price
                )
            )
        if first_amount:
            f.write(
                "- First buy amount mismatch: `{date}` `{code}` JQ={jq_amount} local={local_amount} diff={amount_diff}; price JQ={jq_price} local={local_price}\n".format(
                    **first_amount
                )
            )
            d = daily.get(first_amount["date"])
            if d:
                f.write(
                    "- Same-day portfolio drift at first amount mismatch: total_diff={:.2f}, cash_diff={:.2f}, positions_value_diff={:.2f}\n".format(
                        fnum(d["total_diff"]), fnum(d["cash_diff"]), fnum(d["positions_value_diff"])
                    )
                )
        f.write("\n## Concrete First Chain\n\n")
        f.write(
            "The first material share-count divergence is `2020-07-16 601216.XSHG`: JQ bought 212800 shares, local bought 212900 shares.\n\n"
        )
        f.write(
            "The immediate upstream cause is the previous day's `600502.XSHG` sell price: JQ sold at 4.66, local sold at 4.67. "
            "With 89700 shares, this creates about 897 yuan extra local proceeds before fees. "
            "At `601216.XSHG` price 3.48, one lot costs about 348 yuan, so this cash drift is sufficient to cross one 100-share lot boundary.\n\n"
        )
        f.write("Relevant nearby rows:\n\n")
        f.write("| date | code | action | category | jq_amount | local_amount | amount_diff | jq_price | local_price | price_diff |\n")
        f.write("|---|---|---|---|---:|---:|---:|---:|---:|---:|\n")
        nearby_codes = {"600502.XSHG", "601216.XSHG", "002626.XSHE", "600685.XSHG"}
        for row in detail:
            if "2020-07-15" <= row["date"] <= "2020-07-17" and row["code"] in nearby_codes:
                f.write(
                    "| {date} | {code} | {action} | {category} | {jq_amount} | {local_amount} | {amount_diff} | {jq_price} | {local_price} | {price_diff} |\n".format(
                        **row
                    )
                )

        f.write("\n## Pattern Classification\n\n")
        f.write("- Early share-count differences are mostly 100-share boundary effects after small cash/price drifts.\n")
        f.write("- A single 0.01 execution price difference on a large position can create enough cash drift to change the next buy by one or more lots.\n")
        f.write("- Once cash differs, later `order_value` sizing will keep producing amount differences even when signal, code, direction, and nominal price match.\n")
        f.write("- Larger late-2021 gaps are mixed with true key mismatches and incomplete JQ fund export, so they must be reviewed separately from early rounding drift.\n")

        f.write("\n## Monthly Concentration\n\n")
        f.write("| month | buy amount diffs | price diffs | max abs amount diff |\n")
        f.write("|---|---:|---:|---:|\n")
        for month in sorted(by_month):
            row = by_month[month]
            f.write(f"| {month} | {row['amount_buy']} | {row['price']} | {row['max_abs_amount_diff']:.0f} |\n")

        f.write("\n## Prior Price Differences Before First Amount Mismatch\n\n")
        f.write("| date | code | action | jq_price | local_price | price_diff |\n")
        f.write("|---|---|---|---:|---:|---:|\n")
        for row in prior_price:
            f.write("| {date} | {code} | {action} | {jq_price} | {local_price} | {price_diff} |\n".format(**row))

    print(f"wrote={OUT}")


if __name__ == "__main__":
    main()
