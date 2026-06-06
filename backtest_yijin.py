"""
backtest_yijin.py — 短线情绪门控 v218「一进二腿」复刻（精确分钟版）

架构说明:
  · 日线数据：全量预加载到内存（~400MB），用于首板识别、过滤、市场模式
  · 分钟数据：按年 parquet 文件 LRU 缓存（300个年份×1.4MB≈420MB），
              仅在 v130 过滤 + 盘中退出时按需读取，不缓存整个10年文件
  · 首板识别：全向量化 numpy，替代逐股 Python 循环
  · 预建 date→idx 字典，消除 list.index() O(N) 瓶颈

分钟级退出逻辑（与原策略一致）:
  9:31~任意   low ≤ entry×0.95  → stop_loss（-5% 止损）
  11:25       close > entry      → morning_profit（早盘止盈）
  13:01       close ≤ entry×0.98 → midday_loss（午间撤退）
  14:50       close              → eod_clear / eod_limit

v130（尾封过滤）:
  T-1 首次涨停时刻 ≥ 14:00 → 排除（尾盘拉板，隔日高开风险大）

依赖: pandas numpy pyarrow matplotlib  (akshare 仅在第一次下载指数时需要)
运行: python backtest_yijin.py
预计耗时: 5–10 分钟（2016–2025，10年）
"""

import warnings, zipfile
from pathlib import Path
from collections import deque
from decimal import Decimal, ROUND_HALF_UP
from functools import lru_cache

import numpy as np
import pandas as pd
import matplotlib
import matplotlib.pyplot as plt
import sys
sys.path.append(r'D:\work space\hdata\scripts')
from core import paths

matplotlib.rcParams['font.family'] = ['Microsoft YaHei', 'SimHei', 'sans-serif']
matplotlib.rcParams['axes.unicode_minus'] = False
warnings.filterwarnings('ignore')

# ================================================================
# 路径
# ================================================================
HDATA   = Path(r'D:\work space\hdata')
DAILY_D = Path(r'D:\work space\hdata\data\processed\1d_stock')
IND_D   = Path(r'D:\work space\hdata\data\processed\1d_feature\stock_indicator')
ST_D    = HDATA / '基本面数据' / '1d_st_list'
M1_D    = HDATA / '1m_stock'          # 1分钟线：{code}/{year}.parquet
BASIC_F = paths.RAW_STOCK_BASIC
HERE    = Path(__file__).parent
IDX_F   = HERE / 'idx_000852.parquet'

# ================================================================
# 策略参数（与原版一致）
# ================================================================
START_DATE     = '20160101'
END_DATE       = '20251231'
INIT_CASH      = 1_000_000.0

IPO_DAYS       = 250
SLOTS          = 2
V227_STOP      = -0.05       # -5% 止损
MONEY_MIN      = 6e8         # 成交额下限（元）
MONEY_MAX_BULL = 20e8        # bull 模式成交额上限
CIRC_MIN       = 30.0        # 流通市值下限（亿）
CIRC_MAX       = 500.0       # 流通市值上限（亿）
WIN_WIN        = 60          # 胜率追踪窗口
FB_WIN         = 60          # FB_pct 历史窗口
FB_MIN_HIST    = 10
COMMISSION     = 0.0003      # 单边佣金
MIN_COMMISSION = 5.0         # 最低佣金（与原版一致）
STAMP_TAX      = 0.001       # 卖出印花税
SLIPPAGE       = 0.01        # 固定滑点（元/股，买入时加）

# 分钟缓存：100 个「股票×年份」槽位
# 每个 DataFrame ~1.5MB（Categorical 编码后），峰值 ≈ 150MB
M1_CACHE_SIZE  = 100

# ================================================================
# 工具函数
# ================================================================
def ts(msg):
    from datetime import datetime
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

def round2(x: float) -> float:
    return float(Decimal(str(x)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))

# ================================================================
# 日线数据加载
# ================================================================
def load_daily(start_y: int, end_y: int) -> pd.DataFrame:
    ts(f"加载日线 {start_y}–{end_y}…")
    frames = []
    for yr in range(start_y, end_y + 1):
        f = DAILY_D / f'{yr}.parquet'
        if f.exists():
            frames.append(pd.read_parquet(f))
    if not frames:
        raise FileNotFoundError("无日线数据")
    df = pd.concat(frames, ignore_index=True)
    df['date'] = df['date'].astype(str)
    # 排除科创板(688)、北交所(8xx)；创业板(30x)保留（母版未排除）
    c = df['code']
    mask = (~c.str.startswith('688')) & (~c.str.startswith('8'))
    df = df[mask].copy()
    for col in ('open', 'high', 'low', 'close', 'pre_close', 'vol', 'amount'):
        df[col] = pd.to_numeric(df[col], errors='coerce').astype('float32')
    ts(f"  {len(df):,} 行，{df['code'].nunique():,} 只股票")
    return df

def load_indicator(start_y: int, end_y: int) -> pd.DataFrame:
    ts(f"加载市值指标 {start_y}–{end_y}…")
    frames = []
    for yr in range(start_y, end_y + 1):
        f = IND_D / f'{yr}.parquet'
        if f.exists():
            frames.append(pd.read_parquet(f, columns=['code', 'date', 'circ_mv']))
    if not frames:
        return pd.DataFrame(columns=['code', 'date', 'circ_mv_yi'])
    df = pd.concat(frames, ignore_index=True)
    df['date'] = df['date'].astype(str)
    df['circ_mv_yi'] = pd.to_numeric(df['circ_mv'], errors='coerce').astype(float) / 1e8
    ts(f"  {len(df):,} 行")
    return df[['code', 'date', 'circ_mv_yi']]

def load_basic() -> dict:
    ts("加载上市日期…")
    df = pd.read_parquet(BASIC_F)
    code_col = 'ts_code' if 'ts_code' in df.columns else 'code'
    date_col = 'list_date'
    sub = df[[code_col, date_col]].dropna()
    sub = sub[sub[date_col].astype(str).str.len() == 8]
    ipo = dict(zip(sub[code_col].astype(str), sub[date_col].astype(str)))
    ts(f"  {len(ipo)} 只股票")
    return ipo

