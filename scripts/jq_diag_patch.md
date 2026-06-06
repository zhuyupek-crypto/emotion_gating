# 聚宽 2022 v227 诊断补丁

## 用法

把下面三段代码**追加到母版-20260506-Clone.py 末尾**（或粘贴到聚宽编辑器的对应位置），然后在聚宽**用 force_v227 模式跑一遍 2022 全年**（其他参数与你产出 `jq_force_v227_2022_raw.txt` 时完全一致）。

跑完后把日志（输出区"日志"标签下的全部文本）**保存为 `jq_diag_2022.txt`** 发给我。

我会拿这份日志和本地逐日比对，精确定位每个分歧的根因——不再猜。

---

## 代码（追加到母版末尾即可，会覆盖三个目标函数）

```python
# ============================================================
# 诊断补丁 v3：每日 log 关键中间状态，便于对齐本地复现
# 重要：回测仍从 2022-01-01 起跑（保持 fb_hist 与正式回测一致）
#       仅在 DIAG_WINDOW 区间内输出 DIAG 日志，控制日志量
#       v3：拦截母版原生 log.info，只放行 [DIAG / [v227买 / [天蝎] 行
# ============================================================
import json as _diag_json

DIAG_START = '2022-06-01'
DIAG_END   = '2022-08-31'

# === 关键：DIAG 写文件而非 log，规避聚宽自身日志干扰 ===
# 聚宽日志区会有大量框架级日志（订单成交流水、系统警告等），无法 monkey-patch 屏蔽。
# 解决方案：把 DIAG 行追加写到聚宽研究环境文件里，跑完后用 read_file 下载。
#
# 用法：
#   1) 回测跑完后，新建一个研究 notebook，在 cell 里执行：
#        with open('jq_diag_2022.txt', 'rb') as f:
#            data = f.read()
#        from jqdata import *
#        # 或直接：把 data 写到一个 markdown cell 下载
#   2) 或在研究环境的"文件管理"里直接看到 jq_diag_2022.txt 并下载
#
# 注意：聚宽 write_file 是追加模式（mode='a'），每次回测开始时先清空
DIAG_FILE = 'jq_diag_2022.txt'

# 用 list 在内存缓冲，定期 flush 到文件，减少 I/O 次数
_DIAG_BUF = []
_DIAG_BUF_MAX = 200  # 攒到 200 行刷一次

def _diag_clear_file():
    """回测启动时清空旧文件。"""
    try:
        write_file(DIAG_FILE, '', append=False)
    except Exception as _e:
        pass  # 文件不存在时忽略

def _diag_flush():
    if not _DIAG_BUF:
        return
    try:
        write_file(DIAG_FILE, ''.join(_DIAG_BUF), append=True)
        _DIAG_BUF[:] = []
    except Exception as _e:
        pass  # 写失败时静默，避免影响回测

def _diag_write(line):
    """缓冲一行 DIAG 日志，攒够了批量写入。"""
    _DIAG_BUF.append(line + '\n')
    if len(_DIAG_BUF) >= _DIAG_BUF_MAX:
        _diag_flush()

# 在 initialize 之外的第一次调用时清空文件
_DIAG_FILE_CLEARED = [False]
def _diag_ensure_init():
    if not _DIAG_FILE_CLEARED[0]:
        _diag_clear_file()
        _DIAG_FILE_CLEARED[0] = True

def _in_diag_window(context):
    today = context.current_dt.strftime('%Y-%m-%d')
    return DIAG_START <= today <= DIAG_END

def _diag_log_state(context, label):
    """每日记录 g.* 关键状态。日志前缀 [DIAG] 便于过滤。"""
    if not _in_diag_window(context):
        return
    _diag_ensure_init()
    today = context.current_dt.strftime('%Y-%m-%d')

    # 1) 模式 / fb 系列 / 路由
    state = {
        'date': today,
        'phase': label,
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
        'win_scale': round(float(_win_scale()), 3) if 'WIN_WINDOW' in globals() else None,
        'recent_trades_len': len(getattr(g, 'recent_trades', [])),
        'recent_trades_win': int(sum(getattr(g, 'recent_trades', []))),
    }
    _diag_write('[DIAG-STATE] ' + _diag_json.dumps(state, ensure_ascii=False))

    # 2) 候选列表（含顺序）
    yjj = []
    for item in getattr(g, 'yjj_candidates', []) or []:
        s = item[0] if isinstance(item, tuple) else item
        yjj.append(s)
    _diag_write('[DIAG-YJJ] %s cands=%d list=%s' % (today, len(yjj), ','.join(yjj)))

    bear = []
    for item in getattr(g, 'bear_candidates', []) or []:
        s = item[0] if isinstance(item, tuple) else item
        bear.append(s)
    _diag_write('[DIAG-BEAR] %s cands=%d list=%s' % (today, len(bear), ','.join(bear)))

    # 3) prev_first_boards（fb_perf 的样本宇宙）
    pfb = list(getattr(g, 'prev_first_boards', []) or [])
    _diag_write('[DIAG-PFB] %s n=%d codes=%s' % (today, len(pfb), ','.join(pfb)))


def _diag_log_buy_attempt(context, label, stock, day_open, yclose, high_limit, open_pct, decision, reason=''):
    """每只候选在 9:26 一进二买入循环里的具体决策日志。"""
    if not _in_diag_window(context):
        return
    _diag_ensure_init()
    today = context.current_dt.strftime('%Y-%m-%d')
    _diag_write('[DIAG-BUY] %s %s stock=%s open=%.4f yclose=%.4f hl=%.4f open_pct=%.4f%% %s %s' % (
        today, label, stock, day_open, yclose, high_limit, open_pct * 100, decision, reason))


def _diag_log(context, msg):
    """简化版：直接写文件。"""
    if not _in_diag_window(context):
        return
    _diag_ensure_init()
    _diag_write(msg)


# ===== 钩子1：在 prepare_all 完成后 / buy 之前 dump 状态 =====
_orig_prepare_all = prepare_all
def prepare_all(context):
    _orig_prepare_all(context)
    _diag_log_state(context, 'after_prepare')


# ===== 钩子2：替换 buy_v227_一进二，加入逐候选决策日志 =====
_orig_yjj = buy_v227_一进二
def buy_v227_一进二(context):
    """完全替代版本：保留原始决策逻辑 + 加 DIAG 日志。"""
    today = context.current_dt.strftime('%Y-%m-%d')
    in_diag = _in_diag_window(context)
    if in_diag:
        _diag_ensure_init()
    if not g.enable_v227:
        if in_diag:
            _diag_write('[DIAG-BLOCK] %s yjj reason=not_enabled active=%s' % (today, g.active))
        return
    if _v227_shock_new_buy_blocked('v227一进二'):
        if in_diag:
            _diag_write('[DIAG-BLOCK] %s yjj reason=shock_cooldown days=%d' % (today, g.v227_shock_cooldown))
        return
    if g.market_mode == 'cautious' and 0.4 <= g.fb_pct < 0.6:
        if in_diag:
            _diag_write('[DIAG-BLOCK] %s yjj reason=cautious_pct_dz fb_pct=%.4f' % (today, g.fb_pct))
        return
    if g.market_mode == 'bull' and g.fb_pct < 0.2:
        if in_diag:
            _diag_write('[DIAG-BLOCK] %s yjj reason=bull_pct_lt_020 fb_pct=%.4f' % (today, g.fb_pct))
        return
    if g.market_mode == 'bull' and g.bull_cooldown > 0:
        if in_diag:
            _diag_write('[DIAG-BLOCK] %s yjj reason=bull_cooldown days=%d' % (today, g.bull_cooldown))
        return
    if g.market_mode == 'bear':
        if in_diag:
            _diag_write('[DIAG-BLOCK] %s yjj reason=bear_mode' % today)
        return
    if g.stoploss_cooldown > 0 and g.market_mode != 'bull':
        if in_diag:
            _diag_write('[DIAG-BLOCK] %s yjj reason=stoploss_cooldown days=%d' % (today, g.stoploss_cooldown))
        return
    if not g.yjj_candidates:
        if in_diag:
            _diag_write('[DIAG-BLOCK] %s yjj reason=no_candidates' % today)
        return

    held = _held_count_by('v227', context)
    slots = g.v227_slots - held
    if in_diag:
        _diag_write('[DIAG-SLOTS] %s yjj v227_slots=%d held=%d free=%d' % (today, g.v227_slots, held, slots))
    if slots <= 0:
        return

    if g.market_mode == 'bull':
        open_hi = 0.095
    else:
        open_hi = 0.07 if g.first_board_perf > 0 else 0.03

    pos_pct = 1.00 if g.market_mode == 'bull' else 0.75
    scale = _win_scale()
    if scale == 0.0:
        if in_diag:
            _diag_write('[DIAG-BLOCK] %s yjj reason=win_scale_zero' % today)
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
            _diag_log_buy_attempt(context, 'yjj', stock, 0, yc, 0, 0, 'SKIP', 'paused')
            continue
        if yc <= 0:
            _diag_log_buy_attempt(context, 'yjj', stock, d.day_open, yc, d.high_limit, 0, 'SKIP', 'yc<=0')
            continue
        if d.day_open >= d.high_limit * 0.999:
            _diag_log_buy_attempt(context, 'yjj', stock, d.day_open, yc, d.high_limit,
                                  d.day_open/yc-1, 'SKIP', 'open_at_limit')
            continue
        open_pct = d.day_open / yc - 1
        if open_pct < 0 or open_pct > open_hi:
            _diag_log_buy_attempt(context, 'yjj', stock, d.day_open, yc, d.high_limit, open_pct,
                                  'SKIP', 'open_pct_out_range[%.3f,%.3f]' % (0, open_hi))
            continue
        if stock in context.portfolio.positions and context.portfolio.positions[stock].total_amount > 0:
            _diag_log_buy_attempt(context, 'yjj', stock, d.day_open, yc, d.high_limit, open_pct,
                                  'SKIP', 'already_held')
            continue
        cash = context.portfolio.available_cash * pos_pct / max(slots - bought, 1)
        if cash > 5000:
            o = order_value(stock, cash, MarketOrderStyle(d.day_open))
            if not o:
                _diag_log_buy_attempt(context, 'yjj', stock, d.day_open, yc, d.high_limit, open_pct,
                                      'SKIP', 'order_failed')
                continue
            g.owner[stock] = 'v227'
            g.buy_mode[stock] = g.market_mode
            log.info('[v227买] %s 开%.1f%% [%s]' % (stock, open_pct * 100, g.market_mode))
            _diag_log_buy_attempt(context, 'yjj', stock, d.day_open, yc, d.high_limit, open_pct,
                                  'BUY', 'cash=%.0f' % cash)
            bought += 1
        else:
            _diag_log_buy_attempt(context, 'yjj', stock, d.day_open, yc, d.high_limit, open_pct,
                                  'SKIP', 'cash<=5000')


# ===== 钩子3：替换 buy_v227_天蝎座，加入逐候选决策日志 =====
_orig_天蝎 = buy_v227_天蝎座
def buy_v227_天蝎座(context):
    today = context.current_dt.strftime('%Y-%m-%d')
    in_diag = _in_diag_window(context)
    if in_diag:
        _diag_ensure_init()
    if not g.enable_v227:
        if in_diag:
            _diag_write('[DIAG-BLOCK] %s scorpion reason=not_enabled' % today)
        return
    if g.market_mode != 'bear':
        if in_diag:
            _diag_write('[DIAG-BLOCK] %s scorpion reason=mode_not_bear mode=%s' % (today, g.market_mode))
        return
    if not g.bear_candidates:
        if in_diag:
            _diag_write('[DIAG-BLOCK] %s scorpion reason=no_candidates' % today)
        return

    if in_diag:
        _diag_write('[DIAG-SCORPION-START] %s n_cands=%d v227_slots=%d held=%d cands=%s' % (
            today, len(g.bear_candidates), g.v227_slots, _held_count_by('v227', context),
            ','.join([(c[0] if isinstance(c, tuple) else c) for c in g.bear_candidates])))
    _orig_天蝎(context)


# ===== 钩子4：每天收盘后 flush 一次缓冲到文件；回测结束时也 flush =====
_orig_tag_leaders = tag_leaders if 'tag_leaders' in globals() else None
def tag_leaders(context):
    if _orig_tag_leaders is not None:
        _orig_tag_leaders(context)
    # 每个交易日尾盘 14:55 flush 一次（tag_leaders 已注册在 14:55）
    if _in_diag_window(context):
        _diag_flush()


def process_initialize(context):
    """聚宽框架会在回测启动时调用此函数，用于初始化。"""
    _diag_clear_file()
    _DIAG_FILE_CLEARED[0] = True


def after_code_changed(context):
    """聚宽内置钩子：策略代码变更时调用。这里用作回测结束兜底 flush。"""
    _diag_flush()
```

