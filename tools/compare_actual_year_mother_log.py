from __future__ import annotations

import argparse
import csv
import re
import zipfile
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CODE_RE = r"\d{6}\.(?:XSHE|XSHG)"
DATE_RE = re.compile(r"\[?(\d{4}-\d{2}-\d{2})\s+((?:\d{1,2}:\d{2})(?::\d{2})?|every_bar)\]?")
BUY_LABELS = (
    ("v227", re.compile(r"\[v227买\]\s+(?P<code>" + CODE_RE + r")")),
    ("scorpion", re.compile(r"\[天蝎座\]\s+(?P<code>" + CODE_RE + r")")),
    ("rzq", re.compile(r"\[rzq买\]\s+(?P<code>" + CODE_RE + r")")),
    ("zb", re.compile(r"\[zb买\]\s+(?P<code>" + CODE_RE + r")")),
    ("auction", re.compile(r"\[竞价买\]\s+(?P<code>" + CODE_RE + r")")),
)
SELL_LINE_RE = re.compile(r"\[(?P<label>[^\]]+)\]\s+(?P<code>" + CODE_RE + r")\s+(?:ret=)?[+\-]?\d+(?:\.\d+)?%")
TRAILING_SELL_RE = re.compile(r"\[(?P<label>[^\]]+)\]\s+(?P<code>" + CODE_RE + r").*\bhigh=[+\-]?\d+(?:\.\d+)?%\s+now=[+\-]?\d+(?:\.\d+)?%")
BULL_FORCE_RE = re.compile(r"\[bull强清\]\s+\d+笔:\s*(?P<body>.*)")
BULL_FORCE_ITEM_RE = re.compile(r"(?P<code>" + CODE_RE + r")\s+[+\-]?\d+(?:\.\d+)?%")
SKIP_LABELS = {"v227买", "天蝎座", "rzq买", "zb买", "竞价买", "BIG_TRADE", "REGIME", "DEBUG"}
SELL_KEYWORDS = ("卖", "止盈", "午撤", "尾盘清", "止损", "跌停打开清", "线性回落", "落袋", "MA5", "龙头出局", "盈利回落", "强清")


def norm_time(value: str) -> str:
    value = (value or "").strip().replace(" every_bar", " 09:30:00").replace(" 9:", " 09:")
    if len(value) == 16:
        value += ":00"
    return value