def load_st(start_y: int, end_y: int) -> dict:
    ts("加载 ST 名单…")
    result = {}
    for yr in range(start_y, end_y + 1):
        f = ST_D / f'{yr}.zip'
        if not f.exists():
            continue
        try:
            with zipfile.ZipFile(f) as zf:
                for name in zf.namelist():
                    ds = name.replace('.parquet', '')
                    if not ds.isdigit():
                        continue
                    with zf.open(name) as bf:
                        result[ds] = set(pd.read_parquet(bf)['code'].tolist())
        except Exception as e:
            ts(f"  ST {yr} 读取失败: {e}")
    ts(f"  {len(result)} 个交易日")
    return result

def load_index() -> pd.DataFrame:
    if IDX_F.exists():
        ts("加载中证1000指数…")
        df = pd.read_parquet(IDX_F)
        df['date']  = df['date'].astype(str)
        df['close'] = df['close'].astype(float)
        return df
    ts("下载中证1000 (akshare)…")
    try:
        import akshare as ak
        df = ak.index_zh_a_hist(symbol='000852', period='daily',
                                 start_date='20100101', end_date='20260101')
        df = df.rename(columns={'日期': 'date', '收盘': 'close'})
        df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y%m%d')
        df = df[['date', 'close']].sort_values('date').reset_index(drop=True)
        df.to_parquet(IDX_F)
        ts(f"  {len(df)} 条")
        return df
    except Exception as e:
        raise RuntimeError(f"中证1000数据获取失败: {e}")

# ================================================================
# 日线 lookup 构建
# ================================================================
def build_daily_lookup(df: pd.DataFrame) -> dict:
    ts("构建日线 lookup…")
    lkp = {str(d): g.set_index('code')
           for d, g in df.groupby('date', sort=False)}
    ts(f"  {len(lkp)} 个交易日")
    return lkp

def build_indicator_lookup(df: pd.DataFrame) -> dict:
    ts("构建市值 lookup…")
    lkp = {str(d): g.set_index('code')['circ_mv_yi']
           for d, g in df.groupby('date', sort=False)}
    ts(f"  {len(lkp)} 个交易日")
    return lkp

# ================================================================
# 1分钟数据：按年 LRU 缓存（核心优化）
# ================================================================
@lru_cache(maxsize=M1_CACHE_SIZE)
def _load_1m_year(code: str, year: str) -> pd.DataFrame:
    """
    读取单只股票单年分钟数据，仅保留必要列。
    结果缓存在 LRU 中；maxsize=300 ≈ 420MB RAM 上限。
    """
    f = M1_D / code / f'{year}.parquet'
    if not f.exists():
        return pd.DataFrame()
    try:
        df = pd.read_parquet(f, columns=['date', 'trade_time', 'high', 'low', 'close'])
        # hhmm 存为整数（930=09:30, 1125=11:25），天然可比较，int16 仅 116KB/年
        df['hhmm'] = (df['trade_time'].dt.hour * 100
                      + df['trade_time'].dt.minute).astype('int16')
        # date 用 Categorical（仅做 == 比较，无序即可）
        df['date'] = pd.Categorical(df['date'])
        return df
    except Exception:
        return pd.DataFrame()


def get_1m_date(code: str, date_str: str) -> pd.DataFrame:
    """取指定股票指定日期的分钟数据（从 LRU 缓存年份文件中切片）。"""
    year = date_str[:4]
    df = _load_1m_year(code, year)
    if df.empty:
        return df
    return df[df['date'] == date_str]


# ================================================================
# v130：尾封过滤（14:00 后才首次涨停 → 排除）
# ================================================================
def check_tail_seal(code: str, prev_date: str, hl_price: float) -> bool:
    """
    返回 True 表示是尾封（应排除）。
    尾封定义：T-1 日首次涨停时刻 ≥ 14:00。
    """
    df = get_1m_date(code, prev_date)
    if df.empty:
        return False
    limit_bars = df[df['close'] >= hl_price * 0.999]
    if limit_bars.empty:
        return False   # 数据异常，不排除
    first_hhmm = int(limit_bars.iloc[0]['hhmm'])   # e.g. 1400
    return first_hhmm >= 1400


# ================================================================
# 向量化首板识别
# ================================================================
def _high_limit_v(pre_close: pd.Series, codes: pd.Index) -> pd.Series:
    """向量化涨停价计算：创业板20%，其余10%"""
    pct = pd.Series(0.10, index=codes)
    cyb = codes.str.startswith('30')
    pct[cyb] = 0.20
    return (pre_close * (1.0 + pct)).round(2)


def _high_limit(pre_close: float, code: str) -> float:
    """单票涨停价：创业板20%，其余10%"""
    limit = 0.20 if code.startswith('30') else 0.10
    return round(pre_close * (1.0 + limit), 2)

def identify_first_boards(df1: pd.DataFrame, df2: pd.DataFrame) -> set:
    """
    df1 = T-1 日线（indexed by code），df2 = T-2 日线
    返回在 T-1 涨停、T-2 未涨停的股票集合（首板宽集）。

    涨停判别对标原版：abs(close - high_limit) <= 0.02
    high_limit 按板块区分（创业板20%，其余10%）。
    """
    if df1 is None or df2 is None or df1.empty or df2.empty:
        return set()
    common = df1.index.intersection(df2.index)
    if len(common) == 0:
        return set()
    pc1 = df1.loc[common, 'pre_close'].astype(float)
    pc2 = df2.loc[common, 'pre_close'].astype(float)
    c1  = df1.loc[common, 'close'].astype(float)
    c2  = df2.loc[common, 'close'].astype(float)
    valid = (pc1 > 0) & (pc2 > 0)
    hl1 = _high_limit_v(pc1, common)
    hl2 = _high_limit_v(pc2, common)
    up1 = (c1 - hl1).abs() <= 0.02
    up2 = (c2 - hl2).abs() <= 0.02
    mask = valid & up1 & ~up2
    return set(common[mask])


