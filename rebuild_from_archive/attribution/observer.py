"""Phase 1A attribution observer."""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from .schema import (
    BRANCH_CANDIDATE_ATTR,
    BRANCH_ENABLE_ATTR,
    BRANCH_SLOT_ATTR,
    BRANCH_VARIANTS,
    BUY_HANDLER_BRANCH,
    SCHEMA_VERSION,
)

_CURRENT_OBSERVER = None


def set_current_observer(observer):
    global _CURRENT_OBSERVER
    _CURRENT_OBSERVER = observer


def get_current_observer():
    return _CURRENT_OBSERVER or NullAttributionObserver()


def _date(context) -> str:
    return context.current_dt.strftime("%Y-%m-%d")


def _time(context) -> str:
    dt = getattr(context, "current_dt", None)
    if dt is None:
        return ""
    return dt.strftime("%H:%M")


def _status_name(order) -> str | None:
    status = getattr(order, "status", None)
    return getattr(status, "name", status)


def _code_from_candidate(item):
    return item[0] if isinstance(item, tuple) else item


class NullAttributionObserver:
    enabled = False

    def set_current_handler(self, *args, **kwargs):
        return None

    def clear_current_handler(self):
        return None

    def snapshot_handler(self, *args, **kwargs):
        return None

    def observe_after_prepare(self, *args, **kwargs):
        return None

    def emit_order_intent(self, *args, **kwargs):
        return None

    def bind_order(self, *args, **kwargs):
        return None

    def emit_exit_intent(self, *args, **kwargs):
        return None

    def finalize(self, *args, **kwargs):
        return {}


