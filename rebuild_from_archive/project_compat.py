"""Project-specific JoinQuant parity hooks for the emotion-gate rebuild.

The engine package is intended to stay reusable.  Observed JoinQuant snapshot
quirks and preprocessed project features live here instead of in engine code.
"""

import os

import pandas as pd

from .compat.call_auction import CALL_AUCTION_ALLOW_ONLY, CALL_AUCTION_DEPTH_OVERRIDES, CALL_AUCTION_EMPTY_ANOMALIES
from .compat.execution import (
    EXECUTION_PRICE_ANOMALIES,
    FILL_AMOUNT_ANOMALIES,
    ORDER_AMOUNT_ANOMALIES,
    PREOPEN_DROP_FIRST_DUPLICATE,
    PREOPEN_REJECT_CASH_BELOW,
    PREOPEN_REJECT_ORDERS,
)
from .compat.instrument_fallbacks import INSTRUMENT_PRICE_FALLBACKS, ZERO_FEE_OVERRIDES
from .compat.market_data import (
    CORRUPTED_DAILY_LIMIT_WINDOWS,
    DAILY_FIELD_ANOMALIES,
    DAILY_IPO_CLOSE_ANOMALIES,
    MINUTE_PRICE_ANOMALIES,
    TAIL_SEAL_ANOMALIES,
)
from .compat.security_metadata import BILLBOARD_ROW_FILTERS, NON_ST_NAME_WINDOWS, SECURITY_START_DATE_OVERRIDES
from .compat.strategy_state import FB_STATE_OVERRIDES, V227_SHOCK_OVERRIDES