# ================================================================
# 向量化候选过滤
# ================================================================
def filter_candidates(
    first_boards: set,
    df1: pd.DataFrame,      # T-1 日线（indexed by code）
    circ_s: pd.Series,      # T-1 流通市值（亿）
    st_set: set,
    ipo_lkp: dict,
    today_str: str,
    market_mode: str,
) -> list:
    """返回按股票代码排序的候选列表（母版按 get_all_securities() 遍历顺序 = code order）"""
    if df1 is None or df1.empty or not first_boards:
        return []

    codes = list(first_boards.intersection(df1.index))
    if not codes:
        return []

    sub = df1.loc[codes].copy()

    # ST 过滤
    sub = sub[~sub.index.isin(st_set)]
    if sub.empty:
        return []

    # IPO 天数（仅对已过滤后的小集合循环）
    today_ts = pd.Timestamp(today_str)
    ok = []
    for code in sub.index:
        ld = ipo_lkp.get(code, '')
        if len(ld) == 8:
            if (today_ts - pd.Timestamp(ld)).days < IPO_DAYS:
                continue
        ok.append(code)
    if not ok:
        return []
    sub = sub.loc[ok]

    # 成交额（元）
    amt = sub['amount'].astype(float)
    sub = sub[amt >= MONEY_MIN]
    if market_mode == 'bull':
        sub = sub[sub['amount'].astype(float) <= MONEY_MAX_BULL]
    if sub.empty:
        return []

    # 均价涨幅 > 7%（排除尾盘拉涨停）
    a = sub['amount'].astype(float)
    v = sub['vol'].astype(float)
    c = sub['close'].astype(float)
    avg_chg = np.where((v > 0) & (c > 0), a / v / c * 1.1 - 1, 0.0)
    sub = sub[avg_chg >= 0.07]
    if sub.empty:
        return []

    # 流通市值（亿）
    circ = circ_s.reindex(sub.index).fillna(0.0)
    sub = sub[(circ >= CIRC_MIN) & (circ <= CIRC_MAX)]
    if sub.empty:
        return []

    # 母版无成交额排序，候选按 get_all_securities() 遍历顺序（股票代码 alphabetically）
    # 改为按股票代码排序以对齐母版（母版遍历全市场用 stock code order）
    return sorted(list(sub.index))


# ================================================================
# v122：爆量 + 创31日新高 排除
# ================================================================
def apply_v122(
    candidates: list,
    prev_date: str,
    date_to_idx: dict,
    trade_dates: list,
    daily_lkp: dict,
) -> list:
    if not candidates:
        return candidates
    idx = date_to_idx.get(prev_date, -1)
    if idx < 5:
        return candidates
    hist_dates = trade_dates[max(0, idx - 30): idx + 1]  # ≤31 天

    kept = []
    for code in candidates:
        vols   = []
        highs  = []
        closes = []
        for d in hist_dates:
            df = daily_lkp.get(d)
            if df is not None and code in df.index:
                r = df.loc[code]
                vols.append(float(r['vol']))
                highs.append(float(r['high']))
                closes.append(float(r['close']))
        if len(vols) < 6:
            kept.append(code)
            continue
        pv = np.array(vols[-6:-1], dtype=float)
        if pv.min() <= 0:
            kept.append(code)
            continue
        is_blast = (vols[-1] > pv.mean() * 8) or (vols[-1] > pv.min() * 12)
        is_new_h = (len(highs) >= 2) and (closes[-1] > max(highs[:-1]))
        if is_blast and is_new_h:
            continue
        kept.append(code)
    return kept


# ================================================================
# v130：尾封批量过滤
# ================================================================
def apply_v130(candidates: list, prev_date: str, daily_lkp: dict) -> list:
    """
    过滤 T-1 尾封（首次涨停 ≥ 14:00）的股票。
    仅读取候选股 T-1 日的分钟数据（LRU 缓存）。
    """
    if not candidates:
        return candidates
    df_prev = daily_lkp.get(prev_date)
    if df_prev is None:
        return candidates

    kept = []
    for code in candidates:
        if code not in df_prev.index:
            kept.append(code)
            continue
        pc = float(df_prev.loc[code, 'pre_close'])
        if pc <= 0:
            kept.append(code)
            continue
        hl = round2(pc * 1.10)
        if check_tail_seal(code, prev_date, hl):
            continue   # 尾封，排除
        kept.append(code)
    return kept


# ================================================================
# 市场模式计算
# ================================================================
def compute_raw_mode(
    trade_dates: list, t_idx: int, idx_map: dict, fb_perf: float
) -> str:
    hist = [idx_map[trade_dates[i]]
            for i in range(max(0, t_idx - 64), t_idx + 1)
            if trade_dates[i] in idx_map]
    if len(hist) < 20:
        return 'bear'
    arr = np.array(hist, dtype=float)

    # 20 日最高回撤 ≤-12%
    high_20 = arr[-20:].max()
    if high_20 > 0 and (arr[-1] - high_20) / high_20 <= -0.12:
        return 'bear'

    if len(arr) < 60:
        return 'bear'

    ma20 = arr[-20:].mean()
    ma60 = arr[-60:].mean()
    price = arr[-1]
    days_above = int((arr[-30:] > ma60).sum())

    if price <= ma60 and ma20 <= ma60:
        return 'bear'
    if price <= ma60 and ma20 > ma60:
        return 'cautious' if fb_perf > 0 else 'bear'
    if days_above >= len(arr[-30:]) * 0.66:
        return 'bull'
    return 'cautious' if fb_perf > -0.02 else 'bear'


# ================================================================
# 精确分钟级退出模拟
# ================================================================
def simulate_ohlc_fallback(
    low_p: float, close_p: float, pre_close: float, entry_price: float,
    hl: float = 0.0,
) -> tuple:
    """聚宽日线回测兜底（无分钟数据时）：全部基于日收盘价。"""
    # 封板
    hl = hl if hl > 0 else round(pre_close * 1.10, 2)
    if close_p >= hl * 0.999:
        return None, 'carryover'
    # morning_profit
    if close_p > entry_price:
        return close_p, 'morning_profit'
    # midday_loss
    if close_p <= entry_price * 0.98:
        return close_p, 'midday_loss'
    # stop_loss
    stop_p = entry_price * (1.0 + V227_STOP)
    if close_p <= stop_p:
        return min(close_p, stop_p), 'stop_loss'
    # eod_clear
    return close_p, 'eod_clear'

