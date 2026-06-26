"""
回测引擎主类
=============

Phase 2 重构后：主循环、namespace、调度逻辑保留在此。
订单数据类在 order.py，绩效计算在 performance.py。
"""

import pandas as pd
import numpy as np
import sys
import traceback
import time
from types import ModuleType

from .context import Context, g
from .data_api import DataAPI
from .order import (
    OrderCost, FixedSlippage, PriceRelatedSlippage, MarketOrderStyle, LimitOrderStyle,
    get_trade_price, Order, OrderStatus, Trade,
)
from .performance import calculate_metrics


# --- 兼容层 ---
class JQSeries(pd.Series):
    @property
    def _constructor(self):
        return JQSeries

    def __getitem__(self, key):
        try:
            return super().__getitem__(key)
        except Exception:
            if key == 0 and len(self) > 0:
                return self.iloc[0]
            raise


class JQDataFrame(pd.DataFrame):
    @property
    def _constructor(self):
        return JQDataFrame

    def __getitem__(self, key):
        try:
            res = super().__getitem__(key)
        except Exception:
            if isinstance(self.columns, pd.MultiIndex):
                try:
                    res = self.xs(key, axis=1, level=0)
                except Exception:
                    raise KeyError(key)
            else:
                raise
        if isinstance(res, pd.Series):
            return JQSeries(res)
        elif isinstance(res, pd.DataFrame):
            return JQDataFrame(res)
        return res


# --- 聚宽查询 DSL ---
class JQField:
    def __init__(self, table, name):
        self.table, self.name = table, name

    def in_(self, coll):
        return ("in", self.name, coll)

    def __gt__(self, val):
        return (">", self.name, val)

    def __ge__(self, val):
        return (">=", self.name, val)

    def __lt__(self, val):
        return ("<", self.name, val)

    def __le__(self, val):
        return ("<=", self.name, val)

    def __eq__(self, val):
        return ("==", self.name, val)

    def __ne__(self, val):
        return ("!=", self.name, val)


class JQQuery:
    def __init__(self, *args):
        self.targets, self.filters = args, []

    def filter(self, *cond):
        self.filters.extend(cond)
        return self

    def order_by(self, *args):
        return self

    def limit(self, *args):
        return self


