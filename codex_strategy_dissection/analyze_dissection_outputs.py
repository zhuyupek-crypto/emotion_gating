from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path


HERE = Path(__file__).resolve().parent
OUT_DIR = HERE / "outputs"

BRANCHES = ("v227_yjj", "v227_scorpion", "rzq", "zb", "auction_y2", "auction_rzq")

BRANCH_CANDIDATE_FIELD = {
    "v227_yjj": "yjj_candidate_count",
    "v227_scorpion": "bear_candidate_count",
    "rzq": "rzq_candidate_count",
    "zb": "zb_candidate_count",
    "auction_y2": "auction_candidate_count",
    "auction_rzq": "auction_candidate_count",
}

BRANCH_ENABLE_FIELD = {
    "v227_yjj": "enable_v227",
    "v227_scorpion": "enable_v227",
    "rzq": "enable_rzq",
    "zb": "enable_zb",
    "auction_y2": "enable_auction",
    "auction_rzq": "enable_auction",
}

BRANCH_SLOT_FIELD = {
    "v227_yjj": "slot_v227",
    "v227_scorpion": "slot_v227",
    "rzq": "slot_rzq",
    "zb": "slot_zb",
    "auction_y2": "slot_auction",
    "auction_rzq": "slot_auction",
}

COOLDOWN_TARGET_BRANCHES = {
    "bull_cooldown": ("v227_yjj", "rzq", "zb", "auction_y2", "auction_rzq"),
    "stoploss_cooldown": ("v227_yjj",),
    "v227_shock_cooldown": ("v227_yjj",),
    "rzq_cooldown": ("rzq",),
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def to_float(value: object, default: float = 0.0) -> float:
    try:
        if value in ("", None):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def to_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() == "true"


def wr_bucket(value: object) -> str:
    wr = to_float(value, default=-1.0)
    if wr < 0:
        return "unknown"
    if wr < 0.50:
        return "<50%"
    if wr < 0.55:
        return "50-55%"
    if wr < 0.60:
        return "55-60%"
    if wr < 0.65:
        return "60-65%"
    return ">=65%"


def slot_state_for_branch(row: dict[str, str]) -> str:
    branch = row.get("branch", "")
    slot_field = BRANCH_SLOT_FIELD.get(branch)
    if not slot_field:
        return "unknown"
    slots = int(to_float(row.get(slot_field), default=-1))
    if slots < 0:
        return "unknown"
    return f"{slot_field}={slots}"


def group_trade_returns(rows: list[dict[str, str]], keys: list[str]) -> list[dict[str, object]]:
    grouped: dict[tuple[str, ...], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[tuple(str(row.get(key, "")) for key in keys)].append(row)

    out: list[dict[str, object]] = []
    for group_key, items in grouped.items():
        record: dict[str, object] = {key: value for key, value in zip(keys, group_key)}
        record.update(summarize_returns(items))
        out.append(record)
    out.sort(key=lambda row: (str(row.get(keys[0], "")), -to_float(row.get("avg_ret_pct"))))
    return out


def summarize_returns(rows: list[dict[str, str]]) -> dict[str, object]:
    vals = [to_float(row.get("ret_pct")) for row in rows]
    if not vals:
        return {
            "closed_trades": 0,
            "win_rate": "",
            "avg_ret_pct": "",
            "median_ret_pct": "",
            "best_ret_pct": "",
            "worst_ret_pct": "",
            "profit_factor": "",
        }
    vals_sorted = sorted(vals)
    wins = [v for v in vals if v > 0]
    losses = [v for v in vals if v < 0]
    gross_loss = abs(sum(losses))
    mid = len(vals_sorted) // 2
    median = (
        vals_sorted[mid]
        if len(vals_sorted) % 2
        else (vals_sorted[mid - 1] + vals_sorted[mid]) / 2
    )
    return {
        "closed_trades": len(vals),
        "win_rate": len(wins) / len(vals),
        "avg_ret_pct": sum(vals) / len(vals),
        "median_ret_pct": median,
        "best_ret_pct": max(vals),
        "worst_ret_pct": min(vals),
        "profit_factor": sum(wins) / gross_loss if gross_loss else "",
    }


def build_buy_day_maps(trades: list[dict[str, str]]) -> tuple[dict[tuple[str, str], list[dict[str, str]]], dict[tuple[str, str, str], list[dict[str, str]]]]:
    by_branch_day: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    by_branch_day_mode: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in trades:
        buy_date = row.get("buy_date", "")
        branch = row.get("branch", "")
        if not buy_date or branch not in BRANCHES:
            continue
        by_branch_day[(buy_date, branch)].append(row)
        by_branch_day_mode[(buy_date, branch, row.get("market_mode", ""))].append(row)
    return by_branch_day, by_branch_day_mode


def build_candidate_conversion(daily: list[dict[str, str]], trades: list[dict[str, str]]) -> list[dict[str, object]]:
    by_branch_day, _ = build_buy_day_maps(trades)
    rows: list[dict[str, object]] = []

    for day in daily:
        date = day["date"]
        for branch in BRANCHES:
            candidate_field = BRANCH_CANDIDATE_FIELD[branch]
            enable_field = BRANCH_ENABLE_FIELD[branch]
            slot_field = BRANCH_SLOT_FIELD[branch]
            branch_trades = by_branch_day.get((date, branch), [])
            candidates = to_float(day.get(candidate_field))
            slots = to_float(day.get(slot_field))
            enabled = to_bool(day.get(enable_field))
            summary = summarize_returns(branch_trades)
            rows.append(
                {
                    "date": date,
                    "branch": branch,
                    "market_mode": day.get("market_mode", ""),
                    "active": day.get("active", ""),
                    "fb_pct_bucket": day.get("fb_pct_bucket", ""),
                    "enabled": enabled,
                    "slots": int(slots),
                    "candidate_count": int(candidates),
                    "closed_buys": summary["closed_trades"],
                    "conversion_per_candidate": (summary["closed_trades"] / candidates) if candidates else "",
                    "slot_fill_ratio": (summary["closed_trades"] / slots) if slots else "",
                    **{key: value for key, value in summary.items() if key != "closed_trades"},
                }
            )
    return rows


def group_conversion(rows: list[dict[str, object]], keys: list[str]) -> list[dict[str, object]]:
    grouped: dict[tuple[str, ...], list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        grouped[tuple(str(row.get(key, "")) for key in keys)].append(row)

    out: list[dict[str, object]] = []
    for group_key, items in grouped.items():
        record: dict[str, object] = {key: value for key, value in zip(keys, group_key)}
        days = len(items)
        candidate_days = [row for row in items if to_float(row.get("candidate_count")) > 0]
        enabled_candidate_days = [
            row for row in items if to_float(row.get("candidate_count")) > 0 and to_bool(row.get("enabled"))
        ]
        disabled_candidate_days = [
            row for row in items if to_float(row.get("candidate_count")) > 0 and not to_bool(row.get("enabled"))
        ]
        total_candidates = sum(to_float(row.get("candidate_count")) for row in items)
        total_slots = sum(to_float(row.get("slots")) for row in items)
        total_closed_buys = sum(to_float(row.get("closed_buys")) for row in items)
        trade_rows = []
        for row in items:
            # Daily rows only carry summary returns. Reconstructing all trade rows
            # would require a second grouping, so aggregate daily weighted fields
            # explicitly below.
            pass

        winning_closed = 0.0
        weighted_return_sum = 0.0
        best = None
        worst = None
        gross_win = 0.0
        gross_loss = 0.0
        for row in items:
            closed = to_float(row.get("closed_buys"))
            if not closed:
                continue
            win_rate = to_float(row.get("win_rate"))
            avg_ret = to_float(row.get("avg_ret_pct"))
            weighted_return_sum += avg_ret * closed
            winning_closed += win_rate * closed
            row_best = row.get("best_ret_pct")
            row_worst = row.get("worst_ret_pct")
            if row_best != "":
                best = to_float(row_best) if best is None else max(best, to_float(row_best))
            if row_worst != "":
                worst = to_float(row_worst) if worst is None else min(worst, to_float(row_worst))
            pf = row.get("profit_factor")
            # PF is not algebraically recoverable from daily PF alone.
            # Leave exact PF to trade-level summaries.

        record.update(
            {
                "days": days,
                "candidate_days": len(candidate_days),
                "enabled_candidate_days": len(enabled_candidate_days),
                "disabled_candidate_days": len(disabled_candidate_days),
                "total_candidates": int(total_candidates),
                "total_slots": int(total_slots),
                "closed_buys": int(total_closed_buys),
                "conversion_per_candidate": total_closed_buys / total_candidates if total_candidates else "",
                "slot_fill_ratio": total_closed_buys / total_slots if total_slots else "",
                "win_rate": winning_closed / total_closed_buys if total_closed_buys else "",
                "avg_ret_pct": weighted_return_sum / total_closed_buys if total_closed_buys else "",
                "best_ret_pct": best if best is not None else "",
                "worst_ret_pct": worst if worst is not None else "",
            }
        )
        out.append(record)
    out.sort(key=lambda row: (str(row.get(keys[0], "")), -to_float(row.get("avg_ret_pct"))))
    return out


def build_route_opportunity(daily: list[dict[str, str]]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for branch in BRANCHES:
        candidate_field = BRANCH_CANDIDATE_FIELD[branch]
        enable_field = BRANCH_ENABLE_FIELD[branch]
        slot_field = BRANCH_SLOT_FIELD[branch]
        for day in daily:
            candidates = to_float(day.get(candidate_field))
            slots = to_float(day.get(slot_field))
            enabled = to_bool(day.get(enable_field))
            if candidates <= 0:
                continue
            rows.append(
                {
                    "date": day["date"],
                    "branch": branch,
                    "market_mode": day.get("market_mode", ""),
                    "active": day.get("active", ""),
                    "fb_pct_bucket": day.get("fb_pct_bucket", ""),
                    "enabled": enabled,
                    "slots": int(slots),
                    "candidate_count": int(candidates),
                    "blocked_by_route": not enabled or slots <= 0,
                }
            )
    return rows


def group_route_opportunity(rows: list[dict[str, object]], keys: list[str]) -> list[dict[str, object]]:
    grouped: dict[tuple[str, ...], list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        grouped[tuple(str(row.get(key, "")) for key in keys)].append(row)

    out: list[dict[str, object]] = []
    for group_key, items in grouped.items():
        record: dict[str, object] = {key: value for key, value in zip(keys, group_key)}
        blocked = [row for row in items if to_bool(row.get("blocked_by_route"))]
        total_candidates = sum(to_float(row.get("candidate_count")) for row in items)
        blocked_candidates = sum(to_float(row.get("candidate_count")) for row in blocked)
        record.update(
            {
                "candidate_days": len(items),
                "blocked_candidate_days": len(blocked),
                "blocked_day_rate": len(blocked) / len(items) if items else "",
                "total_candidates": int(total_candidates),
                "blocked_candidates": int(blocked_candidates),
                "blocked_candidate_rate": blocked_candidates / total_candidates if total_candidates else "",
            }
        )
        out.append(record)
    out.sort(key=lambda row: (str(row.get(keys[0], "")), -to_float(row.get("blocked_candidate_rate"))))
    return out


def build_cooldown_daily(daily: list[dict[str, str]], trades: list[dict[str, str]]) -> list[dict[str, object]]:
    by_branch_day, _ = build_buy_day_maps(trades)
    rows: list[dict[str, object]] = []
    for day in daily:
        date = day["date"]
        for cooldown, branches in COOLDOWN_TARGET_BRANCHES.items():
            cooldown_value = to_float(day.get(cooldown))
            active = cooldown_value > 0
            for branch in branches:
                candidate_field = BRANCH_CANDIDATE_FIELD[branch]
                enable_field = BRANCH_ENABLE_FIELD[branch]
                slot_field = BRANCH_SLOT_FIELD[branch]
                branch_trades = by_branch_day.get((date, branch), [])
                summary = summarize_returns(branch_trades)
                candidates = to_float(day.get(candidate_field))
                slots = to_float(day.get(slot_field))
                enabled = to_bool(day.get(enable_field))
                rows.append(
                    {
                        "date": date,
                        "cooldown": cooldown,
                        "cooldown_value": int(cooldown_value),
                        "cooldown_active": active,
                        "branch": branch,
                        "market_mode": day.get("market_mode", ""),
                        "active_route": day.get("active", ""),
                        "fb_pct_bucket": day.get("fb_pct_bucket", ""),
                        "enabled": enabled,
                        "slots": int(slots),
                        "candidate_count": int(candidates),
                        "closed_buys": summary["closed_trades"],
                        **{key: value for key, value in summary.items() if key != "closed_trades"},
                    }
                )
    return rows


def group_cooldown_daily(rows: list[dict[str, object]], keys: list[str]) -> list[dict[str, object]]:
    grouped: dict[tuple[str, ...], list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        grouped[tuple(str(row.get(key, "")) for key in keys)].append(row)

    out: list[dict[str, object]] = []
    for group_key, items in grouped.items():
        record: dict[str, object] = {key: value for key, value in zip(keys, group_key)}
        active_items = [row for row in items if to_bool(row.get("cooldown_active"))]
        candidate_items = [row for row in active_items if to_float(row.get("candidate_count")) > 0]
        total_candidates = sum(to_float(row.get("candidate_count")) for row in active_items)
        total_slots = sum(to_float(row.get("slots")) for row in active_items)
        total_closed = sum(to_float(row.get("closed_buys")) for row in active_items)
        winning_closed = 0.0
        weighted_return_sum = 0.0
        best = None
        worst = None
        for row in active_items:
            closed = to_float(row.get("closed_buys"))
            if not closed:
                continue
            winning_closed += to_float(row.get("win_rate")) * closed
            weighted_return_sum += to_float(row.get("avg_ret_pct")) * closed
            row_best = row.get("best_ret_pct")
            row_worst = row.get("worst_ret_pct")
            if row_best != "":
                best = to_float(row_best) if best is None else max(best, to_float(row_best))
            if row_worst != "":
                worst = to_float(row_worst) if worst is None else min(worst, to_float(row_worst))

        record.update(
            {
                "observed_days": len(items),
                "cooldown_days": len(active_items),
                "candidate_days_during_cooldown": len(candidate_items),
                "total_candidates_during_cooldown": int(total_candidates),
                "total_slots_during_cooldown": int(total_slots),
                "closed_buys_during_cooldown": int(total_closed),
                "slot_fill_during_cooldown": total_closed / total_slots if total_slots else "",
                "win_rate_during_cooldown": winning_closed / total_closed if total_closed else "",
                "avg_ret_pct_during_cooldown": weighted_return_sum / total_closed if total_closed else "",
                "best_ret_pct_during_cooldown": best if best is not None else "",
                "worst_ret_pct_during_cooldown": worst if worst is not None else "",
            }
        )
        out.append(record)
    out.sort(key=lambda row: (str(row.get(keys[0], "")), str(row.get(keys[1], "")) if len(keys) > 1 else ""))
    return out


def build_cooldown_episodes(daily: list[dict[str, str]], trades: list[dict[str, str]]) -> list[dict[str, object]]:
    by_date_branch, _ = build_buy_day_maps(trades)
    rows: list[dict[str, object]] = []
    for cooldown, branches in COOLDOWN_TARGET_BRANCHES.items():
        current: dict[str, object] | None = None
        for day in daily:
            value = to_float(day.get(cooldown))
            active = value > 0
            if active and current is None:
                current = {
                    "cooldown": cooldown,
                    "start_date": day["date"],
                    "end_date": day["date"],
                    "days": 0,
                    "max_value": 0,
                    "market_modes": set(),
                    "active_routes": set(),
                    "total_candidates": 0,
                    "closed_buys": 0,
                    "returns": [],
                }
            if active and current is not None:
                current["end_date"] = day["date"]
                current["days"] = int(current["days"]) + 1
                current["max_value"] = max(int(current["max_value"]), int(value))
                current["market_modes"].add(day.get("market_mode", ""))
                current["active_routes"].add(day.get("active", ""))
                for branch in branches:
                    current["total_candidates"] = int(current["total_candidates"]) + int(
                        to_float(day.get(BRANCH_CANDIDATE_FIELD[branch]))
                    )
                    branch_trades = by_date_branch.get((day["date"], branch), [])
                    current["closed_buys"] = int(current["closed_buys"]) + len(branch_trades)
                    current["returns"].extend(to_float(row.get("ret_pct")) for row in branch_trades)
            if not active and current is not None:
                rows.append(finish_cooldown_episode(current))
                current = None
        if current is not None:
            rows.append(finish_cooldown_episode(current))
    return rows


def finish_cooldown_episode(record: dict[str, object]) -> dict[str, object]:
    returns = list(record.pop("returns"))
    market_modes = ",".join(sorted(str(v) for v in record.pop("market_modes") if v))
    active_routes = ",".join(sorted(str(v) for v in record.pop("active_routes") if v))
    summary = summarize_returns([{"ret_pct": str(value)} for value in returns])
    return {
        **record,
        "market_modes": market_modes,
        "active_routes": active_routes,
        "avg_candidates_per_day": to_float(record["total_candidates"]) / to_float(record["days"]) if to_float(record["days"]) else "",
        **{f"during_{key}": value for key, value in summary.items()},
    }


def write_cooldown_markdown(
    path: Path,
    cooldown_by_type_branch: list[dict[str, object]],
    cooldown_episodes: list[dict[str, object]],
) -> None:
    def fmt(value: object, col: str) -> str:
        if isinstance(value, float):
            if "rate" in col or "fill" in col:
                return f"{value:.2%}"
            return f"{value:.2f}"
        return str(value)

    def table(rows: list[dict[str, object]], cols: list[str], max_rows: int = 30) -> list[str]:
        out = ["|" + "|".join(cols) + "|", "|" + "|".join("---" for _ in cols) + "|"]
        for row in rows[:max_rows]:
            out.append("|" + "|".join(fmt(row.get(col, ""), col) for col in cols) + "|")
        return out

    text = [
        "# Cooldown Attribution",
        "",
        "This report attributes cooldown windows from `daily_state_snapshot.csv`.",
        "",
        "Caution: this is not a counterfactual replay. It measures candidate and",
        "trade activity during cooldown windows. Whether blocked candidates would",
        "have won still needs replay validation.",
        "",
        "## Cooldown By Type And Target Branch",
        "",
    ]
    text.extend(
        table(
            cooldown_by_type_branch,
            [
                "cooldown",
                "branch",
                "cooldown_days",
                "candidate_days_during_cooldown",
                "total_candidates_during_cooldown",
                "closed_buys_during_cooldown",
                "slot_fill_during_cooldown",
                "win_rate_during_cooldown",
                "avg_ret_pct_during_cooldown",
            ],
            max_rows=50,
        )
    )
    text.extend(["", "## Cooldown Episodes", ""])
    text.extend(
        table(
            cooldown_episodes,
            [
                "cooldown",
                "start_date",
                "end_date",
                "days",
                "max_value",
                "market_modes",
                "active_routes",
                "total_candidates",
                "closed_buys",
                "during_avg_ret_pct",
                "during_worst_ret_pct",
            ],
            max_rows=80,
        )
    )
    path.write_text("\n".join(text) + "\n", encoding="utf-8")


def build_sizing_trade_rows(trades: list[dict[str, str]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for row in trades:
        new_row = dict(row)
        new_row["recent_wr_bucket"] = wr_bucket(row.get("recent_wr"))
        new_row["core_wr_bucket"] = wr_bucket(row.get("core_wr"))
        new_row["slot_state"] = slot_state_for_branch(row)
        new_row["route_slot_count"] = str(
            int(to_float(row.get(BRANCH_SLOT_FIELD.get(row.get("branch", ""), ""), ""), default=-1))
        )
        rows.append(new_row)
    return rows


def build_daily_sizing_rows(daily: list[dict[str, str]]) -> list[dict[str, object]]:
    rows = []
    for row in daily:
        rows.append(
            {
                "date": row.get("date", ""),
                "market_mode": row.get("market_mode", ""),
                "active": row.get("active", ""),
                "fb_pct_bucket": row.get("fb_pct_bucket", ""),
                "recent_wr": row.get("recent_wr", ""),
                "core_wr": row.get("core_wr", ""),
                "recent_wr_bucket": wr_bucket(row.get("recent_wr")),
                "core_wr_bucket": wr_bucket(row.get("core_wr")),
                "slot_v227": int(to_float(row.get("slot_v227"))),
                "slot_rzq": int(to_float(row.get("slot_rzq"))),
                "slot_zb": int(to_float(row.get("slot_zb"))),
                "slot_auction": int(to_float(row.get("slot_auction"))),
                "total_slots": int(
                    to_float(row.get("slot_v227"))
                    + to_float(row.get("slot_rzq"))
                    + to_float(row.get("slot_zb"))
                    + to_float(row.get("slot_auction"))
                ),
                "core_slots": int(
                    to_float(row.get("slot_v227"))
                    + to_float(row.get("slot_rzq"))
                    + to_float(row.get("slot_zb"))
                ),
            }
        )
    return rows


def group_daily_sizing(rows: list[dict[str, object]], keys: list[str]) -> list[dict[str, object]]:
    grouped: dict[tuple[str, ...], list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        grouped[tuple(str(row.get(key, "")) for key in keys)].append(row)

    out: list[dict[str, object]] = []
    for group_key, items in grouped.items():
        record: dict[str, object] = {key: value for key, value in zip(keys, group_key)}
        record["days"] = len(items)
        for field in ("total_slots", "core_slots", "slot_v227", "slot_rzq", "slot_zb", "slot_auction"):
            vals = [to_float(row.get(field)) for row in items]
            record[f"avg_{field}"] = sum(vals) / len(vals) if vals else ""
        out.append(record)
    out.sort(key=lambda row: (str(row.get(keys[0], "")), str(row.get(keys[1], "")) if len(keys) > 1 else ""))
    return out


def write_sizing_markdown(
    path: Path,
    by_recent: list[dict[str, object]],
    by_core: list[dict[str, object]],
    by_branch_recent: list[dict[str, object]],
    daily_by_recent: list[dict[str, object]],
) -> None:
    def fmt(value: object, col: str) -> str:
        if isinstance(value, float):
            if "rate" in col:
                return f"{value:.2%}"
            return f"{value:.2f}"
        return str(value)

    def table(rows: list[dict[str, object]], cols: list[str], max_rows: int = 40) -> list[str]:
        out = ["|" + "|".join(cols) + "|", "|" + "|".join("---" for _ in cols) + "|"]
        for row in rows[:max_rows]:
            out.append("|" + "|".join(fmt(row.get(col, ""), col) for col in cols) + "|")
        return out

    text = [
        "# Sizing And Win-Rate State Attribution",
        "",
        "This report slices closed trades by `recent_wr`, `core_wr`, and slot state.",
        "",
        "Caution: the log contains slot counts and recent win-rate state, but not",
        "a full per-trade target weight for every branch. These slices describe",
        "trade quality by sizing state, not exact capital-weighted performance.",
        "",
        "## Closed Trades By Recent WR Bucket",
        "",
    ]
    text.extend(table(by_recent, ["recent_wr_bucket", "closed_trades", "win_rate", "avg_ret_pct", "median_ret_pct", "profit_factor"]))
    text.extend(["", "## Closed Trades By Core WR Bucket", ""])
    text.extend(table(by_core, ["core_wr_bucket", "closed_trades", "win_rate", "avg_ret_pct", "median_ret_pct", "profit_factor"]))
    text.extend(["", "## Branch By Recent WR Bucket", ""])
    text.extend(table(by_branch_recent, ["branch", "recent_wr_bucket", "closed_trades", "win_rate", "avg_ret_pct", "median_ret_pct"], max_rows=80))
    text.extend(["", "## Daily Slot State By Recent WR Bucket", ""])
    text.extend(table(daily_by_recent, ["recent_wr_bucket", "days", "avg_total_slots", "avg_core_slots", "avg_slot_v227", "avg_slot_rzq", "avg_slot_zb", "avg_slot_auction"]))
    path.write_text("\n".join(text) + "\n", encoding="utf-8")


def write_markdown(
    path: Path,
    conversion_by_branch: list[dict[str, object]],
    route_by_branch: list[dict[str, object]],
    route_by_branch_mode: list[dict[str, object]],
) -> None:
    def lines_for_table(rows: list[dict[str, object]], cols: list[str], max_rows: int = 20) -> list[str]:
        out = ["|" + "|".join(cols) + "|", "|" + "|".join("---" for _ in cols) + "|"]
        for row in rows[:max_rows]:
            vals = []
            for col in cols:
                val = row.get(col, "")
                if isinstance(val, float):
                    if "rate" in col or "ratio" in col or "conversion" in col:
                        vals.append(f"{val:.2%}")
                    else:
                        vals.append(f"{val:.2f}")
                else:
                    vals.append(str(val))
            out.append("|" + "|".join(vals) + "|")
        return out

    text: list[str] = [
        "# Candidate Conversion And Route Opportunity",
        "",
        "This report is derived from `daily_state_snapshot.csv` and",
        "`branch_state_attribution.csv`.",
        "",
        "Important caution: route-blocked rows identify days where a branch had",
        "candidates but was disabled or had zero slots. They do not prove those",
        "untraded candidates would have made money.",
        "",
        "Auction candidate counts come from the daily `auction_candidate_count`",
        "state field. The log does not split daily auction candidates into `y2`",
        "and `rzq` pools, so `auction_y2` and `auction_rzq` share the same",
        "candidate denominator in this conversion report.",
        "",
        "## Conversion By Branch",
        "",
    ]
    text.extend(
        lines_for_table(
            conversion_by_branch,
            [
                "branch",
                "candidate_days",
                "total_candidates",
                "closed_buys",
                "conversion_per_candidate",
                "slot_fill_ratio",
                "win_rate",
                "avg_ret_pct",
            ],
        )
    )
    text.extend(["", "## Route-Blocked Opportunity By Branch", ""])
    text.extend(
        lines_for_table(
            route_by_branch,
            [
                "branch",
                "candidate_days",
                "blocked_candidate_days",
                "blocked_day_rate",
                "total_candidates",
                "blocked_candidates",
                "blocked_candidate_rate",
            ],
        )
    )
    text.extend(["", "## Route-Blocked Opportunity By Branch And Mode", ""])
    text.extend(
        lines_for_table(
            route_by_branch_mode,
            [
                "branch",
                "market_mode",
                "candidate_days",
                "blocked_candidate_days",
                "blocked_day_rate",
                "blocked_candidate_rate",
            ],
            max_rows=40,
        )
    )
    path.write_text("\n".join(text) + "\n", encoding="utf-8")


def main() -> None:
    daily = read_csv(OUT_DIR / "daily_state_snapshot.csv")
    trades = read_csv(OUT_DIR / "branch_state_attribution.csv")

    conversion_rows = build_candidate_conversion(daily, trades)
    route_rows = build_route_opportunity(daily)
    conversion_by_branch = group_conversion(conversion_rows, ["branch"])
    conversion_by_branch_mode = group_conversion(conversion_rows, ["branch", "market_mode"])
    conversion_by_branch_bucket = group_conversion(conversion_rows, ["branch", "fb_pct_bucket"])
    route_by_branch = group_route_opportunity(route_rows, ["branch"])
    route_by_branch_mode = group_route_opportunity(route_rows, ["branch", "market_mode"])
    route_by_branch_active = group_route_opportunity(route_rows, ["branch", "active"])
    cooldown_rows = build_cooldown_daily(daily, trades)
    cooldown_by_type_branch = group_cooldown_daily(cooldown_rows, ["cooldown", "branch"])
    cooldown_by_type_mode = group_cooldown_daily(cooldown_rows, ["cooldown", "market_mode"])
    cooldown_episodes = build_cooldown_episodes(daily, trades)
    sizing_trades = build_sizing_trade_rows(trades)
    sizing_daily = build_daily_sizing_rows(daily)
    sizing_by_recent = group_trade_returns(sizing_trades, ["recent_wr_bucket"])
    sizing_by_core = group_trade_returns(sizing_trades, ["core_wr_bucket"])
    sizing_by_branch_recent = group_trade_returns(sizing_trades, ["branch", "recent_wr_bucket"])
    sizing_by_branch_core = group_trade_returns(sizing_trades, ["branch", "core_wr_bucket"])
    sizing_by_branch_slot = group_trade_returns(sizing_trades, ["branch", "slot_state"])
    daily_sizing_by_recent = group_daily_sizing(sizing_daily, ["recent_wr_bucket"])
    daily_sizing_by_active_recent = group_daily_sizing(sizing_daily, ["active", "recent_wr_bucket"])

    write_csv(OUT_DIR / "candidate_conversion_daily.csv", conversion_rows)
    write_csv(OUT_DIR / "candidate_conversion_by_branch.csv", conversion_by_branch)
    write_csv(OUT_DIR / "candidate_conversion_by_branch_market_mode.csv", conversion_by_branch_mode)
    write_csv(OUT_DIR / "candidate_conversion_by_branch_fb_pct_bucket.csv", conversion_by_branch_bucket)
    write_csv(OUT_DIR / "route_opportunity_daily.csv", route_rows)
    write_csv(OUT_DIR / "route_opportunity_by_branch.csv", route_by_branch)
    write_csv(OUT_DIR / "route_opportunity_by_branch_market_mode.csv", route_by_branch_mode)
    write_csv(OUT_DIR / "route_opportunity_by_branch_active.csv", route_by_branch_active)
    write_csv(OUT_DIR / "cooldown_attribution_daily.csv", cooldown_rows)
    write_csv(OUT_DIR / "cooldown_attribution_by_type_branch.csv", cooldown_by_type_branch)
    write_csv(OUT_DIR / "cooldown_attribution_by_type_market_mode.csv", cooldown_by_type_mode)
    write_csv(OUT_DIR / "cooldown_episodes.csv", cooldown_episodes)
    write_csv(OUT_DIR / "sizing_trades_enriched.csv", sizing_trades)
    write_csv(OUT_DIR / "sizing_by_recent_wr_bucket.csv", sizing_by_recent)
    write_csv(OUT_DIR / "sizing_by_core_wr_bucket.csv", sizing_by_core)
    write_csv(OUT_DIR / "sizing_by_branch_recent_wr_bucket.csv", sizing_by_branch_recent)
    write_csv(OUT_DIR / "sizing_by_branch_core_wr_bucket.csv", sizing_by_branch_core)
    write_csv(OUT_DIR / "sizing_by_branch_slot_state.csv", sizing_by_branch_slot)
    write_csv(OUT_DIR / "daily_sizing_by_recent_wr_bucket.csv", daily_sizing_by_recent)
    write_csv(OUT_DIR / "daily_sizing_by_active_recent_wr_bucket.csv", daily_sizing_by_active_recent)
    write_markdown(
        OUT_DIR / "candidate_conversion_route_report.md",
        conversion_by_branch,
        route_by_branch,
        route_by_branch_mode,
    )
    write_cooldown_markdown(
        OUT_DIR / "cooldown_attribution_report.md",
        cooldown_by_type_branch,
        cooldown_episodes,
    )
    write_sizing_markdown(
        OUT_DIR / "sizing_attribution_report.md",
        sizing_by_recent,
        sizing_by_core,
        sizing_by_branch_recent,
        daily_sizing_by_recent,
    )

    print(f"daily_rows={len(daily)} trade_rows={len(trades)}")
    print(f"candidate_conversion_daily={len(conversion_rows)} route_opportunity_daily={len(route_rows)} cooldown_daily={len(cooldown_rows)} sizing_trades={len(sizing_trades)}")
    print(f"out_dir={OUT_DIR}")


if __name__ == "__main__":
    main()