def simulate_minute_exit(
    code: str,
    today: str,
    entry_price: float,
    hl_price: float,        # T日涨停价（用于判断是否封板不卖）
    ohlc_fallback: tuple,   # (low, close, pre_close) 兜底
) -> tuple:
    """聚宽日线回测退出模拟：
    - run_daily 的 d.last_price = 该时间点分钟收盘价
    - every_bar 的 d.last_price = 日线收盘价（仅止损用）
    - A股T+1：买入当天不被卖出（由调用方强制 carryover）
    """
    df = get_1m_date(code, today)
    if df.empty:
        return simulate_ohlc_fallback(*ohlc_fallback, entry_price, hl_price)

    stop_p   = entry_price * (1.0 + V227_STOP)
    daily_close = float(ohlc_fallback[1])  # 日线收盘价（用于 every_bar 止损）
    hhmm     = df['hhmm']

    def _at_limit(idx_):
        return float(df.loc[idx_, 'close']) >= hl_price * 0.999

    # ── 阶段1: ~11:25（原版 run_daily sell_v227_morning）───────
    phase1    = df[hhmm <= 1125]
    bar_1125  = phase1[hhmm[phase1.index] >= 1125].head(1)
    p1125_idx = bar_1125.index[0] if not bar_1125.empty else None
    if p1125_idx is not None:
        cl_1125 = float(df.loc[p1125_idx, 'close'])
        # d.last_price > avg_cost 且未封板 → 止盈
        if cl_1125 > entry_price and not _at_limit(p1125_idx):
            return cl_1125, 'morning_profit'

    # ── 阶段2: 11:25–13:01（原版 run_daily sell_v227_midday）───
    phase2   = df[(hhmm > 1125) & (hhmm <= 1301)]
    bar_1301 = phase2[hhmm[phase2.index] >= 1301].head(1)
    if not bar_1301.empty:
        cl_1301 = float(bar_1301.iloc[0]['close'])
        # d.last_price ≤ avg_cost×0.98 且未封板 → 午撤
        if not _at_limit(bar_1301.index[0]) and cl_1301 <= entry_price * 0.98:
            return cl_1301, 'midday_loss'

    # ── 阶段3: 13:01–14:50（原版 run_daily sell_v227_afternoon）─
    phase3   = df[(hhmm > 1301) & (hhmm <= 1450)]
    bar_eod = phase3[hhmm[phase3.index] >= 1450].head(1)
    if bar_eod.empty:
        bar_eod = df.tail(1)
    cl_eod = float(bar_eod.iloc[0]['close'])
    if cl_eod >= hl_price * 0.999:
        return None, 'carryover'

    # ── every_bar（原版 check_stop_all）：d.last_price = 日收盘价 ───
    if daily_close <= stop_p:
        return min(daily_close, stop_p), 'stop_loss'

    return cl_eod, 'eod_clear'

def process_carryover_day(
    code: str,
    today: str,
    entry_price: float,
    entry_hl_price: float,   # 入场日的涨停价（供 stop_p 参考，但 daily 有 pre_close）
    shares: int,
    cost: float,
    daily_row: pd.Series,    # T 日 daily row
) -> tuple:
    """
    处理延持持仓在 T 日的退出。
    返回 (exit_price, reason, keep_holding)：
      - 正常退出 → (价格, 原因, False)
      - 继续延持 → (None, 'carryover', True)
    """
    pc_today = float(daily_row['pre_close'])
    hl_today = _high_limit(pc_today, code) if pc_today > 0 else entry_hl_price
    ohlc_fb = (float(daily_row['low']), float(daily_row['close']), pc_today)

    exit_p, reason = simulate_minute_exit(code, today, entry_price, hl_today, ohlc_fb)
    if reason == 'carryover':
        return None, 'carryover', True
    return exit_p, reason, False


# ================================================================
# v227 bull 模式评分（对标原版 _score_with_left_pressure）
# ================================================================
def _score_candidates_bull(
    candidates: list, df_prev: pd.DataFrame, prev_date: str,
    trade_dates: list, date_to_idx: dict, daily_lkp: dict,
) -> list:
    """
    对标原版 _score_with_left_pressure：
      - 是否突破60日高点 → lp_score (1.0/0.5/0.0)
      - 简化：仅用是否接近60日高排序（全量芯片分布计算过重）
      - 若无法获取60日历史，按原序保留
    """
    if not candidates or df_prev is None:
        return candidates

    idx = date_to_idx.get(prev_date, -1)
    if idx < 60:
        return candidates
    hist_start = max(0, idx - 60)
    hist_dates = trade_dates[hist_start:idx + 1]

    scored = []
    for code in candidates:
        closes = []
        highs = []
        for d in hist_dates:
            df = daily_lkp.get(d)
            if df is not None and code in df.index:
                r = df.loc[code]
                closes.append(float(r['close']))
                highs.append(float(r['high']))
        if len(closes) < 20:
            scored.append((code, 0.5))
            continue
        c60 = np.array(closes, dtype=float)
        h60 = np.array(highs, dtype=float)
        curr_c = c60[-1]
        prev_high_max = c60[:-1].max()  # 60日（不含当日）最高收盘
        is_break = curr_c >= prev_high_max * 0.99 if prev_high_max > 0 else False
        lp_score = 1.0 if is_break else 0.0
        scored.append((code, lp_score))

    scored.sort(key=lambda x: -x[1])
    return [s for s, _ in scored]


# ================================================================
# 空仓月判断（对标原版 _is_pass_month）
# ================================================================
_SPRING_FESTIVAL = {
    2016: "2016-02-08", 2017: "2017-01-28", 2018: "2018-02-16",
    2019: "2019-02-05", 2020: "2020-01-25", 2021: "2021-02-12",
    2022: "2022-02-01", 2023: "2023-01-22", 2024: "2024-02-10",
    2025: "2025-01-29", 2026: "2026-02-17",
}


def _is_pass_month(today_str: str) -> bool:
    """
    原版 rzq 空仓月判断：
      - 1/4/12月15号后（rzq 空仓月，v227 回退启用）
      - 春节前15天
    """
    date = pd.Timestamp(today_str).date()
    month, day = date.month, date.day
    if month in (1, 4, 12) and day >= 15:
        return True
    y = date.year
    if y in _SPRING_FESTIVAL:
        sf = pd.Timestamp(_SPRING_FESTIVAL[y]).date()
        if (sf - pd.Timedelta(days=15)) <= date < sf:
            return True
    return False


