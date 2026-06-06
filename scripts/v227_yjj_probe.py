"""
Local hdata probe for the mother strategy's v227 "一进二" leg.

This script does not simulate PnL. It audits the chain that decides whether
buy_v227_一进二 would buy at 09:26:
  market mode -> first-board candidates -> base filters -> v130 tail-seal
  filter -> fb_perf/open_hi -> open filter -> v227 slot availability.

Data root: D:\\work space\\hdata\\data\\processed
"""

from __future__ import annotations

from collections import deque
from pathlib import Path
import argparse
import re

import numpy as np
import pandas as pd


ROOT = Path(r"D:\work space\hdata\data\processed")
IDX_FILE = Path(__file__).resolve().parents[1] / "idx_000852.parquet"

WARMUP_START = "20231001"
BACKTEST_START = "20240301"
BACKTEST_END = "20240320"
PRINT_START = "20240301"
PRINT_END = "20240320"
VERBOSE_DAILY = True
TRACK_SLOTS = False
SIMULATE_V227_SELLS = True
SELL_TIME_SHIFT_MINUTES = 0
INCLUDE_SCORPION = True
ENABLE_LEADER_PROTECT = False
USE_ST_LIST_FILTER = True
DELIST_TAIL_DAYS = 30
SCORPION_ST_LIST_FILTER = False
SCORPION_DELIST_NAME_FILTER = False
JQ_NA_PROPAGATION = False
USE_JQ_FB_PERF_OVERRIDE = False
USE_JQ_FB_STATE_OVERRIDE = False
FORCE_V227_ROUTE = False
SIMULATE_COOLDOWNS = False
DISABLE_CAUTIOUS_POISON = False
YJJ_EXCLUDE_OPEN_RANGES: list[tuple[float, float]] = []
TRADES_OUT = Path(__file__).resolve().parents[1] / "trades_v227_yjj_probe.csv"
EQUITY_OUT = Path(__file__).resolve().parents[1] / "equity_v227_yjj_probe.csv"
STATE_OUT = Path(__file__).resolve().parents[1] / "state_v227_yjj_probe.csv"
EXPLAIN_OUT = Path(__file__).resolve().parents[1] / "explain_jq_buy_days_2022.csv"
INIT_CASH = 1_000_000.0
COMMISSION = 0.0003
MIN_COMMISSION = 5.0
STAMP_TAX = 0.001

IPO_DAYS = 250
SLOTS = 2
LIMIT_TOL = 0.01
MONEY_MIN = 6e8
MONEY_MAX_BULL = 20e8
CIRC_MIN = 30.0
CIRC_MAX = 500.0
FB_WIN = 60

# 加载 JQ DIAG 提供的 fb_perf 覆盖（6-1 ~ 8-31）
# 用 JQ 的 ground truth 替代本地计算，精确对齐 force_v227 模式
import json as _json_for_jq
import os as _os_for_jq
_JQ_FB_PERF_PATH = _os_for_jq.path.join(_os_for_jq.path.dirname(_os_for_jq.path.abspath(__file__)), "..", "jq_fb_perf_jun_aug.json")
_JQ_FB_STATE_PATH = _os_for_jq.path.join(_os_for_jq.path.dirname(_os_for_jq.path.abspath(__file__)), "..", "jq_fb_state_overrides.json")
JQ_FB_PERF_OVERRIDE = {}
if _os_for_jq.path.exists(_JQ_FB_PERF_PATH):
    with open(_JQ_FB_PERF_PATH) as _f:
        for k, v in _json_for_jq.load(_f).items():
            JQ_FB_PERF_OVERRIDE[k] = float("nan") if v is None else float(v)
JQ_FB_STATE_OVERRIDE = {}
if _os_for_jq.path.exists(_JQ_FB_STATE_PATH):
    with open(_JQ_FB_STATE_PATH, encoding="utf-8") as _f:
        JQ_FB_STATE_OVERRIDE = _json_for_jq.load(_f)
FB_MIN_HIST = 10
WIN_WINDOW = 60
LOW_PRICE_REF = 20.0
LOW_PRICE_WEIGHT = 0.15
LOW_PRICE_MIN_WIN_RATE = 0.45

SPRING_FESTIVAL = {
    2015: "2015-02-19",
    2016: "2016-02-08",
    2017: "2017-01-28",
    2018: "2018-02-16",
    2019: "2019-02-05",
    2020: "2020-01-25",
    2021: "2021-02-12",
    2022: "2022-02-01",
    2023: "2023-01-22",
    2024: "2024-02-10",
    2025: "2025-01-29",
    2026: "2026-02-17",
    2027: "2027-02-06",
    2028: "2028-01-26",
    2029: "2029-02-13",
    2030: "2030-02-03",
}


def is_pass_month(today: str) -> bool:
    date = pd.Timestamp(today).date()
    if date.month in (1, 4, 12) and date.day >= 15:
        return True
    sf = SPRING_FESTIVAL.get(date.year)
    if not sf:
        return False
    spring_date = pd.Timestamp(sf).date()
    return (spring_date - pd.Timedelta(days=15)) <= date < spring_date


def route_active(market_mode: str, fb_pct: float, bull_release_guard: bool, today: str) -> str:
    if market_mode in ("bear", "cautious"):
        return "v227"
    if fb_pct >= 0.8:
        return "v227"
    if bull_release_guard:
        return "v227"
    if not is_pass_month(today):
        return "rzq+zb"
    return "v227"


def parse_open_ranges(text: str) -> list[tuple[float, float]]:
    ranges: list[tuple[float, float]] = []
    if not text:
        return ranges
    for part in text.split(","):
        part = part.strip()
        if not part:
            continue
        left, right = part.split(":", 1)
        lo = float(left)
        hi = float(right)
        ranges.append((lo, hi))
    return ranges


def in_any_range(value: float, ranges: list[tuple[float, float]]) -> bool:
    if pd.isna(value):
        return False
    return any(lo <= value < hi for lo, hi in ranges)


def ipo_first_day_limit(close: float, pre_close: float, code: str, trade_date: str | None, list_date_map: dict[str, str] | None, tol_cents: int) -> bool:
    if not trade_date or not list_date_map or list_date_map.get(code) != trade_date:
        return False
    # 科创板/创业板注册制后首日无涨跌幅限制，不作为涨停板延续。
    if code.startswith("688") or _is_twenty_pct_board(code, trade_date):
        return False
    limit_price = _jq_round_limit(float(pre_close), 144, 100)
    return abs(int(round(float(close) * 100)) - int(round(limit_price * 100))) <= tol_cents


def calc_fb_perf_from_prev_boards(
    prev_first_boards: list[str],
    df_prev: pd.DataFrame,
    df_prev2: pd.DataFrame,
    jq_na_propagation: bool = False,
) -> float:
    if not prev_first_boards:
        return 0.0
    rets = []
    for code in prev_first_boards:
        if code in df_prev.index and code in df_prev2.index:
            base = float(df_prev2.loc[code, "close"])
            if base > 0:
                rets.append(float(df_prev.loc[code, "close"]) / base - 1)
        elif jq_na_propagation and code in df_prev2.index and code not in df_prev.index:
            rets.append(np.nan)
    if not rets:
        return 0.0
    return float(np.mean(rets))


def win_rate(recent_trades: deque[int]) -> float:
    if len(recent_trades) < WIN_WINDOW:
        return 0.5
    return float(sum(recent_trades)) / len(recent_trades)


def retreat_phase_for_low_price(market_mode: str, fb_pct: float, fb_perf: float, board_heights: deque[int]) -> bool:
    if market_mode == "cautious" and fb_pct < 0.4:
        return True
    if fb_perf < 0 and fb_pct < 0.5:
        return True
    heights = list(board_heights)
    if len(heights) >= 10:
        recent = float(np.mean(heights[-3:]))
        prior = float(np.mean(heights[-10:]))
        if recent < prior and recent <= 3:
            return True
    return False


def low_price_tilt_active(
    market_mode: str,
    fb_pct: float,
    fb_perf: float,
    board_heights: deque[int],
    recent_trades: deque[int],
) -> bool:
    if market_mode not in ("bear", "cautious"):
        return False
    if fb_pct >= 0.6:
        return False
    if retreat_phase_for_low_price(market_mode, fb_pct, fb_perf, board_heights):
        return False
    return win_rate(recent_trades) >= LOW_PRICE_MIN_WIN_RATE


def apply_low_price_tilt(cands: list[str], price_map: pd.Series | dict[str, float], active: bool) -> list[str]:
    if not cands or not active:
        return cands
    ranked = []
    for idx, code in enumerate(cands):
        price = float(price_map.get(code, 0))
        bonus = max(0.0, min(1.0, LOW_PRICE_REF / price - 1.0)) if price > 0 else 0.0
        score = 1.0 + LOW_PRICE_WEIGHT * bonus
        ranked.append((code, score, idx))
    ranked.sort(key=lambda x: (-x[1], x[2]))
    return [code for code, _, _ in ranked]


def calc_chip_stats(
    close_arr,
    high_arr,
    low_arr,
    volume_arr,
    circulating_shares: float,
    decay_factor: float = 1.0,
    bins: int = 30,
) -> tuple[float, float]:
    n = len(close_arr)
    if n < 20 or circulating_shares <= 0:
        return 0.0, 0.0
    highs = np.asarray(high_arr, dtype=float)
    lows = np.asarray(low_arr, dtype=float)
    closes = np.asarray(close_arr, dtype=float)
    vols = np.asarray(volume_arr, dtype=float)
    price_min = lows.min() * 0.95
    price_max = highs.max() * 1.05
    if price_max <= price_min:
        return 0.0, 0.0
    prices = np.linspace(price_min, price_max, bins)
    span = highs - lows
    avg_p = (highs + lows + closes) / 3.0
    valid = (vols > 0) & (span > 0)
    safe_span = np.where(valid, span, 1.0)
    mask = (prices[None, :] >= lows[:, None]) & (prices[None, :] <= highs[:, None])
    raw_w = np.maximum(1.0 - np.abs(prices[None, :] - avg_p[:, None]) / safe_span[:, None], 0.0)
    raw_w = np.where(mask, raw_w, 0.0)
    ws = raw_w.sum(axis=1, keepdims=True)
    new_dist = np.where(ws > 0, raw_w / np.where(ws > 0, ws, 1.0), 0.0)
    t = np.where(valid, np.minimum(vols / circulating_shares * decay_factor, 1.0), 0.0)
    keep = 1.0 - t
    suffix_keep = np.empty(n)
    suffix_keep[-1] = 1.0
    if n > 1:
        suffix_keep[:-1] = np.cumprod(keep[:0:-1])[::-1]
    weights = t * suffix_keep
    chips0 = np.ones(bins) / bins
    chips = chips0 * keep.prod() + (new_dist * weights[:, None]).sum(axis=0)
    total = chips.sum()
    if total <= 0:
        return 0.0, 0.0
    chips /= total
    winner_rate = float(chips[prices <= closes[-1]].sum())
    return 0.0, winner_rate


