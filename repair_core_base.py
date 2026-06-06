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
from types import ModuleType

from .context import Context, g
from .data_api import DataAPI
from .order import (
    OrderCost, FixedSlippage, MarketOrderStyle, LimitOrderStyle,
    get_trade_price,
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
                 initial_cash=1000000, data_root=None):
        self.strategy_code = strategy_code
        self.start_date, self.end_date = start_date, end_date
        self.data_api = DataAPI(data_root=data_root)
        self.context = Context(start_date, initial_cash)
        self.handlers = []                      # run_daily 注册的任务
        self.current_time = "09:30"
        self.order_cost = OrderCost()
        self.slippage = FixedSlippage(0)
        self.trades, self.logs = [], []
        self._current_bar_securities = []       # T+1 防重复买入

        # 聚宽查询表
        valuation = type('Valuation', (), {
            'code': JQField('valuation', 'code'),
            'market_cap': JQField('valuation', 'market_cap'),
            'pe_ratio': JQField('valuation', 'pe'),
            'pb_ratio': JQField('valuation', 'pb'),
        })
        indicator = type('Indicator', (), {
            'code': JQField('indicator', 'code'),
            'eps': JQField('indicator', 'eps'),
            'gross_margin': JQField('indicator', 'gross_margin'),
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
            'get_extras':       lambda *a, **kw: self.data_api.get_extras(*a, **kw),
            'get_security_info': lambda *a, **kw: self.data_api.get_security_info(*a, **kw),
            'get_trade_days':   lambda *a, **kw: self.data_api.get_trade_days(*a, **kw),
            'get_all_trade_days': lambda *a, **kw: self.data_api.get_all_trade_days(*a, **kw),
            'order':            self.order,
            'order_target':     self.order_target,
            'order_target_value': self.order_target_value,
            'order_value': self.order_value,
            'history': self.wrapped_history,
            'attribute_history': self.wrapped_attribute_history,
            'get_current_data': self.get_current_data,
            'run_daily':        self.run_daily,
            'log':              self,
            'query':            lambda *a: JQQuery(*a),
            'valuation':        valuation,
            'indicator':        indicator,
            'set_benchmark':    lambda x: None,
            'set_option':       lambda k, v: None,
            'set_order_cost':   self.set_order_cost,
            'set_slippage':     self.set_slippage,
            'OrderCost':        OrderCost,
            'FixedSlippage':    FixedSlippage,
            'MarketOrderStyle': MarketOrderStyle,
            'LimitOrderStyle':  LimitOrderStyle,
        }
        self._mock_modules()

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
    # order / order_target / order_target_value
    # ------------------------------------------------------------------
    def order(self, security, amount, style=None):
        """聚宽兼容 order — 当前持仓 + 变动量计算目标股数"""
        pos = self.context.portfolio.positions.get(security)
        curr_amount = pos.total_amount if pos else 0
        target_amount = curr_amount + amount
        return self.order_target(security, target_amount)

    def set_order_cost(self, cost, type='stock'):
        self.order_cost = cost

    def set_slippage(self, slippage):
        self.slippage = slippage

    # ------------------------------------------------------------------
    # get_fundamentals wrapper
    # ------------------------------------------------------------------
    def wrapped_get_fundamentals(self, query_obj, date=None):
        df = self.data_api.get_fundamentals(query_obj, date=date)
        if hasattr(query_obj, 'filters'):
            for f in query_obj.filters:
                if isinstance(f, tuple) and f[0] == 'in' and f[1] == 'code':
                    df = df[df['code'].isin(f[2])]
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
        return get_trade_price(
            self.data_api, self.context.current_dt, self.current_time, security
        )

    # ------------------------------------------------------------------
    # info / run_daily
    # ------------------------------------------------------------------
    def info(self, msg):
        formatted = f"[{self.context.current_dt.date()} {self.current_time}] INFO: {msg}"
        self.logs.append(formatted)

    def run_daily(self, func, time="09:30"):
        self.handlers.append((func, time))

    # ------------------------------------------------------------------
    # order_target — 核心撮合逻辑
    # ------------------------------------------------------------------
    def order_target(self, security, amount):
        is_etf = security.startswith('511') or security.startswith('159')
        if not is_etf:
            amount = int(round(amount / 100) * 100)
        else:
            amount = int(amount)

        curr_price, high_limit, low_limit, paused = self._get_trade_price(security)
        if curr_price <= 0 or paused:
            return

        pos = self.context.portfolio.positions.get(security)
        curr_amount = pos.total_amount if pos else 0
        diff = int(amount - curr_amount)
        if diff == 0:
            return

        if not is_etf:
            diff = int(round(diff / 100) * 100)
        if diff == 0:
            return

        # 涨跌停检查
        if diff > 0 and curr_price >= high_limit:
            return
        if diff < 0 and curr_price <= low_limit:
            return

        trade_price = curr_price
        value = abs(diff * trade_price)

        # 费用计算
        if security == '511880.XSHG':
            commission, tax = 0.0, 0.0
        else:
            if diff > 0:
                comm_rate = self.order_cost.open_commission
                tax_rate = self.order_cost.open_tax
            else:
                comm_rate = self.order_cost.close_commission
                tax_rate = self.order_cost.close_tax
            commission = round(max(value * comm_rate, self.order_cost.min_commission), 2)
            tax = round(value * tax_rate, 2)

        total_cost = value + commission + tax if diff > 0 else -value + commission + tax

        # 资金不足时调整买入量
        if diff > 0 and total_cost > self.context.portfolio.available_cash:
            max_available = self.context.portfolio.available_cash - self.order_cost.min_commission
            if max_available < 0:
                return
            rates = (self.order_cost.open_commission if diff > 0 else 0) + \
                    (self.order_cost.open_tax if diff > 0 else 0)
            if security == '511880.XSHG':
                rates = 0
            max_shares_float = max_available / (trade_price * (1 + rates))
            diff = int((max_shares_float // 100) * 100)
            if diff <= 0:
                return
            value = diff * trade_price
            if security == '511880.XSHG':
                commission, tax = 0.0, 0.0
            else:
                commission = round(max(value * self.order_cost.open_commission,
                                       self.order_cost.min_commission), 2)
                tax = round(value * self.order_cost.open_tax, 2)
            total_cost = value + commission + tax

        # 执行交易
        self.context.portfolio.available_cash -= total_cost
        if security not in self.context.portfolio.positions:
            from .context import Position
            self.context.portfolio.positions[security] = Position(security, trade_price, 0)

        p_obj = self.context.portfolio.positions[security]
        p_obj.total_amount += diff
        p_obj.price = trade_price

        if p_obj.total_amount <= 0:
            del self.context.portfolio.positions[security]

        self.trades.append({
            'time': f"{self.context.current_dt.date()} {self.current_time}",
            'code': security, 'amount': diff, 'price': trade_price,
            'commission': commission, 'tax': tax,
        })

    # ------------------------------------------------------------------
    # order_target_value — 按目标市值下单
    # ------------------------------------------------------------------
    def order_target_value(self, security, value):
        curr_price, _, _, _ = self._get_trade_price(security)
        if curr_price <= 0:
            return
        target_amount = int(value / curr_price / 100) * 100
        self.order_target(security, target_amount)

    # ------------------------------------------------------------------
    # order_value — 按金额下单（聚宽兼容）
    # order_value(security, value, style=None)
    #   value > 0: 买入 floor(value / price / 100) * 100 股
    #   value < 0: 卖出 floor(abs(value) / price / 100) * 100 股
    # ------------------------------------------------------------------
    def order_value(self, security, value, style=None):
        curr_price, _, _, _ = self._get_trade_price(security)
        if curr_price <= 0:
            return None
        amount = int(value / curr_price / 100) * 100
        if amount == 0:
            return None
        return self.order(security, amount, style=style)

    # ------------------------------------------------------------------
    # history — 多标的历史数据查询（聚宽兼容）
    # ------------------------------------------------------------------
    def wrapped_history(self, count, unit='1d', field='close',
                        security_list=None, df=True, fq=None,
                        skip_paused=False, fq_ref_date=None):
        if security_list is None:
            return {} if not df else pd.DataFrame()
        result = self.data_api.get_price(
            list(security_list) if not isinstance(security_list, str) else [security_list],
            end_date=self.context.current_dt, count=count,
            fields=[field], frequency='daily' if unit == '1d' else unit,
        )
        if df:
            return self._wrap_pandas(result)
        # df=False: 返回 dict {code: [value_t-1, value_t-2, ..., value_t-n]}
        if result.empty:
            return {s: [] for s in (security_list if isinstance(security_list, (list, tuple)) else [security_list])}
        if isinstance(result.columns, pd.MultiIndex):
            # MultiIndex columns: (field, code) or (date, field)
            level_values = result.columns.get_level_values(0)
            if field in level_values:
                # (field, code) structure
                out = {}
                for code in security_list if isinstance(security_list, (list, tuple)) else [security_list]:
                    try:
                        vals = result.xs(code, axis=1, level=1)[field].tolist()
                        out[code] = vals
                    except Exception:
                        out[code] = []
                return out
            # (date, field) structure — extract field
            try:
                sub = result[field]
                if isinstance(sub.columns, pd.MultiIndex):
                    # still multi-level after xs
                    out = {}
                    for code in security_list if isinstance(security_list, (list, tuple)) else [security_list]:
                        try:
                            out[code] = sub[code].tolist() if code in sub.columns else []
                        except Exception:
                            out[code] = []
                    return out
                out = {}
                for s in (security_list if isinstance(security_list, (list, tuple)) else [security_list]):
                    out[s] = sub.tolist()
                return out
            except Exception:
                pass
            return {}
        # 单标的（非 MultiIndex）
        slist = security_list if isinstance(security_list, (list, tuple)) else [security_list]
        out = {}
        for s in slist:
            if s in result.columns:
                try:
                    out[s] = result[s].tolist()
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
                                   df=True, fq=None, fq_ref_date=None):
        if fields is None:
            fields = ['close', 'high', 'low', 'open', 'volume']
        result = self.data_api.get_price(
            security, end_date=self.context.current_dt, count=count,
            fields=fields, frequency='daily' if unit == '1d' else unit,
        )
        return self._wrap_pandas(result) if df else result

    # ------------------------------------------------------------------
    # get_current_price / get_current_data
    # ------------------------------------------------------------------
    def get_current_price(self, security):
        price, _, _, _ = self._get_trade_price(security)
        if price > 0:
            return price
        pos = self.context.portfolio.positions.get(security)
        if pos:
            return pos.price
        return 0

    def get_current_data(self):
        class CurrentData:
            def __init__(self, engine):
                self.engine = engine
                self._cache = {}

            def __getitem__(self, code):
                if code in self._cache:
                    return self._cache[code]
                price = self.engine.get_current_price(code)
                df_daily = self.engine.data_api.get_price(
                    code, end_date=self.engine.context.current_dt, count=1,
                    fields=['high_limit', 'low_limit', 'paused'],
                )
                if df_daily.empty:
                    high, low, paused = 99999, 0, False
                else:
                    high = df_daily['high_limit'].iloc[0]
                    low = df_daily['low_limit'].iloc[0]
                    paused = df_daily.get('paused', pd.Series([False])).iloc[0]
                is_st = self.engine.data_api.get_extras(
                    'is_st', code,
                    start_date=self.engine.context.current_dt,
                ).data.get(code, False)
                res = type('Data', (), {
                    'paused': paused or price <= 0,
                    'is_st': is_st,
                    'last_price': price,
                    'high_limit': high,
                    'low_limit': low,
                })()
                self._cache[code] = res
                return res
        return CurrentData(self)

    # ------------------------------------------------------------------
    # run — 主回测循环
    # ------------------------------------------------------------------
    def run(self):
        exec(self.strategy_code, self.namespace)
        if 'initialize' in self.namespace:
            self.namespace['initialize'](self.context)

        all_days = [
            pd.Timestamp(d)
            for d in self.data_api.get_trade_days("2000-01-01", self.end_date)
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

        self.handlers.sort(key=lambda x: x[1])
        equity_curve = []

        for i, dt in enumerate(trade_days):
            if i % 10 == 0:
                print(f"Progress: {i}/{len(trade_days)} days processed...")
            if i > 0:
                self.context.previous_date = trade_days[i - 1]

            # 执行盘中 handler
            for handler_func, time_str in self.handlers:
                self.current_time = time_str
                h, m = map(int, time_str.split(':'))
                self.context.current_dt = dt.replace(hour=h, minute=m)
                try:
                    handler_func(self.context)
                except Exception as e:
                    self.info(f"执行 Handler ({time_str}) 出错: {e}")

            # EOD 估值
            self.current_time = "15:00"
            self.context.current_dt = dt.replace(hour=15, minute=0)
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

            equity_curve.append({'date': dt, 'value': total_value})

        equity_df = pd.DataFrame(equity_curve)
        metrics = calculate_metrics(equity_df)
        return equity_df, pd.DataFrame(self.trades), self.logs, metrics
