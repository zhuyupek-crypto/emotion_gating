"""Create a JoinQuant force-v227 copy that observes state without changing logic.

The source is the force branch file, not the normal mother file. The generated
strategy is meant for JoinQuant backtests and logs the state machine surface we
need before looking at trade PnL.
"""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "母版-20260506-Clone-强制单分支回测.py"
DST = ROOT / "母版-20260506-Clone-强制单分支回测-状态机观察.py"

INSERT_BEFORE = "\ndef initialize(context):"


OBSERVER_PATCH = r'''

# ==============================================================================
# force_v227 状态机观察补丁：只加日志，不改策略逻辑。
# 在聚宽回测日志里搜索 SM- 即可导出。
# ==============================================================================
import json as _sm_json

SM_START = '2020-01-01'
SM_END = '2020-12-31'
SM_DATES = set([])  # 非空时只输出这些 YYYY-MM-DD 日期
SM_CAND_LIMIT = 1000


def _sm_in_window(context):
    t = context.current_dt.strftime('%Y-%m-%d')
    if SM_DATES:
        return t in SM_DATES
    return SM_START <= t <= SM_END


def _sm_code(item):
    return item[0] if isinstance(item, tuple) else item


def _sm_codes(items, limit=SM_CAND_LIMIT):
    arr = [_sm_code(x) for x in (items or [])]
    text = ','.join(arr[:limit])
    if len(arr) > limit:
        text += ',...(+%d)' % (len(arr) - limit)
    return text


def _sm_positions(context):
    rows = []
    try:
        for s, p in context.portfolio.positions.items():
            if p.total_amount > 0:
                rows.append('%s:%s:%s:%.4f' % (
                    s,
                    getattr(g, 'owner', {}).get(s, '?'),
                    int(p.total_amount),
                    float(p.avg_cost),
                ))
    except Exception as e:
        rows.append('ERR:%s' % e)
    return '|'.join(sorted(rows))


def _sm_state(context, stage):
    if not _sm_in_window(context):
        return
    try:
        held_v227 = int(_held_count_by('v227', context))
    except Exception:
        held_v227 = None
    try:
        wr = sum(getattr(g, 'recent_trades', [])) / float(len(getattr(g, 'recent_trades', []))) if len(getattr(g, 'recent_trades', [])) else 0.5
    except Exception:
        wr = 0.5
    state = {
        'dt': context.current_dt.strftime('%Y%m%d %H:%M:%S'),
        'stage': stage,
        'branch_test': getattr(g, 'branch_test', None),
        'active': getattr(g, 'active', None),
        'route_active': getattr(g, 'route_active', None),
        'enable_v227': bool(getattr(g, 'enable_v227', False)),
        'v227_slots': int(getattr(g, 'v227_slots', 0)),
        'held_v227': held_v227,
        'raw_market_mode': getattr(g, 'raw_market_mode', None),
        'market_mode': getattr(g, 'market_mode', None),
        'first_board_perf': float(getattr(g, 'first_board_perf', 0.0)),
        'fb_pct': float(getattr(g, 'fb_pct', 0.5)),
        'fb_hist_len': len(getattr(g, 'fb_perf_history', [])),
        'prev_first_n': len(getattr(g, 'prev_first_boards', []) or []),
        'yjj_n': len(getattr(g, 'yjj_candidates', []) or []),
        'bear_n': len(getattr(g, 'bear_candidates', []) or []),
        'bull_sticky': int(getattr(g, 'bull_sticky', 0)),
        'bull_cooldown': int(getattr(g, 'bull_cooldown', 0)),
        'bull_consec_loss': int(getattr(g, 'bull_consec_loss', 0)),
        'bull_release_guard': bool(getattr(g, 'bull_release_guard', False)),
        'bull_release_confirm_pending': bool(getattr(g, 'bull_release_confirm_pending', False)),
        'stoploss_cooldown': int(getattr(g, 'stoploss_cooldown', 0)),
        'v227_shock_cooldown': int(getattr(g, 'v227_shock_cooldown', 0)),
        'recent_trades_len': len(getattr(g, 'recent_trades', [])),
        'recent_trades_win': int(sum(getattr(g, 'recent_trades', []))),
        'recent_trades_wr': float(wr),
        'portfolio_value': float(context.portfolio.total_value),
        'available_cash': float(context.portfolio.available_cash),
        'positions': _sm_positions(context),
    }
    log.info('[SM-STATE] ' + _sm_json.dumps(state, ensure_ascii=False, sort_keys=True))


def _sm_candidate_lines(context, label, candidates):
    if not _sm_in_window(context):
        return
    today = context.current_dt.strftime('%Y%m%d %H:%M:%S')
    log.info('[SM-CANDS] %s %s n=%d list=%s' % (
        today, label, len(candidates or []), _sm_codes(candidates)))
    try:
        cd = get_current_data()
    except Exception as e:
        log.info('[SM-CAND-ERR] %s %s get_current_data=%s' % (today, label, e))
        return
    for item in (candidates or [])[:SM_CAND_LIMIT]:
        s = _sm_code(item)
        try:
            d = cd[s]
            yc = getattr(g, 'yjj_yclose', {}).get(s, 0)
            op = float(getattr(d, 'day_open', 0) or 0)
            hl = float(getattr(d, 'high_limit', 0) or 0)
            ll = float(getattr(d, 'low_limit', 0) or 0)
            paused = bool(getattr(d, 'paused', False))
            held = bool(s in context.portfolio.positions and context.portfolio.positions[s].total_amount > 0)
            opct = op / yc - 1 if yc and yc > 0 else 0
            log.info('[SM-CAND] %s %s stock=%s yc=%.4f open=%.4f high_limit=%.4f low_limit=%.4f opct=%.6f paused=%s held=%s' % (
                today, label, s, float(yc or 0), op, hl, ll, opct, paused, held))
        except Exception as e:
            log.info('[SM-CAND-ERR] %s %s stock=%s err=%s' % (today, label, s, e))


def _sm_call(label, context, fn, cand_label=None, cand_attr=None):
    if not _sm_in_window(context):
        return fn(context)
    before = _sm_positions(context)
    _sm_state(context, label + ':before')
    if cand_attr:
        _sm_candidate_lines(context, cand_label, getattr(g, cand_attr, []))
    result = fn(context)
    after = _sm_positions(context)
    _sm_state(context, label + ':after')
    if before != after:
        log.info('[SM-ACTION] %s %s before=%s after=%s' % (
            context.current_dt.strftime('%Y%m%d %H:%M:%S'), label, before, after))
    return result


def sm_prepare_all(context):
    result = prepare_all(context)
    _sm_state(context, 'prepare_all:after')
    if _sm_in_window(context):
        log.info('[SM-PFB] %s n=%d list=%s' % (
            context.current_dt.strftime('%Y%m%d %H:%M:%S'),
            len(getattr(g, 'prev_first_boards', []) or []),
            _sm_codes(getattr(g, 'prev_first_boards', [])),
        ))
    return result


def sm_buy_v227_yjj(context):
    return _sm_call('buy_v227_yjj', context, buy_v227_一进二, 'yjj', 'yjj_candidates')


def sm_buy_v227_scorpion(context):
    return _sm_call('buy_v227_scorpion', context, buy_v227_天蝎座, 'scorpion', 'bear_candidates')


def sm_sell_v227_morning(context):
    return _sm_call('sell_v227_morning', context, sell_v227_morning)


def sm_check_stop_all(context):
    return _sm_call('check_stop_all', context, check_stop_all)


def sm_sell_v227_midday(context):
    return _sm_call('sell_v227_midday', context, sell_v227_midday)


def sm_sell_v227_afternoon(context):
    return _sm_call('sell_v227_afternoon', context, sell_v227_afternoon)


def sm_tag_leaders(context):
    return _sm_call('tag_leaders', context, tag_leaders)
# ==============================================================================
'''


