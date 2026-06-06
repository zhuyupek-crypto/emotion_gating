"""生成聚宽母版的 DIAG 副本：把母版自身 log.* 调用静默化，并追加 DIAG 补丁。

不动原文件。输出：母版-20260506-Clone-DIAG.py

母版里的 log 调用模式多样：
- log.info('...') / log.warn('...') / log.warning('...') / log.debug('...')
- 既有单行调用，也有跨多行的（参数换行）

策略：用 monkey-patch 拦截（最稳，不需要逐行改）。
在文件开头紧跟 import 之后插入猴子补丁：
    _real_log_info = log.info
    def _silent_info(msg, *a, **kw):
        if isinstance(msg, str) and msg.startswith('[DIAG'):
            _real_log_info(msg, *a, **kw)
    log.info = _silent_info
    log.warn = lambda *a, **kw: None
    log.warning = lambda *a, **kw: None
    log.debug = lambda *a, **kw: None

但聚宽的 log 对象是模块级单例，函数定义里捕获的是模块时的 log 引用——
即便我们在策略代码顶部 monkey-patch，框架内部的成交日志（"成交回报"）
是聚宽自己输出的，无法拦截。这部分用户接受。

我们只关心策略侧 log，因此 monkey-patch 足够。
"""
from pathlib import Path

SRC = Path(r"D:\Work Space\他山之石\情绪门控\母版-20260506-Clone.py")
DST = Path(r"D:\Work Space\他山之石\情绪门控\母版-20260506-Clone-DIAG.py")
PATCH = Path(r"D:\Work Space\他山之石\情绪门控\scripts\jq_diag_patch_body.py")

# === monkey-patch 注入位置：紧跟 from jqdata import * 之后（确保 log 已注入）===
INJECT_AFTER_LINE_CONTAINS = "from jqdata import *"

MONKEY_PATCH = """
# ==============================================================================
# DIAG 补丁 v4：用聚宽官方 log.set_level API 关掉无关日志
# - 把所有 logger 调到 WARNING 及以上
# - DIAG 改用 log.warning 输出（保证可见）
# - 母版自身的 log.info 自动被吞掉
# ==============================================================================
_DIAG_INSTALLED = [False]

def _install_diag_log_filter():
    if _DIAG_INSTALLED[0]:
        return
    try:
        _ = log.set_level
    except (NameError, AttributeError):
        return  # log 还没注入，等运行期再装

    # 聚宽只允许这四类 logger 名称。
    for name in ('order', 'history', 'strategy', 'system'):
        log.set_level(name, 'warning')
    _DIAG_INSTALLED[0] = True

_install_diag_log_filter()
# ==============================================================================
"""