---

## 跑完后我需要的产物（v3：写文件不依赖日志区）

**v3 把 DIAG 写到了聚宽研究环境的文件 `jq_diag_2022.txt`，不再走 log，规避聚宽自身日志干扰。**

获取文件的方式：

### 方式 A：研究环境 notebook 下载
1. 回测跑完后，**右上角 → 研究**，新建一个 notebook
2. 在 cell 里执行（也可直接用 `read_file`）：
   ```python
   with open('jq_diag_2022.txt', 'r') as f:
       print(f.read()[:2000])  # 预览前 2000 字符
   ```
3. 在研究环境**左侧文件管理面板**找到 `jq_diag_2022.txt`，右键下载

### 方式 B：研究环境 cell 一次性 dump 到下载
```python
from jqdata import *
with open('jq_diag_2022.txt', 'r') as f:
    data = f.read()
print(len(data), '字符')
# 拷出来贴给我
```

预计 6-8 月约 60 个交易日，每天 5-10 行 DIAG 行，**文件大小约 30-60 KB**，完全可下载。

## 注意事项

- `DIAG_START='2022-06-01'` / `DIAG_END='2022-08-31'` 写死在补丁开头，如需改窗口直接改这两行
- 回测**仍然从 2022-01-01 起跑**（保持 `fb_perf_history` 与正式回测一致），但 DIAG 文件只记录 6-8 月
- 聚宽自身的日志（订单流水、警告等）会照常输出到日志区，**忽略即可**，我们只看文件
- 如果聚宽不允许 `write_file`（某些计费策略限制），改成在日志里加 `[DIAG` 前缀，您下载日志区文本后我用脚本过滤