REPLACEMENTS = {
    "run_daily(prepare_all, '9:05')": "run_daily(sm_prepare_all, '9:05')",
    "run_daily(buy_v227_一进二, '9:26')": "run_daily(sm_buy_v227_yjj, '9:26')",
    "run_daily(buy_v227_天蝎座, '9:30')": "run_daily(sm_buy_v227_scorpion, '9:30')",
    "run_daily(sell_v227_morning, '11:25')": "run_daily(sm_sell_v227_morning, '11:25')",
    "run_daily(check_stop_all, 'every_bar')": "run_daily(sm_check_stop_all, 'every_bar')",
    "run_daily(sell_v227_midday, '13:01')": "run_daily(sm_sell_v227_midday, '13:01')",
    "run_daily(sell_v227_afternoon, '14:50')": "run_daily(sm_sell_v227_afternoon, '14:50')",
    "run_daily(tag_leaders, '14:55')": "run_daily(sm_tag_leaders, '14:55')",
}


def main() -> None:
    text = SRC.read_text(encoding="utf-8")
    if INSERT_BEFORE not in text:
        raise RuntimeError("找不到 initialize 插入点")
    text = text.replace(INSERT_BEFORE, OBSERVER_PATCH + INSERT_BEFORE, 1)
    changed = 0
    for old, new in REPLACEMENTS.items():
        if old in text:
            text = text.replace(old, new, 1)
            changed += 1
    DST.write_text(text, encoding="utf-8")
    print(f"写入 {DST}")
    print(f"run_daily 替换 {changed}/{len(REPLACEMENTS)}")


if __name__ == "__main__":
    main()