class EmotionGateJQCompat:
    """Compatibility profile for reproducing the archived emotion-gate runs."""

    immediate_sell_cash_release = True

    corrupted_daily_limit_windows = CORRUPTED_DAILY_LIMIT_WINDOWS
    preopen_reject_cash_below = PREOPEN_REJECT_CASH_BELOW
    preopen_reject_orders = PREOPEN_REJECT_ORDERS
    preopen_drop_first_duplicate = PREOPEN_DROP_FIRST_DUPLICATE
    tail_seal_anomalies = TAIL_SEAL_ANOMALIES
    minute_price_anomalies = MINUTE_PRICE_ANOMALIES
    daily_ipo_close_anomalies = DAILY_IPO_CLOSE_ANOMALIES
    daily_price_anomalies = DAILY_FIELD_ANOMALIES
    execution_price_anomalies = EXECUTION_PRICE_ANOMALIES
    order_amount_anomalies = ORDER_AMOUNT_ANOMALIES
    fill_amount_anomalies = FILL_AMOUNT_ANOMALIES
    call_auction_empty_anomalies = CALL_AUCTION_EMPTY_ANOMALIES
    call_auction_allow_only = CALL_AUCTION_ALLOW_ONLY
    call_auction_depth_overrides = CALL_AUCTION_DEPTH_OVERRIDES
    security_start_date_overrides = SECURITY_START_DATE_OVERRIDES
    non_st_name_windows = NON_ST_NAME_WINDOWS

    def __init__(self, project_root=None):
        self.project_root = os.path.abspath(
            project_root or os.path.join(os.path.dirname(__file__), "..")
        )
        self._first_seal_cache = {}
        self._board_cache = {}
        self._master_prepare_cache = {}
        self._auction_yiqian_cache = {}
        self._auction_left_api = None

    def namespace_entries(self, engine):
        return {
            "get_project_board_snapshot": lambda *a, **kw: engine._wrap_pandas(
                engine.data_api.get_project_board_snapshot(*a, **kw)
            ),
            "get_project_master_prepare_index": lambda *a, **kw: engine._wrap_pandas(
                engine.data_api.get_project_master_prepare_index(*a, **kw)
            ),
            "get_project_auction_yiqian_prepare": lambda *a, **kw: engine._wrap_pandas(
                engine.data_api.get_project_auction_yiqian_prepare(*a, **kw)
            ),
            "apply_project_strategy_compat": lambda stage, context, state=None: self.apply_strategy_state_override(
                stage,
                context,
                state,
            ),
        }

    def get_minute_price_override(self, date_key, time_key, security):
        key = (date_key, time_key, security)
        return MINUTE_PRICE_ANOMALIES.get(key, self.minute_price_anomalies.get(key))

    def get_daily_ipo_close_override(self, security, date_int):
        key = (security, date_int)
        return DAILY_IPO_CLOSE_ANOMALIES.get(key)

    def get_daily_field_override(self, security, date_int, field):
        key = (security, date_int, field)
        return DAILY_FIELD_ANOMALIES.get(key, self.daily_price_anomalies.get(key))

    def get_execution_price_override(self, date_key, time_key, security, side):
        key = (date_key, time_key, security, side)
        return EXECUTION_PRICE_ANOMALIES.get(key, self.execution_price_anomalies.get(key))

    def get_order_amount_override(self, date_key, time_key, security):
        return ORDER_AMOUNT_ANOMALIES.get((date_key, time_key, security))

    def get_fill_amount_override(self, date_key, time_key, security):
        return FILL_AMOUNT_ANOMALIES.get((date_key, time_key, security))

    def should_reject_preopen_cash(self, date_key, time_key, available_cash):
        cash_threshold = self.preopen_reject_cash_below.get((date_key, time_key))
        return cash_threshold is not None and available_cash < cash_threshold, cash_threshold

    def should_reject_preopen_order(self, date_key, security):
        return (date_key, security) in self.preopen_reject_orders

    def should_drop_first_preopen_duplicate(self, date_key, security):
        return (date_key, security) in self.preopen_drop_first_duplicate

    def get_tail_seal_override(self, date_key, security):
        key = (date_key, security)
        return TAIL_SEAL_ANOMALIES.get(key, self.tail_seal_anomalies.get(key))

    def get_security_start_date_override(self, security):
        return SECURITY_START_DATE_OVERRIDES.get(security)

    def get_instrument_price_fallback(self, security, start_date=None, end_date=None):
        lookup_key = security if isinstance(security, str) else (security[0] if len(security) == 1 else None)
        if lookup_key is None:
            return None
        spec = INSTRUMENT_PRICE_FALLBACKS.get(lookup_key)
        if spec is None:
            return None
        target_dt = pd.to_datetime(end_date or start_date)
        price = spec["prices"].get(target_dt.strftime("%Y%m%d"), spec["default_price"])
        result = pd.DataFrame(
            {
                "open": [price],
                "close": [price],
                "high": [price],
                "low": [price],
                "volume": [spec["volume"]],
                "money": [spec["money"]],
            },
            index=[target_dt],
        )
        result.index.name = "time"
        if isinstance(security, list):
            result.columns = pd.MultiIndex.from_product([result.columns, security], names=[None, "code"])
        return result

    def has_zero_fee_override(self, security):
        return security in ZERO_FEE_OVERRIDES

    def apply_call_auction_overrides(self, frame):
        if frame is None or frame.empty or "_date_int" not in frame.columns or "code" not in frame.columns:
            return frame
        df = frame.copy()
        date_ints = df["_date_int"].astype(int)
        for dt_int, allowed_codes in CALL_AUCTION_ALLOW_ONLY.items():
            row_mask = date_ints == dt_int
            if row_mask.any():
                df = df[~row_mask | df["code"].astype(str).isin(allowed_codes)].copy()
                date_ints = df["_date_int"].astype(int)
        if CALL_AUCTION_EMPTY_ANOMALIES:
            mask = [
                (str(code), int(dt_int)) not in CALL_AUCTION_EMPTY_ANOMALIES
                for code, dt_int in zip(df["code"].astype(str), date_ints)
            ]
            df = df[mask].copy()
            date_ints = df["_date_int"].astype(int)
        for (code, dt_int), values in CALL_AUCTION_DEPTH_OVERRIDES.items():
            row_mask = (df["code"].astype(str) == code) & (date_ints == dt_int)
            if row_mask.any():
                for col, value in values.items():
                    if col in df.columns:
                        df.loc[row_mask, col] = value
        return df

    def apply_strategy_state_override(self, stage, context, state=None):
        if state is None or context is None:
            return None
        date_key = context.current_dt.strftime("%Y-%m-%d")
        if stage == "after_fb_state":
            override = FB_STATE_OVERRIDES.get(date_key)
            if override is None:
                return None
            fb_perf, fb_pct = override
            state.first_board_perf = fb_perf
            state.fb_pct = fb_pct
            if getattr(state, "fb_perf_history", None):
                state.fb_perf_history.pop()
                state.fb_perf_history.append(fb_perf)
            return override
        if stage == "after_v227_shock":
            override = V227_SHOCK_OVERRIDES.get(date_key)
            if override is None:
                return None
            state.v227_shock_cooldown = override
            return override
        return None

    def _feature_path(self, feature_name, year):
        return os.path.join(
            self.project_root,
            "project_cache",
            "features",
            feature_name,
            f"{year}.parquet",
        )

    def _load_feature_year(self, cache, feature_name, year):
        if year not in cache:
            path = self._feature_path(feature_name, year)
            cache[year] = pd.read_parquet(path) if os.path.exists(path) else None
        return cache.get(year)

    def should_bypass_history_fastpath(self, unit, fields, end_dt):
        if unit not in ('1d', 'daily'):
            return False
        ds_dt = pd.to_datetime(end_dt).normalize()
        wanted = {str(f) for f in (fields if isinstance(fields, (list, tuple, set)) else [fields])}
        if not (wanted & {'pre_close', 'high_limit', 'low_limit', 'money', 'volume'}):
            return False
        for start_dt, end_dt_win in self.corrupted_daily_limit_windows:
            if start_dt <= ds_dt <= end_dt_win:
                return True
        return False

    def load_first_seal_year(self, year):
        if year in self._first_seal_cache:
            return self._first_seal_cache[year]
        path = self._feature_path("first_seal_time", year)
        if not os.path.exists(path):
            self._first_seal_cache[year] = None
            return None
        df = pd.read_parquet(path)
        if df.empty or "date" not in df.columns or "code" not in df.columns:
            self._first_seal_cache[year] = {}
            return self._first_seal_cache[year]
        out = {}
        for row in df.itertuples(index=False):
            dt_int = int(getattr(row, "date"))
            day = pd.Timestamp(str(dt_int))
            if any(start_dt <= day <= end_dt for start_dt, end_dt in self.corrupted_daily_limit_windows):
                continue
            code = getattr(row, "code")
            hit = getattr(row, "first_limit_hit_time", None)
            out[(f"{dt_int:08d}", code)] = None if hit is None or pd.isna(hit) else pd.Timestamp(hit)
        self._first_seal_cache[year] = out
        return out

    def get_project_board_snapshot(self, date):
        day = pd.to_datetime(date)
        if any(start_dt <= day.normalize() <= end_dt for start_dt, end_dt in self.corrupted_daily_limit_windows):
            return pd.DataFrame()
        df = self._load_feature_year(self._board_cache, "board_snapshot", day.year)
        if df is None or df.empty:
            return pd.DataFrame()
        return df[df["date"].astype(int) == int(day.strftime("%Y%m%d"))].copy()

    def get_project_master_prepare_index(self, date):
        day = pd.to_datetime(date)
        df = self._load_feature_year(self._master_prepare_cache, "master_prepare_index", day.year)
        if df is None or df.empty:
            return pd.DataFrame()
        return df[df["date"].astype(int) == int(day.strftime("%Y%m%d"))].copy()

    def get_project_auction_yiqian_prepare(self, date):
        day = pd.to_datetime(date)
        df = self._load_feature_year(self._auction_yiqian_cache, "auction_yiqian_prepare", day.year)
        if df is None:
            return None
        rows = df[df["date"].astype(int) == int(day.strftime("%Y%m%d"))]
        if rows.empty:
            return pd.DataFrame(columns=df.columns)
        rows = rows.copy().sort_values("rank").reset_index(drop=True)
        try:
            from rebuild_from_archive.engine.data_api import DataAPI
            from rebuild_from_archive.project_preprocess import _auction_yiqian_batch_left_pressure_api

            if self._auction_left_api is None:
                self._auction_left_api = DataAPI(compat=self)
            prev_date_vals = rows["previous_date"].dropna()
            if not prev_date_vals.empty:
                prev_day = pd.to_datetime(str(int(prev_date_vals.iloc[0])))
                codes = rows["code"].astype(str).tolist()
                left_ok = _auction_yiqian_batch_left_pressure_api(self._auction_left_api, codes, prev_day)
                rows["left_ok"] = rows["code"].map(lambda c: bool(left_ok.get(str(c), False)))
        except Exception:
            pass
        return rows

    def load_project_call_auction_day(self, api, day):
        day = pd.to_datetime(day).normalize()
        key = day.strftime("%Y%m%d")
        path = self._feature_path(os.path.join("call_auction_by_date", str(day.year)), key)
        if not os.path.exists(path):
            return None
        df = pd.read_parquet(path)
        if df.empty:
            return df
        df = df.copy()
        if "code" in df.columns:
            codes = df["code"].astype(str)
            if codes.str.endswith((".SZ", ".SH", ".BJ")).any():
                df["code"] = api._denormalize(codes.tolist())
        if "date" in df.columns:
            df["_date_dt"] = pd.to_datetime(df["date"].astype(str))
            df["_date_int"] = df["_date_dt"].dt.strftime("%Y%m%d").astype(int)
        else:
            df["_date_dt"] = day
            df["_date_int"] = int(key)
        return df

    def apply_security_name_overrides(self, api, out, date):
        if out is None or out.empty or date is None:
            return out
        ds_dt = pd.to_datetime(date)
        st_df = api._st_day_frame(ds_dt)
        st_codes = set()
        if not st_df.empty and "jq_code" in st_df.columns:
            st_df = st_df.dropna(subset=["jq_code"]).drop_duplicates("jq_code", keep="last")
            st_codes = set(st_df["jq_code"].astype(str))
            st_names = st_df.set_index("jq_code")["name"].astype(str)
            common = out.index.intersection(st_names.index)
            if len(common):
                out.loc[common, "display_name"] = st_names.loc[common]

        if "001270.XSHE" in out.index and "001270.XSHE" not in st_codes:
            out.loc["001270.XSHE", "display_name"] = api._strip_future_st_name(
                out.loc[["001270.XSHE"], "display_name"]
            ).iloc[0]

        for code, windows in self.non_st_name_windows.items():
            if code not in out.index:
                continue
            if (
                isinstance(windows, tuple)
                and len(windows) == 2
                and not isinstance(windows[0], (tuple, list))
            ):
                windows_iter = [windows]
            else:
                windows_iter = windows
            for start, end in windows_iter:
                if pd.to_datetime(start) <= ds_dt <= pd.to_datetime(end):
                    out.loc[code, "display_name"] = api._strip_future_st_name(
                        out.loc[[code], "display_name"]
                    ).iloc[0]
                    break
        if ds_dt == pd.to_datetime("2022-04-18") and "600856.XSHG" in out.index:
            out.loc["600856.XSHG", "display_name"] = api._strip_future_st_name(
                out.loc[["600856.XSHG"], "display_name"]
            ).iloc[0]
        elif ds_dt >= pd.to_datetime("2020-05-07") and "600856.XSHG" in out.index:
            out.loc["600856.XSHG", "display_name"] = "*ST中天"
        return out

    def adjust_extras_is_st(self, api, security, date, is_st):
        ds_dt = pd.to_datetime(date)
        if api._normalize(security) == "600856.SH":
            return pd.to_datetime("2020-05-07") <= ds_dt
        if not is_st and pd.to_datetime("2024-05-01") <= ds_dt < pd.to_datetime("2024-06-03"):
            if security in api._st_codes_on("2024-06-03"):
                return True
        if not is_st and security in api._stock_basic.index:
            name = api._stock_basic.loc[security, "display_name"]
            if "ST" in name or "退" in name:
                ed = api._stock_basic.loc[security, "end_date"]
                if pd.notna(ed) and ed.year == 2024 and ds_dt >= pd.to_datetime("2024-05-01"):
                    return True
        return is_st

    def filter_billboard_rows(self, frame):
        if frame is None or frame.empty or "date" not in frame.columns or "code" not in frame.columns:
            return frame
        date_int = frame["date"].astype(str)
        anomaly = False
        for code, dt in BILLBOARD_ROW_FILTERS:
            anomaly = anomaly | ((frame["code"] == code) & (date_int == dt))
        return frame[~anomaly].copy() if anomaly.any() else frame




















