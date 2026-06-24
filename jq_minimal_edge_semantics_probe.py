# Minimal JoinQuant runtime semantics probe.
#
# Upload this file to JoinQuant as a strategy and run 2023-02-21..2023-03-01.
# It does not depend on the emotion-gate strategy state.
# Return log lines containing EDGE-MIN.


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
    run_daily(edge_min_pf_0925, "09:25")
    run_daily(edge_min_order_a, "09:26")
    run_daily(edge_min_order_b, "09:26")
    run_daily(edge_min_buy_002229, "09:27")
    run_daily(edge_min_pf_0926_after, "09:26")
    run_daily(edge_min_pf_0930, "09:30")
    run_daily(edge_min_pf_1500, "15:00")
    run_daily(edge_min_002229_price, "11:27")
    run_daily(edge_min_002229_price, "11:28")
    run_daily(edge_min_002229_price, "11:29")
    run_daily(edge_min_002229_price, "14:46")
    run_daily(edge_min_002229_price, "14:47")
    run_daily(edge_min_002229_price, "14:48")
    run_daily(edge_min_002229_price, "14:50")


def _edge_min_open_orders_text():
    try:
        orders = get_open_orders()
        parts = []
        for code, value in orders.items():
            if not isinstance(value, (list, tuple)):
                value = [value]
            for order in value:
                parts.append("%s:amount=%s:filled=%s:status=%s:price=%s" % (
                    code,
                    getattr(order, "amount", ""),
                    getattr(order, "filled", ""),
                    getattr(order, "status", ""),
                    getattr(order, "price", ""),
                ))
        return "|".join(parts)
    except Exception as e:
        return "ERR(%s)" % e


def _edge_min_positions_text(context):
    parts = []
    for code, pos in context.portfolio.positions.items():
        try:
            if pos.total_amount:
                parts.append("%s:total=%s:closeable=%s:avg=%.4f:price=%.4f" % (
                    code,
                    int(pos.total_amount),
                    int(pos.closeable_amount),
                    pos.avg_cost,
                    pos.price,
                ))
        except Exception as e:
            parts.append("%s:ERR(%s)" % (code, e))
    return "|".join(parts)


def _edge_min_pf(context, label):
    p = context.portfolio
    fields = []
    for name in ("available_cash", "cash", "locked_cash", "positions_value", "total_value"):
        try:
            fields.append("%s=%.2f" % (name, float(getattr(p, name))))
        except Exception as e:
            fields.append("%s=ERR(%s)" % (name, e))
    log.info("[EDGE-MIN-PF] %s %s | positions=%s | open_orders=%s" % (
        label,
        " ".join(fields),
        _edge_min_positions_text(context),
        _edge_min_open_orders_text(),
    ))


def edge_min_pf_0925(context):
    if context.current_dt.strftime("%Y-%m-%d") == "2023-02-21":
        _edge_min_pf(context, "before-dup 09:25")


def edge_min_order_a(context):
    if context.current_dt.strftime("%Y-%m-%d") != "2023-02-21":
        return
    _edge_min_pf(context, "before order A")
    order_value("000581.XSHE", context.portfolio.total_value * 0.30)
    _edge_min_pf(context, "after order A")


def edge_min_order_b(context):
    if context.current_dt.strftime("%Y-%m-%d") != "2023-02-21":
        return
    _edge_min_pf(context, "before order B")
    order_value("000581.XSHE", context.portfolio.total_value * 0.30)
    _edge_min_pf(context, "after order B")


def edge_min_pf_0926_after(context):
    if context.current_dt.strftime("%Y-%m-%d") == "2023-02-21":
        _edge_min_pf(context, "after both 09:26")


def edge_min_pf_0930(context):
    if context.current_dt.strftime("%Y-%m-%d") in ("2023-02-21", "2023-02-22"):
        _edge_min_pf(context, context.current_dt.strftime("%Y-%m-%d") + " 09:30")


def edge_min_pf_1500(context):
    if context.current_dt.strftime("%Y-%m-%d") in ("2023-02-21", "2023-02-22"):
        _edge_min_pf(context, context.current_dt.strftime("%Y-%m-%d") + " 15:00")


def edge_min_buy_002229(context):
    if context.current_dt.strftime("%Y-%m-%d") != "2023-02-27":
        return
    _edge_min_pf(context, "before 002229 buy")
    order_value("002229.XSHE", 100000)
    _edge_min_pf(context, "after 002229 buy")


def edge_min_002229_price(context):
    if context.current_dt.strftime("%Y-%m-%d") != "2023-02-28":
        return
    code = "002229.XSHE"
    try:
        cd = get_current_data()[code]
        last_price = cd.last_price
        high_limit = cd.high_limit
        low_limit = cd.low_limit
        paused = cd.paused
    except Exception as e:
        last_price = "ERR(%s)" % e
        high_limit = ""
        low_limit = ""
        paused = ""
    try:
        bars = get_price(
            code,
            end_date=context.current_dt,
            count=3,
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
        ret_pct = (float(last_price) - avg_cost) / avg_cost * 100
    except Exception as e:
        avg_cost = "ERR(%s)" % e
        amount = ""
        ret_pct = ""
    log.info("[EDGE-MIN-002229] dt=%s last=%s hl=%s ll=%s paused=%s avg=%s amount=%s ret=%s bars=%s" % (
        context.current_dt,
        last_price,
        high_limit,
        low_limit,
        paused,
        avg_cost,
        amount,
        ret_pct,
        bar_text,
    ))
