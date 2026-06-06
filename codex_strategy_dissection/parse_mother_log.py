from __future__ import annotations

import argparse
import csv
import re
import statistics
import zipfile
from collections import defaultdict, deque
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LOG_ZIP = ROOT / "母版2020-2026日志.zip"
OUT_DIR = Path(__file__).resolve().parent / "outputs"


CODE_PAT = r"(\d{6}\.(?:XSHE|XSHG|SZ|SH))"


def label_pattern(label: str) -> re.Pattern[str]:
    return re.compile(r"\[" + re.escape(label) + r"\]\s+" + CODE_PAT)


BUY_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("v227_yjj", label_pattern("v227买")),
    ("v227_scorpion", label_pattern("天蝎座")),
    ("rzq", label_pattern("rzq买")),
    ("zb", label_pattern("zb买")),
    (
        "auction",
        re.compile(r"\[" + re.escape("竞价买") + r"\]\s+" + CODE_PAT + r"\s+(\S+)\s+auction="),
    ),
]

SELL_RE = re.compile(r"\[([^\]]+)\]\s+" + CODE_PAT + r"\s+(?:ret=)?([+\-]?\d+(?:\.\d+)?)%")
DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2}:\d{2})")
STATE_LINE_RE = re.compile(r"\[STATE\]\s+date=(?P<date>\d{4}-\d{2}-\d{2})\s+\|\s+(?P<body>.*)")
V227_CANDS_RE = re.compile(
    r"\[V227_CANDS\]\s+date=(?P<date>\d{4}-\d{2}-\d{2})\s+\|\s+"
    r"yjj=(?P<yjj>.*?)\s+\|\s+bear=(?P<bear>.*)"
)
STATUS_RE = re.compile(
    r"模式=(?P<mode>\S+)\s+\|\s+FB(?P<fb_text>[+\-]?\d+(?:\.\d+)?)%\s+\|\s+"
    r"pct=(?P<pct>[+\-]?\d+(?:\.\d+)?)\s+\|\s+活跃=(?P<active>\S+)"
)

SKIP_SELL_LABELS = {"v227买", "天蝎座", "rzq买", "zb买", "竞价买"}
SELL_KEYS = (
    "卖",
    "止盈",
    "午撤",
    "尾盘清",
    "止损",
    "跌停打开清",
    "线性回落",
    "落袋",
    "MA5",
    "龙头出局",
    "盈利回落",
    "强清",
)


def read_log_text(path: Path) -> tuple[str, str, str]:
    if path.suffix.lower() == ".zip":
        with zipfile.ZipFile(path) as zf:
            names = [name for name in zf.namelist() if not name.endswith("/")]
            if not names:
                raise ValueError(f"No file entries in {path}")
            entry = "log.txt" if "log.txt" in names else names[0]
            raw = zf.read(entry)
        source_name = f"{path.name}:{entry}"
    else:
        raw = path.read_bytes()
        source_name = path.name

    for enc in ("gbk", "utf-8-sig", "utf-8"):
        try:
            return raw.decode(enc), source_name, enc
        except UnicodeDecodeError:
            continue
    return raw.decode("gbk", errors="replace"), source_name, "gbk-replace"


def parse_list(text: str) -> list[str]:
    text = text.strip()
    if not text:
        return []
    return [part.strip() for part in text.split(",") if part.strip()]


def infer_branch_from_label(label: str) -> str:
    if label.startswith("rzq"):
        return "rzq"
    if label.startswith("zb"):
        return "zb"
    if label.startswith("竞价"):
        return "auction_unknown"
    if label.startswith("v227") or label.startswith("龙头"):
        return "v227_unknown"
    return "unknown"


def pct_bucket(value: float | None) -> str:
    if value is None:
        return "unknown"
    if value <= 0.2:
        return "<=20%"
    if value <= 0.4:
        return "20-40%"
    if value <= 0.6:
        return "40-60%"
    if value <= 0.8:
        return "60-80%"
    return ">80%"


def rank_bucket(value: object) -> str:
    try:
        rank = int(value)
    except (TypeError, ValueError):
        return "unknown"
    if rank <= 1:
        return "rank_1"
    if rank <= 2:
        return "rank_2"
    if rank <= 5:
        return "rank_3_5"
    return "rank_gt5"


