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
from .compat.profiles import (
    JQ_PARITY,
    LOCAL_NATIVE_L1A,
    LOCAL_NATIVE_L1B,
    LOCAL_NATIVE_L2,
    PROFILE_DISABLED_HOOKS,
    SUPPORTED_COMPAT_PROFILES,
)
from .compat.security_metadata import BILLBOARD_ROW_FILTERS, NON_ST_NAME_WINDOWS, SECURITY_START_DATE_OVERRIDES
from .compat.strategy_state import FB_STATE_OVERRIDES, V227_SHOCK_OVERRIDES


class EmotionGateJQCompat:
    """Compatibility profile for reproducing the archived emotion-gate runs.

    Parameters
    ----------
    project_root : str or None
        Root directory for project cache paths.
    profile : str
        Compat profile name. Default 'jq_parity' preserves full JoinQuant parity.
        'local_native_l1a' disables L1A price hooks.
    """

    _HOOK_ID_MINUTE_PRICE = "market_data.minute_price_anomalies"
    _HOOK_ID_EXECUTION_PRICE = "execution.execution_price_anomalies"
    _HOOK_ID_ORDER_AMOUNT = "execution.order_amount_anomalies"
    _HOOK_ID_FILL_AMOUNT = "execution.fill_amount_anomalies"
    _HOOK_ID_PREOPEN_REJECT_CASH = "execution.preopen_reject_cash_below"
    _HOOK_ID_PREOPEN_REJECT_ORDER = "execution.preopen_reject_orders"
    _HOOK_ID_PREOPEN_DROP_DUPLICATE = "execution.preopen_drop_first_duplicate"

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

    def __init__(self, project_root=None, profile=None):
        if profile is None:
            profile = JQ_PARITY
        if profile not in SUPPORTED_COMPAT_PROFILES:
            raise ValueError(
                f"Unknown compat profile: '{profile}'. "
                f"Supported profiles: {sorted(SUPPORTED_COMPAT_PROFILES)}"
            )
        self._profile = profile
        self.project_root = os.path.abspath(
            project_root or os.path.join(os.path.dirname(__file__), "..")
        )
        self._first_seal_cache = {}
        self._board_cache = {}
        self._master_prepare_cache = {}
        self._auction_yiqian_cache = {}
        self._auction_left_api = None
        # Hook telemetry counters
        self._hook_queries: dict[str, int] = {}
        self._hook_hits: dict[str, int] = {}
        self._hook_hit_keys: list[dict] = []
        self._hook_would_have_hit_keys: list[dict] = []
        # L1B specific query ordinal counters
        self._order_query_counts = {}
        self._fill_query_counts = {}
        self._order_global_query_count = 0
        self._fill_global_query_count = 0
        self.size_hook_events = []
        # L2 order presence telemetry
        self._order_presence_query_ordinal = 0
        self._order_presence_dup_ordinal = {}
        self.order_presence_hook_events = []
        self.engine = None

    @property
    def profile(self) -> str:
        return self._profile

    @property
    def disabled_hook_ids(self) -> frozenset:
        return PROFILE_DISABLED_HOOKS.get(self._profile, frozenset())

    def is_hook_enabled(self, hook_id: str) -> bool:
        """Return True if the given hook_id is active in the current profile."""
        return hook_id not in self.disabled_hook_ids

    def profile_manifest(self) -> dict:
        """Return a stable, serialisable manifest of the current profile."""
        return {
            "profile": self._profile,
            "disabled_hook_ids": sorted(self.disabled_hook_ids),
        }

    def _record_hook_query(self, hook_id: str, hit: bool, would_have_hit: bool = False, key=None, override_value=None, key_query_ordinal=None, sequence_index=None):
        """Record hook telemetry for acceptance testing."""
        self._hook_queries[hook_id] = self._hook_queries.get(hook_id, 0) + 1
        
        # Track would-have hits
        if not hasattr(self, "_hook_would_have_hits"):
            self._hook_would_have_hits = {}
        if would_have_hit:
            self._hook_would_have_hits[hook_id] = self._hook_would_have_hits.get(hook_id, 0) + 1

        if hit:
            self._hook_hits[hook_id] = self._hook_hits.get(hook_id, 0) + 1
            
        if (hit or would_have_hit) and key is not None:
            date_str = str(key[0]) if len(key) > 0 and key[0] else ""
            time_str = str(key[1]) if len(key) > 1 and key[1] else ""
            code_str = str(key[2]) if len(key) > 2 and key[2] else ""
            side_str = str(key[3]) if len(key) > 3 and key[3] else None
            
            event = {
                "date": date_str,
                "time": time_str,
                "code": code_str,
                "side": side_str,
                "hook_id": hook_id,
                "override_value": override_value,
                "key_query_ordinal": key_query_ordinal,
                "sequence_index": sequence_index,
                "effective_hit": hit,
                "would_have_hit": would_have_hit,
            }
            
            if hit:
                self._hook_hit_keys.append(event)
            if would_have_hit and not hit:
                self._hook_would_have_hit_keys.append(event)

    def record_order_presence_event(self, hook_id, date_key, time_key, code, side,
                                     order_id, requested_amount, requested_price,
                                     available_cash, cash_threshold,
                                     duplicate_ordinal, pending_count_before, pending_count_after,
                                     raw_decision, final_decision, order_created, order_retained,
                                     effective_hit, would_have_hit):
        """Record order-presence-level telemetry for L2 hooks. Called by Engine."""
        self._order_presence_query_ordinal += 1
        request_ordinal = self._order_presence_query_ordinal
        self.order_presence_hook_events.append({
            "hook_id": hook_id,
            "profile": self._profile,
            "date": str(date_key) if date_key else "",
            "time": str(time_key) if time_key else "",
            "code": str(code) if code else "",
            "side": str(side) if side else "",
            "order_id": str(order_id) if order_id else "",
            "request_ordinal": request_ordinal,
            "requested_amount": requested_amount,
            "requested_price": requested_price,
            "available_cash": available_cash,
            "cash_threshold": cash_threshold,
            "duplicate_ordinal": duplicate_ordinal,
            "pending_count_before": pending_count_before,
            "pending_count_after": pending_count_after,
            "raw_decision": str(raw_decision) if raw_decision is not None else "",
            "final_decision": str(final_decision) if final_decision is not None else "",
            "order_created": order_created,
            "order_retained": order_retained,
            "effective_hit": effective_hit,
            "would_have_hit": would_have_hit,
        })

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
        # Always check raw table first (for would-have-hit telemetry)
        raw_override = MINUTE_PRICE_ANOMALIES.get(key, self.minute_price_anomalies.get(key))
        if not self.is_hook_enabled(self._HOOK_ID_MINUTE_PRICE):
            self._record_hook_query(
                self._HOOK_ID_MINUTE_PRICE, hit=False,
                would_have_hit=raw_override is not None,
                key=key, override_value=raw_override,
            )
            return None
        self._record_hook_query(
            self._HOOK_ID_MINUTE_PRICE, hit=raw_override is not None,
            key=key, override_value=raw_override,
        )
        return raw_override

    def get_daily_ipo_close_override(self, security, date_int):
        key = (security, date_int)
        return DAILY_IPO_CLOSE_ANOMALIES.get(key)

    def get_daily_field_override(self, security, date_int, field):
        key = (security, date_int, field)
        return DAILY_FIELD_ANOMALIES.get(key, self.daily_price_anomalies.get(key))

    def get_execution_price_override(self, date_key, time_key, security, side):
        key = (date_key, time_key, security, side)
        # Always check raw table first (for would-have-hit telemetry)
        raw_override = EXECUTION_PRICE_ANOMALIES.get(key, self.execution_price_anomalies.get(key))
        if not self.is_hook_enabled(self._HOOK_ID_EXECUTION_PRICE):
            self._record_hook_query(
                self._HOOK_ID_EXECUTION_PRICE, hit=False,
                would_have_hit=raw_override is not None,
                key=key, override_value=raw_override,
            )
            return None
        self._record_hook_query(
            self._HOOK_ID_EXECUTION_PRICE, hit=raw_override is not None,
            key=key, override_value=raw_override,
        )
        return raw_override

    def get_order_amount_override(self, date_key, time_key, security, amount=None):
        key = (date_key, time_key, security)
        self._order_global_query_count += 1
        query_ord = self._order_global_query_count
        
        # Track query count per key
        key_ord = self._order_query_counts.get(key, 0) + 1
        self._order_query_counts[key] = key_ord
        
        raw_override = ORDER_AMOUNT_ANOMALIES.get(key)
        
        # Resolve specific override value for this query ordinal
        override_val = None
        seq_idx = 0
        has_cand = False
        if raw_override is not None:
            if isinstance(raw_override, list):
                seq_idx = key_ord - 1
                if seq_idx < len(raw_override):
                    override_val = raw_override[seq_idx]
                    has_cand = True
            else:
                seq_idx = 0
                if key_ord == 1:
                    override_val = raw_override
                    has_cand = True
                    
        enabled = self.is_hook_enabled(self._HOOK_ID_ORDER_AMOUNT)
        hit = enabled and has_cand
        would_have = (not enabled) and has_cand
        
        # Record hook query telemetry
        self._record_hook_query(
            self._HOOK_ID_ORDER_AMOUNT,
            hit=hit,
            would_have_hit=would_have,
            key=key,
            override_value=override_val,
            key_query_ordinal=key_ord,
            sequence_index=seq_idx
        )
        
        # Record detailed size hook event for SIZE_HOOK_EVENTS.csv
        final_amt = override_val if hit else amount
        
        order_id = str(self.engine._order_id_counter) if (self.engine is not None) else ""
        side = "buy" if (amount is not None and amount > 0) else "sell"
        
        self.size_hook_events.append({
            "hook_id": self._HOOK_ID_ORDER_AMOUNT,
            "date": date_key,
            "time": time_key,
            "code": security,
            "side": side,
            "order_id": order_id,
            "query_ordinal": query_ord,
            "key_query_ordinal": key_ord,
            "sequence_index": seq_idx,
            "computed_amount_before_override": amount,
            "override_amount": override_val,
            "final_order_amount": final_amt,
            "final_fill_amount": None,
            "profile": self.profile,
            "effective_hit": hit,
            "would_have_hit": would_have,
        })
        
        return raw_override if enabled else None

    def get_fill_amount_override(self, date_key, time_key, security, amount=None):
        key = (date_key, time_key, security)
        self._fill_global_query_count += 1
        query_ord = self._fill_global_query_count
        
        # Track query count per key
        key_ord = self._fill_query_counts.get(key, 0) + 1
        self._fill_query_counts[key] = key_ord
        
        raw_override = FILL_AMOUNT_ANOMALIES.get(key)
        
        # Resolve specific override value for this query ordinal
        override_val = None
        seq_idx = 0
        has_cand = False
        if raw_override is not None:
            if isinstance(raw_override, list):
                seq_idx = key_ord - 1
                if seq_idx < len(raw_override):
                    override_val = raw_override[seq_idx]
                    has_cand = True
            else:
                seq_idx = 0
                if key_ord == 1:
                    override_val = raw_override
                    has_cand = True
                    
        enabled = self.is_hook_enabled(self._HOOK_ID_FILL_AMOUNT)
        hit = enabled and has_cand
        would_have = (not enabled) and has_cand
        
        # Record hook query telemetry
        self._record_hook_query(
            self._HOOK_ID_FILL_AMOUNT,
            hit=hit,
            would_have_hit=would_have,
            key=key,
            override_value=override_val,
            key_query_ordinal=key_ord,
            sequence_index=seq_idx
        )
        
        # Record detailed size hook event for SIZE_HOOK_EVENTS.csv
        final_amt = override_val if hit else amount
        
        order_id = ""
        side = "buy" if (amount is not None and amount > 0) else "sell"
        if self.engine is not None and getattr(self.engine, "_current_matching_order", None) is not None:
            order_id = getattr(self.engine._current_matching_order, "order_id", "")
            side = getattr(self.engine._current_matching_order, "side", side)
            
        self.size_hook_events.append({
            "hook_id": self._HOOK_ID_FILL_AMOUNT,
            "date": date_key,
            "time": time_key,
            "code": security,
            "side": side,
            "order_id": order_id,
            "query_ordinal": query_ord,
            "key_query_ordinal": key_ord,
            "sequence_index": seq_idx,
            "computed_amount_before_override": amount,
            "override_amount": override_val,
            "final_order_amount": None,
            "final_fill_amount": final_amt,
            "profile": self.profile,
            "effective_hit": hit,
            "would_have_hit": would_have,
        })
        
        return raw_override if enabled else None

    def should_reject_preopen_cash(self, date_key, time_key, available_cash):
        """Check if pre-open order should be rejected due to cash below threshold.

        With gating for L2 ablation. Engine records telemetry after actual decision.
        """
        cash_threshold = self.preopen_reject_cash_below.get((date_key, time_key))
        raw_reject = cash_threshold is not None and available_cash < cash_threshold

        enabled = self.is_hook_enabled(self._HOOK_ID_PREOPEN_REJECT_CASH)
        final_reject = raw_reject if enabled else False

        # Record query + hit telemetry
        self._hook_queries[self._HOOK_ID_PREOPEN_REJECT_CASH] = \
            self._hook_queries.get(self._HOOK_ID_PREOPEN_REJECT_CASH, 0) + 1

        if raw_reject:
            if enabled:
                self._hook_hits[self._HOOK_ID_PREOPEN_REJECT_CASH] = \
                    self._hook_hits.get(self._HOOK_ID_PREOPEN_REJECT_CASH, 0) + 1
            else:
                if not hasattr(self, "_hook_would_have_hits"):
                    self._hook_would_have_hits = {}
                self._hook_would_have_hits[self._HOOK_ID_PREOPEN_REJECT_CASH] = \
                    self._hook_would_have_hits.get(self._HOOK_ID_PREOPEN_REJECT_CASH, 0) + 1

        return final_reject, cash_threshold

    def should_reject_preopen_order(self, date_key, security):
        """Check if a pre-open order should be explicitly rejected.

        With gating for L2 ablation. Engine records telemetry after actual decision.
        """
        raw_reject = (date_key, security) in self.preopen_reject_orders
        enabled = self.is_hook_enabled(self._HOOK_ID_PREOPEN_REJECT_ORDER)
        final_reject = raw_reject if enabled else False

        self._hook_queries[self._HOOK_ID_PREOPEN_REJECT_ORDER] = \
            self._hook_queries.get(self._HOOK_ID_PREOPEN_REJECT_ORDER, 0) + 1

        if raw_reject:
            if enabled:
                self._hook_hits[self._HOOK_ID_PREOPEN_REJECT_ORDER] = \
                    self._hook_hits.get(self._HOOK_ID_PREOPEN_REJECT_ORDER, 0) + 1
            else:
                if not hasattr(self, "_hook_would_have_hits"):
                    self._hook_would_have_hits = {}
                self._hook_would_have_hits[self._HOOK_ID_PREOPEN_REJECT_ORDER] = \
                    self._hook_would_have_hits.get(self._HOOK_ID_PREOPEN_REJECT_ORDER, 0) + 1

        return final_reject

    def should_drop_first_preopen_duplicate(self, date_key, security):
        """Check if the first pre-open duplicate order should be dropped.

        With gating for L2 ablation. Engine records telemetry after actual decision.
        The "first duplicate" state is maintained by the engine"s _pending_orders list,
        not by this compat layer. This method only answers the yes/no question.
        """
        raw_drop = (date_key, security) in self.preopen_drop_first_duplicate
        enabled = self.is_hook_enabled(self._HOOK_ID_PREOPEN_DROP_DUPLICATE)
        final_drop = raw_drop if enabled else False

        self._hook_queries[self._HOOK_ID_PREOPEN_DROP_DUPLICATE] = \
            self._hook_queries.get(self._HOOK_ID_PREOPEN_DROP_DUPLICATE, 0) + 1

        if raw_drop:
            if enabled:
                self._hook_hits[self._HOOK_ID_PREOPEN_DROP_DUPLICATE] = \
                    self._hook_hits.get(self._HOOK_ID_PREOPEN_DROP_DUPLICATE, 0) + 1
            else:
                if not hasattr(self, "_hook_would_have_hits"):
                    self._hook_would_have_hits = {}
                self._hook_would_have_hits[self._HOOK_ID_PREOPEN_DROP_DUPLICATE] = \
                    self._hook_would_have_hits.get(self._HOOK_ID_PREOPEN_DROP_DUPLICATE, 0) + 1

        return final_drop

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




