def jq_code(code: str) -> str:
    raw, exch = code.split(".")
    return raw + (".XSHG" if exch == "SH" else ".XSHE")


def local_code(code: str) -> str:
    raw, exch = code.split(".")
    return raw + (".SH" if exch == "XSHG" else ".SZ")


def hdata_minute_code(code: str) -> str:
    raw, exch = code.split(".")
    if exch == "XSHE":
        return raw + ".SZ"
    if exch == "XSHG":
        return raw + ".SH"
    return code


JQ_CODE_RE = re.compile(r"\((\d{6}\.XS(?:HG|HE))\)")
DATE_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})\s+(\d{2}):(\d{2}):(\d{2})")


def parse_jq_buy_targets(path: Path | None) -> dict[str, list[dict]]:
    if path is None or not path.exists():
        return {}
    out: dict[str, list[dict]] = {}
    for raw_line in path.read_text(encoding="utf-8-sig", errors="ignore").splitlines():
        line = raw_line.strip()
        if not line or "市价单" not in line or "买" not in line:
            continue
        m_date = DATE_RE.match(line)
        m_code = JQ_CODE_RE.search(line)
        if not m_date or not m_code:
            continue
        y, mo, d, hh, mm, ss = m_date.groups()
        date = f"{y}{mo}{d}"
        time = f"{hh}:{mm}:{ss}"
        jq = m_code.group(1)
        price = np.nan
        shares = np.nan
        parts = re.split(r"\s+", line)
        if "市价单" in parts:
            i = parts.index("市价单")
            if i + 2 < len(parts):
                try:
                    shares = abs(int(parts[i + 1].rstrip("股").replace(",", "")))
                    price = float(parts[i + 2].replace(",", ""))
                except ValueError:
                    pass
        out.setdefault(date, []).append({
            "date": date,
            "time": time,
            "code": jq,
            "local_code": local_code(jq),
            "jq_price": price,
            "jq_shares": shares,
            "path_guess": "scorpion" if time.startswith("09:30") else "yjj",
            "raw": raw_line,
        })
    return out


def _jq_round_limit(pre_close: float, mult_num: int, mult_den: int) -> float:
    """模拟聚宽 high_limit/low_limit 字段的算法：
    pre_close 先 round 到分（消除 float32/64 精度损失），再用整数运算乘除，
    最后 round-half-up 到分。等价于交易所官方价格生成规则。

    例如 pre_close=8.45 (实际 float32=8.4499998), mult=1.10:
      pre_cents = round(8.4499998 * 100) = 845
      raw = 845 * 11 = 9295
      round-half-up(9295/10) = 930 → 9.30
    （旧版 round(8.4499998*1.10, 2) = round(9.29499..., 2) = 9.29，错。）
    """
    pre_cents = int(round(float(pre_close) * 100))
    raw_x_den = pre_cents * mult_num
    q, r = divmod(raw_x_den, mult_den)
    if r * 2 >= mult_den:  # 余数 ≥ 一半 → 入
        q += 1
    return q / 100.0


def _is_twenty_pct_board(code: str, trade_date: str | None = None) -> bool:
    # 科创板自开市起 20%；创业板 2020-08-24 注册制后 20%。
    if code.startswith("688"):
        return True
    if code.startswith("30"):
        return trade_date is not None and str(trade_date).replace("-", "") >= "20200824"
    return False


def high_limit(pre_close: float, code: str, is_st: bool = False, trade_date: str | None = None) -> float:
    if _is_twenty_pct_board(code, trade_date):
        return _jq_round_limit(pre_close, 120, 100)  # 1.20
    if is_st:
        return _jq_round_limit(pre_close, 105, 100)  # 主板 ST 5%
    return _jq_round_limit(pre_close, 110, 100)  # 主板非 ST 10%


def low_limit(pre_close: float, code: str, is_st: bool = False, trade_date: str | None = None) -> float:
    if _is_twenty_pct_board(code, trade_date):
        return _jq_round_limit(pre_close, 80, 100)  # 创业/科创板 20% 跌幅
    if is_st:
        return _jq_round_limit(pre_close, 95, 100)
    return _jq_round_limit(pre_close, 90, 100)


def high_limit_series(pre_close: pd.Series, st_set: set[str] | None = None,
                      delist_trans_set: set[str] | None = None,
                      trade_date: str | pd.Series | None = None) -> pd.Series:
    """向量化的 _jq_round_limit。先把 pre_close 转分（整数），再按类型分桶乘除。
    规则：创业板/科创板（含 ST）一律 20%；退市整理期 10%（非 ST）；主板 ST 5%；主板非 ST 10%。

    delist_trans_set：退市整理期股票集合（涨停 10%，非 ST 5%）。
    这些股票在 hdata ST 表中可能仍被标记为 ST，需显式剔除 ST 标签。
    """
    codes_idx = pre_close.index.astype(str)
    codes_arr = np.asarray(codes_idx, dtype=object)
    pre_arr = pre_close.astype(float).to_numpy()
    pre_cents = np.rint(pre_arr * 100).astype(np.int64)  # 先消除 float 损失
    is_st = np.array([c in st_set for c in codes_arr], dtype=bool) if st_set else np.zeros(len(codes_arr), dtype=bool)
    # 退市整理期：强制移除 ST 标签（整理期涨幅 10%，不适用 ST 5% 规则）
    if delist_trans_set:
        is_delist_trans = np.array([c in delist_trans_set for c in codes_arr], dtype=bool)
        is_st = is_st & ~is_delist_trans
    if isinstance(trade_date, pd.Series):
        dates_arr = trade_date.reindex(pre_close.index).astype(str).to_numpy()
        is_gem = np.array([_is_twenty_pct_board(c, d) for c, d in zip(codes_arr, dates_arr)], dtype=bool)
    else:
        is_gem = np.array([_is_twenty_pct_board(c, trade_date) for c in codes_arr], dtype=bool)
    # 创业/科创板优先（含 ST），主板再分 ST/非 ST
    num = np.where(is_gem, 120, np.where(is_st, 105, 110)).astype(np.int64)
    raw_x100 = pre_cents * num  # 整数乘法
    q = raw_x100 // 100
    r = raw_x100 % 100
    q = q + (r * 2 >= 100).astype(np.int64)  # round-half-up
    return pd.Series(q.astype(float) / 100.0, index=pre_close.index)


def load_daily(years: list[int]) -> dict[str, pd.DataFrame]:
    frames = []
    for year in years:
        path = ROOT / "1d_stock" / f"{year}.parquet"
        frames.append(pd.read_parquet(path))
    df = pd.concat(frames, ignore_index=True)
    df["date"] = df["date"].astype(str)
    # 排除科创板（688）、北交所旧代码（8 开头）、北交所新代码（92/920 开头）
    df = df[~df["code"].str.startswith("688")
            & ~df["code"].str.startswith("8")
            & ~df["code"].str.startswith("92")]
    return {d: g.set_index("code") for d, g in df.groupby("date", sort=False)}