def signal_bucket(kind: object, value: object) -> str:
    try:
        signal = float(value)
    except (TypeError, ValueError):
        return "unknown"
    kind_text = str(kind)
    if kind_text == "open_pct":
        if signal < -4:
            return "open_<-4%"
        if signal < -2:
            return "open_-4~-2%"
        if signal < 0:
            return "open_-2~0%"
        if signal < 2:
            return "open_0~2%"
        if signal < 4:
            return "open_2~4%"
        if signal < 6:
            return "open_4~6%"
        return "open_>=6%"
    if kind_text in {"op_yc", "auction_ratio"}:
        gap = signal - 1.0
        if gap < -0.04:
            return "ratio_<-4%"
        if gap < -0.02:
            return "ratio_-4~-2%"
        if gap < 0:
            return "ratio_-2~0%"
        if gap < 0.02:
            return "ratio_0~2%"
        if gap < 0.04:
            return "ratio_2~4%"
        if gap < 0.06:
            return "ratio_4~6%"
        return "ratio_>=6%"
    return "unknown"


def parse_scalar(text: str) -> object:
    text = text.strip()
    if text == "True":
        return True
    if text == "False":
        return False
    try:
        if re.fullmatch(r"[+\-]?\d+", text):
            return int(text)
        if re.fullmatch(r"[+\-]?\d+(?:\.\d+)?", text):
            return float(text)
    except ValueError:
        pass
    return text


def parse_named_counts(text: str) -> dict[str, int]:
    out: dict[str, int] = {}
    for part in text.split(","):
        if ":" not in part:
            continue
        key, value = part.split(":", 1)
        try:
            out[key.strip()] = int(float(value.strip()))
        except ValueError:
            continue
    return out


def parse_state_line(line: str) -> tuple[str, dict[str, object]] | None:
    match = STATE_LINE_RE.search(line)
    if not match:
        return None

    date = match.group("date")
    state: dict[str, object] = {}
    for part in match.group("body").split("|"):
        part = part.strip()
        if not part or "=" not in part:
            continue
        key, value = part.split("=", 1)
        key = key.strip()
        value = value.strip()
        if key == "FB":
            key = "fb_perf"
        elif key == "slots":
            for slot_key, slot_value in parse_named_counts(value).items():
                state[f"slot_{slot_key}"] = slot_value
            continue
        elif key == "cands":
            for cand_key, cand_value in parse_named_counts(value).items():
                state[f"{cand_key}_candidate_count"] = cand_value
            continue
        state[key] = parse_scalar(value)
    return date, state


def extract_buy_signal(branch: str, line: str) -> tuple[object, str]:
    if branch == "v227_yjj":
        match = re.search(r"开([+\-]?\d+(?:\.\d+)?)%", line)
        return (float(match.group(1)) if match else "", "open_pct")
    if branch == "v227_scorpion":
        match = re.search(r"低开([+\-]?\d+(?:\.\d+)?)%", line)
        return (float(match.group(1)) if match else "", "open_pct")
    if branch in {"rzq", "zb"}:
        match = re.search(r"op/yc=([+\-]?\d+(?:\.\d+)?)", line)
        return (float(match.group(1)) if match else "", "op_yc")
    if branch.startswith("auction_"):
        match = re.search(r"auction=([+\-]?\d+(?:\.\d+)?)", line)
        return (float(match.group(1)) if match else "", "auction_ratio")
    return "", ""


def candidate_rank(code: str, branch: str, cand: dict[str, object]) -> object:
    key = ""
    if branch == "v227_yjj":
        key = "yjj_candidates"
    elif branch == "v227_scorpion":
        key = "bear_candidates"
    if not key:
        return ""
    candidates_text = str(cand.get(key, ""))
    candidates = [item for item in candidates_text.split("|") if item]
    try:
        return candidates.index(code) + 1
    except ValueError:
        return ""


