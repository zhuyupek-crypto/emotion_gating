import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LOCAL = ROOT / "alignment_reports" / "probe_local_20240411_rzq_zb.json"
DEFAULT_JQ = ROOT / "alignment_reports" / "probe_jq_20240411_rzq_zb.json"

FIELDS = [
    "yclose",
    "open",
    "ratio",
    "paused",
    "last_price",
    "high_limit",
    "low_limit",
    "ratio_ok",
    "not_limit",
    "auction_rows",
    "buy_m",
    "sell_m",
    "auction_ok",
    "turnover_ratio",
    "market_cap",
    "circulating_market_cap",
    "score",
]


def load_json(path):
    with Path(path).open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def code_set(data, key):
    return set(data.get(key) or [])


def gate_map(data, key):
    out = {}
    for row in data.get(key) or []:
        code = row.get("code")
        if code:
            out[code] = row
    return out


def pass_codes(data, key):
    return [row.get("code") for row in data.get(key) or [] if row.get("code")]


def fmt_val(v):
    if isinstance(v, float):
        return f"{v:.6g}"
    return repr(v)


def numeric_diff(a, b, tol):
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(float(a) - float(b)) > tol
    return a != b


def print_set_diff(title, local_values, jq_values):
    only_local = sorted(local_values - jq_values)
    only_jq = sorted(jq_values - local_values)
    print(f"\n== {title} ==")
    print(f"local={len(local_values)} jq={len(jq_values)} common={len(local_values & jq_values)}")
    if only_local:
        print("local_only:", ", ".join(only_local))
    if only_jq:
        print("jq_only:", ", ".join(only_jq))
    if not only_local and not only_jq:
        print("same")


def compare_gate(title, local_rows, jq_rows, tol):
    print(f"\n== {title} gate rows ==")
    local_codes = set(local_rows)
    jq_codes = set(jq_rows)
    print_set_diff(f"{title} gate code set", local_codes, jq_codes)
    for code in sorted(local_codes & jq_codes):
        diffs = []
        lrow = local_rows[code]
        jrow = jq_rows[code]
        for field in FIELDS:
            lv = lrow.get(field)
            jv = jrow.get(field)
            if numeric_diff(lv, jv, tol):
                diffs.append(f"{field}: local={fmt_val(lv)} jq={fmt_val(jv)}")
        if diffs:
            print(f"\n{code}")
            for diff in diffs:
                print("  " + diff)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--local", default=str(DEFAULT_LOCAL))
    parser.add_argument("--jq", default=str(DEFAULT_JQ))
    parser.add_argument("--tol", type=float, default=1e-6)
    args = parser.parse_args()

    local = load_json(args.local)
    jq = load_json(args.jq)

    print("local:", args.local)
    print("jq:", args.jq)
    print("dates:", local.get("prev_day"), local.get("buy_day"), "vs", jq.get("prev_day"), jq.get("buy_day"))

    print_set_diff("rzq_prepare_valid", code_set(local, "rzq_prepare_valid"), code_set(jq, "rzq_prepare_valid"))
    print_set_diff("zb_prepare_valid", code_set(local, "zb_prepare_valid"), code_set(jq, "zb_prepare_valid"))
    print_set_diff("rzq_pass", set(pass_codes(local, "rzq_pass")), set(pass_codes(jq, "rzq_pass")))
    print_set_diff("zb_pass", set(pass_codes(local, "zb_pass")), set(pass_codes(jq, "zb_pass")))

    compare_gate("rzq", gate_map(local, "rzq_gate"), gate_map(jq, "rzq_gate"), args.tol)
    compare_gate("zb", gate_map(local, "zb_gate"), gate_map(jq, "zb_gate"), args.tol)


if __name__ == "__main__":
    main()