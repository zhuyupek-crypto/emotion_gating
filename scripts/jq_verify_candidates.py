"""
一进二策略 — 候选池对比验证脚本（修复版）
用 get_price 替代 history，确保日期正确
"""
import pandas as pd
import numpy as np
from jqdata import *
from datetime import datetime, date, timedelta

CHECK_DATES = [
    "2024-03-01", "2024-03-15", "2024-06-05",
    "2024-09-10", "2024-11-20", "2024-01-15",
    "2024-04-22", "2024-08-01",
]
CIRC_MIN, CIRC_MAX = 30.0, 500.0
MONEY_MIN = 6e8
IPO_DAYS = 250
LIMIT_TOL = 0.02


def get_prev_trade_day(trade_date_str):
    parts = trade_date_str.split("-")
    dt = date(int(parts[0]), int(parts[1]), int(parts[2]))
    all_days = list(get_all_trade_days())
    try:
        idx = all_days.index(dt)
        if idx > 0:
            d = all_days[idx - 1]
            return f"{d.year}-{d.month:02d}-{d.day:02d}"
    except ValueError:
        pass
    for i in range(len(all_days)-1, -1, -1):
        if all_days[i] < dt:
            d = all_days[i]
            return f"{d.year}-{d.month:02d}-{d.day:02d}"
    return None


def fetch_ohlc_d1(codes, end_date):
    """获取指定日期的一日行情数据。返回 dict {code: {...}}"""
    if not codes:
        return {}
    df = get_price(codes, end_date=end_date, count=1, frequency='daily',
                   fields=['open', 'close', 'pre_close', 'high', 'low',
                           'high_limit', 'money', 'volume'],
                   panel=False, fill_paused=False, skip_paused=False)
    if df.empty:
        return {}
    result = {}
    for _, row in df.iterrows():
        c = row['code']
        result[c] = {
            'open': float(row['open']) if 'open' in row and not pd.isna(row['open']) else 0,
            'close': float(row['close']) if 'close' in row and not pd.isna(row['close']) else 0,
            'pre_close': float(row['pre_close']) if 'pre_close' in row and not pd.isna(row['pre_close']) else 0,
            'high_limit': float(row['high_limit']) if 'high_limit' in row and not pd.isna(row['high_limit']) else 0,
            'money': float(row['money']) if 'money' in row and not pd.isna(row['money']) else 0,
            'volume': float(row['volume']) if 'volume' in row and not pd.isna(row['volume']) else 0,
        }
    return result


