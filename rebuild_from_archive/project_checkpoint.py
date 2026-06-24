"""Application-level checkpoints for emotion-gate warmup runs.

This is not part of the public LocalQuant base.  It serializes only the pieces
needed to resume this strategy after a long warmup window.
"""

from __future__ import annotations

import pickle
from pathlib import Path

from engine.context import g


def _position_to_dict(pos):
    row = {
        "security": pos.security,
        "avg_cost": float(pos.avg_cost),
        "total_amount": int(pos.total_amount),
        "closeable_amount": int(pos.closeable_amount),
        "price": float(pos.price),
    }
    pending = int(getattr(pos, "_pending_buy_amount", 0) or 0)
    if pending:
        row["_pending_buy_amount"] = pending
    return row


def export_engine_checkpoint(engine, as_of_date) -> dict:
    portfolio = engine.context.portfolio
    return {
        "schema": "emotion_gate_checkpoint_v1",
        "as_of_date": str(as_of_date)[:10],
        "portfolio": {
            "available_cash": float(portfolio.available_cash),
            "locked_cash": float(portfolio.locked_cash),
            "positions": {
                code: _position_to_dict(pos)
                for code, pos in portfolio.positions.items()
            },
        },
        "g_data": dict(getattr(g, "_data", {}) or {}),
        "order_id_counter": int(getattr(engine, "_order_id_counter", 0)),
    }


def save_engine_checkpoint(engine, path, as_of_date) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    state = export_engine_checkpoint(engine, as_of_date)
    with path.open("wb") as f:
        pickle.dump(state, f, protocol=pickle.HIGHEST_PROTOCOL)
    return path


def load_engine_checkpoint(path) -> dict:
    with Path(path).open("rb") as f:
        return pickle.load(f)