# === 末尾追加：DIAG 钩子 ===
DIAG_PATCH = '''
# ==============================================================================
# DIAG v3-log 模式：6-8 月每日记录关键中间状态到日志（前缀 [DIAG）
# 回测仍从 2022-01-01 起跑，DIAG 仅在 DIAG_START~DIAG_END 输出
# ==============================================================================
import json as _diag_json

DIAG_START = '2022-06-01'
DIAG_END   = '2022-08-31'

def _in_diag(ctx):
    t = ctx.current_dt.strftime('%Y-%m-%d')
    return DIAG_START <= t <= DIAG_END

# 重新拿一次原始 log.info（前面 _silent_info 会拦截，需要绕过去）
def _dlog(msg):
    """DIAG 行用 log.warning 输出，避免被 set_level('xxx','warning') 关掉。"""
    log.warning(msg)

def _diag_state(context):
    if not _in_diag(context):
        return
    today = context.current_dt.strftime('%Y-%m-%d')
    state = {
        'date': today,
        'market_mode': getattr(g, 'market_mode', None),
        'raw_market_mode': getattr(g, 'raw_market_mode', None),
        'first_board_perf': round(float(getattr(g, 'first_board_perf', 0.0)), 6),
        'fb_pct': round(float(getattr(g, 'fb_pct', 0.5)), 4),
        'fb_hist_len': len(getattr(g, 'fb_perf_history', [])),
        'active': getattr(g, 'active', None),
        'enable_v227': bool(getattr(g, 'enable_v227', False)),
        'v227_slots': int(getattr(g, 'v227_slots', 0)),
        'bull_cooldown': int(getattr(g, 'bull_cooldown', 0)),
        'bull_consec_loss': int(getattr(g, 'bull_consec_loss', 0)),
        'bull_sticky': int(getattr(g, 'bull_sticky', 0)),
        'bull_release_guard': bool(getattr(g, 'bull_release_guard', False)),
        'bull_release_confirm_pending': bool(getattr(g, 'bull_release_confirm_pending', False)),
        'stoploss_cooldown': int(getattr(g, 'stoploss_cooldown', 0)),
        'v227_shock_cooldown': int(getattr(g, 'v227_shock_cooldown', 0)),
        'recent_trades_len': len(getattr(g, 'recent_trades', [])),
        'recent_trades_win': int(sum(getattr(g, 'recent_trades', []))),
    }
    _dlog('[DIAG-STATE] ' + _diag_json.dumps(state, ensure_ascii=False))

    yjj = [(item[0] if isinstance(item, tuple) else item)
           for item in (getattr(g, 'yjj_candidates', []) or [])]
    _dlog('[DIAG-YJJ] %s n=%d list=%s' % (today, len(yjj), ','.join(yjj)))

    bear = [(item[0] if isinstance(item, tuple) else item)
            for item in (getattr(g, 'bear_candidates', []) or [])]
    _dlog('[DIAG-BEAR] %s n=%d list=%s' % (today, len(bear), ','.join(bear)))

    pfb = list(getattr(g, 'prev_first_boards', []) or [])
    _dlog('[DIAG-PFB] %s n=%d codes=%s' % (today, len(pfb), ','.join(pfb)))


def _diag_buy_attempt(context, label, stock, day_open, yclose, high_limit, open_pct, decision, reason=''):
    if not _in_diag(context):
        return
    today = context.current_dt.strftime('%Y-%m-%d')
    _dlog('[DIAG-BUY] %s %s stock=%s open=%.4f yclose=%.4f hl=%.4f open_pct=%.4f%% %s %s' % (
        today, label, stock, day_open, yclose, high_limit, open_pct * 100, decision, reason))


# ===== 钩子1：prepare_all 完成后 dump 状态（在所有 buy_* 之前）=====
_orig_prepare_all = prepare_all
def prepare_all(context):
    _install_diag_log_filter()  # 兜底：确保 monkey-patch 已生效（幂等）
    _orig_prepare_all(context)
    _diag_state(context)


# ===== 钩子2：替换 buy_v227_一进二，加入逐候选决策日志 =====
def buy_v227_一进二(context):
    today = context.current_dt.strftime('%Y-%m-%d')
    in_diag = _in_diag(context)
    if not g.enable_v227:
        if in_diag: _dlog('[DIAG-BLOCK] %s yjj reason=not_enabled active=%s' % (today, g.active))
        return
    if _v227_shock_new_buy_blocked('v227一进二'):
        if in_diag: _dlog('[DIAG-BLOCK] %s yjj reason=shock_cooldown days=%d' % (today, g.v227_shock_cooldown))
        return
    if g.market_mode == 'cautious' and 0.4 <= g.fb_pct < 0.6:
        if in_diag: _dlog('[DIAG-BLOCK] %s yjj reason=cautious_pct_dz fb_pct=%.4f' % (today, g.fb_pct))
        return
    if g.market_mode == 'bull' and g.fb_pct < 0.2:
        if in_diag: _dlog('[DIAG-BLOCK] %s yjj reason=bull_pct_lt_020 fb_pct=%.4f' % (today, g.fb_pct))
        return
    if g.market_mode == 'bull' and g.bull_cooldown > 0:
        if in_diag: _dlog('[DIAG-BLOCK] %s yjj reason=bull_cooldown days=%d' % (today, g.bull_cooldown))
        return
    if g.market_mode == 'bear':
        if in_diag: _dlog('[DIAG-BLOCK] %s yjj reason=bear_mode' % today)
        return
    if g.stoploss_cooldown > 0 and g.market_mode != 'bull':
        if in_diag: _dlog('[DIAG-BLOCK] %s yjj reason=stoploss_cooldown days=%d' % (today, g.stoploss_cooldown))
        return
    if not g.yjj_candidates:
        if in_diag: _dlog('[DIAG-BLOCK] %s yjj reason=no_candidates' % today)
        return

    held = _held_count_by('v227', context)
    slots = g.v227_slots - held
    if in_diag: _dlog('[DIAG-SLOTS] %s yjj v227_slots=%d held=%d free=%d' % (today, g.v227_slots, held, slots))
    if slots <= 0:
        return

    open_hi = 0.095 if g.market_mode == 'bull' else (0.07 if g.first_board_perf > 0 else 0.03)
    pos_pct = 1.00 if g.market_mode == 'bull' else 0.75
    scale = _win_scale()
    if scale == 0.0:
        if in_diag: _dlog('[DIAG-BLOCK] %s yjj reason=win_scale_zero' % today)
        return
    pos_pct *= scale
    cd = get_current_data()
    bought = 0
    for item in g.yjj_candidates:
        if bought >= slots:
            break
        stock = item[0] if isinstance(item, tuple) else item
        d = cd[stock]
        yc = g.yjj_yclose.get(stock, 0)
        if d.paused:
            _diag_buy_attempt(context, 'yjj', stock, 0, yc, 0, 0, 'SKIP', 'paused'); continue
        if yc <= 0:
            _diag_buy_attempt(context, 'yjj', stock, d.day_open, yc, d.high_limit, 0, 'SKIP', 'yc<=0'); continue
        if d.day_open >= d.high_limit * 0.999:
            _diag_buy_attempt(context, 'yjj', stock, d.day_open, yc, d.high_limit,
                              d.day_open/yc-1, 'SKIP', 'open_at_limit'); continue
        open_pct = d.day_open / yc - 1
        if open_pct < 0 or open_pct > open_hi:
            _diag_buy_attempt(context, 'yjj', stock, d.day_open, yc, d.high_limit, open_pct,
                              'SKIP', 'open_pct_out_range[0,%.3f]' % open_hi); continue
        if stock in context.portfolio.positions and context.portfolio.positions[stock].total_amount > 0:
            _diag_buy_attempt(context, 'yjj', stock, d.day_open, yc, d.high_limit, open_pct,
                              'SKIP', 'already_held'); continue
        cash = context.portfolio.available_cash * pos_pct / max(slots - bought, 1)
        if cash > 5000:
            o = order_value(stock, cash, MarketOrderStyle(d.day_open))
            if not o:
                _diag_buy_attempt(context, 'yjj', stock, d.day_open, yc, d.high_limit, open_pct,
                                  'SKIP', 'order_failed'); continue
            g.owner[stock] = 'v227'
            g.buy_mode[stock] = g.market_mode
            _diag_buy_attempt(context, 'yjj', stock, d.day_open, yc, d.high_limit, open_pct,
                              'BUY', 'cash=%.0f' % cash)
            bought += 1
        else:
            _diag_buy_attempt(context, 'yjj', stock, d.day_open, yc, d.high_limit, open_pct,
                              'SKIP', 'cash<=5000')


# ===== 钩子3：替换 buy_v227_天蝎座，进入前 dump 一次 =====
_orig_天蝎 = buy_v227_天蝎座
def buy_v227_天蝎座(context):
    today = context.current_dt.strftime('%Y-%m-%d')
    in_diag = _in_diag(context)
    if not g.enable_v227:
        if in_diag: _dlog('[DIAG-BLOCK] %s scorpion reason=not_enabled' % today)
        return
    if g.market_mode != 'bear':
        if in_diag: _dlog('[DIAG-BLOCK] %s scorpion reason=mode_not_bear mode=%s' % (today, g.market_mode))
        return
    if not g.bear_candidates:
        if in_diag: _dlog('[DIAG-BLOCK] %s scorpion reason=no_candidates' % today)
        return
    if in_diag:
        cands_str = ','.join([(c[0] if isinstance(c, tuple) else c) for c in g.bear_candidates])
        _dlog('[DIAG-SCORPION-START] %s n=%d v227_slots=%d held=%d cands=%s' % (
            today, len(g.bear_candidates), g.v227_slots,
            _held_count_by('v227', context), cands_str))
    _orig_天蝎(context)
# ==============================================================================
'''


def main():
    src_text = SRC.read_text(encoding='utf-8')
    src_lines = src_text.split('\n')

    out_lines = []
    injected = False
    for line in src_lines:
        out_lines.append(line)
        if (not injected) and INJECT_AFTER_LINE_CONTAINS in line:
            # 找 import 段的最后一行（这里用第一处 "from collections import deque"）
            # 实际我们在 line 25-28 之间。injected 标记防重复
            out_lines.append(MONKEY_PATCH)
            injected = True

    out_lines.append(DIAG_PATCH)

    DST.write_text('\n'.join(out_lines), encoding='utf-8')
    print(f'写入 {DST}')
    print(f'原文件 {len(src_lines)} 行 → 副本 {len(out_lines)} 行')
    print(f'monkey-patch 注入: {injected}')


if __name__ == '__main__':
    main()