def verify_one_day(today_str):
    lines = []
    lines.append("\n" + "=" * 60)
    lines.append("T日 = " + today_str)
    lines.append("=" * 60)

    try:
        today = datetime.strptime(today_str, "%Y-%m-%d").date()
    except:
        return "\n".join(lines) + "\n日期格式错误"

    prev_str = get_prev_trade_day(today_str)
    if prev_str is None:
        return "\n".join(lines) + "\n无法获取前一交易日"
    prev = datetime.strptime(prev_str, "%Y-%m-%d").date()
    prev2_str = get_prev_trade_day(prev_str)
    prev2 = datetime.strptime(prev2_str, "%Y-%m-%d").date() if prev2_str else None

    lines.append("T-1 = " + prev_str + "  T-2 = " + (prev2_str or "None"))

    # Step 0
    secs = get_all_securities(['stock'], date=prev)
    codes_all = [s for s in secs.index if not s.startswith('688') and not s.startswith('8')]
    lines.append("\n【0】全市场（排除688/8开头）: " + str(len(codes_all)) + " 只")
    if not codes_all:
        return "\n".join(lines)

    # Step 1: 首板识别 (T-1涨停、T-2未涨停)
    d1 = fetch_ohlc_d1(codes_all, prev_str)
    d2 = fetch_ohlc_d1(codes_all, prev2_str) if prev2 else {}

    first_boards = []
    for s in codes_all:
        r1 = d1.get(s)
        if r1 is None or r1['high_limit'] <= 0 or abs(r1['close'] - r1['high_limit']) > LIMIT_TOL:
            continue
        r2 = d2.get(s)
        if r2 and r2['high_limit'] > 0 and abs(r2['close'] - r2['high_limit']) <= LIMIT_TOL:
            continue
        first_boards.append(s)

    lines.append("\n【1】首板宽集: " + str(len(first_boards)) + " 只")
    if not first_boards:
        return "\n".join(lines)

    # Step 2: ST/IPO/市值
    q = query(valuation.code, valuation.circulating_market_cap)
    df_val = get_fundamentals(q, date=prev)
    val_map = dict(zip(df_val['code'], df_val['circulating_market_cap'])) if not df_val.empty else {}

    step2 = []
    st_c, ipo_c, cap_c = 0, 0, 0
    for s in first_boards:
        if s not in secs.index:
            st_c += 1; continue
        name = secs.loc[s, 'display_name']
        if 'ST' in name or 'st' in name or '*' in name:
            st_c += 1; continue
        if (today - secs.loc[s, 'start_date']).days < IPO_DAYS:
            ipo_c += 1; continue
        if s not in val_map:
            cap_c += 1; continue
        circ = float(val_map[s])
        if circ < CIRC_MIN or circ > CIRC_MAX:
            cap_c += 1; continue
        step2.append((s, circ))

    lines.append("  排除ST=" + str(st_c) + "  IPO=" + str(ipo_c) + "  市值=" + str(cap_c))
    lines.append("  通过: " + str(len(step2)) + " 只")

    if step2:
        lines.append("\n  DEBUG - 前10只首板流通市值:")
        for s, circ in step2[:10]:
            lines.append("    " + s + ": circ_mv=" + f"{circ:.2f}" + "亿")
        excluded = []
        for s in first_boards:
            if s in val_map:
                if s not in [x[0] for x in step2]:
                    cv = float(val_map[s])
                    if cv < CIRC_MIN or cv > CIRC_MAX:
                        excluded.append((s, cv))
        if excluded:
            lines.append("  DEBUG - 前5只被市值排除的首板:")
            for s, cv in sorted(excluded, key=lambda x: x[1])[:5]:
                lines.append("    " + s + ": circ=" + f"{cv:.1f}" + "亿 (阀值: " + f"{CIRC_MIN}-{CIRC_MAX}" + "亿)")

    if not step2:
        return "\n".join(lines)

    # Step 3: 成交额 + avg_chg
    codes2 = [s for s, _ in step2]
    d_t1 = fetch_ohlc_d1(codes2, prev_str)
    step3 = []
    mon_c, avg_c = 0, 0
    for s, circ in step2:
        r = d_t1.get(s)
        if r is None:
            mon_c += 1; continue
        m = r['money']
        v = r['volume']
        c = r['close']
        if m < MONEY_MIN:
            mon_c += 1; continue
        if v > 0 and c > 0:
            avg_chg = m / v / c * 1.1 - 1
            if avg_chg < 0.07:
                avg_c += 1; continue
        step3.append((s, circ, m))

    lines.append("  排除money<6亿=" + str(mon_c) + "  avg_chg<7%=" + str(avg_c))
    lines.append("  通过: " + str(len(step3)) + " 只")
    if not step3:
        return "\n".join(lines)

    # Step 4: 开盘涨幅
    codes3 = [s for s, _, _ in step3]
    d_today = fetch_ohlc_d1(codes3, today_str)
    step4 = []
    opn_c = 0
    for s, circ, money in step3:
        r_t = d_today.get(s)
        if r_t is None:
            opn_c += 1; continue
        t_open = r_t['open']
        hl_today = r_t['high_limit']
        yclose = d_t1.get(s, {}).get('close', 0)
        if yclose <= 0 or t_open <= 0:
            opn_c += 1; continue
        if t_open >= hl_today * 0.999:
            opn_c += 1; continue
        open_pct = t_open / yclose - 1
        if open_pct < 0 or open_pct > 0.095:
            opn_c += 1; continue
        step4.append((s, circ, money, open_pct))

    lines.append("  排除开盘异常=" + str(opn_c))
    lines.append("  通过: " + str(len(step4)) + " 只")

    step4.sort(key=lambda x: -(x[2] if x[2] > 0 else 0))
    lines.append("\n最终候选（前10按成交额降序）:")
    lines.append(f"{'代码':<15s} {'流通市值(亿)':<12s} {'成交额(亿)':<12s} {'开盘涨幅':<10s}")
    lines.append('-' * 49)
    for s, circ, money, op in step4[:10]:
        ms = f"{money/1e8:.1f}" if money > 0 else "nan"
        lines.append(f"{s:<15s} {circ:<12.1f} {ms:<12s} {op*100:<10.2f}%")
    lines.append("\nALL(" + str(len(step4)) + "): " + ",".join(s for s, _, _, _ in step4))
    return "\n".join(lines)


# ============================================================
# 执行
# ============================================================
print("=== 一进二候选池对比验证 ===\n")
for dt in CHECK_DATES:
    print(verify_one_day(dt))
print("\n验证结束")
