import pandas as pd
import os
import numpy as np
from datetime import datetime
import sys

try:
    from scripts.core import hdata_reader
except Exception:
    hdata_scripts = os.path.join(os.environ.get('LOCALQUANT_HDATA_ROOT', r"D:\work space\hdata"), "scripts")
    if hdata_scripts not in sys.path:
        sys.path.insert(0, hdata_scripts)
    from core import hdata_reader

class JQMockResult:
    def __init__(self, data_dict): self.data = data_dict
    def __getitem__(self, key):
        val = self.data.get(key, False)
        return type('MockSeries', (), {'__getitem__': lambda s, idx: val})()

class SecurityInfo:
    """模拟聚宽 get_security_info 返回的对象"""
    def __init__(self, code, name, display_name, start_date, end_date, type='stock'):
        self.code = code
        self.name = name
        self.display_name = display_name
        self.type = type
        self.start_date = start_date
        self.end_date = end_date
        self.delist_date = end_date
    def __repr__(self):
        return f"SecurityInfo({self.code}, '{self.display_name}')"


class DataAPI:
    def __init__(self, data_root=None, compat=None):
        if data_root is None:
            data_root = os.environ.get('LOCALQUANT_DATA_ROOT', "D:/work space/hdata/data/processed")
        if not os.path.exists(os.path.join(data_root, '1d_stock')):
            processed_root = os.path.join(data_root, 'data/processed')
            if os.path.exists(os.path.join(processed_root, '1d_stock')):
                data_root = processed_root
        self.data_root = data_root
        self.compat = compat
        self._stock_basic = None
        self._st_history = None
        self._price_records = {}
        self._indicator_cache = {}
        self._income_cache = None
        self._all_trade_days = None
        self._minute_cache = {}
        self._sealing_points_cache = {}
        self._call_auction_cache = {}
        self._call_auction_day_cache = {}
        self._call_auction_query_cache = {}
        self._history_cache = {}
        self._st_day_cache = {}
        self._st_year_cache = {}
        self._all_securities_cache = {}

    def _st_day_frame(self, date):
        ds = pd.to_datetime(date).strftime('%Y%m%d')
        cached = self._st_day_cache.get(ds)
        if cached is not None:
            return cached
        year = ds[:4]
        if year not in self._st_year_cache:
            path = os.path.join(self.data_root, f'1d_feature/st_list/{year}.parquet')
            try:
                year_df = pd.read_parquet(path) if os.path.exists(path) else pd.DataFrame()
            except Exception:
                year_df = pd.DataFrame()
            if not year_df.empty and 'date' in year_df.columns:
                year_df = year_df.copy()
                year_df['date'] = year_df['date'].astype(str)
            self._st_year_cache[year] = year_df
        year_df = self._st_year_cache.get(year, pd.DataFrame())
        if not year_df.empty and 'date' in year_df.columns:
            df = year_df[year_df['date'] == ds].copy()
        else:
            try:
                df = hdata_reader.load_1d_feature(name='st_list', start=ds, end=ds)
            except Exception:
                df = pd.DataFrame()
        if df is None:
            df = pd.DataFrame()
        df = df.copy()
        if not df.empty and 'code' in df.columns:
            df['jq_code'] = self._denormalize(df['code'].astype(str).tolist())
        self._st_day_cache[ds] = df
        return df

    def _st_codes_on(self, date):
        df = self._st_day_frame(date)
        if df.empty or 'jq_code' not in df.columns:
            return set()
        return set(df['jq_code'].dropna().astype(str))

    def _strip_future_st_name(self, names):
        cleaned = names.astype(str)
        cleaned = cleaned.str.replace(r'^\s*\*?ST', '', regex=True)
        cleaned = cleaned.str.replace(r'^\s*SST', '', regex=True)
        return cleaned

    def _apply_jq_security_name_overrides(self, out, date):
        if self.compat is not None and hasattr(self.compat, "apply_security_name_overrides"):
            return self.compat.apply_security_name_overrides(self, out, date)
        return out

    def _history_cached(self, count, unit, field, security_list, df=True, fq=None,
                        start_date=None, end_date=None):
        securities = tuple(security_list if isinstance(security_list, (list, tuple, pd.Index, pd.Series)) else [security_list])
        field_key = tuple(field) if isinstance(field, (list, tuple, pd.Index, pd.Series)) else field
        start_key = None if start_date is None else str(pd.to_datetime(start_date))
        end_key = None if end_date is None else str(pd.to_datetime(end_date))
        key = (int(count or 1), unit, field_key, securities, bool(df), fq, start_key, end_key)
        cached = self._history_cache.get(key)
        if cached is not None:
            return cached.copy() if hasattr(cached, 'copy') else cached
        result = hdata_reader.history(
            count=count,
            unit=unit,
            field=field,
            security_list=list(securities),
            df=df,
            fq=fq,
            start_date=start_date,
            end_date=end_date,
        )
        if len(self._history_cache) > 4096:
            self._history_cache.pop(next(iter(self._history_cache)))
        self._history_cache[key] = result.copy() if hasattr(result, 'copy') else result
        return result.copy() if hasattr(result, 'copy') else result

    def _normalize(self, code):
        if isinstance(code, (list, pd.Index, pd.Series)): return [self._normalize(c) for c in code]
        return code.replace('.XSHE', '.SZ').replace('.XSHG', '.SH') if isinstance(code, str) else code

    def _denormalize(self, code):
        if isinstance(code, (list, pd.Index, pd.Series)): return [self._denormalize(c) for c in code]
        return code.replace('.SZ', '.XSHE').replace('.SH', '.XSHG') if isinstance(code, str) else code

    def _should_bypass_history_fastpath(self, unit, fields, end_dt):
        if unit not in ('1d', 'daily'):
            return False
        compat = self.compat
        if compat is not None and hasattr(compat, 'should_bypass_history_fastpath'):
            try:
                return bool(compat.should_bypass_history_fastpath(unit, fields, end_dt))
            except Exception:
                return False
        return False

    def _apply_jq_daily_anomalies(self, frame, field, securities, end_dt):
        """Patch documented JQ daily-history quirks without mutating hdata."""
        if frame is None or frame.empty or field not in ('open', 'close', 'high', 'high_limit', 'low_limit', 'pre_close', 'money'):
            return frame
        try:
            end_int = int(pd.to_datetime(end_dt).strftime('%Y%m%d'))
        except Exception:
            return frame

        out = frame.copy()
        sec_list = [securities] if isinstance(securities, str) else list(securities)
        for sec in sec_list:
            point_value = (
                self.compat.get_daily_field_override(sec, end_int, field)
                if self.compat is not None and hasattr(self.compat, "get_daily_field_override")
                else None
            )
            if point_value is not None:
                if sec in out.columns:
                    col = sec
                elif len(sec_list) == 1 and field in out.columns:
                    col = field
                else:
                    col = None
                if col is not None and len(out.index) >= 1:
                    out.iloc[-1, out.columns.get_loc(col)] = point_value
            ipo_value = (
                self.compat.get_daily_ipo_close_override(sec, end_int)
                if self.compat is not None and hasattr(self.compat, "get_daily_ipo_close_override")
                else None
            )
            if ipo_value is None or len(out.index) < 2:
                continue
            if sec in out.columns:
                col = sec
            elif len(sec_list) == 1 and field in out.columns:
                col = field
            else:
                continue
            if field == 'close':
                out.iloc[-2, out.columns.get_loc(col)] = ipo_value
                out.iloc[-1, out.columns.get_loc(col)] = np.nan
            elif field in ('high_limit', 'low_limit', 'pre_close'):
                out.iloc[-2, out.columns.get_loc(col)] = ipo_value
                out.iloc[-1, out.columns.get_loc(col)] = np.nan
        return out

    def _apply_jq_daily_anomalies_records(self, frame, fields, securities, end_dt):
        """Same JQ daily quirks as _apply_jq_daily_anomalies, for long-form rows."""
        if frame is None or frame.empty:
            return frame
        wanted = set(fields or [])
        patch_fields = wanted & {'open', 'close', 'high', 'high_limit', 'low_limit', 'pre_close', 'money'}
        if not patch_fields:
            return frame
        try:
            end_int = int(pd.to_datetime(end_dt).strftime('%Y%m%d'))
        except Exception:
            return frame

        out = frame.copy()
        sec_list = [securities] if isinstance(securities, str) else list(securities)
        for sec in sec_list:
            sec_rows = out.index[out['code'] == sec].tolist()
            if not sec_rows:
                continue
            for field in patch_fields:
                point_value = (
                    self.compat.get_daily_field_override(sec, end_int, field)
                    if self.compat is not None and hasattr(self.compat, "get_daily_field_override")
                    else None
                )
                if point_value is not None and field in out.columns:
                    out.loc[sec_rows[-1], field] = point_value
                ipo_value = (
                    self.compat.get_daily_ipo_close_override(sec, end_int)
                    if self.compat is not None and hasattr(self.compat, "get_daily_ipo_close_override")
                    else None
                )
                if ipo_value is None or len(sec_rows) < 2 or field not in out.columns:
                    continue
                if field == 'close':
                    out.loc[sec_rows[-2], field] = ipo_value
                    out.loc[sec_rows[-1], field] = np.nan
                elif field in ('high_limit', 'low_limit', 'pre_close'):
                    out.loc[sec_rows[-2], field] = ipo_value
                    out.loc[sec_rows[-1], field] = np.nan
        return out

    def _get_price_raw(self, security, start_date=None, end_date=None, frequency='daily', fields=None, fq=None, count=None, **kwargs):
        return self.get_price(
            security,
            start_date=start_date,
            end_date=end_date,
            frequency=frequency,
            fields=fields,
            fq=fq,
            count=count,
        )

    def get_order_reference_price(self, security, current_dt, phase='pre_open', fq=None):
        dt = pd.to_datetime(current_dt)
        if phase == 'pre_open':
            trade_days = self.get_trade_days(dt - pd.Timedelta(days=30), dt)
            prev_days = [d for d in trade_days if d.date() < dt.date()]
            ref_dt = prev_days[-1] if prev_days else dt
            field = 'close'
        else:
            ref_dt = dt
            field = 'open'
        df = self.get_price(
            security,
            end_date=ref_dt,
            frequency='daily',
            fields=[field],
            fq=fq,
            count=1,
        )
        if df.empty or field not in df.columns:
            return 0.0
        try:
            val = float(df[field].iloc[-1])
            return val if np.isfinite(val) else 0.0
        except Exception:
            return 0.0

    # ------------------------------------------------------------------
    # get_bars — 聚宽最常用的行情 API
    # 签名: get_bars(security, count, unit='1d', fields=['close','high','low','open','volume'],
    #                include_now=False, df=True, fq_ref_date=None, end_dt=None)
    # end_dt 由引擎注入（当前回测时间），策略代码不传此参数
    # ------------------------------------------------------------------
    def get_bars(self, security, count, unit='1d', fields=None, include_now=False, df=True, fq_ref_date=None, end_dt=None):
        if fields is None:
            fields = ['close', 'high', 'low', 'open', 'volume']
        
        is_single = isinstance(security, str)
        securities = [security] if is_single else list(security)
        
        freq_map = {
            '1d': 'daily', 'd': 'daily', 'daily': 'daily',
            '1m': '1m', 'm': '1m', 'minute': '1m',
            '5m': '5m', '15m': '15m', '30m': '30m', '60m': '60m',
        }
        frequency = freq_map.get(unit, 'daily')
        
        field_map = {
            'open': 'open', 'close': 'close', 'high': 'high', 'low': 'low',
            'volume': 'volume', 'money': 'money',
            'high_limit': 'high_limit', 'low_limit': 'low_limit',
            'paused': 'paused', 'pre_close': 'pre_close',
        }
        mapped_fields = []
        for f in fields:
            mf = field_map.get(f, f)
            if mf not in mapped_fields:
                mapped_fields.append(mf)
        
        if end_dt is None:
            end_dt = datetime.now()
        
        if frequency == 'daily':
            # 单标的传字符串, 多标的传列表 — 这样 get_price 返回的格式不同
            price_arg = security if is_single else securities
            df_data = self.get_price(
                price_arg,
                end_date=end_dt,
                frequency='daily',
                fields=mapped_fields,
                count=count
            )
        elif frequency == '1m':
            price_arg = security if is_single else securities
            df_data = self.get_price(
                price_arg,
                end_date=end_dt,
                frequency='1m',
                fields=mapped_fields,
                count=count
            )
        else:
            df_data = pd.DataFrame()
        
        if df_data.empty:
            return pd.DataFrame()
        
        if is_single:
            available = [f for f in mapped_fields if f in df_data.columns]
            if not available:
                return pd.DataFrame()
            result = df_data[available]
            if len(result) > count:
                result = result.iloc[-count:]
            return result
        else:
            result = df_data
            if len(result) > count:
                result = result.iloc[-count:]
            return result

    # ------------------------------------------------------------------
    # get_security_info
    # ------------------------------------------------------------------
    def get_security_info(self, security):
        if self._stock_basic is None:
            self.get_all_securities()
        if security not in self._stock_basic.index:
            return None
        row = self._stock_basic.loc[security]
        return SecurityInfo(
            code=security,
            name=row.get('display_name', ''),
            display_name=row.get('display_name', ''),
            start_date=row.get('start_date', pd.NaT),
            end_date=row.get('end_date', pd.NaT),
            type='stock',
        )

    # ------------------------------------------------------------------
    # get_trade_days / get_all_trade_days
    # ------------------------------------------------------------------
    def get_trade_days(self, start, end):
        start_dt, end_dt = pd.to_datetime(start), pd.to_datetime(end)
        self._ensure_trade_days_loaded(start_dt.year, end_dt.year)
        return [d for d in self._all_trade_days if d >= start_dt and d <= end_dt]

    def get_all_trade_days(self):
        self._ensure_trade_days_loaded(2010, 2027)
        return list(self._all_trade_days)

    def _ensure_trade_days_loaded(self, start_year, end_year):
        if self._all_trade_days is not None:
            return
        self._all_trade_days = []
        for y in range(max(2010, start_year), min(2027, end_year + 1)):
            p = os.path.join(self.data_root, f'1d_stock/{y}.parquet')
            if os.path.exists(p):
                dates = pd.to_datetime(pd.read_parquet(p, columns=['date'])['date'].unique().astype(str))
                self._all_trade_days.extend(dates)
        self._all_trade_days = sorted(list(set(self._all_trade_days)))

    # ------------------------------------------------------------------
    # get_price — 原有的行情API，保留不动
    # ------------------------------------------------------------------
    def get_price(self, security, start_date=None, end_date=None, frequency='daily', fields=None, fq='pre', count=None, **kwargs):
        if self.compat is not None and hasattr(self.compat, "get_instrument_price_fallback"):
            fallback = self.compat.get_instrument_price_fallback(
                security,
                start_date=start_date,
                end_date=end_date,
            )
            if fallback is not None:
                return fallback

        is_single = isinstance(security, str)
        securities = [security] if is_single else list(security)
        local_secs = self._normalize(securities)
        target_dt = pd.to_datetime(end_date or start_date or datetime.now())
        target_year = target_dt.year

        default_fields = ['open', 'close', 'high', 'low', 'volume', 'money']
        if fields is None:
            fields_to_get = default_fields
        elif isinstance(fields, str):
            fields_to_get = [fields]
        else:
            fields_to_get = list(fields)

        all_index_files = frequency == 'daily' and all(
            os.path.exists(os.path.join(self.data_root, f'1d_index/{sec}.parquet'))
            for sec in local_secs
        )
        if not all_index_files:
            try:
                unit = '1d' if frequency in ('daily', '1d') else frequency
                end_dt = pd.to_datetime(end_date or start_date or datetime.now())
                def _normalize_history_columns(frame, field):
                    if frame is None or frame.empty or len(securities) != 1:
                        return frame
                    sec = securities[0]
                    if sec not in frame.columns and field in frame.columns and len(frame.columns) == 1:
                        return frame.rename(columns={field: sec})
                    return frame

                if self._should_bypass_history_fastpath(unit, fields_to_get, end_dt):
                    raise RuntimeError('history fastpath bypass requested by compat')

                if len(fields_to_get) == 1:
                    hd = self._history_cached(
                        count=count or 1,
                        unit=unit,
                        field=fields_to_get[0],
                        security_list=securities,
                        df=True,
                        fq=fq,
                        start_date=start_date,
                        end_date=end_dt,
                    )
                    if unit == '1d':
                        hd = self._apply_jq_daily_anomalies(hd, fields_to_get[0], securities, end_dt)
                    hd = _normalize_history_columns(hd, fields_to_get[0])
                    if hd.empty:
                        return pd.DataFrame()
                    hd.index.name = 'time'
                    if kwargs.get('panel') is False:
                        flat = hd.stack().reset_index()
                        flat.columns = ['time', 'code', fields_to_get[0]]
                        return flat
                    if is_single:
                        return hd.rename(columns={securities[0]: fields_to_get[0]})[[fields_to_get[0]]]
                    return hd

                non_paused_fields = [f for f in fields_to_get if f != 'paused']
                if is_single and len(non_paused_fields) > 1:
                    hd = self._history_cached(
                        count=count or 1,
                        unit=unit,
                        field=tuple(non_paused_fields),
                        security_list=securities,
                        df=True,
                        fq=fq,
                        start_date=start_date,
                        end_date=end_dt,
                    )
                    if unit == '1d':
                        for f in non_paused_fields:
                            hd = self._apply_jq_daily_anomalies(hd, f, securities, end_dt)
                    if hd.empty:
                        return pd.DataFrame()
                    hd.index.name = 'time'
                    if 'paused' in fields_to_get:
                        hd['paused'] = False
                    output = [f for f in fields_to_get if f in hd.columns]
                    if kwargs.get('panel') is False:
                        flat = hd[output].reset_index()
                        flat.insert(1, 'code', securities[0])
                        return flat
                    return hd[output]

                field_frames = []
                needs_paused = False
                for f in fields_to_get:
                    if f == 'paused':
                        needs_paused = True
                        continue
                    one = self._history_cached(
                        count=count or 1,
                        unit=unit,
                        field=f,
                        security_list=securities,
                        df=True,
                        fq=fq,
                        start_date=start_date,
                        end_date=end_dt,
                    )
                    if unit == '1d':
                        one = self._apply_jq_daily_anomalies(one, f, securities, end_dt)
                    one = _normalize_history_columns(one, f)
                    if one.empty:
                        continue
                    one.index.name = 'time'
                    field_frames.append((f, one))
                if needs_paused:
                    if field_frames:
                        idx = field_frames[0][1].index
                    else:
                        idx = self._history_cached(
                            count=count or 1,
                            unit=unit,
                            field='close',
                            security_list=securities,
                            df=True,
                            fq=fq,
                            start_date=start_date,
                            end_date=end_dt,
                        ).index
                    one = pd.DataFrame(False, index=idx, columns=[securities[0]] if is_single else securities)
                    one.index.name = 'time'
                    field_frames.append(('paused', one))
                if not field_frames:
                    return pd.DataFrame()
                if kwargs.get('panel') is False:
                    flats = []
                    for f, one in field_frames:
                        flat = one.stack().reset_index()
                        flat.columns = ['time', 'code', f]
                        flats.append(flat)
                    out = flats[0]
                    for flat in flats[1:]:
                        out = out.merge(flat, on=['time', 'code'], how='outer')
                    return out.sort_values(['time', 'code']).reset_index(drop=True)
                if is_single:
                    data = {}
                    for f, frame in field_frames:
                        if securities[0] in frame.columns:
                            data[f] = frame[securities[0]]
                        elif f in frame.columns:
                            data[f] = frame[f]
                        elif len(frame.columns) == 1:
                            data[f] = frame.iloc[:, 0]
                    return pd.DataFrame(data, index=field_frames[0][1].index)
                out = pd.concat({f: frame for f, frame in field_frames}, axis=1)
                return out
            except Exception:
                pass

        if frequency == 'daily':
            index_frames = []
            all_index_files = True
            for sec, local_sec in zip(securities, local_secs):
                index_path = os.path.join(self.data_root, f'1d_index/{local_sec}.parquet')
                if not os.path.exists(index_path):
                    all_index_files = False
                    break
                df_idx = pd.read_parquet(index_path)
                if 'date' not in df_idx.columns:
                    all_index_files = False
                    break
                df_idx = df_idx.copy()
                df_idx['date'] = df_idx['date'].astype(str)
                end_dt = pd.to_datetime(end_date or start_date)
                if count:
                    target_dates = [d.strftime('%Y%m%d') for d in self.get_trade_days("2010-01-01", end_dt)[-count:]]
                    df_idx = df_idx[df_idx['date'].isin(target_dates)]
                else:
                    start_dt = pd.to_datetime(start_date or end_date)
                    ds0, ds1 = start_dt.strftime('%Y%m%d'), end_dt.strftime('%Y%m%d')
                    df_idx = df_idx[(df_idx['date'] >= ds0) & (df_idx['date'] <= ds1)]
                if 'vol' in df_idx.columns:
                    df_idx['volume'] = df_idx['vol']
                if 'amount' in df_idx.columns:
                    df_idx['money'] = df_idx['amount']
                df_idx['code'] = sec
                df_idx['time'] = pd.to_datetime(df_idx['date'].astype(str))
                index_frames.append(df_idx)
            if all_index_files and index_frames:
                res_idx = pd.concat(index_frames, ignore_index=True)
                output_fields = [f for f in fields_to_get if f in res_idx.columns]
                if is_single:
                    return res_idx.set_index('time')[output_fields].sort_index()
                if len(output_fields) == 1:
                    return res_idx.pivot(index='time', columns='code', values=output_fields[0])
                return res_idx.pivot(index='time', columns='code', values=output_fields).sort_index(axis=1)

        if frequency in ('daily', '1d'):
            end_dt = pd.to_datetime(end_date or start_date)
            if count:
                all_dates = self.get_trade_days("2010-01-01", end_dt)
                target_dates = all_dates[-count:]
            else:
                target_dates = self.get_trade_days(pd.to_datetime(start_date or end_date), end_dt)
            years = sorted({pd.Timestamp(d).year for d in target_dates})
            frames = []
            for year in years:
                self._load_year_to_records(year)
                df_year = self._price_records.get(year)
                if df_year is not None:
                    frames.append(df_year)
            if not frames:
                return pd.DataFrame()
            df_year = frames[0] if len(frames) == 1 else pd.concat(frames, ignore_index=True)
            date_strs = [d.strftime('%Y%m%d') for d in target_dates]
            res_df = df_year[df_year['date'].isin(date_strs) & df_year['code'].isin(local_secs)]
            if res_df.empty:
                return pd.DataFrame()
            res_df = res_df.copy()
            if 'vol' in res_df.columns:
                res_df['volume'] = res_df['vol']
            if 'amount' in res_df.columns:
                res_df['money'] = res_df['amount']
            if any(f in fields_to_get for f in ['high_limit', 'low_limit', 'paused']):
                pc = res_df['pre_close'].astype(float)
                is_star_chi = res_df['code'].str.startswith(('300', '301', '688'))
                res_df['high_limit'] = np.where(is_star_chi, (pc * 1.20 + 0.000001).round(2), (pc * 1.10 + 0.000001).round(2))
                res_df['low_limit'] = np.where(is_star_chi, (pc * 0.80 + 0.000001).round(2), (pc * 0.90 + 0.000001).round(2))
                res_df['paused'] = (res_df['vol'].astype(float) == 0)
            res_df['code'] = self._denormalize(res_df['code'].tolist())
            res_df['time'] = pd.to_datetime(res_df['date'].astype(str))
            res_df = res_df.sort_values(['code', 'time']).reset_index(drop=True)
            output_fields = [f for f in fields_to_get if f in res_df.columns]
            res_df = self._apply_jq_daily_anomalies_records(res_df, output_fields, securities, end_dt)
            if kwargs.get('panel') is False:
                return res_df[['time', 'code'] + output_fields].sort_values(['time', 'code']).reset_index(drop=True)
            if is_single:
                return res_df.set_index('time')[output_fields].sort_index()
            else:
                if len(output_fields) == 1:
                    return res_df.pivot(index='time', columns='code', values=output_fields[0])
                pivoted = res_df.pivot(index='time', columns='code', values=output_fields)
                return pivoted.sort_index(axis=1)

        elif frequency == '1m':
            end_dt = pd.to_datetime(end_date or start_date)
            res_list = []
            daily_limits = pd.DataFrame()
            if any(f in fields_to_get for f in ['high_limit', 'low_limit']):
                try:
                    daily_limits = self.get_price(
                        security if is_single else securities,
                        end_date=end_dt,
                        frequency='daily',
                        count=1,
                        fields=['high_limit', 'low_limit'],
                        fq=fq,
                    )
                except Exception:
                    daily_limits = pd.DataFrame()
            for i, s_local in enumerate(local_secs):
                df_min = self._load_minute_data(s_local, target_year)
                if df_min is None or df_min.empty:
                    continue
                mask = df_min['time'] <= end_dt
                sub_df = df_min[mask].tail(count if count else 1).copy()
                if sub_df.empty:
                    continue
                if 'vol' in sub_df.columns:
                    sub_df['volume'] = sub_df['vol']
                if 'amount' in sub_df.columns:
                    sub_df['money'] = sub_df['amount']
                if not daily_limits.empty:
                    try:
                        if isinstance(daily_limits.columns, pd.MultiIndex):
                            daily_row = daily_limits.xs(securities[i], axis=1, level=1).iloc[0]
                        elif is_single:
                            daily_row = daily_limits.iloc[0]
                        elif securities[i] in daily_limits.columns:
                            daily_row = daily_limits[securities[i]].iloc[0]
                        else:
                            daily_row = None
                        if daily_row is not None:
                            sub_df['high_limit'] = daily_row.get('high_limit', np.nan)
                            sub_df['low_limit'] = daily_row.get('low_limit', np.nan)
                    except Exception:
                        pass
                sub_df['code'] = securities[i]
                res_list.append(sub_df)
            if not res_list:
                return pd.DataFrame()
            res_df = pd.concat(res_list)
            output_fields = [f for f in fields_to_get if f in res_df.columns]
            if kwargs.get('panel') is False:
                return res_df[['time', 'code'] + output_fields].sort_values(['time', 'code']).reset_index(drop=True)
            if is_single:
                return res_df.set_index('time')[output_fields].sort_index()
            else:
                if len(output_fields) == 1:
                    return res_df.pivot(index='time', columns='code', values=output_fields[0])
                pivoted = res_df.pivot(index='time', columns='code', values=output_fields)
                return pivoted.sort_index(axis=1)
        return pd.DataFrame()

    def get_valuation(self, security, start_date=None, end_date=None, fields=None, count=None):
        securities = security if isinstance(security, (list, tuple, pd.Index, pd.Series)) else [security]
        dt = pd.to_datetime(end_date or start_date or datetime.now())
        include_income = fields is None or any(f == 'operating_revenue' for f in fields)
        df = self.get_fundamentals(None, date=dt) if include_income else self._get_indicator_day(dt, include_income=False)
        if df.empty:
            return df
        if securities:
            df = df[df['code'].isin(list(securities))].copy()
        if fields is not None:
            requested = []
            for f in fields:
                mapped = 'turnover_rate' if f == 'turnover_ratio' else f
                if mapped not in requested:
                    requested.append(mapped)
            keep = ['code'] + [f for f in requested if f in df.columns and f != 'code']
            df = df[keep]
            if 'turnover_ratio' in fields and 'turnover_rate' in df.columns:
                df['turnover_ratio'] = df['turnover_rate']
                if 'turnover_rate' not in fields:
                    df = df.drop(columns=['turnover_rate'])
        return df

    def get_call_auction(self, security, start_date=None, end_date=None, fields=None):
        securities = security if isinstance(security, (list, tuple, pd.Index, pd.Series)) else [security]
        is_single = isinstance(security, str)
        start_dt = pd.to_datetime(start_date or end_date)
        end_dt = pd.to_datetime(end_date or start_date)
        fields_key = None if fields is None else tuple(fields)
        key = (tuple(securities), str(start_dt.normalize()), str(end_dt.normalize()), fields_key, is_single)
        cached = self._call_auction_query_cache.get(key)
        if cached is not None:
            if isinstance(cached, dict):
                return {k: v.copy() for k, v in cached.items()}
            return cached.copy()
        if start_dt.normalize() == end_dt.normalize():
            df = self._get_call_auction_day(start_dt)
        else:
            years = range(start_dt.year, end_dt.year + 1)
            dfs = []
            for year in years:
                df_year = self._load_call_auction_year(year)
                if df_year is not None and not df_year.empty:
                    dfs.append(df_year)
            if not dfs:
                return pd.DataFrame()
            df = pd.concat(dfs, ignore_index=True)
            if '_date_dt' in df.columns:
                df = df[(df['_date_dt'] >= start_dt.normalize()) & (df['_date_dt'] <= end_dt.normalize())].copy()
        if df is None or df.empty:
            return pd.DataFrame()
        if 'code' in df.columns:
            df = df[df['code'].isin(list(securities))].copy()
        if '_date_dt' in df.columns and self.compat is not None and hasattr(self.compat, "apply_call_auction_overrides"):
            df = self.compat.apply_call_auction_overrides(df)
        drop_cols = [c for c in ['_date_dt', '_date_int'] if c in df.columns]
        if drop_cols:
            df = df.drop(columns=drop_cols)
        if fields is not None:
            keep = [f for f in fields if f in df.columns]
            if 'code' in df.columns and 'code' not in keep:
                keep.insert(0, 'code')
            df = df[keep]
        out = {s: pd.DataFrame() for s in securities}
        if not df.empty and 'code' in df.columns:
            for code, sub in df.groupby('code'):
                out[code] = sub.reset_index(drop=True).copy()
        result = out.get(security, pd.DataFrame()) if is_single else out
        if len(self._call_auction_query_cache) > 2048:
            self._call_auction_query_cache.pop(next(iter(self._call_auction_query_cache)))
        if isinstance(result, dict):
            self._call_auction_query_cache[key] = {k: v.copy() for k, v in result.items()}
            return {k: v.copy() for k, v in result.items()}
        self._call_auction_query_cache[key] = result.copy()
        return result.copy()

    def _load_call_auction_year(self, year):
        if year in self._call_auction_cache:
            return self._call_auction_cache[year]
        path = os.path.join(self.data_root, f'1d_feature/call_auction/{year}.parquet')
        if not os.path.exists(path):
            self._call_auction_cache[year] = pd.DataFrame()
            return self._call_auction_cache[year]
        df = pd.read_parquet(path)
        df = df.copy()
        if 'code' in df.columns:
            df['code'] = self._denormalize(df['code'].astype(str).tolist())
        if 'date' in df.columns:
            df['_date_dt'] = pd.to_datetime(df['date'].astype(str))
            df['_date_int'] = df['_date_dt'].dt.strftime('%Y%m%d').astype(int)
        self._call_auction_cache[year] = df
        return df

    def _get_call_auction_day(self, day):
        day = pd.to_datetime(day).normalize()
        key = day.strftime('%Y%m%d')
        cached = self._call_auction_day_cache.get(key)
        if cached is not None:
            return cached.copy()
        out = None
        if self.compat is not None and hasattr(self.compat, "load_project_call_auction_day"):
            out = self.compat.load_project_call_auction_day(self, day)
        if out is None:
            df_year = self._load_call_auction_year(day.year)
            if df_year is None or df_year.empty or '_date_int' not in df_year.columns:
                out = pd.DataFrame()
            else:
                out = df_year[df_year['_date_int'] == int(key)].copy()
        if len(self._call_auction_day_cache) > 512:
            self._call_auction_day_cache.pop(next(iter(self._call_auction_day_cache)))
        self._call_auction_day_cache[key] = out
        return out.copy()

    def _load_project_first_seal_year(self, year):
        if self.compat is not None and hasattr(self.compat, "load_first_seal_year"):
            return self.compat.load_first_seal_year(year)
        return None

    def get_project_board_snapshot(self, date):
        if self.compat is not None and hasattr(self.compat, "get_project_board_snapshot"):
            return self.compat.get_project_board_snapshot(date)
        return pd.DataFrame()

    def get_project_master_prepare_index(self, date):
        if self.compat is not None and hasattr(self.compat, "get_project_master_prepare_index"):
            return self.compat.get_project_master_prepare_index(date)
        return pd.DataFrame()

    def get_project_auction_yiqian_prepare(self, date):
        if self.compat is not None and hasattr(self.compat, "get_project_auction_yiqian_prepare"):
            return self.compat.get_project_auction_yiqian_prepare(date)
        return None

    def get_batch_sealing_points(self, securities, date):
        securities = securities if isinstance(securities, (list, tuple, pd.Index, pd.Series)) else [securities]
        clean_secs = [s[0] if isinstance(s, tuple) else s for s in securities]
        day = pd.to_datetime(date)
        day_key = day.strftime('%Y%m%d')
        result = {}
        if not clean_secs:
            return result
        missing_secs = []
        project_seals = self._load_project_first_seal_year(day.year)
        for sec in clean_secs:
            cache_key = (day_key, sec)
            override = (
                self.compat.get_tail_seal_override(day_key, sec)
                if self.compat is not None and hasattr(self.compat, "get_tail_seal_override")
                else None
            )
            if override is not None:
                result[sec] = override
                self._sealing_points_cache[cache_key] = result[sec]
            elif cache_key in self._sealing_points_cache:
                result[sec] = self._sealing_points_cache[cache_key]
            elif project_seals is not None and cache_key in project_seals:
                result[sec] = project_seals[cache_key]
                self._sealing_points_cache[cache_key] = result[sec]
            else:
                missing_secs.append(sec)
        if not missing_secs:
            return result
        try:
            limits = self.get_price(
                missing_secs,
                end_date=day,
                frequency='daily',
                count=1,
                fields=['high_limit'],
                fq=None,
                panel=False,
            )
        except Exception:
            limits = pd.DataFrame()

        minute_closes = pd.DataFrame()
        try:
            minute_closes = self._history_cached(
                count=240,
                unit='1m',
                field='close',
                security_list=missing_secs,
                df=True,
                fq=None,
                end_date=day.replace(hour=15, minute=0),
            )
        except Exception:
            minute_closes = pd.DataFrame()

        for sec in missing_secs:
            cache_key = (day_key, sec)
            try:
                if cache_key in jq_tail_seal_anomalies:
                    first_hit = jq_tail_seal_anomalies[cache_key]
                    self._sealing_points_cache[cache_key] = first_hit
                    result[sec] = first_hit
                    continue
                high_limit = None
                if not limits.empty:
                    if 'code' in limits.columns and 'high_limit' in limits.columns:
                        sub = limits[limits['code'] == sec]
                        if not sub.empty:
                            high_limit = sub['high_limit'].iloc[-1]
                    elif sec in limits.columns:
                        high_limit = limits[sec].iloc[-1]
                    elif 'high_limit' in limits.columns and len(clean_secs) == 1:
                        high_limit = limits['high_limit'].iloc[-1]
                    elif len(limits.columns) == 1:
                        high_limit = limits.iloc[-1, 0]
                if high_limit is None or pd.isna(high_limit) or high_limit <= 0:
                    self._sealing_points_cache[cache_key] = None
                    result[sec] = None
                    continue
                if minute_closes.empty:
                    self._sealing_points_cache[cache_key] = None
                    result[sec] = None
                    continue
                if sec in minute_closes.columns:
                    series = minute_closes[sec]
                elif 'close' in minute_closes.columns and len(missing_secs) == 1:
                    series = minute_closes['close']
                elif len(minute_closes.columns) == 1:
                    series = minute_closes.iloc[:, 0]
                else:
                    self._sealing_points_cache[cache_key] = None
                    result[sec] = None
                    continue
                hit = series[series >= float(high_limit) - 1e-6]
                first_hit = hit.index[0] if not hit.empty else None
                self._sealing_points_cache[cache_key] = first_hit
                result[sec] = first_hit
            except Exception:
                self._sealing_points_cache[cache_key] = None
                result[sec] = None
        return result

    def _load_minute_data(self, code_local, year):
        key = f"{code_local}_{year}"
        if key in self._minute_cache:
            return self._minute_cache[key]
        for base in ["1m_stock", "1m_stock_v2"]:
            path = os.path.join(self.data_root, f"{base}/{code_local}/{year}.parquet")
            if os.path.exists(path):
                df_tmp = pd.read_parquet(path)
                if 'trade_time' in df_tmp.columns:
                    df_tmp = df_tmp.rename(columns={'trade_time': 'time'})
                elif 'datetime' in df_tmp.columns:
                    df_tmp = df_tmp.rename(columns={'datetime': 'time'})
                df_tmp['time'] = pd.to_datetime(df_tmp['time'])
                cols = [c for c in ['time', 'open', 'high', 'low', 'close', 'vol', 'amount'] if c in df_tmp.columns]
                self._minute_cache[key] = df_tmp[cols]
                return self._minute_cache[key]
        return None

    def _load_year_to_records(self, year):
        if year in self._price_records:
            return
        path = os.path.join(self.data_root, f'1d_stock/{year}.parquet')
        if not os.path.exists(path):
            return
        df_tmp = pd.read_parquet(path)
        df_tmp['date'] = df_tmp['date'].astype(str)
        self._price_records[year] = df_tmp

    def get_all_securities(self, types=['stock'], date=None):
        types_key = tuple(types) if isinstance(types, (list, tuple, pd.Index, pd.Series)) else (types,)
        date_key = pd.to_datetime(date).strftime('%Y-%m-%d') if date else None
        cache_key = (types_key, date_key)
        cached = self._all_securities_cache.get(cache_key)
        if cached is not None:
            out = cached.copy()
            if date:
                out = self._apply_jq_security_name_overrides(out, date)
            return out.copy()

        if self._stock_basic is None:
            basic_path = os.path.join(self.data_root, 'stock_basic.parquet')
            if not os.path.exists(basic_path):
                basic_path = os.path.join(self.data_root, 'metadata/stock_basic.parquet')
            self._stock_basic = pd.read_parquet(basic_path)
            self._stock_basic['start_date'] = pd.to_datetime(self._stock_basic['list_date'].astype(str))
            self._stock_basic['end_date'] = pd.to_datetime(self._stock_basic['delist_date'].astype(str), errors='coerce')
            self._stock_basic.index = self._denormalize(self._stock_basic['code'].tolist())
            if 'name' in self._stock_basic.columns:
                self._stock_basic = self._stock_basic.rename(columns={'name': 'display_name'})
            if self.compat is not None and hasattr(self.compat, "get_security_start_date_override"):
                for code in self._stock_basic.index:
                    start_date = self.compat.get_security_start_date_override(code)
                    if start_date is not None:
                        self._stock_basic.loc[code, 'start_date'] = start_date

        df_tmp = self._stock_basic.copy()
        if date:
            dt = pd.to_datetime(date)
            df_tmp = df_tmp[(df_tmp['start_date'] <= dt) & ((df_tmp['end_date'].isna()) | (df_tmp['end_date'] >= dt))]
        out = df_tmp[['display_name', 'start_date']].copy()
        if date and 'end_date' in df_tmp.columns:
            active_before_delist = df_tmp['end_date'].notna() & (pd.to_datetime(df_tmp['end_date']) > dt)
            if active_before_delist.any():
                # Temporary PIT-name guard: stock_basic contains final names such
                # as delisting labels.  Strip only future delisting markers here;
                # replace this with a real name-history table when available.
                cleaned = out.loc[active_before_delist, 'display_name'].astype(str)
                cleaned = cleaned.str.replace(r'^\s*退市', '', regex=True)
                cleaned = cleaned.str.replace(r'^\s*退(?=\S)', '', regex=True)
                cleaned = cleaned.str.replace(r'[\(（]退[\)）]\s*$', '', regex=True)
                cleaned = cleaned.str.replace(r'退\s*$', '', regex=True)
                out.loc[active_before_delist, 'display_name'] = cleaned
            out = self._apply_jq_security_name_overrides(out, date)
        out['start_date'] = pd.to_datetime(out['start_date'], errors='coerce').dt.date
        if len(self._all_securities_cache) > 2048:
            self._all_securities_cache.pop(next(iter(self._all_securities_cache)))
        self._all_securities_cache[cache_key] = out
        return out.copy()

    def get_extras(self, label, security, start_date=None, end_date=None):
        securities = list(security) if isinstance(security, (list, tuple, pd.Index, pd.Series)) else [security]
        ds_dt = pd.to_datetime(start_date)
        ds = ds_dt.strftime('%Y%m%d')
        if self._stock_basic is None:
            self.get_all_securities()
        st_codes = self._st_codes_on(ds_dt)
        res_dict = {}
        for s in securities:
            is_st = s in st_codes
            if self.compat is not None and hasattr(self.compat, "adjust_extras_is_st"):
                is_st = self.compat.adjust_extras_is_st(self, s, ds_dt, is_st)
            res_dict[s] = is_st
        return JQMockResult(res_dict)

    def get_industry_stocks(self, industry_code, date=None):
        try:
            p = os.path.join(self.data_root, 'metadata/industry_member.parquet')
            df = pd.read_parquet(p)
            if 'industry_code' not in df.columns:
                return []
            mask = df['industry_code'] == industry_code
            if date is not None and 'in_date' in df.columns:
                dt = pd.to_datetime(date)
                in_date = pd.to_datetime(df['in_date'], errors='coerce')
                out_date = pd.to_datetime(df.get('out_date'), errors='coerce') if 'out_date' in df.columns else pd.Series(pd.NaT, index=df.index)
                mask &= (in_date <= dt) & (out_date.isna() | (out_date > dt))
            codes = df.loc[mask, 'code'].dropna().astype(str).tolist()
            return self._denormalize(codes)
        except Exception:
            return []

    def get_index_stocks(self, index_symbol, date=None):
        return []

    def get_billboard_list(self, stock_list=None, end_date=None, count=1, start_date=None, **kwargs):
        end_dt = pd.to_datetime(end_date or start_date or datetime.now())
        if start_date is not None:
            start_dt = pd.to_datetime(start_date)
        else:
            trade_days = self.get_trade_days(end_dt - pd.Timedelta(days=max(20, int(count or 1) * 5)), end_dt)
            start_dt = pd.to_datetime(trade_days[-int(count or 1)]) if trade_days else end_dt
        try:
            df = hdata_reader.load_billboard(start_dt.strftime('%Y%m%d'), end_dt.strftime('%Y%m%d'))
        except Exception:
            return pd.DataFrame()
        if df.empty:
            return df
        df = df.copy()
        if 'code' in df.columns:
            df['code'] = self._denormalize(df['code'].astype(str).tolist())
        if 'date' in df.columns and 'code' in df.columns:
            if self.compat is not None and hasattr(self.compat, "filter_billboard_rows"):
                df = self.compat.filter_billboard_rows(df)
        if stock_list is not None and 'code' in df.columns:
            stocks = stock_list if isinstance(stock_list, (list, tuple, pd.Index, pd.Series)) else [stock_list]
            df = df[df['code'].isin(list(stocks))].copy()
        if 'date' in df.columns:
            df['time'] = pd.to_datetime(df['date'].astype(str), format='%Y%m%d', errors='coerce')
        return df.reset_index(drop=True)

    def get_fundamentals(self, query_obj, date=None):
        return self._get_indicator_day(date, include_income=True)

    def _get_indicator_day(self, date=None, include_income=True):
        dt_str = pd.to_datetime(date).strftime('%Y%m%d')
        cache_key = (dt_str, bool(include_income))
        if cache_key in self._indicator_cache:
            return self._indicator_cache[cache_key]
        base_key = (dt_str, False)
        if include_income and base_key in self._indicator_cache:
            df_tmp = self._indicator_cache[base_key].copy()
        else:
            df_tmp = self._load_indicator_day_base(dt_str)
            self._indicator_cache[base_key] = df_tmp
        if include_income:
            df_tmp = df_tmp.copy()
            income = self._get_latest_income(pd.to_datetime(date))
            if not income.empty:
                df_tmp = df_tmp.merge(income, on='code', how='left')
        self._indicator_cache[cache_key] = df_tmp
        return df_tmp

    def _load_indicator_day_base(self, dt_str):
        path = os.path.join(self.data_root, f'基本面数据/stock_indicator/{dt_str}.parquet')
        if os.path.exists(path):
            df_tmp = pd.read_parquet(path)
        else:
            if not hasattr(self, '_yearly_indicator_cache'):
                self._yearly_indicator_cache = {}
            year_str = dt_str[:4]
            if year_str not in self._yearly_indicator_cache:
                year_path = os.path.join(self.data_root, f'1d_feature/stock_indicator/{year_str}.parquet')
                if not os.path.exists(year_path):
                    df_year = pd.DataFrame()
                else:
                    df_year = pd.read_parquet(year_path)
                    if not df_year.empty and 'date' in df_year.columns:
                        df_year['date_str'] = df_year['date'].astype(str)
                self._yearly_indicator_cache[year_str] = df_year
            
            df_year = self._yearly_indicator_cache[year_str]
            if df_year.empty:
                return pd.DataFrame(columns=['code', 'market_cap'])
            df_tmp = df_year[df_year['date_str'] == dt_str].copy()
            
        df_tmp['market_cap'] = df_tmp['total_mv'] / 1e8
        if 'circ_mv' in df_tmp.columns:
            df_tmp['circulating_market_cap'] = df_tmp['circ_mv'] / 1e8
        if 'turnover_rate' in df_tmp.columns and 'turnover_ratio' not in df_tmp.columns:
            df_tmp['turnover_ratio'] = df_tmp['turnover_rate']
        df_tmp['code'] = self._denormalize(df_tmp['code'].tolist())
        return df_tmp

    def _get_latest_income(self, date):
        if self._income_cache is None:
            path = os.path.join(self.data_root, 'fundamental', 'income.parquet')
            if not os.path.exists(path):
                self._income_cache = pd.DataFrame(columns=['code', 'ann_date', 'operating_revenue'])
            else:
                cols = ['code', 'f_ann_date', 'end_date', 'revenue']
                df = pd.read_parquet(path, columns=cols)
                df = df.rename(columns={'f_ann_date': 'ann_date', 'revenue': 'operating_revenue'})
                df['ann_date'] = pd.to_datetime(df['ann_date'].astype(str), errors='coerce')
                df['end_date'] = pd.to_datetime(df['end_date'].astype(str), errors='coerce')
                df['code'] = self._denormalize(df['code'].astype(str).tolist())
                self._income_cache = df.dropna(subset=['ann_date'])
        df = self._income_cache
        if df.empty:
            return pd.DataFrame(columns=['code', 'operating_revenue'])
        visible = df[df['ann_date'] <= pd.to_datetime(date)].copy()
        if visible.empty:
            return pd.DataFrame(columns=['code', 'operating_revenue'])
        visible = visible.sort_values(['code', 'ann_date', 'end_date'])
        return visible.groupby('code', as_index=False).tail(1)[['code', 'operating_revenue']]