class AttributionObserver:
    enabled = True

    def __init__(self, strategy_commit: str = "unknown", strategy_sha256: str = "unknown"):
        self.strategy_commit = strategy_commit
        self.strategy_sha256 = strategy_sha256
        self.signal_events: list[dict] = []
        self.decision_events: list[dict] = []
        self.trade_outcomes: list[dict] = []
        self.handler_snapshots: list[dict] = []
        self.order_intents: list[dict] = []
        self.exit_intents: list[dict] = []
        self.signal_index: dict[tuple[str, str, str], str] = {}
        self.signals_by_id: dict[str, dict] = {}
        self.order_to_signal: dict[str, str] = {}
        self.order_to_branch: dict[str, str] = {}
        self.order_to_handler: dict[str, str] = {}
        self.current_handler: str | None = None
        self.current_time: str | None = None
        self._decision_seq = defaultdict(int)
        self._intent_seq = 0
        self._intent_by_token: dict[str, dict] = {}
        self.unmapped_buy_trades: list[dict] = []
        self.unmapped_sell_trades: list[dict] = []
        self.sell_trace_rows: list[dict] = []

    def set_current_handler(self, handler: str, time: str, context=None):
        self.current_handler = handler
        self.current_time = time

    def clear_current_handler(self):
        self.current_handler = None
        self.current_time = None

    def _positions_payload(self, context):
        positions = getattr(context.portfolio, "positions", {}) or {}
        return json.dumps({k: getattr(v, "total_amount", 0) for k, v in sorted(positions.items())}, ensure_ascii=False)

    def _owners_payload(self, g):
        return json.dumps(getattr(g, "owner", {}) or {}, ensure_ascii=False, sort_keys=True)

    def _pending_orders(self, context):
        engine = getattr(getattr(context, "portfolio", None), "engine", None)
        return [] if engine is None else list(getattr(engine, "_pending_orders", []) or [])

    def snapshot_handler(self, context, g, handler: str, time: str, stage: str):
        pending = []
        engine = getattr(self, "engine", None)
        if engine is not None:
            pending = list(getattr(engine, "_pending_orders", []) or [])
        row = {
            "schema_version": SCHEMA_VERSION,
            "date": _date(context),
            "time": time,
            "handler": handler,
            "stage": stage,
            "available_cash": float(getattr(context.portfolio, "available_cash", 0.0)),
            "locked_cash": float(getattr(context.portfolio, "locked_cash", 0.0)),
            "portfolio_total_value": float(getattr(context.portfolio, "total_value", 0.0)),
            "positions_count": len(getattr(context.portfolio, "positions", {}) or {}),
            "positions": self._positions_payload(context),
            "owners": self._owners_payload(g),
            "pending_order_count": len(pending),
            "pending_order_ids": json.dumps([str(getattr(o, "order_id", "")) for o in pending], ensure_ascii=False),
            "slot_v227": getattr(g, "v227_slots", None),
            "slot_rzq": getattr(g, "rzq_slots", None),
            "slot_zb": getattr(g, "zb_slots", None),
            "slot_auction": getattr(g, "auction_yiqian_slots", None),
            "candidate_counts": json.dumps({
                "YJJ": len(getattr(g, "yjj_candidates", []) or []),
                "Scorpion": len(getattr(g, "bear_candidates", []) or []),
                "RZQ": len(getattr(g, "rzq_candidates", []) or []),
                "ZB": len(getattr(g, "zb_candidates", []) or []),
                "Auction": len(getattr(g, "auction_yiqian_candidates", []) or []),
            }, ensure_ascii=False),
            "candidate_codes": json.dumps({
                branch: [_code_from_candidate(x) for x in (getattr(g, attr, []) or [])]
                for branch, attr in BRANCH_CANDIDATE_ATTR.items()
            }, ensure_ascii=False),
        }
        self.handler_snapshots.append(row)

    def _signal_id(self, branch: str, date: str, code: str) -> str:
        return f"{branch}|{date}|{code}|{BRANCH_VARIANTS[branch]}"

    def _ensure_signal(self, context, g, branch: str, code: str, rank=None, count=None, prepared=True):
        date = _date(context)
        key = (date, branch, code)
        existing = self.signal_index.get(key)
        if existing:
            return existing
        signal_id = self._signal_id(branch, date, code)
        row = {
            "schema_version": SCHEMA_VERSION,
            "signal_id": signal_id,
            "trade_date": date,
            "signal_time": _time(context),
            "code": code,
            "branch": branch,
            "signal_variant": BRANCH_VARIANTS[branch],
            "strategy_commit": self.strategy_commit,
            "strategy_sha256": self.strategy_sha256,
            "observation_level": "PREPARED_CANDIDATE",
            "raw_pattern_hit": None,
            "prepared_candidate": bool(prepared),
            "handler_eligible": None,
            "branch_eligible": None,
            "raw_candidate_rank": rank,
            "final_candidate_rank": None,
            "branch_candidate_count": count,
            "terminal_state": "UNRESOLVED",
            "market_mode": getattr(g, "market_mode", None),
            "raw_market_mode": getattr(g, "raw_market_mode", None),
            "active_route": getattr(g, "active", None),
            "emotion_state": getattr(g, "market_mode", None),
            "emotion_heat": getattr(g, "fb_pct", None),
            "emotion_momentum": getattr(g, "first_board_perf", None),
            "emotion_stress": None,
            "source_function": "prepare_all",
            "source_path": "research/instrumented_strategies/motherboard_phase1a_observed.py",
            "source_line": None,
            "branch_payload": "{}",
        }
        self.signal_events.append(row)
        self.signals_by_id[signal_id] = row
        self.signal_index[key] = signal_id
        return signal_id

    def observe_after_prepare(self, context, g):
        for branch, attr in BRANCH_CANDIDATE_ATTR.items():
            candidates = list(getattr(g, attr, []) or [])
            count = len(candidates)
            for idx, item in enumerate(candidates, start=1):
                code = _code_from_candidate(item)
                signal_id = self._ensure_signal(context, g, branch, code, idx, count, prepared=True)
                enabled = bool(getattr(g, BRANCH_ENABLE_ATTR[branch], False))
                self.emit_decision(
                    signal_id=signal_id,
                    context=context,
                    g=g,
                    stage="ROUTE_GATE",
                    name="branch_enabled",
                    value=enabled,
                    passed=enabled,
                    reason_code=None if enabled else "ROUTE_DISABLED",
                    detail=f"active={getattr(g, 'active', None)}",
                    branch_enabled=enabled,
                    branch_slots_total=getattr(g, BRANCH_SLOT_ATTR[branch], None),
                    candidate_rank=idx,
                )
                if not enabled:
                    self.set_terminal(signal_id, "ROUTED_OUT")

    def emit_decision(self, signal_id, context, g, stage, name, value, passed, reason_code=None, detail=None, **extra):
        self._decision_seq[signal_id] += 1
        self.decision_events.append({
            "schema_version": SCHEMA_VERSION,
            "signal_id": signal_id,
            "decision_seq": self._decision_seq[signal_id],
            "decision_time": f"{_date(context)} {_time(context)}",
            "decision_stage": stage,
            "decision_name": name,
            "decision_value": value,
            "rule_description": detail,
            "passed": bool(passed),
            "reason_code": reason_code,
            "reason_detail": detail,
            "market_mode": getattr(g, "market_mode", None),
            "active_route": getattr(g, "active", None),
            "branch_enabled": extra.get("branch_enabled"),
            "branch_slots_total": extra.get("branch_slots_total"),
            "branch_slots_used": extra.get("branch_slots_used"),
            "branch_slots_remaining": extra.get("branch_slots_remaining"),
            "available_cash": float(getattr(context.portfolio, "available_cash", 0.0)),
            "locked_cash": float(getattr(context.portfolio, "locked_cash", 0.0)),
            "positions_count": len(getattr(context.portfolio, "positions", {}) or {}),
            "pending_order_count": len(getattr(getattr(self, "engine", None), "_pending_orders", []) or []),
            "candidate_rank": extra.get("candidate_rank"),
            "selected_for_order": extra.get("selected_for_order"),
            "blocking_signal_id": extra.get("blocking_signal_id"),
            "blocking_branch": extra.get("blocking_branch"),
            "blocking_code": extra.get("blocking_code"),
            "blocking_order_id": extra.get("blocking_order_id"),
        })

    def set_terminal(self, signal_id: str, terminal_state: str):
        row = self.signals_by_id.get(signal_id)
        if row and row.get("terminal_state") != "FILLED":
            row["terminal_state"] = terminal_state

    def emit_order_intent(self, context, g, order_func: str, security: str, requested_value=None, requested_amount=None, style=None):
        handler = self.current_handler
        branch = BUY_HANDLER_BRANCH.get(handler or "")
        side = "buy"
        if requested_amount is not None and requested_amount <= 0:
            side = "sell"
        if requested_value is not None and requested_value <= 0:
            side = "sell"
        if branch is None and side == "buy":
            return None
        if side == "buy":
            signal_id = self._ensure_signal(context, g, branch, security, prepared=False)
        else:
            signal_id = None
        self._intent_seq += 1
        token = f"intent_{self._intent_seq}"
        intent = {
            "token": token,
            "schema_version": SCHEMA_VERSION,
            "signal_id": signal_id,
            "branch": branch,
            "code": security,
            "side": side,
            "order_func": order_func,
            "requested_value": requested_value,
            "requested_amount": requested_amount,
            "available_cash_before": float(getattr(context.portfolio, "available_cash", 0.0)),
            "handler": handler,
            "time": f"{_date(context)} {_time(context)}",
        }
        self._intent_by_token[token] = intent
        self.order_intents.append(intent)
        if signal_id:
            self.emit_decision(signal_id, context, g, "ORDER_CREATION", "order_intent", order_func, True, selected_for_order=True)
        return token

    def bind_order(self, token, order):
        if token is None:
            return
        intent = self._intent_by_token.get(token)
        if intent is None:
            return
        signal_id = intent.get("signal_id")
        order_id = None if order is None else str(getattr(order, "order_id", ""))
        status = None if order is None else _status_name(order)
        intent["order_returned"] = order is not None
        intent["order_id"] = order_id
        intent["order_status"] = status
        intent["order_amount"] = None if order is None else getattr(order, "amount", None)
        if order_id:
            self.order_to_handler[order_id] = intent.get("handler")
            if intent.get("branch"):
                self.order_to_branch[order_id] = intent.get("branch")
        if order_id and signal_id:
            self.order_to_signal[order_id] = signal_id
        if signal_id and order is None:
            self.set_terminal(signal_id, "ORDER_REJECTED")
        elif signal_id and status == "rejected":
            self.set_terminal(signal_id, "ORDER_REJECTED")

    def finalize(self, engine=None, out_dir: str | Path | None = None):
        if engine is not None:
            self.engine = engine
        open_lots = defaultdict(list)
        for trade in getattr(engine, "trades", []) or []:
            order_id = str(trade.get("order_id", ""))
            code = trade.get("code")
            amount = float(trade.get("amount", 0) or 0)
            if amount > 0:
                signal_id = self.order_to_signal.get(order_id)
                if not signal_id:
                    self.unmapped_buy_trades.append(trade)
                    continue
                self.set_terminal(signal_id, "FILLED")
                order = getattr(engine, "orders", {}).get(order_id)
                requested = abs(float(getattr(order, "amount", amount) or amount)) if order is not None else abs(amount)
                filled = abs(float(getattr(order, "filled", amount) or amount)) if order is not None else abs(amount)
                fill_status = "PARTIAL" if filled < requested else "FULL"
                open_lots[code].append({"signal_id": signal_id, "amount": abs(amount), "entry_trade": trade})
                self.trade_outcomes.append({
                    "schema_version": SCHEMA_VERSION,
                    "signal_id": signal_id,
                    "outcome_type": "MASTER_ACTUAL",
                    "actual_traded": True,
                    "order_id": order_id,
                    "trade_ids": trade.get("trade_id"),
                    "entry_time": trade.get("time"),
                    "entry_price": trade.get("price"),
                    "entry_amount": amount,
                    "entry_value": abs(amount) * float(trade.get("price", 0) or 0),
                    "requested_amount": requested,
                    "filled_amount": filled,
                    "unfilled_amount": max(0.0, requested - filled),
                    "fill_status": fill_status,
                    "exit_time": None,
                    "exit_price": None,
                    "exit_reason": None,
                    "holding_days": None,
                    "gross_return": None,
                    "net_return": None,
                    "commission": trade.get("commission"),
                    "tax": trade.get("tax"),
                    "slippage": None,
                    "order_status": _status_name(order) if order is not None else None,
                    "order_reject_reason": None,
                    "is_limit_up_entry": None,
                    "is_limit_down_exit": None,
                })
            elif amount < 0:
                remaining = abs(amount)
                lots = open_lots.get(code, [])
                while remaining > 0 and lots:
                    lot = lots[0]
                    take = min(remaining, lot["amount"])
                    lot["amount"] -= take
                    remaining -= take
                    self.sell_trace_rows.append({
                        "sell_trade_id": trade.get("trade_id"),
                        "sell_order_id": order_id,
                        "code": code,
                        "signal_id": lot["signal_id"],
                        "allocated_amount": take,
                        "sell_time": trade.get("time"),
                        "sell_price": trade.get("price"),
                    })
                    if lot["amount"] <= 0:
                        lots.pop(0)
                if remaining > 0:
                    self.unmapped_sell_trades.append(trade)
        return self.audit_summary()

    def audit_summary(self):
        buy_trades = len([x for x in self.trade_outcomes if x.get("entry_amount", 0) > 0])
        sell_traced = len(self.sell_trace_rows)
        states = defaultdict(int)
        for row in self.signal_events:
            states[row.get("terminal_state") or "UNRESOLVED"] += 1
        return {
            "signal_events": len(self.signal_events),
            "decision_events": len(self.decision_events),
            "trade_outcomes": len(self.trade_outcomes),
            "handler_snapshots": len(self.handler_snapshots),
            "mapped_buy_trades": buy_trades,
            "unmapped_buy_trades": len(self.unmapped_buy_trades),
            "mapped_sell_allocations": sell_traced,
            "unmapped_sell_trades": len(self.unmapped_sell_trades),
            "terminal_states": dict(sorted(states.items())),
        }