def build_daily_by_code(daily: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    frames = []
    for d, df in daily.items():
        tmp = df.reset_index().copy()
        tmp["date"] = d
        frames.append(tmp)
    if not frames:
        return {}
    all_daily = pd.concat(frames, ignore_index=True)
    all_daily = all_daily.sort_values(["code", "date"])
    return {c: g.reset_index(drop=True) for c, g in all_daily.groupby("code", sort=False)}


def effective_history_frames(
    daily_by_code: dict[str, pd.DataFrame],
    asof: str,
    count: int = 3,
) -> list[pd.DataFrame]:
    buckets: list[list[pd.Series]] = [[] for _ in range(count)]
    for _, g in daily_by_code.items():
        hist = g[g["date"].astype(str) <= asof].tail(count)
        if hist.empty:
            continue
        rows = list(hist.iloc[::-1].iterrows())
        for idx, (_, row) in enumerate(rows[:count]):
            buckets[idx].append(row)
    out = []
    for rows in buckets:
        if rows:
            out.append(pd.DataFrame(rows).set_index("code"))
        else:
            out.append(pd.DataFrame())
    return out


def load_indicator(years: list[int]) -> dict[str, pd.Series]:
    frames = []
    for year in years:
        path = ROOT / "1d_feature" / "stock_indicator" / f"{year}.parquet"
        frames.append(pd.read_parquet(path, columns=["code", "date", "circ_mv"]))
    df = pd.concat(frames, ignore_index=True)
    df["date"] = df["date"].astype(str)
    df["circ_yi"] = df["circ_mv"].astype(float) / 1e8
    return {d: g.set_index("code")["circ_yi"] for d, g in df.groupby("date", sort=False)}


def load_st(years: list[int]) -> dict[str, set[str]]:
    """加载每日 ST 集合，并补全 hdata ST 表的覆盖缺口。

    hdata ST 表对已退市股票（如 600146、600209）在退市前最后阶段往往
    停止更新 ST 标记，但 JQ 数据保留 ST 状态直到退市日。
    修复：对于每只在 ST 表中出现过的股票，把它从首次 ST 日延伸到 delist_date
    （若已退市）或表覆盖的末日之后所有的交易日。
    """
    frames = []
    for year in years:
        path = ROOT / "1d_feature" / "st_list" / f"{year}.parquet"
        if path.exists():
            frames.append(pd.read_parquet(path, columns=["code", "date"]))
    if not frames:
        return {}
    df = pd.concat(frames, ignore_index=True)
    df["date"] = df["date"].astype(str)
    st_per_day: dict[str, set[str]] = {d: set(g["code"].astype(str)) for d, g in df.groupby("date")}

    # 注：不做 ST 补全。
    # hdata ST 表覆盖的是"被实施 ST 监管"日期；退市整理期股票虽即将退市，
    # 但实际涨跌幅限制改为 10%（非 5%），所以**不要**把它们补成 ST。
    # ST 表的末日通常恰好接近退市整理期开始，原始数据足够准确。
    return st_per_day


def fill_st_calendar(st_per_day: dict[str, set[str]], trade_dates: list[str]) -> dict[str, set[str]]:
    """Forward-fill ST sets across trading days.

    The local ST parquet can miss isolated trading days such as 2020-01-02.
    Treating such days as "no ST" breaks high_limit reconstruction. JoinQuant's
    high_limit/current_data effectively carries the ST status, so we do the same.
    """
    if not st_per_day:
        return {}
    out: dict[str, set[str]] = {}
    known_dates = sorted(st_per_day)
    prev_set: set[str] = set()
    k = 0
    for d in sorted(trade_dates):
        while k < len(known_dates) and known_dates[k] <= d:
            prev_set = set(st_per_day[known_dates[k]])
            k += 1
        out[d] = set(st_per_day.get(d, prev_set))
    return out


def build_delist_trans_map(
    list_status_map: dict[str, str],
    delist_map: dict[str, str],
    trade_dates: list[str],
    window: int = 20,
) -> dict[str, set[str]]:
    """构建每日退市整理期股票集合。

    退市整理期（最后 15 个交易日）涨跌停 ±10%，首日无限制。
    hdata ST 表在此期间可能仍标记这些股票为 ST（应用 5% 规则）。
    本函数返回每个交易日处于整理期的股票集，供 high_limit_series 剔除 ST 标签。

    window：向前看多少个交易日作为整理期窗口（默认 20，覆盖 15 日整理期 + 缓冲）。
    """
    # 收集所有已退市股票的退市日期（股票代码 → 退市日 YYYYMMDD）
    delist_stocks: dict[str, str] = {}
    for code, dd in delist_map.items():
        if list_status_map.get(code) == "D" and len(dd) == 8:
            delist_stocks[code] = dd

    td_arr = sorted(trade_dates)
    td_idx: dict[str, int] = {d: i for i, d in enumerate(td_arr)}

    result: dict[str, set[str]] = {}
    if not td_arr:
        return result
    min_td, max_td = td_arr[0], td_arr[-1]
    for code, ddate in delist_stocks.items():
        if ddate < min_td or ddate > max_td:
            continue
        if ddate not in td_idx:
            # 退市日不在交易日历中，取最近的前一个交易日作为 ddate
            candidates = [d for d in td_arr if d <= ddate]
            if not candidates:
                continue
            ddate = candidates[-1]
        end_idx = td_idx[ddate]
        # 整理期：从退市日前 window 个交易日到退市日（含）
        start_idx = max(0, end_idx - window + 1)
        for d in td_arr[start_idx:end_idx + 1]:
            result.setdefault(d, set()).add(code)
    return result


def load_basic() -> tuple[dict[str, str], dict[str, str], dict[str, str], dict[str, str]]:
    df = pd.read_parquet(ROOT / "metadata" / "stock_basic.parquet")
    delist = df["delist_date"].astype(str).replace({"nan": "", "NaT": "", "None": ""})
    return (
        dict(zip(df["code"].astype(str), df["list_date"].astype(str))),
        dict(zip(df["code"].astype(str), df["name"].astype(str))),
        dict(zip(df["code"].astype(str), df["list_status"].astype(str))),
        dict(zip(df["code"].astype(str), delist)),
    )


def load_index() -> dict[str, float]:
    if not IDX_FILE.exists():
        return {}
    df = pd.read_parquet(IDX_FILE)
    df["date"] = df["date"].astype(str)
    return dict(zip(df["date"], df["close"].astype(float)))


def identify_first_boards(
    df1: pd.DataFrame,
    df2: pd.DataFrame,
    st1: set[str] | None = None,
    st2: set[str] | None = None,
    tol: float | None = None,
    d1_date: str | None = None,
    d2_date: str | None = None,
    list_date_map: dict[str, str] | None = None,
    dt1: set[str] | None = None,  # 退市整理期（df1 日）
    dt2: set[str] | None = None,  # 退市整理期（df2 日）
) -> list[str]:
    """识别首板：cr[-1] 涨停 且 cr[-2] 不涨停。

    用整数（分）做涨停判定，彻底规避 float32 精度问题。
    tol 单位仍为元，转成分（1 分 ≈ 0.01 元）。

    d1_date / list_date_map：可选。提供后会额外检查 IPO 首日股票
    （仅在 df1 有数据、df2 无数据的股票）。
    沪深主板 2023-04-10 之前：首日涨幅限制 +44%。
    创业板 2020-08-24 之后：首 5 日无涨跌幅限制，不识别为首板。
    """
    if tol is None:
        tol = LIMIT_TOL
    tol_cents = int(round(tol * 100))  # 0.01 元 → 1 分

    # --- 普通股票：prev 和 prev2 都有数据 ---
    common = df1.index.intersection(df2.index)
    result = []
    if len(common) > 0:
        c1_cents = np.rint(df1.loc[common, "close"].astype(float).to_numpy() * 100).astype(np.int64)
        c2_cents = np.rint(df2.loc[common, "close"].astype(float).to_numpy() * 100).astype(np.int64)
        d1_series = df1.loc[common, "date"] if "date" in df1.columns else pd.Series(d1_date, index=common)
        d2_series = df2.loc[common, "date"] if "date" in df2.columns else pd.Series(d2_date, index=common)
        hl1_cents = np.rint(high_limit_series(df1.loc[common, "pre_close"], st1, dt1, d1_series).to_numpy() * 100).astype(np.int64)
        hl2_cents = np.rint(high_limit_series(df2.loc[common, "pre_close"], st2, dt2, d2_series).to_numpy() * 100).astype(np.int64)
        if tol_cents <= 1:
            # JQ's bear scan compares decimal-looking floats directly with
            # abs(close - high_limit) <= 0.01. A printed one-cent gap such as
            # 17.61 vs 17.62 can evaluate slightly above 0.01 and be excluded.
            # Use rounded Python floats here to preserve that edge behavior.
            c1_cmp = np.array([round(float(x), 2) for x in df1.loc[common, "close"].to_numpy()], dtype=float)
            c2_cmp = np.array([round(float(x), 2) for x in df2.loc[common, "close"].to_numpy()], dtype=float)
            hl1_cmp = np.array([round(float(x), 2) for x in high_limit_series(df1.loc[common, "pre_close"], st1, dt1, d1_series).to_numpy()], dtype=float)
            hl2_cmp = np.array([round(float(x), 2) for x in high_limit_series(df2.loc[common, "pre_close"], st2, dt2, d2_series).to_numpy()], dtype=float)
            is_lim1 = np.abs(c1_cmp - hl1_cmp) <= tol
            is_lim2 = np.abs(c2_cmp - hl2_cmp) <= tol
        else:
            is_lim1 = np.abs(c1_cents - hl1_cents) <= tol_cents
            is_lim2 = np.abs(c2_cents - hl2_cents) <= tol_cents
        if list_date_map is not None:
            pre1 = df1.loc[common, "pre_close"].astype(float).to_numpy()
            ipo_limit1 = np.array([_jq_round_limit(x, 144, 100) for x in pre1], dtype=float)
            d1_arr = d1_series.astype(str).to_numpy()
            list1 = np.array([list_date_map.get(code) == d for code, d in zip(common, d1_arr)], dtype=bool)
            no_ipo_limit1 = np.array([code.startswith("688") or _is_twenty_pct_board(code, d) for code, d in zip(common, d1_arr)], dtype=bool)
            ipo_lim1 = list1 & ~no_ipo_limit1 & (np.abs(c1_cents - np.rint(ipo_limit1 * 100).astype(np.int64)) <= tol_cents)
            is_lim1 = is_lim1 | ipo_lim1
        if list_date_map is not None:
            pre2 = df2.loc[common, "pre_close"].astype(float).to_numpy()
            ipo_limit2 = np.array([_jq_round_limit(x, 144, 100) for x in pre2], dtype=float)
            d2_arr = d2_series.astype(str).to_numpy()
            list2 = np.array([list_date_map.get(code) == d for code, d in zip(common, d2_arr)], dtype=bool)
            no_ipo_limit2 = np.array([code.startswith("688") or _is_twenty_pct_board(code, d) for code, d in zip(common, d2_arr)], dtype=bool)
            ipo_lim2 = list2 & ~no_ipo_limit2 & (np.abs(c2_cents - np.rint(ipo_limit2 * 100).astype(np.int64)) <= tol_cents)
            is_lim2 = is_lim2 | ipo_lim2
        mask = is_lim1 & ~is_lim2
        result.extend(list(common[mask]))

    # --- IPO 首日股票：仅 df1 有数据（prev2 无数据 = 上市前）---
    # prev2 无数据 → prev2 必然不涨停（条件自动满足）
    # 只需验证 prev 是否触及首日涨停价
    if d1_date is not None and list_date_map is not None:
        d1_only = df1.index.difference(df2.index)
        for code in d1_only:
            ld = list_date_map.get(code, "")
            if ld != d1_date:
                # 不是首日（可能是停牌复牌），跳过
                continue
            if code.startswith("30") or code.startswith("688"):
                # 创业板（2020-08-24 起）/科创板：首 5 日无涨跌幅限制，无法触板
                continue
            # 沪深主板（2023-04-10 以前）：首日限制 +44%
            pc = float(df1.loc[code, "pre_close"])
            cl = float(df1.loc[code, "close"])
            ipo_limit = _jq_round_limit(pc, 144, 100)  # +44%
            if abs(int(round(cl * 100)) - int(round(ipo_limit * 100))) <= tol_cents:
                result.append(code)

    return result


def board_counts(
    df1: pd.DataFrame,
    df2: pd.DataFrame,
    df3: pd.DataFrame,
    st1: set[str] | None = None,
    st2: set[str] | None = None,
    st3: set[str] | None = None,
    d1_date: str | None = None,
    d2_date: str | None = None,
    d3_date: str | None = None,
    tol: float | None = None,
) -> dict[str, int]:
    if tol is None:
        tol = LIMIT_TOL
    common = df1.index.intersection(df2.index).intersection(df3.index)
    if len(common) == 0:
        return {}
    c1 = df1.loc[common, "close"].astype(float)
    c2 = df2.loc[common, "close"].astype(float)
    c3 = df3.loc[common, "close"].astype(float)
    d1_series = df1.loc[common, "date"] if "date" in df1.columns else pd.Series(d1_date, index=common)
    d2_series = df2.loc[common, "date"] if "date" in df2.columns else pd.Series(d2_date, index=common)
    d3_series = df3.loc[common, "date"] if "date" in df3.columns else pd.Series(d3_date, index=common)
    limit1 = (c1 - high_limit_series(df1.loc[common, "pre_close"], st1, trade_date=d1_series)).abs() <= tol
    limit2 = (c2 - high_limit_series(df2.loc[common, "pre_close"], st2, trade_date=d2_series)).abs() <= tol
    limit3 = (c3 - high_limit_series(df3.loc[common, "pre_close"], st3, trade_date=d3_series)).abs() <= tol
    boards = pd.Series(0, index=common, dtype="int8")
    boards.loc[limit1] = 1
    boards.loc[limit1 & limit2] = 2
    boards.loc[limit1 & limit2 & limit3] = 3
    boards = boards[boards > 0]
    return boards.astype(int).to_dict()


def compute_raw_mode(trade_dates: list[str], idx: int, idx_map: dict[str, float], fb_perf: float) -> str:
    # JoinQuant attribute_history can look back before the backtest start.
    # Use the full local index history before today's 9:05, not just the
    # strategy warmup window.
    today = trade_dates[idx]
    idx_dates = sorted(d for d in idx_map if d < today)
    vals = [idx_map[d] for d in idx_dates[-65:]]
    if len(vals) < 20:
        return "bear"
    arr = np.asarray(vals, dtype=float)
    high20 = arr[-20:].max()
    if high20 > 0 and (arr[-1] - high20) / high20 <= -0.12:
        return "bear"
    if len(arr) < 60:
        return "bear"
    ma20, ma60, price = arr[-20:].mean(), arr[-60:].mean(), arr[-1]
    days_above = int((arr[-30:] > ma60).sum())
    if price <= ma60 and ma20 <= ma60:
        return "bear"
    if price <= ma60 and ma20 > ma60:
        return "cautious" if fb_perf > 0 else "bear"
    if days_above >= len(arr[-30:]) * 0.66:
        return "bull"
    return "cautious" if fb_perf > -0.02 else "bear"


def filter_base(
    first_boards: list[str],
    df_prev: pd.DataFrame,
    circ: pd.Series,
    st_set: set[str],
    list_date: dict[str, str],
    name_map: dict[str, str],
    list_status: dict[str, str],
    delist_date: dict[str, str],
    today: str,
    market_mode: str,
    use_st_list_filter: bool,
    delist_tail_days: int,
) -> tuple[list[str], dict[str, int]]:
    drops = {"st": 0, "delist": 0, "ipo": 0, "cap": 0, "money": 0, "bullmoney": 0, "avg": 0}
    out = []
    today_ts = pd.Timestamp(today)
    for code in first_boards:
        nm = name_map.get(code, "")
        if (use_st_list_filter and code in st_set) or "ST" in nm or "st" in nm or "*" in nm:
            drops["st"] += 1
            continue
        dd = delist_date.get(code, "")
        if list_status.get(code) == "D" and len(dd) == 8:
            days_to_delist = (pd.Timestamp(dd) - today_ts).days
            if days_to_delist <= delist_tail_days:
                drops["delist"] += 1
                continue
        ld = list_date.get(code, "")
        if len(ld) == 8 and (today_ts - pd.Timestamp(ld)).days < IPO_DAYS:
            drops["ipo"] += 1
            continue
        cv = float(circ.get(code, 0))
        if not (CIRC_MIN < cv < CIRC_MAX):
            drops["cap"] += 1
            continue
        r = df_prev.loc[code]
        money, vol, close = float(r["amount"]), float(r["vol"]), float(r["close"])
        if money < MONEY_MIN:
            drops["money"] += 1
            continue
        if market_mode == "bull" and money > MONEY_MAX_BULL:
            drops["bullmoney"] += 1
            continue
        avg_chg = money / vol / close * 1.1 - 1 if vol > 0 and close > 0 else 0
        if avg_chg < 0.07:
            drops["avg"] += 1
            continue
        out.append(code)
    return out, drops


def apply_v130(cands: list[str], prev: str, df_prev: pd.DataFrame, st_set: set[str]) -> tuple[list[str], int, int]:
    kept, tail, err = [], 0, 0
    for code in cands:
        mdf = minute_bars(code, prev)
        if mdf.empty:
            kept.append(code)
            continue
        hl = high_limit(df_prev.loc[code, "pre_close"], code, code in st_set, prev)
        hit = mdf[mdf["close"].astype(float) >= hl - 0.001]
        if hit.empty:
            kept.append(code)
            continue
        first_hit = pd.to_datetime(hit.iloc[0]["trade_time"])
        if first_hit.hour >= 14:
            tail += 1
            continue
        kept.append(code)
    return kept, tail, err


def apply_v122_blast_filter(
    cands: list[str],
    prev: str,
    trade_dates_before_today: list[str],
    daily: dict[str, pd.DataFrame],
) -> tuple[list[str], int]:
    kept, removed = [], 0
    if len(trade_dates_before_today) < 31:
        return cands, 0
    hist_dates = trade_dates_before_today[-31:]
    for code in cands:
        vols = hist_values(code, hist_dates, daily, "vol", fq_pre=False)
        highs = hist_values(code, hist_dates, daily, "high", fq_pre=True)
        closes = hist_values(code, hist_dates, daily, "close", fq_pre=True)
        if len(vols) < 31:
            kept.append(code)
            continue
        prev_vols = np.asarray(vols[-6:-1], dtype=float)
        if len(prev_vols) == 5 and prev_vols.min() > 0:
            is_blast = (vols[-1] > float(prev_vols.mean()) * 8) or (vols[-1] > float(prev_vols.min()) * 12)
            is_new_high = closes[-1] > float(np.max(highs[-31:-1]))
            if is_blast and is_new_high:
                removed += 1
                continue
        kept.append(code)
    return kept, removed


def hist_values(
    code: str,
    dates: list[str],
    daily: dict[str, pd.DataFrame],
    field: str,
    fq_pre: bool = False,
) -> list[float]:
    rows = []
    for d in dates:
        df = daily.get(d)
        if df is None or code not in df.index:
            continue
        r = df.loc[code]
        val = float(r[field])
        adj = float(r.get("adj_factor", 1.0) or 1.0)
        rows.append((val, adj))
    if not fq_pre or not rows:
        return [v for v, _ in rows]
    ref_adj = rows[-1][1]
    if ref_adj <= 0:
        return [v for v, _ in rows]
    return [v * adj / ref_adj for v, adj in rows]


def score_with_left_pressure(
    cands: list[str],
    prev: str,
    trade_dates_before_today: list[str],
    daily: dict[str, pd.DataFrame],
    circ: pd.Series,
) -> list[str]:
    scored = []
    if not cands:
        return cands
    hist_dates = trade_dates_before_today[-100:]
    high_dates = trade_dates_before_today[-60:]
    for code in cands:
        closes = hist_values(code, hist_dates, daily, "close", fq_pre=True)
        vols = hist_values(code, hist_dates, daily, "vol", fq_pre=False)
        if len(closes) < 60 or len(vols) < 60:
            continue
        c = np.asarray(closes, dtype=float)
        v = np.asarray(vols, dtype=float)
        prev_highs = c[:-1]
        prev_vols = v[:-1]
        max_idx = int(np.argmax(prev_highs))
        is_break = c[-1] >= prev_highs[max_idx] * 0.99
        vol_ok = v[-1] >= prev_vols[max_idx] * 0.9 if prev_vols[max_idx] > 0 else False
        lp_score = 1.0 if (is_break and vol_ok) else 0.5 if is_break else 0.0

        wr = 0.0
        circ_yi = float(circ.get(code, 0))
        if circ_yi > 0 and c[-1] > 0:
            highs = hist_values(code, high_dates, daily, "high", fq_pre=True)
            lows = hist_values(code, high_dates, daily, "low", fq_pre=True)
            n = min(len(c), 60, len(highs), len(lows))
            if n >= 20:
                circulating_shares = circ_yi * 1e8 / c[-1]
                _, wr = calc_chip_stats(c[-n:], highs[-n:], lows[-n:], v[-n:], circulating_shares, bins=30)
        scored.append((code, lp_score * 0.5 + wr * 0.5, lp_score, wr))
    if not scored:
        return []
    scored.sort(key=lambda x: -x[1])
    return [code for code, _, _, _ in scored]

def scan_bear_scorpion(
    first_boards: list[str],
    df_prev: pd.DataFrame,
    daily_dates: list[str],
    daily: dict[str, pd.DataFrame],
    st_set: set[str],
    list_date: dict[str, str],
    name_map: dict[str, str],
    list_status: dict[str, str],
    delist_date: dict[str, str],
    today: str,
    use_st_list_filter: bool,
    delist_tail_days: int,
    scorpion_st_list_filter: bool = False,
    scorpion_delist_name_filter: bool = False,
) -> list[str]:
    """Bear-mode v227 天蝎座 candidates from yesterday's main-board first boards."""
    today_ts = pd.Timestamp(today)
    out = []
    for code in first_boards:
        if code.startswith("30"):
            continue
        nm = name_map.get(code, "")
        # Don't exclude ST stocks by name or st_set here; the 2022 JQ backtest
        # included ST stocks in bear_candidates (bear_pool had no ST name filter
        # in the 2022 code version). ST is excluded from yjj candidates above.
        # if (use_st_list_filter and code in st_set) or "ST" in nm or "st" in nm or "*" in nm:
        #     continue
        if "ST" in nm or "st" in nm or "*" in nm:
            # name_map stores base names without *ST prefix, so this rarely fires
            continue
        if scorpion_st_list_filter and code in st_set:
            continue
        if scorpion_delist_name_filter and "退" in nm:
            continue
        dd = delist_date.get(code, "")
        if list_status.get(code) == "D" and len(dd) == 8:
            days_to_delist = (pd.Timestamp(dd) - today_ts).days
            if days_to_delist <= delist_tail_days:
                continue
        ld = list_date.get(code, "")
        if len(ld) == 8 and (today_ts - pd.Timestamp(ld)).days < IPO_DAYS:
            continue
        closes = hist_values(code, daily_dates[-60:], daily, "close", fq_pre=True)
        if len(closes) < 20:
            continue
        h60, l60 = max(closes), min(closes)
        if h60 <= l60:
            continue
        # Match JoinQuant-style decimal behavior around the exact midpoint.
        # hdata stores float32 prices, so a mathematically exact 0.5 can become
        # 0.50000016 and incorrectly drop from the bear scorpion pool.
        if (closes[-1] - l60) / (h60 - l60) <= 0.500001:
            out.append(code)
    return out


_MINUTE_CACHE: dict[tuple[str, str], pd.DataFrame] = {}


def minute_bars(code: str, day: str) -> pd.DataFrame:
    key = (code, day)
    if key in _MINUTE_CACHE:
        return _MINUTE_CACHE[key]
    path = ROOT / "1m_stock" / hdata_minute_code(code) / f"{day[:4]}.parquet"
    if not path.exists():
        _MINUTE_CACHE[key] = pd.DataFrame()
        return _MINUTE_CACHE[key]
    try:
        df = pd.read_parquet(path, columns=["date", "trade_time", "close"], filters=[("date", "==", day)])
    except Exception:
        df = pd.read_parquet(path, columns=["date", "trade_time", "close"])
        df = df[df["date"].astype(str) == day].copy()
    if df.empty:
        _MINUTE_CACHE[key] = df
        return df
    df["hhmm"] = pd.to_datetime(df["trade_time"]).dt.hour * 100 + pd.to_datetime(df["trade_time"]).dt.minute
    _MINUTE_CACHE[key] = df
    return df


def buy_cost(price: float, shares: int) -> float:
    return shares * price + max(shares * price * COMMISSION, MIN_COMMISSION)


def affordable_buy_shares(price: float, target_cash: float, available_cash: float) -> int:
    if price <= 0 or target_cash <= 0 or available_cash <= 0:
        return 0
    cash_cap = min(target_cash, available_cash)
    shares = int(cash_cap / price / 100) * 100
    while shares > 0 and buy_cost(price, shares) > available_cash:
        shares -= 100
    return max(shares, 0)


def sell_proceeds(price: float, shares: int) -> float:
    gross = shares * price
    return gross - max(gross * COMMISSION, MIN_COMMISSION) - gross * STAMP_TAX


def mark_to_market(cash: float, held: dict[str, dict], day: str, daily: dict[str, pd.DataFrame]) -> float:
    value = cash
    df = daily.get(day)
    if df is None:
        return value
    for code, pos in held.items():
        if code in df.index:
            value += int(pos["shares"]) * float(df.loc[code, "close"])
        else:
            value += int(pos["shares"]) * float(pos["entry"])
    return value


def simulate_v227_exit(
    code: str,
    pos: dict,
    day: str,
    daily_row: pd.Series,
    today_st_set: set[str],
) -> tuple[float | None, str]:
    entry = float(pos["entry"])
    is_st = code in today_st_set
    hl = high_limit(float(daily_row["pre_close"]), code, is_st, day)
    df = minute_bars(code, day)
    if df.empty:
        close = float(daily_row["close"])
        if close >= hl * 0.999:
            return None, "carryover"
        if close > entry:
            return close, "morning_profit_fallback"
        if close <= entry * 0.98:
            return close, "midday_loss_fallback"
        if close <= entry * 0.95:
            return min(close, entry * 0.95), "stop_loss_fallback"
        return close, "eod_clear_fallback"

    def first_at_or_after(hhmm: int) -> pd.Series | None:
        sub = df[df["hhmm"] >= hhmm]
        return None if sub.empty else sub.iloc[0]

    def shifted_hhmm(hhmm: int) -> int:
        minutes = (hhmm // 100) * 60 + (hhmm % 100) + SELL_TIME_SHIFT_MINUTES
        return (minutes // 60) * 100 + minutes % 60

    # In JoinQuant daily backtests, run_daily(..., 'every_bar') does not scan
    # the whole historical 1m tape. For parity with the observed transaction
    # log, model the v227 -5% stop as an opening check near 09:30.
    bar0930 = first_at_or_after(shifted_hhmm(930))
    ll = low_limit(float(daily_row["pre_close"]), code, is_st)
    if bar0930 is not None:
        p = float(bar0930["close"])
        if p > 0 and p < hl * 0.999 and p > ll * 1.001 and p <= entry * 0.95:
            return p, "stop_loss"

    bar1125 = first_at_or_after(shifted_hhmm(1125))
    if bar1125 is not None:
        p = float(bar1125["close"])
        if not pos.get("leader") and p > entry and p < hl * 0.999 and p > ll * 1.001:
            return p, "morning_profit"

    bar1301 = first_at_or_after(shifted_hhmm(1301))
    if bar1301 is not None:
        p = float(bar1301["close"])
        if not pos.get("leader") and p < hl * 0.999 and p > ll * 1.001 and p <= entry * 0.98:
            return p, "midday_loss"

    bar1450 = first_at_or_after(shifted_hhmm(1450))
    if bar1450 is None:
        bar1450 = df.iloc[-1]
    p = float(bar1450["close"])
    if p >= hl * 0.999:
        return None, "carryover"
    if p <= ll * 1.001:
        return None, "carryover"
    if pos.get("leader"):
        return p, "leader_exit"
    return p, "eod_clear"


def apply_trade_state_after_sell(
    *,
    entry: float,
    exit_price: float,
    buy_mode: str,
    recent_trades: deque[int],
    bull_state: dict[str, int | bool],
) -> None:
    """Approximate mother `_record_trade` side effects for v227 sells."""
    if entry <= 0:
        return
    is_win = exit_price > entry
    recent_trades.append(1 if is_win else 0)
    if buy_mode == "bull":
        if is_win:
            bull_state["bull_consec_loss"] = 0
            bull_state["bull_cooldown"] = 0
        else:
            prev = int(bull_state.get("bull_consec_loss", 0))
            bull_state["bull_consec_loss"] = prev + 1
            if bull_state["bull_consec_loss"] >= 3:
                bull_state["bull_cooldown"] = 5
                bull_state["bull_release_confirm_pending"] = True
                if prev < 3:
                    bull_state["bull_force_clear"] = True
    elif buy_mode in ("cautious", "bear"):
        if is_win:
            bull_state["non_bull_consec_wins"] = int(bull_state.get("non_bull_consec_wins", 0)) + 1
            if bull_state["non_bull_consec_wins"] >= 1 and int(bull_state.get("bull_consec_loss", 0)) > 0:
                bull_state["bull_consec_loss"] = max(0, int(bull_state["bull_consec_loss"]) - 1)
                bull_state["non_bull_consec_wins"] = 0
                if int(bull_state["bull_consec_loss"]) < 3:
                    bull_state["bull_cooldown"] = 0
        else:
            bull_state["non_bull_consec_wins"] = 0


def explain_target_buy(
    target: dict,
    *,
    today: str,
    prev: str,
    market_mode: str,
    raw_market_mode: str,
    fb_perf: float,
    fb_pct: float,
    active: str,
    enable_v227: bool,
    open_hi: float,
    buy_block: str,
    held_before: set[str],
    slots_before: int,
    cands: list[str],
    bear_cands: list[str],
    local_yjj_buys: list[str],
    local_scorpion_buys: list[str],
    df_prev: pd.DataFrame,
    today_df: pd.DataFrame,
    st_today: set[str],
) -> dict:
    code = target["local_code"]
    path = target["path_guess"]
    path_cands = bear_cands if path == "scorpion" else cands
    local_buys = set(local_yjj_buys) | set(local_scorpion_buys)
    in_yjj = code in cands
    in_scorpion = code in bear_cands
    rank = path_cands.index(code) + 1 if code in path_cands else 0

    reason = ""
    open_price = np.nan
    yclose = np.nan
    high_lim = np.nan
    open_pct = np.nan

    if code in local_buys:
        reason = "local_bought"
    elif path == "yjj" and not enable_v227:
        reason = "not_enabled"
    elif path == "scorpion" and not enable_v227:
        reason = "not_enabled"
    elif path == "yjj" and buy_block:
        reason = "blocked_" + buy_block
    elif path == "scorpion" and market_mode != "bear":
        reason = "blocked_mode_not_bear"
    elif code not in path_cands:
        reason = "no_candidate"
    elif slots_before <= 0:
        reason = "no_slot"
    elif code in held_before:
        reason = "already_held_before_buy"
    elif code not in today_df.index:
        reason = "no_today_data"
    elif code not in df_prev.index:
        reason = "no_prev_data"
    else:
        yclose = float(df_prev.loc[code, "close"])
        row = today_df.loc[code]
        open_price = float(row["open"])
        high_lim = high_limit(float(row["pre_close"]), code, code in st_today, today)
        open_pct = open_price / yclose - 1 if yclose > 0 else np.nan
        if open_price <= 0 or yclose <= 0:
            reason = "bad_price"
        elif open_price >= high_lim * 0.999:
            reason = "open_limit"
        elif path == "yjj" and (open_pct < 0 or open_pct > open_hi):
            reason = "open_pct_out"
        elif path == "scorpion" and (open_pct < -0.04 or open_pct > -0.03):
            reason = "open_pct_out"
        elif slots_before <= len(local_yjj_buys if path == "yjj" else local_scorpion_buys):
            reason = "no_slot_after_prior_candidates"
        else:
            reason = "passed_filters_not_bought"

    return {
        "date": today,
        "prev": prev,
        "time": target["time"],
        "code": target["code"],
        "path_guess": path,
        "jq_price": target["jq_price"],
        "jq_shares": target["jq_shares"],
        "explain_reason": reason,
        "market_mode": market_mode,
        "raw_market_mode": raw_market_mode,
        "first_board_perf": round(fb_perf, 8) if not pd.isna(fb_perf) else np.nan,
        "fb_pct": round(fb_pct, 6) if not pd.isna(fb_pct) else np.nan,
        "active": active,
        "enable_v227": bool(enable_v227),
        "buy_block": buy_block,
        "open_hi": round(open_hi, 6),
        "held_before": len(held_before),
        "slots_before": slots_before,
        "in_yjj": bool(in_yjj),
        "in_scorpion": bool(in_scorpion),
        "candidate_rank": rank,
        "yjj_n": len(cands),
        "scorpion_n": len(bear_cands),
        "local_yjj_buys": "|".join(jq_code(c) for c in local_yjj_buys),
        "local_scorpion_buys": "|".join(jq_code(c) for c in local_scorpion_buys),
        "open": round(open_price, 4) if not pd.isna(open_price) else np.nan,
        "yclose": round(yclose, 4) if not pd.isna(yclose) else np.nan,
        "high_limit": round(high_lim, 4) if not pd.isna(high_lim) else np.nan,
        "open_pct": round(open_pct, 6) if not pd.isna(open_pct) else np.nan,
    }


def probe():
    global WARMUP_START, BACKTEST_START, BACKTEST_END, PRINT_START, PRINT_END, VERBOSE_DAILY
    global SELL_TIME_SHIFT_MINUTES, INCLUDE_SCORPION, ENABLE_LEADER_PROTECT, USE_ST_LIST_FILTER
    global DELIST_TAIL_DAYS, SCORPION_ST_LIST_FILTER, SCORPION_DELIST_NAME_FILTER, JQ_NA_PROPAGATION, USE_JQ_FB_PERF_OVERRIDE, USE_JQ_FB_STATE_OVERRIDE, FORCE_V227_ROUTE, SIMULATE_COOLDOWNS, DISABLE_CAUTIOUS_POISON, YJJ_EXCLUDE_OPEN_RANGES, TRADES_OUT, EQUITY_OUT, STATE_OUT, EXPLAIN_OUT
    parser = argparse.ArgumentParser(description="Probe local v227 一进二 behavior.")
    parser.add_argument("--start", default=BACKTEST_START, help="Backtest start YYYYMMDD")
    parser.add_argument("--end", default=BACKTEST_END, help="Backtest end YYYYMMDD")
    parser.add_argument("--warmup", default=WARMUP_START, help="Warmup start YYYYMMDD")
    parser.add_argument("--verbose", action="store_true", help="Print daily diagnostics")
    parser.add_argument("--sell-time-shift", type=int, default=SELL_TIME_SHIFT_MINUTES,
                        help="Shift scheduled sell checks by N minutes; use -1/0/1 to test bar alignment.")
    parser.add_argument("--include-scorpion", default=INCLUDE_SCORPION, action="store_true",
                        help="Also simulate v227 天蝎座 bear-mode low-open branch.")
    parser.add_argument("--no-scorpion", dest="include_scorpion", action="store_false",
                        help="Disable scorpion (overrides module default).")
    parser.add_argument("--leader-protect", default=ENABLE_LEADER_PROTECT, action="store_true",
                        help="Protect held v227 >=3-board leaders until they break limit near close.")
    parser.add_argument("--use-st-list-filter", default=USE_ST_LIST_FILTER, action="store_true",
                        help="Use local hdata st_list as an ST filter.")
    parser.add_argument("--no-st-list-filter", dest="use_st_list_filter", action="store_false",
                        help="Disable ST list filter (overrides module default).")
    parser.add_argument("--delist-tail-days", type=int, default=DELIST_TAIL_DAYS,
                        help="Exclude delisted stocks within N calendar days before delist_date.")
    parser.add_argument("--scorpion-st-list-filter", default=SCORPION_ST_LIST_FILTER, action="store_true",
                        help="Diagnostic: also exclude local hdata ST-list names from bear scorpion candidates.")
    parser.add_argument("--no-scorpion-st-list-filter", dest="scorpion_st_list_filter", action="store_false",
                        help="Diagnostic: do not exclude local hdata ST-list names from bear scorpion candidates.")
    parser.add_argument("--scorpion-delist-name-filter", default=SCORPION_DELIST_NAME_FILTER, action="store_true",
                        help="Diagnostic: exclude names containing 退 from bear scorpion candidates.")
    parser.add_argument("--no-scorpion-delist-name-filter", dest="scorpion_delist_name_filter", action="store_false",
                        help="Diagnostic: do not exclude names containing 退 from bear scorpion candidates.")
    parser.add_argument("--jq-na-propagation", default=JQ_NA_PROPAGATION, action="store_true",
                        help="Mimic JoinQuant calc_fb_perf NaN propagation when PFB names lack close data.")
    parser.add_argument("--no-jq-na-propagation", dest="jq_na_propagation", action="store_false",
                        help="Skip missing PFB names when calculating fb_perf.")
    parser.add_argument("--jq-fb-perf-override", default=USE_JQ_FB_PERF_OVERRIDE, action="store_true",
                        help="Use jq_fb_perf_jun_aug.json to override first_board_perf on covered dates.")
    parser.add_argument("--no-jq-fb-perf-override", dest="jq_fb_perf_override", action="store_false",
                        help="Do not use jq_fb_perf_jun_aug.json overrides.")
    parser.add_argument("--jq-fb-state-override", default=USE_JQ_FB_STATE_OVERRIDE, action="store_true",
                        help="Use jq_fb_state_overrides.json to override first_board_perf/fb_pct on covered dates.")
    parser.add_argument("--no-jq-fb-state-override", dest="jq_fb_state_override", action="store_false",
                        help="Do not use jq_fb_state_overrides.json overrides.")
    parser.add_argument("--force-v227-route", default=FORCE_V227_ROUTE, action="store_true",
                        help="Mimic branch_test=force_v227: force enable_v227 and two slots after route calculation.")
    parser.add_argument("--normal-route", dest="force_v227_route", action="store_false",
                        help="Use mother normal route instead of force_v227.")
    parser.add_argument("--simulate-cooldowns", default=SIMULATE_COOLDOWNS, action="store_true",
                        help="Simulate bull/stoploss cooldown state. Useful only after upstream buys are aligned.")
    parser.add_argument("--no-simulate-cooldowns", dest="simulate_cooldowns", action="store_false",
                        help="Disable cooldown simulation.")
    parser.add_argument("--disable-cautious-poison", default=DISABLE_CAUTIOUS_POISON, action="store_true",
                        help="Diagnostic: do not block cautious fb_pct in [0.4, 0.6).")
    parser.add_argument("--enable-cautious-poison", dest="disable_cautious_poison", action="store_false",
                        help="Keep the mother cautious fb_pct [0.4, 0.6) block.")
    parser.add_argument("--yjj-exclude-open-ranges", default="",
                        help="Diagnostic: comma-separated YJJ open_pct ranges to skip, e.g. 0.02:0.04,0.06:1.")
    parser.add_argument("--trades-out", default=str(TRADES_OUT), help="Output CSV for trades.")
    parser.add_argument("--equity-out", default=str(EQUITY_OUT), help="Output CSV for daily equity.")
    parser.add_argument("--state-out", default=str(STATE_OUT), help="Output CSV for daily pre-trade state.")
    parser.add_argument("--explain-jq-raw", default="", help="JQ transaction history text; if set, explain each JQ buy with local state.")
    parser.add_argument("--explain-out", default=str(EXPLAIN_OUT), help="Output CSV for JQ-buy explanations.")
    args = parser.parse_args()
    BACKTEST_START = args.start
    BACKTEST_END = args.end
    WARMUP_START = args.warmup
    PRINT_START = args.start
    PRINT_END = args.end
    VERBOSE_DAILY = args.verbose
    SELL_TIME_SHIFT_MINUTES = args.sell_time_shift
    INCLUDE_SCORPION = args.include_scorpion
    ENABLE_LEADER_PROTECT = args.leader_protect
    USE_ST_LIST_FILTER = args.use_st_list_filter
    DELIST_TAIL_DAYS = args.delist_tail_days
    SCORPION_ST_LIST_FILTER = args.scorpion_st_list_filter
    SCORPION_DELIST_NAME_FILTER = args.scorpion_delist_name_filter
    JQ_NA_PROPAGATION = args.jq_na_propagation
    USE_JQ_FB_PERF_OVERRIDE = args.jq_fb_perf_override
    USE_JQ_FB_STATE_OVERRIDE = args.jq_fb_state_override
    FORCE_V227_ROUTE = args.force_v227_route
    SIMULATE_COOLDOWNS = args.simulate_cooldowns
    DISABLE_CAUTIOUS_POISON = args.disable_cautious_poison
    YJJ_EXCLUDE_OPEN_RANGES = parse_open_ranges(args.yjj_exclude_open_ranges)
    TRADES_OUT = Path(args.trades_out)
    EQUITY_OUT = Path(args.equity_out)
    STATE_OUT = Path(args.state_out)
    EXPLAIN_OUT = Path(args.explain_out)
    jq_buy_targets = parse_jq_buy_targets(Path(args.explain_jq_raw)) if args.explain_jq_raw else {}

    years = list(range(int(WARMUP_START[:4]), int(PRINT_END[:4]) + 1))
    daily = load_daily(years)
    daily_by_code = build_daily_by_code(daily)
    ind = load_indicator(years)
    st = load_st(years)
    list_date, name_map, list_status, delist_date = load_basic()
    idx_map = load_index()
    trade_dates = sorted(d for d in daily if WARMUP_START <= d <= BACKTEST_END)
    st = fill_st_calendar(st, trade_dates)
    # 退市整理期股票集合（涨停 10%，不适用 ST 5% 规则）
    delist_trans_map = build_delist_trans_map(list_status, delist_date, trade_dates)
    start_idx = next((j for j, d in enumerate(trade_dates) if d >= BACKTEST_START), len(trade_dates))
    fb_hist = deque(maxlen=FB_WIN)
    prev_first_boards: list[str] = []
    held_v227: dict[str, dict] = {}
    trades: list[dict] = []
    equity: list[dict] = []
    states: list[dict] = []
    explanations: list[dict] = []
    cash = INIT_CASH
    bull_sticky = 0
    stoploss_cooldown = 0
    bull_state: dict[str, int | bool] = {
        "bull_consec_loss": 0,
        "bull_cooldown": 0,
        "non_bull_consec_wins": 0,
        "bull_force_clear": False,
        "bull_release_confirm_pending": False,
    }
    board_heights: deque[int] = deque(maxlen=20)
    recent_trades: deque[int] = deque(maxlen=WIN_WINDOW)

    for i, today in enumerate(trade_dates):
        if i < 2 or i < start_idx:
            continue
        if SIMULATE_COOLDOWNS and stoploss_cooldown > 0:
            stoploss_cooldown -= 1
        if SIMULATE_COOLDOWNS and int(bull_state.get("bull_cooldown", 0)) > 0:
            bull_state["bull_cooldown"] = int(bull_state["bull_cooldown"]) - 1
        prev, prev2 = trade_dates[i - 1], trade_dates[i - 2]
        prev3 = trade_dates[i - 3] if i >= 3 else prev2
        df_prev_cal, df_prev2_cal, df_prev3_cal = daily[prev], daily[prev2], daily[prev3]
        df_prev, df_prev2, df_prev3 = effective_history_frames(daily_by_code, prev, 3)
        st_prev = st.get(prev, set())
        st_prev2 = st.get(prev2, set())
        st_prev3 = st.get(prev3, set())
        st_today = st.get(today, set())
        dt_prev = delist_trans_map.get(prev, set())    # 退市整理期（prev）
        dt_prev2 = delist_trans_map.get(prev2, set())  # 退市整理期（prev2）

        fb_perf = calc_fb_perf_from_prev_boards(
            prev_first_boards,
            df_prev,
            df_prev2,
            jq_na_propagation=JQ_NA_PROPAGATION,
        )

        # === 精准 NaN 注入（暂时禁用以单独验证 R7 修复）===
        if USE_JQ_FB_PERF_OVERRIDE and today in JQ_FB_PERF_OVERRIDE:
            fb_perf = JQ_FB_PERF_OVERRIDE[today]

        fb_hist.append(fb_perf)
        if isinstance(fb_perf, float) and np.isnan(fb_perf):
            fb_pct = 0.0  # NaN fallback to 0（与 JQ 一致）
        elif len(fb_hist) >= FB_MIN_HIST:
            fb_pct = sum(1 for x in fb_hist if (not (isinstance(x, float) and np.isnan(x))) and x < fb_perf) / len(fb_hist)
        else:
            fb_pct = 0.5
        if USE_JQ_FB_STATE_OVERRIDE and today in JQ_FB_STATE_OVERRIDE:
            ov = JQ_FB_STATE_OVERRIDE[today]
            if "first_board_perf" in ov:
                fb_perf = float(ov["first_board_perf"])
            if "fb_pct" in ov:
                fb_pct = float(ov["fb_pct"])
        raw_market_mode = compute_raw_mode(trade_dates, i, idx_map, fb_perf)
        if raw_market_mode == "bull":
            bull_sticky = 2
            market_mode = "bull"
        elif bull_sticky > 0 and raw_market_mode == "cautious":
            bull_sticky -= 1
            market_mode = "bull"
        else:
            bull_sticky = 0
            market_mode = raw_market_mode
        # JQ 的涨停容差是 mode-dependent：
        #   bear → _scan_boards_for_prev 用 0.01
        #   cautious/bull → _scan_all 用 0.02
        # 这影响 first_boards 识别（PFB 用于 fb_perf, yjj 候选基础）
        scan_tol = 0.01 if market_mode == "bear" else 0.02
        first_boards = identify_first_boards(
            df_prev, df_prev2, st_prev, st_prev2, tol=scan_tol,
            d1_date=prev, d2_date=prev2, list_date_map=list_date,
            dt1=dt_prev, dt2=dt_prev2,
        )
        # first_boards_for_perf 与 first_boards 用相同容差（JQ 中是同一变量）
        first_boards_for_perf = identify_first_boards(
            df_prev, df_prev2, st_prev, st_prev2, tol=scan_tol,
            d1_date=prev, d2_date=prev2, list_date_map=list_date,
            dt1=dt_prev, dt2=dt_prev2,
        )
        prev_board_counts = board_counts(
            df_prev, df_prev2, df_prev3, st_prev, st_prev2, st_prev3,
            d1_date=prev, d2_date=prev2, d3_date=trade_dates[i - 3] if i >= 3 else None,
        )
        board_heights.append(max(prev_board_counts.values()) if prev_board_counts else 0)
        prev_first_boards = first_boards_for_perf
        low_tilt = low_price_tilt_active(market_mode, fb_pct, fb_perf, board_heights, recent_trades)
        bull_release_guard = False
        active = route_active(market_mode, fb_pct, bull_release_guard, today)
        enable_v227 = active == "v227"
        if FORCE_V227_ROUTE:
            active = "force_v227"
            enable_v227 = True

        base, drops = filter_base(
            first_boards, df_prev, ind.get(prev, pd.Series(dtype=float)),
            st_prev, list_date, name_map, list_status, delist_date,
            today, market_mode, USE_ST_LIST_FILTER, DELIST_TAIL_DAYS,
        )
        base, blast = apply_v122_blast_filter(base, prev, trade_dates[:i], daily)
        cands, tail, err = apply_v130(base, prev, df_prev, st_prev)
        if cands and market_mode == "bull":
            cands = score_with_left_pressure(cands, prev, trade_dates[:i], daily, ind.get(prev, pd.Series(dtype=float)))
        elif cands:
            cands = apply_low_price_tilt(cands, df_prev["close"], low_tilt)
        bear_cands = []
        if INCLUDE_SCORPION and market_mode == "bear":
            bear_cands = scan_bear_scorpion(
                first_boards, df_prev, trade_dates[:i], daily, st_prev,
                list_date, name_map, list_status, delist_date, today,
                USE_ST_LIST_FILTER, DELIST_TAIL_DAYS,
                SCORPION_ST_LIST_FILTER, SCORPION_DELIST_NAME_FILTER,
            )
            bear_cands = apply_low_price_tilt(bear_cands, df_prev["close"], low_tilt)
        open_hi = 0.095 if market_mode == "bull" else (0.07 if fb_perf > 0 else 0.03)
        held_at_buy = len(held_v227)
        held_before_buy = set(held_v227)
        buy_block = ""
        if market_mode == "bear":
            buy_block = "bear_mode"
        elif market_mode == "bull" and fb_pct < 0.2:
            buy_block = "bull_pct_lt_020"
        elif SIMULATE_COOLDOWNS and market_mode == "bull" and int(bull_state.get("bull_cooldown", 0)) > 0:
            buy_block = "bull_cooldown"
        elif (not DISABLE_CAUTIOUS_POISON) and market_mode == "cautious" and 0.4 <= fb_pct < 0.6:
            buy_block = "cautious_pct_040_060"
        elif SIMULATE_COOLDOWNS and stoploss_cooldown > 0 and market_mode != "bull":
            buy_block = "stoploss_cooldown"
        slots = 0 if buy_block else (SLOTS - len(held_v227) if (TRACK_SLOTS or SIMULATE_V227_SELLS) else SLOTS)
        if today >= BACKTEST_START:
            states.append({
                "date": today,
                "prev": prev,
                "prev2": prev2,
                "raw_market_mode": raw_market_mode,
                "market_mode": market_mode,
                "first_board_perf": round(fb_perf, 8) if not pd.isna(fb_perf) else np.nan,
                "fb_pct": round(fb_pct, 6) if not pd.isna(fb_pct) else np.nan,
                "fb_hist_len": len(fb_hist),
                "active": active,
                "enable_v227": bool(enable_v227),
                "v227_slots": SLOTS if enable_v227 else 0,
                "held_v227": len(held_v227),
                "slots": slots,
                "buy_block": buy_block,
                "bull_sticky": bull_sticky,
                "bull_cooldown": int(bull_state.get("bull_cooldown", 0)),
                "bull_consec_loss": int(bull_state.get("bull_consec_loss", 0)),
                "bull_release_guard": bool(bull_release_guard),
                "bull_release_confirm_pending": bool(bull_state.get("bull_release_confirm_pending", False)),
                "stoploss_cooldown": int(stoploss_cooldown),
                "v227_shock_cooldown": 0,
                "recent_trades_len": len(recent_trades),
                "recent_trades_win": int(sum(recent_trades)),
                "recent_trades_wr": round(win_rate(recent_trades), 6),
                "low_tilt": bool(low_tilt),
                "jq_na_propagation": bool(JQ_NA_PROPAGATION),
                "jq_fb_perf_override": bool(USE_JQ_FB_PERF_OVERRIDE),
                "jq_fb_state_override": bool(USE_JQ_FB_STATE_OVERRIDE),
                "force_v227_route": bool(FORCE_V227_ROUTE),
                "simulate_cooldowns": bool(SIMULATE_COOLDOWNS),
                "disable_cautious_poison": bool(DISABLE_CAUTIOUS_POISON),
                "scan_tol": scan_tol,
                "first_boards_n": len(first_boards),
                "base_n": len(base),
                "v130_n": len(cands),
                "bear_n": len(bear_cands),
                "first_boards_codes": "|".join(jq_code(c) for c in first_boards[:120]),
                "base_codes": "|".join(jq_code(c) for c in base[:120]),
                "v130_codes": "|".join(jq_code(c) for c in cands[:120]),
                "bear_codes": "|".join(jq_code(c) for c in bear_cands[:120]),
            })
        buys, buy_infos, detail = [], [], []
        today_df = daily[today]
        pos_pct = 1.0 if market_mode == "bull" else 0.75
        for code in cands:
            if slots <= len(buys):
                break
            if code not in today_df.index:
                detail.append(f"{jq_code(code)}:no_today")
                continue
            yclose = float(df_prev.loc[code, "close"])
            row = today_df.loc[code]
            op = float(row["open"])
            hl = high_limit(float(row["pre_close"]), code, code in st_today, today)
            opct = op / yclose - 1 if yclose > 0 else np.nan
            reason = "ok"
            if op <= 0 or yclose <= 0:
                reason = "bad_price"
            elif op >= hl * 0.999:
                reason = "open_limit"
            elif opct < 0 or opct > open_hi:
                reason = "open_pct"
            elif in_any_range(opct, YJJ_EXCLUDE_OPEN_RANGES):
                reason = "open_range_skip"
            detail.append(f"{jq_code(code)} pct={opct*100:.2f}% {reason}")
            if reason == "ok":
                slot_cash = cash * pos_pct / max(slots - len(buys), 1) if today >= BACKTEST_START else 0.0
                shares = affordable_buy_shares(op, slot_cash, cash)
                cost = buy_cost(op, shares) if shares > 0 else 0
                if shares > 0 and cost <= cash:
                    buys.append(code)
                    cash -= cost
                    buy_infos.append((code, op, shares, cash))
        if TRACK_SLOTS or SIMULATE_V227_SELLS:
            for code, op, shares, cash_after in buy_infos:
                held_v227[code] = {"entry": op, "entry_date": today, "shares": shares, "buy_mode": market_mode}
                trades.append({
                    "date": today,
                    "code": jq_code(code),
                    "side": "buy",
                    "price": round(op, 3),
                    "shares": shares,
                    "reason": "v227_yjj",
                    "entry_date": today,
                    "entry": round(op, 3),
                    "ret": 0.0,
                    "cash": round(cash_after, 2),
                })

        scorpion_buys, scorpion_detail = [], []
        held_before_scorpion = set(held_v227)
        scorpion_slots_before = SLOTS - len(held_v227)
        if INCLUDE_SCORPION and market_mode == "bear" and bear_cands:
            slots_left = SLOTS - len(held_v227)
            slot_cash = cash / max(slots_left, 1) if today >= BACKTEST_START else 0.0
            for code in bear_cands:
                if slots_left <= len(scorpion_buys):
                    break
                if code in held_v227 or code not in today_df.index:
                    continue
                yclose = float(df_prev.loc[code, "close"])
                row = today_df.loc[code]
                op = float(row["open"])
                hl = high_limit(float(row["pre_close"]), code, code in st_today, today)
                opct = op / yclose - 1 if yclose > 0 else np.nan
                reason = "ok"
                if op <= 0 or yclose <= 0:
                    reason = "bad_price"
                elif op >= hl * 0.999:
                    reason = "open_limit"
                elif opct < -0.04 or opct > -0.03:
                    reason = "open_pct"
                scorpion_detail.append(f"{jq_code(code)} pct={opct*100:.2f}% {reason}")
                if reason != "ok":
                    continue
                shares = affordable_buy_shares(op, slot_cash, cash)
                cost = buy_cost(op, shares) if shares > 0 else 0
                if shares > 0 and cost <= cash:
                    cash -= cost
                    held_v227[code] = {"entry": op, "entry_date": today, "shares": shares}
                    held_v227[code]["buy_mode"] = market_mode
                    scorpion_buys.append(code)
                    trades.append({
                        "date": today,
                        "code": jq_code(code),
                        "side": "buy",
                        "price": round(op, 3),
                        "shares": shares,
                        "reason": "v227_scorpion",
                        "entry_date": today,
                        "entry": round(op, 3),
                        "ret": 0.0,
                        "cash": round(cash, 2),
                    })

        if today in jq_buy_targets:
            for target in jq_buy_targets[today]:
                is_scorpion_target = target["path_guess"] == "scorpion"
                explanations.append(explain_target_buy(
                    target,
                    today=today,
                    prev=prev,
                    market_mode=market_mode,
                    raw_market_mode=raw_market_mode,
                    fb_perf=fb_perf,
                    fb_pct=fb_pct,
                    active=active,
                    enable_v227=enable_v227,
                    open_hi=open_hi,
                    buy_block=buy_block,
                    held_before=held_before_scorpion if is_scorpion_target else held_before_buy,
                    slots_before=scorpion_slots_before if is_scorpion_target else slots,
                    cands=cands,
                    bear_cands=bear_cands,
                    local_yjj_buys=buys,
                    local_scorpion_buys=scorpion_buys,
                    df_prev=df_prev,
                    today_df=today_df,
                    st_today=st_today,
                ))

        sell_events = []
        if SIMULATE_V227_SELLS and held_v227:
            # Mother sells after the 09:26 buy decision; these exits must not
            # free slots for today's buy_v227_一进二 call.
            for code, pos in list(held_v227.items()):
                if pos.get("entry_date") == today or code not in daily[today].index:
                    continue
                exit_price, reason = simulate_v227_exit(code, pos, today, daily[today].loc[code], st_today)
                if exit_price is not None:
                    sell_events.append(f"{jq_code(code)} {reason} {exit_price:.2f}")
                    entry = float(pos["entry"])
                    shares = int(pos["shares"])
                    cash += sell_proceeds(exit_price, shares)
                    if SIMULATE_COOLDOWNS:
                        apply_trade_state_after_sell(
                            entry=entry,
                            exit_price=exit_price,
                            buy_mode=str(pos.get("buy_mode", "")),
                            recent_trades=recent_trades,
                            bull_state=bull_state,
                        )
                        if reason == "stop_loss":
                            ret_for_cd = exit_price / entry - 1 if entry > 0 else 0
                            if ret_for_cd <= -0.10:
                                stoploss_cooldown = 3
                            elif ret_for_cd <= -0.06:
                                stoploss_cooldown = 2
                    else:
                        recent_trades.append(1 if exit_price > entry else 0)
                    trades.append({
                        "date": today,
                        "code": jq_code(code),
                        "side": "sell",
                        "price": round(exit_price, 3),
                        "shares": shares,
                        "reason": reason,
                        "entry_date": pos.get("entry_date", ""),
                        "entry": round(entry, 3),
                        "ret": round(exit_price / entry - 1, 5) if entry > 0 else np.nan,
                        "cash": round(cash, 2),
                    })
                    del held_v227[code]

        leader_tags = []
        if ENABLE_LEADER_PROTECT and held_v227 and i >= 2:
            for code, pos in held_v227.items():
                boards = int(prev_board_counts.get(code, 0))
                if boards < 3:
                    continue
                row = daily[today].loc[code]
                hl = high_limit(float(row["pre_close"]), code, code in st_today, today)
                if float(row["close"]) >= hl * 0.999:
                    pos["leader"] = True
                    pos["leader_boards"] = boards
                    leader_tags.append(f"{jq_code(code)} {boards}B")

        if today >= BACKTEST_START:
            equity.append({
                "date": today,
                "equity": round(mark_to_market(cash, held_v227, today, daily), 2),
                "cash": round(cash, 2),
                "positions": len(held_v227),
            })

        if VERBOSE_DAILY and PRINT_START <= today <= PRINT_END:
            print(
                f"{today} mode={market_mode} fb={fb_perf*100:.2f}% fb_pct={fb_pct:.2f} "
                f"open_hi={open_hi*100:.1f}% held_at_buy={held_at_buy} block={buy_block or '-'} "
                f"slots={slots} first={len(first_boards)} base={len(base)} "
                f"v130={len(cands)} bear={len(bear_cands)} leaders={sum(1 for p in held_v227.values() if p.get('leader'))} "
                f"blast={blast} tail={tail} err={err} low_tilt={int(low_tilt)} drops={drops}"
            )
            print("  CANDS=" + "|".join(jq_code(c) for c in cands))
            if sell_events:
                print("  SELLS=" + " ; ".join(sell_events))
            if leader_tags:
                print("  LEADER_TAG=" + " ; ".join(leader_tags))
            print("  DETAIL=" + " ; ".join(detail))
            print("  BUY_TOP=" + "|".join(jq_code(c) for c in buys))
            if scorpion_detail:
                print("  SCORPION_DETAIL=" + " ; ".join(scorpion_detail))
            if scorpion_buys:
                print("  SCORPION_BUY=" + "|".join(jq_code(c) for c in scorpion_buys))

    if trades:
        pd.DataFrame(trades).to_csv(TRADES_OUT, index=False, encoding="utf-8-sig")
        print(f"WROTE {TRADES_OUT}")
    elif TRADES_OUT.exists():
        TRADES_OUT.unlink()
    if equity:
        eq = pd.DataFrame(equity)
        eq.to_csv(EQUITY_OUT, index=False, encoding="utf-8-sig")
        total_ret = eq.iloc[-1]["equity"] / INIT_CASH - 1
        sells = pd.DataFrame(trades)
        sells = sells[sells["side"] == "sell"] if not sells.empty else sells
        sell_win_rate = (sells["ret"] > 0).mean() if not sells.empty else np.nan
        print(f"WROTE {EQUITY_OUT}")
        print(f"SUMMARY days={len(eq)} trades={len(trades)} sells={len(sells)} ret={total_ret*100:.2f}% win={sell_win_rate*100:.1f}%")
    if states:
        pd.DataFrame(states).to_csv(STATE_OUT, index=False, encoding="utf-8-sig")
        print(f"WROTE {STATE_OUT}")
    if explanations:
        pd.DataFrame(explanations).to_csv(EXPLAIN_OUT, index=False, encoding="utf-8-sig")
        print(f"WROTE {EXPLAIN_OUT}")
        print(pd.Series([r["explain_reason"] for r in explanations]).value_counts().to_string())


if __name__ == "__main__":
    probe()
