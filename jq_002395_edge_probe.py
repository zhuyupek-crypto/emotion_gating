# Minimal JoinQuant runtime probe for 002395 execution/price semantics.
#
# Upload this file to JoinQuant as a standalone strategy and run
# 2023-12-12..2023-12-14 with initial cash 1,000,000.
# Return all log lines containing EDGE-002395.


def initialize(context):
    set_option("avoid_future_data", True)
    set_option("use_real_price", True)
    set_benchmark("000300.XSHG")
    set_slippage(FixedSlippage(0.01))
    set_order_cost(OrderCost(
        open_tax=0,
        close_tax=0.001,
        open_commission=0.0003,
        close_commission=0.0003,
        min_commission=5,
    ), type="stock")
    run_daily(edge_002395_buy, "09:28")
    run_daily(edge_002395_snapshot, "09:30")
    run_daily(edge_002395_snapshot, "11:25")
    run_daily(edge_002395_snapshot, "11:30")
    run_daily(edge_002395_snapshot, "14:50")
    run_daily(edge_002395_snapshot, "15:00")


def _position_text(context):
    code = "002395.XSHE"
    try:
        pos = context.portfolio.positions[code]
        return "total=%s closeable=%s avg=%.4f price=%.4f" % (
            int(pos.total_amount),
            int(pos.closeable_amount),
            float(pos.avg_cost),
            float(pos.price),
        )
    except Exception as e:
        return "ERR(%s)" % e


def _pf(context, label):
    p = context.portfolio
    log.info("[EDGE-002395-PF] %s available_cash=%.2f cash=%.2f locked_cash=%.2f positions_value=%.2f total_value=%.2f | position=%s" % (
        label,
        float(p.available_cash),
        float(p.cash),
        float(p.locked_cash),
        float(p.positions_value),
        float(p.total_value),
        _position_text(context),
    ))


def edge_002395_buy(context):
    if context.current_dt.strftime("%Y-%m-%d") != "2023-12-12":
        return
    code = "002395.XSHE"
    try:
        d = get_current_data()[code]
        style = MarketOrderStyle(d.day_open)
        log.info("[EDGE-002395-BUY] dt=%s day_open=%s last=%s hl=%s ll=%s paused=%s" % (
            context.current_dt,
            d.day_open,
            d.last_price,
            d.high_limit,
            d.low_limit,
            d.paused,
        ))
    except Exception as e:
        style = None
        log.info("[EDGE-002395-BUY] current_data ERR(%s)" % e)
    _pf(context, "before buy")
    if style is None:
        order_value(code, 100000)
    else:
        order_value(code, 100000, style)
    _pf(context, "after buy")


def edge_002395_snapshot(context):
    if context.current_dt.strftime("%Y-%m-%d") not in (
        "2023-12-12",
        "2023-12-13",
        "2023-12-14",
    ):
        return
    code = "002395.XSHE"
    try:
        d = get_current_data()[code]
        last_price = d.last_price
        high_limit = d.high_limit
        low_limit = d.low_limit
        day_open = d.day_open
        paused = d.paused
    except Exception as e:
        last_price = "ERR(%s)" % e
        high_limit = ""
        low_limit = ""
        day_open = ""
        paused = ""
    try:
        bars = get_price(
            code,
            end_date=context.current_dt,
            count=5,
            frequency="1m",
            fields=["open", "high", "low", "close"],
            panel=False,
        )
        bar_text = bars.to_csv(index=True).replace("\n", ";")
    except Exception as e:
        bar_text = "ERR(%s)" % e
    try:
        pos = context.portfolio.positions[code]
        avg_cost = float(pos.avg_cost)
        amount = int(pos.total_amount)
        closeable = int(pos.closeable_amount)
        ret_pct = (float(last_price) - avg_cost) / avg_cost * 100
    except Exception as e:
        avg_cost = "ERR(%s)" % e
        amount = ""
        closeable = ""
        ret_pct = ""
    log.info("[EDGE-002395] dt=%s last=%s open=%s hl=%s ll=%s paused=%s avg=%s amount=%s closeable=%s ret=%s bars=%s" % (
        context.current_dt,
        last_price,
        day_open,
        high_limit,
        low_limit,
        paused,
        avg_cost,
        amount,
        closeable,
        ret_pct,
        bar_text,
    ))