class Engine:
    """LocalQuant 回测引擎主类"""

    def __init__(self, strategy_code, start_date, end_date,
                 initial_cash=1000000, data_root=None, frequency='daily', compat=None):
        self.strategy_code = strategy_code
        self.start_date, self.end_date = start_date, end_date
        self.frequency = frequency
        self.compat = compat
        if self.compat is not None:
            self.compat.engine = self
        self._current_matching_order = None
        self.data_api = DataAPI(data_root=data_root, compat=compat)
        self.context = Context(start_date, initial_cash)
        self.handlers = []                      # run_daily 注册的任务
        self.current_time = "09:30"
        self.order_cost = OrderCost()
        self._order_costs = {
            'stock': OrderCost(open_tax=0, close_tax=0.001, open_commission=0.0003, close_commission=0.0003, min_commission=5),
            'etf': OrderCost(open_tax=0, close_tax=0, open_commission=0.0001, close_commission=0.0001, min_commission=0),
            'bond': OrderCost(open_tax=0, close_tax=0, open_commission=0.0001, close_commission=0.0001, min_commission=0),
        }
        self.slippage = FixedSlippage(0)
        self.order_volume_ratio = None
        self.trades, self.logs = [], []
        self.daily_portfolio_stats = []
        self.daily_state_snapshots = []
        self.profile_daily = []
        self.profile_handlers = []
        self.on_day_end = None
        self.progress_interval = 1
        # EMOTION_GATE_COMPAT_HOOK:
        # Temporary resume hook for application-level warmup checkpoints.
        # Move this to the future local_quant public extension API when the
        # strategy switches to the shared base.
        self.resume_state = None
        self._current_bar_securities = []       # T+1 防重复买入
        self.orders = {}
        self._pending_orders = []
        self._order_id_counter = 0
        self._trade_price_cache = {}
        self._current_data_cache = {}
        self._daily_current_snapshot_cache = {}
        self._daily_trade_snapshot_cache = {}
        self._pre_open_mark_cache = {}

        # 聚宽查询表
        valuation = type('Valuation', (), {
            'code': JQField('valuation', 'code'),
            'market_cap': JQField('valuation', 'market_cap'),
            'circulating_market_cap': JQField('valuation', 'circulating_market_cap'),
            'pe_ratio': JQField('valuation', 'pe_ratio'),
            'pb_ratio': JQField('valuation', 'pb_ratio'),
            'pe': JQField('valuation', 'pe'),
            'pb': JQField('valuation', 'pb'),
            'ps': JQField('valuation', 'ps'),
            'ps_ttm': JQField('valuation', 'ps_ttm'),
            'pcf_ratio': JQField('valuation', 'pcf_ratio'),
            'turnover_ratio': JQField('valuation', 'turnover_rate'),
        })
        indicator = type('Indicator', (), {
            'code': JQField('indicator', 'code'),
            'eps': JQField('indicator', 'eps'),
            'gross_margin': JQField('indicator', 'gross_margin'),
            'roe': JQField('indicator', 'roe'),
            'roa': JQField('indicator', 'roa'),
        })
        income = type('Income', (), {
            'code': JQField('income', 'code'),
            'operating_revenue': JQField('income', 'operating_revenue'),
        })

        # 核心 namespace —— 策略代码的执行上下文
        self.namespace = {
            'g': g,
            'context': self.context,
            'get_price':        lambda *a, **kw: self._wrap_pandas(
                                    self.data_api.get_price(*a, **kw)),
            'get_bars':         self._wrapped_get_bars,
            'get_all_securities': lambda *a, **kw: self._wrap_pandas(
                                    self.data_api.get_all_securities(*a, **kw)),
            'get_fundamentals': self.wrapped_get_fundamentals,
            'get_valuation':    lambda *a, **kw: self._wrap_pandas(self.data_api.get_valuation(*a, **kw)),
            'get_call_auction': lambda *a, **kw: self._wrap_pandas(self.data_api.get_call_auction(*a, **kw)),
            'get_batch_sealing_points': self.data_api.get_batch_sealing_points,
            'get_extras':       lambda *a, **kw: self.data_api.get_extras(*a, **kw),
            'get_industry_stocks': self.data_api.get_industry_stocks,
            'get_index_stocks': self.data_api.get_index_stocks,
            'get_billboard_list': self.data_api.get_billboard_list,
            'get_security_info': lambda *a, **kw: self.data_api.get_security_info(*a, **kw),
            'get_trade_days':   lambda *a, **kw: self.data_api.get_trade_days(*a, **kw),
            'get_all_trade_days': lambda *a, **kw: self.data_api.get_all_trade_days(*a, **kw),
            'order':            self.order,
            'order_target':     self.order_target,
            'order_target_value': self.order_target_value,
            'order_value':      self.order_value,
            'cancel_order':     self.cancel_order,
            'history':          self.wrapped_history,
            'attribute_history': self.wrapped_attribute_history,
            'get_current_data': self.get_current_data,
            'run_daily':        self.run_daily,
            'log':              self,
            'query':            lambda *a: JQQuery(*a),
            'valuation':        valuation,
            'indicator':        indicator,
            'income':           income,
            'set_benchmark':    lambda x: None,
            'set_option':       self.set_option,
            'set_order_cost':   self.set_order_cost,
            'set_slippage':     self.set_slippage,
            'OrderCost':        OrderCost,
            'FixedSlippage':    FixedSlippage,
            'PriceRelatedSlippage': PriceRelatedSlippage,
            'MarketOrderStyle': MarketOrderStyle,
            'LimitOrderStyle':  LimitOrderStyle,
            'Order':            Order,
            'OrderStatus':      OrderStatus,
            'Trade':            Trade,
        }
        if self.compat is not None and hasattr(self.compat, "namespace_entries"):
            self.namespace.update(self.compat.namespace_entries(self))
        self._mock_modules()
        try:
            import jqdata_compat
            jqdata_compat.bind_engine(self)
        except Exception:
            pass

    def set_resume_state(self, state):
        """EMOTION_GATE_COMPAT_HOOK: install an application checkpoint state."""
        self.resume_state = state

    def _apply_resume_state(self):
        """EMOTION_GATE_COMPAT_HOOK: restore portfolio and strategy globals."""
        state = getattr(self, "resume_state", None)
        if not state:
            return
        try:
            from .context import Position

            portfolio = state.get("portfolio", {})
            self.context.portfolio.available_cash = float(portfolio.get("available_cash", 0.0))
            self.context.portfolio.locked_cash = float(portfolio.get("locked_cash", 0.0))
            positions = {}
            for code, row in (portfolio.get("positions") or {}).items():
                pos = Position(code, float(row.get("price", row.get("avg_cost", 0.0))), int(row.get("total_amount", 0)))
                pos.avg_cost = float(row.get("avg_cost", pos.price))
                pos.closeable_amount = int(row.get("closeable_amount", pos.total_amount))
                pos.price = float(row.get("price", pos.avg_cost))
                pending = int(row.get("_pending_buy_amount", 0) or 0)
                if pending:
                    pos._pending_buy_amount = pending
                positions[code] = pos
            self.context.portfolio.positions = positions
            if "g_data" in state:
                g._data = state.get("g_data") or {}
            self._order_id_counter = int(state.get("order_id_counter", self._order_id_counter))
        except Exception as exc:
            self.info(f"恢复 checkpoint 状态失败: {exc}")

    def _capture_daily_state_snapshot(self, dt):
        win_window = int(self.namespace.get('WIN_WINDOW', 60) or 60)
        recent_trades = list(getattr(g, 'recent_trades', []))
        core_trades = list(getattr(g, 'recent_core_trades', []))
        recent_wr = sum(recent_trades) / len(recent_trades) if len(recent_trades) >= win_window else 0.5
        core_wr = sum(core_trades) / len(core_trades) if len(core_trades) >= win_window else 0.5
        positions = self.context.portfolio.positions
        owners = getattr(g, 'owner', {}) or {}
        self.daily_state_snapshots.append({
            'date': dt.strftime('%Y-%m-%d'),
            'market_mode': getattr(g, 'market_mode', ''),
            'raw_market_mode': getattr(g, 'raw_market_mode', getattr(g, 'market_mode', '')),
            'active': getattr(g, 'active', ''),
            'FB': getattr(g, 'first_board_perf', np.nan),
            'fb_pct': getattr(g, 'fb_pct', np.nan),
            'bull_sticky': getattr(g, 'bull_sticky', 0),
            'bull_cooldown': getattr(g, 'bull_cooldown', 0),
            'bull_release_pending': getattr(g, 'bull_release_confirm_pending', False),
            'bull_release_guard': getattr(g, 'bull_release_guard', False),
            'stoploss_cooldown': getattr(g, 'stoploss_cooldown', 0),
            'rzq_cooldown': getattr(g, 'rzq_cooldown', 0),
            'v227_shock_cooldown': getattr(g, 'v227_shock_cooldown', 0),
            'enable_v227': getattr(g, 'enable_v227', False),
            'enable_rzq': getattr(g, 'enable_rzq', False),
            'enable_zb': getattr(g, 'enable_zb', False),
            'enable_auction': getattr(g, 'enable_auction_yiqian', False),
            'slot_v227': getattr(g, 'v227_slots', 0),
            'slot_rzq': getattr(g, 'rzq_slots', 0),
            'slot_zb': getattr(g, 'zb_slots', 0),
            'slot_auction': getattr(g, 'auction_yiqian_slots', 0),
            'cand_yjj': len(getattr(g, 'yjj_candidates', []) or []),
            'cand_bear': len(getattr(g, 'bear_candidates', []) or []),
            'cand_rzq': len(getattr(g, 'rzq_candidates', []) or []),
            'cand_zb': len(getattr(g, 'zb_candidates', []) or []),
            'cand_auction': len(getattr(g, 'auction_yiqian_candidates', []) or []),
            'auction_daily_value': getattr(g, 'auction_yiqian_daily_value', np.nan),
            'recent_wr': recent_wr,
            'core_wr': core_wr,
            'recent_trade_count': len(recent_trades),
            'core_trade_count': len(core_trades),
            'available_cash': self.context.portfolio.available_cash,
            'locked_cash': self.context.portfolio.locked_cash,
            'positions_count': len(positions),
            'positions': ','.join(sorted(positions.keys())),
            'owners': ','.join(f'{code}:{owners.get(code, "")}' for code in sorted(positions.keys())),
        })

    # ------------------------------------------------------------------
    # get_bars（封装 data_api.get_bars, 自动注入当前回测时间）
    # ------------------------------------------------------------------
    def _wrapped_get_bars(self, security, count, unit='1d', fields=None,
                          include_now=False, df=True, fq_ref_date=None):
        result = self.data_api.get_bars(
            security, count, unit=unit, fields=fields,
            include_now=include_now, df=df, fq_ref_date=fq_ref_date,
            end_dt=self.context.current_dt,
        )
        return self._wrap_pandas(result)

    # ------------------------------------------------------------------
    # order / order_target / order_target_value / order_value
    # ------------------------------------------------------------------
    def _create_order(self, security, amount, style=None):
        self._order_id_counter += 1
        order_id = str(self._order_id_counter)

        inst_type = self._get_instrument_type(security)
        if inst_type == 'index':
            order = Order(
                order_id=order_id,
                security=security,
                amount=amount,
                price=0.0,
                style=style,
                side="buy" if amount > 0 else "sell",
                add_time=self.context.current_dt
            )
            order.status = OrderStatus("rejected")
            self.orders[order_id] = order
            self.info(f"Rejected order for {security}: Indices cannot be traded.")
            return order

        # Apply rounding rules for buy orders
        if amount > 0:
            if inst_type in ('stock', 'etf'):
                amount = int(amount // 100) * 100
            elif inst_type == 'bond':
                amount = int(amount // 10) * 10
            amount = self._apply_jq_order_amount_anomaly(security, amount)

        order = Order(
            order_id=order_id,
            security=security,
            amount=amount,
            price=0.0,
            style=style,
            side="buy" if amount > 0 else "sell",
            add_time=self.context.current_dt
        )
        if isinstance(style, LimitOrderStyle):
            order.price = style.limit_price

        self.orders[order_id] = order

        if amount == 0:
            order.status = OrderStatus("rejected")
            return order

        if self._should_reject_jq_preopen_order(security, amount, style):
            return None

        # T+1 / closeable shares check for selling
        if amount < 0:
            pos = self.context.portfolio.positions.get(security)
            closeable = pos.closeable_amount if pos else 0
            if abs(amount) > closeable:
                order.status = OrderStatus("rejected")
                self.info(f"Rejected sell order for {security}: sell amount {abs(amount)} exceeds closeable amount {closeable}")
                return order
            else:
                # Freeze shares
                pos.closeable_amount -= abs(amount)

        try:
            h, m = map(int, str(self.current_time).split(':')[:2])
            time_val = h * 100 + m
        except Exception:
            time_val = 1500

        # Execution path
        if not isinstance(style, LimitOrderStyle):
            if time_val < 930:
                order.is_pre_open_market = True
                if amount > 0:
                    ref_price = self.data_api.get_order_reference_price(
                        security, self.context.current_dt, phase='pre_open', fq=None
                    )
                    if ref_price <= 0:
                        ref_price, _, _, _, _ = self._get_trade_price(security)
                    cost_model = self._order_costs.get(inst_type, self.order_cost)
                    est_value = ref_price * amount
                    if self._has_zero_fee_override(security):
                        est_fee = 0.0
                    else:
                        est_commission = round(max(est_value * cost_model.open_commission, cost_model.min_commission), 2)
                        est_tax = round(est_value * cost_model.open_tax, 2)
                        est_fee = est_commission + est_tax
                    est_total_cost = est_value + est_fee
                    frozen_cash = min(est_total_cost, max(0.0, self.context.portfolio.available_cash))
                    self.context.portfolio.available_cash -= frozen_cash
                    self.context.portfolio.locked_cash += frozen_cash
                    order._frozen_cash = frozen_cash
                    order._reference_price = ref_price
                self._pending_orders.append(order)
                self._apply_jq_preopen_duplicate_order_anomaly(order)
            else:
                # Market order executes immediately
                self._execute_trade(order)
        else:
            # Limit order
            if amount > 0:
                # Freeze cash for buying
                est_price = style.limit_price
                est_value = est_price * amount
                if self._has_zero_fee_override(security):
                    est_fee = 0.0
                else:
                    cost_model = self._order_costs.get(inst_type, self.order_cost)
                    comm_rate = cost_model.open_commission
                    tax_rate = cost_model.open_tax
                    est_commission = round(max(est_value * comm_rate, cost_model.min_commission), 2)
                    est_tax = round(est_value * tax_rate, 2)
                    est_fee = est_commission + est_tax
                est_total_cost = est_value + est_fee

                if est_total_cost > self.context.portfolio.available_cash:
                    order.status = OrderStatus("rejected")
                    self.info(f"Rejected limit buy order for {security}: cash insufficient (needs {est_total_cost}, available {self.context.portfolio.available_cash})")
                    return order

                # Freeze cash
                self.context.portfolio.available_cash -= est_total_cost
                self.context.portfolio.locked_cash += est_total_cost
                order._frozen_cash = est_total_cost

            self._pending_orders.append(order)

        return order

    def _has_zero_fee_override(self, security):
        return bool(
            self.compat is not None
            and hasattr(self.compat, "has_zero_fee_override")
            and self.compat.has_zero_fee_override(security)
        )

    def _should_reject_jq_preopen_order(self, security, amount, style):
        if amount <= 0 or isinstance(style, LimitOrderStyle):
            return False
        try:
            h, m = map(int, str(self.current_time).split(':')[:2])
            if h * 100 + m >= 930:
                return False
            date_key = self.context.current_dt.strftime('%Y-%m-%d')
        except Exception:
            return False

        time_key = f"{h:02d}:{m:02d}"
        if self.compat is not None and hasattr(self.compat, "should_reject_preopen_cash"):
            should_reject, cash_threshold = self.compat.should_reject_preopen_cash(
                date_key,
                time_key,
                self.context.portfolio.available_cash,
            )
            if should_reject:
                self.info(
                    f"Rejected pre-open market order for {security}: JQ compat cash floor "
                    f"on {date_key} {time_key} (available={self.context.portfolio.available_cash:.2f}, "
                    f"threshold={cash_threshold:.2f})."
                )
                return True

        if (
            self.compat is not None
            and hasattr(self.compat, "should_reject_preopen_order")
            and self.compat.should_reject_preopen_order(date_key, security)
        ):
            self.info(f"Rejected pre-open market order for {security}: JQ compat skip on {date_key}.")
            return True
        return False

    def _apply_jq_preopen_duplicate_order_anomaly(self, order):
        """Replicate observed JQ pending-order drops for same-stock 09:26 duplicates."""
        if order.amount <= 0 or not getattr(order, 'is_pre_open_market', False):
            return
        try:
            date_key = self.context.current_dt.strftime('%Y-%m-%d')
        except Exception:
            return

        if (
            self.compat is None
            or not hasattr(self.compat, "should_drop_first_preopen_duplicate")
            or not self.compat.should_drop_first_preopen_duplicate(date_key, order.security)
        ):
            return

        earlier = [
            pending for pending in self._pending_orders
            if pending is not order
            and pending.security == order.security
            and pending.amount > 0
            and getattr(pending, 'is_pre_open_market', False)
            and pending.status in (OrderStatus.open, "open")
        ]
        if not earlier:
            return

        for pending in earlier:
            pending.status = OrderStatus("canceled")
            if pending in self._pending_orders:
                self._pending_orders.remove(pending)
            self._release_pre_open_buy_resources(pending)

    def _reserve_pre_open_buy_position(self, order, ref_price):
        if order.amount <= 0 or getattr(order, "_reserved_position_amount", 0):
            return
        from .context import Position

        pos = self.context.portfolio.positions.get(order.security)
        if pos is None:
            pos = Position(order.security, ref_price, 0)
            self.context.portfolio.positions[order.security] = pos
        pos.total_amount += order.amount
        pos.price = ref_price
        pos._pending_buy_amount = getattr(pos, "_pending_buy_amount", 0) + order.amount
        order._reserved_position_amount = order.amount

    def _release_pre_open_buy_position(self, order):
        reserved = getattr(order, "_reserved_position_amount", 0)
        if not reserved:
            return
        pos = self.context.portfolio.positions.get(order.security)
        if pos is not None:
            pos.total_amount -= reserved
            pos._pending_buy_amount = max(0, getattr(pos, "_pending_buy_amount", 0) - reserved)
            if pos.total_amount <= 0:
                del self.context.portfolio.positions[order.security]
        order._reserved_position_amount = 0

    def _release_pre_open_buy_cash(self, order):
        frozen_cash = getattr(order, "_frozen_cash", 0)
        if frozen_cash > 0:
            self.context.portfolio.locked_cash -= frozen_cash
            self.context.portfolio.available_cash += frozen_cash
            order._frozen_cash = 0

    def _release_pre_open_buy_resources(self, order):
        self._release_pre_open_buy_cash(order)
        self._release_pre_open_buy_position(order)

    def order(self, security, amount, style=None):
        """聚宽兼容 order — 当前持仓 + 变动量计算目标股数"""
        return self._create_order(security, amount, style)

    def order_target(self, security, amount, style=None):
        inst_type = self._get_instrument_type(security)
        if inst_type in ('stock', 'etf'):
            amount = int(round(amount / 100) * 100)
        elif inst_type == 'bond':
            amount = int(round(amount / 10) * 10)
        else:
            amount = int(amount)

        pos = self.context.portfolio.positions.get(security)
        curr_amount = pos.total_amount if pos else 0
        diff = int(amount - curr_amount)

        if inst_type in ('stock', 'etf'):
            diff = int(round(diff / 100) * 100)
        elif inst_type == 'bond':
            diff = int(round(diff / 10) * 10)

        if diff == 0:
            return None

        return self._create_order(security, diff, style)

    def order_target_value(self, security, value, style=None):
        curr_price, _, _, _, _ = self._get_trade_price(security)
        if curr_price <= 0:
            return None
        price = curr_price
        if isinstance(style, LimitOrderStyle):
            price = style.limit_price
        
        inst_type = self._get_instrument_type(security)
        if inst_type == 'bond':
            target_amount = int(value / price / 10) * 10
        elif inst_type in ('stock', 'etf'):
            target_amount = int(value / price / 100) * 100
        else:
            target_amount = int(value / price)
            
        return self.order_target(security, target_amount, style)

    def order_value(self, security, value, style=None):
        curr_price, _, _, _, _ = self._get_trade_price(security)
        if curr_price <= 0:
            return None
        price = curr_price
        if isinstance(style, LimitOrderStyle):
            price = style.limit_price
        else:
            try:
                h, m = map(int, str(self.current_time).split(':')[:2])
                if h * 100 + m < 930:
                    ref_price = self.data_api.get_order_reference_price(
                        security, self.context.current_dt, phase='pre_open', fq=None
                    )
                    if ref_price > 0:
                        price = ref_price
            except Exception:
                pass
            
        inst_type = self._get_instrument_type(security)
        if inst_type == 'bond':
            amount = int(value / price / 10) * 10
        elif inst_type in ('stock', 'etf'):
            amount = int(value / price / 100) * 100
        else:
            amount = int(value / price)
            
        if amount == 0:
            return None
        return self.order(security, amount, style=style)

    def cancel_order(self, order_id):
        if isinstance(order_id, Order):
            order = order_id
            order_id = order.order_id
        else:
            order_id = str(order_id)
            order = self.orders.get(order_id)

        if not order:
            return False

        if order.status not in (OrderStatus.open, "open"):
            return False

        order.status = OrderStatus("canceled")

        if order in self._pending_orders:
            self._pending_orders.remove(order)

        if order.amount > 0:
            self._release_pre_open_buy_resources(order)
        else:
            pos = self.context.portfolio.positions.get(order.security)
            if pos:
                pos.closeable_amount += abs(order.amount) - abs(order.filled)

        self.info(f"Order {order_id} canceled successfully.")
        return True

    def _match_pending_orders(self):
        still_pending = []
        for order in self._pending_orders:
            try:
                h, m = map(int, str(self.current_time).split(':')[:2])
                time_val = h * 100 + m
            except Exception:
                time_val = 1500
            if getattr(order, 'is_pre_open_market', False) and time_val < 930:
                still_pending.append(order)
                continue

            curr_price, high_limit, low_limit, paused, volume = self._get_trade_price(order.security)
            if curr_price <= 0 or paused:
                still_pending.append(order)
                continue

            if not isinstance(order.style, LimitOrderStyle):
                self._execute_trade(order)
                if order.status in (OrderStatus.open, "open"):
                    still_pending.append(order)
                continue

            filled = False
            if order.amount > 0:
                if curr_price <= order.style.limit_price:
                    if curr_price >= high_limit:
                        still_pending.append(order)
                        continue
                    filled = True
            else:
                if curr_price >= order.style.limit_price:
                    if curr_price <= low_limit:
                        still_pending.append(order)
                        continue
                    filled = True

            if filled:
                self._execute_trade(order, curr_price)
                if order.status in (OrderStatus.open, "open"):
                    still_pending.append(order)
            else:
                still_pending.append(order)

        self._pending_orders = still_pending

    def _cancel_all_pending_orders(self):
        pending = list(self._pending_orders)
        for order in pending:
            self.cancel_order(order)

    def _execute_trade(self, order, match_price=None):
        self._current_matching_order = order
        security = order.security
        amount = order.amount
        inst_type = self._get_instrument_type(security)
        cost_model = self._order_costs.get(inst_type, self.order_cost)

        curr_price, high_limit, low_limit, paused, volume = self._get_trade_price(security)
        if curr_price <= 0 or paused:
            if not isinstance(order.style, LimitOrderStyle):
                order.status = OrderStatus("rejected")
                self._release_pre_open_buy_resources(order)
            return

        if not isinstance(order.style, LimitOrderStyle):
            if amount > 0 and curr_price >= high_limit:
                order.status = OrderStatus("rejected")
                self._release_pre_open_buy_resources(order)
                self.info(f"Rejected market buy for {security} due to limit up")
                return
            if amount < 0 and curr_price <= low_limit:
                order.status = OrderStatus("rejected")
                self.info(f"Rejected market sell for {security} due to limit down")
                return

        if match_price is None:
            base_price = curr_price
        else:
            base_price = order.style.limit_price

        # Calculate slippage
        try:
            h, m = map(int, str(self.current_time).split(':')[:2])
            time_val = h * 100 + m
        except Exception:
            time_val = self.context.current_dt.hour * 100 + self.context.current_dt.minute
        if order.amount < 0 and not isinstance(order.style, LimitOrderStyle):
            slippage_val = 0.0
        elif isinstance(self.slippage, PriceRelatedSlippage):
            slippage_val = base_price * self.slippage.slippage
        elif isinstance(self.slippage, FixedSlippage):
            slippage_val = self.slippage.slippage / 2
        else:
            slippage_val = getattr(self.slippage, "slippage", 0)

        if order.amount > 0:
            trade_price = round(base_price + slippage_val, 2)
        else:
            trade_price = round(base_price - slippage_val, 2)
        trade_price = self._apply_jq_execution_price_anomaly(security, order.amount, trade_price)

        # Apply liquidity volume constraints (order_volume_ratio)
        if self.order_volume_ratio is not None:
            max_fill_vol = volume * self.order_volume_ratio
            if inst_type in ('stock', 'etf'):
                max_fill_vol = int(max_fill_vol // 100) * 100
            elif inst_type == 'bond':
                max_fill_vol = int(max_fill_vol // 10) * 10
            else:
                max_fill_vol = int(max_fill_vol)

            if max_fill_vol <= 0:
                if not isinstance(order.style, LimitOrderStyle):
                    order.status = OrderStatus("rejected")
                    self.info(f"Rejected market order for {security}: execution volume limit is 0 (bar volume={volume})")
                return
        else:
            max_fill_vol = 999999999999

        # Calculate target fill amount in this transaction
        abs_rem = abs(order.amount) - abs(order.filled)
        fill_amount_abs = min(abs_rem, max_fill_vol)

        # Check cash availability for market buy orders
        if order.amount > 0 and not isinstance(order.style, LimitOrderStyle):
            comm_rate = cost_model.open_commission
            tax_rate = cost_model.open_tax
            # Calculate cost for current fill_amount_abs
            fill_value = fill_amount_abs * trade_price
            if self._has_zero_fee_override(security):
                commission, tax = 0.0, 0.0
            else:
                commission = round(max(fill_value * comm_rate, cost_model.min_commission), 2)
                tax = round(fill_value * tax_rate, 2)
            fill_total_cost = fill_value + commission + tax

            if fill_total_cost > self.context.portfolio.available_cash and not getattr(order, 'is_pre_open_market', False):
                max_available = self.context.portfolio.available_cash - cost_model.min_commission
                if max_available < 0:
                    order.status = OrderStatus("rejected")
                    self.info(f"Rejected market buy for {security}: available cash is too low for min commission.")
                    return
                rates = comm_rate + tax_rate
                if self._has_zero_fee_override(security):
                    rates = 0.0
                max_shares_float = max_available / (trade_price * (1 + rates))
                if inst_type in ('stock', 'etf'):
                    max_cash_shares = int(max_shares_float // 100) * 100
                elif inst_type == 'bond':
                    max_cash_shares = int(max_shares_float // 10) * 10
                else:
                    max_cash_shares = int(max_shares_float)

                fill_amount_abs = min(fill_amount_abs, max_cash_shares)
                if fill_amount_abs <= 0:
                    order.status = OrderStatus("rejected")
                    self.info(f"Rejected market buy for {security}: cash insufficient for even 1 lot.")
                    return
        fill_amount_abs = self._apply_jq_fill_amount_anomaly(security, order.amount, fill_amount_abs)

        # Re-calculate value and fees for the final fill_amount_abs
        fill_value = fill_amount_abs * trade_price
        if self._has_zero_fee_override(security):
            commission, tax = 0.0, 0.0
        else:
            if order.amount > 0:
                comm_rate = cost_model.open_commission
                tax_rate = cost_model.open_tax
            else:
                comm_rate = cost_model.close_commission
                tax_rate = cost_model.close_tax
            commission = round(max(fill_value * comm_rate, cost_model.min_commission), 2)
            tax = round(fill_value * tax_rate, 2)

        fill_total_cost = fill_value + commission + tax

        # Deduct or adjust cash
        if order.amount > 0:
            reserved_amount = getattr(order, "_reserved_position_amount", 0)
            base_amount = 0
            base_cost = 0.0
            p_existing = self.context.portfolio.positions.get(security)
            if reserved_amount and p_existing is not None:
                base_amount = max(0, p_existing.total_amount - reserved_amount)
                base_cost = p_existing.avg_cost
            if getattr(order, 'is_pre_open_market', False):
                frozen = getattr(order, "_frozen_cash", 0.0)
                if frozen > 0:
                    self.context.portfolio.locked_cash -= frozen
                    self.context.portfolio.available_cash += frozen - fill_total_cost
                    order._frozen_cash = 0.0
                else:
                    self.context.portfolio.available_cash -= fill_total_cost
            elif isinstance(order.style, LimitOrderStyle):
                frozen_to_deduct = min(fill_total_cost, order._frozen_cash)
                self.context.portfolio.locked_cash -= frozen_to_deduct
                order._frozen_cash -= frozen_to_deduct
                extra_to_deduct = fill_total_cost - frozen_to_deduct
                if extra_to_deduct > 0:
                    self.context.portfolio.available_cash -= extra_to_deduct
            else:
                self.context.portfolio.available_cash -= fill_total_cost
        else:
            net_received = fill_value - commission - tax
            if getattr(self.compat, "immediate_sell_cash_release", False):
                self.context.portfolio.available_cash += net_received
            else:
                try:
                    h, m = map(int, str(self.current_time).split(':')[:2])
                    time_val = h * 100 + m
                except Exception:
                    time_val = 930

                if not isinstance(order.style, LimitOrderStyle) and (self.frequency == 'daily' or time_val <= 930):
                    try:
                        ref_df = self.data_api.get_price(
                            security,
                            end_date=self.context.previous_date,
                            count=1,
                            fields=['close'],
                            frequency='daily',
                            fq=None,
                        )
                        if not ref_df.empty:
                            if isinstance(ref_df.columns, pd.MultiIndex):
                                ref_close = float(ref_df.xs(security, axis=1, level=1)['close'].iloc[-1])
                            elif security in ref_df.columns:
                                ref_close = float(ref_df[security].iloc[-1])
                            else:
                                ref_close = float(ref_df['close'].iloc[-1])
                        else:
                            ref_close = trade_price
                    except Exception:
                        ref_close = trade_price

                    est_received = fill_amount_abs * ref_close
                    self.context.portfolio.available_cash += est_received
                    cash_diff = net_received - est_received
                    if not hasattr(self, '_jq_cash_adjustments'):
                        self._jq_cash_adjustments = []
                    self._jq_cash_adjustments.append(cash_diff)
                else:
                    self.context.portfolio.available_cash += net_received

        # Update position
        if security not in self.context.portfolio.positions:
            from .context import Position
            self.context.portfolio.positions[security] = Position(security, trade_price, 0)

        p_obj = self.context.portfolio.positions[security]
        trade_amount = fill_amount_abs if order.amount > 0 else -fill_amount_abs
        position_delta = trade_amount
        if order.amount > 0:
            reserved_amount = getattr(order, "_reserved_position_amount", 0)
            if reserved_amount:
                if base_amount > 0:
                    p_obj.avg_cost = (base_amount * base_cost + trade_amount * trade_price) / (base_amount + trade_amount)
                else:
                    p_obj.avg_cost = trade_price
                p_obj.total_amount = base_amount + trade_amount
                p_obj._pending_buy_amount = max(0, getattr(p_obj, "_pending_buy_amount", 0) - reserved_amount)
                order._reserved_position_amount = 0
                position_delta = 0
            elif p_obj.total_amount > 0:
                p_obj.avg_cost = (p_obj.total_amount * p_obj.avg_cost + trade_amount * trade_price) / (p_obj.total_amount + trade_amount)
            else:
                p_obj.avg_cost = trade_price

        p_obj.total_amount += position_delta
        p_obj.price = trade_price

        if p_obj.total_amount <= 0:
            del self.context.portfolio.positions[security]

        # Update order stats
        old_filled = order.filled
        if order.amount > 0:
            order.filled += fill_amount_abs
        else:
            order.filled -= fill_amount_abs

        if abs(order.filled) > 0:
            order.avg_cost = (order.avg_cost * abs(old_filled) + fill_amount_abs * trade_price) / abs(order.filled)
        else:
            order.avg_cost = trade_price
        order.price = order.avg_cost
        order.commission += commission + tax

        # Check filled status
        if abs(order.filled) == abs(order.amount):
            order.status = OrderStatus("filled")
            if order.amount > 0 and isinstance(order.style, LimitOrderStyle):
                if order._frozen_cash > 0:
                    self.context.portfolio.locked_cash -= order._frozen_cash
                    self.context.portfolio.available_cash += order._frozen_cash
                    order._frozen_cash = 0
        else:
            if not isinstance(order.style, LimitOrderStyle):
                # Market order: partial fill results in filled status, remainder is canceled
                order.status = OrderStatus("filled")
                if order.amount < 0:
                    unfilled_abs = abs(order.amount) - abs(order.filled)
                    pos = self.context.portfolio.positions.get(security)
                    if pos and unfilled_abs > 0:
                        pos.closeable_amount += unfilled_abs
            else:
                order.status = OrderStatus("open")

        # Record trade
        trade_id = f"t_{len(self.trades) + 1}"
        trade_time = f"{self.context.current_dt.date()} {self.current_time}"
        self.trades.append({
            'time': trade_time,
            'code': security,
            'amount': trade_amount,
            'price': trade_price,
            'commission': commission,
            'tax': tax,
            'trade_id': trade_id,
            'order_id': order.order_id,
        })
        self.info(f"Order {order.order_id} matched/executed: filled {trade_amount} of {security} at {trade_price:.2f}")

    def rollover_day(self):
        for pos in self.context.portfolio.positions.values():
            pos.closeable_amount = pos.total_amount

    def set_order_cost(self, cost, type='stock'):
        self.order_cost = cost
        self._order_costs[type] = cost

    def set_slippage(self, slippage):
        self.slippage = slippage

    def set_option(self, key, value):
        if key == "order_volume_ratio":
            self.order_volume_ratio = value

    def _get_instrument_type(self, security):
        local_code = security.replace(".XSHE", ".SZ").replace(".XSHG", ".SH").replace(".XBSE", ".BJ")
        clean_code = local_code.split('.')[0]
        if clean_code.startswith(('51', '58', '159', '56', '16')):
            return 'etf'
        elif clean_code.startswith(('11', '12', '13', '10')):
            return 'bond'
        if clean_code.startswith('399') or (clean_code.startswith('000') and local_code.endswith('.SH')):
            return 'index'
        return 'stock'

    # ------------------------------------------------------------------
    # get_fundamentals wrapper
    # ------------------------------------------------------------------
    def wrapped_get_fundamentals(self, query_obj, date=None):
        names = set()
        if hasattr(query_obj, 'targets'):
            names.update(t.name for t in query_obj.targets if hasattr(t, 'name'))
        if hasattr(query_obj, 'filters'):
            for f in query_obj.filters:
                if isinstance(f, tuple) and len(f) >= 2:
                    names.add(f[1])
        if names and 'operating_revenue' not in names:
            df = self.data_api._get_indicator_day(date, include_income=False)
        else:
            df = self.data_api.get_fundamentals(query_obj, date=date)
        if df.empty:
            return self._wrap_pandas(df)
        if hasattr(query_obj, 'filters'):
            for f in query_obj.filters:
                if not isinstance(f, tuple):
                    continue
                op, col, val = f[0], f[1], f[2]
                if col not in df.columns:
                    continue
                if op == 'in':
                    df = df[df[col].isin(val)]
                elif op == '>':
                    df = df[df[col] > val]
                elif op == '>=':
                    df = df[df[col] >= val]
                elif op == '<':
                    df = df[df[col] < val]
                elif op == '<=':
                    df = df[df[col] <= val]
                elif op == '==':
                    df = df[df[col] == val]
                elif op == '!=':
                    df = df[df[col] != val]
        if hasattr(query_obj, 'targets'):
            cols = [t.name for t in query_obj.targets if hasattr(t, 'name')]
            if 'code' not in cols:
                cols.append('code')
            df = df[[c for c in cols if c in df.columns]]
        return self._wrap_pandas(df)

    # ------------------------------------------------------------------
    # 兼容性工具
    # ------------------------------------------------------------------
    def _wrap_pandas(self, obj):
        if isinstance(obj, pd.Series):
            return JQSeries(obj)
        if isinstance(obj, pd.DataFrame):
            return JQDataFrame(obj)
        return obj

    def _mock_modules(self):
        for name in ['jqdata', 'jqdatasdk']:
            mock_mod = ModuleType(name)
            for k, v in self.namespace.items():
                setattr(mock_mod, k, v)
            sys.modules[name] = mock_mod

    # ------------------------------------------------------------------
    # 成交价 —— 委托给 order.py 的纯函数
    # ------------------------------------------------------------------
    def _get_trade_price(self, security):
        key = (pd.Timestamp(self.context.current_dt), str(self.current_time), security)
        if key in self._trade_price_cache:
            return self._trade_price_cache[key]
        try:
            parts = str(self.current_time).split(':')
            norm_time = f"{int(parts[0]):02d}:{int(parts[1]):02d}" if len(parts) == 2 else "09:30"
        except Exception:
            norm_time = "09:30"
        if norm_time <= "09:35" or norm_time >= "14:55":
            snap = self._get_daily_trade_snapshot()
            row = snap.get(security)
            if row:
                field = "open" if norm_time <= "09:35" else "close"
                try:
                    price = round(float(row.get(field, 0)), 2)
                    high = round(float(row.get("high_limit", 999999)), 2)
                    low = round(float(row.get("low_limit", 0)), 2)
                    paused = row.get("paused", False)
                    volume = row.get("volume", 999999999)
                    if price > 0:
                        value = (price, high, low, paused, volume)
                        self._trade_price_cache[key] = value
                        return value
                except Exception:
                    pass
        value = get_trade_price(
            self.data_api, self.context.current_dt, self.current_time, security
        )
        value = self._apply_jq_minute_price_anomaly(security, norm_time, value)
        self._trade_price_cache[key] = value
        return value

    def _apply_jq_minute_price_anomaly(self, security, norm_time, value):
        try:
            day_key = pd.Timestamp(self.context.current_dt).strftime('%Y%m%d')
            if self.compat is not None and hasattr(self.compat, "get_minute_price_override"):
                override = self.compat.get_minute_price_override(day_key, norm_time, security)
                if override is not None:
                    return (override, value[1], value[2], value[3], value[4])
        except Exception:
            pass
        return value

    def _apply_jq_execution_price_anomaly(self, security, amount, trade_price):
        try:
            day_key = pd.Timestamp(self.context.current_dt).strftime('%Y%m%d')
            parts = str(self.current_time).split(':')
            norm_time = f"{int(parts[0]):02d}:{int(parts[1]):02d}" if len(parts) >= 2 else "09:30"
            side = "buy" if amount > 0 else "sell"
            if self.compat is not None and hasattr(self.compat, "get_execution_price_override"):
                override = self.compat.get_execution_price_override(day_key, norm_time, security, side)
                if override is not None:
                    return override
            return trade_price
        except Exception:
            return trade_price

    def _apply_jq_order_amount_anomaly(self, security, amount):
        try:
            day_key = pd.Timestamp(self.context.current_dt).strftime('%Y%m%d')
            parts = str(self.current_time).split(':')
            norm_time = f"{int(parts[0]):02d}:{int(parts[1]):02d}" if len(parts) >= 2 else "09:30"
            anomaly_key = (day_key, norm_time, security)
            if self.compat is not None and hasattr(self.compat, "get_order_amount_override"):
                override = self.compat.get_order_amount_override(day_key, norm_time, security, amount=amount)
            else:
                override = None
            if isinstance(override, list):
                counts = getattr(self, "_jq_order_amount_anomaly_counts", None)
                if counts is None:
                    counts = {}
                    self._jq_order_amount_anomaly_counts = counts
                idx = counts.get(anomaly_key, 0)
                counts[anomaly_key] = idx + 1
                if idx < len(override):
                    return override[idx]
                return amount
            if override is not None:
                return override
            return amount
        except Exception:
            return amount

    def _apply_jq_fill_amount_anomaly(self, security, amount, fill_amount_abs):
        try:
            if amount <= 0:
                return fill_amount_abs
            day_key = pd.Timestamp(self.context.current_dt).strftime('%Y%m%d')
            parts = str(self.current_time).split(':')
            norm_time = f"{int(parts[0]):02d}:{int(parts[1]):02d}" if len(parts) >= 2 else "09:30"
            if self.compat is not None and hasattr(self.compat, "get_fill_amount_override"):
                override = self.compat.get_fill_amount_override(day_key, norm_time, security, amount=fill_amount_abs)
                if override is not None:
                    return override
            return fill_amount_abs
        except Exception:
            return fill_amount_abs

    def _get_daily_snapshot_fast(self, fields):
        """Read one-day stock snapshots directly from hdata pivot cache.

        This narrow path avoids rebuilding a full panel through get_price when
        current_data/order matching only needs the current day's daily row.
        """
        day = pd.Timestamp(self.context.current_dt)
        day_int = int(day.strftime('%Y%m%d'))
        fields = list(fields)
        try:
            compat_bypass = getattr(self.compat, 'should_bypass_history_fastpath', None) if self.compat is not None else None
            if compat_bypass is not None and compat_bypass('daily', fields, day):
                return None
        except Exception:
            pass
        try:
            from core import hdata_reader
            hdata_reader._update_pivot_cache({day.year}, fields_needed=set(fields))
            secs = self.data_api.get_all_securities(['stock'], date=day)
            codes = list(secs.index)
            local_codes = self.data_api._normalize(codes)
            out = {code: {} for code in codes}
            for field in fields:
                frame = getattr(hdata_reader, '_PIVOT_CACHE', {}).get(field)
                if frame is None or day_int not in frame.index:
                    return None
                available = frame.columns
                values = frame.loc[day_int]
                for code, local in zip(codes, local_codes):
                    point_value = (
                        self.compat.get_daily_field_override(code, day_int, field)
                        if self.compat is not None and hasattr(self.compat, "get_daily_field_override")
                        else None
                    )
                    if point_value is not None:
                        out[code][field] = point_value
                    elif local in available:
                        out[code][field] = values.get(local)
                    else:
                        out[code][field] = np.nan
            return out
        except Exception:
            return None

    def _get_daily_trade_snapshot(self):
        day_key = pd.Timestamp(self.context.current_dt).strftime('%Y%m%d')
        cached = self._daily_trade_snapshot_cache.get(day_key)
        if cached is not None:
            return cached
        try:
            fields = ['open', 'close', 'high_limit', 'low_limit', 'paused', 'volume']
            cached = self._get_daily_snapshot_fast(fields)
            if cached is None:
                secs = self.data_api.get_all_securities(['stock'], date=self.context.current_dt)
                codes = list(secs.index)
                snap = self.data_api.get_price(
                    codes,
                    end_date=self.context.current_dt.replace(hour=15, minute=0),
                    count=1,
                    fields=fields,
                    frequency='daily',
                    fq=None,
                    panel=False,
                )
                if snap is None or snap.empty:
                    cached = {}
                else:
                    cached = snap.set_index('code')[fields].to_dict('index')
        except Exception:
            cached = {}
        if len(self._daily_trade_snapshot_cache) > 512:
            self._daily_trade_snapshot_cache.pop(next(iter(self._daily_trade_snapshot_cache)))
        self._daily_trade_snapshot_cache[day_key] = cached
        return cached

    # ------------------------------------------------------------------
    # info / run_daily
    # ------------------------------------------------------------------
    def info(self, msg):
        formatted = f"[{self.context.current_dt.date()} {self.current_time}] INFO: {msg}"
        self.logs.append(formatted)

    def run_daily(self, func, time="09:30"):
        self.handlers.append((func, time))

    # ------------------------------------------------------------------
    # history — 多标的历史数据查询（聚宽兼容）
    # ------------------------------------------------------------------
    def wrapped_history(self, count, unit='1d', field='close',
                        security_list=None, df=True, fq='pre',
                        skip_paused=False, fq_ref_date=None):
        if security_list is None:
            return {} if not df else pd.DataFrame()
        end_date = self.context.current_dt
        if unit in ('1d', 'daily'):
            end_date = getattr(self.context, 'previous_date', self.context.current_dt)
        result = self.data_api.get_price(
            list(security_list) if not isinstance(security_list, str) else [security_list],
            end_date=end_date, count=count,
            fields=[field], frequency='daily' if unit == '1d' else unit,
            fq=fq,
        )
        slist = security_list if isinstance(security_list, (list, tuple)) else [security_list]
        if (
            df
            and not isinstance(security_list, str)
            and len(slist) == 1
            and not result.empty
            and not isinstance(result.columns, pd.MultiIndex)
            and list(result.columns) == [field]
        ):
            result = result.rename(columns={field: slist[0]})
        if df:
            return self._wrap_pandas(result)
        if result.empty:
            return {s: [] for s in slist}
        if isinstance(result.columns, pd.MultiIndex):
            level_values = result.columns.get_level_values(0)
            if field in level_values:
                out = {}
                for code in slist:
                    try:
                        vals = result.xs(code, axis=1, level=1)[field].to_numpy()
                        out[code] = vals
                    except Exception:
                        out[code] = []
                return out
            try:
                sub = result[field]
                if isinstance(sub.columns, pd.MultiIndex):
                    out = {}
                    for code in slist:
                        try:
                            out[code] = sub[code].to_numpy() if code in sub.columns else []
                        except Exception:
                            out[code] = []
                    return out
                out = {}
                for s in slist:
                    out[s] = sub.to_numpy()
                return out
            except Exception:
                pass
            return {}
        out = {}
        for s in slist:
            if s in result.columns:
                try:
                    out[s] = result[s].to_numpy()
                except Exception:
                    out[s] = []
            elif len(slist) == 1 and field in result.columns:
                try:
                    out[s] = result[field].to_numpy()
                except Exception:
                    out[s] = []
            else:
                out[s] = []
        return out

    # ------------------------------------------------------------------
    # attribute_history — 单标的历史属性查询（聚宽兼容）
    # ------------------------------------------------------------------
    def wrapped_attribute_history(self, security, count, unit='1d',
                                   fields=None, skip_paused=False,
                                   df=True, fq='pre', fq_ref_date=None):
        if fields is None:
            fields = ['close', 'high', 'low', 'open', 'volume']
        end_date = self.context.current_dt
        if unit in ('1d', 'daily'):
            end_date = getattr(self.context, 'previous_date', self.context.current_dt)
        result = self.data_api.get_price(
            security, end_date=end_date, count=count,
            fields=fields, frequency='daily' if unit == '1d' else unit,
            fq=fq,
        )
        return self._wrap_pandas(result) if df else result

    # ------------------------------------------------------------------
    # get_current_price / get_current_data
    # ------------------------------------------------------------------
    def get_current_price(self, security):
        price, _, _, _, _ = self._get_trade_price(security)
        if price > 0:
            return price
        pos = self.context.portfolio.positions.get(security)
        if pos:
            return pos.price
        return 0

    def _get_daily_current_snapshot(self):
        day_key = pd.Timestamp(self.context.current_dt).strftime('%Y%m%d')
        cached = self._daily_current_snapshot_cache.get(day_key)
        if cached is not None:
            return cached
        try:
            fields = ['open', 'high_limit', 'low_limit', 'paused']
            cached = self._get_daily_snapshot_fast(fields)
            if cached is None:
                secs = self.data_api.get_all_securities(['stock'], date=self.context.current_dt)
                codes = list(secs.index)
                snap = self.data_api.get_price(
                    codes,
                    end_date=self.context.current_dt,
                    count=1,
                    fields=fields,
                    frequency='daily',
                    fq='pre',
                    panel=False,
                )
                if snap is None or snap.empty:
                    cached = {}
                else:
                    cached = snap.set_index('code')[fields].to_dict('index')
        except Exception:
            cached = {}
        if len(self._daily_current_snapshot_cache) > 512:
            self._daily_current_snapshot_cache.pop(next(iter(self._daily_current_snapshot_cache)))
        self._daily_current_snapshot_cache[day_key] = cached
        return cached

    def _refresh_portfolio_prices(self):
        """Refresh held position marks before strategy code reads portfolio value."""
        if not self.context.portfolio.positions:
            return
        try:
            parts = str(self.current_time).split(':')
            time_val = int(parts[0]) * 100 + int(parts[1])
            norm_time = f"{int(parts[0]):02d}:{int(parts[1]):02d}"
        except Exception:
            time_val = 930
            norm_time = "09:30"

        codes = list(self.context.portfolio.positions.keys())
        if time_val < 930:
            end_date = getattr(self.context, 'previous_date', self.context.current_dt)
            mark_key = (pd.Timestamp(end_date).strftime('%Y%m%d'), tuple(sorted(codes)))
            prices = self._pre_open_mark_cache.get(mark_key)
            if prices is None:
                try:
                    prices = self.data_api.get_price(
                        codes, end_date=end_date, count=1,
                        fields=['close'], frequency='daily', fq=None,
                    )
                except Exception:
                    prices = pd.DataFrame()
                if len(self._pre_open_mark_cache) > 1024:
                    self._pre_open_mark_cache.pop(next(iter(self._pre_open_mark_cache)))
                self._pre_open_mark_cache[mark_key] = prices
            for code, pos in self.context.portfolio.positions.items():
                try:
                    if isinstance(prices.columns, pd.MultiIndex):
                        p = prices.xs(code, axis=1, level=1)['close'].iloc[0]
                    elif code in prices.columns:
                        p = prices[code].iloc[0]
                    else:
                        p = prices['close'].iloc[0]
                    if pd.notnull(p) and p > 0:
                        pos.price = float(p)
                except Exception:
                    pass
            return

        if time_val <= 935 or time_val >= 1455:
            snap = self._get_daily_trade_snapshot()
            field = "open" if time_val <= 935 else "close"
            for code, pos in self.context.portfolio.positions.items():
                try:
                    row = snap.get(code)
                    if not row:
                        continue
                    p = float(row.get(field, 0))
                    if pd.notnull(p) and p > 0 and not row.get('paused', False):
                        pos.price = p
                        key = (pd.Timestamp(self.context.current_dt), str(self.current_time), code)
                        self._trade_price_cache[key] = (
                            round(p, 2),
                            round(float(row.get('high_limit', 999999)), 2),
                            round(float(row.get('low_limit', 0)), 2),
                            row.get('paused', False),
                            row.get('volume', 999999999),
                        )
                except Exception:
                    pass
            return

        try:
            prices = self.data_api.get_price(
                codes,
                end_date=self.context.current_dt,
                count=1,
                fields=['close', 'high_limit', 'low_limit', 'paused', 'volume'],
                frequency='1m',
                fq=None,
            )
        except Exception:
            prices = pd.DataFrame()
        if not prices.empty:
            for code, pos in self.context.portfolio.positions.items():
                try:
                    if isinstance(prices.columns, pd.MultiIndex):
                        row = prices.xs(code, axis=1, level=1).iloc[-1]
                    elif len(codes) == 1:
                        row = prices.iloc[-1]
                    elif code in prices.columns:
                        p = prices[code].iloc[-1]
                        row = {'close': p}
                    else:
                        continue
                    p = float(row.get('close', 0))
                    paused = row.get('paused', False)
                    if pd.notnull(p) and p > 0 and not paused:
                        value = self._apply_jq_minute_price_anomaly(
                            code,
                            norm_time,
                            (
                                round(p, 2),
                                round(float(row.get('high_limit', 999999)), 2),
                                round(float(row.get('low_limit', 0)), 2),
                                paused,
                                row.get('volume', 999999999),
                            ),
                        )
                        pos.price = float(value[0])
                        key = (pd.Timestamp(self.context.current_dt), str(self.current_time), code)
                        self._trade_price_cache[key] = value
                except Exception:
                    pass
            return

        for code, pos in self.context.portfolio.positions.items():
            try:
                p, _, _, paused, _ = self._get_trade_price(code)
                if pd.notnull(p) and p > 0 and not paused:
                    pos.price = float(p)
            except Exception:
                pass

    def get_current_data(self):
        class CurrentData:
            def __init__(self, engine):
                self.engine = engine
                self._cache = {}

            def __getitem__(self, code):
                if code in self._cache:
                    return self._cache[code]
                engine_key = (pd.Timestamp(self.engine.context.current_dt), str(self.engine.current_time), code)
                if engine_key in self.engine._current_data_cache:
                    res = self.engine._current_data_cache[engine_key]
                    self._cache[code] = res
                    return res
                price = self.engine.get_current_price(code)
                snap_row = self.engine._get_daily_current_snapshot().get(code)
                if not snap_row:
                    high, low, paused = 99999, 0, False
                else:
                    high = snap_row.get('high_limit', 99999)
                    low = snap_row.get('low_limit', 0)
                    paused = snap_row.get('paused', False)
                is_st = self.engine.data_api.get_extras(
                    'is_st', code,
                    start_date=self.engine.context.current_dt,
                ).data.get(code, False)
                
                day_open = snap_row.get('open', price) if snap_row else price
                res = type('Data', (), {
                    'paused': paused or price <= 0,
                    'is_st': is_st,
                    'last_price': price,
                    'high_limit': high,
                    'low_limit': low,
                    'day_open': day_open,
                })()
                self._cache[code] = res
                self.engine._current_data_cache[engine_key] = res
                return res
        return CurrentData(self)

    # ------------------------------------------------------------------
    # run — 主回测循环
    # ------------------------------------------------------------------
    def run(self):
        try:
            sys.stdout.reconfigure(encoding='utf-8')
            sys.stderr.reconfigure(encoding='utf-8')
        except Exception:
            pass

        exec(self.strategy_code, self.namespace)
        if 'initialize' in self.namespace:
            self.namespace['initialize'](self.context)
        self._apply_resume_state()

        calendar_start = pd.to_datetime(self.start_date) - pd.Timedelta(days=370)
        all_days = [
            pd.Timestamp(d)
            for d in self.data_api.get_trade_days(calendar_start, self.end_date)
        ]
        trade_days = [d for d in all_days
                      if d >= pd.to_datetime(self.start_date)]
        if not trade_days:
            return pd.DataFrame(), pd.DataFrame(), self.logs, {}

        try:
            idx_start = all_days.index(trade_days[0])
            self.context.previous_date = (
                all_days[idx_start - 1] if idx_start > 0 else trade_days[0]
            )
        except Exception:
            self.context.previous_date = pd.to_datetime(self.start_date)

        def get_sort_time(h_item):
            t = h_item[1]
            if t in ('every_bar', 'every_minute', 'open'):
                return "09:30"
            elif t in ('close', 'after_close'):
                return "15:00"
            if ':' in t:
                parts = t.split(':')
                if len(parts) == 2:
                    return f"{int(parts[0]):02d}:{int(parts[1]):02d}"
            return t
        self.handlers.sort(key=get_sort_time)
        equity_curve = []

        for i, dt in enumerate(trade_days):
            profile_day_start = time.perf_counter()
            profile = {
                'date': dt.strftime('%Y-%m-%d'),
                'before_sec': 0.0,
                'refresh_sec': 0.0,
                'match_sec': 0.0,
                'handle_data_sec': 0.0,
                'scheduled_sec': 0.0,
                'eod_sec': 0.0,
                'after_sec': 0.0,
                'rollover_sec': 0.0,
                'trades': 0,
                'logs': 0,
            }
            progress_interval = int(getattr(self, "progress_interval", 1) or 0)
            if progress_interval > 0 and (i % progress_interval == 0 or i == len(trade_days) - 1):
                print(f"Progress: {i}/{len(trade_days)} days processed: {dt.strftime('%Y-%m-%d')}", flush=True)
            if i > 0:
                self.context.previous_date = trade_days[i - 1]

            # --- CALL before_trading_start IF DEFINED ---
            if 'before_trading_start' in self.namespace:
                t0 = time.perf_counter()
                self.current_time = "09:00"
                self.context.current_dt = dt.replace(hour=9, minute=0)
                self._refresh_portfolio_prices()
                try:
                    self.namespace['before_trading_start'](self.context)
                except Exception as e:
                    self.info(f"执行 before_trading_start 出错: {e}")
                elapsed = time.perf_counter() - t0
                profile['before_sec'] += elapsed
                self.profile_handlers.append({
                    'date': dt.strftime('%Y-%m-%d'),
                    'time': '09:00',
                    'handler': 'before_trading_start',
                    'sec': elapsed,
                })

            # 执行盘中 handler
            if self.frequency == 'minute':
                # Minute frequency trading loop
                trading_minutes = set()
                # Morning: 09:31 to 11:30
                for h in range(9, 12):
                    for m in range(0, 60):
                        if h == 9 and m <= 30:
                            continue
                        if h == 11 and m > 30:
                            continue
                        trading_minutes.add(f"{h:02d}:{m:02d}")
                # Afternoon: 13:01 to 15:00
                for h in range(13, 16):
                    for m in range(0, 60):
                        if h == 13 and m == 0:
                            continue
                        if h == 15 and m > 0:
                            continue
                        trading_minutes.add(f"{h:02d}:{m:02d}")

                minutes = list(trading_minutes)
                # Add custom handler times that are outside standard trading minutes
                for _, time_str in self.handlers:
                    if time_str not in ('every_bar', 'every_minute', 'open', 'close', 'after_close'):
                        if ':' in time_str:
                            parts = time_str.split(':')
                            if len(parts) == 2:
                                normalized_time = f"{int(parts[0]):02d}:{int(parts[1]):02d}"
                                if normalized_time not in minutes:
                                    minutes.append(normalized_time)
                
                minutes.sort()

                scheduled_handlers = {}
                for handler_func, time_str in self.handlers:
                    normalized_time = time_str
                    if ':' in time_str:
                        parts = time_str.split(':')
                        if len(parts) == 2:
                            normalized_time = f"{int(parts[0]):02d}:{int(parts[1]):02d}"
                    scheduled_handlers.setdefault(normalized_time, []).append(handler_func)

                for time_str in minutes:
                    self.current_time = time_str
                    h, m = map(int, time_str.split(':'))
                    self.context.current_dt = dt.replace(hour=h, minute=m)

                    handlers_to_run = []
                    if time_str in scheduled_handlers:
                        handlers_to_run.extend(scheduled_handlers[time_str])

                    # Match special JQ time keywords
                    for handler_func, t_opt in self.handlers:
                        if t_opt in ('every_bar', 'every_minute') and time_str in trading_minutes:
                            handlers_to_run.append(handler_func)
                        elif t_opt == 'open' and time_str == '09:31':
                            handlers_to_run.append(handler_func)
                        elif t_opt in ('close', 'after_close') and time_str == '15:00':
                            handlers_to_run.append(handler_func)

                    should_handle_data = time_str in trading_minutes and 'handle_data' in self.namespace
                    if not handlers_to_run and not should_handle_data and not self._pending_orders:
                        continue

                    t0 = time.perf_counter()
                    self._refresh_portfolio_prices()
                    profile['refresh_sec'] += time.perf_counter() - t0
                    # 1. Match pending orders
                    t0 = time.perf_counter()
                    self._match_pending_orders()
                    profile['match_sec'] += time.perf_counter() - t0

                    # 2. Execute handle_data if defined (only during trading minutes)
                    if should_handle_data:
                        t0 = time.perf_counter()
                        try:
                            self.namespace['handle_data'](self.context)
                        except Exception as e:
                            self.info(f"执行 handle_data 出错: {e}")
                        profile['handle_data_sec'] += time.perf_counter() - t0

                    # 3. Execute scheduled daily handlers for this minute
                    for handler_func in handlers_to_run:
                        t0 = time.perf_counter()
                        try:
                            handler_func(self.context)
                        except Exception as e:
                            self.info(f"执行 Handler 出错: {e}")
                        elapsed = time.perf_counter() - t0
                        profile['scheduled_sec'] += elapsed
                        self.profile_handlers.append({
                            'date': dt.strftime('%Y-%m-%d'),
                            'time': time_str,
                            'handler': getattr(handler_func, '__name__', str(handler_func)),
                            'sec': elapsed,
                        })
                        if getattr(handler_func, '__name__', '') == 'prepare_all':
                            self._capture_daily_state_snapshot(dt)

                    # 4. Match pending orders again
                    t0 = time.perf_counter()
                    self._match_pending_orders()
                    profile['match_sec'] += time.perf_counter() - t0
            else:
                # Daily frequency scheduled handler loop
                for handler_func, time_str in self.handlers:
                    self.current_time = time_str
                    if time_str in ('every_bar', 'every_minute', 'open'):
                        h, m = 9, 30
                    elif time_str in ('close', 'after_close'):
                        h, m = 15, 0
                    else:
                        try:
                            h, m = map(int, time_str.split(':'))
                        except Exception:
                            h, m = 9, 30
                    self.context.current_dt = dt.replace(hour=h, minute=m)
                    
                    t0 = time.perf_counter()
                    self._refresh_portfolio_prices()
                    profile['refresh_sec'] += time.perf_counter() - t0
                    t0 = time.perf_counter()
                    self._match_pending_orders()
                    profile['match_sec'] += time.perf_counter() - t0
                    t0 = time.perf_counter()
                    try:
                        handler_func(self.context)
                    except Exception as e:
                        self.info(f"执行 Handler ({time_str}) 出错: {e}")
                    elapsed = time.perf_counter() - t0
                    profile['scheduled_sec'] += elapsed
                    self.profile_handlers.append({
                        'date': dt.strftime('%Y-%m-%d'),
                        'time': time_str,
                        'handler': getattr(handler_func, '__name__', str(handler_func)),
                        'sec': elapsed,
                    })
                    if getattr(handler_func, '__name__', '') == 'prepare_all':
                        self._capture_daily_state_snapshot(dt)
                    t0 = time.perf_counter()
                    self._match_pending_orders()
                    profile['match_sec'] += time.perf_counter() - t0

            # EOD 估值
            t0 = time.perf_counter()
            self.current_time = "15:00"
            self.context.current_dt = dt.replace(hour=15, minute=0)
            
            # Cancel all pending orders at EOD
            self._cancel_all_pending_orders()
            
            if hasattr(self, '_jq_cash_adjustments') and self._jq_cash_adjustments:
                for adj in self._jq_cash_adjustments:
                    self.context.portfolio.available_cash += adj
                self._jq_cash_adjustments = []

            total_value = self.context.portfolio.available_cash

            if self.context.portfolio.positions:
                codes = list(self.context.portfolio.positions.keys())
                prices = self.data_api.get_price(
                    codes, end_date=self.context.current_dt, count=1,
                )
                for code, pos in self.context.portfolio.positions.items():
                    try:
                        if isinstance(prices.columns, pd.MultiIndex):
                            p = prices.xs(code, axis=1, level=1)['close'].iloc[0]
                        else:
                            p = (prices['close'].iloc[0]
                                 if len(codes) == 1 else prices[code].iloc[0])
                        if pd.isnull(p) or p <= 0:
                            p = pos.price
                    except Exception:
                        p = pos.price
                    total_value += pos.total_amount * p
                    pos.price = p
            profile['eod_sec'] += time.perf_counter() - t0

            # --- CALL after_trading_end IF DEFINED ---
            if 'after_trading_end' in self.namespace:
                t0 = time.perf_counter()
                self.current_time = "15:30"
                self.context.current_dt = dt.replace(hour=15, minute=30)
                try:
                    self.namespace['after_trading_end'](self.context)
                except Exception as e:
                    self.info(f"执行 after_trading_end 出错: {e}")
                elapsed = time.perf_counter() - t0
                profile['after_sec'] += elapsed
                self.profile_handlers.append({
                    'date': dt.strftime('%Y-%m-%d'),
                    'time': '15:30',
                    'handler': 'after_trading_end',
                    'sec': elapsed,
                })

            # EOD T+1 Rollover
            t0 = time.perf_counter()
            self.rollover_day()
            profile['rollover_sec'] += time.perf_counter() - t0

            equity_curve.append({'date': dt, 'value': total_value})
            self.daily_portfolio_stats.append({
                'date': dt,
                'available_cash': self.context.portfolio.available_cash,
                'frozen_cash': self.context.portfolio.locked_cash,
                'positions_value': self.context.portfolio.positions_value,
                'total_value': total_value,
                'positions': {
                    sec: {
                        'total_amount': pos.total_amount,
                        'avg_cost': pos.avg_cost,
                        'price': pos.price
                    }
                    for sec, pos in self.context.portfolio.positions.items()
                }
            })

            # Fire dynamic day-end callback
            if getattr(self, 'on_day_end', None) is not None:
                try:
                    self.on_day_end(dt, total_value, self.daily_portfolio_stats[-1])
                except Exception:
                    pass
            profile['trades'] = len(self.trades)
            profile['logs'] = len(self.logs)
            profile['total_sec'] = time.perf_counter() - profile_day_start
            self.profile_daily.append(profile)

        equity_df = pd.DataFrame(equity_curve)
        metrics = calculate_metrics(equity_df)
        return equity_df, pd.DataFrame(self.trades), self.logs, metrics
