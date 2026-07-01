"""Phase 1B attribution observer."""

from __future__ import annotations

import json
from collections import defaultdict
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
    return "" if dt is None else dt.strftime("%H:%M")


def _status_name(order) -> str | None:
    status = getattr(order, "status", None)
    return getattr(status, "name", status)


def _code_from_candidate(item):
    return item[0] if isinstance(item, tuple) else item


class NullAttributionObserver:
    enabled = False

    def __getattr__(self, _name):
        def _noop(*args, **kwargs):
            return None
        return _noop

    def finalize(self, *args, **kwargs):
        return {}


class AttributionObserver:
    enabled = True

    def __init__(self, strategy_commit: str = "unknown", strategy_sha256: str = "unknown",
                 formal_strategy_commit: str | None = None, formal_strategy_sha256: str | None = None,
                 observer_commit: str | None = None):
        self.formal_strategy_commit = formal_strategy_commit or strategy_commit
        self.formal_strategy_sha256 = formal_strategy_sha256 or strategy_sha256
        self.instrumented_strategy_commit = strategy_commit
        self.instrumented_strategy_sha256 = strategy_sha256
        self.observer_commit = observer_commit or strategy_commit
        self.signal_events: list[dict] = []
        self.decision_events: list[dict] = []
        self.trade_outcomes: list[dict] = []
        self.handler_snapshots: list[dict] = []
        self.order_intents: list[dict] = []
        self.exit_intents: list[dict] = []
        self.loop_stop_events: list[dict] = []
        self.position_block_events: list[dict] = []
        self.order_none_events: list[dict] = []
        self.signal_index: dict[tuple[str, str, str, str], str] = {}
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

    def snapshot_handler(self, context, g, handler: str, time: str, stage: str):
        pending = list(getattr(getattr(self, "engine", None), "_pending_orders", []) or [])
        self.handler_snapshots.append({
            "schema_version": SCHEMA_VERSION,
            "date": _date(context), "time": time, "handler": handler, "stage": stage,
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
        })

    def _signal_id(self, branch: str, date: str, code: str, signal_variant: str) -> str:
        return f"{branch}|{date}|{code}|{signal_variant}"

    def _ensure_signal(self, context, g, branch: str, code: str, rank=None, count=None,
                       prepared=True, signal_variant: str | None = None):
        date = _date(context)
        variant = signal_variant or BRANCH_VARIANTS[branch]
        key = (date, branch, code, variant)
        existing = self.signal_index.get(key)
        if existing:
            return existing
        signal_id = self._signal_id(branch, date, code, variant)
        row = {
            "schema_version": SCHEMA_VERSION,
            "signal_id": signal_id,
            "trade_date": date,
            "signal_time": _time(context),
            "code": code,
            "branch": branch,
            "signal_variant": variant,
            "formal_strategy_commit": self.formal_strategy_commit,
            "formal_strategy_sha256": self.formal_strategy_sha256,
            "instrumented_strategy_commit": self.instrumented_strategy_commit,
            "instrumented_strategy_sha256": self.instrumented_strategy_sha256,
            "observer_commit": self.observer_commit,
            "observation_level": "PREPARED_CANDIDATE",
            "raw_pattern_hit": None,
            "prepared_candidate": bool(prepared),
            "handler_reached": False,
            "candidate_loop_reached": False,
            "handler_eligible": None,
            "branch_eligible": None,
            "qualified_for_ranking": False,
            "participated_in_ranking": False,
            "selected_for_order": False,
            "loop_stop_reason": None,
            "terminal_reason_code": None,
            "terminal_decision_seq": None,
            "raw_candidate_rank": rank,
            "final_candidate_rank": None,
            "branch_candidate_count": count,
            "terminal_state": "UNRESOLVED",
            "market_mode": getattr(g, "market_mode", None),
            "raw_market_mode": getattr(g, "raw_market_mode", None),
            "active_route": getattr(g, "active", None),
            "fb_pct": getattr(g, "fb_pct", None),
            "first_board_perf": getattr(g, "first_board_perf", None),
            "emotion_state": None,
            "emotion_heat": None,
            "emotion_momentum": None,
            "emotion_stress": None,
            "source_function": "prepare_all",
            "source_path": "research/instrumented_strategies/motherboard_phase1b_observed.py",
            "source_line": None,
            "branch_payload": "{}",
        }
        self.signal_events.append(row)
        self.signals_by_id[signal_id] = row
        self.signal_index[key] = signal_id
        return signal_id

    def signal_id_for(self, context, g, branch: str, code: str, signal_variant: str | None = None):
        return self._ensure_signal(context, g, branch, code, prepared=False, signal_variant=signal_variant)

    def signals_for_branch_date(self, context, branch: str):
        date = _date(context)
        return [r["signal_id"] for r in self.signal_events if r.get("trade_date") == date and r.get("branch") == branch]

    def observe_after_prepare(self, context, g):
        for branch, attr in BRANCH_CANDIDATE_ATTR.items():
            candidates = list(getattr(g, attr, []) or [])
            count = len(candidates)
            for idx, item in enumerate(candidates, start=1):
                code = _code_from_candidate(item)
                signal_id = self._ensure_signal(context, g, branch, code, idx, count, prepared=True)
                enabled = bool(getattr(g, BRANCH_ENABLE_ATTR[branch], False))
                seq = self.emit_decision(signal_id, context, g, "ROUTE_GATE", "branch_enabled", enabled,
                                         enabled, None if enabled else "ROUTE_DISABLED",
                                         f"active={getattr(g, 'active', None)}",
                                         branch_enabled=enabled,
                                         branch_slots_total=getattr(g, BRANCH_SLOT_ATTR[branch], None),
                                         candidate_rank=idx)
                if not enabled:
                    self.set_terminal_once(signal_id, "ROUTED_OUT", "ROUTE_DISABLED", seq)

    def emit_decision(self, signal_id, context, g, stage, name, value, passed, reason_code=None, detail=None, **extra):
        self._decision_seq[signal_id] += 1
        seq = self._decision_seq[signal_id]
        self.decision_events.append({
            "schema_version": SCHEMA_VERSION,
            "signal_id": signal_id,
            "decision_seq": seq,
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
        return seq

    def _mark(self, signal_id: str, field: str, value=True):
        row = self.signals_by_id.get(signal_id)
        if row:
            row[field] = value

    def mark_handler_reached(self, context, branch: str):
        for sid in self.signals_for_branch_date(context, branch):
            self._mark(sid, "handler_reached", True)

    def mark_candidate_loop_reached(self, signal_id):
        self._mark(signal_id, "candidate_loop_reached", True)

    def mark_handler_eligible(self, signal_id, value=True):
        self._mark(signal_id, "handler_eligible", value)

    def mark_branch_eligible(self, signal_id, value=True):
        self._mark(signal_id, "branch_eligible", value)

    def mark_qualified_for_ranking(self, signal_id, payload=None):
        self._mark(signal_id, "qualified_for_ranking", True)
        if payload is not None and signal_id in self.signals_by_id:
            self.signals_by_id[signal_id]["branch_payload"] = json.dumps(payload, ensure_ascii=False)

    def mark_ranked(self, signal_id, rank=None, score=None):
        row = self.signals_by_id.get(signal_id)
        if row:
            row["participated_in_ranking"] = True
            row["final_candidate_rank"] = rank
            payload = {}
            try:
                payload = json.loads(row.get("branch_payload") or "{}")
            except Exception:
                payload = {}
            if score is not None:
                payload["score"] = score
            row["branch_payload"] = json.dumps(payload, ensure_ascii=False)

    def mark_selected_for_order(self, signal_id):
        self._mark(signal_id, "selected_for_order", True)

    def set_terminal_once(self, signal_id: str, terminal_state: str, reason_code=None, decision_seq=None):
        row = self.signals_by_id.get(signal_id)
        if not row:
            return
        old = row.get("terminal_state")
        if old == "FILLED":
            return
        if old and old != "UNRESOLVED" and old != terminal_state:
            raise RuntimeError(f"terminal conflict for {signal_id}: {old} -> {terminal_state}")
        row["terminal_state"] = terminal_state
        row["terminal_reason_code"] = reason_code
        row["terminal_decision_seq"] = decision_seq

    def emit_loop_stop(self, context, g, branch, handler, stop_type, stop_reason, candidate_index=None,
                       bought_count=None, take=None, slots=None, affected_signal_ids=None):
        affected = affected_signal_ids or []
        row = {
            "schema_version": SCHEMA_VERSION,
            "branch": branch,
            "date": _date(context),
            "handler": handler,
            "stop_type": stop_type,
            "stop_reason": stop_reason,
            "candidate_index": candidate_index,
            "bought_count": bought_count,
            "take": take,
            "slots": slots,
            "available_cash": float(getattr(context.portfolio, "available_cash", 0.0)),
            "remaining_candidate_count": len(affected),
            "affected_signal_ids": json.dumps(affected, ensure_ascii=False),
        }
        self.loop_stop_events.append(row)
        for sid in affected:
            sig = self.signals_by_id.get(sid)
            if sig:
                sig["loop_stop_reason"] = stop_reason
                seq = self.emit_decision(sid, context, g, "LOOP_CONTROL", stop_type, stop_reason, False, stop_reason, handler)
                term = "SLOT_BLOCKED" if stop_reason in ("SLOTS_FILLED", "TAKE_FILLED") else "NOT_EVALUATED_AFTER_STOP"
                self.set_terminal_once(sid, term, stop_reason, seq)

    def emit_block(self, signal_id, context, g, terminal, reason, stage="BRANCH_FILTER", detail=None, **extra):
        seq = self.emit_decision(signal_id, context, g, stage, reason, False, False, reason, detail or reason, **extra)
        self.set_terminal_once(signal_id, terminal, reason, seq)
        if terminal == "POSITION_BLOCKED":
            self.position_block_events.append({
                "schema_version": SCHEMA_VERSION,
                "signal_id": signal_id,
                "code": self.signals_by_id.get(signal_id, {}).get("code"),
                "reason_code": reason,
                "detail": detail,
            })
        return seq

    def emit_order_intent(self, context, g, order_func: str, security: str, requested_value=None, requested_amount=None, style=None):
        handler = self.current_handler
        branch = BUY_HANDLER_BRANCH.get(handler or "")
        side = "buy"
        if requested_amount is not None and requested_amount <= 0:
            side = "sell"
        if requested_value is not None and requested_value <= 0:
            side = "sell"
        signal_id = self.signal_id_for(context, g, branch, security) if branch and side == "buy" else None
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
            self.mark_selected_for_order(signal_id)
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
            self.order_none_events.append({"schema_version": SCHEMA_VERSION, "signal_id": signal_id, "reason_code": "UNKNOWN_ORDER_NONE"})
            self.set_terminal_once(signal_id, "ORDER_NOT_CREATED", "UNKNOWN_ORDER_NONE")
        elif signal_id and status == "rejected":
            self.set_terminal_once(signal_id, "ORDER_REJECTED", "ORDER_REJECTED")

    def finalize(self, engine=None, out_dir: str | None = None):
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
                self.set_terminal_once(signal_id, "FILLED", "FILLED")
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
        states = defaultdict(int)
        for row in self.signal_events:
            states[row.get("terminal_state") or "UNRESOLVED"] += 1
        total = len(self.signal_events)
        unresolved = states.get("UNRESOLVED", 0)
        return {
            "signal_events": total,
            "decision_events": len(self.decision_events),
            "trade_outcomes": len(self.trade_outcomes),
            "handler_snapshots": len(self.handler_snapshots),
            "mapped_buy_trades": len([x for x in self.trade_outcomes if x.get("entry_amount", 0) > 0]),
            "unmapped_buy_trades": len(self.unmapped_buy_trades),
            "mapped_sell_allocations": len(self.sell_trace_rows),
            "unmapped_sell_trades": len(self.unmapped_sell_trades),
            "terminal_states": dict(sorted(states.items())),
            "closure_rate": 1.0 - unresolved / max(1, total),
            "unresolved": unresolved,
        }