def summarize(rows: list[dict[str, object]], key: str) -> list[dict[str, object]]:
    grouped: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get(key, ""))].append(float(row["ret_pct"]))

    out = []
    for group_key, vals in grouped.items():
        wins = [v for v in vals if v > 0]
        losses = [v for v in vals if v < 0]
        gross_win = sum(wins)
        gross_loss = abs(sum(losses))
        out.append(
            {
                key: group_key,
                "trades": len(vals),
                "win_rate": len(wins) / len(vals) if vals else 0.0,
                "avg_ret_pct": sum(vals) / len(vals),
                "median_ret_pct": statistics.median(vals),
                "best_ret_pct": max(vals),
                "worst_ret_pct": min(vals),
                "profit_factor": gross_win / gross_loss if gross_loss else "",
            }
        )
    out.sort(key=lambda r: (float(r["avg_ret_pct"]), float(r["median_ret_pct"])), reverse=True)
    return out


def summarize_multi(rows: list[dict[str, object]], keys: list[str]) -> list[dict[str, object]]:
    grouped: dict[tuple[str, ...], list[float]] = defaultdict(list)
    for row in rows:
        grouped[tuple(str(row.get(key, "")) for key in keys)].append(float(row["ret_pct"]))

    out = []
    for group_key, vals in grouped.items():
        wins = [v for v in vals if v > 0]
        losses = [v for v in vals if v < 0]
        gross_win = sum(wins)
        gross_loss = abs(sum(losses))
        record: dict[str, object] = {key: value for key, value in zip(keys, group_key)}
        record.update(
            {
                "trades": len(vals),
                "win_rate": len(wins) / len(vals) if vals else 0.0,
                "avg_ret_pct": sum(vals) / len(vals),
                "median_ret_pct": statistics.median(vals),
                "best_ret_pct": max(vals),
                "worst_ret_pct": min(vals),
                "profit_factor": gross_win / gross_loss if gross_loss else "",
            }
        )
        out.append(record)
    out.sort(key=lambda r: (str(r[keys[0]]), float(r["avg_ret_pct"])), reverse=False)
    return out


