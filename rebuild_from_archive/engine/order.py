"""Order models and trade price lookup helpers."""

import pandas as pd


class OrderCost:
    """JoinQuant-compatible transaction cost model."""

    def __init__(self, open_tax=0, close_tax=0.001,
                 open_commission=0.0003, close_commission=0.0003,
                 min_commission=5):
        self.open_tax = open_tax
        self.close_tax = close_tax
        self.open_commission = open_commission
        self.close_commission = close_commission
        self.min_commission = min_commission


class FixedSlippage:
    """JoinQuant-compatible fixed slippage model."""

    def __init__(self, slippage=0):
        self.slippage = slippage


class PriceRelatedSlippage:
    """JoinQuant-compatible price-related slippage model."""

    def __init__(self, slippage=0.00246):
        self.slippage = slippage


class MarketOrderStyle:
    """JoinQuant-compatible market order style."""
    def __init__(self, *args, **kwargs):
        pass

    def __repr__(self):
        return "MarketOrderStyle()"


class LimitOrderStyle:
    """JoinQuant-compatible limit order style."""

    def __init__(self, limit_price, round=False):
        self.limit_price = limit_price
        self.round = round

    def __repr__(self):
        return f"LimitOrderStyle({self.limit_price})"


class OrderStatus:
    open = "open"
    filled = "filled"
    canceled = "canceled"
    rejected = "rejected"
    held = "held"

    def __init__(self, name):
        self.name = name

    def __eq__(self, other):
        if isinstance(other, OrderStatus):
            return self.name == other.name
        if isinstance(other, str):
            return self.name == other
        return False

    def __repr__(self):
        return f"OrderStatus('{self.name}')"


class Order:
    def __init__(self, order_id, security, amount, price=0.0, style=None, side=None, add_time=None):
        self.order_id = str(order_id)
        self.security = security
        self.amount = amount
        self.filled = 0
        self.price = price
        self.avg_cost = price
        self.style = style or MarketOrderStyle()
        self.side = side or ("buy" if amount > 0 else "sell")
        self.status = OrderStatus("open")
        self.add_time = add_time
        self.commission = 0.0  # Total commission/tax for this order

    @property
    def created_time(self):
        return self.add_time

    def __bool__(self):
        return self.status not in (OrderStatus.rejected, "rejected")

    def __repr__(self):
        return f"Order({self.order_id}, {self.security}, amount={self.amount}, filled={self.filled}, status={self.status.name})"


class Trade:
    """JoinQuant-compatible trade object."""

    def __init__(self, trade_id, order_id, security, price, amount, time):
        self.trade_id = str(trade_id)
        self.order_id = str(order_id)
        self.security = security
        self.price = price
        self.amount = amount
        self.time = time

    def __repr__(self):
        return f"Trade({self.trade_id}, order={self.order_id}, {self.security}, price={self.price}, amount={self.amount})"


def get_trade_price(data_api, current_dt, current_time, security):
    """
    Return the best available simulated trade price for the current backtest time.

    Rules:
    - 09:30-09:35 uses the daily open price.
    - Intraday times use the latest minute close.
    - 14:55 and later uses the daily close price.
    """
    # Normalize time to HH:MM for reliable string comparison
    if ':' in str(current_time):
        parts = str(current_time).split(':')
        norm_time = f"{int(parts[0]):02d}:{int(parts[1]):02d}"
    else:
        norm_time = '09:30'

    if norm_time <= "09:35":
        df = data_api._get_price_raw(
            security, end_date=current_dt.replace(hour=15, minute=0), count=1,
            fields=["open", "close", "high_limit", "low_limit", "paused", "volume"],
            frequency="daily", fq=None
        )
        field = "open"
    elif norm_time >= "14:55":
        df = data_api._get_price_raw(
            security, end_date=current_dt.replace(hour=15, minute=0), count=1,
            fields=["open", "close", "high_limit", "low_limit", "paused", "volume"],
            frequency="daily", fq=None
        )
        field = "close"
    else:
        # Intraday minute data: use ACTUAL current time to find the latest bar
        df = data_api._get_price_raw(
            security, end_date=current_dt, count=1,
            fields=["close", "high_limit", "low_limit", "paused", "volume"],
            frequency="1m", fq=None
        )
        field = "close"
        if df.empty:
            df = data_api._get_price_raw(
                security, end_date=current_dt.replace(hour=15, minute=0), count=1,
                fields=["close", "high_limit", "low_limit", "paused", "volume"],
                frequency="daily", fq=None
            )

    if df.empty:
        return 0, 999999, 0, False, 999999999

    try:
        if isinstance(df.columns, pd.MultiIndex):
            row = df.xs(security, axis=1, level=1).iloc[0]
        else:
            row = df.iloc[0]
        price = round(float(row[field]), 2)
        high_limit = round(float(row.get("high_limit", 999999)), 2)
        low_limit = round(float(row.get("low_limit", 0)), 2)
        paused = row.get("paused", False)
        volume = row.get("volume", 999999999)
        return price, high_limit, low_limit, paused, volume
    except Exception:
        return 0, 999999, 0, False, 999999999
