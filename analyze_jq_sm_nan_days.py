import csv
import html
import json
import math
import re
from pathlib import Path


ROOT = Path(r"D:\Work Space\他山之石\情绪门控")
JQ_SM_LOG = Path(r"D:\work space\local_quant\research\temp\unzipped_diary\20200101-20201231状态机日志\log.txt")
LOCAL_COMPARE = ROOT / "compare_localquant_state_2020.csv"
OUT_NAN = ROOT / "jq_sm_nan_days_2020.csv"
OUT_MISMATCH = ROOT / "jq_sm_nan_local_mismatch_2020.csv"


STATE_RE = re.compile(r"\[SM-STATE\]\s+(\{.*\})")
PFB_RE = re.compile(r"\[SM-PFB\]\s+(\d{8})\s+\d{2}:\d{2}:\d{2}\s+n=(\d+)\s+list=(.*)$")


def parse_float(value):
    if value is None or value == "":
        return math.nan
    try:
        return float(value)
    except ValueError:
        return math.nan


def load_local_compare():
    rows = {}
    if not LOCAL_COMPARE.exists():
        return rows
    with LOCAL_COMPARE.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            rows[row["date"]] = row
    return rows


def main():
    pfb_by_date = {}
    prepare_states = {}

    with JQ_SM_LOG.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line = html.unescape(line.rstrip("\n"))
            m = PFB_RE.search(line)
            if m:
                ymd, n, code_list = m.groups()
                date = f"{ymd[:4]}-{ymd[4:6]}-{ymd[6:]}"
                codes = [c for c in code_list.split(",") if c]
                pfb_by_date[date] = {"pfb_n": int(n), "pfb_codes": codes}
                continue

            m = STATE_RE.search(line)
            if not m:
                continue
            try:
                state = json.loads(m.group(1))
            except json.JSONDecodeError:
                continue
            if state.get("stage") != "prepare_all:after":
                continue
            dt = state.get("dt", "")
            if len(dt) < 8:
                continue
            date = f"{dt[:4]}-{dt[4:6]}-{dt[6:8]}"
            prepare_states[date] = state

    local = load_local_compare()
    nan_rows = []
    mismatch_rows = []
    pfb_dates = sorted(pfb_by_date)

    for date in sorted(prepare_states):
        state = prepare_states[date]
        fb = state.get("first_board_perf")
        is_nan = isinstance(fb, float) and math.isnan(fb)
        if not is_nan:
            continue

        prev_pfb_date = ""
        for pfb_date in pfb_dates:
            if pfb_date < date:
                prev_pfb_date = pfb_date
            else:
                break
        pfb = pfb_by_date.get(prev_pfb_date, {"pfb_n": "", "pfb_codes": []})
        codes = pfb["pfb_codes"]
        new_605 = [c for c in codes if c.startswith("605")]
        row = {
            "date": date,
            "calc_pfb_date": prev_pfb_date,
            "jq_mode": state.get("market_mode", ""),
            "jq_raw_mode": state.get("raw_market_mode", ""),
            "jq_active": state.get("route_active") or state.get("active", ""),
            "jq_fb_pct": state.get("fb_pct", ""),
            "jq_fb_hist_len": state.get("fb_hist_len", ""),
            "jq_prev_first_n": state.get("prev_first_n", ""),
            "pfb_n": pfb["pfb_n"],
            "has_605": bool(new_605),
            "codes_605": "|".join(new_605),
            "pfb_codes": "|".join(codes),
        }
        nan_rows.append(row)

        cmp_row = local.get(date)
        if cmp_row:
            row2 = dict(row)
            row2.update(
                {
                    "local_mode": cmp_row.get("market_mode_local", ""),
                    "local_active": cmp_row.get("active_local", ""),
                    "local_fb_perf": cmp_row.get("FB_local", ""),
                    "local_fb_pct": cmp_row.get("fb_pct_local", ""),
                    "fb_pct_diff": cmp_row.get("pct_diff", ""),
                    "mode_match": cmp_row.get("mode_match", ""),
                    "active_match": cmp_row.get("active_match", ""),
                }
            )
            mismatch_rows.append(row2)

    fieldnames = [
        "date",
        "calc_pfb_date",
        "jq_mode",
        "jq_raw_mode",
        "jq_active",
        "jq_fb_pct",
        "jq_fb_hist_len",
        "jq_prev_first_n",
        "pfb_n",
        "has_605",
        "codes_605",
        "pfb_codes",
    ]
    with OUT_NAN.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(nan_rows)

    mismatch_fields = fieldnames + [
        "local_mode",
        "local_active",
        "local_fb_perf",
        "local_fb_pct",
        "fb_pct_diff",
        "mode_match",
        "active_match",
    ]
    with OUT_MISMATCH.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=mismatch_fields)
        writer.writeheader()
        writer.writerows(mismatch_rows)

    print(f"prepare_states={len(prepare_states)} pfb_days={len(pfb_by_date)}")
    print(f"nan_days={len(nan_rows)} with_605={sum(1 for r in nan_rows if r['has_605'])}")
    print(f"wrote {OUT_NAN}")
    print(f"wrote {OUT_MISMATCH}")
    for row in mismatch_rows[:10]:
        print(
            row["date"],
            "jq",
            row["jq_mode"],
            row["jq_active"],
            "local",
            row["local_mode"],
            row["local_active"],
            "local_fb",
            row["local_fb_perf"],
            "local_pct",
            row["local_fb_pct"],
            "605",
            row["codes_605"],
        )


if __name__ == "__main__":
    main()