def read_text(path: Path) -> str:
    if path.suffix.lower() == ".zip":
        with zipfile.ZipFile(path) as zf:
            names = [name for name in zf.namelist() if not name.endswith("/")]
            if not names:
                raise ValueError("zip has no file entries: %s" % path)
            entry = "log.txt" if "log.txt" in names else names[0]
            raw = zf.read(entry)
    else:
        raw = path.read_bytes()
    for enc in ("utf-8-sig", "utf-8", "gbk"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            pass
    return raw.decode("utf-8", errors="replace")


def drop_unmatched_sells(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    """Drop residual exit log lines that have no parsed open position.

    Some archived mother-log exits are stale bookkeeping lines after an earlier
    full exit, e.g. BIG_TRADE branch=unknown_v227 entry=NA pnl=-0 followed by a
    stop-loss label.  They are useful diagnostics, but not actual trade keys.
    """
    open_counts: dict[str, int] = defaultdict(int)
    filtered: list[dict[str, str]] = []
    for row in sorted(rows, key=lambda r: (r["time"], r["line"], r["code"], r["action"])):
        code = row["code"]
        if row["action"] == "buy":
            open_counts[code] += 1
            filtered.append(row)
            continue
        if open_counts[code] <= 0:
            continue
        open_counts[code] -= 1
        filtered.append(row)
    filtered.sort(key=lambda r: (r["time"], r["code"], r["action"], r["branch"], r["line"]))
    return filtered


def parse_mother_events(path: Path, year: int) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for line_no, line in enumerate(read_text(path).splitlines(), 1):
        dt = DATE_RE.match(line)
        if not dt:
            continue
        date, time = dt.group(1), dt.group(2)
        if time == "every_bar":
            time = "09:30:00"
        if len(time) == 4:
            time = "0" + time
        if len(time) == 5:
            time += ":00"
        if date[:4] != str(year):
            continue
        stamp = f"{date} {time}"

        for branch, pat in BUY_LABELS:
            m = pat.search(line)
            if m:
                rows.append({"time": stamp, "code": m.group("code"), "action": "buy", "branch": branch, "line": str(line_no), "source_label": branch})
                break

        bf = BULL_FORCE_RE.search(line)
        if bf:
            for item in BULL_FORCE_ITEM_RE.finditer(bf.group("body")):
                rows.append({"time": stamp, "code": item.group("code"), "action": "sell", "branch": "bull强清", "line": str(line_no), "source_label": "bull强清"})
            continue

        sm = SELL_LINE_RE.search(line) or TRAILING_SELL_RE.search(line)
        if not sm:
            continue
        label = sm.group("label")
        if label in SKIP_LABELS:
            continue
        if not any(k in label for k in SELL_KEYWORDS):
            continue
        rows.append({"time": stamp, "code": sm.group("code"), "action": "sell", "branch": label, "line": str(line_no), "source_label": label})

    rows.sort(key=lambda r: (r["time"], r["code"], r["action"], r["branch"], r["line"]))
    return rows


def parse_local_csv_events(path: Path, year: int) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            time = norm_time(r["time"])
            if time[:4] != str(year):
                continue
            amount = int(float(r["amount"]))
            rows.append({"time": time, "code": r["code"], "action": "buy" if amount > 0 else "sell", "branch": "", "amount": str(abs(amount)), "price": r.get("price", "")})
    rows.sort(key=lambda r: (r["time"], r["code"], r["action"]))
    return rows


def key(row: dict[str, str]) -> tuple[str, str, str, str]:
    branch = row.get("branch", "") if row.get("action") == "buy" else ""
    return (row["time"][:10], row["code"], row["action"], branch)


def compare(jq: list[dict[str, str]], local: list[dict[str, str]]) -> list[dict[str, str]]:
    jb: dict[tuple[str, str, str, str], list[dict[str, str]]] = defaultdict(list)
    lb: dict[tuple[str, str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in jq:
        jb[key(row)].append(row)
    for row in local:
        lb[key(row)].append(row)

    out: list[dict[str, str]] = []
    for k in sorted(set(jb) | set(lb)):
        n = max(len(jb.get(k, [])), len(lb.get(k, [])))
        for i in range(n):
            j = jb.get(k, [])[i] if i < len(jb.get(k, [])) else None
            l = lb.get(k, [])[i] if i < len(lb.get(k, [])) else None
            out.append({
                "date": k[0],
                "code": k[1],
                "action": k[2],
                "branch_key": k[3],
                "side": "both" if j and l else ("missing" if j else "extra"),
                "jq_time": j.get("time", "") if j else "",
                "local_time": l.get("time", "") if l else "",
                "jq_branch": j.get("branch", "") if j else "",
                "local_branch": l.get("branch", "") if l else "",
                "jq_line": j.get("line", "") if j else "",
                "local_line": l.get("line", "") if l else "",
                "local_amount": l.get("amount", "") if l else "",
                "local_price": l.get("price", "") if l else "",
            })
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("year", type=int)
    parser.add_argument("local_dir", type=Path)
    parser.add_argument("--mother-log", type=Path, default=ROOT / "母版2024交易日志.txt")
    parser.add_argument("--local-log", type=Path, default=None)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--drop-unmatched-sells", action="store_true")
    args = parser.parse_args()

    local_path = args.local_dir / f"local_trades_{args.year}.csv"
    jq = parse_mother_events(args.mother_log, args.year)
    local = parse_mother_events(args.local_log, args.year) if args.local_log else parse_local_csv_events(local_path, args.year)
    if args.drop_unmatched_sells:
        jq = drop_unmatched_sells(jq)
        if args.local_log:
            local = drop_unmatched_sells(local)
    rows = compare(jq, local)

    out_path = args.out or ROOT / f"compare_actual_{args.year}_{args.local_dir.name}_mother_log_by_key.csv"
    with out_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else ["date", "code", "action", "side"])
        writer.writeheader()
        writer.writerows(rows)

    missing = [r for r in rows if r["side"] == "missing"]
    extra = [r for r in rows if r["side"] == "extra"]
    both = [r for r in rows if r["side"] == "both"]
    print(f"YEAR={args.year} mother={len(jq)} local={len(local)} both={len(both)} missing={len(missing)} extra={len(extra)}")
    print(f"compare_csv={out_path}")
    print("missing:")
    for row in missing[:80]:
        print(row)
    if len(missing) > 80:
        print(f"... {len(missing) - 80} more")
    print("extra:")
    for row in extra[:80]:
        print(row)
    if len(extra) > 80:
        print(f"... {len(extra) - 80} more")


if __name__ == "__main__":
    main()