# ================================================================
# 主回测循环
# ================================================================
def run_backtest(daily_lkp: dict, ind_lkp: dict,
                 ipo_lkp: dict, st_lkp: dict, idx_df: pd.DataFrame):

    trade_dates = sorted(d for d in daily_lkp if START_DATE <= d <= END_DATE)
    if len(trade_dates) < 5:
        raise ValueError("交易日不足")
    ts(f"共 {len(trade_dates)} 个交易日（{trade_dates[0]}~{trade_dates[-1]}）")

    # O(1) 日期索引
    date_to_idx = {d: i for i, d in enumerate(trade_dates)}

    # 指数数据
    idx_map: dict = {}
    if not idx_df.empty:
        for _, r in idx_df.iterrows():
            idx_map[str(r['date'])] = float(r['close'])

    # 策略状态
    portfolio    = INIT_CASH
    recent_win   = deque(maxlen=WIN_WIN)
    bull_closs   = 0   # bull 连亏计数
    bull_cd      = 0   # bull 冷却剩余天数
    sl_cd        = 0   # 止损冷却剩余天数
    bull_sticky  = 0

    fb_hist      = deque(maxlen=FB_WIN)
    prev_fb_brd  = set()   # 上一交易日识别的首板（用于今日 FB_perf 计算）

    equity_curve = []
    trade_log    = []
    v130_filtered = 0   # 统计 v130 过滤数量
    carryover = {}
          # code → {entry_p, shares, cost, entry_date, hl_price, mode, fb_pct, ...}

    # v227 冲击冷却（对标原版 _update_v227_shock_cooldown）
    v227_shock_cd = 0
    prev_day_total_value = None
    board_heights = deque(maxlen=20)

    # bull 释放确认（对标原版 bull_release_guard）
    bull_release_confirm_pending = False
    raw_market_mode = 'bear'

    def _is_retreat_phase():
        """退潮态检测（对标原版 _retreat_phase_for_low_price）"""
        if market_mode == 'cautious' and fb_pct < 0.4:
            return True
        if fb_perf < 0 and fb_pct < 0.5:
            return True
        if len(board_heights) >= 10:
            recent = np.mean(list(board_heights)[-3:])
            prior = np.mean(list(board_heights)[-10:])
            if recent < prior and recent <= 3:
                return True
        return False

    def _win_scale():
        if len(recent_win) < WIN_WIN:
            return 1.0
        wr = sum(recent_win) / len(recent_win)
        if wr < 0.30: return 0.0
        if wr < 0.40: return 0.5
        return 1.0

    for t_idx, today in enumerate(trade_dates):
        # 进度打印（每250天一次）
        if t_idx % 250 == 0:
            ci = _load_1m_year.cache_info()
            ts(f"进度 {t_idx}/{len(trade_dates)} ({today})  "
               f"净值={portfolio/INIT_CASH:.3f}  "
               f"1m缓存命中率={ci.hits/(ci.hits+ci.misses)*100:.0f}%"
               if (ci.hits + ci.misses) > 0 else
               f"进度 {t_idx}/{len(trade_dates)} ({today})  净值={portfolio/INIT_CASH:.3f}")

        # 至少需要 3 个历史交易日
        if t_idx < 3:
            equity_curve.append({'date': today, 'equity': portfolio})
            continue

        prev_date  = trade_dates[t_idx - 1]   # T-1
        prev2_date = trade_dates[t_idx - 2]   # T-2

        # ── 冷却递减 ──
        if bull_cd > 0: bull_cd -= 1
        if sl_cd   > 0: sl_cd   -= 1
        if v227_shock_cd > 0: v227_shock_cd -= 1

        # ── FB_perf：prev_fb_brd（T-2 首板）在 T-1 的表现 ──
        rets = []
        df_t1 = daily_lkp.get(prev_date)
        df_t2 = daily_lkp.get(prev2_date)
        if prev_fb_brd and df_t1 is not None and df_t2 is not None:
            common = list(prev_fb_brd.intersection(df_t1.index).intersection(df_t2.index))
            if common:
                c1 = df_t1.loc[common, 'close'].astype(float)
                c2 = df_t2.loc[common, 'close'].astype(float)
                valid = c2 > 0
                rets  = ((c1[valid] / c2[valid]) - 1).tolist()
        fb_perf = float(np.mean(rets)) if rets else 0.0
        fb_hist.append(fb_perf)

        buf    = list(fb_hist)
        fb_pct = (sum(1 for v in buf if v < fb_perf) / len(buf)
                  if len(buf) >= FB_MIN_HIST else 0.5)

        # ── 市场模式 ──
        raw_mode = compute_raw_mode(trade_dates, t_idx, idx_map, fb_perf)
        raw_market_mode = raw_mode  # 保存原始模式（bull_release_guard 需要）
        if raw_mode == 'bull':
            bull_sticky = 2
            market_mode = 'bull'
        elif bull_sticky > 0 and raw_mode == 'cautious':
            bull_sticky -= 1
            market_mode  = 'bull'
        else:
            bull_sticky = 0
            market_mode = raw_mode

        # ── 今日首板宽集（T-1 涨停，T-2 未涨停）──
        today_fb = identify_first_boards(df_t1, df_t2)
        prev_fb_brd = today_fb   # 交给下一日计算 FB_perf

        # ── 最大连板数（用于退潮态检测 board_heights）──
        df_t3 = daily_lkp.get(trade_dates[t_idx - 3]) if t_idx >= 3 else None
        max_boards = 0
        if df_t1 is not None and df_t2 is not None and df_t3 is not None:
            common3 = df_t1.index.intersection(df_t2.index).intersection(df_t3.index)
            if len(common3) > 0:
                _pc1 = df_t1.loc[common3, 'pre_close'].astype(float)
                _c1  = df_t1.loc[common3, 'close'].astype(float)
                _hl1 = _high_limit_v(_pc1, common3)
                _up1 = (_c1 - _hl1).abs() <= 0.02
                _pc2 = df_t2.loc[common3, 'pre_close'].astype(float)
                _c2  = df_t2.loc[common3, 'close'].astype(float)
                _hl2 = _high_limit_v(_pc2, common3)
                _up2 = (_c2 - _hl2).abs() <= 0.02
                _pc3 = df_t3.loc[common3, 'pre_close'].astype(float)
                _c3  = df_t3.loc[common3, 'close'].astype(float)
                _hl3 = _high_limit_v(_pc3, common3)
                _up3 = (_c3 - _hl3).abs() <= 0.02
                if (_up1 & _up2 & _up3).any():
                    max_boards = 3
                elif (_up1 & _up2).any():
                    max_boards = 2
                elif _up1.any():
                    max_boards = 1
        board_heights.append(max_boards)

        # ── 延持持仓处理（涨停跨日）─────────────────────────────
        if today in daily_lkp:
            today_df = daily_lkp[today]
            for code in list(carryover.keys()):
                pos = carryover[code]
                if code not in today_df.index:
                    continue
                row = today_df.loc[code]
                exit_p, reason, keep = process_carryover_day(
                    code, today, pos['entry_p'], pos['hl_price'],
                    pos['shares'], pos['cost'], row,
                )
                if not keep:
                    comm_sell = max(pos['shares'] * exit_p * COMMISSION, MIN_COMMISSION)
                    sell_fee = comm_sell + pos['shares'] * exit_p * STAMP_TAX
                    proceeds = pos['shares'] * exit_p - sell_fee
                    pnl = proceeds - pos['cost']
                    portfolio += proceeds
                    ret = (exit_p - pos['entry_p']) / pos['entry_p']
                    is_win = 1 if exit_p > pos['entry_p'] else 0
                    recent_win.append(is_win)

                    # bull 连亏冷却（延持卖出也算）
                    if pos.get('mode') == 'bull':
                        if is_win:
                            bull_closs = 0
                            bull_cd = 0
                        else:
                            bull_closs += 1
                            if bull_closs >= 3:
                                bull_cd = 5
                                bull_release_confirm_pending = True

                    if reason == 'stop_loss':
                        if ret <= -0.10: sl_cd = 3
                        elif ret <= -0.06: sl_cd = 2

                    trade_log.append({
                        'date':     today,
                        'code':     code,
                        'entry':    round(pos['entry_p'], 3),
                        'exit':     round(exit_p, 3),
                        'shares':   pos['shares'],
                        'ret':      round(ret, 5),
                        'pnl':      round(pnl, 2),
                        'reason':   reason,
                        'mode':     pos.get('mode', '?'),
                        'fb_pct':   pos.get('fb_pct', 0),
                        'fb_perf':  pos.get('fb_perf', 0),
                        'hold_days': pos['hold_days'],
                    })
                    del carryover[code]
                else:
                    # 继续延持
                    carryover[code]['hold_days'] += 1

        # ── v227 冲击冷却（对标原版 _update_v227_shock_cooldown）──
        current_total = portfolio
        # 加上 carryover 的 MTM 得到真实日收益
        for _code, _pos in carryover.items():
            if today in daily_lkp and _code in daily_lkp[today].index:
                _cp = float(daily_lkp[today].loc[_code, 'close'])
                current_total += _pos['shares'] * _cp * (1 - COMMISSION - STAMP_TAX)
        if prev_day_total_value is not None and prev_day_total_value > 0:
            daily_ret = current_total / prev_day_total_value - 1.0
            if (daily_ret <= -0.048 and _is_retreat_phase()):
                v227_shock_cd = 1
        prev_day_total_value = current_total

        # ── bull 释放确认（对标原版 bull_release_guard）──
        # bull_release_confirm_pending 在 bull 连亏≥3 时设为 True
        bull_release_guard = False
        if bull_release_confirm_pending and bull_cd <= 0:
            if market_mode == 'bull':
                if raw_market_mode != 'bull' and fb_pct < 0.60:
                    bull_release_guard = True
                else:
                    bull_release_confirm_pending = False
            else:
                bull_release_confirm_pending = False

        # ── 跳过条件（对标原版路由 + buy_v227_一进二内部禁开）───
        # 原版路由：
        #   bear → 天蝎座（非一进二）
        #   cautious → v227一进二（cautious+pct[0.4,0.6) 跳过）
        #   bull+fb_pct≥0.8 → v227一进二
        #   bull_release_guard → v227（冷却释放未确认）
        #   bull+fb_pct[0.2,0.8)+非pass_month → rzq+zb（v227不交易）
        #   bull+fb_pct[0.2,0.8)+pass_month → v227一进二 回退
        pass_month = _is_pass_month(today)
        use_v227_in_bull = (fb_pct >= 0.8) or pass_month or bull_release_guard
        skip = (
            market_mode == 'bear'
            or (market_mode == 'cautious' and 0.4 <= fb_pct < 0.6)
            or (market_mode == 'bull'     and fb_pct < 0.2)
            or (market_mode == 'bull'     and 0.2 <= fb_pct < 0.8 and not use_v227_in_bull)
            or (market_mode == 'bull'     and bull_cd > 0)
            or (sl_cd > 0                 and market_mode != 'bull')
            or (v227_shock_cd > 0)
        )

        if not skip and today_fb and today in daily_lkp:
            today_df = daily_lkp[today]
            df_prev  = daily_lkp.get(prev_date)

            # 仓位参数
            open_hi  = 0.095 if market_mode == 'bull' else (0.07 if fb_perf > 0 else 0.03)
            pos_pct  = 1.0   if market_mode == 'bull' else 0.75
            scale    = _win_scale()
            pos_pct *= scale

            if scale > 0:
                circ_s  = ind_lkp.get(prev_date, pd.Series(dtype=float))
                st_set  = st_lkp.get(prev_date, set())

                cands = filter_candidates(
                    today_fb, df_t1, circ_s,
                    st_set, ipo_lkp, today, market_mode,
                )
                cands = apply_v122(cands, prev_date, date_to_idx, trade_dates, daily_lkp)

                # v130：尾封过滤
                before_v130 = len(cands)
                cands = apply_v130(cands, prev_date, daily_lkp)
                v130_filtered += before_v130 - len(cands)
                # 诊断日志：记录2024年候选变化
                if today >= '20240101' and today <= '20241231':
                    with open(HERE / '_cand_log.csv', 'a', encoding='utf-8') as flog:
                        flog.write(f"{today},{market_mode},{fb_pct:.3f},{fb_perf:.4f},{int(skip)},"
                                   f"{before_v130},{len(cands)},{v130_filtered},{len(carryover)}\n")

                # bull 模式：左压排序（对标 _score_with_left_pressure）
                if cands and market_mode == 'bull':
                    cands = _score_candidates_bull(cands, df_t1, prev_date, trade_dates, date_to_idx, daily_lkp)

                available_slots = SLOTS - len(carryover)
                if available_slots <= 0:
                    continue

                # cash_remain 模拟原版 available_cash 递减（order_value 逐笔冻结）
                cash_remain = portfolio
                bought = 0

                for code in cands:
                    if bought >= available_slots:
                        break
                    if code not in today_df.index:
                        continue
                    row = today_df.loc[code]
                    yclose   = (float(df_prev.loc[code, 'close'])
                                if df_prev is not None and code in df_prev.index else 0.0)
                    pc_today = float(row['pre_close'])
                    t_open   = float(row['open'])

                    if yclose <= 0 or t_open <= 0 or pc_today <= 0:
                        continue
                    # 开盘即涨停排除
                    hl_today = _high_limit(pc_today, code)
                    if t_open >= hl_today * 0.999:
                        continue
                    open_pct = t_open / yclose - 1
                    if open_pct < 0 or open_pct > open_hi:
                        continue

                    buy_p  = t_open + SLIPPAGE
                    slot_val = cash_remain * pos_pct / max(available_slots - bought, 1)
                    invest = min(slot_val, cash_remain * 0.99)
                    if invest < 5000:
                        break
                    shares = int(invest / buy_p / 100) * 100
                    if shares <= 0:
                        continue
                    comm_buy = max(shares * buy_p * COMMISSION, MIN_COMMISSION)
                    cost = shares * buy_p + comm_buy
                    cash_remain -= cost  # order_value 冻结现金，后续 slot 可用现金减少
                    ohlc_fb = (float(row['low']), float(row['close']), pc_today)
                    exit_p, reason = simulate_minute_exit(
                        code, today, buy_p, hl_today, ohlc_fb
                    )

                    # A股T+1：当天买入不可卖出，强制延持到下一日
                    # 原版聚宽日线回测中 closeable_amount=0，所有 sell check 跳过
                    reason = 'carryover'

                    if True:  # 强制延持到下一日（T+1）
                        portfolio -= cost  # 扣除买入成本
                        carryover[code] = {
                            'entry_p':  buy_p,
                            'shares':   shares,
                            'cost':     cost,
                            'entry_date': today,
                            'hl_price': hl_today,
                            'mode':     market_mode,
                            'fb_pct':   round(fb_pct, 3),
                            'fb_perf':  round(fb_perf * 100, 2),
                            'hold_days': 0,
                        }
                        trade_log.append({
                            'date':     today,
                            'code':     code,
                            'entry':    round(buy_p, 3),
                            'exit':     None,
                            'shares':   shares,
                            'ret':      0,
                            'pnl':      0,
                            'reason':   'carryover',
                            'mode':     market_mode,
                            'fb_pct':   round(fb_pct, 3),
                            'fb_perf':  round(fb_perf * 100, 2),
                            'hold_days': 0,
                        })
                    else:
                        comm_sell = max(shares * exit_p * COMMISSION, MIN_COMMISSION)
                        sell_fee = comm_sell + shares * exit_p * STAMP_TAX
                        pnl      = shares * exit_p - sell_fee - cost
                        ret      = (exit_p - buy_p) / buy_p
                        portfolio += pnl
                        trade_log.append({
                            'date':     today,
                            'code':     code,
                            'entry':    round(buy_p, 3),
                            'exit':     round(exit_p, 3),
                            'shares':   shares,
                            'ret':      round(ret, 5),
                            'pnl':      round(pnl, 2),
                            'reason':   reason,
                            'mode':     market_mode,
                            'fb_pct':   round(fb_pct, 3),
                            'fb_perf':  round(fb_perf * 100, 2),
                            'hold_days': 0,
                        })

                    bought    += 1
                    # 延持不算胜率（原版延持不触发 _record_trade）
                    trade_is_win = 0
                    if reason != 'carryover':
                        is_win = 1 if exit_p > buy_p else 0
                        recent_win.append(is_win)

                    # bull 连亏冷却
                    if market_mode == 'bull' and trade_is_win:
                        bull_closs = 0
                        bull_cd    = 0
                    elif market_mode == 'bull' and not trade_is_win and reason != 'carryover':
                        bull_closs += 1
                        if bull_closs >= 3:
                            bull_cd = 5
                            bull_release_confirm_pending = True

                    # 止损冷却
                    if reason == 'stop_loss':
                        if ret <= -0.10: sl_cd = 3
                        elif ret <= -0.06: sl_cd = 2

        # 延持持仓按市价估值（mark-to-market）
        # portfolio = cash（已扣除延持成本），需加回持仓市值
        mtm_add = 0.0
        for code, pos in carryover.items():
            if today in daily_lkp and code in daily_lkp[today].index:
                close_p = float(daily_lkp[today].loc[code, 'close'])
                pos_value = pos['shares'] * close_p * (1 - COMMISSION - STAMP_TAX)
                mtm_add += pos_value
        equity_curve.append({'date': today, 'equity': round(portfolio + mtm_add, 2)})

    # ── 回测结束：强制了结剩余延持 ──
    if carryover:
        ts(f"回测结束，强制了结 {len(carryover)} 笔延持持仓...")
        for code, pos in list(carryover.items()):
            trade_log.append({
                'date':     '99999999',
                'code':     code,
                'entry':    round(pos['entry_p'], 3),
                'exit':     round(pos['entry_p'], 3),
                'shares':   pos['shares'],
                'ret':      0,
                'pnl':      0,
                'reason':   'force_close',
                'mode':     pos.get('mode', '?'),
                'fb_pct':   pos.get('fb_pct', 0),
                'fb_perf':  pos.get('fb_perf', 0),
                'hold_days': pos['hold_days'],
            })

    ts(f"回测完成：{len(trade_log)} 笔交易（含 {len(carryover)} 笔延持了结），v130 过滤 {v130_filtered} 只")
    # 打印分钟缓存命中情况
    ci = _load_1m_year.cache_info()
    ts(f"1m缓存: hits={ci.hits}, misses={ci.misses}, "
       f"命中率={ci.hits/(ci.hits+ci.misses)*100:.1f}% (maxsize={ci.maxsize})")
    return pd.DataFrame(equity_curve), pd.DataFrame(trade_log) if trade_log else pd.DataFrame()


