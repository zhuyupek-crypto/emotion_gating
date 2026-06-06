import pandas as pd
from datetime import datetime

class Position:
    def __init__(self, security, price, amount):
        self.security = security
        self.avg_cost = price
        self.total_amount = amount
        self.closeable_amount = 0 # T+1 rule: bought today cannot be sold today
        self.price = price # Current price

    def __repr__(self):
        return f"Position({self.security}, cost={self.avg_cost}, amount={self.total_amount})"

class Portfolio:
    def __init__(self, cash=1000000):
        self.available_cash = cash
        self.positions = {} # {code: Position}
        self.locked_cash = 0

    @property
    def frozen_cash(self):
        return self.locked_cash

    @frozen_cash.setter
    def frozen_cash(self, value):
        self.locked_cash = value

    @property
    def positions_value(self):
        return sum(p.price * p.total_amount for p in self.positions.values())

    @property
    def total_value(self):
        return self.available_cash + self.positions_value + self.locked_cash

class Context:
    def __init__(self, start_date, cash=1000000):
        self.portfolio = Portfolio(cash)
        self._current_dt = pd.to_datetime(start_date)
        self.previous_date = None
        self.run_params = None

    @property
    def current_dt(self):
        return self._current_dt

    @current_dt.setter
    def current_dt(self, value):
        self._current_dt = pd.to_datetime(value)
        try:
            from scripts.core import local_jq
            local_jq.set_current_dt(self._current_dt)
        except Exception:
            pass

class GlobalG:
    def __init__(self):
        self._data = {}
    def __getattr__(self, name):
        return self._data.get(name)
    def __setattr__(self, name, value):
        if name == '_data':
            super().__setattr__(name, value)
        else:
            self._data[name] = value

g = GlobalG()