def summarize_daily(rows: list[dict[str, object]], keys: list[str]) -> list[dict[str, object]]:
    grouped: dict[tuple[str, ...], list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        grouped[tuple(str(row.get(key, "")) for key in keys)].append(row)

    out = []
    for group_key, group_rows in grouped.items():
        record: dict[str, object] = {key: value for key, value in zip(keys, group_key)}
        record["days"] = len(group_rows)
        for count_key in (
            "yjj_candidate_count",
            "bear_candidate_count",
            "rzq_candidate_count",
            "zb_candidate_count",
            "auction_candidate_count",
        ):
            vals = []
            for row in group_rows:
                try:
                    vals.append(float(row.get(count_key, 0) or 0))
                except ValueError:
                    vals.append(0.0)
            record[f"avg_{count_key}"] = sum(vals) / len(vals) if vals else 0.0
            record[f"sum_{count_key}"] = int(sum(vals))
        out.append(record)
    out.sort(key=lambda r: (str(r[keys[0]]), str(r[keys[1]]) if len(keys) > 1 else ""))
    return out


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def parse_log(log_path: Path) -> tuple[list[dict[str, object]], list[dict[str, object]], dict[str, object]]:
    text, source_name, encoding = read_log_text(log_path)
    lines = text.splitlines()

    states: dict[str, dict[str, object]] = {}
    candidates: dict[str, dict[str, object]] = {}
    current_status: dict[str, object] = {}
    open_positions: dict[str, deque[dict[str, object]]] = defaultdict(deque)

    buys: list[dict[str, object]] = []
    trades: list[dict[str, object]] = []
    unmatched_sells: list[dict[str, object]] = []
    first_date = ""
    last_date = ""

    for line_no, line in enumerate(lines, start=1):
        date_match = DATE_RE.match(line)
        date = date_match.group(1) if date_match else ""
        time = date_match.group(2) if date_match else ""
        if date:
            if not first_date:
                first_date = date
            last_date = date

        parsed_state = parse_state_line(line)
        if parsed_state:
            state_date, state = parsed_state
            states[state_date] = state

        cand_match = V227_CANDS_RE.search(line)
        if cand_match:
            yjj = parse_list(cand_match.group("yjj"))
            bear = parse_list(cand_match.group("bear"))
            candidates[cand_match.group("date")] = {
                "yjj_candidates": "|".join(yjj),
                "bear_candidates": "|".join(bear),
                "yjj_candidate_count": len(yjj),
                "bear_candidate_count": len(bear),
            }

        status_match = STATUS_RE.search(line)
        if status_match and date:
            current_status[date] = {
                "status_mode": status_match.group("mode"),
                "status_active": status_match.group("active"),
                "status_fb_pct": float(status_match.group("pct")),
                "status_fb_perf_pct": float(status_match.group("fb_text")),
            }

        for branch, pattern in BUY_PATTERNS:
            buy_match = pattern.search(line)
            if not buy_match:
                continue
            code = buy_match.group(1)
            kind = buy_match.group(2) if branch == "auction" and len(buy_match.groups()) >= 2 else ""
            resolved_branch = branch if branch != "auction" else f"auction_{kind}"
            state = states.get(date, {})
            cand = candidates.get(date, {})
            buy_signal_value, buy_signal_kind = extract_buy_signal(resolved_branch, line)
            buy_row = {
                "buy_date": date,
                "buy_time": time,
                "code": code,
                "branch": resolved_branch,
                "buy_line": line_no,
                "buy_signal_kind": buy_signal_kind,
                "buy_signal_value": buy_signal_value,
                "candidate_rank": candidate_rank(code, resolved_branch, cand),
                **state,
                **cand,
            }
            open_positions[code].append(buy_row)
            buys.append(buy_row)
            break

        sell_match = SELL_RE.search(line)
        if not sell_match:
            continue
        label, code, ret_text = sell_match.groups()
        if label in SKIP_SELL_LABELS:
            continue
        if not any(key in label for key in SELL_KEYS):
            continue

        ret_pct = float(ret_text)
        if open_positions[code]:
            buy_row = open_positions[code].popleft()
            branch = str(buy_row["branch"])
            buy_date = str(buy_row["buy_date"])
            buy_time = str(buy_row["buy_time"])
            buy_line = int(buy_row["buy_line"])
        else:
            buy_row = {}
            branch = infer_branch_from_label(label)
            buy_date = ""
            buy_time = ""
            buy_line = 0
            unmatched_sells.append({"sell_date": date, "code": code, "sell_label": label, "ret_pct": ret_pct})

        fb_pct_value = buy_row.get("fb_pct")
        row = {
            "sell_date": date,
            "sell_time": time,
            "buy_date": buy_date,
            "buy_time": buy_time,
            "code": code,
            "branch": branch,
            "sell_label": label,
            "ret_pct": ret_pct,
            "ret": ret_pct / 100.0,
            "year": date[:4],
            "month": date[:7],
            "buy_line": buy_line,
            "sell_line": line_no,
            "market_mode": buy_row.get("market_mode", ""),
            "raw_market_mode": buy_row.get("raw_market_mode", ""),
            "active": buy_row.get("active", ""),
            "fb_perf": buy_row.get("fb_perf", ""),
            "fb_pct": fb_pct_value if fb_pct_value is not None else "",
            "fb_pct_bucket": pct_bucket(float(fb_pct_value)) if fb_pct_value not in (None, "") else "unknown",
            "bull_sticky": buy_row.get("bull_sticky", ""),
            "bull_cooldown": buy_row.get("bull_cooldown", ""),
            "bull_release_pending": buy_row.get("bull_release_pending", ""),
            "bull_release_guard": buy_row.get("bull_release_guard", ""),
            "stoploss_cooldown": buy_row.get("stoploss_cooldown", ""),
            "rzq_cooldown": buy_row.get("rzq_cooldown", ""),
            "v227_shock_cooldown": buy_row.get("v227_shock_cooldown", ""),
            "enable_v227": buy_row.get("enable_v227", ""),
            "enable_rzq": buy_row.get("enable_rzq", ""),
            "enable_zb": buy_row.get("enable_zb", ""),
            "enable_auction": buy_row.get("enable_auction", ""),
            "slot_v227": buy_row.get("slot_v227", ""),
            "slot_rzq": buy_row.get("slot_rzq", ""),
            "slot_zb": buy_row.get("slot_zb", ""),
            "slot_auction": buy_row.get("slot_auction", ""),
            "recent_wr": buy_row.get("recent_wr", ""),
            "core_wr": buy_row.get("core_wr", ""),
            "buy_signal_kind": buy_row.get("buy_signal_kind", ""),
            "buy_signal_value": buy_row.get("buy_signal_value", ""),
            "buy_signal_bucket": signal_bucket(buy_row.get("buy_signal_kind", ""), buy_row.get("buy_signal_value", "")),
            "candidate_rank": buy_row.get("candidate_rank", ""),
            "candidate_rank_bucket": rank_bucket(buy_row.get("candidate_rank", "")),
            "yjj_candidate_count": buy_row.get("yjj_candidate_count", ""),
            "bear_candidate_count": buy_row.get("bear_candidate_count", ""),
            "rzq_candidate_count": buy_row.get("rzq_candidate_count", ""),
            "zb_candidate_count": buy_row.get("zb_candidate_count", ""),
            "auction_candidate_count": buy_row.get("auction_candidate_count", ""),
        }
        trades.append(row)

    daily_rows: list[dict[str, object]] = []
    for state_date in sorted(states):
        state = states.get(state_date, {})
        cand = candidates.get(state_date, {})
        status = current_status.get(state_date, {})
        daily_rows.append(
            {
                "date": state_date,
                "market_mode": state.get("market_mode", ""),
                "raw_market_mode": state.get("raw_market_mode", ""),
                "active": state.get("active", ""),
                "fb_perf": state.get("fb_perf", ""),
                "fb_pct": state.get("fb_pct", ""),
                "fb_pct_bucket": pct_bucket(float(state["fb_pct"])) if "fb_pct" in state else "unknown",
                "bull_sticky": state.get("bull_sticky", ""),
                "bull_cooldown": state.get("bull_cooldown", ""),
                "bull_release_pending": state.get("bull_release_pending", ""),
                "bull_release_guard": state.get("bull_release_guard", ""),
                "stoploss_cooldown": state.get("stoploss_cooldown", ""),
                "rzq_cooldown": state.get("rzq_cooldown", ""),
                "v227_shock_cooldown": state.get("v227_shock_cooldown", ""),
                "enable_v227": state.get("enable_v227", ""),
                "enable_rzq": state.get("enable_rzq", ""),
                "enable_zb": state.get("enable_zb", ""),
                "enable_auction": state.get("enable_auction", ""),
                "slot_v227": state.get("slot_v227", ""),
                "slot_rzq": state.get("slot_rzq", ""),
                "slot_zb": state.get("slot_zb", ""),
                "slot_auction": state.get("slot_auction", ""),
                "recent_wr": state.get("recent_wr", ""),
                "core_wr": state.get("core_wr", ""),
                "yjj_candidate_count": state.get("yjj_candidate_count", cand.get("yjj_candidate_count", "")),
                "bear_candidate_count": state.get("bear_candidate_count", cand.get("bear_candidate_count", "")),
                "rzq_candidate_count": state.get("rzq_candidate_count", ""),
                "zb_candidate_count": state.get("zb_candidate_count", ""),
                "auction_candidate_count": state.get("auction_candidate_count", ""),
                "yjj_candidates": cand.get("yjj_candidates", ""),
                "bear_candidates": cand.get("bear_candidates", ""),
                "status_mode": status.get("status_mode", ""),
                "status_active": status.get("status_active", ""),
                "status_fb_pct": status.get("status_fb_pct", ""),
                "status_fb_perf_pct": status.get("status_fb_perf_pct", ""),
            }
        )

    meta = {
        "source": source_name,
        "encoding": encoding,
        "lines": len(lines),
        "first_date": first_date,
        "last_date": last_date,
        "buys": len(buys),
        "closed_trades": len(trades),
        "unmatched_sells": len(unmatched_sells),
        "open_left": sum(len(items) for items in open_positions.values()),
        "daily_states": len(daily_rows),
    }
    return trades, daily_rows, meta


def write_summary_markdown(path: Path, meta: dict[str, object], rows: list[dict[str, object]]) -> None:
    overall = summarize(rows, "all") if False else []
    vals = [float(row["ret_pct"]) for row in rows]
    wins = [v for v in vals if v > 0]
    losses = [v for v in vals if v < 0]
    pf = sum(wins) / abs(sum(losses)) if losses else 0
    text = [
        "# Mother Log Dissection Run",
        "",
        f"Source: `{meta['source']}`",
        f"Date range: {meta['first_date']} to {meta['last_date']}",
        f"Closed trades parsed: {meta['closed_trades']}",
        f"Buys parsed: {meta['buys']}",
        f"Open/unclosed positions left in log: {meta['open_left']}",
        f"Unmatched sells: {meta['unmatched_sells']}",
        f"Daily state rows: {meta['daily_states']}",
        "",
        "## Closed-Trade Summary",
        "",
        f"- Win rate: {len(wins) / len(vals):.2%}" if vals else "- Win rate: n/a",
        f"- Average return: {sum(vals) / len(vals):.2f}%" if vals else "- Average return: n/a",
        f"- Median return: {statistics.median(vals):.2f}%" if vals else "- Median return: n/a",
        f"- Profit factor: {pf:.2f}" if vals else "- Profit factor: n/a",
        f"- Best / worst: {max(vals):.2f}% / {min(vals):.2f}%" if vals else "- Best / worst: n/a",
        "",
        "Notes:",
        "",
        "- This is closed-trade attribution from the mother log, not a daily equity curve.",
        "- Max drawdown, Sharpe, and Calmar require either exported daily equity or a replay with daily marking.",
        "- The parser writes only under `codex_strategy_dissection/outputs`.",
    ]
    path.write_text("\n".join(text) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--log", type=Path, default=DEFAULT_LOG_ZIP)
    parser.add_argument("--out-dir", type=Path, default=OUT_DIR)
    args = parser.parse_args()

    rows, daily_rows, meta = parse_log(args.log)
    out_dir = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    write_csv(out_dir / "branch_state_attribution.csv", rows)
    write_csv(out_dir / "daily_state_snapshot.csv", daily_rows)
    write_csv(out_dir / "summary_by_branch.csv", summarize(rows, "branch"))
    write_csv(out_dir / "summary_by_year.csv", summarize(rows, "year"))
    write_csv(out_dir / "summary_by_month.csv", summarize(rows, "month"))
    write_csv(out_dir / "summary_by_market_mode.csv", summarize(rows, "market_mode"))
    write_csv(out_dir / "summary_by_fb_pct_bucket.csv", summarize(rows, "fb_pct_bucket"))
    write_csv(out_dir / "summary_by_exit_label.csv", summarize(rows, "sell_label"))
    write_csv(out_dir / "summary_by_branch_market_mode.csv", summarize_multi(rows, ["branch", "market_mode"]))
    write_csv(out_dir / "summary_by_branch_fb_pct_bucket.csv", summarize_multi(rows, ["branch", "fb_pct_bucket"]))
    write_csv(out_dir / "summary_by_branch_exit_label.csv", summarize_multi(rows, ["branch", "sell_label"]))
    write_csv(out_dir / "summary_by_branch_buy_signal_bucket.csv", summarize_multi(rows, ["branch", "buy_signal_bucket"]))
    write_csv(out_dir / "summary_by_branch_candidate_rank_bucket.csv", summarize_multi(rows, ["branch", "candidate_rank_bucket"]))
    write_csv(out_dir / "daily_summary_by_active_mode.csv", summarize_daily(daily_rows, ["active", "market_mode"]))
    write_csv(out_dir / "daily_summary_by_fb_pct_bucket.csv", summarize_daily(daily_rows, ["fb_pct_bucket"]))
    write_summary_markdown(out_dir / "run_summary.md", meta, rows)

    print(f"source={meta['source']}")
    print(f"date_range={meta['first_date']}..{meta['last_date']}")
    print(f"buys={meta['buys']} closed_trades={meta['closed_trades']} open_left={meta['open_left']} unmatched_sells={meta['unmatched_sells']}")
    print(f"out_dir={out_dir}")


if __name__ == "__main__":
    main()