# ================================================================
# 绩效统计
# ================================================================
def compute_metrics(equity: pd.DataFrame, trades: pd.DataFrame) -> dict:
    eq    = equity.set_index('date')['equity']
    years = len(eq) / 252
    total = eq.iloc[-1] / eq.iloc[0] - 1
    cagr  = (eq.iloc[-1] / eq.iloc[0]) ** (1 / years) - 1 if years > 0 else 0

    dr   = eq.pct_change().dropna()
    vol  = dr.std() * np.sqrt(252)
    shrp = (cagr - 0.02) / vol if vol > 0 else 0

    dd     = (eq - eq.cummax()) / eq.cummax()
    max_dd = dd.min()
    calmar = abs(cagr / max_dd) if max_dd != 0 else float('inf')

    m = {
        '总收益率':   f"{total*100:.1f}%",
        '年化收益率': f"{cagr*100:.1f}%",
        '年化波动率': f"{vol*100:.1f}%",
        'Sharpe':     f"{shrp:.2f}",
        '最大回撤':   f"{max_dd*100:.1f}%",
        'Calmar':     f"{calmar:.2f}",
    }
    if not trades.empty:
        # 排除延持中间记录（ret=0 的占位），仅统计实际成交
        actual = trades[trades['reason'] != 'carryover'].copy()
        if actual.empty:
            return m
        wins   = actual[actual['ret'] > 0]
        losses = actual[actual['ret'] <= 0]
        trades = actual
        aw = wins['ret'].mean()   if len(wins)   else 0
        al = losses['ret'].mean() if len(losses) else 0
        m.update({
            '总交易笔数': len(trades),
            '胜率':       f"{len(wins)/len(trades)*100:.1f}%",
            '平均盈利':   f"{aw*100:.2f}%",
            '平均亏损':   f"{al*100:.2f}%",
            '盈亏比':     f"{abs(aw/al):.2f}" if al else 'N/A',
            '年均笔数':   f"{len(trades)/years:.0f}",
        })
        for mode in ('bull', 'cautious', 'bear'):
            sub = trades[trades['mode'] == mode]
            if len(sub):
                wr = (sub['ret'] > 0).mean()
                m[f'{mode}模式笔/胜率'] = f"{len(sub)} / {wr*100:.0f}%"
        for r in sorted(trades['reason'].unique()):
            sub = trades[trades['reason'] == r]
            m[f'出场[{r}]'] = f"{len(sub)}笔 avg={sub['ret'].mean()*100:.1f}%"
    return m


