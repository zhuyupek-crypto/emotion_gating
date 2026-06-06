"""Compatibility shim for jqdata imports used by legacy strategies.
Only provides stubs required for local execution with the custom Engine.
All functions are no-ops or simple wrappers around local utilities.
"""
import sys

_BOUND_ENGINE = None

def bind_engine(engine):
    global _BOUND_ENGINE
    _BOUND_ENGINE = engine

def _get_engine():
    if _BOUND_ENGINE is not None:
        return _BOUND_ENGINE
    frame = sys._getframe(1)
    while frame:
        self_obj = frame.f_locals.get('self')
        if self_obj is not None and (self_obj.__class__.__name__ == 'Engine' or hasattr(self_obj, 'context')):
            return self_obj
        frame = frame.f_back
    return None

def set_option(name, value):
    engine = _get_engine()
    if engine and hasattr(engine, 'set_option'):
        engine.set_option(name, value)

def set_benchmark(code):
    # No-op; benchmark handling is managed elsewhere if needed.
    pass

def set_slippage(slippage):
    engine = _get_engine()
    if engine and hasattr(engine, 'set_slippage'):
        engine.set_slippage(slippage)

def set_order_cost(cost, type='stock'):
    engine = _get_engine()
    if engine and hasattr(engine, 'set_order_cost'):
        engine.set_order_cost(cost, type)

def run_daily(func, time_str):
    engine = _get_engine()
    if engine and hasattr(engine, 'run_daily'):
        engine.run_daily(func, time_str)

def __getattr__(name):
    engine = _get_engine()
    if engine is not None and hasattr(engine, 'namespace') and name in engine.namespace:
        return engine.namespace[name]
    raise AttributeError(name)
