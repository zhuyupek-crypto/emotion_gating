# JoinQuant research/backtest probe for 2023 edge semantics.
#
# Usage:
# 1. Paste the hook functions below into a copy of the mother strategy.
# 2. In initialize(context), call install_edge_probe(context) after the
#    strategy's own run_daily registrations.
# 3. Run 2023-02-20..2023-03-02 with the same capital/settings as the mother
#    backtest, then return the EDGE lines from log.txt.
#
# This probe only logs runtime state. It should not change orders or strategy
# state.


def _edge_fmt_positions(context):
    parts = []
    for code, pos in context.portfolio.positions.items():
        try:
            if pos.total_amount > 0:
                owner = globals().get("g").owner.get(code, "") if hasattr(globals().get("g"), "owner") else ""
                parts.append("%s:%s:%s:cost=%.3f:price=%.3f" % (
                    code, owner, int(pos.total_amount), pos.avg_cost, pos.price
                ))
        except Exception as e:
            parts.append("%s:ERR:%s" % (code, e))
    return "|".join(parts)


def _edge_portfolio_line(context, label):
    p = context.portfolio
    fields = []
    for name in ("available_cash", "cash", "locked_cash", "positions_value", "total_value"):
        try:
            fields.append("%s=%.2f" % (name, float(getattr(p, name))))
        except Exception as e:
            fields.append("%s=ERR(%s)" % (name, e))
    try:
        open_orders = get_open_orders()
        oo = []
        for code, orders in open_orders.items():
            if not isinstance(orders, (list, tuple)):
                orders = [orders]
            for order in orders:
                oo.append("%s:%s:%s:%s" % (
                    code,
                    getattr(order, "amount", ""),
                    getattr(order, "filled", ""),
                    getattr(order, "status", ""),
                ))
        oo_text = "|".join(oo)
    except Exception as e:
        oo_text = "ERR(%s)" % e
    log.info("[EDGE-PF] %s %s | positions=%s | open_orders=%s" % (
        label, " ".join(fields), _edge_fmt_positions(context), oo_text
    ))


def edge_pf_0905(context):
    day = context.current_dt.strftime("%Y-%m-%d")
    if day in ("2023-02-21", "2023-02-22"):
        _edge_portfolio_line(context, day + " 09:05")


def edge_pf_0925(context):
    day = context.current_dt.strftime("%Y-%m-%d")
    if day in ("2023-02-21", "2023-02-22"):
        _edge_portfolio_line(context, day + " 09:25")


def edge_pf_0926_after(context):
    day = context.current_dt.strftime("%Y-%m-%d")
    if day in ("2023-02-21", "2023-02-22"):
        _edge_portfolio_line(context, day + " 09:26-after")


def edge_pf_0930(context):
    day = context.current_dt.strftime("%Y-%m-%d")
    if day in ("2023-02-21", "2023-02-22"):
        _edge_portfolio_line(context, day + " 09:30")


def edge_pf_1500(context):
    day = context.current_dt.strftime("%Y-%m-%d")
    if day in ("2023-02-21", "2023-02-22"):
        _edge_portfolio_line(context, day + " 15:00")


def edge_002229_112x(context):
    day = context.current_dt.strftime("%Y-%m-%d")
    if day != "2023-02-28":
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
        pos = context.portfolio.positions.get(code)
        avg_cost = pos.avg_cost if pos else 0
        amount = pos.total_amount if pos else 0
    except Exception:
        avg_cost = 0
        amount = 0
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
    log.info("[EDGE-002229] dt=%s last=%s hl=%s ll=%s paused=%s avg=%.4f amount=%s bars=%s" % (
        context.current_dt, last_price, high_limit, low_limit, paused, avg_cost, amount, bar_text
    ))


def install_edge_probe(context):
    run_daily(edge_pf_0905, "09:05")
    run_daily(edge_pf_0925, "09:25")
    run_daily(edge_pf_0926_after, "09:26")
    run_daily(edge_pf_0930, "09:30")
    run_daily(edge_pf_1500, "15:00")
    run_daily(edge_002229_112x, "11:27")
    run_daily(edge_002229_112x, "11:28")
    run_daily(edge_002229_112x, "11:29")
    run_daily(edge_002229_112x, "14:46")
    run_daily(edge_002229_112x, "14:47")
    run_daily(edge_002229_112x, "14:48")
    run_daily(edge_002229_112x, "14:50")