# ================================================================
# 绘图
# ================================================================
def plot_results(equity: pd.DataFrame, trades: pd.DataFrame, idx_df: pd.DataFrame):
    fig, axes = plt.subplots(3, 1, figsize=(14, 12))
    fig.suptitle('短线情绪门控——一进二腿复刻回测（2016-2025）',
                 fontsize=14, fontweight='bold')

    eq     = equity.set_index('date')['equity']
    eq_n   = eq / eq.iloc[0]
    xpos   = range(len(eq_n))

    # ─ 净值 ─
    ax = axes[0]
    ax.plot(xpos, eq_n.values, lw=1.3, color='steelblue', label='策略净值')
    if not idx_df.empty:
        idx   = idx_df.set_index('date')['close']
        cdays = [d for d in eq.index if d in idx.index]
        if cdays:
            idx_n = idx.reindex(cdays).ffill()
            idx_n = idx_n / idx_n.iloc[0]
            ax.plot(range(len(idx_n)), idx_n.values,
                    lw=1, color='tomato', alpha=0.7, label='中证1000')
    ax.set_ylabel('净值')
    ax.legend()
    ax.grid(alpha=0.3)

    # x 轴年份刻度
    yr_pos = {}
    for i, d in enumerate(eq.index):
        y = d[:4]
        if y not in yr_pos: yr_pos[y] = i
    ax.set_xticks(list(yr_pos.values()))
    ax.set_xticklabels(list(yr_pos.keys()), rotation=45)

    # ─ 回撤 ─
    ax2 = axes[1]
    dd  = (eq - eq.cummax()) / eq.cummax() * 100
    ax2.fill_between(xpos, dd.values, 0, color='salmon', alpha=0.45)
    ax2.plot(xpos, dd.values, color='red', lw=0.8)
    ax2.set_ylabel('回撤 (%)')
    ax2.set_xticks(list(yr_pos.values()))
    ax2.set_xticklabels(list(yr_pos.keys()), rotation=45)
    ax2.grid(alpha=0.3)

    # ─ 年度 PnL ─
    ax3 = axes[2]
    if not trades.empty and 'date' in trades.columns:
        trades = trades.copy()
        trades['year'] = trades['date'].str[:4]
        yr_eq = equity.copy()
        yr_eq['year'] = yr_eq['date'].str[:4]

        yr_ret = {}
        for yr, grp in yr_eq.groupby('year'):
            s, e = grp['equity'].iloc[0], grp['equity'].iloc[-1]
            yr_ret[yr] = (e / s - 1) * 100
        yrs  = sorted(yr_ret)
        vals = [yr_ret[y] for y in yrs]
        cols = ['steelblue' if v >= 0 else 'salmon' for v in vals]
        bars = ax3.bar(yrs, vals, color=cols, alpha=0.85)
        ax3.axhline(0, color='black', lw=0.8)
        ax3.set_ylabel('年度收益率 (%)')
        for bar, v in zip(bars, vals):
            va = 'bottom' if v >= 0 else 'top'
            ax3.text(bar.get_x() + bar.get_width()/2,
                     bar.get_height() + (0.5 if v >= 0 else -0.5),
                     f'{v:.0f}%', ha='center', va=va, fontsize=9)
        ax3.grid(alpha=0.3, axis='y')

    plt.tight_layout()
    out = HERE / 'backtest_yijin_result.png'
    plt.savefig(out, dpi=130, bbox_inches='tight')
    ts(f"图表已保存: {out}")
    plt.show()