## 关键校验日期（我会重点对比这些）

| 日期 | 我们要确认什么 |
|---|---|
| 2022-03-18 | 天蝎座为何只买 1 只（slot 限制？候选数？） |
| 2022-06-16 | JQ 的 `fb_pct` 究竟是多少？为什么不买？ |
| 2022-07-05 | JQ 的 `yjj_candidates` 列表是什么？有无 600477/603127？为何不买？ |
| 2022-08-04, 08-05 | JQ 的 `fb_pct` 是多少？模式是什么？ |
| 2022-09-13, 09-21 | 候选与状态对比 |
| 2022-11-21, 11-22 | 候选与状态对比 |
| 2022-12-20, 12-23, 12-27 | 候选与状态对比 |

---

## 如果聚宽日志量太大

可以**只跑 2022-06 到 2022-08** 三个月（含最关键的分歧簇），或者把 `_diag_log_state` 改为只在分歧日期触发：

```python
DIAG_DATES = {'2022-03-18', '2022-06-16', '2022-07-05', '2022-07-06',
              '2022-08-04', '2022-08-05', '2022-09-13', '2022-09-21',
              '2022-11-21', '2022-11-22', '2022-12-20', '2022-12-23', '2022-12-27'}

def _diag_log_state(context, label):
    today = context.current_dt.strftime('%Y-%m-%d')
    if today not in DIAG_DATES:
        return
    # ...其余不变
```

请告诉我你倾向跑全年还是只跑分歧日。
