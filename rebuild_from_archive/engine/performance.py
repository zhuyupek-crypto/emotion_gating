"""Backtest performance metrics."""

import numpy as np


def calculate_metrics(equity_df):
    """
    Calculate basic backtest performance metrics.

    Returns total_return, annual_return, sharpe, max_drawdown, and volatility.
    """
    if equity_df.empty:
        return {}

    equity_df = equity_df.copy()
    equity_df["return"] = equity_df["value"].pct_change().fillna(0)

    total_return = (equity_df["value"].iloc[-1] / equity_df["value"].iloc[0]) - 1
    active_days = len(equity_df)
    annual_return = (1 + total_return) ** (252 / active_days) - 1 if active_days > 0 else 0

    returns = equity_df["return"].values
    volatility = float(np.std(returns, ddof=1) * np.sqrt(252)) if len(returns) > 1 else 0
    sharpe = (annual_return - 0.03) / volatility if volatility > 0 else 0

    peak = np.maximum.accumulate(equity_df["value"].values)
    max_drawdown = float(np.min((equity_df["value"].values - peak) / peak))

    return {
        "total_return": float(total_return),
        "annual_return": float(annual_return),
        "sharpe": float(sharpe),
        "max_drawdown": float(max_drawdown),
        "volatility": float(volatility),
    }