# ================================================================
# 入口
# ================================================================
def main():
    start_y = int(START_DATE[:4])
    end_y   = int(END_DATE[:4])

    ts("=== 一进二策略复刻回测（精确分钟版）===")

    df_daily = load_daily(start_y, end_y)   # 使用当前年份数据
    df_ind   = load_indicator(start_y, end_y)
    ipo_lkp  = load_basic()
    st_lkp   = load_st(start_y, end_y)
    idx_df   = load_index()

    daily_lkp = build_daily_lookup(df_daily)
    ind_lkp   = build_indicator_lookup(df_ind)

    ts("开始回测…")
    equity, trades = run_backtest(daily_lkp, ind_lkp, ipo_lkp, st_lkp, idx_df)

    ts("\n=== 绩效统计 ===")
    metrics = compute_metrics(equity, trades)
    for k, v in metrics.items():
        print(f"  {k:20s}: {v}")

    if not trades.empty:
        out_t = HERE / 'trades_yijin.csv'
        trades.to_csv(out_t, index=False, encoding='utf-8-sig')
        ts(f"交易明细: {out_t}")

    out_e = HERE / 'equity_yijin.csv'
    equity.to_csv(out_e, index=False, encoding='utf-8-sig')
    ts(f"净值序列: {out_e}")

    plot_results(equity, trades, idx_df)


if __name__ == '__main__':
    main()
